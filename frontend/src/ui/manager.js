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

// Manager dialog: shows installed plugins (built-in + user-loaded) and
// the indicator library (user-saved scripts). Provides:
//   - "Load plugin from URL" — calls registry.loadPluginFromUrl().
//   - "Remove" for user-loaded plugins.
//   - "Save current script" / "Load" / "Delete" for the script library.
//   - "Export / Import library" as JSON.

import { registry, loadPluginFromUrl } from '../registry.js';
import { getState } from '../state.js';
import { setScript, getScript } from '../../pine-editor.js';
import { setStatus } from './status.js';

let _backdrop = null;

const LIBRARY_KEY = 'pynescript.superchart.library.v1';
const PLUGINS_KEY = 'pynescript.superchart.plugins.v1';

function loadLibrary() {
    try { return JSON.parse(localStorage.getItem(LIBRARY_KEY) || '[]'); } catch (_) { return []; }
}
function saveLibrary(lib) { try { localStorage.setItem(LIBRARY_KEY, JSON.stringify(lib)); } catch (_) { /* ignore */ } }
function loadInstalledPlugins() {
    try { return JSON.parse(localStorage.getItem(PLUGINS_KEY) || '[]'); } catch (_) { return []; }
}
function saveInstalledPlugins(arr) { try { localStorage.setItem(PLUGINS_KEY, JSON.stringify(arr)); } catch (_) { /* ignore */ } }

function escape(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}

function renderAllPlugins() {
    const groups = [
        { kind: 'source', title: 'Sources', items: registry.listSources() },
        { kind: 'stream', title: 'Streams', items: registry.listStreams() },
        { kind: 'engine', title: 'Engines', items: registry.listEngines() },
    ];
    const installed = new Set(loadInstalledPlugins().map((p) => `${p.kind}:${p.id}`));
    return groups.map((g) => {
        const rows = g.items.map((p) => {
            const userLoaded = installed.has(`${p.kind}:${p.id}`);
            return `<tr>
                <td><span class="kind-badge kind-${g.kind}">${g.kind}</span></td>
                <td><strong>${escape(p.id)}</strong></td>
                <td>${escape(p.name)}</td>
                <td>${escape(p.description || '')}</td>
                <td class="manager-actions">
                    ${userLoaded
                        ? `<button class="btn btn-ghost btn-sm" data-action="remove" data-kind="${g.kind}" data-id="${escape(p.id)}">Remove</button>`
                        : (g.items.find((x) => x.id === p.id && x.builtIn) ? '<span class="kind-builtin">built-in</span>' : '')}
                </td>
            </tr>`;
        }).join('');
        return `<div class="manager-section">
            <h3>${g.title}</h3>
            <table class="manager-table"><thead><tr>
                <th>Kind</th><th>ID</th><th>Name</th><th>Description</th><th></th>
            </tr></thead><tbody>${rows}</tbody></table>
        </div>`;
    }).join('');
}

function renderLibrary() {
    const lib = loadLibrary();
    if (!lib.length) {
        return `<div class="empty">No saved scripts. Use "Save current script" below to add one.</div>`;
    }
    const rows = lib.map((s) => `<tr>
        <td>${escape(s.name)}</td>
        <td>${escape(s.description || '')}</td>
        <td>${new Date(s.savedAt).toLocaleString()}</td>
        <td>${s.script.length} chars</td>
        <td class="manager-actions">
            <button class="btn btn-ghost btn-sm" data-action="load-script" data-id="${escape(s.id)}">Load</button>
            <button class="btn btn-ghost btn-sm" data-action="delete-script" data-id="${escape(s.id)}">Delete</button>
        </td>
    </tr>`).join('');
    return `<table class="manager-table"><thead><tr>
        <th>Name</th><th>Description</th><th>Saved</th><th>Size</th><th></th>
    </tr></thead><tbody>${rows}</tbody></table>`;
}

function open() {
    if (_backdrop) return;
    const html = `
        <div class="settings-modal manager-modal" role="dialog" aria-modal="true" aria-label="Plugin Manager">
            <div class="settings-header">
                <span class="settings-title">Manager</span>
                <button class="btn btn-ghost btn-sm" data-action="close" aria-label="Close">×</button>
            </div>
            <div class="manager-tabs" role="tablist">
                <button class="tab tab-active" data-mtab="plugins" role="tab">Plugins</button>
                <button class="tab" data-mtab="library" role="tab">Script Library</button>
                <button class="tab" data-mtab="themes" role="tab">Theme</button>
            </div>
            <div class="manager-body">
                <div data-mtab-panel="plugins" class="manager-panel">
                    <div class="manager-row">
                        <input class="settings-input" type="text" id="plugin-url"
                               placeholder="https://example.com/my-plugin.js (must default-export a plugin)" />
                        <button class="btn btn-primary" data-action="load-plugin">Load</button>
                    </div>
                    <div class="manager-row">
                        <button class="btn btn-ghost btn-sm" data-action="export-plugins">Export installed</button>
                        <button class="btn btn-ghost btn-sm" data-action="import-plugins">Import…</button>
                        <input type="file" id="import-plugins-input" accept="application/json" hidden />
                    </div>
                    <div id="plugins-list">${renderAllPlugins()}</div>
                </div>
                <div data-mtab-panel="library" class="manager-panel" hidden>
                    <div class="manager-row">
                        <input class="settings-input" type="text" id="script-name" placeholder="Script name" />
                        <input class="settings-input" type="text" id="script-desc" placeholder="Description (optional)" />
                        <button class="btn btn-primary" data-action="save-script">💾 Save current</button>
                    </div>
                    <div class="manager-row">
                        <button class="btn btn-ghost btn-sm" data-action="export-library">Export library</button>
                        <button class="btn btn-ghost btn-sm" data-action="import-library">Import…</button>
                        <input type="file" id="import-library-input" accept="application/json" hidden />
                    </div>
                    <div id="library-list">${renderLibrary()}</div>
                </div>
                <div data-mtab-panel="themes" class="manager-panel" hidden>
                    <div class="manager-row">
                        <label class="settings-field">
                            <span class="settings-label">Theme</span>
                            <select class="settings-input" id="theme-select">
                                <option value="dark">TV Dark (default)</option>
                                <option value="light">TV Light</option>
                            </select>
                        </label>
                    </div>
                    <div class="empty" style="text-align:left">
                        Theme controls all CSS variables.  Custom themes can be added by setting
                        a different <code>data-theme</code> attribute on <code>&lt;html&gt;</code>.
                    </div>
                </div>
            </div>
        </div>`;
    _backdrop = document.createElement('div');
    _backdrop.className = 'settings-backdrop';
    _backdrop.innerHTML = html;
    document.body.appendChild(_backdrop);

    _backdrop.addEventListener('click', (e) => { if (e.target === _backdrop) close(); });
    _backdrop.querySelector('[data-action="close"]').addEventListener('click', close);

    // Tabs
    _backdrop.querySelectorAll('.manager-tabs .tab').forEach((t) => {
        t.addEventListener('click', () => {
            const name = t.dataset.mtab;
            _backdrop.querySelectorAll('.manager-tabs .tab').forEach((x) => x.classList.toggle('tab-active', x === t));
            _backdrop.querySelectorAll('[data-mtab-panel]').forEach((p) => p.hidden = p.dataset.mtabPanel !== name);
        });
    });

    // Plugin actions
    _backdrop.querySelector('[data-action="load-plugin"]').addEventListener('click', async () => {
        const url = _backdrop.querySelector('#plugin-url').value.trim();
        if (!url) return;
        await loadPlugin(url);
    });
    _backdrop.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action]');
        if (!btn) return;
        const a = btn.dataset.action;
        if (a === 'remove') {
            removePlugin(btn.dataset.kind, btn.dataset.id);
        } else if (a === 'load-script') {
            const lib = loadLibrary();
            const s = lib.find((x) => x.id === btn.dataset.id);
            if (s) { setScript(s.script); setStatus(`Loaded "${s.name}".`, 'success'); }
        } else if (a === 'delete-script') {
            const lib = loadLibrary().filter((x) => x.id !== btn.dataset.id);
            saveLibrary(lib);
            refreshLibrary();
            setStatus('Script deleted.', 'info');
        } else if (a === 'export-library') {
            downloadJson('pynescript-library.json', loadLibrary());
        } else if (a === 'export-plugins') {
            downloadJson('pynescript-plugins.json', loadInstalledPlugins());
        } else if (a === 'import-library') {
            _backdrop.querySelector('#import-library-input').click();
        } else if (a === 'import-plugins') {
            _backdrop.querySelector('#import-plugins-input').click();
        }
    });
    _backdrop.querySelector('#import-plugins-input').addEventListener('change', async (e) => {
        const f = e.target.files?.[0]; if (!f) return;
        try {
            const data = JSON.parse(await f.text());
            if (!Array.isArray(data)) throw new Error('expected an array of plugin descriptors');
            saveInstalledPlugins(data);
            for (const desc of data) {
                if (desc.url) await loadPlugin(desc.url, desc);
            }
            refreshPlugins();
        } catch (err) { setStatus(`Import failed: ${err.message}`, 'error'); }
        e.target.value = '';
    });
    _backdrop.querySelector('#import-library-input').addEventListener('change', async (e) => {
        const f = e.target.files?.[0]; if (!f) return;
        try {
            const data = JSON.parse(await f.text());
            if (!Array.isArray(data)) throw new Error('expected an array of scripts');
            saveLibrary([...loadLibrary(), ...data]);
            refreshLibrary();
            setStatus(`Imported ${data.length} script(s).`, 'success');
        } catch (err) { setStatus(`Import failed: ${err.message}`, 'error'); }
        e.target.value = '';
    });

    // Library save
    _backdrop.querySelector('[data-action="save-script"]').addEventListener('click', () => {
        const name = _backdrop.querySelector('#script-name').value.trim();
        if (!name) { setStatus('Script name is required.', 'error'); return; }
        const desc = _backdrop.querySelector('#script-desc').value.trim();
        const lib = loadLibrary();
        lib.push({ id: `s_${Date.now().toString(36)}`, name, description: desc, script: getScript(), savedAt: Date.now() });
        saveLibrary(lib);
        refreshLibrary();
        setStatus(`Saved "${name}".`, 'success');
    });

    // Theme
    const themeSel = _backdrop.querySelector('#theme-select');
    themeSel.value = document.documentElement.dataset.theme || 'dark';
    themeSel.addEventListener('change', () => {
        applyTheme(themeSel.value);
        getState().assign({ theme: themeSel.value });
    });

    document.addEventListener('keydown', escClose);
}

function close() {
    if (_backdrop) { _backdrop.remove(); _backdrop = null; }
    document.removeEventListener('keydown', escClose);
}

function escClose(e) { if (e.key === 'Escape') close(); }

function refreshPlugins() {
    if (!_backdrop) return;
    const el = _backdrop.querySelector('#plugins-list');
    if (el) el.innerHTML = renderAllPlugins();
}

function refreshLibrary() {
    if (!_backdrop) return;
    const el = _backdrop.querySelector('#library-list');
    if (el) el.innerHTML = renderLibrary();
}

async function loadPlugin(url, desc) {
    setStatus(`Loading plugin from ${url}…`, 'busy');
    try {
        const plugin = await loadPluginFromUrl(url);
        // Track as user-installed so we can remove it.
        const installed = loadInstalledPlugins();
        const entry = desc || { url, kind: plugin.kind, id: plugin.id, name: plugin.name, installedAt: Date.now() };
        if (!installed.find((p) => p.kind === entry.kind && p.id === entry.id)) {
            installed.push(entry);
            saveInstalledPlugins(installed);
        }
        refreshPlugins();
        setStatus(`Loaded ${plugin.name} (${plugin.kind}).`, 'success');
        // Fire a custom event so main.js can repopulate dropdowns.
        window.dispatchEvent(new CustomEvent('plugin-loaded', { detail: plugin }));
    } catch (err) {
        setStatus(`Plugin load failed: ${err.message}`, 'error');
    }
}

function removePlugin(kind, id) {
    if (!confirm(`Remove plugin "${id}"?`)) return;
    // We don't have a registry.unregister in the current API; the entry is removed
    // from the installed list so it won't be auto-reloaded on next page load.
    const installed = loadInstalledPlugins().filter((p) => !(p.kind === kind && p.id === id));
    saveInstalledPlugins(installed);
    setStatus(`Removed ${id} (will be back on reload until you delete the installed entry).`, 'info');
    refreshPlugins();
}

function downloadJson(name, data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export function openManager() { open(); }
export function closeManager() { close(); }

// Theme switching — toggles the `data-theme` attribute on <html>. CSS
// overrides follow the attribute selector.
export function applyTheme(theme) {
    document.documentElement.dataset.theme = theme || 'dark';
}

export function initManager() {
    // Auto-restore the last theme.
    const last = (() => { try { return JSON.parse(localStorage.getItem('pynescript.superchart.v1') || '{}').theme; } catch (_) { return null; } })();
    applyTheme(last || 'dark');
    // Auto-load any plugins the user previously installed.
    const installed = loadInstalledPlugins();
    for (const p of installed) {
        if (p.url) loadPluginFromUrl(p.url).catch(() => { /* ignore */ });
    }
}
