/**
 * Map Pro API / Runtime ``drawings`` payloads → SVG-friendly geometry.
 */

export interface ScriptDrawing {
  id: string;
  type: 'line' | 'box' | 'label';
  t1: number;
  p1: number;
  t2?: number;
  p2?: number;
  color: string;
  bgcolor?: string;
  text?: string;
  textcolor?: string;
  width?: number;
  style?: string;
  extend?: string;
}

/** Normalize mixed API shapes into ScriptDrawing[]. */
export function normalizeScriptDrawings(raw: unknown[] | undefined | null): ScriptDrawing[] {
  if (!raw?.length) return [];
  const out: ScriptDrawing[] = [];
  let i = 0;
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const r = item as Record<string, unknown>;
    const type = String(r.type || r.kind || '').toLowerCase();
    const t1 = num(r.t1 ?? r.time ?? r.x1 ?? r.left ?? r.x);
    const p1 = num(r.p1 ?? r.price ?? r.y1 ?? r.top ?? r.y);
    if (t1 == null || p1 == null) continue;

    if (type === 'line' || type === 'trend') {
      const t2 = num(r.t2 ?? r.x2 ?? r.right);
      const p2 = num(r.p2 ?? r.y2 ?? r.bottom);
      if (t2 == null || p2 == null) continue;
      out.push({
        id: `pine_line_${i++}`,
        type: 'line',
        t1,
        p1,
        t2,
        p2,
        color: str(r.color, '#939fff'),
        width: num(r.width) ?? 1,
        style: str(r.style, 'solid'),
        extend: str(r.extend, 'none'),
      });
      continue;
    }
    if (type === 'box' || type === 'rect') {
      const t2 = num(r.t2 ?? r.x2 ?? r.right);
      const p2 = num(r.p2 ?? r.y2 ?? r.bottom);
      if (t2 == null || p2 == null) continue;
      out.push({
        id: `pine_box_${i++}`,
        type: 'box',
        t1,
        p1,
        t2,
        p2,
        color: str(r.color ?? r.border_color, '#939fff'),
        bgcolor: str(r.bgcolor, 'rgba(147,159,255,0.08)'),
        width: num(r.width ?? r.border_width) ?? 1,
        text: str(r.text, ''),
      });
      continue;
    }
    if (type === 'label' || type === 'text') {
      out.push({
        id: `pine_label_${i++}`,
        type: 'label',
        t1,
        p1,
        color: str(r.color, '#939fff'),
        textcolor: str(r.textcolor, '#eceef4'),
        text: str(r.text, ''),
      });
    }
  }
  return out;
}

function num(v: unknown): number | null {
  if (v == null) return null;
  const n = typeof v === 'number' ? v : Number(v);
  if (!Number.isFinite(n)) return null;
  return n;
}

function str(v: unknown, fallback: string): string {
  if (v == null) return fallback;
  const s = String(v);
  return s || fallback;
}
