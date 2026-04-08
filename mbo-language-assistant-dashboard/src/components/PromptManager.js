import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Check, X, AlertCircle, ChevronDown, ChevronRight, Search } from 'lucide-react';
import {
  API_BASE_URL,
  createPrompt as apiCreatePrompt,
  deletePrompt as apiDeletePrompt,
  fetchPrompts as apiFetchPrompts,
  updatePrompt as apiUpdatePrompt,
} from '../api';

const PromptManager = ({ onPromptsUpdated }) => {
  const [prompts, setPrompts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [searchQuery, setSearchQuery] = useState('');
  const [formData, setFormData] = useState({ title: '', content: '', is_active: true, is_default: false });

  useEffect(() => {
    fetchPrompts();
  }, []);

  const fetchPrompts = async () => {
    setLoading(true);
    setError(null);
    try {
      const nextPrompts = await apiFetchPrompts(API_BASE_URL);
      setPrompts(nextPrompts);
    } catch (err) {
      setError('Kan prompts niet ophalen. Is de service beschikbaar?');
      console.error('Error fetching prompts:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!formData.title.trim() || !formData.content.trim()) {
      setError('Titel en inhoud zijn verplicht');
      return;
    }

    try {
      await apiCreatePrompt(formData, API_BASE_URL);
      await fetchPrompts();
      setFormData({ title: '', content: '', is_active: true, is_default: false });
      setShowAddForm(false);
      setCurrentPage(1); // Reset to first page
      if (onPromptsUpdated) onPromptsUpdated();
    } catch (err) {
      setError(err.message || 'Kan prompt niet aanmaken');
      console.error('Error creating prompt:', err);
    }
  };

  const handleUpdate = async (promptId, updates) => {
    try {
      console.log('Updating prompt:', promptId, updates);
      await apiUpdatePrompt(promptId, updates, API_BASE_URL);
      await fetchPrompts();
      setEditingId(null);
      if (onPromptsUpdated) onPromptsUpdated();
    } catch (err) {
      const errorMsg = `Kan prompt niet bijwerken: ${err.message}`;
      console.error('Error updating prompt:', err);
      setError(errorMsg);
    }
  };

  // Reset to page 1 when search query changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  const handleDelete = async (promptId) => {
    if (!window.confirm('Weet je zeker dat je deze prompt wilt verwijderen?')) {
      return;
    }

    try {
      await apiDeletePrompt(promptId, API_BASE_URL);
      await fetchPrompts();
      if (onPromptsUpdated) onPromptsUpdated();
    } catch (err) {
      setError('Kan prompt niet verwijderen');
      console.error('Error deleting prompt:', err);
    }
  };

  const toggleActive = async (promptId, currentActive) => {
    await handleUpdate(promptId, { is_active: !currentActive });
  };

  // Filter prompts based on search query
  const filteredPrompts = prompts.filter(prompt =>
    prompt.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    prompt.content.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-800">System Prompts (Global)</h3>
            <p className="text-sm text-gray-600 mt-1">
              Prompts worden gebruikt door het taalmodel voor ALLE vakken
            </p>
          </div>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2 text-sm"
          >
            <Plus size={16} />
            Nieuwe Prompt
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
          <AlertCircle size={20} className="text-red-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-red-800 font-medium">Fout</p>
            <p className="text-red-700 text-sm">{error}</p>
          </div>
          <button
            onClick={() => setError(null)}
            className="ml-auto text-red-600 hover:text-red-800"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Add Form */}
      {showAddForm && (
        <div className="p-6 border-b border-gray-200 bg-gray-50">
          <h4 className="font-medium text-gray-800 mb-4">Nieuwe Prompt Toevoegen</h4>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Titel
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Bijv. System Prompt, Instructie, etc."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Prompt Inhoud
              </label>
              <textarea
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                placeholder="Schrijf hier de prompt instructies voor het taalmodel..."
                rows={6}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <label htmlFor="is_active" className="text-sm text-gray-700">
                Actief (wordt gebruikt door het taalmodel)
              </label>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_default"
                checked={formData.is_default}
                onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <label htmlFor="is_default" className="text-sm text-gray-700">
                Standaard prompt (aanbevolen voor productie)
              </label>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2 text-sm"
              >
                <Check size={16} />
                Opslaan
              </button>
              <button
                onClick={() => {
                  setShowAddForm(false);
                  setFormData({ title: '', content: '', is_active: true, is_default: false });
                }}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition flex items-center gap-2 text-sm"
              >
                <X size={16} />
                Annuleren
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Prompts List */}
      <div className="p-6">
        {loading ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="text-gray-600 text-sm mt-2">Laden...</p>
          </div>
        ) : prompts.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p>Nog geen prompts toegevoegd</p>
            <p className="text-sm mt-1">Voeg een prompt toe om het taalmodel te instrueren</p>
          </div>
        ) : (
          <>
            {/* Search and Filter Controls */}
            <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
              {/* Search Bar */}
              <div className="relative">
                <Search className="absolute left-3 top-3 text-gray-400" size={18} />
                <input
                  type="text"
                  placeholder="Zoeken in prompts (titel of inhoud)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
                />
              </div>

              {/* Items Per Page Selector */}
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700">
                  Prompts per pagina
                </label>
                <select
                  value={itemsPerPage}
                  onChange={(e) => {
                    setItemsPerPage(Number(e.target.value));
                    setCurrentPage(1); // Reset to page 1
                  }}
                  className="px-3 py-1 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
                >
                  <option value={1}>1 per pagina</option>
                  <option value={2}>2 per pagina</option>
                  <option value={3}>3 per pagina</option>
                  <option value={5}>5 per pagina</option>
                  <option value={10}>10 per pagina</option>
                </select>
              </div>
            </div>

            {/* No Results Message */}
            {filteredPrompts.length === 0 && searchQuery ? (
              <div className="text-center py-8 text-gray-500">
                <p>Geen prompts gevonden voor "{searchQuery}"</p>
                <p className="text-sm mt-1">Probeer een ander zoekterm</p>
              </div>
            ) : (
              <>
                {/* Pagination Info and Controls */}
                {filteredPrompts.length > itemsPerPage && (
                  <div className="mb-6 flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                        disabled={currentPage === 1}
                        className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                      >
                        ←
                      </button>
                      <span className="text-sm text-gray-700">
                        Pagina <span className="font-semibold">{currentPage}</span> van <span className="font-semibold">{Math.ceil(filteredPrompts.length / itemsPerPage)}</span>
                      </span>
                      <button
                        onClick={() => setCurrentPage(prev => Math.min(Math.ceil(filteredPrompts.length / itemsPerPage), prev + 1))}
                        disabled={currentPage === Math.ceil(filteredPrompts.length / itemsPerPage)}
                        className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                      >
                        →
                      </button>
                    </div>
                    <div className="text-sm text-gray-600">
                      {Math.min((currentPage - 1) * itemsPerPage + 1, filteredPrompts.length)} - {Math.min(currentPage * itemsPerPage, filteredPrompts.length)} van {filteredPrompts.length}
                    </div>
                  </div>
                )}

                {/* Prompts Grid */}
                <div className="space-y-4">
                  {filteredPrompts
                    .slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
                    .map((prompt) => (
                      <PromptCard
                        key={prompt.id}
                        prompt={prompt}
                        isEditing={editingId === prompt.id}
                        onEdit={() => setEditingId(prompt.id)}
                        onCancelEdit={() => setEditingId(null)}
                        onUpdate={handleUpdate}
                        onDelete={handleDelete}
                        onToggleActive={toggleActive}
                      />
                    ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
};

const PromptCard = ({ prompt, isEditing, onEdit, onCancelEdit, onUpdate, onDelete, onToggleActive }) => {
  const [editData, setEditData] = useState({ 
    title: prompt.title, 
    content: prompt.content, 
    is_active: prompt.is_active,
    is_default: prompt.is_default || false
  });
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    setEditData({ 
      title: prompt.title, 
      content: prompt.content, 
      is_active: prompt.is_active,
      is_default: prompt.is_default || false
    });
  }, [prompt]);

  const handleSave = () => {
    onUpdate(prompt.id, editData);
  };

  if (isEditing) {
    return (
      <div className="border border-blue-300 rounded-lg p-4 bg-blue-50">
        <div className="space-y-3">
          <input
            type="text"
            value={editData.title}
            onChange={(e) => setEditData({ ...editData, title: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <textarea
            value={editData.content}
            onChange={(e) => setEditData({ ...editData, content: e.target.value })}
            rows={8}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none font-mono text-sm"
          />
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id={`edit_active_${prompt.id}`}
                checked={editData.is_active}
                onChange={(e) => setEditData({ ...editData, is_active: e.target.checked })}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <label htmlFor={`edit_active_${prompt.id}`} className="text-sm text-gray-700">
                Actief
              </label>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id={`edit_default_${prompt.id}`}
                checked={editData.is_default}
                onChange={(e) => setEditData({ ...editData, is_default: e.target.checked })}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <label htmlFor={`edit_default_${prompt.id}`} className="text-sm text-gray-700">
                Standaard
              </label>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-1 text-sm"
            >
              <Check size={14} />
              Opslaan
            </button>
            <button
              onClick={onCancelEdit}
              className="px-3 py-1.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition flex items-center gap-1 text-sm"
            >
              <X size={14} />
              Annuleren
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`border rounded-lg overflow-hidden ${prompt.is_active ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'}`}>
      {/* Header - Always visible and clickable */}
      <div className="p-4 hover:bg-opacity-80 transition">
        <div className="flex items-start justify-between">
          <div 
            className="flex-1 flex items-start gap-3 cursor-pointer"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {/* Expand/Collapse Icon */}
            <div className="mt-0.5">
              {isExpanded ? (
                <ChevronDown size={20} className="text-gray-600" />
              ) : (
                <ChevronRight size={20} className="text-gray-600" />
              )}
            </div>
            
            {/* Title and Badges */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h4 className="font-medium text-gray-800 truncate" title={prompt.title}>{prompt.title}</h4>
                {prompt.is_active && (
                  <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full flex-shrink-0">
                    Actief
                  </span>
                )}
                {prompt.is_default && (
                  <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full flex-shrink-0">
                    Standaard
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-1 truncate">
                {isExpanded ? 'Klik om in te klappen' : 'Klik om prompt te bekijken'} • 
                Aangemaakt: {new Date(prompt.created_at).toLocaleDateString('nl-NL')}
              </p>
            </div>
          </div>
          
          {/* Action Buttons */}
          <div className="flex items-center gap-2 ml-4 flex-shrink-0">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                console.log('Toggle button clicked!', prompt.id, prompt.is_active);
                onToggleActive(prompt.id, prompt.is_active);
              }}
              className={`px-3 py-1.5 rounded-lg transition text-sm cursor-pointer ${
                prompt.is_active
                  ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
                  : 'bg-green-100 text-green-700 hover:bg-green-200'
              }`}
            >
              {prompt.is_active ? 'Deactiveren' : 'Activeren'}
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                console.log('Edit button clicked!', prompt.id);
                onEdit();
              }}
              className="p-2 text-blue-600 hover:bg-blue-100 rounded-lg transition cursor-pointer"
              title="Bewerken"
            >
              <Edit2 size={16} />
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                console.log('Delete button clicked!', prompt.id);
                onDelete(prompt.id);
              }}
              className="p-2 text-red-600 hover:bg-red-100 rounded-lg transition cursor-pointer"
              title="Verwijderen"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Content - Only visible when expanded */}
      {isExpanded && (
        <div className="px-4 pb-4 border-t border-gray-200">
          <div className="bg-white rounded-lg p-4 mt-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-2 font-semibold">Prompt Inhoud:</p>
            <pre className="text-gray-700 text-sm whitespace-pre-wrap font-mono bg-gray-50 p-3 rounded border border-gray-200 max-h-96 overflow-y-auto">
{prompt.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};

export default PromptManager;
