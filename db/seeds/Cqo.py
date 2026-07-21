import json

from RoomManager import get_persona
from Discussion import build_system_prompt
from llmClient import ask_llm
from Jsonutils import clean_json_response

CQO_PERSONA_ID = "persona_exec_cqo"  # leadership.pyで生成したCQOのagent_persona_id


def audit_department(department_id, task_text, decisions):
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

    user_prompt = f"""以下は{department_id}部署に割り振られたタスクと、そこで確定した決定事項です。
要件との整合性、重大な欠陥の有無を監査してください。

【割り振られたタスク】
{task_text}

【決定事項】
{decisions_text}

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