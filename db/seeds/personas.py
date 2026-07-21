import json

from Data import (
    judgment_anchor_map,
    style_persona_map,
    executive_anchor_map,
    executive_scope_lock,
)

#選んだpersonalityをJSON構造に変換する
def build_style_persona(personality):
    #personality(例:論理的)からstyle_personaのJSON構造を取り出す
    return style_persona_map[personality]


def build_persona_row(agent_persona_id, role_type, department_id, judgment_anchor, style_persona):
    """agent_personasテーブル1行分のdictを組み立てる(職人・部長・PM・役員共通)"""
    return {
        "agent_persona_id": agent_persona_id,
        "role_type": role_type,
        "department_id": department_id,
        "judgment_anchor": json.dumps(judgment_anchor, ensure_ascii=False),
        "style_persona": json.dumps(style_persona, ensure_ascii=False),
    }


#役職ごとのjudgment_anchor(判断軸)の設定
#役職が上がるほどjudgment_anchorを強く、専門的にする
def make_member_judgment_anchor(department_id):
    #職人用。ドメイン専門知識のみ(専門領域:強い)
    base = judgment_anchor_map[department_id]
    return {
        **base,
        "scope_lock": department_id,
        "out_of_scope_reply": "redirect_to_relevant_dept",
        "version": 1,
    }


def make_manager_judgment_anchor(department_id):
    #部長用。ドメイン専門知識+検収の視点(専門領域:強い)
    base = judgment_anchor_map[department_id]
    return {
        "primary_questions": base["primary_questions"]
        + [
            "元タスクとの乖離はないか",
            "他部署依存の前提に矛盾はないか",
        ],
        "auto_reject_conditions": base["auto_reject_conditions"]
        + [
            "元タスクから逸脱した成果物",
            "他部署の仕様と矛盾する成果物",
        ],
        "output_required_fields": base["output_required_fields"],
        "scope_lock": department_id,
        "out_of_scope_reply": "redirect_to_relevant_dept",
        "version": 1,
    }


def make_pm_judgment_anchor(department_id):
    #PM用。ドメイン専門性は薄く、進行管理が中心(専門領域:中程度)
    return {
        "primary_questions": [
            "メンバー編成・役割分担は適切か",
            "動的スカウトが必要な状況か",
            "D-list昇格の基準を満たしているか",
        ],
        "auto_reject_conditions": [
            "承認基準を満たさない未成熟な決定をD-list化しようとする場合",
        ],
        "output_required_fields": ["team_assignment_status", "vote_summary"],
        "scope_lock": department_id,
        "out_of_scope_reply": "redirect_to_relevant_dept",
        "version": 1,
    }


def make_executive_judgment_anchor(role_id):
    #役員用(CEO/CTO/CFO/CQO)(専門領域:非常に強く)
    base = executive_anchor_map[role_id]
    return {
        **base,
        "scope_lock": executive_scope_lock[role_id],
        "out_of_scope_reply": "redirect_to_relevant_dept",
        "version": 1,
    }