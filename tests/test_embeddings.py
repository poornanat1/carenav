"""Embedding tests — real Mistral (skipped without a MISTRAL_API_KEY)."""

import math

from carenav.config import settings
from carenav.rag import embeddings
from tests.conftest import requires_mistral


@requires_mistral
def test_embedding_dim_matches_column():
    v = embeddings.embed_query("metformin side effects")
    assert len(v) == settings.embedding_dim  # mistral-embed native 1024-dim == column width


@requires_mistral
def test_query_and_doc_share_space():
    # A query and a topically-matching document should be more similar than an unrelated
    # one (mistral-embed is symmetric — both land in the same space).
    def cos(x, y):
        dot = sum(a * b for a, b in zip(x, y, strict=True))
        nx = math.sqrt(sum(a * a for a in x))
        ny = math.sqrt(sum(b * b for b in y))
        return dot / (nx * ny) if nx and ny else 0.0

    q = embeddings.embed_query("side effects of metformin for diabetes")
    near = embeddings.embed_texts(["Metformin can cause gastrointestinal side effects."])[0]
    far = embeddings.embed_texts(["The plan deductible and out-of-pocket limit reset yearly."])[0]
    assert cos(q, near) > cos(q, far)


def test_empty_batch_needs_no_call():
    assert embeddings.embed_texts([]) == []
