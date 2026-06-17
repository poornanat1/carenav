import { MEMBERS, MEMBER_DETAILS, SUGGESTED_QUESTIONS } from './data';
import type { Member, MemberDetail, SuggestedQuestion, TurnResponse } from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ''}`);
  }
  return res.json() as Promise<T>;
}

export async function healthCheck(): Promise<boolean> {
  try {
    await request<{ status: string }>('/health');
    return true;
  } catch {
    return false;
  }
}

export async function listMembers(): Promise<Member[]> {
  try {
    return await request<Member[]>('/members');
  } catch {
    return MEMBERS;
  }
}

export async function listSuggestedQuestions(member: Member): Promise<SuggestedQuestion[]> {
  try {
    const questions = await request<SuggestedQuestion[]>(`/members/${encodeURIComponent(member.id)}/suggested-questions`);
    return questions.length > 0 ? questions : SUGGESTED_QUESTIONS[member.id] ?? [];
  } catch {
    return SUGGESTED_QUESTIONS[member.id] ?? [];
  }
}

export function detailFor(member: Member): MemberDetail | null {
  if (member.detail) return member.detail;
  if (member.deductible && member.oop) {
    return {
      planType: member.plan_type ?? member.plan,
      deductible: member.deductible,
      oop: member.oop,
      medications: member.medications ?? [],
      conditions: member.conditions ?? [],
      kbTopics: member.kb_topics ?? [],
      recentClaims: member.recent_claims ?? [],
      recentProviders: member.recent_providers ?? [],
      note: member.note ?? member.summary,
    };
  }
  return MEMBER_DETAILS[member.id] ?? null;
}

export async function callTurn(
  question: string,
  memberRef?: string,
  memberId?: string,
): Promise<TurnResponse> {
  return request<TurnResponse>('/turn', {
    method: 'POST',
    body: JSON.stringify({
      question,
      member_ref: memberRef || null,
      member_id: memberId || null,
    }),
  });
}
