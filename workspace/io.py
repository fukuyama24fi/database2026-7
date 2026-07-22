from pathlib import Path

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


def write_provisional_d_list(room_id, decisions):
    #変更: extract_decisionsの結果を暫定d_list.txtとしてworkspaceに保存(DB確定前)
    lines = []
    for idx, decision in enumerate(decisions, start=1):
        lines.append(f"[{idx}] type={decision.get('decision_type', 'unknown')}")
        lines.append(f"  summary: {decision.get('summary', '')}")
        lines.append(f"  rationale: {decision.get('rationale', '')}")
        lines.append(f"  confidence: {decision.get('confidence', '')}")
        lines.append("")
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
        if path.is_file() and path.suffix.lower() in (".txt", ".py", ".md"):
            parts.append(f"--- {path.name} ---\n{path.read_text(encoding='utf-8')}")

    if not parts:
        return "（未作成）"
    return "\n\n".join(parts)
