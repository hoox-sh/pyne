/**
 * Minimal WebSocket stub for stream plugin tests.
 */

type Handler = (ev: { data: string }) => void;

export class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: Handler | null = null;
  private listeners = new Map<string, Set<(...a: unknown[]) => void>>();

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.readyState = 1;
      this.onopen?.();
      this.emit('open');
    });
  }

  addEventListener(type: string, fn: (...a: unknown[]) => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(fn);
  }

  removeEventListener(type: string, fn: (...a: unknown[]) => void) {
    this.listeners.get(type)?.delete(fn);
  }

  send(_data: string) {
    /* no-op */
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
    this.emit('close');
  }

  /** Test helper: push a message */
  push(data: unknown) {
    const raw = typeof data === 'string' ? data : JSON.stringify(data);
    this.onmessage?.({ data: raw });
    this.emit('message', { data: raw });
  }

  private emit(type: string, ev?: unknown) {
    for (const fn of this.listeners.get(type) || []) {
      fn(ev);
    }
  }

  static install(): () => void {
    MockWebSocket.instances = [];
    const prev = globalThis.WebSocket;
    (globalThis as unknown as { WebSocket: typeof MockWebSocket }).WebSocket =
      MockWebSocket as unknown as typeof WebSocket;
    return () => {
      (globalThis as unknown as { WebSocket: typeof prev }).WebSocket = prev;
      MockWebSocket.instances = [];
    };
  }
}
