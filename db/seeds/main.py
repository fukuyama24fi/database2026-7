from Dmployees import generate_employee_rows
from Leadership import generate_leadership_rows

from db_writer import (
    write_employees_to_db,
    write_leadership_to_db,
)


def main():
    employee_rows = generate_employee_rows()
    write_employees_to_db(employee_rows)

    exec_rows, leader_rows, persona_rows = generate_leadership_rows()

    write_leadership_to_db(
        exec_rows,
        leader_rows,
        persona_rows,
    )

    print("Seed completed.")


if __name__ == "__main__":
    from db_writer import reset_seed_tables
    reset_seed_tables()  #開発中はテーブルを初期化しておく
    main()