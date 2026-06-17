import React, { useEffect, useRef } from 'react';
import { ShieldAlert, CheckCircle2, AlertCircle, Phone, ExternalLink } from 'lucide-react';
import type { Citation, Message, Member, SuggestedQuestion } from './types';
import { citationRefMap, citationTooltip, groupCitations, sourceLabel } from './citations';

type Props = {
  messages: Message[];
  member: Member | null;
  suggestions: SuggestedQuestion[];
  onSuggestedClick: (q: SuggestedQuestion) => void;
};

const INTENT_STYLE: Record<string, { border: string; bg: string; text: string }> = {
  member_profile: { border: 'rgba(14,14,9,0.22)', bg: 'rgba(14,14,9,0.045)', text: '#3E3D36' },
  medication: { border: 'rgba(78,122,78,0.35)',  bg: 'rgba(78,122,78,0.06)',  text: '#3A6B3A' },
  benefits:   { border: 'rgba(60,90,140,0.3)',   bg: 'rgba(60,90,140,0.05)',  text: '#3A5A8A' },
  claims:     { border: 'rgba(140,100,40,0.3)',  bg: 'rgba(140,100,40,0.05)', text: '#7A5A20' },
  providers:  { border: 'rgba(110,60,130,0.3)',  bg: 'rgba(110,60,130,0.05)', text: '#6A3A80' },
  safety:     { border: 'rgba(160,50,50,0.4)',   bg: 'rgba(160,50,50,0.06)',  text: '#A03030' },
};

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
            background: 'rgba(14,14,9,0.2)',
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
        background: 'rgba(78,122,78,0.15)',
        color: '#4E7A4E',
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
          <strong key={k++} style={{ fontWeight: 700, color: '#0E0E09' }}>
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
          color: 'rgba(14,14,9,0.28)',
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
                background: 'rgba(78,122,78,0.13)',
                color: '#4E7A4E',
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
          border: '1px solid rgba(14,14,9,0.09)',
          background: 'rgba(14,14,9,0.035)',
          color: 'rgba(14,14,9,0.55)',
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
    color: 'rgba(14,14,9,0.3)',
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
            background: '#EEEADB',
            border: '1px solid rgba(14,14,9,0.1)',
            borderRadius: '3px 10px 10px 10px',
            padding: '12px 16px',
            maxWidth: 420,
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
            background: 'rgba(160,48,48,0.05)',
            border: '1px solid rgba(160,48,48,0.2)',
            borderRadius: '3px 10px 10px 10px',
            padding: '12px 16px',
            maxWidth: 420,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <AlertCircle size={13} color="#A03030" />
            <span style={{ color: '#A03030', fontSize: 13, fontFamily: 'var(--font-sans)', fontWeight: 400 }}>
              Request failed. Please try again.
            </span>
          </div>
        </div>
      </div>
    );
  }

  if (r?.escalated) {
    const isEmergent = r.safety_flag === 'emergent' || r.handoff?.reason === 'emergent_safety';
    return (
      <div style={{ marginBottom: 22 }}>
        <div style={{ ...labelStyle, color: 'rgba(160,48,48,0.5)' }}>CareNav · escalation</div>
        <div
          style={{
            background: 'rgba(160,48,48,0.04)',
            border: '1.5px solid rgba(160,48,48,0.3)',
            borderRadius: '3px 10px 10px 10px',
            padding: '16px',
            maxWidth: 540,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 14 }}>
            <div
              style={{
                width: 32, height: 32, borderRadius: 7,
                background: 'rgba(160,48,48,0.1)',
                border: '1px solid rgba(160,48,48,0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}
            >
              <ShieldAlert size={16} color="#A03030" />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14, color: '#0E0E09', fontFamily: 'var(--font-sans)', letterSpacing: '-0.01em' }}>
                {isEmergent ? 'Human handoff recommended' : 'Unable to answer safely'}
              </div>
              <div style={{ fontSize: 12, color: 'rgba(160,48,48,0.7)', fontFamily: 'var(--font-sans)', fontWeight: 300, marginTop: 2 }}>
                {isEmergent
                  ? 'CareNav does not provide emergency medical advice.'
                  : 'CareNav only answers grounded care, benefit, and selected member profile questions.'}
              </div>
            </div>
          </div>

          {r.handoff && (
            <div
              style={{
                background: 'rgba(160,48,48,0.04)',
                border: '1px solid rgba(160,48,48,0.12)',
                borderRadius: 7,
                padding: '11px 13px',
                marginBottom: 12,
              }}
            >
              <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'rgba(160,48,48,0.5)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 5 }}>
                Reason
              </div>
              <p style={{ fontSize: 13, color: 'rgba(14,14,9,0.65)', fontFamily: 'var(--font-sans)', fontWeight: 300, lineHeight: 1.55, margin: 0 }}>
                {r.handoff.reason}
              </p>
              {r.handoff.gathered.length > 0 && (
                <ul style={{ margin: '8px 0 0', padding: '0 0 0 14px' }}>
                  {r.handoff.gathered.map((g, i) => (
                    <li key={i} style={{ fontSize: 11, color: 'rgba(14,14,9,0.4)', fontFamily: 'var(--font-mono)', lineHeight: 1.6 }}>
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
                background: '#A03030', borderRadius: 6, padding: '9px 14px',
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

  return (
    <div style={{ marginBottom: 22 }}>
      <div style={labelStyle}>CareNav</div>
      <div
        style={{
          background: '#EEEADB',
          border: '1px solid rgba(14,14,9,0.1)',
          borderRadius: '3px 10px 10px 10px',
          padding: '14px 16px',
          maxWidth: 620,
        }}
      >
        <div
          style={{
            fontSize: 14, color: 'rgba(14,14,9,0.75)',
            fontFamily: 'var(--font-sans)', fontWeight: 300,
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
              borderTop: '1px solid rgba(14,14,9,0.07)',
              display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap',
            }}
          >
            <MetaPill
              bg={r.grounded ? 'rgba(78,122,78,0.08)' : 'rgba(14,14,9,0.04)'}
              color={r.grounded ? '#4E7A4E' : 'rgba(14,14,9,0.3)'}
              border={r.grounded ? 'rgba(78,122,78,0.25)' : 'rgba(14,14,9,0.1)'}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                {r.grounded ? <CheckCircle2 size={9} /> : <AlertCircle size={9} />}
                {r.grounded ? 'Grounded' : 'Ungrounded'}
              </span>
            </MetaPill>

            <MetaPill bg="rgba(14,14,9,0.04)" color="rgba(14,14,9,0.35)" border="rgba(14,14,9,0.08)">
              {r.tier_used}
            </MetaPill>

            <MetaPill
              bg={r.confidence >= 0.8 ? 'rgba(78,122,78,0.08)' : r.confidence >= 0.65 ? 'rgba(140,100,40,0.08)' : 'rgba(160,48,48,0.06)'}
              color={r.confidence >= 0.8 ? '#4E7A4E' : r.confidence >= 0.65 ? '#7A5A20' : '#A03030'}
              border={r.confidence >= 0.8 ? 'rgba(78,122,78,0.2)' : r.confidence >= 0.65 ? 'rgba(140,100,40,0.2)' : 'rgba(160,48,48,0.2)'}
            >
              {Math.round(r.confidence * 100)}% confidence
            </MetaPill>

            <MetaPill bg="rgba(14,14,9,0.03)" color="rgba(14,14,9,0.2)" border="rgba(14,14,9,0.06)">
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
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#E6E2D4' }}>
        <div
          style={{
            width: 38, height: 38, borderRadius: 8,
            border: '1.5px solid rgba(14,14,9,0.1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14,
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="rgba(14,14,9,0.25)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
        <p style={{ fontWeight: 700, fontSize: 14, color: 'rgba(14,14,9,0.5)', fontFamily: 'var(--font-sans)', marginBottom: 4, letterSpacing: '-0.01em' }}>
          Select a member to begin
        </p>
        <p style={{ fontSize: 12, color: 'rgba(14,14,9,0.3)', fontFamily: 'var(--font-sans)', fontWeight: 300, textAlign: 'center', maxWidth: 240, lineHeight: 1.5 }}>
          Choose a member above to load their context and start navigating care.
        </p>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0 24px', background: '#E6E2D4' }}>
        <div style={{ marginBottom: 10 }}>
          <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'rgba(14,14,9,0.3)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
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
        <p style={{ marginTop: 18, fontSize: 11, color: 'rgba(14,14,9,0.2)', fontFamily: 'var(--font-sans)', fontWeight: 300 }}>
          or type a question below
        </p>
      </div>
    );
  }

  return (
    <div
      style={{ flex: 1, overflowY: 'auto', padding: '24px 24px', background: '#E6E2D4', scrollbarWidth: 'none' }}
    >
      {messages.map(msg => {
        if (msg.role === 'user') {
          return (
            <div key={msg.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', marginBottom: 22 }}>
              <div
                style={{
                  background: '#0E0E09',
                  color: 'rgba(230,226,212,0.85)',
                  borderRadius: '10px 3px 10px 10px',
                  padding: '10px 15px',
                  maxWidth: 440,
                  fontSize: 14, fontFamily: 'var(--font-sans)',
                  fontWeight: 300, lineHeight: 1.55,
                }}
              >
                {msg.content}
              </div>
              <span style={{ fontSize: 9, color: 'rgba(14,14,9,0.25)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          );
        }
        return <AssistantBubble key={msg.id} msg={msg} />;
      })}
      <div ref={bottomRef} />
    </div>
  );
}
