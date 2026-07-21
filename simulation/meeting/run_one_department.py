from simulation.data.departments import DEPARTMENTS
from simulation.db.read import get_department_members
from simulation.db.write import create_room, update_short_summary, save_decision
from simulation.meeting.department_meeting import department_discussion_loop
from simulation.memory.make_summary import make_summary
from simulation.memory.extract_decisions import extract_decisions


def run_department_room(project_id, department_id, sub_task_text, room_suffix):
    """1部署分のルームを作り、議論→要約→D-list化までを実行する
    (フェーズ3で作った仕組みをそのまま再利用)
    """
    department_name = DEPARTMENTS[department_id]
    room_id = f"room_{project_id}_{room_suffix}"

    create_room(room_id, project_id, department_name, sub_task_text)

    members = get_department_members(department_id, count=2)
    if len(members) < 2:
        print(f"[{department_id}] メンバーが2人未満のためスキップします")
        return None

    full_transcript = department_discussion_loop(room_id, sub_task_text, members, max_turns=3)

    summary = make_summary(sub_task_text, full_transcript)
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
