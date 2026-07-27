import {
  store,
  setStore,
  addIndicator,
  addPane,
  setStatus,
  setLastRun,
  appendLog,
  recordRunLatency,
  setTelemetryPlane,
  setTelemetryState,
} from '../store';
import { getManager } from '../chart/manager-access';
import { PLOT_PALETTE } from '../chart/series-factory';
import { normalizeStrategyEvents, eventsToMarkers, buildEquityCurve } from '../results/events';
import { buildStrategyReport } from '../results/strategy';
import { getActiveDrawingLayer } from '../chart/drawing-layer';
import { getActiveEngine, getActiveEngineConfig } from '../plugins/active';
import type { RunResult as EngineRunResult } from '../plugins/types';
import { classifyTransport } from '../ui/telemetry';

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
    const transport = classifyTransport('engine', engine.id, engine.capabilities);
    const mode = String(config?.mode || 'interpret');
    setTelemetryPlane('engine', {
      id: engine.id,
      name: engine.name,
      transport,
      state: 'connecting',
      detail: mode,
      error: null,
    });
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
    const runTransport =
      result.meta?.transport === 'ws'
        ? 'ws'
        : result.meta?.transport === 'local'
          ? 'local'
          : transport;
    recordRunLatency(ms);
    if (result.status === 'error') {
      const msg = result.error || 'Engine error';
      setTelemetryState('engine', 'error', {
        error: msg,
        latencyMs: ms,
        detail: mode,
        transport: runTransport,
      });
      if (!silent) setStatus('error', msg);
      else appendLog('error', `Live re-run failed: ${msg}`, 'live');
      return {
        ...result,
        series: result.series || {},
        events: result.events || [],
        meta: { ...result.meta, ms },
      };
    }
    setTelemetryState('engine', 'open', {
      latencyMs: ms,
      detail: `${mode} · ${runTransport} · ${ms.toFixed(0)}ms`,
      error: null,
      transport: runTransport,
    });
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
    const ms = performance.now() - t0;
    recordRunLatency(ms);
    setTelemetryState('engine', 'error', { error: msg, latencyMs: ms });
    if (!silent) setStatus('error', msg);
    else appendLog('error', `Live re-run: ${msg}`, 'live');
    return {
      status: 'error',
      plots: [],
      series: {},
      events: [],
      error: msg,
      meta: { ms },
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

  // Pine: indicator defaults overlay=false; strategy defaults overlay=true.
  // Explicit false must never be coerced to true.
  const overlayFlag = result.meta?.overlay;
  const overlay = overlayFlag !== false && overlayFlag !== 0 && overlayFlag !== 'false';
  const existing = indicatorId
    ? store.scripts.find((s) => s.id === indicatorId)
    : undefined;
  const scriptName = String(result.meta?.script_name || existing?.name || 'Indicator');
  let paneId = 'price';
  if (!overlay) {
    paneId =
      existing?.paneId && existing.paneId !== 'price' ? existing.paneId : 'indicator';
    if (!manager.getPane(paneId)) {
      // Keep store panes list in sync
      if (!store.panes.some((p) => p.id === 'indicator')) {
        addPane('indicator', scriptName);
      }
      manager.createPane('indicator', 'indicator', scriptName, 140);
      paneId = 'indicator';
      manager.syncTimeScales();
    } else {
      try {
        manager.setLabel(paneId, scriptName);
      } catch {
        /* ignore */
      }
    }
  }

  const ohlcvTimes = store.bars.map((b) => b.time);
  const plotMeta = (result.meta?.plot_meta || {}) as Record<
    string,
    { title?: string; color?: string | null; linewidth?: number; index?: number }
  >;
  const seriesEntries = Object.entries(result.series || {}).filter(
    ([k]) => !k.startsWith('__') && !k.startsWith('_'),
  );

  const toLineData = (arr: (number | null)[]) =>
    arr
      .map((v, i) => {
        const t = ohlcvTimes[i];
        if (v == null || typeof v !== 'number' || isNaN(v)) return null;
        if (t == null || !Number.isFinite(t)) return null;
        return { time: t as number, value: v };
      })
      .filter(Boolean) as { time: number; value: number }[];

  // Stable overlay sync: update-in-place when keys match (no remove→blank→add flash)
  const overlayLines: Array<{
    name: string;
    data: { time: number; value: number }[];
    color?: string;
  }> = [];
  if (seriesEntries.length > 0) {
    let colorIdx = 0;
    for (const [k, arr] of seriesEntries) {
      const data = toLineData(arr as (number | null)[]);
      if (!data.length) continue;
      const meta = plotMeta[k];
      const color =
        (meta?.color && String(meta.color)) ||
        PLOT_PALETTE[colorIdx % PLOT_PALETTE.length];
      colorIdx += 1;
      overlayLines.push({ name: k, data, color });
    }
  } else if (result.plots.length) {
    const data = toLineData(result.plots as (number | null)[]);
    if (data.length) overlayLines.push({ name: scriptName, data, color: PLOT_PALETTE[0] });
  }
  manager.syncOverlayLines(paneId, overlayLines);

  // Non-overlay scripts must not leave series on the price pane
  if (!overlay && paneId !== 'price') {
    const pricePane = manager.getPane('price');
    if (pricePane) {
      for (const line of overlayLines) {
        const key = `overlay_${line.name}`;
        if (pricePane.series[key]) {
          try {
            pricePane.chart.removeSeries(pricePane.series[key]);
          } catch {
            /* ignore */
          }
          delete pricePane.series[key];
        }
      }
    }
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
          `Strategy: ${report.stats.trades} trades · net ${report.stats.totalPnl >= 0 ? '+' : ''}${report.stats.totalPnl.toFixed(2)} · ${markers.length} markers`,
          'strategy',
        );
      }
    } else {
      // Live silent re-runs: skip hide to avoid equity pane thrash
      if (!silent) {
        manager.hideEquityPane();
        if (markers.length) {
          appendLog('ok', `Strategy events: ${events.length} · ${markers.length} markers`, 'strategy');
        }
      }
    }
  } else if (!silent) {
    manager.hideEquityPane();
  }

  // Pine drawings: atomic replace (no clear→empty→set flash)
  const drawings = (result as RunResult & { drawings?: unknown[] }).drawings;
  const layer = getActiveDrawingLayer();
  if (drawings?.length) {
    layer?.setScriptDrawings(drawings);
    if (!silent) {
      appendLog('ok', `Pine drawings: ${drawings.length} object(s)`, 'drawings');
    }
  } else if (!silent) {
    // Only clear on interactive full runs when engine returned none
    layer?.clearScriptDrawings();
  }

  if (indicatorId === undefined) {
    const plots: Record<string, { color: string }> = {};
    let colorIdx = 0;
    if (seriesEntries.length) {
      for (const [k] of seriesEntries) {
        const meta = plotMeta[k];
        plots[k] = {
          color:
            (meta?.color && String(meta.color)) ||
            PLOT_PALETTE[colorIdx % PLOT_PALETTE.length],
        };
        colorIdx += 1;
      }
    } else {
      plots[scriptName] = { color: PLOT_PALETTE[0] };
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
