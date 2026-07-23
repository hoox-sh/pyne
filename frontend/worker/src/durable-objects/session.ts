// Durable Object: per-session WebSocket relay for live datastreams.
//
// A browser connects to /api/stream?symbol=…&interval=… and the Worker
// pins a DO instance to that session. The DO opens a connection to the
// configured upstream (Binance WS by default) and forwards each kline
// message to the browser.  When the browser disconnects, the DO hibernates
// and the upstream socket is released.
//
// In the future this DO can also fan-out a single upstream subscription to
// many browsers (broadcast mode).

import type { Env } from '../index';

interface SessionState {
    symbol: string;
    interval: string;
    upstream: WebSocket | null;
    clients: WebSocket[];
}

export class SessionDO {
    private state: DurableObjectState;
    private env: Env;
    private sess: SessionState;

    constructor(state: DurableObjectState, env: Env) {
        this.state = state;
        this.env = env;
        this.sess = { symbol: '', interval: '', upstream: null, clients: [] };
    }

    async fetch(req: Request): Promise<Response> {
        const url = new URL(req.url);
        if (url.pathname !== '/ws') {
            return new Response('not found', { status: 404 });
        }

        if (req.headers.get('Upgrade') !== 'websocket') {
            return new Response('expected websocket', { status: 426 });
        }

        const symbol = url.searchParams.get('symbol') ?? 'BTCUSDT';
        const interval = url.searchParams.get('interval') ?? '1m';
        this.sess.symbol = symbol.toUpperCase();
        this.sess.interval = interval;

        const pair = new WebSocketPair();
        const [client, server] = [pair[0], pair[1]];
        this.state.acceptWebSocket(server);
        this.sess.clients.push(server);
        server.addEventListener('close', () => {
            this.sess.clients = this.sess.clients.filter((c) => c !== server);
            if (this.sess.clients.length === 0) this.closeUpstream();
        });
        server.addEventListener('error', () => this.closeUpstream());

        this.ensureUpstream();
        return new Response(null, { status: 101, webSocket: client });
    }

    async webSocketMessage(ws: WebSocket, message: string | ArrayBuffer): Promise<void> {
        // Clients can send `{"action":"subscribe","symbol":"…","interval":"…"}`.
        try {
            const msg = JSON.parse(typeof message === 'string' ? message : new TextDecoder().decode(message));
            if (msg.action === 'subscribe' && (msg.symbol !== this.sess.symbol || msg.interval !== this.sess.interval)) {
                this.sess.symbol = String(msg.symbol ?? this.sess.symbol).toUpperCase();
                this.sess.interval = String(msg.interval ?? this.sess.interval);
                this.closeUpstream();
                this.ensureUpstream();
            } else if (msg.action === 'ping') {
                ws.send(JSON.stringify({ action: 'pong', t: Date.now() }));
            }
        } catch (_) {
            // ignore non-JSON
        }
    }

    async webSocketClose(ws: WebSocket, code: number, reason: string, wasClean: boolean): Promise<void> {
        try { ws.close(code, reason); } catch (_) { /* ignore */ }
    }

    async webSocketError(ws: WebSocket, error: unknown): Promise<void> {
        try { ws.close(1011, 'upstream error'); } catch (_) { /* ignore */ }
    }

    private ensureUpstream(): void {
        if (this.sess.upstream) return;
        const url = `wss://stream.binance.com:9443/ws/${this.sess.symbol.toLowerCase()}@kline_${this.sess.interval}`;
        try {
            const upstream = new WebSocket(url);
            upstream.addEventListener('open', () => this.broadcast(JSON.stringify({ type: 'status', state: 'open', url })));
            upstream.addEventListener('close', () => {
                this.sess.upstream = null;
                this.broadcast(JSON.stringify({ type: 'status', state: 'closed' }));
            });
            upstream.addEventListener('message', (ev) => {
                // Re-emit raw Binance kline payloads.  The browser fan-outs into
                // OHLCV bars the same way it does when running off a direct WS.
                this.broadcast(typeof ev.data === 'string' ? ev.data : new TextDecoder().decode(ev.data as ArrayBuffer));
            });
            this.sess.upstream = upstream;
        } catch (err) {
            this.broadcast(JSON.stringify({ type: 'error', message: err instanceof Error ? err.message : String(err) }));
        }
    }

    private closeUpstream(): void {
        if (this.sess.upstream) {
            try { this.sess.upstream.close(); } catch (_) { /* ignore */ }
            this.sess.upstream = null;
        }
    }

    private broadcast(payload: string): void {
        for (const c of this.sess.clients) {
            try { c.send(payload); } catch (_) { /* ignore */ }
        }
    }
}
