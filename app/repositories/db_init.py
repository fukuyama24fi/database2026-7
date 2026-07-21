import psycopg2 #pythonでPostgresSQLを使うとき
import os #PCのファイルや環境とやりとりできる

def init_db():
    #PostgresSQLサーバに接続
    database_connection = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME","simulation"),
        user=os.getenv("DB_USER","postgres"),
        password=os.getenv("DB_PASSWORD","password"),
        port=os.getenv("DB_PORT",5432) #デフォルト値
    )

    #データベース操作係　cursorはカーソル(位置を示すもの)
    db_operator = database_connection.cursor()
    print("---データベースの初期化を開始します---")

    #D-list保存用テーブル(department_rooms_decisions)(各ターンで確定した決定事項。重要。長期記憶)
    db_operator.execute('''
    CREATE TABLE IF NOT EXISTS department_rooms_decisions (
        id SERIAL PRIMARY KEY, --SERIALは数字を自動で増やす型。id = 1 id = 2って書かなくて済む
        room_id TEXT NOT NULL, --どの部署で決まった決定か。department_roomsの外部キー
        department_name TEXT NOT NULL, --決定を出した部署名
        decision_id TEXT NOT NULL, --決定内容の識別ID
        decision_type TEXT NOT NULL, --決定の種類(spec_commit、api_contract、data_modelなど)
        summary TEXT NOT NULL, --決定内容の要約テキスト
        rationale TEXT NOT NULL, --決定の根拠
        scope_anchor TEXT, --どの役職の判断軸に基づいた視点か(CFO:cost_dimension)
        confidence REAL, --決定の自信の強さ
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, --この行がいつ作られたか
        UNIQUE(room_id, decision_id) --重複を許さない
    )
    ''')
    print("department_room_decisionsテーブルを作成しました")

    #プロジェクト状態管理テーブル(project_states)
    db_operator.execute('''
    CREATE TABLE IF NOT EXISTS project_states (
        project_id TEXT PRIMARY KEY, ----プロジェクトを一意に識別するID
        current_phase TEXT NOT NULL, --現在のフェーズ(例:phase2_department_dev)
        status TEXT NOT NULL, --プロジェクトの状態(例:進行中、完了、差し戻し中など)
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP --updated_atは最後に更新された時刻
    )
    ''')
    print("project_statesテーブルを作成しました");


    #部署別開発ルーム状態テーブル(department_rooms)
    db_operator.execute('''
    CREATE TABLE IF NOT EXISTS department_rooms (
        room_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL, --project_statesの外部キー
        department_name TEXT NOT NULL, --このルームの担当部署
        original_task_text TEXT, --CTOから振られたタスク内容
        recent_messages TEXT, --直近5件の会話(短期記憶。JSON文字列)
        short_summary TEXT, --200字要約(中期記憶)
        status TEXT NOT NULL, --ルームの状態(例:進行中、完了、差し戻し中など)
        retry_count INTEGER DEFAULT 0, --差し戻し回数
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP     
    )
    ''')
    print("department_rooms テーブルを作成しました")

    #部署別一般社員テーブル(department_menbers_master)
    db_operator.execute('''
    CREATE TABLE IF NOT EXISTS department_members_master (
        member_id TEXT PRIMARY KEY, --Python側で決めたID(mem_00000など)
        department_id TEXT NOT NULL, --部門ID
        display_name TEXT NOT NULL, --名前
        personality TEXT, --性格(例:論理的、慎重など)
        skills TEXT, --スキル。JSON文字列として保存
        is_active BOOLEAN DEFAULT TRUE, --すでにルームに入っていないか(拡張機能として、1つの部署内に複数ルームを取り入れるときに使う可能性あり)
        agent_persona_id TEXT, --agent_personasへの紐付け(まだFK制約はつけない)
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    print("department_members_masterテーブルを作成しました")

    #経営陣テーブル(executives_master)(CEO,CTO,CFO,CQO)
    db_operator.execute('''
    CREATE TABLE IF NOT EXISTS executives_master (
        role_id TEXT PRIMARY KEY, --"CEO","CTO","CFO","CQO"を直接入れる
        display_name TEXT NOT NULL,
        agent_persona_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    print("executives_masterテーブルを作成しました")

    #部署リーダーテーブル(department_leaders_master)(部長とPM)
    db_operator.execute('''
    CREATE TABLE IF NOT EXISTS department_leaders_master (
        department_id TEXT PRIMARY KEY,
        department_name TEXT NOT NULL,
        manager_name TEXT NOT NULL, --部長の名前
        pm_name TEXT NOT NULL, --PMの名前
        agent_persona_id_manager TEXT,
        agent_persona_id_pm TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK (manager_name <> pm_name)
    )
    ''')
    print("department_leaders_masterテーブルを作成しました")

    #人格テーブル(agent_personas)
    db_operator.execute('''
    CREATE TABLE IF NOT EXISTS agent_personas (
        agent_persona_id TEXT PRIMARY KEY,
        role_type TEXT NOT NULL, --"member"として固定(このCSVは職人用)
        department_id TEXT NOT NULL, 
        judgment_anchor TEXT, --部署ごとの専門領域の判断軸。JSON文字列として保存
        style_persona TEXT --性格詳細。JSON文字列として保存
    )
    ''')
    print("agent_personasテーブルを作成しました")
    
    db_operator.execute('''
    CREATE TABLE IF NOT EXISTS staging_employees (
        member_id TEXT,
        department_id TEXT,
        display_name TEXT,
        personality TEXT,
        skills TEXT,
        agent_persona_id TEXT,
        role_type TEXT,
        judgment_anchor TEXT,
        style_persona TEXT
    )
    ''')
    print("staging_employeesテーブルを作成しました")


    #コミット。これがないと作ったテーブルが仮置きになり、プログラム終了時に変更が全部消える
    database_connection.commit()

    #接続を切る。
    database_connection.close()

    print("---データベースの初期化が完了しました---")

    #直接実行時のみ動く。
    # 他のプログラムでこのファイル内の関数を使うとき、importしたら勝手にデータベースの初期化(上書き)が起こる
if __name__ == "__main__":
    #処理開始
    init_db()