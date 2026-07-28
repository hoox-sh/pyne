// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

import { Component, createSignal, onMount, onCleanup } from 'solid-js';
import { EditorPane } from './EditorPane';
import {
  bridgeSubscribe,
  bridgePublish,
  writeSharedDoc,
  readSharedDoc,
} from './editor-bridge';
import { store } from '../store';

/**
 * Standalone editor window (?view=editor).
 * Run commands are forwarded to the main chart window via BroadcastChannel.
 */
export const EditorApp: Component = () => {
  const [runStatus, setRunStatus] = createSignal('');
  const editorRef: { getDoc: () => string; setDoc?: (doc: string) => void } = {
    getDoc: () => '',
  };

  onMount(() => {
    document.title = 'AXIS · Editor';
    document.documentElement.setAttribute('data-theme', store.theme);
    bridgePublish({ type: 'hello', role: 'editor' });
    bridgePublish({ type: 'popout-opened' });

    const unsub = bridgeSubscribe((msg) => {
      if (msg.type === 'run-status') {
        setRunStatus(`${msg.status}: ${msg.message}`);
      }
      if (msg.type === 'doc' && editorRef.setDoc) {
        // Only apply if different to avoid cursor jumps on echo
        if (msg.doc !== editorRef.getDoc()) {
          editorRef.setDoc(msg.doc);
        }
      }
      if (msg.type === 'reattach') {
        // Another window requested reattach — ignore in editor
      }
    });

    const onBeforeUnload = () => {
      const doc = editorRef.getDoc();
      writeSharedDoc(doc);
      bridgePublish({ type: 'popout-closed' });
    };
    window.addEventListener('beforeunload', onBeforeUnload);

    onCleanup(() => {
      unsub();
      window.removeEventListener('beforeunload', onBeforeUnload);
      bridgePublish({ type: 'popout-closed' });
    });
  });

  const onRun = (doc: string) => {
    writeSharedDoc(doc);
    setRunStatus('running…');
    bridgePublish({ type: 'run', doc });
  };

  return (
    <div class="h-screen flex flex-col bg-bg-base text-text overflow-hidden">
      <div class="flex items-center gap-2 px-2.5 py-1 bg-bg-panel border-b-2 border-border min-h-[32px] flex-shrink-0">
        <span class="font-semibold text-sm text-text">
          AXIS
          <span class="text-text-faint font-normal text-[11px] ml-1.5">Editor</span>
        </span>
        <span class="text-[10px] text-text-faint font-mono truncate flex-1">{runStatus()}</span>
        <button
          class="sc-btn sc-btn-primary"
          onClick={() => {
            const doc = editorRef.getDoc() || readSharedDoc();
            if (doc.trim()) onRun(doc);
          }}
        >
          ▶ Run
        </button>
      </div>
      <div class="flex-1 min-h-0 overflow-hidden">
        <EditorPane
          standalone
          editorRef={editorRef}
          onRun={onRun}
        />
      </div>
    </div>
  );
};
