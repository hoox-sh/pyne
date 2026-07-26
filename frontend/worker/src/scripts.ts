/**
 * /api/scripts — user Pine script library.
 * Backed by D1 when bound; otherwise in-memory (wrangler dev without D1).
 */

import type { Env } from './index';
import { requireApiKey } from './auth';

export interface ScriptRow {
  id: string;
  name: string;
  description?: string | null;
  path?: string | null;
  content: string;
  revision: string;
  created_at: number;
  updated_at: number;
}

export interface ScriptMeta {
  id: string;
  name: string;
  description?: string;
  path?: string;
  revision: string;
  createdAt: number;
  updatedAt: number;
}

// --- In-memory fallback (per isolate; fine for local dev) ---
const memScripts = new Map<string, Map<string, ScriptRow>>();
const memDrafts = new Map<string, { content: string; name?: string; updated_at: number }>();

function memUser(userId: string): Map<string, ScriptRow> {
  let m = memScripts.get(userId);
  if (!m) {
    m = new Map();
    memScripts.set(userId, m);
  }
  return m;
}

function rowToMeta(r: ScriptRow): ScriptMeta {
  return {
    id: r.id,
    name: r.name,
    description: r.description || undefined,
    path: r.path || undefined,
    revision: r.revision,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  };
}

function newRevision(): string {
  return `rev_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

async function listD1(db: D1Database, userId: string): Promise<ScriptMeta[]> {
  const res = await db
    .prepare(
      `SELECT id, name, description, path, revision, created_at, updated_at
       FROM scripts WHERE user_id = ? ORDER BY updated_at DESC`,
    )
    .bind(userId)
    .all<Omit<ScriptRow, 'content'>>();
  return (res.results || []).map((r) => ({
    id: r.id,
    name: r.name,
    description: r.description || undefined,
    path: r.path || undefined,
    revision: r.revision,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  }));
}

async function getD1(db: D1Database, userId: string, id: string): Promise<ScriptRow | null> {
  return db
    .prepare(
      `SELECT id, name, description, path, content, revision, created_at, updated_at
       FROM scripts WHERE user_id = ? AND id = ?`,
    )
    .bind(userId, id)
    .first<ScriptRow>();
}

async function putD1(db: D1Database, userId: string, row: ScriptRow): Promise<void> {
  await db
    .prepare(
      `INSERT INTO scripts (user_id, id, name, description, path, content, revision, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(user_id, id) DO UPDATE SET
         name = excluded.name,
         description = excluded.description,
         path = excluded.path,
         content = excluded.content,
         revision = excluded.revision,
         updated_at = excluded.updated_at`,
    )
    .bind(
      userId,
      row.id,
      row.name,
      row.description ?? null,
      row.path ?? null,
      row.content,
      row.revision,
      row.created_at,
      row.updated_at,
    )
    .run();
}

async function delD1(db: D1Database, userId: string, id: string): Promise<boolean> {
  const r = await db
    .prepare(`DELETE FROM scripts WHERE user_id = ? AND id = ?`)
    .bind(userId, id)
    .run();
  return (r.meta?.changes ?? 0) > 0;
}

function corsJson(body: unknown, status: number, origin: string): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Admin-Token, If-Match',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    },
  });
}

export async function handleScripts(
  req: Request,
  env: Env,
  origin: string,
  path: string,
): Promise<Response> {
  const auth = await requireApiKey(req, env);
  if (!auth.ok) {
    return corsJson({ status: 'error', code: auth.code, message: auth.message }, auth.status, origin);
  }
  const { userId } = auth.ctx;
  const db = env.DB;
  const url = new URL(req.url);

  // /api/scripts or /api/scripts/
  // /api/scripts/_draft
  // /api/scripts/:id

  const rest = path.replace(/^\/api\/scripts\/?/, '');
  const parts = rest ? rest.split('/').filter(Boolean) : [];

  // Draft
  if (parts[0] === '_draft') {
    if (req.method === 'GET') {
      if (db) {
        const row = await db
          .prepare(`SELECT content, name, updated_at FROM script_drafts WHERE user_id = ?`)
          .bind(userId)
          .first<{ content: string; name: string | null; updated_at: number }>();
        if (!row) return corsJson({ status: 'success', draft: null }, 200, origin);
        return corsJson(
          { status: 'success', draft: { content: row.content, name: row.name || undefined } },
          200,
          origin,
        );
      }
      const d = memDrafts.get(userId);
      return corsJson(
        { status: 'success', draft: d ? { content: d.content, name: d.name } : null },
        200,
        origin,
      );
    }
    if (req.method === 'PUT' || req.method === 'POST') {
      const body = (await req.json().catch(() => ({}))) as { content?: string; name?: string };
      const content = String(body.content ?? '');
      const name = body.name ? String(body.name) : undefined;
      const now = Date.now();
      if (db) {
        await db
          .prepare(
            `INSERT INTO script_drafts (user_id, content, name, updated_at)
             VALUES (?, ?, ?, ?)
             ON CONFLICT(user_id) DO UPDATE SET content = excluded.content, name = excluded.name, updated_at = excluded.updated_at`,
          )
          .bind(userId, content, name ?? null, now)
          .run();
      } else {
        memDrafts.set(userId, { content, name, updated_at: now });
      }
      return corsJson({ status: 'success' }, 200, origin);
    }
    return corsJson({ status: 'error', code: 'METHOD', message: 'GET or PUT required' }, 405, origin);
  }

  // Collection
  if (parts.length === 0) {
    if (req.method === 'GET') {
      if (db) {
        try {
          const items = await listD1(db, userId);
          return corsJson({ status: 'success', scripts: items }, 200, origin);
        } catch (e) {
          const msg = e instanceof Error ? e.message : String(e);
          if (/no such table/i.test(msg)) {
            return corsJson(
              {
                status: 'error',
                code: 'NO_SCHEMA',
                message: 'D1 scripts table missing. Run schemas/scripts.sql',
              },
              503,
              origin,
            );
          }
          throw e;
        }
      }
      const items = [...memUser(userId).values()]
        .sort((a, b) => b.updated_at - a.updated_at)
        .map(rowToMeta);
      return corsJson({ status: 'success', scripts: items, backend: 'memory' }, 200, origin);
    }
    if (req.method === 'POST') {
      // Create with server-generated id optional
      const body = (await req.json().catch(() => ({}))) as Partial<ScriptRow> & { script?: string };
      const now = Date.now();
      const id = String(body.id || `s_${now.toString(36)}`);
      const row: ScriptRow = {
        id,
        name: String(body.name || 'Untitled'),
        description: body.description ?? null,
        path: body.path ?? null,
        content: String(body.content ?? body.script ?? ''),
        revision: newRevision(),
        created_at: now,
        updated_at: now,
      };
      if (db) await putD1(db, userId, row);
      else memUser(userId).set(id, row);
      return corsJson({ status: 'success', script: { ...rowToMeta(row), content: row.content } }, 201, origin);
    }
    return corsJson({ status: 'error', code: 'METHOD', message: 'GET or POST required' }, 405, origin);
  }

  // Item /api/scripts/:id
  const id = decodeURIComponent(parts[0]);

  if (req.method === 'GET') {
    let row: ScriptRow | null = null;
    if (db) row = await getD1(db, userId, id);
    else row = memUser(userId).get(id) || null;
    if (!row) {
      return corsJson({ status: 'error', code: 'NOT_FOUND', message: `script ${id} not found` }, 404, origin);
    }
    return corsJson(
      {
        status: 'success',
        script: {
          ...rowToMeta(row),
          content: row.content,
        },
      },
      200,
      origin,
    );
  }

  if (req.method === 'PUT' || req.method === 'POST') {
    const body = (await req.json().catch(() => ({}))) as Partial<ScriptRow> & {
      script?: string;
      revision?: string;
    };
    const ifMatch = req.headers.get('If-Match') || body.revision;
    const now = Date.now();

    let prev: ScriptRow | null = null;
    if (db) prev = await getD1(db, userId, id);
    else prev = memUser(userId).get(id) || null;

    if (ifMatch && prev && prev.revision !== ifMatch) {
      return corsJson(
        {
          status: 'error',
          code: 'CONFLICT',
          message: 'revision mismatch',
          remoteRevision: prev.revision,
        },
        409,
        origin,
      );
    }

    const row: ScriptRow = {
      id,
      name: String(body.name || prev?.name || 'Untitled'),
      description: body.description !== undefined ? body.description : prev?.description ?? null,
      path: body.path !== undefined ? body.path : prev?.path ?? null,
      content: String(body.content ?? body.script ?? prev?.content ?? ''),
      revision: newRevision(),
      created_at: prev?.created_at || now,
      updated_at: now,
    };
    if (db) await putD1(db, userId, row);
    else memUser(userId).set(id, row);
    return corsJson(
      { status: 'success', script: { ...rowToMeta(row), content: row.content } },
      prev ? 200 : 201,
      origin,
    );
  }

  if (req.method === 'DELETE') {
    let deleted = false;
    if (db) deleted = await delD1(db, userId, id);
    else {
      deleted = memUser(userId).delete(id);
    }
    if (!deleted) {
      return corsJson({ status: 'error', code: 'NOT_FOUND', message: `script ${id} not found` }, 404, origin);
    }
    return corsJson({ status: 'success' }, 200, origin);
  }

  return corsJson({ status: 'error', code: 'METHOD', message: 'unsupported method' }, 405, origin);
}

/** Test helpers */
export function _clearMemScripts() {
  memScripts.clear();
  memDrafts.clear();
}
