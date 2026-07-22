import json
import re

try:
    import dirtyjson  #変更: クォート忘れ・末尾カンマ等の壊れたJSONを寛容にパース
except ImportError:
    dirtyjson = None

CHAT_MAX_CHARS = 200  #変更: メンバー進行用chatの最大文字数

JSON_STRING_REPAIR_KEYS = (
    "artifact_update",
    "chat",
    "reason",
    "rationale",
    "revision_report",
    "message",
    "description",
    "summary",
)


def clean_json_response(raw):
    """LLMが```json ... ```のようにコードブロックで囲んで返してくることがあるので、
    先頭・末尾の```を取り除いてから渡せるようにする(memory.py/cto.py/cqo.py共通で使う)
    """
    cleaned = raw.strip()
    #変更: 文頭・文末の不要なバックスラッシュを除去
    cleaned = cleaned.strip("\\")
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def extract_json_object(raw):
    #変更: 前置き文混じりの出力から最初のJSONオブジェクト{...}だけを抜き出す
    text = clean_json_response(raw)
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json_array_after_key(text, key):
    #変更: conflicts等の配列を括弧バランスで抽出(非貪欲regexの取りこぼし防止)
    marker = f'"{key}"'
    idx = text.find(marker)
    if idx < 0:
        return None
    colon = text.find(":", idx + len(marker))
    if colon < 0:
        return None
    start = text.find("[", colon)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json_array_root(raw):
    #変更: 前置き混じり出力から最初のJSON配列[...]だけを抜き出す(D-list extract用)
    text = clean_json_response(raw)
    start = text.find("[")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _try_json_loads_any(text):
    if not text:
        return None
    for loader in (json.loads, dirtyjson.loads if dirtyjson else None):
        if loader is None:
            continue
        try:
            return loader(text)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return None


def parse_llm_json_array(raw):
    #変更: D-list extract等のJSON配列出力を寛容にパース(rationale内改行対応)
    candidates = []
    preprocessed = preprocess_llm_json(raw)
    if preprocessed:
        candidates.append(preprocessed)
    array_root = extract_json_array_root(raw)
    if array_root:
        candidates.append(array_root)
    extracted = extract_json_object(raw)
    if extracted:
        candidates.append(extracted)
    candidates.append(clean_json_response(raw))

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        for text in (candidate, normalize_json_text(candidate)):
            data = _try_json_loads_any(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for key in ("decisions", "items", "results"):
                    if isinstance(data.get(key), list):
                        return data[key]

    cleaned = normalize_json_text(
        preprocess_llm_json(raw) or extract_json_array_root(raw) or clean_json_response(raw)
    )
    array_text = extract_json_array_root(cleaned)
    if array_text:
        data = _try_json_loads_any(array_text)
        if isinstance(data, list):
            return data
    return []


def sanitize_markdown_line(line):
    #変更: JSON文字列内のMarkdown行頭記号(# * - 番号付き)を除去
    line = line.rstrip()
    line = re.sub(r"^#{1,6}\s*", "", line)
    line = re.sub(r"^[\*\-\+]\s+", "", line)
    line = re.sub(r"^\d+\.\s+", "", line)
    line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
    line = re.sub(r"\*(.+?)\*", r"\1", line)
    line = re.sub(r"`([^`]+)`", r"\1", line)
    return line


def sanitize_markdown_in_plain_text(text):
    #変更: 文字列値内Markdownをプレーン文本に整形
    if not text:
        return text
    lines = [sanitize_markdown_line(line) for line in text.split("\n")]
    return "\n".join(lines).strip()


def _json_escape_string_content(text):
    return json.dumps(text, ensure_ascii=False)[1:-1]


def repair_json_string_field(text, key):
    #変更: 指定キーの文字列値で生改行・未エスケープ引用符を修復
    pattern = re.compile(rf'"{re.escape(key)}"\s*:\s*"', re.DOTALL)
    match = pattern.search(text)
    if not match:
        return text

    start_quote = match.end() - 1
    i = start_quote + 1
    content_chars = []
    closed = False

    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            content_chars.append(ch)
            content_chars.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            rest = text[i + 1 :].lstrip()
            if rest.startswith(",") or rest.startswith("}"):
                closed = True
                break
            content_chars.append('"')
            i += 1
            continue
        if ch == "\n":
            content_chars.append("\n")
            i += 1
            continue
        content_chars.append(ch)
        i += 1

    if closed:
        raw_value = "".join(content_chars)
        end_idx = i
    else:
        end_brace = text.rfind("}")
        raw_value = text[start_quote + 1 : end_brace].strip()
        if raw_value.endswith('"'):
            raw_value = raw_value[:-1]
        end_idx = text.rfind("}")

    cleaned_value = sanitize_markdown_in_plain_text(raw_value)
    escaped_value = _json_escape_string_content(cleaned_value)
    return text[: start_quote + 1] + escaped_value + text[end_idx:]


def normalize_json_text(text):
    #変更: 日本語引用符やreasonフィールドの不正引用をASCII JSON向けに正規化
    normalized = text
    normalized = re.sub(r":\s*「([^」]*)」", r': "\1"', normalized)
    normalized = re.sub(r":\s*『([^』]*)』", r': "\1"', normalized)
    normalized = normalized.replace("「", '"').replace("」", '"')
    normalized = normalized.replace("『", '"').replace("』", '"')
    normalized = re.sub(r",\s*}", "}", normalized)
    normalized = re.sub(r",\s*]", "]", normalized)
    return normalized


def preprocess_llm_json(raw):
    #変更: LLM出力JSONのプリプロセッサ(Markdown除去・文字列修復・引用符正規化)
    text = extract_json_object(raw) or clean_json_response(raw)
    if not text:
        return ""
    text = normalize_json_text(text)
    for key in JSON_STRING_REPAIR_KEYS:
        text = repair_json_string_field(text, key)
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)
    return text


def _try_json_loads(text):
    if not text:
        return None
    data = _try_json_loads_any(text)
    if isinstance(data, dict):
        return data
    return None


def parse_llm_json(raw):
    """LLM出力をdictに変換。前置き混じり・Markdown混入・日本語引用符・壊れたJSONにも耐性"""
    candidates = []
    preprocessed = preprocess_llm_json(raw)
    if preprocessed:
        candidates.append(preprocessed)
    extracted = extract_json_object(raw)
    if extracted:
        candidates.append(extracted)
    candidates.append(clean_json_response(raw))

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        for text in (candidate, normalize_json_text(candidate)):
            data = _try_json_loads(text)
            if data is not None:
                return data

    cleaned = normalize_json_text(preprocess_llm_json(raw) or extract_json_object(raw) or clean_json_response(raw))
    result = {}

    consensus_match = re.search(
        r'"consensus_reached"\s*:\s*(true|false)', cleaned, re.IGNORECASE
    )
    if consensus_match:
        result["consensus_reached"] = consensus_match.group(1).lower() == "true"

    verdict_match = re.search(
        r'"verdict"\s*:\s*"(approved|needs_revision|needs_rollback|agree|disagree)"',
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

    reason_match = re.search(r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    if reason_match:
        result["reason"] = sanitize_markdown_in_plain_text(
            reason_match.group(1).replace("\\n", " ")
        ).strip()

    conflicts_array = extract_json_array_after_key(cleaned, "conflicts")
    if conflicts_array:
        parsed_conflicts = _try_json_loads(f"{{\"conflicts\": {conflicts_array}}}")
        if parsed_conflicts and isinstance(parsed_conflicts.get("conflicts"), list):
            result["conflicts"] = parsed_conflicts["conflicts"]

    if result:
        if "conflicts" not in result:
            result["conflicts"] = []
        return result

    return None


def _regex_fallback_member_response(cleaned):
    data = {}
    chat_match = re.search(
        r'"chat"\s*:\s*"(.*?)"\s*,\s*"artifact_update"',
        cleaned,
        re.DOTALL,
    )
    if chat_match:
        data["chat"] = sanitize_markdown_in_plain_text(
            chat_match.group(1).replace("\\n", " ").replace("\n", " ")
        )

    artifact_match = re.search(
        r'"artifact_update"\s*:\s*"(.*)"\s*\}\s*$',
        cleaned,
        re.DOTALL,
    )
    if not artifact_match:
        artifact_match = re.search(
            r'"artifact_update"\s*:\s*"(.*)',
            cleaned,
            re.DOTALL,
        )
    if artifact_match:
        raw_artifact = artifact_match.group(1)
        raw_artifact = re.sub(r'"\s*\}\s*$', "", raw_artifact, flags=re.DOTALL)
        data["artifact_update"] = sanitize_markdown_in_plain_text(
            raw_artifact.replace("\\n", "\n")
        )
    return data


def parse_member_response(raw):
    """メンバー出力(JSON: chat + artifact_update)をパース。parse_errorで構文失敗を返す"""
    parse_error = False
    data = None

    candidates = []
    preprocessed = preprocess_llm_json(raw)
    if preprocessed:
        candidates.append(preprocessed)
    extracted = extract_json_object(raw)
    if extracted:
        candidates.append(extracted)
    candidates.append(clean_json_response(raw))

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        for text in (candidate, normalize_json_text(candidate)):
            loaded = _try_json_loads(text)
            if loaded is not None:
                data = loaded
                break
        if data is not None:
            break

    if data is None:
        parse_error = True
        cleaned = preprocess_llm_json(raw) or clean_json_response(raw)
        data = _regex_fallback_member_response(cleaned)
        if not data.get("chat") and not data.get("artifact_update"):
            return None

    chat = data.get("chat", "")
    if isinstance(chat, list):
        chat = " ".join(str(item) for item in chat)
    chat = sanitize_markdown_in_plain_text(str(chat).replace("\n", " ")).strip()
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
        artifact = sanitize_markdown_in_plain_text(str(artifact))

    if not chat and not artifact:
        return None

    return {"chat": chat, "artifact_update": artifact, "parse_error": parse_error}


def is_parser_error_message(message):
    if not message:
        return False
    markers = (
        "解析できませんでした",
        "出力を解析",
        "personaが見つかりません",
        "JSON",
    )
    return any(m in message for m in markers)
