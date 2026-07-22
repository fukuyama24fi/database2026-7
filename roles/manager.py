import json

from db.read import get_department_leader, get_persona
from llm.ask_llm import ask_llm
from prompts.build_system_prompt import build_system_prompt
from utils.parse_json import clean_json_response, parse_llm_json
from workspace.io import task_expects_code, write_workspace_text


def _normalize_llm_text(value):
    #変更: LLMがconcerns等をリストで返した場合も文字列に統一する
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value).strip()
    return str(value).strip()


def ask_managers_agreement(task_text, assignments):
    """各部署の部長に、割り振られたタスクへの合意可否を確認する
    (部長のjudgment_anchor:「元タスクとの乖離」「他部署依存の前提との矛盾」の判断軸を使う)

    戻り値: [{"department_id":..., "verdict":"agree"または"disagree", "reason":"..."}]
    """
    #部長が「他部署の担当範囲と重複していないか」も判断できるよう、全体の配分を見せる
    assignment_overview = "\n".join(
        f"{a['department_id']}: {a['sub_task_text']}" for a in assignments
    )

    verdicts = []
    for assignment in assignments:
        department_id = assignment["department_id"]
        sub_task_text = assignment["sub_task_text"]

        leader = get_department_leader(department_id)
        if leader is None:
            print(f"[{department_id}] 部長情報が見つかりません。スキップします")
            continue

        persona = get_persona(leader["agent_persona_id_manager"])
        if persona is None:
            print(f"[{department_id}] 部長のpersonaが見つかりません。スキップします")
            continue

        system_prompt = build_system_prompt(leader["manager_name"], persona)

        user_prompt = f"""プロジェクト全体の要件: {task_text}

CTOによる部署配分(全体):
{assignment_overview}

あなたの部署に割り振られたタスク: {sub_task_text}

このタスクが自部署の専門範囲内であり、他部署との役割の重複や矛盾が無いか判断してください。
出力は必ず以下のJSON形式のみにしてください。前置きや説明文は一切含めないでください。

{{
  "verdict": "agree または disagree",
  "reason": "判断理由(簡潔に)"
}}"""

        raw = ask_llm(system_prompt, user_prompt)
        cleaned = clean_json_response(raw)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            print(f"[{department_id}] 部長の出力がJSONとして解析できませんでした:")
            print(raw)
            result = {"verdict": "agree", "reason": "解析失敗のため暫定的に合意扱い"}

        result["department_id"] = department_id
        verdicts.append(result)

    return verdicts


def manager_review_deliverables(
    department_id,
    task_text,
    d_list_text,
    short_summary,
    deliverables_text,
    review_round,
    is_final_review=False,
):
    #変更: 部長が暫定D-list・制作物を検収する(anchor内のみ判断。3回目は必ずapproval)
    leader = get_department_leader(department_id)
    if leader is None:
        return {
            "verdict": "approved" if is_final_review else "needs_revision",
            "reason": "部長情報が見つかりません",
            "revision_report": "",
            "concerns": "部長情報が見つかりません" if is_final_review else "",
        }

    persona = get_persona(leader["agent_persona_id_manager"])
    if persona is None:
        return {
            "verdict": "approved" if is_final_review else "needs_revision",
            "reason": "部長のpersonaが見つかりません",
            "revision_report": "",
            "concerns": "部長のpersonaが見つかりません" if is_final_review else "",
        }

    system_prompt = build_system_prompt(leader["manager_name"], persona)

    final_review_note = ""
    if is_final_review:
        final_review_note = """
これは3回目(最終)の検収です。verdictは必ず approved にしてください。
制作物に未達があっても差し戻しはできません。concerns に懸念点をまとめてください。
"""

    expects_code = task_expects_code(task_text)
    if expects_code:
        deliverable_criteria = """制作物(spec.txt)が一般論のみの場合は needs_revision としてください。
実装・コード担当タスクのため、コード片または実装可能な具体記述(項目名・型・API・関数等)が必要です。"""
    else:
        deliverable_criteria = """制作物(spec.txt)が一般論のみの場合は needs_revision としてください。
本タスクは設計・デザイン担当のため、コード片は不要です。
具体的な設計仕様(画面構成・項目定義・ワイヤー・レイアウト・コンポーネント名・サイズ・色・状態遷移など)があれば合格です。"""
    #変更: 設計タスクと実装タスクで部長検収基準を分ける(上記)

    user_prompt = f"""タスク: {task_text}

あなたは{department_id}部署の部長です。判断は自部署のjudgment_anchor(専門ドメイン)の範囲内のみで行ってください。
他部署の領域(例:UIUX部署でセキュリティ要件の差し戻し)は対象外です。該当する場合は差し戻し理由に含めないでください。

【検収回数】{review_round}回目
{final_review_note}

【暫定D-list】
{d_list_text}

【議論要約】
{short_summary}

【制作物(deliverables/)】
{deliverables_text}

暫定D-listと制作物がタスクに適合しているか、自部署ドメインの観点で検収してください。
{deliverable_criteria}
差し戻す場合は revision_report に、メンバーが修正できる具体的指摘(anchor内のみ)を書いてください。
"""
    #変更: 一般論禁止と設計/実装の合格基準をuser_promptに反映(上記deliverable_criteria)

    user_prompt = user_prompt + """
出力は必ず以下のJSON形式のみにしてください。前置きや説明文は一切含めないでください。

{{
  "verdict": "approved または needs_revision",
  "reason": "判断理由(簡潔に)",
  "revision_report": "差し戻し時のみ。メンバー向け修正指示(anchor内のみ)",
  "concerns": "最終検収で未達がある場合のみ。CQO向け懸念まとめ"
}}"""

    raw = ask_llm(system_prompt, user_prompt)
    result = parse_llm_json(raw)

    if result is None:
        print(f"[{department_id}] 部長の検収結果がJSONとして解析できませんでした:")
        print(raw)
        result = {
            "verdict": "approved" if is_final_review else "needs_revision",
            "reason": "解析失敗",
            "revision_report": "",
            "concerns": "解析失敗のため要確認" if is_final_review else "",
        }

    if is_final_review:
        #変更: 3回目はPython側で必ずapproval(懸念はconcernsに残す)
        result["verdict"] = "approved"
        result["concerns"] = _normalize_llm_text(result.get("concerns"))
    else:
        result["revision_report"] = _normalize_llm_text(result.get("revision_report"))
        result["concerns"] = _normalize_llm_text(result.get("concerns"))

    result["reason"] = _normalize_llm_text(result.get("reason"))

    return result


def write_same_department_contradiction_report(department_id, affected_results, conflict_description):
    #変更: 同一部署内矛盾は部長弁論をスキップし、内部矛盾レポートを書く
    task_lines = "\n".join(
        f"- {r['room_id']}: {r['sub_task_text']}" for r in affected_results
    )
    report = f"""【同一部署内D-list矛盾】
department_id={department_id}

あなたの部署内で矛盾したままD-listを確定させています。
関連ルーム:
{task_lines}

CQOが検出した衝突:
{conflict_description}

各ルームの担当者は、矛盾箇所を修正し、整合するD-list/spec.txtに更新してください。
"""
    for result in affected_results:
        write_workspace_text(result["room_id"], "revision_report.txt", report)
    return report


def managers_resolve_cross_department_conflict(task_text, conflict, affected_results):
    """関連部署の部長を呼び、整合性確保のための討論(合意)と修正指示を得る

    戻り値: {
      agreed: bool,
      reason: str,
      revision_reports: {room_id: report_text}
    }
    """
    dept_ids = conflict.get("department_ids") or []
    if conflict.get("same_department") and len(set(dept_ids)) <= 1:
        dept_id = dept_ids[0] if dept_ids else affected_results[0]["department_id"]
        report = write_same_department_contradiction_report(
            dept_id, affected_results, conflict.get("description", "")
        )
        return {
            "agreed": True,
            "reason": "同一部署内矛盾のため部長弁論をスキップ",
            "revision_reports": {r["room_id"]: report for r in affected_results},
        }

    revision_reports = {}
    all_agreed = True
    reasons = []

    overview = "\n".join(
        f"{r['department_id']}({r['room_id']}): {r['sub_task_text']}" for r in affected_results
    )

    for result in affected_results:
        department_id = result["department_id"]
        leader = get_department_leader(department_id)
        if leader is None:
            all_agreed = False
            reasons.append(f"{department_id}: 部長不在")
            continue

        persona = get_persona(leader["agent_persona_id_manager"])
        if persona is None:
            all_agreed = False
            reasons.append(f"{department_id}: persona不在")
            continue

        system_prompt = build_system_prompt(leader["manager_name"], persona)
        user_prompt = f"""プロジェクト要件: {task_text}

【CQOが検出した部署間衝突】
{conflict.get('description', '')}

【関連ルーム一覧】
{overview}

あなたは{department_id}部署の部長です。CQOより専門ドメインの判断はあなたに委ねられています。
他部署との整合性を取るため、自部署ルーム({result['room_id']})の担当者向け修正指示を書いてください。
一般論ではなく、D-list/spec.txtのどこをどう直すか具体化すること。

出力JSONのみ:
{{
  "verdict": "agree または disagree",
  "revision_report": "自部署メンバー向け修正指示(anchor内のみ)"
}}"""

        raw = ask_llm(system_prompt, user_prompt)
        parsed = parse_llm_json(raw)
        if parsed is None:
            all_agreed = False
            reasons.append(f"{department_id}: 解析失敗")
            continue

        if parsed.get("verdict") != "agree":
            all_agreed = False
            reasons.append(f"{department_id}: {parsed.get('reason', 'disagree')}")

        report = _normalize_llm_text(parsed.get("revision_report"))
        if report:
            revision_reports[result["room_id"]] = report

    return {
        "agreed": all_agreed and bool(revision_reports),
        "reason": "; ".join(reasons) if reasons else "関連部長が合意",
        "revision_reports": revision_reports,
    }
