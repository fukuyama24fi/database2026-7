from db.read import get_department_members_by_skill, get_persona, get_recent_messages
from db.write import add_message_to_room, assign_member_to_room
from llm.ask_llm import ask_llm
from memory.make_summary import make_turn_summary
from prompts.build_system_prompt import build_system_prompt
from prompts.build_user_prompt import build_user_prompt
from roles.pm import pm_check_agreement, pm_decide_scouting


def department_discussion_loop(
    room_id,
    task_text,
    members,
    max_turns=5,
    reference_context=None,
    department_id=None,
    min_turns_before_check=2,
    start_turn_number=1,
    accumulated_transcript=None,
    accumulated_turn_summaries=None,
):
    """1部署ルームで、メンバー全員がmax_turns回ずつ発言するループ
 
    department_idを渡すと、各ターン終了後にPMが合意形成できたか判定し、
    できていればmax_turnsに達する前に打ち切る(無駄なターンの削減)。
 
    戻り値: {
        "full_transcript": このルームでの全発言のリスト(D-list抽出用),
        "turn_summaries": 各ターンの要約リスト(short_summary生成用)
    }
    """
    #変更: 差し戻し後の延長ブロックでも議論を引き継ぐため、呼び出し元のリストに追記する
    if accumulated_transcript is None:
        full_transcript = []
    else:
        full_transcript = accumulated_transcript

    if accumulated_turn_summaries is None:
        turn_summaries = []
    else:
        turn_summaries = accumulated_turn_summaries
 
    for turn_offset in range(max_turns):
        turn_number = start_turn_number + turn_offset  #変更: 延長時もターン番号を連番にする
        turn_start_index = len(full_transcript)  #新規: このターンの発言開始位置を記録

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
            print(f"[ターン{turn_number}] {member['display_name']}: {reply}")
 
            full_transcript.append({"speaker": member["display_name"], "message": reply})
            add_message_to_room(room_id, member["display_name"], reply)

        this_turn_messages = full_transcript[turn_start_index:]  #新規: このターン分の発言だけ切り出す
        consensus_reached = False

        # 1ターン(全員が1回ずつ発言)終わるごとに、PMが合意形成できたか判定する
        if department_id:
            if (turn_offset + 1) >= min_turns_before_check:
                consensus = pm_check_agreement(
                    department_id,
                    task_text,
                    turn_summaries,  #新規: 今回ターンはまだ含まない過去分のみ
                    this_turn_messages,
                )
                print(f"[PM判定] consensus_reached={consensus.get('consensus_reached')} - {consensus.get('reason')}")
                consensus_reached = bool(consensus.get("consensus_reached"))

                #新規: 合意未達かつ8名未満のときのみスカウト判定
                if not consensus_reached and len(members) < 8:
                    current_names = [m["display_name"] for m in members]
                    scout = pm_decide_scouting(
                        department_id,
                        task_text,
                        turn_summaries,
                        this_turn_messages,
                        current_names,
                        len(members),
                    )
                    print(
                        f"[PMスカウト判定] needs_scout={scout.get('needs_scout')} "
                        f"- {scout.get('reason')}"
                    )

                    if scout.get("needs_scout"):
                        #新規: Python側で上限を強制(1ターン最大2名、総数最大8名)
                        slots_left = min(2, 8 - len(members))
                        exclude_ids = [m["member_id"] for m in members]
                        needed_skills = scout.get("needed_skills") or []

                        candidates = get_department_members_by_skill(
                            department_id,
                            needed_skills,
                            slots_left,
                            exclude_ids,
                        )

                        for candidate in candidates:
                            assign_member_to_room(
                                room_id,
                                candidate["member_id"],
                                "scouted",
                                turn_number,
                            )
                            members.append(candidate)
                            print(
                                f"[スカウト] {candidate['display_name']} がルームに追加されました"
                                f" (ターン{turn_number + 1}から参加)"
                            )

        #新規: 合意有無に関わらず毎ターン要約を貯める(最終short_summary用。合意ターンも欠落させない)
        turn_summary = make_turn_summary(task_text, this_turn_messages)
        turn_summaries.append({"turn_number": turn_number, "summary": turn_summary})
        print(f"[ターン{turn_number}要約] {turn_summary}")

        if consensus_reached:
            print(f"ターン{turn_number}で合意形成を確認したため、議論を早期終了します")
            break
 
    return {
        "full_transcript": full_transcript,
        "turn_summaries": turn_summaries,
    }
