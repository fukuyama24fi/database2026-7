from simulation.seed.make_employees import make_employee_data
from simulation.seed.make_leaders import make_leader_data
from simulation.seed.writer import (
    write_employees_to_db,
    write_leadership_to_db,
)


def main():
    employee_rows = make_employee_data()
    write_employees_to_db(employee_rows)

    exec_rows, leader_rows, persona_rows = make_leader_data()

    write_leadership_to_db(
        exec_rows,
        leader_rows,
        persona_rows,
    )

    print("Seed completed.")


if __name__ == "__main__":
    from simulation.seed.writer import reset_seed_tables
    reset_seed_tables()  #開発中はテーブルを初期化しておく
    main()
