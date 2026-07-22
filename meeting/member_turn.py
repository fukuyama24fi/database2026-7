from db.read import get_persona, get_recent_messages
from db.write import add_message_to_room
from llm.ask_llm import ask_llm
from prompts.build_system_prompt import build_member_system_prompt
from prompts.build_user_prompt import build_user_prompt
from utils.parse_json import parse_member_response
from workspace.io import (
    read_spec_text,
    read_team_memo,
    task_expects_code,
    write_spec_with_history,
)


def run_member_turn(room_id, member, task_text, reference_context=None, peer_context=""):
    #変更: メンバー1回分のLLM呼び出し(JSON出力)とchat/spec.txt保存。parse_errorを返す
    persona = get_persona(member["agent_persona_id"])
    if persona is None:
        print(f"personaが見つかりません: {member['display_name']}")
        return {"chat": "（personaが見つかりません）", "parse_error": True}

    system_prompt = build_member_system_prompt(
        member["display_name"], persona, expects_code=task_expects_code(task_text)
    )
    recent_messages = get_recent_messages(room_id)
    current_spec = read_spec_text(room_id)
    team_memo = read_team_memo(room_id)
    user_prompt = build_user_prompt(
        task_text,
        recent_messages,
        reference_context,
        current_spec,
        team_memo=team_memo,
        expects_code=task_expects_code(task_text),
        member_role=member.get("task_role", "未割当"),
        peer_context=peer_context,
    )

    raw = ask_llm(system_prompt, user_prompt)
    parsed = parse_member_response(raw)

    if parsed is None:
        print(f"変更: {member['display_name']} の出力をJSONとして解析できませんでした:")
        print(raw)
        parsed = {
            "chat": "（出力を解析できませんでした）",
            "artifact_update": "",
            "parse_error": True,
        }

    chat = parsed["chat"]
    artifact = parsed["artifact_update"]
    if artifact:
        #変更: spec.txtは最新版のみ。旧版はspec_history.txtへ自動退避
        write_spec_with_history(
            room_id,
            artifact.strip(),
            member["display_name"],
            note=chat,
        )

    add_message_to_room(room_id, member["display_name"], chat)
    return {
        "chat": chat,
        "parse_error": bool(parsed.get("parse_error")),
    }
