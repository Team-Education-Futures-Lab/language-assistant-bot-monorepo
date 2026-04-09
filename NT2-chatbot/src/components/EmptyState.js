import React from 'react';

export default function EmptyState({ onSuggestionClick }) {
  void onSuggestionClick;

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-10 max-w-3xl mx-auto w-full bg-app-bg">
      <h1 className="text-4xl font-semibold mb-4 text-app-text-primary animate-fadeIn text-center">
        Hoe kan ik je vandaag helpen?
      </h1>
      <div className="text-app-text-secondary text-center text-base animate-fadeIn">
        Stel je vraag hieronder en ik help je direct verder.
      </div>
    </div>
  );
}
