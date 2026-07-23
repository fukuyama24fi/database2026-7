from data.departments import DEPARTMENTS
from data.skills import skill_map
from db.read import get_active_decisions, get_department_members_by_skill
from db.write import (
    assign_member_to_room,
    create_room,
    refresh_active_decisions,
    update_room_status,
    update_short_summary,
)
from meeting.department_meeting import department_discussion_loop
from meeting.partial_rollback import apply_partial_rollback, apply_turn_rollback
from memory.find_decisions_from_log import find_decisions_from_log
from memory.make_summary import polish_final_summary
from roles.pm import pm_assign_member_roles
from roles.manager import manager_review_outputs
from workspace.io import (
    ensure_room_workspace,
    other_dept_outputs_text,
    read_all_outputs,
    read_design_doc,
    read_workspace_text,
    write_d_list,
    write_team_memo,
    write_workspace_text,
)

#通常の部署議論ターン数(延長前)
BASE_TURNS = 3
#部長差し戻し後に追加で議論できるターン数
EXTENSION_TURNS = 3
#部長が差し戻しできる最大回数(3回目は強制承認)
MAX_REVISIONS = 2
#部分修正(partial)モードで追加議論するターン数
PARTIAL_FIX_TURNS = 2


def _next_turn_number(turn_summaries):
    #次に始める議論ターン番号を計算する(ロールバック再開時に使う)
    if not turn_summaries:
        return 1
    return turn_summaries[-1]["turn_number"] + 1


def _restore_members_for_room(room_id, department_id, resume_members):
    #ロールバック再開時、保存済みメンバーが無ければDBから再取得する
    if resume_members:
        return resume_members
    required_skills = skill_map.get(department_id, [])
    return get_department_members_by_skill(
        department_id, required_skills, count=2, exclude_member_ids=[]
    )


def _format_revision_with_decisions(revision_report, affected_decision_ids):
    #revision_reportに「どのdecision_idだけ直すか」を追記する
    if not affected_decision_ids:
        return revision_report
    ids_text = ", ".join(affected_decision_ids)
    return f"""{revision_report}

【修正対象D-list】
decision_id: {ids_text}
上記決定のみ修正・差し替えしてください。他のactive D-listは変更しないでください。"""


def run_department_room(
    project_id,
    department_id,
    dept_task,
    room_index,
    reopen_state=None,
    peer_results=None,
):
    """1部署分のルーム。reopen_state.mode=partial|turn でロールバック再開。"""
    department_name = DEPARTMENTS[department_id]
    room_id = reopen_state["room_id"] if reopen_state else f"room_{project_id}_{room_index}"
    other_dept_info = other_dept_outputs_text(peer_results or [], current_room_id=room_id)

    if reopen_state:
        members = _restore_members_for_room(room_id, department_id, reopen_state.get("members"))
        talk_log = reopen_state.get("talk_log", [])
        turn_summaries = reopen_state.get("turn_summaries", [])
        revision_report = reopen_state.get("revision_report")
        retry_count = reopen_state.get("retry_count", 0)
        affected_ids = reopen_state.get("affected_decision_ids") or []
        mode = reopen_state.get("mode", "turn")

        if mode == "partial":
            apply_partial_rollback(room_id, affected_ids, revision_report or "")
            revision_report = _format_revision_with_decisions(revision_report, affected_ids)
            update_room_status(room_id, "partial_rollback", retry_count=retry_count)
            print(f"[{department_id}] 部分修正開始 targets={affected_ids}")
        else:
            rollback_from = reopen_state.get("rollback_from_turn", 1)
            apply_turn_rollback(room_id, rollback_from, revision_report or "")
            revision_report = _format_revision_with_decisions(revision_report, affected_ids)
            update_room_status(room_id, "turn_rollback", retry_count=retry_count)
            print(f"[{department_id}] Turnロールバック再開 turn{rollback_from}〜")
    else:
        create_room(room_id, project_id, department_name, dept_task)
        ensure_room_workspace(room_id)
        members = get_department_members_by_skill(
            department_id, skill_map.get(department_id, []), count=2, exclude_member_ids=[]
        )
        if len(members) < 2:
            print(f"[{department_id}] メンバーが2人未満のためスキップします")
            return None
        for member in members:
            assign_member_to_room(room_id, member["member_id"], "initial", turn=0)
        pm_assign_member_roles(department_id, dept_task, members)
        write_team_memo(room_id, members)
        talk_log = []
        turn_summaries = []
        revision_report = None
        retry_count = 0
        mode = None

    manager_review_count = 0
    final_status = "approved"
    concerns_report = None

    if reopen_state and reopen_state.get("mode") == "partial":
        start_turn_number = _next_turn_number(turn_summaries)
        loop_result = department_discussion_loop(
            room_id,
            dept_task,
            members,
            max_turns=PARTIAL_FIX_TURNS,
            department_id=department_id,
            reference_context=revision_report,
            start_turn_number=start_turn_number,
            accumulated_talk_log=talk_log,
            accumulated_turn_summaries=turn_summaries,
            other_dept_info=other_dept_info,
        )
        talk_log = loop_result["talk_log"]
        turn_summaries = loop_result["turn_summaries"]
        last_turn = turn_summaries[-1]["turn_number"] if turn_summaries else start_turn_number
        extracted = find_decisions_from_log(
            department_id, dept_task, talk_log, design_doc=read_design_doc(room_id)
        )
        refresh_active_decisions(
            room_id, department_name, extracted, last_turn, scope_anchor=department_id
        )
        active = get_active_decisions(room_id)
        write_d_list(room_id, active, skip_if_empty=False)
        summary = polish_final_summary(dept_task, turn_summaries)
        update_short_summary(room_id, summary)
        update_room_status(room_id, "approved", retry_count=retry_count)
        return _build_room_result(
            room_id, department_id, department_name, dept_task,
            active, "approved", summary, talk_log, turn_summaries,
            members, retry_count, concerns_report=None,
        )

    while True:
        segment_max = BASE_TURNS if retry_count == 0 else EXTENSION_TURNS
        start_turn_number = _next_turn_number(turn_summaries)

        print(
            f"[{department_id}] 議論ブロック開始 "
            f"(retry_count={retry_count}, 最大{segment_max}T, turn{start_turn_number}〜)"
        )

        loop_result = department_discussion_loop(
            room_id,
            dept_task,
            members,
            max_turns=segment_max,
            department_id=department_id,
            reference_context=revision_report,
            start_turn_number=start_turn_number,
            accumulated_talk_log=talk_log,
            accumulated_turn_summaries=turn_summaries,
            other_dept_info=other_dept_info,
        )
        talk_log = loop_result["talk_log"]
        turn_summaries = loop_result["turn_summaries"]
        last_turn = turn_summaries[-1]["turn_number"] if turn_summaries else start_turn_number - 1

        extracted = find_decisions_from_log(
            department_id, dept_task, talk_log, design_doc=read_design_doc(room_id)
        )
        refresh_active_decisions(
            room_id, department_name, extracted, last_turn, scope_anchor=department_id
        )
        active = get_active_decisions(room_id)
        d_list_text = write_d_list(room_id, active)
        summary_for_review = polish_final_summary(dept_task, turn_summaries)
        outputs_text = read_all_outputs(room_id)

        manager_review_count += 1
        is_final_review = manager_review_count == 3
        review = manager_review_outputs(
            department_id,
            dept_task,
            d_list_text,
            summary_for_review,
            outputs_text,
            manager_review_count,
            is_final_review=is_final_review,
        )
        print(f"[部長検収] verdict={review.get('verdict')} - {review.get('reason')}")

        if is_final_review:
            concerns_text = review.get("concerns") or ""
            if concerns_text:
                concerns_report = concerns_text
                write_workspace_text(room_id, "concerns_report.txt", concerns_report)
                final_status = "forced_approved"
            else:
                final_status = "approved"
            break

        if review.get("verdict") == "approved":
            final_status = "approved"
            break

        revision_report = review.get("revision_report") or review.get("reason") or ""
        write_workspace_text(room_id, "revision_report.txt", revision_report)
        retry_count += 1
        update_room_status(room_id, "revision", retry_count=retry_count)
        if retry_count > MAX_REVISIONS:
            break

    summary = polish_final_summary(dept_task, turn_summaries)
    update_short_summary(room_id, summary)
    update_room_status(room_id, final_status, retry_count=retry_count)

    extracted = find_decisions_from_log(
        department_id, dept_task, talk_log, design_doc=read_design_doc(room_id)
    )
    last_turn = turn_summaries[-1]["turn_number"] if turn_summaries else 1
    refresh_active_decisions(
        room_id, department_name, extracted, last_turn, scope_anchor=department_id
    )
    active = get_active_decisions(room_id)
    write_d_list(room_id, active, skip_if_empty=False)

    return _build_room_result(
        room_id, department_id, department_name, dept_task,
        active, final_status, summary, talk_log, turn_summaries,
        members, retry_count, concerns_report,
    )


def _build_room_result(
    room_id, department_id, department_name, dept_task,
    decisions, final_status, summary, talk_log, turn_summaries,
    members, retry_count, concerns_report,
):
    #部署ルーム1件分の結果辞書を組み立てる(run_project/CQOが読む形式)
    return {
        "room_id": room_id,
        "department_id": department_id,
        "department_name": department_name,
        "dept_task": dept_task,
        "decisions": decisions,
        "status": final_status,
        "outputs_text": read_all_outputs(room_id),
        "concerns_report": concerns_report or read_workspace_text(room_id, "concerns_report.txt"),
        "short_summary": summary,
        "talk_log": talk_log,
        "turn_summaries": turn_summaries,
        "members": members,
        "retry_count": retry_count,
        "is_suspicious": final_status == "forced_approved",
    }
