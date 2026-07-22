import re

CHAT_MAX_CHARS = 200  #変更: メンバー進行用chatの最大文字数


def clean_json_response(raw):
    """LLMが```json ... ```のようにコードブロックで囲んで返してくることがあるので、
    先頭・末尾の```を取り除いてから渡せるようにする(memory.py/cto.py/cqo.py共通で使う)
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned) #先頭の```や```jsonを除去
        cleaned = re.sub(r"\s*```$", "", cleaned) #末尾の```を除去
    return cleaned.strip()


def parse_llm_json(raw):
    """LLM出力をdictに変換する。通常のjson.loads失敗時は主要フィールドだけ抜き出す"""
    import json

    cleaned = clean_json_response(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    #変更: reason内の改行などでjson.loadsが失敗したとき、主要フィールドだけ正規表現で復元する
    result = {}

    consensus_match = re.search(
        r'"consensus_reached"\s*:\s*(true|false)', cleaned, re.IGNORECASE
    )
    if consensus_match:
        result["consensus_reached"] = consensus_match.group(1).lower() == "true"

    verdict_match = re.search(
        r'"verdict"\s*:\s*"(approved|needs_revision|agree|disagree)"',
        cleaned,
        re.IGNORECASE,
    )
    if verdict_match:
        result["verdict"] = verdict_match.group(1).lower()

    needs_scout_match = re.search(
        r'"needs_scout"\s*:\s*(true|false)', cleaned, re.IGNORECASE
    )
    if needs_scout_match:
        result["needs_scout"] = needs_scout_match.group(1).lower() == "true"

    reason_match = re.search(r'"reason"\s*:\s*"(.*)"\s*\}\s*$', cleaned, re.DOTALL)
    if not reason_match:
        reason_match = re.search(r'"reason"\s*:\s*"(.*)', cleaned, re.DOTALL)
    if reason_match:
        reason = reason_match.group(1)
        reason = re.sub(r'"\s*\}\s*$', "", reason, flags=re.DOTALL)
        result["reason"] = reason.replace("\n", " ").strip()

    if result:
        return result

    return None


def parse_member_response(raw):
    """メンバー出力(JSON: chat + artifact_update)をパースし、chatは最大200字に切り詰める"""
    import json

    cleaned = clean_json_response(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        data = {}
        #変更: artifact_update内改行などでjson.loads失敗時、chat/artifact_updateだけ復元する
        chat_match = re.search(
            r'"chat"\s*:\s*"(.*?)"\s*,\s*"artifact_update"',
            cleaned,
            re.DOTALL,
        )
        if chat_match:
            data["chat"] = chat_match.group(1).replace("\\n", " ").replace("\n", " ")

        artifact_match = re.search(
            r'"artifact_update"\s*:\s*"(.*)"\s*\}\s*$',
            cleaned,
            re.DOTALL,
        )
        if artifact_match:
            data["artifact_update"] = artifact_match.group(1).replace("\\n", "\n")

    if not isinstance(data, dict):
        return None

    chat = data.get("chat", "")
    if isinstance(chat, list):
        chat = " ".join(str(item) for item in chat)
    chat = str(chat).replace("\n", " ").strip()
    if len(chat) > CHAT_MAX_CHARS:
        print(
            f"変更: chatが{CHAT_MAX_CHARS}字を超えたため切り詰めます"
            f"({len(chat)}字→{CHAT_MAX_CHARS}字)"
        )
        chat = chat[:CHAT_MAX_CHARS]

    artifact = data.get("artifact_update", "")
    if isinstance(artifact, list):
        artifact = "\n".join(str(item) for item in artifact)
    elif artifact is None:
        artifact = ""
    else:
        artifact = str(artifact)

    if not chat and not artifact:
        return None

    return {"chat": chat, "artifact_update": artifact}
