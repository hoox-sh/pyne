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
 * SVG overlay drawing layer on the LWC price pane.
 * Converts pointer coords ↔ (time, price) via series/chart scales.
 */

import type { IChartApi, ISeriesApi, UTCTimestamp } from 'lightweight-charts';
import {
  DRAWING_COLORS,
  FIB_LEVELS,
  needsTwoPoints,
  type Drawing,
  type DrawingToolId,
  type Point,
} from './drawing-types';
import { normalizeScriptDrawings, type ScriptDrawing } from './pine-drawings';

export type DrawingChangeHandler = (drawings: Drawing[]) => void;

/** Active layer singleton for toolbar / external callers (avoids ChartHost cycles). */
let activeLayer: DrawingLayer | null = null;

export function getActiveDrawingLayer(): DrawingLayer | null {
  return activeLayer;
}

function uid(): string {
  return `dw_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}

type DragMode = 'move' | 'p1' | 'p2' | 'price';

type DragState = {
  id: string;
  start: Point;
  origin: Drawing;
  mode: DragMode;
};

export class DrawingLayer {
  private host: HTMLElement;
  private chart: IChartApi;
  private series: ISeriesApi<'Candlestick'>;
  private svg: SVGSVGElement;
  private gScript: SVGGElement;
  private gDraw: SVGGElement;
  private gDraft: SVGGElement;
  private tool: DrawingToolId = 'cursor';
  private drawings: Drawing[] = [];
  private scriptDrawings: ScriptDrawing[] = [];
  private selectedId: string | null = null;
  private draft: { tool: DrawingToolId; p1?: Point; p2?: Point } | null = null;
  private drag: DragState | null = null;
  private didDrag = false;
  private onChange: DrawingChangeHandler | null = null;
  private unsubs: Array<() => void> = [];
  private ro: ResizeObserver | null = null;

  constructor(
    host: HTMLElement,
    chart: IChartApi,
    series: ISeriesApi<'Candlestick'>,
  ) {
    this.host = host;
    this.chart = chart;
    this.series = series;
    activeLayer = this;

    // Ensure host is positioning context
    const cs = getComputedStyle(host);
    if (cs.position === 'static') host.style.position = 'relative';

    this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    this.svg.setAttribute('class', 'axis-drawing-layer');
    Object.assign(this.svg.style, {
      position: 'absolute',
      inset: '0',
      width: '100%',
      height: '100%',
      zIndex: '4',
      // none: empty areas pass pan/zoom to LWC; shapes set pointer-events
      pointerEvents: 'none',
      overflow: 'hidden',
    } as CSSStyleDeclaration);

    this.gScript = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    this.gScript.setAttribute('class', 'axis-pine-drawings');
    this.gDraw = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    this.gDraft = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    this.svg.appendChild(this.gScript);
    this.svg.appendChild(this.gDraw);
    this.svg.appendChild(this.gDraft);
    host.appendChild(this.svg);

    this.bindEvents();
    this.syncSize();
    this.redraw();
  }

  setOnChange(cb: DrawingChangeHandler | null) {
    this.onChange = cb;
  }

  setTool(tool: DrawingToolId) {
    this.tool = tool;
    this.draft = null;
    this.drag = null;
    this.gDraft.innerHTML = '';
    // Drawing tools capture full surface; cursor only hits painted shapes
    this.svg.style.pointerEvents = tool === 'cursor' ? 'none' : 'auto';
    this.svg.style.cursor = tool === 'cursor' ? 'default' : 'crosshair';
    this.redraw();
  }

  getTool(): DrawingToolId {
    return this.tool;
  }

  setDrawings(drawings: Drawing[]) {
    this.drawings = drawings.slice();
    this.redrawUser();
  }

  /** Pine line/label/box from last /run (not user-editable). Atomic replace — no empty frame. */
  setScriptDrawings(raw: unknown[] | undefined | null) {
    this.scriptDrawings = normalizeScriptDrawings(raw);
    this.redrawScript();
  }

  clearScriptDrawings() {
    this.scriptDrawings = [];
    this.redrawScript();
  }

  getDrawings(): Drawing[] {
    return this.drawings.slice();
  }

  clearAll() {
    this.drawings = [];
    this.selectedId = null;
    this.draft = null;
    this.drag = null;
    this.emit();
    this.redraw();
  }

  deleteSelected() {
    if (!this.selectedId) return;
    this.drawings = this.drawings.filter((d) => d.id !== this.selectedId);
    this.selectedId = null;
    this.emit();
    this.redraw();
  }

  destroy() {
    for (const u of this.unsubs) u();
    this.unsubs = [];
    this.ro?.disconnect();
    this.svg.remove();
    if (activeLayer === this) activeLayer = null;
  }

  private emit() {
    this.onChange?.(this.drawings.slice());
  }

  private bindEvents() {
    const onClick = (e: MouseEvent) => this.handleClick(e);
    const onMove = (e: MouseEvent) => this.handleMove(e);
    const onDown = (e: PointerEvent) => this.handlePointerDown(e);
    const onUp = (e: PointerEvent) => this.handlePointerUp(e);
    const onKey = (e: KeyboardEvent) => this.handleKey(e);
    const onCtx = (e: Event) => {
      if (this.tool !== 'cursor') {
        e.preventDefault();
        this.draft = null;
        this.gDraft.innerHTML = '';
      }
    };

    this.svg.addEventListener('click', onClick);
    this.svg.addEventListener('pointerdown', onDown);
    this.svg.addEventListener('pointermove', onMove);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    this.svg.addEventListener('contextmenu', onCtx);
    window.addEventListener('keydown', onKey);
    this.unsubs.push(() => this.svg.removeEventListener('click', onClick));
    this.unsubs.push(() => this.svg.removeEventListener('pointerdown', onDown));
    this.unsubs.push(() => this.svg.removeEventListener('pointermove', onMove));
    this.unsubs.push(() => window.removeEventListener('pointermove', onMove));
    this.unsubs.push(() => window.removeEventListener('pointerup', onUp));
    this.unsubs.push(() => this.svg.removeEventListener('contextmenu', onCtx));
    this.unsubs.push(() => window.removeEventListener('keydown', onKey));

    const subRange = () => this.redraw();
    this.chart.timeScale().subscribeVisibleLogicalRangeChange(subRange);
    this.unsubs.push(() => {
      try {
        this.chart.timeScale().unsubscribeVisibleLogicalRangeChange(subRange);
      } catch {
        /* ignore */
      }
    });

    // Crosshair move also shifts price labels when panning
    const subCross = () => this.redraw();
    this.chart.subscribeCrosshairMove(subCross);
    this.unsubs.push(() => {
      try {
        this.chart.unsubscribeCrosshairMove(subCross);
      } catch {
        /* ignore */
      }
    });

    this.ro = new ResizeObserver(() => {
      this.syncSize();
      this.redraw();
    });
    this.ro.observe(this.host);
  }

  private syncSize() {
    const r = this.host.getBoundingClientRect();
    this.svg.setAttribute('viewBox', `0 0 ${r.width} ${r.height}`);
    this.svg.setAttribute('width', String(r.width));
    this.svg.setAttribute('height', String(r.height));
  }

  private clientToPoint(e: MouseEvent): Point | null {
    const rect = this.svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const time = this.chart.timeScale().coordinateToTime(x);
    const price = this.series.coordinateToPrice(y);
    if (time == null || price == null) return null;
    const t = typeof time === 'number' ? time : (time as { timestamp?: number }).timestamp;
    if (t == null || !Number.isFinite(t) || !Number.isFinite(price)) return null;
    return { time: t as number, price };
  }

  private toXY(p: Point): { x: number; y: number } | null {
    const x = this.chart.timeScale().timeToCoordinate(p.time as UTCTimestamp);
    const y = this.series.priceToCoordinate(p.price);
    if (x == null || y == null) return null;
    return { x, y };
  }

  private handleKey(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      this.draft = null;
      this.gDraft.innerHTML = '';
      this.selectedId = null;
      this.redraw();
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && this.selectedId) {
      // Don't steal from inputs
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      e.preventDefault();
      this.deleteSelected();
    }
  }

  private handlePointerDown(e: PointerEvent) {
    if (this.tool !== 'cursor') return;
    const start = this.clientToPoint(e);
    if (!start) return;
    const handle = this.hitTestHandle(e);
    const hit = handle?.id ?? this.hitTest(e);
    if (!hit) return;
    const origin = this.drawings.find((d) => d.id === hit);
    if (!origin) return;
    e.preventDefault();
    e.stopPropagation();
    this.selectedId = hit;
    this.drag = {
      id: hit,
      start,
      origin: structuredClone(origin) as Drawing,
      mode: handle?.mode ?? 'move',
    };
    this.didDrag = false;
    this.svg.style.pointerEvents = 'auto';
    this.svg.setPointerCapture?.(e.pointerId);
    this.redraw();
  }

  private handlePointerUp(e: PointerEvent) {
    if (!this.drag) return;
    try {
      this.svg.releasePointerCapture?.(e.pointerId);
    } catch {
      /* ignore */
    }
    if (this.didDrag) this.emit();
    this.drag = null;
    this.svg.style.pointerEvents = this.tool === 'cursor' ? 'none' : 'auto';
    this.redraw();
  }

  private handleClick(e: MouseEvent) {
    if (this.didDrag) {
      this.didDrag = false;
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    if (this.tool === 'cursor') {
      // Hit-test select (shapes have pointer-events; empty area doesn't fire)
      const hit = this.hitTest(e);
      this.selectedId = hit;
      this.redraw();
      return;
    }

    const pt = this.clientToPoint(e);
    if (!pt) return;

    if (this.tool === 'hline') {
      this.drawings.push({
        id: uid(),
        kind: 'hline',
        price: pt.price,
        color: DRAWING_COLORS.default,
      });
      this.emit();
      this.redraw();
      return;
    }

    if (this.tool === 'text') {
      const label = window.prompt('Label text', 'Note');
      if (label == null || !label.trim()) return;
      this.drawings.push({
        id: uid(),
        kind: 'text',
        p1: pt,
        text: label.trim(),
        color: DRAWING_COLORS.default,
      });
      this.emit();
      this.redraw();
      return;
    }

    if (needsTwoPoints(this.tool)) {
      if (!this.draft || this.draft.tool !== this.tool || !this.draft.p1) {
        this.draft = { tool: this.tool, p1: pt };
        this.renderDraft(pt);
        return;
      }
      // second point
      const p1 = this.draft.p1;
      const p2 = pt;
      this.draft = null;
      this.gDraft.innerHTML = '';
      const color =
        this.tool === 'measure'
          ? DRAWING_COLORS.measure
          : this.tool === 'fib'
            ? DRAWING_COLORS.default
            : DRAWING_COLORS.default;
      this.drawings.push({
        id: uid(),
        kind: this.tool as TwoPointKind,
        p1,
        p2,
        color,
      } as Drawing);
      this.emit();
      this.redraw();
    }
  }

  private handleMove(e: MouseEvent) {
    if (this.drag) {
      const pt = this.clientToPoint(e);
      if (!pt) return;
      const dTime = pt.time - this.drag.start.time;
      const dPrice = pt.price - this.drag.start.price;
      if (Math.abs(dTime) > 0 || Math.abs(dPrice) > 1e-12) this.didDrag = true;
      let next: Drawing;
      if (this.drag.mode === 'move') {
        next = shiftDrawing(this.drag.origin, dTime, dPrice);
      } else {
        next = resizeDrawing(this.drag.origin, this.drag.mode, pt);
      }
      const idx = this.drawings.findIndex((d) => d.id === this.drag!.id);
      if (idx >= 0) {
        this.drawings[idx] = next;
        this.redraw();
      }
      return;
    }
    if (!this.draft?.p1) return;
    const pt = this.clientToPoint(e);
    if (!pt) return;
    this.renderDraft(pt);
  }

  private renderDraft(p2: Point) {
    this.gDraft.innerHTML = '';
    if (!this.draft?.p1) return;
    const d: Drawing = needsTwoPoints(this.draft.tool)
      ? ({
          id: 'draft',
          kind: this.draft.tool as TwoPointKind,
          p1: this.draft.p1,
          p2,
          color: DRAWING_COLORS.muted,
        } as Drawing)
      : {
          id: 'draft',
          kind: 'hline',
          price: p2.price,
          color: DRAWING_COLORS.muted,
        };
    this.paintDrawing(this.gDraft, d, true);
  }

  private hitTestHandle(e: MouseEvent): { id: string; mode: DragMode } | null {
    if (!this.selectedId) return null;
    const d = this.drawings.find((x) => x.id === this.selectedId);
    if (!d) return null;
    const rect = this.svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const tol = 10;
    if (d.kind === 'hline') {
      // No endpoint handles beyond body move
      return null;
    }
    if (d.kind === 'text') {
      const c = this.toXY(d.p1);
      if (c && Math.hypot(x - c.x, y - c.y) <= tol) return { id: d.id, mode: 'p1' };
      return null;
    }
    const a = this.toXY(d.p1);
    const b = this.toXY(d.p2);
    if (a && Math.hypot(x - a.x, y - a.y) <= tol) return { id: d.id, mode: 'p1' };
    if (b && Math.hypot(x - b.x, y - b.y) <= tol) return { id: d.id, mode: 'p2' };
    return null;
  }

  private hitTest(e: MouseEvent): string | null {
    const rect = this.svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    // Reverse order (topmost last drawn)
    for (let i = this.drawings.length - 1; i >= 0; i--) {
      const d = this.drawings[i]!;
      if (this.nearDrawing(d, x, y, 8)) return d.id;
    }
    return null;
  }

  private nearDrawing(d: Drawing, x: number, y: number, tol: number): boolean {
    if (d.kind === 'hline') {
      const yy = this.series.priceToCoordinate(d.price);
      if (yy == null) return false;
      return Math.abs(y - yy) <= tol;
    }
    if (d.kind === 'text') {
      const c = this.toXY(d.p1);
      if (!c) return false;
      return Math.hypot(x - c.x, y - c.y) <= 16;
    }
    const a = this.toXY(d.p1);
    const b = this.toXY(d.p2);
    if (!a || !b) return false;
    if (d.kind === 'rect') {
      const minX = Math.min(a.x, b.x) - tol;
      const maxX = Math.max(a.x, b.x) + tol;
      const minY = Math.min(a.y, b.y) - tol;
      const maxY = Math.max(a.y, b.y) + tol;
      const inside = x >= minX && x <= maxX && y >= minY && y <= maxY;
      // Edge hit preferred
      const onEdge =
        Math.abs(x - minX) <= tol ||
        Math.abs(x - maxX) <= tol ||
        Math.abs(y - minY) <= tol ||
        Math.abs(y - maxY) <= tol;
      return inside && onEdge;
    }
    return distToSegment(x, y, a.x, a.y, b.x, b.y) <= tol;
  }

  private redraw() {
    this.syncSize();
    this.redrawScriptInner();
    this.redrawUserInner();
  }

  /** Full redraw (range/crosshair) — both layers. */
  private redrawScript() {
    this.syncSize();
    this.redrawScriptInner();
  }

  private redrawUser() {
    this.syncSize();
    this.redrawUserInner();
  }

  private redrawScriptInner() {
    // Build off-DOM then swap once to avoid a blank frame during live re-runs
    const next = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    next.setAttribute('class', 'axis-pine-drawings');
    for (const sd of this.scriptDrawings) {
      this.paintScriptDrawing(next, sd);
    }
    this.gScript.replaceWith(next);
    this.gScript = next;
  }

  private redrawUserInner() {
    const next = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    for (const d of this.drawings) {
      this.paintDrawing(next, d, d.id === this.selectedId);
    }
    this.gDraw.replaceWith(next);
    this.gDraw = next;
  }

  private paintScriptDrawing(g: SVGGElement, d: ScriptDrawing) {
    const pe = 'none'; // script drawings are view-only
    if (d.type === 'polyline' && d.points?.length) {
      const coords = d.points
        .map((p) => this.toXY({ time: p.time, price: p.price }))
        .filter(Boolean) as { x: number; y: number }[];
      if (coords.length < 2) return;
      let dPath = `M ${coords[0]!.x} ${coords[0]!.y}`;
      for (let i = 1; i < coords.length; i++) dPath += ` L ${coords[i]!.x} ${coords[i]!.y}`;
      if (d.closed) dPath += ' Z';
      el(g, 'path', {
        d: dPath,
        fill: d.closed ? d.bgcolor || 'rgba(147,159,255,0.06)' : 'none',
        stroke: d.color,
        'stroke-width': String(d.width || 1.5),
        'stroke-linejoin': 'round',
        'pointer-events': pe,
        ...(d.style === 'dashed' ? { 'stroke-dasharray': '4 3' } : {}),
      });
      return;
    }
    if (d.type === 'line' && d.t2 != null && d.p2 != null) {
      const a = this.toXY({ time: d.t1, price: d.p1 });
      const b = this.toXY({ time: d.t2, price: d.p2 });
      if (!a || !b) return;
      const ext = (d.extend || 'none').toLowerCase();
      const { x1, y1, x2, y2 } = extendSegment(a.x, a.y, b.x, b.y, ext, this.host.clientWidth, this.host.clientHeight);
      const dash =
        d.style === 'dashed' ? '4 3' : d.style === 'dotted' ? '1 3' : undefined;
      line(g, x1, y1, x2, y2, d.color, d.width || 1.5, dash, pe);
      return;
    }
    if (d.type === 'box' && d.t2 != null && d.p2 != null) {
      const a = this.toXY({ time: d.t1, price: d.p1 });
      const b = this.toXY({ time: d.t2, price: d.p2 });
      if (!a || !b) return;
      const x = Math.min(a.x, b.x);
      const y = Math.min(a.y, b.y);
      el(g, 'rect', {
        x: String(x),
        y: String(y),
        width: String(Math.abs(b.x - a.x)),
        height: String(Math.abs(b.y - a.y)),
        fill: d.bgcolor || 'rgba(147,159,255,0.08)',
        stroke: d.color,
        'stroke-width': String(d.width || 1),
        'pointer-events': pe,
      });
      if (d.text) label(g, x + 4, y + 12, d.text, d.color, 10);
      return;
    }
    if (d.type === 'label') {
      const c = this.toXY({ time: d.t1, price: d.p1 });
      if (!c) return;
      // Bubble
      const text = d.text || '';
      const pad = 4;
      const tw = Math.max(24, text.length * 6.5 + pad * 2);
      const th = 16;
      el(g, 'rect', {
        x: String(c.x - tw / 2),
        y: String(c.y - th - 6),
        width: String(tw),
        height: String(th),
        rx: '2',
        fill: d.color || '#939fff',
        stroke: '#0a0b10',
        'stroke-width': '1',
        'pointer-events': pe,
      });
      label(g, c.x, c.y - 10, text, d.textcolor || '#0a0b10', 10, 'middle');
      circle(g, c.x, c.y, 2.5, d.color || '#939fff');
    }
  }

  private paintDrawing(g: SVGGElement, d: Drawing, selected: boolean) {
    const stroke = d.color || DRAWING_COLORS.default;
    const sw = selected ? 2.5 : 1.5;
    const dash = selected ? '4 3' : undefined;

    if (d.kind === 'hline') {
      const y = this.series.priceToCoordinate(d.price);
      if (y == null) return;
      const w = this.host.clientWidth;
      line(g, 0, y, w, y, stroke, sw, dash, 'stroke');
      label(g, 6, y - 4, d.price.toFixed(2), stroke);
      if (selected) {
        // Mid handle for visual feedback
        circle(g, w / 2, y, 5, stroke, true);
      }
      return;
    }

    if (d.kind === 'text') {
      const c = this.toXY(d.p1);
      if (!c) return;
      label(g, c.x + 4, c.y - 4, d.text || '', stroke, 12);
      // anchor dot
      circle(g, c.x, c.y, selected ? 5 : 3, stroke, selected);
      return;
    }

    const a = this.toXY(d.p1);
    const b = this.toXY(d.p2);
    if (!a || !b) return;

    if (d.kind === 'trend' || d.kind === 'measure') {
      line(g, a.x, a.y, b.x, b.y, stroke, sw, dash);
      circle(g, a.x, a.y, selected ? 5 : 3, stroke, selected);
      circle(g, b.x, b.y, selected ? 5 : 3, stroke, selected);
      if (d.kind === 'measure') {
        const bars = Math.abs(
          barIndexApprox(this.chart, d.p1.time) - barIndexApprox(this.chart, d.p2.time),
        );
        const dPrice = d.p2.price - d.p1.price;
        const pct = d.p1.price !== 0 ? (dPrice / d.p1.price) * 100 : 0;
        const midX = (a.x + b.x) / 2;
        const midY = (a.y + b.y) / 2;
        label(
          g,
          midX + 6,
          midY - 6,
          `${dPrice >= 0 ? '+' : ''}${dPrice.toFixed(2)} (${pct.toFixed(2)}%) · ${bars} bars`,
          DRAWING_COLORS.measure,
          11,
        );
      }
      return;
    }

    if (d.kind === 'ray') {
      // Extend beyond p2 in the p1→p2 direction to the edge of the chart
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const w = this.host.clientWidth;
      const h = this.host.clientHeight;
      let extX = b.x;
      let extY = b.y;
      if (Math.abs(dx) > 0.001 || Math.abs(dy) > 0.001) {
        // Scale to far edge
        const scale = 5000 / Math.max(Math.hypot(dx, dy), 0.001);
        extX = a.x + dx * scale;
        extY = a.y + dy * scale;
        // Clamp roughly
        extX = Math.max(-w, Math.min(2 * w, extX));
        extY = Math.max(-h, Math.min(2 * h, extY));
      }
      line(g, a.x, a.y, extX, extY, stroke, sw, dash);
      circle(g, a.x, a.y, selected ? 5 : 3, stroke, selected);
      circle(g, b.x, b.y, selected ? 5 : 3, stroke, selected);
      return;
    }

    if (d.kind === 'rect') {
      const x = Math.min(a.x, b.x);
      const y = Math.min(a.y, b.y);
      const rw = Math.abs(b.x - a.x);
      const rh = Math.abs(b.y - a.y);
      el(g, 'rect', {
        x: String(x),
        y: String(y),
        width: String(rw),
        height: String(rh),
        fill: 'rgba(147, 159, 255, 0.08)',
        stroke,
        'stroke-width': String(sw),
        'pointer-events': 'all',
        ...(dash ? { 'stroke-dasharray': dash } : {}),
      });
      if (selected) {
        circle(g, a.x, a.y, 5, stroke, true);
        circle(g, b.x, b.y, 5, stroke, true);
      }
      return;
    }

    if (d.kind === 'fib') {
      const lo = Math.min(d.p1.price, d.p2.price);
      const hi = Math.max(d.p1.price, d.p2.price);
      const span = hi - lo || 1;
      const x1 = Math.min(a.x, b.x);
      const x2 = Math.max(a.x, b.x);
      const right = Math.max(x2, this.host.clientWidth - 8);
      for (const lvl of FIB_LEVELS) {
        // From high of range (standard retracement from p1 if p1 is high)
        const price =
          d.p1.price >= d.p2.price
            ? d.p1.price - span * lvl
            : d.p1.price + span * lvl;
        const y = this.series.priceToCoordinate(price);
        if (y == null) continue;
        line(g, x1, y, right, y, stroke, 1, lvl === 0.5 ? undefined : '3 3');
        label(g, right - 4, y - 3, `${(lvl * 100).toFixed(1)}%  ${price.toFixed(2)}`, stroke, 10, 'end');
      }
      // Vertical spine
      line(g, a.x, a.y, b.x, b.y, DRAWING_COLORS.muted, 1, '2 2');
    }
  }
}

type TwoPointKind = 'trend' | 'ray' | 'rect' | 'fib' | 'measure';

function el(
  parent: SVGElement,
  name: string,
  attrs: Record<string, string>,
): SVGElement {
  const node = document.createElementNS('http://www.w3.org/2000/svg', name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  parent.appendChild(node);
  return node;
}

function line(
  g: SVGElement,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  stroke: string,
  sw: number,
  dash?: string,
  pointerEvents = 'stroke',
) {
  el(g, 'line', {
    x1: String(x1),
    y1: String(y1),
    x2: String(x2),
    y2: String(y2),
    stroke,
    'stroke-width': String(Math.max(sw, 8)), // wider hit area
    'stroke-opacity': '0.01',
    'pointer-events': pointerEvents,
    'stroke-linecap': 'round',
  });
  // visible stroke on top
  el(g, 'line', {
    x1: String(x1),
    y1: String(y1),
    x2: String(x2),
    y2: String(y2),
    stroke,
    'stroke-width': String(sw),
    'stroke-linecap': 'round',
    'pointer-events': 'none',
    ...(dash ? { 'stroke-dasharray': dash } : {}),
  });
}

function circle(
  g: SVGElement,
  cx: number,
  cy: number,
  r: number,
  stroke: string,
  handle = false,
) {
  el(g, 'circle', {
    cx: String(cx),
    cy: String(cy),
    r: String(r),
    fill: handle ? '#0a0b10' : stroke,
    stroke: handle ? stroke : '#0a0b10',
    'stroke-width': handle ? '2' : '1',
    'pointer-events': 'auto',
    ...(handle ? { cursor: 'nwse-resize' } : {}),
  });
}

function extendSegment(
  ax: number,
  ay: number,
  bx: number,
  by: number,
  extend: string,
  w: number,
  h: number,
): { x1: number; y1: number; x2: number; y2: number } {
  const dx = bx - ax;
  const dy = by - ay;
  const len = Math.hypot(dx, dy) || 1;
  const scale = Math.max(w, h) * 4 / len;
  let x1 = ax;
  let y1 = ay;
  let x2 = bx;
  let y2 = by;
  if (extend === 'right' || extend === 'both') {
    x2 = bx + dx * scale;
    y2 = by + dy * scale;
  }
  if (extend === 'left' || extend === 'both') {
    x1 = ax - dx * scale;
    y1 = ay - dy * scale;
  }
  return { x1, y1, x2, y2 };
}

function resizeDrawing(origin: Drawing, mode: DragMode, pt: Point): Drawing {
  if (origin.kind === 'hline') {
    return { ...origin, price: pt.price };
  }
  if (origin.kind === 'text') {
    return { ...origin, p1: { ...pt } };
  }
  if (mode === 'p1') {
    return { ...origin, p1: { ...pt } };
  }
  if (mode === 'p2') {
    return { ...origin, p2: { ...pt } };
  }
  return origin;
}

function label(
  g: SVGElement,
  x: number,
  y: number,
  text: string,
  fill: string,
  size = 11,
  anchor: 'start' | 'end' | 'middle' = 'start',
) {
  const t = el(g, 'text', {
    x: String(x),
    y: String(y),
    fill,
    'font-size': String(size),
    'font-family': 'ui-monospace, SFMono-Regular, Menlo, monospace',
    'text-anchor': anchor,
    'pointer-events': 'none',
  });
  t.textContent = text;
}

function shiftDrawing(d: Drawing, dTime: number, dPrice: number): Drawing {
  if (d.kind === 'hline') {
    return { ...d, price: d.price + dPrice };
  }
  if (d.kind === 'text') {
    return {
      ...d,
      p1: { time: d.p1.time + dTime, price: d.p1.price + dPrice },
    };
  }
  return {
    ...d,
    p1: { time: d.p1.time + dTime, price: d.p1.price + dPrice },
    p2: { time: d.p2.time + dTime, price: d.p2.price + dPrice },
  };
}

function distToSegment(
  px: number,
  py: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  if (dx === 0 && dy === 0) return Math.hypot(px - x1, py - y1);
  const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

function barIndexApprox(chart: IChartApi, time: number): number {
  const c = chart.timeScale().timeToCoordinate(time as UTCTimestamp);
  if (c == null) return 0;
  const logical = chart.timeScale().coordinateToLogical(c);
  return logical ?? 0;
}

/** Pure helper for tests: fib prices between two endpoints */
export function fibPrices(p1: number, p2: number): number[] {
  const lo = Math.min(p1, p2);
  const hi = Math.max(p1, p2);
  const span = hi - lo || 1;
  const fromHigh = p1 >= p2;
  return FIB_LEVELS.map((lvl) => (fromHigh ? p1 - span * lvl : p1 + span * lvl));
}
