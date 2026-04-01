import React, { useState, useRef, useEffect } from 'react';
import { Plus } from 'lucide-react';
import Sidebar from './components/Sidebar';
import Message from './components/Message';
import ChatInput from './components/ChatInput';
import EmptyState from './components/EmptyState';
import SpeechPage from './components/SpeechPage';
import LiveSpeechPage from './components/LiveSpeechPage';
import { queryBackendAPI } from './api';
import useStreamingVoiceChat from './hooks/useStreamingVoiceChat';


function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [activePage, setActivePage] = useState('chat');
  const [isStartingNewConversation, setIsStartingNewConversation] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const pendingActiveRef = useRef(null);
  const activeConversationIdRef = useRef(null);
  const liveVoiceRef = useRef({
    conversationId: null,
    userMessageId: null,
    assistantMessageId: null,
  });

  const generateId = (prefix = '') => `${Date.now()}-${Math.random().toString(36).slice(2,8)}${prefix ? `-${prefix}` : ''}`;

  const activeConversation = conversations.find(c => c.id === activeConversationId);

  useEffect(() => {
    activeConversationIdRef.current = activeConversationId;
  }, [activeConversationId]);

  const scrollToMessage = (messageId, block = 'start') => {
    setTimeout(() => {
      try {
        const element = document.querySelector(`[data-message-id="${messageId}"]`);
        if (element) element.scrollIntoView({ behavior: 'smooth', block });
      } catch (error) {
      }
    }, 80);
  };

  const resetLiveVoiceState = () => {
    liveVoiceRef.current = {
      conversationId: null,
      userMessageId: null,
      assistantMessageId: null,
    };
  };

  const ensureLiveVoiceConversation = () => {
    if (liveVoiceRef.current.conversationId && liveVoiceRef.current.userMessageId) {
      return liveVoiceRef.current;
    }

    const existingConversationId = activeConversationIdRef.current || pendingActiveRef.current || null;
    const conversationId = existingConversationId || generateId('conv');
    const userMessageId = generateId('msg');
    const userMessage = {
      id: userMessageId,
      role: 'user',
      content: 'Luisteren...',
      isComplete: false,
      streamLive: true,
      createdAt: Date.now(),
    };

    liveVoiceRef.current = {
      conversationId,
      userMessageId,
      assistantMessageId: null,
    };

    if (!existingConversationId) {
      const newConversation = {
        id: conversationId,
        title: 'Spraakchat',
        messages: [userMessage],
        createdAt: Date.now(),
      };

      pendingActiveRef.current = conversationId;
      setConversations((prev) => [newConversation, ...prev]);
      setActiveConversationId(conversationId);
      setActivePage('chat');
      if (isStartingNewConversation) setIsStartingNewConversation(false);
    } else {
      setConversations((prev) => prev.map((conversation) => (
        conversation.id === conversationId
          ? { ...conversation, messages: [...conversation.messages, userMessage] }
          : conversation
      )));
    }

    scrollToMessage(userMessageId, 'start');
    return liveVoiceRef.current;
  };

  const updateLiveVoiceUserMessage = (content, isComplete = false) => {
    const { conversationId, userMessageId } = ensureLiveVoiceConversation();
    setConversations((prev) => prev.map((conversation) => {
      if (conversation.id !== conversationId) return conversation;
      return {
        ...conversation,
        title: isComplete && content ? content.slice(0, 30) : conversation.title,
        messages: conversation.messages.map((message) => (
          message.id === userMessageId
            ? { ...message, content, isComplete, streamLive: !isComplete }
            : message
        )),
      };
    }));
  };

  const ensureLiveVoiceAssistantMessage = () => {
    const liveVoiceState = ensureLiveVoiceConversation();
    if (liveVoiceState.assistantMessageId) return liveVoiceState.assistantMessageId;

    const assistantMessageId = generateId('msg');
    liveVoiceRef.current = {
      ...liveVoiceState,
      assistantMessageId,
    };

    const assistantPlaceholder = {
      id: assistantMessageId,
      role: 'assistant',
      content: 'Antwoord genereren...',
      isComplete: false,
      shouldAnimate: false,
      streamLive: true,
      createdAt: Date.now(),
    };

    setConversations((prev) => prev.map((conversation) => (
      conversation.id === liveVoiceState.conversationId
        ? { ...conversation, messages: [...conversation.messages, assistantPlaceholder] }
        : conversation
    )));
    scrollToMessage(assistantMessageId, 'center');
    return assistantMessageId;
  };

  const updateLiveVoiceAssistantMessage = (content, isComplete = false) => {
    const assistantMessageId = ensureLiveVoiceAssistantMessage();
    const { conversationId } = liveVoiceRef.current;

    setConversations((prev) => prev.map((conversation) => {
      if (conversation.id !== conversationId) return conversation;
      return {
        ...conversation,
        messages: conversation.messages.map((message) => (
          message.id === assistantMessageId
            ? {
                ...message,
                content,
                isComplete,
                streamLive: !isComplete,
                shouldAnimate: false,
              }
            : message
        )),
      };
    }));
  };

  const streamingVoice = useStreamingVoiceChat({
    onSessionStarted: () => {
      ensureLiveVoiceConversation();
    },
    onTranscriptDelta: (event) => {
      updateLiveVoiceUserMessage(event.transcript || 'Luisteren...', false);
    },
    onTranscriptFinal: (event) => {
      updateLiveVoiceUserMessage(event.transcript || 'Geen transcriptie ontvangen', true);
    },
    onAssistantResponseStarted: () => {
      ensureLiveVoiceAssistantMessage();
    },
    onAssistantTextDelta: (event) => {
      updateLiveVoiceAssistantMessage(event.text || '', false);
    },
    onAssistantTextFinal: (event) => {
      updateLiveVoiceAssistantMessage(event.text || '', true);
    },
    onResponseDone: () => {
      resetLiveVoiceState();
    },
    onError: () => {
      // Realtime voice errors are shown in the status panel, not as chat messages.
      resetLiveVoiceState();
    },
  });


  // NOTE: do not auto-scroll on every conversation change. We'll only auto-scroll
  // immediately after the user sends a message so the user sees their own message.
  // During assistant generation we intentionally reserve space and let the user
  // scroll to see the full response (Chatbot-like behavior).

  // Clear pending active ref when activeConversationId is set
  useEffect(() => {
    if (activeConversationId && pendingActiveRef.current === activeConversationId) {
      pendingActiveRef.current = null;
    }
  }, [activeConversationId]);

  const createNewChat = () => {
    // Do not create a conversation yet — wait until the user sends the first message.
    // This toggles a compose/new-chat mode so the main area shows an empty composer.
    setIsStartingNewConversation(true);
    // Ensure no conversation is selected while composing a brand new chat
    setActiveConversationId(null);
    // Switch to chat page when creating new chat
    setActivePage('chat');
  };

  const handleSendMessage = async (content) => {
    // Use activeConversationId if available, otherwise fallback to pending created id
    const convId = activeConversationId || pendingActiveRef.current || null;

    if (!convId) {
      // No conversation exists or pending - create one and insert the user message immediately
      const newId = generateId('conv');
      const userMessage = {
        id: generateId('msg'),
        role: 'user',
        content,
        isComplete: true
      };

      const newConversation = {
        id: newId,
        title: content.slice(0, 30),
        messages: [userMessage],
        createdAt: Date.now()
      };

      // mark pending so rapid send after creation uses this id
      pendingActiveRef.current = newId;
      setConversations(prev => [newConversation, ...prev]);
      setActiveConversationId(newId);
      // If we were in the 'starting new conversation' mode, clear that state now that the convo exists
      if (isStartingNewConversation) setIsStartingNewConversation(false);

      // After the DOM updates, scroll the user's message into view at the top so the
      // reserved assistant placeholder sits just below it. This keeps the user's
      // message visible at the top while the user can scroll inside the reserved area.
      setTimeout(() => {
        try {
          const el = document.querySelector(`[data-message-id="${userMessage.id}"]`);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (e) {
          // ignore
        }
      }, 80);

      // Query the backend API for AI response
      setIsGenerating(true);
      const aiMessageId = generateId('msg');
      const aiPlaceholder = {
        id: aiMessageId,
        role: 'assistant',
        content: 'Antwoord laden...',
        isComplete: false,
        shouldAnimate: false,
        reservedSpace: true,
        reservedHeight: 300,
        createdAt: Date.now()
      };

      setConversations(prev => prev.map(c => c.id === newId ? { ...c, messages: [...c.messages, aiPlaceholder] } : c));

      // Auto-scroll to reserved space after it's rendered
      setTimeout(() => {
        try {
          const el = document.querySelector(`[data-message-id="${aiMessageId}"]`);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } catch (e) {
          // ignore
        }
      }, 50);

      // Call the backend API
      // Don't update state during streaming to avoid flickering - just ignore chunks
      const apiResult = await queryBackendAPI(content, () => {
        // Do nothing during streaming - we'll update state only when complete
      });

      // Update state only once with the complete response
      if (apiResult.success) {
        setConversations(prev => prev.map(c => c.id === newId ? { ...c, messages: c.messages.map(m => m.id === aiMessageId ? { 
          ...m, 
          content: apiResult.answer, 
          isComplete: true,
          shouldAnimate: true
        } : m) } : c));
      } else {
        setConversations(prev => prev.map(c => c.id === newId ? { ...c, messages: c.messages.map(m => m.id === aiMessageId ? { 
          ...m, 
          content: `Fout: ${apiResult.error || 'Kan geen antwoord ophalen van de server. Controleer of de Python-backend draait op localhost:5000.'}`,
          isComplete: true,
          shouldAnimate: false
        } : m) } : c));
      }

      setIsGenerating(false);
      return;
    }

    // Existing (or pending) conversation: append user message and placeholder
    const userMessage = {
      id: generateId('msg'),
      role: 'user',
      content,
      isComplete: true
    };

    setConversations(prev => prev.map(c => c.id === convId ? { ...c, messages: [...c.messages, userMessage], title: c.messages.length === 0 ? content.slice(0,30) : c.title } : c));

    // After the user's message is inserted, scroll it to the top of the chat
    // container so the reserved assistant placeholder is visible below it.
    setTimeout(() => {
      try {
        const el = document.querySelector(`[data-message-id="${userMessage.id}"]`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (e) {
        // ignore
      }
    }, 80);

    // Query the backend API for AI response
    setIsGenerating(true);
    const aiMessageId = generateId('msg');
    const aiPlaceholder = {
      id: aiMessageId,
      role: 'assistant',
      content: 'Antwoord laden...',
      isComplete: false,
      shouldAnimate: false,
      reservedSpace: true,
      reservedHeight: 300,
      createdAt: Date.now()
    };

    setConversations(prev => prev.map(c => c.id === convId ? { ...c, messages: [...c.messages, aiPlaceholder] } : c));

    // Auto-scroll to reserved space after it's rendered
    setTimeout(() => {
      try {
        const el = document.querySelector(`[data-message-id="${aiMessageId}"]`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } catch (e) {
        // ignore
      }
    }, 50);

    // Call the backend API
    // Don't update state during streaming to avoid flickering - just ignore chunks
    const apiResult = await queryBackendAPI(content, () => {
      // Do nothing during streaming - we'll update state only when complete
    });

    // Update state only once with the complete response
    if (apiResult.success) {
      setConversations(prev => prev.map(c => c.id === convId ? { ...c, messages: c.messages.map(m => m.id === aiMessageId ? { 
        ...m, 
        content: apiResult.answer, 
        isComplete: true,
        shouldAnimate: true
      } : m) } : c));
    } else {
      setConversations(prev => prev.map(c => c.id === convId ? { ...c, messages: c.messages.map(m => m.id === aiMessageId ? { 
        ...m, 
        content: `Fout: ${apiResult.error || 'Kan geen antwoord ophalen van de server. Controleer of de Python-backend draait op localhost:5000.'}`,
        isComplete: true,
        shouldAnimate: false
      } : m) } : c));
    }

    setIsGenerating(false);
  };

  const markAnimationDone = (convId, messageId) => {
    setConversations(prev => prev.map(c =>
      c.id === convId ? { ...c, messages: c.messages.map(m => m.id === messageId ? { ...m, shouldAnimate: false } : m) } : c
    ));
  };

  const editMessage = (convId, messageId, newContent) => {
    setConversations(prev => prev.map(c =>
      c.id === convId ? { ...c, messages: c.messages.map(m => m.id === messageId ? { ...m, content: newContent } : m) } : c
    ));
  };

  const deleteMessage = (convId, messageId) => {
    setConversations(prev => prev.map(c =>
      c.id === convId ? { ...c, messages: c.messages.filter(m => m.id !== messageId) } : c
    ));
  };

  // Fallback: mark assistant placeholders complete if they've been pending too long
  useEffect(() => {
    const TIMEOUT_MS = 8000; // if a placeholder is older than this, mark complete
    const timer = setInterval(() => {
      const now = Date.now();
      let changed = false;
      const updated = conversations.map(c => {
        const newMessages = c.messages.map(m => {
          if (m.role === 'assistant' && !m.isComplete && m.createdAt && (now - m.createdAt) > TIMEOUT_MS) {
            changed = true;
            return { ...m, isComplete: true };
          }
          return m;
        });
        return c.messages === newMessages ? c : { ...c, messages: newMessages };
      });
      if (changed) setConversations(updated);
    }, 1000);
    
    return () => clearInterval(timer);
  }, []);

  const deleteConversation = (id) => {
    const newConversations = conversations.filter(c => c.id !== id);
    setConversations(newConversations);
    if (activeConversationId === id) {
      if (newConversations.length > 0) {
        setActiveConversationId(newConversations[0].id);
      } else {
        setActiveConversationId(null);
      }
    }
  };

  const handleSelectChat = (id) => {
    setActiveConversationId(id);
    setActivePage('chat'); // Switch to chat page when selecting a conversation
  };

  const renameConversation = (id, newTitle) => {
    setConversations(conversations.map(c => 
      c.id === id ? { ...c, title: newTitle } : c
    ));
  };

  const handleSuggestionClick = (text) => {
    handleSendMessage(text);
  };

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-app-bg">
      <Sidebar
        conversations={[...conversations].sort((a,b) => b.createdAt - a.createdAt)}
        activeId={activeConversationId}
        currentPage={activePage}
        onSwitchPage={setActivePage}
        onNewChat={createNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={deleteConversation}
        onRenameChat={renameConversation}
        isOpen={sidebarOpen}
        onToggle={toggleSidebar}
      />

      <main className={`flex-1 ml-0 flex flex-col h-screen relative bg-app-bg transition-all duration-300 ${sidebarOpen ? 'ml-sidebar-width' : ''}`}>
        <header className="h-15 flex items-center px-4 border-b border-app-border bg-white sticky top-0 z-10">
          <div className="flex items-center w-10">
            {!sidebarOpen && (
              <button 
                className="p-2 border-none bg-transparent cursor-pointer text-app-text-secondary rounded hover:bg-gray-100 hover:text-app-text-primary flex items-center justify-center transition-all duration-200 ripple"
                onClick={createNewChat}
                title="Nieuwe chat"
              >
                <Plus size={20} />
              </button>
            )}
          </div>
          
          {/* Title hidden as requested - keeping header spacing */}
          <div style={{flex:1}} />
        </header>

        {activePage === 'chat' ? (
          <>
            <div className="flex-1 overflow-y-auto flex flex-col bg-app-bg" ref={messagesContainerRef}>
              {!activeConversation || activeConversation.messages.length === 0 ? (
                <EmptyState onSuggestionClick={handleSuggestionClick} />
              ) : (
                <div className="flex flex-col pb-5">
                  {activeConversation.messages.map((message, index) => (
                    <Message 
                      key={message.id} 
                      message={message} 
                      isNew={index === activeConversation.messages.length - 1}
                      conversationId={activeConversationId}
                      onEdit={editMessage}
                      onDelete={deleteMessage}
                      onAnimationDone={markAnimationDone}
                    />
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            <ChatInput 
              onSend={handleSendMessage} 
              disabled={isGenerating || streamingVoice.isBusy}
              onStartRecording={streamingVoice.startRecording}
              onEndSession={streamingVoice.endSession}
              isRecording={streamingVoice.isRecording}
              isConnecting={streamingVoice.isConnecting}
              isConnected={streamingVoice.isConnected}
              awaitingResponse={streamingVoice.awaitingResponse}
              statusText={streamingVoice.statusText}
            />
          </>
        ) : activePage === 'speech' ? (
          // placeholder for speech page component
          <div className="flex justify-center items-center h-full">
            {/* will render SpeechPage component via lazy import or directly later */}
            <SpeechPage />
          </div>
        ) : (
          <div className="flex justify-center items-start h-full overflow-y-auto py-6">
            <LiveSpeechPage />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;