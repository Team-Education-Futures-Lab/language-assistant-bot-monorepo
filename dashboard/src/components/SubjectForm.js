import React, { useState, useEffect } from 'react';
import { Save, X, Trash2, Loader2 } from 'lucide-react';
import {
  API_BASE_URL,
  createSubject as apiCreateSubject,
  deleteSubject as apiDeleteSubject,
  updateSubject as apiUpdateSubject,
} from '../api';

const normalizeSubjectFormData = (inputSubject) => {
  if (!inputSubject) {
    return { name: '', description: '', retrieval_k: 10 };
  }

  const normalizedRetrieval = Number.isInteger(inputSubject.retrieval_k)
    ? inputSubject.retrieval_k
    : 10;

  return {
    ...inputSubject,
    name: inputSubject.name || '',
    description: inputSubject.description || '',
    retrieval_k: normalizedRetrieval
  };
};

const SubjectForm = ({ subject, onSubmit, onCancel, onDelete }) => {
  const [formData, setFormData] = useState(normalizeSubjectFormData(subject));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [action, setAction] = useState('save');

  useEffect(() => {
    setFormData(normalizeSubjectFormData(subject));
    setError('');
  }, [subject]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    setAction('save');

    try {
      const parsedRetrieval = parseInt(formData.retrieval_k, 10);
      const retrievalValue = Number.isNaN(parsedRetrieval) ? 10 : parsedRetrieval;

      const payload = {
        name: formData.name,
        description: formData.description,
        retrieval_k: retrievalValue
      };

      const nextSubject = subject
        ? await apiUpdateSubject(subject.id, payload, API_BASE_URL)
        : await apiCreateSubject(payload, API_BASE_URL);

      onSubmit(nextSubject);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Zeker weten dat je "${subject.name}" wilt verwijderen?`)) {
      return;
    }

    setLoading(true);
    setAction('delete');
    try {
      await apiDeleteSubject(subject.id, API_BASE_URL);
      onDelete(subject.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard-card bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-800">
          {subject ? 'Onderwerp Bewerken' : 'Nieuw Onderwerp'}
        </h3>
        {onCancel && (
          <button
            onClick={onCancel}
            className="p-2 hover:bg-gray-100 rounded-lg transition"
          >
            <X size={20} />
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Naam
          </label>
          <input
            type="text"
            name="name"
            value={formData.name}
            onChange={handleChange}
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
            placeholder="bijv. Haarcutting, Sanitair, etc."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Beschrijving
          </label>
          <textarea
            name="description"
            value={formData.description}
            onChange={handleChange}
            rows="4"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition resize-none"
            placeholder="Beschrijf wat dit onderwerp bevat..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Retrieval Size (chunks per vraag)
          </label>
          <input
            type="number"
            name="retrieval_k"
            value={formData.retrieval_k}
            onChange={handleChange}
            min="1"
            max="20"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition"
            placeholder="10"
          />
          <p className="text-xs text-gray-600 mt-1">Aantal context chunks dat wordt opgehaald per vraag (1-20). Standaard: 10</p>
        </div>

        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            disabled={loading}
            className="dashboard-primary-btn flex items-center gap-2 px-6 py-2 transition disabled:opacity-50"
          >
            {loading && action === 'save' ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
            {loading && action === 'save' ? 'Opslaan...' : 'Opslaan'}
          </button>

          {subject && onDelete && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={loading}
              className="flex items-center gap-2 px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition disabled:opacity-50"
            >
              {loading && action === 'delete' ? <Loader2 size={18} className="animate-spin" /> : <Trash2 size={18} />}
              {loading && action === 'delete' ? 'Verwijderen...' : 'Verwijderen'}
            </button>
          )}

          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="dashboard-secondary-btn px-6 py-2 transition"
            >
              Annuleren
            </button>
          )}
        </div>
      </form>
    </div>
  );
};

export default SubjectForm;
