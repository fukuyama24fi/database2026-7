import os

import psycopg2


def connect_db():
    #DB接続を作る。既存の各ファイルと同じ接続設定を再利用
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "simulation"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "password"),
        port=os.getenv("DB_PORT", 5432),
    )
