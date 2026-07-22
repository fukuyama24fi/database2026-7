from db.read import get_active_decisions, get_decisions_by_ids
from db.write import override_decisions_by_ids, override_decisions_from_turn, update_room_rollback_state
from workspace.io import write_provisional_d_list, write_workspace_text


def truncate_discussion_state(full_transcript, turn_summaries, from_turn):
    #変更: 指定ターン未満の議論だけ残し、それ以降をTurn巻き戻し対象にする
    keep_turns = [t for t in turn_summaries if t["turn_number"] < from_turn]
    if keep_turns:
        end_idx = keep_turns[-1].get("message_end_index", len(full_transcript))
        return full_transcript[:end_idx], keep_turns
    return [], []


def apply_surgical_rollback(room_id, decision_ids, rejection_report):
    #変更: 決定事項単位のsurgicalロールバック(該当decision_idのみoverridden)
    override_decisions_by_ids(room_id, decision_ids)
    update_room_rollback_state(
        room_id,
        last_rejection_report=rejection_report,
        status="surgical_rollback",
    )
    write_workspace_text(room_id, "last_rejection_report.txt", rejection_report)
    active = get_active_decisions(room_id)
    write_provisional_d_list(room_id, active, preserve_if_empty=False)
    print(f"[surgicalロールバック] room={room_id} decisions={decision_ids}")


def apply_turn_rollback(room_id, from_turn, rejection_report):
    #変更: 再交渉が必要な場合のみ。origin_turn>=from_turn の決定をoverridden
    override_decisions_from_turn(room_id, from_turn)
    update_room_rollback_state(
        room_id,
        local_rollback_cursor=from_turn,
        last_rejection_report=rejection_report,
        status="turn_rollback",
    )
    write_workspace_text(room_id, "last_rejection_report.txt", rejection_report)
    active = get_active_decisions(room_id)
    write_provisional_d_list(room_id, active, preserve_if_empty=False)
    print(f"[Turnロールバック] room={room_id} turn{from_turn}〜を再交渉")


def _min_origin_turn_for_decisions(room_id, decision_ids):
    #変更: 対象決定の最小origin_turnを返す(Turn巻き戻し開始位置)
    rows = get_decisions_by_ids(room_id, decision_ids)
    turns = [r["origin_turn"] for r in rows if r.get("origin_turn") is not None]
    return min(turns) if turns else None


def build_surgical_revision_state(result, decision_ids, rejection_report):
    #変更: surgical修正用。議論は切り詰めずrevision_reportだけ渡す
    return {
        "room_id": result["room_id"],
        "department_id": result["department_id"],
        "sub_task_text": result["sub_task_text"],
        "members": result["members"],
        "full_transcript": result["full_transcript"],
        "turn_summaries": result["turn_summaries"],
        "revision_report": rejection_report,
        "affected_decision_ids": decision_ids,
        "retry_count": result.get("retry_count", 0),
        "mode": "surgical",
    }


def build_turn_rollback_resume_state(result, decision_ids, rejection_report, default_turn=3):
    #変更: 再交渉用。origin_turn最小値からTurn巻き戻し
    from_turn = _min_origin_turn_for_decisions(result["room_id"], decision_ids) or default_turn
    transcript, summaries = truncate_discussion_state(
        result["full_transcript"], result["turn_summaries"], from_turn
    )
    return {
        "room_id": result["room_id"],
        "department_id": result["department_id"],
        "sub_task_text": result["sub_task_text"],
        "members": result["members"],
        "full_transcript": transcript,
        "turn_summaries": summaries,
        "revision_report": rejection_report,
        "rollback_from_turn": from_turn,
        "affected_decision_ids": decision_ids,
        "retry_count": result.get("retry_count", 0),
        "mode": "turn",
    }


def group_affected_decisions_by_room(conflict, results_by_room):
    #変更: CQO conflictのaffected_decisionsをroom_idごとにグループ化
    grouped = {}
    for item in conflict.get("affected_decisions") or []:
        room_id = item.get("room_id")
        decision_id = item.get("decision_id")
        if room_id and decision_id:
            grouped.setdefault(room_id, []).append(decision_id)

    if grouped:
        return grouped

    for room_id in conflict.get("room_ids") or []:
        result = results_by_room.get(room_id)
        if not result:
            continue
        ids = [d["decision_id"] for d in (result.get("decisions") or []) if d.get("decision_id")]
        if ids:
            grouped[room_id] = ids
    return grouped
