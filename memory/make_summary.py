from llm.ask_llm import ask_llm


def make_summary(task_text, full_transcript):
    #議論全文(full_transcript)から200字程度の日本語要約を作る(中期記憶)"""
    transcript_text = "\n".join(
        f"{m['speaker']}: {m['message']}" for m in full_transcript
    )

    system_prompt = "あなたは会議の記録係です。要約以外の文章は出力しないでください。"
    user_prompt = f"""タスク: {task_text}

以下は部署内での議論の全文です。200字程度の日本語で要約してください。

{transcript_text}"""

    return ask_llm(system_prompt, user_prompt)
