import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import PromptManager from './PromptManager';
import { API_BASE_URL, fetchSettings as apiFetchSettings, saveSettings as apiSaveSettings } from '../api';

const createEmptyOpenAISettings = () => ({
  openai_realtime_model: '',
  openai_realtime_voice: '',
});

const MODEL_OPTIONS = [
  { label: 'gpt-realtime-mini', value: 'gpt-realtime-mini' },
  { label: 'gpt-realtime-1.5', value: 'gpt-realtime-1.5' },
];

const VOICE_OPTIONS = [
  { label: 'echo', value: 'echo' },
  { label: 'cedar', value: 'cedar' },
  { label: 'alloy', value: 'alloy' },
  { label: 'shimmer', value: 'shimmer' },
  { label: 'marin', value: 'marin' },
];

const VOICE_HELP_TEXT = [
  'echo -> often perceived as male / deeper tone',
  'cedar -> often perceived as male / calm deeper voice',
  'alloy -> neutral (hard to categorize)',
  'shimmer -> often perceived as female / lighter tone',
  'marin -> more neutral to slightly female-leaning depending on usage',
].join('\n');

const withSelectedOption = (options, selectedValue) => {
  if (!selectedValue) {
    return options;
  }

  const hasSelectedValue = options.some((option) => option.value === selectedValue);
  if (hasSelectedValue) {
    return options;
  }

  return [{ label: selectedValue, value: selectedValue }, ...options];
};

export default function SettingsPage({ apiUrl }) {
  const [selectedSection, setSelectedSection] = useState('openai');
  const [openaiSettings, setOpenAISettings] = useState(() => createEmptyOpenAISettings());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const allSettings = useMemo(() => openaiSettings, [openaiSettings]);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const settings = await apiFetchSettings(apiUrl || API_BASE_URL);

      const mapped = settings.reduce((acc, row) => {
        acc[row.key] = String(row.value ?? '');
        return acc;
      }, {});

      const openaiKeys = Object.keys(createEmptyOpenAISettings());
      
      const openaiMapped = {};
      
      Object.keys(mapped).forEach(key => {
        if (openaiKeys.includes(key)) {
          openaiMapped[key] = mapped[key];
        }
      });

      setOpenAISettings((prev) => ({ ...prev, ...openaiMapped }));
    } catch (err) {
      setError(err.message || 'Kon instellingen niet ophalen.');
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const handleOpenAIChange = (key, value) => {
    setOpenAISettings((prev) => ({ ...prev, [key]: value }));
  };

  const settingDescriptions = {
    openai_realtime_model: 'OpenAI Realtime model voor spraak en LLM (bijv. gpt-4o-mini-realtime-preview).',
    openai_realtime_voice: 'Stem voor TTS in realtime mode (alloy, echo, fable, onyx, nova, shimmer).',
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      await apiSaveSettings(allSettings, settingDescriptions, apiUrl || API_BASE_URL);

      setSuccess('Instellingen succesvol opgeslagen.');
      await loadSettings();
    } catch (err) {
      setError(err.message || 'Opslaan van instellingen mislukt.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="dashboard-card bg-white rounded-lg border border-gray-200 p-6">
        <h3 className="text-xl font-semibold text-gray-800">Service Instellingen</h3>
        <p className="text-sm text-gray-600 mt-1">
          Configureer de realtime instellingen voor de OpenAI service.
        </p>
      </div>

      {loading && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-700 text-sm">
          Instellingen laden...
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-green-700 text-sm">
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <section className="dashboard-card lg:col-span-3 bg-white rounded-lg border border-gray-200 p-4">
          <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">Configureerbaar</h4>
          <div className="space-y-2">
            <button
              onClick={() => setSelectedSection('openai')}
              className={`w-full text-left px-3 py-2 rounded-lg border transition ${
                selectedSection === 'openai'
                  ? 'bg-blue-100 text-blue-700 border-blue-300'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              OpenAI
            </button>
            <button
              onClick={() => setSelectedSection('prompts')}
              className={`w-full text-left px-3 py-2 rounded-lg border transition ${
                selectedSection === 'prompts'
                  ? 'bg-blue-100 text-blue-700 border-blue-300'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              Prompts
            </button>
          </div>
        </section>

        <section
          className={selectedSection === 'openai'
            ? 'dashboard-card lg:col-span-9 bg-white rounded-lg border border-gray-200 p-6'
            : 'lg:col-span-9'}
        >
          {selectedSection === 'openai' && (
            <h4 className="text-lg font-semibold text-gray-800 mb-4">
              OpenAI instellingen
            </h4>
          )}

          {selectedSection === 'openai' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl">
            <SelectField
              label="Realtime Model"
              value={openaiSettings.openai_realtime_model}
              onChange={(v) => handleOpenAIChange('openai_realtime_model', v)}
              options={withSelectedOption(MODEL_OPTIONS, openaiSettings.openai_realtime_model)}
            />
            <SelectField
              label="Stem"
              value={openaiSettings.openai_realtime_voice}
              onChange={(v) => handleOpenAIChange('openai_realtime_voice', v)}
              options={withSelectedOption(VOICE_OPTIONS, openaiSettings.openai_realtime_voice)}
              helpText={VOICE_HELP_TEXT}
            />
          </div>
          ) : (
            <PromptManager />
          )}
        </section>
      </div>

      {selectedSection === 'openai' && (
        <div className="dashboard-card bg-white rounded-lg border border-gray-200 p-6 flex justify-end">
          <button
            onClick={handleSaveSettings}
            disabled={saving || loading}
            className="dashboard-primary-btn px-6 py-2 transition disabled:opacity-60 disabled:cursor-not-allowed inline-flex items-center gap-2"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : null}
            {saving ? 'Opslaan...' : 'Instellingen Opslaan'}
          </button>
        </div>
      )}
    </div>
  );
}

function SelectField({ label, value, onChange, options, helpText = '' }) {
  return (
    <label className="block">
      <span className="flex items-center gap-2 text-sm font-medium text-gray-700">
        {label}
        {helpText && <HelpTooltip text={helpText} />}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function HelpTooltip({ text }) {
  return (
    <span className="group relative inline-flex h-5 w-5 items-center justify-center rounded-full border border-gray-400 text-[11px] font-semibold text-gray-600 cursor-help">
      ?
      <span className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 hidden w-72 -translate-x-1/2 rounded-lg bg-gray-900 px-3 py-2 text-xs leading-5 text-white shadow-lg group-hover:block group-focus-within:block whitespace-pre-line">
        {text}
      </span>
    </span>
  );
}
