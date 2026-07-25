import { Component, For, createSignal } from 'solid-js';
import { store, setStore, loadBars, toggleTheme, persist, setLive } from '../store';
import { getManager, setDataToChart } from '../chart/ChartHost';
import { runAndApply } from '../indicators/runner';
import { startLive, stopLive } from '../streams/multiplex';
import { setStatus } from '../store';

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];
const INTERVALS = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'];

export const Topbar: Component<{
  onToggleEditor: () => void;
  onToggleIndicatorPanel: () => void;
  onOpenSettings: () => void;
  editorRef: { getDoc: () => string };
}> = (props) => {
  const [loading, setLoading] = createSignal(false);

  const loadHistorical = async () => {
    if (loading()) return;
    setLoading(true);
    setStatus('loading', `Loading ${store.symbol} ${store.interval}…`);
    try {
      const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=${store.symbol}&interval=${store.interval}&limit=500`);
      const raw = await res.json();
      const bars = raw.map((k: any[]) => ({
        time: Math.floor(k[0] / 1000),
        open: +k[1], high: +k[2], low: +k[3], close: +k[4], volume: +k[5],
      }));
      loadBars(bars, store.symbol, store.interval, store.exchange);
      const manager = getManager();
      if (manager) {
        setDataToChart(bars);
        manager.fitContent();
      }
      setStatus('ready', `Loaded ${bars.length} bars`);
    } catch (err: any) {
      console.error('Load failed:', err);
      setStatus('error', `Load failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const onRun = async () => {
    const doc = props.editorRef.getDoc();
    if (!doc?.trim()) return;
    await runAndApply(doc);
  };

  const toggleLive = () => {
    const next = !store.live.active;
    if (next) {
      startLive(store.live.streamId, store.symbol, store.interval);
    } else {
      stopLive();
    }
  };

  return (
    <header class="flex items-center gap-3 px-2.5 py-1.5 bg-bg-panel border-b border-border flex-shrink-0 min-h-[40px]">
      <div class="font-semibold text-sm text-text mr-2">SuperChart Lite</div>

      <label class="text-[11px] text-text-dim uppercase tracking-wider">Symbol</label>
      <select
        class="bg-bg-elev text-text border border-border rounded px-2 py-1 text-xs outline-none focus:border-accent min-w-[80px]"
        value={store.symbol}
        onChange={(e) => { setStore('symbol', e.currentTarget.value); persist(); }}
      >
        <For each={SYMBOLS}>{(s) => <option value={s}>{s}</option>}</For>
      </select>

      <label class="text-[11px] text-text-dim uppercase tracking-wider">Interval</label>
      <select
        class="bg-bg-elev text-text border border-border rounded px-2 py-1 text-xs outline-none focus:border-accent min-w-[60px]"
        value={store.interval}
        onChange={(e) => { setStore('interval', e.currentTarget.value); persist(); }}
      >
        <For each={INTERVALS}>{(i) => <option value={i}>{i}</option>}</For>
      </select>

      <button
        class={`bg-bg-elev text-text border border-border rounded px-2.5 py-1 text-xs cursor-pointer hover:bg-bg-hover ${loading() ? 'opacity-50' : ''}`}
        onClick={loadHistorical}
        disabled={loading()}
      >
        {loading() ? 'Loading…' : 'Load'}
      </button>

      <button
        class={`bg-bg-elev text-text border border-border rounded px-2.5 py-1 text-xs cursor-pointer hover:bg-bg-hover flex items-center gap-1.5 ${store.live.active ? 'border-green text-green' : ''}`}
        onClick={toggleLive}
      >
        <span class={`inline-block w-2 h-2 rounded-full ${store.live.active ? 'bg-green animate-pulse' : 'bg-text-faint'}`} />
        Live
      </button>

      <div class="flex-1" />

      <button class="bg-accent text-white border border-accent rounded px-2.5 py-1 text-xs cursor-pointer font-medium hover:bg-accent-hover" onClick={onRun}>
        ▶ Run
      </button>

      <button class="text-text-dim hover:text-text text-xs cursor-pointer bg-transparent border-none px-1.5" onClick={props.onToggleEditor}>
        📝 Editor
      </button>

      <button class="text-text-dim hover:text-text text-xs cursor-pointer bg-transparent border-none px-1.5" onClick={props.onToggleIndicatorPanel}>
        📊 Indicators
      </button>

      <button class="text-text-dim hover:text-text text-xs cursor-pointer bg-transparent border-none px-1.5" onClick={props.onOpenSettings}>
        ⚙
      </button>

      <button class="text-text-dim hover:text-text text-xs cursor-pointer bg-transparent border-none px-1.5" onClick={toggleTheme}>
        {store.theme === 'dark' ? '☀' : '🌙'}
      </button>
    </header>
  );
};
