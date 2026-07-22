from db.write import create_project, update_room_rollback_state
from meeting.manager_conflict_meeting import run_managers_conflict_meeting
from meeting.run_one_department import run_department_room
from meeting.surgical_rollback import (
    build_surgical_revision_state,
    build_turn_rollback_resume_state,
    group_affected_decisions_by_room,
)
from meeting.top_meeting import run_top_meeting
from roles.cqo import cqo_check_cross_department, flag_suspicious_results
from roles.cto import cto_assign_tasks
from workspace.io import consolidate_project_deliverables, write_workspace_text

#変更: 実験時3回・本番5回。severity_level降順で処理するロールバック上限
MAX_CQO_ROLLBACKS = 3
# MAX_CQO_ROLLBACKS = 5  # 本番
MAX_MANAGER_CONFLICT_TURNS = 5
DEFAULT_ROLLBACK_TURN = 3


def _results_by_room(results):
    return {r["room_id"]: r for r in results}


def _sort_conflicts_by_severity(conflicts):
    #変更: 重大度(0〜5)が大きい順に並べる
    return sorted(
        conflicts,
        key=lambda c: c.get("severity_level", 0),
        reverse=True,
    )


def _build_rollback_states(conflict, results_by_room, resolution):
    #変更: surgical(デフォルト)またはTurn巻き戻し(再交渉)のresume_stateを組み立てる
    grouped = group_affected_decisions_by_room(conflict, results_by_room)
    needs_renegotiation = resolution.get("needs_renegotiation", False)
    revision_reports = resolution.get("revision_reports") or {}
    states = []

    for room_id, decision_ids in grouped.items():
        result = results_by_room.get(room_id)
        if not result:
            continue
        report = revision_reports.get(room_id) or conflict.get("description", "")
        if needs_renegotiation:
            state = build_turn_rollback_resume_state(
                result, decision_ids, report, default_turn=DEFAULT_ROLLBACK_TURN
            )
        else:
            state = build_surgical_revision_state(result, decision_ids, report)
        states.append(state)
    return states


def main():
    project_id = "proj_test_001"
    task_text = "Webアプリ版ポモドーロタイマーのログイン画面のUIをどう設計するか検討してください"

    create_project(project_id)

    assignments = cto_assign_tasks(task_text)
    if not assignments:
        print("CTOが部署配分を決められませんでした")
        return

    print("=== CTOによる部署配分(初期案) ===")
    for a in assignments:
        print(f"{a['department_id']}: {a['sub_task_text']}")

    assignments = run_top_meeting(task_text, assignments, max_rounds=3)

    print("\n=== 最終的な部署配分 ===")
    for a in assignments:
        print(f"{a['department_id']}: {a['sub_task_text']}")

    results = []
    completed_for_peers = []  #変更: 先行部署成果物を後続部署へ渡す
    for idx, assignment in enumerate(assignments):
        department_id = assignment["department_id"]
        sub_task_text = assignment["sub_task_text"]
        print(f"\n--- [{department_id}] ルーム開始 ---")
        result = run_department_room(
            project_id,
            department_id,
            sub_task_text,
            f"{idx:02d}",
            peer_results=completed_for_peers,
        )
        if result:
            results.append(result)
            completed_for_peers.append(result)

    cqo_status = "未実施"
    cqo_round = 0
    while cqo_round < MAX_CQO_ROLLBACKS:
        print(f"\n=== CQO横断監査 (サイクル{cqo_round + 1}/{MAX_CQO_ROLLBACKS}) ===")
        flag_suspicious_results(results)

        integration = cqo_check_cross_department(task_text, results)
        print(f"[CQO] verdict={integration.get('verdict')} - {integration.get('reason')}")

        if integration.get("parse_failed"):
            cqo_status = "parse_failed"
            print("CQO横断監査: JSON解析失敗のため処理を中断します")
            break

        if integration.get("verdict") == "approved":
            cqo_status = "approved"
            print("CQO横断監査: 整合性OK")
            break

        if not integration.get("conflicts"):
            cqo_status = "needs_rollback_no_conflicts"
            print("CQO: needs_rollbackだがconflictsが空のため処理を中断します")
            break

        conflicts = _sort_conflicts_by_severity(integration.get("conflicts", []))
        conflict = conflicts[0]
        severity = conflict.get("severity_level", 3)
        affected = conflict.get("affected_decisions") or []
        print(
            f"[CQO衝突] severity={severity}/5 id={conflict.get('conflict_id')}: "
            f"{conflict.get('description', '')[:120]}"
        )
        print(f"  affected_decisions={len(affected)}件")

        results_by_room = _results_by_room(results)
        room_ids = conflict.get("room_ids") or []
        affected_results = [results_by_room[rid] for rid in room_ids if rid in results_by_room]
        if not affected_results:
            dept_ids = conflict.get("department_ids") or []
            affected_results = [r for r in results if r["department_id"] in dept_ids]
        if not affected_results:
            print("CQO: ロールバック対象ルームを特定できませんでした")
            cqo_round += 1
            continue

        resolution = run_managers_conflict_meeting(
            task_text,
            conflict,
            affected_results,
            max_turns=MAX_MANAGER_CONFLICT_TURNS,
        )
        print(
            f"  部長討論: 合意={resolution.get('agreed')} "
            f"renegotiate={resolution.get('needs_renegotiation')} - {resolution.get('reason')}"
        )

        for room_id, report in (resolution.get("revision_reports") or {}).items():
            write_workspace_text(room_id, "revision_report.txt", report)
            update_room_rollback_state(room_id, last_rejection_report=report)

        resume_states = _build_rollback_states(conflict, results_by_room, resolution)
        if not resume_states:
            cqo_round += 1
            continue

        mode_label = "Turn巻き戻し" if resolution.get("needs_renegotiation") else "surgical"
        print(f"\n=== {mode_label}: {len(resume_states)}ルーム修正 ===")
        for resume in resume_states:
            dept = resume["department_id"]
            print(f"--- [{dept}] mode={resume.get('mode')} ---")
            updated = run_department_room(
                project_id,
                dept,
                resume["sub_task_text"],
                room_suffix=resume["room_id"].split("_")[-1],
                resume_state=resume,
                peer_results=[r for r in results if r["room_id"] != resume["room_id"]],
            )
            if updated:
                for i, r in enumerate(results):
                    if r["room_id"] == updated["room_id"]:
                        results[i] = updated
                        break

        cqo_round += 1

    if cqo_status == "未実施" and cqo_round >= MAX_CQO_ROLLBACKS:
        cqo_status = "max_rollback_cycles_reached"

    final_dir = consolidate_project_deliverables(
        project_id, task_text, results, cqo_status=cqo_status
    )

    print("\n=== 最終結果 ===")
    for result in results:
        suspicious = " [怪しい]" if result.get("is_suspicious") else ""
        print(
            f"[{result['department_id']}]{suspicious} status={result['status']} "
            f"D-list={len(result.get('decisions') or [])}件"
        )
    print(f"\n最終成果物(一括): {final_dir}")


if __name__ == "__main__":
    print("main start")
    main()
