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