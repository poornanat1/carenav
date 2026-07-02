import { CheckCircle2, AlertCircle } from 'lucide-react';
import type { Message } from '../types';
import { CitationChips, labelStyle, renderAnswer, severityOf } from './shared';

export function AnswerBubble({ msg }: { msg: Message }) {
  const r = msg.response;
  const isUrgent = r ? severityOf(r) === 'urgent' : false;
  return (
    <div style={{ marginBottom: 22 }}>
      <div style={labelStyle}>CareNav</div>
      <div
        style={{
          background: 'var(--cn-card-strong)',
          border: isUrgent ? '1px solid var(--cn-warn-border)' : '1px solid var(--cn-border)',
          borderRadius: '3px 10px 10px 10px',
          padding: '16px 20px',
          maxWidth: 800,
          boxShadow: 'var(--cn-shadow)',
        }}
      >
        {isUrgent && (
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--cn-warn-soft)', border: '1px solid var(--cn-warn-border)',
              borderRadius: 6, padding: '6px 10px', marginBottom: 11,
              fontSize: 11, color: 'var(--cn-warn)', fontFamily: 'var(--font-sans)', fontWeight: 500,
            }}
          >
            <AlertCircle size={12} /> Time-sensitive — if symptoms are severe or worsening, seek care now.
          </div>
        )}
        <div
          style={{
            fontSize: 15, color: 'var(--cn-ink)',
            fontFamily: 'var(--font-sans)', fontWeight: 400,
            lineHeight: 1.7, whiteSpace: 'pre-wrap',
          }}
        >
          {r ? (
            <>
              {renderAnswer(r.answer, r.citations)}
            </>
          ) : msg.content}
        </div>

        {r && <CitationChips citations={r.citations} />}

        {r && (
          <div
            style={{
              marginTop: 12, paddingTop: 10,
              borderTop: '1px solid var(--cn-border-soft)',
              display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
              fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--cn-subtle)',
            }}
          >
            {/* Telemetry stays one quiet line so the answer owns the bubble; it only takes
                color when a signal needs attention (ungrounded, low confidence). */}
            <span
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 3,
                color: r.grounded ? 'var(--cn-accent-strong)' : 'var(--cn-warn)',
              }}
            >
              {r.grounded ? <CheckCircle2 size={10} /> : <AlertCircle size={10} />}
              {r.grounded ? 'Grounded' : 'Ungrounded'}
            </span>
            <span aria-hidden>·</span>
            <span>{r.tier_used}</span>
            <span aria-hidden>·</span>
            <span style={{ color: r.confidence < 0.65 ? 'var(--cn-danger)' : undefined }}>
              {Math.round(r.confidence * 100)}% confidence
            </span>
            <span aria-hidden>·</span>
            <span>${r.cost_usd.toFixed(5)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
