import json

from db.read import get_persona
from llm.ask_llm import ask_llm
from prompts.build_system_prompt import build_system_prompt
from utils.parse_json import clean_json_response

CQO_PERSONA_ID = "persona_exec_cqo"  # leadership.pyで生成したCQOのagent_persona_id


def cqo_check_decisions(
    department_id,
    task_text,
    decisions,
    deliverables_text=None,
    concerns_report=None,
    forced_approval=False,
):
    """CQOが部署の決定事項(D-list)を監査し、承認/差し戻しを判断する
    (CQOの責務:要件との整合性・重大な欠陥の有無をチェックする)

    戻り値: {"verdict": "approved"または"needs_revision", "reason": "..."}
    """
    persona = get_persona(CQO_PERSONA_ID)
    if persona is None:
        print("CQOのpersonaが見つかりません。leadership.pyの実行結果を確認してください")
        return {"verdict": "needs_revision", "reason": "CQOのpersonaが見つからないため監査できません"}

    system_prompt = build_system_prompt("CQO", persona)

    if decisions:
        decisions_text = "\n".join(
            f"- {d.get('summary', '')}(根拠: {d.get('rationale', '')})" for d in decisions
        )
    else:
        decisions_text = "(決定事項はありません)"

    #変更: 部長強制承認時は制作物と懸念レポートもCQOに渡す
    deliverables_section = deliverables_text or "（未作成）"
    concerns_section = ""
    if forced_approval:
        concerns_section = f"""
【部長による強制承認】
部長は2回差し戻し後の最終検収で承認しました。以下の懸念点に留意して監査してください。
{concerns_report or "(懸念レポートなし)"}
"""

    user_prompt = f"""以下は{department_id}部署に割り振られたタスクと、そこで確定した決定事項です。
要件との整合性、重大な欠陥の有無を監査してください。
{concerns_section}
【割り振られたタスク】
{task_text}

【決定事項】
{decisions_text}

【制作物(deliverables/)】
{deliverables_section}

出力は必ず以下のJSON形式のみにしてください。前置きや説明文、コードブロックの記号は一切含めないでください。

{{
  "verdict": "approved または needs_revision",
  "reason": "判断理由(簡潔に)"
}}"""

    raw = ask_llm(system_prompt, user_prompt)
    cleaned = clean_json_response(raw)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        print("CQOの出力がJSONとして解析できませんでした:")
        print(raw)
        result = {"verdict": "needs_revision", "reason": "監査結果の解析に失敗したため要確認"}

    return result
