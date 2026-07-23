import json

from db.connect import connect_db


def get_department_members(department_name, count=2):
    #指定部署から稼働可能(is_active)なメンバーをcount人取得する
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


def get_department_members_by_skill(
    department_id, required_skills, count, exclude_member_ids=None
):
    #指定部署から、必要スキルが合う順にメンバーをcount人取る(スカウト追加用)
    #exclude_member_ids: すでにルームにいる人を除外する(スカウト時に使う)
    if exclude_member_ids is None:
        exclude_member_ids = []

    conn = connect_db()
    cur = conn.cursor()

    if exclude_member_ids:
        cur.execute(
            """
            SELECT member_id, display_name, personality, skills, agent_persona_id
            FROM department_members_master
            WHERE department_id = %s
              AND is_active = TRUE
              AND member_id NOT IN %s
            """,
            (department_id, tuple(exclude_member_ids)),
        )
    else:
        cur.execute(
            """
            SELECT member_id, display_name, personality, skills, agent_persona_id
            FROM department_members_master
            WHERE department_id = %s AND is_active = TRUE
            """,
            (department_id,),
        )

    rows = cur.fetchall()
    cur.close()
    conn.close()

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

    if not required_skills:
        return members[:count]

    required_set = set(required_skills)

    def skill_score(member):
        try:
            member_skills = json.loads(member["skills"]) if member["skills"] else []
        except (json.JSONDecodeError, TypeError):
            member_skills = []
        return len(set(member_skills) & required_set)

    members.sort(key=skill_score, reverse=True)
    return members[:count]


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
    #department_leaders_masterから部署の部長・PM情報を取得する
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


def get_active_decisions(room_id):
    #CQO向けにactiveなD-listのみ取得する(cancelledは除外)
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT decision_id, decision_type, summary, rationale, scope_anchor, confidence, origin_turn
        FROM department_rooms_decisions
        WHERE room_id = %s AND status = 'active'
        ORDER BY decision_id
        """,
        (room_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "decision_id": row[0],
            "decision_type": row[1],
            "summary": row[2],
            "rationale": row[3],
            "scope_anchor": row[4],
            "confidence": row[5],
            "origin_turn": row[6],
        }
        for row in rows
    ]


def get_decisions_by_ids(room_id, decision_ids):
    #部分ロールバック対象の決定事項をdecision_id指定で取得する
    if not decision_ids:
        return []
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT decision_id, decision_type, summary, rationale, origin_turn, status
        FROM department_rooms_decisions
        WHERE room_id = %s AND decision_id = ANY(%s)
        """,
        (room_id, list(decision_ids)),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "decision_id": row[0],
            "decision_type": row[1],
            "summary": row[2],
            "rationale": row[3],
            "origin_turn": row[4],
            "status": row[5],
        }
        for row in rows
    ]
