import threading
import time
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException, create_connection


def register_ws_routes(sock, config):
    realtime_voice_service_ws_url = config['REALTIME_VOICE_SERVICE_WS_URL']
    gateway_backend_ws_timeout_sec = config['GATEWAY_BACKEND_WS_TIMEOUT_SEC']
    gateway_backend_ws_ping_interval_sec = config['GATEWAY_BACKEND_WS_PING_INTERVAL_SEC']

    @sock.route('/api/query/ws/realtime-voice')
    def realtime_voice_proxy(ws):
        backend_ws = create_connection(
            realtime_voice_service_ws_url,
            timeout=gateway_backend_ws_timeout_sec,
            enable_multithread=True,
        )
        stop_event = threading.Event()

        def forward_backend_to_browser():
            try:
                while not stop_event.is_set():
                    try:
                        message = backend_ws.recv()
                    except WebSocketTimeoutException:
                        continue

                    if not message:
                        break
                    ws.send(message)
            except Exception:
                pass
            finally:
                stop_event.set()

        def keep_backend_alive():
            if gateway_backend_ws_ping_interval_sec <= 0:
                return

            while not stop_event.is_set():
                time.sleep(gateway_backend_ws_ping_interval_sec)
                if stop_event.is_set():
                    break

                try:
                    backend_ws.ping('gateway-keepalive')
                except (WebSocketConnectionClosedException, WebSocketTimeoutException):
                    break
                except Exception:
                    break

        backend_thread = threading.Thread(target=forward_backend_to_browser, daemon=True)
        backend_thread.start()
        ping_thread = threading.Thread(target=keep_backend_alive, daemon=True)
        ping_thread.start()

        try:
            while not stop_event.is_set():
                message = ws.receive()
                if message is None:
                    break
                backend_ws.send(message)
        finally:
            stop_event.set()
            try:
                backend_ws.close()
            except Exception:
                pass
