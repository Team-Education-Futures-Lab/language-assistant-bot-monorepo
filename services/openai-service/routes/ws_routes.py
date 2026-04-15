import json
import threading
from simple_websocket import ConnectionClosed


def register_ws_routes(sock, context):
    log = context['log']
    clamp_realtime_speed = context['clamp_realtime_speed']
    openai_realtime_speed_default = context['OPENAI_REALTIME_SPEED_DEFAULT']
    build_openai_session_config = context['build_openai_session_config']
    build_session_state = context['build_session_state']
    connect_to_openai = context['connect_to_openai']
    maybe_start_openai_keepalive = context['maybe_start_openai_keepalive']
    build_dutch_system_message = context['build_dutch_system_message']
    openai_listener = context['openai_listener']
    send_openai = context['send_openai']
    send_browser = context['send_browser']
    close_state = context['close_state']

    @sock.route('/ws/realtime-voice')
    def realtime_voice_socket(ws):
        log.info('[BROWSER WS] New browser WebSocket connection')
        state = build_session_state(ws)

        try:
            while True:
                raw_message = ws.receive()
                if raw_message is None:
                    log.info('[BROWSER WS] Browser disconnected (None message)')
                    break

                payload = json.loads(raw_message)
                message_type = payload.get('type', '')

                if message_type == 'session.start':
                    log.info('[SESSION] session.start received from browser')
                    requested_speed = clamp_realtime_speed(payload.get('speed', openai_realtime_speed_default))
                    state['playback_speed'] = requested_speed
                    session_config = build_openai_session_config(speed=requested_speed)
                    state['openai_ws'] = connect_to_openai(session_config)
                    state['openai_ping_thread'] = maybe_start_openai_keepalive(state)
                    send_openai(state, build_dutch_system_message())
                    log.info('[SESSION] Dutch system instruction injected into conversation context')
                    threading.Thread(target=openai_listener, args=(state,), daemon=True).start()
                    log.info('[SESSION] Listener thread started, sending session.started to browser')
                    send_browser(
                        ws,
                        {
                            'type': 'session.started',
                            'message': 'Realtime sessie gestart',
                        },
                    )
                    continue

                if message_type == 'session.update':
                    if state['openai_ws'] is None:
                        log.warning('[SESSION] session.update received but session not started')
                        send_browser(ws, {'type': 'error', 'message': 'Realtime sessie is nog niet gestart'})
                        continue

                    requested_speed = clamp_realtime_speed(payload.get('speed', state.get('playback_speed', openai_realtime_speed_default)))
                    state['playback_speed'] = requested_speed
                    send_openai(
                        state,
                        {
                            'type': 'session.update',
                            'session': {
                                'type': 'realtime',
                                'audio': {
                                    'output': {
                                        'speed': requested_speed,
                                    }
                                }
                            },
                        },
                    )
                    send_browser(ws, {'type': 'session.updated', 'speed': requested_speed})
                    log.info('[SESSION] Applied speed update: %.2f', requested_speed)
                    continue

                if message_type == 'audio.chunk':
                    if state['openai_ws'] is None:
                        log.warning('[AUDIO] audio.chunk received but session not started')
                        send_browser(ws, {'type': 'error', 'message': 'Realtime sessie is nog niet gestart'})
                        continue

                    if state.get('response_in_progress'):
                        continue

                    audio_b64 = payload.get('audio', '')
                    if not audio_b64:
                        continue

                    send_openai(
                        state,
                        {
                            'type': 'input_audio_buffer.append',
                            'audio': audio_b64,
                        },
                    )
                    continue

                if message_type == 'recording.stop':
                    log.info('[SESSION] recording.stop received from browser, keeping session open for response audio')
                    continue

                if message_type == 'session.close':
                    log.info('[SESSION] session.close received from browser')
                    break

                # Ignore unknown browser message types.

        except ConnectionClosed:
            log.info('[BROWSER WS] Browser closed connection normally')
        except Exception as error:
            log.exception('[BROWSER WS] Error in realtime_voice_socket: %s', error)
            try:
                send_browser(ws, {'type': 'error', 'message': str(error)})
            except Exception:
                pass
        finally:
            log.info('[BROWSER WS] Browser WebSocket handler exiting')
            close_state(state)
