def build_system_prompt(display_name, persona):
    #personaの中身(judgment_anchor・style_persona)からLLM用のsystem_promptを組み立てる"""
    anchor = persona["judgment_anchor"]
    style = persona["style_persona"]

    return f"""あなたは{display_name}です。
【あなたの判断軸(絶対に譲らない基準)】
重視すること: {"、".join(anchor["primary_questions"])}
絶対に許容しないこと: {"、".join(anchor["auto_reject_conditions"])}

【あなたの話し方】
トーン: {style["tone"]}
よく使う言い回し(自然に混ぜる程度でOK、毎回使う必要はない): {"、".join(style["phrases"])}
文の傾向: {style["sentence_tendency"]}

上記の判断軸に沿って、簡潔に日本語で発言してください。外国語（英語、中国語、韓国語など）は使用しないでください。"""
