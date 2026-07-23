#employees.py
import json
import random

from data.departments import DEPARTMENTS
from data.names import first_names, last_names
from data.personalities import personality_list
from data.skills import skill_map
from seed.personas import build_style_persona, make_member_judgment_anchor
from seed.writer import write_employees_to_db


def make_employee_data(target_count=9974):  #CEO,CFO,CTO,CQO,部長,PM 計26名を除く社員数
    rows = []

    for i in range(target_count):
        serial_num = i + 1
        member_id = f"mem_{serial_num:05d}"  #0:空いている桁は0。5:最低5桁。d:整数 例:mem_00001
        persona_id = f"persona_{serial_num:05d}"
        display_name = f"{random.choice(first_names)} {random.choice(last_names)}"
        department_id = random.choice(list(DEPARTMENTS.keys()))
        personality = random.choice(personality_list)

        available_skills = skill_map.get(department_id, [])
        if available_skills:  #リストに入ってたら
            max_skill = min(3, len(available_skills))  #部署のスキル一覧が2個以下の時のエラー対策
            chosen_skill = random.randint(1, max_skill)  #1~3個ランダムでスキルを与える
            skills = random.sample(
                available_skills, k=chosen_skill
            )  #random.sampleは指定した個数の要素をランダム重複なしで取って新しいリストをつくる
        else:
            skills = []

        row = {
            "member_id": member_id,
            "department_id": department_id,
            "display_name": display_name,
            "personality": personality,
            #dumpはlistやdict(辞書)をJSON形式の文字列に変換する関数
            #ensure_ascii=True(デフォルト)だと、csv変換時に日本語が16進数になる
            "skills": json.dumps(skills, ensure_ascii=False),
            "agent_persona_id": persona_id,
            "role_type": "member",
            "judgment_anchor": json.dumps(
                make_member_judgment_anchor(department_id), ensure_ascii=False
            ),
            "style_persona": json.dumps(
                build_style_persona(personality), ensure_ascii=False
            ),
        }
        rows.append(row)
    return rows


if __name__ == "__main__":
    rows = make_employee_data()
    write_employees_to_db(rows)
