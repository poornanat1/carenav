"""Generate a KB bridge for every clinical condition label in the Synthea fixture."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from carenav.data import condition_topics

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "synthea_clinical_codes.json"
OUT = (
    ROOT
    / "src"
    / "carenav"
    / "rag"
    / "corpus"
    / "consumer_health"
    / "synthea-condition-index.md"
)


def _topic_label(topic: str) -> str:
    return topic.replace("-", " ").title()


def _clean_display(display: str) -> str:
    suffixes = [
        " (disorder)",
        " (finding)",
        " (situation)",
        " (morphologic abnormality)",
    ]
    for suffix in suffixes:
        if display.endswith(suffix):
            return display[: -len(suffix)]
    return display


def _line(display: str, topic: str) -> str:
    clean = _clean_display(display)
    label = _topic_label(topic)
    if clean == display:
        return f"- {display}: Synthea clinical condition mapped to {label}."
    return f"- {clean}: Synthea clinical condition label `{display}` mapped to {label}."


def main() -> None:
    rows = json.loads(FIXTURE.read_text())
    grouped: dict[str, list[dict]] = defaultdict(list)
    skipped = 0
    for row in rows:
        display = row["display"]
        topic = condition_topics.topic_for(display)
        if topic is None:
            skipped += 1
            continue
        grouped[topic].append(row)

    lines = [
        "---",
        "doc_id: mplus-synthea-condition-index",
        "source_type: consumer_health",
        "title: Synthea Clinical Condition Index",
        "source_url: https://github.com/synthetichealth/synthea",
        "last_reviewed: 2026-06-17",
        "---",
        "",
        "# Synthea Clinical Condition Index",
        "",
        "This CareNav demo index bridges Synthea clinical condition labels to the",
        "consumer-health KB topic used for retrieval. It is not a standalone diagnosis",
        "guide; it exists so exact Synthea terms can be grounded and then connected to",
        "the broader reviewed health topic.",
        "",
    ]

    total = 0
    for topic in sorted(grouped):
        items = sorted(grouped[topic], key=lambda item: item["display"].lower())
        total += len(items)
        lines.extend([f"## {_topic_label(topic)}", ""])
        lines.extend(_line(item["display"], topic) for item in items)
        lines.append("")

    lines.append(f"Indexed clinical condition labels: {total}.")
    lines.append(f"Skipped non-clinical Synthea context labels: {skipped}.")
    OUT.write_text("\n".join(lines) + "\n")
    print({"indexed": total, "skipped": skipped, "out": str(OUT.relative_to(ROOT))})


if __name__ == "__main__":
    main()
