import { store, addIndicator, addPane, setStatus } from '../store';
import { getManager } from '../chart/ChartHost';
import { PLOT_PALETTE } from '../chart/series-factory';

export interface RunResult {
  status: 'success' | 'error';
  plots: (number | null)[];
  series: Record<string, (number | null)[]>;
  events: any[];
  error?: string;
  meta?: { overlay?: boolean; script_name?: string; ms?: number };
}

export async function runScript(script: string): Promise<RunResult> {
  const endpoint = store.endpoint;
  setStatus('running', 'Executing Pine Script…');
  const t0 = performance.now();
  try {
    const res = await fetch(`${endpoint}/run?mode=interpret`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script, data: store.bars }),
      signal: AbortSignal.timeout(30_000),
    });
    const payload = await res.json().catch(() => ({ status: 'error', message: 'invalid JSON' }));
    if (!res.ok || payload.status === 'error') {
      setStatus('error', payload.message || `HTTP ${res.status}`);
      return { status: 'error', plots: [], series: {}, events: [], error: payload.message || `HTTP ${res.status}`, meta: { ms: performance.now() - t0 } };
    }
    const ms = performance.now() - t0;
    setStatus('ready', `Completed in ${ms.toFixed(0)}ms`);
    return {
      status: 'success',
      plots: payload.plots || [],
      series: payload.series || {},
      events: payload.events || [],
      meta: { ...(payload.meta || {}), ms, overlay: payload.meta?.overlay ?? true, script_name: payload.meta?.script_name || 'plot' },
    };
  } catch (err: any) {
    setStatus('error', err.message);
    return { status: 'error', plots: [], series: {}, events: [], error: err.message, meta: { ms: performance.now() - t0 } };
  }
}

/**
 * Run a Pine Script and apply results to the chart.
 * @param script - Pine Script source code
 * @param indicatorId - If provided, an existing indicator ID to update.
 *                     If undefined, a new indicator is created automatically.
 */
export async function runAndApply(script: string, indicatorId?: string): Promise<RunResult> {
  const result = await runScript(script);
  if (result.status === 'error') return result;

  const manager = getManager();
  if (!manager) return result;

  const overlay = result.meta?.overlay !== false;
  const paneId = overlay ? 'price' : 'indicator';
  const scriptName = result.meta?.script_name || 'Indicator';

  // Create indicator pane if needed (non-overlay scripts)
  if (!overlay && !manager.getPane('indicator')) {
    addPane('indicator', scriptName);
    manager.createPane('indicator', 'indicator', scriptName, 120);
    manager.syncTimeScales();
  }

  // Clear previous overlays on this pane
  manager.removeOverlays(paneId);

  const ohlcvTimes = store.bars.map((b) => b.time);

  // Apply primary plots array
  if (result.plots.length) {
    const data = result.plots
      .map((v, i) => (v != null && typeof v === 'number' && !isNaN(v) && ohlcvTimes[i] ? { time: ohlcvTimes[i], value: v } : null))
      .filter(Boolean) as { time: number; value: number }[];
    if (data.length) manager.addOverlayLine(paneId, scriptName, data);
  }

  // Apply named series (e.g. ta.macd returns multiple series)
  for (const [k, arr] of Object.entries(result.series)) {
    if (k.startsWith('__')) continue;
    const data = (arr as (number | null)[])
      .map((v, i) => (v != null && typeof v === 'number' && !isNaN(v) && ohlcvTimes[i] ? { time: ohlcvTimes[i], value: v } : null))
      .filter(Boolean) as { time: number; value: number }[];
    if (data.length) manager.addOverlayLine(paneId, k, data);
  }

  // Track indicator in store
  if (indicatorId === undefined) {
    // New indicator — create entry
    const plots: Record<string, { color: string }> = {};
    plots[scriptName] = { color: PLOT_PALETTE[0] };
    for (const k of Object.keys(result.series)) {
      plots[k] = { color: PLOT_PALETTE[Object.keys(plots).length % PLOT_PALETTE.length] };
    }
    addIndicator(scriptName, script, paneId, plots);
  }
  // If indicatorId is defined, the indicator entry already exists — don't duplicate

  return result;
}
