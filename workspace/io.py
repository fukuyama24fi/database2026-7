from datetime import datetime
from pathlib import Path
import json
import shutil

#部長レビュー・CQO向けに、ルームごとのworkspace(成果物置き場)を扱う


def get_room_workspace(room_id):
    #ルーム専用フォルダ(workspaces/room_xxx)のPathを返す
    return Path("workspaces") / room_id


def _outputs_dir(room_id):
    #新形式 outputs/ を優先。既存 workspaces の deliverables/ も読める
    root = get_room_workspace(room_id)
    new_dir = root / "outputs"
    legacy_dir = root / "deliverables"
    if new_dir.exists() or not legacy_dir.exists():
        return new_dir
    return legacy_dir


def ensure_room_workspace(room_id):
    #ルーム用フォルダとoutputs/を無ければ作成する
    root = get_room_workspace(room_id)
    outputs = root / "outputs"
    root.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(exist_ok=True)
    return root


def write_workspace_text(room_id, filename, content):
    #team_memo.txt等、ルーム直下のテキストファイルを書き込む
    root = ensure_room_workspace(room_id)
    path = root / filename
    path.write_text(content, encoding="utf-8")
    print(f"workspace/{room_id}/{filename} を書き込みました")
    return path


def read_workspace_text(room_id, filename, default=""):
    #ルーム直下のテキストファイルを読む(無ければdefaultを返す)
    path = get_room_workspace(room_id) / filename
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def task_expects_code(task_text):
    #タスク文から「コード実装」か「設計のみ」かをキーワードで判定する
    impl_keywords = ["実装", "コード", "プログラム", "コーディング", "開発する", "APIを実装"]
    design_keywords = ["設計", "デザイン", "ワイヤー", "UI仕様", "情報設計", "レイアウト案", "ビジュアル"]
    has_impl = any(k in task_text for k in impl_keywords)
    has_design = any(k in task_text for k in design_keywords)
    if has_design and not has_impl:
        return False
    return True


def write_team_memo(room_id, members):
    lines = ["#ルーム参加メンバー一覧", ""]
    for member in members:
        try:
            skills = json.loads(member["skills"]) if member.get("skills") else []
        except (json.JSONDecodeError, TypeError):
            skills = []
        if isinstance(skills, list):
            skills_text = ", ".join(str(s) for s in skills)
        else:
            skills_text = str(skills)
        lines.append(f"##{member['display_name']} ({member['member_id']})")
        lines.append(f"性格: {member.get('personality', '不明')}")
        lines.append(f"スキル: {skills_text if skills_text else 'なし'}")
        lines.append(f"担当役割: {member.get('task_role', '未割当')}")
        lines.append("")
    write_workspace_text(room_id, "team_memo.txt", "\n".join(lines).strip())


def read_team_memo(room_id):
    return read_workspace_text(room_id, "team_memo.txt", default="")


def write_d_list(room_id, decisions, skip_if_empty=True):
    #D-list(決定事項一覧)をd_list.txtに書き出す。空抽出時は既存を保持できる
    if not decisions:
        if skip_if_empty:
            existing = read_workspace_text(room_id, "d_list.txt")
            if existing.strip() and existing != "(決定事項はありません)":
                print(f"変更: 抽出結果が空のため既存d_list.txtを保持します(room={room_id})")
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
    content = "\n".join(lines).strip() or "(決定事項はありません)"
    write_workspace_text(room_id, "d_list.txt", content)
    return content


def _design_file_paths(room_id):
    root = get_room_workspace(room_id)
    return [
        root / "outputs" / "design.txt",
        root / "deliverables" / "spec.txt",
    ]


def read_all_outputs(room_id):
    #outputs/内の.txt/.py/.mdを全部読んで1つの文字列にまとめる(部長検収用)
    outputs_dir = _outputs_dir(room_id)
    if not outputs_dir.exists():
        return "（未作成）"

    skip_names = {"design_history.txt", "spec_history.txt"}
    parts = []
    for path in sorted(outputs_dir.iterdir()):
        if path.name in skip_names:
            continue
        if path.is_file() and path.suffix.lower() in (".txt", ".py", ".md"):
            parts.append(f"--- {path.name} ---\n{path.read_text(encoding='utf-8')}")

    if not parts:
        return "（未作成）"
    return "\n\n".join(parts)


def read_design_doc(room_id):
    #design.txt(旧spec.txt)の内容を読む。新形式outputs/を優先
    for path in _design_file_paths(room_id):
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def write_design_doc(room_id, content):
    #outputs/design.txtに設計書を書き込む
    outputs = ensure_room_workspace(room_id) / "outputs"
    path = outputs / "design.txt"
    path.write_text(content, encoding="utf-8")
    print(f"workspace/{room_id}/outputs/design.txt を更新しました")


def append_design_history(room_id, previous_content, new_content, author, note=""):
    outputs = ensure_room_workspace(room_id) / "outputs"
    history_path = outputs / "design_history.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = [
        f"===== design revision {timestamp} by {author} =====",
        f"note: {note or '(なし)'}",
        "--- previous design.txt ---",
        previous_content.strip() or "(empty)",
        "--- replaced with ---",
        new_content.strip() or "(empty)",
        "",
    ]
    with history_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(entry))
    print(f"workspace/{room_id}/outputs/design_history.txt に履歴を追記しました")


def write_design_with_history(room_id, new_content, author, note=""):
    #design.txt更新時にdesign_history.txtへ差分履歴を残す
    ensure_room_workspace(room_id)
    previous = read_design_doc(room_id)
    new_content = (new_content or "").strip()
    if not new_content:
        return

    if not previous.strip():
        append_design_history(room_id, "(empty)", new_content, author, note or "初回作成")
    elif previous.strip() != new_content:
        append_design_history(room_id, previous, new_content, author, note)
    else:
        append_design_history(
            room_id, previous, new_content, author, note or "同一内容の再出力"
        )
    write_design_doc(room_id, new_content)


def get_project_final_dir(project_id):
    return Path("workspaces") / "projects" / project_id / "final_outputs"


def _dept_folder_name(result):
    room_id = result["room_id"]
    dept = result["department_id"]
    suffix = room_id.split("_")[-1] if "_" in room_id else room_id
    return f"{dept}_{suffix}"


def collect_final_outputs(project_id, task_text, results, cqo_status=None):
    #全部署のdesign.txt等をworkspaces/projects/xxx/final_outputs/に集約する
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
    all_designs = []

    for result in results:
        room_id = result["room_id"]
        folder = _dept_folder_name(result)
        dept_dir = root / folder
        dept_dir.mkdir(parents=True, exist_ok=True)

        design = read_design_doc(room_id)
        d_list = read_workspace_text(room_id, "d_list.txt")
        (dept_dir / "design.txt").write_text(design.strip() or "(未作成)", encoding="utf-8")
        (dept_dir / "d_list.txt").write_text(d_list.strip() or "(なし)", encoding="utf-8")
        (dept_dir / "task.txt").write_text(result.get("dept_task", ""), encoding="utf-8")

        meta_lines = [
            f"room_id={room_id}",
            f"department_id={result['department_id']}",
            f"status={result.get('status', '')}",
            f"is_suspicious={result.get('is_suspicious', False)}",
            f"decisions_count={len(result.get('decisions') or [])}",
        ]
        (dept_dir / "meta.txt").write_text("\n".join(meta_lines), encoding="utf-8")

        src_outputs = _outputs_dir(room_id)
        if src_outputs.exists():
            for path in sorted(src_outputs.iterdir()):
                if path.name in ("design.txt", "design_history.txt", "spec.txt", "spec_history.txt"):
                    continue
                if path.is_file():
                    shutil.copy2(path, dept_dir / path.name)

        index_lines.append(
            f"- {folder}/  status={result.get('status')}  room={room_id}"
        )
        if design.strip():
            all_designs.append(
                f"===== {result['department_id']} ({room_id}) =====\n{design.strip()}"
            )

    (root / "INDEX.txt").write_text("\n".join(index_lines), encoding="utf-8")
    (root / "ALL_DESIGNS.txt").write_text(
        "\n\n".join(all_designs) if all_designs else "(designなし)", encoding="utf-8"
    )

    rel = f"workspaces/projects/{project_id}/final_outputs/"
    print(f"{rel} に最終成果物を集約しました ({len(results)}部署)")
    return root


def other_dept_outputs_text(peer_results, current_room_id=None):
    #他部署のdesign.txt/D-list抜粋をメンバー向けプロンプト用に整形する
    if not peer_results:
        return ""
    lines = [
        "【他部署の確定成果物(参照用。自部署決定はこれと矛盾しないこと)】",
    ]
    for result in peer_results:
        if current_room_id and result.get("room_id") == current_room_id:
            continue
        lines.append(f"##{result['department_id']} room_id={result['room_id']}")
        lines.append(f"タスク: {result.get('dept_task', '')}")
        design = read_design_doc(result["room_id"])
        if design.strip():
            excerpt = design.strip()[:1500]
            lines.append(f"design.txt:\n{excerpt}")
        decisions = result.get("decisions") or []
        if decisions:
            lines.append("D-list(summary):")
            for d in decisions[:8]:
                lines.append(f"- {d.get('decision_type', '?')}: {d.get('summary', '')}")
        lines.append("")
    return "\n".join(lines).strip()
