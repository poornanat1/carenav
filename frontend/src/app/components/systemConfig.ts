// Hardcoded backend provider/model config surfaced in the UI.
//
// NOTE: this duplicates the backend's own configuration. It should ideally be
// fetched from the /health endpoint rather than hardcoded here, but until that
// is wired up these strings live in one place so the System tab and the top bar
// can't drift apart.
export const SYSTEM_CONFIG = {
  provider: 'Mistral',
  smallModel: 'mistral-small-latest',
  frontierModel: 'mistral-large-latest',
  rag: 'enabled',
} as const;

// Compact one-line summary shown in the top bar (e.g. "Mistral · RAG enabled").
export const PROVIDER_SUMMARY = `${SYSTEM_CONFIG.provider} · RAG ${SYSTEM_CONFIG.rag}`;
