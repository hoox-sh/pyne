// Status bar — single set of helpers shared by every module.

const el = {};

export function initStatus() {
    el.bar = document.getElementById('status-bar');
    el.text = document.getElementById('status-text');
    el.meta = document.getElementById('status-meta');

    // Copy status text to clipboard
    const copyBtn = document.getElementById('status-copy');
    if (copyBtn) {
        copyBtn.addEventListener('click', async () => {
            const text = (el.text?.textContent || '') + (el.meta?.textContent ? ' · ' + el.meta.textContent : '');
            if (!text) return;
            try {
                await navigator.clipboard.writeText(text);
                flashCopied(copyBtn);
            } catch { /* no-op */ }
        });
    }

    return el;
}

function flashCopied(btn) {
    btn.classList.add('copied');
    const orig = btn.innerHTML;
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    setTimeout(() => {
        btn.innerHTML = orig;
        btn.classList.remove('copied');
    }, 1200);
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
