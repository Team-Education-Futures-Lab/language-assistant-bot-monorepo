import React, { useState } from 'react';

const SubjectList = ({ subjects, selectedId, onSelect, onRefresh }) => {
  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="p-6 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-800">Onderwerpen</h2>
      </div>

      <div className="divide-y divide-gray-200">
        {subjects.map(subject => (
          <button
            key={subject.id}
            onClick={() => onSelect(subject)}
            className={`w-full text-left p-4 hover:bg-gray-50 transition ${
              selectedId === subject.id ? 'bg-blue-50 border-l-4 border-blue-600' : ''
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0 pr-4">
                <h3 className="font-medium text-gray-800 truncate" title={subject.name}>{subject.name}</h3>
                <p className="text-sm text-gray-600 mt-1 line-clamp-2" title={subject.description}>{subject.description}</p>
                <p className="text-xs text-gray-500 mt-2 truncate">{subject.chunk_count} chunks</p>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-2xl font-bold text-gray-300">{subject.chunk_count}</p>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

export default SubjectList;
