import json

from db.connect import connect_db
from db.read import get_active_decisions


def create_project(project_id, current_phase="phase2_department_dev", status="in_progress"):
    #project_statesに1件作る
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO project_states (project_id, current_phase, status)
        VALUES (%s, %s, %s)
        """,
        (project_id, current_phase, status),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"project_states: {project_id} を作成しました")


def create_room(room_id, project_id, department_name, task_text):
    #department_roomsに1件作る。recent_messagesは空リスト([])で初期化
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO department_rooms
            (room_id, project_id, department_name, original_task_text,
             recent_messages, short_summary, status, retry_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            room_id,
            project_id,
            department_name,
            task_text,
            json.dumps([], ensure_ascii=False),  #会話が無い状態は空リスト
            "",
            "in_progress",
            0,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"department_rooms: {room_id} を作成しました")


def update_short_summary(room_id, summary_text):
    #department_roomsのshort_summary(中期記憶)を更新する
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE department_rooms SET short_summary = %s WHERE room_id = %s",
        (summary_text, room_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"room={room_id} のshort_summaryを更新しました")


def save_decision(
    room_id,
    department_name,
    decision_id,
    decision_type,
    summary,
    rationale,
    scope_anchor=None,
    confidence=None,
    status="active",
    discarded_from_turn=None,
    origin_turn=None,
):
    #department_rooms_decisions(D-list。長期記憶)に1件保存する
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO department_rooms_decisions
            (room_id, department_name, decision_id, decision_type,
             summary, rationale, scope_anchor, confidence, status,
             discarded_from_turn, origin_turn)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (room_id, decision_id) DO UPDATE SET
            decision_type = EXCLUDED.decision_type,
            summary = EXCLUDED.summary,
            rationale = EXCLUDED.rationale,
            scope_anchor = EXCLUDED.scope_anchor,
            confidence = EXCLUDED.confidence,
            status = EXCLUDED.status,
            discarded_from_turn = EXCLUDED.discarded_from_turn,
            origin_turn = EXCLUDED.origin_turn
        """,
        (
            room_id,
            department_name,
            decision_id,
            decision_type,
            summary,
            rationale,
            scope_anchor,
            confidence,
            status,
            discarded_from_turn,
            origin_turn,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"room={room_id} にD-list({decision_id})を保存しました(status={status})")


def supersede_active_decisions(room_id, discarded_from_turn=None):
    #変更: 現行D-listをoverriddenにし、CQOには見せない(監査用にDBには残す)
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE department_rooms_decisions
        SET status = 'overridden', discarded_from_turn = %s
        WHERE room_id = %s AND status = 'active'
        """,
        (discarded_from_turn, room_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"room={room_id} のactive D-listをoverriddenにしました")


def override_decisions_by_ids(room_id, decision_ids):
    #変更: surgicalロールバック。指定decision_idだけoverriddenにする(他はactiveのまま)
    if not decision_ids:
        return
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE department_rooms_decisions
        SET status = 'overridden'
        WHERE room_id = %s AND decision_id = ANY(%s) AND status = 'active'
        """,
        (room_id, list(decision_ids)),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"room={room_id} のD-list {len(decision_ids)}件をsurgical overriddenしました")


def override_decisions_from_turn(room_id, from_turn):
    #変更: origin_turn>=from_turn の決定だけoverridden(Turn巻き戻し時の補助)
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE department_rooms_decisions
        SET status = 'overridden', discarded_from_turn = %s
        WHERE room_id = %s AND status = 'active'
          AND (origin_turn IS NULL OR origin_turn >= %s)
        """,
        (from_turn, room_id, from_turn),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"room={room_id} origin_turn>={from_turn} のD-listをoverriddenしました")


def refresh_active_decisions(
    room_id, department_name, extracted_decisions, current_turn, scope_anchor=None
):
    #変更: extract結果を反映。未変更決定はorigin_turn/decision_idを保持、surgicalに差し替え可能
    existing = get_active_decisions(room_id)
    existing_by_type = {d["decision_type"]: d for d in existing}
    seen_types = set()
    next_idx = len(existing) + 1

    for decision in extracted_decisions or []:
        dtype = decision.get("decision_type", "unknown")
        seen_types.add(dtype)
        old = existing_by_type.get(dtype)
        if old and old.get("summary") == decision.get("summary"):
            decision_id = old["decision_id"]
            origin_turn = old.get("origin_turn") or current_turn  #変更: 内容不変ならorigin_turn保持
        elif old:
            decision_id = old["decision_id"]
            origin_turn = current_turn  #変更: 内容変更時のみorigin_turn更新
        else:
            decision_id = f"dec_{room_id}_{next_idx:03d}"
            next_idx += 1
            origin_turn = current_turn
        save_decision(
            room_id=room_id,
            department_name=department_name,
            decision_id=decision_id,
            decision_type=dtype,
            summary=decision.get("summary", ""),
            rationale=decision.get("rationale", ""),
            scope_anchor=scope_anchor,
            confidence=decision.get("confidence"),
            status="active",
            origin_turn=origin_turn,
        )

    for dtype, old in existing_by_type.items():
        if dtype not in seen_types:
            save_decision(
                room_id=room_id,
                department_name=department_name,
                decision_id=old["decision_id"],
                decision_type=dtype,
                summary=old.get("summary", ""),
                rationale=old.get("rationale", ""),
                scope_anchor=scope_anchor,
                confidence=old.get("confidence"),
                status="overridden",
                origin_turn=old.get("origin_turn"),
            )


def save_active_decisions(room_id, department_name, decisions, scope_anchor=None, current_turn=1):
    #変更: 互換ラッパー。refresh_active_decisionsへ委譲(origin_turn付き)
    refresh_active_decisions(
        room_id, department_name, decisions, current_turn, scope_anchor
    )


def update_room_rollback_state(
    room_id,
    local_rollback_cursor=None,
    last_rejection_report=None,
    is_suspicious=None,
    status=None,
    retry_count=None,
):
    #変更: 局所ロールバック用のルーム状態を更新する
    conn = connect_db()
    cur = conn.cursor()
    fields = []
    values = []
    if local_rollback_cursor is not None:
        fields.append("local_rollback_cursor = %s")
        values.append(local_rollback_cursor)
    if last_rejection_report is not None:
        fields.append("last_rejection_report = %s")
        values.append(last_rejection_report)
    if is_suspicious is not None:
        fields.append("is_suspicious = %s")
        values.append(is_suspicious)
    if status is not None:
        fields.append("status = %s")
        values.append(status)
    if retry_count is not None:
        fields.append("retry_count = %s")
        values.append(retry_count)
    if not fields:
        cur.close()
        conn.close()
        return
    values.append(room_id)
    cur.execute(
        f"UPDATE department_rooms SET {', '.join(fields)} WHERE room_id = %s",
        tuple(values),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"room={room_id} のロールバック状態を更新しました")


def add_message_to_room(room_id, speaker, message):
    #department_roomsのrecent_messagesに1件発言を追加する(直近5件に切り詰める)
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT recent_messages FROM department_rooms WHERE room_id = %s", (room_id,))
    row = cur.fetchone()
    current_messages = json.loads(row[0]) if row and row[0] else []

    current_messages.append({"speaker": speaker, "message": message})
    current_messages = current_messages[-5:]  # 直近5件だけ残す(短期記憶のルール)

    cur.execute(
        "UPDATE department_rooms SET recent_messages = %s WHERE room_id = %s",
        (json.dumps(current_messages, ensure_ascii=False), room_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"room={room_id} に発言を追加しました({speaker})")


def assign_member_to_room(room_id, member_id, role_in_room, turn):
    #新規: room_assignmentsに1行INSERTする。同じ人を二重登録してもエラーにしない
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO room_assignments
            (room_id, member_id, role_in_room, assigned_at_turn)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (room_id, member_id) DO NOTHING
        """,
        (room_id, member_id, role_in_room, turn),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"room={room_id} にメンバー({member_id}, {role_in_room})をアサインしました")


def update_room_status(room_id, status, retry_count=None):
    #変更: 部長レビュー・差し戻しに伴い、ルームのstatus/retry_countを更新する
    conn = connect_db()
    cur = conn.cursor()
    if retry_count is None:
        cur.execute(
            "UPDATE department_rooms SET status = %s WHERE room_id = %s",
            (status, room_id),
        )
    else:
        cur.execute(
            "UPDATE department_rooms SET status = %s, retry_count = %s WHERE room_id = %s",
            (status, retry_count, room_id),
        )
    conn.commit()
    cur.close()
    conn.close()
    print(f"room={room_id} のstatus={status}, retry_count={retry_count} を更新しました")
