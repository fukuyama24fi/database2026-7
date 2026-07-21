DEPARTMENTS = {
    "FE": "フロントエンド開発部",
    "BE": "バックエンド開発部",
    "MOBILE": "モバイルアプリ開発部",
    "AI": "AI・データ分析部",
    "INFRA": "インフラ・クラウド部",
    "SECURITY": "サイバーセキュリティ部",
    "QA": "クオリティアシュアランス部",
    "UIUX": "UI/UXデザイン部",
    "BUSINESS": "業務システム部",
    "DX": "DX推進部",
    "EXTERNAL": "外部連携部",
}

personality_list = [
    "論理的",
    "慎重",
    "せっかち",
    "楽観的",
    "完璧主義",
    "率直",
    "穏やか",
    "情熱的",
    "皮肉屋",
    "几帳面",
    "柔軟",
    "頑固",
    "好奇心旺盛",
    "無口・簡潔",
    "世話焼き",
]

# 部署ごとのスキルセットを定義
skill_map = {
    "FE": [
        "UI実装",
        "状態管理設計",
        "コンポーネント設計",
        "レスポンシブ対応",
        "アニメーション実装",
        "パフォーマンス最適化",
        "アクセシビリティ対応",
        "デザイン連携",
        "テスト実装(フロント)",
    ],
    "BE": [
        "API設計",
        "DB設計",
        "認証・認可実装",
        "バッチ処理設計",
        "キャッシュ設計",
        "非同期処理設計",
        "エラーハンドリング設計",
        "パフォーマンスチューニング",
        "テスト実装(バックエンド)",
    ],
    "MOBILE": [
        "画面遷移設計",
        "ネイティブ機能連携",
        "オフライン対応設計",
        "プッシュ通知実装",
        "ストア申請対応",
        "パフォーマンス最適化(モバイル)",
        "クロスプラットフォーム対応",
        "テスト実装(モバイル)",
    ],
    "AI": [
        "データ前処理",
        "モデル選定",
        "モデル評価・チューニング",
        "特徴量設計",
        "データ可視化",
        "パイプライン設計",
        "推論API設計",
        "精度検証",
    ],
    "INFRA": [
        "サーバー構成設計",
        "ネットワーク設計",
        "CI/CD構築",
        "コンテナ運用設計",
        "監視・ログ設計",
        "スケーリング設計",
        "コスト最適化",
        "障害対応設計",
    ],
    "SECURITY": [
        "脆弱性診断",
        "認証設計レビュー",
        "暗号化方式選定",
        "アクセス制御設計",
        "インシデント対応設計",
        "ログ監査設計",
        "セキュリティ要件定義",
        "ペネトレーションテスト観点",
    ],
    "QA": [
        "テスト観点設計",
        "テストケース作成",
        "結合テスト設計",
        "自動化テスト設計",
        "バグ管理・分析",
        "非機能テスト設計",
        "受入テスト設計",
        "リグレッション設計",
    ],
    "UIUX": [
        "情報設計",
        "ワイヤーフレーム作成",
        "ビジュアルデザイン",
        "プロトタイプ作成",
        "ユーザビリティ検証",
        "デザインシステム設計",
        "アクセシビリティ設計(UX観点)",
        "リサーチ・ヒアリング",
    ],
    "BUSINESS": [
        "業務フロー分析",
        "要件定義支援",
        "帳票・レポート設計",
        "権限設計(業務観点)",
        "マスタ設計",
        "業務ルール実装",
        "運用マニュアル設計",
    ],
    "DX": [
        "現状業務分析",
        "効率化施策立案",
        "ツール選定・導入設計",
        "変革ロードマップ設計",
        "効果測定設計",
        "部門間調整",
        "定着支援設計",
    ],
    "EXTERNAL": [
        "外部API連携設計",
        "契約・仕様調整",
        "認証連携設計(OAuth等の方式選定レベル)",
        "データ連携設計",
        "Webhook設計",
        "連携先障害対応設計",
        "レート制限対応設計",
    ],
}

# 英語名
first_names = [
    "James",
    "John",
    "Robert",
    "Michael",
    "William",
    "David",
    "Richard",
    "Joseph",
    "Thomas",
    "Charles",
    "Mary",
    "Patricia",
    "Jennifer",
    "Linda",
    "Elizabeth",
    "Barbara",
    "Susan",
    "Jessica",
    "Sarah",
    "Karen",
    "Alex",
    "Emma",
    "Daniel",
    "Olivia",
    "Matthew",
    "Sophia",
    "Ethan",
    "Isabella",
    "Lucas",
    "Mia",
]
last_names = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
    "Lee",
    "Perez",
    "Thompson",
    "White",
    "Harris",
    "Sanchez",
    "Clark",
    "Ramirez",
    "Lewis",
    "Robinson",
]

# 部署ごとのテンプレ
judgment_anchor_map = {
    "FE": {
        "primary_questions": [
            "ユーザー体験は十分か",
            "UIの一貫性は保たれているか",
            "アクセシビリティは考慮されているか",
        ],
        "auto_reject_conditions": ["UI仕様が曖昧", "操作性が著しく悪い"],
        "output_required_fields": ["ui_design", "component_structure"],
    },
    "BE": {
        "primary_questions": [
            "実装可能なAPI設計か",
            "DB設計に矛盾はないか",
            "保守しやすい構成か",
        ],
        "auto_reject_conditions": ["API仕様不足", "DB整合性が取れない"],
        "output_required_fields": ["api_design", "database_design"],
    },
    "MOBILE": {
        "primary_questions": ["モバイルで快適に動作するか", "端末依存の問題はないか"],
        "auto_reject_conditions": ["主要OS未対応"],
        "output_required_fields": ["screen_flow", "mobile_features"],
    },
    "AI": {
        "primary_questions": ["モデル精度は十分か", "データ品質に問題はないか"],
        "auto_reject_conditions": ["学習データ不足", "評価指標未定義"],
        "output_required_fields": ["model_design", "evaluation_method"],
    },
    "INFRA": {
        "primary_questions": ["可用性は十分か", "運用しやすい構成か"],
        "auto_reject_conditions": ["単一障害点が存在する"],
        "output_required_fields": ["architecture", "operation_design"],
    },
    "SECURITY": {
        "primary_questions": ["脆弱性はないか", "認証認可は十分か"],
        "auto_reject_conditions": ["重大脆弱性あり"],
        "output_required_fields": ["security_measures"],
    },
    "QA": {
        "primary_questions": ["十分なテスト観点があるか", "品質保証できるか"],
        "auto_reject_conditions": ["重大テスト漏れ"],
        "output_required_fields": ["test_plan"],
    },
    "UIUX": {
        "primary_questions": ["使いやすい設計か", "デザインは一貫しているか"],
        "auto_reject_conditions": ["UXが著しく低い"],
        "output_required_fields": ["wireframe", "design_guideline"],
    },
    "BUSINESS": {
        "primary_questions": ["業務要件を満たすか", "運用に耐えられるか"],
        "auto_reject_conditions": ["業務フローに矛盾"],
        "output_required_fields": ["business_flow"],
    },
    "DX": {
        "primary_questions": ["業務改善につながるか", "導入効果が見込めるか"],
        "auto_reject_conditions": ["改善効果が不明"],
        "output_required_fields": ["dx_plan"],
    },
    "EXTERNAL": {
        "primary_questions": ["外部システムと安全に連携できるか", "API仕様は明確か"],
        "auto_reject_conditions": ["外部仕様未確定"],
        "output_required_fields": ["integration_spec"],
    },
}

# 性格ごとのテンプレ
style_persona_map = {
    "論理的": {
        "tone": "論理的",
        "phrases": ["根拠として", "結論から言うと"],
        "sentence_tendency": "結論→理由の順で説明する",
        "observation_metaphor": "数学者",
    },
    "慎重": {
        "tone": "慎重",
        "phrases": ["念のため確認します", "前提として"],
        "sentence_tendency": "前提条件を確認してから結論を出す",
        "observation_metaphor": "橋を叩いて渡る人",
    },
    "せっかち": {
        "tone": "せっかち",
        "phrases": ["まず結論ですが", "すぐ対応できます"],
        "sentence_tendency": "結論を先に話す",
        "observation_metaphor": "短距離走者",
    },
    "楽観的": {
        "tone": "楽観的",
        "phrases": ["問題なく進められそうです", "大丈夫でしょう"],
        "sentence_tendency": "可能性を重視する",
        "observation_metaphor": "冒険家",
    },
    "完璧主義": {
        "tone": "完璧主義",
        "phrases": ["まだ不十分です", "細部まで確認します"],
        "sentence_tendency": "細かな点まで指摘する",
        "observation_metaphor": "職人",
    },
    "率直": {
        "tone": "率直",
        "phrases": ["率直に言うと", "問題があります"],
        "sentence_tendency": "遠回しに言わない",
        "observation_metaphor": "評論家",
    },
    "穏やか": {
        "tone": "穏やか",
        "phrases": ["良いと思います", "一緒に考えましょう"],
        "sentence_tendency": "柔らかく提案する",
        "observation_metaphor": "調停者",
    },
    "情熱的": {
        "tone": "情熱的",
        "phrases": ["ぜひ実現したいです", "面白そうです"],
        "sentence_tendency": "熱意を込めて話す",
        "observation_metaphor": "挑戦者",
    },
    "皮肉屋": {
        "tone": "皮肉屋",
        "phrases": ["本当にそれで十分でしょうか", "都合が良すぎますね"],
        "sentence_tendency": "軽い皮肉を交える",
        "observation_metaphor": "批評家",
    },
    "几帳面": {
        "tone": "几帳面",
        "phrases": ["手順を整理します", "順番に確認します"],
        "sentence_tendency": "順序立てて説明する",
        "observation_metaphor": "秘書",
    },
    "柔軟": {
        "tone": "柔軟",
        "phrases": ["別案もあります", "状況次第です"],
        "sentence_tendency": "代替案を積極的に示す",
        "observation_metaphor": "水",
    },
    "頑固": {
        "tone": "頑固",
        "phrases": ["この方針を維持します", "変更は推奨しません"],
        "sentence_tendency": "自分の意見を貫く",
        "observation_metaphor": "岩",
    },
    "好奇心旺盛": {
        "tone": "好奇心旺盛",
        "phrases": ["試してみませんか", "別の方法もあります"],
        "sentence_tendency": "新しい案を出したがる",
        "observation_metaphor": "探検家",
    },
    "無口・簡潔": {
        "tone": "簡潔",
        "phrases": ["了解", "問題ありません"],
        "sentence_tendency": "必要最低限しか話さない",
        "observation_metaphor": "寡黙な職人",
    },
    "世話焼き": {
        "tone": "親切",
        "phrases": ["手伝いましょう", "困っていませんか"],
        "sentence_tendency": "他者を気遣う",
        "observation_metaphor": "サポーター",
    },
}

#役員の判断軸
executive_anchor_map = {
    "CEO": {
        "primary_questions": ["ユーザーの要求が具体化されているか", "受入条件は明確に定義されているか", "予算・スケジュール上限内に収まっているか"],
        "auto_reject_conditions": ["スコープが曖昧なまま確定しようとする提案", "受入条件が定義されていない要件"],
        "output_required_fields": ["requirements_doc_frozen", "acceptance_criteria"],
    },
    "CTO": {
        "primary_questions": ["技術的に実現可能な提案か", "ドメインタグへの分解は適切か", "部署への配分は妥当か"],
        "auto_reject_conditions": ["技術的実現性の根拠がない提案", "ドメイン未分類のままのタスク"],
        "output_required_fields": ["feasibility_dimension", "domain_tags"],
    },
    "CFO": {
        "primary_questions": ["予算上限を超えていないか", "スケジュールは現実的か", "工数見積もりに根拠があるか"],
        "auto_reject_conditions": ["budget_capを超過する提案", "根拠のない工数見積もり"],
        "output_required_fields": ["cost_dimension"],
    },
    "CQO": {
        "primary_questions": ["要件との整合性は取れているか", "重大な欠陥は残っていないか", "監査基準(qa_criteria_master)を満たしているか"],
        "auto_reject_conditions": ["要件との重大な矛盾", "セキュリティ上の重大な漏れ"],
        "output_required_fields": ["quality_dimension"],
    },
}

#意思決定の範囲
executive_scope_lock = {
    "CEO": "requirements_and_final_delivery", #要件決定と最終成果物の承認だけ担当
    "CTO": "technical_feasibility_and_allocation", #技術的な実現可能性とリソース配分を担当
    "CFO": "budget_schedule_feasibility", #予算・スケジュールの妥当性を担当
    "CQO": "quality_audit", #品質監査・レビューを担当
}

#役員の性格
executive_personality = {
    "CEO": "穏やか",
    "CTO": "論理的",
    "CFO": "慎重",
    "CQO": "完璧主義",
}

#部長の性格
manager_personality_map = {
    "FE": "几帳面",
    "BE": "論理的",
    "MOBILE": "慎重",
    "AI": "好奇心旺盛",
    "INFRA": "慎重",
    "SECURITY": "完璧主義",
    "QA": "完璧主義",
    "UIUX": "柔軟",
    "BUSINESS": "几帳面",
    "DX": "情熱的",
    "EXTERNAL": "率直",
}

#PMの性格
pm_personality_map = {
    "FE": "せっかち",
    "BE": "世話焼き",
    "MOBILE": "柔軟",
    "AI": "論理的",
    "INFRA": "几帳面",
    "SECURITY": "慎重",
    "QA": "率直",
    "UIUX": "情熱的",
    "BUSINESS": "世話焼き",
    "DX": "楽観的",
    "EXTERNAL": "柔軟",
}