import type { Message } from '../types';
import { LoadingBubble } from './LoadingBubble';
import { ErrorBubble } from './ErrorBubble';
import { EscalationBubble } from './EscalationBubble';
import { AnswerBubble } from './AnswerBubble';

// Thin dispatcher: picks the bubble variant for an assistant message based on its
// machine-readable state. Each branch's markup lives in its own component.
export function AssistantBubble({ msg }: { msg: Message }) {
  if (msg.loading) return <LoadingBubble />;
  if (msg.error) return <ErrorBubble />;
  if (msg.response?.escalated) return <EscalationBubble r={msg.response} />;
  return <AnswerBubble msg={msg} />;
}
