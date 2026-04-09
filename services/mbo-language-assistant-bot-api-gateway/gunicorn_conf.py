import os


bind = f"0.0.0.0:{os.getenv('PORT', os.getenv('GATEWAY_PORT', '5000'))}"
worker_class = os.getenv(
    'GUNICORN_WORKER_CLASS',
    'geventwebsocket.gunicorn.workers.GeventWebSocketWorker',
)
workers = int(os.getenv('WEB_CONCURRENCY', '1'))
timeout = int(os.getenv('GUNICORN_TIMEOUT', '180'))
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '5'))
loglevel = os.getenv('GUNICORN_LOG_LEVEL', os.getenv('LOG_LEVEL', 'info')).lower()
accesslog = '-'
errorlog = '-'

