from flask import jsonify
import requests


def register_health_routes(app, config):
    database_service_url = config['DATABASE_SERVICE_URL']
    realtime_voice_service_url = config['REALTIME_VOICE_SERVICE_URL']
    gateway_host = config['GATEWAY_HOST']
    gateway_port = config['GATEWAY_PORT']

    @app.route('/api/query/health/gateway', methods=['GET'])
    def health_gateway_only():
        """Health check for the API Gateway process only."""
        return jsonify({
            'status': 'healthy',
            'gateway': {
                'host': gateway_host,
                'port': gateway_port,
            }
        }), 200

    @app.route('/api/query/health', methods=['GET'])
    @app.route('/api/query/health/all', methods=['GET'])
    def health_detailed():
        """Detailed health check with gateway and downstream service status."""
        services_status = {}

        services_status['gateway'] = {
            'status': 'healthy',
            'host': gateway_host,
            'port': gateway_port,
        }

        try:
            response = requests.get(f'{database_service_url}/health', timeout=2)
            services_status['database_service'] = {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'url': database_service_url
            }
        except Exception as error:
            services_status['database_service'] = {
                'status': 'unreachable',
                'url': database_service_url,
                'error': str(error)
            }

        try:
            response = requests.get(f'{realtime_voice_service_url}/health', timeout=2)
            services_status['realtime_voice_service'] = {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'url': realtime_voice_service_url
            }
        except Exception as error:
            services_status['realtime_voice_service'] = {
                'status': 'unreachable',
                'url': realtime_voice_service_url,
                'error': str(error)
            }

        all_healthy = all(service['status'] == 'healthy' for service in services_status.values())

        return jsonify({
            'status': 'healthy' if all_healthy else 'degraded',
            'gateway': {
                'host': gateway_host,
                'port': gateway_port
            },
            'services': services_status
        }), 200 if all_healthy else 503
