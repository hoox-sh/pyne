// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Map Pro API / Runtime ``drawings`` payloads → SVG-friendly geometry.
 */

export interface ScriptDrawing {
  id: string;
  type: 'line' | 'box' | 'label' | 'polyline';
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
  closed?: boolean;
  points?: Array<{ time: number; price: number }>;
}

function parsePolylinePoints(raw: unknown): Array<{ time: number; price: number }> {
  if (!Array.isArray(raw)) return [];
  const points: Array<{ time: number; price: number }> = [];
  for (const p of raw) {
    if (!p || typeof p !== 'object') continue;
    const pr = p as Record<string, unknown>;
    const t = num(pr.time ?? pr.t);
    const price = num(pr.price ?? pr.p ?? pr.y);
    if (t == null || price == null) continue;
    points.push({ time: t, price });
  }
  return points;
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

    // Polylines often only carry `points` — handle before t1/p1 gate.
    if (type === 'polyline') {
      const points = parsePolylinePoints(r.points);
      if (points.length < 2) continue;
      out.push({
        id: `pine_poly_${i++}`,
        type: 'polyline',
        t1: points[0]!.time,
        p1: points[0]!.price,
        t2: points[points.length - 1]!.time,
        p2: points[points.length - 1]!.price,
        color: str(r.color, '#939fff'),
        bgcolor: str(r.bgcolor, 'rgba(147,159,255,0.06)'),
        width: num(r.width) ?? 1,
        style: str(r.style, 'solid'),
        closed: Boolean(r.closed),
        points,
      });
      continue;
    }

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
