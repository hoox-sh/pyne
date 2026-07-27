import type { Bar } from '../store/types';
import {
  appendBar,
  setLive,
  store,
  setStore,
  setStatus,
  appendLog,
  noteTick,
  setTelemetryPlane,
  setTelemetryState,
} from '../store';
import { getManager } from '../chart/manager-access';
import { runAndApply } from '../indicators/runner';
import {
  getStream,
  listStreams,
  defaultStreamForSource,
  type StreamPlugin,
} from './catalog';
import { classifyTransport } from '../ui/telemetry';

export type { StreamPlugin };
export { listStreams, defaultStreamForSource };

let currentStop: (() => void) | null = null;
let rerunTimer: ReturnType<typeof setTimeout> | null = null;
let rerunInFlight = false;

export function getAvailableStreams(): StreamPlugin[] {
  return listStreams();
}

export function startLive(streamId: string, symbol: string, interval: string) {
  stopLive();

  // Auto-pick stream if id missing / mismatched for source
  let id = streamId || store.live.streamId;
  if (!getStream(id)) {
    id = defaultStreamForSource(store.source);
  }
  const stream = getStream(id);
  if (!stream) {
    setStatus('error', `Unknown stream: ${id}`);
    setTelemetryState('stream', 'error', { error: `Unknown stream: ${id}` });
    return;
  }

  setStore('live', 'streamId', id);
  setStore('activePlugins', 'stream', id);
  setLive(true);
  // Honest connect state — green only after onStatus(open)
  setStore('stream', 'status', 'connecting');
  const transport = classifyTransport('stream', stream.id, stream.capabilities);
  setTelemetryPlane('stream', {
    id: stream.id,
    name: stream.name,
    transport,
    state: 'connecting',
    detail: `${symbol} ${interval}`,
    error: null,
  });
  appendLog('info', `Live start · ${stream.name} · ${symbol} ${interval}`, 'stream');

  const lastBar = store.bars.length ? store.bars[store.bars.length - 1] : null;
  let lastSeenBarTime = lastBar?.time ?? 0;

  const stop = stream.start({
    symbol,
    interval,
    lastBar,
    onBar: (bar: Bar) => {
      // Strip ephemeral closed flag before store (optional field is fine to keep)
      appendBar(bar);
      const manager = getManager();
      if (manager) manager.appendBar(bar);
      noteTick(bar.close, bar.time);

      const timeAdvanced = lastSeenBarTime > 0 && bar.time > lastSeenBarTime;
      lastSeenBarTime = bar.time;
      const mode = store.live.rerunOn || 'every-tick';
      if (mode === 'every-tick' || bar.closed || timeAdvanced) {
        scheduleRerun();
      }
    },
    onStatus: (s) => {
      if (s.state === 'open') {
        setStore('stream', 'status', 'connected');
        setTelemetryState('stream', 'open', {
          detail: s.detail || s.url || `${symbol} ${interval}`,
          error: null,
        });
        appendLog('ok', `Stream open${s.detail ? ` · ${s.detail}` : ''}`, 'stream');
      } else if (s.state === 'reconnecting') {
        setStore('stream', 'status', 'connecting');
        setTelemetryState('stream', 'degraded', { detail: s.detail || 'reconnecting' });
        appendLog('warn', `Stream reconnecting${s.detail ? ` · ${s.detail}` : ''}`, 'stream');
      } else if (s.state === 'closed') {
        // Only flip disconnected when live was stopped or exhausted — reconnect path uses degraded
        if (!store.live.active) {
          setStore('stream', 'status', 'disconnected');
          setTelemetryState('stream', 'closed');
        }
      }
    },
    onError: (e) => {
      appendLog('error', e.message || 'Stream error', 'stream');
      setStore('stream', 'status', 'error');
      setTelemetryState('stream', 'error', { error: e.message });
      setStatus('error', `Live error: ${e.message}`);
      stopLive();
    },
  });

  currentStop = stop;
}

export function stopLive() {
  const wasActive = store.live.active;
  // Mark inactive before stop() so reconnect closed callbacks don't fight UI state
  setLive(false);
  setStore('stream', 'status', 'disconnected');
  setTelemetryState('stream', 'closed', { error: null });
  if (currentStop) {
    currentStop();
    currentStop = null;
  }
  if (wasActive) {
    appendLog('info', 'Live stopped', 'stream');
  }
  if (rerunTimer) {
    clearTimeout(rerunTimer);
    rerunTimer = null;
  }
}

/**
 * Debounced re-run of all visible indicators after live bars.
 * Silent: no Results drawer spam; updates chart overlays only.
 */
function scheduleRerun() {
  if (!store.scripts.some((s) => s.visible && s.code?.trim())) return;
  if (rerunTimer) return;
  rerunTimer = setTimeout(async () => {
    rerunTimer = null;
    if (rerunInFlight || !store.live.active) return;
    rerunInFlight = true;
    setStore('live', 'needsRerun', false);
    try {
      for (const ind of store.scripts) {
        if (!ind.visible || !ind.code?.trim()) continue;
        await runAndApply(ind.code, ind.id, {
          silent: true,
          openResults: false,
        });
      }
    } finally {
      rerunInFlight = false;
    }
  }, 400);
}
