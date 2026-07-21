import csv
import os

import psycopg2

from simulation.db.connect import connect_db


def write_employees_to_db(rows):
    output_filepath = "employees_seed.csv"
    with open(
        output_filepath, "w", newline="", encoding="utf-8"
    ) as f:  # "W":書き込みモード。newline="":二重改行を防ぐ
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()  # 列名
        writer.writerows(rows)

    print(f"{len(rows)}件を {output_filepath} に書き出しました。")

    print("--- ステージングテーブルへの流し込みを開始します ---")

    # DBに接続
    database_connection = connect_db()
    db_operator = database_connection.cursor()

    # COPYコマンドの実行
    with open(output_filepath, "r", encoding="utf-8") as f:
        # FROM STDIN:ファイルfの中身をPostgreSQLにつながるSTDINに流す。意味は分かっていない
        db_operator.copy_expert("COPY staging_employees FROM STDIN WITH CSV HEADER", f)

    print("CSVデータを staging_employees に流し込みました。")

    # 各テーブルに社員情報を振り分ける
    #department_members_masterへ
    db_operator.execute("""
        INSERT INTO department_members_master
            (member_id, department_id, display_name, personality, skills, agent_persona_id)
        SELECT member_id, department_id, display_name, personality, skills, agent_persona_id
        FROM staging_employees
        """)

    #agent_personasへ
    db_operator.execute("""
        INSERT INTO agent_personas
            (agent_persona_id, role_type, department_id, judgment_anchor, style_persona)
        SELECT agent_persona_id, role_type, department_id, judgment_anchor, style_persona
        FROM staging_employees
        """)

    database_connection.commit()
    print("本番テーブルへの振り分けが完了しました")

    db_operator.execute("TRUNCATE TABLE staging_employees") #中身を空にする
    database_connection.commit()

    #デバッグ
    db_operator.execute("SELECT COUNT(*) FROM department_members_master")
    print("department_members_master件数:", db_operator.fetchone()[0])

    db_operator.execute("SELECT COUNT(*) FROM agent_personas")
    print("agent_personas件数:", db_operator.fetchone()[0])


    database_connection.commit()
    db_operator.close()
    database_connection.close()

    print("--- すべての工程が完了しました ---")


def write_leadership_to_db(executive_rows, leader_rows, persona_rows):

    print("--- 役員・部長・PMの登録を開始します ---")

    database_connection = connect_db()
    db_operator = database_connection.cursor()

    for row in persona_rows:
        db_operator.execute(
            """
            INSERT INTO agent_personas
                (agent_persona_id, role_type, department_id, judgment_anchor, style_persona)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                row["agent_persona_id"],
                row["role_type"],
                row["department_id"],
                row["judgment_anchor"],
                row["style_persona"],
            ),
        )

    for row in executive_rows:
        db_operator.execute(
            """
            INSERT INTO executives_master (role_id, display_name, agent_persona_id)
            VALUES (%s, %s, %s)
            """,
            (row["role_id"], row["display_name"], row["agent_persona_id"]),
        )

    for row in leader_rows:
        db_operator.execute(
            """
            INSERT INTO department_leaders_master
                (department_id, department_name, manager_name, pm_name,
                 agent_persona_id_manager, agent_persona_id_pm)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                row["department_id"],
                row["department_name"],
                row["manager_name"],
                row["pm_name"],
                row["agent_persona_id_manager"],
                row["agent_persona_id_pm"],
            ),
        )

    database_connection.commit()
    print("executives_master / department_leaders_master / agent_personas への登録が完了しました")

    db_operator.execute("SELECT COUNT(*) FROM executives_master")
    print("executives_master件数:", db_operator.fetchone()[0])

    db_operator.execute("SELECT COUNT(*) FROM department_leaders_master")
    print("department_leaders_master件数:", db_operator.fetchone()[0])

    db_operator.execute("SELECT COUNT(*) FROM agent_personas")
    print("agent_personas件数(9974+26=10000のはず):", db_operator.fetchone()[0])

    db_operator.close()
    database_connection.close()

    print("--- 役員・部長・PMの登録が完了しました ---")


def reset_seed_tables():
    #初期化開発中の動作確認用。
    connection = connect_db()
    db_operator = connection.cursor()
    # 外部キー依存がある場合は削除順に注意
    db_operator.execute("TRUNCATE TABLE department_members_master, agent_personas, executives_master, department_leaders_master")
    connection.commit()
    db_operator.close()
    connection.close()
    print("既存のseedデータを削除しました")
