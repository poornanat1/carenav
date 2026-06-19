"""Contextualize a follow-up question into a standalone one (docs/03 routing input).

Each turn is otherwise stateless: the orchestrator routes, retrieves, and grounds on the
question text alone. That breaks multi-turn conversation — a follow-up like "what are the
side effects?" after "what is albuterol?" has no subject of its own, so routing and
retrieval land on whatever those bare words happen to match (an unrelated drug class).

This step runs FIRST, before redaction and routing. Given the recent conversation and the
new question, it asks a small model to rewrite the question so it stands on its own
("what are albuterol's side effects?"). It only rewrites when there is prior context AND
the question reads as a follow-up; a question that is already self-contained passes
through unchanged. It fails OPEN — no history, no gateway, or any error returns the
original question — so it can never make a turn worse than the stateless behavior.

The rewrite happens on the RAW question (before PII redaction) using the RAW history,
exactly as a human would read the thread; the redaction layer downstream then tokenizes
the resulting standalone question as usual.
"""

from __future__ import annotations

from dataclasses import dataclass

from carenav.models import ModelGateway


@dataclass(frozen=True)
class Turn:
    role: str  # "user" | "assistant"
    content: str


# Keep the prompt small: only the last few turns matter for resolving a follow-up.
_MAX_HISTORY_TURNS = 6
_MAX_QUESTION_LEN = 400

_CONTEXTUALIZE_PROMPT = """You rewrite a follow-up question so it can be understood on its \
own, without the chat history.

Conversation so far:
{history}

New question: {question}

Rewrite ONLY to resolve references the question cannot stand without — pronouns ("it", \
"that", "they"), elisions ("the side effects?", "what about dosage?"), or a missing \
subject. When you rewrite, name the omitted subject and change NOTHING else.

Do NOT add scope, framing, or topics the new question did not ask about. In particular, \
never bolt on the previous turn's topic — if the earlier turn was about plan coverage, \
deductibles, or benefits, do NOT add "under my plan", "coverage", "my CareNav plan", or \
similar to a question that did not mention them. A question that already names its own \
subject (e.g. "What should I know about high cholesterol?") ALREADY stands on its own — \
return it completely unchanged.

Output ONLY the question, nothing else."""


# Profile/coverage framing the rewrite must not introduce. If the model bolts any of these
# onto a question that didn't already contain them, we discard the rewrite — that framing
# drags an educational question into the member's coverage path and misroutes the turn.
_FRAMING_TERMS = (
    "my plan",
    "my carenav",
    "coverage",
    "covered",
    "deductible",
    "copay",
    "co-pay",
    "coinsurance",
    "out-of-pocket",
    "benefit",
    "in-network",
    "prior auth",
)


def _introduces_framing(original: str, rewritten: str) -> bool:
    """True if the rewrite added coverage/plan framing the original question lacked."""
    orig_low = original.lower()
    rew_low = rewritten.lower()
    return any(term in rew_low and term not in orig_low for term in _FRAMING_TERMS)


def _format_history(history: list[Turn]) -> str:
    recent = history[-_MAX_HISTORY_TURNS:]
    lines = []
    for turn in recent:
        who = "User" if turn.role == "user" else "Assistant"
        text = " ".join(turn.content.split())
        if text:
            lines.append(f"{who}: {text}")
    return "\n".join(lines)


def contextualize_question(
    question: str, history: list[Turn] | None, gateway: ModelGateway | None = None
) -> str:
    """Return a standalone version of `question` given prior `history`.

    Fails open: with no usable history, no gateway, or any model error, returns the
    original question unchanged.
    """
    if not history or gateway is None:
        return question
    formatted = _format_history(history)
    if not formatted:
        return question
    try:
        raw = gateway.generate(
            _CONTEXTUALIZE_PROMPT.format(history=formatted, question=question),
            label="orchestrator.contextualize",
        ).text
    except Exception:
        return question
    rewritten = raw.strip().strip("\"'`").splitlines()[0].strip() if raw.strip() else ""
    if not rewritten or len(rewritten) > _MAX_QUESTION_LEN:
        return question
    # Reject a rewrite that bolts on coverage/plan framing the original lacked — that
    # over-rewrite (e.g. adding "coverage under my CareNav Gold plan") misroutes an
    # educational question to the member's coverage path. Fail open to the original.
    if _introduces_framing(question, rewritten):
        return question
    return rewritten
