#変更: 後方互換。新フローは meeting/surgical_rollback.py を使用
from meeting.surgical_rollback import (
    apply_surgical_rollback,
    apply_turn_rollback,
    build_surgical_revision_state,
    build_turn_rollback_resume_state,
    truncate_discussion_state,
)

#変更: 旧名互換
build_rollback_resume_state = build_turn_rollback_resume_state
apply_local_rollback = apply_turn_rollback

__all__ = [
    "truncate_discussion_state",
    "build_rollback_resume_state",
    "build_turn_rollback_resume_state",
    "build_surgical_revision_state",
    "apply_local_rollback",
    "apply_turn_rollback",
    "apply_surgical_rollback",
]
