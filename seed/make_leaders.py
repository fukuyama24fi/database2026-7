from data.departments import DEPARTMENTS
from data.personalities import (
    executive_personality,
    manager_personality_map,
    pm_personality_map,
)
from seed.personas import (
    build_persona_row,
    build_style_persona,
    make_executive_judgment_anchor,
    make_manager_judgment_anchor,
    make_pm_judgment_anchor,
)


def make_leader_data():
    #役員4名+部長・PM22名(計26名)分のデータを生成
    #戻り値:(executive_rows, leader_rows, persona_rows) のタプル
    
    executive_rows = [] #executives_masterへ(4件)
    leader_rows = [] #department_leaders_masterへ(11件。1行=1部署。部長とPMは同じ)
    persona_rows = [] #agent_personasへ(26件)

    #役員4名
    for role_id in ["CEO", "CTO", "CFO", "CQO"]:
        persona_id = f"persona_exec_{role_id.lower()}"
        personality = executive_personality[role_id]

        persona_rows.append(
            build_persona_row(
                agent_persona_id=persona_id,
                role_type="executive",
                department_id="EXECUTIVE", #役員グループ。NONEは怒られます
                judgment_anchor=make_executive_judgment_anchor(role_id),
                style_persona=build_style_persona(personality),
            )
        )
        executive_rows.append(
            {
                "role_id": role_id,
                "display_name": role_id, #個別の名前を付けたくなったら後で変更する
                "agent_persona_id": persona_id,
            }
        )

    #各部署の部長・PM(11部署 x 2名 = 22名)
    for idx, department_id in enumerate(DEPARTMENTS):
        manager_personality = manager_personality_map[department_id]
        pm_personality = pm_personality_map[department_id]

        manager_persona_id = f"persona_mgr_{idx:02d}"
        pm_persona_id = f"persona_pm_{idx:02d}"

        persona_rows.append(
            build_persona_row(
                agent_persona_id=manager_persona_id,
                role_type="manager",
                department_id=department_id,
                judgment_anchor=make_manager_judgment_anchor(department_id),
                style_persona=build_style_persona(manager_personality),
            )
        )
        persona_rows.append(
            build_persona_row(
                agent_persona_id=pm_persona_id,
                role_type="pm",
                department_id=department_id,
                judgment_anchor=make_pm_judgment_anchor(department_id),
                style_persona=build_style_persona(pm_personality),
            )
        )
        leader_rows.append(
            {
                "department_id": department_id,
                "department_name": DEPARTMENTS[department_id],
                "manager_name": f"{DEPARTMENTS[department_id]}_部長",
                "pm_name": f"{DEPARTMENTS[department_id]}_PM",
                "agent_persona_id_manager": manager_persona_id,
                "agent_persona_id_pm": pm_persona_id,
            }
        )

    return executive_rows, leader_rows, persona_rows


if __name__ == "__main__":
    from seed.writer import write_leadership_to_db

    executive_rows, leader_rows, persona_rows = make_leader_data()
    write_leadership_to_db(executive_rows, leader_rows, persona_rows)
