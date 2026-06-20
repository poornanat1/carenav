import { AlertCircle } from 'lucide-react';
import { labelStyle } from './shared';

export function ErrorBubble() {
  return (
    <div style={{ marginBottom: 22 }}>
      <div style={labelStyle}>CareNav</div>
      <div
        style={{
          background: 'var(--cn-danger-soft)',
          border: '1px solid rgba(180,35,47,0.22)',
          borderRadius: '3px 10px 10px 10px',
          padding: '12px 16px',
          maxWidth: 420,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <AlertCircle size={13} color="var(--cn-danger)" />
          <span style={{ color: 'var(--cn-danger)', fontSize: 13, fontFamily: 'var(--font-sans)', fontWeight: 400 }}>
            Request failed. Please try again.
          </span>
        </div>
      </div>
    </div>
  );
}
