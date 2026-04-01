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
import re
import sys
import threading
import time
import requests
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sock import Sock
from dotenv import load_dotenv
from simple_websocket import ConnectionClosed
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException, create_connection


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


SERVICE_HOST = os.getenv('SERVICE_HOST', 'localhost')
SERVICE_PORT = int(os.getenv('SERVICE_PORT', 5005))
SERVICE_NAME = 'Realtime Voice Service'

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_REALTIME_MODEL = os.getenv('OPENAI_REALTIME_MODEL', 'gpt-4o-mini-realtime-preview')
OPENAI_REALTIME_TRANSCRIPTION_MODEL = os.getenv('OPENAI_REALTIME_TRANSCRIPTION_MODEL', 'whisper-1')
OPENAI_REALTIME_LANGUAGE = os.getenv('OPENAI_REALTIME_LANGUAGE', 'nl')
OPENAI_REALTIME_VOICE = os.getenv('OPENAI_REALTIME_VOICE', 'fable')

# system prompt

DEFAULT_OPENAI_REALTIME_SYSTEM_PROMPT = (
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
)

# DEFAULT_OPENAI_REALTIME_SYSTEM_PROMPT = (
#     'System Instructions: NT2 Spoken Exam Practice (Universal Voice Assistant Mode)\n'
#     'Your Role & Context:\n'
#     'You are a patient Dutch language tutor helping an NT2 (Dutch as a Second Language) student practice speaking for an oral exam.\n'
#     'STRICT KNOWLEDGE & VOCABULARY BOUNDARY (ZERO HALLUCINATION):\n'
#     'The exam and all practice questions MUST be based entirely and exclusively on the specific document(s) uploaded by the user.\n'
#     '- For your own speech (The AI): You must actively use the exact technical terms, jargon, and phrasing found in the uploaded document. Do not invent your own synonyms. While you must use simple B1-level grammar, NEVER simplify the technical terms from the text.\n'
#     '- No Outside Knowledge: You are strictly forbidden from using outside knowledge, facts, or industry standards that are not explicitly written in the uploaded text. If a topic is not in the text, say exactly: "Dat staat niet in het document. Laten we het houden bij de tekst." and ask a new question.\n'
#     'CRITICAL RULES FOR VOICE CONVERSATION (STRICT RESPONSE SIZE):\n'
#     'You are functioning as a voice assistant. Your responses must be exactly 2 to 3 short sentences (around 20 to 40 words total).\n'
#     '- NO lists. NO bullet points. NO long paragraphs.\n'
#     '- Every response must follow this simple 3-part conversational structure:\n'
#     '1. Feedback: ("Dat is goed", "Precies", "Dat is fout", "Dat klopt niet helemaal").\n'
#     '2. Correction/Context: Correct their grammar, enforce the right vocabulary from the text, or give a tiny hint.\n'
#     '3. One Open-Ended Question: End with an open question that forces the student to speak 1 or 2 full sentences (e.g., "Hoe doe je dat precies?", "Waarom is dat belangrijk?"). NEVER ask yes/no questions or questions that can be answered with one word.\n'
#     'How to Handle the Student\'s Answers (The Socratic Loop):\n'
#     '- Explicitly Say "Wrong": If the student\'s answer is factually incorrect based on the uploaded text, you MUST explicitly say so (e.g., "Dat is fout", "Dat klopt niet", of "Dat is niet juist").\n'
#     '- Strict Vocabulary Correction (For the Student): If the student uses informal or simple words instead of the specific professional terms from the uploaded document, correct them immediately (e.g., "Je zegt [informal word], maar in het document gebruiken we de term [professional term from text]."). Demand that they use the correct term in their next answer.\n'
#     '- If the student gives a wrong answer or use wrong vocabulary, clearly say: "Nee, dat is fout. In het dossier staat dat ..." and guide the student to correct it.\n'
#     '- Always ask follow-up questions to help the student practice explaining, arguing, and giving detailed answers.\n'
#     '- Simplify if needed: If the student says they don\'t understand, repeat the question using simpler B1-level verbs/grammar, but keep the technical nouns from the text intact.\n'
#     'Dynamic Conversation Flow:\n'
#     '- If the user asks a question (and it is in the text): Answer it briefly using ONLY the exact concepts and words from the text, then ask a follow-up question.\n'
#     '- If the user just says hello or waits: You take the lead. Pick a key concept from the uploaded document and ask an open-ended "Waarom" (Why) or "Hoe" (How) question.\n'
#     'GOLD STANDARD EXAMPLES (Copy this exact length and tone, adapting to the uploaded subject):\n'
#     '- "Dat is al beter, maar let op de termen. In het document staat dat je [Term from text] nodig hebt, zodat [Term from text] duidelijk is. Kun je beschrijven hoe je dat precies toepast?"\n'
#     '- "Dat klopt niet helemaal. In de tekst staat dat je controleert op [Term 1] en [Term 2]. Kun je uitleggen wat je precies doet als je een afwijking vindt?"\n'
#     '- "Precies. En kun je ook beschrijven wat je doet als er een probleem is met de [Technical term from text]? Hoe pas je dan je werk aan?"\n'
#     '- "Dat staat niet in het document, dus daar hoef je je geen zorgen over te maken. Laten we teruggaan naar de tekst: Waarom is het belangrijk dat je [Action from text] goed uitvoert?"\n'
#     'How to Start:\n'
#     'Do not give any lists or introductions. Read the uploaded document to extract the specific vocabulary and subject. Greet the user briefly in simple B1 Dutch, and immediately ask your first open-ended question using a core term from the text. Wait for the user\'s voice response.'
# )

OPENAI_REALTIME_SYSTEM_PROMPT = (
    os.getenv('OPENAI_REALTIME_SYSTEM_PROMPT')
    or os.getenv('OPENAI_REALTIME_SYSTEMP_PRMOPT')
)

OPENAI_REALTIME_WS_URL = os.getenv('OPENAI_REALTIME_WS_URL', 'wss://api.openai.com/v1/realtime')
OPENAI_REALTIME_API_BASE = os.getenv('OPENAI_REALTIME_API_BASE', 'https://api.openai.com/v1')
OPENAI_REALTIME_USE_EPHEMERAL_TOKEN = os.getenv(
    'OPENAI_REALTIME_USE_EPHEMERAL_TOKEN',
    'false',
).strip().lower() in ('1', 'true', 'yes', 'on')

OPENAI_REALTIME_VAD_THRESHOLD = float(os.getenv('OPENAI_REALTIME_VAD_THRESHOLD', 0.5))
OPENAI_REALTIME_VAD_SILENCE_MS = int(os.getenv('OPENAI_REALTIME_VAD_SILENCE_MS', 500))
OPENAI_REALTIME_PREFIX_PADDING_MS = int(os.getenv('OPENAI_REALTIME_PREFIX_PADDING_MS', 300))

DATABASE_MANAGER_URL = os.getenv('DATABASE_MANAGER_URL', 'http://localhost:5004')
RETRIEVE_TOP_K = int(os.getenv('RETRIEVE_TOP_K', 5))
RETRIEVE_TIMEOUT_SEC = float(os.getenv('RETRIEVE_TIMEOUT_SEC', 4))
OPENAI_WS_TIMEOUT_SEC = float(os.getenv('OPENAI_WS_TIMEOUT_SEC', 180))
OPENAI_WS_PING_INTERVAL_SEC = float(os.getenv('OPENAI_WS_PING_INTERVAL_SEC', 0))


def get_prompts_from_database():
    """
    Retrieve all active prompts from the database (global management).

    Returns:
        String containing the prompt(s) or None if database unavailable
    """
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
                        print(f"✓ Using {len(prompt_texts)} active prompt(s) from database", file=sys.stderr)
                        return '\n\n'.join(prompt_texts)

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


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
sock = Sock(app)


def build_openai_session_config():
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


def tokenize_text(text: str) -> list[str]:
    if not text:
        return []
    return [token for token in re.findall(r'\w+', text.lower()) if len(token) > 2]


def rank_chunk_records(user_query: str, chunk_records: list[dict], k: int) -> list[dict]:
    query_tokens = set(tokenize_text(user_query))
    if not query_tokens:
        return chunk_records[:k]

    scored_chunks = []
    query_lower = user_query.lower()

    for chunk in chunk_records:
        content = (chunk.get('content') or '').lower()
        if not content.strip():
            continue

        content_tokens = set(tokenize_text(content))
        overlap_score = len(query_tokens.intersection(content_tokens))
        phrase_bonus = 2 if query_lower in content else 0
        score = overlap_score + phrase_bonus

        if score > 0:
            scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored_chunks[:k]]


def format_chunk_records_for_llm(chunks: list[dict]) -> str:
    parts = []
    for index, chunk in enumerate(chunks, start=1):
        source_filename = os.path.basename(chunk.get('source_file') or 'Unknown Source')
        parts.append(f'--- Context from {source_filename} (Chunk {index}) ---')
        parts.append((chunk.get('content') or '').strip())
        parts.append('')
    return '\n'.join(parts).strip()


def retrieve_external_context(user_query: str) -> dict:
    if not user_query:
        return {'context_found': False, 'formatted_context': '', 'sources': [], 'chunk_count': 0}

    try:
        log.info('[RETRIEVE] Calling database manager (k=%s) for query=%r', RETRIEVE_TOP_K, user_query)
        subjects_response = requests.get(
            f'{DATABASE_MANAGER_URL}/subjects',
            timeout=RETRIEVE_TIMEOUT_SEC,
        )
        if subjects_response.status_code != 200:
            log.warning('[RETRIEVE] Non-200 response from database manager /subjects: %s', subjects_response.status_code)
            return {'context_found': False, 'formatted_context': '', 'sources': [], 'chunk_count': 0}

        subjects_payload = subjects_response.json()
        subjects = subjects_payload.get('subjects', []) or []
        all_chunks = []

        for subject in subjects:
            subject_id = subject.get('id')
            if subject_id is None:
                continue

            chunks_response = requests.get(
                f'{DATABASE_MANAGER_URL}/subjects/{subject_id}/chunks',
                timeout=RETRIEVE_TIMEOUT_SEC,
            )
            if chunks_response.status_code != 200:
                log.warning(
                    '[RETRIEVE] Skipping subject %s because /chunks returned %s',
                    subject_id,
                    chunks_response.status_code,
                )
                continue

            chunks_payload = chunks_response.json()
            all_chunks.extend(chunks_payload.get('chunks', []) or [])

        ranked_chunks = rank_chunk_records(user_query, all_chunks, RETRIEVE_TOP_K)
        if not ranked_chunks:
            log.info('[RETRIEVE] No matching chunks found in database manager')
            return {'context_found': False, 'formatted_context': '', 'sources': [], 'chunk_count': 0}

        sources = []
        for chunk in ranked_chunks:
            source_filename = os.path.basename(chunk.get('source_file') or 'Unknown Source')
            if source_filename not in sources:
                sources.append(source_filename)

        payload = {
            'context_found': True,
            'formatted_context': format_chunk_records_for_llm(ranked_chunks),
            'sources': sources,
            'chunk_count': len(ranked_chunks),
        }
        log.info(
            '[RETRIEVE] Database manager response context_found=%s chunk_count=%s sources=%s',
            payload.get('context_found'),
            payload.get('chunk_count', 0),
            payload.get('sources', []),
        )
        return {
            'context_found': bool(payload.get('context_found')),
            'formatted_context': payload.get('formatted_context', '') or '',
            'sources': payload.get('sources', []) or [],
            'chunk_count': int(payload.get('chunk_count', 0) or 0),
        }
    except Exception as error:
        log.warning('[RETRIEVE] Retrieval failed: %s', error)
        return {'context_found': False, 'formatted_context': '', 'sources': [], 'chunk_count': 0}


def build_retrieval_system_message(formatted_context: str, sources: list[str]) -> dict:
    source_text = ', '.join(sources) if sources else 'onbekende bron'
    system_prompt = get_effective_system_prompt()

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

    log.info('[OPENAI] Connecting to OpenAI Realtime API, model=%s', OPENAI_REALTIME_MODEL)
    auth_token = OPENAI_API_KEY
    if OPENAI_REALTIME_USE_EPHEMERAL_TOKEN:
        log.info('[OPENAI] Fetching ephemeral token...')
        auth_token = create_openai_client_secret(session_config)
        log.info('[OPENAI] Ephemeral token obtained')

    ws_url = f'{OPENAI_REALTIME_WS_URL}?model={OPENAI_REALTIME_MODEL}'
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
        'current_user_item_id': None,
        'openai_ping_thread': None,
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
                        send_openai(
                            state,
                            build_retrieval_system_message(
                                retrieval['formatted_context'],
                                retrieval.get('sources', []),
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
                                'sources': retrieval.get('sources', []),
                            },
                        )
                    else:
                        state['last_retrieval_used'] = False
                        state['last_retrieval_sources'] = []
                        state['last_retrieval_chunk_count'] = 0
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
                    '[RESPONSE] retrieval_used=%s chunks=%s sources=%s query=%r',
                    state.get('last_retrieval_used'),
                    state.get('last_retrieval_chunk_count', 0),
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


@app.route('/', methods=['GET'])
def root():
    return jsonify(
        {
            'status': 'ok',
            'service': SERVICE_NAME,
            'message': 'Realtime voice service is actief',
        }
    ), 200


@app.route('/health', methods=['GET'])
def health():
    api_key_present = bool(OPENAI_API_KEY)

    return jsonify(
        {
            'status': 'ok' if api_key_present else 'degraded',
            'service': SERVICE_NAME,
            'openai_api_key_configured': api_key_present,
            'service_host': SERVICE_HOST,
            'service_port': SERVICE_PORT,
            'model': OPENAI_REALTIME_MODEL,
            'voice': OPENAI_REALTIME_VOICE,
        }
    ), 200 if api_key_present else 503


@sock.route('/ws/realtime-voice')
def realtime_voice_socket(ws):
    log.info('[BROWSER WS] New browser WebSocket connection')
    state = build_session_state(ws)

    try:
        while True:
            raw_message = ws.receive()
            if raw_message is None:
                log.info('[BROWSER WS] Browser disconnected (None message)')
                break

            payload = json.loads(raw_message)
            message_type = payload.get('type', '')

            if message_type == 'session.start':
                log.info('[SESSION] session.start received from browser')
                session_config = build_openai_session_config()
                state['openai_ws'] = connect_to_openai(session_config)
                state['openai_ping_thread'] = maybe_start_openai_keepalive(state)
                send_openai(state, build_dutch_system_message())
                log.info('[SESSION] Dutch system instruction injected into conversation context')
                threading.Thread(target=openai_listener, args=(state,), daemon=True).start()
                log.info('[SESSION] Listener thread started, sending session.started to browser')
                send_browser(
                    ws,
                    {
                        'type': 'session.started',
                        'message': 'Realtime sessie gestart',
                    },
                )
                continue

            if message_type == 'audio.chunk':
                if state['openai_ws'] is None:
                    log.warning('[AUDIO] audio.chunk received but session not started')
                    send_browser(ws, {'type': 'error', 'message': 'Realtime sessie is nog niet gestart'})
                    continue

                if state.get('response_in_progress'):
                    continue

                audio_b64 = payload.get('audio', '')
                if not audio_b64:
                    continue

                send_openai(
                    state,
                    {
                        'type': 'input_audio_buffer.append',
                        'audio': audio_b64,
                    },
                )
                continue

            if message_type == 'recording.stop':
                log.info('[SESSION] recording.stop received from browser, keeping session open for response audio')
                continue

            if message_type == 'session.close':
                log.info('[SESSION] session.close received from browser')
                break

            # Ignore unknown browser message types.

    except ConnectionClosed:
        log.info('[BROWSER WS] Browser closed connection normally')
    except Exception as error:
        log.exception('[BROWSER WS] Error in realtime_voice_socket: %s', error)
        try:
            send_browser(ws, {'type': 'error', 'message': str(error)})
        except Exception:
            pass
    finally:
        log.info('[BROWSER WS] Browser WebSocket handler exiting')
        close_state(state)


if __name__ == '__main__':
    log.info('Starting %s on http://%s:%s', SERVICE_NAME, SERVICE_HOST, SERVICE_PORT)
    log.info('Model: %s | Voice: %s | API key present: %s', OPENAI_REALTIME_MODEL, OPENAI_REALTIME_VOICE, bool(OPENAI_API_KEY))
    app.run(host=SERVICE_HOST, port=SERVICE_PORT, debug=False, threaded=True)
