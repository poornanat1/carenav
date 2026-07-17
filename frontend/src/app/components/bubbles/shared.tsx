import React from 'react';
import { ExternalLink } from 'lucide-react';
import type { Citation, TurnResponse } from '../types';
import { citationRefMap, citationTooltip, groupCitations, sourceLabel } from '../citations';

// Human-readable copy for the orchestrator's escalation reason codes. Falls back to
// a de-snake-cased version of the raw code for any reason not listed here.
const HANDOFF_REASON_COPY: Record<string, string> = {
  member_context_required: 'This question is about a specific member. Select a member above, then ask again.',
  emergent_safety: 'This looks like a medical emergency. CareNav cannot give emergency advice — call 911 or your local emergency number now.',
  low_confidence: 'CareNav was not confident enough in an answer to give one safely. A care advocate can follow up.',
  out_of_scope: 'This is outside what CareNav can answer. CareNav covers care navigation, benefits, and selected member profile questions.',
};

export function handoffReasonText(reason: string): string {
  return HANDOFF_REASON_COPY[reason] ?? reason.replace(/_/g, ' ');
}

// Severity tier for an answer, derived only from machine-readable response signals
// (never from the answer text). Drives the alert treatment so important answers are
// visually unmistakable from routine ones:
//   emergent  — medical emergency; strongest red treatment + 911.
//   escalated — handed off for a non-emergency reason; amber caution, not full red.
//   urgent    — time-sensitive but still answered; amber banner atop a normal bubble.
//   none      — routine answer.
export type Severity = 'emergent' | 'escalated' | 'urgent' | 'none';

export function severityOf(r: TurnResponse): Severity {
  const isEmergent = r.safety_flag === 'emergent' || r.handoff?.reason === 'emergent_safety';
  if (isEmergent) return 'emergent';
  if (r.escalated) return 'escalated';
  if (r.safety_flag === 'urgent') return 'urgent';
  return 'none';
}

export const labelStyle: React.CSSProperties = {
  fontSize: 9,
  color: 'var(--cn-subtle)',
  fontFamily: 'var(--font-mono)',
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  marginBottom: 5,
};

// Speaker label above every assistant bubble; the gradient dot is the brand mark.
export function BubbleLabel({ children, color }: { children: React.ReactNode; color?: string }) {
  return (
    <div style={{ ...labelStyle, color: color ?? labelStyle.color, display: 'flex', alignItems: 'center', gap: 5 }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--cn-grad-brand)', flexShrink: 0 }} />
      {children}
    </div>
  );
}

export function LoadingDots() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 0' }}>
      {[0, 1, 2].map(i => (
        <div
          key={i}
          style={{
            width: 5,
            height: 5,
            borderRadius: '50%',
            background: 'var(--cn-muted)',
            animation: `cBounce 1.2s ${i * 0.2}s ease-in-out infinite`,
          }}
        />
      ))}
      <style>{`
        @keyframes cBounce {
          0%,80%,100%{transform:translateY(0);opacity:0.25}
          40%{transform:translateY(-5px);opacity:0.7}
        }
      `}</style>
    </div>
  );
}

function CitationMarker({ label, citation }: { label: string; citation?: Citation }) {
  return (
    <sup
      title={citationTooltip(citation, label)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: 14,
        height: 14,
        padding: '0 4px',
        borderRadius: 7,
        background: 'var(--cn-accent-soft)',
        color: 'var(--cn-accent-strong)',
        fontSize: 8,
        fontFamily: 'var(--font-mono)',
        fontWeight: 500,
        verticalAlign: 'super',
        marginLeft: 1,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </sup>
  );
}

export function renderAnswer(text: string, citations: Citation[]): React.ReactNode[] {
  const byChunkId = citationRefMap(citations);
  const tokenRe = /(\[CHUNK:([^\]]+)\]|\*\*(.+?)\*\*)/g;

  return text.split('\n').map((line, li, arr) => {
    const parts: React.ReactNode[] = [];
    let cursor = 0;
    let k = 0;

    for (const match of line.matchAll(tokenRe)) {
      const matchIndex = match.index ?? 0;
      if (matchIndex > cursor) {
        const nextIsCitation = Boolean(match[2]);
        const segment = line.slice(cursor, matchIndex);
        parts.push(<span key={k++}>{nextIsCitation ? segment.replace(/\s+$/, '') : segment}</span>);
      }

      if (match[2]) {
        const found = byChunkId.get(match[2]);
        if (found) {
          parts.push(
            <CitationMarker key={k++} label={found.label} citation={found.citation} />
          );
        }
      } else {
        parts.push(
          <strong key={k++} style={{ fontWeight: 700, color: 'var(--cn-ink)' }}>
            {match[3]}
          </strong>
        );
      }

      cursor = matchIndex + match[0].length;
    }

    if (cursor < line.length) {
      parts.push(<span key={k++}>{line.slice(cursor)}</span>);
    }

    return <span key={li}>{parts}{li < arr.length - 1 ? '\n' : ''}</span>;
  });
}

export function CitationChips({ citations }: { citations: Citation[] }) {
  const sources = groupCitations(citations);
  if (sources.length === 0) return null;

  return (
    <div
      style={{
        marginTop: 12,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        flexWrap: 'wrap',
      }}
    >
      <span
        style={{
          fontSize: 9,
          fontFamily: 'var(--font-mono)',
          color: 'var(--cn-subtle)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
        }}
      >
        Sources
      </span>
      {sources.map((source, i) => {
        const { citation } = source;
        const content = (
          <>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 15,
                height: 15,
                borderRadius: '50%',
                background: 'var(--cn-accent-soft)',
                color: 'var(--cn-accent-strong)',
                fontSize: 8,
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {i + 1}
            </span>
            <span
              style={{
                minWidth: 0,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {sourceLabel(citation)}
            </span>
            {citation.source_url ? <ExternalLink size={10} /> : null}
          </>
        );
        const style: React.CSSProperties = {
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          maxWidth: 220,
          padding: '3px 7px 3px 4px',
          borderRadius: 5,
          border: '1px solid var(--cn-border)',
          background: 'var(--cn-card-strong)',
          color: 'var(--cn-muted)',
          fontSize: 10,
          fontFamily: 'var(--font-sans)',
          fontWeight: 400,
          textDecoration: 'none',
        };

        return citation.source_url ? (
          <a
            key={source.key}
            href={citation.source_url}
            target="_blank"
            rel="noopener noreferrer"
            title={citation.title}
            style={style}
          >
            {content}
          </a>
        ) : (
          <span key={source.key} title={citation.title} style={style}>
            {content}
          </span>
        );
      })}
    </div>
  );
}
