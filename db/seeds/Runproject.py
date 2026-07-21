from Data import DEPARTMENTS
from RoomManager import (
    create_project,
    create_room,
    get_department_members,
    update_short_summary,
    save_decision,
)
from Discussion import department_discussion_loop
from Memory import summarize_discussion, extract_decisions
from Cto import assign_departments
from Cqo import audit_department
from ExecMetting import run_alignment_meeting


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

    summary = summarize_discussion(sub_task_text, full_transcript)
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


def main():
    project_id = "proj_test_600"
    task_text = "Webアプリ版ポモドーロタイマーのログイン画面のUIをどう設計するか検討してください"

    create_project(project_id)

    # 1. CTOが要件を読んで、関係する部署とタスクを決める
    assignments = assign_departments(task_text)
    if not assignments:
        print("CTOが部署配分を決められませんでした")
        return

    print("=== CTOによる部署配分(初期案) ===")
    for a in assignments:
        print(f"{a['department_id']}: {a['sub_task_text']}")

    # 1.5. 各部署の部長が配分に合意するか確認する上流会議(最大3ラウンド)
    assignments = run_alignment_meeting(task_text, assignments, max_rounds=3)

    print("\n=== 最終的な部署配分 ===")
    for a in assignments:
        print(f"{a['department_id']}: {a['sub_task_text']}")

    # 2. 各部署でルームを作って議論・D-list化(今回は順番に実行。並列化は今後の課題)
    results = []
    for idx, assignment in enumerate(assignments):
        department_id = assignment["department_id"]
        sub_task_text = assignment["sub_task_text"]
        print(f"\n--- [{department_id}] ルーム開始 ---")
        result = run_department_room(project_id, department_id, sub_task_text, f"{idx:02d}")
        if result:
            results.append(result)

    # 3. CQOが各部署の決定事項を監査する
    print("\n=== CQOによる監査 ===")
    for result in results:
        verdict = audit_department(
            result["department_id"], result["sub_task_text"], result["decisions"]
        )
        print(f"[{result['department_id']}] {verdict['verdict']} - {verdict['reason']}")


if __name__ == "__main__":
    print("main start")
    main()