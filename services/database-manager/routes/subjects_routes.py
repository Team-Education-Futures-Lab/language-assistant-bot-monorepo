from datetime import datetime
from flask import request, jsonify


def register_subject_routes(app, context):
    get_supabase = context['get_supabase']
    get_log = context['get_log']

    @app.route('/subjects', methods=['GET'])
    def get_subjects():
        """Get all subjects"""
        try:
            log = get_log()
            log.info('[RETRIEVE TRACE] GET /subjects from %s ua=%s', request.remote_addr, request.headers.get('User-Agent', 'unknown'))
            supabase = get_supabase()
            data = supabase.table('subjects').select('*').execute()

            subjects = data.data or []
            for subject in subjects:
                raw_retrieval_k = subject.get('retrieval_k', 10)
                try:
                    subject['retrieval_k'] = int(raw_retrieval_k)
                except (TypeError, ValueError):
                    subject['retrieval_k'] = 10

            return jsonify({
                'status': 'success',
                'subjects': subjects
            }), 200
        except Exception as error:
            return jsonify({
                'status': 'error',
                'message': f'Fout bij ophalen subjects: {str(error)}'
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

            raw_retrieval_k = data.get('retrieval_k', 10)
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

            subject = {
                'name': data['name'],
                'description': data.get('description', ''),
                'retrieval_k': retrieval_k,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }

            supabase = get_supabase()
            result = supabase.table('subjects').insert(subject).execute()

            return jsonify({
                'status': 'success',
                'message': 'Subject created',
                'subject': result.data[0] if result.data else subject
            }), 201
        except Exception as error:
            return jsonify({
                'status': 'error',
                'message': f'Fout bij aanmaken subject: {str(error)}'
            }), 500

    @app.route('/subjects/<int:subject_id>', methods=['GET'])
    def get_subject(subject_id):
        """Get specific subject"""
        try:
            supabase = get_supabase()
            data = supabase.table('subjects').select('*').eq('id', subject_id).execute()

            if not data.data:
                return jsonify({
                    'status': 'error',
                    'message': 'Subject not found'
                }), 404

            subject = data.data[0]
            raw_retrieval_k = subject.get('retrieval_k', 10)
            try:
                subject['retrieval_k'] = int(raw_retrieval_k)
            except (TypeError, ValueError):
                subject['retrieval_k'] = 10

            return jsonify({
                'status': 'success',
                'subject': subject
            }), 200
        except Exception as error:
            return jsonify({
                'status': 'error',
                'message': f'Fout bij ophalen subject: {str(error)}'
            }), 500

    @app.route('/subjects/<int:subject_id>', methods=['PUT'])
    def update_subject(subject_id):
        """Update subject"""
        try:
            data = request.get_json()
            update_data = {'updated_at': datetime.utcnow().isoformat()}

            if 'name' in data:
                update_data['name'] = data['name']
            if 'description' in data:
                update_data['description'] = data['description']

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
                    update_data['retrieval_k'] = retrieval_k

            supabase = get_supabase()
            result = supabase.table('subjects').update(update_data).eq('id', subject_id).execute()

            if not result.data:
                return jsonify({
                    'status': 'error',
                    'message': 'Subject not found'
                }), 404

            raw_retrieval_k = result.data[0].get('retrieval_k', 10)
            try:
                result.data[0]['retrieval_k'] = int(raw_retrieval_k)
            except (TypeError, ValueError):
                result.data[0]['retrieval_k'] = 10

            return jsonify({
                'status': 'success',
                'message': 'Subject updated',
                'subject': result.data[0]
            }), 200
        except Exception as error:
            return jsonify({
                'status': 'error',
                'message': f'Fout bij bijwerken subject: {str(error)}'
            }), 500

    @app.route('/subjects/<int:subject_id>', methods=['DELETE'])
    def delete_subject(subject_id):
        """Delete subject (cascades to chunks)"""
        try:
            supabase = get_supabase()
            supabase.table('subjects').delete().eq('id', subject_id).execute()
            return jsonify({
                'status': 'success',
                'message': 'Subject deleted'
            }), 200
        except Exception as error:
            return jsonify({
                'status': 'error',
                'message': f'Fout bij verwijderen subject: {str(error)}'
            }), 500
