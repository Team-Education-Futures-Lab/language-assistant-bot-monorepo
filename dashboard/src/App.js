import React, { useState, useEffect } from 'react';
import SubjectList from './components/SubjectList';
import SubjectForm from './components/SubjectForm';
import ChunkManager from './components/ChunkManager';
import SettingsPage from './components/SettingsPage';
import { Menu, X, Settings, Loader2, PlusCircle, FolderPlus, BookOpenText } from 'lucide-react';
import appLogo from './components/images/yonder_logo.png';
import {
  API_BASE_URL,
  fetchApiHealth as apiFetchApiHealth,
  fetchSubjects as apiFetchSubjects,
  fetchSubjectById as apiFetchSubjectById,
} from './api';

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
      const isHealthy = await apiFetchApiHealth(API_BASE_URL);
      if (isHealthy) {
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
      const nextSubjects = await apiFetchSubjects(API_BASE_URL);
      setSubjects(nextSubjects);
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
        const subject = await apiFetchSubjectById(selectedSubject.id, API_BASE_URL);
        if (subject) {
          setSelectedSubject(subject);
          // Also update the subject in the list
          setSubjects(subjects.map(s => s.id === selectedSubject.id ? subject : s));
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
    <div className="dashboard-root flex h-screen">
      {/* Sidebar */}
      <div
        style={{ 
          width: sidebarOpen ? `${sidebarWidth}px` : '80px',
          minWidth: sidebarOpen ? '200px' : '80px',
          maxWidth: sidebarOpen ? '600px' : '80px'
        }}
        className="dashboard-sidebar border-r transition-all duration-300 flex flex-col relative"
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            {sidebarOpen ? (
              <button
                className="dashboard-home-btn flex items-center gap-2 border-none bg-transparent p-1 rounded-lg cursor-pointer hover:bg-white/10 transition"
                onClick={() => {
                  setCurrentPage('subjects');
                  setSelectedSubject(null);
                  setShowForm(false);
                }}
                title="Home"
                aria-label="Home"
              >
                <img src={appLogo} alt="Yonder logo" className="w-7 h-7 object-contain" />
                <span className="dashboard-brand text-base truncate">Dashboard</span>
              </button>
            ) : (
              <button
                className="group relative w-10 h-10 rounded-xl border-none bg-transparent p-0 cursor-pointer overflow-hidden transition-all duration-300 hover:shadow-sm hover:scale-[1.03]"
                onClick={() => setSidebarOpen(true)}
                title="Zijbalk openen"
                aria-label="Zijbalk openen"
              >
                <img
                  src={appLogo}
                  alt="Yonder logo"
                  className="absolute inset-0 w-full h-full object-contain p-1.5 transition-all duration-300 ease-out group-hover:opacity-0 group-hover:scale-90"
                />
                <span className="absolute inset-0 flex items-center justify-center text-app-text-secondary opacity-0 scale-90 transition-all duration-300 ease-out group-hover:opacity-100 group-hover:scale-100 group-hover:bg-gray-200">
                  <Menu size={18} />
                </span>
              </button>
            )}
            {sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(false)}
                className="dashboard-secondary-btn p-2 transition"
                title="Zijbalk sluiten"
                aria-label="Zijbalk sluiten"
              >
                <X size={20} />
              </button>
            )}
          </div>
        </div>

        {/* New Subject Button */}
        <div className={`${sidebarOpen ? 'p-4' : 'p-2'}`}>
          <button
            onClick={() => {
              setCurrentPage('subjects');
              setShowForm(true);
            }}
            className={`dashboard-primary-btn w-full ${sidebarOpen ? 'px-3 py-1.5' : 'px-2 py-1.5'} transition text-sm font-medium flex items-center ${sidebarOpen ? 'justify-start gap-2' : 'justify-center'}`}
          >
            <PlusCircle size={16} />
            {sidebarOpen ? 'Nieuw Onderwerp' : ''}
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
                  className={`w-full text-left ${sidebarOpen ? 'px-2.5 py-2' : 'p-2'} rounded-lg transition ${
                    selectedSubject?.id === subject.id
                      ? 'bg-white/20 text-white border border-white/35'
                      : 'hover:bg-white/10 border border-transparent text-slate-100'
                  }`}
                >
                  {sidebarOpen ? (
                    <div className="flex items-center gap-2.5 min-w-0">
                      <BookOpenText size={15} className="opacity-90 shrink-0" />
                      <p className="font-medium text-sm truncate" title={subject.name}>{subject.name}</p>
                    </div>
                  ) : (
                    <BookOpenText size={15} className="mx-auto opacity-90" />
                  )}
                </button>
              ))}
            </div>
          ) : (
            <div className={`${sidebarOpen ? 'p-4 text-left' : 'p-2 text-center'} text-gray-500 text-sm`}>
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
            className={`rounded-lg border transition flex items-center ${sidebarOpen ? 'px-2.5 py-1.5 justify-center gap-1.5' : 'p-2 justify-center'} ${
              currentPage === 'settings'
                ? 'bg-white/20 text-white border-white/40'
                : 'bg-white/5 text-slate-100 border-white/25 hover:bg-white/10'
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
      <div className="dashboard-main-panel flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <div className="dashboard-topbar border-b border-gray-200 p-6">
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
            <div className="dashboard-card rounded-lg p-6 flex flex-col items-start justify-center text-left gap-3 min-h-[180px]">
              <Loader2 size={28} className="animate-spin text-blue-600" />
              <p className="text-lg font-semibold text-gray-800">Database loading...</p>
              <p className="text-sm text-gray-600">Even geduld, de verbinding wordt opgezet.</p>
            </div>
          ) : currentPage === 'settings' ? (
            <SettingsPage apiUrl={API_BASE_URL} />
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
            <div className="text-left text-gray-500 py-12">
              <p className="text-lg">Selecteer een onderwerp of maak een nieuw</p>
              <button
                onClick={() => setShowForm(true)}
                className="dashboard-primary-btn mt-4 px-4 py-1.5 transition inline-flex items-center gap-2"
              >
                <FolderPlus size={16} />
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
