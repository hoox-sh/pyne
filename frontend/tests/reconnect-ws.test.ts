/**
 * Reconnectable WS helper + backoff math.
 */

import { describe, expect, it, mock, beforeEach, afterEach } from 'bun:test';
import { nextBackoffMs, openReconnectableWs } from '../src/streams/reconnect-ws';

describe('nextBackoffMs', () => {
  it('grows exponentially and caps', () => {
    expect(nextBackoffMs(1, 1000, 30_000)).toBe(1000);
    expect(nextBackoffMs(2, 1000, 30_000)).toBe(2000);
    expect(nextBackoffMs(3, 1000, 30_000)).toBe(4000);
    expect(nextBackoffMs(10, 1000, 30_000)).toBe(30_000);
  });
});

class FakeWS {
  static instances: FakeWS[] = [];
  static shouldFailConstruct = false;
  onopen: ((ev?: unknown) => void) | null = null;
  onclose: ((ev?: unknown) => void) | null = null;
  onerror: ((ev?: unknown) => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  readyState = 0;
  url: string;

  constructor(url: string) {
    if (FakeWS.shouldFailConstruct) throw new Error('construct fail');
    this.url = url;
    FakeWS.instances.push(this);
  }

  close() {
    this.readyState = 3;
    this.onclose?.({});
  }

  open() {
    this.readyState = 1;
    this.onopen?.({});
  }

  emitMessage(data: string) {
    this.onmessage?.({ data });
  }
}

describe('openReconnectableWs', () => {
  const prevWS = globalThis.WebSocket;

  beforeEach(() => {
    FakeWS.instances = [];
    FakeWS.shouldFailConstruct = false;
    (globalThis as unknown as { WebSocket: typeof FakeWS }).WebSocket = FakeWS as never;
  });

  afterEach(() => {
    globalThis.WebSocket = prevWS;
  });

  it('opens and delivers messages', () => {
    const statuses: string[] = [];
    const bars: string[] = [];
    const stop = openReconnectableWs({
      url: 'wss://example.test/ws',
      onStatus: (s) => statuses.push(s.state),
      onError: () => {},
      onMessage: (e) => bars.push(String(e.data)),
    });
    expect(FakeWS.instances.length).toBe(1);
    FakeWS.instances[0]!.open();
    expect(statuses).toContain('open');
    FakeWS.instances[0]!.emitMessage('hello');
    expect(bars).toEqual(['hello']);
    stop();
    expect(statuses.at(-1)).toBe('closed');
  });

  it('reconnects after unexpected close', async () => {
    const statuses: string[] = [];
    const stop = openReconnectableWs({
      url: 'wss://example.test/ws',
      maxAttempts: 3,
      baseDelayMs: 10,
      maxDelayMs: 50,
      onStatus: (s) => statuses.push(s.state),
      onError: () => {},
      onMessage: () => {},
    });
    FakeWS.instances[0]!.open();
    FakeWS.instances[0]!.close(); // unexpected — not stopped
    expect(statuses).toContain('reconnecting');
    await new Promise((r) => setTimeout(r, 30));
    expect(FakeWS.instances.length).toBeGreaterThanOrEqual(2);
    stop();
  });

  it('calls onError when construct fails', () => {
    FakeWS.shouldFailConstruct = true;
    let err: Error | null = null;
    openReconnectableWs({
      url: 'wss://bad',
      onStatus: () => {},
      onError: (e) => {
        err = e;
      },
      onMessage: () => {},
    });
    expect(err).toBeTruthy();
    expect(err!.message).toMatch(/construct|fail/i);
  });
});
