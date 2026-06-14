"""orchestrator — the turn state machine (docs/03, docs/06).

Implemented: route (safety triage + intent) → decompose → plan → tool_exec →
reflect → retrieve → generate (grounded) → verify → respond | escalate, with specialist
tools (member/benefit/claims/provider) whose structured facts are cited and grounded like
KB chunks, composite confidence (incl. tool_conf), tau-threshold bars, one frontier retry,
and a structured human handoff. Redaction is applied at user-input and tool-output
boundaries; session persistence extends this pipeline. Node names follow docs/03 so
adopting a graph framework stays mechanical.
"""

from carenav.orchestrator.state import ConfidenceBreakdown, HandoffPacket, TurnResult
from carenav.orchestrator.turn import run_turn

__all__ = ["run_turn", "TurnResult", "HandoffPacket", "ConfidenceBreakdown"]
