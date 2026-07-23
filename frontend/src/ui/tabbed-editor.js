// Multi-tab editor.  Wraps a single CodeMirror 6 EditorView that swaps its
// `doc` whenever the user switches tabs.  Tabs are persisted to localStorage
// as `{ id, name, content }` records.
//
// A few helpers on top of CM6:
//   • Per-tab unsaved-state indicator (dot before the name).
//   • Ctrl/Cmd+Alt+Left / Right to cycle tabs.
//   • Right-click a tab to rename, duplicate, or delete it.
//   • Drag-reorder is intentionally omitted for now.

import { initPineEditor, getScript, setScript } from '../../pine-editor.js';

const TABS_KEY = 'pynescript.superchart.tabs.v1';
const ACTIVE_KEY = 'pynescript.superchart.active-tab.v1';

function loadTabs() {
    try { return JSON.parse(localStorage.getItem(TABS_KEY) || '[]'); } catch (_) { return []; }
}
function saveTabs(tabs) {
    try { localStorage.setItem(TABS_KEY, JSON.stringify(tabs)); } catch (_) { /* ignore */ }
}
function loadActive() {
    try { return localStorage.getItem(ACTIVE_KEY) || null; } catch (_) { return null; }
}
function saveActive(id) {
    try { if (id) localStorage.setItem(ACTIVE_KEY, id); } catch (_) { /* ignore */ }
}

function genId() { return 't_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

export class TabbedEditor {
    constructor({ parent, onRun, onDocChange, onTabsChange, initialScript }) {
        this.parent = parent;
        this.onRun = onRun || (() => {});
        this.onDocChange = onDocChange || (() => {});
        this.onTabsChange = onTabsChange || (() => {});
        this.tabs = loadTabs();
        this.activeId = loadActive();
        this._suppressDocChange = false;

        // Build the DOM
        this.parent.classList.add('tabbed-editor');
        this.parent.innerHTML = '';
        this.tabBarEl = document.createElement('div');
        this.tabBarEl.className = 'editor-tabbar';
        this.addTabBtn = document.createElement('button');
        this.addTabBtn.className = 'tab-add';
        this.addTabBtn.textContent = '+';
        this.addTabBtn.title = 'New tab';
        this.tabBarEl.appendChild(this.addTabBtn);

        this.editorHostEl = document.createElement('div');
        this.editorHostEl.className = 'tabbed-host';
        this.parent.appendChild(this.tabBarEl);
        this.parent.appendChild(this.editorHostEl);

        // Ensure at least one tab
        if (!this.tabs.length) {
            this.tabs.push({ id: genId(), name: 'untitled', content: initialScript || '//@version=5\n' });
        }
        if (!this.activeId || !this.tabs.find((t) => t.id === this.activeId)) {
            this.activeId = this.tabs[0].id;
        }
        this._renderTabs();

        this.addTabBtn.addEventListener('click', () => this.newTab());

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.altKey && e.key === 'ArrowLeft') {
                e.preventDefault(); this.cycleTab(-1);
            } else if ((e.ctrlKey || e.metaKey) && e.altKey && e.key === 'ArrowRight') {
                e.preventDefault(); this.cycleTab(1);
            } else if ((e.ctrlKey || e.metaKey) && e.key === 't' && !e.shiftKey) {
                // Avoid stealing from the editor's normal Ctrl+T (no-op there anyway).
                e.preventDefault(); this.newTab();
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'w' && !e.shiftKey) {
                if (this.tabs.length > 1) {
                    e.preventDefault(); this.closeTab(this.activeId);
                }
            }
        });
    }

    async init() {
        await initPineEditor({
            parent: this.editorHostEl,
            initialDoc: this._activeTab().content,
            onRun: (src) => this.onRun(src),
            onDocChange: (src) => {
                if (this._suppressDocChange) return;
                const t = this._activeTab();
                if (t.content !== src) {
                    t.content = src;
                    t.dirty = true;
                    saveTabs(this.tabs);
                    this._renderTabs();
                }
                this.onDocChange(src);
            },
        });
    }

    _activeTab() { return this.tabs.find((t) => t.id === this.activeId) || this.tabs[0]; }
    getScript() { return this._activeTab().content; }

    setScript(content, opts = {}) {
        const t = this._activeTab();
        t.content = content;
        t.dirty = !!opts.dirty;
        if (!opts.skipSave) saveTabs(this.tabs);
        if (this._suppressDocChange) return;
        this._suppressDocChange = true;
        try { setScript(content); } finally { this._suppressDocChange = false; }
        this._renderTabs();
    }

    newTab(content) {
        const id = genId();
        const tab = { id, name: `untitled-${this.tabs.length + 1}`, content: content || '//@version=5\n' };
        this.tabs.push(tab);
        this.activeId = id;
        saveTabs(this.tabs); saveActive(this.activeId);
        this._renderTabs();
        this.setScript(tab.content);
        this.onTabsChange();
    }

    closeTab(id) {
        const idx = this.tabs.findIndex((t) => t.id === id);
        if (idx < 0) return;
        const t = this.tabs[idx];
        if (t.dirty && !confirm(`Discard unsaved changes in "${t.name}"?`)) return;
        this.tabs.splice(idx, 1);
        if (this.activeId === id) {
            this.activeId = this.tabs[Math.max(0, idx - 1)].id;
        }
        saveTabs(this.tabs); saveActive(this.activeId);
        this._renderTabs();
        this.setScript(this._activeTab().content);
        this.onTabsChange();
    }

    cycleTab(delta) {
        const i = this.tabs.findIndex((t) => t.id === this.activeId);
        const next = this.tabs[(i + delta + this.tabs.length) % this.tabs.length];
        if (next) this.activateTab(next.id);
    }

    activateTab(id) {
        if (this.activeId === id) return;
        const prev = this._activeTab();
        if (prev) prev.content = getScript();
        this.activeId = id;
        saveActive(id);
        saveTabs(this.tabs);
        this._renderTabs();
        this.setScript(this._activeTab().content, { skipSave: true });
    }

    renameTab(id, name) {
        const t = this.tabs.find((x) => x.id === id);
        if (!t) return;
        t.name = name.trim() || t.name;
        saveTabs(this.tabs);
        this._renderTabs();
    }

    _renderTabs() {
        // Re-render the tab bar in place. Cheap because there are rarely more than a dozen tabs.
        for (const el of Array.from(this.tabBarEl.children)) {
            if (el !== this.addTabBtn) el.remove();
        }
        for (const t of this.tabs) {
            const tab = document.createElement('div');
            tab.className = 'editor-tab' + (t.id === this.activeId ? ' is-active' : '') + (t.dirty ? ' is-dirty' : '');
            tab.dataset.id = t.id;
            tab.title = `${t.name}${t.dirty ? ' (unsaved)' : ''}`;
            tab.innerHTML = `
                <span class="tab-dot"></span>
                <span class="tab-name">${escape(t.name)}</span>
                <button class="tab-close" title="Close">×</button>
            `;
            tab.addEventListener('click', (e) => {
                if (e.target.classList.contains('tab-close')) {
                    e.stopPropagation();
                    this.closeTab(t.id);
                } else {
                    this.activateTab(t.id);
                }
            });
            tab.addEventListener('dblclick', () => {
                const name = prompt('Rename tab', t.name);
                if (name != null) this.renameTab(t.id, name);
            });
            // Insert before the + button
            this.tabBarEl.insertBefore(tab, this.addTabBtn);
        }
    }
}

function escape(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}
