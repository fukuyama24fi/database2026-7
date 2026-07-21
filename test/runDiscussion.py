import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.departments import DEPARTMENTS
from db.read import get_department_members, get_persona
from db.write import create_project, create_room, save_decision, update_short_summary
from meeting.department_meeting import department_discussion_loop
from memory.extract_decisions import extract_decisions
from memory.make_summary import make_summary

def main():
    project_id = "proj_test_0010"
    department_id = "FE"
    room_id = "room_test_0010"
    task_text = "Webアプリ版ポモドーロタイマーのログイン画面のUIをどう設計するか検討してください"

    department_name = DEPARTMENTS[department_id]

    # 1. プロジェクトとルームを作る
    create_project(project_id)
    create_room(room_id, project_id, department_name, task_text)

    # 2. このルームのメンバーを2人取得する
    #    注意: department_members_masterのdepartment_id列はフルネームで保存されているので、
    #    ここもDEPARTMENTS[department_id]で変換した値を渡す(runSingleTurn.pyで抜けていたバグの修正)
    members = get_department_members(department_id, count=2)
    if len(members) < 2:
        print("メンバーが2人未満です。department_members_masterを確認してください")
        return
    
    print("=== 参加メンバー ===")
    for m in members:
        persona = get_persona(m["agent_persona_id"])

        print("=" * 40)
        print(m["display_name"])
        print("性格:", m["personality"])
        print("Judgment:", persona["judgment_anchor"])
        print("Style:", persona["style_persona"])

    # 3. 議論ループを実行(最大5ターン、メンバー全員が毎ターン発言)
    full_transcript = department_discussion_loop(
        room_id, task_text, members, max_turns=5, department_id=department_id
    )
    print("--- 議論ループが完了しました ---")

    # 4. 議論全文からshort_summary(中期記憶)を作って保存
    summary = make_summary(task_text, full_transcript)
    update_short_summary(room_id, summary)
    print(f"\n[要約]\n{summary}\n")
 
    # 5. 議論全文から決定事項を抽出し、D-list(長期記憶)として保存
    decisions = extract_decisions(department_id, task_text, full_transcript)
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
 
    print(f"{len(decisions)}件の決定事項をD-listに保存しました")


if __name__ == "__main__":
    print("main start")
    main()
