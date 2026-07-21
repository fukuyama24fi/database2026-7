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


#新規: 実験設定(3ターン想定)の文字数定数。本番(5ターン)に切り替えるときは下のコメントアウトを入れ替える
TURN_SUMMARY_MAX_CHARS = 150
FINAL_SUMMARY_TARGET_CHARS = 450
# 本番設定(5ターン想定)
# TURN_SUMMARY_MAX_CHARS = 150
# FINAL_SUMMARY_TARGET_CHARS = 750


def make_turn_summary(task_text, turn_messages):
    #新規: 1ターン分(全員が1回ずつ発言した分)だけを短い要約に圧縮する。PM判定用の材料を作る
    transcript_text = "\n".join(
        f"{m['speaker']}: {m['message']}" for m in turn_messages
    )

    system_prompt = "あなたは会議の記録係です。要約以外の文章は出力しないでください。"
    user_prompt = f"""タスク: {task_text}

以下は1ターン分(全メンバーが1回ずつ発言した分)の議論です。
{TURN_SUMMARY_MAX_CHARS}字程度の日本語で要約してください。
要約以外の文章は出力しないでください。

{transcript_text}"""

    return ask_llm(system_prompt, user_prompt)


def join_turn_summaries(turn_summaries):
    #新規: 各ターンの要約をターン番号付きで連結する(LLM呼び出しなし。最終整形の材料を作る)
    return "\n".join(
        f"ターン{s['turn_number']}: {s['summary']}" for s in turn_summaries
    )


def polish_final_summary(task_text, turn_summaries):
    #新規: ターン要約の連結結果を、読みやすい1つの文章に整形する(既存make_summaryの置き換え)
    material = join_turn_summaries(turn_summaries)
    material_len = len(material)

    system_prompt = "あなたは会議の記録係です。整形結果以外の文章は出力しないでください。"
    user_prompt = f"""タスク: {task_text}

以下は各ターンの要約を連結した材料です。
この材料に書かれていない情報を付け加えないでください。
文字数は材料と同程度({FINAL_SUMMARY_TARGET_CHARS}字程度、最大でも{material_len}字を超えないこと)で構いません。
無理に短くする必要はありません。
ターンごとの内容を、時系列の流れが分かる自然な日本語の文章にまとめてください。

【材料】
{material}"""

    return ask_llm(system_prompt, user_prompt)
