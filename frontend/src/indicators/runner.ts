import { store, setStore, addIndicator, addPane, setStatus, setLastRun, appendLog } from '../store';
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

export interface RunOptions {
  /** Quiet status bar / fewer log lines (live re-runs) */
  silent?: boolean;
  /** Open Results drawer after run (default true when not silent) */
  openResults?: boolean;
}

export async function runScript(script: string, opts: RunOptions = {}): Promise<RunResult> {
  const silent = !!opts.silent;
  const endpoint = store.endpoint.replace(/\/$/, '');
  if (!silent) setStatus('running', 'Executing Pine Script…');
  const t0 = performance.now();
  try {
    const res = await fetch(`${endpoint}/run?mode=interpret`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script, data: store.bars }),
      signal: AbortSignal.timeout(silent ? 20_000 : 30_000),
    });
    const payload = await res.json().catch(() => ({ status: 'error', message: 'invalid JSON' }));
    if (!res.ok || payload.status === 'error') {
      const msg = payload.message || `HTTP ${res.status}`;
      if (!silent) setStatus('error', msg);
      else appendLog('error', `Live re-run failed: ${msg}`, 'live');
      return {
        status: 'error',
        plots: [],
        series: {},
        events: [],
        error: msg,
        meta: { ms: performance.now() - t0 },
      };
    }
    const ms = performance.now() - t0;
    if (!silent) setStatus('ready', `Completed in ${ms.toFixed(0)}ms`);
    return {
      status: 'success',
      plots: payload.plots || [],
      series: payload.series || {},
      events: payload.events || [],
      meta: {
        ...(payload.meta || {}),
        ms,
        overlay: payload.meta?.overlay ?? true,
        script_name: payload.meta?.script_name || 'plot',
      },
    };
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (!silent) setStatus('error', msg);
    else appendLog('error', `Live re-run: ${msg}`, 'live');
    return {
      status: 'error',
      plots: [],
      series: {},
      events: [],
      error: msg,
      meta: { ms: performance.now() - t0 },
    };
  }
}

/**
 * Run a Pine Script and apply results to the chart.
 * @param script - Pine Script source code
 * @param indicatorId - If provided, an existing indicator ID to update.
 * @param opts - silent / openResults for live path
 */
export async function runAndApply(
  script: string,
  indicatorId?: string,
  opts: RunOptions = {},
): Promise<RunResult> {
  const silent = !!opts.silent;
  const openResults = opts.openResults ?? !silent;

  const result = await runScript(script, opts);
  setLastRun(result);
  if (openResults) {
    setStore('resultsPanel', 'open', true);
  }
  if (result.status === 'error') return result;

  const manager = getManager();
  if (!manager) return result;

  const overlay = result.meta?.overlay !== false;
  const paneId = overlay ? 'price' : 'indicator';
  const scriptName = result.meta?.script_name || 'Indicator';

  if (!overlay && !manager.getPane('indicator')) {
    addPane('indicator', scriptName);
    manager.createPane('indicator', 'indicator', scriptName, 120);
    manager.syncTimeScales();
  }

  manager.removeOverlays(paneId);

  const ohlcvTimes = store.bars.map((b) => b.time);

  if (result.plots.length) {
    const data = result.plots
      .map((v, i) =>
        v != null && typeof v === 'number' && !isNaN(v) && ohlcvTimes[i]
          ? { time: ohlcvTimes[i], value: v }
          : null,
      )
      .filter(Boolean) as { time: number; value: number }[];
    if (data.length) manager.addOverlayLine(paneId, scriptName, data);
  }

  for (const [k, arr] of Object.entries(result.series)) {
    if (k.startsWith('__')) continue;
    const data = (arr as (number | null)[])
      .map((v, i) =>
        v != null && typeof v === 'number' && !isNaN(v) && ohlcvTimes[i]
          ? { time: ohlcvTimes[i], value: v }
          : null,
      )
      .filter(Boolean) as { time: number; value: number }[];
    if (data.length) manager.addOverlayLine(paneId, k, data);
  }

  if (indicatorId === undefined) {
    const plots: Record<string, { color: string }> = {};
    plots[scriptName] = { color: PLOT_PALETTE[0] };
    for (const k of Object.keys(result.series)) {
      if (k.startsWith('__')) continue;
      plots[k] = { color: PLOT_PALETTE[Object.keys(plots).length % PLOT_PALETTE.length] };
    }
    addIndicator(scriptName, script, paneId, plots);
  }

  return result;
}

/** Probe Pro API health at current endpoint. */
export async function probeEndpoint(endpoint?: string): Promise<{ ok: boolean; message: string }> {
  const base = (endpoint || store.endpoint).replace(/\/$/, '');
  try {
    const res = await fetch(`${base}/`, {
      method: 'GET',
      signal: AbortSignal.timeout(8_000),
    });
    if (!res.ok) return { ok: false, message: `HTTP ${res.status}` };
    const text = await res.text();
    let detail = `HTTP ${res.status}`;
    try {
      const j = JSON.parse(text);
      if (j.endpoints || j.status) detail = 'Pro API reachable';
    } catch {
      /* plain text ok */
    }
    return { ok: true, message: detail };
  } catch (e: unknown) {
    return { ok: false, message: e instanceof Error ? e.message : String(e) };
  }
}
