import React, { useCallback, useEffect, useMemo, useState } from 'react';
import PromptManager from './PromptManager';
import { API_BASE_URL, fetchSettings as apiFetchSettings, saveSettings as apiSaveSettings } from '../api';

const defaultSpeechSettings = {
  speech_whisper_model_size: 'small',
  speech_language: 'nl',
  speech_vad_silence_ms: '900',
  speech_max_recording_ms: '10000',
  speech_retrieval_k_default: '10',
  speech_enable_tts_default: 'true',
  speech_ollama_model_name: 'llama3',
  speech_ollama_temperature: '0.3',
  speech_ollama_num_ctx: '4096',
};

const defaultTextSettings = {
  text_retrieval_k_default: '10',
  text_enable_tts_default: 'false',
  text_ollama_model_name: 'llama3',
  text_ollama_temperature: '0.3',
  text_ollama_num_ctx: '4096',
};

const createDefaultOpenAISettings = (apiUrl) => ({
  openai_realtime_model: 'gpt-4o-mini-realtime-preview',
  openai_realtime_transcription_model: 'whisper-1',
  openai_realtime_barge_in_enabled: 'true',
  openai_realtime_max_output_tokens: '200',
  openai_realtime_temperature: '0.4',
  openai_realtime_top_p: '1.0',
  openai_realtime_language: 'nl',
  openai_realtime_voice: 'alloy',
  openai_realtime_vad_threshold: '0.5',
  openai_realtime_vad_silence_ms: '500',
  openai_realtime_prefix_padding_ms: '300',
  openai_ws_timeout_sec: '180',
  openai_ws_ping_interval_sec: '0',
  database_manager_url: apiUrl || API_BASE_URL || '',
  retrieve_top_k: '5',
  retrieve_timeout_sec: '4',
  openai_realtime_use_ephemeral_token: 'false',
  openai_realtime_ws_url: 'wss://api.openai.com/v1/realtime',
  openai_realtime_api_base: 'https://api.openai.com/v1',
});

export default function SettingsPage({ apiUrl }) {
  const [selectedSection, setSelectedSection] = useState('openai');
  const [speechSettings, setSpeechSettings] = useState(defaultSpeechSettings);
  const [textSettings, setTextSettings] = useState(defaultTextSettings);
  const [openaiSettings, setOpenAISettings] = useState(() => createDefaultOpenAISettings(apiUrl));
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const allSettings = useMemo(
    () => {
      // Merge settings, prioritizing the most recent changes
      // Text settings should NOT overwrite speech settings and vice versa
      const merged = {};
      
      // Add all speech settings
      Object.keys(speechSettings).forEach(key => {
        merged[key] = speechSettings[key];
      });
      
      // Add text settings (won't overwrite speech keys since they have different prefixes)
      Object.keys(textSettings).forEach(key => {
        merged[key] = textSettings[key];
      });

      // Add OpenAI settings
      Object.keys(openaiSettings).forEach(key => {
        merged[key] = openaiSettings[key];
      });
      
      return merged;
    },
    [speechSettings, textSettings, openaiSettings]
  );

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const settings = await apiFetchSettings(apiUrl || API_BASE_URL);

      const mapped = settings.reduce((acc, row) => {
        acc[row.key] = String(row.value ?? '');
        return acc;
      }, {});

      // Separate speech, text, and openai settings to avoid conflicts
      const speechKeys = Object.keys(defaultSpeechSettings);
      const textKeys = Object.keys(defaultTextSettings);
      const openaiKeys = Object.keys(createDefaultOpenAISettings(apiUrl));
      
      const speechMapped = {};
      const textMapped = {};
      const openaiMapped = {};
      
      Object.keys(mapped).forEach(key => {
        if (speechKeys.includes(key)) {
          speechMapped[key] = mapped[key];
        } else if (textKeys.includes(key)) {
          textMapped[key] = mapped[key];
        } else if (openaiKeys.includes(key)) {
          openaiMapped[key] = mapped[key];
        }
        // subject_X_retrieval_k goes to both for now
        if (key.startsWith('subject_')) {
          speechMapped[key] = mapped[key];
          textMapped[key] = mapped[key];
        }
      });

      setSpeechSettings((prev) => ({ ...prev, ...speechMapped }));
      setTextSettings((prev) => ({ ...prev, ...textMapped }));
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
    console.log(`[DASHBOARD] OpenAI setting changed: ${key} = ${value}`);
    setOpenAISettings((prev) => ({ ...prev, [key]: value }));
  };

  const settingDescriptions = {
    speech_whisper_model_size: 'Whisper model voor speech-to-text (tiny/base/small/medium/large).',
    speech_language: 'Taalcode voor transcriptie (bijv. nl).',
    speech_vad_silence_ms: 'Stilte-drempel in milliseconden voordat opname stopt in de speech UI.',
    speech_max_recording_ms: 'Maximale opnameduur in milliseconden voor de speech UI.',
    speech_retrieval_k_default: 'Standaard aantal contextfragmenten voor speech retrieval.',
    speech_enable_tts_default: 'Standaard TTS gedrag voor speech endpoint.',
    speech_ollama_model_name: 'LLM modelnaam voor speech antwoorden.',
    speech_ollama_temperature: 'Creativiteit van het model voor speech antwoorden.',
    speech_ollama_num_ctx: 'Context window (tokens) voor speech prompts.',
    text_retrieval_k_default: 'Standaard aantal contextfragmenten voor tekst retrieval.',
    text_enable_tts_default: 'Standaard TTS gedrag voor tekst endpoint.',
    text_ollama_model_name: 'LLM modelnaam voor tekst antwoorden.',
    text_ollama_temperature: 'Creativiteit van het model voor tekst antwoorden.',
    text_ollama_num_ctx: 'Context window (tokens) voor tekst prompts.',
    openai_realtime_model: 'OpenAI Realtime model voor spraak en LLM (bijv. gpt-4o-mini-realtime-preview).',
    openai_realtime_transcription_model: 'Model voor spraak-naar-tekst transcriptie (bijv. whisper-1).',
    openai_realtime_barge_in_enabled: 'Onderbreek assistent-audio wanneer gebruiker begint te spreken (stuurt response.cancel tijdens praten).',
    openai_realtime_max_output_tokens: 'Maximale lengte van een antwoord in tokens voor response.create.',
    openai_realtime_temperature: 'Randomness van antwoorden: lager = consistenter, hoger = creatiever.',
    openai_realtime_top_p: 'Nucleus sampling: lager = veiliger/focuster, hoger = breder gevarieerd.',
    openai_realtime_language: 'Taalcode voor OpenAI realtime (bijv. nl voor Nederlands).',
    openai_realtime_voice: 'Stem voor TTS in realtime mode (alloy, echo, fable, onyx, nova, shimmer).',
    openai_realtime_vad_threshold: 'Voice Activity Detection drempel (0.0-1.0) voor automatische spraakdetectie.',
    openai_realtime_vad_silence_ms: 'Stilteduur in ms voordat OpenAI spraakdetectie eindigt.',
    openai_realtime_prefix_padding_ms: 'Padding voor audio buffer in milliseconden.',
    openai_ws_timeout_sec: 'Timeout in seconden voor OpenAI WebSocket verbinding.',
    openai_ws_ping_interval_sec: 'Interval in seconden voor keepalive pings (0 = uitgeschakeld).',
    database_manager_url: 'URL van de database manager service voor context retrieval.',
    retrieve_top_k: 'Aantal contextfragmenten om op te halen voor elk retrieval.',
    retrieve_timeout_sec: 'Timeout in seconden voor retrieval requests.',
    openai_realtime_use_ephemeral_token: 'Of ephemeral tokens moeten gebruikt worden voor OpenAI.',
    openai_realtime_ws_url: 'WebSocket URL voor OpenAI realtime API.',
    openai_realtime_api_base: 'Base URL voor OpenAI API calls.',
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
        <h3 className="text-xl font-semibold text-gray-800">OpenAI Instellingen</h3>
        <p className="text-sm text-gray-600 mt-1">
          Configureer runtime-parameters voor de OpenAI Realtime API service.
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

        <section className="dashboard-card lg:col-span-9 bg-white rounded-lg border border-gray-200 p-6">
          <h4 className="text-lg font-semibold text-gray-800 mb-4">
            {selectedSection === 'openai' ? 'OpenAI instellingen' : 'System Prompts (Global)'}
          </h4>

          {selectedSection === 'openai' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SelectField
              label="Realtime Model"
              value={openaiSettings.openai_realtime_model}
              onChange={(v) => handleOpenAIChange('openai_realtime_model', v)}
              options={[
                { label: 'gpt-4o-mini-realtime-preview', value: 'gpt-4o-mini-realtime-preview' },
                { label: 'gpt-4o-realtime-preview', value: 'gpt-4o-realtime-preview' },
              ]}
            />
            <SelectField
              label="Transcriptie Model"
              value={openaiSettings.openai_realtime_transcription_model}
              onChange={(v) => handleOpenAIChange('openai_realtime_transcription_model', v)}
              options={[
                { label: 'whisper-1', value: 'whisper-1' },
                { label: 'gpt-4o-mini-transcribe', value: 'gpt-4o-mini-transcribe' },
                { label: 'gpt-4o-transcribe', value: 'gpt-4o-transcribe' },
              ]}
            />
            <SelectField
              label="Interruption (Barge-in)"
              value={openaiSettings.openai_realtime_barge_in_enabled}
              onChange={(v) => handleOpenAIChange('openai_realtime_barge_in_enabled', v)}
              options={[
                { label: 'Enabled (cancel response on user speech)', value: 'true' },
                { label: 'Disabled', value: 'false' },
              ]}
            />
            <Field
              label="Max Output Tokens"
              type="number"
              value={openaiSettings.openai_realtime_max_output_tokens}
              onChange={(v) => handleOpenAIChange('openai_realtime_max_output_tokens', v)}
              placeholder="200"
            />
            <Field
              label="Temperature"
              type="number"
              step="0.1"
              value={openaiSettings.openai_realtime_temperature}
              onChange={(v) => handleOpenAIChange('openai_realtime_temperature', v)}
              placeholder="0.4"
            />
            <Field
              label="Top P"
              type="number"
              step="0.1"
              value={openaiSettings.openai_realtime_top_p}
              onChange={(v) => handleOpenAIChange('openai_realtime_top_p', v)}
              placeholder="1.0"
            />
            <Field
              label="Taal Code"
              value={openaiSettings.openai_realtime_language}
              onChange={(v) => handleOpenAIChange('openai_realtime_language', v)}
              placeholder="nl"
            />
            <SelectField
              label="Stem"
              value={openaiSettings.openai_realtime_voice}
              onChange={(v) => handleOpenAIChange('openai_realtime_voice', v)}
              options={[
                { label: 'Alloy', value: 'alloy' },
                { label: 'Echo', value: 'echo' },
                { label: 'Fable', value: 'fable' },
                { label: 'Onyx', value: 'onyx' },
                { label: 'Nova', value: 'nova' },
                { label: 'Shimmer', value: 'shimmer' },
              ]}
            />
            <Field
              label="VAD Drempel (0.0-1.0)"
              type="number"
              step="0.1"
              value={openaiSettings.openai_realtime_vad_threshold}
              onChange={(v) => handleOpenAIChange('openai_realtime_vad_threshold', v)}
              placeholder="0.5"
            />
            <Field
              label="VAD Stilteduur (ms)"
              type="number"
              value={openaiSettings.openai_realtime_vad_silence_ms}
              onChange={(v) => handleOpenAIChange('openai_realtime_vad_silence_ms', v)}
              placeholder="500"
            />
            <Field
              label="Prefix Padding (ms)"
              type="number"
              value={openaiSettings.openai_realtime_prefix_padding_ms}
              onChange={(v) => handleOpenAIChange('openai_realtime_prefix_padding_ms', v)}
              placeholder="300"
            />
            <Field
              label="WebSocket Timeout (sec)"
              type="number"
              value={openaiSettings.openai_ws_timeout_sec}
              onChange={(v) => handleOpenAIChange('openai_ws_timeout_sec', v)}
              placeholder="180"
            />
            <Field
              label="Ping Interval (sec, 0=disabled)"
              type="number"
              step="0.1"
              value={openaiSettings.openai_ws_ping_interval_sec}
              onChange={(v) => handleOpenAIChange('openai_ws_ping_interval_sec', v)}
              placeholder="0"
            />
            <Field
              label="Database Manager URL"
              value={openaiSettings.database_manager_url}
              onChange={(v) => handleOpenAIChange('database_manager_url', v)}
              placeholder="http://localhost:5004"
            />
            <Field
              label="Retrieve Top K"
              type="number"
              value={openaiSettings.retrieve_top_k}
              onChange={(v) => handleOpenAIChange('retrieve_top_k', v)}
              placeholder="5"
            />
            <Field
              label="Retrieve Timeout (sec)"
              type="number"
              step="0.1"
              value={openaiSettings.retrieve_timeout_sec}
              onChange={(v) => handleOpenAIChange('retrieve_timeout_sec', v)}
              placeholder="4"
            />
            <SelectField
              label="Use Ephemeral Token"
              value={openaiSettings.openai_realtime_use_ephemeral_token}
              onChange={(v) => handleOpenAIChange('openai_realtime_use_ephemeral_token', v)}
              options={[
                { label: 'Enabled', value: 'true' },
                { label: 'Disabled', value: 'false' },
              ]}
            />
            <Field
              label="Realtime WebSocket URL"
              value={openaiSettings.openai_realtime_ws_url}
              onChange={(v) => handleOpenAIChange('openai_realtime_ws_url', v)}
              placeholder="wss://api.openai.com/v1/realtime"
            />
            <Field
              label="Realtime API Base URL"
              value={openaiSettings.openai_realtime_api_base}
              onChange={(v) => handleOpenAIChange('openai_realtime_api_base', v)}
              placeholder="https://api.openai.com/v1"
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
            className="dashboard-primary-btn px-6 py-2 transition disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {saving ? 'Opslaan...' : 'Instellingen Opslaan'}
          </button>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, onChange, type = 'text', placeholder = '', step = undefined }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        step={step}
        className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
    </label>
  );
}

function SelectField({ label, value, onChange, options }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-gray-700">{label}</span>
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
