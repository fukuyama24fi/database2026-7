from data import DEPARTMENTS
from roomManager import (
    create_project,
    create_room,
    get_department_members,
    get_persona,
    append_message_to_room,
)
from llmClient import ask_llm


def build_system_prompt(display_name, persona):
    """personaの中身(judgment_anchor・style_persona)からLLM用のsystem_promptを組み立てる"""
    anchor = persona["judgment_anchor"]
    style = persona["style_persona"]

    return f"""あなたは{display_name}です。
【あなたの判断軸(絶対に譲らない基準)】
重視すること: {"、".join(anchor["primary_questions"])}
絶対に許容しないこと: {"、".join(anchor["auto_reject_conditions"])}

【あなたの話し方】
トーン: {style["tone"]}
よく使う言い回し: {"、".join(style["phrases"])}
文の傾向: {style["sentence_tendency"]}

上記の判断軸に沿って、簡潔に日本語で発言してください。"""


def main():
    project_id = "proj_test_004"
    department_id = "FE"
    room_id = "room_test_004"
    task_text = "ログイン画面のUIをどう設計するか検討してください"

    # 1. プロジェクトとルームを作る
    create_project(project_id)
    create_room(room_id, project_id, DEPARTMENTS[department_id], task_text)

    # 2. このルームのメンバーを2人取得する
    members = get_department_members(department_id, count=2)
    if not members:
        print("メンバーが見つかりませんでした。department_members_masterのdepartment_idを確認してください")
        return

    # 3. 1人目のメンバーにLLMで発言させる
    member = members[0]
    persona = get_persona(member["agent_persona_id"])
    if persona is None:
        print("personaが見つかりませんでした。agent_persona_idを確認してください")
        return

    system_prompt = build_system_prompt(member["display_name"], persona)
    user_prompt = f"タスク: {task_text}\nこのタスクについて、あなたの意見を一言述べてください。"

    reply = ask_llm(system_prompt, user_prompt)
    print(f"\n[{member['display_name']}の発言]\n{reply}\n")

    # 4. 発言をrecent_messagesに保存する
    append_message_to_room(room_id, member["display_name"], reply)


if __name__ == "__main__":
    print("main start")
    main()