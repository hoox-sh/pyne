import { store, setStore, addIndicator, addPane, setStatus, setLastRun, appendLog } from '../store';
import { getManager } from '../chart/ChartHost';
import { PLOT_PALETTE } from '../chart/series-factory';
import { normalizeStrategyEvents, eventsToMarkers, buildEquityCurve } from '../results/events';
import { buildStrategyReport } from '../results/strategy';
import { getActiveDrawingLayer } from '../chart/drawing-layer';
import { getActiveEngine, getActiveEngineConfig } from '../plugins/active';
import type { RunResult as EngineRunResult } from '../plugins/types';

export type RunResult = EngineRunResult & {
  series: Record<string, (number | null)[]>;
};

export interface RunOptions {
  /** Quiet status bar / fewer log lines (live re-runs) */
  silent?: boolean;
  /** Open Results drawer after run (default true when not silent) */
  openResults?: boolean;
}

export async function runScript(script: string, opts: RunOptions = {}): Promise<RunResult> {
  const silent = !!opts.silent;
  if (!silent) setStatus('running', 'Executing Pine Script…');
  const t0 = performance.now();
  try {
    const engine = getActiveEngine();
    const config = getActiveEngineConfig();
    const timeoutMs = silent
      ? 45_000
      : Math.min(180_000, Math.max(60_000, 30_000 + (store.bars?.length || 0) * 80));
    const result = await engine.run({
      script,
      bars: store.bars,
      config,
      signal: AbortSignal.timeout(timeoutMs),
    });
    const ms = result.meta?.ms ?? performance.now() - t0;
    if (result.status === 'error') {
      const msg = result.error || 'Engine error';
      if (!silent) setStatus('error', msg);
      else appendLog('error', `Live re-run failed: ${msg}`, 'live');
      return {
        ...result,
        series: result.series || {},
        events: result.events || [],
        meta: { ...result.meta, ms },
      };
    }
    if (!silent) setStatus('ready', `Completed in ${ms.toFixed(0)}ms`);
    return {
      ...result,
      series: result.series || {},
      events: result.events || [],
      meta: {
        ...result.meta,
        ms,
        overlay: result.meta?.overlay ?? true,
        script_name: result.meta?.script_name || 'plot',
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
  manager.clearTradeMarkers();
  // Clear previous Pine drawings; re-apply after plots if present
  getActiveDrawingLayer()?.clearScriptDrawings();

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

  // Strategy: markers on price pane + equity curve
  const events = result.events || [];
  if (events.length) {
    const normalized = normalizeStrategyEvents(events, {
      bars: store.bars,
      includeOrders: false,
    });
    const markers = eventsToMarkers(normalized);
    manager.setTradeMarkers(markers);

    const report = buildStrategyReport(events, store.bars);
    if (report.trades.length) {
      const equity = buildEquityCurve(report.trades, 10_000);
      manager.setEquityCurve(equity);
      if (!silent) {
        appendLog(
          'ok',
          `Strategy: ${report.stats.trades} trades · net ${report.stats.totalPnl >= 0 ? '+' : ''}${report.stats.totalPnl.toFixed(2)}`,
          'strategy',
        );
      }
    } else {
      manager.hideEquityPane();
    }
  } else {
    manager.hideEquityPane();
  }

  // Pine line.new / label.new / box.new from interpret runtime
  const drawings = (result as RunResult & { drawings?: unknown[] }).drawings;
  if (drawings?.length) {
    getActiveDrawingLayer()?.setScriptDrawings(drawings);
    if (!silent) {
      appendLog('ok', `Pine drawings: ${drawings.length} object(s)`, 'drawings');
    }
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
