#build_user_prompt内でchat最大文字数として参照(parse_json側にも同名定数あり)
CHAT_MAX_CHARS = 200

from prompts.json_format_rules import JSON_FORMAT_RULES, MEMBER_JSON_EXAMPLE


def build_user_prompt(
    task_text,
    recent_messages,
    reference_context=None,
    current_design="",
    team_memo="",
    expects_code=True,
    member_role="未割当",
    other_dept_info="",
):
    #メンバーLLM向けuser_prompt(タスク・履歴・design.txt・差し戻し指摘をまとめる)
    if recent_messages:
        history_text = "\n".join(
            f"{m['speaker']}: {m['message']}" for m in recent_messages
        )
    else:
        history_text = "(まだ発言はありません)"

    reference_section = ""
    if reference_context:
        reference_section = f"""
【部長からの差し戻し指摘】
{reference_context}
"""

    if team_memo:
        team_section = f"""
【チームメンバー(team_memo.txt)】
{team_memo}
"""
    else:
        team_section = ""

    if other_dept_info:
        peer_section = f"""
{other_dept_info}
"""
    else:
        peer_section = ""

    if current_design:
        design_section = f"""
【現在の成果物 design.txt】
{current_design}
"""
    else:
        design_section = """
【現在の成果物 design.txt】
(まだ内容はありません)
"""

    if expects_code:
        design_guide = """- 次のような「実装可能な具体情報」を優先して書く:
  * 画面/コンポーネント名、入力項目(名前・型・必須・placeholder・エラー文言)
  * API/データ構造(JSONキー名)、状態管理の変数名、画面遷移条件
  * 書ける場合はコード片(HTML/CSS/TSX/Python等)"""
    else:
        design_guide = """- 本タスクは設計・デザイン担当のため、コードは不要。次のような「具体的な設計仕様」を書く:
  * 画面構成・ワイヤー・情報設計・コンポーネント名・レイアウト(配置・サイズ)
  * 色・ typography・状態(通常/エラー/ disabled)・遷移条件
  * 入力項目定義(名前・必須・バリデーション・エラー文言)"""

    return f"""タスク: {task_text}
{team_section}
{peer_section}
{design_section}
これまでの会話(直近):
{history_text}
{reference_section}
あなたは次の発言者です。
あなたの担当役割(PM割当): {member_role}
- 自分の担当役割の範囲のみ design.txt を更新すること。他メンバーの担当領域に書かない。

【成果物の書き方(design.txt / design_update)】
- 議論の本体は design_update に書く。chat は「何を更新したか」の報告のみ(最大{CHAT_MAX_CHARS}字)
- design_update は design.txt の最新版全文(1つの統一フォーマット)。Markdown見出し形式を推奨
- 「# 追記・修正」など履歴セクションは書かない(旧版はシステムが design_history.txt に自動保存)
- 既存 design.txt をベースに、自分の担当範囲を反映した完全版を毎回出力すること
- 毎ターン、1つ以上の具体項目を追加・修正すること(空文字 "" は不可)
{design_guide}
- 次のような「一般論だけ」は chat にも design にも書かない:
  * 「UXを向上させる」「ユーザー目線が重要」など中身のない抽象論
  * タスクに紐づかない教科書的説明

出力は必ず以下のJSON形式のみにしてください。前置きや説明文、コードブロック記号(```)はJSONの外に書かないでください。
{JSON_FORMAT_RULES}
{MEMBER_JSON_EXAMPLE}
- chat: 最大{CHAT_MAX_CHARS}字・1行のみ・改行不可
- design_update: design.txt の新しい全文(JSON文字列内で改行可。値はすべて "" で囲む)

{{
  "chat": "...",
  "design_update": "..."
}}"""
