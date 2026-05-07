from pathlib import Path
import json
import sys
import importlib.util

from flask import Flask

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))


def _load_module(module_name, relative_path):
    module_path = SERVICE_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


http_routes_module = _load_module('openai_service_http_routes', Path('routes') / 'http_routes.py')
ws_routes_module = _load_module('openai_service_ws_routes', Path('routes') / 'ws_routes.py')

register_http_routes = http_routes_module.register_http_routes
register_ws_routes = ws_routes_module.register_ws_routes


class NoopLimiter:
    def limit(self, _rate):
        def decorator(func):
            return func

        return decorator


def build_http_client(openai_api_key=''):
    app = Flask(__name__)
    context = {
        'limiter': NoopLimiter(),
        'RATE_LIMIT_DEFAULT': '120 per minute',
        'SERVICE_NAME': 'Realtime Voice Service',
        'OPENAI_API_KEY': openai_api_key,
        'SERVICE_HOST': 'localhost',
        'SERVICE_PORT': 5005,
        'get_openai_realtime_model': lambda: 'gpt-realtime-mini',
        'get_openai_realtime_voice': lambda: 'marin',
    }
    register_http_routes(app, context)
    app.config.update(TESTING=True)
    return app.test_client()


class FakeSock:
    def __init__(self):
        self.routes = {}

    def route(self, path):
        def decorator(func):
            self.routes[path] = func
            return func

        return decorator


class FakeWS:
    def __init__(self, messages):
        self._messages = list(messages)
        self.sent = []

    def receive(self):
        if not self._messages:
            return None
        return self._messages.pop(0)


class FakeLogger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
        return None


def test_http_root_and_health_degraded_without_key():
    client = build_http_client(openai_api_key='')

    root = client.get('/')
    assert root.status_code == 200
    assert root.get_json()['service'] == 'Realtime Voice Service'

    health = client.get('/health')
    assert health.status_code == 503
    assert health.get_json()['status'] == 'degraded'


def test_http_health_ok_with_key():
    client = build_http_client(openai_api_key='sk-test')
    health = client.get('/health')

    assert health.status_code == 200
    payload = health.get_json()
    assert payload['status'] == 'ok'
    assert payload['openai_api_key_configured'] is True


def test_ws_realtime_voice_endpoint_handles_session_flow_with_mocks():
    sent_to_openai = []
    sent_to_browser = []
    close_state_calls = []

    def build_session_state(ws):
        return {
            'ws': ws,
            'openai_ws': None,
            'openai_ping_thread': None,
            'playback_speed': 1.0,
            'subject_id': None,
            'language_level': None,
            'response_in_progress': False,
        }

    def send_openai(state, payload):
        sent_to_openai.append(payload)

    def send_browser(ws, payload):
        ws.sent.append(payload)
        sent_to_browser.append(payload)

    def close_state(state):
        close_state_calls.append(state)

    fake_sock = FakeSock()
    context = {
        'log': FakeLogger(),
        'clamp_realtime_speed': lambda v: 1.1,
        'OPENAI_REALTIME_SPEED_DEFAULT': 1.0,
        'build_openai_session_config': lambda speed=1.0: {'speed': speed},
        'build_session_state': build_session_state,
        'connect_to_openai': lambda session_config: {'connected': True, 'config': session_config},
        'maybe_start_openai_keepalive': lambda state: 'ping-thread',
        'build_dutch_system_message': lambda level: {'type': 'conversation.item.create', 'level': level},
        'openai_listener': lambda state: None,
        'send_openai': send_openai,
        'send_browser': send_browser,
        'close_state': close_state,
        'ALLOWED_CEFR_LEVELS': ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
    }

    register_ws_routes(fake_sock, context)
    handler = fake_sock.routes['/ws/realtime-voice']

    ws = FakeWS([
        json.dumps({'type': 'session.start', 'subject_id': 3, 'language_level': 'B1', 'speed': 1.25}),
        json.dumps({'type': 'session.update', 'speed': 1.2}),
        json.dumps({'type': 'audio.chunk', 'audio': 'ZmFrZQ=='}),
        json.dumps({'type': 'recording.stop'}),
        json.dumps({'type': 'session.close'}),
    ])

    handler(ws)

    assert any(message.get('type') == 'session.started' for message in ws.sent)
    assert any(message.get('type') == 'session.updated' for message in ws.sent)
    assert any(payload.get('type') == 'input_audio_buffer.append' for payload in sent_to_openai)
    assert len(close_state_calls) == 1


def test_ws_realtime_voice_endpoint_validates_inputs():
    sent_to_browser = []

    def send_browser(ws, payload):
        ws.sent.append(payload)
        sent_to_browser.append(payload)

    fake_sock = FakeSock()
    context = {
        'log': FakeLogger(),
        'clamp_realtime_speed': lambda v: 1.0,
        'OPENAI_REALTIME_SPEED_DEFAULT': 1.0,
        'build_openai_session_config': lambda speed=1.0: {'speed': speed},
        'build_session_state': lambda ws: {
            'ws': ws,
            'openai_ws': None,
            'openai_ping_thread': None,
            'playback_speed': 1.0,
            'subject_id': None,
            'language_level': None,
            'response_in_progress': False,
        },
        'connect_to_openai': lambda session_config: {'connected': True},
        'maybe_start_openai_keepalive': lambda state: None,
        'build_dutch_system_message': lambda level: {'type': 'conversation.item.create'},
        'openai_listener': lambda state: None,
        'send_openai': lambda state, payload: None,
        'send_browser': send_browser,
        'close_state': lambda state: None,
        'ALLOWED_CEFR_LEVELS': ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
    }

    register_ws_routes(fake_sock, context)
    handler = fake_sock.routes['/ws/realtime-voice']

    ws_bad_subject = FakeWS([
        json.dumps({'type': 'session.start', 'subject_id': 'bad', 'language_level': 'B1'}),
        json.dumps({'type': 'session.close'}),
    ])
    handler(ws_bad_subject)
    assert any('subject_id must be a valid integer' in msg.get('message', '') for msg in sent_to_browser)

    sent_to_browser.clear()
    ws_bad_level = FakeWS([
        json.dumps({'type': 'session.start', 'subject_id': 1, 'language_level': 'Z9'}),
        json.dumps({'type': 'session.close'}),
    ])
    handler(ws_bad_level)
    assert any('language_level must be one of' in msg.get('message', '') for msg in sent_to_browser)


# ============================================================================
# ADDITIONAL COMPREHENSIVE TESTS
# ============================================================================

def test_http_root_endpoint_info():
    """Test root endpoint returns correct service info."""
    client = build_http_client(openai_api_key='sk-test')
    
    response = client.get('/')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert 'service' in data
    assert 'message' in data
    assert 'Realtime' in data['message'] or 'actief' in data['message'].lower()


def test_http_health_endpoint_with_key_includes_model_and_voice():
    """Test health endpoint includes model and voice configuration."""
    client = build_http_client(openai_api_key='sk-test')
    
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert 'model' in data
    assert 'voice' in data
    assert data['model'] == 'gpt-realtime-mini'
    assert data['voice'] == 'marin'
    assert data['service_host'] == 'localhost'
    assert data['service_port'] == 5005


def test_http_invalid_methods_on_endpoints():
    """Test that invalid HTTP methods are rejected."""
    client = build_http_client(openai_api_key='sk-test')
    
    # POST to root (only GET allowed)
    response = client.post('/')
    assert response.status_code == 405
    
    # PUT to health (only GET allowed)
    response = client.put('/health')
    assert response.status_code == 405
    
    # DELETE to health (only GET allowed)
    response = client.delete('/health')
    assert response.status_code == 405


def test_ws_session_start_without_parameters():
    """Test session.start with minimal/no optional parameters."""
    sent_to_browser = []
    
    def send_browser(ws, payload):
        ws.sent.append(payload)
        sent_to_browser.append(payload)

    fake_sock = FakeSock()
    context = {
        'log': FakeLogger(),
        'clamp_realtime_speed': lambda v: 1.0,
        'OPENAI_REALTIME_SPEED_DEFAULT': 1.0,
        'build_openai_session_config': lambda speed=1.0: {'speed': speed},
        'build_session_state': lambda ws: {
            'ws': ws,
            'openai_ws': None,
            'openai_ping_thread': None,
            'playback_speed': 1.0,
            'subject_id': None,
            'language_level': None,
            'response_in_progress': False,
        },
        'connect_to_openai': lambda session_config: {'connected': True},
        'maybe_start_openai_keepalive': lambda state: None,
        'build_dutch_system_message': lambda level: {'type': 'conversation.item.create', 'level': level},
        'openai_listener': lambda state: None,
        'send_openai': lambda state, payload: None,
        'send_browser': send_browser,
        'close_state': lambda state: None,
        'ALLOWED_CEFR_LEVELS': ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
    }

    register_ws_routes(fake_sock, context)
    handler = fake_sock.routes['/ws/realtime-voice']

    # Start session with no optional parameters
    ws = FakeWS([
        json.dumps({'type': 'session.start'}),
        json.dumps({'type': 'session.close'}),
    ])
    handler(ws)
    
    assert any(message.get('type') == 'session.started' for message in ws.sent)


def test_ws_all_valid_cefr_levels():
    """Test all valid CEFR levels (A1, A2, B1, B2, C1, C2)."""
    levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    
    for level in levels:
        sent_to_browser = []
        
        def send_browser(ws, payload):
            ws.sent.append(payload)
            sent_to_browser.append(payload)

        fake_sock = FakeSock()
        context = {
            'log': FakeLogger(),
            'clamp_realtime_speed': lambda v: 1.0,
            'OPENAI_REALTIME_SPEED_DEFAULT': 1.0,
            'build_openai_session_config': lambda speed=1.0: {'speed': speed},
            'build_session_state': lambda ws: {
                'ws': ws,
                'openai_ws': None,
                'openai_ping_thread': None,
                'playback_speed': 1.0,
                'subject_id': None,
                'language_level': None,
                'response_in_progress': False,
            },
            'connect_to_openai': lambda session_config: {'connected': True},
            'maybe_start_openai_keepalive': lambda state: None,
            'build_dutch_system_message': lambda lvl: {'type': 'conversation.item.create', 'level': lvl},
            'openai_listener': lambda state: None,
            'send_openai': lambda state, payload: None,
            'send_browser': send_browser,
            'close_state': lambda state: None,
            'ALLOWED_CEFR_LEVELS': tuple(levels),
        }

        register_ws_routes(fake_sock, context)
        handler = fake_sock.routes['/ws/realtime-voice']

        ws = FakeWS([
            json.dumps({'type': 'session.start', 'language_level': level}),
            json.dumps({'type': 'session.close'}),
        ])
        handler(ws)
        
        assert any(message.get('type') == 'session.started' for message in ws.sent), f"Failed for level {level}"


def test_ws_session_update_without_active_session():
    """Test session.update fails gracefully when session not started."""
    sent_to_browser = []
    
    def send_browser(ws, payload):
        ws.sent.append(payload)
        sent_to_browser.append(payload)

    fake_sock = FakeSock()
    context = {
        'log': FakeLogger(),
        'clamp_realtime_speed': lambda v: 1.0,
        'OPENAI_REALTIME_SPEED_DEFAULT': 1.0,
        'build_openai_session_config': lambda speed=1.0: {'speed': speed},
        'build_session_state': lambda ws: {
            'ws': ws,
            'openai_ws': None,
            'openai_ping_thread': None,
            'playback_speed': 1.0,
            'subject_id': None,
            'language_level': None,
            'response_in_progress': False,
        },
        'connect_to_openai': lambda session_config: {'connected': True},
        'maybe_start_openai_keepalive': lambda state: None,
        'build_dutch_system_message': lambda level: {'type': 'conversation.item.create'},
        'openai_listener': lambda state: None,
        'send_openai': lambda state, payload: None,
        'send_browser': send_browser,
        'close_state': lambda state: None,
        'ALLOWED_CEFR_LEVELS': ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
    }

    register_ws_routes(fake_sock, context)
    handler = fake_sock.routes['/ws/realtime-voice']

    # Try to update session without starting it
    ws = FakeWS([
        json.dumps({'type': 'session.update', 'speed': 1.2}),
        json.dumps({'type': 'session.close'}),
    ])
    handler(ws)
    
    # Check for error message sent to browser
    assert any(msg.get('type') == 'error' for msg in sent_to_browser)


def test_ws_audio_chunk_without_active_session():
    """Test audio.chunk fails gracefully when session not started."""
    sent_to_browser = []
    
    def send_browser(ws, payload):
        ws.sent.append(payload)
        sent_to_browser.append(payload)

    fake_sock = FakeSock()
    context = {
        'log': FakeLogger(),
        'clamp_realtime_speed': lambda v: 1.0,
        'OPENAI_REALTIME_SPEED_DEFAULT': 1.0,
        'build_openai_session_config': lambda speed=1.0: {'speed': speed},
        'build_session_state': lambda ws: {
            'ws': ws,
            'openai_ws': None,
            'openai_ping_thread': None,
            'playback_speed': 1.0,
            'subject_id': None,
            'language_level': None,
            'response_in_progress': False,
        },
        'connect_to_openai': lambda session_config: {'connected': True},
        'maybe_start_openai_keepalive': lambda state: None,
        'build_dutch_system_message': lambda level: {'type': 'conversation.item.create'},
        'openai_listener': lambda state: None,
        'send_openai': lambda state, payload: None,
        'send_browser': send_browser,
        'close_state': lambda state: None,
        'ALLOWED_CEFR_LEVELS': ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
    }

    register_ws_routes(fake_sock, context)
    handler = fake_sock.routes['/ws/realtime-voice']

    # Try to send audio without starting session
    ws = FakeWS([
        json.dumps({'type': 'audio.chunk', 'audio': 'ZmFrZQ=='}),
        json.dumps({'type': 'session.close'}),
    ])
    handler(ws)
    
    # Check for error message sent to browser
    assert any(msg.get('type') == 'error' for msg in sent_to_browser)


def test_ws_speed_boundary_values():
    """Test speed clamping with boundary values."""
    speeds = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]
    
    for speed in speeds:
        sent_to_browser = []
        
        def send_browser(ws, payload):
            ws.sent.append(payload)
            sent_to_browser.append(payload)

        def clamp_speed(v):
            # Typical clamp behavior: 0.5 to 2.0
            return max(0.5, min(2.0, v))

        fake_sock = FakeSock()
        context = {
            'log': FakeLogger(),
            'clamp_realtime_speed': clamp_speed,
            'OPENAI_REALTIME_SPEED_DEFAULT': 1.0,
            'build_openai_session_config': lambda speed=1.0: {'speed': speed},
            'build_session_state': lambda ws: {
                'ws': ws,
                'openai_ws': None,
                'openai_ping_thread': None,
                'playback_speed': 1.0,
                'subject_id': None,
                'language_level': None,
                'response_in_progress': False,
            },
            'connect_to_openai': lambda session_config: {'connected': True},
            'maybe_start_openai_keepalive': lambda state: None,
            'build_dutch_system_message': lambda level: {'type': 'conversation.item.create'},
            'openai_listener': lambda state: None,
            'send_openai': lambda state, payload: None,
            'send_browser': send_browser,
            'close_state': lambda state: None,
            'ALLOWED_CEFR_LEVELS': ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
        }

        register_ws_routes(fake_sock, context)
        handler = fake_sock.routes['/ws/realtime-voice']

        ws = FakeWS([
            json.dumps({'type': 'session.start', 'speed': speed}),
            json.dumps({'type': 'session.close'}),
        ])
        handler(ws)
        
        assert any(message.get('type') == 'session.started' for message in ws.sent), f"Failed for speed {speed}"


def test_ws_subject_id_edge_cases():
    """Test subject_id with various edge cases."""
    subject_ids = [0, 1, 999, 1000000]
    
    for subject_id in subject_ids:
        sent_to_browser = []
        
        def send_browser(ws, payload):
            ws.sent.append(payload)
            sent_to_browser.append(payload)

        fake_sock = FakeSock()
        context = {
            'log': FakeLogger(),
            'clamp_realtime_speed': lambda v: 1.0,
            'OPENAI_REALTIME_SPEED_DEFAULT': 1.0,
            'build_openai_session_config': lambda speed=1.0: {'speed': speed},
            'build_session_state': lambda ws: {
                'ws': ws,
                'openai_ws': None,
                'openai_ping_thread': None,
                'playback_speed': 1.0,
                'subject_id': None,
                'language_level': None,
                'response_in_progress': False,
            },
            'connect_to_openai': lambda session_config: {'connected': True},
            'maybe_start_openai_keepalive': lambda state: None,
            'build_dutch_system_message': lambda level: {'type': 'conversation.item.create'},
            'openai_listener': lambda state: None,
            'send_openai': lambda state, payload: None,
            'send_browser': send_browser,
            'close_state': lambda state: None,
            'ALLOWED_CEFR_LEVELS': ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
        }

        register_ws_routes(fake_sock, context)
        handler = fake_sock.routes['/ws/realtime-voice']

        ws = FakeWS([
            json.dumps({'type': 'session.start', 'subject_id': subject_id}),
            json.dumps({'type': 'session.close'}),
        ])
        handler(ws)
        
        assert any(message.get('type') == 'session.started' for message in ws.sent), f"Failed for subject_id {subject_id}"


def test_ws_empty_audio_chunk_ignored():
    """Test that empty audio chunks are silently ignored."""
    sent_to_openai = []
    
    def send_openai(state, payload):
        sent_to_openai.append(payload)

    fake_sock = FakeSock()
    context = {
        'log': FakeLogger(),
        'clamp_realtime_speed': lambda v: 1.0,
        'OPENAI_REALTIME_SPEED_DEFAULT': 1.0,
        'build_openai_session_config': lambda speed=1.0: {'speed': speed},
        'build_session_state': lambda ws: {
            'ws': ws,
            'openai_ws': {'connected': True},
            'openai_ping_thread': None,
            'playback_speed': 1.0,
            'subject_id': None,
            'language_level': None,
            'response_in_progress': False,
        },
        'connect_to_openai': lambda session_config: {'connected': True},
        'maybe_start_openai_keepalive': lambda state: None,
        'build_dutch_system_message': lambda level: {'type': 'conversation.item.create'},
        'openai_listener': lambda state: None,
        'send_openai': send_openai,
        'send_browser': lambda ws, payload: ws.sent.append(payload),
        'close_state': lambda state: None,
        'ALLOWED_CEFR_LEVELS': ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
    }

    register_ws_routes(fake_sock, context)
    handler = fake_sock.routes['/ws/realtime-voice']

    # Start session, then send empty audio chunk
    ws = FakeWS([
        json.dumps({'type': 'session.start'}),
        json.dumps({'type': 'audio.chunk', 'audio': ''}),
        json.dumps({'type': 'session.close'}),
    ])
    handler(ws)
    
    # Empty audio should be ignored, not forwarded to OpenAI
    audio_chunks = [p for p in sent_to_openai if p.get('type') == 'input_audio_buffer.append']
    assert len(audio_chunks) == 0


def test_ws_unknown_message_types_ignored():
    """Test that unknown message types are silently ignored."""
    sent_to_browser = []
    sent_to_openai = []
    
    def send_browser(ws, payload):
        ws.sent.append(payload)
        sent_to_browser.append(payload)
    
    def send_openai(state, payload):
        sent_to_openai.append(payload)

    fake_sock = FakeSock()
    context = {
        'log': FakeLogger(),
        'clamp_realtime_speed': lambda v: 1.0,
        'OPENAI_REALTIME_SPEED_DEFAULT': 1.0,
        'build_openai_session_config': lambda speed=1.0: {'speed': speed},
        'build_session_state': lambda ws: {
            'ws': ws,
            'openai_ws': {'connected': True},
            'openai_ping_thread': None,
            'playback_speed': 1.0,
            'subject_id': None,
            'language_level': None,
            'response_in_progress': False,
        },
        'connect_to_openai': lambda session_config: {'connected': True},
        'maybe_start_openai_keepalive': lambda state: None,
        'build_dutch_system_message': lambda level: {'type': 'conversation.item.create'},
        'openai_listener': lambda state: None,
        'send_openai': send_openai,
        'send_browser': send_browser,
        'close_state': lambda state: None,
        'ALLOWED_CEFR_LEVELS': ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
    }

    register_ws_routes(fake_sock, context)
    handler = fake_sock.routes['/ws/realtime-voice']

    ws = FakeWS([
        json.dumps({'type': 'session.start'}),
        json.dumps({'type': 'unknown.message.type', 'data': 'ignore'}),
        json.dumps({'type': 'session.close'}),
    ])
    handler(ws)
    
    # Should not error and should complete successfully
    assert any(message.get('type') == 'session.started' for message in ws.sent)


def test_ws_case_insensitive_language_level():
    """Test that language level is case-normalized (uppercase)."""
    sent_to_browser = []
    
    def send_browser(ws, payload):
        ws.sent.append(payload)
        sent_to_browser.append(payload)

    fake_sock = FakeSock()
    context = {
        'log': FakeLogger(),
        'clamp_realtime_speed': lambda v: 1.0,
        'OPENAI_REALTIME_SPEED_DEFAULT': 1.0,
        'build_openai_session_config': lambda speed=1.0: {'speed': speed},
        'build_session_state': lambda ws: {
            'ws': ws,
            'openai_ws': None,
            'openai_ping_thread': None,
            'playback_speed': 1.0,
            'subject_id': None,
            'language_level': None,
            'response_in_progress': False,
        },
        'connect_to_openai': lambda session_config: {'connected': True},
        'maybe_start_openai_keepalive': lambda state: None,
        'build_dutch_system_message': lambda level: {'type': 'conversation.item.create', 'level': level},
        'openai_listener': lambda state: None,
        'send_openai': lambda state, payload: None,
        'send_browser': send_browser,
        'close_state': lambda state: None,
        'ALLOWED_CEFR_LEVELS': ('A1', 'A2', 'B1', 'B2', 'C1', 'C2'),
    }

    register_ws_routes(fake_sock, context)
    handler = fake_sock.routes['/ws/realtime-voice']

    # Test lowercase level gets converted to uppercase
    ws = FakeWS([
        json.dumps({'type': 'session.start', 'language_level': 'b1'}),
        json.dumps({'type': 'session.close'}),
    ])
    handler(ws)
    
    assert any(message.get('type') == 'session.started' for message in ws.sent)