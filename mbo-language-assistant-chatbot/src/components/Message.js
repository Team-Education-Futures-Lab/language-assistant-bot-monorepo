import React, { useState, memo, useEffect } from 'react';
import { Bot, Copy, ThumbsUp, ThumbsDown, RotateCcw, Edit3, Trash2 } from 'lucide-react';
import AnimatedText from './AnimatedText';

function Message({ message, isNew, onEdit, onDelete, conversationId, onAnimationDone }) {
  const isUser = message.role === 'user';
  const normalizedContent = (message.content || '').trim().toLowerCase();
  const showUserListeningAnimation = isUser && message.streamLive && (!normalizedContent || normalizedContent === 'luisteren...');
  const [copied, setCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(message.content || '');
  const [displayContent, setDisplayContent] = useState(message.content || '');
  
  useEffect(() => {
    if (isUser || message.streamLive || !message.isComplete || message.shouldAnimate || message.isComplete) {
      setDisplayContent(message.content || '');
    }
  }, [isUser, message.streamLive, message.shouldAnimate, message.isComplete, message.content]);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="py-2 px-4 md:px-6 group"
      data-message-id={message.id}
    >
      <div className="max-w-4xl mx-auto flex flex-col">
        {!isUser && (
          <div className="flex items-center gap-2 mb-1.5 text-app-text-secondary">
            <div className="w-6 h-6 rounded-md bg-app-accent text-white flex items-center justify-center">
              <Bot size={14} />
            </div>
            <span className="text-xs font-medium">Assistent</span>
          </div>
        )}

        <div className={`flex-1 min-w-0 ${isUser ? 'flex flex-col items-end' : ''}`}>

          <div className={`text-base leading-relaxed text-app-text-primary whitespace-pre-wrap ${isUser ? 'max-w-[72%] rounded-[22px] px-4 py-2.5 bg-[#e9eef6]' : ''}`}>
            {isUser ? (
              <div className="text-base leading-relaxed text-app-text-primary">
                {isEditing ? (
                  <div className="flex flex-col gap-2">
                    <textarea
                      className="w-full px-2.5 py-2 rounded border border-app-border resize min-h-12 focus:outline-none focus:ring-2 focus:ring-app-accent"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      rows={2}
                    />
                    <div className="flex gap-2 justify-end">
                      <button className="px-2.5 py-1.5 rounded bg-app-accent text-white cursor-pointer hover:bg-app-accent-hover transition-colors duration-200 ripple" onClick={() => {
                        if (editValue.trim()) onEdit && onEdit(conversationId, message.id, editValue.trim());
                        setIsEditing(false);
                      }}>Opslaan</button>
                      <button className="px-2.5 py-1.5 rounded bg-transparent text-app-text-primary cursor-pointer hover:bg-gray-100 transition-colors duration-200 ripple" onClick={() => { setIsEditing(false); setEditValue(message.content); }}>Annuleren</button>
                    </div>
                  </div>
                ) : (
                  showUserListeningAnimation ? (
                    <div className="voice-listening-message" aria-live="polite">
                      <span className="voice-listening-message-bars" aria-hidden="true">
                        <span />
                        <span />
                        <span />
                        <span />
                      </span>
                    </div>
                  ) : (
                    <p>{message.content}</p>
                  )
                )}
              </div>
            ) : (
              <div className="text-base leading-relaxed">
                {message.reservedSpace ? (
                  <div className="overflow-visible p-3 bg-transparent rounded" style={{ minHeight: (message.reservedHeight || 300) + 'px' }}>
                    {!message.isComplete && !message.streamLive ? (
                      <div className="w-full h-full" />
                    ) : (
                      <div className="whitespace-pre-wrap text-base leading-relaxed text-app-text-primary">
                        {message.isComplete && message.shouldAnimate ? (
                          <AnimatedText
                            text={displayContent}
                            isComplete={message.isComplete}
                            shouldAnimate={message.shouldAnimate}
                            onDone={() => { if (onAnimationDone) onAnimationDone(conversationId, message.id); }}
                          />
                        ) : (
                          displayContent
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  message.isComplete && message.shouldAnimate ? (
                    <AnimatedText
                      text={displayContent}
                      isComplete={message.isComplete}
                      shouldAnimate={message.shouldAnimate}
                      onDone={() => { if (onAnimationDone) onAnimationDone(conversationId, message.id); }}
                    />
                  ) : (
                    <div className="whitespace-pre-wrap">{displayContent}</div>
                  )
                )}
              </div>
            )}
          </div>

          <div className={`flex gap-2 mt-2 opacity-0 pointer-events-none -translate-y-1.5 transition-all duration-200 group-hover:opacity-100 group-hover:pointer-events-auto group-hover:translate-y-0 ${isUser ? 'justify-end w-full' : ''}`}>
            {isUser ? (
              <>
                <button className="relative p-1.5 border-none bg-transparent cursor-pointer text-app-text-secondary rounded hover:bg-gray-100 hover:text-app-text-primary flex items-center justify-center transition-all duration-200 ripple" title="Bewerken" onClick={(e) => { e.stopPropagation(); setIsEditing(true); }}>
                  <Edit3 size={14} />
                </button>
                <button className="relative p-1.5 border-none bg-transparent cursor-pointer text-app-text-secondary rounded hover:bg-gray-100 hover:text-app-text-primary flex items-center justify-center transition-all duration-200 ripple" title="Verwijderen" onClick={(e) => { e.stopPropagation(); onDelete && onDelete(conversationId, message.id); }}>
                  <Trash2 size={14} />
                </button>
              </>
            ) : (
              message.isComplete && (
                <>
                  <button className="relative p-1.5 border-none bg-transparent cursor-pointer text-app-text-secondary rounded hover:bg-gray-100 hover:text-app-text-primary flex items-center justify-center transition-all duration-200 ripple" onClick={handleCopy} title="Kopieren"><Copy size={14} />{copied && <span className="tooltip">Gekopieerd!</span>}</button>
                  <button className="relative p-1.5 border-none bg-transparent cursor-pointer text-app-text-secondary rounded hover:bg-gray-100 hover:text-app-text-primary flex items-center justify-center transition-all duration-200 ripple" title="Goed antwoord"><ThumbsUp size={14} /></button>
                  <button className="relative p-1.5 border-none bg-transparent cursor-pointer text-app-text-secondary rounded hover:bg-gray-100 hover:text-app-text-primary flex items-center justify-center transition-all duration-200 ripple" title="Slecht antwoord"><ThumbsDown size={14} /></button>
                  <button className="relative p-1.5 border-none bg-transparent cursor-pointer text-app-text-secondary rounded hover:bg-gray-100 hover:text-app-text-primary flex items-center justify-center transition-all duration-200 ripple" title="Opnieuw genereren"><RotateCcw size={14} /></button>
                </>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Custom memo comparison to prevent unnecessary re-renders
// Only care about message structure changes, not content changes during streaming
const arePropsEqual = (prevProps, nextProps) => {
  // Always re-render if these critical props change
  if (prevProps.isNew !== nextProps.isNew || 
      prevProps.message.id !== nextProps.message.id ||
      prevProps.message.isComplete !== nextProps.message.isComplete ||
      prevProps.message.shouldAnimate !== nextProps.message.shouldAnimate ||
      prevProps.message.content !== nextProps.message.content ||
      prevProps.message.streamLive !== nextProps.message.streamLive) {
    return false;
  }
  
  // Don't re-render just because content changed (it's handled by useEffect/displayContent)
  return true;
};

export default memo(Message, arePropsEqual);
