#全エージェント共通のJSON出力ルール(ネガティブプロンプト+OK/NG例)

JSON_FORMAT_RULES = """
【絶対遵守：JSONフォーマットルール】
- 出力はJSONオブジェクト1つのみ。前置き・後書き・```json```囲み禁止
- 全値のクォート必須: 数値・文字列・カラーコード・単位(8px, #ffffff)も必ず "" で囲む
- Markdown記法禁止: JSON内部で - や --- や # の箇条書き・区切り線は使わない
- 複数要素は配列 ["A", "B"] を使う
- HTML/属性記述禁止: id = \\"login-form\\" のような複雑エスケープは避け "login-form" とだけ書く
- 改行は design_update 等の長文フィールド内のみ。chat/reason は1行

❌ NG例: "サイズ": 8px, "色": #fff, "構成": { "- タイトル" }
⭕ OK例: "サイズ": "8px", "色": "#fff", "構成": ["タイトル"]
"""

MEMBER_JSON_EXAMPLE = """
⭕ メンバー出力OK例:
{"chat": "レイアウト座標をdesignに反映", "design_update": "レイアウト\\n入力部座標: \\"100px\\", \\"280px\\""}
"""

CQO_JSON_EXAMPLE = """
⭕ CQO出力OK例:
{"verdict": "needs_rollback", "reason": "UIUXとFEのバリデーション矛盾", "conflicts": [{"conflict_id": "c1", "department_ids": ["UIUX", "FE"], "room_ids": ["room_x_00", "room_x_01"], "same_department": false, "severity_level": 4, "rollback_from_turn": 3, "affected_decisions": [{"room_id": "room_x_00", "decision_id": "dec_room_x_00_001"}], "description": "矛盾の具体"}]}
重要: 衝突詳細は reason ではなく必ず conflicts 配列に書く。reasonは1〜2文の要約のみ。
"""
