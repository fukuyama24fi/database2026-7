from db.read import get_department_leader, get_persona
from llm.ask_llm import ask_llm
from prompts.build_system_prompt import build_system_prompt
from utils.parse_json import parse_llm_json

#PMの役割。議論の進行と合意形成の判断を担当する


def _format_past_turn_summaries(turn_summaries):
    #PMの合意判定・スカウト判定用。過去ターンの要約をプロンプト文字列にする
    if turn_summaries:
        return "\n".join(
            f"ターン{s['turn_number']}: {s['summary']}" for s in turn_summaries
        )
    return "(まだ過去ターンはありません)"


def _format_current_turn_messages(current_turn_messages):
    #PMの合意判定・スカウト判定用。直近ターンの発言全文をプロンプト文字列にする
    return "\n".join(
        f"{m['speaker']}: {m['message']}" for m in current_turn_messages
    )


def pm_check_agreement(department_id, task_text, turn_summaries, current_turn_messages):
    """PMが現時点の議論を読み、D-list化できる程度に合意形成されたか判断する
    (PMのjudgment_anchor:「D-list昇格の基準を満たしているか」を使う)

    戻り値: {"agreed": True/False, "reason": "..."}
    """
    leader = get_department_leader(department_id)
    if leader is None:
        return {"agreed": False, "reason": "PM情報が見つかりません"}

    persona = get_persona(leader["agent_persona_id_pm"])
    if persona is None:
        return {"agreed": False, "reason": "PMのpersonaが見つかりません"}

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
  "agreed": trueまたはfalse,
  "reason": "判断理由(簡潔に・1行のみ・改行不可)"
}}"""

    raw = ask_llm(system_prompt, user_prompt)
    result = parse_llm_json(raw)

    if result is None:
        print("PMの合意判定がJSONとして解析できませんでした:")
        print(raw)
        result = {"agreed": False, "reason": "解析失敗のため議論を継続します"}

    if "agreed" not in result and "consensus_reached" in result:
        result["agreed"] = result.pop("consensus_reached")

    return result


def pm_decide_scouting(
    department_id,
    task_text,
    turn_summaries,
    current_turn_messages,
    current_member_names,
    current_team_size,
    parse_error_count=0,
):
    #スキル不足・議論停滞のみでスカウト判断。構文解析エラーは別問題
    if parse_error_count > 0:
        return {
            "needs_scout": False,
            "reason": f"構文解析エラー{parse_error_count}件のためスカウト不可",
            "needed_skills": [],
            "blocked_by_parse_error": True,
        }

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

上記の議論を踏まえ、以下のいずれかに該当する場合のみ追加メンバー(スカウト)が必要と判断してください。
- 現在のメンバーのスキルではタスク遂行に不足がある(スキルギャップ)
- 議論が停滞しており、別視点・専門性を持つメンバーが必要(セマンティックな行き詰まり)

重要: 以下はスカウト理由にしないでください。
- メンバー出力のJSON/構文解析エラー(Parse Error)
- 「出力を解析できませんでした」等のフォーマット失敗
- design.txt更新の形式崩れ

該当しない場合は needs_scout を false にしてください。

出力は必ず以下のJSON形式のみにしてください。前置きや説明文は一切含めないでください。

{{
  "needs_scout": trueまたはfalse,
  "reason": "判断理由(簡潔に・1行のみ・改行不可)",
  "needed_skills": ["不足していると感じるスキル名", "..."]
}}"""

    raw = ask_llm(system_prompt, user_prompt)
    result = parse_llm_json(raw)

    if result is None:
        print("PMのスカウト判定がJSONとして解析できませんでした:")
        print(raw)
        result = {
            "needs_scout": False,
            "reason": "解析失敗のためスカウトなしとみなします",
            "needed_skills": [],
        }

    if "needed_skills" not in result:
        result["needed_skills"] = []

    #PMが誤って構文エラーを停滞と判断してもPython側でスカウトをブロック
    reason_text = str(result.get("reason", ""))
    parse_error_keywords = ("解析", "JSON", "構文", "フォーマット", "形式", "parse")
    if result.get("needs_scout") and any(k.lower() in reason_text.lower() for k in parse_error_keywords):
        result["needs_scout"] = False
        result["reason"] = "構文エラーはスカウト理由にしない(Python側でブロック)"
        result["blocked_by_parse_error"] = True

    return result


def pm_assign_member_roles(department_id, task_text, members, new_member_ids=None):
    """PMがメンバー一人ひとりに重複しない担当役割を割り当てる

    new_member_ids: スカウトで追加されたmember_idリスト(未指定なら全員)
    戻り値: {member_id: task_role}
    """
    leader = get_department_leader(department_id)
    if leader is None:
        return {m["member_id"]: m.get("task_role", "未割当") for m in members}

    persona = get_persona(leader["agent_persona_id_pm"])
    if persona is None:
        return {m["member_id"]: m.get("task_role", "未割当") for m in members}

    if new_member_ids is None:
        targets = members
    else:
        targets = [m for m in members if m["member_id"] in new_member_ids]

    if not targets:
        return {m["member_id"]: m.get("task_role", "未割当") for m in members}

    system_prompt = build_system_prompt(leader["pm_name"], persona)
    existing_roles = "\n".join(
        f"- {m['display_name']}({m['member_id']}): {m.get('task_role', '未割当')}"
        for m in members
        if m.get("task_role") and m["member_id"] not in {t["member_id"] for t in targets}
    ) or "(まだ役割割当なし)"
    target_lines = "\n".join(
        f"- {m['display_name']} ({m['member_id']}) スキル:{m.get('skills', '')}"
        for m in targets
    )

    user_prompt = f"""タスク: {task_text}

あなたはPMです。ルームメンバーが役割を奪い合わないよう、担当領域を明確に割り当ててください。
既存メンバーの役割(変更不可):
{existing_roles}

役割を割り当てる対象:
{target_lines}

ルール:
- 1人1役割。他メンバーと重複・競合しない具体的な担当名にする
- 例:「レイアウト担当」「配色・タイポ担当」「入力項目・バリデーション担当」「コンポーネント構成担当」
- 既存役割と被らないこと

JSONのみ:
{{
  "assignments": [
    {{"member_id": "mem_xxxxx", "task_role": "具体的担当名"}}
  ]
}}"""

    raw = ask_llm(system_prompt, user_prompt)
    result = parse_llm_json(raw)
    role_map = {m["member_id"]: m.get("task_role", "未割当") for m in members}

    if result and isinstance(result.get("assignments"), list):
        for item in result["assignments"]:
            mid = item.get("member_id")
            role = item.get("task_role")
            if mid and role:
                role_map[mid] = str(role).strip()

    for member in members:
        member["task_role"] = role_map.get(member["member_id"], member.get("task_role", "未割当"))

    return role_map
