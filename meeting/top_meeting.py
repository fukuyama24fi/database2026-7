#上流会議。CTOと選ばれた各部長が担当領域について話し合う
#CTOの部署配分に部長が合意するか確認し、反対があればCTOに修正させる

from roles.cto import cto_fix_assignments
from roles.manager import ask_managers_agreement


def run_top_meeting(task_text, assignments, max_rounds=3):
    """CTOの部署配分について、各部署の部長が合意するか確認する上流会議。
    反対意見が出た場合はCTOに配分を修正させて再確認する(最大max_rounds回)。

    戻り値: 最終的な部署配分のリスト
    """
    current_assignments = assignments

    for round_num in range(1, max_rounds + 1):
        print(f"\n=== 上流会議 ラウンド{round_num} ===")
        verdicts = ask_managers_agreement(task_text, current_assignments)

        for v in verdicts:
            print(f"[{v['department_id']}] {v['verdict']} - {v['reason']}")

        disagreements = [v for v in verdicts if v.get("verdict") != "agree"]

        if not disagreements:
            print("全部署が合意しました")
            return current_assignments

        if round_num == max_rounds:
            print("最大ラウンドに達しました。現在の配分のまま進めます")
            return current_assignments

        print(f"{len(disagreements)}件の反対意見があります。CTOに配分を修正させます")
        current_assignments = cto_fix_assignments(task_text, current_assignments, disagreements)

    return current_assignments
