from db.read import get_persona, get_recent_messages
from db.write import add_message_to_room
from llm.ask_llm import ask_llm
from prompts.build_system_prompt import build_member_system_prompt
from prompts.build_user_prompt import build_user_prompt
from utils.parse_json import parse_member_response
from workspace.io import read_spec_text, write_spec_text


def run_member_turn(room_id, member, task_text, reference_context=None):
    #変更: メンバー1回分のLLM呼び出し(JSON出力)とchat/spec.txt保存を行う
    persona = get_persona(member["agent_persona_id"])
    if persona is None:
        print(f"personaが見つかりません: {member['display_name']}")
        return "（personaが見つかりません）"

    system_prompt = build_member_system_prompt(member["display_name"], persona)
    recent_messages = get_recent_messages(room_id)
    current_spec = read_spec_text(room_id)
    user_prompt = build_user_prompt(
        task_text, recent_messages, reference_context, current_spec
    )

    raw = ask_llm(system_prompt, user_prompt)
    parsed = parse_member_response(raw)

    if parsed is None:
        print(f"変更: {member['display_name']} の出力をJSONとして解析できませんでした:")
        print(raw)
        parsed = {"chat": "（出力を解析できませんでした）", "artifact_update": ""}

    chat = parsed["chat"]
    if parsed["artifact_update"]:
        write_spec_text(room_id, parsed["artifact_update"])

    add_message_to_room(room_id, member["display_name"], chat)
    return chat
