from datetime import datetime
from pathlib import Path
import json
import shutil

#変更: 部長レビュー・CQO向けに、ルームごとのworkspace(成果物置き場)を扱う


def get_room_workspace(room_id):
    #変更: room_idごとの作業フォルダパスを返す
    return Path("workspaces") / room_id


def ensure_room_workspace(room_id):
    #変更: workspaceとdeliverablesサブフォルダを作成する
    root = get_room_workspace(room_id)
    deliverables = root / "deliverables"
    root.mkdir(parents=True, exist_ok=True)
    deliverables.mkdir(exist_ok=True)
    return root


def write_workspace_text(room_id, filename, content):
    #変更: workspace直下にテキストファイルを書き込む(d_list.txt等)
    root = ensure_room_workspace(room_id)
    path = root / filename
    path.write_text(content, encoding="utf-8")
    print(f"workspace/{room_id}/{filename} を書き込みました")
    return path


def read_workspace_text(room_id, filename, default=""):
    #変更: workspace直下のテキストファイルを読み込む
    path = get_room_workspace(room_id) / filename
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def task_expects_code(task_text):
    #変更: タスク文から「実装/コード必須」か「具体設計のみでOK」かを判定する
    impl_keywords = ["実装", "コード", "プログラム", "コーディング", "開発する", "APIを実装"]
    design_keywords = ["設計", "デザイン", "ワイヤー", "UI仕様", "情報設計", "レイアウト案", "ビジュアル"]
    has_impl = any(k in task_text for k in impl_keywords)
    has_design = any(k in task_text for k in design_keywords)
    if has_design and not has_impl:
        return False
    return True


def write_team_memo(room_id, members):
    #変更: 参加メンバーの名前・性格・スキル・PM割当役割を team_memo.txt に記録する
    lines = ["# ルーム参加メンバー一覧", ""]
    for member in members:
        try:
            skills = json.loads(member["skills"]) if member.get("skills") else []
        except (json.JSONDecodeError, TypeError):
            skills = []
        if isinstance(skills, list):
            skills_text = ", ".join(str(s) for s in skills)
        else:
            skills_text = str(skills)
        lines.append(f"## {member['display_name']} ({member['member_id']})")
        lines.append(f"性格: {member.get('personality', '不明')}")
        lines.append(f"スキル: {skills_text if skills_text else 'なし'}")
        lines.append(f"担当役割: {member.get('task_role', '未割当')}")  #変更: PMが割り当てた役割
        lines.append("")
    write_workspace_text(room_id, "team_memo.txt", "\n".join(lines).strip())


def read_team_memo(room_id):
    #変更: team_memo.txt を読み込む
    return read_workspace_text(room_id, "team_memo.txt", default="")


def merge_decisions(existing, new_decisions):
    #変更: 互換のため残すが、新フローでは extract の結果で全文上書きする(非推奨)
    if not new_decisions:
        return existing
    return new_decisions


def patch_decisions(existing, new_decisions):
    #変更: decision_typeをキーに変更箇所だけ上書き(同一typeは新内容で置換、無いtypeは追加、新リストに無いtypeは削除)
    if not new_decisions:
        return existing
    if not existing:
        return new_decisions
    by_type = {}
    for idx, decision in enumerate(existing):
        key = decision.get("decision_type") or f"legacy_{idx}"
        by_type[key] = decision
    for decision in new_decisions:
        key = decision.get("decision_type") or decision.get("summary", "")[:80]
        by_type[key] = decision
    new_types = {
        d.get("decision_type") or d.get("summary", "")[:80] for d in new_decisions
    }
    merged = []
    for decision in new_decisions:
        key = decision.get("decision_type") or decision.get("summary", "")[:80]
        merged.append(by_type[key])
    for key, decision in by_type.items():
        if key not in new_types and key.startswith("legacy_"):
            merged.append(decision)
    return merged


def write_provisional_d_list(room_id, decisions, preserve_if_empty=True):
    #変更: extract結果でd_list.txtを全文上書き(CQOが見る現行版。旧版はDBでoverridden)
    if not decisions:
        if preserve_if_empty:
            existing = read_workspace_text(room_id, "d_list.txt")
            if existing.strip() and existing != "(決定事項はありません)":
                print(f"変更: extract結果が空のため既存d_list.txtを保持します(room={room_id})")
                return existing
    lines = []
    for idx, decision in enumerate(decisions, start=1):
        decision_id = decision.get("decision_id", "")
        origin_turn = decision.get("origin_turn", "")
        lines.append(f"[{idx}] id={decision_id} turn={origin_turn} type={decision.get('decision_type', 'unknown')}")
        lines.append(f"  summary: {decision.get('summary', '')}")
        lines.append(f"  rationale: {decision.get('rationale', '')}")
        lines.append(f"  confidence: {decision.get('confidence', '')}")
        lines.append("")
    #変更: d_list.txtにdecision_id/origin_turnを出力(CQOのaffected_decisions特定用)
    content = "\n".join(lines).strip() or "(決定事項はありません)"
    write_workspace_text(room_id, "d_list.txt", content)
    return content


def read_deliverables_text(room_id):
    #変更: deliverables/内の制作物(.txt/.py/.md)を1つの文字列にまとめて返す
    deliverables_dir = get_room_workspace(room_id) / "deliverables"
    if not deliverables_dir.exists():
        return "（未作成）"

    parts = []
    for path in sorted(deliverables_dir.iterdir()):
        if path.name == "spec_history.txt":
            continue  #変更: 修正履歴は他部署参照用deliverablesから除外
        if path.is_file() and path.suffix.lower() in (".txt", ".py", ".md"):
            parts.append(f"--- {path.name} ---\n{path.read_text(encoding='utf-8')}")

    if not parts:
        return "（未作成）"
    return "\n\n".join(parts)


def read_spec_text(room_id):
    #変更: 全員共有の成果物 spec.txt を読み込む
    path = get_room_workspace(room_id) / "deliverables" / "spec.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_spec_text(room_id, content):
    #変更: artifact_update で spec.txt(最新版)を上書き保存する
    deliverables = ensure_room_workspace(room_id) / "deliverables"
    path = deliverables / "spec.txt"
    path.write_text(content, encoding="utf-8")
    print(f"workspace/{room_id}/deliverables/spec.txt を更新しました")


def append_spec_history(room_id, previous_content, new_content, author, note=""):
    #変更: ロールバック用に旧版specを spec_history.txt へ追記(他部署は参照しない)
    deliverables = ensure_room_workspace(room_id) / "deliverables"
    history_path = deliverables / "spec_history.txt"
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = [
        f"===== spec revision {timestamp} by {author} =====",
        f"note: {note or '(なし)'}",
        "--- previous spec.txt ---",
        previous_content.strip() or "(empty)",
        "--- replaced with ---",
        new_content.strip() or "(empty)",
        "",
    ]
    with history_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(entry))
    print(f"workspace/{room_id}/deliverables/spec_history.txt に履歴を追記しました")


def write_spec_with_history(room_id, new_content, author, note=""):
    #変更: spec.txtは最新版のみ。初回作成含め毎回spec_history.txtへ記録
    ensure_room_workspace(room_id)
    previous = read_spec_text(room_id)
    new_content = (new_content or "").strip()
    if not new_content:
        return

    if not previous.strip():
        append_spec_history(room_id, "(empty)", new_content, author, note or "初回作成")
    elif previous.strip() != new_content:
        append_spec_history(room_id, previous, new_content, author, note)
    else:
        append_spec_history(
            room_id, previous, new_content, author, note or "同一内容の再出力"
        )
    write_spec_text(room_id, new_content)


def get_project_final_dir(project_id):
    #変更: プロジェクト単位で最終成果物を集約するフォルダ
    return Path("workspaces") / "projects" / project_id / "final_deliverables"


def _dept_folder_name(result):
    room_id = result["room_id"]
    dept = result["department_id"]
    suffix = room_id.split("_")[-1] if "_" in room_id else room_id
    return f"{dept}_{suffix}"


def consolidate_project_deliverables(project_id, task_text, results, cqo_status=None):
    #変更: 各ルームの成果物を workspaces/projects/{project_id}/final_deliverables/ へ集約
    root = get_project_final_dir(project_id)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    index_lines = [
        f"プロジェクト: {project_id}",
        f"タスク: {task_text}",
        f"CQO状態: {cqo_status or '未実施'}",
        f"集約日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "=== 部署一覧 ===",
    ]
    all_specs = []

    for result in results:
        room_id = result["room_id"]
        folder = _dept_folder_name(result)
        dept_dir = root / folder
        dept_dir.mkdir(parents=True, exist_ok=True)

        spec = read_spec_text(room_id)
        d_list = read_workspace_text(room_id, "d_list.txt")
        (dept_dir / "spec.txt").write_text(spec.strip() or "(未作成)", encoding="utf-8")
        (dept_dir / "d_list.txt").write_text(d_list.strip() or "(なし)", encoding="utf-8")
        (dept_dir / "task.txt").write_text(result.get("sub_task_text", ""), encoding="utf-8")

        meta_lines = [
            f"room_id={room_id}",
            f"department_id={result['department_id']}",
            f"status={result.get('status', '')}",
            f"is_suspicious={result.get('is_suspicious', False)}",
            f"decisions_count={len(result.get('decisions') or [])}",
        ]
        (dept_dir / "meta.txt").write_text("\n".join(meta_lines), encoding="utf-8")

        src_deliverables = get_room_workspace(room_id) / "deliverables"
        if src_deliverables.exists():
            for path in sorted(src_deliverables.iterdir()):
                if path.name in ("spec.txt", "spec_history.txt"):
                    continue
                if path.is_file():
                    shutil.copy2(path, dept_dir / path.name)

        index_lines.append(
            f"- {folder}/  status={result.get('status')}  room={room_id}"
        )
        if spec.strip():
            all_specs.append(
                f"===== {result['department_id']} ({room_id}) =====\n{spec.strip()}"
            )

    (root / "INDEX.txt").write_text("\n".join(index_lines), encoding="utf-8")
    (root / "ALL_SPECS.txt").write_text(
        "\n\n".join(all_specs) if all_specs else "(specなし)", encoding="utf-8"
    )

    rel = f"workspaces/projects/{project_id}/final_deliverables/"
    print(f"{rel} に最終成果物を集約しました ({len(results)}部署)")
    return root


def build_peer_deliverables_context(peer_results, current_room_id=None):
    #変更: 先行部署のspec/D-list概要を後続部署メンバーが参照できるようにする
    if not peer_results:
        return ""
    lines = [
        "【他部署の確定成果物(参照用。自部署決定はこれと矛盾しないこと)】",
    ]
    for result in peer_results:
        if current_room_id and result.get("room_id") == current_room_id:
            continue
        lines.append(f"## {result['department_id']} room_id={result['room_id']}")
        lines.append(f"タスク: {result.get('sub_task_text', '')}")
        spec = read_spec_text(result["room_id"])
        if spec.strip():
            excerpt = spec.strip()[:1500]
            lines.append(f"spec.txt:\n{excerpt}")
        decisions = result.get("decisions") or []
        if decisions:
            lines.append("D-list(summary):")
            for d in decisions[:8]:
                lines.append(f"- {d.get('decision_type', '?')}: {d.get('summary', '')}")
        lines.append("")
    return "\n".join(lines).strip()
