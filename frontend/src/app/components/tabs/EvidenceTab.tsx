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

  const actionStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0,
    fontSize: 11, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 500,
    textDecoration: 'none', cursor: 'pointer', background: 'none',
    padding: '3px 8px', borderRadius: 5, border: '1px solid var(--cn-border)', transition: 'color 0.15s',
  };

  return (
    <div style={tabBodyStyle}>
      <div style={{ fontSize: 13, fontFamily: 'var(--font-sans)', fontWeight: 600, color: 'var(--cn-ink)', marginBottom: 10 }}>
        Sources{' '}
        <span style={{ fontWeight: 400, color: 'var(--cn-muted)' }}>
          · {sources.length} cited in the latest answer
        </span>
      </div>
      {sources.map((source, i) => {
        const cit = source.citation;
        return (
        // Chunk ids are retrieval internals; keep them reachable on hover, not in the layout.
        <div key={source.key} title={source.chunkIds.join(', ')} style={{ background: 'var(--cn-card-strong)', border: '1px solid var(--cn-border-soft)', borderRadius: 8, padding: '12px 13px', marginBottom: 8, boxShadow: 'var(--cn-shadow)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9 }}>
            <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'var(--cn-accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>
              <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--cn-accent-strong)', fontWeight: 600 }}>{i + 1}</span>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, color: 'var(--cn-ink)', fontFamily: 'var(--font-sans)', fontWeight: 600, lineHeight: 1.4 }}>{sourceLabel(cit)}</div>
              <div style={{ fontSize: 11, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, marginTop: 2 }}>{sourceKind(cit)}</div>
            </div>
            {cit.source_url ? (
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
            ) : null}
          </div>
        </div>
        );
      })}
      {openDocId && <KbDocViewer docId={openDocId} onClose={() => setOpenDocId(null)} />}
    </div>
  );
}
