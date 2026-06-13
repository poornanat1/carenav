"""orchestrator — the turn state machine (docs/03, docs/06).

Implemented (M2 + M4): route (safety triage + intent) → decompose → plan → tool_exec →
reflect → retrieve → generate (grounded) → verify → respond | escalate, with specialist
tools (member/benefit/claims/provider) whose structured facts are cited and grounded like
KB chunks, composite confidence (incl. tool_conf), tau-threshold bars, one frontier retry,
and a structured human handoff. Remaining M3 node (redact) and session persistence extend
this pipeline; node names follow docs/03 so adopting a graph framework stays mechanical.
"""

from carenav.orchestrator.state import ConfidenceBreakdown, HandoffPacket, TurnResult
from carenav.orchestrator.turn import run_turn

__all__ = ["run_turn", "TurnResult", "HandoffPacket", "ConfidenceBreakdown"]
