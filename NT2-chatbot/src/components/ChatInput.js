import React, { useState, useRef } from 'react';
import { Send, Mic, SlidersHorizontal } from 'lucide-react';

const SHOW_TYPING_INPUT = false;

export default function ChatInput({
  onSend,
  disabled,
  onStartRecording,
  onEndSession,
  playbackSpeed = 1,
  onPlaybackSpeedChange,
  isRecording,
  isConnecting,
  isConnected,
  awaitingResponse,
  statusText,
}) {
  const [input, setInput] = useState('');
  const textareaRef = useRef(null);
  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput('');
      if (textareaRef.current) textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleInput = (e) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
  };

  const handleMicClick = () => {
    if (disabled || isConnecting || isConnected) return;
    onStartRecording();
  };

  const showEndButton = isConnected;
  const speedLabel = `${Number(playbackSpeed || 1).toFixed(3)}x`;

  return (
    <div className="sticky bottom-0 px-4 py-5 bg-gradient-to-t from-white to-white/95 border-t border-transparent">
      <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
        <div className="flex items-end gap-2 p-3 border border-app-border rounded-[28px] bg-white transition-all duration-200 focus-within:border-app-accent focus-within:shadow-[0_2px_12px_rgba(16,163,127,0.15)]" style={{ boxShadow: '0 2px 6px rgba(0, 0, 0, 0.05)' }}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Typ je bericht..."
            rows={1}
            disabled={disabled || isRecording}
            className={`${SHOW_TYPING_INPUT ? 'flex-1 border-none bg-transparent text-base leading-relaxed resize-none max-h-52 min-h-6 py-2 px-0 text-app-text-primary placeholder-gray-500 focus:outline-none focus-ring' : 'hidden'}`}
          />
          <button 
            type="button"
            onClick={handleMicClick}
            disabled={disabled || isConnecting || isConnected}
            className={`relative p-2 border-none cursor-pointer rounded-full flex items-center justify-center transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed ripple ${isRecording ? 'text-white bg-sky-500' : 'bg-transparent hover:bg-gray-100 hover:text-app-text-primary text-gray-500'}`}
            title="Opname starten"
          >
            {isConnecting && <span className="mic-ring mic-ring-connecting" />}
            {isRecording && <span className="mic-ring mic-ring-connected" />}
            <Mic size={18} />
          </button>

          <div className="relative group/speed">
            <button
              type="button"
              aria-label="Spreeksnelheid"
              title={`Spreeksnelheid (${speedLabel})`}
              className="p-2 border-none cursor-pointer rounded-full flex items-center justify-center transition-all duration-200 text-gray-500 hover:bg-gray-100 hover:text-app-text-primary"
            >
              <SlidersHorizontal size={18} />
            </button>

            <div className="absolute left-1/2 bottom-full -translate-x-1/2 opacity-0 scale-95 transition-all duration-150 group-hover/speed:opacity-100 group-hover/speed:scale-100">
              <div className="w-16 rounded-xl border border-app-border bg-white shadow-lg px-2 py-3 flex flex-col items-center gap-2">
                <span className="text-[11px] font-medium text-app-text-secondary">{speedLabel}</span>
                <div className="h-28 w-8 flex items-center justify-center">
                  <input
                    id="voice-speed"
                    type="range"
                    min={0.25}
                    max={1.5}
                    step={0.001}
                    value={playbackSpeed}
                    onChange={(event) => onPlaybackSpeedChange?.(event.target.value)}
                    className="h-24 w-24 -rotate-90 accent-app-accent cursor-pointer"
                  />
                </div>
              </div>
            </div>
          </div>

          {showEndButton && (
            <button
              type="button"
              onClick={onEndSession}
              aria-label="End Voice"
              className="rounded-full overflow-hidden h-9 px-3 flex flex-row items-center justify-center gap-2 hover:opacity-80 font-semibold transition-colors duration-300 bg-app-text-primary text-white"
            >
              <span className="h-2.5 w-2.5 rounded-full bg-white" />
              End
            </button>
          )}

          <button 
            type="submit" 
            disabled={!input.trim() || disabled || isRecording || awaitingResponse}
            className={`${SHOW_TYPING_INPUT ? 'p-2 border-none rounded flex items-center justify-center transition-all duration-200 ripple' : 'hidden'} ${input.trim() && !disabled && !isRecording ? 'bg-app-accent text-white cursor-pointer hover:bg-app-accent-hover' : 'bg-transparent text-gray-500 cursor-not-allowed'}`}
          >
            <Send size={18} />
          </button>
        </div>
        {!!statusText && <p className="text-center mt-2 text-xs text-app-text-secondary">{statusText}</p>}
        <p className="text-center mt-2 text-xs text-app-text-secondary">De chatbot kan fouten maken. Controleer belangrijke informatie altijd.</p>
      </form>
    </div>
  );
}
