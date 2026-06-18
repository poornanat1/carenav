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

If the new question depends on the conversation (it refers to "it", "that", "the side \
effects", "what about ...", or otherwise omits its subject), rewrite it as a single \
self-contained question that names the subject explicitly. If the new question already \
stands on its own, return it unchanged. Output ONLY the question, nothing else."""


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
    return rewritten
