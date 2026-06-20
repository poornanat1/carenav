import { Cpu } from 'lucide-react';
import type { TurnResponse } from '../types';
import { SYSTEM_CONFIG } from '../systemConfig';
import { Label, Row, tabBodyStyle } from './shared';

export function SystemTab({ lastResponse }: { lastResponse: TurnResponse | null }) {
  const fields: [string, string][] = lastResponse ? [
    ['intent', lastResponse.intent ?? 'none'],
    ['safety_flag', lastResponse.safety_flag],
    ['grounded', String(lastResponse.grounded)],
    ['escalated', String(lastResponse.escalated)],
    ['tier_used', lastResponse.tier_used],
    ['confidence', `${Math.round(lastResponse.confidence * 100)}%`],
    ['cost_usd', `$${lastResponse.cost_usd.toFixed(5)}`],
  ] : [];

  return (
    <div style={tabBodyStyle}>
      <div style={{ marginBottom: 16 }}>
        <Label>Provider config</Label>
        <Row label="provider" value={SYSTEM_CONFIG.provider} mono />
        <Row label="small_model" value={SYSTEM_CONFIG.smallModel} mono />
        <Row label="frontier_model" value={SYSTEM_CONFIG.frontierModel} mono />
        <Row label="rag" value={SYSTEM_CONFIG.rag} mono />
      </div>
      {lastResponse ? (
        <div>
          <Label>Latest turn</Label>
          {fields.map(([label, val]) => <Row key={label} label={label} value={val} mono />)}
        </div>
      ) : (
        <div style={{ textAlign: 'center', marginTop: 20 }}>
          <Cpu size={20} color="var(--cn-subtle)" style={{ margin: '0 auto 8px' }} />
          <p style={{ fontSize: 10, color: 'var(--cn-muted)', fontFamily: 'var(--font-mono)' }}>no turn data</p>
        </div>
      )}
    </div>
  );
}
