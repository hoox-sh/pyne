import { Component, onMount, onCleanup } from 'solid-js';
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { defaultKeymap, indentWithTab } from '@codemirror/commands';
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search';
import { autocompletion, completionKeymap } from '@codemirror/autocomplete';
import { bracketMatching } from '@codemirror/language';
import { pineScript } from './pine-language';
import { voidEditorExtensions } from './cm-void';

interface Props {
  initialDoc?: string;
  onDocChange?: (doc: string) => void;
  onRun?: () => void;
  height?: string;
  editorRef?: { getDoc: () => string; setDoc?: (doc: string) => void };
}

export const PineEditor: Component<Props> = (props) => {
  let containerRef!: HTMLDivElement;
  let view: EditorView;

  const getDoc = () => view?.state.doc.toString() ?? '';

  const setDoc = (doc: string) => {
    if (view) {
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: doc },
      });
    }
  };

  onMount(() => {
    const runKeymap = keymap.of([{
      key: 'Mod-Enter',
      run: () => { props.onRun?.(); return true; },
    }]);

    const state = EditorState.create({
      doc: props.initialDoc ?? '',
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        highlightActiveLineGutter(),
        bracketMatching(),
        highlightSelectionMatches(),
        autocompletion(),
        runKeymap,
        keymap.of([...defaultKeymap, indentWithTab, ...searchKeymap, ...completionKeymap]),
        pineScript,
        ...voidEditorExtensions,
        EditorView.updateListener.of((update) => {
          if (update.docChanged) props.onDocChange?.(update.state.doc.toString());
        }),
      ],
    });

    view = new EditorView({ state, parent: containerRef });
    if (props.editorRef) {
      props.editorRef.getDoc = getDoc;
      props.editorRef.setDoc = setDoc;
    }
  });

  onCleanup(() => view?.destroy());

  return <div ref={containerRef!} class="h-full overflow-hidden bg-bg-panel" style={{ height: props.height || '100%' }} />;
};
