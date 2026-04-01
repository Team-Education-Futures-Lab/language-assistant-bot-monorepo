"""
API Gateway - Central Backend Service
Acts as the main entry point for all client requests and routes them to appropriate microservices.
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_sock import Sock
import requests
import os
import json
import threading
import time
from urllib.parse import quote
from functools import wraps
from dotenv import load_dotenv
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException, create_connection


SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SERVICE_DIR, '.env'))
load_dotenv(os.path.join(SERVICE_DIR, '.env.example'), override=False)

# Initialize Flask appW
app = Flask(__name__)
sock = Sock(app)

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})

# ============================================================================
# SERVICE CONFIGURATION
# ============================================================================

# Text Input Service Configuration
TEXT_SERVICE_URL = os.getenv('TEXT_SERVICE_URL', 'http://localhost:5001')

# Speech Input Service Configuration  
SPEECH_SERVICE_URL = os.getenv('SPEECH_SERVICE_URL', 'http://localhost:5002')

# Retrieve Service Configuration
RETRIEVE_SERVICE_URL = os.getenv('RETRIEVE_SERVICE_URL', 'http://localhost:5003')

# Database Manager Service Configuration
DATABASE_SERVICE_URL = os.getenv('DATABASE_SERVICE_URL', 'http://localhost:5004')

# Realtime Voice Service Configuration
REALTIME_VOICE_SERVICE_URL = os.getenv('REALTIME_VOICE_SERVICE_URL', 'http://localhost:5005')
REALTIME_VOICE_SERVICE_WS_URL = os.getenv(
    'REALTIME_VOICE_SERVICE_WS_URL',
    'ws://localhost:5005/ws/realtime-voice'
)
GATEWAY_BACKEND_WS_TIMEOUT_SEC = float(os.getenv('GATEWAY_BACKEND_WS_TIMEOUT_SEC', 180))
GATEWAY_BACKEND_WS_PING_INTERVAL_SEC = float(os.getenv('GATEWAY_BACKEND_WS_PING_INTERVAL_SEC', 0))

# API Gateway Configuration
GATEWAY_HOST = os.getenv('GATEWAY_HOST', 'localhost')
GATEWAY_PORT = int(os.getenv('GATEWAY_PORT', 5000))

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'API Gateway is running',
        'services': {
            'text_service': TEXT_SERVICE_URL,
            'speech_service': SPEECH_SERVICE_URL,
            'retrieve_service': RETRIEVE_SERVICE_URL,
            'database_service': DATABASE_SERVICE_URL,
            'realtime_voice_service': REALTIME_VOICE_SERVICE_URL,
        }
    }), 200

@app.route('/health', methods=['GET'])
def health_detailed():
    """Detailed health check with service status"""
    services_status = {}
    
    # Check text service
    try:
        response = requests.get(f'{TEXT_SERVICE_URL}/health', timeout=2)
        services_status['text_service'] = {
            'status': 'healthy' if response.status_code == 200 else 'unhealthy',
            'url': TEXT_SERVICE_URL
        }
    except Exception as e:
        services_status['text_service'] = {
            'status': 'unreachable',
            'url': TEXT_SERVICE_URL,
            'error': str(e)
        }
    
    # Check speech service
    try:
        response = requests.get(f'{SPEECH_SERVICE_URL}/health', timeout=2)
        services_status['speech_service'] = {
            'status': 'healthy' if response.status_code == 200 else 'unhealthy',
            'url': SPEECH_SERVICE_URL
        }
    except Exception as e:
        services_status['speech_service'] = {
            'status': 'unreachable',
            'url': SPEECH_SERVICE_URL,
            'error': str(e)
        }

    # Check retrieve service
    try:
        response = requests.get(f'{RETRIEVE_SERVICE_URL}/health', timeout=2)
        services_status['retrieve_service'] = {
            'status': 'healthy' if response.status_code == 200 else 'unhealthy',
            'url': RETRIEVE_SERVICE_URL
        }
    except Exception as e:
        services_status['retrieve_service'] = {
            'status': 'unreachable',
            'url': RETRIEVE_SERVICE_URL,
            'error': str(e)
        }

    # Check realtime voice service
    try:
        response = requests.get(f'{REALTIME_VOICE_SERVICE_URL}/health', timeout=2)
        services_status['realtime_voice_service'] = {
            'status': 'healthy' if response.status_code == 200 else 'unhealthy',
            'url': REALTIME_VOICE_SERVICE_URL
        }
    except Exception as e:
        services_status['realtime_voice_service'] = {
            'status': 'unreachable',
            'url': REALTIME_VOICE_SERVICE_URL,
            'error': str(e)
        }
    
    # Determine overall gateway status
    all_healthy = all(s['status'] == 'healthy' for s in services_status.values())
    
    return jsonify({
        'status': 'healthy' if all_healthy else 'degraded',
        'gateway': {
            'host': GATEWAY_HOST,
            'port': GATEWAY_PORT
        },
        'services': services_status
    }), 200 if all_healthy else 503

# ============================================================================
# TEXT QUERY ENDPOINT
# ============================================================================

@app.route('/api/query/text', methods=['POST'])
def query_text():
    """
    Route text-based queries to the Text Input Service
    
    Expected JSON payload:
    {
        "question": "Your question here",
        "enable_tts": false (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing "question" field in request body'
            }), 400
        
        # Forward request to text service with streaming
        response = requests.post(
            f'{TEXT_SERVICE_URL}/query',
            json=data,
            timeout=150,  # Increased to allow text service's 120s Ollama timeout + overhead
            stream=True
        )
        
        if response.status_code != 200:
            return jsonify({
                'status': 'error',
                'message': response.text or f'Text Service error: {response.status_code}'
            }), response.status_code
        
        # Stream response back to client
        def generate():
            try:
                for line in response.iter_lines():
                    if line:
                        yield line + b'\n'
            except Exception as e:
                yield json.dumps({
                    'status': 'error',
                    'message': f'Error forwarding response: {str(e)}'
                }).encode() + b'\n'
        
        return Response(
            generate(),
            mimetype='application/x-ndjson'
        )
        
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'error',
            'message': f'Could not connect to Text Service at {TEXT_SERVICE_URL}. Is it running?'
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': 'Text Service request timed out'
        }), 504
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error communicating with Text Service: {str(e)}'
        }), 500

# ============================================================================
# SPEECH QUERY ENDPOINT
# ============================================================================

@app.route('/api/query/speech', methods=['POST'])
def query_speech():
    """
    Route speech-based queries to the Speech Input Service
    
    Expected: multipart/form-data with audio file and optional parameters
    - audio: Audio file (WAV, MP3, etc.)
    - enable_tts: Whether to return audio response (optional, default: true)
    """
    try:
        if 'audio' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'Missing audio file in request'
            }), 400
        
        audio_file = request.files['audio']
        enable_tts = request.form.get('enable_tts', 'true').lower() == 'true'
        
        # Prepare form data for speech service
        audio_file.seek(0)
        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({
                'status': 'error',
                'message': 'Uploaded audio file is empty'
            }), 400

        files = {
            'audio': (
                audio_file.filename or 'audio.wav',
                audio_bytes,
                audio_file.content_type or 'application/octet-stream'
            )
        }
        data = {'enable_tts': enable_tts}
        
        # Forward request to speech service
        response = requests.post(
            f'{SPEECH_SERVICE_URL}/query',
            files=files,
            data=data,
            timeout=120
        )
        
        return response.json(), response.status_code
        
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'error',
            'message': f'Could not connect to Speech Service at {SPEECH_SERVICE_URL}. Is it running?'
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': 'Speech Service request timed out'
        }), 504
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error communicating with Speech Service: {str(e)}'
        }), 500

# ============================================================================
# TTS SYNTHESIS ENDPOINT
# ============================================================================

@app.route('/api/tts', methods=['POST'])
def synthesize_tts():
    """
    Proxy text-to-speech requests to Speech Input Service

    Expected JSON payload:
    {
        "text": "Text to synthesize"
    }
    """
    try:
        data = request.get_json()

        if not data or 'text' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing "text" field in request body'
            }), 400

        response = requests.post(
            f'{SPEECH_SERVICE_URL}/synthesize',
            json={'text': data['text']},
            timeout=60
        )

        if response.status_code != 200:
            try:
                error_data = response.json()
                return jsonify(error_data), response.status_code
            except Exception:
                return jsonify({
                    'status': 'error',
                    'message': response.text or f'Speech Service error: {response.status_code}'
                }), response.status_code

        return Response(
            response.content,
            mimetype=response.headers.get('Content-Type', 'audio/wav'),
            headers={
                'Content-Disposition': response.headers.get('Content-Disposition', 'attachment; filename=response.wav')
            }
        )

    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'error',
            'message': f'Could not connect to Speech Service at {SPEECH_SERVICE_URL}. Is it running?'
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': 'Speech Service TTS request timed out'
        }), 504
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error communicating with Speech Service TTS: {str(e)}'
        }), 500

# ============================================================================
# UNIFIED QUERY ENDPOINT (Auto-detects input type)
# ============================================================================

@app.route('/api/query', methods=['POST'])
def query_unified():
    """
    Unified query endpoint that accepts both text and speech inputs.
    
    For text queries:
    {
        "type": "text",
        "question": "Your question here",
        "enable_tts": false (optional)
    }
    
    For speech queries:
    multipart/form-data with:
    - type: "speech"
    - audio: Audio file
    - enable_tts: Whether to return audio response (optional)
    """
    try:
        content_type = request.content_type or ''
        
        # Check if it's JSON (text query)
        if 'application/json' in content_type:
            data = request.get_json()
            
            if not data or 'question' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing "question" field in request body'
                }), 400
            
            query_type = data.get('type', 'text')
            
            if query_type == 'speech':
                return jsonify({
                    'status': 'error',
                    'message': 'Speech queries must be sent as multipart/form-data with audio file'
                }), 400
            
            # Route to text service with streaming
            response = requests.post(
                f'{TEXT_SERVICE_URL}/query',
                json=data,
                timeout=150,  # Increased to allow text service's 120s Ollama timeout + overhead
                stream=True
            )
            
            if response.status_code != 200:
                return jsonify({
                    'status': 'error',
                    'message': response.text or f'Text Service error: {response.status_code}'
                }), response.status_code
            
            # Stream response back to client
            def generate():
                try:
                    for line in response.iter_lines():
                        if line:
                            yield line + b'\n'
                except Exception as e:
                    yield json.dumps({
                        'status': 'error',
                        'message': f'Error forwarding response: {str(e)}'
                    }).encode() + b'\n'
            
            return Response(
                generate(),
                mimetype='application/x-ndjson'
            )
        
        # Check if it's multipart (speech query)
        elif 'multipart/form-data' in content_type:
            if 'audio' not in request.files:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing audio file in request'
                }), 400
            
            audio_file = request.files['audio']
            enable_tts = request.form.get('enable_tts', 'true').lower() == 'true'
            
            # Prepare form data for speech service
            files = {'audio': (audio_file.filename, audio_file.stream, audio_file.content_type)}
            data = {'enable_tts': enable_tts}
            
            # Route to speech service
            response = requests.post(
                f'{SPEECH_SERVICE_URL}/query',
                files=files,
                data=data,
                timeout=120
            )
            return response.json(), response.status_code
        
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid content type. Use application/json for text or multipart/form-data for speech'
            }), 400
    
    except requests.exceptions.ConnectionError as e:
        service = 'Text Service' if 'application/json' in (request.content_type or '') else 'Speech Service'
        return jsonify({
            'status': 'error',
            'message': f'Could not connect to {service}. Is it running?'
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': 'Service request timed out'
        }), 504
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error processing request: {str(e)}'
        }), 500

# ============================================================================
# DATABASE MANAGEMENT ENDPOINTS (Subjects & Prompts)
# ============================================================================

# --- Subjects Endpoints ---

@app.route('/api/subjects', methods=['GET', 'POST'])
def subjects():
    """Proxy for subjects list and create"""
    try:
        if request.method == 'GET':
            response = requests.get(f'{DATABASE_SERVICE_URL}/subjects', timeout=10)
        else:  # POST
            response = requests.post(
                f'{DATABASE_SERVICE_URL}/subjects',
                json=request.get_json(),
                timeout=10
            )
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/subjects/<int:subject_id>', methods=['GET', 'PUT', 'DELETE'])
def subject_detail(subject_id):
    """Proxy for subject detail, update, delete"""
    try:
        if request.method == 'GET':
            response = requests.get(f'{DATABASE_SERVICE_URL}/subjects/{subject_id}', timeout=10)
        elif request.method == 'PUT':
            response = requests.put(
                f'{DATABASE_SERVICE_URL}/subjects/{subject_id}',
                json=request.get_json(),
                timeout=10
            )
        else:  # DELETE
            response = requests.delete(f'{DATABASE_SERVICE_URL}/subjects/{subject_id}', timeout=10)
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/subjects/<int:subject_id>/upload', methods=['POST'])
def subject_upload(subject_id):
    """Proxy for file upload"""
    try:
        files = {'file': (request.files['file'].filename, request.files['file'].stream, request.files['file'].content_type)}
        response = requests.post(
            f'{DATABASE_SERVICE_URL}/subjects/{subject_id}/upload',
            files=files,
            timeout=300
        )
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/subjects/<int:subject_id>/uploads/<path:upload_name>', methods=['DELETE'])
def subject_upload_delete(subject_id, upload_name):
    """Proxy for deleting an upload and all related chunks"""
    try:
        response = requests.delete(
            f'{DATABASE_SERVICE_URL}/subjects/{subject_id}/uploads/{quote(upload_name, safe="")}',
            timeout=30
        )
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/subjects/<int:subject_id>/chunks', methods=['GET', 'POST'])
def subject_chunks(subject_id):
    """Proxy for getting and creating chunks"""
    try:
        if request.method == 'GET':
            response = requests.get(f'{DATABASE_SERVICE_URL}/subjects/{subject_id}/chunks', timeout=10)
        else:  # POST
            response = requests.post(
                f'{DATABASE_SERVICE_URL}/subjects/{subject_id}/chunks',
                json=request.get_json(),
                timeout=10
            )
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- Prompts Endpoints (Global Management) ---

@app.route('/api/prompts', methods=['GET', 'POST'])
def prompts():
    """Proxy for getting and creating prompts (global management)"""
    try:
        if request.method == 'GET':
            response = requests.get(f'{DATABASE_SERVICE_URL}/prompts', timeout=10)
        else:  # POST
            response = requests.post(
                f'{DATABASE_SERVICE_URL}/prompts',
                json=request.get_json(),
                timeout=10
            )
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/prompts/active', methods=['GET'])
def prompts_active():
    """Proxy for getting active prompts (used by LLM services)"""
    try:
        response = requests.get(f'{DATABASE_SERVICE_URL}/prompts/active', timeout=10)
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/prompts/<int:prompt_id>', methods=['GET', 'PUT', 'DELETE'])
def prompt_detail(prompt_id):
    """Proxy for prompt detail, update, delete"""
    try:
        if request.method == 'GET':
            response = requests.get(f'{DATABASE_SERVICE_URL}/prompts/{prompt_id}', timeout=10)
        elif request.method == 'PUT':
            response = requests.put(
                f'{DATABASE_SERVICE_URL}/prompts/{prompt_id}',
                json=request.get_json(),
                timeout=10
            )
        else:  # DELETE
            response = requests.delete(f'{DATABASE_SERVICE_URL}/prompts/{prompt_id}', timeout=10)
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- Settings Endpoints (Runtime Configuration) ---

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    """Proxy for getting and creating/updating settings"""
    try:
        if request.method == 'GET':
            response = requests.get(
                f'{DATABASE_SERVICE_URL}/settings',
                params=request.args,
                timeout=10
            )
        else:  # POST
            response = requests.post(
                f'{DATABASE_SERVICE_URL}/settings',
                json=request.get_json(),
                timeout=10
            )
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/settings/<key>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def setting_detail(key):
    """Proxy for setting detail, update, and delete"""
    try:
        if request.method == 'GET':
            response = requests.get(f'{DATABASE_SERVICE_URL}/settings/{key}', timeout=10)
        elif request.method == 'PUT':
            response = requests.put(
                f'{DATABASE_SERVICE_URL}/settings/{key}',
                json=request.get_json(),
                timeout=10
            )
        elif request.method == 'PATCH':
            response = requests.patch(
                f'{DATABASE_SERVICE_URL}/settings/{key}',
                json=request.get_json(),
                timeout=10
            )
        else:  # DELETE
            response = requests.delete(f'{DATABASE_SERVICE_URL}/settings/{key}', timeout=10)
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- Live STT Endpoints (Streaming-like chunked transcription) ---

@app.route('/api/live-stt/start', methods=['POST'])
def live_stt_start():
    """Start a live STT session."""
    try:
        response = requests.post(f'{SPEECH_SERVICE_URL}/live-stt/start', json=request.get_json(silent=True) or {}, timeout=10)
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/live-stt/chunk', methods=['POST'])
def live_stt_chunk():
    """Send one audio chunk for live STT partial transcription."""
    try:
        if 'audio' not in request.files:
            return jsonify({'status': 'error', 'message': 'Audiobestand ontbreekt in verzoek'}), 400

        audio_file = request.files['audio']
        files = {
            'audio': (audio_file.filename, audio_file.stream, audio_file.content_type)
        }
        data = {
            'session_id': request.form.get('session_id', ''),
            'is_final': request.form.get('is_final', 'false')
        }

        response = requests.post(
            f'{SPEECH_SERVICE_URL}/live-stt/chunk',
            files=files,
            data=data,
            timeout=180
        )
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/live-stt/chunk-with-response', methods=['POST'])
def live_stt_chunk_with_response():
    """NEW: Send one audio chunk for live STT AND auto-generate AI response."""
    try:
        if 'audio' not in request.files:
            return jsonify({'status': 'error', 'message': 'Audiobestand ontbreekt in verzoek'}), 400

        audio_file = request.files['audio']
        files = {
            'audio': (audio_file.filename, audio_file.stream, audio_file.content_type)
        }
        data = {
            'session_id': request.form.get('session_id', ''),
            'is_final': request.form.get('is_final', 'false')
        }

        response = requests.post(
            f'{SPEECH_SERVICE_URL}/live-stt/chunk-with-response',
            files=files,
            data=data,
            timeout=180
        )
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/live-stt/finalize', methods=['POST'])
def live_stt_finalize():
    """Finalize a live STT session and return the full transcript."""
    try:
        response = requests.post(
            f'{SPEECH_SERVICE_URL}/live-stt/finalize',
            json=request.get_json(silent=True) or {},
            timeout=10
        )
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/live-stt/session/<session_id>', methods=['DELETE'])
def live_stt_abort(session_id):
    """Abort and delete a live STT session."""
    try:
        response = requests.delete(f'{SPEECH_SERVICE_URL}/live-stt/session/{session_id}', timeout=10)
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@sock.route('/ws/realtime-voice')
def realtime_voice_proxy(ws):
    backend_ws = create_connection(
        REALTIME_VOICE_SERVICE_WS_URL,
        timeout=GATEWAY_BACKEND_WS_TIMEOUT_SEC,
        enable_multithread=True,
    )
    stop_event = threading.Event()

    def forward_backend_to_browser():
        try:
            while not stop_event.is_set():
                try:
                    message = backend_ws.recv()
                except WebSocketTimeoutException:
                    continue

                if not message:
                    break
                ws.send(message)
        except Exception:
            pass
        finally:
            stop_event.set()

    def keep_backend_alive():
        if GATEWAY_BACKEND_WS_PING_INTERVAL_SEC <= 0:
            return

        while not stop_event.is_set():
            time.sleep(GATEWAY_BACKEND_WS_PING_INTERVAL_SEC)
            if stop_event.is_set():
                break

            try:
                backend_ws.ping('gateway-keepalive')
            except (WebSocketConnectionClosedException, WebSocketTimeoutException):
                break
            except Exception:
                break

    backend_thread = threading.Thread(target=forward_backend_to_browser, daemon=True)
    backend_thread.start()
    ping_thread = threading.Thread(target=keep_backend_alive, daemon=True)
    ping_thread.start()

    try:
        while not stop_event.is_set():
            message = ws.receive()
            if message is None:
                break
            backend_ws.send(message)
    finally:
        stop_event.set()
        try:
            backend_ws.close()
        except Exception:
            pass

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    print(f"\n{'='*70}")
    print(f"API Gateway - Central Backend Service")
    print(f"{'='*70}")
    print(f"\nStarting API Gateway on http://{GATEWAY_HOST}:{GATEWAY_PORT}")
    print(f"\nRouting to services:")
    print(f"  - Text Service:   {TEXT_SERVICE_URL}")
    print(f"  - Speech Service: {SPEECH_SERVICE_URL}")
    print(f"\nEndpoints:")
    print(f"  - Health Check:        GET  http://{GATEWAY_HOST}:{GATEWAY_PORT}/health")
    print(f"  - Text Query:          POST http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/text")
    print(f"  - Speech Query:        POST http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/speech")
    print(f"  - Unified Query:       POST http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query")
    print(f"\nAPI Gateway is ready to receive requests...\n")
    print(f"{'='*70}\n")
    
    app.run(host=GATEWAY_HOST, port=GATEWAY_PORT, debug=False)
