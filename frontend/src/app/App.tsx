import { useState, useCallback, useEffect } from 'react';
import { TopBar } from './components/TopBar';
import { MemberSelector } from './components/MemberSelector';
import { ChatPanel } from './components/ChatPanel';
import { RightPanel } from './components/RightPanel';
import { Composer } from './components/Composer';
import {
  callTurn,
  healthCheck,
  listMembers,
  listProviders,
  listSuggestedQuestions,
} from './components/api';
import { useIsMobile } from './components/useMediaQuery';
import type { Member, Message, SuggestedQuestion } from './components/types';

type RightTab = 'member' | 'evidence' | 'system';

let msgCounter = 0;
function newId() {
  return `msg_${++msgCounter}_${Date.now()}`;
}

export default function App() {
  const [member, setMember] = useState<Member | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [suggestions, setSuggestions] = useState<SuggestedQuestion[]>([]);
  const [apiOnline, setApiOnline] = useState(false);
  const [loading, setLoading] = useState(false);
  const [rightTab, setRightTab] = useState<RightTab>('member');
  const [pendingQuestion, setPendingQuestion] = useState('');
  const [panelOpen, setPanelOpen] = useState(false);
  const isMobile = useIsMobile();

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      const [online, loadedMembers] = await Promise.all([healthCheck(), listMembers()]);
      if (cancelled) return;
      setApiOnline(online);
      setMembers(loadedMembers);
    }
    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  function handleMemberSelect(m: Member) {
    setMember(m);
    setMessages([]);
    setSuggestions([]);
    setRightTab('member');
    setPanelOpen(false);
    listSuggestedQuestions(m).then(setSuggestions).catch(() => setSuggestions([]));
    // Provider recommendations are fetched lazily per member so the /members list stays fast.
    listProviders(m)
      .then((providers) => {
        const withProviders: Member = { ...m, recent_providers: providers };
        setMember((current) => (current?.id === m.id ? withProviders : current));
        setMembers((prev) => prev.map((x) => (x.id === m.id ? withProviders : x)));
      })
      .catch(() => undefined);
  }

  function handleReset() {
    setMessages([]);
    setRightTab('member');
  }

  const handleSend = useCallback(
    async (question: string) => {
      if (!member || loading) return;

      const userMsg: Message = {
        id: newId(),
        role: 'user',
        content: question,
        timestamp: new Date(),
      };
      const loadingId = newId();
      const loadingMsg: Message = {
        id: loadingId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        loading: true,
      };

      // Build conversation history (oldest first) from completed turns so a follow-up
      // like "what are the side effects?" resolves to its subject. Cap to recent turns.
      const history = messages
        .filter(m => !m.loading && !m.error)
        .map(m => ({
          role: m.role,
          content: m.role === 'assistant' ? m.response?.answer ?? m.content : m.content,
        }))
        .filter(h => h.content)
        .slice(-6) as { role: 'user' | 'assistant'; content: string }[];

      setMessages(prev => [...prev, userMsg, loadingMsg]);
      setLoading(true);

      try {
        const response = await callTurn(question, member.member_ref, member.id, history);
        setMessages(prev =>
          prev.map(m =>
            m.id === loadingId
              ? {
                  ...m,
                  loading: false,
                  content: response.answer,
                  response,
                }
              : m
          )
        );

        if (response.escalated) {
          setRightTab('system');
        } else if (response.citations.length > 0) {
          setRightTab('evidence');
        }
      } catch {
        setMessages(prev =>
          prev.map(m =>
            m.id === loadingId ? { ...m, loading: false, error: true } : m
          )
        );
      } finally {
        setLoading(false);
      }
    },
    [member, loading, messages]
  );

  function handleSuggestedClick(sq: SuggestedQuestion) {
    setPendingQuestion(sq.question);
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        fontFamily: 'var(--font-sans)',
<<<<<<< Updated upstream
        background: 'var(--cn-grad-canvas)',
=======
        background: 'var(--cn-bg)',
>>>>>>> Stashed changes
      }}
    >
      <TopBar
        onReset={handleReset}
        hasConversation={messages.length > 0}
        apiOnline={apiOnline}
        isMobile={isMobile}
        onOpenPanel={() => setPanelOpen(true)}
      />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', minHeight: 0 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
          <MemberSelector members={members} selected={member} onSelect={handleMemberSelect} />
          <ChatPanel
            messages={messages}
            member={member}
            suggestions={suggestions}
            onSuggestedClick={handleSuggestedClick}
          />
          <Composer
            member={member}
            suggestions={suggestions}
            loading={loading}
            onSend={handleSend}
            pendingQuestion={pendingQuestion}
            onPendingClear={() => setPendingQuestion('')}
          />
        </div>

        {!isMobile && (
          <RightPanel
            member={member}
            messages={messages}
            activeTab={rightTab}
            onTabChange={setRightTab}
          />
        )}
      </div>

      {isMobile && panelOpen && (
        <RightPanel
          member={member}
          messages={messages}
          activeTab={rightTab}
          onTabChange={setRightTab}
          mobile
          onClose={() => setPanelOpen(false)}
        />
      )}
    </div>
  );
}
