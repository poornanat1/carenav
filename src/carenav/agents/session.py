"""member_ref → member_id indirection (docs/04).

The orchestrator and prompts only ever see an opaque `member_ref`; the agent layer
resolves it to the real `member_id` here. The map is process-local for now (the M2
slice); the session store moves out of process (Redis / managed KV) with deployment.
"""

from __future__ import annotations

import secrets

_REF_TO_MEMBER: dict[str, str] = {}


def create_member_ref(member_id: str) -> str:
    """Issue an opaque session ref for a member (e.g. at authentication time)."""
    ref = f"mref_{secrets.token_hex(8)}"
    _REF_TO_MEMBER[ref] = member_id
    return ref


def resolve_member_ref(member_ref: str | None) -> str | None:
    """Resolve a ref to the real member_id; None if absent/unknown (caller degrades)."""
    if not member_ref:
        return None
    return _REF_TO_MEMBER.get(member_ref)


def clear_sessions() -> None:
    """Test hook."""
    _REF_TO_MEMBER.clear()
