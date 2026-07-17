import React, { useState } from 'react';
import { ExternalLink, FileText, BookOpen } from 'lucide-react';
import type { TurnResponse } from '../types';
import { citationDocId, groupCitations, isInternalDoc, sourceKind, sourceLabel } from '../citations';
import { KbDocViewer } from '../KbDocViewer';
import { tabBodyStyle } from './shared';

export function EvidenceTab({ lastResponse }: { lastResponse: TurnResponse | null }) {
  const [openDocId, setOpenDocId] = useState<string | null>(null);

  if (!lastResponse) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <p style={{ fontSize: 12, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, textAlign: 'center' }}>No response yet. Send a message to see evidence.</p>
    </div>
  );

  if (!lastResponse.grounded) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ textAlign: 'center' }}>
        <FileText size={22} color="var(--cn-subtle)" style={{ margin: '0 auto 8px' }} />
        <p style={{ fontSize: 12, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400 }}>Grounding unavailable or failed.</p>
      </div>
    </div>
  );

  const sources = groupCitations(lastResponse.citations);

  if (sources.length === 0) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <p style={{ fontSize: 12, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, textAlign: 'center' }}>No citations for this response.</p>
    </div>
  );

  // Understated text-link action, no chrome — reads like a byline note in a column.
  const actionStyle: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 4, flexShrink: 0,
    fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase',
    color: 'var(--cn-muted)', fontFamily: 'var(--font-mono)', fontWeight: 500,
    textDecoration: 'none', cursor: 'pointer', background: 'none', border: 'none',
    padding: 0, transition: 'color 0.15s',
  };

  return (
    <div style={tabBodyStyle}>
      {/* Masthead: broadsheet-style top rule + tracked all-caps label. */}
      <div style={{ borderTop: '2px solid var(--cn-ink)', paddingTop: 8, marginBottom: 4 }}>
        <div style={{
          display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
          fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.14em',
          textTransform: 'uppercase', color: 'var(--cn-ink)', fontWeight: 600,
        }}>
          <span>Sources</span>
          <span style={{ color: 'var(--cn-muted)', fontWeight: 400, letterSpacing: '0.1em' }}>
            {sources.length} cited
          </span>
        </div>
        <div style={{ borderBottom: '1px solid var(--cn-border)', marginTop: 8 }} />
      </div>

      {sources.map((source, i) => {
        const cit = source.citation;
        const action = cit.source_url ? (
          <a href={cit.source_url} target="_blank" rel="noopener noreferrer" style={actionStyle}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--cn-ink)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--cn-muted)')}
          >
            <ExternalLink size={10} /> Open
          </a>
        ) : isInternalDoc(cit) ? (
          <button onClick={() => setOpenDocId(citationDocId(cit))} style={actionStyle}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--cn-ink)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--cn-muted)')}
          >
            <BookOpen size={10} /> View
          </button>
        ) : null;

        return (
        // Chunk ids are retrieval internals; keep them reachable on hover, not in the layout.
        // No card box — hairline rules separate entries like columns in a reference page.
        <article key={source.key} title={source.chunkIds.join(', ')} style={{
          padding: '16px 0',
          borderBottom: i < sources.length - 1 ? '1px solid var(--cn-border-soft)' : 'none',
        }}>
          {/* Footnote-style header: 01 · TITLE — KIND, with the action tucked to the right. */}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 500, color: 'var(--cn-accent-strong)', flexShrink: 0 }}>
              {String(i + 1).padStart(2, '0')}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontFamily: 'var(--font-display)', fontSize: 15, fontWeight: 700,
                color: 'var(--cn-ink)', lineHeight: 1.25, letterSpacing: '-0.01em',
              }}>
                {sourceLabel(cit)}
              </div>
              <div style={{
                fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.1em',
                textTransform: 'uppercase', color: 'var(--cn-muted)', fontWeight: 400, marginTop: 4,
              }}>
                {sourceKind(cit)}
              </div>
            </div>
            {action && <div style={{ flexShrink: 0, alignSelf: 'flex-start', marginTop: 3 }}>{action}</div>}
          </div>
          {/* Column body. A single-passage source reads as one paragraph; a multi-passage
              source labels each passage 1-1, 1-2… to match the inline citation markers, so
              the reader can trace a specific marker to its exact paragraph. */}
          {source.excerpts.map((excerpt, j) => {
            const multi = source.excerpts.length > 1;
            return (
              <div key={j} style={{ display: 'flex', gap: 8, margin: j === 0 ? 0 : '12px 0 0' }}>
                {multi && (
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 500,
                    color: 'var(--cn-accent-strong)', flexShrink: 0, marginTop: 3,
                  }}>
                    {i + 1}-{j + 1}
                  </span>
                )}
                <p style={{
                  fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--cn-text)', fontWeight: 400,
                  lineHeight: 1.62, textAlign: 'left', margin: 0, flex: 1, minWidth: 0,
                }}>{excerpt}</p>
              </div>
            );
          })}
        </article>
        );
      })}
      {openDocId && <KbDocViewer docId={openDocId} onClose={() => setOpenDocId(null)} />}
    </div>
  );
}
