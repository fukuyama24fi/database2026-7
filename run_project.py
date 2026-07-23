from db.write import create_project, update_room_rollback_state
from meeting.manager_conflict_meeting import run_managers_conflict_meeting
from meeting.run_one_department import run_department_room
from meeting.partial_rollback import (
    build_partial_fix_state,
    build_redo_from_turn_state,
    group_affected_decisions_by_room,
)
from meeting.top_meeting import run_top_meeting
from roles.cqo import cqo_check_cross_department, flag_suspicious_results
from roles.cto import cto_assign_tasks
from workspace.io import collect_final_outputs, write_workspace_text

#CQOが矛盾を見つけたあと、同じ横断監査を繰り返す上限回数
MAX_CQO_ROLLBACKS = 3
#部長同士が衝突について話し合う最大ターン数
MAX_MANAGER_CONFLICT_TURNS = 5
#Turn巻き戻し(議論のやり直し)を始めるデフォルトのターン番号
DEFAULT_ROLLBACK_TURN = 3


def _room_results(results):
    #部署結果のリストをroom_idで引ける辞書に変換する
    return {r["room_id"]: r for r in results}


def _sort_conflicts_by_severity(conflicts):
    #CQOが見つけた矛盾を重大度(0〜5)の高い順に並べる
    return sorted(
        conflicts,
        key=lambda c: c.get("severity_level", 0),
        reverse=True,
    )


def _build_rollback_states(conflict, room_results, resolution):
    #部長会議の結果から、各ルームの再開用データ(reopen_state)を組み立てる
    grouped = group_affected_decisions_by_room(conflict, room_results)
    needs_talk_redo = resolution.get("needs_talk_redo", False)
    revision_reports = resolution.get("revision_reports") or {}
    states = []

    for room_id, decision_ids in grouped.items():
        result = room_results.get(room_id)
        if not result:
            continue
        report = revision_reports.get(room_id) or conflict.get("description", "")
        if needs_talk_redo:
            state = build_redo_from_turn_state(
                result, decision_ids, report, default_turn=DEFAULT_ROLLBACK_TURN
            )
        else:
            state = build_partial_fix_state(result, decision_ids, report)
        states.append(state)
    return states


def main():
    #プロジェクト全体の実行入口(CTO配分→部署議論→CQO監査→必要なら修正)
    project_id = "proj_test_003"
    task_text = "Webアプリ版ポモドーロタイマーのログイン機能を設計してください"

    create_project(project_id)

    assignments = cto_assign_tasks(task_text)
    if not assignments:
        print("CTOが部署配分を決められませんでした")
        return

    print("=== CTOによる部署配分(初期案) ===")
    for a in assignments:
        print(f"{a['department_id']}: {a['dept_task']}")

    assignments = run_top_meeting(task_text, assignments, max_rounds=3)

    print("\n=== 最終的な部署配分 ===")
    for a in assignments:
        print(f"{a['department_id']}: {a['dept_task']}")

    results = []
    completed_for_peers = []
    for idx, assignment in enumerate(assignments):
        department_id = assignment["department_id"]
        dept_task = assignment["dept_task"]
        print(f"\n--- [{department_id}] ルーム開始 ---")
        result = run_department_room(
            project_id,
            department_id,
            dept_task,
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

        room_results = _room_results(results)
        room_ids = conflict.get("room_ids") or []
        affected_results = [room_results[rid] for rid in room_ids if rid in room_results]
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
            f"talk_redo={resolution.get('needs_talk_redo')} - {resolution.get('reason')}"
        )

        for room_id, report in (resolution.get("revision_reports") or {}).items():
            write_workspace_text(room_id, "revision_report.txt", report)
            update_room_rollback_state(room_id, last_rejection_report=report)

        reopen_states = _build_rollback_states(conflict, room_results, resolution)
        if not reopen_states:
            cqo_round += 1
            continue

        mode_label = "Turn巻き戻し" if resolution.get("needs_talk_redo") else "部分修正"
        print(f"\n=== {mode_label}: {len(reopen_states)}ルーム修正 ===")
        for reopen in reopen_states:
            dept = reopen["department_id"]
            print(f"--- [{dept}] mode={reopen.get('mode')} ---")
            updated = run_department_room(
                project_id,
                dept,
                reopen["dept_task"],
                room_index=reopen["room_id"].split("_")[-1],
                reopen_state=reopen,
                peer_results=[r for r in results if r["room_id"] != reopen["room_id"]],
            )
            if updated:
                for i, r in enumerate(results):
                    if r["room_id"] == updated["room_id"]:
                        results[i] = updated
                        break

        cqo_round += 1

    if cqo_status == "未実施" and cqo_round >= MAX_CQO_ROLLBACKS:
        cqo_status = "max_rollback_cycles_reached"

    final_dir = collect_final_outputs(
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
