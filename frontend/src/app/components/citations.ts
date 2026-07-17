import type { Citation } from './types';

export type CitationSource = {
  key: string;
  citation: Citation;
  chunkIds: string[];
  // Distinct excerpts across every chunk grouped under this source, in citation order.
  // A source cited from several passages contributes one excerpt per passage.
  excerpts: string[];
};

export function sourceLabel(citation: Citation) {
  const id = citation.chunk_id.toLowerCase();
  if (id === 'tool:member_profile') return 'Profile';
  if (id.startsWith('openfda-')) return citation.title.replace(/\s+—\s+Drug Label$/, ' label');
  if (id.startsWith('mplus-')) return citation.title;
  if (id.startsWith('tool:')) return citation.title;
  return citation.title;
}

export function sourceKind(citation: Citation) {
  const id = citation.chunk_id.toLowerCase();
  if (id === 'tool:member_profile') return 'selected member';
  if (id.startsWith('openfda-')) return 'drug label';
  if (id.startsWith('mplus-')) return 'health article';
  if (id.startsWith('tool:')) return 'internal source';
  return 'knowledge base';
}

// KB chunk ids are "{doc_id}::{ordinal}". Tool/profile citations (e.g. "tool:provider:..")
// are not KB docs and have no renderable markdown.
export function citationDocId(citation: Citation): string | null {
  const id = citation.chunk_id;
  if (id.startsWith('tool:')) return null;
  const sep = id.indexOf('::');
  return sep > 0 ? id.slice(0, sep) : null;
}

// An internal doc we render in-app: it has a KB doc id and no external source_url.
export function isInternalDoc(citation: Citation): boolean {
  return !citation.source_url && citationDocId(citation) !== null;
}

export function citationSourceKey(citation: Citation) {
  if (!citation.source_url) return `chunk:${citation.chunk_id}`;
  return `source:${citation.source_url}::${citation.title}`;
}

export function groupCitations(citations: Citation[]) {
  const bySource = new Map<string, CitationSource>();
  for (const citation of citations) {
    const key = citationSourceKey(citation);
    const excerpt = citation.excerpt?.trim();
    const existing = bySource.get(key);
    if (existing) {
      existing.chunkIds.push(citation.chunk_id);
      // Dedupe: the same passage can be cited more than once — show it only once.
      if (excerpt && !existing.excerpts.includes(excerpt)) existing.excerpts.push(excerpt);
    } else {
      bySource.set(key, {
        key,
        citation,
        chunkIds: [citation.chunk_id],
        excerpts: excerpt ? [excerpt] : [],
      });
    }
  }
  return Array.from(bySource.values());
}

// A citation reference resolves to a source ("1") and, when that source is cited from
// more than one passage, the specific passage within it ("1-2"). Passage index is the
// 1-based position of this chunk's excerpt in the grouped source's deduped excerpts, so
// the inline marker points at the exact paragraph shown in the Evidence panel.
export type CitationRef = {
  citation: Citation;
  sourceIndex: number;
  passageIndex: number; // 1-based; 0 when the source has no distinct passages
  label: string;        // "1", or "1-2" when the source is multi-passage
};

export function citationRefMap(citations: Citation[]): Map<string, CitationRef> {
  const refs = new Map<string, CitationRef>();
  const sources = groupCitations(citations);
  const byKey = new Map(sources.map((s, i) => [s.key, { source: s, index: i + 1 }]));
  citations.forEach(citation => {
    const entry = byKey.get(citationSourceKey(citation));
    const sourceIndex = entry?.index ?? 1;
    const excerpt = citation.excerpt?.trim();
    // Multi-passage sources get a passage suffix; single-passage sources stay "1".
    const multi = (entry?.source.excerpts.length ?? 0) > 1;
    const passageIndex = multi && excerpt ? entry!.source.excerpts.indexOf(excerpt) + 1 : 0;
    const label = passageIndex > 0 ? `${sourceIndex}-${passageIndex}` : `${sourceIndex}`;
    refs.set(citation.chunk_id, { citation, sourceIndex, passageIndex, label });
  });
  return refs;
}

export function citationTooltip(citation: Citation | undefined, label: string) {
  if (!citation) return `Source ${label}`;
  const heading = `${label} · ${sourceLabel(citation)}\n${citation.chunk_id}`;
  return citation.excerpt ? `${heading}\n\n${citation.excerpt}` : heading;
}
