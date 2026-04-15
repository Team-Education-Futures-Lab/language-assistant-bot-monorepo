from flask import request, jsonify


def register_settings_routes(app, context):
    openai_settings_table = context['OPENAI_SETTINGS_TABLE']
    get_supabase = context['get_supabase']

    @app.route('/settings', methods=['GET'])
    def get_settings():
        """Get all OpenAI/runtime settings"""
        try:
            prefix = request.args.get('prefix', '').strip()
            keys_csv = request.args.get('keys', '').strip()

            supabase = get_supabase()
            query = supabase.table(openai_settings_table).select('*').order('updated_at', desc=True)

            if prefix:
                query = query.like('key', f'{prefix}%')

            if keys_csv:
                keys = [key.strip() for key in keys_csv.split(',') if key.strip()]
                if keys:
                    query = query.in_('key', keys)

            data = query.execute()
            return jsonify({'status': 'success', 'settings': data.data}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij ophalen settings: {str(error)}'}), 500

    @app.route('/settings/<key>', methods=['GET'])
    def get_setting(key):
        """Get specific OpenAI/runtime setting by key"""
        try:
            supabase = get_supabase()
            data = (
                supabase.table(openai_settings_table)
                .select('*')
                .eq('key', key)
                .order('updated_at', desc=True)
                .limit(1)
                .execute()
            )

            if not data.data:
                return jsonify({'status': 'error', 'message': f'Setting "{key}" not found'}), 404
            return jsonify({'status': 'success', 'setting': data.data[0]}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij ophalen setting: {str(error)}'}), 500

    @app.route('/settings', methods=['POST'])
    def upsert_setting():
        """Create or update an OpenAI/runtime setting"""
        try:
            data = request.get_json()
            if not data or 'key' not in data or 'value' not in data:
                return jsonify({'status': 'error', 'message': 'key and value are required'}), 400

            key = data['key']
            value = str(data['value'])
            description = data.get('description', '')

            if not str(key).strip():
                return jsonify({'status': 'error', 'message': 'key cannot be empty'}), 400

            print('[DEBUG] === UPSERT SETTING ===')
            print(f'[DEBUG] Key: {key}')
            print(f'[DEBUG] Value: {value} (type: {type(value)})')
            print(f'[DEBUG] Description: {description}')

            supabase = get_supabase()
            check_result = (
                supabase.table(openai_settings_table)
                .select('*')
                .eq('key', key)
                .order('updated_at', desc=True)
                .limit(1)
                .execute()
            )
            print(f'[DEBUG] Existing setting: {check_result.data}')

            setting_data = {'key': key, 'value': value, 'description': description}

            if check_result.data:
                print('[DEBUG] Updating existing setting...')
                result = supabase.table(openai_settings_table).update({
                    'value': value,
                    'description': description
                }).eq('key', key).execute()
                print(f'[DEBUG] Update result: {result.data}')
            else:
                print('[DEBUG] Inserting new setting...')
                result = supabase.table(openai_settings_table).insert(setting_data).execute()
                print(f'[DEBUG] Insert result: {result.data}')

            verify_result = (
                supabase.table(openai_settings_table)
                .select('*')
                .eq('key', key)
                .order('updated_at', desc=True)
                .limit(1)
                .execute()
            )
            print(f'[DEBUG] After operation, setting is: {verify_result.data}')

            return jsonify({
                'status': 'success',
                'message': 'Setting saved',
                'setting': result.data[0] if result.data else setting_data
            }), 201
        except Exception as error:
            import traceback
            print(f'[ERROR] Failed to upsert setting: {str(error)}')
            print(f'[ERROR] Traceback: {traceback.format_exc()}')
            return jsonify({'status': 'error', 'message': f'Fout bij opslaan setting: {str(error)}'}), 500

    @app.route('/settings/<key>', methods=['PUT', 'PATCH'])
    def update_setting(key):
        """Update existing OpenAI/runtime setting by key (explicit update endpoint)"""
        try:
            data = request.get_json()
            if not data or 'value' not in data:
                return jsonify({'status': 'error', 'message': 'value is required'}), 400

            value = str(data['value'])
            description = data.get('description')

            supabase = get_supabase()
            existing = (
                supabase.table(openai_settings_table)
                .select('*')
                .eq('key', key)
                .order('updated_at', desc=True)
                .limit(1)
                .execute()
            )
            if not existing.data:
                return jsonify({'status': 'error', 'message': f'Setting "{key}" not found'}), 404

            update_data = {'value': value}
            if description is not None:
                update_data['description'] = description

            result = supabase.table(openai_settings_table).update(update_data).eq('key', key).execute()
            return jsonify({
                'status': 'success',
                'message': 'Setting updated',
                'setting': result.data[0] if result.data else {'key': key, **update_data}
            }), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij bijwerken setting: {str(error)}'}), 500

    @app.route('/settings/<key>', methods=['DELETE'])
    def delete_setting(key):
        """Delete an OpenAI/runtime setting"""
        try:
            supabase = get_supabase()
            supabase.table(openai_settings_table).delete().eq('key', key).execute()
            return jsonify({'status': 'success', 'message': f'Setting "{key}" deleted'}), 200
        except Exception as error:
            return jsonify({'status': 'error', 'message': f'Fout bij verwijderen setting: {str(error)}'}), 500
