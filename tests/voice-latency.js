const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('@playwright/test');

const REPO_ROOT = path.resolve(__dirname, '..');
const APP_PORT = 3100;
const APP_URL = `http://127.0.0.1:${APP_PORT}`;
const MIC_BUTTON_SELECTOR = 'button[title="Opname starten"]';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function createPcm16SineWaveWav(filePath, durationMs = 1200, sampleRate = 16000, frequencyHz = 440) {
  const sampleCount = Math.floor((sampleRate * durationMs) / 1000);
  const bytesPerSample = 2;
  const dataSize = sampleCount * bytesPerSample;
  const buffer = Buffer.alloc(44 + dataSize);

  buffer.write('RIFF', 0);
  buffer.writeUInt32LE(36 + dataSize, 4);
  buffer.write('WAVE', 8);
  buffer.write('fmt ', 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * bytesPerSample, 28);
  buffer.writeUInt16LE(bytesPerSample, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write('data', 36);
  buffer.writeUInt32LE(dataSize, 40);

  for (let index = 0; index < sampleCount; index += 1) {
    const t = index / sampleRate;
    const amplitude = 0.24;
    const sample = Math.round(Math.sin(2 * Math.PI * frequencyHz * t) * 32767 * amplitude);
    buffer.writeInt16LE(sample, 44 + index * 2);
  }

  fs.writeFileSync(filePath, buffer);
}

function createAssistantAudioBase64(durationMs = 350, sampleRate = 24000) {
  const sampleCount = Math.floor((sampleRate * durationMs) / 1000);
  return Buffer.alloc(sampleCount * 2).toString('base64');
}

function waitForHttp(url, timeoutMs = 120000) {
  const startedAt = Date.now();

  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const response = await fetch(url);
        if (response.ok) {
          resolve();
          return;
        }
      } catch (error) {
        // keep polling until timeout
      }

      if (Date.now() - startedAt >= timeoutMs) {
        reject(new Error(`Timed out waiting for ${url}`));
        return;
      }

      setTimeout(tick, 500);
    };

    tick();
  });
}

function startAppServer() {
  const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const child = spawn(npmCommand, ['run', 'start', '--prefix', 'NT2-chatbot'], {
    cwd: REPO_ROOT,
    env: {
      ...process.env,
      PORT: String(APP_PORT),
      HOST: '127.0.0.1',
      BROWSER: 'none',
      CI: 'true',
    },
    shell: process.platform === 'win32',
    stdio: 'inherit',
  });

  return child;
}

async function main() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'nt2-voice-latency-'));
  const fakeAudioPath = path.join(tempDir, 'fake-mic.wav');
  createPcm16SineWaveWav(fakeAudioPath);
  const assistantAudioBase64 = createAssistantAudioBase64();

  const appServer = startAppServer();
  const cleanup = async () => {
    try {
      if (!appServer.killed) {
        appServer.kill('SIGINT');
      }
    } catch (error) {
      // ignore cleanup errors
    }

    try {
      fs.rmSync(tempDir, { recursive: true, force: true });
    } catch (error) {
      // ignore cleanup errors
    }
  };

  process.on('SIGINT', async () => {
    await cleanup();
    process.exit(130);
  });

  process.on('SIGTERM', async () => {
    await cleanup();
    process.exit(143);
  });

  try {
    await waitForHttp(APP_URL, 120000);

    const browser = await chromium.launch({
      headless: true,
      args: [
        '--use-fake-ui-for-media-stream',
        '--use-fake-device-for-media-stream',
        `--use-file-for-fake-audio-capture=${fakeAudioPath}`,
      ],
    });

    const context = await browser.newContext();
    await context.addInitScript((audioBase64) => {
      const metrics = {
        clickAt: null,
        sessionStartedAt: null,
        firstUserChunkAt: null,
        playbackStartedAt: null,
      };

      window.__nt2VoiceLatency = metrics;

      const originalAudioContext = window.AudioContext || window.webkitAudioContext;
      const patchAudioContext = (AudioContextCtor) => {
        if (!AudioContextCtor || !AudioContextCtor.prototype) return;
        const originalCreateBufferSource = AudioContextCtor.prototype.createBufferSource;

        AudioContextCtor.prototype.createBufferSource = function patchedCreateBufferSource() {
          const source = originalCreateBufferSource.call(this);
          const originalStart = source.start.bind(source);

          source.start = function patchedStart(...args) {
            if (!window.__nt2VoiceLatency.playbackStartedAt) {
              window.__nt2VoiceLatency.playbackStartedAt = performance.now();
            }
            return originalStart(...args);
          };

          return source;
        };
      };

      patchAudioContext(window.AudioContext);
      patchAudioContext(window.webkitAudioContext);

      class MockWebSocket {
        static CONNECTING = 0;
        static OPEN = 1;
        static CLOSING = 2;
        static CLOSED = 3;

        constructor(url) {
          this.url = url;
          this.readyState = MockWebSocket.CONNECTING;
          this.binaryType = 'blob';
          this.onopen = null;
          this.onmessage = null;
          this.onerror = null;
          this.onclose = null;

          setTimeout(() => {
            this.readyState = MockWebSocket.OPEN;
            if (typeof this.onopen === 'function') {
              this.onopen(new Event('open'));
            }
          }, 140);
        }

        send(rawPayload) {
          let payload = null;
          try {
            payload = JSON.parse(rawPayload);
          } catch (error) {
            payload = null;
          }

          if (!payload || typeof payload !== 'object') {
            return;
          }

          if (payload.type === 'session.start') {
            setTimeout(() => {
              window.__nt2VoiceLatency.sessionStartedAt = performance.now();
              this._emit({ type: 'session.started' });
            }, 90);
            return;
          }

          if (payload.type === 'audio.chunk' && !window.__nt2VoiceLatency.firstUserChunkAt) {
            window.__nt2VoiceLatency.firstUserChunkAt = performance.now();

            setTimeout(() => this._emit({ type: 'speech.started' }), 40);
            setTimeout(() => this._emit({ type: 'transcript.delta', transcript: 'Ik wil graag een oefening.' }), 80);
            setTimeout(() => this._emit({ type: 'speech.stopped' }), 140);
            setTimeout(() => this._emit({ type: 'transcript.final', transcript: 'Ik wil graag een oefening.' }), 180);
            setTimeout(() => this._emit({ type: 'assistant.response.started' }), 220);
            setTimeout(() => this._emit({ type: 'assistant.audio.delta', audio: audioBase64 }), 280);
            setTimeout(() => this._emit({ type: 'assistant.audio.done' }), 340);
            setTimeout(() => this._emit({ type: 'response.done' }), 420);
          }
        }

        close() {
          this.readyState = MockWebSocket.CLOSED;
          if (typeof this.onclose === 'function') {
            this.onclose(new Event('close'));
          }
        }

        addEventListener(eventName, handler) {
          this[`on${eventName}`] = handler;
        }

        removeEventListener(eventName, handler) {
          if (this[`on${eventName}`] === handler) {
            this[`on${eventName}`] = null;
          }
        }

        _emit(payload) {
          if (typeof this.onmessage === 'function') {
            this.onmessage({ data: JSON.stringify(payload) });
          }
        }
      }

      window.WebSocket = MockWebSocket;
    }, assistantAudioBase64);

    const page = await context.newPage();
    page.on('console', (message) => {
      if (message.type() === 'error') {
        console.error('[browser]', message.text());
      }
    });

    await page.goto(APP_URL, { waitUntil: 'domcontentloaded' });
    await page.locator(MIC_BUTTON_SELECTOR).waitFor({ state: 'visible', timeout: 30000 });

    await page.evaluate(() => {
      const button = document.querySelector('button[title="Opname starten"]');
      if (!button) {
        throw new Error('Mic button not found');
      }

      button.addEventListener('click', () => {
        window.__nt2VoiceLatency.clickAt = performance.now();
      }, { once: true });
    });

    await page.locator(MIC_BUTTON_SELECTOR).click();

    await page.waitForFunction(() => window.__nt2VoiceLatency?.sessionStartedAt != null, null, { timeout: 15000 });
    await page.waitForFunction(() => window.__nt2VoiceLatency?.playbackStartedAt != null, null, { timeout: 15000 });

    const metrics = await page.evaluate(() => window.__nt2VoiceLatency);
    const connectMs = Math.round(metrics.sessionStartedAt - metrics.clickAt);
    const firstChunkToPlaybackMs = Math.round(metrics.playbackStartedAt - metrics.firstUserChunkAt);
    const clickToPlaybackMs = Math.round(metrics.playbackStartedAt - metrics.clickAt);

    console.log('NT2 voice latency results');
    console.log(`  1. Mic click -> websocket/session start: ${connectMs} ms`);
    console.log(`  2. First audio chunk -> bot audio playback: ${firstChunkToPlaybackMs} ms`);
    console.log(`  2b. Mic click -> bot audio playback: ${clickToPlaybackMs} ms`);

    await browser.close();
  } finally {
    await cleanup();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});