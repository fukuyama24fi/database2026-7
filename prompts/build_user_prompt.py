CHAT_MAX_CHARS = 200  #変更: メンバー進行用chatの最大文字数


def build_user_prompt(task_text, recent_messages, reference_context=None, current_spec=""):
    """直近の会話履歴(短期記憶)を踏まえたuser_promptを組み立てる"""
    if recent_messages:
        history_text = "\n".join(
            f"{m['speaker']}: {m['message']}" for m in recent_messages
        )
    else:
        history_text = "(まだ発言はありません)"

    #変更: 部長差し戻し時にrevision_reportをメンバーへ渡す
    reference_section = ""
    if reference_context:
        reference_section = f"""
【部長からの差し戻し指摘】
{reference_context}
"""

    #変更: 全員共有の成果物spec.txtの現状を渡す(議論の本体はここに書く)
    if current_spec:
        spec_section = f"""
【現在の成果物 spec.txt】
{current_spec}
"""
    else:
        spec_section = """
【現在の成果物 spec.txt】
(まだ内容はありません)
"""

    return f"""タスク: {task_text}
{spec_section}
これまでの会話(直近):
{history_text}
{reference_section}
あなたは次の発言者です。

【成果物の書き方(spec.txt / artifact_update)】
- 議論の本体は必ず artifact_update に書く。chat は「何を更新したか」の報告のみ(最大{CHAT_MAX_CHARS}字)
- 毎ターン、artifact_update で spec.txt 全文を更新すること(変更がなければ空文字 "" は不可。必ず1つ以上の具体項目を追加・修正)
- 次のような「実装可能な具体情報」を優先して書く:
  * 画面/コンポーネント名、入力項目(名前・型・必須・placeholder・エラー文言)
  * API/データ構造(JSONキー名)、状態管理の変数名、画面遷移条件
  * レイアウト(配置・サイズ・クラス名)、アクセシビリティ属性(aria-*)
  * 書ける場合はコード片(HTML/CSS/TSX/Python等)。将来の実装・部長検収の材料にする
- 次のような「一般論だけ」は chat にも spec にも書かない:
  * 「UXを向上させる」「ユーザー目線が重要」「デザインの一貫性が大切」など中身のない文
  * タスクに紐づかない抽象論・教科書的説明

出力は必ず以下のJSON形式のみにしてください。前置きや説明文、コードブロック記号(```)はJSONの外に書かないでください。
- chat: 最大{CHAT_MAX_CHARS}字・1行のみ・改行不可
- artifact_update: spec.txt の新しい全文(JSON文字列内で改行可)

{{
  "chat": "...",
  "artifact_update": "..."
}}"""
