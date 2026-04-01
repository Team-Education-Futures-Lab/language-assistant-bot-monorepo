# Configuration Audit: Realtime Voice Service

## Currently Hardcoded Values (Already Configurable via .env)

All the following are already using `os.getenv()` with fallback defaults, so they can be modified via environment variables:

### 1. **OpenAI API Configuration**
- `OPENAI_API_KEY` (default: empty string `''`)
  - Type: Credential/String
  - Current: `os.getenv('OPENAI_API_KEY', '')`
  - Status: ✅ Already configurable

- `OPENAI_REALTIME_MODEL` (default: `'gpt-4o-mini-realtime-preview'`)
  - Type: String
  - Current: `os.getenv('OPENAI_REALTIME_MODEL', 'gpt-4o-mini-realtime-preview')`
  - Status: ✅ Already configurable

- `OPENAI_REALTIME_TRANSCRIPTION_MODEL` (default: `'whisper-1'`)
  - Type: String
  - Current: `os.getenv('OPENAI_REALTIME_TRANSCRIPTION_MODEL', 'whisper-1')`
  - Status: ✅ Already configurable

### 2. **Language & Voice Configuration**
- `OPENAI_REALTIME_LANGUAGE` (default: `'nl'`)
  - Type: String (language code)
  - Current: `os.getenv('OPENAI_REALTIME_LANGUAGE', 'nl')`
  - Status: ✅ Already configurable

- `OPENAI_REALTIME_VOICE` (default: `'alloy'`)
  - Type: String (OpenAI voice: alloy, echo, fable, onyx, nova, shimmer)
  - Current: `os.getenv('OPENAI_REALTIME_VOICE', 'alloy')`
  - Status: ✅ Already configurable
  - Note: Options are: alloy | echo | fable | onyx | nova | shimmer

### 3. **System Prompt Configuration**
- `OPENAI_REALTIME_SYSTEM_PROMPT` (default: `DEFAULT_OPENAI_REALTIME_SYSTEM_PROMPT`)
  - Type: String (long text prompt)
  - Current: Reads from `.env` or `DEFAULT_OPENAI_REALTIME_SYSTEM_PROMPT` hardcoded in code
  - Status: ⚠️ **HARDCODED FALLBACK** (can be overridden via env var)
  - Content: 7-rule Dutch language coaching prompt
  - Note: Alternative prompt is commented out in source code
  - Location: Lines 55-104 in `realtime_voice_service.py`

### 4. **OpenAI API Endpoints**
- `OPENAI_REALTIME_WS_URL` (default: `'wss://api.openai.com/v1/realtime'`)
  - Type: URL
  - Current: `os.getenv('OPENAI_REALTIME_WS_URL', 'wss://api.openai.com/v1/realtime')`
  - Status: ✅ Already configurable

- `OPENAI_REALTIME_API_BASE` (default: `'https://api.openai.com/v1'`)
  - Type: URL
  - Current: `os.getenv('OPENAI_REALTIME_API_BASE', 'https://api.openai.com/v1')`
  - Status: ✅ Already configurable

### 5. **Ephemeral Token Configuration**
- `OPENAI_REALTIME_USE_EPHEMERAL_TOKEN` (default: `'false'`)
  - Type: Boolean (converted from string: '1', 'true', 'yes', 'on' → True)
  - Current: `os.getenv('OPENAI_REALTIME_USE_EPHEMERAL_TOKEN', 'false')`
  - Status: ✅ Already configurable

### 6. **Voice Activity Detection (VAD) Configuration**
- `OPENAI_REALTIME_VAD_THRESHOLD` (default: `0.5`)
  - Type: Float
  - Current: `float(os.getenv('OPENAI_REALTIME_VAD_THRESHOLD', 0.5))`
  - Status: ✅ Already configurable
  - Range: Typically 0.0 to 1.0

- `OPENAI_REALTIME_VAD_SILENCE_MS` (default: `500`)
  - Type: Integer (milliseconds)
  - Current: `int(os.getenv('OPENAI_REALTIME_VAD_SILENCE_MS', 500))`
  - Status: ✅ Already configurable

- `OPENAI_REALTIME_PREFIX_PADDING_MS` (default: `300`)
  - Type: Integer (milliseconds)
  - Current: `int(os.getenv('OPENAI_REALTIME_PREFIX_PADDING_MS', 300))`
  - Status: ✅ Already configurable

### 7. **Timeout & Keepalive Configuration**
- `OPENAI_WS_TIMEOUT_SEC` (default: `180`)
  - Type: Float (seconds)
  - Current: `float(os.getenv('OPENAI_WS_TIMEOUT_SEC', 180))`
  - Status: ✅ Already configurable

- `OPENAI_WS_PING_INTERVAL_SEC` (default: `0` = disabled)
  - Type: Float (seconds)
  - Current: `float(os.getenv('OPENAI_WS_PING_INTERVAL_SEC', 0))`
  - Status: ✅ Already configurable

### 8. **Database/Retrieval Configuration**
- `DATABASE_MANAGER_URL` (default: `'http://localhost:5004'`)
  - Type: URL
  - Current: `os.getenv('DATABASE_MANAGER_URL', 'http://localhost:5004')`
  - Status: ✅ Already configurable

- `RETRIEVE_TOP_K` (default: `5`)
  - Type: Integer
  - Current: `int(os.getenv('RETRIEVE_TOP_K', 5))`
  - Status: ✅ Already configurable

- `RETRIEVE_TIMEOUT_SEC` (default: `4`)
  - Type: Float (seconds)
  - Current: `float(os.getenv('RETRIEVE_TIMEOUT_SEC', 4))`
  - Status: ✅ Already configurable

---

## Summary

### ✅ **Fully Configurable (14 settings)**
All major OpenAI API configurations in the realtime voice service **already support environment variable overrides**:
- API Key, Model, Voice, Language
- Endpoints and token settings
- VAD parameters (threshold, silence, padding)
- Timeouts and keepalive
- Retrieval settings (URL, top_k, timeout)

### ⚠️ **System Prompt: PARTIALLY HARDCODED (1 setting)**
- `DEFAULT_OPENAI_REALTIME_SYSTEM_PROMPT` is hardcoded in the Python source code (lines 55-104)
- Can be overridden via `OPENAI_REALTIME_SYSTEM_PROMPT` environment variable
- **Recommendation**: Create database schema to store system prompts and fetch them dynamically

### 🎯 **Next Steps for Flexible Configuration Dashboard**
To make these settings configurable through the **mbo-language-assistant-dashboard** frontend with **Supabase** persistence:

1. Create `openai_settings` table in Supabase
2. Add CRUD endpoints in **database-manager** service
3. Create UI components in **dashboard** to display/edit settings
4. Modify microservices to fetch settings from database instead of just .env
5. Implement fallback chain: Database → Environment Variables → Hardcoded Defaults

