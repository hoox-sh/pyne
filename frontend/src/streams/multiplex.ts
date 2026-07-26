import type { Bar } from '../store/types';
import {
  appendBar,
  setLive,
  store,
  setStore,
  setStatus,
  appendLog,
} from '../store';
import { getManager } from '../chart/ChartHost';
import { runAndApply } from '../indicators/runner';
import {
  getStream,
  listStreams,
  defaultStreamForSource,
  type StreamPlugin,
} from './catalog';

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
    return;
  }

  setStore('live', 'streamId', id);
  setLive(true);
  setStore('stream', 'status', 'connected');
  appendLog('info', `Live start · ${stream.name} · ${symbol} ${interval}`, 'stream');

  const lastBar = store.bars.length ? store.bars[store.bars.length - 1] : null;

  const stop = stream.start({
    symbol,
    interval,
    lastBar,
    onBar: (bar: Bar) => {
      appendBar(bar);
      const manager = getManager();
      if (manager) manager.appendBar(bar);
      scheduleRerun();
    },
    onStatus: (s) => {
      if (s.state === 'open') {
        setStore('stream', 'status', 'connected');
        appendLog('ok', `Stream open${s.detail ? ` · ${s.detail}` : ''}`, 'stream');
      } else if (s.state === 'closed') {
        setStore('stream', 'status', 'disconnected');
        appendLog('warn', 'Stream closed', 'stream');
      }
    },
    onError: (e) => {
      appendLog('error', e.message || 'Stream error', 'stream');
      setStore('stream', 'status', 'error');
      setStatus('error', `Live error: ${e.message}`);
      stopLive();
    },
  });

  currentStop = stop;
}

export function stopLive() {
  if (currentStop) {
    currentStop();
    currentStop = null;
  }
  if (store.live.active) {
    appendLog('info', 'Live stopped', 'stream');
  }
  setLive(false);
  setStore('stream', 'status', 'disconnected');
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
