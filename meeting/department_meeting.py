from db.read import get_department_members_by_skill, get_persona
from db.write import assign_member_to_room
from meeting.member_turn import run_member_turn
from memory.make_summary import make_turn_summary
from roles.pm import pm_assign_member_roles, pm_check_agreement, pm_decide_scouting
from utils.parse_json import is_parser_error_message
from workspace.io import write_team_memo


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
    peer_context="",
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
        turn_parse_errors = 0  #変更: ターン内の構文解析エラー数(PMスカウト判定から分離)

        for member in members:
            if get_persona(member["agent_persona_id"]) is None:
                print(f"personaが見つかりません: {member['display_name']}")
                continue

            #変更: JSON(chat+artifact_update)方式。parse_errorを返す
            turn_result = run_member_turn(
                room_id, member, task_text, reference_context, peer_context=peer_context
            )
            chat = turn_result["chat"]
            if turn_result.get("parse_error") or is_parser_error_message(chat):
                turn_parse_errors += 1
            print(f"[ターン{turn_number}] {member['display_name']}: {chat}")

            full_transcript.append({"speaker": member["display_name"], "message": chat})

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
                print(f"[PM合意判定] consensus_reached={consensus.get('consensus_reached')} - {consensus.get('reason')}")
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
                        parse_error_count=turn_parse_errors,
                    )
                    if scout.get("blocked_by_parse_error"):
                        print(
                            f"[PMスカウト判定] スキップ: 構文解析エラー{turn_parse_errors}件 "
                            f"(停滞と混同しない)"
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
                        #変更: スカウト追加後、PMが新メンバーへ重複しない役割を割り当てる
                        new_ids = [c["member_id"] for c in candidates]
                        pm_assign_member_roles(
                            department_id, task_text, members, new_member_ids=new_ids
                        )
                        write_team_memo(room_id, members)

        #新規: 合意有無に関わらず毎ターン要約を貯める(最終short_summary用。合意ターンも欠落させない)
        turn_summary = make_turn_summary(task_text, this_turn_messages)
        turn_summaries.append({
            "turn_number": turn_number,
            "summary": turn_summary,
            "message_end_index": len(full_transcript),  #変更: 局所ロールバック用
        })
        print(f"[ターン{turn_number}要約] {turn_summary}")

        if consensus_reached:
            print(f"ターン{turn_number}で合意形成を確認したため、議論を早期終了します")
            break
 
    return {
        "full_transcript": full_transcript,
        "turn_summaries": turn_summaries,
    }
