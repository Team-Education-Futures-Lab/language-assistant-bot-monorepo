from flask import Response, jsonify, request
import requests
from urllib.parse import quote


def _build_proxy_response(response):
    return Response(response.content, status=response.status_code, content_type=response.headers['content-type'])


def register_database_routes(app, config):
    database_service_url = config['DATABASE_SERVICE_URL']

    @app.route('/api/query/subjects', methods=['GET', 'POST'])
    def subjects():
        """Proxy for subjects list and create"""
        try:
            if request.method == 'GET':
                response = requests.get(f'{database_service_url}/subjects', timeout=10)
            else:
                response = requests.post(
                    f'{database_service_url}/subjects',
                    json=request.get_json(),
                    timeout=10
                )
            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500

    @app.route('/api/query/subjects/<int:subject_id>', methods=['GET', 'PUT', 'DELETE'])
    def subject_detail(subject_id):
        """Proxy for subject detail, update, delete"""
        try:
            if request.method == 'GET':
                response = requests.get(f'{database_service_url}/subjects/{subject_id}', timeout=10)
            elif request.method == 'PUT':
                response = requests.put(
                    f'{database_service_url}/subjects/{subject_id}',
                    json=request.get_json(),
                    timeout=10
                )
            else:
                response = requests.delete(f'{database_service_url}/subjects/{subject_id}', timeout=10)
            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500

    @app.route('/api/query/subjects/<int:subject_id>/upload', methods=['POST'])
    def subject_upload(subject_id):
        """Proxy for file upload"""
        try:
            files = {
                'file': (
                    request.files['file'].filename,
                    request.files['file'].stream,
                    request.files['file'].content_type,
                )
            }
            response = requests.post(
                f'{database_service_url}/subjects/{subject_id}/upload',
                files=files,
                timeout=300
            )
            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500

    @app.route('/api/query/subjects/<int:subject_id>/uploads/<path:upload_name>', methods=['DELETE'])
    def subject_upload_delete(subject_id, upload_name):
        """Proxy for deleting an upload and all related chunks"""
        try:
            response = requests.delete(
                f'{database_service_url}/subjects/{subject_id}/uploads/{quote(upload_name, safe="")}',
                timeout=30
            )
            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500

    @app.route('/api/query/subjects/<int:subject_id>/chunks', methods=['GET', 'POST'])
    def subject_chunks(subject_id):
        """Proxy for getting and creating chunks"""
        try:
            if request.method == 'GET':
                response = requests.get(f'{database_service_url}/subjects/{subject_id}/chunks', timeout=10)
            else:
                response = requests.post(
                    f'{database_service_url}/subjects/{subject_id}/chunks',
                    json=request.get_json(),
                    timeout=10
                )
            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500

    @app.route('/api/query/chunks/<int:chunk_id>', methods=['GET', 'PUT', 'DELETE'])
    def chunk_detail(chunk_id):
        """Proxy for chunk detail, update, delete"""
        try:
            if request.method == 'GET':
                response = requests.get(f'{database_service_url}/chunks/{chunk_id}', timeout=10)
            elif request.method == 'PUT':
                response = requests.put(
                    f'{database_service_url}/chunks/{chunk_id}',
                    json=request.get_json(),
                    timeout=10
                )
            else:
                response = requests.delete(f'{database_service_url}/chunks/{chunk_id}', timeout=10)

            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500

    @app.route('/api/query/prompts', methods=['GET', 'POST'])
    def prompts():
        """Proxy for getting and creating prompts (global management)"""
        try:
            if request.method == 'GET':
                response = requests.get(f'{database_service_url}/prompts', timeout=10)
            else:
                response = requests.post(
                    f'{database_service_url}/prompts',
                    json=request.get_json(),
                    timeout=10
                )
            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500

    @app.route('/api/query/prompts/active', methods=['GET'])
    def prompts_active():
        """Proxy for getting active prompts (used by LLM services)"""
        try:
            response = requests.get(f'{database_service_url}/prompts/active', timeout=10)
            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500

    @app.route('/api/query/prompts/<int:prompt_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
    def prompt_detail(prompt_id):
        """Proxy for prompt detail, update, delete"""
        try:
            if request.method == 'GET':
                response = requests.get(f'{database_service_url}/prompts/{prompt_id}', timeout=10)
            elif request.method in ['PUT', 'PATCH']:
                response = requests.patch(
                    f'{database_service_url}/prompts/{prompt_id}',
                    json=request.get_json(),
                    timeout=10
                )
            else:
                response = requests.delete(f'{database_service_url}/prompts/{prompt_id}', timeout=10)
            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500

    @app.route('/api/query/settings', methods=['GET', 'POST'])
    def settings():
        """Proxy for getting and creating/updating settings"""
        try:
            if request.method == 'GET':
                response = requests.get(
                    f'{database_service_url}/settings',
                    params=request.args,
                    timeout=10
                )
            else:
                response = requests.post(
                    f'{database_service_url}/settings',
                    json=request.get_json(),
                    timeout=10
                )
            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500

    @app.route('/api/query/settings/<key>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
    def setting_detail(key):
        """Proxy for setting detail, update, and delete"""
        try:
            if request.method == 'GET':
                response = requests.get(f'{database_service_url}/settings/{key}', timeout=10)
            elif request.method == 'PUT':
                response = requests.put(
                    f'{database_service_url}/settings/{key}',
                    json=request.get_json(),
                    timeout=10
                )
            elif request.method == 'PATCH':
                response = requests.patch(
                    f'{database_service_url}/settings/{key}',
                    json=request.get_json(),
                    timeout=10
                )
            else:
                response = requests.delete(f'{database_service_url}/settings/{key}', timeout=10)
            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500

    @app.route('/api/query/retrieve', methods=['POST'])
    def retrieve_context():
        """Proxy retrieval requests to Database Manager."""
        try:
            response = requests.post(
                f'{database_service_url}/retrieve',
                json=request.get_json(),
                timeout=30
            )
            return _build_proxy_response(response)
        except Exception as error:
            return jsonify({'status': 'error', 'message': str(error)}), 500
