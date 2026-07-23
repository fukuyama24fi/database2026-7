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
    accumulated_talk_log=None,
    accumulated_turn_summaries=None,
    other_dept_info="",
):
    #1部署ルームでメンバー全員がmax_turns回ずつ発言するメインループ
    """1部署ルームで、メンバー全員がmax_turns回ずつ発言するループ"""
    if accumulated_talk_log is None:
        talk_log = []
    else:
        talk_log = accumulated_talk_log

    if accumulated_turn_summaries is None:
        turn_summaries = []
    else:
        turn_summaries = accumulated_turn_summaries

    for loop_count in range(max_turns):
        turn_number = start_turn_number + loop_count
        turn_start_index = len(talk_log)
        turn_parse_errors = 0

        for member in members:
            if get_persona(member["agent_persona_id"]) is None:
                print(f"personaが見つかりません: {member['display_name']}")
                continue

            turn_result = run_member_turn(
                room_id, member, task_text, reference_context, other_dept_info=other_dept_info
            )
            chat = turn_result["chat"]
            if turn_result.get("parse_error") or is_parser_error_message(chat):
                turn_parse_errors += 1
            print(f"[ターン{turn_number}] {member['display_name']}: {chat}")

            talk_log.append({"speaker": member["display_name"], "message": chat})

        this_turn_messages = talk_log[turn_start_index:]
        agreed = False

        if department_id:
            if (loop_count + 1) >= min_turns_before_check:
                agreement = pm_check_agreement(
                    department_id,
                    task_text,
                    turn_summaries,
                    this_turn_messages,
                )
                print(f"[PM合意判定] agreed={agreement.get('agreed')} - {agreement.get('reason')}")
                agreed = bool(agreement.get("agreed"))

                if not agreed and len(members) < 8:
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
                        new_ids = [c["member_id"] for c in candidates]
                        pm_assign_member_roles(
                            department_id, task_text, members, new_member_ids=new_ids
                        )
                        write_team_memo(room_id, members)

        turn_summary = make_turn_summary(task_text, this_turn_messages)
        turn_summaries.append({
            "turn_number": turn_number,
            "summary": turn_summary,
            "message_end_index": len(talk_log),
        })
        print(f"[ターン{turn_number}要約] {turn_summary}")

        if agreed:
            print(f"ターン{turn_number}で合意形成を確認したため、議論を早期終了します")
            break

    return {
        "talk_log": talk_log,
        "turn_summaries": turn_summaries,
    }
