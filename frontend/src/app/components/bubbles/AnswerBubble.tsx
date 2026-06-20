import { CheckCircle2, AlertCircle } from 'lucide-react';
import type { Message } from '../types';
import { CitationChips, labelStyle, MetaPill, renderAnswer, severityOf } from './shared';

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
            fontSize: 14, color: 'var(--cn-text)',
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
              marginTop: 11, paddingTop: 10,
              borderTop: '1px solid var(--cn-border-soft)',
              display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap',
            }}
          >
            <MetaPill
              bg={r.grounded ? 'var(--cn-info-soft)' : 'var(--cn-surface)'}
              color={r.grounded ? 'var(--cn-info)' : 'var(--cn-subtle)'}
              border={r.grounded ? 'rgba(39,107,143,0.25)' : 'var(--cn-border)'}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                {r.grounded ? <CheckCircle2 size={9} /> : <AlertCircle size={9} />}
                {r.grounded ? 'Grounded' : 'Ungrounded'}
              </span>
            </MetaPill>

            <MetaPill bg="var(--cn-surface)" color="var(--cn-muted)" border="var(--cn-border-soft)">
              {r.tier_used}
            </MetaPill>

            <MetaPill
              bg={r.confidence >= 0.8 ? 'var(--cn-info-soft)' : r.confidence >= 0.65 ? 'rgba(149,106,22,0.1)' : 'var(--cn-danger-soft)'}
              color={r.confidence >= 0.8 ? 'var(--cn-info)' : r.confidence >= 0.65 ? 'var(--cn-warn)' : 'var(--cn-danger)'}
              border={r.confidence >= 0.8 ? 'rgba(39,107,143,0.22)' : r.confidence >= 0.65 ? 'rgba(149,106,22,0.22)' : 'rgba(180,35,47,0.2)'}
            >
              {Math.round(r.confidence * 100)}% confidence
            </MetaPill>

            <MetaPill bg="var(--cn-surface)" color="var(--cn-subtle)" border="var(--cn-border-soft)">
              ${r.cost_usd.toFixed(5)}
            </MetaPill>
          </div>
        )}
      </div>
    </div>
  );
}
