"""Fine-tune a Fireworks SFT model to extract free-text PII entities.

Pipeline: reshape the generated corpus (text + gold spans) into OpenAI-style chat JSONL,
upload train/eval datasets to Fireworks, create a supervised fine-tuning job, poll to a
terminal state, and print the fine-tuned model id to set as ``PII_MODEL``.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from carenav.config import settings
from carenav.models.gateway import ModelGateway

_SYSTEM = ModelGateway._PII_SYSTEM
_FW_TERMINAL_STATES = {
    "JOB_STATE_COMPLETED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
    "JOB_STATE_EARLY_STOPPED",
}


def _target_entities(ex: dict) -> list[dict]:
    """Convert gold offsets to the value-copy target the model is trained to emit."""
    text = ex["text"]
    return [
        {"text": text[s["start"]:s["end"]], "label": s["label"]}
        for s in ex["spans"]
    ]


def _to_sft_pairs(corpus_path: str) -> list[dict]:
    """Reshape {"text", "spans"} corpus lines into chat SFT messages."""
    pairs: list[dict] = []
    with open(corpus_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ex = json.loads(line)
            target = json.dumps(_target_entities(ex), ensure_ascii=False)
            pairs.append({
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": ex["text"]},
                    {"role": "assistant", "content": target},
                ]
            })
    return pairs


def _write_sft(pairs: list[dict], path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    return path


def _require_fireworks_key() -> str:
    if not settings.fireworks_api_key:
        raise RuntimeError("FIREWORKS_API_KEY required to fine-tune with Fireworks.")
    return settings.fireworks_api_key


def _headers(*, json_content: bool = True) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {_require_fireworks_key()}"}
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


def _fw_url(path: str) -> str:
    return f"{settings.fireworks_api_base.rstrip('/')}{path}"


def _raise_for_fireworks(resp: httpx.Response, action: str) -> dict[str, Any]:
    try:
        body = resp.json()
    except ValueError:
        body = {"message": resp.text}
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Fireworks {action} failed ({resp.status_code}): {json.dumps(body, sort_keys=True)}"
        )
    return body if isinstance(body, dict) else {"response": body}


def _account_id(client: httpx.Client) -> str:
    configured = settings.fireworks_account_id
    if configured:
        return configured.removeprefix("accounts/")

    resp = client.get(_fw_url("/v1/accounts"), headers=_headers(json_content=False))
    body = _raise_for_fireworks(resp, "account discovery")
    accounts = body.get("accounts", [])
    ready = [
        str(a.get("name", "")).removeprefix("accounts/")
        for a in accounts
        if isinstance(a, dict) and a.get("state") == "READY" and a.get("name")
    ]
    if len(ready) == 1:
        return ready[0]
    if not ready:
        raise RuntimeError("FIREWORKS_ACCOUNT_ID required; no READY Fireworks account was found.")
    raise RuntimeError(
        "FIREWORKS_ACCOUNT_ID required; the API key can access multiple READY accounts."
    )


def _count_jsonl(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _create_upload_validate_dataset(
    client: httpx.Client,
    *,
    account_id: str,
    dataset_id: str,
    path: str,
    display_name: str,
) -> str:
    create_payload = {
        "datasetId": dataset_id,
        "dataset": {
            "displayName": display_name,
            "exampleCount": str(_count_jsonl(path)),
            "userUploaded": {},
            "format": "CHAT",
        },
    }
    base = f"/v1/accounts/{account_id}/datasets"
    create_resp = client.post(_fw_url(base), headers=_headers(), json=create_payload)
    if create_resp.status_code == 409:
        # Reusing the same dataset id is useful while iterating locally.
        pass
    else:
        _raise_for_fireworks(create_resp, f"dataset create {dataset_id}")

    with open(path, "rb") as f:
        upload_resp = client.post(
            _fw_url(f"{base}/{dataset_id}:upload"),
            headers=_headers(json_content=False),
            files={"file": (os.path.basename(path), f, "application/jsonl")},
        )
    _raise_for_fireworks(upload_resp, f"dataset upload {dataset_id}")

    validate_resp = client.post(_fw_url(f"{base}/{dataset_id}:validateUpload"), headers=_headers(), json={})
    if validate_resp.status_code >= 400 and "dataset is already uploaded" not in validate_resp.text:
        _raise_for_fireworks(validate_resp, f"dataset validate {dataset_id}")
    return f"accounts/{account_id}/datasets/{dataset_id}"


def _create_fireworks_sft_job(
    client: httpx.Client,
    *,
    account_id: str,
    train_dataset: str,
    eval_dataset: str,
    suffix: str,
) -> dict[str, Any]:
    output_id = f"{settings.pii_output_model}-{suffix}"
    if settings.pii_output_model.startswith("accounts/"):
        output_model = output_id
    else:
        output_model = f"accounts/{account_id}/models/{output_id}"
    payload: dict[str, Any] = {
        "dataset": train_dataset,
        "evaluationDataset": eval_dataset,
        "displayName": "CareNav PII detector",
        "baseModel": settings.pii_base_model,
        "outputModel": output_model,
        "epochs": settings.pii_train_epochs,
        "loraRank": settings.pii_lora_rank,
    }
    if settings.pii_learning_rate is not None:
        payload["learningRate"] = settings.pii_learning_rate

    resp = client.post(
        _fw_url(f"/v1/accounts/{account_id}/supervisedFineTuningJobs"),
        headers=_headers(),
        json=payload,
    )
    return _raise_for_fireworks(resp, "SFT job create")


def _get_fireworks_sft_job(client: httpx.Client, job_name: str) -> dict[str, Any]:
    resp = client.get(_fw_url(f"/v1/{job_name}"), headers=_headers(json_content=False))
    return _raise_for_fireworks(resp, f"SFT job get {job_name}")


def run(*, poll_seconds: int = 30, max_polls: int = 240) -> dict:
    """Reshape corpus -> Fireworks datasets -> SFT job -> poll -> return job info."""
    if settings.pii_model:
        return {"status": "skipped", "reason": "pii_model already set", "model": settings.pii_model}

    _require_fireworks_key()
    train_corpus = os.path.join(settings.pii_corpus_dir, "train.jsonl")
    eval_corpus = os.path.join(settings.pii_corpus_dir, "eval.jsonl")
    if not (os.path.isfile(train_corpus) and os.path.isfile(eval_corpus)):
        raise RuntimeError(
            f"Corpus not found in {settings.pii_corpus_dir!r}. Generate it first: "
            "`python -m carenav.redaction.training.generate_corpus`."
        )

    train_sft = _write_sft(
        _to_sft_pairs(train_corpus), os.path.join(settings.pii_corpus_dir, "train.fireworks.sft.jsonl")
    )
    eval_sft = _write_sft(
        _to_sft_pairs(eval_corpus), os.path.join(settings.pii_corpus_dir, "eval.fireworks.sft.jsonl")
    )

    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    with httpx.Client(timeout=120) as client:
        account_id = _account_id(client)
        train_dataset = _create_upload_validate_dataset(
            client,
            account_id=account_id,
            dataset_id=f"carenav-pii-train-{suffix}",
            path=train_sft,
            display_name="CareNav PII train",
        )
        eval_dataset = _create_upload_validate_dataset(
            client,
            account_id=account_id,
            dataset_id=f"carenav-pii-eval-{suffix}",
            path=eval_sft,
            display_name="CareNav PII eval",
        )
        job = _create_fireworks_sft_job(
            client,
            account_id=account_id,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            suffix=suffix,
        )
        job_name = str(job.get("name", ""))
        if not job_name:
            raise RuntimeError(f"Unexpected Fireworks SFT response: {job!r}")

        for _ in range(max_polls):
            info = _get_fireworks_sft_job(client, job_name)
            state = str(info.get("state", ""))
            if state in _FW_TERMINAL_STATES:
                return {
                    "status": state,
                    "job_id": job_name,
                    "fine_tuned_model": info.get("outputModel"),
                    "hint": "Set PII_MODEL to the fine_tuned_model value after deployment is ready.",
                }
            time.sleep(poll_seconds)

    return {"status": "TIMEOUT", "job_id": job_name, "hint": "Job still running; poll Fireworks."}


if __name__ == "__main__":
    print(run())
