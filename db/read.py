import json

from db.connect import connect_db


def get_department_members(department_name, count=2):
    #指定部署から、稼働可能(is_active)なメンバーをcount人取得する。
    #戻り値: [{"member_id":..., "display_name":..., "personality":..., "agent_persona_id":...}, ...]

    conn = connect_db()
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
    conn = connect_db()
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
    conn = connect_db()
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
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT recent_messages FROM department_rooms WHERE room_id = %s", (room_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None or not row[0]:
        return []
    return json.loads(row[0])
