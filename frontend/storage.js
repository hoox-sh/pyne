// localStorage persistence for SuperChart Lite
// Keys: script, symbol, interval, run mode, API key (local-only; not synced)

const STORAGE_KEY = 'pynescript.superchart.v1';

/**
 * @typedef {{
 *   script?: string,
 *   symbol?: string,
 *   interval?: string,
 *   mode?: 'local' | 'cloud',
 *   apiKey?: string,
 *   savedAt?: number,
 * }} SuperChartState
 */

/**
 * @returns {SuperChartState | null}
 */
export function loadState() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return null;
        const data = JSON.parse(raw);
        if (!data || typeof data !== 'object') return null;
        return data;
    } catch (e) {
        console.warn('loadState failed', e);
        return null;
    }
}

/**
 * @param {SuperChartState} partial
 * @returns {SuperChartState}
 */
export function saveState(partial = {}) {
    const prev = loadState() || {};
    const next = {
        ...prev,
        ...partial,
        savedAt: Date.now(),
    };
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch (e) {
        console.warn('saveState failed (quota?)', e);
    }
    return next;
}

export function clearState() {
    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
        /* ignore */
    }
}

/**
 * Debounced save helper.
 * @param {() => SuperChartState} getPartial
 * @param {number} [ms]
 */
export function createAutoSaver(getPartial, ms = 800) {
    let timer = null;
    return {
        schedule() {
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => {
                timer = null;
                try {
                    saveState(getPartial());
                } catch (e) {
                    console.warn('auto-save failed', e);
                }
            }, ms);
        },
        flush() {
            if (timer) {
                clearTimeout(timer);
                timer = null;
            }
            return saveState(getPartial());
        },
        cancel() {
            if (timer) {
                clearTimeout(timer);
                timer = null;
            }
        },
    };
}
