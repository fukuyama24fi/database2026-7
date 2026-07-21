from simulation.db.read import get_persona, get_recent_messages
from simulation.db.write import add_message_to_room
from simulation.prompts.make_system_prompt import build_system_prompt
from simulation.prompts.make_user_prompt import build_user_prompt
from simulation.llm.ask_llm import ask_llm
from simulation.roles.pm import pm_check_agreement


def department_discussion_loop(
    room_id,
    task_text,
    members,
    max_turns=5,
    reference_context=None,
    department_id=None,
    min_turns_before_check=2,
):
    """1部署ルームで、メンバー全員がmax_turns回ずつ発言するループ
 
    department_idを渡すと、各ターン終了後にPMが合意形成できたか判定し、
    できていればmax_turnsに達する前に打ち切る(無駄なターンの削減)。
 
    戻り値: full_transcript(このルームでの全発言のリスト。recent_messagesと違い、
    5件で切り詰められない。あとでshort_summary・D-list化に使う)
    """
    full_transcript = []
 
    for turn in range(max_turns):
        for member in members:
            persona = get_persona(member["agent_persona_id"])
            if persona is None:
                print(f"personaが見つかりません: {member['display_name']}")
                continue
 
            system_prompt = build_system_prompt(member["display_name"], persona)
            # 直近の会話をDBから毎回取り直す。前の発言者の発言も踏まえて話すため
            recent_messages = get_recent_messages(room_id)
            user_prompt = build_user_prompt(task_text, recent_messages, reference_context)
 
            reply = ask_llm(system_prompt, user_prompt)
            print(f"[ターン{turn + 1}] {member['display_name']}: {reply}")
 
            full_transcript.append({"speaker": member["display_name"], "message": reply})
            add_message_to_room(room_id, member["display_name"], reply)
 
        # 1ターン(全員が1回ずつ発言)終わるごとに、PMが合意形成できたか判定する
        if department_id and (turn + 1) >= min_turns_before_check:
            consensus = pm_check_agreement(department_id, task_text, full_transcript)
            print(f"[PM判定] consensus_reached={consensus.get('consensus_reached')} - {consensus.get('reason')}")
            if consensus.get("consensus_reached"):
                print(f"ターン{turn + 1}で合意形成を確認したため、議論を早期終了します")
                break
 
    return full_transcript
