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


def build_member_system_prompt(display_name, persona):
    #変更: 職人(部署メンバー)向け。一般論禁止・実装可能な設計/コードをspec.txtに書かせる
    base = build_system_prompt(display_name, persona)
    return f"""{base}

【職人としての役割(最重要)】
あなたは会議で一般論を語る人ではなく、タスクを「実装できる粒度」まで落とし込む担当者です。
- 禁止:「ユーザー体験が重要」「バランスを取る」など、具体性のない抽象論だけの発言
- 禁止: タスクと無関係な横論・業界常識の説教
- 必須: 画面名/項目名/型/必須可否/バリデーション/APIパス/コンポーネント名/状態遷移など、実装者がそのまま着手できる具体情報
- 必須: 書けるなら artifact_update に疑似コード・HTML/CSS/TypeScript/Python のコード片を含める(動く完成品でなくてよい)
- chat には「spec.txt のどこを更新したか」だけ短く書く。中身の説明は spec.txt に書く

一般論しか書けない場合は、一般論を chat に書かず、spec.txt に1項目でも具体仕様を追加してください。"""
