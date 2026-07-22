from data.departments import DEPARTMENTS
from data.skills import skill_map
from db.read import get_department_members_by_skill
from db.write import assign_member_to_room, create_room, save_decision, update_room_status, update_short_summary
from meeting.department_meeting import department_discussion_loop
from memory.extract_decisions import extract_decisions
from memory.make_summary import polish_final_summary
from roles.manager import manager_review_deliverables
from workspace.io import (
    ensure_room_workspace,
    read_deliverables_text,
    read_workspace_text,
    write_provisional_d_list,
    write_workspace_text,
)

#変更: 実験設定(初回3T + 延長3T x 2 = 最大9T)。本番は BASE_TURNS=5 で最大11T
BASE_TURNS = 3
# BASE_TURNS = 5
EXTENSION_TURNS = 3
MAX_REVISIONS = 2


def _next_turn_number(turn_summaries):
    #変更: 延長ブロック開始時のターン番号(前ブロックの続き)を計算する
    if not turn_summaries:
        return 1
    return turn_summaries[-1]["turn_number"] + 1


def run_department_room(project_id, department_id, sub_task_text, room_suffix):
    """1部署分のルームを作り、議論→要約→D-list化までを実行する
    (フェーズ3で作った仕組みをそのまま再利用)
    """
    department_name = DEPARTMENTS[department_id]
    room_id = f"room_{project_id}_{room_suffix}"

    create_room(room_id, project_id, department_name, sub_task_text)
    ensure_room_workspace(room_id)

    #新規: 部署のスキルセットに合うメンバーをスキル一致数順に2人選抜
    required_skills = skill_map.get(department_id, [])
    members = get_department_members_by_skill(
        department_id, required_skills, count=2, exclude_member_ids=[]
    )
    if len(members) < 2:
        print(f"[{department_id}] メンバーが2人未満のためスキップします")
        return None

    #新規: 初期メンバーをroom_assignmentsに記録(turn=0, role=initial)
    for member in members:
        assign_member_to_room(room_id, member["member_id"], "initial", turn=0)

    #変更: 議論→部長検収→差し戻し→延長を繰り返す外側ループ
    full_transcript = []
    turn_summaries = []
    revision_report = None
    retry_count = 0
    manager_review_count = 0
    final_status = "approved"
    concerns_report = None

    while True:
        segment_max = BASE_TURNS if retry_count == 0 else EXTENSION_TURNS
        start_turn_number = _next_turn_number(turn_summaries)

        print(
            f"[{department_id}] 議論ブロック開始 "
            f"(retry_count={retry_count}, 最大{segment_max}T, turn{start_turn_number}〜)"
        )

        department_discussion_loop(
            room_id,
            sub_task_text,
            members,
            max_turns=segment_max,
            department_id=department_id,
            reference_context=revision_report,
            start_turn_number=start_turn_number,
            accumulated_transcript=full_transcript,
            accumulated_turn_summaries=turn_summaries,
        )

        #変更: 部長検収は「1ブロック分の議論が終わった後」に行う(ターン途中では呼ばない)
        last_turn = turn_summaries[-1]["turn_number"] if turn_summaries else start_turn_number - 1
        print(
            f"[{department_id}] 議論ブロック終了 (turn{start_turn_number}〜{last_turn}) "
            f"→ 部長検収へ"
        )

        provisional_decisions = extract_decisions(department_id, sub_task_text, full_transcript)
        d_list_text = write_provisional_d_list(room_id, provisional_decisions)
        summary_for_review = polish_final_summary(sub_task_text, turn_summaries)
        deliverables_text = read_deliverables_text(room_id)

        manager_review_count += 1
        is_final_review = manager_review_count == 3

        print(f"[{department_id}] 部長検収 {manager_review_count}回目 (final={is_final_review})")

        review = manager_review_deliverables(
            department_id,
            sub_task_text,
            d_list_text,
            summary_for_review,
            deliverables_text,
            manager_review_count,
            is_final_review=is_final_review,
        )
        print(
            f"[部長検収] verdict={review.get('verdict')} - {review.get('reason')}"
        )

        if is_final_review:
            concerns_text = review.get("concerns") or ""
            if concerns_text:
                concerns_report = concerns_text
                write_workspace_text(room_id, "concerns_report.txt", concerns_report)
                final_status = "forced_approved"
                print(f"[{department_id}] 最終検収: 強制承認(forced_approved)")
            else:
                final_status = "approved"
                print(f"[{department_id}] 最終検収: 承認(approved)")
            break

        if review.get("verdict") == "approved":
            final_status = "approved"
            print(f"[{department_id}] 部長承認。D-list確定へ進みます")
            break

        revision_report = review.get("revision_report") or review.get("reason") or ""
        if not revision_report:
            revision_report = "部長からの具体的指摘はありません。暫定D-listとタスクの整合を再確認してください。"

        write_workspace_text(room_id, "revision_report.txt", revision_report)
        retry_count += 1
        update_room_status(room_id, "revision", retry_count=retry_count)
        print(f"[{department_id}] 差し戻し({retry_count}/{MAX_REVISIONS}): revision_report.txt を保存しました")

        if retry_count > MAX_REVISIONS:
            break

    summary = polish_final_summary(sub_task_text, turn_summaries)
    update_short_summary(room_id, summary)
    update_room_status(room_id, final_status, retry_count=retry_count)

    decisions = extract_decisions(department_id, sub_task_text, full_transcript)
    for idx, decision in enumerate(decisions):
        decision_id = f"dec_{room_id}_{idx:03d}"
        save_decision(
            room_id=room_id,
            department_name=department_name,
            decision_id=decision_id,
            decision_type=decision.get("decision_type", "unknown"),
            summary=decision.get("summary", ""),
            rationale=decision.get("rationale", ""),
            scope_anchor=department_id,
            confidence=decision.get("confidence"),
        )

    return {
        "room_id": room_id,
        "department_id": department_id,
        "department_name": department_name,
        "sub_task_text": sub_task_text,
        "decisions": decisions,
        "status": final_status,
        "deliverables_text": read_deliverables_text(room_id),
        "concerns_report": concerns_report or read_workspace_text(room_id, "concerns_report.txt"),
    }
