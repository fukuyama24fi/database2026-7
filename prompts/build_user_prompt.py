def build_user_prompt(task_text, recent_messages, reference_context=None): #参照情報があるときは渡す
    """直近の会話履歴(短期記憶)を踏まえたuser_promptを組み立てる"""
    if recent_messages:
        history_text = "\n".join(
            f"{m['speaker']}: {m['message']}" for m in recent_messages
        )
    else:
        history_text = "(まだ発言はありません)"

    return f"""タスク: {task_text}
これまでの会話:
{history_text}

あなたは次の発言者です。

前の発言に賛成・反対・補足・改善案を述べてください。
新しい観点を1つ以上追加してください。。
外国語（英語、中国語、韓国語など）は使用しないでください。"""
