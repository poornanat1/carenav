import React from 'react';
import { ExternalLink, FileText, Cpu, User } from 'lucide-react';
import type { Citation, Member, Message, TurnResponse } from './types';
import { detailFor } from './api';
import { groupCitations, sourceKind, sourceLabel } from './citations';

type Tab = 'member' | 'evidence' | 'system';

type Props = {
  member: Member | null;
  messages: Message[];
  activeTab: Tab;
  onTabChange: (t: Tab) => void;
};

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'rgba(14,14,9,0.3)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
      {children}
    </div>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, padding: '6px 0', borderBottom: '1px solid rgba(14,14,9,0.07)' }}>
      <span style={{ fontSize: 11, color: 'rgba(14,14,9,0.4)', fontFamily: 'var(--font-sans)', fontWeight: 400, flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 11, color: 'rgba(14,14,9,0.7)', fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)', fontWeight: mono ? 400 : 500, textAlign: 'right' }}>{value}</span>
    </div>
  );
}

function Bar({ used, total, filled }: { used: number; total: number; filled: boolean }) {
  const pct = Math.min(100, (used / total) * 100);
  return (
    <div style={{ height: 3, background: 'rgba(14,14,9,0.1)', borderRadius: 2, overflow: 'hidden', marginTop: 3 }}>
      <div style={{ width: `${pct}%`, height: '100%', background: filled ? '#4E7A4E' : 'rgba(14,14,9,0.35)', borderRadius: 2, transition: 'width 0.4s' }} />
    </div>
  );
}

function MemberTab({ member }: { member: Member | null }) {
  if (!member) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ fontSize: 12, color: 'rgba(14,14,9,0.25)', fontFamily: 'var(--font-sans)', fontWeight: 300, textAlign: 'center' }}>No member selected</p>
      </div>
    );
  }

  const detail = detailFor(member);
  if (!detail) return null;
  const deductibleMet = detail.deductible.used >= detail.deductible.total;

  return (
    <div style={{ overflowY: 'auto', flex: 1, padding: 14, scrollbarWidth: 'none' }}>
      <div
        style={{
          background: '#0E0E09', borderRadius: 8, padding: '12px 14px', marginBottom: 16,
        }}
      >
        <div style={{ fontWeight: 900, fontSize: 15, color: '#E6E2D4', fontFamily: 'var(--font-sans)', letterSpacing: '-0.02em', textTransform: 'uppercase' }}>{member.name}</div>
        <div style={{ fontSize: 10, color: 'rgba(230,226,212,0.4)', fontFamily: 'var(--font-mono)', marginTop: 3 }}>Age {member.age} · {member.plan}</div>
        <div style={{ marginTop: 8, padding: '7px 9px', background: 'rgba(255,255,255,0.05)', borderRadius: 5 }}>
          <p style={{ fontSize: 11, color: 'rgba(230,226,212,0.45)', fontFamily: 'var(--font-sans)', fontWeight: 300, margin: 0, lineHeight: 1.55 }}>{detail.note}</p>
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <Label>Cost sharing</Label>
        <div style={{ marginBottom: 9 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 1 }}>
            <span style={{ fontSize: 11, color: 'rgba(14,14,9,0.4)', fontFamily: 'var(--font-sans)' }}>Deductible</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: deductibleMet ? '#4E7A4E' : 'rgba(14,14,9,0.55)' }}>
              ${detail.deductible.used.toLocaleString()} / ${detail.deductible.total.toLocaleString()}{deductibleMet && ' ✓'}
            </span>
          </div>
          <Bar used={detail.deductible.used} total={detail.deductible.total} filled={deductibleMet} />
        </div>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 1 }}>
            <span style={{ fontSize: 11, color: 'rgba(14,14,9,0.4)', fontFamily: 'var(--font-sans)' }}>Out-of-pocket</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'rgba(14,14,9,0.55)' }}>
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
            <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#3A5A8A', flexShrink: 0, marginTop: 5 }} />
            <span style={{ fontSize: 11, color: 'rgba(14,14,9,0.65)', fontFamily: 'var(--font-sans)', fontWeight: 300 }}>{condition}</span>
          </div>
        ))}
        {(detail.kbTopics ?? []).length > 0 && (
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 8 }}>
            {(detail.kbTopics ?? []).map(topic => (
              <span key={topic} style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: '#3A5A8A', background: 'rgba(60,90,140,0.08)', border: '1px solid rgba(60,90,140,0.18)', borderRadius: 4, padding: '2px 6px' }}>
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
            <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#4E7A4E', flexShrink: 0, marginTop: 5 }} />
            <span style={{ fontSize: 11, color: 'rgba(14,14,9,0.65)', fontFamily: 'var(--font-sans)', fontWeight: 300 }}>{med}</span>
          </div>
        ))}
      </div>

      <div style={{ marginBottom: 16 }}>
        <Label>Recent claims</Label>
        {detail.recentClaims.map((claim, i) => (
          <div key={i} style={{ marginBottom: 5, padding: '8px 10px', background: 'rgba(14,14,9,0.03)', borderRadius: 6, border: '1px solid rgba(14,14,9,0.07)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <span style={{ fontSize: 11, color: 'rgba(14,14,9,0.65)', fontFamily: 'var(--font-sans)', fontWeight: 300, flex: 1 }}>{claim.description}</span>
              <span style={{
                fontSize: 9, fontFamily: 'var(--font-mono)', padding: '2px 5px', borderRadius: 3, marginLeft: 6, flexShrink: 0,
                background: claim.status === 'Paid' ? 'rgba(78,122,78,0.1)' : claim.status === 'Processing' ? 'rgba(60,90,140,0.1)' : 'rgba(160,48,48,0.1)',
                color: claim.status === 'Paid' ? '#4E7A4E' : claim.status === 'Processing' ? '#3A5A8A' : '#A03030',
              }}>
                {claim.status}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
              <span style={{ fontSize: 9, color: 'rgba(14,14,9,0.25)', fontFamily: 'var(--font-mono)' }}>{claim.date}</span>
              <span style={{ fontSize: 9, color: 'rgba(14,14,9,0.35)', fontFamily: 'var(--font-mono)' }}>${claim.amount.toLocaleString()}</span>
            </div>
          </div>
        ))}
      </div>

      <div>
        <Label>Recent providers</Label>
        {detail.recentProviders.map((p, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div style={{ width: 26, height: 26, borderRadius: '50%', border: '1px solid rgba(14,14,9,0.12)', background: 'rgba(14,14,9,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <User size={12} color="rgba(14,14,9,0.3)" />
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'rgba(14,14,9,0.7)', fontFamily: 'var(--font-sans)', fontWeight: 500 }}>{p.name}</div>
              <div style={{ fontSize: 10, color: 'rgba(14,14,9,0.35)', fontFamily: 'var(--font-sans)', fontWeight: 300 }}>{p.specialty}</div>
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
      <p style={{ fontSize: 12, color: 'rgba(14,14,9,0.25)', fontFamily: 'var(--font-sans)', fontWeight: 300, textAlign: 'center' }}>No response yet. Send a message to see evidence.</p>
    </div>
  );

  if (!lastResponse.grounded) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ textAlign: 'center' }}>
        <FileText size={22} color="rgba(14,14,9,0.12)" style={{ margin: '0 auto 8px' }} />
        <p style={{ fontSize: 12, color: 'rgba(14,14,9,0.25)', fontFamily: 'var(--font-sans)', fontWeight: 300 }}>Grounding unavailable or failed.</p>
      </div>
    </div>
  );

  const sources = groupCitations(lastResponse.citations);

  if (sources.length === 0) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <p style={{ fontSize: 12, color: 'rgba(14,14,9,0.25)', fontFamily: 'var(--font-sans)', fontWeight: 300, textAlign: 'center' }}>No citations for this response.</p>
    </div>
  );

  return (
    <div style={{ overflowY: 'auto', flex: 1, padding: 14, scrollbarWidth: 'none' }}>
      <Label>{sources.length} source{sources.length !== 1 ? 's' : ''} · latest answer</Label>
      {sources.map((source, i) => {
        const cit = source.citation;
        return (
        <div key={source.key} style={{ background: 'rgba(14,14,9,0.03)', border: '1px solid rgba(14,14,9,0.08)', borderRadius: 8, padding: '11px 12px', marginBottom: 7 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
            <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'rgba(78,122,78,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>
              <span style={{ fontSize: 8, fontFamily: 'var(--font-mono)', color: '#4E7A4E', fontWeight: 500 }}>{i + 1}</span>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, color: 'rgba(14,14,9,0.75)', fontFamily: 'var(--font-sans)', fontWeight: 500, lineHeight: 1.4 }}>{sourceLabel(cit)}</div>
              <div style={{ fontSize: 10, color: 'rgba(14,14,9,0.35)', fontFamily: 'var(--font-sans)', fontWeight: 300, marginTop: 2 }}>{sourceKind(cit)}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'rgba(14,14,9,0.2)', marginTop: 4 }}>{source.chunkIds.join(', ')}</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(78,122,78,0.08)', border: '1px solid rgba(78,122,78,0.2)', borderRadius: 4, padding: '2px 7px' }}>
              <div style={{ width: 4, height: 4, borderRadius: '50%', background: '#4E7A4E' }} />
              <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: '#4E7A4E' }}>used in latest answer</span>
            </div>
            {cit.source_url ? (
              <a href={cit.source_url} target="_blank" rel="noopener noreferrer"
                style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, color: 'rgba(14,14,9,0.35)', fontFamily: 'var(--font-mono)', textDecoration: 'none', padding: '2px 7px', borderRadius: 4, border: '1px solid rgba(14,14,9,0.1)', transition: 'color 0.15s' }}
                onMouseEnter={e => (e.currentTarget.style.color = 'rgba(14,14,9,0.7)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(14,14,9,0.35)')}
              >
                <ExternalLink size={9} /> source
              </a>
            ) : (
              <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'rgba(14,14,9,0.2)' }}>internal</span>
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
    <div style={{ overflowY: 'auto', flex: 1, padding: 14, scrollbarWidth: 'none' }}>
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
          <Cpu size={20} color="rgba(14,14,9,0.12)" style={{ margin: '0 auto 8px' }} />
          <p style={{ fontSize: 10, color: 'rgba(14,14,9,0.25)', fontFamily: 'var(--font-mono)' }}>no turn data</p>
        </div>
      )}
    </div>
  );
}

export function RightPanel({ member, messages, activeTab, onTabChange }: Props) {
  const lastAssistantMsg = [...messages].reverse().find(m => m.role === 'assistant' && !m.loading && !m.error);
  const lastResponse = lastAssistantMsg?.response ?? null;
  const tabs: { id: Tab; label: string }[] = [
    { id: 'member', label: 'Member' },
    { id: 'evidence', label: 'Evidence' },
    { id: 'system', label: 'System' },
  ];

  return (
    <aside style={{ width: 282, flexShrink: 0, borderLeft: '1px solid rgba(14,14,9,0.1)', background: '#DDDAC9', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', borderBottom: '1px solid rgba(14,14,9,0.1)' }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            style={{
              flex: 1, padding: '10px 6px', background: 'none', border: 'none',
              borderBottom: activeTab === tab.id ? '1.5px solid rgba(78,122,78,0.7)' : '1.5px solid transparent',
              color: activeTab === tab.id ? '#0E0E09' : 'rgba(14,14,9,0.35)',
              fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: activeTab === tab.id ? 500 : 400,
              cursor: 'pointer', transition: 'all 0.15s', marginBottom: -1, letterSpacing: '0.02em',
            }}
            onMouseEnter={e => { if (activeTab !== tab.id) e.currentTarget.style.color = 'rgba(14,14,9,0.6)'; }}
            onMouseLeave={e => { if (activeTab !== tab.id) e.currentTarget.style.color = 'rgba(14,14,9,0.35)'; }}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {activeTab === 'member' && <MemberTab member={member} />}
      {activeTab === 'evidence' && <EvidenceTab lastResponse={lastResponse} />}
      {activeTab === 'system' && <SystemTab lastResponse={lastResponse} />}
    </aside>
  );
}
