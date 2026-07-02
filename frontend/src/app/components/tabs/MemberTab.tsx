import { User } from 'lucide-react';
import type { Member } from '../types';
import { detailFor } from '../api';
import { Bar, DetailRow, MAX_PROVIDERS, Section, tabBodyStyle, TopicTag } from './shared';

export function MemberTab({ member }: { member: Member | null }) {
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
    <div style={tabBodyStyle}>
      {/* Quiet white card; the brand carries in the slim gradient rule, not a color slab. */}
      <div
        style={{
          background: 'var(--cn-card-strong)', border: '1px solid var(--cn-border-soft)',
          borderRadius: 10, marginBottom: 16, overflow: 'hidden', boxShadow: 'var(--cn-shadow)',
        }}
      >
        <div style={{ height: 3, background: 'var(--cn-grad-brand)' }} />
        <div style={{ padding: '12px 14px' }}>
          <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--cn-ink)', fontFamily: 'var(--font-sans)', letterSpacing: '-0.01em' }}>{member.name}</div>
          <div style={{ fontSize: 10, color: 'var(--cn-muted)', fontFamily: 'var(--font-mono)', marginTop: 3 }}>Age {member.age} · {member.plan}</div>
          <p style={{ fontSize: 11.5, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, margin: '9px 0 0', lineHeight: 1.55 }}>{detail.note}</p>
        </div>
      </div>

      <Section title="Cost sharing">
        <div style={{ marginBottom: 9 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 1 }}>
            <span style={{ fontSize: 11, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)' }}>Deductible</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: deductibleMet ? 'var(--cn-info)' : 'var(--cn-text)' }}>
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
      </Section>

      <Section title="Clinical profile">
        {(detail.conditions ?? []).map((condition, i) => (
          <DetailRow key={i}>
            <span
              title={condition}
              style={{ display: 'block', fontSize: 11, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', fontWeight: 400, lineHeight: 1.45, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
            >
              {condition}
            </span>
          </DetailRow>
        ))}
        {(detail.kbTopics ?? []).length > 0 && (
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 9 }}>
            {(detail.kbTopics ?? []).map(topic => (
              <TopicTag key={topic}>{topic}</TopicTag>
            ))}
          </div>
        )}
      </Section>

      <Section title="Active medications" collapsible defaultOpen={false} count={detail.medications.length}>
        {detail.medications.map((med, i) => (
          <DetailRow key={i} marker="var(--cn-muted)">
            <span style={{ fontSize: 11, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', fontWeight: 400, lineHeight: 1.45 }}>{med}</span>
          </DetailRow>
        ))}
      </Section>

      <Section title="Recent claims" collapsible defaultOpen={false} count={detail.recentClaims.length}>
        {detail.recentClaims.map((claim, i) => (
          <div key={i} style={{ padding: '7px 0', borderBottom: '1px solid var(--cn-border-soft)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <span style={{ fontSize: 11, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', fontWeight: 400, flex: 1 }}>{claim.description}</span>
              <span style={{
                fontSize: 9, fontFamily: 'var(--font-mono)', padding: '2px 5px', borderRadius: 3, marginLeft: 6, flexShrink: 0,
                background: claim.status === 'Paid' ? 'var(--cn-surface)' : claim.status === 'Processing' ? 'var(--cn-info-soft)' : 'var(--cn-danger-soft)',
                color: claim.status === 'Paid' ? 'var(--cn-muted)' : claim.status === 'Processing' ? 'var(--cn-info)' : 'var(--cn-danger)',
                border: '1px solid var(--cn-border-soft)',
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
      </Section>

      <Section title="Recommended providers" collapsible defaultOpen={false} count={Math.min(MAX_PROVIDERS, detail.recentProviders.length)}>
        {detail.recentProviders.slice(0, MAX_PROVIDERS).map((p, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 0', borderBottom: '1px solid var(--cn-border-soft)' }}>
            <div style={{ width: 24, height: 24, borderRadius: '50%', border: '1px solid var(--cn-border)', background: 'var(--cn-card)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <User size={12} color="var(--cn-muted)" />
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--cn-text)', fontFamily: 'var(--font-sans)', fontWeight: 500 }}>{p.name}</div>
              <div style={{ fontSize: 10, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400 }}>{p.specialty}</div>
            </div>
          </div>
        ))}
      </Section>
    </div>
  );
}
