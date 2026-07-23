
from llm.ask_llm import ask_llm
from prompts.json_format_rules import JSON_FORMAT_RULES
from utils.parse_json import parse_llm_json_array


def find_decisions_from_log(department_id, task_text, talk_log, design_doc=None):
    #議論ログ(talk_log)から確定した決定事項をLLMで抽出し、D-list用リストを作る
    """議論ログから確定した決定事項を抽出し、D-list用のリストを作る(長期記憶)。
    1つのdecisionには1つの決定内容だけを入れる。複数の決定がある場合は配列を分ける。
    戻り値: [{"decision_type":..., "summary":..., "rationale":..., "confidence":...}, ...]
    """
    talk_log_text = "\n".join(
        f"{m['speaker']}: {m['message']}" for m in talk_log
    )

    if design_doc:
        design_section = f"""
【成果物 design.txt】
{design_doc}
"""
    else:
        design_section = ""

    system_prompt = f"""あなたは議事録係です。以下のJSON形式で決定事項だけを抽出してください。
{JSON_FORMAT_RULES}
出力は必ずJSON配列のみにしてください。前置きや説明文、コードブロックの記号は一切含めないでください。
rationale内の改行は必ず \\n にエスケープし、文字列を閉じてから次のフィールドへ進むこと。

[
  {{
    "decision_type": "spec_commitなど、決定の種類を表す短い英語タグ",
    "summary": "決定内容の要約(500文字以内)",
    "rationale": "決定の根拠(20~2000文字。改行は\\\\n)",
    "confidence": 0.0から1.0の数値(この決定の確信度)
  }}
]


「決定事項」の判定基準:
- 明確に「これに決定した」と言い切っている場合はもちろん対象です。
- それだけでなく、複数のメンバーが同意・賛成し、議論の中で繰り返し支持されている提案も
  「事実上合意された決定事項」とみなして抽出してください。
- 一人だけが提案していて他のメンバーからの賛同や反応がまだ無いものは含めないでください。
- 1つのdecisionには1つの決定内容だけを入れてください。
- 出力は「現時点の確定D-list全文」です。decision_typeは同じ決定の更新時に再利用してください。"""

    user_prompt = f"""部署: {department_id}
タスク: {task_text}
{design_section}
以下は部署内での議論ログ(chat)です。ここから確定した決定事項だけを抽出してください。

{talk_log_text}"""

    raw = ask_llm(system_prompt, user_prompt)
    decisions = parse_llm_json_array(raw)

    if not decisions:
        print("LLMの出力がJSONとして解析できませんでした。中身を確認してください:")
        print(raw)
        return []

    return decisions
