import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "simulation"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "password"),
    port=os.getenv("DB_PORT", 5432),
)
cur = conn.cursor()
cur.execute(
    "SELECT room_id, department_name, original_task_text, short_summary FROM department_rooms WHERE room_id = %s",
    ("room_test_0010",),
)
row = cur.fetchone()
print("room_id:", repr(row[0]))
print("department_name:", repr(row[1]))
print("original_task_text:", repr(row[2]))
print("short_summary:", repr(row[3]))

cur.close()
conn.close()