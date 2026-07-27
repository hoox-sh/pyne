/**
 * Persistent WebSocket client for PYNE Pro API `/ws/run`.
 * Prefer WSS when the HTTP endpoint is https; fall back handled by caller.
 */

export type EngineWsRunRequest = {
  script: string;
  data: unknown[];
  mode?: string;
  symbol?: string;
  id?: string;
};

export type EngineWsResult = {
  status: 'success' | 'error';
  plots?: unknown[];
  series?: Record<string, unknown>;
  events?: unknown[];
  drawings?: unknown[];
  error?: string;
  message?: string;
  code?: string;
  meta?: Record<string, unknown>;
  mode?: string;
  script_id?: string;
  run_id?: string;
  plot_meta?: Record<string, unknown>;
  transport?: 'ws';
  [k: string]: unknown;
};

/** http(s)://host:port → ws(s)://host:port/ws/run */
export function endpointToRunWsUrl(endpoint: string): string {
  const base = endpoint.replace(/\/$/, '');
  let u: URL;
  try {
    u = new URL(base.includes('://') ? base : `http://${base}`);
  } catch {
    u = new URL(`http://${base}`);
  }
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
  // Drop path so endpoint "http://x:5002/api" still targets /ws/run on host
  // (Pro API is typically origin-root). Keep origin only.
  const origin = `${u.protocol}//${u.host}`;
  return `${origin}/ws/run`;
}

type Pending = {
  resolve: (v: EngineWsResult) => void;
  reject: (e: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};

class EngineWsClient {
  private url: string;
  private ws: WebSocket | null = null;
  private pending = new Map<string, Pending>();
  private connectPromise: Promise<void> | null = null;
  private dead = false;
  private reqSeq = 0;

  constructor(url: string) {
    this.url = url;
  }

  get isOpen(): boolean {
    // WebSocket.OPEN === 1; don't rely on static when tests mock WebSocket
    return !!this.ws && this.ws.readyState === 1;
  }

  /** True after hard failure so callers skip WS for a while. */
  get isDead(): boolean {
    return this.dead;
  }

  async ensureConnected(timeoutMs = 6_000): Promise<void> {
    if (this.dead) throw new Error('WebSocket client marked dead');
    if (this.isOpen) return;
    if (this.connectPromise) return this.connectPromise;

    this.connectPromise = new Promise<void>((resolve, reject) => {
      let settled = false;
      let ws: WebSocket;
      try {
        ws = new WebSocket(this.url);
      } catch (e) {
        this.dead = true;
        this.connectPromise = null;
        reject(e instanceof Error ? e : new Error(String(e)));
        return;
      }
      this.ws = ws;

      const timer = setTimeout(() => {
        if (settled) return;
        settled = true;
        try {
          ws.close();
        } catch {
          /* ignore */
        }
        this.ws = null;
        this.connectPromise = null;
        this.dead = true;
        reject(new Error('WebSocket connect timeout'));
      }, timeoutMs);

      ws.onopen = () => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        this.dead = false;
        this.connectPromise = null;
        resolve();
      };

      ws.onerror = () => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        this.ws = null;
        this.connectPromise = null;
        this.dead = true;
        reject(new Error('WebSocket error'));
      };

      ws.onclose = () => {
        this.ws = null;
        this.connectPromise = null;
        // Reject all in-flight
        for (const [id, p] of this.pending) {
          clearTimeout(p.timer);
          p.reject(new Error('WebSocket closed'));
          this.pending.delete(id);
        }
        if (!settled) {
          settled = true;
          clearTimeout(timer);
          this.dead = true;
          reject(new Error('WebSocket closed before open'));
        }
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(String(ev.data)) as Record<string, unknown>;
          if (msg.type === 'pong') return;
          const id = msg.id != null ? String(msg.id) : '';
          const pend = id ? this.pending.get(id) : undefined;
          if (!pend) return;
          clearTimeout(pend.timer);
          this.pending.delete(id);
          if (msg.type === 'error' || msg.status === 'error') {
            pend.resolve({
              status: 'error',
              error: String(msg.message || msg.error || 'Engine error'),
              code: msg.code as string | undefined,
              transport: 'ws',
            });
            return;
          }
          pend.resolve({
            ...(msg as EngineWsResult),
            status: 'success',
            transport: 'ws',
          });
        } catch {
          /* ignore malformed */
        }
      };
    });

    return this.connectPromise;
  }

  run(req: EngineWsRunRequest, timeoutMs: number): Promise<EngineWsResult> {
    return this.ensureConnected().then(
      () =>
        new Promise<EngineWsResult>((resolve, reject) => {
          if (!this.ws || this.ws.readyState !== 1) {
            reject(new Error('WebSocket not open'));
            return;
          }
          const id = req.id || `r${++this.reqSeq}_${Date.now().toString(36)}`;
          const timer = setTimeout(() => {
            this.pending.delete(id);
            reject(new Error('WebSocket run timeout'));
          }, timeoutMs);
          this.pending.set(id, { resolve, reject, timer });
          try {
            this.ws.send(
              JSON.stringify({
                type: 'run',
                id,
                script: req.script,
                data: req.data,
                mode: req.mode || 'interpret',
                symbol: req.symbol,
              }),
            );
          } catch (e) {
            clearTimeout(timer);
            this.pending.delete(id);
            reject(e instanceof Error ? e : new Error(String(e)));
          }
        }),
    );
  }

  close() {
    this.dead = true;
    for (const [, p] of this.pending) {
      clearTimeout(p.timer);
      p.reject(new Error('WebSocket client closed'));
    }
    this.pending.clear();
    const sock = this.ws;
    this.ws = null;
    if (sock) {
      try {
        sock.onclose = null;
        sock.onerror = null;
        sock.onmessage = null;
        sock.onopen = null;
        sock.close();
      } catch {
        /* ignore */
      }
    }
  }
}

const clients = new Map<string, EngineWsClient>();

export function getEngineWsClient(endpoint: string): EngineWsClient {
  const url = endpointToRunWsUrl(endpoint);
  let c = clients.get(url);
  if (!c || c.isDead) {
    c?.close();
    c = new EngineWsClient(url);
    clients.set(url, c);
  }
  return c;
}

/** Probe whether /ws/run accepts a socket (short timeout). */
export async function probeEngineWs(endpoint: string, timeoutMs = 4_000): Promise<boolean> {
  const client = getEngineWsClient(endpoint);
  if (client.isDead) return false;
  try {
    await client.ensureConnected(timeoutMs);
    return client.isOpen;
  } catch {
    return false;
  }
}

/** @internal */
export function _resetEngineWsClients() {
  for (const c of clients.values()) c.close();
  clients.clear();
}
