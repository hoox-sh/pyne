import { Component, For, createSignal, batch, onCleanup, onMount } from 'solid-js';
import { PineEditor } from './PineEditor';
import { store, loadEditorDoc, saveEditorDoc } from '../store';
import { saveDraft, loadDraft, writeScript } from '../storage/service';
import { setStatus } from '../store';

interface Tab {
  id: string;
  name: string;
  doc: string;
  dirty: boolean;
  /** Bound library script id when loaded/saved */
  libraryId?: string;
}

const DEMOS: Record<string, string> = {
  'rsi-overlay': `//@version=5
strategy("RSI Overlay", overlay=true)
length = input.int(14, "RSI Length", minval=2, maxval=100)
rsi = ta.rsi(close, length)
plot(rsi * 0.01, "RSI scaled", color=color.new(color.purple, 50))
`,
  macd: `//@version=5
indicator("MACD", overlay=false)
fastLen   = input.int(12, "Fast Length")
slowLen   = input.int(26, "Slow Length")
signalLen = input.int(9,  "Signal Length")
[macdLine, signalLine, histLine] = ta.macd(close, fastLen, slowLen, signalLen)
plot(macdLine, "MACD", color=color.blue)
plot(signalLine, "Signal", color=color.orange)
`,
};

let tabIdCounter = 0;
const newTab = (name: string, doc: string, libraryId?: string): Tab => ({
  id: `tab_${Date.now()}_${++tabIdCounter}`,
  name,
  doc,
  dirty: false,
  libraryId,
});

function initialDoc(): string {
  const shared = loadEditorDoc();
  if (shared.trim()) return shared;
  return store.scripts[0]?.code || DEMOS['rsi-overlay'];
}

interface Props {
  onRun?: (doc: string) => void;
  onDocChange?: (doc: string) => void;
  editorRef?: {
    getDoc: () => string;
    setDoc?: (doc: string) => void;
    /** Load external library content into active tab */
    loadLibraryDoc?: (doc: string, name?: string, libraryId?: string) => void;
  };
}

export const TabbedEditor: Component<Props> = (props) => {
  const [tabs, setTabs] = createSignal<Tab[]>([newTab('Script 1', initialDoc())]);
  const [activeTab, setActiveTab] = createSignal(0);
  const [saving, setSaving] = createSignal(false);

  let draftTimer: ReturnType<typeof setTimeout> | null = null;

  const scheduleDraft = (doc: string, name?: string) => {
    saveEditorDoc(doc);
    if (draftTimer) clearTimeout(draftTimer);
    draftTimer = setTimeout(() => {
      void saveDraft(doc, name).catch(() => {});
    }, 400);
  };

  onMount(() => {
    // Prefer storage draft over empty first paint (async)
    void loadDraft().then((d) => {
      if (!d?.content?.trim()) return;
      const current = props.editorRef?.getDoc?.() || tabs()[0]?.doc || '';
      // Don't clobber if user already typed or initial had content from localStorage
      if (current.trim() && current !== DEMOS['rsi-overlay']) return;
      if (loadEditorDoc().trim()) return;
      setTabs((t) => t.map((tab, i) => (i === 0 ? { ...tab, doc: d.content, name: d.name || tab.name } : tab)));
      props.editorRef?.setDoc?.(d.content);
    });

    if (props.editorRef) {
      props.editorRef.loadLibraryDoc = (doc: string, name?: string, libraryId?: string) => {
        const idx = activeTab();
        setTabs((t) =>
          t.map((tab, i) =>
            i === idx
              ? {
                  ...tab,
                  doc,
                  name: name || tab.name,
                  dirty: false,
                  libraryId,
                }
              : tab,
          ),
        );
        props.editorRef?.setDoc?.(doc);
        scheduleDraft(doc, name);
      };
    }
  });

  onCleanup(() => {
    if (draftTimer) clearTimeout(draftTimer);
  });

  const addTab = () => {
    const newIdx = tabs().length;
    setTabs((t) => [...t, newTab(`Script ${t.length + 1}`, '')]);
    setActiveTab(newIdx);
    if (props.editorRef?.setDoc) {
      props.editorRef.setDoc('');
    }
  };

  const closeTab = (idx: number) => {
    if (tabs().length <= 1) return;
    batch(() => {
      const newTabs = tabs().filter((_, i) => i !== idx);
      setTabs(newTabs);
      if (activeTab() >= newTabs.length) {
        setActiveTab(newTabs.length - 1);
      }
    });
    const newActiveIdx = Math.min(activeTab(), tabs().length - 1);
    if (props.editorRef?.setDoc) {
      props.editorRef.setDoc(tabs()[newActiveIdx]?.doc ?? '');
    }
  };

  const switchTab = (idx: number) => {
    if (props.editorRef?.getDoc) {
      const currentDoc = props.editorRef.getDoc();
      setTabs((t) =>
        t.map((tab, i) => (i === activeTab() ? { ...tab, doc: currentDoc } : tab)),
      );
    }
    setActiveTab(idx);
    if (props.editorRef?.setDoc) {
      props.editorRef.setDoc(tabs()[idx]?.doc ?? '');
    }
  };

  const onDocChange = (doc: string) => {
    setTabs((t) =>
      t.map((tab, i) => (i === activeTab() ? { ...tab, doc, dirty: true } : tab)),
    );
    props.onDocChange?.(doc);
    scheduleDraft(doc, tabs()[activeTab()]?.name);
  };

  const saveActiveToLibrary = async () => {
    const tab = tabs()[activeTab()];
    const doc = props.editorRef?.getDoc?.() || tab?.doc || '';
    if (!doc.trim()) {
      setStatus('error', 'Editor is empty');
      return;
    }
    const name = tab?.name || 'Script';
    setSaving(true);
    try {
      const meta = await writeScript({
        id: tab?.libraryId || `s_${Date.now().toString(36)}`,
        name,
        content: doc,
      });
      setTabs((t) =>
        t.map((tb, i) =>
          i === activeTab()
            ? { ...tb, dirty: false, libraryId: meta.id, name: meta.name }
            : tb,
        ),
      );
      setStatus('ready', `Saved "${meta.name}"`);
    } catch (e: unknown) {
      setStatus('error', e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div class="flex flex-col h-full min-h-0">
      <div class="flex items-stretch bg-bg-base border-b-2 border-border overflow-x-auto flex-shrink-0">
        <For each={tabs()}>
          {(tab, idx) => (
            <button
              class={`flex items-center gap-1.5 px-2.5 py-1 text-[11px] border-r-2 border-border-soft cursor-pointer whitespace-nowrap select-none ${
                idx() === activeTab()
                  ? 'bg-bg-panel text-text border-b-2 border-b-accent -mb-[2px]'
                  : 'text-text-dim hover:bg-bg-hover hover:text-text border-b-2 border-b-transparent'
              }`}
              onClick={() => switchTab(idx())}
            >
              {tab.dirty && <span class="inline-block w-1.5 h-1.5 rounded-full bg-orange" />}
              <span class="max-w-[140px] overflow-hidden text-ellipsis">{tab.name}</span>
              {tabs().length > 1 && (
                <span
                  class="text-text-faint hover:text-red text-sm px-0.5 hover:bg-bg-hover"
                  onClick={(e) => {
                    e.stopPropagation();
                    closeTab(idx());
                  }}
                >
                  ×
                </span>
              )}
            </button>
          )}
        </For>
        <button
          class="text-text-dim border-none bg-transparent px-2.5 cursor-pointer text-lg hover:text-accent hover:bg-bg-hover"
          onClick={addTab}
          title="New tab"
        >
          +
        </button>
        <div class="flex-1" />
        <button
          class="sc-btn sc-btn-ghost px-2 text-[10px] m-0.5 self-center"
          title={`Save to ${store.activePlugins?.storage || 'local'} library`}
          disabled={saving()}
          onClick={() => void saveActiveToLibrary()}
        >
          {saving() ? 'Saving…' : 'Save'}
        </button>
      </div>
      <div class="flex-1 min-h-0 overflow-hidden relative">
        <PineEditor
          initialDoc={tabs()[activeTab()]?.doc}
          onDocChange={onDocChange}
          onRun={() => {
            const doc = props.editorRef?.getDoc?.() || tabs()[activeTab()]?.doc;
            if (doc?.trim()) props.onRun?.(doc);
          }}
          editorRef={props.editorRef}
        />
      </div>
    </div>
  );
};
