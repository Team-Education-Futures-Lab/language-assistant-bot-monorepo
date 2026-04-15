from flask import jsonify


def register_health_routes(app, context):
    service_name = context['SERVICE_NAME']
    service_host = context['SERVICE_HOST']
    service_port = context['SERVICE_PORT']
    get_db_connected = context['get_db_connected']
    get_vector_db_connected = context['get_vector_db_connected']

    @app.route('/health/all', methods=['GET'])
    def health():
        """Full health check: database-manager server plus Supabase/vector DB connectivity."""
        return jsonify({
            'status': 'healthy',
            'service': service_name,
            'database': 'connected' if get_db_connected() else 'disconnected',
            'vector_database': 'connected' if get_vector_db_connected() else 'disconnected'
        }), 200

    @app.route('/health', methods=['GET'])
    def health_server_only():
        """Health check for the database-manager process only."""
        return jsonify({
            'status': 'healthy',
            'service': service_name,
            'database_manager': {
                'host': service_host,
                'port': service_port,
            }
        }), 200
