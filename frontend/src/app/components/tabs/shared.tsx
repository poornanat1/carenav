import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';

export function Label({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--cn-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 9 }}>
      {children}
    </div>
  );
}

export function Section({
  children,
  title,
  collapsible = false,
  defaultOpen = true,
  count,
}: {
  children: React.ReactNode;
  title: string;
  collapsible?: boolean;
  defaultOpen?: boolean;
  count?: number;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!collapsible) {
    return (
      <section style={{ marginBottom: 20 }}>
        <Label>{title}</Label>
        {children}
      </section>
    );
  }
  const heading = count !== undefined ? `${title} · ${count}` : title;
  return (
    <section style={{ marginBottom: 20 }}>
      <button
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%',
          background: 'none', border: 'none', padding: 0, marginBottom: open ? 9 : 0, cursor: 'pointer',
        }}
      >
        <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--cn-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          {heading}
        </span>
        <ChevronDown
          size={13}
          color="var(--cn-subtle)"
          style={{ transform: open ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform 0.15s' }}
        />
      </button>
      {open && children}
    </section>
  );
}

export function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--cn-border-soft)' }}>
      <span style={{ fontSize: 11, color: 'var(--cn-muted)', fontFamily: 'var(--font-sans)', fontWeight: 400, flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 11, color: 'var(--cn-text)', fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)', fontWeight: mono ? 400 : 500, textAlign: 'right' }}>{value}</span>
    </div>
  );
}

export function DetailRow({
  children,
  marker = 'var(--cn-info)',
}: {
  children: React.ReactNode;
  marker?: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--cn-border-soft)' }}>
      <div style={{ width: 4, height: 4, borderRadius: '50%', background: marker, flexShrink: 0, marginTop: 7 }} />
      <div style={{ minWidth: 0, flex: 1 }}>{children}</div>
    </div>
  );
}

export function TopicTag({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--cn-info)', background: 'var(--cn-info-soft)', border: '1px solid rgba(39,107,143,0.22)', borderRadius: 4, padding: '2px 6px' }}>
      {children}
    </span>
  );
}

export function Bar({ used, total, filled }: { used: number; total: number; filled: boolean }) {
  const pct = Math.min(100, (used / total) * 100);
  return (
    <div style={{ height: 3, background: 'var(--cn-border)', borderRadius: 2, overflow: 'hidden', marginTop: 3 }}>
      <div style={{ width: `${pct}%`, height: '100%', background: filled ? 'var(--cn-info)' : 'var(--cn-subtle)', borderRadius: 2, transition: 'width 0.4s' }} />
    </div>
  );
}

// Scroll container style shared by all three tab bodies.
export const tabBodyStyle: React.CSSProperties = {
  overflowY: 'auto',
  flex: 1,
  padding: 14,
  paddingBottom: 'calc(28px + env(safe-area-inset-bottom))',
  scrollbarWidth: 'none',
  WebkitOverflowScrolling: 'touch',
};

// Number of recommended providers surfaced in the Member tab. Used in two places
// (the section count and the slice) that must stay in sync.
export const MAX_PROVIDERS = 2;
