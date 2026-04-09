import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Trash2, FileUp, Search, ChevronDown, ChevronUp } from 'lucide-react';
import {
  API_BASE_URL,
  createChunk as apiCreateChunk,
  deleteChunk as apiDeleteChunk,
  deleteUpload as apiDeleteUpload,
  fetchChunks as apiFetchChunks,
  uploadSubjectFile as apiUploadSubjectFile,
} from '../api';

const ChunkManager = ({ subjectId, onChunksUpdated }) => {
  const [chunks, setChunks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [formData, setFormData] = useState({ content: '', source_file: '' });
  const [expandedChunks, setExpandedChunks] = useState({});
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [deletingUpload, setDeletingUpload] = useState('');
  const [chunkSize, setChunkSize] = useState(500); // Default chunk size
  
  // Upload-level state
  const [expandedUploads, setExpandedUploads] = useState({});
  const [uploadPagination, setUploadPagination] = useState({}); // { uploadName: currentPage }
  const [currentUploadPage, setCurrentUploadPage] = useState(1);
  const [uploadsPerPage, setUploadsPerPage] = useState(10);
  
  // Search/filter/sort state (global for uploads)
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('newest');
  const itemsPerPage = 5; // Fixed items per page for chunks within uploads

  const fetchChunks = useCallback(async () => {
    setLoading(true);
    try {
      const nextChunks = await apiFetchChunks(subjectId, API_BASE_URL);
      setChunks(nextChunks);
    } catch (err) {
      setError('Error fetching chunks');
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  useEffect(() => {
    fetchChunks();
  }, [fetchChunks]);

  // Reset to page 1 when search or sort changes
  useEffect(() => {
    setCurrentUploadPage(1);
  }, [searchQuery, sortBy]);

  const handleAddChunk = async (e) => {
    e.preventDefault();
    setError('');

    if (!formData.content.trim()) {
      setError('Content is required');
      return;
    }

    setLoading(true);
    try {
      await apiCreateChunk(subjectId, {
        content: formData.content,
        source_file: formData.source_file || 'Untitled'
      }, API_BASE_URL);

      setFormData({ content: '', source_file: '' });
      setShowForm(false);
      await fetchChunks();
      onChunksUpdated?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteChunk = async (chunkId) => {
    if (!window.confirm('Zeker weten dat je deze chunk wilt verwijderen?')) {
      return;
    }

    try {
      await apiDeleteChunk(chunkId, API_BASE_URL);
      await fetchChunks();
      onChunksUpdated?.();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDeleteUpload = async (uploadName) => {
    if (!window.confirm(`Zeker weten dat je upload "${uploadName}" wilt verwijderen? Alle bijbehorende chunks worden verwijderd.`)) {
      return;
    }

    setError('');
    setDeletingUpload(uploadName);

    try {
      await apiDeleteUpload(subjectId, uploadName, API_BASE_URL);

      setExpandedUploads((prev) => {
        const next = { ...prev };
        delete next[uploadName];
        return next;
      });

      setUploadPagination((prev) => {
        const next = { ...prev };
        delete next[uploadName];
        return next;
      });

      await fetchChunks();
      onChunksUpdated?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingUpload('');
    }
  };

  const toggleExpanded = (chunkId) => {
    setExpandedChunks(prev => ({
      ...prev,
      [chunkId]: !prev[chunkId]
    }));
  };

  const toggleUpload = (uploadName) => {
    setExpandedUploads(prev => ({
      ...prev,
      [uploadName]: !prev[uploadName]
    }));
    // Initialize pagination for this upload if not exists
    if (!uploadPagination[uploadName]) {
      setUploadPagination(prev => ({
        ...prev,
        [uploadName]: 1
      }));
    }
  };

  // Group chunks by material (upload)
  const groupedMaterials = chunks.reduce((acc, chunk) => {
    const sourceFile = chunk.source_file || 'Onbekend bestand';
    if (!acc[sourceFile]) {
      acc[sourceFile] = [];
    }
    acc[sourceFile].push(chunk);
    return acc;
  }, {});

  const totalUploads = Object.keys(groupedMaterials).length;

  // Sort chunks within each upload
  const getSortedChunks = (chunkList) => {
    const sorted = [...chunkList];
    sorted.sort((a, b) => {
      switch (sortBy) {
        case 'oldest':
          return new Date(a.created_at || 0) - new Date(b.created_at || 0);
        case 'newest':
          return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        case 'name':
          return (a.source_file || '').localeCompare(b.source_file || '');
        case 'size':
          return (b.content?.length || 0) - (a.content?.length || 0);
        default:
          return 0;
      }
    });
    return sorted;
  };

  // Filter uploads based on search and apply sorting
  const getFilteredAndSortedUploads = () => {
    let filtered = Object.entries(groupedMaterials);
    
    // Filter by search query (on upload names only)
    if (searchQuery) {
      filtered = filtered.filter(([uploadName]) =>
        uploadName.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    
    // Sort uploads
    filtered.sort((a, b) => {
      const [nameA, chunksA] = a;
      const [nameB, chunksB] = b;
      
      switch (sortBy) {
        case 'oldest':
          return (
            new Date(chunksA[0]?.created_at || 0) - new Date(chunksB[0]?.created_at || 0)
          );
        case 'newest':
          return (
            new Date(chunksB[0]?.created_at || 0) - new Date(chunksA[0]?.created_at || 0)
          );
        case 'name':
          return nameA.localeCompare(nameB);
        case 'size':
          return chunksB.length - chunksA.length;
        default:
          return 0;
      }
    });
    
    return filtered;
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!['text/plain', 'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'].includes(file.type)) {
        setError('Ondersteunde bestanden: TXT, PDF, DOC, DOCX');
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        setError('Bestandsgrootte mag niet groter zijn dan 50 MB');
        return;
      }
      setUploadFile(file);
      setError('');
    }
  };

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!uploadFile) {
      setError('Selecteer alstublieft een bestand');
      return;
    }

    setError('');
    setLoading(true);

    try {
      await apiUploadSubjectFile(
        subjectId,
        uploadFile,
        chunkSize,
        API_BASE_URL,
        setUploadProgress
      );

      setUploadFile(null);
      setUploadProgress(0);
      setChunkSize(500);
      setShowFileUpload(false);
      await fetchChunks();
      onChunksUpdated?.();
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div className="dashboard-card bg-white rounded-lg shadow-md p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-800">
          Content ({totalUploads} uploads)
        </h3>
        <div className="flex gap-2">
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
          >
            <Plus size={18} />
            Chunk Toevoegen
          </button>
          <button
            onClick={() => setShowFileUpload(!showFileUpload)}
            className="dashboard-primary-btn flex items-center gap-2 px-4 py-2 transition"
          >
            <FileUp size={18} />
            Bestand Uploaden
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {showFileUpload && (
        <form onSubmit={handleFileUpload} className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <h4 className="text-sm font-semibold text-gray-800 mb-3">Bestand uploaden</h4>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Selecteer bestand
              </label>
              <input
                type="file"
                onChange={handleFileChange}
                accept=".txt,.pdf,.doc,.docx"
                disabled={loading}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
              />
              <p className="text-xs text-gray-600 mt-1">Ondersteunde formaten: TXT, PDF, DOC, DOCX (max 50 MB)</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Chunk grootte (aantal karakters)
              </label>
              <input
                type="number"
                min="100"
                max="2000"
                step="50"
                value={chunkSize}
                onChange={(e) => setChunkSize(parseInt(e.target.value) || 500)}
                disabled={loading}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
              />
              <p className="text-xs text-gray-600 mt-1">Aanbevolen: 500 karakters. Bereik: 100-2000</p>
            </div>

            {uploadFile && (
              <div className="p-2 bg-white rounded border border-blue-300">
                <p className="text-sm text-gray-700">
                  <strong>Bestand:</strong> {uploadFile.name}
                </p>
              </div>
            )}

            {uploadProgress > 0 && (
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            )}

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={!uploadFile || loading}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
              >
                {loading ? 'Uploaden...' : 'Upload'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowFileUpload(false);
                  setUploadFile(null);
                  setUploadProgress(0);
                  setChunkSize(500);
                }}
                className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400 transition"
              >
                Annuleren
              </button>
            </div>
          </div>
        </form>
      )}

      {showForm && (
        <form onSubmit={handleAddChunk} className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Content
              </label>
              <textarea
                value={formData.content}
                onChange={(e) => setFormData(prev => ({ ...prev, content: e.target.value }))}
                rows="4"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none transition resize-none"
                placeholder="Voer de content in..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Bron (bijv. chapter1.pdf)
              </label>
              <input
                type="text"
                value={formData.source_file}
                onChange={(e) => setFormData(prev => ({ ...prev, source_file: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent outline-none transition"
                placeholder="Optional"
              />
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:opacity-50"
              >
                {loading ? 'Opslaan...' : 'Opslaan'}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition"
              >
                Annuleren
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Search and Sort Controls */}
      {chunks.length > 0 && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div className="space-y-4">
            {/* Search Bar */}
            <div className="relative">
              <Search className="absolute left-3 top-3 text-gray-400" size={18} />
              <input
                type="text"
                placeholder="Zoeken in content..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
              />
            </div>

            {/* Sort Controls */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Sorteren op
              </label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
              >
                <option value="newest">Nieuwste eerst</option>
                <option value="oldest">Oudste eerst</option>
                <option value="name">Bestandsnaam</option>
                <option value="size">Grootste eerst</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {chunks.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p>Geen content beschikbaar</p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Pagination for uploads */}
          {getFilteredAndSortedUploads().length > uploadsPerPage && (
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentUploadPage(prev => Math.max(1, prev - 1))}
                  disabled={currentUploadPage === 1}
                  className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  <ChevronUp size={16} />
                </button>

                <span className="text-sm text-gray-700">
                  Pagina <span className="font-semibold">{currentUploadPage}</span> van <span className="font-semibold">{Math.ceil(getFilteredAndSortedUploads().length / uploadsPerPage)}</span>
                </span>

                <button
                  onClick={() => setCurrentUploadPage(prev => Math.min(Math.ceil(getFilteredAndSortedUploads().length / uploadsPerPage), prev + 1))}
                  disabled={currentUploadPage === Math.ceil(getFilteredAndSortedUploads().length / uploadsPerPage)}
                  className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  <ChevronDown size={16} />
                </button>
              </div>

              <div className="text-sm text-gray-600">
                {Math.min((currentUploadPage - 1) * uploadsPerPage + 1, getFilteredAndSortedUploads().length)} - {Math.min(currentUploadPage * uploadsPerPage, getFilteredAndSortedUploads().length)} van {getFilteredAndSortedUploads().length}
              </div>
            </div>
          )}

          {/* Upload cards with items per page control */}
          <div className="flex items-center justify-between mb-4 px-2">
            <span className="text-sm font-medium text-gray-700">Uploads per pagina</span>
            <select
              value={uploadsPerPage}
              onChange={(e) => {
                setUploadsPerPage(Number(e.target.value));
                setCurrentUploadPage(1); // Reset to page 1
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

          {/* Display paginated uploads */}
          {getFilteredAndSortedUploads().length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p>Geen uploads gevonden</p>
            </div>
          ) : (
            getFilteredAndSortedUploads()
              .slice((currentUploadPage - 1) * uploadsPerPage, currentUploadPage * uploadsPerPage)
              .map(([uploadName, uploadChunks]) => {
              const isExpanded = expandedUploads[uploadName];
              const currentPage = uploadPagination[uploadName] || 1;
              
              // Apply sort to chunks within this upload
              const sortedChunks = getSortedChunks(uploadChunks);
              const totalPages = Math.ceil(sortedChunks.length / itemsPerPage);
              const paginatedChunks = sortedChunks.slice(
                (currentPage - 1) * itemsPerPage,
                currentPage * itemsPerPage
              );

            return (
              <div key={uploadName} className="border border-gray-200 rounded-lg overflow-hidden">
                {/* Upload Header - Always Visible */}
                <div
                  onClick={() => toggleUpload(uploadName)}
                  className="bg-gradient-to-r from-blue-50 to-blue-100 p-4 cursor-pointer hover:from-blue-100 hover:to-blue-200 transition flex items-center justify-between"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <h4 className="font-semibold text-gray-800 truncate flex-1" title={uploadName}>{uploadName}</h4>
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-200 text-blue-800 flex-shrink-0">
                        {uploadChunks.length} chunks
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteUpload(uploadName);
                        }}
                        disabled={deletingUpload === uploadName}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium text-red-700 bg-red-100 hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed transition flex-shrink-0"
                        title="Verwijder upload en alle bijbehorende chunks"
                      >
                        <Trash2 size={14} />
                        <span className="hidden sm:inline">{deletingUpload === uploadName ? 'Verwijderen...' : 'Verwijder upload'}</span>
                      </button>
                    </div>
                  </div>
                  <div className="text-gray-600 flex-shrink-0">
                    {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                  </div>
                </div>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="p-4 space-y-4 bg-white">
                    {/* Metadata */}
                    <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                      <h5 className="font-semibold text-gray-800 mb-3">Metadata</h5>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-gray-600">Bestandsnaam</p>
                          <p className="text-gray-800 font-medium truncate" title={uploadName}>{uploadName}</p>
                        </div>
                        <div>
                          <p className="text-gray-600">Totaal chunks</p>
                          <p className="text-gray-800 font-medium">{uploadChunks.length}</p>
                        </div>
                        <div>
                          <p className="text-gray-600">Eerste upload</p>
                          <p className="text-gray-800 font-medium">
                            {uploadChunks[0]?.created_at 
                              ? new Date(uploadChunks[0].created_at).toLocaleDateString('nl-NL')
                              : '-'}
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-600">Chunks in resultaat</p>
                          <p className="text-gray-800 font-medium">{sortedChunks.length}</p>
                        </div>
                      </div>
                    </div>

                    {/* Chunks */}
                    {sortedChunks.length === 0 ? (
                      <div className="text-center py-6 text-gray-500">
                        <p>Geen chunks gevonden met je zoekterm</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div className="text-sm text-gray-600 px-2">
                          Toont {Math.min(itemsPerPage, sortedChunks.length)} van {sortedChunks.length} chunks
                        </div>

                        {paginatedChunks.map(chunk => (
                          <div key={chunk.id} className="p-3 border border-gray-200 rounded-lg hover:border-gray-300 transition">
                            <div className="flex items-start justify-between gap-3 mb-2">
                              <div className="text-xs text-gray-500 truncate">
                                ID: {chunk.id} | {chunk.content?.length || 0} tekens
                                {chunk.created_at && (
                                  <> | {new Date(chunk.created_at).toLocaleDateString('nl-NL')}</>
                                )}
                              </div>
                              <button
                                onClick={() => handleDeleteChunk(chunk.id)}
                                className="p-1 hover:bg-red-50 rounded transition flex-shrink-0"
                                title="Verwijder chunk"
                              >
                                <Trash2 size={16} className="text-red-600" />
                              </button>
                            </div>
                            <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap break-words">
                              {expandedChunks[chunk.id]
                                ? chunk.content
                                : chunk.content.substring(0, 150) + (chunk.content.length > 150 ? '...' : '')}
                            </p>
                            {chunk.content.length > 150 && (
                              <button
                                onClick={() => toggleExpanded(chunk.id)}
                                className="mt-2 text-xs text-blue-600 hover:text-blue-700 font-medium"
                              >
                                {expandedChunks[chunk.id] ? '▼ Minder tonen' : '▶ Meer tonen'}
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Pagination for this upload */}
                    {sortedChunks.length > itemsPerPage && (
                      <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200 mt-4">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setUploadPagination(prev => ({
                              ...prev,
                              [uploadName]: Math.max(1, currentPage - 1)
                            }))}
                            disabled={currentPage === 1}
                            className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                          >
                            <ChevronUp size={16} />
                          </button>

                          <span className="text-sm text-gray-700">
                            Pagina <span className="font-semibold">{currentPage}</span> van <span className="font-semibold">{totalPages}</span>
                          </span>

                          <button
                            onClick={() => setUploadPagination(prev => ({
                              ...prev,
                              [uploadName]: Math.min(totalPages, currentPage + 1)
                            }))}
                            disabled={currentPage === totalPages}
                            className="p-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                          >
                            <ChevronDown size={16} />
                          </button>
                        </div>

                        <div className="text-sm text-gray-600">
                          {Math.min((currentPage - 1) * itemsPerPage + 1, sortedChunks.length)} - {Math.min(currentPage * itemsPerPage, sortedChunks.length)} van {sortedChunks.length}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
          )}
        </div>
      )}
    </div>
  );
};

export default ChunkManager;
