"""
Retrieve Service - Dedicated microservice for vector similarity retrieval.
Provides context chunks and source metadata to other services.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from dotenv import load_dotenv
import os
import sys
import re
import requests


SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICES_DIR = os.path.dirname(SERVICE_DIR)

# Load env files from service-local first, then shared services-level files.
load_dotenv(os.path.join(SERVICE_DIR, '.env'))
load_dotenv(os.path.join(SERVICES_DIR, '.env'), override=False)

# --- PART 1: DATABASE CONNECTION DETAILS ---
DB_USER = os.getenv('DB_USER', "user")
DB_PASSWORD = os.getenv('DB_PASSWORD', "password")
DB_HOST = os.getenv('DB_HOST', "localhost")
DB_PORT = os.getenv('DB_PORT', "5432")
DB_NAME = os.getenv('DB_NAME', "school-db")
COLLECTION_NAME = os.getenv('COLLECTION_NAME', "course_materials_vectors")
CONNECTION_STRING = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- Service Configuration ---
SERVICE_HOST = os.getenv('SERVICE_HOST', "localhost")
SERVICE_PORT = int(os.getenv('SERVICE_PORT', 5003))
SERVICE_NAME = "Retrieve Service"
DEFAULT_DATABASE_MANAGER_URL = os.getenv('DATABASE_MANAGER_URL', 'http://localhost:5004')
DEFAULT_RETRIEVE_TOP_K = int(os.getenv('RETRIEVE_TOP_K', 10))
DEFAULT_RETRIEVE_TIMEOUT_SEC = float(os.getenv('RETRIEVE_TIMEOUT_SEC', 8))

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


def get_runtime_setting(key, default_value, value_type=str, database_manager_url=None, timeout_sec=2.5):
    """Read a runtime setting from database manager; fallback to default on errors."""
    base_url = database_manager_url or DEFAULT_DATABASE_MANAGER_URL
    try:
        response = requests.get(f'{base_url}/settings/{key}', timeout=timeout_sec)
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


def get_runtime_config():
    """Resolve current runtime config with DB -> env fallbacks."""
    database_manager_url = get_runtime_setting(
        'database_manager_url',
        DEFAULT_DATABASE_MANAGER_URL,
        str,
        database_manager_url=DEFAULT_DATABASE_MANAGER_URL,
    )
    retrieve_top_k = get_runtime_setting(
        'retrieve_top_k',
        DEFAULT_RETRIEVE_TOP_K,
        int,
        database_manager_url=database_manager_url,
    )
    retrieve_timeout_sec = get_runtime_setting(
        'retrieve_timeout_sec',
        DEFAULT_RETRIEVE_TIMEOUT_SEC,
        float,
        database_manager_url=database_manager_url,
    )

    return {
        'database_manager_url': database_manager_url,
        'retrieve_top_k': retrieve_top_k,
        'retrieve_timeout_sec': retrieve_timeout_sec,
    }


def format_docs_for_llm(docs):
    """Format document chunks into a single context string for an LLM."""
    formatted_string = ""
    for i, doc in enumerate(docs):
        source_filename = os.path.basename(doc.metadata.get('source', 'Unknown Source'))
        formatted_string += f"--- Context from {source_filename} (Chunk {i+1}) ---\n"
        formatted_string += doc.page_content.strip() + "\n\n"
    return formatted_string.strip()


def tokenize_text(text):
    """Tokenize text into lowercase words for simple lexical ranking."""
    if not text:
        return []
    return [token for token in re.findall(r"\w+", text.lower()) if len(token) > 2]


def rank_chunk_records(question, chunk_records, k):
    """Simple lexical ranking fallback when vector DB is unavailable."""
    query_tokens = set(tokenize_text(question))
    if not query_tokens:
        return chunk_records[:k]

    scored = []
    question_lower = question.lower()

    for chunk in chunk_records:
        content = (chunk.get('content') or '').lower()
        if not content.strip():
            continue

        content_tokens = set(tokenize_text(content))
        overlap = len(query_tokens.intersection(content_tokens))
        phrase_bonus = 2 if question_lower in content else 0
        score = overlap + phrase_bonus

        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:k]]


def format_chunk_records_for_llm(chunks):
    """Format DB-manager chunk records to a single context string for LLM prompts."""
    parts = []
    for i, chunk in enumerate(chunks):
        source_filename = os.path.basename(chunk.get('source_file') or 'Unknown Source')
        parts.append(f"--- Context from {source_filename} (Chunk {i+1}) ---")
        parts.append((chunk.get('content') or '').strip())
        parts.append('')
    return "\n".join(parts).strip()


def retrieve_via_database_manager(user_query, k, database_manager_url, request_timeout_sec):
    """Fallback retrieval path using Database Manager REST API."""
    subjects_response = requests.get(f'{database_manager_url}/subjects', timeout=request_timeout_sec)
    if subjects_response.status_code != 200:
        raise RuntimeError(f'Database Manager subjects endpoint gaf status {subjects_response.status_code}')

    subjects_payload = subjects_response.json()
    subjects = subjects_payload.get('subjects', [])

    all_chunks = []
    for subject in subjects:
        subject_id = subject.get('id')
        if subject_id is None:
            continue

        chunks_response = requests.get(f'{database_manager_url}/subjects/{subject_id}/chunks', timeout=request_timeout_sec)
        if chunks_response.status_code != 200:
            continue

        chunks_payload = chunks_response.json()
        chunks = chunks_payload.get('chunks', [])
        all_chunks.extend(chunks)

    if not all_chunks:
        return {
            'context_found': False,
            'formatted_context': '',
            'sources': [],
            'chunk_count': 0
        }

    ranked_chunks = rank_chunk_records(user_query, all_chunks, k)
    if not ranked_chunks:
        return {
            'context_found': False,
            'formatted_context': '',
            'sources': [],
            'chunk_count': 0
        }

    sources = []
    for chunk in ranked_chunks:
        source_filename = os.path.basename(chunk.get('source_file') or 'Unknown Source')
        if source_filename not in sources:
            sources.append(source_filename)

    return {
        'context_found': True,
        'formatted_context': format_chunk_records_for_llm(ranked_chunks),
        'sources': sources,
        'chunk_count': len(ranked_chunks)
    }


print(f"1. Initializing vector database connection for {SERVICE_NAME}...")
try:
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_db = PGVector.from_existing_index(
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        connection=CONNECTION_STRING,
    )
    print("✓ Vector database connected successfully.")
    db_connected = True
except Exception as e:
    print(f"✗ Error connecting to vector database: {e}", file=sys.stderr)
    db_connected = False


@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'message': f'{SERVICE_NAME} is actief',
        'service': SERVICE_NAME,
        'database_connected': db_connected
    }), 200


@app.route('/health', methods=['GET'])
def health_detailed():
    runtime_config = get_runtime_config()
    database_manager_url = runtime_config['database_manager_url']

    fallback_status = 'unknown'
    try:
        response = requests.get(f'{database_manager_url}/health', timeout=2)
        fallback_status = 'healthy' if response.status_code == 200 else 'unhealthy'
    except Exception:
        fallback_status = 'unreachable'

    service_healthy = db_connected or fallback_status == 'healthy'

    return jsonify({
        'status': 'ok' if service_healthy else 'degraded',
        'service': SERVICE_NAME,
        'database_connected': db_connected,
        'fallback_database_manager': {
            'url': database_manager_url,
            'status': fallback_status
        },
        'service_host': SERVICE_HOST,
        'service_port': SERVICE_PORT,
        'database_url': f"postgresql://{DB_HOST}:{DB_PORT}/{DB_NAME}",
        'collection_name': COLLECTION_NAME
    }), 200 if service_healthy else 503


@app.route('/retrieve', methods=['POST'])
def retrieve_context():
    """
    Retrieve context chunks from PGVector across all subjects.

    Expected JSON payload:
    {
      "question": "...",
      "k": 10
    }
    """
    try:
        data = request.get_json()

        if not data or 'question' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Ontbrekend veld "question" in requestbody'
            }), 400

        runtime_config = get_runtime_config()
        user_query = data['question'].strip()
        k = int(data.get('k', runtime_config['retrieve_top_k']))
        
        if k < 1:
            k = 1
        if k > 20:
            k = 20

        if not user_query:
            return jsonify({
                'status': 'error',
                'message': 'Vraag kan niet leeg zijn'
            }), 400

        retrieval_mode = 'vector'
        if db_connected:
            try:
                # Search entire chunks table (all subjects)
                print(f"🔍 Retrieving chunks from all subjects", file=sys.stderr)
                results = vector_db.similarity_search(user_query, k=k)

                if not results:
                    return jsonify({
                        'status': 'success',
                        'question': user_query,
                        'context_found': False,
                        'formatted_context': '',
                        'sources': [],
                        'chunk_count': 0,
                        'service': SERVICE_NAME,
                        'mode': retrieval_mode
                    }), 200

                sources = []
                for doc in results:
                    source_filename = os.path.basename(doc.metadata.get('source', 'Unknown Source'))
                    if source_filename not in sources:
                        sources.append(source_filename)

                formatted_context = format_docs_for_llm(results)
                chunk_count = len(results)
            except Exception:
                retrieval_mode = 'fallback'
                fallback_payload = retrieve_via_database_manager(
                    user_query,
                    k,
                    runtime_config['database_manager_url'],
                    runtime_config['retrieve_timeout_sec'],
                )
                formatted_context = fallback_payload['formatted_context']
                sources = fallback_payload['sources']
                chunk_count = fallback_payload['chunk_count']
                if not fallback_payload['context_found']:
                    return jsonify({
                        'status': 'success',
                        'question': user_query,
                        'context_found': False,
                        'formatted_context': '',
                        'sources': [],
                        'chunk_count': 0,
                        'service': SERVICE_NAME,
                        'mode': retrieval_mode
                    }), 200
        else:
            retrieval_mode = 'fallback'
            fallback_payload = retrieve_via_database_manager(
                user_query,
                k,
                runtime_config['database_manager_url'],
                runtime_config['retrieve_timeout_sec'],
            )
            formatted_context = fallback_payload['formatted_context']
            sources = fallback_payload['sources']
            chunk_count = fallback_payload['chunk_count']
            if not fallback_payload['context_found']:
                return jsonify({
                    'status': 'success',
                    'question': user_query,
                    'context_found': False,
                    'formatted_context': '',
                    'sources': [],
                    'chunk_count': 0,
                    'service': SERVICE_NAME,
                    'mode': retrieval_mode
                }), 200

        return jsonify({
            'status': 'success',
            'question': user_query,
            'context_found': True,
            'formatted_context': formatted_context,
            'sources': sources,
            'chunk_count': chunk_count,
            'service': SERVICE_NAME,
            'mode': retrieval_mode
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Een onverwachte fout is opgetreden: {str(e)}'
        }), 500


@app.route('/settings', methods=['GET', 'POST'])
def proxy_settings_collection():
    """Proxy settings CRUD collection operations to Database Manager."""
    try:
        runtime_config = get_runtime_config()
        database_manager_url = runtime_config['database_manager_url']

        if request.method == 'GET':
            response = requests.get(
                f'{database_manager_url}/settings',
                params=request.args,
                timeout=10,
            )
        else:
            response = requests.post(
                f'{database_manager_url}/settings',
                json=request.get_json(silent=True) or {},
                timeout=10,
            )

        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Kon settings proxy niet uitvoeren: {str(e)}'
        }), 500


@app.route('/settings/<path:key>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def proxy_settings_item(key):
    """Proxy settings item CRUD operations to Database Manager."""
    try:
        runtime_config = get_runtime_config()
        database_manager_url = runtime_config['database_manager_url']

        if request.method == 'GET':
            response = requests.get(f'{database_manager_url}/settings/{key}', timeout=10)
        elif request.method == 'PUT':
            response = requests.put(
                f'{database_manager_url}/settings/{key}',
                json=request.get_json(silent=True) or {},
                timeout=10,
            )
        elif request.method == 'PATCH':
            response = requests.patch(
                f'{database_manager_url}/settings/{key}',
                json=request.get_json(silent=True) or {},
                timeout=10,
            )
        else:
            response = requests.delete(f'{database_manager_url}/settings/{key}', timeout=10)

        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Kon setting proxy niet uitvoeren: {str(e)}'
        }), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'message': 'Eindpunt niet gevonden'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'status': 'error',
        'message': 'Interne serverfout'
    }), 500


if __name__ == '__main__':
    print(f"\n{'='*70}")
    print(f"{SERVICE_NAME}")
    print(f"Dedicated Retrieval Service for Course Materials")
    print(f"{'='*70}")
    print(f"\n{SERVICE_NAME} starten op http://{SERVICE_HOST}:{SERVICE_PORT}")
    print(f"Database: {DB_NAME} @ {DB_HOST}:{DB_PORT}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"\nEindpunten:")
    print(f"  - Gezondheidscheck: GET  http://{SERVICE_HOST}:{SERVICE_PORT}/health")
    print(f"  - Retrieve:         POST http://{SERVICE_HOST}:{SERVICE_PORT}/retrieve")
    print(f"\n{SERVICE_NAME} is klaar om verzoeken te ontvangen...\n")
    print(f"{'='*70}\n")

    app.run(host=SERVICE_HOST, port=SERVICE_PORT, debug=False)
