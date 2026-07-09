import { useRef } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { Member } from './types';

type Props = {
  members: Member[];
  selected: Member | null;
  onSelect: (m: Member) => void;
};

export function MemberSelector({ members, selected, onSelect }: Props) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  function scrollByCard(direction: -1 | 1) {
    scrollerRef.current?.scrollBy({ left: direction * 310, behavior: 'smooth' });
  }

  return (
    <div
      style={{
<<<<<<< Updated upstream
        borderBottom: '1px solid var(--cn-border)',
        background: 'var(--cn-panel)',
        padding: '8px 16px',
=======
        borderBottom: '1px solid rgba(14,14,9,0.1)',
        background: 'var(--cn-panel)',
        padding: '10px 12px',
>>>>>>> Stashed changes
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button
          onClick={() => scrollByCard(-1)}
          disabled={members.length === 0}
          aria-label="Previous members"
          style={{
            width: 28,
            height: 56,
            borderRadius: 7,
            border: '1px solid var(--cn-border)',
            background: 'var(--cn-card)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: members.length === 0 ? 'not-allowed' : 'pointer',
            flexShrink: 0,
          }}
        >
          <ChevronLeft size={14} color="var(--cn-muted)" />
        </button>

        <div
          ref={scrollerRef}
          style={{
            display: 'flex',
            gap: 8,
            overflowX: 'auto',
            scrollbarWidth: 'none',
            scrollSnapType: 'x mandatory',
            flex: 1,
            minWidth: 0,
          }}
        >
        {members.map(m => {
          const isSelected = selected?.id === m.id;
          return (
            <button
              key={m.id}
              onClick={() => onSelect(m)}
              style={{
                width: 300,
                minWidth: 300,
                border: isSelected
                  ? '1.5px solid var(--cn-accent)'
                  : '1.5px solid var(--cn-border)',
                background: isSelected ? 'var(--cn-accent-soft)' : 'var(--cn-card-strong)',
                borderRadius: 7,
                padding: '9px 13px',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s',
                scrollSnapAlign: 'start',
                boxShadow: isSelected ? 'none' : 'var(--cn-shadow)',
              }}
              onMouseEnter={e => {
                if (!isSelected) {
                  e.currentTarget.style.borderColor = 'var(--cn-accent)';
                  e.currentTarget.style.background = 'var(--cn-card)';
                }
              }}
              onMouseLeave={e => {
                if (!isSelected) {
                  e.currentTarget.style.borderColor = 'var(--cn-border)';
                  e.currentTarget.style.background = 'var(--cn-card-strong)';
                }
              }}
            >
              <div
                style={{
                  fontWeight: 700,
                  fontSize: 13,
                  color: 'var(--cn-ink)',
                  fontFamily: 'var(--font-sans)',
                  letterSpacing: '-0.01em',
                }}
              >
                {m.name}
              </div>
              <div
                style={{
                  fontSize: 10,
<<<<<<< Updated upstream
                  color: isSelected ? 'var(--cn-accent-strong)' : 'var(--cn-muted)',
=======
                  color: isSelected ? 'var(--cn-accent)' : 'rgba(14,14,9,0.45)',
>>>>>>> Stashed changes
                  fontFamily: 'var(--font-mono)',
                  marginTop: 2,
                }}
              >
                {m.age} · {m.plan}
              </div>
              <div
                title={m.summary}
                style={{
                  fontSize: 10,
                  color: 'var(--cn-muted)',
                  fontFamily: 'var(--font-sans)',
                  fontWeight: 400,
                  marginTop: 3,
                  lineHeight: 1.4,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {m.summary}
              </div>
            </button>
          );
        })}
        {members.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', padding: 8 }}>
            Loading members...
          </div>
        )}
        </div>

        <button
          onClick={() => scrollByCard(1)}
          disabled={members.length === 0}
          aria-label="Next members"
          style={{
            width: 28,
            height: 56,
            borderRadius: 7,
            border: '1px solid var(--cn-border)',
            background: 'var(--cn-card)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: members.length === 0 ? 'not-allowed' : 'pointer',
            flexShrink: 0,
          }}
        >
          <ChevronRight size={14} color="var(--cn-muted)" />
        </button>
      </div>
    </div>
  );
}
