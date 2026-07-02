import { BubbleLabel, LoadingDots } from './shared';

export function LoadingBubble() {
  return (
    <div style={{ marginBottom: 22 }}>
      <BubbleLabel>CareNav</BubbleLabel>
      <div
        style={{
          background: 'var(--cn-card-strong)',
          border: '1px solid var(--cn-border)',
          borderRadius: '3px 10px 10px 10px',
          padding: '12px 16px',
          maxWidth: 420,
          boxShadow: 'var(--cn-shadow)',
        }}
      >
        <LoadingDots />
      </div>
    </div>
  );
}
