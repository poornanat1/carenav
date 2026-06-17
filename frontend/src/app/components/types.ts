export type Member = {
  id: string;
  name: string;
  age: number;
  plan: string;
  summary: string;
  member_ref?: string;
  plan_type?: string;
  deductible?: { used: number; total: number };
  oop?: { used: number; total: number };
  medications?: string[];
  conditions?: string[];
  kb_topics?: string[];
  recent_claims?: ClaimRecord[];
  recent_providers?: { name: string; specialty: string }[];
  note?: string;
  detail?: MemberDetail;
};

export type SuggestedQuestion = {
  label: string;
  question: string;
  intent: string;
};

export type Citation = {
  chunk_id: string;
  title: string;
  source_url?: string | null;
  excerpt?: string | null;
};

export type Handoff = {
  reason: string;
  suspected_intent: string | null;
  safety_flag: string;
  gathered: string[];
};

export type TurnResponse = {
  answer: string;
  intent: string | null;
  grounded: boolean;
  escalated: boolean;
  citations: Citation[];
  handoff: Handoff | null;
  tier_used: string;
  safety_flag: string;
  confidence: number;
  cost_usd: number;
};

export type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  response?: TurnResponse;
  timestamp: Date;
  loading?: boolean;
  error?: boolean;
};

export type ClaimRecord = {
  description: string;
  date: string;
  amount: number;
  status: string;
};

export type MemberDetail = {
  planType: string;
  deductible: { used: number; total: number };
  oop: { used: number; total: number };
  medications: string[];
  conditions?: string[];
  kbTopics?: string[];
  recentClaims: ClaimRecord[];
  recentProviders: { name: string; specialty: string }[];
  note: string;
};
