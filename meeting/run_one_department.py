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
from meeting.surgical_rollback import apply_surgical_rollback, apply_turn_rollback
from memory.extract_decisions import extract_decisions
from memory.make_summary import polish_final_summary
from roles.pm import pm_assign_member_roles
from roles.manager import manager_review_deliverables
from workspace.io import (
    build_peer_deliverables_context,
    ensure_room_workspace,
    read_deliverables_text,
    read_spec_text,
    read_workspace_text,
    write_provisional_d_list,
    write_team_memo,
    write_workspace_text,
)

BASE_TURNS = 3
EXTENSION_TURNS = 3
MAX_REVISIONS = 2
SURGICAL_REVISION_TURNS = 2  #変更: surgical差し戻し時の追加議論ターン数


def _next_turn_number(turn_summaries):
    if not turn_summaries:
        return 1
    return turn_summaries[-1]["turn_number"] + 1


def _restore_members_for_room(room_id, department_id, resume_members):
    if resume_members:
        return resume_members
    required_skills = skill_map.get(department_id, [])
    return get_department_members_by_skill(
        department_id, required_skills, count=2, exclude_member_ids=[]
    )


def _format_revision_with_decisions(revision_report, affected_decision_ids):
    #変更: メンバーへ影響decision_idを明示したrevision_reportを渡す
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
    sub_task_text,
    room_suffix,
    resume_state=None,
    peer_results=None,
):
    """1部署分のルーム。resume_state.mode=surgical|turn でロールバック再開。"""
    department_name = DEPARTMENTS[department_id]
    room_id = resume_state["room_id"] if resume_state else f"room_{project_id}_{room_suffix}"
    #変更: 先行部署の成果物/D-listを後続部署メンバーへ渡す
    peer_context = build_peer_deliverables_context(peer_results or [], current_room_id=room_id)

    if resume_state:
        members = _restore_members_for_room(room_id, department_id, resume_state.get("members"))
        full_transcript = resume_state.get("full_transcript", [])
        turn_summaries = resume_state.get("turn_summaries", [])
        revision_report = resume_state.get("revision_report")
        retry_count = resume_state.get("retry_count", 0)
        affected_ids = resume_state.get("affected_decision_ids") or []
        mode = resume_state.get("mode", "turn")

        if mode == "surgical":
            apply_surgical_rollback(room_id, affected_ids, revision_report or "")
            revision_report = _format_revision_with_decisions(revision_report, affected_ids)
            update_room_status(room_id, "surgical_rollback", retry_count=retry_count)
            print(f"[{department_id}] surgical修正開始 targets={affected_ids}")
        else:
            rollback_from = resume_state.get("rollback_from_turn", 1)
            apply_turn_rollback(room_id, rollback_from, revision_report or "")
            revision_report = _format_revision_with_decisions(revision_report, affected_ids)
            update_room_status(room_id, "turn_rollback", retry_count=retry_count)
            print(f"[{department_id}] Turnロールバック再開 turn{rollback_from}〜")
    else:
        create_room(room_id, project_id, department_name, sub_task_text)
        ensure_room_workspace(room_id)
        members = get_department_members_by_skill(
            department_id, skill_map.get(department_id, []), count=2, exclude_member_ids=[]
        )
        if len(members) < 2:
            print(f"[{department_id}] メンバーが2人未満のためスキップします")
            return None
        for member in members:
            assign_member_to_room(room_id, member["member_id"], "initial", turn=0)
        #変更: 初期メンバーにもPMが担当役割を割り当てる
        pm_assign_member_roles(department_id, sub_task_text, members)
        write_team_memo(room_id, members)
        full_transcript = []
        turn_summaries = []
        revision_report = None
        retry_count = 0
        mode = None

    manager_review_count = 0
    final_status = "approved"
    concerns_report = None

    if resume_state and resume_state.get("mode") == "surgical":
        #変更: surgicalは短い修正議論のみ(全ターン巻き戻ししない)
        start_turn_number = _next_turn_number(turn_summaries)
        loop_result = department_discussion_loop(
            room_id,
            sub_task_text,
            members,
            max_turns=SURGICAL_REVISION_TURNS,
            department_id=department_id,
            reference_context=revision_report,
            start_turn_number=start_turn_number,
            accumulated_transcript=full_transcript,
            accumulated_turn_summaries=turn_summaries,
            peer_context=peer_context,
        )
        full_transcript = loop_result["full_transcript"]
        turn_summaries = loop_result["turn_summaries"]
        last_turn = turn_summaries[-1]["turn_number"] if turn_summaries else start_turn_number
        extracted = extract_decisions(
            department_id, sub_task_text, full_transcript, spec_text=read_spec_text(room_id)
        )
        refresh_active_decisions(
            room_id, department_name, extracted, last_turn, scope_anchor=department_id
        )
        active = get_active_decisions(room_id)
        write_provisional_d_list(room_id, active, preserve_if_empty=False)
        summary = polish_final_summary(sub_task_text, turn_summaries)
        update_short_summary(room_id, summary)
        update_room_status(room_id, "approved", retry_count=retry_count)
        return _build_room_result(
            room_id, department_id, department_name, sub_task_text,
            active, "approved", summary, full_transcript, turn_summaries,
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
            sub_task_text,
            members,
            max_turns=segment_max,
            department_id=department_id,
            reference_context=revision_report,
            start_turn_number=start_turn_number,
            accumulated_transcript=full_transcript,
            accumulated_turn_summaries=turn_summaries,
            peer_context=peer_context,
        )
        full_transcript = loop_result["full_transcript"]
        turn_summaries = loop_result["turn_summaries"]
        last_turn = turn_summaries[-1]["turn_number"] if turn_summaries else start_turn_number - 1

        extracted = extract_decisions(
            department_id, sub_task_text, full_transcript, spec_text=read_spec_text(room_id)
        )
        refresh_active_decisions(
            room_id, department_name, extracted, last_turn, scope_anchor=department_id
        )
        active = get_active_decisions(room_id)
        d_list_text = write_provisional_d_list(room_id, active)
        summary_for_review = polish_final_summary(sub_task_text, turn_summaries)
        deliverables_text = read_deliverables_text(room_id)

        manager_review_count += 1
        is_final_review = manager_review_count == 3
        review = manager_review_deliverables(
            department_id,
            sub_task_text,
            d_list_text,
            summary_for_review,
            deliverables_text,
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

    summary = polish_final_summary(sub_task_text, turn_summaries)
    update_short_summary(room_id, summary)
    update_room_status(room_id, final_status, retry_count=retry_count)

    extracted = extract_decisions(
        department_id, sub_task_text, full_transcript, spec_text=read_spec_text(room_id)
    )
    last_turn = turn_summaries[-1]["turn_number"] if turn_summaries else 1
    refresh_active_decisions(
        room_id, department_name, extracted, last_turn, scope_anchor=department_id
    )
    active = get_active_decisions(room_id)
    write_provisional_d_list(room_id, active, preserve_if_empty=False)

    return _build_room_result(
        room_id, department_id, department_name, sub_task_text,
        active, final_status, summary, full_transcript, turn_summaries,
        members, retry_count, concerns_report,
    )


def _build_room_result(
    room_id, department_id, department_name, sub_task_text,
    decisions, final_status, summary, full_transcript, turn_summaries,
    members, retry_count, concerns_report,
):
    #変更: CQO/surgical用にdecision_id/origin_turn付きdecisionsを返す
    return {
        "room_id": room_id,
        "department_id": department_id,
        "department_name": department_name,
        "sub_task_text": sub_task_text,
        "decisions": decisions,
        "status": final_status,
        "deliverables_text": read_deliverables_text(room_id),
        "concerns_report": concerns_report or read_workspace_text(room_id, "concerns_report.txt"),
        "short_summary": summary,
        "full_transcript": full_transcript,
        "turn_summaries": turn_summaries,
        "members": members,
        "retry_count": retry_count,
        "is_suspicious": final_status == "forced_approved",
    }
