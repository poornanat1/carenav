import type { Citation } from './types';

export type CitationSource = {
  key: string;
  citation: Citation;
  chunkIds: string[];
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
    const existing = bySource.get(key);
    if (existing) {
      existing.chunkIds.push(citation.chunk_id);
    } else {
      bySource.set(key, { key, citation, chunkIds: [citation.chunk_id] });
    }
  }
  return Array.from(bySource.values());
}

export function citationRefMap(citations: Citation[]) {
  const refs = new Map<string, { citation: Citation; index: number }>();
  const sourceIndexes = new Map<string, number>();
  groupCitations(citations).forEach((source, index) => sourceIndexes.set(source.key, index + 1));
  citations.forEach(citation => {
    refs.set(citation.chunk_id, {
      citation,
      index: sourceIndexes.get(citationSourceKey(citation)) ?? 1,
    });
  });
  return refs;
}

export function citationTooltip(citation: Citation | undefined, index: number) {
  if (!citation) return `Source ${index}`;
  const heading = `${sourceLabel(citation)}\n${citation.chunk_id}`;
  return citation.excerpt ? `${heading}\n\n${citation.excerpt}` : heading;
}
