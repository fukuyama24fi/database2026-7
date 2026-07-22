import re


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
