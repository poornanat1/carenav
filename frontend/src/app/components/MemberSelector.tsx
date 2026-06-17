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
        borderBottom: '1px solid rgba(14,14,9,0.1)',
        background: '#DDDAC9',
        padding: '10px 12px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <button
          onClick={() => scrollByCard(-1)}
          disabled={members.length === 0}
          aria-label="Previous members"
          style={{
            width: 28,
            height: 72,
            borderRadius: 7,
            border: '1px solid rgba(14,14,9,0.1)',
            background: 'rgba(14,14,9,0.03)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: members.length === 0 ? 'not-allowed' : 'pointer',
            flexShrink: 0,
          }}
        >
          <ChevronLeft size={14} color="rgba(14,14,9,0.45)" />
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
                width: 292,
                minWidth: 292,
                border: isSelected
                  ? '1.5px solid rgba(78,122,78,0.5)'
                  : '1.5px solid rgba(14,14,9,0.1)',
                background: isSelected ? 'rgba(78,122,78,0.07)' : 'rgba(14,14,9,0.03)',
                borderRadius: 7,
                padding: '9px 12px',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s',
                scrollSnapAlign: 'start',
              }}
              onMouseEnter={e => {
                if (!isSelected) {
                  e.currentTarget.style.borderColor = 'rgba(14,14,9,0.2)';
                  e.currentTarget.style.background = 'rgba(14,14,9,0.05)';
                }
              }}
              onMouseLeave={e => {
                if (!isSelected) {
                  e.currentTarget.style.borderColor = 'rgba(14,14,9,0.1)';
                  e.currentTarget.style.background = 'rgba(14,14,9,0.03)';
                }
              }}
            >
              <div
                style={{
                  fontWeight: 700,
                  fontSize: 13,
                  color: '#0E0E09',
                  fontFamily: 'var(--font-sans)',
                  letterSpacing: '-0.01em',
                }}
              >
                {m.name}
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: isSelected ? '#4E7A4E' : 'rgba(14,14,9,0.45)',
                  fontFamily: 'var(--font-mono)',
                  marginTop: 2,
                }}
              >
                {m.age} · {m.plan}
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: 'rgba(14,14,9,0.35)',
                  fontFamily: 'var(--font-sans)',
                  fontWeight: 300,
                  marginTop: 3,
                  lineHeight: 1.4,
                }}
              >
                {m.summary}
              </div>
            </button>
          );
        })}
        {members.length === 0 && (
          <div style={{ fontSize: 12, color: 'rgba(14,14,9,0.35)', fontFamily: 'var(--font-sans)', padding: 8 }}>
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
            height: 72,
            borderRadius: 7,
            border: '1px solid rgba(14,14,9,0.1)',
            background: 'rgba(14,14,9,0.03)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: members.length === 0 ? 'not-allowed' : 'pointer',
            flexShrink: 0,
          }}
        >
          <ChevronRight size={14} color="rgba(14,14,9,0.45)" />
        </button>
      </div>
    </div>
  );
}
