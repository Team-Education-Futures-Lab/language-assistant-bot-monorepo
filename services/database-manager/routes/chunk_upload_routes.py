import os
from datetime import datetime
from flask import request, jsonify
from werkzeug.utils import secure_filename


def register_chunk_upload_routes(app, context):
    get_supabase = context['get_supabase']
    get_log = context['get_log']
    upload_folder = context['UPLOAD_FOLDER']
    allowed_extensions = context['ALLOWED_EXTENSIONS']
    max_file_size = context['MAX_FILE_SIZE']
    allowed_file = context['allowed_file']
    extract_text_from_file = context['extract_text_from_file']
    sanitize_text = context['sanitize_text']
    chunk_text = context['chunk_text']

    @app.route('/subjects/<int:subject_id>/upload', methods=['POST'])
    def upload_file(subject_id):
        """Upload file, extract text, chunk, and store"""
        filepath = None
        try:
            supabase = get_supabase()
            subject_check = supabase.table('subjects').select('id').eq('id', subject_id).execute()
            if not subject_check.data:
                return jsonify({'status': 'error', 'message': 'Subject not found'}), 404

            if 'file' not in request.files:
                return jsonify({'status': 'error', 'message': 'Geen bestand geüpload'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'status': 'error', 'message': 'Geen bestand geselecteerd'}), 400

            if not allowed_file(file.filename, allowed_extensions):
                return jsonify({'status': 'error', 'message': 'Bestandstype niet ondersteund. Ondersteunde types: TXT, PDF, DOC, DOCX'}), 400

            if len(file.read()) > max_file_size:
                file.seek(0)
                return jsonify({'status': 'error', 'message': 'Bestandsgrootte mag niet groter zijn dan 50 MB'}), 400

            file.seek(0)
            filename = secure_filename(file.filename)
            unique_filename = f"{datetime.utcnow().timestamp()}_{filename}"
            filepath = os.path.join(upload_folder, unique_filename)
            file.save(filepath)
            print(f"[DEBUG] File saved to: {filepath}")

            text = extract_text_from_file(filepath)
            if not text:
                return jsonify({'status': 'error', 'message': 'Kon geen text uit bestand extraheren'}), 400

            chunk_size = request.form.get('chunk_size', 500, type=int)
            text = sanitize_text(text)
            chunks = chunk_text(text, chunk_size=chunk_size, overlap=100)

            if not chunks:
                return jsonify({'status': 'error', 'message': 'Geen content gevonden in bestand'}), 400

            chunk_records = []
            for index, chunk_content in enumerate(chunks):
                chunk_record = {
                    'subject_id': subject_id,
                    'content': sanitize_text(chunk_content),
                    'source_file': filename,
                    'chunk_metadata': {
                        'chunk_index': index,
                        'chunk_size': chunk_size,
                        'total_chunks': len(chunks),
                        'uploaded_at': datetime.utcnow().isoformat(),
                        'original_filename': filename
                    },
                    'created_at': datetime.utcnow().isoformat(),
                    'updated_at': datetime.utcnow().isoformat()
                }
                chunk_records.append(chunk_record)

            supabase.table('chunks').insert(chunk_records).execute()
            return jsonify({
                'status': 'success',
                'message': f'Bestand geüpload en {len(chunks)} chunks aangemaakt',
                'chunks_created': len(chunks),
                'filename': filename
            }), 201
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij uploaden bestand: {str(error)}'}), 500
        finally:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass

    @app.route('/subjects/<int:subject_id>/uploads/<path:upload_name>', methods=['DELETE'])
    def delete_upload(subject_id, upload_name):
        """Delete an uploaded material by filename and remove all related chunks"""
        try:
            supabase = get_supabase()
            subject_check = supabase.table('subjects').select('id').eq('id', subject_id).execute()
            if not subject_check.data:
                return jsonify({'status': 'error', 'message': 'Subject not found'}), 404

            existing_chunks = (
                supabase.table('chunks')
                .select('id', count='exact')
                .eq('subject_id', subject_id)
                .eq('source_file', upload_name)
                .execute()
            )

            matching_count = existing_chunks.count or len(existing_chunks.data or [])
            if matching_count == 0:
                return jsonify({'status': 'error', 'message': 'Upload not found for this subject'}), 404

            supabase.table('chunks').delete().eq('subject_id', subject_id).eq('source_file', upload_name).execute()
            return jsonify({
                'status': 'success',
                'message': f'Upload verwijderd: {upload_name}',
                'upload_name': upload_name,
                'deleted_chunks': matching_count
            }), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij verwijderen upload: {str(error)}'}), 500

    @app.route('/subjects/<int:subject_id>/chunks', methods=['GET'])
    def get_chunks(subject_id):
        """Get all chunks for a subject"""
        try:
            log = get_log()
            log.info('[RETRIEVE TRACE] GET /subjects/%s/chunks from %s ua=%s', subject_id, request.remote_addr, request.headers.get('User-Agent', 'unknown'))
            supabase = get_supabase()
            data = supabase.table('chunks').select('*').eq('subject_id', subject_id).order('id').execute()
            return jsonify({'status': 'success', 'chunks': data.data, 'count': len(data.data)}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij ophalen chunks: {str(error)}'}), 500

    @app.route('/subjects/<int:subject_id>/chunks', methods=['POST'])
    def create_chunk(subject_id):
        """Create new chunk"""
        try:
            data = request.get_json()
            if not data or 'content' not in data:
                return jsonify({'status': 'error', 'message': 'Content is required'}), 400

            chunk = {
                'subject_id': subject_id,
                'content': data['content'],
                'source_file': data.get('source_file'),
                'chunk_metadata': data.get('chunk_metadata', {}),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }

            supabase = get_supabase()
            result = supabase.table('chunks').insert(chunk).execute()
            return jsonify({'status': 'success', 'message': 'Chunk created', 'chunk': result.data[0] if result.data else chunk}), 201
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij aanmaken chunk: {str(error)}'}), 500

    @app.route('/chunks/<int:chunk_id>', methods=['GET'])
    def get_chunk(chunk_id):
        """Get specific chunk"""
        try:
            supabase = get_supabase()
            data = supabase.table('chunks').select('*').eq('id', chunk_id).execute()
            if not data.data:
                return jsonify({'status': 'error', 'message': 'Chunk not found'}), 404
            return jsonify({'status': 'success', 'chunk': data.data[0]}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij ophalen chunk: {str(error)}'}), 500

    @app.route('/chunks/<int:chunk_id>', methods=['PUT'])
    def update_chunk(chunk_id):
        """Update chunk"""
        try:
            data = request.get_json()
            update_data = {'updated_at': datetime.utcnow().isoformat()}
            if 'content' in data:
                update_data['content'] = data['content']
            if 'source_file' in data:
                update_data['source_file'] = data['source_file']
            if 'chunk_metadata' in data:
                update_data['chunk_metadata'] = data['chunk_metadata']

            supabase = get_supabase()
            result = supabase.table('chunks').update(update_data).eq('id', chunk_id).execute()
            if not result.data:
                return jsonify({'status': 'error', 'message': 'Chunk not found'}), 404
            return jsonify({'status': 'success', 'message': 'Chunk updated', 'chunk': result.data[0]}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij bijwerken chunk: {str(error)}'}), 500

    @app.route('/chunks/<int:chunk_id>', methods=['DELETE'])
    def delete_chunk(chunk_id):
        """Delete chunk"""
        try:
            supabase = get_supabase()
            supabase.table('chunks').delete().eq('id', chunk_id).execute()
            return jsonify({'status': 'success', 'message': 'Chunk deleted'}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij verwijderen chunk: {str(error)}'}), 500

    @app.route('/subjects/<int:subject_id>/chunks/bulk', methods=['POST'])
    def bulk_create_chunks(subject_id):
        """Bulk create chunks from JSON array"""
        try:
            data = request.get_json()
            if not data or 'chunks' not in data:
                return jsonify({'status': 'error', 'message': 'chunks array is required'}), 400

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

            supabase = get_supabase()
            supabase.table('chunks').insert(created_chunks).execute()
            return jsonify({'status': 'success', 'message': f'{len(created_chunks)} chunks created', 'count': len(created_chunks)}), 201
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij bulk aanmaken chunks: {str(error)}'}), 500
