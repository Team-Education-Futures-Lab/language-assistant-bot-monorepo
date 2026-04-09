import os


bind = f"0.0.0.0:{os.getenv('PORT', os.getenv('SERVICE_PORT', '5004'))}"
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')
workers = int(os.getenv('WEB_CONCURRENCY', '1'))
threads = int(os.getenv('GUNICORN_THREADS', '4'))
timeout = int(os.getenv('GUNICORN_TIMEOUT', '180'))
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '5'))
loglevel = os.getenv('GUNICORN_LOG_LEVEL', os.getenv('LOG_LEVEL', 'info')).lower()
accesslog = '-'
errorlog = '-'

