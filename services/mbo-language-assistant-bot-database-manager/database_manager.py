"""
Database Manager Service - CRUD operations for course materials
Provides REST API for managing subjects and chunked course content
Uses Supabase REST API (works on Eduroam/network-restricted connections)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from pypdf import PdfReader
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
import re
import logging
from datetime import datetime, timezone

# Load environment variables
load_dotenv()

# --- Service Configuration ---
SERVICE_HOST = os.getenv('SERVICE_HOST', "localhost")
SERVICE_PORT = int(os.getenv('SERVICE_PORT', 5004))
SERVICE_NAME = "Database Manager Service"

# --- Supabase Configuration ---
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
SUBJECT_SETTINGS_TABLE = os.getenv('SUBJECT_SETTINGS_TABLE', 'settings')
OPENAI_SETTINGS_TABLE = os.getenv('OPENAI_SETTINGS_TABLE', 'openai_settings')

# --- Vector Retrieval Configuration ---
DB_USER = os.getenv('DB_USER', "user")
DB_PASSWORD = os.getenv('DB_PASSWORD', "password")
DB_HOST = os.getenv('DB_HOST', "localhost")
DB_PORT = os.getenv('DB_PORT', "5432")
DB_NAME = os.getenv('DB_NAME', "school-db")
COLLECTION_NAME = os.getenv('COLLECTION_NAME', "course_materials_vectors")
CONNECTION_STRING = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

DEFAULT_RETRIEVE_TOP_K = int(os.getenv('DEFAULT_RETRIEVE_TOP_K', 10))
DEFAULT_RETRIEVE_TIMEOUT_SEC = float(os.getenv('DEFAULT_RETRIEVE_TIMEOUT_SEC', 8))

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
CORS(app, resources={r"/*": {"origins": "*"}})

logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO),
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('database_manager')

# Initialize Supabase client
supabase: Client = None
db_connected = False
vector_db = None
vector_db_connected = False

def init_supabase():
    """Initialize Supabase client"""
    global supabase, db_connected
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        db_connected = True
        print("✓ Supabase client initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Error initializing Supabase: {str(e)}")
        db_connected = False
        return False


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

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def chunk_text(text, chunk_size=500, overlap=100):
    """Split text into overlapping chunks"""
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        
        if chunk:
            chunks.append(chunk)
        
        start += chunk_size - overlap
    
    return chunks


def sanitize_text(text):
    """Sanitize text to avoid DB unicode/control character issues"""
    if not text:
        return ''

    sanitized = text.replace('\x00', '')
    sanitized = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ' ', sanitized)
    sanitized = re.sub(r'\r\n?', '\n', sanitized)
    sanitized = re.sub(r'[ \t]+', ' ', sanitized)
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
    return sanitized.strip()

def extract_text_from_file(filepath):
    """Extract text from uploaded file"""
    try:
        print(f"[DEBUG] Extracting text from: {filepath}")
        print(f"[DEBUG] File exists: {os.path.exists(filepath)}")
        
        ext = filepath.rsplit('.', 1)[1].lower()
        
        if ext == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return sanitize_text(f.read())
        
        elif ext == 'pdf':
            reader = PdfReader(filepath)
            pages_text = []
            for page in reader.pages:
                page_text = page.extract_text() or ''
                if page_text:
                    pages_text.append(page_text)
            return sanitize_text('\n\n'.join(pages_text))

        elif ext == 'docx':
            # Graceful fallback: binary docx parsing is not supported without python-docx.
            # Return a clear unsupported message by yielding no text.
            return None

        elif ext == 'doc':
            # Legacy .doc parsing is not supported in this service.
            return None
        
        return None
    except Exception as e:
        print(f"[ERROR] Error extracting text from {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return None


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': SERVICE_NAME,
        'database': 'connected' if db_connected else 'disconnected',
        'vector_database': 'connected' if vector_db_connected else 'disconnected'
    }), 200


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


def tokenize_text(text):
    """Tokenize text into lowercase words for lexical fallback ranking."""
    if not text:
        return []
    return [token for token in re.findall(r"\w+", text.lower()) if len(token) > 2]


def rank_chunk_records(question, chunk_records, k):
    """Simple lexical ranking fallback when vector retrieval is unavailable."""
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


def format_docs_for_llm(docs):
    """Format vector documents into one context block for LLM prompts."""
    formatted_string = ""
    for i, doc in enumerate(docs):
        source_filename = os.path.basename(doc.metadata.get('source', 'Unknown Source'))
        formatted_string += f"--- Context from {source_filename} (Chunk {i+1}) ---\n"
        formatted_string += doc.page_content.strip() + "\n\n"
    return formatted_string.strip()


def format_chunk_records_for_llm(chunks):
    """Format DB chunk records into one context block for LLM prompts."""
    parts = []
    for i, chunk in enumerate(chunks):
        source_filename = os.path.basename(chunk.get('source_file') or 'Unknown Source')
        parts.append(f"--- Context from {source_filename} (Chunk {i+1}) ---")
        parts.append((chunk.get('content') or '').strip())
        parts.append('')
    return "\n".join(parts).strip()


@app.route('/retrieve', methods=['POST'])
def retrieve_context():
    """Retrieve relevant context chunks for a user question."""
    try:
        data = request.get_json()

        if not data or 'question' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Ontbrekend veld "question" in requestbody'
            }), 400

        user_query = str(data['question']).strip()
        if not user_query:
            return jsonify({
                'status': 'error',
                'message': 'Vraag kan niet leeg zijn'
            }), 400

        runtime_retrieve_top_k = get_runtime_setting_value('retrieve_top_k', DEFAULT_RETRIEVE_TOP_K, int)
        requested_k = data.get('k', runtime_retrieve_top_k)
        k = int(requested_k)
        if k < 1:
            k = 1
        if k > 20:
            k = 20

        retrieval_mode = 'vector'

        if vector_db_connected and vector_db is not None:
            try:
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
                all_chunks_data = supabase.table('chunks').select('content,source_file').execute()
                all_chunks = all_chunks_data.data or []
                ranked_chunks = rank_chunk_records(user_query, all_chunks, k)

                if not ranked_chunks:
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
                for chunk in ranked_chunks:
                    source_filename = os.path.basename(chunk.get('source_file') or 'Unknown Source')
                    if source_filename not in sources:
                        sources.append(source_filename)

                formatted_context = format_chunk_records_for_llm(ranked_chunks)
                chunk_count = len(ranked_chunks)
        else:
            retrieval_mode = 'fallback'
            all_chunks_data = supabase.table('chunks').select('content,source_file').execute()
            all_chunks = all_chunks_data.data or []
            ranked_chunks = rank_chunk_records(user_query, all_chunks, k)

            if not ranked_chunks:
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
            for chunk in ranked_chunks:
                source_filename = os.path.basename(chunk.get('source_file') or 'Unknown Source')
                if source_filename not in sources:
                    sources.append(source_filename)

            formatted_context = format_chunk_records_for_llm(ranked_chunks)
            chunk_count = len(ranked_chunks)

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

# ============================================================================
# SUBJECT ENDPOINTS (CRUD)
# ============================================================================

@app.route('/subjects', methods=['GET'])
def get_subjects():
    """Get all subjects"""
    try:
        log.info('[RETRIEVE TRACE] GET /subjects from %s ua=%s', request.remote_addr, request.headers.get('User-Agent', 'unknown'))
        data = supabase.table('subjects').select('*').execute()
        
        # Fetch all retrieval_k settings in one query
        subjects = data.data
        if subjects:
            # Get all subject IDs
            subject_ids = [str(s['id']) for s in subjects]
            setting_keys = [f'subject_{sid}_retrieval_k' for sid in subject_ids]
            
            # Fetch all settings
            settings_result = supabase.table(SUBJECT_SETTINGS_TABLE).select('key, value').in_('key', setting_keys).execute()
            
            # Create a map of subject_id -> retrieval_k
            retrieval_map = {}
            if settings_result.data:
                for setting in settings_result.data:
                    # Extract subject_id from key like 'subject_123_retrieval_k'
                    subject_id = setting['key'].replace('subject_', '').replace('_retrieval_k', '')
                    retrieval_map[subject_id] = int(setting['value'])
            
            # Add retrieval_k to each subject
            for subject in subjects:
                subject['retrieval_k'] = retrieval_map.get(str(subject['id']), 10)
        
        return jsonify({
            'status': 'success',
            'subjects': subjects
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij ophalen subjects: {str(e)}'
        }), 500


@app.route('/subjects', methods=['POST'])
def create_subject():
    """Create new subject"""
    try:
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Name is required'
            }), 400
        
        # Validate retrieval_k if provided
        retrieval_k = data.get('retrieval_k', 10)
        if retrieval_k < 1 or retrieval_k > 20:
            return jsonify({
                'status': 'error',
                'message': 'Retrieval_k must be between 1 and 20'
            }), 400
        
        subject = {
            'name': data['name'],
            'description': data.get('description', ''),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('subjects').insert(subject).execute()
        
        if result.data:
            subject_id = result.data[0]['id']
            # Store retrieval_k in settings table
            setting_key = f'subject_{subject_id}_retrieval_k'
            supabase.table(SUBJECT_SETTINGS_TABLE).upsert({
                'key': setting_key,
                'value': str(retrieval_k),
                'description': f'Retrieval K for subject {data["name"]}',
                'updated_at': datetime.utcnow().isoformat()
            }).execute()
            
            # Add retrieval_k to response
            result.data[0]['retrieval_k'] = retrieval_k
        
        return jsonify({
            'status': 'success',
            'message': 'Subject created',
            'subject': result.data[0] if result.data else subject
        }), 201
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij aanmaken subject: {str(e)}'
        }), 500


@app.route('/subjects/<int:subject_id>', methods=['GET'])
def get_subject(subject_id):
    """Get specific subject"""
    try:
        data = supabase.table('subjects').select('*').eq('id', subject_id).execute()
        
        if not data.data:
            return jsonify({
                'status': 'error',
                'message': 'Subject not found'
            }), 404
        
        subject = data.data[0]
        
        # Fetch retrieval_k from settings
        setting_key = f'subject_{subject_id}_retrieval_k'
        setting_result = supabase.table(SUBJECT_SETTINGS_TABLE).select('value').eq('key', setting_key).execute()
        
        if setting_result.data:
            subject['retrieval_k'] = int(setting_result.data[0]['value'])
        else:
            subject['retrieval_k'] = 10  # Default value
        
        return jsonify({
            'status': 'success',
            'subject': subject
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij ophalen subject: {str(e)}'
        }), 500


@app.route('/subjects/<int:subject_id>', methods=['PUT'])
def update_subject(subject_id):
    """Update subject"""
    try:
        data = request.get_json()
        
        update_data = {
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if 'name' in data:
            update_data['name'] = data['name']
        if 'description' in data:
            update_data['description'] = data['description']
        
        # Handle retrieval_k separately in settings table
        retrieval_k_value = None
        if 'retrieval_k' in data:
            raw_retrieval_k = data.get('retrieval_k')
            if raw_retrieval_k is not None and raw_retrieval_k != '':
                try:
                    retrieval_k = int(raw_retrieval_k)
                except (TypeError, ValueError):
                    return jsonify({
                        'status': 'error',
                        'message': 'Retrieval_k must be a valid integer between 1 and 20'
                    }), 400

                if retrieval_k < 1 or retrieval_k > 20:
                    return jsonify({
                        'status': 'error',
                        'message': 'Retrieval_k must be between 1 and 20'
                    }), 400
                retrieval_k_value = retrieval_k
        
        # Update subjects table (without retrieval_k)
        result = supabase.table('subjects').update(update_data).eq('id', subject_id).execute()
        
        if not result.data:
            return jsonify({
                'status': 'error',
                'message': 'Subject not found'
            }), 404
        
        # Update retrieval_k in settings table if provided
        if retrieval_k_value is not None:
            setting_key = f'subject_{subject_id}_retrieval_k'
            supabase.table(SUBJECT_SETTINGS_TABLE).upsert({
                'key': setting_key,
                'value': str(retrieval_k_value),
                'description': f'Retrieval K for subject {result.data[0]["name"]}',
                'updated_at': datetime.utcnow().isoformat()
            }).execute()
            result.data[0]['retrieval_k'] = retrieval_k_value
        else:
            # Fetch current retrieval_k from settings
            setting_key = f'subject_{subject_id}_retrieval_k'
            setting_result = supabase.table(SUBJECT_SETTINGS_TABLE).select('value').eq('key', setting_key).execute()
            if setting_result.data:
                result.data[0]['retrieval_k'] = int(setting_result.data[0]['value'])
            else:
                result.data[0]['retrieval_k'] = 10
        
        return jsonify({
            'status': 'success',
            'message': 'Subject updated',
            'subject': result.data[0]
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij bijwerken subject: {str(e)}'
        }), 500


@app.route('/subjects/<int:subject_id>', methods=['DELETE'])
def delete_subject(subject_id):
    """Delete subject (cascades to chunks)"""
    try:
        result = supabase.table('subjects').delete().eq('id', subject_id).execute()
        
        return jsonify({
            'status': 'success',
            'message': 'Subject deleted'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij verwijderen subject: {str(e)}'
        }), 500

# ============================================================================
# PROMPT ENDPOINTS (CRUD) - GLOBAL MANAGEMENT
# ============================================================================

@app.route('/prompts', methods=['GET'])
def get_prompts():
    """Get all prompts (global management)"""
    try:
        # Get all prompts, ordered by creation date
        data = supabase.table('prompts').select('*').order('created_at', desc=True).execute()
        
        return jsonify({
            'status': 'success',
            'prompts': data.data
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij ophalen prompts: {str(e)}'
        }), 500


@app.route('/prompts', methods=['POST'])
def create_prompt():
    """Create new prompt (global management)"""
    try:
        data = request.get_json()
        
        if not data or 'title' not in data or 'content' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Title and content are required'
            }), 400
        
        prompt = {
            'subject_id': None,  # Global prompts have no subject
            'title': data['title'],
            'content': data['content'],
            'is_active': data.get('is_active', True),
            'is_default': data.get('is_default', False),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('prompts').insert(prompt).execute()
        
        return jsonify({
            'status': 'success',
            'message': 'Prompt created',
            'prompt': result.data[0] if result.data else prompt
        }), 201
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij aanmaken prompt: {str(e)}'
        }), 500


@app.route('/prompts/<int:prompt_id>', methods=['GET'])
def get_prompt(prompt_id):
    """Get specific prompt"""
    try:
        data = supabase.table('prompts').select('*').eq('id', prompt_id).execute()
        
        if not data.data:
            return jsonify({
                'status': 'error',
                'message': 'Prompt not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'prompt': data.data[0]
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij ophalen prompt: {str(e)}'
        }), 500


@app.route('/prompts/<int:prompt_id>', methods=['PUT', 'PATCH'])
def update_prompt(prompt_id):
    """Update prompt"""
    try:
        data = request.get_json()
        
        update_data = {
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if 'title' in data:
            update_data['title'] = data['title']
        if 'content' in data:
            update_data['content'] = data['content']
        if 'is_active' in data:
            update_data['is_active'] = data['is_active']
        if 'is_default' in data:
            update_data['is_default'] = data['is_default']
        
        result = supabase.table('prompts').update(update_data).eq('id', prompt_id).execute()
        
        if not result.data:
            return jsonify({
                'status': 'error',
                'message': 'Prompt not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'message': 'Prompt updated',
            'prompt': result.data[0]
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij bijwerken prompt: {str(e)}'
        }), 500


@app.route('/prompts/<int:prompt_id>', methods=['DELETE'])
def delete_prompt(prompt_id):
    """Delete prompt"""
    try:
        result = supabase.table('prompts').delete().eq('id', prompt_id).execute()
        
        return jsonify({
            'status': 'success',
            'message': 'Prompt deleted'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij verwijderen prompt: {str(e)}'
        }), 500


@app.route('/prompts/active', methods=['GET'])
def get_active_prompts():
    """Get all active prompts (for LLM usage)"""
    try:
        # Get all active prompts globally
        data = supabase.table('prompts').select('*').eq('is_active', True).order('created_at', desc=True).execute()
        
        return jsonify({
            'status': 'success',
            'prompts': data.data
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij ophalen active prompts: {str(e)}'
        }), 500

# ============================================================================
# FILE UPLOAD ENDPOINTS
# ============================================================================

@app.route('/subjects/<int:subject_id>/upload', methods=['POST'])
def upload_file(subject_id):
    """Upload file, extract text, chunk, and store"""
    filepath = None
    try:
        # Validate subject exists
        subject_check = supabase.table('subjects').select('id').eq('id', subject_id).execute()
        if not subject_check.data:
            return jsonify({
                'status': 'error',
                'message': 'Subject not found'
            }), 404
        
        # Check if file was provided
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'Geen bestand geüpload'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'Geen bestand geselecteerd'
            }), 400
        
        # Validate file
        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'message': 'Bestandstype niet ondersteund. Ondersteunde types: TXT, PDF, DOC, DOCX'
            }), 400
        
        if len(file.read()) > MAX_FILE_SIZE:
            file.seek(0)
            return jsonify({
                'status': 'error',
                'message': 'Bestandsgrootte mag niet groter zijn dan 50 MB'
            }), 400
        
        file.seek(0)
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        unique_filename = f"{datetime.utcnow().timestamp()}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        print(f"[DEBUG] File saved to: {filepath}")
        
        # Extract text
        text = extract_text_from_file(filepath)
        if not text:
            return jsonify({
                'status': 'error',
                'message': 'Kon geen text uit bestand extraheren'
            }), 400
        
        # Get chunk size from request (default 500)
        chunk_size = request.form.get('chunk_size', 500, type=int)
        
        # Ensure extracted content is safe for DB insertion
        text = sanitize_text(text)

        # Create chunks
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=100)
        
        if not chunks:
            return jsonify({
                'status': 'error',
                'message': 'Geen content gevonden in bestand'
            }), 400
        
        # Prepare chunk data
        chunk_records = []
        for i, chunk_content in enumerate(chunks):
            chunk_record = {
                'subject_id': subject_id,
                'content': sanitize_text(chunk_content),
                'source_file': filename,
                'chunk_metadata': {
                    'chunk_index': i,
                    'chunk_size': chunk_size,
                    'total_chunks': len(chunks),
                    'uploaded_at': datetime.utcnow().isoformat(),
                    'original_filename': filename
                },
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            chunk_records.append(chunk_record)
        
        # Insert chunks
        result = supabase.table('chunks').insert(chunk_records).execute()
        
        return jsonify({
            'status': 'success',
            'message': f'Bestand geüpload en {len(chunks)} chunks aangemaakt',
            'chunks_created': len(chunks),
            'filename': filename
        }), 201
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij uploaden bestand: {str(e)}'
        }), 500
    finally:
        # Always clean up the temporary file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass  # Ignore cleanup errors


@app.route('/subjects/<int:subject_id>/uploads/<path:upload_name>', methods=['DELETE'])
def delete_upload(subject_id, upload_name):
    """Delete an uploaded material by filename and remove all related chunks"""
    try:
        # Validate subject exists
        subject_check = supabase.table('subjects').select('id').eq('id', subject_id).execute()
        if not subject_check.data:
            return jsonify({
                'status': 'error',
                'message': 'Subject not found'
            }), 404

        # Count matching chunks first so we can return clear feedback
        existing_chunks = (
            supabase.table('chunks')
            .select('id', count='exact')
            .eq('subject_id', subject_id)
            .eq('source_file', upload_name)
            .execute()
        )

        matching_count = existing_chunks.count or len(existing_chunks.data or [])
        if matching_count == 0:
            return jsonify({
                'status': 'error',
                'message': 'Upload not found for this subject'
            }), 404

        # Delete all chunks tied to the upload filename
        supabase.table('chunks').delete().eq('subject_id', subject_id).eq('source_file', upload_name).execute()

        return jsonify({
            'status': 'success',
            'message': f'Upload verwijderd: {upload_name}',
            'upload_name': upload_name,
            'deleted_chunks': matching_count
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij verwijderen upload: {str(e)}'
        }), 500

# ============================================================================
# CHUNK ENDPOINTS (CRUD)
# ============================================================================

@app.route('/subjects/<int:subject_id>/chunks', methods=['GET'])
def get_chunks(subject_id):
    """Get all chunks for a subject"""
    try:
        log.info(
            '[RETRIEVE TRACE] GET /subjects/%s/chunks from %s ua=%s',
            subject_id,
            request.remote_addr,
            request.headers.get('User-Agent', 'unknown'),
        )
        data = supabase.table('chunks').select('*').eq('subject_id', subject_id).order('id').execute()
        
        return jsonify({
            'status': 'success',
            'chunks': data.data,
            'count': len(data.data)
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij ophalen chunks: {str(e)}'
        }), 500


@app.route('/subjects/<int:subject_id>/chunks', methods=['POST'])
def create_chunk(subject_id):
    """Create new chunk"""
    try:
        data = request.get_json()
        
        if not data or 'content' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Content is required'
            }), 400
        
        chunk = {
            'subject_id': subject_id,
            'content': data['content'],
            'source_file': data.get('source_file'),
            'chunk_metadata': data.get('chunk_metadata', {}),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        result = supabase.table('chunks').insert(chunk).execute()
        
        return jsonify({
            'status': 'success',
            'message': 'Chunk created',
            'chunk': result.data[0] if result.data else chunk
        }), 201
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij aanmaken chunk: {str(e)}'
        }), 500


@app.route('/chunks/<int:chunk_id>', methods=['GET'])
def get_chunk(chunk_id):
    """Get specific chunk"""
    try:
        data = supabase.table('chunks').select('*').eq('id', chunk_id).execute()
        
        if not data.data:
            return jsonify({
                'status': 'error',
                'message': 'Chunk not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'chunk': data.data[0]
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij ophalen chunk: {str(e)}'
        }), 500


@app.route('/chunks/<int:chunk_id>', methods=['PUT'])
def update_chunk(chunk_id):
    """Update chunk"""
    try:
        data = request.get_json()
        
        update_data = {
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if 'content' in data:
            update_data['content'] = data['content']
        if 'source_file' in data:
            update_data['source_file'] = data['source_file']
        if 'chunk_metadata' in data:
            update_data['chunk_metadata'] = data['chunk_metadata']
        
        result = supabase.table('chunks').update(update_data).eq('id', chunk_id).execute()
        
        if not result.data:
            return jsonify({
                'status': 'error',
                'message': 'Chunk not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'message': 'Chunk updated',
            'chunk': result.data[0]
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij bijwerken chunk: {str(e)}'
        }), 500


@app.route('/chunks/<int:chunk_id>', methods=['DELETE'])
def delete_chunk(chunk_id):
    """Delete chunk"""
    try:
        result = supabase.table('chunks').delete().eq('id', chunk_id).execute()
        
        return jsonify({
            'status': 'success',
            'message': 'Chunk deleted'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij verwijderen chunk: {str(e)}'
        }), 500

# ============================================================================
# BULK IMPORT ENDPOINT
# ============================================================================

@app.route('/subjects/<int:subject_id>/chunks/bulk', methods=['POST'])
def bulk_create_chunks(subject_id):
    """Bulk create chunks from JSON array"""
    try:
        data = request.get_json()
        
        if not data or 'chunks' not in data:
            return jsonify({
                'status': 'error',
                'message': 'chunks array is required'
            }), 400
        
        chunks = data['chunks']
        created_chunks = []
        
        for chunk_data in chunks:
            chunk = {
                'subject_id': subject_id,
                'content': chunk_data['content'],
                'source_file': chunk_data.get('source_file'),
                'chunk_metadata': chunk_data.get('chunk_metadata', {}),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            created_chunks.append(chunk)
        
        result = supabase.table('chunks').insert(created_chunks).execute()
        
        return jsonify({
            'status': 'success',
            'message': f'{len(created_chunks)} chunks created',
            'count': len(created_chunks)
        }), 201
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij bulk aanmaken chunks: {str(e)}'
        }), 500

# ============================================================================
# SETTINGS ENDPOINTS (System Configuration)
# ============================================================================

@app.route('/settings', methods=['GET'])
def get_settings():
    """Get all OpenAI/runtime settings"""
    try:
        prefix = request.args.get('prefix', '').strip()
        keys_csv = request.args.get('keys', '').strip()

        query = supabase.table(OPENAI_SETTINGS_TABLE).select('*')

        if prefix:
            query = query.like('key', f'{prefix}%')

        if keys_csv:
            keys = [k.strip() for k in keys_csv.split(',') if k.strip()]
            if keys:
                query = query.in_('key', keys)

        data = query.execute()
        
        return jsonify({
            'status': 'success',
            'settings': data.data
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij ophalen settings: {str(e)}'
        }), 500


@app.route('/settings/<key>', methods=['GET'])
def get_setting(key):
    """Get specific OpenAI/runtime setting by key"""
    try:
        data = supabase.table(OPENAI_SETTINGS_TABLE).select('*').eq('key', key).execute()
        
        if not data.data:
            return jsonify({
                'status': 'error',
                'message': f'Setting "{key}" not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'setting': data.data[0]
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij ophalen setting: {str(e)}'
        }), 500


@app.route('/settings', methods=['POST'])
def upsert_setting():
    """Create or update an OpenAI/runtime setting"""
    try:
        data = request.get_json()
        
        if not data or 'key' not in data or 'value' not in data:
            return jsonify({
                'status': 'error',
                'message': 'key and value are required'
            }), 400
        
        key = data['key']
        value = str(data['value'])  # Ensure value is string
        description = data.get('description', '')

        if not str(key).strip():
            return jsonify({
                'status': 'error',
                'message': 'key cannot be empty'
            }), 400
        
        print(f"[DEBUG] === UPSERT SETTING ===")
        print(f"[DEBUG] Key: {key}")
        print(f"[DEBUG] Value: {value} (type: {type(value)})")
        print(f"[DEBUG] Description: {description}")
        
        # Check if setting exists first
        check_result = supabase.table(OPENAI_SETTINGS_TABLE).select('*').eq('key', key).execute()
        print(f"[DEBUG] Existing setting: {check_result.data}")
        
        # Prepare setting data
        setting_data = {
            'key': key,
            'value': value,
            'description': description
        }
        
        if check_result.data:
            # Update existing
            print(f"[DEBUG] Updating existing setting...")
            result = supabase.table(OPENAI_SETTINGS_TABLE).update({
                'value': value,
                'description': description
            }).eq('key', key).execute()
            print(f"[DEBUG] Update result: {result.data}")
        else:
            # Insert new
            print(f"[DEBUG] Inserting new setting...")
            result = supabase.table(OPENAI_SETTINGS_TABLE).insert(setting_data).execute()
            print(f"[DEBUG] Insert result: {result.data}")
        
        # Verify the update
        verify_result = supabase.table(OPENAI_SETTINGS_TABLE).select('*').eq('key', key).execute()
        print(f"[DEBUG] After operation, setting is: {verify_result.data}")
        
        return jsonify({
            'status': 'success',
            'message': 'Setting saved',
            'setting': result.data[0] if result.data else setting_data
        }), 201
    except Exception as e:
        import traceback
        print(f"[ERROR] Failed to upsert setting: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'message': f'Fout bij opslaan setting: {str(e)}'
        }), 500


@app.route('/settings/<key>', methods=['PUT', 'PATCH'])
def update_setting(key):
    """Update existing OpenAI/runtime setting by key (explicit update endpoint)"""
    try:
        data = request.get_json()

        if not data or 'value' not in data:
            return jsonify({
                'status': 'error',
                'message': 'value is required'
            }), 400

        value = str(data['value'])
        description = data.get('description')

        existing = supabase.table(OPENAI_SETTINGS_TABLE).select('*').eq('key', key).execute()
        if not existing.data:
            return jsonify({
                'status': 'error',
                'message': f'Setting "{key}" not found'
            }), 404

        update_data = {'value': value}
        if description is not None:
            update_data['description'] = description

        result = supabase.table(OPENAI_SETTINGS_TABLE).update(update_data).eq('key', key).execute()

        return jsonify({
            'status': 'success',
            'message': 'Setting updated',
            'setting': result.data[0] if result.data else {
                'key': key,
                **update_data,
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij bijwerken setting: {str(e)}'
        }), 500


@app.route('/settings/<key>', methods=['DELETE'])
def delete_setting(key):
    """Delete an OpenAI/runtime setting"""
    try:
        result = supabase.table(OPENAI_SETTINGS_TABLE).delete().eq('key', key).execute()
        
        return jsonify({
            'status': 'success',
            'message': f'Setting "{key}" deleted'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Fout bij verwijderen setting: {str(e)}'
        }), 500

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'message': 'Endpoint niet gevonden'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'status': 'error',
        'message': 'Interne serverfout'
    }), 500

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    print(f"\n{'='*70}")
    print(f"{SERVICE_NAME}")
    print(f"REST API Service for Course Materials Database")
    print(f"{'='*70}")
    print(f"\n{SERVICE_NAME} starting on http://{SERVICE_HOST}:{SERVICE_PORT}")
    print(f"Database: Supabase ({SUPABASE_URL})")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"\nEndpoints:")
    print(f"  - Health:        GET    http://{SERVICE_HOST}:{SERVICE_PORT}/health")
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
    
    # Initialize Supabase
    if init_supabase():
        init_vector_db()
        app.run(host=SERVICE_HOST, port=SERVICE_PORT, debug=False)
    else:
        print("✗ Failed to initialize Supabase. Check your credentials.")
        exit(1)
