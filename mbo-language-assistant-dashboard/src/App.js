import React, { useState, useEffect } from 'react';
import SubjectList from './components/SubjectList';
import SubjectForm from './components/SubjectForm';
import ChunkManager from './components/ChunkManager';
import SettingsPage from './components/SettingsPage';
import { Menu, X, Settings } from 'lucide-react';

function App() {
  const [subjects, setSubjects] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [apiConnected, setApiConnected] = useState(false);
  const [currentPage, setCurrentPage] = useState(() => {
    return localStorage.getItem('dashboardPage') || 'subjects';
  });
  const [sidebarWidth, setSidebarWidth] = useState(256); // Default 256px (w-64)
  const [isResizing, setIsResizing] = useState(false);

  const API_URL = 'http://localhost:5004';

  // Persist currentPage to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('dashboardPage', currentPage);
  }, [currentPage]);

  // Check API connection on component mount
  useEffect(() => {
    checkApiHealth();
  }, []);

  const checkApiHealth = async () => {
    try {
      const response = await fetch(`${API_URL}/health`);
      if (response.ok) {
        setApiConnected(true);
        fetchSubjects();
      }
    } catch (error) {
      setApiConnected(false);
      console.error('API not available:', error);
    }
  };

  // Fetch subjects on component mount
  const fetchSubjects = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/subjects`);
      const data = await response.json();
      setSubjects(data.subjects || []);
      setSelectedSubject(null);
    } catch (error) {
      console.error('Error fetching subjects:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    fetchSubjects();
  };

  const handleSubjectCreated = (newSubject) => {
    setSubjects([...subjects, newSubject]);
    setShowForm(false);
  };

  const handleSubjectUpdated = (updatedSubject) => {
    setSubjects(subjects.map(s => s.id === updatedSubject.id ? updatedSubject : s));
  };

  const handleSubjectDeleted = (subjectId) => {
    setSubjects(subjects.filter(s => s.id !== subjectId));
    setSelectedSubject(null);
  };

  const handleChunksUpdated = async () => {
    // Refresh the current subject's data without clearing selection
    if (selectedSubject) {
      try {
        const response = await fetch(`${API_URL}/subjects/${selectedSubject.id}`);
        const data = await response.json();
        if (data.subject) {
          setSelectedSubject(data.subject);
          // Also update the subject in the list
          setSubjects(subjects.map(s => s.id === selectedSubject.id ? data.subject : s));
        }
      } catch (error) {
        console.error('Error refreshing subject:', error);
      }
    }
  };

  // Resize handlers
  const startResizing = React.useCallback((e) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  const stopResizing = React.useCallback(() => {
    setIsResizing(false);
  }, []);

  const resize = React.useCallback((e) => {
    if (isResizing) {
      const newWidth = e.clientX;
      if (newWidth >= 200 && newWidth <= 600) {
        setSidebarWidth(newWidth);
      }
    }
  }, [isResizing]);

  useEffect(() => {
    window.addEventListener('mousemove', resize);
    window.addEventListener('mouseup', stopResizing);
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
    };
  }, [resize, stopResizing]);

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div
        style={{ 
          width: sidebarOpen ? `${sidebarWidth}px` : '80px',
          minWidth: sidebarOpen ? '200px' : '80px',
          maxWidth: sidebarOpen ? '600px' : '80px'
        }}
        className="bg-white border-r border-gray-200 transition-all duration-300 flex flex-col relative"
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            {sidebarOpen && (
              <h1 
                className="text-xl font-bold text-blue-600 cursor-pointer hover:text-blue-700 transition truncate"
                onClick={() => {
                  setCurrentPage('subjects');
                  setSelectedSubject(null);
                  setShowForm(false);
                }}
              >
                MBO Dashboard
              </h1>
            )}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 hover:bg-gray-100 rounded-lg transition"
            >
              {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {/* Status */}
        <div className={`${sidebarOpen ? 'p-4' : 'p-2'} border-b border-gray-200`}>
          {apiConnected ? (
            <div className="flex items-center gap-2 text-green-600 text-sm">
              <div className="w-2 h-2 bg-green-600 rounded-full"></div>
              {sidebarOpen && <span>Verbonden</span>}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-red-600 text-sm">
              <div className="w-2 h-2 bg-red-600 rounded-full animate-pulse"></div>
              {sidebarOpen && <span>Niet verbonden</span>}
            </div>
          )}
        </div>

        {/* New Subject Button */}
        <div className={`${sidebarOpen ? 'p-4' : 'p-2'}`}>
          <button
            onClick={() => {
              setCurrentPage('subjects');
              setShowForm(true);
            }}
            className={`w-full ${sidebarOpen ? 'px-4 py-2' : 'px-2 py-2'} bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium`}
          >
            {sidebarOpen ? '+ Nieuw Onderwerp' : '+'}
          </button>
        </div>

        {/* Subjects List */}
        <div className="flex-1 overflow-y-auto">
          {subjects.length > 0 ? (
            <div className={`${sidebarOpen ? 'p-4' : 'p-2'} space-y-2`}>
              {subjects.map((subject) => (
                <button
                  key={subject.id}
                  onClick={() => {
                    setCurrentPage('subjects');
                    setSelectedSubject(subject);
                  }}
                  className={`w-full text-left ${sidebarOpen ? 'p-3' : 'p-2'} rounded-lg transition ${
                    selectedSubject?.id === subject.id
                      ? 'bg-blue-100 text-blue-600 border border-blue-300'
                      : 'hover:bg-gray-100 border border-transparent'
                  }`}
                >
                  {sidebarOpen ? (
                    <>
                      <p className="font-medium text-sm truncate" title={subject.name}>{subject.name}</p>
                    </>
                  ) : (
                    <p className="text-xs font-medium truncate" title={subject.name}>{subject.name.substring(0, 2)}</p>
                  )}
                </button>
              ))}
            </div>
          ) : (
            <div className={`${sidebarOpen ? 'p-4' : 'p-2'} text-center text-gray-500 text-sm`}>
              Geen onderwerpen
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={`${sidebarOpen ? 'p-4' : 'p-2'} border-t border-gray-200 flex items-center gap-2`}>
          <button
            onClick={() => {
              setCurrentPage('settings');
              setShowForm(false);
              setSelectedSubject(null);
            }}
            className={`p-2 rounded-lg border transition ${
              currentPage === 'settings'
                ? 'bg-blue-100 text-blue-700 border-blue-300'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
            title="Instellingen"
            aria-label="Instellingen"
          >
            <Settings size={18} />
          </button>
        </div>

        {/* Resize Handle */}
        {sidebarOpen && (
          <div
            onMouseDown={startResizing}
            className="absolute top-0 right-0 w-1 h-full cursor-col-resize hover:bg-blue-500 transition-colors group"
            style={{ touchAction: 'none' }}
          >
            <div className="absolute top-1/2 right-0 transform translate-x-1/2 -translate-y-1/2 w-3 h-12 bg-gray-300 rounded-full group-hover:bg-blue-500 transition-colors"></div>
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <div className="bg-white border-b border-gray-200 p-6">
          <h2 className="text-2xl font-bold text-gray-800 truncate" title={selectedSubject?.name}>
            {currentPage === 'settings' ? 'Instellingen' : (selectedSubject ? selectedSubject.name : 'Dashboard')}
          </h2>
          {currentPage !== 'settings' && selectedSubject && (
            <p className="text-gray-600 text-sm mt-1 line-clamp-2" title={selectedSubject.description}>{selectedSubject.description}</p>
          )}
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6">
          {!apiConnected ? (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
              <p className="text-yellow-800 font-medium">⚠️ Database Manager niet beschikbaar</p>
              <p className="text-yellow-700 text-sm mt-2">
                Zorg ervoor dat Docker services zijn gestart: <code className="bg-yellow-100 px-2 py-1 rounded">docker compose up --build</code>
              </p>
            </div>
          ) : currentPage === 'settings' ? (
            <SettingsPage apiUrl={API_URL} />
          ) : showForm ? (
            <SubjectForm
              onSubmit={handleSubjectCreated}
              onCancel={() => setShowForm(false)}
            />
          ) : selectedSubject ? (
            <div className="space-y-6">
              <SubjectForm
                subject={selectedSubject}
                onSubmit={handleSubjectUpdated}
                onDelete={handleSubjectDeleted}
              />
              <ChunkManager
                subjectId={selectedSubject.id}
                onChunksUpdated={handleChunksUpdated}
              />
            </div>
          ) : (
            <div className="text-center text-gray-500 py-12">
              <p className="text-lg">Selecteer een onderwerp of maak een nieuw</p>
              <button
                onClick={() => setShowForm(true)}
                className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
              >
                Nieuw Onderwerp Maken
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
