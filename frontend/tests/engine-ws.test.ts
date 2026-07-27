/**
 * Engine WebSocket URL helper + client plumbing (mocked WS).
 */

import { describe, expect, it, beforeEach, afterEach } from 'bun:test';
import {
  endpointToRunWsUrl,
  getEngineWsClient,
  _resetEngineWsClients,
} from '../src/engines/engine-ws';

describe('endpointToRunWsUrl', () => {
  it('maps http → ws and https → wss', () => {
    expect(endpointToRunWsUrl('http://localhost:5002')).toBe('ws://localhost:5002/ws/run');
    expect(endpointToRunWsUrl('https://api.example.com')).toBe('wss://api.example.com/ws/run');
  });

  it('strips trailing slash and extra path', () => {
    expect(endpointToRunWsUrl('http://127.0.0.1:5002/')).toBe('ws://127.0.0.1:5002/ws/run');
    expect(endpointToRunWsUrl('http://host:5002/api')).toBe('ws://host:5002/ws/run');
  });
});

class FakeWS {
  static instances: FakeWS[] = [];
  static failConstruct = false;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  readyState = 0;
  url: string;
  sent: string[] = [];

  constructor(url: string) {
    if (FakeWS.failConstruct) throw new Error('no ws');
    this.url = url;
    FakeWS.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }

  open() {
    this.readyState = 1;
    this.onopen?.();
  }

  reply(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
}

describe('EngineWsClient', () => {
  const prev = globalThis.WebSocket;

  beforeEach(() => {
    FakeWS.instances = [];
    FakeWS.failConstruct = false;
    _resetEngineWsClients();
    (globalThis as unknown as { WebSocket: typeof FakeWS }).WebSocket = FakeWS as never;
  });

  afterEach(() => {
    _resetEngineWsClients();
    globalThis.WebSocket = prev;
  });

  it('runs over open socket and resolves result', async () => {
    const client = getEngineWsClient('http://localhost:5002');
    const connecting = client.ensureConnected();
    expect(FakeWS.instances.length).toBe(1);
    FakeWS.instances[0]!.open();
    await connecting;
    expect(client.isOpen).toBe(true);

    const p = client.run({ script: '//', data: [] }, 5_000);
    // allow send to flush
    await Promise.resolve();
    const sent = FakeWS.instances[0]!.sent[0];
    expect(sent).toBeTruthy();
    const req = JSON.parse(sent!);
    expect(req.type).toBe('run');
    FakeWS.instances[0]!.reply({
      type: 'result',
      id: req.id,
      status: 'success',
      plots: [1, 2],
      series: {},
      events: [],
    });
    const result = await p;
    expect(result.status).toBe('success');
    expect(result.transport).toBe('ws');
    expect(result.plots).toEqual([1, 2]);
  });
});
