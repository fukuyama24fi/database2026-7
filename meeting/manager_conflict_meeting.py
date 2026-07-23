from db.read import get_department_leader, get_persona
from llm.ask_llm import ask_llm
from prompts.build_system_prompt import build_system_prompt
from roles.cqo import cqo_check_managers_agreement
from roles.manager import write_same_dept_conflict
from utils.parse_json import parse_llm_json


def _normalize_llm_text(value):
    #LLMがmessage/revision_report等をリストで返した場合も文字列に統一する
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value).strip()
    return str(value).strip()


def _build_manager_contexts(affected_results):
    #衝突に関わる各部署の部長情報・D-list要約を集める
    contexts = []
    for result in affected_results:
        department_id = result["department_id"]
        leader = get_department_leader(department_id)
        if leader is None:
            continue
        persona = get_persona(leader["agent_persona_id_manager"])
        if persona is None:
            continue
        d_list = "\n".join(
            f"- {d.get('decision_type', '?')}: {d.get('summary', '')}"
            for d in (result.get("decisions") or [])
        ) or "(決定事項なし)"
        contexts.append(
            {
                "department_id": department_id,
                "manager_name": leader["manager_name"],
                "persona": persona,
                "room_id": result["room_id"],
                "dept_task": result.get("dept_task", result.get("sub_task_text", "")),
                "d_list_summary": d_list,
            }
        )
    return contexts


def _manager_conflict_turn(task_text, conflict, manager_ctx, talk_log, turn_number):
    system_prompt = build_system_prompt(manager_ctx["manager_name"], manager_ctx["persona"])
    if talk_log:
        history = "\n".join(f"{m['speaker']}: {m['message']}" for m in talk_log)
    else:
        history = "(まだ発言はありません)"

    user_prompt = f"""プロジェクト要件: {task_text}

【CQOが検出した部署間衝突】
{conflict.get('description', '')}
重大度: {conflict.get('severity_level', 3)}/5

あなたは{manager_ctx['department_id']}部署の部長({manager_ctx['manager_name']})です。
自部署タスク: {manager_ctx['dept_task']}
自部署D-list:
{manager_ctx['d_list_summary']}

他部署部長と整合性を取るための討論です(ターン{turn_number})。
専門ドメイン(自部署anchor)の範囲で、具体的に譲歩・修正・合意案を述べてください。
一般論だけは避け、D-list/design.txtのどこをどう揃えるかを明示してください。

これまでの討論:
{history}

JSONのみ:
{{"message": "発言(200字以内)"}}"""

    raw = ask_llm(system_prompt, user_prompt)
    parsed = parse_llm_json(raw)
    if parsed is None:
        return f"({manager_ctx['department_id']}部長: 発言を解析できませんでした)"
    return _normalize_llm_text(parsed.get("message")) or "(発言なし)"


def _manager_reflection_report(task_text, conflict, manager_ctx, talk_log, agreed):
    system_prompt = build_system_prompt(manager_ctx["manager_name"], manager_ctx["persona"])
    history = "\n".join(f"{m['speaker']}: {m['message']}" for m in talk_log) or "(討論なし)"

    agreement_note = "部長間で合意しました。" if agreed else "最大ターンに達し合意未達です。暫定合意案に基づき修正してください。"

    user_prompt = f"""プロジェクト要件: {task_text}

【衝突内容】
{conflict.get('description', '')}

【部長討論ログ】
{history}

{agreement_note}

あなたは{manager_ctx['department_id']}部署の部長です。
自部署ルーム({manager_ctx['room_id']})のメンバー向けに「反省・修正レポート」を書いてください。
討論で決まった(または暫定の)整合方針に基づき、D-list/design.txtの具体的修正指示を書くこと。
一般論は不可。

JSONのみ:
{{"revision_report": "自部署メンバー向け修正指示"}}"""

    raw = ask_llm(system_prompt, user_prompt)
    parsed = parse_llm_json(raw)
    if parsed is None:
        return f"【{manager_ctx['department_id']}】討論結果を反映し、D-list/design.txtの矛盾箇所を修正してください。"
    return _normalize_llm_text(parsed.get("revision_report"))


def run_managers_conflict_meeting(
    task_text,
    conflict,
    affected_results,
    max_turns=5,
):
    #CQOが見つけた部署間衝突について、関係部長が話し合い修正方針を決める
    dept_ids = conflict.get("department_ids") or []
    if conflict.get("same_department") and len(set(dept_ids)) <= 1:
        dept_id = dept_ids[0] if dept_ids else affected_results[0]["department_id"]
        report = write_same_dept_conflict(
            dept_id, affected_results, conflict.get("description", "")
        )
        return {
            "agreed": True,
            "reason": "同一部署内矛盾のため部長討論をスキップ",
            "meeting_talk_log": [],
            "revision_reports": {r["room_id"]: report for r in affected_results},
            "needs_talk_redo": False,
        }

    contexts = _build_manager_contexts(affected_results)
    if len(contexts) < 2:
        return {
            "agreed": False,
            "reason": "討論に必要な部長が2名未満",
            "meeting_talk_log": [],
            "revision_reports": {},
            "needs_talk_redo": False,
        }

    talk_log = []
    agreed = False
    last_reason = ""

    for turn in range(1, max_turns + 1):
        print(f"  [部長討論] ターン{turn}/{max_turns}")
        for ctx in contexts:
            message = _manager_conflict_turn(
                task_text, conflict, ctx, talk_log, turn
            )
            speaker = f"{ctx['department_id']}部長({ctx['manager_name']})"
            talk_log.append({"speaker": speaker, "message": message})
            print(f"    {speaker}: {message[:80]}{'...' if len(message) > 80 else ''}")

        agreement = cqo_check_managers_agreement(
            task_text, conflict, talk_log, contexts
        )
        agreed = bool(agreement.get("agreed"))
        last_reason = agreement.get("reason", "")
        print(f"  [CQO合意確認] agreed={agreed} - {last_reason}")

        if agreed:
            break

    revision_reports = {}
    for ctx in contexts:
        report = _manager_reflection_report(
            task_text, conflict, ctx, talk_log, agreed
        )
        revision_reports[ctx["room_id"]] = report

    severity = conflict.get("severity_level", 3)
    needs_talk_redo = (not agreed) and severity >= 5

    return {
        "agreed": agreed,
        "reason": last_reason or ("合意" if agreed else "最大ターン到達"),
        "meeting_talk_log": talk_log,
        "revision_reports": revision_reports,
        "needs_talk_redo": needs_talk_redo,
    }
