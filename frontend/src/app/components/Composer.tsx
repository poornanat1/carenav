import { useState, useRef, useEffect } from 'react';
import { Send, ArrowUp } from 'lucide-react';
import type { Member, SuggestedQuestion } from './types';
import { INTENT_STYLE } from './intentStyles';

type Props = {
  member: Member | null;
  suggestions: SuggestedQuestion[];
  loading: boolean;
  onSend: (q: string) => void;
  pendingQuestion: string;
  onPendingClear: () => void;
};

export function Composer({ member, suggestions, loading, onSend, pendingQuestion, onPendingClear }: Props) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (pendingQuestion) {
      setValue(pendingQuestion);
      onPendingClear();
      textareaRef.current?.focus();
    }
  }, [pendingQuestion, onPendingClear]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [value]);

  function handleSend() {
    const q = value.trim();
    if (!q || loading || !member) return;
    onSend(q);
    setValue('');
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const disabled = !member || loading;
  const canSend = !disabled && value.trim().length > 0;

  return (
    <div style={{ borderTop: '1px solid var(--cn-border)', background: 'var(--cn-panel)', flexShrink: 0 }}>
      {!member && (
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 14px',
            borderBottom: '1px solid rgba(31,122,90,0.2)',
            background: 'var(--cn-accent-soft)',
          }}
        >
          <ArrowUp size={14} color="var(--cn-accent)" style={{ flexShrink: 0 }} />
          <span style={{ fontSize: 12, color: 'var(--cn-accent-strong)', fontFamily: 'var(--font-sans)', fontWeight: 400, lineHeight: 1.4 }}>
            Select a member above to start asking about their coverage, claims, and care.
          </span>
        </div>
      )}

      {member && suggestions.length > 0 && (
        <div style={{ padding: '9px 14px 0' }}>
          <div className="chat-stage" style={{ display: 'flex', gap: 6, overflowX: 'auto', scrollbarWidth: 'none' }}>
            {suggestions.map((sq, i) => {
              const s = INTENT_STYLE[sq.intent] ?? INTENT_STYLE.benefits;
              return (
                <button
                  key={i}
                  onClick={() => { setValue(sq.question); textareaRef.current?.focus(); }}
                  disabled={loading}
                  style={{
                    border: `1px solid ${s.border}`, background: s.bg, color: s.text,
                    borderRadius: 13, padding: '4px 11px',
                    fontSize: 11, fontFamily: 'var(--font-sans)', fontWeight: 400,
                    cursor: loading ? 'not-allowed' : 'pointer',
                    whiteSpace: 'nowrap', opacity: loading ? 0.4 : 1, transition: 'opacity 0.15s',
                  }}
                  onMouseEnter={e => { if (!loading) e.currentTarget.style.opacity = '0.65'; }}
                  onMouseLeave={e => { if (!loading) e.currentTarget.style.opacity = '1'; }}
                >
                  {sq.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div style={{ padding: '10px 14px' }}>
        <div className="chat-stage" style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={
            !member ? 'Select a member to begin…'
            : loading ? 'Waiting for response…'
            : `Ask about ${member.name}'s coverage, claims, or medications…`
          }
          rows={1}
          style={{
            flex: 1, resize: 'none',
            border: '1px solid var(--cn-border)',
            borderRadius: 7,
            padding: '9px 13px',
            fontSize: 13, fontFamily: 'var(--font-sans)', fontWeight: 400,
            color: 'var(--cn-ink)',
            background: disabled ? 'var(--cn-surface)' : 'var(--cn-card-strong)',
            outline: 'none', lineHeight: 1.55, transition: 'border-color 0.15s',
            overflowY: 'hidden', minHeight: 40,
          }}
          onFocus={e => (e.currentTarget.style.borderColor = 'var(--cn-accent)')}
          onBlur={e => (e.currentTarget.style.borderColor = 'var(--cn-border)')}
        />
        <button
          onClick={handleSend}
          disabled={!canSend}
          style={{
            width: 38, height: 38, borderRadius: 7,
            background: canSend ? 'var(--cn-accent)' : 'var(--cn-surface)',
            border: canSend ? '1px solid var(--cn-accent)' : '1px solid var(--cn-border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: canSend ? 'pointer' : 'not-allowed',
            transition: 'all 0.15s', flexShrink: 0,
          }}
          onMouseEnter={e => { if (canSend) e.currentTarget.style.background = 'var(--cn-accent-strong)'; }}
          onMouseLeave={e => { if (canSend) e.currentTarget.style.background = 'var(--cn-accent)'; }}
        >
          <Send size={14} color={canSend ? '#ffffff' : 'var(--cn-subtle)'} />
        </button>
        </div>
      </div>
    </div>
  );
}
