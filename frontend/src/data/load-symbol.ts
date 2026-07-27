import { loadBars, setStatus, store } from '../store';
import { getManager, setDataToChart } from '../chart/manager-access';
import { getSource } from '../sources/catalog';
import { getUploadedFileName } from '../sources/upload-store';

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
    return false;
  }

  const label =
    sourceId === 'csv-upload' && getUploadedFileName()
      ? getUploadedFileName()!
      : `${sym} ${interval}`;

  setStatus('loading', `Loading ${label} via ${source.name}…`);
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
      setDataToChart(normalized);
      manager.fitContent();
    }
    setStatus('ready', `Loaded ${normalized.length} bars · ${source.name}`);
    return true;
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error('Load failed:', err);
    setStatus('error', `Load failed: ${msg}`);
    return false;
  }
}
