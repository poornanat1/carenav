import { useEffect, useRef } from 'react';
import type { Member, Message, SuggestedQuestion } from './types';
import { INTENT_STYLE } from './intentStyles';
import { AssistantBubble } from './bubbles/AssistantBubble';

type Props = {
  messages: Message[];
  member: Member | null;
  suggestions: SuggestedQuestion[];
  onSuggestedClick: (q: SuggestedQuestion) => void;
};

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
                    maxWidth: 560,
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
