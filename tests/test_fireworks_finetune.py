from carenav.config import settings
from carenav.redaction.training import finetune


class _Resp:
    status_code = 200

    def __init__(self, body):
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


class _Client:
    def __init__(self):
        self.posts = []

    def post(self, url, *, headers, json=None, files=None):
        self.posts.append({"url": url, "headers": headers, "json": json, "files": files})
        return _Resp({"name": "accounts/acct/supervisedFineTuningJobs/job-1"})


def test_fireworks_sft_job_payload_is_sparse(monkeypatch):
    monkeypatch.setattr(settings, "fireworks_api_key", "fw-test")
    monkeypatch.setattr(
        settings, "pii_base_model", "accounts/fireworks/models/llama-v3p1-8b-instruct"
    )
    monkeypatch.setattr(settings, "pii_output_model", "carenav-pii-detector")
    monkeypatch.setattr(settings, "pii_train_epochs", 1)
    monkeypatch.setattr(settings, "pii_learning_rate", None)
    monkeypatch.setattr(settings, "pii_lora_rank", 8)

    client = _Client()
    finetune._create_fireworks_sft_job(
        client,
        account_id="acct",
        train_dataset="accounts/acct/datasets/train",
        eval_dataset="accounts/acct/datasets/eval",
        suffix="20260613010101",
    )

    payload = client.posts[0]["json"]
    assert payload == {
        "dataset": "accounts/acct/datasets/train",
        "evaluationDataset": "accounts/acct/datasets/eval",
        "displayName": "CareNav PII detector",
        "baseModel": "accounts/fireworks/models/llama-v3p1-8b-instruct",
        "outputModel": "accounts/acct/models/carenav-pii-detector-20260613010101",
        "epochs": 1,
        "loraRank": 8,
    }


def test_sft_target_uses_copied_entity_text():
    ex = {
        "text": "Patient Jordan Reyes was born 3/4/1980.",
        "spans": [
            {"start": 8, "end": 20, "label": "NAME"},
            {"start": 30, "end": 38, "label": "DOB"},
        ],
    }

    assert finetune._target_entities(ex) == [
        {"text": "Jordan Reyes", "label": "NAME"},
        {"text": "3/4/1980", "label": "DOB"},
    ]
