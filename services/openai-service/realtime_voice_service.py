"""
Realtime Voice Service

Browser WebSocket -> API Gateway WebSocket proxy -> this service -> OpenAI Realtime API.

Conversation mode: STT + LLM + TTS in a single Realtime session.
Server-side VAD detects speech automatically, triggers LLM responses, and
streams audio back to the browser for seamless voice chat.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import requests
from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sock import Sock
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from simple_websocket import ConnectionClosed
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException, create_connection
from routes.http_routes import register_http_routes
from routes.ws_routes import register_ws_routes


SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SERVICE_DIR, '.env'))
load_dotenv(os.path.join(SERVICE_DIR, '.env.example'), override=False)

logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO),
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stderr,
)
log = logging.getLogger('realtime_voice')


APP_ENV = os.getenv('APP_ENV', os.getenv('FLASK_ENV', 'development')).lower()
SERVICE_HOST = os.getenv('SERVICE_HOST', 'localhost')
SERVICE_PORT = int(os.getenv('PORT', os.getenv('SERVICE_PORT', 5005)))
SERVICE_NAME = 'Realtime Voice Service'
RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '120 per minute')


def _get_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def _parse_allowed_gateway_origins():
    gateway_origin = os.getenv('API_GATEWAY_ORIGIN', 'http://localhost:5000').strip()
    extra_origins_raw = os.getenv('API_GATEWAY_ALLOWED_ORIGINS', '').strip()

    origins = [gateway_origin]
    if extra_origins_raw:
        origins.extend(origin.strip() for origin in extra_origins_raw.split(',') if origin.strip())

    unique_origins = []
    for origin in origins:
        if origin and origin not in unique_origins:
            unique_origins.append(origin)
    return unique_origins

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_REALTIME_MODEL_DEFAULT = os.getenv('OPENAI_REALTIME_MODEL', 'gpt-4o-mini-realtime-preview')
OPENAI_REALTIME_TRANSCRIPTION_MODEL = os.getenv('OPENAI_REALTIME_TRANSCRIPTION_MODEL', 'whisper-1')
OPENAI_REALTIME_VOICE_DEFAULT = os.getenv('OPENAI_REALTIME_VOICE', 'marin')
DEFAULT_OPENAI_REALTIME_SYSTEM_PROMPT = os.getenv(
    'DEFAULT_OPENAI_REALTIME_SYSTEM_PROMPT',
    (
        'You are my Dutch language coach. I am learning Dutch in the context of school subjects using my uploaded material (PDF, slides, or text)'
        '    Rules for this conversation:'
        '    1. Only use words and data from the uploaded material.'
        '    2. Speak in simple Dutch (B1 level).'
        '    3. Ask me questions about the material and guide me step by step to the correct answers.'
        '    4. Do not give me direct answers. Instead, use **subsequent guiding questions** and **keywords from the material** as hints.'
        '    5. If I give a wrong answer or use wrong vocabulary, clearly say: "Nee, dat is fout. In het dossier staat dat ..." and guide me to correct it.'
        '    6. Always ask follow-up questions to help me practice explaining, arguing, and giving detailed answers.'
        '    7. Focus on helping me **learn vocabulary**, **sentence structure**, and **argumentation skills** in the context of the subject material.'
        '    Start by asking me a simple question about the topic. Then guide me step by step using this method.'
    ),
)

OPENAI_REALTIME_SYSTEM_PROMPT = (
    os.getenv('OPENAI_REALTIME_SYSTEM_PROMPT')
    or os.getenv('OPENAI_REALTIME_SYSTEMP_PRMOPT')
    or DEFAULT_OPENAI_REALTIME_SYSTEM_PROMPT
)

OPENAI_REALTIME_WS_URL = os.getenv('OPENAI_REALTIME_WS_URL', 'wss://api.openai.com/v1/realtime')
OPENAI_REALTIME_API_BASE = os.getenv('OPENAI_REALTIME_API_BASE', 'https://api.openai.com/v1')
OPENAI_REALTIME_USE_EPHEMERAL_TOKEN = os.getenv(
    'OPENAI_REALTIME_USE_EPHEMERAL_TOKEN',
    'false',
).strip().lower() in ('1', 'true', 'yes', 'on')

DATABASE_MANAGER_URL = os.getenv('DATABASE_MANAGER_URL', 'http://localhost:5004')
DEFAULT_RETRIEVE_TOP_K = 5
DEFAULT_RETRIEVE_TIMEOUT_SEC = 4.0
OPENAI_WS_TIMEOUT_SEC = float(os.getenv('OPENAI_WS_TIMEOUT_SEC', 180))
OPENAI_WS_PING_INTERVAL_SEC = float(os.getenv('OPENAI_WS_PING_INTERVAL_SEC', 0))
OPENAI_REALTIME_SPEED_MIN = 0.25
OPENAI_REALTIME_SPEED_MAX = 1.5
OPENAI_REALTIME_SPEED_DEFAULT = 1.0
PROMPTS_CACHE_TTL_SEC = float(os.getenv('PROMPTS_CACHE_TTL_SEC', '30'))
RETRIEVE_LOG_FULL_PAYLOAD = _get_bool_env('RETRIEVE_LOG_FULL_PAYLOAD', default=False)

_prompts_cache_text = None
_prompts_cache_expires_at = 0.0


def _get_cached_prompts_text():
    if PROMPTS_CACHE_TTL_SEC <= 0:
        return None
    if _prompts_cache_text and time.time() < _prompts_cache_expires_at:
        return _prompts_cache_text
    return None


def _set_cached_prompts_text(value):
    global _prompts_cache_text, _prompts_cache_expires_at
    if PROMPTS_CACHE_TTL_SEC <= 0:
        _prompts_cache_text = None
        _prompts_cache_expires_at = 0.0
        return
    _prompts_cache_text = value
    _prompts_cache_expires_at = time.time() + PROMPTS_CACHE_TTL_SEC


def clamp_realtime_speed(value, default_value=OPENAI_REALTIME_SPEED_DEFAULT):
    try:
        speed_value = float(value)
    except (TypeError, ValueError):
        return default_value

    return min(OPENAI_REALTIME_SPEED_MAX, max(OPENAI_REALTIME_SPEED_MIN, speed_value))


def get_prompts_from_database():
    """
    Retrieve all active prompts from the database (global management).

    Returns:
        String containing the prompt(s) or None if database unavailable
    """
    cached = _get_cached_prompts_text()
    if cached:
        return cached

    try:
        response = requests.get(
            f'{DATABASE_MANAGER_URL}/prompts/active',
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                prompts = data.get('prompts', [])
                if prompts:
                    prompt_texts = [p['content'] for p in prompts if p.get('content')]
                    if prompt_texts:
                        merged_prompts = '\n\n'.join(prompt_texts)
                        _set_cached_prompts_text(merged_prompts)
                        print(f"✓ Using {len(prompt_texts)} active prompt(s) from database", file=sys.stderr)
                        return merged_prompts

        print("⚠ No prompts found in database - using configured fallback", file=sys.stderr)
        return None

    except Exception as e:
        print(f"Error accessing database for prompts: {e}", file=sys.stderr)
        return None


def get_effective_system_prompt() -> str:
    database_prompts = get_prompts_from_database()
    if database_prompts:
        return database_prompts
    return OPENAI_REALTIME_SYSTEM_PROMPT or ''


def get_runtime_setting(key: str, default_value, value_type=str):
    """Read runtime settings from database-manager with safe defaults."""
    try:
        response = requests.get(f'{DATABASE_MANAGER_URL}/settings/{key}', timeout=3)
        if response.status_code != 200:
            return default_value

        payload = response.json()
        setting = payload.get('setting', {})
        raw_value = setting.get('value', default_value)

        if value_type == int:
            return int(raw_value)
        if value_type == float:
            return float(raw_value)
        if value_type == bool:
            return str(raw_value).strip().lower() in ('1', 'true', 'yes', 'on')
        return str(raw_value)
    except Exception:
        return default_value


def get_openai_realtime_model() -> str:
    return get_runtime_setting('openai_realtime_model', OPENAI_REALTIME_MODEL_DEFAULT, str)


def get_openai_realtime_voice() -> str:
    return get_runtime_setting('openai_realtime_voice', OPENAI_REALTIME_VOICE_DEFAULT, str)


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": _parse_allowed_gateway_origins()}})
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[RATE_LIMIT_DEFAULT],
    storage_uri='memory://',
)
sock = Sock(app)

if _get_bool_env('USE_PROXY_FIX', default=(APP_ENV == 'production')):
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=int(os.getenv('PROXY_FIX_X_FOR', '1')),
        x_proto=int(os.getenv('PROXY_FIX_X_PROTO', '1')),
        x_host=int(os.getenv('PROXY_FIX_X_HOST', '1')),
        x_port=int(os.getenv('PROXY_FIX_X_PORT', '1')),
        x_prefix=int(os.getenv('PROXY_FIX_X_PREFIX', '1')),
    )


def build_openai_session_config(speed=OPENAI_REALTIME_SPEED_DEFAULT):
    openai_realtime_model = get_openai_realtime_model()
    openai_realtime_voice = get_openai_realtime_voice()
    normalized_speed = clamp_realtime_speed(speed)
    log.info(
        '[OPENAI] Resolved runtime settings model=%s voice=%s speed=%.2f',
        openai_realtime_model,
        openai_realtime_voice,
        normalized_speed,
    )
    return {
        "type": "realtime",
        "audio": {
            "input": {
                "transcription": {
                    "model": OPENAI_REALTIME_TRANSCRIPTION_MODEL
                },
                "turn_detection": {
                    "type": "server_vad",
                    "create_response": False
                }
            },
            "output": {
                "voice": openai_realtime_voice,
                "speed": normalized_speed
            }
        }
    }

# def build_openai_session_config() -> dict:
#     # type: 'realtime' only accepts this minimal config — all other fields are rejected.
#     # The server's default VAD auto-creates responses; no manual response.create needed.
#     return {
#         'type': 'realtime',
#     }


def build_dutch_system_message() -> dict:
    return {
        'type': 'conversation.item.create',
        'item': {
            'type': 'message',
            'role': 'system',
            'content': [
                {
                    'type': 'input_text',
                    'text': get_effective_system_prompt(),
                }
            ],
        },
    }


def extract_user_query_from_item(item: dict, state: dict, event: dict | None = None) -> str:
    if not isinstance(item, dict):
        return ''

    item_id = item.get('id', '')
    content = item.get('content', [])

    # Sometimes transcript is attached at item-level.
    top_level_transcript = (item.get('transcript') or '').strip()
    if top_level_transcript:
        return top_level_transcript

    # Some event variants may place transcript alongside item.
    if isinstance(event, dict):
        event_transcript = (event.get('transcript') or '').strip()
        if event_transcript:
            return event_transcript

    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue

            transcript_text = (part.get('audio_transcript') or '').strip()
            if transcript_text:
                return transcript_text

            transcript_text = (part.get('transcript') or '').strip()
            if transcript_text:
                return transcript_text

            text = (part.get('text') or '').strip()
            if text:
                return text

            input_text = (part.get('input_text') or '').strip()
            if input_text:
                return input_text

            output_text = (part.get('output_text') or '').strip()
            if output_text:
                return output_text

    formatted = item.get('formatted', {})
    if isinstance(formatted, dict):
        formatted_transcript = (formatted.get('transcript') or '').strip()
        if formatted_transcript:
            return formatted_transcript

        formatted_text = (formatted.get('text') or '').strip()
        if formatted_text:
            return formatted_text

    buffered = (state.get('transcript_buffers', {}).get(item_id, '') or '').strip()
    return buffered


def retrieve_external_context(user_query: str) -> dict:
    if not user_query:
        return {'context_found': False, 'formatted_context': '', 'retrieved_items': [], 'sources': [], 'chunk_count': 0}

    try:
        retrieve_timeout_sec = get_runtime_setting('retrieve_timeout_sec', DEFAULT_RETRIEVE_TIMEOUT_SEC, float)

        log.info('[RETRIEVE] Calling database manager /retrieve (using database-manager default k) for query=%r', user_query)
        retrieve_response = requests.post(
            f'{DATABASE_MANAGER_URL}/retrieve',
            json={
                'question': user_query,
            },
            timeout=retrieve_timeout_sec,
        )
        if retrieve_response.status_code != 200:
            log.warning(
                '[RETRIEVE] Non-200 response from database manager /retrieve: %s',
                retrieve_response.status_code,
            )
            return {'context_found': False, 'formatted_context': '', 'retrieved_items': [], 'sources': [], 'chunk_count': 0}

        payload = retrieve_response.json()
        if RETRIEVE_LOG_FULL_PAYLOAD:
            log.info(
                '[RETRIEVE] Database manager /retrieve payload:\n%s',
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
        if payload.get('status') != 'success':
            log.warning('[RETRIEVE] Database manager /retrieve returned non-success payload')
            return {'context_found': False, 'formatted_context': '', 'retrieved_items': [], 'sources': [], 'chunk_count': 0}

        log.info(
            '[RETRIEVE] Database manager response context_found=%s chunk_count=%s sources=%s',
            payload.get('context_found'),
            payload.get('chunk_count', 0),
            payload.get('sources', []),
        )
        return {
            'context_found': bool(payload.get('context_found')),
            'formatted_context': payload.get('formatted_context', '') or '',
            'retrieved_items': payload.get('retrieved_items', []) or [],
            'sources': payload.get('sources', []) or [],
            'chunk_count': int(payload.get('chunk_count', 0) or 0),
        }
    except Exception as error:
        log.warning('[RETRIEVE] Retrieval failed: %s', error)
        return {'context_found': False, 'formatted_context': '', 'retrieved_items': [], 'sources': [], 'chunk_count': 0}


def build_retrieval_system_message(formatted_context: str, sources: list[str], retrieved_items: list[dict] | None = None) -> dict:
    source_text = ', '.join(sources) if sources else 'onbekende bron'
    system_prompt = get_effective_system_prompt()

    if not formatted_context and retrieved_items:
        # Fallback only: database-manager should normally provide formatted_context.
        formatted_context = '\n\n'.join(
            f"--- Context from {(item.get('source_file') or 'Unknown Source')} ---\n{(item.get('content') or '').strip()}"
            for item in retrieved_items
            if (item.get('content') or '').strip()
        )

    # Merge default NT2 system prompt with retrieved context
    merged_text = (
        f"{system_prompt}\n\n"
        f"Gebruik de onderstaande context als primaire bron voor je antwoord. "
        f"Als informatie ontbreekt, zeg dat expliciet.\n"
        f"Bronnen: {source_text}.\n\n"
        f"{formatted_context}"
    )

    return {
        'type': 'conversation.item.create',
        'item': {
            'type': 'message',
            'role': 'system',
            'content': [
                {'type': 'input_text', 'text': merged_text}
            ],
        },
    }


def create_openai_client_secret(session_config: dict) -> str:
    response = requests.post(
        f'{OPENAI_REALTIME_API_BASE}/realtime/client_secrets',
        headers={
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json',
        },
        json={'session': session_config},
        timeout=15,
    )
    response.raise_for_status()

    payload = response.json()
    client_secret = payload.get('client_secret', {})
    secret_value = client_secret.get('value')
    if not secret_value:
        raise RuntimeError('OpenAI gaf geen ephemeral client secret terug')
    return secret_value


def connect_to_openai(session_config: dict):
    if not OPENAI_API_KEY:
        raise RuntimeError('OPENAI_API_KEY ontbreekt voor realtime voice streaming')

    openai_realtime_model = get_openai_realtime_model()
    log.info('[OPENAI] Connecting to OpenAI Realtime API, model=%s', openai_realtime_model)
    auth_token = OPENAI_API_KEY
    if OPENAI_REALTIME_USE_EPHEMERAL_TOKEN:
        log.info('[OPENAI] Fetching ephemeral token...')
        auth_token = create_openai_client_secret(session_config)
        log.info('[OPENAI] Ephemeral token obtained')

    ws_url = f'{OPENAI_REALTIME_WS_URL}?model={openai_realtime_model}'
    log.info('[OPENAI] WebSocket URL: %s', ws_url)
    openai_ws = create_connection(
        ws_url,
        header=[f'Authorization: Bearer {auth_token}'],
        timeout=OPENAI_WS_TIMEOUT_SEC,
        enable_multithread=True,
    )
    log.info('[OPENAI] WebSocket connected, sending session.update: %s', json.dumps(session_config))
    openai_ws.send(json.dumps({'type': 'session.update', 'session': session_config}))
    log.info('[OPENAI] session.update sent')
    return openai_ws


def send_browser(ws, payload: dict):
    ws.send(json.dumps(payload))


def send_openai(state: dict, payload: dict):
    with state['openai_send_lock']:
        state['openai_ws'].send(json.dumps(payload))


def maybe_start_openai_keepalive(state: dict):
    if OPENAI_WS_PING_INTERVAL_SEC <= 0:
        return None

    def run_keepalive():
        log.info('[KEEPALIVE] OpenAI ping enabled, interval=%ss', OPENAI_WS_PING_INTERVAL_SEC)
        while not state['closed']:
            time.sleep(OPENAI_WS_PING_INTERVAL_SEC)
            if state['closed']:
                break

            try:
                with state['openai_send_lock']:
                    state['openai_ws'].ping('keepalive')
            except WebSocketConnectionClosedException:
                break
            except Exception as error:
                log.warning('[KEEPALIVE] OpenAI ping failed: %s', error)
                break

    ping_thread = threading.Thread(target=run_keepalive, daemon=True)
    ping_thread.start()
    return ping_thread


def build_session_state(browser_ws):
    return {
        'browser_ws': browser_ws,
        'openai_ws': None,
        'openai_send_lock': threading.Lock(),
        'closed': False,
        'transcript_buffers': {},      # user speech transcripts keyed by item_id
        'assistant_text_buffer': '',   # accumulated assistant text for current response
        'current_response_id': None,
        'response_in_progress': False, # guard against duplicate response.create
        'last_retrieval_used': False,
        'last_retrieval_query': '',
        'last_retrieval_sources': [],
        'last_retrieval_chunk_count': 0,
        'last_retrieval_items_count': 0,
        'current_user_item_id': None,
        'openai_ping_thread': None,
        'playback_speed': OPENAI_REALTIME_SPEED_DEFAULT,
    }


def close_state(state: dict):
    log.info('[SESSION] Closing state, cleaning up OpenAI WebSocket')
    state['closed'] = True
    openai_ws = state.get('openai_ws')
    if openai_ws is not None:
        try:
            openai_ws.close()
            log.info('[SESSION] OpenAI WebSocket closed')
        except Exception:
            pass


def openai_listener(state: dict):
    browser_ws = state['browser_ws']
    log.info('[LISTENER] OpenAI listener thread started')

    try:
        while not state['closed']:
            try:
                raw_message = state['openai_ws'].recv()
            except WebSocketTimeoutException:
                # Keep waiting: timeout here does not mean the session is dead.
                continue

            if not raw_message:
                log.info('[LISTENER] Empty message received, closing listener')
                break

            event = json.loads(raw_message)
            event_type = event.get('type', '')

            # ── Session lifecycle ──────────────────────────────────────────────
            if event_type in ('session.created', 'session.updated'):
                log.info('[SESSION] %s received', event_type)
                send_browser(browser_ws, {'type': 'session.ready', 'eventType': event_type})
                continue

            # ── Server-side VAD speech detection ──────────────────────────────
            if event_type == 'input_audio_buffer.speech_started':
                log.info('[VAD] Speech started detected by server VAD')
                send_browser(browser_ws, {'type': 'speech.started'})
                continue

            if event_type == 'input_audio_buffer.speech_stopped':
                log.info('[VAD] Speech stopped detected by server VAD')
                send_browser(browser_ws, {'type': 'speech.stopped', 'reason': 'server_vad'})
                continue

            if event_type == 'input_audio_buffer.committed':
                item_id = event.get('item_id')
                log.info('[VAD] Audio buffer committed, item_id=%s', item_id)
                if item_id:
                    state['transcript_buffers'][item_id] = ''
                state['current_user_item_id'] = item_id
                state['last_retrieval_used'] = False
                state['last_retrieval_query'] = ''
                state['last_retrieval_sources'] = []
                state['last_retrieval_chunk_count'] = 0
                state['last_retrieval_items_count'] = 0
                send_browser(browser_ws, {'type': 'input.committed', 'itemId': item_id})
                continue

            # ── User speech transcription ──────────────────────────────────────
            if event_type == 'conversation.item.input_audio_transcription.delta':
                item_id = event.get('item_id', '')
                delta = event.get('delta', '') or ''
                if item_id not in state['transcript_buffers']:
                    state['transcript_buffers'][item_id] = ''
                state['transcript_buffers'][item_id] += delta
                send_browser(
                    browser_ws,
                    {
                        'type': 'transcript.delta',
                        'itemId': item_id,
                        'delta': delta,
                        'transcript': state['transcript_buffers'][item_id],
                    },
                )
                continue

            if event_type == 'conversation.item.input_audio_transcription.completed':
                item_id = event.get('item_id', '')
                transcript = (event.get('transcript') or '').strip()
                state['transcript_buffers'][item_id] = transcript
                log.info('[TRANSCRIPT] Final transcript item_id=%s text=%r', item_id, transcript)
                send_browser(
                    browser_ws,
                    {
                        'type': 'transcript.final',
                        'itemId': item_id,
                        'transcript': transcript,
                    },
                )

                if transcript:
                    log.info('[RETRIEVE] Triggering retrieval from transcription.completed for item_id=%s', item_id)
                    retrieval = retrieve_external_context(transcript)
                    state['last_retrieval_query'] = transcript
                    if retrieval.get('context_found') and retrieval.get('formatted_context'):
                        state['last_retrieval_used'] = True
                        state['last_retrieval_sources'] = retrieval.get('sources', [])
                        state['last_retrieval_chunk_count'] = retrieval.get('chunk_count', 0)
                        state['last_retrieval_items_count'] = len(retrieval.get('retrieved_items', []))
                        send_openai(
                            state,
                            build_retrieval_system_message(
                                retrieval['formatted_context'],
                                retrieval.get('sources', []),
                                retrieval.get('retrieved_items', []),
                            ),
                        )
                        log.info(
                            '[RETRIEVE] Injected context into conversation (chunks=%s, sources=%s)',
                            retrieval.get('chunk_count', 0),
                            retrieval.get('sources', []),
                        )
                        preview = retrieval['formatted_context'].replace('\n', ' ')[:220]
                        log.info('[RETRIEVE] Context preview: %s%s', preview, '...' if len(retrieval['formatted_context']) > 220 else '')
                        send_browser(
                            browser_ws,
                            {
                                'type': 'retrieval.context',
                                'query': transcript,
                                'chunkCount': retrieval.get('chunk_count', 0),
                                'retrievedItemsCount': len(retrieval.get('retrieved_items', [])),
                                'sources': retrieval.get('sources', []),
                            },
                        )
                    else:
                        state['last_retrieval_used'] = False
                        state['last_retrieval_sources'] = []
                        state['last_retrieval_chunk_count'] = 0
                        state['last_retrieval_items_count'] = 0
                        log.info('[RETRIEVE] No context found for transcript query')

                    send_openai(state, {
                        "type": "response.create"
                    })
                    log.info('[RESPONSE] response.create sent after transcription completion')
                else:
                    state['last_retrieval_used'] = False
                    state['last_retrieval_query'] = ''
                    state['last_retrieval_sources'] = []
                    state['last_retrieval_chunk_count'] = 0
                    state['last_retrieval_items_count'] = 0
                    log.info('[RETRIEVE] Skipped: no user query text available')
                continue

            if event_type == 'conversation.item.done':
                # Retrieval is intentionally handled in transcription.completed.
                continue

            # ── Assistant response lifecycle ───────────────────────────────────
            if event_type == 'response.created':
                response_id = event.get('response', {}).get('id')
                state['current_response_id'] = response_id
                state['response_in_progress'] = True
                state['assistant_text_buffer'] = ''
                log.info('[RESPONSE] response.created id=%s', response_id)
                log.info(
                    '[RESPONSE] retrieval_used=%s chunks=%s items=%s sources=%s query=%r',
                    state.get('last_retrieval_used'),
                    state.get('last_retrieval_chunk_count', 0),
                    state.get('last_retrieval_items_count', 0),
                    state.get('last_retrieval_sources', []),
                    state.get('last_retrieval_query', ''),
                )
                send_browser(browser_ws, {
                    'type': 'assistant.response.started',
                    'responseId': response_id,
                })
                continue

            if event_type == 'response.output_item.added':
                item = event.get('item', {})
                if item.get('type') == 'message' and item.get('role') == 'assistant':
                    send_browser(browser_ws, {
                        'type': 'assistant.message.started',
                        'itemId': item.get('id'),
                    })
                continue

            # ── Assistant audio transcript (text of what assistant is saying) ──
            if event_type == 'response.output_audio_transcript.delta':
                delta = event.get('delta', '') or ''
                state['assistant_text_buffer'] += delta
                send_browser(browser_ws, {
                    'type': 'assistant.text.delta',
                    'delta': delta,
                    'text': state['assistant_text_buffer'],
                })
                continue

            if event_type == 'response.output_audio_transcript.done':
                transcript = (event.get('transcript') or '').strip()
                state['assistant_text_buffer'] = transcript
                log.info('[ASSISTANT TEXT] Final: %r', transcript)
                send_browser(browser_ws, {
                    'type': 'assistant.text.final',
                    'text': transcript,
                })
                continue

            # ── Assistant audio chunks ─────────────────────────────────────────
            if event_type == 'response.output_audio.delta':
                audio_delta = event.get('delta', '') or ''
                if audio_delta:
                    send_browser(browser_ws, {
                        'type': 'assistant.audio.delta',
                        'audio': audio_delta,
                    })
                continue

            if event_type == 'response.output_audio.done':
                log.info('[AUDIO] audio.done')
                send_browser(browser_ws, {'type': 'assistant.audio.done'})
                continue

            if event_type == 'response.done':
                state['response_in_progress'] = False
                log.info('[RESPONSE] response.done id=%s', state.get('current_response_id'))
                send_browser(browser_ws, {'type': 'response.done'})
                continue

            if event_type in ('response.failed', 'response.cancelled'):
                state['response_in_progress'] = False
                log.info('[RESPONSE] %s id=%s', event_type, state.get('current_response_id'))
                send_browser(browser_ws, {'type': 'response.done'})
                continue

            # ── Errors ────────────────────────────────────────────────────────
            if event_type == 'error':
                error = event.get('error', {})
                log.error('[OPENAI ERROR] code=%s message=%s', error.get('code'), error.get('message'))
                send_browser(browser_ws, {
                    'type': 'error',
                    'message': error.get('message', 'OpenAI realtime fout'),
                    'code': error.get('code'),
                })
                continue

            # Ignore other OpenAI event types to avoid noisy logs.

    except WebSocketConnectionClosedException:
        log.info('[LISTENER] OpenAI WebSocket connection closed')
    except Exception as error:
        log.exception('[LISTENER] Unexpected error in openai_listener: %s', error)
        if not state['closed']:
            try:
                send_browser(browser_ws, {
                    'type': 'error',
                    'message': f'Realtime upstream verbinding verbroken: {error}',
                })
            except Exception:
                pass
    finally:
        log.info('[LISTENER] Listener thread exiting, closing state')
        close_state(state)


# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

route_context = {
    'limiter': limiter,
    'RATE_LIMIT_DEFAULT': RATE_LIMIT_DEFAULT,
    'SERVICE_NAME': SERVICE_NAME,
    'OPENAI_API_KEY': OPENAI_API_KEY,
    'SERVICE_HOST': SERVICE_HOST,
    'SERVICE_PORT': SERVICE_PORT,
    'OPENAI_REALTIME_SPEED_DEFAULT': OPENAI_REALTIME_SPEED_DEFAULT,
    'log': log,
    'clamp_realtime_speed': clamp_realtime_speed,
    'build_openai_session_config': build_openai_session_config,
    'build_session_state': build_session_state,
    'connect_to_openai': connect_to_openai,
    'maybe_start_openai_keepalive': maybe_start_openai_keepalive,
    'build_dutch_system_message': build_dutch_system_message,
    'openai_listener': openai_listener,
    'send_openai': send_openai,
    'send_browser': send_browser,
    'close_state': close_state,
    'get_openai_realtime_model': get_openai_realtime_model,
    'get_openai_realtime_voice': get_openai_realtime_voice,
}

register_http_routes(app, route_context)
register_ws_routes(sock, route_context)


if __name__ == '__main__':
    log.info('Starting %s on http://%s:%s', SERVICE_NAME, SERVICE_HOST, SERVICE_PORT)
    log.info(
        'Model: %s | Voice: %s | API key present: %s',
        get_openai_realtime_model(),
        get_openai_realtime_voice(),
        bool(OPENAI_API_KEY),
    )
    app.run(host=SERVICE_HOST, port=SERVICE_PORT, debug=False, threaded=True)


if __name__ != '__main__':
    log.info('Realtime voice service loaded by WSGI server')
