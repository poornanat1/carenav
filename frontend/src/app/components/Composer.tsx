import { useState, useRef, useEffect } from 'react';
import { Send, ArrowUp } from 'lucide-react';
import type { Member, SuggestedQuestion } from './types';

const INTENT_STYLE: Record<string, { border: string; bg: string; text: string }> = {
  member_profile: { border: 'rgba(14,14,9,0.22)', bg: 'rgba(14,14,9,0.045)', text: '#3E3D36' },
  medication: { border: 'rgba(78,122,78,0.35)',  bg: 'rgba(78,122,78,0.07)',  text: '#3A6B3A' },
  benefits:   { border: 'rgba(60,90,140,0.3)',   bg: 'rgba(60,90,140,0.06)',  text: '#3A5A8A' },
  claims:     { border: 'rgba(140,100,40,0.3)',  bg: 'rgba(140,100,40,0.06)', text: '#7A5A20' },
  providers:  { border: 'rgba(110,60,130,0.3)',  bg: 'rgba(110,60,130,0.05)', text: '#6A3A80' },
  safety:     { border: 'rgba(160,50,50,0.4)',   bg: 'rgba(160,50,50,0.06)',  text: '#A03030' },
};

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
    <div style={{ borderTop: '1px solid rgba(14,14,9,0.1)', background: '#DDDAC9', flexShrink: 0 }}>
      {!member && (
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 14px',
            borderBottom: '1px solid rgba(78,122,78,0.18)',
            background: 'rgba(78,122,78,0.06)',
          }}
        >
          <ArrowUp size={14} color="#4E7A4E" style={{ flexShrink: 0 }} />
          <span style={{ fontSize: 12, color: '#3A6B3A', fontFamily: 'var(--font-sans)', fontWeight: 400, lineHeight: 1.4 }}>
            Select a member above to start asking about their coverage, claims, and care.
          </span>
        </div>
      )}

      {member && suggestions.length > 0 && (
        <div style={{ padding: '9px 14px 0', display: 'flex', gap: 6, overflowX: 'auto', scrollbarWidth: 'none' }}>
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
      )}

      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, padding: '10px 14px' }}>
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
            border: '1px solid rgba(14,14,9,0.12)',
            borderRadius: 7,
            padding: '9px 13px',
            fontSize: 13, fontFamily: 'var(--font-sans)', fontWeight: 300,
            color: '#0E0E09',
            background: disabled ? 'rgba(14,14,9,0.03)' : '#E6E2D4',
            outline: 'none', lineHeight: 1.55, transition: 'border-color 0.15s',
            overflowY: 'hidden', minHeight: 40,
          }}
          onFocus={e => (e.currentTarget.style.borderColor = 'rgba(78,122,78,0.5)')}
          onBlur={e => (e.currentTarget.style.borderColor = 'rgba(14,14,9,0.12)')}
        />
        <button
          onClick={handleSend}
          disabled={!canSend}
          style={{
            width: 38, height: 38, borderRadius: 7,
            background: canSend ? 'rgba(78,122,78,0.1)' : 'rgba(14,14,9,0.04)',
            border: canSend ? '1px solid rgba(78,122,78,0.35)' : '1px solid rgba(14,14,9,0.1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: canSend ? 'pointer' : 'not-allowed',
            transition: 'all 0.15s', flexShrink: 0,
          }}
          onMouseEnter={e => { if (canSend) e.currentTarget.style.background = 'rgba(78,122,78,0.18)'; }}
          onMouseLeave={e => { if (canSend) e.currentTarget.style.background = 'rgba(78,122,78,0.1)'; }}
        >
          <Send size={14} color={canSend ? '#4E7A4E' : 'rgba(14,14,9,0.2)'} />
        </button>
      </div>
    </div>
  );
}
