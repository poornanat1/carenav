"""ModelGateway — the ONLY place a provider SDK is imported (docs/02, docs/06).

Everything that talks to a model goes through here: text generation and embeddings.
This centralizes (a) the provider-agnostic call interface, (b) per-call token + cost
capture, (c) outbound-prompt capture for the PII-leak gate, and (d) a timeout with a
graceful failure posture. The tiering/escalation policy itself lives in the
orchestrator; the gateway just executes a call at a requested model and records cost.

Backends:
  * **Fireworks** via FIREWORKS_API_KEY — default generation path and deployed PII LoRA
    inference.
  * **Mistral** via MISTRAL_API_KEY — embeddings (`mistral-embed`, 1024-dim) and an
    optional generation fallback.
  * **Offline stub** when no generation key is configured — deterministic canned output
    so the agent, tests, and CI run with no generation spend. The stub is obvious (it
    echoes a fixed grounded sentence citing the first provided chunk id) so it is never
    mistaken for a real answer.

No application code outside this package may import mistralai / any provider SDK.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from carenav.config import settings

logger = logging.getLogger(__name__)


class TransientModelError(RuntimeError):
    """A retryable provider error. Carries the HTTP status so _is_transient can inspect it."""

    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


def _is_transient(exc: BaseException) -> bool:
    """Retry on rate-limit / transient server errors, not on auth/not-found/bad-request."""
    code = getattr(exc, "code", None)
    # 429 rate limit; 500/503 server error; 504 gateway timeout — all worth retrying.
    return code in (429, 500, 503, 504)


# Bounded exponential backoff for rate limits (docs/06: "retries with backoff").
_retry_transient = retry(
    retry=retry_if_exception(_is_transient),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    stop=stop_after_attempt(4),
    reraise=True,
)

# Models we've already warned about missing a price entry — warn once, not per call.
_unpriced_warned: set[str] = set()


def _price_for(model: str) -> tuple[float, float]:
    price = settings.model_prices.get(model)
    if price is None:
        if model not in _unpriced_warned:
            logger.warning(
                "No price entry for model %r; cost capture uses model_price_default %s. "
                "Add it to settings.model_prices.",
                model,
                settings.model_price_default,
            )
            _unpriced_warned.add(model)
        return settings.model_price_default
    return price


def _cost_usd(model: str, in_tok: int, out_tok: int) -> float:
    pin, pout = _price_for(model)
    return (in_tok / 1_000_000) * pin + (out_tok / 1_000_000) * pout


@dataclass
class ModelCall:
    """A single recorded model invocation (cost-capture unit)."""

    model: str
    kind: str  # "generate" | "embed"
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    backend: str  # "fireworks-apikey" | "mistral-apikey" | "stub"


@dataclass
class GenerateResult:
    text: str
    call: ModelCall


@dataclass
class CostLedger:
    """Accumulates every call's cost so totals accrue across a turn or eval run."""

    calls: list[ModelCall] = field(default_factory=list)

    def record(self, call: ModelCall) -> ModelCall:
        self.calls.append(call)
        return call

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    def by_model(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for c in self.calls:
            out[c.model] = out.get(c.model, 0.0) + c.cost_usd
        return out


def _real_backend_name() -> str | None:
    if settings.model_provider == "fireworks" and settings.fireworks_api_key:
        return "fireworks-apikey"
    if settings.mistral_api_key:
        return "mistral-apikey"
    return None


class ModelGateway:
    """Provider-agnostic model access with cost capture and prompt capture.

    Construct one per process (or per turn); pass it into the RAG agent / orchestrator.
    `captured_prompts` holds every outbound prompt (already-redacted by the caller) for
    the PII-leak sweep (docs/05); the gateway never redacts — it only records.
    """

    def __init__(self, capture_prompts: bool = True) -> None:
        self.ledger = CostLedger()
        self.capture_prompts = capture_prompts
        self.captured_prompts: list[dict] = []
        self._client = None  # lazy; only built when a real backend is configured

    # --- client ---------------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            try:
                from mistralai import Mistral
            except ImportError:
                from mistralai.client import Mistral

            self._client = Mistral(api_key=settings.mistral_api_key)
        return self._client

    def using_real_models(self) -> bool:
        """Whether any real model backend is configured for generation or PII calls."""
        return _real_backend_name() is not None

    def backend_name(self) -> str:
        return _real_backend_name() or "stub"

    def _generation_backend(self) -> str:
        """Generation can be stubbed independently of embeddings."""
        if settings.stub_generation:
            return "stub"
        return _real_backend_name() or "stub"

    # --- generation -----------------------------------------------------------

    def generate(self, prompt: str, *, model: str | None = None, label: str = "") -> GenerateResult:
        """Generate text at `model` (defaults to the small tier). Records cost."""
        model = model or settings.model_small
        if self.capture_prompts:
            self.captured_prompts.append({"label": label, "model": model, "prompt": prompt})

        backend = self._generation_backend()
        t0 = time.monotonic()
        if backend == "stub":
            text, in_tok, out_tok = _stub_generate(prompt)
        elif backend == "fireworks-apikey":
            text, in_tok, out_tok = self._fireworks_chat(
                messages=[{"role": "user", "content": prompt}],
                model=model,
            )
        else:
            text, in_tok, out_tok = self._mistral_generate(prompt, model)
        latency = time.monotonic() - t0

        call = self.ledger.record(
            ModelCall(
                model=model,
                kind="generate",
                input_tokens=in_tok,
                output_tokens=out_tok,
                # The stub makes no real call — record zero cost so totals stay honest.
                cost_usd=0.0 if backend == "stub" else _cost_usd(model, in_tok, out_tok),
                latency_s=latency,
                backend=backend,
            )
        )
        return GenerateResult(text=text, call=call)

    @_retry_transient
    def _mistral_generate(self, prompt: str, model: str) -> tuple[str, int, int]:
        client = self._get_client()
        resp = client.chat.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            timeout_ms=int(settings.model_request_timeout_s * 1000),
        )
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        in_tok = getattr(usage, "prompt_tokens", 0) or 0
        out_tok = getattr(usage, "completion_tokens", 0) or 0
        return (text, in_tok, out_tok)

    @_retry_transient
    def _fireworks_chat(self, *, messages: list[dict], model: str) -> tuple[str, int, int]:
        if not settings.fireworks_api_key:
            raise RuntimeError("FIREWORKS_API_KEY required for Fireworks model calls")
        payload = {"model": model, "messages": messages}
        try:
            resp = httpx.post(
                f"{settings.fireworks_api_base.rstrip('/')}/inference/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.fireworks_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=settings.model_request_timeout_s,
            )
        except httpx.TimeoutException as exc:
            # A request timeout is transient — surface it as 504 so the backoff retries.
            raise TransientModelError(f"Fireworks chat timed out: {exc}", code=504) from exc
        if resp.status_code >= 400:
            msg = f"Fireworks chat failed ({resp.status_code}): {resp.text[:500]}"
            # Carry the status code so _is_transient decides: 429/5xx retry with backoff;
            # 4xx (auth/bad-request) raises through immediately (not in the transient set).
            raise TransientModelError(msg, code=resp.status_code)
        body = resp.json()
        text = body["choices"][0]["message"].get("content") or ""
        usage = body.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or 0)
        out_tok = int(usage.get("completion_tokens") or 0)
        return (text, in_tok, out_tok)

    # --- PII detection (fine-tuned SFT model) ---------------------------------

    # System instruction for the fine-tuned extractor. The fine-tune teaches the output
    # shape; this frames the task around copying exact substrings instead of counting
    # offsets. Offsets are resolved locally, which is much more reliable.
    _PII_SYSTEM = (
        "You detect personal/health identifiers in the user's message and return ONLY a "
        'JSON array of entities: [{"text": str, "label": str}]. Labels: '
        "NAME, DOB, ADDRESS, PROVIDER_NAME. text must be copied exactly from the user message. "
        "Return [] if none."
    )

    def classify_pii(self, text: str, *, model: str | None = None) -> list[dict] | None:
        """Detect free-text PII spans with the fine-tuned model. Returns raw span dicts.

        Returns ``None`` when the detector is UNAVAILABLE (no model configured, no real
        backend, or the call/parse failed) — the caller MUST treat None as "fall back to
        the spaCy/regex detector", never as "no PII found". An empty list means the model
        ran and found nothing.

        The input is raw PHI by design (the model's whole job is to find PHI in it), so this
        call is NEVER added to ``captured_prompts`` and its text is never logged. Cost is
        still recorded in the ledger (token counts only, no content).
        """
        model = model or settings.pii_model
        if model is None or not self.using_real_models():
            return None  # not configured / offline → caller falls back to spaCy+regex
        try:
            if self.backend_name() == "fireworks-apikey":
                spans, in_tok, out_tok, latency = self._fireworks_classify_pii(text, model)
            else:
                spans, in_tok, out_tok, latency = self._mistral_classify_pii(text, model)
        except _PII_DETECTOR_UNAVAILABLE as exc:
            # Fail safe: a network/HTTP/parse failure means the detector is unavailable, so
            # the caller falls back to spaCy+regex — never "no PII found". A programming
            # error (e.g. a bug in span resolution) is NOT in this set and propagates loudly
            # so it can't masquerade as graceful degradation of a PHI gate.
            logger.warning("PII classifier unavailable (%s): %s", type(exc).__name__, exc)
            return None
        self.ledger.record(
            ModelCall(
                model=model,
                kind="classify_pii",
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=_cost_usd(model, in_tok, out_tok),
                latency_s=latency,
                backend=self.backend_name(),
            )
        )
        return spans

    @_retry_transient
    def _mistral_classify_pii(self, text: str, model: str) -> tuple[list[dict], int, int, float]:
        client = self._get_client()
        t0 = time.monotonic()
        resp = client.chat.complete(
            model=model,
            messages=[
                {"role": "system", "content": self._PII_SYSTEM},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            timeout_ms=int(settings.model_request_timeout_s * 1000),
        )
        latency = time.monotonic() - t0
        raw = resp.choices[0].message.content or "[]"
        spans = _parse_pii_spans(raw, text)
        usage = getattr(resp, "usage", None)
        in_tok = getattr(usage, "prompt_tokens", 0) or 0
        out_tok = getattr(usage, "completion_tokens", 0) or 0
        return spans, in_tok, out_tok, latency

    @_retry_transient
    def _fireworks_classify_pii(self, text: str, model: str) -> tuple[list[dict], int, int, float]:
        t0 = time.monotonic()
        raw, in_tok, out_tok = self._fireworks_chat(
            model=model,
            messages=[
                {"role": "system", "content": self._PII_SYSTEM},
                {"role": "user", "content": text},
            ],
        )
        latency = time.monotonic() - t0
        spans = _parse_pii_spans(raw or "[]", text)
        return spans, in_tok, out_tok, latency

    # --- embeddings -----------------------------------------------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts at the configured embedding model (`mistral-embed`, 1024-dim).

        Returns vectors; records one ModelCall for the batch. Embeddings are always real:
        `mistral-embed` is symmetric (documents and queries embed identically), so there is
        no document/query task-type distinction. Raises if no Mistral key is configured —
        embeddings require Mistral regardless of the generation provider (docs/06).
        """
        if not texts:
            return []
        if not settings.mistral_api_key:
            raise RuntimeError(
                "Embeddings require MISTRAL_API_KEY (mistral-embed), independent of "
                "MODEL_PROVIDER. Set MISTRAL_API_KEY to run retrieval/ingest."
            )

        t0 = time.monotonic()
        out = self._mistral_embed(texts)
        latency = time.monotonic() - t0

        # Embedding token usage isn't always reported; approximate from characters.
        approx_tok = sum(len(t) for t in texts) // 4
        self.ledger.record(
            ModelCall(
                model=settings.embedding_model,
                kind="embed",
                input_tokens=approx_tok,
                output_tokens=0,
                cost_usd=_cost_usd(settings.embedding_model, approx_tok, 0),
                latency_s=latency,
                backend=self.backend_name(),
            )
        )
        return out

    # Mistral caps the number of inputs per embeddings request; batch to stay under it.
    _EMBED_BATCH = 64

    def _mistral_embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), self._EMBED_BATCH):
            out.extend(self._mistral_embed_batch(texts[start:start + self._EMBED_BATCH]))
        return out

    @_retry_transient
    def _mistral_embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = self._get_client().embeddings.create(
            model=settings.embedding_model, inputs=texts
        )
        return [list(d.embedding) for d in resp.data]


# --- PII span parsing ----------------------------------------------------------------

def _provider_error_types() -> tuple[type[BaseException], ...]:
    """Provider-SDK error base(s), resolved lazily so the SDK stays import-isolated here.

    The Mistral SDK raises its own ``MistralError`` (e.g. a 400 invalid-model / auth error);
    those mean the detector is unavailable and must fail safe, not crash the request.
    """
    try:
        from mistralai.models.sdkerror import SDKError as MistralError
    except ImportError:
        try:
            from mistralai.client.errors.sdkerror import MistralError
        except ImportError:
            return ()
    return (MistralError,)


# Exceptions that mean "the PII detector could not produce a result" (network down, HTTP
# error, provider SDK error, malformed/garbage model output). classify_pii catches THESE and
# fails safe to the spaCy+regex fallback. Anything outside this set (e.g. an AttributeError
# from a real bug in span resolution) propagates so a code defect can't silently disable the
# gate.
_PII_DETECTOR_UNAVAILABLE = (
    httpx.HTTPError,
    TransientModelError,
    json.JSONDecodeError,
    ConnectionError,
    TimeoutError,
    *_provider_error_types(),
)

_PII_LABELS = frozenset({"NAME", "DOB", "ADDRESS", "PROVIDER_NAME"})


def _parse_pii_spans(raw: str, text: str | int) -> list[dict]:
    """Parse + validate fine-tuned model output into character spans.

    The current model contract is ``{"text", "label"}``: models copy substrings, while
    application code resolves offsets. For compatibility with older models/tests, legacy
    ``{"start", "end", "label"}`` spans are still accepted when valid.

    Accepts a bare array or an object wrapper using ``entities``/``spans``. Invalid entries
    are dropped rather than trusted. Raises on totally unparseable JSON so the caller's
    try/except treats it as detector-unavailable (fail safe, not "no PII").
    """
    source_text = "" if isinstance(text, int) else text
    text_len = text if isinstance(text, int) else len(text)
    data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get("entities", data.get("spans", []))
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    search_from: dict[tuple[str, str], int] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", ""))
        if label not in _PII_LABELS:
            continue

        if "text" in item and source_text:
            entity_text = str(item.get("text") or "").strip()
            resolved = _resolve_entity_text(source_text, entity_text, label, search_from)
            if resolved is not None:
                start, end = resolved
                out.append({"start": start, "end": end, "label": label})
            continue

        try:
            start, end = int(item["start"]), int(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= start < end <= text_len:
            out.append({"start": start, "end": end, "label": label})
    return out


def _resolve_entity_text(
    source_text: str,
    entity_text: str,
    label: str,
    search_from: dict[tuple[str, str], int],
) -> tuple[int, int] | None:
    """Map a copied entity string back to the next matching span in source_text."""
    if not entity_text:
        return None
    key = (label, entity_text.casefold())
    start_at = search_from.get(key, 0)
    start = source_text.find(entity_text, start_at)
    if start == -1:
        start = source_text.casefold().find(entity_text.casefold(), start_at)
    if start == -1:
        return None
    end = start + len(entity_text)
    search_from[key] = end
    return start, end


# --- offline stub backend ------------------------------------------------------------

# Parses the first source block emitted by rag.prompts._format_sources, whose layout is
# "[CHUNK:<id>] (source: ...)\n<body>". gateway sits below rag in the layering, so the
# format is duplicated here rather than imported; if _format_sources changes, update this.
_STUB_SOURCE_RE = re.compile(r"\[CHUNK:([^\]]+)\]\s*\([^)]*\)\s*\n(.+)")


# The stub must satisfy the grounding contract so the agent runs end-to-end without a
# real model: it echoes the first sentence of the first cited source block and appends
# that chunk's citation. Because it reuses the source's own words, it passes the
# claim-level entailment check — a faithful stand-in for a grounded model answer.
def _stub_generate(prompt: str) -> tuple[str, int, int]:
    m = _STUB_SOURCE_RE.search(prompt)
    if m:
        chunk_id, body = m.group(1), m.group(2)
        first_sentence = re.split(r"(?<=[.!?])\s+", body.strip())[0]
        text = f"{first_sentence} [CHUNK:{chunk_id}]"
    else:
        text = "The sources do not contain information to answer that."
    in_tok = max(1, len(prompt) // 4)
    out_tok = max(1, len(text) // 4)
    return text, in_tok, out_tok
