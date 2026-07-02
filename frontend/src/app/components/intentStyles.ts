// Single source of truth for suggested-question intent chip colors.
// Chips are deliberately neutral so several visible at once don't turn the composer
// into a rainbow; only safety keeps a color, because it changes what the user should do.
const NEUTRAL = { border: 'var(--cn-border)', bg: 'var(--cn-card-strong)', text: 'var(--cn-text)' };

export const INTENT_STYLE: Record<string, { border: string; bg: string; text: string }> = {
  member_profile: NEUTRAL,
  medication: NEUTRAL,
  benefits: NEUTRAL,
  claims: NEUTRAL,
  providers: NEUTRAL,
  safety: { border: 'rgba(180,35,47,0.3)', bg: 'var(--cn-danger-soft)', text: 'var(--cn-danger)' },
};
