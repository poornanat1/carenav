import { useState } from 'react';
import { ExternalLink, FileText, BookOpen } from 'lucide-react';
import type { TurnResponse } from '../types';
import { citationDocId, groupCitations, isInternalDoc, sourceKind, sourceLabel } from '../citations';
import { KbDocViewer } from '../KbDocViewer';
import { Label, tabBodyStyle } from './shared';

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

  return (
    <div style={tabBodyStyle}>
      <Label>{sources.length} source{sources.length !== 1 ? 's' : ''} · latest answer</Label>
      {sources.map((source, i) => {
        const cit = source.citation;
        return (
        <div key={source.key} style={{ background: 'var(--cn-card)', border: '1px solid var(--cn-border-soft)', borderRadius: 8, padding: '11px 12px', marginBottom: 7 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
            <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'var(--cn-accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>
              <span style={{ fontSize: 8, fontFamily: 'var(--font-mono)', color: 'var(--cn-accent-strong)', fontWeight: 500 }}>{i + 1}</span>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', fontWeight: 500, lineHeight: 1.4 }}>{sourceLabel(cit)}</div>
              <div style={{ fontSize: 10, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, marginTop: 2 }}>{sourceKind(cit)}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--cn-subtle)', marginTop: 4 }}>{source.chunkIds.join(', ')}</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'var(--cn-accent-soft)', border: '1px solid rgba(31,122,90,0.2)', borderRadius: 4, padding: '2px 7px' }}>
              <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--cn-accent)' }} />
              <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--cn-accent-strong)' }}>used in latest answer</span>
            </div>
            {cit.source_url ? (
              <a href={cit.source_url} target="_blank" rel="noopener noreferrer"
                style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, color: 'var(--cn-muted)', fontFamily: 'var(--font-mono)', textDecoration: 'none', padding: '2px 7px', borderRadius: 4, border: '1px solid var(--cn-border)', transition: 'color 0.15s' }}
                onMouseEnter={e => (e.currentTarget.style.color = 'var(--cn-ink)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'var(--cn-muted)')}
              >
                <ExternalLink size={9} /> source
              </a>
            ) : isInternalDoc(cit) ? (
              <button
                onClick={() => setOpenDocId(citationDocId(cit))}
                style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, color: 'var(--cn-muted)', fontFamily: 'var(--font-mono)', cursor: 'pointer', background: 'none', padding: '2px 7px', borderRadius: 4, border: '1px solid var(--cn-border)', transition: 'color 0.15s' }}
                onMouseEnter={e => (e.currentTarget.style.color = 'var(--cn-ink)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'var(--cn-muted)')}
              >
                <BookOpen size={9} /> view doc
              </button>
            ) : (
              <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--cn-subtle)' }}>internal</span>
            )}
          </div>
        </div>
        );
      })}
      {openDocId && <KbDocViewer docId={openDocId} onClose={() => setOpenDocId(null)} />}
    </div>
  );
}
