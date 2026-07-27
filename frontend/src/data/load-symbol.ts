import { loadBars, setStatus, store, setTelemetryPlane, setTelemetryState } from '../store';
import { getManager, setDataToChart } from '../chart/manager-access';
import { getSource } from '../sources/catalog';
import { getUploadedFileName } from '../sources/upload-store';
import { classifyTransport } from '../ui/telemetry';
import { defaultStreamForSource } from '../streams/catalog';

/** Fetch OHLCV via the active historical source and push into chart + store. */
export async function loadSymbolData(
  symbol: string = store.symbol,
  interval: string = store.interval,
  sourceId: string = store.source,
): Promise<boolean> {
  const sym = symbol.toUpperCase();
  const source = getSource(sourceId);
  if (!source) {
    setStatus('error', `Unknown source: ${sourceId}`);
    setTelemetryState('source', 'error', { error: `Unknown source: ${sourceId}` });
    return false;
  }

  const label =
    sourceId === 'csv-upload' && getUploadedFileName()
      ? getUploadedFileName()!
      : `${sym} ${interval}`;

  const transport = classifyTransport('source', source.id, source.capabilities);
  setTelemetryPlane('source', {
    id: source.id,
    name: source.name,
    transport,
    state: 'connecting',
    detail: label,
    error: null,
  });
  setStatus('loading', `Loading ${label} via ${source.name}…`);
  const t0 = performance.now();
  try {
    const bars = await source.fetchHistorical({
      symbol: sym,
      interval,
      config: {},
    });
    if (!bars?.length) {
      throw new Error('Source returned no bars');
    }

    // Normalize times to seconds (defensive)
    const normalized = bars.map((b) => ({
      ...b,
      time: b.time > 1e12 ? Math.floor(b.time / 1000) : b.time,
    }));

    const exchange =
      sourceId === 'binance-rest'
        ? 'binance'
        : sourceId === 'okx-rest'
          ? 'okx'
          : sourceId === 'bybit-rest'
            ? 'bybit'
            : sourceId === 'coinbase-rest'
              ? 'coinbase'
              : sourceId === 'mock-walk'
                ? 'mock'
                : sourceId === 'csv-upload'
                  ? 'upload'
                  : store.exchange;

    loadBars(normalized, sym, interval, exchange);
    const manager = getManager();
    if (manager) {
      setDataToChart(normalized, { fit: true });
    }
    const ms = performance.now() - t0;
    setTelemetryState('source', 'open', {
      latencyMs: ms,
      detail: `${normalized.length} bars · ${label}`,
      error: null,
    });
    setStatus('ready', `Loaded ${normalized.length} bars · ${source.name}`);

    // Optional WSS-first: auto-start paired live stream after successful Load
    if (store.live.preferAfterLoad && !store.live.active) {
      const streamId = store.live.streamId || defaultStreamForSource(sourceId);
      try {
        const { startLive } = await import('../streams/multiplex');
        startLive(streamId, sym, interval);
      } catch {
        /* ignore auto-live failures */
      }
    }
    return true;
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error('Load failed:', err);
    setTelemetryState('source', 'error', {
      error: msg,
      latencyMs: performance.now() - t0,
    });
    setStatus('error', `Load failed: ${msg}`);
    return false;
  }
}
