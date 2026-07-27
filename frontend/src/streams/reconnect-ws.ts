/**
 * Reconnectable WebSocket with exponential backoff for AXIS venue streams.
 */

export type WsStatus = {
  state: 'open' | 'closed' | 'reconnecting' | string;
  url?: string;
  detail?: string;
};

export interface ReconnectableWsOpts {
  url: string;
  /** Called after each successful open (re-subscribe here). */
  onOpen?: (ws: WebSocket) => void;
  onMessage: (ev: MessageEvent, ws: WebSocket) => void;
  onStatus: (s: WsStatus) => void;
  /** Hard failure only (construct error or reconnect exhausted). */
  onError: (e: Error) => void;
  maxAttempts?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
}

/**
 * Open a WebSocket that reconnects on unexpected close.
 * Returns a stop() that closes without further reconnect attempts.
 */
export function openReconnectableWs(opts: ReconnectableWsOpts): () => void {
  const maxAttempts = opts.maxAttempts ?? 8;
  const baseDelayMs = opts.baseDelayMs ?? 1_000;
  const maxDelayMs = opts.maxDelayMs ?? 30_000;

  let stopped = false;
  let ws: WebSocket | null = null;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let openedOnce = false;

  const clearTimer = () => {
    if (timer != null) {
      clearTimeout(timer);
      timer = null;
    }
  };

  const connect = () => {
    if (stopped) return;
    clearTimer();
    try {
      ws = new WebSocket(opts.url);
    } catch (e) {
      opts.onError(e instanceof Error ? e : new Error(String(e)));
      return;
    }

    ws.onopen = () => {
      if (stopped) {
        try {
          ws?.close();
        } catch {
          /* ignore */
        }
        return;
      }
      attempt = 0;
      openedOnce = true;
      opts.onStatus({ state: 'open', url: opts.url, detail: opts.url });
      try {
        opts.onOpen?.(ws!);
      } catch (e) {
        opts.onError(e instanceof Error ? e : new Error(String(e)));
      }
    };

    ws.onmessage = (ev) => {
      if (stopped) return;
      try {
        opts.onMessage(ev, ws!);
      } catch {
        /* ignore parse errors in caller */
      }
    };

    // Rely on close for reconnect; some browsers fire error then close.
    ws.onerror = () => {
      /* no-op — handled in onclose */
    };

    ws.onclose = () => {
      ws = null;
      if (stopped) {
        opts.onStatus({ state: 'closed' });
        return;
      }
      attempt += 1;
      if (attempt > maxAttempts) {
        opts.onStatus({ state: 'closed', detail: 'reconnect exhausted' });
        opts.onError(
          new Error(
            openedOnce
              ? `WebSocket reconnect exhausted after ${maxAttempts} attempts`
              : 'WebSocket failed to connect',
          ),
        );
        return;
      }
      const delay = Math.min(maxDelayMs, baseDelayMs * 2 ** (attempt - 1));
      opts.onStatus({
        state: 'reconnecting',
        url: opts.url,
        detail: `attempt ${attempt}/${maxAttempts} in ${delay}ms`,
      });
      timer = setTimeout(connect, delay);
    };
  };

  connect();

  return () => {
    stopped = true;
    clearTimer();
    const sock = ws;
    ws = null;
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
    opts.onStatus({ state: 'closed' });
  };
}

/** Compute next backoff delay (exported for unit tests). */
export function nextBackoffMs(
  attempt: number,
  baseDelayMs = 1_000,
  maxDelayMs = 30_000,
): number {
  if (attempt < 1) return baseDelayMs;
  return Math.min(maxDelayMs, baseDelayMs * 2 ** (attempt - 1));
}
