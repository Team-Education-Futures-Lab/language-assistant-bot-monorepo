import React, { useState, useRef } from 'react';
import { Send, Mic, Gauge, BookOpen, GraduationCap } from 'lucide-react';

const SHOW_TYPING_INPUT = false;
const CEFR_LEVEL_OPTIONS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const SPEED_PRESETS = [0.8, 0.9, 1.0, 1.1, 1.2];

export default function ChatInput({
  onSend,
  disabled,
  onStartRecording,
  onEndSession,
  playbackSpeed = 1,
  onPlaybackSpeedChange,
  subjects = [],
  selectedSubjectId = null,
  selectedSubject = null,
  onSelectSubject,
  languageLevels = CEFR_LEVEL_OPTIONS,
  selectedLanguageLevel = 'B1',
  onSelectLanguageLevel,
  isRecording,
  isConnecting,
  isConnected,
  awaitingResponse,
  statusText,
}) {
  const [input, setInput] = useState('');
  const [isSubjectMenuOpen, setIsSubjectMenuOpen] = useState(false);
  const [isLevelMenuOpen, setIsLevelMenuOpen] = useState(false);
  const textareaRef = useRef(null);
  const subjectMenuCloseTimerRef = useRef(null);
  const levelMenuCloseTimerRef = useRef(null);
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
  const speedLabel = `${Number(playbackSpeed || 1).toFixed(2)}x`;
  const selectedSubjectLabel = selectedSubject?.name || 'Alle onderwerpen';

  const clearSubjectMenuCloseTimer = () => {
    if (subjectMenuCloseTimerRef.current) {
      window.clearTimeout(subjectMenuCloseTimerRef.current);
      subjectMenuCloseTimerRef.current = null;
    }
  };

  const openSubjectMenu = () => {
    clearSubjectMenuCloseTimer();
    setIsSubjectMenuOpen(true);
  };

  const closeSubjectMenu = () => {
    clearSubjectMenuCloseTimer();
    setIsSubjectMenuOpen(false);
  };

  const scheduleSubjectMenuClose = () => {
    clearSubjectMenuCloseTimer();
    subjectMenuCloseTimerRef.current = window.setTimeout(() => {
      setIsSubjectMenuOpen(false);
      subjectMenuCloseTimerRef.current = null;
    }, 120);
  };

  const clearLevelMenuCloseTimer = () => {
    if (levelMenuCloseTimerRef.current) {
      window.clearTimeout(levelMenuCloseTimerRef.current);
      levelMenuCloseTimerRef.current = null;
    }
  };

  const openLevelMenu = () => {
    clearLevelMenuCloseTimer();
    setIsLevelMenuOpen(true);
  };

  const closeLevelMenu = () => {
    clearLevelMenuCloseTimer();
    setIsLevelMenuOpen(false);
  };

  const scheduleLevelMenuClose = () => {
    clearLevelMenuCloseTimer();
    levelMenuCloseTimerRef.current = window.setTimeout(() => {
      setIsLevelMenuOpen(false);
      levelMenuCloseTimerRef.current = null;
    }, 120);
  };

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
              <Gauge size={18} />
            </button>

            <div className="absolute left-1/2 bottom-full mb-2 -translate-x-1/2 opacity-0 scale-95 transition-all duration-150 group-hover/speed:opacity-100 group-hover/speed:scale-100">
              <div className="w-52 rounded-xl border border-app-border bg-white shadow-lg px-3 py-3">
                <div className="flex flex-col gap-2.5">
                  <span className="text-center text-xs font-semibold text-app-text-secondary">{speedLabel}</span>
                  <input
                    id="voice-speed"
                    type="range"
                    min={0.25}
                    max={1.5}
                    step={0.001}
                    value={playbackSpeed}
                    onChange={(event) => onPlaybackSpeedChange?.(event.target.value)}
                    className="h-1.5 w-full accent-app-accent cursor-pointer"
                  />
                  <div className="grid grid-cols-5 gap-1.5">
                    {SPEED_PRESETS.map((preset) => {
                      const isActive = Math.abs(Number(playbackSpeed) - preset) < 0.001;
                      return (
                        <button
                          key={preset}
                          type="button"
                          onClick={() => onPlaybackSpeedChange?.(preset)}
                          className={`rounded-md px-1.5 py-1 text-[11px] font-medium transition-colors duration-150 ${isActive ? 'bg-app-accent text-white' : 'bg-slate-100 text-app-text-secondary hover:bg-slate-200'}`}
                        >
                          {preset % 1 === 0 ? String(preset.toFixed(0)) : String(preset)}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="relative inline-flex items-center">
            <button
              type="button"
              aria-label="Onderwerp voor retrieval"
              title={`Onderwerp voor retrieval: ${selectedSubjectLabel}`}
              onMouseEnter={openSubjectMenu}
              onMouseLeave={scheduleSubjectMenuClose}
              className={`h-9 min-w-[2.75rem] max-w-[13rem] px-3 border-none cursor-pointer rounded-full flex items-center gap-2 justify-center transition-all duration-200 ${selectedSubjectId ? 'text-app-text-primary bg-emerald-50 hover:bg-emerald-100' : 'text-gray-500 hover:bg-gray-100 hover:text-app-text-primary'}`}
            >
              <BookOpen size={17} />
              <span className="max-w-[9rem] truncate text-xs font-medium">
                {selectedSubjectLabel}
              </span>
            </button>

            {isSubjectMenuOpen && (
              <div
                className="absolute left-1/2 bottom-full z-30 mb-2 -translate-x-1/2"
                onMouseEnter={clearSubjectMenuCloseTimer}
                onMouseLeave={closeSubjectMenu}
              >
                <div className="w-48 rounded-xl border border-app-border bg-white shadow-[0_10px_24px_rgba(15,23,42,0.14)] px-2 py-2">
                <div className="max-h-56 overflow-y-auto rounded-lg border border-app-border bg-slate-50 p-1">
                  <button
                    type="button"
                    onClick={() => onSelectSubject?.(null)}
                    onMouseEnter={clearSubjectMenuCloseTimer}
                    className={`flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm transition-colors duration-150 hover:bg-white ${!selectedSubjectId ? 'bg-white text-app-text-primary shadow-sm' : 'text-app-text-secondary'}`}
                  >
                    <span>Alle onderwerpen</span>
                  </button>

                  <div className="my-1 h-px bg-app-border/70" />

                  {subjects.map((subject) => {
                    const isActive = selectedSubjectId === subject.id;
                    return (
                      <button
                        key={subject.id}
                        type="button"
                        onClick={() => onSelectSubject?.(subject.id)}
                        onMouseEnter={clearSubjectMenuCloseTimer}
                        className={`flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm transition-colors duration-150 hover:bg-white ${isActive ? 'bg-white text-app-text-primary shadow-sm' : 'text-app-text-secondary'}`}
                      >
                        <span className="min-w-0 truncate font-medium">{subject.name}</span>
                      </button>
                    );
                  })}
                </div>
                </div>
              </div>
            )}
          </div>

          <div className="relative inline-flex items-center">
            <button
              type="button"
              aria-label="Taalniveau"
              title={`Taalniveau: ${selectedLanguageLevel}`}
              onMouseEnter={openLevelMenu}
              onMouseLeave={scheduleLevelMenuClose}
              className="h-9 min-w-[2.75rem] max-w-[7rem] px-3 border-none cursor-pointer rounded-full flex items-center gap-2 justify-center transition-all duration-200 text-app-text-primary bg-cyan-50 hover:bg-cyan-100"
            >
              <GraduationCap size={16} />
              <span className="truncate text-xs font-semibold tracking-wide">{selectedLanguageLevel}</span>
            </button>

            {isLevelMenuOpen && (
              <div
                className="absolute left-1/2 bottom-full z-30 mb-2 -translate-x-1/2"
                onMouseEnter={clearLevelMenuCloseTimer}
                onMouseLeave={closeLevelMenu}
              >
                <div className="w-28 rounded-xl border border-app-border bg-white shadow-[0_10px_24px_rgba(15,23,42,0.14)] px-2 py-2">
                  <div className="max-h-56 overflow-y-auto rounded-lg border border-app-border bg-slate-50 p-1">
                    {languageLevels.map((level) => {
                      const isActive = String(selectedLanguageLevel).toUpperCase() === String(level).toUpperCase();
                      return (
                        <button
                          key={level}
                          type="button"
                          onClick={() => onSelectLanguageLevel?.(level)}
                          onMouseEnter={clearLevelMenuCloseTimer}
                          className={`flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm font-medium transition-colors duration-150 hover:bg-white ${isActive ? 'bg-white text-app-text-primary shadow-sm' : 'text-app-text-secondary'}`}
                        >
                          <span>{level}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
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
