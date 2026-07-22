from db.write import create_project
from meeting.run_one_department import run_department_room
from meeting.top_meeting import run_top_meeting
from roles.cqo import cqo_check_decisions
from roles.cto import cto_assign_tasks


def main():
    project_id = "proj_test_120"
    task_text = "Webアプリ版ポモドーロタイマーのログイン画面のUIをどう設計するか検討してください"

    create_project(project_id)

    # 1. CTOが要件を読んで、関係する部署とタスクを決める
    assignments = cto_assign_tasks(task_text)
    if not assignments:
        print("CTOが部署配分を決められませんでした")
        return

    print("=== CTOによる部署配分(初期案) ===")
    for a in assignments:
        print(f"{a['department_id']}: {a['sub_task_text']}")

    # 1.5. 各部署の部長が配分に合意するか確認する上流会議(最大3ラウンド)
    assignments = run_top_meeting(task_text, assignments, max_rounds=3)

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
        #変更: 部長強制承認時は制作物・懸念レポートもCQOへ渡す
        verdict = cqo_check_decisions(
            result["department_id"],
            result["sub_task_text"],
            result["decisions"],
            deliverables_text=result.get("deliverables_text"),
            concerns_report=result.get("concerns_report"),
            forced_approval=(result.get("status") == "forced_approved"),
        )
        print(f"[{result['department_id']}] {verdict['verdict']} - {verdict['reason']}")


if __name__ == "__main__":
    print("main start")
    main()
