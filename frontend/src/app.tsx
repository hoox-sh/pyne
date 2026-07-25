import { Component, createSignal, onMount } from 'solid-js';
import { Topbar } from './ui/Topbar';
import { StatusBar } from './ui/StatusBar';
import { ChartHost } from './chart/ChartHost';
import { TabbedEditor } from './editor/tabbed-editor';
import { IndicatorPanel } from './indicators/IndicatorPanel';
import { SettingsDialog } from './ui/SettingsDialog';
import { runAndApply } from './indicators/runner';
import { store, setStore, persist } from './store';

export const App: Component = () => {
  const [editorOpen, setEditorOpen] = createSignal(true);
  const [indicatorPanelOpen, setIndicatorPanelOpen] = createSignal(false);
  const [settingsOpen, setSettingsOpen] = createSignal(false);

  // Shared mutable ref — PineEditor populates getDoc/setDoc on mount
  const editorRef: { getDoc: () => string; setDoc?: (doc: string) => void } = {
    getDoc: () => '',
  };

  onMount(() => {
    document.documentElement.setAttribute('data-theme', store.theme);
  });

  return (
    <div class="h-screen flex flex-col bg-bg-base text-text overflow-hidden">
      <Topbar
        onToggleEditor={() => setEditorOpen((o) => !o)}
        onToggleIndicatorPanel={() => {
          const next = !indicatorPanelOpen();
          setIndicatorPanelOpen(next);
          setStore('indicatorPanel', 'open', next);
          persist();
        }}
        onOpenSettings={() => setSettingsOpen(true)}
        editorRef={editorRef}
      />

      <div class="flex-1 flex min-h-0 overflow-hidden">
        {editorOpen() && (
          <div class="w-[460px] min-w-[280px] bg-bg-panel border-r border-border flex flex-col flex-shrink-0 overflow-hidden">
            <div class="flex-1 min-h-0 overflow-hidden">
              <TabbedEditor
                onRun={(doc) => {
                  if (doc?.trim()) runAndApply(doc);
                }}
                editorRef={editorRef}
              />
            </div>
          </div>
        )}

        <div class="flex-1 flex min-w-0 min-h-0 overflow-hidden">
          <ChartHost />
          <IndicatorPanel />
        </div>
      </div>

      <StatusBar />

      <SettingsDialog open={settingsOpen()} onClose={() => setSettingsOpen(false)} />
    </div>
  );
};
