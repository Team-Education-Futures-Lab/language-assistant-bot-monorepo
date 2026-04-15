"""
API Gateway - Central Backend Service
Acts as the main entry point for all client requests and routes them to appropriate microservices.
"""

from flask import Flask
from flask_cors import CORS
from flask_sock import Sock
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import logging
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from routes.health_routes import register_health_routes
from routes.database_routes import register_database_routes
from routes.ws_routes import register_ws_routes
from routes.error_routes import register_error_handlers


SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SERVICE_DIR, '.env'))

# Initialize Flask app
app = Flask(__name__)
sock = Sock(app)

def _get_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def _parse_allowed_origins():
    chatbot_origin = os.getenv('FRONTEND_CHATBOT_ORIGIN', 'http://localhost:3000').strip()
    dashboard_origin = os.getenv('FRONTEND_DASHBOARD_ORIGIN', 'http://localhost:3001').strip()
    extra_origins_raw = os.getenv('FRONTEND_ALLOWED_ORIGINS', '').strip()

    origins = [chatbot_origin, dashboard_origin]
    if extra_origins_raw:
        origins.extend(origin.strip() for origin in extra_origins_raw.split(',') if origin.strip())

    unique_origins = []
    for origin in origins:
        if origin and origin not in unique_origins:
            unique_origins.append(origin)
    return unique_origins


APP_ENV = os.getenv('APP_ENV', os.getenv('FLASK_ENV', 'development')).lower()
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))

# CORS allowlist for frontend apps
ALLOWED_ORIGINS = _parse_allowed_origins()
FRONTEND_CHATBOT_ORIGIN = os.getenv('FRONTEND_CHATBOT_ORIGIN', 'http://localhost:3000').strip()
FRONTEND_DASHBOARD_ORIGIN = os.getenv('FRONTEND_DASHBOARD_ORIGIN', 'http://localhost:3001').strip()

# Enable CORS for configured frontend origins
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

# Respect reverse proxy headers when deployed behind a platform/load balancer.
if _get_bool_env('USE_PROXY_FIX', default=(APP_ENV == 'production')):
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=int(os.getenv('PROXY_FIX_X_FOR', '1')),
        x_proto=int(os.getenv('PROXY_FIX_X_PROTO', '1')),
        x_host=int(os.getenv('PROXY_FIX_X_HOST', '1')),
        x_port=int(os.getenv('PROXY_FIX_X_PORT', '1')),
        x_prefix=int(os.getenv('PROXY_FIX_X_PREFIX', '1')),
    )

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
GATEWAY_PORT = int(os.getenv('PORT', os.getenv('GATEWAY_PORT', 5000)))

# Basic, standard request rate limit for HTTP endpoints
RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '120 per minute')
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[RATE_LIMIT_DEFAULT],
    storage_uri='memory://',
)

# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

route_config = {
    'DATABASE_SERVICE_URL': DATABASE_SERVICE_URL,
    'REALTIME_VOICE_SERVICE_URL': REALTIME_VOICE_SERVICE_URL,
    'REALTIME_VOICE_SERVICE_WS_URL': REALTIME_VOICE_SERVICE_WS_URL,
    'GATEWAY_BACKEND_WS_TIMEOUT_SEC': GATEWAY_BACKEND_WS_TIMEOUT_SEC,
    'GATEWAY_BACKEND_WS_PING_INTERVAL_SEC': GATEWAY_BACKEND_WS_PING_INTERVAL_SEC,
    'GATEWAY_HOST': GATEWAY_HOST,
    'GATEWAY_PORT': GATEWAY_PORT,
}

register_health_routes(app, route_config)
register_database_routes(app, route_config)
register_ws_routes(sock, route_config)
register_error_handlers(app)

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
    print(f"\nAllowed CORS Origins:")
    print(f"  - Chatbot:          {FRONTEND_CHATBOT_ORIGIN}")
    print(f"  - Dashboard:        {FRONTEND_DASHBOARD_ORIGIN}")
    if os.getenv('FRONTEND_ALLOWED_ORIGINS', '').strip():
        print(f"  - Extra origins:    {os.getenv('FRONTEND_ALLOWED_ORIGINS')}")
    print(f"\nEnvironment:")
    print(f"  - APP_ENV:          {APP_ENV}")
    print(f"  - LOG_LEVEL:        {LOG_LEVEL}")
    print(f"  - USE_PROXY_FIX:    {_get_bool_env('USE_PROXY_FIX', default=(APP_ENV == 'production'))}")
    print(f"\nEndpoints:")
    print(f"  - Gateway Health:      GET  http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/health/gateway")
    print(f"  - Full Health:         GET  http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/health")
    print(f"  - Full Health Alias:   GET  http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/health/all")
    print(f"  - Subjects:            GET/POST http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/subjects")
    print(f"  - Prompts:             GET/POST http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/prompts")
    print(f"  - Settings:            GET/POST http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/settings")
    print(f"  - Retrieve:            POST http://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/retrieve")
    print(f"  - Realtime WS:         ws://{GATEWAY_HOST}:{GATEWAY_PORT}/api/query/ws/realtime-voice")
    print(f"\nAPI Gateway is ready to receive requests...\n")
    print(f"{'='*70}\n")
    
    app.run(host=GATEWAY_HOST, port=GATEWAY_PORT, debug=False)
