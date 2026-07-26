import { Component, Show } from 'solid-js';
import { TabbedEditor } from './tabbed-editor';
import {
  store,
  setEditorOpen,
  setEditorMode,
  setEditorWidth,
  saveEditorDoc,
} from '../store';
import { ResizeHandle } from '../ui/ResizeHandle';
import { openEditorWindow, writeSharedDoc, bridgePublish } from './editor-bridge';
import { runAndApply } from '../indicators/runner';

interface Props {
  editorRef: { getDoc: () => string; setDoc?: (doc: string) => void };
  /** When true, render as full-window editor (no resize handle / detach chrome simplified) */
  standalone?: boolean;
  onRun?: (doc: string) => void;
}

export const EditorPane: Component<Props> = (props) => {
  const onRun = (doc: string) => {
    if (doc?.trim()) {
      props.onRun?.(doc) ?? runAndApply(doc);
    }
  };

  const detachPopup = () => {
    const doc = props.editorRef.getDoc?.() || '';
    writeSharedDoc(doc);
    saveEditorDoc(doc);
    setEditorMode('popout');
    openEditorWindow('popup');
  };

  const openTab = () => {
    const doc = props.editorRef.getDoc?.() || '';
    writeSharedDoc(doc);
    saveEditorDoc(doc);
    setEditorMode('popout');
    openEditorWindow('tab');
  };

  const header = (
    <div class="flex items-center gap-1 px-2 py-1 border-b-2 border-border bg-bg-base flex-shrink-0 min-h-[28px]">
      <span class="text-[10px] text-text-dim uppercase tracking-wider font-semibold mr-auto">
        Editor
      </span>
      <Show when={!props.standalone}>
        <button
          class="sc-btn sc-btn-ghost px-1.5 text-[10px]"
          title="Detach to floating window"
          onClick={detachPopup}
        >
          ⧉ Detach
        </button>
        <button
          class="sc-btn sc-btn-ghost px-1.5 text-[10px]"
          title="Open editor in new tab"
          onClick={openTab}
        >
          ↗ Tab
        </button>
        <button
          class="sc-btn sc-btn-ghost px-1.5 text-[11px] leading-none"
          title="Hide editor"
          onClick={() => setEditorOpen(false)}
        >
          ›
        </button>
      </Show>
      <Show when={props.standalone}>
        <button
          class="sc-btn sc-btn-ghost px-1.5 text-[10px]"
          title="Reattach to main chart window"
          onClick={() => {
            const doc = props.editorRef.getDoc?.() || '';
            writeSharedDoc(doc);
            bridgePublish({ type: 'reattach' });
            setTimeout(() => {
              try { window.close(); } catch { /* tab may ignore */ }
            }, 120);
          }}
        >
          ⬅ Reattach
        </button>
      </Show>
    </div>
  );

  if (props.standalone) {
    return (
      <div class="flex flex-col h-full min-h-0 bg-bg-panel">
        {header}
        <div class="flex-1 min-h-0 overflow-hidden">
          <TabbedEditor onRun={onRun} editorRef={props.editorRef} />
        </div>
      </div>
    );
  }

  return (
    <Show when={store.editor.open && store.editor.mode === 'docked'}>
      <aside
        class="flex flex-col flex-shrink-0 bg-bg-panel border-l-2 border-border min-h-0 overflow-hidden relative"
        style={{ width: `${store.editor.width}px` }}
      >
        <ResizeHandle
          direction="grow-left"
          getWidth={() => store.editor.width}
          setWidth={setEditorWidth}
          min={280}
          max={Math.floor(window.innerWidth * 0.8)}
          class="absolute top-0 left-0 bottom-0 z-20"
        />
        {header}
        <div class="flex-1 min-h-0 overflow-hidden">
          <TabbedEditor
            onRun={onRun}
            editorRef={props.editorRef}
            onDocChange={(doc) => {
              saveEditorDoc(doc);
            }}
          />
        </div>
      </aside>
    </Show>
  );
};
