"""ModelGateway — the ONLY place a provider SDK is imported (docs/02, docs/06).

Everything that talks to a model goes through here: text generation and embeddings.
This centralizes (a) the provider-agnostic call interface, (b) per-call token + cost
capture, (c) outbound-prompt capture for the PII-leak gate, and (d) a timeout with a
graceful failure posture. The tiering/escalation policy itself lives in the
orchestrator; the gateway just executes a call at a requested model and records cost.

Backends:
  * **Mistral** via an API key (MISTRAL_API_KEY) — the real path, for both generation
    and embeddings (`mistral-embed`, 1024-dim).
  * **Offline stub** when no Mistral key is configured — deterministic canned output so
    the agent, tests, and CI run with no key and no network. The stub is obvious
    (it echoes a fixed grounded sentence citing the first provided chunk id) so it is
    never mistaken for a real answer.

No application code outside this package may import mistralai / any provider SDK.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from carenav.config import settings


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

# Per-million-token USD prices for cost capture. Keyed by model; unlisted models fall
# back to _DEFAULT_PRICE. Approximate public Mistral pricing — update as it changes.
_PRICES: dict[str, tuple[float, float]] = {  # model -> (input_per_mtok, output_per_mtok)
    "mistral-small-latest": (0.10, 0.30),
    "mistral-large-latest": (2.00, 6.00),
    "mistral-embed": (0.10, 0.0),
}
_DEFAULT_PRICE = (0.10, 0.30)


def _price_for(model: str) -> tuple[float, float]:
    return _PRICES.get(model, _DEFAULT_PRICE)


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
    backend: str  # "mistral-apikey" | "stub"


@dataclass
class GenerateResult:
    text: str
    call: ModelCall


@dataclass
class CostLedger:
    """Accumulates every call's cost so totals accrue across a turn / a milestone."""

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
            from mistralai.client import Mistral

            self._client = Mistral(api_key=settings.mistral_api_key)
        return self._client

    def using_real_models(self) -> bool:
        """Whether a real Mistral backend is configured (used for embeddings)."""
        return _real_backend_name() is not None

    def backend_name(self) -> str:
        return _real_backend_name() or "stub"

    def _generation_backend(self) -> str:
        """Generation can be stubbed independently of embeddings (settings.stub_generation
        or no credential), e.g. when a key has embedding quota but no generate quota."""
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

    # --- embeddings -----------------------------------------------------------

    def embed(self, texts: list[str], *, task_type: str) -> list[list[float]]:
        """Embed texts at the configured embedding model.

        Returns vectors; records one ModelCall for the batch. Raises if no real backend
        is configured (the RAG layer owns the offline fallback, not the gateway).

        `task_type` (RETRIEVAL_DOCUMENT vs RETRIEVAL_QUERY) is accepted for caller
        compatibility but is a no-op: `mistral-embed` is a single symmetric model with a
        fixed 1024-dim output (no asymmetric task types, no dimension truncation).
        """
        if not texts:
            return []
        if not self.using_real_models():
            raise RuntimeError("ModelGateway.embed called with no Mistral backend configured")

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


# --- offline stub backend ------------------------------------------------------------

# The stub must satisfy the grounding contract so the agent runs end-to-end without a
# real model: it echoes the first sentence of the first cited source block and appends
# that chunk's citation. Because it reuses the source's own words, it passes the
# claim-level entailment check — a faithful stand-in for a grounded model answer.
def _stub_generate(prompt: str) -> tuple[str, int, int]:
    import re

    m = re.search(r"\[CHUNK:([^\]]+)\]\s*\([^)]*\)\s*\n(.+)", prompt)
    if m:
        chunk_id, body = m.group(1), m.group(2)
        first_sentence = re.split(r"(?<=[.!?])\s+", body.strip())[0]
        text = f"{first_sentence} [CHUNK:{chunk_id}]"
    else:
        text = "The sources do not contain information to answer that."
    in_tok = max(1, len(prompt) // 4)
    out_tok = max(1, len(text) // 4)
    return text, in_tok, out_tok
