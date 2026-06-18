import React from 'react';
import { ExternalLink, FileText, Cpu, User, X } from 'lucide-react';
import type { Citation, Member, Message, TurnResponse } from './types';
import { detailFor } from './api';
import { groupCitations, sourceKind, sourceLabel } from './citations';

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

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--cn-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
      {children}
    </div>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--cn-border-soft)' }}>
      <span style={{ fontSize: 11, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 11, color: 'var(--cn-text)', fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)', fontWeight: mono ? 400 : 500, textAlign: 'right' }}>{value}</span>
    </div>
  );
}

function Bar({ used, total, filled }: { used: number; total: number; filled: boolean }) {
  const pct = Math.min(100, (used / total) * 100);
  return (
    <div style={{ height: 3, background: 'var(--cn-border)', borderRadius: 2, overflow: 'hidden', marginTop: 3 }}>
      <div style={{ width: `${pct}%`, height: '100%', background: filled ? 'var(--cn-accent)' : 'var(--cn-subtle)', borderRadius: 2, transition: 'width 0.4s' }} />
    </div>
  );
}

function MemberTab({ member }: { member: Member | null }) {
  if (!member) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ fontSize: 12, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, textAlign: 'center' }}>No member selected</p>
      </div>
    );
  }

  const detail = detailFor(member);
  if (!detail) return null;
  const deductibleMet = detail.deductible.used >= detail.deductible.total;

  return (
    <div style={{ overflowY: 'auto', flex: 1, padding: 14, paddingBottom: 'calc(28px + env(safe-area-inset-bottom))', scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch' }}>
      <div
        style={{
          background: 'var(--cn-ink)', borderRadius: 8, padding: '12px 14px', marginBottom: 16,
        }}
      >
        <div style={{ fontWeight: 900, fontSize: 15, color: 'var(--cn-card-strong)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.02em', textTransform: 'uppercase' }}>{member.name}</div>
        <div style={{ fontSize: 10, color: 'rgba(244,247,242,0.68)', fontFamily: 'var(--font-mono)', marginTop: 3 }}>Age {member.age} · {member.plan}</div>
        <div style={{ marginTop: 8, padding: '7px 9px', background: 'rgba(255,255,255,0.08)', borderRadius: 5 }}>
          <p style={{ fontSize: 11, color: 'rgba(244,247,242,0.78)', fontFamily: 'var(--font-sans)', fontWeight: 400, margin: 0, lineHeight: 1.55 }}>{detail.note}</p>
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <Label>Cost sharing</Label>
        <div style={{ marginBottom: 9 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 1 }}>
            <span style={{ fontSize: 11, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)' }}>Deductible</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: deductibleMet ? 'var(--cn-accent-strong)' : 'var(--cn-text)' }}>
              ${detail.deductible.used.toLocaleString()} / ${detail.deductible.total.toLocaleString()}{deductibleMet && ' ✓'}
            </span>
          </div>
          <Bar used={detail.deductible.used} total={detail.deductible.total} filled={deductibleMet} />
        </div>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 1 }}>
            <span style={{ fontSize: 11, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)' }}>Out-of-pocket</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--cn-text)' }}>
              ${detail.oop.used.toLocaleString()} / ${detail.oop.total.toLocaleString()}
            </span>
          </div>
          <Bar used={detail.oop.used} total={detail.oop.total} filled={false} />
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <Label>Clinical profile</Label>
        {(detail.conditions ?? []).map((condition, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 7, marginBottom: 5 }}>
            <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--cn-info)', flexShrink: 0, marginTop: 5 }} />
            <span style={{ fontSize: 11, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', fontWeight: 400 }}>{condition}</span>
          </div>
        ))}
        {(detail.kbTopics ?? []).length > 0 && (
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 8 }}>
            {(detail.kbTopics ?? []).map(topic => (
              <span key={topic} style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--cn-info)', background: 'var(--cn-info-soft)', border: '1px solid rgba(39,107,143,0.2)', borderRadius: 4, padding: '2px 6px' }}>
                {topic}
              </span>
            ))}
          </div>
        )}
      </div>

      <div style={{ marginBottom: 16 }}>
        <Label>Active medications</Label>
        {detail.medications.map((med, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 7, marginBottom: 5 }}>
            <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--cn-accent)', flexShrink: 0, marginTop: 5 }} />
            <span style={{ fontSize: 11, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', fontWeight: 400 }}>{med}</span>
          </div>
        ))}
      </div>

      <div style={{ marginBottom: 16 }}>
        <Label>Recent claims</Label>
        {detail.recentClaims.map((claim, i) => (
          <div key={i} style={{ marginBottom: 5, padding: '8px 10px', background: 'var(--cn-card)', borderRadius: 6, border: '1px solid var(--cn-border-soft)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <span style={{ fontSize: 11, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', fontWeight: 400, flex: 1 }}>{claim.description}</span>
              <span style={{
                fontSize: 9, fontFamily: 'var(--font-mono)', padding: '2px 5px', borderRadius: 3, marginLeft: 6, flexShrink: 0,
                background: claim.status === 'Paid' ? 'var(--cn-accent-soft)' : claim.status === 'Processing' ? 'var(--cn-info-soft)' : 'var(--cn-danger-soft)',
                color: claim.status === 'Paid' ? 'var(--cn-accent)' : claim.status === 'Processing' ? 'var(--cn-info)' : 'var(--cn-danger)',
              }}>
                {claim.status}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
              <span style={{ fontSize: 9, color: 'var(--cn-subtle)', fontFamily: 'var(--font-mono)' }}>{claim.date}</span>
              <span style={{ fontSize: 9, color: 'var(--cn-muted)', fontFamily: 'var(--font-mono)' }}>${claim.amount.toLocaleString()}</span>
            </div>
          </div>
        ))}
      </div>

      <div>
        <Label>Recent providers</Label>
        {detail.recentProviders.map((p, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div style={{ width: 26, height: 26, borderRadius: '50%', border: '1px solid var(--cn-border)', background: 'var(--cn-card)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <User size={12} color="var(--cn-muted)" />
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', fontWeight: 500 }}>{p.name}</div>
              <div style={{ fontSize: 10, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400 }}>{p.specialty}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidenceTab({ lastResponse }: { lastResponse: TurnResponse | null }) {
  if (!lastResponse) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <p style={{ fontSize: 12, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, textAlign: 'center' }}>No response yet. Send a message to see evidence.</p>
    </div>
  );

  if (!lastResponse.grounded) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ textAlign: 'center' }}>
        <FileText size={22} color="var(--cn-subtle)" style={{ margin: '0 auto 8px' }} />
        <p style={{ fontSize: 12, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400 }}>Grounding unavailable or failed.</p>
      </div>
    </div>
  );

  const sources = groupCitations(lastResponse.citations);

  if (sources.length === 0) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <p style={{ fontSize: 12, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, textAlign: 'center' }}>No citations for this response.</p>
    </div>
  );

  return (
    <div style={{ overflowY: 'auto', flex: 1, padding: 14, paddingBottom: 'calc(28px + env(safe-area-inset-bottom))', scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch' }}>
      <Label>{sources.length} source{sources.length !== 1 ? 's' : ''} · latest answer</Label>
      {sources.map((source, i) => {
        const cit = source.citation;
        return (
        <div key={source.key} style={{ background: 'var(--cn-card)', border: '1px solid var(--cn-border-soft)', borderRadius: 8, padding: '11px 12px', marginBottom: 7 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
            <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'var(--cn-accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>
              <span style={{ fontSize: 8, fontFamily: 'var(--font-mono)', color: 'var(--cn-accent-strong)', fontWeight: 500 }}>{i + 1}</span>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', fontWeight: 500, lineHeight: 1.4 }}>{sourceLabel(cit)}</div>
              <div style={{ fontSize: 10, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, marginTop: 2 }}>{sourceKind(cit)}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--cn-subtle)', marginTop: 4 }}>{source.chunkIds.join(', ')}</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'var(--cn-accent-soft)', border: '1px solid rgba(31,122,90,0.2)', borderRadius: 4, padding: '2px 7px' }}>
              <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--cn-accent)' }} />
              <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--cn-accent-strong)' }}>used in latest answer</span>
            </div>
            {cit.source_url ? (
              <a href={cit.source_url} target="_blank" rel="noopener noreferrer"
                style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, color: 'var(--cn-muted)', fontFamily: 'var(--font-mono)', textDecoration: 'none', padding: '2px 7px', borderRadius: 4, border: '1px solid var(--cn-border)', transition: 'color 0.15s' }}
                onMouseEnter={e => (e.currentTarget.style.color = 'var(--cn-ink)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'var(--cn-muted)')}
              >
                <ExternalLink size={9} /> source
              </a>
            ) : (
              <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--cn-subtle)' }}>internal</span>
            )}
          </div>
        </div>
        );
      })}
    </div>
  );
}

function SystemTab({ lastResponse }: { lastResponse: TurnResponse | null }) {
  const fields: [string, string][] = lastResponse ? [
    ['intent', lastResponse.intent ?? 'none'],
    ['safety_flag', lastResponse.safety_flag],
    ['grounded', String(lastResponse.grounded)],
    ['escalated', String(lastResponse.escalated)],
    ['tier_used', lastResponse.tier_used],
    ['confidence', `${Math.round(lastResponse.confidence * 100)}%`],
    ['cost_usd', `$${lastResponse.cost_usd.toFixed(5)}`],
  ] : [];

  return (
    <div style={{ overflowY: 'auto', flex: 1, padding: 14, paddingBottom: 'calc(28px + env(safe-area-inset-bottom))', scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch' }}>
      <div style={{ marginBottom: 16 }}>
        <Label>Provider config</Label>
        <Row label="provider" value="Mistral" mono />
        <Row label="small_model" value="mistral-small-latest" mono />
        <Row label="frontier_model" value="mistral-large-latest" mono />
        <Row label="rag" value="enabled" mono />
      </div>
      {lastResponse ? (
        <div>
          <Label>Latest turn</Label>
          {fields.map(([label, val]) => <Row key={label} label={label} value={val} mono />)}
        </div>
      ) : (
        <div style={{ textAlign: 'center', marginTop: 20 }}>
          <Cpu size={20} color="var(--cn-subtle)" style={{ margin: '0 auto 8px' }} />
          <p style={{ fontSize: 10, color: 'var(--cn-muted)', fontFamily: 'var(--font-mono)' }}>no turn data</p>
        </div>
      )}
    </div>
  );
}

export function RightPanel({ member, messages, activeTab, onTabChange, mobile = false, onClose }: Props) {
  const lastAssistantMsg = [...messages].reverse().find(m => m.role === 'assistant' && !m.loading && !m.error);
  const lastResponse = lastAssistantMsg?.response ?? null;
  const tabs: { id: Tab; label: string }[] = [
    { id: 'member', label: 'Member' },
    { id: 'evidence', label: 'Evidence' },
    { id: 'system', label: 'System' },
  ];

  const asideStyle: React.CSSProperties = mobile
    ? {
        width: '100%', height: '88vh', maxHeight: '88vh',
        borderTopLeftRadius: 18, borderTopRightRadius: 18,
        background: 'var(--cn-panel)', display: 'flex', flexDirection: 'column', overflow: 'hidden',
        boxShadow: '0 -10px 40px rgba(23,33,27,0.2)',
      }
    : {
        width: 282, flexShrink: 0, borderLeft: '1px solid var(--cn-border)',
        background: 'var(--cn-panel)', display: 'flex', flexDirection: 'column', overflow: 'hidden',
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
              flex: 1, padding: mobile ? '13px 6px' : '10px 6px', background: 'none', border: 'none',
              borderBottom: activeTab === tab.id ? '1.5px solid var(--cn-accent)' : '1.5px solid transparent',
              color: activeTab === tab.id ? 'var(--cn-ink)' : 'var(--cn-muted)',
              fontSize: mobile ? 13 : 11, fontFamily: 'var(--font-mono)', fontWeight: activeTab === tab.id ? 500 : 400,
              cursor: 'pointer', transition: 'all 0.15s', marginBottom: -1, letterSpacing: '0.02em',
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
