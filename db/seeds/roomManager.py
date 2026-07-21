import json
import psycopg2
import os


def get_connection():
    #DB接続を作る。既存の各ファイルと同じ接続設定を再利用
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "simulation"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "password"),
        port=os.getenv("DB_PORT", 5432),
    )

def create_project(project_id, current_phase="phase2_department_dev", status="in_progress"):
    #project_statesに1件作る
    conn = get_connection()
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
    conn = get_connection()
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


def get_department_members(department_name, count=2):
    #指定部署から、稼働可能(is_active)なメンバーをcount人取得する。
    #戻り値: [{"member_id":..., "display_name":..., "personality":..., "agent_persona_id":...}, ...]

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT member_id, display_name, personality, skills, agent_persona_id
        FROM department_members_master
        WHERE department_id = %s AND is_active = TRUE
        LIMIT %s
        """,
        (department_name, count),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    #fetchall()はタプルのリストで返るので、辞書に変換して扱いやすくする
    #つまり欲しいデータが何番目のインデックスか覚えなくても、列名でデータを取れるよ！
    members = []
    for row in rows:
        members.append(
            {
                "member_id": row[0],
                "display_name": row[1],
                "personality": row[2],
                "skills": row[3],
                "agent_persona_id": row[4],
            }
        )
    return members


def get_persona(agent_persona_id):
    #agent_personasから1人分のjudgment_anchor/style_personaを取得する
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT judgment_anchor, style_persona
        FROM agent_personas
        WHERE agent_persona_id = %s
        """,
        (agent_persona_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        return None
    return {
        "judgment_anchor": json.loads(row[0]),
        "style_persona": json.loads(row[1]),
    }

def get_department_leader(department_id):
    #department_leaders_masterから、activeな部署の部長・PMの情報を取得する
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT manager_name, pm_name, agent_persona_id_manager, agent_persona_id_pm
        FROM department_leaders_master
        WHERE department_id = %s
        """,
        (department_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
 
    if row is None:
        return None
    return {
        "manager_name": row[0],
        "pm_name": row[1],
        "agent_persona_id_manager": row[2],
        "agent_persona_id_pm": row[3],
    }

def get_recent_messages(room_id):
    #department_roomsのrecent_messagesを取得する(短期記憶=直近5件)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT recent_messages FROM department_rooms WHERE room_id = %s", (room_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
 
    if row is None or not row[0]:
        return []
    return json.loads(row[0])


def update_short_summary(room_id, summary_text):
    #department_roomsのshort_summary(中期記憶)を更新する
    conn = get_connection()
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
    conn = get_connection()
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


def append_message_to_room(room_id, speaker, message):
    #department_roomsのrecent_messagesに1件発言を追加する(直近5件に切り詰める)
    conn = get_connection()
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