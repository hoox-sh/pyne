import { render } from 'solid-js/web';
import { App } from './app';
import { EditorApp } from './editor/EditorApp';
import { isEditorView } from './editor/editor-bridge';
import './index.css';

const root = document.getElementById('app');
if (root) {
  if (isEditorView()) {
    render(() => <EditorApp />, root);
  } else {
    render(() => <App />, root);
  }
}
