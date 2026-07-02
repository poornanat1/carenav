import { ShieldAlert, AlertCircle, Phone } from 'lucide-react';
import type { TurnResponse } from '../types';
import { BubbleLabel, handoffReasonText, severityOf } from './shared';

export function EscalationBubble({ r }: { r: TurnResponse }) {
  const isEmergent = severityOf(r) === 'emergent';
  // Emergent → red (top of the scale). Non-emergent escalation → amber caution, so the
  // two severity tiers are visually distinct instead of both reading as full red.
  const pal = isEmergent
    ? {
        soft: 'var(--cn-danger-soft)', strong: 'var(--cn-danger)',
        border: 'rgba(180,35,47,0.28)', iconBg: 'rgba(180,35,47,0.1)',
        iconBorder: 'rgba(180,35,47,0.25)', reasonBorder: 'rgba(180,35,47,0.16)',
      }
    : {
        soft: 'var(--cn-warn-soft)', strong: 'var(--cn-warn)',
        border: 'var(--cn-warn-border)', iconBg: 'rgba(149,106,22,0.1)',
        iconBorder: 'rgba(149,106,22,0.25)', reasonBorder: 'rgba(149,106,22,0.16)',
      };
  return (
    <div style={{ marginBottom: 22 }}>
      <BubbleLabel color={pal.strong}>CareNav · escalation</BubbleLabel>
      <div
        style={{
          background: pal.soft,
          border: `1.5px solid ${pal.border}`,
          borderRadius: '3px 10px 10px 10px',
          padding: '16px 20px',
          maxWidth: 680,
        }}
      >
        {isEmergent && (
          <div
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              background: 'var(--cn-danger)', color: 'white', borderRadius: 5,
              padding: '3px 9px', marginBottom: 12,
              fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 500,
              letterSpacing: '0.06em',
            }}
          >
            <AlertCircle size={11} /> URGENT — EMERGENCY
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 14 }}>
          <div
            style={{
              width: 32, height: 32, borderRadius: 7,
              background: pal.iconBg,
              border: `1px solid ${pal.iconBorder}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}
          >
            <ShieldAlert size={16} color={pal.strong} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--cn-ink)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.01em' }}>
              {isEmergent ? 'Human handoff recommended' : 'Needs review — unable to answer safely'}
            </div>
            <div style={{ fontSize: 12, color: pal.strong, fontFamily: 'var(--font-sans)', fontWeight: 400, marginTop: 2 }}>
              {isEmergent
                ? 'CareNav does not provide emergency medical advice.'
                : 'CareNav only answers grounded care, benefit, and selected member profile questions.'}
            </div>
          </div>
        </div>

        {r.handoff && (
          <div
            style={{
              background: 'rgba(255,255,255,0.56)',
              border: `1px solid ${pal.reasonBorder}`,
              borderRadius: 7,
              padding: '11px 13px',
              marginBottom: 12,
            }}
          >
            <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: pal.strong, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 5 }}>
              Reason
            </div>
            <p style={{ fontSize: 13, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', fontWeight: 400, lineHeight: 1.55, margin: 0 }}>
              {handoffReasonText(r.handoff.reason)}
            </p>
            {r.handoff.gathered.length > 0 && (
              <ul style={{ margin: '8px 0 0', padding: '0 0 0 14px' }}>
                {r.handoff.gathered.map((g, i) => (
                  <li key={i} style={{ fontSize: 11, color: 'var(--cn-muted)', fontFamily: 'var(--font-mono)', lineHeight: 1.6 }}>
                    {g}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {isEmergent && (
          <div
            style={{
              background: 'var(--cn-danger)', borderRadius: 6, padding: '9px 14px',
              display: 'flex', alignItems: 'center', gap: 8,
            }}
          >
            <Phone size={13} color="white" />
            <span style={{ color: 'white', fontWeight: 700, fontSize: 13, fontFamily: 'var(--font-sans)' }}>
              Call 911 immediately for emergencies
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
