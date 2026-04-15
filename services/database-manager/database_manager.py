"""
Database Manager Service - CRUD operations for course materials
Provides REST API for managing subjects and chunked course content
Uses Supabase REST API (works on Eduroam/network-restricted connections)
"""

from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from supabase import create_client, Client
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import time
import logging
from datetime import datetime, timezone
from typing import Any
from modules.mariadb_adapter import MariaDBAdapter, MARIADB_ADAPTER_AVAILABLE
from modules.text_processing import (
    allowed_file,
    chunk_text,
    sanitize_text,
    extract_text_from_file,
    rank_chunk_records,
    format_docs_for_llm,
    format_chunk_records_for_llm,
)
from routes.health_routes import register_health_routes
from routes.retrieval_routes import register_retrieval_routes
from routes.subjects_routes import register_subject_routes
from routes.prompts_routes import register_prompt_routes
from routes.chunk_upload_routes import register_chunk_upload_routes
from routes.settings_routes import register_settings_routes
from routes.error_routes import register_error_handlers

# Load environment variables
load_dotenv()

# --- Service Configuration ---
APP_ENV = os.getenv('APP_ENV', os.getenv('FLASK_ENV', 'development')).lower()
SERVICE_HOST = os.getenv('SERVICE_HOST', "localhost")
SERVICE_PORT = int(os.getenv('PORT', os.getenv('SERVICE_PORT', 5004)))
SERVICE_NAME = "Database Manager Service"


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

# --- Supabase Configuration ---
DB_BACKEND = os.getenv('DB_BACKEND', 'supabase').strip().lower()
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
OPENAI_SETTINGS_TABLE = os.getenv('OPENAI_SETTINGS_TABLE', 'openai_settings')

# --- MariaDB Configuration ---
MARIADB_URL = os.getenv('MARIADB_URL', '').strip()
MARIADB_HOST = os.getenv('MARIADB_HOST', 'localhost').strip()
MARIADB_PORT = int(os.getenv('MARIADB_PORT', '3306'))
MARIADB_USER = os.getenv('MARIADB_USER', '').strip()
MARIADB_PASSWORD = os.getenv('MARIADB_PASSWORD', '').strip()
MARIADB_DATABASE = os.getenv('MARIADB_DATABASE', '').strip()

# --- Vector Retrieval Configuration ---
DB_USER = os.getenv('DB_USER', "user")
DB_PASSWORD = os.getenv('DB_PASSWORD', "password")
DB_HOST = os.getenv('DB_HOST', "localhost")
DB_PORT = os.getenv('DB_PORT', "5432")
DB_NAME = os.getenv('DB_NAME', "school-db")
COLLECTION_NAME = os.getenv('COLLECTION_NAME', "course_materials_vectors")
CONNECTION_STRING = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

_retrieve_top_k_env = os.getenv('RETRIEVE_TOP_K', os.getenv('DEFAULT_RETRIEVE_TOP_K', '10'))
try:
    DEFAULT_RETRIEVE_TOP_K = int(_retrieve_top_k_env)
except (TypeError, ValueError):
    DEFAULT_RETRIEVE_TOP_K = 10

if DEFAULT_RETRIEVE_TOP_K < 1:
    DEFAULT_RETRIEVE_TOP_K = 1
if DEFAULT_RETRIEVE_TOP_K > 20:
    DEFAULT_RETRIEVE_TOP_K = 20
DEFAULT_RETRIEVE_TIMEOUT_SEC = float(os.getenv('DEFAULT_RETRIEVE_TIMEOUT_SEC', 8))
FALLBACK_CHUNKS_CACHE_TTL_SEC = int(os.getenv('FALLBACK_CHUNKS_CACHE_TTL_SEC', '20'))

# Upload configuration - use absolute path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'doc'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

ALLOWED_GATEWAY_ORIGINS = _parse_allowed_gateway_origins()
CORS(app, resources={r"/*": {"origins": ALLOWED_GATEWAY_ORIGINS}})

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

RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '120 per minute')
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[RATE_LIMIT_DEFAULT],
    storage_uri='memory://',
)

logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO),
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('database_manager')


# Initialize database client
supabase: Any = None
db_connected = False
vector_db = None
vector_db_connected = False
_fallback_chunks_cache_data = None
_fallback_chunks_cache_expires_at = 0.0


def get_fallback_chunks_cached():
    """Fetch fallback retrieval chunks with a short TTL cache to reduce Supabase roundtrips."""
    global _fallback_chunks_cache_data, _fallback_chunks_cache_expires_at

    now = time.time()
    if (
        FALLBACK_CHUNKS_CACHE_TTL_SEC > 0
        and _fallback_chunks_cache_data is not None
        and now < _fallback_chunks_cache_expires_at
    ):
        return _fallback_chunks_cache_data

    all_chunks_data = supabase.table('chunks').select('content,source_file,subject_id').execute()
    chunks = all_chunks_data.data or []

    if FALLBACK_CHUNKS_CACHE_TTL_SEC > 0:
        _fallback_chunks_cache_data = chunks
        _fallback_chunks_cache_expires_at = now + FALLBACK_CHUNKS_CACHE_TTL_SEC
    else:
        _fallback_chunks_cache_data = None
        _fallback_chunks_cache_expires_at = 0.0

    return chunks

def init_database_client():
    """Initialize configured database backend client."""
    global supabase, db_connected
    try:
        if DB_BACKEND == 'mariadb':
            if not MARIADB_ADAPTER_AVAILABLE:
                raise RuntimeError('MariaDB backend requires sqlalchemy and pymysql packages')

            if MARIADB_URL:
                connection_url = MARIADB_URL
            else:
                if not (MARIADB_USER and MARIADB_DATABASE):
                    raise RuntimeError('Set MARIADB_URL or MARIADB_USER/MARIADB_PASSWORD/MARIADB_DATABASE')
                connection_url = (
                    f"mysql+pymysql://{MARIADB_USER}:{MARIADB_PASSWORD}"
                    f"@{MARIADB_HOST}:{MARIADB_PORT}/{MARIADB_DATABASE}"
                )

            supabase = MariaDBAdapter(connection_url)
            supabase.ping()
            print('✓ MariaDB client initialized successfully')
        else:
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            print('✓ Supabase client initialized successfully')

        db_connected = True
        return True
    except Exception as e:
        print(f"✗ Error initializing database backend ({DB_BACKEND}): {str(e)}")
        db_connected = False
        return False


def init_supabase():
    """Backward-compatible wrapper."""
    return init_database_client()


def init_vector_db():
    """Initialize PGVector connection for semantic retrieval."""
    global vector_db, vector_db_connected
    try:
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vector_db = PGVector.from_existing_index(
            embedding=embeddings,
            collection_name=COLLECTION_NAME,
            connection=CONNECTION_STRING,
        )
        vector_db_connected = True
        print("✓ Vector database connected successfully")
        return True
    except Exception as e:
        print(f"✗ Error connecting to vector database: {str(e)}")
        vector_db = None
        vector_db_connected = False
        return False

def get_runtime_setting_value(key, default_value, value_type=str):
    """Read a runtime setting from the DB with env fallback."""
    try:
        data = supabase.table(OPENAI_SETTINGS_TABLE).select('value').eq('key', key).execute()
        if not data.data:
            return default_value

        raw_value = data.data[0].get('value', default_value)
        if value_type == int:
            return int(raw_value)
        if value_type == float:
            return float(raw_value)
        if value_type == bool:
            return str(raw_value).strip().lower() in ('1', 'true', 'yes', 'on')
        return str(raw_value)
    except Exception:
        return default_value


def get_subject_retrieval_k(subject_id: int, default_value: int) -> int:
    """Resolve retrieval_k from subjects table for a given subject id."""
    subject_result = supabase.table('subjects').select('id,retrieval_k').eq('id', subject_id).limit(1).execute()
    if not subject_result.data:
        raise ValueError(f'Subject with id {subject_id} not found')

    raw_value = subject_result.data[0].get('retrieval_k', default_value)
    try:
        retrieval_k = int(raw_value)
    except (TypeError, ValueError):
        retrieval_k = default_value

    if retrieval_k < 1:
        retrieval_k = 1
    if retrieval_k > 20:
        retrieval_k = 20
    return retrieval_k

# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

route_context = {
    'SERVICE_NAME': SERVICE_NAME,
    'SERVICE_HOST': SERVICE_HOST,
    'SERVICE_PORT': SERVICE_PORT,
    'DEFAULT_RETRIEVE_TOP_K': DEFAULT_RETRIEVE_TOP_K,
    'OPENAI_SETTINGS_TABLE': OPENAI_SETTINGS_TABLE,
    'UPLOAD_FOLDER': UPLOAD_FOLDER,
    'ALLOWED_EXTENSIONS': ALLOWED_EXTENSIONS,
    'MAX_FILE_SIZE': MAX_FILE_SIZE,
    'allowed_file': allowed_file,
    'extract_text_from_file': extract_text_from_file,
    'sanitize_text': sanitize_text,
    'chunk_text': chunk_text,
    'rank_chunk_records': rank_chunk_records,
    'format_docs_for_llm': format_docs_for_llm,
    'format_chunk_records_for_llm': format_chunk_records_for_llm,
    'get_runtime_setting_value': get_runtime_setting_value,
    'get_subject_retrieval_k': get_subject_retrieval_k,
    'get_fallback_chunks_cached': get_fallback_chunks_cached,
    'get_supabase': lambda: supabase,
    'get_vector_db': lambda: vector_db,
    'get_vector_db_connected': lambda: vector_db_connected,
    'get_db_connected': lambda: db_connected,
    'get_log': lambda: log,
}

register_health_routes(app, route_context)
register_retrieval_routes(app, route_context)
register_subject_routes(app, route_context)
register_prompt_routes(app, route_context)
register_chunk_upload_routes(app, route_context)
register_settings_routes(app, route_context)
register_error_handlers(app)

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    print(f"\n{'='*70}")
    print(f"{SERVICE_NAME}")
    print(f"REST API Service for Course Materials Database")
    print(f"{'='*70}")
    print(f"\n{SERVICE_NAME} starting on http://{SERVICE_HOST}:{SERVICE_PORT}")
    if DB_BACKEND == 'mariadb':
        mariadb_target = MARIADB_URL or f"{MARIADB_HOST}:{MARIADB_PORT}/{MARIADB_DATABASE}"
        print(f"Database backend: MariaDB ({mariadb_target})")
    else:
        print(f"Database backend: Supabase ({SUPABASE_URL})")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"\nEnvironment:")
    print(f"  - APP_ENV:            {APP_ENV}")
    print(f"  - DB_BACKEND:         {DB_BACKEND}")
    print(f"  - RATE_LIMIT_DEFAULT: {RATE_LIMIT_DEFAULT}")
    print(f"  - API_GATEWAY_ORIGIN: {os.getenv('API_GATEWAY_ORIGIN', 'http://localhost:5000')}")
    if os.getenv('API_GATEWAY_ALLOWED_ORIGINS', '').strip():
        print(f"  - Extra origins:      {os.getenv('API_GATEWAY_ALLOWED_ORIGINS')}")
    print(f"  - USE_PROXY_FIX:      {_get_bool_env('USE_PROXY_FIX', default=(APP_ENV == 'production'))}")
    print(f"\nEndpoints:")
    print(f"  - Server Health: GET    http://{SERVICE_HOST}:{SERVICE_PORT}/health")
    print(f"  - Full Health:   GET    http://{SERVICE_HOST}:{SERVICE_PORT}/health/all")
    print(f"  - Subjects:      GET    http://{SERVICE_HOST}:{SERVICE_PORT}/subjects")
    print(f"  - Add Subject:   POST   http://{SERVICE_HOST}:{SERVICE_PORT}/subjects")
    print(f"  - Get Subject:   GET    http://{SERVICE_HOST}:{SERVICE_PORT}/subjects/<id>")
    print(f"  - Update:        PUT    http://{SERVICE_HOST}:{SERVICE_PORT}/subjects/<id>")
    print(f"  - Delete:        DELETE http://{SERVICE_HOST}:{SERVICE_PORT}/subjects/<id>")
    print(f"  - Chunks:        GET    http://{SERVICE_HOST}:{SERVICE_PORT}/subjects/<id>/chunks")
    print(f"  - Add Chunk:     POST   http://{SERVICE_HOST}:{SERVICE_PORT}/subjects/<id>/chunks")
    print(f"  - Get Chunk:     GET    http://{SERVICE_HOST}:{SERVICE_PORT}/chunks/<id>")
    print(f"  - Update Chunk:  PUT    http://{SERVICE_HOST}:{SERVICE_PORT}/chunks/<id>")
    print(f"  - Delete Chunk:  DELETE http://{SERVICE_HOST}:{SERVICE_PORT}/chunks/<id>")
    print(f"  - Upload File:   POST   http://{SERVICE_HOST}:{SERVICE_PORT}/subjects/<id>/upload")
    print(f"  - Bulk Chunks:   POST   http://{SERVICE_HOST}:{SERVICE_PORT}/subjects/<id>/chunks/bulk")
    print(f"  - Settings:      GET    http://{SERVICE_HOST}:{SERVICE_PORT}/settings")
    print(f"  - Get Setting:   GET    http://{SERVICE_HOST}:{SERVICE_PORT}/settings/<key>")
    print(f"  - Save Setting:  POST   http://{SERVICE_HOST}:{SERVICE_PORT}/settings")
    print(f"  - Delete Setting:DELETE http://{SERVICE_HOST}:{SERVICE_PORT}/settings/<key>")
    print(f"  - Retrieve:      POST   http://{SERVICE_HOST}:{SERVICE_PORT}/retrieve")
    print(f"\n{SERVICE_NAME} is ready to receive requests...")
    print(f"{'='*70}\n")
    
    # Initialize services
    if not init_database_client():
        print(f"✗ Failed to initialize database backend ({DB_BACKEND}). Check your credentials/configuration.")
        exit(1)
    init_vector_db()
    app.run(host=SERVICE_HOST, port=SERVICE_PORT, debug=False)

# Initialize clients when imported by a production WSGI server (e.g. gunicorn).
if __name__ != '__main__':
    init_database_client()
    init_vector_db()
