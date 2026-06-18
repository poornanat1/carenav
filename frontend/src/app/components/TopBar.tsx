import { Activity, RotateCcw, PanelRight } from 'lucide-react';

type Props = {
  onReset: () => void;
  hasConversation: boolean;
  apiOnline: boolean;
  isMobile?: boolean;
  onOpenPanel?: () => void;
};

export function TopBar({ onReset, hasConversation, apiOnline, isMobile = false, onOpenPanel }: Props) {
  return (
    <header
      style={{
        borderBottom: '1px solid rgba(244,247,242,0.14)',
        background: 'var(--cn-ink)',
        height: 52,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: isMobile ? '0 14px' : '0 22px',
        flexShrink: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Activity size={14} color="#58b98b" strokeWidth={2} />
        <span
          style={{
            color: 'var(--cn-card-strong)',
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
            color: 'rgba(244,247,242,0.58)',
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
          }}
        >
          beta
        </span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 10 : 18 }}>
        {!isMobile && (
          <>
            <span
              style={{
                color: 'rgba(244,247,242,0.68)',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
              }}
            >
              Mistral · RAG enabled
            </span>

            <div style={{ width: 1, height: 14, background: 'rgba(244,247,242,0.18)' }} />
          </>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: apiOnline ? '#58b98b' : '#ff8a8f',
              boxShadow: apiOnline ? '0 0 6px rgba(88,185,139,0.72)' : '0 0 6px rgba(255,138,143,0.5)',
            }}
          />
          {!isMobile && (
            <span
              style={{
                color: 'rgba(244,247,242,0.68)',
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
              }}
            >
              {apiOnline ? 'API connected' : 'API offline'}
            </span>
          )}
        </div>

        {!isMobile && (
          <>
            <div style={{ width: 1, height: 14, background: 'rgba(244,247,242,0.18)' }} />

            <span
              style={{
                color: 'rgba(244,247,242,0.52)',
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
              }}
            >
              synthetic demo
            </span>
          </>
        )}

        {isMobile && (
          <button
            onClick={onOpenPanel}
            aria-label="Open details panel"
            style={{
              background: 'transparent',
              border: '1px solid rgba(244,247,242,0.24)',
              borderRadius: 5,
              color: 'rgba(244,247,242,0.78)',
              padding: '5px 9px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
            }}
          >
            <PanelRight size={13} />
            <span style={{ fontSize: 11, fontFamily: 'var(--font-sans)', fontWeight: 400 }}>Details</span>
          </button>
        )}

        {hasConversation && (
          <button
            onClick={onReset}
            style={{
              background: 'transparent',
              border: '1px solid rgba(244,247,242,0.24)',
              borderRadius: 5,
              color: 'rgba(244,247,242,0.68)',
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
              e.currentTarget.style.color = 'rgba(244,247,242,0.92)';
              e.currentTarget.style.borderColor = 'rgba(244,247,242,0.42)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = 'rgba(244,247,242,0.68)';
              e.currentTarget.style.borderColor = 'rgba(244,247,242,0.24)';
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
