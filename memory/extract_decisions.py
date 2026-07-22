import json

from llm.ask_llm import ask_llm
from utils.parse_json import clean_json_response


def extract_decisions(department_id, task_text, full_transcript, spec_text=None):
    """議論全文から確定した決定事項を抽出し、D-list用のリストを作る(長期記憶)。
    1つのdecisionには1つの決定内容だけを入れる。複数の決定がある場合は配列を分ける。
    戻り値: [{"decision_type":..., "summary":..., "rationale":..., "confidence":...}, ...]
    """
    transcript_text = "\n".join(
        f"{m['speaker']}: {m['message']}" for m in full_transcript
    )

    #変更: chatは短文化したため、成果物spec.txtもD-list抽出の材料に含める
    if spec_text:
        spec_section = f"""
【成果物 spec.txt】
{spec_text}
"""
    else:
        spec_section = ""

    system_prompt = """あなたは議事録係です。以下のJSON形式で決定事項だけを抽出してください。
出力は必ずJSON配列のみにしてください。前置きや説明文、コードブロックの記号は一切含めないでください。

[
  {
    "decision_type": "spec_commitなど、決定の種類を表す短い英語タグ",
    "summary": "決定内容の要約(500文字以内)",
    "rationale": "決定の根拠(20~2000文字)",
    "confidence": 0.0から1.0の数値(この決定の確信度)
  }
]


「決定事項」の判定基準:
- 明確に「これに決定した」と言い切っている場合はもちろん対象です。
- それだけでなく、複数のメンバーが同意・賛成し、議論の中で繰り返し支持されている提案も
  「事実上合意された決定事項」とみなして抽出してください。
- 一人だけが提案していて他のメンバーからの賛同や反応がまだ無いものは含めないでください。
- 会話全体がまだ提案段階に見えても、その中で最も合意が強い項目については、
  確信度(confidence)を少し低めにした上で抽出して構いません。全て除外して空配列にする必要はありません。
- 1つのdecisionには1つの決定内容だけを入れてください。複数の異なる決定がある場合は、
  配列の要素を分けて、それぞれ別のdecisionとして出力してください。"""

    user_prompt = f"""部署: {department_id}
タスク: {task_text}
{spec_section}
以下は部署内での議論ログ(chat)です。ここから確定した決定事項だけを抽出してください。
まだ議論中で確定していない内容は含めないでください。

{transcript_text}"""

    raw = ask_llm(system_prompt, user_prompt)
    cleaned = clean_json_response(raw)

    try:
        decisions = json.loads(cleaned)
    except json.JSONDecodeError:
        # LLMがJSON以外の文章を混ぜて返してくることがあるための保険
        print("LLMの出力がJSONとして解析できませんでした。中身を確認してください:")
        print(raw)
        decisions = []

    return decisions
