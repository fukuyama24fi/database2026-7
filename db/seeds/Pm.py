import json

from roomManager import get_persona, get_department_leader
from llmClient import ask_llm
from Jsonutils import clean_json_response

# 循環import回避のため、build_system_promptはdiscussion.pyから遅延importする
# (discussion.py側もこのファイルのcheck_consensusを使うため、
#  モジュール読み込み時に互いを参照するとエラーになる)

# PMの役割:議論の進行と合意形成の判断

def check_consensus(department_id, task_text, full_transcript):
    """PMが現時点の議論を読み、D-list化できる程度に合意形成されたか判断する
    (PMのjudgment_anchor:「D-list昇格の基準を満たしているか」を使う)

    戻り値: {"consensus_reached": True/False, "reason": "..."}
    """
    from discussion import build_system_prompt  # 遅延import

    leader = get_department_leader(department_id)
    if leader is None:
        return {"consensus_reached": False, "reason": "PM情報が見つかりません"}

    persona = get_persona(leader["agent_persona_id_pm"])
    if persona is None:
        return {"consensus_reached": False, "reason": "PMのpersonaが見つかりません"}

    system_prompt = build_system_prompt(leader["pm_name"], persona)

    transcript_text = "\n".join(
        f"{m['speaker']}: {m['message']}" for m in full_transcript
    )

    user_prompt = f"""タスク: {task_text}

これまでの部署内議論:
{transcript_text}

メンバー間で実質的な合意が形成され、これ以上議論を続けても新しい決定が
生まれる見込みが低い場合は、議論を打ち切ってD-list化に進めるべきだと判断してください。
逆に、まだ議論が広がり続けていて収束していない場合は、合意形成されていないと判断してください。

出力は必ず以下のJSON形式のみにしてください。前置きや説明文は一切含めないでください。

{{
  "consensus_reached": trueまたはfalse,
  "reason": "判断理由(簡潔に)"
}}"""

    raw = ask_llm(system_prompt, user_prompt)
    cleaned = clean_json_response(raw)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        print("PMの合意判定がJSONとして解析できませんでした:")
        print(raw)
        result = {"consensus_reached": False, "reason": "解析失敗のため議論を継続します"}

    return result