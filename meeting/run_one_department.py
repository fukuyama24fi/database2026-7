from data.departments import DEPARTMENTS
from data.skills import skill_map
from db.read import get_department_members_by_skill
from db.write import assign_member_to_room, create_room, save_decision, update_short_summary
from meeting.department_meeting import department_discussion_loop
from memory.extract_decisions import extract_decisions
from memory.make_summary import polish_final_summary


def run_department_room(project_id, department_id, sub_task_text, room_suffix):
    """1部署分のルームを作り、議論→要約→D-list化までを実行する
    (フェーズ3で作った仕組みをそのまま再利用)
    """
    department_name = DEPARTMENTS[department_id]
    room_id = f"room_{project_id}_{room_suffix}"

    create_room(room_id, project_id, department_name, sub_task_text)

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

    discussion_result = department_discussion_loop(
        room_id, sub_task_text, members, max_turns=3, department_id=department_id
    )
    full_transcript = discussion_result["full_transcript"]
    turn_summaries = discussion_result["turn_summaries"]

    #新規: ターン要約の連結結果を整形してshort_summaryとする(旧make_summaryの全文読み込みは廃止)
    summary = polish_final_summary(sub_task_text, turn_summaries)
    update_short_summary(room_id, summary)

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
    }
