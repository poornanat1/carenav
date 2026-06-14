"""Generate a labeled PII corpus by templating real Synthea values into member utterances.

The key trick (internal/phase-3-plan.md): CareNav already loads synthetic members,
providers, and conditions into Postgres. We slot those real values into natural-language
templates; since we control where each value lands, the character-span labels are exact
and free — no hand annotation.

Output: JSON Lines, one example per line:

    {"text": "...", "spans": [{"start": 5, "end": 11, "label": "NAME"}, ...]}

Splits use DISJOINT member sets (train vs eval) so recall isn't memorization. Hard
negatives — health-laden utterances with no PII — are mixed in so the model doesn't learn
to tag clinical vocabulary.

Deterministic: no RNG (Date.now/random are avoided), variety comes from template index ×
record index, so a fresh clone regenerates the identical corpus.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from sqlalchemy import select

from carenav.config import settings
from carenav.data.db import session_scope
from carenav.data.models import Member, Provider
from carenav.redaction import entities as E


@dataclass(frozen=True)
class _Record:
    """One synthetic member's PII values, plus a provider name to weave in."""

    name: str
    dob: str  # ISO yyyy-mm-dd as it appears in prose
    address: str
    member_id: str
    provider_name: str | None


# The model's job is the FREE-TEXT RESIDUAL: PHI a user types in prose that field-match
# and regex structurally can't catch — names of THIRD PARTIES (a spouse, child, the
# member's doctor) we have no DB field for, and DOBs phrased differently than the stored
# ISO string. Member IDs / emails / phones are regex's job, so templates lean on the
# prose-only entities (NAME, DOB, ADDRESS, PROVIDER_NAME) and frame names as third parties.
_TEMPLATES: tuple[str, ...] = (
    "Hi, I'm calling about my husband {name}, born {dob}.",
    "My daughter {name} ({dob}) needs to see a specialist — is that covered?",
    "My doctor {provider_name} ordered an MRI. Is it covered?",
    "I saw {provider_name} last week and got a bill I don't understand.",
    "Can {provider_name} refer my son {name} to a cardiologist?",
    "My wife {name} was born on {dob}; is she still on my plan?",
    "We just moved to {address} — can you update the file for {name}?",
    "{name}, date of birth {dob}, is the patient. {provider_name} is the referring doctor.",
    "Following up for my mother {name}, who lives at {address}.",
    "My provider is {provider_name}. My partner {name} ({dob}) is also covered.",
    "The patient is {name}; DOB: {dob}; address: {address}.",
    "{provider_name} told {name} to call about coverage for therapy.",
    "Please send any plan letters for {name} to {address}.",
    "I need to confirm benefits for {name}. Birthday is {dob}.",
    "Our pediatrician {provider_name} referred {name} after the visit.",
    "The bill lists {provider_name}, but it should be under {name}.",
    "{name} lives at {address} and sees {provider_name}.",
    "Can you look up {name}? Their date of birth is {dob}.",
    "We moved. The new mailing address for {name} is {address}.",
    "I am helping {name}, DOB {dob}, with a claim from {provider_name}.",
    "The claim has the wrong home address: {address}.",
    "{provider_name} is not in network for {name}, born {dob}.",
    "My spouse {name} has a referral from {provider_name}.",
    "Use {address} as the service address for the appointment.",
    "This is about {name} at {address}; the doctor is {provider_name}.",
)

# Hard negatives: health/insurance vocabulary but NO patient PII. The model must NOT tag
# these (e.g. "MRI", drug names, plan terms, generic clinical mentions).
_HARD_NEGATIVES: tuple[str, ...] = (
    "Is an MRI covered under my plan?",
    "What's the copay for a specialist visit?",
    "Do I need prior authorization for physical therapy?",
    "Is metformin on the formulary?",
    "How much of my deductible have I met this year?",
    "Are urgent care visits in network?",
    "What does coinsurance mean for an emergency room visit?",
    "Can you explain why my claim was denied?",
    "Is a flu shot considered preventive care?",
    "What's the difference between the Gold and Silver plans?",
    "My doctor ordered lab work after an annual visit.",
    "Can a spouse stay on the plan after open enrollment?",
    "Please explain the referral rules for a specialist.",
    "Is a cardiology consult covered before meeting the deductible?",
    "The provider billed under the wrong place of service.",
    "Does the plan cover an out-of-network emergency?",
    "How do I appeal a denied imaging claim?",
    "Can you summarize my preventive care benefits?",
)

_LABEL_BY_PLACEHOLDER = {
    "name": E.NAME,
    "dob": E.DOB,
    "address": E.ADDRESS,
    "member_id": E.MEMBER_ID,
    "provider_name": E.PROVIDER_NAME,
}


def _render(template: str, rec: _Record) -> tuple[str, list[dict]] | None:
    """Fill a template from a record, returning (text, spans). None if a needed field is absent.

    Builds the string incrementally so each inserted value's character span is exact.
    """
    import re

    field_values = {
        "name": rec.name,
        "dob": rec.dob,
        "address": rec.address,
        "member_id": rec.member_id,
        "provider_name": rec.provider_name,
    }
    needed = set(re.findall(r"\{(\w+)\}", template))
    if any(not field_values.get(f) for f in needed):
        return None  # skip templates that need a field this record lacks (e.g. no provider)

    out: list[str] = []
    spans: list[dict] = []
    values: list[str] = []
    cursor = 0
    for m in re.finditer(r"\{(\w+)\}|([^{]+)", template):
        placeholder, literal = m.group(1), m.group(2)
        if literal is not None:
            out.append(literal)
            cursor += len(literal)
            continue
        value = field_values[placeholder]
        spans.append({
            "start": cursor,
            "end": cursor + len(value),
            "label": _LABEL_BY_PLACEHOLDER[placeholder],
        })
        values.append(value)
        out.append(value)
        cursor += len(value)
    text = "".join(out)
    # Sanity: every recorded span must slice back to the exact value inserted there.
    for s, fv in zip(spans, values, strict=True):
        assert text[s["start"]:s["end"]] == fv, (text, s, fv)
    return text, spans


_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def _phrase_dob(d, variant: int) -> str:
    """Render a DOB the way a person types it — NOT the stored ISO string.

    The stored value is yyyy-mm-dd; field-match keys on that exact form, so a reformatted
    DOB is precisely the residual the model must catch. Variant is chosen deterministically
    from the record index (no RNG) to spread phrasings across the corpus.
    """
    if d is None:
        return ""
    forms = (
        f"{_MONTHS[d.month - 1]} {d.day}, {d.year}",  # March 4, 1980
        f"{d.month}/{d.day}/{d.year}",                # 3/4/1980
        f"{d.month:02d}/{d.day:02d}/{str(d.year)[2:]}",  # 03/04/80
        f"{d.day} {_MONTHS[d.month - 1]} {d.year}",   # 4 March 1980
    )
    return forms[variant % len(forms)]


def _load_records(limit: int | None) -> list[_Record]:
    """Pull synthetic members (+ a provider name each, round-robin) from Postgres.

    NOTE: a record's `name` is a real synthetic person, but the templates frame it as a
    THIRD PARTY (spouse/child/doctor) — the residual field-match can't resolve for a turn.
    DOB is reformatted away from the stored ISO string for the same reason.
    """
    with session_scope() as session:
        members = session.execute(select(Member)).scalars().all()
        providers = session.execute(select(Provider.name)).scalars().all()
        recs: list[_Record] = []
        for i, m in enumerate(members):
            prov = providers[i % len(providers)] if providers else None
            recs.append(_Record(
                name=m.name,
                dob=_phrase_dob(m.dob, i),
                address=m.address or "",
                member_id=m.member_id,
                provider_name=prov,
            ))
    return recs[:limit] if limit else recs


def _examples_for(records: list[_Record]) -> list[dict]:
    """Cross each record with templates (record_index × template_index for variety)."""
    examples: list[dict] = []
    for ri, rec in enumerate(records):
        for ti in range(len(_TEMPLATES)):
            # Offset the template index by the record index so consecutive records don't
            # all start with template 0 — deterministic variety without RNG.
            tmpl = _TEMPLATES[(ti + ri) % len(_TEMPLATES)]
            rendered = _render(tmpl, rec)
            if rendered is None:
                continue
            text, spans = rendered
            examples.append({"text": text, "spans": spans})
    return examples


def _write_jsonl(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def generate(eval_fraction: float = 0.2, limit: int | None = None) -> dict[str, int]:
    """Generate train/eval PII corpora from Postgres members. Returns example counts.

    Members are split into disjoint train/eval sets BEFORE templating, so no member's
    values appear in both splits (recall on eval reflects generalization, not memorization).
    Hard negatives are appended to both splits.
    """
    records = _load_records(limit)
    if not records:
        raise RuntimeError(
            "No members found in Postgres. Run `make data` (Synthea ingest) before "
            "generating the PII corpus."
        )

    split = max(1, int(len(records) * (1 - eval_fraction)))
    train_recs, eval_recs = records[:split], records[split:]

    train = _examples_for(train_recs)
    eval_ = _examples_for(eval_recs)

    # Hard negatives (no spans) in both splits.
    negs = [{"text": t, "spans": []} for t in _HARD_NEGATIVES]
    train.extend(negs)
    eval_.extend(negs)

    train_path = os.path.join(settings.pii_corpus_dir, "train.jsonl")
    eval_path = os.path.join(settings.pii_corpus_dir, "eval.jsonl")
    _write_jsonl(train_path, train)
    _write_jsonl(eval_path, eval_)

    return {
        "train_examples": len(train),
        "eval_examples": len(eval_),
        "train_members": len(train_recs),
        "eval_members": len(eval_recs),
        "negatives_per_split": len(negs),
    }


if __name__ == "__main__":
    print(generate())
