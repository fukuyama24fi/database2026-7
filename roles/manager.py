import json

from db.read import get_department_leader, get_persona
from llm.ask_llm import ask_llm
from prompts.build_system_prompt import build_system_prompt
from utils.parse_json import clean_json_response


def ask_managers_agreement(task_text, assignments):
    """各部署の部長に、割り振られたタスクへの合意可否を確認する
    (部長のjudgment_anchor:「元タスクとの乖離」「他部署依存の前提との矛盾」の判断軸を使う)

    戻り値: [{"department_id":..., "verdict":"agree"または"disagree", "reason":"..."}]
    """
    #部長が「他部署の担当範囲と重複していないか」も判断できるよう、全体の配分を見せる
    assignment_overview = "\n".join(
        f"{a['department_id']}: {a['sub_task_text']}" for a in assignments
    )

    verdicts = []
    for assignment in assignments:
        department_id = assignment["department_id"]
        sub_task_text = assignment["sub_task_text"]

        leader = get_department_leader(department_id)
        if leader is None:
            print(f"[{department_id}] 部長情報が見つかりません。スキップします")
            continue

        persona = get_persona(leader["agent_persona_id_manager"])
        if persona is None:
            print(f"[{department_id}] 部長のpersonaが見つかりません。スキップします")
            continue

        system_prompt = build_system_prompt(leader["manager_name"], persona)

        user_prompt = f"""プロジェクト全体の要件: {task_text}

CTOによる部署配分(全体):
{assignment_overview}

あなたの部署に割り振られたタスク: {sub_task_text}

このタスクが自部署の専門範囲内であり、他部署との役割の重複や矛盾が無いか判断してください。
出力は必ず以下のJSON形式のみにしてください。前置きや説明文は一切含めないでください。

{{
  "verdict": "agree または disagree",
  "reason": "判断理由(簡潔に)"
}}"""

        raw = ask_llm(system_prompt, user_prompt)
        cleaned = clean_json_response(raw)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            print(f"[{department_id}] 部長の出力がJSONとして解析できませんでした:")
            print(raw)
            result = {"verdict": "agree", "reason": "解析失敗のため暫定的に合意扱い"}

        result["department_id"] = department_id
        verdicts.append(result)

    return verdicts
