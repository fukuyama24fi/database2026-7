import json

from db.connect import connect_db


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
):
    #department_rooms_decisions(D-list。長期記憶)に1件保存する"""
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO department_rooms_decisions
            (room_id, department_name, decision_id, decision_type,
             summary, rationale, scope_anchor, confidence)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (room_id, decision_id) DO NOTHING
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
        ),
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"room={room_id} にD-list({decision_id})を保存しました")


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
