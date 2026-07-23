// Status bar — single set of helpers shared by every module.

const el = {};

export function initStatus() {
    el.bar = document.getElementById('status-bar');
    el.text = document.getElementById('status-text');
    el.meta = document.getElementById('status-meta');
    return el;
}

export function setStatus(text, kind = 'info', meta = '') {
    if (!el.text) initStatus();
    el.text.textContent = text;
    el.bar.classList.remove('is-error', 'is-success', 'is-busy');
    if (kind === 'error') el.bar.classList.add('is-error');
    else if (kind === 'success') el.bar.classList.add('is-success');
    else if (kind === 'busy') el.bar.classList.add('is-busy');
    el.meta.textContent = meta;
}
