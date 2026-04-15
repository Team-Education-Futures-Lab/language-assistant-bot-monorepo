from flask import jsonify


def register_http_routes(app, context):
    limiter = context['limiter']
    rate_limit_default = context['RATE_LIMIT_DEFAULT']
    service_name = context['SERVICE_NAME']
    openai_api_key = context['OPENAI_API_KEY']
    service_host = context['SERVICE_HOST']
    service_port = context['SERVICE_PORT']
    get_openai_realtime_model = context['get_openai_realtime_model']
    get_openai_realtime_voice = context['get_openai_realtime_voice']

    @app.route('/', methods=['GET'])
    @limiter.limit(rate_limit_default)
    def root():
        return jsonify(
            {
                'status': 'ok',
                'service': service_name,
                'message': 'Realtime voice service is actief',
            }
        ), 200

    @app.route('/health', methods=['GET'])
    @limiter.limit(rate_limit_default)
    def health():
        api_key_present = bool(openai_api_key)
        openai_realtime_model = get_openai_realtime_model()
        openai_realtime_voice = get_openai_realtime_voice()

        return jsonify(
            {
                'status': 'ok' if api_key_present else 'degraded',
                'service': service_name,
                'openai_api_key_configured': api_key_present,
                'service_host': service_host,
                'service_port': service_port,
                'model': openai_realtime_model,
                'voice': openai_realtime_voice,
            }
        ), 200 if api_key_present else 503
