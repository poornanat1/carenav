import { Activity, RotateCcw } from 'lucide-react';

type Props = {
  onReset: () => void;
  hasConversation: boolean;
  apiOnline: boolean;
};

export function TopBar({ onReset, hasConversation, apiOnline }: Props) {
  return (
    <header
      style={{
        borderBottom: '1px solid rgba(14,14,9,0.12)',
        background: '#0E0E09',
        height: 52,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 22px',
        flexShrink: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Activity size={14} color="#4E7A4E" strokeWidth={2} />
        <span
          style={{
            color: '#E6E2D4',
            fontFamily: 'var(--font-display)',
            fontWeight: 900,
            fontSize: 17,
            letterSpacing: '-0.03em',
            textTransform: 'uppercase',
          }}
        >
          CareNav
        </span>
        <span
          style={{
            color: 'rgba(230,226,212,0.25)',
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
          }}
        >
          beta
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <span
          style={{
            color: 'rgba(230,226,212,0.35)',
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
          }}
        >
          Mistral · RAG enabled
        </span>

        <div style={{ width: 1, height: 14, background: 'rgba(230,226,212,0.12)' }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: apiOnline ? '#4E7A4E' : '#A03030',
              boxShadow: apiOnline ? '0 0 6px rgba(78,122,78,0.7)' : '0 0 6px rgba(160,48,48,0.45)',
            }}
          />
          <span
            style={{
              color: 'rgba(230,226,212,0.35)',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
            }}
          >
            {apiOnline ? 'API connected' : 'API offline'}
          </span>
        </div>

        <div style={{ width: 1, height: 14, background: 'rgba(230,226,212,0.12)' }} />

        <span
          style={{
            color: 'rgba(230,226,212,0.18)',
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
        >
          synthetic demo
        </span>

        {hasConversation && (
          <button
            onClick={onReset}
            style={{
              background: 'transparent',
              border: '1px solid rgba(230,226,212,0.15)',
              borderRadius: 5,
              color: 'rgba(230,226,212,0.35)',
              padding: '4px 10px',
              fontSize: 11,
              fontFamily: 'var(--font-sans)',
              fontWeight: 400,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.color = 'rgba(230,226,212,0.7)';
              e.currentTarget.style.borderColor = 'rgba(230,226,212,0.3)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = 'rgba(230,226,212,0.35)';
              e.currentTarget.style.borderColor = 'rgba(230,226,212,0.15)';
            }}
          >
            <RotateCcw size={11} />
            Reset
          </button>
        )}
      </div>
    </header>
  );
}
