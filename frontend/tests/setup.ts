/**
 * Shared AXIS test environment (localStorage + document stub).
 * Import first in suites that touch store/plugins/storage.
 */

export class MemoryStorage {
  store = new Map<string, string>();
  get length() {
    return this.store.size;
  }
  key(i: number) {
    return [...this.store.keys()][i] ?? null;
  }
  getItem(k: string) {
    return this.store.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.store.set(k, String(v));
  }
  removeItem(k: string) {
    this.store.delete(k);
  }
  clear() {
    this.store.clear();
  }
}

export function installMemoryLocalStorage(): MemoryStorage {
  const mem = new MemoryStorage();
  (globalThis as unknown as { localStorage: MemoryStorage }).localStorage = mem;
  return mem;
}

/** Minimal document for theme toggles + pane DOM ops. */
export function installDocumentStub() {
  if (typeof document !== 'undefined' && (document as { __axisStub?: boolean }).__axisStub) {
    return;
  }
  const attrs = new Map<string, string>();
  const nodes = new Map<string, FakeEl>();

  class FakeEl {
    id = '';
    className = '';
    style: Record<string, string> = {};
    dataset: Record<string, string> = {};
    textContent = '';
    children: FakeEl[] = [];
    parent: FakeEl | null = null;
    listeners = new Map<string, Set<(...a: unknown[]) => void>>();
    setAttribute(k: string, v: string) {
      attrs.set(`${this.id}:${k}`, v);
    }
    getAttribute(k: string) {
      return attrs.get(`${this.id}:${k}`) ?? null;
    }
    appendChild(c: FakeEl) {
      c.parent = this;
      this.children.push(c);
      if (c.id) nodes.set(c.id, c);
      return c;
    }
    remove() {
      if (this.id) nodes.delete(this.id);
      if (this.parent) {
        this.parent.children = this.parent.children.filter((x) => x !== this);
      }
    }
    querySelector(sel: string) {
      if (sel === 'span') return this.children.find((c) => c.tag === 'span') || null;
      return null;
    }
    getBoundingClientRect() {
      return { width: 800, height: 200, top: 0, left: 0, right: 800, bottom: 200 };
    }
    addEventListener(type: string, fn: (...a: unknown[]) => void) {
      if (!this.listeners.has(type)) this.listeners.set(type, new Set());
      this.listeners.get(type)!.add(fn);
    }
    removeEventListener(type: string, fn: (...a: unknown[]) => void) {
      this.listeners.get(type)?.delete(fn);
    }
    setPointerCapture() {}
    releasePointerCapture() {}
    tag = 'div';
  }

  const docEl = new FakeEl();
  docEl.setAttribute = (k: string, v: string) => {
    attrs.set(k, v);
  };
  docEl.getAttribute = (k: string) => attrs.get(k) ?? null;

  const body = new FakeEl();
  body.tag = 'body';

  (globalThis as unknown as { document: unknown; ResizeObserver: unknown }).document = {
    __axisStub: true,
    documentElement: docEl,
    body,
    createElement(tag: string) {
      const el = new FakeEl();
      el.tag = tag;
      return el;
    },
    getElementById(id: string) {
      return nodes.get(id) || null;
    },
  };

  if (typeof (globalThis as { ResizeObserver?: unknown }).ResizeObserver === 'undefined') {
    (globalThis as { ResizeObserver: unknown }).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }

  if (typeof (globalThis as { getComputedStyle?: unknown }).getComputedStyle === 'undefined') {
    (globalThis as { getComputedStyle: (el: { style?: Record<string, string> }) => Record<string, string> }).getComputedStyle =
      (el) => ({
        position: el?.style?.position || 'static',
        getPropertyValue: () => '',
      });
  }
}

export function installWindowStub(width = 1280) {
  const w = globalThis as unknown as {
    innerWidth?: number;
    window?: { innerWidth: number };
  };
  w.innerWidth = width;
  if (!w.window) {
    (globalThis as unknown as { window: { innerWidth: number } }).window = { innerWidth: width };
  } else {
    w.window!.innerWidth = width;
  }
}

/** Call at top of test files before importing store when possible; else in beforeEach. */
export function installAxisTestEnv() {
  installMemoryLocalStorage();
  installDocumentStub();
  installWindowStub();
}

// Auto-install when this module is loaded
installAxisTestEnv();
