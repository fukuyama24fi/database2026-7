from roomManager import get_persona, get_recent_messages, append_message_to_room
from llmClient import ask_llm


def build_system_prompt(display_name, persona):
    #personaの中身(judgment_anchor・style_persona)からLLM用のsystem_promptを組み立てる"""
    anchor = persona["judgment_anchor"]
    style = persona["style_persona"]

    return f"""あなたは{display_name}です。
【あなたの判断軸(絶対に譲らない基準)】
重視すること: {"、".join(anchor["primary_questions"])}
絶対に許容しないこと: {"、".join(anchor["auto_reject_conditions"])}

【あなたの話し方】
トーン: {style["tone"]}
よく使う言い回し(自然に混ぜる程度でOK、毎回使う必要はない): {"、".join(style["phrases"])}
文の傾向: {style["sentence_tendency"]}

上記の判断軸に沿って、簡潔に日本語で発言してください。外国語（英語、中国語、韓国語など）は使用しないでください。"""


def build_user_prompt(task_text, recent_messages, reference_context=None): #参照情報があるときは渡す
    """直近の会話履歴(短期記憶)を踏まえたuser_promptを組み立てる"""
    if recent_messages:
        history_text = "\n".join(
            f"{m['speaker']}: {m['message']}" for m in recent_messages
        )
    else:
        history_text = "(まだ発言はありません)"

    return f"""タスク: {task_text}
これまでの会話:
{history_text}

あなたは次の発言者です。

前の発言に賛成・反対・補足・改善案を述べてください。
新しい観点を1つ以上追加してください。。
外国語（英語、中国語、韓国語など）は使用しないでください。"""


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
    from Pm import check_consensus  # 循環import回避のため関数内でimport
 
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
            append_message_to_room(room_id, member["display_name"], reply)
 
        # 1ターン(全員が1回ずつ発言)終わるごとに、PMが合意形成できたか判定する
        if department_id and (turn + 1) >= min_turns_before_check:
            consensus = check_consensus(department_id, task_text, full_transcript)
            print(f"[PM判定] consensus_reached={consensus.get('consensus_reached')} - {consensus.get('reason')}")
            if consensus.get("consensus_reached"):
                print(f"ターン{turn + 1}で合意形成を確認したため、議論を早期終了します")
                break
 
    return full_transcript