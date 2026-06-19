import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { getKbDoc, type KbDoc } from './api';
import { renderMarkdown } from './markdown';

// Modal that fetches an internal KB doc by id and renders its markdown in-app, so
// citations for synthetic/internal docs (the CareNav SBC plans, coverage explainers)
// show the actual content instead of linking out.
export function KbDocViewer({ docId, onClose }: { docId: string; onClose: () => void }) {
  const [doc, setDoc] = useState<KbDoc | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setDoc(null);
    setError(false);
    getKbDoc(docId)
      .then(d => {
        if (!cancelled) setDoc(d);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [docId]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex',
        alignItems: 'center', justifyContent: 'center', padding: 24, zIndex: 50,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--cn-bg)', border: '1px solid var(--cn-border)', borderRadius: 12,
          maxWidth: 760, width: '100%', maxHeight: '85vh', display: 'flex', flexDirection: 'column',
          boxShadow: '0 12px 40px rgba(0,0,0,0.25)',
        }}
      >
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 18px', borderBottom: '1px solid var(--cn-border-soft)',
        }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)' }}>
              {doc?.title ?? 'Internal document'}
            </div>
            <div style={{ fontSize: 10, color: 'var(--cn-muted)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
              {docId}{doc?.last_reviewed ? ` · reviewed ${doc.last_reviewed}` : ''}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'none', border: 'none', cursor: 'pointer', color: 'var(--cn-muted)',
              display: 'flex', padding: 4,
            }}
          >
            <X size={16} />
          </button>
        </div>
        <div style={{ overflowY: 'auto', padding: '16px 20px', fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--cn-text)', lineHeight: 1.6 }}>
          {error ? (
            <p style={{ color: 'var(--cn-muted)' }}>Could not load this document.</p>
          ) : doc ? (
            renderMarkdown(doc.body)
          ) : (
            <p style={{ color: 'var(--cn-muted)' }}>Loading…</p>
          )}
        </div>
      </div>
    </div>
  );
}
