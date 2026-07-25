import type { Bar } from '../store/types';
import type { StreamPlugin } from './binance';
import { binanceStream } from './binance';
import { appendBar, setLive, store } from '../store';
import { getManager } from '../chart/ChartHost';
import { runScript } from '../indicators/runner';

const STREAMS: StreamPlugin[] = [binanceStream];

let currentStop: (() => void) | null = null;
let rerunTimer: ReturnType<typeof setTimeout> | null = null;

export function getAvailableStreams(): StreamPlugin[] {
  return STREAMS;
}

export function startLive(streamId: string, symbol: string, interval: string) {
  stopLive();
  const stream = STREAMS.find((s) => s.id === streamId);
  if (!stream) return;

  // Set live active BEFORE starting stream to avoid race condition
  // where first bar arrives before live.active is true
  setLive(true);

  const stop = stream.start({
    symbol,
    interval,
    onBar: (bar: Bar) => {
      appendBar(bar);
      const manager = getManager();
      if (manager) manager.appendBar(bar);
      // live.active is already true at this point (set above)
      scheduleRerun();
    },
    onStatus: (s) => console.log('[stream]', s.state),
    onError: (e) => { console.error('[stream]', e); stopLive(); },
  });

  currentStop = stop;
}

export function stopLive() {
  if (currentStop) { currentStop(); currentStop = null; }
  setLive(false);
  if (rerunTimer) { clearTimeout(rerunTimer); rerunTimer = null; }
}

function scheduleRerun() {
  if (rerunTimer) return;
  rerunTimer = setTimeout(async () => {
    rerunTimer = null;
    for (const ind of store.scripts) {
      if (!ind.visible) continue;
      await runScript(ind.code);
    }
  }, 300);
}
