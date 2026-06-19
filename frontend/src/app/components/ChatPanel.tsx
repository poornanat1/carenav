import React, { useEffect, useRef } from 'react';
import { ShieldAlert, CheckCircle2, AlertCircle, Phone, ExternalLink } from 'lucide-react';
import type { Citation, Message, Member, SuggestedQuestion, TurnResponse } from './types';
import { citationRefMap, citationTooltip, groupCitations, sourceLabel } from './citations';

type Props = {
  messages: Message[];
  member: Member | null;
  suggestions: SuggestedQuestion[];
  onSuggestedClick: (q: SuggestedQuestion) => void;
};

const INTENT_STYLE: Record<string, { border: string; bg: string; text: string }> = {
  member_profile: { border: 'var(--cn-border)', bg: 'var(--cn-surface)', text: 'var(--cn-text)' },
  medication: { border: 'rgba(31,122,90,0.3)',  bg: 'var(--cn-accent-soft)',  text: 'var(--cn-accent-strong)' },
  benefits:   { border: 'rgba(39,107,143,0.28)', bg: 'var(--cn-info-soft)',  text: 'var(--cn-info)' },
  claims:     { border: 'rgba(140,100,40,0.3)',  bg: 'rgba(140,100,40,0.05)', text: 'var(--cn-warn)' },
  providers:  { border: 'rgba(110,60,130,0.3)',  bg: 'rgba(110,60,130,0.05)', text: '#70418a' },
  safety:     { border: 'rgba(180,35,47,0.3)',   bg: 'var(--cn-danger-soft)',  text: 'var(--cn-danger)' },
};

// Human-readable copy for the orchestrator's escalation reason codes. Falls back to
// a de-snake-cased version of the raw code for any reason not listed here.
const HANDOFF_REASON_COPY: Record<string, string> = {
  member_context_required: 'This question is about a specific member. Select a member above, then ask again.',
  emergent_safety: 'This looks like a medical emergency. CareNav cannot give emergency advice — call 911 or your local emergency number now.',
  low_confidence: 'CareNav was not confident enough in an answer to give one safely. A care advocate can follow up.',
  out_of_scope: 'This is outside what CareNav can answer. CareNav covers care navigation, benefits, and selected member profile questions.',
};

function handoffReasonText(reason: string): string {
  return HANDOFF_REASON_COPY[reason] ?? reason.replace(/_/g, ' ');
}

// Severity tier for an answer, derived only from machine-readable response signals
// (never from the answer text). Drives the alert treatment so important answers are
// visually unmistakable from routine ones:
//   emergent  — medical emergency; strongest red treatment + 911.
//   escalated — handed off for a non-emergency reason; amber caution, not full red.
//   urgent    — time-sensitive but still answered; amber banner atop a normal bubble.
//   none      — routine answer.
type Severity = 'emergent' | 'escalated' | 'urgent' | 'none';

function severityOf(r: TurnResponse): Severity {
  const isEmergent = r.safety_flag === 'emergent' || r.handoff?.reason === 'emergent_safety';
  if (isEmergent) return 'emergent';
  if (r.escalated) return 'escalated';
  if (r.safety_flag === 'urgent') return 'urgent';
  return 'none';
}

function LoadingDots() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 0' }}>
      {[0, 1, 2].map(i => (
        <div
          key={i}
          style={{
            width: 5,
            height: 5,
            borderRadius: '50%',
            background: 'var(--cn-muted)',
            animation: `cBounce 1.2s ${i * 0.2}s ease-in-out infinite`,
          }}
        />
      ))}
      <style>{`
        @keyframes cBounce {
          0%,80%,100%{transform:translateY(0);opacity:0.25}
          40%{transform:translateY(-5px);opacity:0.7}
        }
      `}</style>
    </div>
  );
}

function CitationMarker({ index, citation }: { index: number; citation?: Citation }) {
  return (
    <sup
      title={citationTooltip(citation, index)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 14,
        height: 14,
        borderRadius: '50%',
        background: 'var(--cn-accent-soft)',
        color: 'var(--cn-accent-strong)',
        fontSize: 8,
        fontFamily: 'var(--font-mono)',
        fontWeight: 500,
        verticalAlign: 'super',
        marginLeft: 1,
      }}
    >
      {index}
    </sup>
  );
}

function renderAnswer(text: string, citations: Citation[]): React.ReactNode[] {
  const byChunkId = citationRefMap(citations);
  const tokenRe = /(\[CHUNK:([^\]]+)\]|\*\*(.+?)\*\*)/g;

  return text.split('\n').map((line, li, arr) => {
    const parts: React.ReactNode[] = [];
    let cursor = 0;
    let k = 0;

    for (const match of line.matchAll(tokenRe)) {
      const matchIndex = match.index ?? 0;
      if (matchIndex > cursor) {
        const nextIsCitation = Boolean(match[2]);
        const segment = line.slice(cursor, matchIndex);
        parts.push(<span key={k++}>{nextIsCitation ? segment.replace(/\s+$/, '') : segment}</span>);
      }

      if (match[2]) {
        const found = byChunkId.get(match[2]);
        if (found) {
          parts.push(
            <CitationMarker key={k++} index={found.index} citation={found.citation} />
          );
        }
      } else {
        parts.push(
          <strong key={k++} style={{ fontWeight: 700, color: 'var(--cn-ink)' }}>
            {match[3]}
          </strong>
        );
      }

      cursor = matchIndex + match[0].length;
    }

    if (cursor < line.length) {
      parts.push(<span key={k++}>{line.slice(cursor)}</span>);
    }

    return <span key={li}>{parts}{li < arr.length - 1 ? '\n' : ''}</span>;
  });
}

function CitationChips({ citations }: { citations: Citation[] }) {
  const sources = groupCitations(citations);
  if (sources.length === 0) return null;

  return (
    <div
      style={{
        marginTop: 12,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        flexWrap: 'wrap',
      }}
    >
      <span
        style={{
          fontSize: 9,
          fontFamily: 'var(--font-mono)',
          color: 'var(--cn-subtle)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
        }}
      >
        Sources
      </span>
      {sources.map((source, i) => {
        const { citation } = source;
        const content = (
          <>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 15,
                height: 15,
                borderRadius: '50%',
                background: 'var(--cn-accent-soft)',
                color: 'var(--cn-accent-strong)',
                fontSize: 8,
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {i + 1}
            </span>
            <span
              style={{
                minWidth: 0,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {sourceLabel(citation)}
            </span>
            {citation.source_url ? <ExternalLink size={10} /> : null}
          </>
        );
        const style: React.CSSProperties = {
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          maxWidth: 220,
          padding: '3px 7px 3px 4px',
          borderRadius: 5,
          border: '1px solid var(--cn-border)',
          background: 'var(--cn-card-strong)',
          color: 'var(--cn-muted)',
          fontSize: 10,
          fontFamily: 'var(--font-sans)',
          fontWeight: 400,
          textDecoration: 'none',
        };

        return citation.source_url ? (
          <a
            key={source.key}
            href={citation.source_url}
            target="_blank"
            rel="noopener noreferrer"
            title={citation.title}
            style={style}
          >
            {content}
          </a>
        ) : (
          <span key={source.key} title={citation.title} style={style}>
            {content}
          </span>
        );
      })}
    </div>
  );
}

function MetaPill({
  children, bg, color, border,
}: { children: React.ReactNode; bg: string; color: string; border: string }) {
  return (
    <div
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        padding: '2px 8px', borderRadius: 4, background: bg,
        border: `1px solid ${border}`,
      }}
    >
      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color }}>{children}</span>
    </div>
  );
}

function AssistantBubble({ msg }: { msg: Message }) {
  const r = msg.response;

  const labelStyle: React.CSSProperties = {
    fontSize: 9,
    color: 'var(--cn-subtle)',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    marginBottom: 5,
  };

  if (msg.loading) {
    return (
      <div style={{ marginBottom: 22 }}>
        <div style={labelStyle}>CareNav</div>
        <div
          style={{
            background: 'var(--cn-card-strong)',
            border: '1px solid var(--cn-border)',
            borderRadius: '3px 10px 10px 10px',
            padding: '12px 16px',
            maxWidth: 420,
            boxShadow: 'var(--cn-shadow)',
          }}
        >
          <LoadingDots />
        </div>
      </div>
    );
  }

  if (msg.error) {
    return (
      <div style={{ marginBottom: 22 }}>
        <div style={labelStyle}>CareNav</div>
        <div
          style={{
            background: 'var(--cn-danger-soft)',
            border: '1px solid rgba(180,35,47,0.22)',
            borderRadius: '3px 10px 10px 10px',
            padding: '12px 16px',
            maxWidth: 420,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <AlertCircle size={13} color="var(--cn-danger)" />
            <span style={{ color: 'var(--cn-danger)', fontSize: 13, fontFamily: 'var(--font-sans)', fontWeight: 400 }}>
              Request failed. Please try again.
            </span>
          </div>
        </div>
      </div>
    );
  }

  if (r?.escalated) {
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
        <div style={{ ...labelStyle, color: pal.strong }}>CareNav · escalation</div>
        <div
          style={{
            background: pal.soft,
            border: `1.5px solid ${pal.border}`,
            borderRadius: '3px 10px 10px 10px',
            padding: '16px',
            maxWidth: 540,
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

  const isUrgent = r ? severityOf(r) === 'urgent' : false;
  return (
    <div style={{ marginBottom: 22 }}>
      <div style={labelStyle}>CareNav</div>
      <div
        style={{
          background: 'var(--cn-card-strong)',
          border: isUrgent ? '1px solid var(--cn-warn-border)' : '1px solid var(--cn-border)',
          borderRadius: '3px 10px 10px 10px',
          padding: '14px 16px',
          maxWidth: 620,
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

export function ChatPanel({ messages, member, suggestions, onSuggestedClick }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (!member) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: 'var(--cn-bg)' }}>
        <div
          style={{
            width: 38, height: 38, borderRadius: 8,
            border: '1.5px solid var(--cn-border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14,
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--cn-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
        <p style={{ fontWeight: 700, fontSize: 14, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', marginBottom: 4, letterSpacing: '-0.01em' }}>
          Select a member to begin
        </p>
        <p style={{ fontSize: 12, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, textAlign: 'center', maxWidth: 240, lineHeight: 1.5 }}>
          Choose a member above to load their context and start navigating care.
        </p>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 24px', background: 'var(--cn-bg)' }}>
        <div className="chat-stage" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{ marginBottom: 10 }}>
            <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--cn-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
              Suggested for {member.name}
            </span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, justifyContent: 'center', maxWidth: 560 }}>
            {suggestions.map((sq, i) => {
              const s = INTENT_STYLE[sq.intent] ?? INTENT_STYLE.benefits;
              return (
                <button
                  key={i}
                  onClick={() => onSuggestedClick(sq)}
                  style={{
                    border: `1px solid ${s.border}`, background: s.bg, color: s.text,
                    borderRadius: 16, padding: '6px 14px',
                    fontSize: 12, fontFamily: 'var(--font-sans)', fontWeight: 400,
                    cursor: 'pointer', transition: 'opacity 0.15s',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.opacity = '0.65')}
                  onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
                >
                  {sq.label}
                </button>
              );
            })}
          </div>
          <p style={{ marginTop: 18, fontSize: 11, color: 'var(--cn-subtle)', fontFamily: 'var(--font-sans)', fontWeight: 400 }}>
            or type a question below
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="chat-scroll"
      style={{ flex: 1, overflowY: 'auto', padding: '24px 24px', background: 'var(--cn-bg)', scrollbarWidth: 'none' }}
    >
      <div className="chat-stage">
        {messages.map(msg => {
          if (msg.role === 'user') {
            return (
              <div key={msg.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', marginBottom: 22 }}>
                <div
                  style={{
                    background: 'var(--cn-ink)',
                    color: 'var(--cn-card-strong)',
                    borderRadius: '10px 3px 10px 10px',
                    padding: '10px 15px',
                    maxWidth: 440,
                    fontSize: 14, fontFamily: 'var(--font-sans)',
                    fontWeight: 400, lineHeight: 1.55,
                  }}
                >
                  {msg.content}
                </div>
                <span style={{ fontSize: 9, color: 'var(--cn-subtle)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            );
          }
          return <AssistantBubble key={msg.id} msg={msg} />;
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
