from datetime import datetime
from flask import request, jsonify


def register_prompt_routes(app, context):
    get_supabase = context['get_supabase']

    @app.route('/prompts', methods=['GET'])
    def get_prompts():
        """Get all prompts (global management)"""
        try:
            supabase = get_supabase()
            data = supabase.table('prompts').select('*').order('created_at', desc=True).execute()
            return jsonify({'status': 'success', 'prompts': data.data}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij ophalen prompts: {str(error)}'}), 500

    @app.route('/prompts', methods=['POST'])
    def create_prompt():
        """Create new prompt (global management)"""
        try:
            data = request.get_json()
            if not data or 'title' not in data or 'content' not in data:
                return jsonify({'status': 'error', 'message': 'Title and content are required'}), 400

            prompt = {
                'subject_id': None,
                'title': data['title'],
                'content': data['content'],
                'is_active': data.get('is_active', True),
                'is_default': data.get('is_default', False),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }

            supabase = get_supabase()
            result = supabase.table('prompts').insert(prompt).execute()
            return jsonify({'status': 'success', 'message': 'Prompt created', 'prompt': result.data[0] if result.data else prompt}), 201
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij aanmaken prompt: {str(error)}'}), 500

    @app.route('/prompts/<int:prompt_id>', methods=['GET'])
    def get_prompt(prompt_id):
        """Get specific prompt"""
        try:
            supabase = get_supabase()
            data = supabase.table('prompts').select('*').eq('id', prompt_id).execute()
            if not data.data:
                return jsonify({'status': 'error', 'message': 'Prompt not found'}), 404
            return jsonify({'status': 'success', 'prompt': data.data[0]}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij ophalen prompt: {str(error)}'}), 500

    @app.route('/prompts/<int:prompt_id>', methods=['PUT', 'PATCH'])
    def update_prompt(prompt_id):
        """Update prompt"""
        try:
            data = request.get_json()
            update_data = {'updated_at': datetime.utcnow().isoformat()}
            if 'title' in data:
                update_data['title'] = data['title']
            if 'content' in data:
                update_data['content'] = data['content']
            if 'is_active' in data:
                update_data['is_active'] = data['is_active']
            if 'is_default' in data:
                update_data['is_default'] = data['is_default']

            supabase = get_supabase()
            result = supabase.table('prompts').update(update_data).eq('id', prompt_id).execute()
            if not result.data:
                return jsonify({'status': 'error', 'message': 'Prompt not found'}), 404
            return jsonify({'status': 'success', 'message': 'Prompt updated', 'prompt': result.data[0]}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij bijwerken prompt: {str(error)}'}), 500

    @app.route('/prompts/<int:prompt_id>', methods=['DELETE'])
    def delete_prompt(prompt_id):
        """Delete prompt"""
        try:
            supabase = get_supabase()
            supabase.table('prompts').delete().eq('id', prompt_id).execute()
            return jsonify({'status': 'success', 'message': 'Prompt deleted'}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij verwijderen prompt: {str(error)}'}), 500

    @app.route('/prompts/active', methods=['GET'])
    def get_active_prompts():
        """Get all active prompts (for LLM usage)"""
        try:
            supabase = get_supabase()
            data = supabase.table('prompts').select('*').eq('is_active', True).order('created_at', desc=True).execute()
            return jsonify({'status': 'success', 'prompts': data.data}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij ophalen active prompts: {str(error)}'}), 500
