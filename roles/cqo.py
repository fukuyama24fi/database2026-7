import json
import re

from db.read import get_persona
from llm.ask_llm import ask_llm
from prompts.build_system_prompt import build_system_prompt
from prompts.json_format_rules import CQO_JSON_EXAMPLE, JSON_FORMAT_RULES
from utils.parse_json import parse_llm_json

CQO_PERSONA_ID = "persona_exec_cqo"


def flag_suspicious_results(results):
    #部長2回差し戻し後の強制承認(forced_approved)を機械的に「怪しい」としてマーク
    flagged = []
    for result in results:
        is_suspicious = result.get("status") == "forced_approved" or bool(
            result.get("concerns_report")
        )
        result["is_suspicious"] = is_suspicious
        if is_suspicious:
            flagged.append(result)
    return flagged


def build_decision_summary(results):
    #CQO向けに各部署D-listのsummaryだけを渡す(プロンプト爆発対策)
    lines = []
    for result in results:
        dept = result["department_id"]
        task = result.get("dept_task", result.get("sub_task_text", ""))
        suspicious = " [怪しい]" if result.get("is_suspicious") else ""
        lines.append(f"## {dept}{suspicious}")
        lines.append(f"room_id: {result['room_id']}")  #CQO向けroom_id明示
        lines.append(f"タスク: {task}")
        lines.append(f"ルーム要約: {result.get('short_summary', '(なし)')}")
        decisions = result.get("decisions") or []
        if not decisions:
            lines.append("- (決定事項なし)")
        else:
            for idx, d in enumerate(decisions, start=1):
                did = d.get("decision_id", "?")
                ot = d.get("origin_turn", "?")
                lines.append(
                    f"- [{idx}] id={did} turn={ot} "
                    f"{d.get('decision_type', '?')}: {d.get('summary', '')}"
                )
        lines.append("")
    return "\n".join(lines).strip()


def build_suspicious_detail_section(flagged_results):
    #怪しい部署だけ詳細(D-list rationale + 懸念レポート)を追加
    if not flagged_results:
        return ""
    parts = ["【怪しい部署の詳細(重点監査)】"]
    for result in flagged_results:
        parts.append(f"\n### {result['department_id']} (status={result.get('status')})")
        if result.get("concerns_report"):
            parts.append(f"懸念レポート:\n{result['concerns_report']}")
        for d in result.get("decisions") or []:
            parts.append(
                f"- {d.get('summary', '')} (根拠: {d.get('rationale', '')})"
            )
        outputs = result.get("outputs_text", result.get("deliverables_text"))
        if outputs:
            parts.append(f"outputs抜粋:\n{outputs[:1500]}")
    return "\n".join(parts)


def build_room_id_reference(results):
    #CQOがroom_id/decision_idを取り違えないよう参照表を渡す(なぜかごちゃまぜにされる)
    lines = ["【room_id / decision_id 参照表(必ずこの値を使う)】"]
    for result in results:
        lines.append(f"room_id={result['room_id']} department={result['department_id']}")
        for d in result.get("decisions") or []:
            lines.append(
                f"  decision_id={d.get('decision_id')} type={d.get('decision_type')} "
                f"summary={d.get('summary', '')[:60]}"
            )
    return "\n".join(lines)


def normalize_cqo_conflicts(conflicts, results):
    #LLMが誤ったroom_id/decision_idを返した場合に機械的に補正する
    room_map = {r["room_id"]: r for r in results}
    decisions_by_room = {
        r["room_id"]: {d["decision_id"]: d for d in (r.get("decisions") or []) if d.get("decision_id")}
        for r in results
    }

    normalized = []
    for conflict in conflicts or []:
        fixed_affected = []
        for item in conflict.get("affected_decisions") or []:
            room_id = item.get("room_id", "")
            decision_id = item.get("decision_id", "")

            if room_id.startswith("dec_") or room_id not in room_map:
                for rid in room_map:
                    if rid in str(decision_id) or rid in str(room_id):
                        room_id = rid
                        break

            if room_id not in room_map:
                dept_ids = conflict.get("department_ids") or []
                for rid, res in room_map.items():
                    if res["department_id"] in dept_ids:
                        room_id = rid
                        break

            room_decisions = decisions_by_room.get(room_id, {})
            if decision_id not in room_decisions:
                for did, dec in room_decisions.items():
                    summary = dec.get("summary", "")
                    if decision_id == did or decision_id in summary or summary in str(decision_id):
                        decision_id = did
                        break
                if decision_id not in room_decisions and room_decisions:
                    decision_id = next(iter(room_decisions.keys()))

            if room_id in room_map and decision_id:
                fixed_affected.append({"room_id": room_id, "decision_id": decision_id})

        room_ids = [r for r in (conflict.get("room_ids") or []) if r in room_map]
        if not room_ids:
            room_ids = list({a["room_id"] for a in fixed_affected if a.get("room_id")})

        conflict["affected_decisions"] = fixed_affected
        conflict["room_ids"] = room_ids
        normalized.append(conflict)
    return normalized


def infer_conflicts_from_text(reason, results, raw_text=""):
    #CQOがconflicts配列を出さずreasonに長文を書いた場合、decision_id等から機械推定する
    combined = f"{reason}\n{raw_text}"
    decision_ids = list(dict.fromkeys(re.findall(r"dec_[a-zA-Z0-9_]+", combined)))
    if not decision_ids:
        return []

    dec_to_room = {}
    dept_by_room = {}
    for result in results:
        dept_by_room[result["room_id"]] = result["department_id"]
        for decision in result.get("decisions") or []:
            did = decision.get("decision_id")
            if did:
                dec_to_room[did] = result["room_id"]

    affected = []
    for did in decision_ids:
        room_id = dec_to_room.get(did)
        if room_id:
            affected.append({"room_id": room_id, "decision_id": did})

    if not affected:
        return []

    room_ids = list(dict.fromkeys(a["room_id"] for a in affected))
    department_ids = list(dict.fromkeys(dept_by_room[r] for r in room_ids))
    dept_in_text = re.findall(
        r"\b(UIUX|FE|BE|DX|QA|MOBILE|AI|INFRA|SECURITY|BUSINESS|EXTERNAL)\b",
        combined,
    )
    if dept_in_text:
        department_ids = list(dict.fromkeys(dept_in_text))

    return [
        {
            "conflict_id": "inferred_c1",
            "department_ids": department_ids,
            "room_ids": room_ids,
            "same_department": len(set(department_ids)) <= 1,
            "severity_level": 4,
            "rollback_from_turn": 3,
            "affected_decisions": affected,
            "description": (reason or "CQO reasonから推定")[:800],
            "inferred_from_reason": True,
        }
    ]


def cqo_check_cross_department(task_text, results):
    #CQOが全部署のD-list/outputsを横断して監査し、矛盾(conflicts)を検出する
    """CQOが全部署のD-listを横断監査し、部署間衝突・結合テスト整合性を確認する

    戻り値: {
      verdict: approved | needs_rollback,
      reason: str,
      conflicts: [{conflict_id, department_ids, room_ids, same_department, rollback_from_turn, description}]
    }
    """
    persona = get_persona(CQO_PERSONA_ID)
    if persona is None:
        return {
            "verdict": "needs_rollback",
            "reason": "CQO persona未設定",
            "conflicts": [],
        }

    flagged = flag_suspicious_results(results)
    overview = build_decision_summary(results)
    detail = build_suspicious_detail_section(flagged)
    room_ref = build_room_id_reference(results)

    system_prompt = build_system_prompt("CQO", persona)
    user_prompt = f"""プロジェクト要件: {task_text}

あなたはCQOです。全部署の確定D-list(summary)を見て、以下を確認してください:
1. 部署間でタスク・API・データ契約・UI仕様が矛盾していないか
2. 結合テスト可能な整合性があるか
3. 怪しい部署([怪しい]マーク)は重点的に確認(詳細セクション参照)

判断は各部署部長の専門ドメインに委ねる前提で、衝突の「事実」と「影響範囲」だけを特定してください。
同一department_id内の複数ルーム(例:UIUX設計とUIUX実装)の矛盾は same_department=true として報告してください。

{room_ref}

【全部署D-list概要(summaryのみ)】
{overview}

{detail}

重要: 出力はJSONオブジェクト1つのみ。前置き文・後書き・説明文は一切書かない。
{JSON_FORMAT_RULES}
{CQO_JSON_EXAMPLE}
reasonの値は必ずASCII二重引用符 "..." で囲む(「」は使わない)。reasonは1〜2文の要約のみ。
衝突の詳細は必ず conflicts 配列に書く(reasonに箇条書きを書かない)。
room_id/decision_idは参照表の値をそのままコピーすること(dec_で始まるのはdecision_id)。

出力JSON:
{{
  "verdict": "approved または needs_rollback",
  "reason": "判断理由",
  "conflicts": [
    {{
      "conflict_id": "c1",
      "department_ids": ["FE", "BE"],
      "room_ids": ["room_xxx_00", "room_xxx_01"],
      "same_department": false,
      "severity_level": 4,
      "rollback_from_turn": 3,
      "affected_decisions": [
        {{"room_id": "room_xxx_00", "decision_id": "dec_room_xxx_00_001"}},
        {{"room_id": "room_xxx_01", "decision_id": "dec_room_xxx_01_002"}}
      ],
      "description": "衝突内容の具体説明"
    }}
  ]
}}

severity_level: 0(軽微)〜5(致命的)。結合テスト不能・契約矛盾は4〜5。
affected_decisions: 矛盾に関わる決定を room_id+decision_id(参照表)で指定。
衝突が無ければ conflicts は空配列。verdict=approved。"""

    raw = ask_llm(system_prompt, user_prompt)
    result = parse_llm_json(raw)
    if result is None:
        print("CQO横断監査のJSON解析に失敗:")
        print(raw)
        return {
            "verdict": "needs_rollback",
            "reason": "解析失敗",
            "conflicts": [],
            "parse_failed": True,  #解析失敗フラグ(run_projectが誤って整合性OKとしない)(こうしないと喋れないLLMは放置されたままカオスになるだけ)
        }

    if "conflicts" not in result:
        result["conflicts"] = []

    #needs_rollbackなのにconflicts空=LLMがreasonに長文を書いたケースを機械推定
    if result.get("verdict") == "needs_rollback" and not result.get("conflicts"):
        inferred = infer_conflicts_from_text(result.get("reason", ""), results, raw_text=raw)
        if inferred:
            print(f"[CQO] conflicts空のためreason/rawから{len(inferred)}件を推定しました")
            result["conflicts"] = inferred
            result["conflicts_inferred"] = True

    result["conflicts"] = normalize_cqo_conflicts(result["conflicts"], results)
    result["parse_failed"] = False
    for conflict in result["conflicts"]:
        if "severity_level" not in conflict:
            conflict["severity_level"] = 3
        else:
            try:
                conflict["severity_level"] = max(0, min(5, int(conflict["severity_level"])))
            except (TypeError, ValueError):
                conflict["severity_level"] = 3
        if "affected_decisions" not in conflict:
            conflict["affected_decisions"] = []
    return result


def cqo_check_managers_agreement(task_text, conflict, meeting_transcript, manager_contexts):
    #部長討論ログを読み、衝突について合意できたかCQOが判定する
    """CQOが部長討論の合意形成をPMのように確認する

    戻り値: {agreed: bool, reason: str}
    """
    persona = get_persona(CQO_PERSONA_ID)
    if persona is None:
        return {"agreed": False, "reason": "CQO persona未設定"}

    system_prompt = build_system_prompt("CQO", persona)
    history = "\n".join(
        f"{m['speaker']}: {m['message']}" for m in meeting_transcript
    ) or "(まだ発言なし)"
    managers_overview = "\n".join(
        f"- {c['department_id']}: {c.get('dept_task', c.get('sub_task_text', ''))}" for c in manager_contexts
    )

    user_prompt = f"""プロジェクト要件: {task_text}

あなたはCQOですが、今はPMのように部長間討論の合意形成を確認してください。
専門判断は部長に委ね、両者(または全員)が整合方針で合意したかだけを判定します。

【衝突】
{conflict.get('description', '')}
重大度: {conflict.get('severity_level', 3)}/5

【参加部長】
{managers_overview}

【討論ログ】
{history}

JSONのみ:
{{
  "agreed": true または false,
  "reason": "合意/未合意の理由(簡潔に)"
}}"""

    raw = ask_llm(system_prompt, user_prompt)
    parsed = parse_llm_json(raw)
    if parsed is None:
        return {"agreed": False, "reason": "CQO合意確認の解析失敗"}
    if "agreed" not in parsed and "consensus_reached" in parsed:
        parsed["agreed"] = parsed.pop("consensus_reached")
    return {
        "agreed": bool(parsed.get("agreed")),
        "reason": str(parsed.get("reason", "")).strip(),
    }
