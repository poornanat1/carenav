"""Diagnose Mistral fine-tuning availability for the PII SFT job.

Legacy / manual diagnostic for the *Mistral* managed fine-tuning path, kept separate from
the live PII pipeline (which runs on Fireworks — see finetune.py). By default this is
read-only: it calls GET /v1/models and prints the fine-tuning metadata Mistral returns for
base models. Pass ``--attempt-create`` with an already uploaded training file id to
reproduce the job-create response with ``auto_start=false``.

Note ``--model`` must be a MISTRAL base model id (this hits api.mistral.ai), not the
Fireworks ``settings.pii_base_model`` the production pipeline uses.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import httpx

from carenav.config import settings

_API_BASE = "https://api.mistral.ai"
# A Mistral base model that supports managed fine-tuning (this script targets api.mistral.ai,
# so it must NOT default to the Fireworks settings.pii_base_model).
_DEFAULT_MISTRAL_BASE = "open-mistral-7b"


def _headers() -> dict[str, str]:
    if not settings.mistral_api_key:
        raise RuntimeError("MISTRAL_API_KEY is required for Mistral fine-tuning diagnostics.")
    return {
        "Authorization": f"Bearer {settings.mistral_api_key}",
        "Content-Type": "application/json",
    }


def _model_id(model: dict[str, Any]) -> str:
    return str(model.get("id") or model.get("name") or "")


def _model_type(model: dict[str, Any]) -> str:
    return str(model.get("type") or model.get("model_type") or "")


def _fine_tuning_flag(model: dict[str, Any]) -> bool:
    capabilities = model.get("capabilities")
    if isinstance(capabilities, dict) and capabilities.get("fine_tuning") is True:
        return True
    return model.get("fine_tuning") is True


def _not_deprecated(model: dict[str, Any]) -> bool:
    return model.get("deprecated") is not True and model.get("deprecation") is None


def _redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(payload))
    for file_ref in redacted.get("training_files", []):
        if "file_id" in file_ref:
            file_ref["file_id"] = "<training-file-id>"
    if redacted.get("validation_files"):
        redacted["validation_files"] = ["<validation-file-id>"]
    return redacted


def list_models(client: httpx.Client) -> list[dict[str, Any]]:
    resp = client.get(f"{_API_BASE}/v1/models", headers=_headers())
    print(f"GET /v1/models -> {resp.status_code}")
    resp.raise_for_status()
    body = resp.json()
    models = body.get("data", body if isinstance(body, list) else [])
    if not isinstance(models, list):
        raise RuntimeError(f"Unexpected /v1/models response shape: {type(body).__name__}")

    fine_tunable = [
        m for m in models
        if isinstance(m, dict) and _fine_tuning_flag(m) and _model_type(m) in ("", "base")
    ]
    print("\nFine-tuning=true base models returned by /v1/models:")
    for model in fine_tunable:
        caps = model.get("capabilities") if isinstance(model.get("capabilities"), dict) else {}
        print(json.dumps({
            "id": _model_id(model),
            "type": _model_type(model),
            "deprecated": not _not_deprecated(model),
            "fine_tuning": model.get("fine_tuning", caps.get("fine_tuning")),
            "capabilities": caps,
        }, sort_keys=True))
    return fine_tunable


def create_job(
    client: httpx.Client,
    *,
    model: str,
    train_file_id: str,
    validation_file_id: str | None,
    job_type: str | None,
) -> None:
    payload: dict[str, Any] = {
        "model": model,
        "training_files": [{"file_id": train_file_id, "weight": 1}],
        "hyperparameters": {"training_steps": 10, "learning_rate": 0.0001},
        # Keep this false so a fixed provider config creates a queued job, not a running one.
        "auto_start": False,
    }
    if validation_file_id:
        payload["validation_files"] = [validation_file_id]
    if job_type:
        payload["job_type"] = job_type

    print("\nPOST /v1/fine_tuning/jobs payload (redacted):")
    print(json.dumps(_redact_payload(payload), indent=2, sort_keys=True))
    resp = client.post(f"{_API_BASE}/v1/fine_tuning/jobs", headers=_headers(), json=payload)
    print(f"\nPOST /v1/fine_tuning/jobs -> {resp.status_code}")
    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    print(json.dumps(body, indent=2, sort_keys=True) if isinstance(body, dict) else body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=_DEFAULT_MISTRAL_BASE)
    parser.add_argument("--attempt-create", action="store_true")
    parser.add_argument("--train-file-id")
    parser.add_argument("--validation-file-id")
    parser.add_argument("--job-type", choices=("completion", "classifier"))
    args = parser.parse_args()

    with httpx.Client(timeout=30) as client:
        list_models(client)
        if not args.attempt_create:
            print(
                "\nNo job create attempted. "
                "Add --attempt-create --train-file-id <id> to reproduce 422."
            )
            return
        if not args.train_file_id:
            raise RuntimeError("--train-file-id is required with --attempt-create")
        create_job(
            client,
            model=args.model,
            train_file_id=args.train_file_id,
            validation_file_id=args.validation_file_id,
            job_type=args.job_type,
        )


if __name__ == "__main__":
    main()
