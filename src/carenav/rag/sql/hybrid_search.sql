-- hybrid_search — CareNav's KB retrieval, consolidated as ONE Postgres function.
--
-- The whole retrieval policy lives here as a CTE pipeline (carenav/rag/retrieval.py is a
-- thin caller). CareNav is Postgres-only — this function IS the retrieval path:
--
--   candidates    — pgvector ANN: top (k * pool_factor) chunks by cosine similarity,
--                   filtered to the intent's allowed source_types. The pool is wider than
--                   k so the lexical term can PROMOTE rows the vector ranking put just
--                   outside the top-k (e.g. the "Silver plan" SBC for a Silver question).
--   scored        — hybrid score: cosine similarity + lex_weight * ts_rank over
--                   title/section/text. Embeddings blur named entities (Gold vs Silver,
--                   drug names); the lexical term re-anchors them.
--   top_k         — best k by hybrid score.
--   top_score     — the leader's score.
--   relevant_docs — doc-level relevance prune: keep docs whose BEST chunk is within
--                   relevance_margin (a relative fraction) of the leader. A doc that only
--                   appears well below the leader is an off-subject intruder (another
--                   drug's similarly-worded side-effects section) and is dropped whole,
--                   so the generator is never handed chunks it might mis-attribute.
--
-- Installed idempotently by carenav.data.db.init_schema(); safe to re-run.

-- Weighted document vector: title (A) ≫ section (B) ≫ body (D). ts_rank's default
-- weights are {D=0.1, C=0.2, B=0.4, A=1.0}, so a named entity matching the TITLE
-- ("CareNav Silver — …", "Metformin — …") outranks generic body-term frequency
-- ("plan", "covered", "emergency") that sibling docs share.
CREATE INDEX IF NOT EXISTS kb_chunk_fts_idx ON kb_chunk USING gin ((
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(section_path, '')), 'B') ||
    setweight(to_tsvector('english', text), 'D')
));

CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding  vector,
    query_text       text,
    filter_types     text[],   -- NULL => search every source_type
    k                int,
    relevance_margin float8,   -- relative fraction below the top hybrid score; <=0 disables
    lex_weight       float8    -- weight of the ts_rank term; 0 = pure vector
) RETURNS TABLE (
    chunk_id      text,
    doc_id        text,
    source_type   text,
    title         text,
    source_url    text,
    last_reviewed text,
    section_path  text,
    text          text,
    score         float8
)
LANGUAGE sql STABLE AS $$
WITH candidates AS (
    SELECT c.chunk_id, c.doc_id, c.source_type, c.title, c.source_url,
           c.last_reviewed, c.section_path, c.text,
           1 - (c.embedding <=> query_embedding) AS vec_score,
           ts_rank(
               setweight(to_tsvector('english', coalesce(c.title, '')), 'A') ||
               setweight(to_tsvector('english', coalesce(c.section_path, '')), 'B') ||
               setweight(to_tsvector('english', c.text), 'D'),
               websearch_to_tsquery('english', query_text)
           ) AS lex_score
    FROM kb_chunk c
    WHERE filter_types IS NULL OR c.source_type = ANY(filter_types)
    ORDER BY c.embedding <=> query_embedding
    LIMIT k * 3
),
scored AS (
    SELECT *, vec_score + lex_weight * lex_score AS hybrid
    FROM candidates
),
top_k AS (
    SELECT * FROM scored ORDER BY hybrid DESC LIMIT k
),
top_score AS (
    SELECT max(hybrid) AS top FROM top_k
),
relevant_docs AS (
    SELECT DISTINCT t.doc_id
    FROM top_k t CROSS JOIN top_score s
    WHERE relevance_margin <= 0 OR t.hybrid >= s.top * (1 - relevance_margin)
)
SELECT t.chunk_id, t.doc_id, t.source_type, t.title, t.source_url,
       t.last_reviewed, t.section_path, t.text, t.hybrid AS score
FROM top_k t
JOIN relevant_docs USING (doc_id)
ORDER BY t.hybrid DESC
$$;
