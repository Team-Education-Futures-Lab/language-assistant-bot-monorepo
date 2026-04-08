"""
API Gateway - Central Backend Service
Acts as the main entry point for all client requests and routes them to appropriate microservices.
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_sock import Sock
import requests
import os
import threading
import time
from urllib.parse import quote
from functools import wraps
from dotenv import load_dotenv
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException, create_connection


SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SERVICE_DIR, '.env'))

# Initialize Flask appW
app = Flask(__name__)
sock = Sock(app)

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})

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

@app.route('/api/query/health', methods=['GET'])
def health_detailed():
    """Detailed health check with service status"""
    services_status = {}

    # Check database manager service
    try:
        response = requests.get(f'{DATABASE_SERVICE_URL}/health', timeout=2)
        services_status['database_service'] = {
            'status': 'healthy' if response.status_code == 200 else 'unhealthy',
            'url': DATABASE_SERVICE_URL
        }
    except Exception as e:
        services_status['database_service'] = {
            'status': 'unreachable',
            'url': DATABASE_SERVICE_URL,
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
# DATABASE MANAGEMENT ENDPOINTS (Subjects & Prompts)
# ============================================================================

# --- Subjects Endpoints ---

@app.route('/api/query/subjects', methods=['GET', 'POST'])
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

@app.route('/api/query/subjects/<int:subject_id>', methods=['GET', 'PUT', 'DELETE'])
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

@app.route('/api/query/subjects/<int:subject_id>/upload', methods=['POST'])
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


@app.route('/api/query/subjects/<int:subject_id>/uploads/<path:upload_name>', methods=['DELETE'])
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

@app.route('/api/query/subjects/<int:subject_id>/chunks', methods=['GET', 'POST'])
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

@app.route('/api/query/prompts', methods=['GET', 'POST'])
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

@app.route('/api/query/prompts/active', methods=['GET'])
def prompts_active():
    """Proxy for getting active prompts (used by LLM services)"""
    try:
        response = requests.get(f'{DATABASE_SERVICE_URL}/prompts/active', timeout=10)
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/query/prompts/<int:prompt_id>', methods=['GET', 'PUT', 'DELETE'])
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

@app.route('/api/query/settings', methods=['GET', 'POST'])
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

@app.route('/api/query/settings/<key>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
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


@app.route('/api/query/retrieve', methods=['POST'])
def retrieve_context():
    """Proxy retrieval requests to Database Manager."""
    try:
        response = requests.post(
            f'{DATABASE_SERVICE_URL}/retrieve',
            json=request.get_json(),
            timeout=30
        )
        return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@sock.route('/api/query/ws/realtime-voice')
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
    print(f"  - Database Service: {DATABASE_SERVICE_URL}")
    print(f"  - Realtime Voice:   {REALTIME_VOICE_SERVICE_URL}")
    print(f"\nEndpoints:")
    print(f"  - Health Check:        GET  http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/health")
    print(f"  - Subjects:            GET/POST http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/subjects")
    print(f"  - Prompts:             GET/POST http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/prompts")
    print(f"  - Settings:            GET/POST http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/settings")
    print(f"  - Retrieve:            POST http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/retrieve")
    print(f"  - Realtime WS:         ws://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/ws/realtime-voice")
    print(f"\nAPI Gateway is ready to receive requests...\n")
    print(f"{'='*70}\n")
    
    app.run(host=GATEWAY_HOST, port=GATEWAY_PORT, debug=False)
