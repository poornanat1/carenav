// Single source of truth for suggested-question intent chip colors.
// Previously this map was duplicated in ChatPanel.tsx and Composer.tsx and had
// drifted (claims background alpha 0.05 vs 0.06). The 0.05 value is kept here so
// it stays consistent with the providers chip, which uses the same alpha.
export const INTENT_STYLE: Record<string, { border: string; bg: string; text: string }> = {
  member_profile: { border: 'var(--cn-border)', bg: 'var(--cn-surface)', text: 'var(--cn-text)' },
  medication: { border: 'rgba(31,122,90,0.3)',  bg: 'var(--cn-accent-soft)',  text: 'var(--cn-accent-strong)' },
  benefits:   { border: 'rgba(39,107,143,0.28)', bg: 'var(--cn-info-soft)',  text: 'var(--cn-info)' },
  claims:     { border: 'rgba(140,100,40,0.3)',  bg: 'rgba(140,100,40,0.05)', text: 'var(--cn-warn)' },
  providers:  { border: 'rgba(110,60,130,0.3)',  bg: 'rgba(110,60,130,0.05)', text: '#70418a' },
  safety:     { border: 'rgba(180,35,47,0.3)',   bg: 'var(--cn-danger-soft)',  text: 'var(--cn-danger)' },
};
