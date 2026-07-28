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

// Top bar wiring — symbols, intervals, engine/source/stream pickers, mode,
// API key, upload, live, run, save, reset. Everything goes through the
// registry + state — no hardcoded fetch.

import { registry } from '../registry.js';
import { getState } from '../state.js';
import { setStatus } from './status.js';

const $ = (id) => document.getElementById(id);

export function initTopbar({ onRun, onLoad, onUpload, onLiveToggle, onSave, onReset, onUploadFile }) {
    const els = {
        symbol: $('symbol-input'),
        interval: $('interval-select'),
        loadBtn: $('load-btn'),
        uploadBtn: $('upload-btn'),
        uploadInput: $('upload-input'),
        liveBtn: $('live-btn'),
        runBtn: $('run-button'),
        saveBtn: $('save-button'),
        resetBtn: $('reset-button'),
        modeBadge: $('mode-badge'),
        modeToggle: $('mode-toggle'),
        apiKeyInput: $('api-key-input'),
        engineSelect: $('engine-select'),
        sourceSelect: $('source-select'),
        streamSelect: $('stream-select'),
        endpointInput: $('endpoint-input'),
    };

    // Populate select boxes from the registry.
    function fillSelect(sel, items, current) {
        sel.innerHTML = '';
        for (const it of items) {
            const opt = document.createElement('option');
            opt.value = it.id;
            opt.textContent = it.name;
            if (it.id === current) opt.selected = true;
            sel.appendChild(opt);
        }
    }
    fillSelect(els.engineSelect, registry.listEngines(), getState().get('engine'));
    fillSelect(els.sourceSelect, registry.listSources(), getState().get('source'));
    fillSelect(els.streamSelect, registry.listStreams(), getState().get('stream'));

    // Restore symbol/interval/endpoint/api key.
    const s = getState().snapshot();
    els.symbol.value = s.symbol;
    els.interval.value = s.interval;
    els.endpointInput.value = s.endpoint;
    els.apiKeyInput.value = s.apiKey;

    // Handlers
    els.symbol.addEventListener('change', () => {
        const v = (els.symbol.value || '').toUpperCase() || 'BTCUSDT';
        els.symbol.value = v;
        getState().assign({ symbol: v });
    });
    els.interval.addEventListener('change', () => getState().assign({ interval: els.interval.value }));
    els.endpointInput.addEventListener('change', () => getState().assign({ endpoint: els.endpointInput.value.trim() }));
    els.engineSelect.addEventListener('change', () => getState().assign({ engine: els.engineSelect.value }));
    els.sourceSelect.addEventListener('change', () => getState().assign({ source: els.sourceSelect.value }));
    els.streamSelect.addEventListener('change', () => getState().assign({ stream: els.streamSelect.value }));
    els.apiKeyInput.addEventListener('change', () => getState().assign({ apiKey: els.apiKeyInput.value.trim() }));
    els.modeToggle.addEventListener('click', () => {
        const next = getState().get('mode') === 'local' ? 'cloud' : 'local';
        getState().assign({ mode: next });
        setModeBadge(next);
        setStatus(`Mode: ${next}`, 'info');
    });

    els.loadBtn.addEventListener('click', onLoad);
    els.uploadBtn.addEventListener('click', () => els.uploadInput.click());
    els.uploadInput.addEventListener('change', async (e) => {
        const f = e.target.files && e.target.files[0];
        if (f) await onUploadFile(f);
        e.target.value = '';
    });
    els.liveBtn.addEventListener('click', onLiveToggle);
    els.runBtn.addEventListener('click', onRun);
    els.saveBtn.addEventListener('click', onSave);
    els.resetBtn.addEventListener('click', onReset);

    setModeBadge(s.mode);
    return els;
}

function setModeBadge(mode) {
    const badge = $('mode-badge');
    if (!badge) return;
    badge.textContent = mode === 'cloud' ? 'Cloud' : 'Local';
    badge.classList.remove('mode-local', 'mode-cloud', 'mode-error');
    badge.classList.add(mode === 'cloud' ? 'mode-cloud' : 'mode-local');
}

export function setLiveIndicator(on) {
    const btn = $('live-btn');
    if (!btn) return;
    let dot = btn.querySelector('.live-dot');
    let label = btn.querySelector('.live-label');
    if (!dot) { dot = document.createElement('span'); dot.className = 'live-dot'; btn.prepend(dot); }
    if (!label) { label = document.createElement('span'); label.className = 'live-label'; btn.appendChild(label); }
    dot.classList.toggle('is-on', !!on);
    label.textContent = on ? '■ Stop' : '▶ Live';
}
