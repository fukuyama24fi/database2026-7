import json

from db.read import get_department_leader, get_persona
from llm.ask_llm import ask_llm
from prompts.build_system_prompt import build_system_prompt
from utils.parse_json import clean_json_response

# PMの役割:議論の進行と合意形成の判断


def _format_past_turn_summaries(turn_summaries):
    #新規: PM判定用に、過去ターンの要約をプロンプト向けテキストに整形する
    if turn_summaries:
        return "\n".join(
            f"ターン{s['turn_number']}: {s['summary']}" for s in turn_summaries
        )
    return "(まだ過去ターンはありません)"


def _format_current_turn_messages(current_turn_messages):
    #新規: PM判定用に、直近ターンの発言全文をプロンプト向けテキストに整形する
    return "\n".join(
        f"{m['speaker']}: {m['message']}" for m in current_turn_messages
    )


def pm_check_agreement(department_id, task_text, turn_summaries, current_turn_messages):
    """PMが現時点の議論を読み、D-list化できる程度に合意形成されたか判断する
    (PMのjudgment_anchor:「D-list昇格の基準を満たしているか」を使う)

    戻り値: {"consensus_reached": True/False, "reason": "..."}
    """
    leader = get_department_leader(department_id)
    if leader is None:
        return {"consensus_reached": False, "reason": "PM情報が見つかりません"}

    persona = get_persona(leader["agent_persona_id_pm"])
    if persona is None:
        return {"consensus_reached": False, "reason": "PMのpersonaが見つかりません"}

    system_prompt = build_system_prompt(leader["pm_name"], persona)

    past_turns_text = _format_past_turn_summaries(turn_summaries)
    current_turn_text = _format_current_turn_messages(current_turn_messages)

    user_prompt = f"""タスク: {task_text}

過去のターン要約:
{past_turns_text}

直近ターンの発言全文:
{current_turn_text}

メンバー間で実質的な合意が形成され、これ以上議論を続けても新しい決定が
生まれる見込みが低い場合は、議論を打ち切ってD-list化に進めるべきだと判断してください。
逆に、まだ議論が広がり続けていて収束していない場合は、合意形成されていないと判断してください。

出力は必ず以下のJSON形式のみにしてください。前置きや説明文は一切含めないでください。

{{
  "consensus_reached": trueまたはfalse,
  "reason": "判断理由(簡潔に)"
}}"""

    raw = ask_llm(system_prompt, user_prompt)
    cleaned = clean_json_response(raw)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        print("PMの合意判定がJSONとして解析できませんでした:")
        print(raw)
        result = {"consensus_reached": False, "reason": "解析失敗のため議論を継続します"}

    return result


def pm_decide_scouting(
    department_id,
    task_text,
    turn_summaries,
    current_turn_messages,
    current_member_names,
    current_team_size,
):
    #新規: PMが議論を読み、スキル不足や停滞により追加メンバー(スカウト)が必要か判断する
    leader = get_department_leader(department_id)
    if leader is None:
        return {
            "needs_scout": False,
            "reason": "PM情報が見つかりません",
            "needed_skills": [],
        }

    persona = get_persona(leader["agent_persona_id_pm"])
    if persona is None:
        return {
            "needs_scout": False,
            "reason": "PMのpersonaが見つかりません",
            "needed_skills": [],
        }

    system_prompt = build_system_prompt(leader["pm_name"], persona)

    past_turns_text = _format_past_turn_summaries(turn_summaries)
    current_turn_text = _format_current_turn_messages(current_turn_messages)
    member_list_text = "、".join(current_member_names)

    user_prompt = f"""タスク: {task_text}

現在のルームメンバー({current_team_size}名): {member_list_text}
※ルーム総人数は最大8名までです。現在 {current_team_size} 名です。

過去のターン要約:
{past_turns_text}

直近ターンの発言全文:
{current_turn_text}

上記の議論を踏まえ、以下のいずれかに該当する場合は追加メンバー(スカウト)が必要と判断してください。
- 現在のメンバーのスキルではタスク遂行に不足がある
- 議論が停滞しており、別視点・専門性を持つメンバーが必要

該当しない場合は needs_scout を false にしてください。

出力は必ず以下のJSON形式のみにしてください。前置きや説明文は一切含めないでください。

{{
  "needs_scout": trueまたはfalse,
  "reason": "判断理由(簡潔に)",
  "needed_skills": ["不足していると感じるスキル名", "..."]
}}"""

    raw = ask_llm(system_prompt, user_prompt)
    cleaned = clean_json_response(raw)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        print("PMのスカウト判定がJSONとして解析できませんでした:")
        print(raw)
        result = {
            "needs_scout": False,
            "reason": "解析失敗のためスカウトなしとみなします",
            "needed_skills": [],
        }

    return result
