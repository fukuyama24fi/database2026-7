from db.read import get_persona, get_recent_messages
from db.write import add_message_to_room
from llm.ask_llm import ask_llm
from prompts.build_system_prompt import build_member_system_prompt
from prompts.build_user_prompt import build_user_prompt
from utils.parse_json import read_member_json
from workspace.io import (
    read_design_doc,
    read_team_memo,
    task_expects_code,
    write_design_with_history,
)


def run_member_turn(room_id, member, task_text, reference_context=None, other_dept_info=""):
    #メンバー1人分の発言ターン。LLM→JSON解析→DB保存→design.txt更新
    persona = get_persona(member["agent_persona_id"])
    if persona is None:
        print(f"personaが見つかりません: {member['display_name']}")
        return {"chat": "（personaが見つかりません）", "parse_error": True}

    system_prompt = build_member_system_prompt(
        member["display_name"], persona, expects_code=task_expects_code(task_text)
    )
    recent_messages = get_recent_messages(room_id)
    current_design = read_design_doc(room_id)
    team_memo = read_team_memo(room_id)
    user_prompt = build_user_prompt(
        task_text,
        recent_messages,
        reference_context,
        current_design,
        team_memo=team_memo,
        expects_code=task_expects_code(task_text),
        member_role=member.get("task_role", "未割当"),
        other_dept_info=other_dept_info,
    )

    raw = ask_llm(system_prompt, user_prompt)
    parsed = read_member_json(raw)

    if parsed is None:
        print(f"変更: {member['display_name']} の出力をJSONとして解析できませんでした:")
        print(raw)
        parsed = {
            "chat": "（出力を解析できませんでした）",
            "design_update": "",
            "parse_error": True,
        }

    chat = parsed["chat"]
    design = parsed["design_update"]
    if design:
        write_design_with_history(
            room_id,
            design.strip(),
            member["display_name"],
            note=chat,
        )

    add_message_to_room(room_id, member["display_name"], chat)
    return {
        "chat": chat,
        "parse_error": bool(parsed.get("parse_error")),
    }
