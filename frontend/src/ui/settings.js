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

// Generic settings dialog — reads any plugin's `configSchema` and renders
// a form. Supports text, number, boolean, and select field types. Changes
// are persisted to localStorage (keyed per plugin) and the plugin instance
// is reloaded.
//
// Usage:
//   import { openSettings } from './ui/settings.js';
//   openSettings({ title: 'Binance REST', schema: binanceRest.configSchema,
//                  current: cfg, onSave: (next) => { ... } });

const FIELD_TEMPLATES = {
    string: (k, def, cur, s) => `
        <label class="settings-field">
            <span class="settings-label">${escape(def.label || k)}</span>
            <input class="settings-input" type="text" data-key="${k}"
                   value="${escape(String(cur ?? def.default ?? ''))}"
                   ${def.placeholder ? `placeholder="${escape(def.placeholder)}"` : ''} />
            ${def.description ? `<span class="settings-help">${escape(def.description)}</span>` : ''}
        </label>`,
    number: (k, def, cur) => `
        <label class="settings-field">
            <span class="settings-label">${escape(def.label || k)}</span>
            <input class="settings-input" type="number" data-key="${k}"
                   value="${Number(cur ?? def.default ?? 0)}"
                   ${def.min !== undefined ? `min="${def.min}"` : ''}
                   ${def.max !== undefined ? `max="${def.max}"` : ''}
                   step="${def.step ?? 'any'}" />
            ${def.description ? `<span class="settings-help">${escape(def.description)}</span>` : ''}
        </label>`,
    boolean: (k, def, cur) => `
        <label class="settings-field settings-field-check">
            <input type="checkbox" data-key="${k}"
                   ${(cur ?? def.default) ? 'checked' : ''} />
            <span>
                <span class="settings-label">${escape(def.label || k)}</span>
                ${def.description ? `<span class="settings-help">${escape(def.description)}</span>` : ''}
            </span>
        </label>`,
    select: (k, def, cur) => `
        <label class="settings-field">
            <span class="settings-label">${escape(def.label || k)}</span>
            <select class="settings-input" data-key="${k}">
                ${(def.options || []).map((o) => `<option value="${escape(String(o))}" ${String(cur ?? def.default) === String(o) ? 'selected' : ''}>${escape(String(o))}</option>`).join('')}
            </select>
            ${def.description ? `<span class="settings-help">${escape(def.description)}</span>` : ''}
        </label>`,
};

function escape(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}

function renderField(key, def, current) {
    const tpl = FIELD_TEMPLATES[def.type] || FIELD_TEMPLATES.string;
    return tpl(key, def, current, def);
}

function collectForm(form) {
    const out = {};
    for (const el of form.querySelectorAll('[data-key]')) {
        const k = el.dataset.key;
        if (el.type === 'checkbox') out[k] = el.checked;
        else if (el.type === 'number') out[k] = el.value === '' ? null : Number(el.value);
        else out[k] = el.value;
    }
    return out;
}

let _backdrop = null;

export function openSettings({ title, schema, current, onSave, onCancel }) {
    closeSettings();
    const backdrop = document.createElement('div');
    backdrop.className = 'settings-backdrop';
    const fields = Object.entries(schema || {}).map(([k, def]) => renderField(k, def, current?.[k])).join('');
    backdrop.innerHTML = `
        <div class="settings-modal" role="dialog" aria-modal="true" aria-label="${escape(title)}">
            <div class="settings-header">
                <span class="settings-title">${escape(title)}</span>
                <button class="btn btn-ghost btn-sm" data-action="close" aria-label="Close">×</button>
            </div>
            <form class="settings-body">
                ${fields || '<div class="empty">This plugin has no settings.</div>'}
            </form>
            <div class="settings-footer">
                <button class="btn btn-ghost" data-action="reset">Reset to defaults</button>
                <span style="flex:1"></span>
                <button class="btn btn-ghost" data-action="cancel">Cancel</button>
                <button class="btn btn-primary" data-action="save">Save</button>
            </div>
        </div>`;
    document.body.appendChild(backdrop);
    _backdrop = backdrop;

    const form = backdrop.querySelector('form');
    const close = (result) => {
        backdrop.remove();
        _backdrop = null;
        document.removeEventListener('keydown', escListener);
        (result?.onFulfilled || (() => {}))(result?.value);
    };
    const escListener = (e) => { if (e.key === 'Escape') close({ onFulfilled: onCancel, value: undefined }); };
    document.addEventListener('keydown', escListener);
    backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) close({ onFulfilled: onCancel, value: undefined });
    });

    backdrop.querySelector('[data-action="close"]').addEventListener('click', () => close({ onFulfilled: onCancel, value: undefined }));
    backdrop.querySelector('[data-action="cancel"]').addEventListener('click', () => close({ onFulfilled: onCancel, value: undefined }));
    backdrop.querySelector('[data-action="reset"]').addEventListener('click', () => {
        for (const el of form.querySelectorAll('[data-key]')) {
            const k = el.dataset.key;
            const def = schema[k];
            if (!def) continue;
            if (el.type === 'checkbox') el.checked = !!def.default;
            else el.value = def.default ?? '';
        }
    });
    backdrop.querySelector('[data-action="save"]').addEventListener('click', () => {
        const next = collectForm(form);
        close({ onFulfilled: onSave, value: next });
    });
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        backdrop.querySelector('[data-action="save"]').click();
    });
    // Focus the first field
    setTimeout(() => form.querySelector('input, select')?.focus(), 30);
}

export function closeSettings() {
    if (_backdrop) { _backdrop.remove(); _backdrop = null; }
}
