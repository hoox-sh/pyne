/**
 * Install a fetch mock for the duration of a test; restore on dispose.
 */

export type FetchHandler = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response> | Response;

const originalFetch = globalThis.fetch;

export function mockFetch(handler: FetchHandler): () => void {
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    return handler(input, init);
  }) as typeof fetch;
  return () => {
    globalThis.fetch = originalFetch;
  };
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
