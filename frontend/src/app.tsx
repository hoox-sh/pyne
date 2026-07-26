import { Component, createSignal, onMount, onCleanup, Show } from 'solid-js';
import { Topbar } from './ui/Topbar';
import { StatusBar } from './ui/StatusBar';
import { Watchlist } from './ui/Watchlist';
import { ChartHost } from './chart/ChartHost';
import { EditorPane } from './editor/EditorPane';
import { IndicatorPanel } from './indicators/IndicatorPanel';
import { SettingsDialog } from './ui/SettingsDialog';
import { ResultsPanel } from './ui/ResultsPanel';
import { SystemLogs } from './ui/SystemLogs';
import { PluginManager } from './ui/PluginManager';
import { runAndApply } from './indicators/runner';
import { restoreInstalledPlugins } from './plugins/loader';
import {
  store,
  setStore,
  persist,
  setEditorOpen,
  setEditorMode,
  setWatchlistOpen,
  saveEditorDoc,
  appendLog,
} from './store';
import {
  bridgeSubscribe,
  bridgePublish,
  writeSharedDoc,
  readSharedDoc,
} from './editor/editor-bridge';
import { loadSymbolData } from './data/load-symbol';

export const App: Component = () => {
  const [settingsOpen, setSettingsOpen] = createSignal(false);
  const [pluginsOpen, setPluginsOpen] = createSignal(false);
  const [catalogTick, setCatalogTick] = createSignal(0);

  // Shared mutable ref — PineEditor populates getDoc/setDoc on mount
  const editorRef: { getDoc: () => string; setDoc?: (doc: string) => void } = {
    getDoc: () => '',
  };

  onMount(() => {
    document.documentElement.setAttribute('data-theme', store.theme);
    document.title = 'AXIS';
    appendLog('ok', 'AXIS ready · void chrome · Lucide icons', 'boot');
    restoreInstalledPlugins()
      .then(() => setCatalogTick((n) => n + 1))
      .catch(() => {});
    // Auto-load default symbol so the chart is not an empty void on first paint
    if (!store.bars.length && store.source !== 'csv-upload') {
      void loadSymbolData(store.symbol, store.interval, store.source);
    }
    bridgePublish({ type: 'hello', role: 'main' });

    // If we reloaded while popout was open, stay in docked until popout says hello
    // (mode may be stale from localStorage)
    if (store.editor.mode === 'popout') {
      // keep mode; docked editor hidden until reattach or popout-closed
    }

    const unsub = bridgeSubscribe((msg) => {
      if (msg.type === 'popout-opened') {
        setEditorMode('popout');
      }
      if (msg.type === 'popout-closed') {
        setEditorMode('docked');
        setEditorOpen(true);
        // Restore doc from shared storage
        const doc = readSharedDoc();
        if (doc && editorRef.setDoc) editorRef.setDoc(doc);
      }
      if (msg.type === 'run') {
        // External editor requested a run — execute on main (has chart + bars)
        runAndApply(msg.doc).then((result) => {
          bridgePublish({
            type: 'run-status',
            status: result?.status || 'done',
            message: result?.error || store.statusMessage,
          });
        });
      }
      if (msg.type === 'doc') {
        saveEditorDoc(msg.doc);
        if (store.editor.mode === 'docked' && editorRef.setDoc) {
          if (msg.doc !== editorRef.getDoc()) editorRef.setDoc(msg.doc);
        }
      }
      if (msg.type === 'reattach') {
        setEditorMode('docked');
        setEditorOpen(true);
        const doc = readSharedDoc();
        if (doc && editorRef.setDoc) editorRef.setDoc(doc);
      }
      if (msg.type === 'hello' && msg.role === 'editor') {
        setEditorMode('popout');
        // Push current doc if main still has it
        const doc = editorRef.getDoc() || readSharedDoc();
        if (doc) writeSharedDoc(doc);
      }
    });

    onCleanup(unsub);
  });

  return (
    <div class="h-screen flex flex-col bg-bg-base text-text overflow-hidden">
      <Topbar
        onToggleEditor={() => {
          if (store.editor.mode === 'popout') {
            // Bring back docked
            setEditorMode('docked');
            setEditorOpen(true);
            return;
          }
          setEditorOpen(!store.editor.open);
        }}
        onToggleWatchlist={() => setWatchlistOpen(!store.watchlist.open)}
        onToggleIndicatorPanel={() => {
          const next = !store.indicatorPanel.open;
          setStore('indicatorPanel', 'open', next);
          persist();
        }}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenPlugins={() => setPluginsOpen(true)}
        catalogTick={catalogTick()}
        editorRef={editorRef}
      />

      <div class="flex-1 flex min-h-0 overflow-hidden">
        {/* Left: watchlist */}
        <Watchlist />

        {/* Center: chart + indicators */}
        <div class="flex-1 flex min-w-0 min-h-0 overflow-hidden bg-bg-base relative">
          <ChartHost />
          <IndicatorPanel />

          {/* Popout placeholder when editor is external */}
          <Show when={store.editor.mode === 'popout'}>
            <div class="absolute bottom-3 right-3 z-20 flex items-center gap-2 px-2.5 py-1.5 bg-bg-panel border-2 border-accent text-[11px] text-accent shadow-[0_4px_20px_rgba(0,0,0,0.45)]">
              <span>Editor detached</span>
              <button
                class="sc-btn sc-btn-primary px-2 py-0.5 text-[10px]"
                onClick={() => {
                  setEditorMode('docked');
                  setEditorOpen(true);
                  bridgePublish({ type: 'reattach' });
                  const doc = readSharedDoc();
                  if (doc && editorRef.setDoc) editorRef.setDoc(doc);
                }}
              >
                Reattach
              </button>
            </div>
          </Show>
        </div>

        {/* Right: editor (docked) */}
        <EditorPane
          editorRef={editorRef}
          onRun={(doc) => {
            if (doc?.trim()) runAndApply(doc);
          }}
        />
      </div>

      <ResultsPanel />
      <SystemLogs />
      <StatusBar />

      <SettingsDialog open={settingsOpen()} onClose={() => setSettingsOpen(false)} />
      <PluginManager
        open={pluginsOpen()}
        onClose={() => setPluginsOpen(false)}
        onChanged={() => setCatalogTick((n) => n + 1)}
      />
    </div>
  );
};
