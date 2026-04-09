import React, { useState, useEffect, memo } from 'react';

function AnimatedText({ text, isComplete, shouldAnimate = true, onDone, onProgress }) {
  const [displayedText, setDisplayedText] = useState('');
  const [showCursor, setShowCursor] = useState(true);
  const indexRef = React.useRef(0);
  const intervalRef = React.useRef(null);
  const onDoneRef = React.useRef(onDone);
  const onProgressRef = React.useRef(onProgress);

  useEffect(() => { onDoneRef.current = onDone; }, [onDone]);
  useEffect(() => { onProgressRef.current = onProgress; }, [onProgress]);

  useEffect(() => {
    if (!isComplete) return;

    // If we shouldn't animate, immediately render full text
    if (!shouldAnimate) {
      setDisplayedText(text);
      setShowCursor(false);
      if (onDoneRef.current) onDoneRef.current();
      return;
    }

    // reset state
    setDisplayedText('');
    setShowCursor(true);
    indexRef.current = 0;

    // Use interval to avoid race with frequent parent re-renders cancelling timers
    intervalRef.current = setInterval(() => {
      const i = indexRef.current;
      if (i < text.length) {
        setDisplayedText(prev => prev + text.charAt(i));
        indexRef.current = i + 1;
        if (onProgressRef.current) onProgressRef.current();
      } else {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
        setShowCursor(false);
        if (onDoneRef.current) onDoneRef.current();
      }
    }, 15);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [text, isComplete, shouldAnimate]);

  if (!isComplete) {
    return (
      <div className="loading-dots">
        <span></span>
        <span></span>
        <span></span>
      </div>
    );
  }

  return (
    <span className={showCursor ? 'cursor-blink' : ''}>
      {displayedText}
    </span>
  );
}

// Memoize to prevent unnecessary re-renders
const arePropsEqual = (prevProps, nextProps) => {
  // Re-render only when these props change
  if (prevProps.text !== nextProps.text ||
      prevProps.isComplete !== nextProps.isComplete ||
      prevProps.shouldAnimate !== nextProps.shouldAnimate) {
    return false;
  }
  return true;
};

export default memo(AnimatedText, arePropsEqual);
