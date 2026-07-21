#上流会議
#CTOと選ばれた各部長が、それぞれの担当領域について話し合う

import json

from RoomManager import get_persona, get_department_leader
from Discussion import build_system_prompt
from llmClient import ask_llm
from Jsonutils import clean_json_response
from Cto import revise_assignments


def collect_manager_verdicts(task_text, assignments):
    """各部署の部長に、割り振られたタスクへの合意可否を確認する
    (部長のjudgment_anchor:「元タスクとの乖離」「他部署依存の前提との矛盾」の判断軸を使う)

    戻り値: [{"department_id":..., "verdict":"agree"または"disagree", "reason":"..."}]
    """
    # 部長が「他部署の担当範囲と重複していないか」も判断できるよう、全体の配分を見せる
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


def run_alignment_meeting(task_text, assignments, max_rounds=3):
    """CTOの部署配分について、各部署の部長が合意するか確認する上流会議。
    反対意見が出た場合はCTOに配分を修正させて再確認する(最大max_rounds回)。

    戻り値: 最終的な部署配分のリスト
    """
    current_assignments = assignments

    for round_num in range(1, max_rounds + 1):
        print(f"\n=== 上流会議 ラウンド{round_num} ===")
        verdicts = collect_manager_verdicts(task_text, current_assignments)

        for v in verdicts:
            print(f"[{v['department_id']}] {v['verdict']} - {v['reason']}")

        disagreements = [v for v in verdicts if v.get("verdict") != "agree"]

        if not disagreements:
            print("全部署が合意しました")
            return current_assignments

        if round_num == max_rounds:
            print("最大ラウンドに達しました。現在の配分のまま進めます")
            return current_assignments

        print(f"{len(disagreements)}件の反対意見があります。CTOに配分を修正させます")
        current_assignments = revise_assignments(task_text, current_assignments, disagreements)

    return current_assignments