import React from 'react';
import { X } from 'lucide-react';
import type { Member, Message } from './types';
import { MemberTab } from './tabs/MemberTab';
import { EvidenceTab } from './tabs/EvidenceTab';
import { SystemTab } from './tabs/SystemTab';

type Tab = 'member' | 'evidence' | 'system';

type Props = {
  member: Member | null;
  messages: Message[];
  activeTab: Tab;
  onTabChange: (t: Tab) => void;
  /** Render as a slide-up bottom sheet over the chat (phone layout). */
  mobile?: boolean;
  onClose?: () => void;
};

export function RightPanel({ member, messages, activeTab, onTabChange, mobile = false, onClose }: Props) {
  const lastAssistantMsg = [...messages].reverse().find(m => m.role === 'assistant' && !m.loading && !m.error);
  const lastResponse = lastAssistantMsg?.response ?? null;
  const tabs: { id: Tab; label: string }[] = [
    { id: 'member', label: 'Member' },
    { id: 'evidence', label: 'Evidence' },
    { id: 'system', label: 'System' },
  ];

  // The panel shares the chat's canvas color (not its own surface) so it reads as part
  // of the same workspace rather than a bolted-on inspector.
  const asideStyle: React.CSSProperties = mobile
    ? {
        width: '100%', height: '88vh', maxHeight: '88vh',
        borderTopLeftRadius: 18, borderTopRightRadius: 18,
        background: 'var(--cn-bg)', display: 'flex', flexDirection: 'column', overflow: 'hidden',
        boxShadow: '0 -10px 40px rgba(23,33,27,0.2)',
      }
    : {
        width: 348, flexShrink: 0, borderLeft: '1px solid var(--cn-border)',
        background: 'transparent', display: 'flex', flexDirection: 'column', overflow: 'hidden',
      };

  const aside = (
    <aside style={asideStyle}>
      {mobile && (
        <div style={{ flexShrink: 0, display: 'flex', justifyContent: 'center', paddingTop: 9, paddingBottom: 3 }}>
          <div style={{ width: 38, height: 4, borderRadius: 3, background: 'var(--cn-border)' }} />
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'stretch', borderBottom: '1px solid var(--cn-border)' }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            style={{
              flex: 1, padding: mobile ? '13px 6px' : '11px 6px', background: 'none', border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid var(--cn-accent)' : '2px solid transparent',
              color: activeTab === tab.id ? 'var(--cn-ink)' : 'var(--cn-muted)',
              fontSize: mobile ? 13 : 12, fontFamily: 'var(--font-sans)', fontWeight: activeTab === tab.id ? 600 : 400,
              cursor: 'pointer', transition: 'all 0.15s', marginBottom: -1,
            }}
            onMouseEnter={e => { if (activeTab !== tab.id) e.currentTarget.style.color = 'var(--cn-ink)'; }}
            onMouseLeave={e => { if (activeTab !== tab.id) e.currentTarget.style.color = 'var(--cn-muted)'; }}
          >
            {tab.label}
          </button>
        ))}
        {mobile && (
          <button
            onClick={onClose}
            aria-label="Close panel"
            style={{
              width: 46, flexShrink: 0, background: 'none', border: 'none',
              borderLeft: '1px solid var(--cn-border-soft)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
            }}
          >
            <X size={16} color="var(--cn-muted)" />
          </button>
        )}
      </div>
      {activeTab === 'member' && <MemberTab member={member} />}
      {activeTab === 'evidence' && <EvidenceTab lastResponse={lastResponse} />}
      {activeTab === 'system' && <SystemTab lastResponse={lastResponse} />}
    </aside>
  );

  if (!mobile) return aside;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 50,
        background: 'rgba(23,33,27,0.45)',
        display: 'flex', flexDirection: 'column', justifyContent: 'flex-end',
        animation: 'cn-fade-in 0.18s ease-out',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{ display: 'flex', flexDirection: 'column', minHeight: 0, animation: 'cn-slide-up 0.26s cubic-bezier(0.22,1,0.36,1)' }}
      >
        {aside}
      </div>
    </div>
  );
}
