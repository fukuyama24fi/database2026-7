import json

from Data import DEPARTMENTS
from RoomManager import get_persona
from Discussion import build_system_prompt
from llmClient import ask_llm
from Jsonutils import clean_json_response

CTO_PERSONA_ID = "persona_exec_cto"  # leadership.pyで生成したCTOのagent_persona_id


def assign_departments(task_text):
    """CTOがプロジェクト要件を読み、関係する部署と各部署へのタスクを決める
    (設計書2.1のCTOの責務:技術的な実現可能性を判断し、部署へ配分する)

    戻り値: [{"department_id": "FE", "sub_task_text": "..."}, ...]
    """
    persona = get_persona(CTO_PERSONA_ID)
    if persona is None:
        print("CTOのpersonaが見つかりません。leadership.pyの実行結果を確認してください")
        return []

    system_prompt = build_system_prompt("CTO", persona)

    department_list_text = "\n".join(
        f"{code}: {name}" for code, name in DEPARTMENTS.items()
    )

    user_prompt = f"""以下のプロジェクト要件を読み、関係する部署を選び、
各部署に対する具体的なタスク内容を割り振ってください。

【プロジェクト要件】
{task_text}

【部署一覧(コード: 名称)】
{department_list_text}

出力は必ず以下のJSON配列のみにしてください。前置きや説明文、コードブロックの記号は一切含めないでください。
本当に必要な部署だけを選んでください(全部署を無理に含める必要はありません)。

部署間に依存関係がある場合(例:UIデザインが先に決まらないと実装できない)は、
orderで実行順序を、depends_onで前提となる部署のコードを指定してください。
依存関係が無い部署はdepends_onを空配列[]にしてください。同じorder番号の部署は並行実施可能とみなします。

[
  {{
    "department_id": "FEなど、部署一覧のコードのいずれか",
    "sub_task_text": "その部署が具体的に何をすべきかの説明",
    "order": 1から始まる整数(実行順序。依存関係が無ければ全部1でよい),
    "depends_on": ["この部署が始まる前に完了しているべき部署のコード"]
  }}
]"""

    raw = ask_llm(system_prompt, user_prompt)
    cleaned = clean_json_response(raw)

    try:
        assignments = json.loads(cleaned)
    except json.JSONDecodeError:
        print("CTOの出力がJSONとして解析できませんでした:")
        print(raw)
        assignments = []

    return assignments


def revise_assignments(task_text, assignments, disagreements):
    """部署の部長からの反対意見を踏まえて、CTOが部署配分を修正する
    (上流会議で使う。設計書2.1のCTOの責務:部署配分の妥当性判断)
    """
    persona = get_persona(CTO_PERSONA_ID)
    if persona is None:
        print("CTOのpersonaが見つかりません。元の配分を維持します")
        return assignments

    system_prompt = build_system_prompt("CTO", persona)

    assignment_text = "\n".join(
        f"{a['department_id']}: {a['sub_task_text']}" for a in assignments
    )
    disagreement_text = "\n".join(
        f"{d['department_id']}: {d['reason']}" for d in disagreements
    )
    department_list_text = "\n".join(
        f"{code}: {name}" for code, name in DEPARTMENTS.items()
    )

    user_prompt = f"""以下は現在の部署配分と、それに対する部長からの反対意見です。
反対意見を踏まえて、部署配分を修正してください。

重要: タスクの文言を直すだけでなく、根本的な見直しも検討してください。
- 反対している部署が本当に適切な担当か疑わしい場合、その部署を配分から外して構いません。
- 別の部署の方が適任だと判断した場合、新しく部署を追加しても構いません。
- 単に文言が曖昧なだけで担当自体は正しい場合は、タスクの説明を明確にするだけで構いません。
- 現在選ばれていない部署についても、今回の反対意見を踏まえて改めて見て、
  本当は必要なのに漏れている部署が無いか、毎回ゼロから見直してください。
  現在の配分に引きずられず、部署一覧全体から再検討して構いません。
どちらが適切かは、反対意見の内容から判断してください。

【プロジェクト要件】
{task_text}

【現在の部署配分】
{assignment_text}

【反対意見】
{disagreement_text}

【部署一覧(コード: 名称)】
{department_list_text}

出力は必ず以下のJSON配列のみにしてください。前置きや説明文、コードブロックの記号は一切含めないでください。
実行順序(order)・依存関係(depends_on)も、必要に応じて見直して構いません。

[
  {{
    "department_id": "FEなど、部署一覧のコードのいずれか",
    "sub_task_text": "その部署が具体的に何をすべきかの説明",
    "order": 1から始まる整数(実行順序。依存関係が無ければ全部1でよい),
    "depends_on": ["この部署が始まる前に完了しているべき部署のコード"]
  }}
]"""

    raw = ask_llm(system_prompt, user_prompt)
    cleaned = clean_json_response(raw)

    try:
        new_assignments = json.loads(cleaned)
    except json.JSONDecodeError:
        print("CTOの修正案がJSONとして解析できませんでした。元の配分を維持します:")
        print(raw)
        new_assignments = assignments

    return new_assignments