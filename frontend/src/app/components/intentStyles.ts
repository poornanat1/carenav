// Single source of truth for suggested-question intent chip colors.
// Every intent gets a tint from the same recipe — bg at ~10% alpha, a hairline border of
// the same hue, deep-toned text, and a saturated dot — so a row of mixed intents reads as
// one designed family rather than per-widget paint.
export const INTENT_STYLE: Record<string, { border: string; bg: string; text: string; dot: string }> = {
  member_profile: { border: 'rgba(63,82,73,0.2)',   bg: 'rgba(63,82,73,0.07)',   text: '#3f5249', dot: '#5d6f66' },
  medication:     { border: 'rgba(23,132,94,0.22)',  bg: 'rgba(23,132,94,0.09)',  text: '#0e6344', dot: '#17845e' },
  benefits:       { border: 'rgba(29,127,138,0.22)', bg: 'rgba(29,127,138,0.09)', text: '#14616a', dot: '#1d7f8a' },
  claims:         { border: 'rgba(154,106,16,0.22)', bg: 'rgba(154,106,16,0.09)', text: '#7d5406', dot: '#b07c14' },
  providers:      { border: 'rgba(110,60,130,0.2)',  bg: 'rgba(110,60,130,0.08)', text: '#5d3a72', dot: '#7c4f96' },
  safety:         { border: 'rgba(180,35,47,0.22)',  bg: 'rgba(180,35,47,0.07)',  text: '#9c1f2a', dot: '#c23440' },
};
