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

export type DrawingChangeHandler = (drawings: Drawing[]) => void;

/** Active layer singleton for toolbar / external callers (avoids ChartHost cycles). */
let activeLayer: DrawingLayer | null = null;

export function getActiveDrawingLayer(): DrawingLayer | null {
  return activeLayer;
}

function uid(): string {
  return `dw_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}

export class DrawingLayer {
  private host: HTMLElement;
  private chart: IChartApi;
  private series: ISeriesApi<'Candlestick'>;
  private svg: SVGSVGElement;
  private gDraw: SVGGElement;
  private gDraft: SVGGElement;
  private tool: DrawingToolId = 'cursor';
  private drawings: Drawing[] = [];
  private selectedId: string | null = null;
  private draft: { tool: DrawingToolId; p1?: Point; p2?: Point } | null = null;
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
      pointerEvents: 'none',
      overflow: 'hidden',
    } as CSSStyleDeclaration);

    this.gDraw = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    this.gDraft = document.createElementNS('http://www.w3.org/2000/svg', 'g');
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
    this.gDraft.innerHTML = '';
    this.svg.style.pointerEvents = tool === 'cursor' ? 'none' : 'auto';
    this.svg.style.cursor = tool === 'cursor' ? 'default' : 'crosshair';
    this.redraw();
  }

  getTool(): DrawingToolId {
    return this.tool;
  }

  setDrawings(drawings: Drawing[]) {
    this.drawings = drawings.slice();
    this.redraw();
  }

  getDrawings(): Drawing[] {
    return this.drawings.slice();
  }

  clearAll() {
    this.drawings = [];
    this.selectedId = null;
    this.draft = null;
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
    const onKey = (e: KeyboardEvent) => this.handleKey(e);
    const onCtx = (e: Event) => {
      if (this.tool !== 'cursor') {
        e.preventDefault();
        this.draft = null;
        this.gDraft.innerHTML = '';
      }
    };

    this.svg.addEventListener('click', onClick);
    this.svg.addEventListener('pointermove', onMove);
    this.svg.addEventListener('contextmenu', onCtx);
    window.addEventListener('keydown', onKey);
    this.unsubs.push(() => this.svg.removeEventListener('click', onClick));
    this.unsubs.push(() => this.svg.removeEventListener('pointermove', onMove));
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

  private handleClick(e: MouseEvent) {
    if (this.tool === 'cursor') {
      // Hit-test select
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
    this.gDraw.innerHTML = '';
    for (const d of this.drawings) {
      this.paintDrawing(this.gDraw, d, d.id === this.selectedId);
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
      line(g, 0, y, w, y, stroke, sw, dash);
      label(g, 6, y - 4, d.price.toFixed(2), stroke);
      return;
    }

    if (d.kind === 'text') {
      const c = this.toXY(d.p1);
      if (!c) return;
      label(g, c.x + 4, c.y - 4, d.text || '', stroke, 12);
      // anchor dot
      circle(g, c.x, c.y, selected ? 4 : 3, stroke);
      return;
    }

    const a = this.toXY(d.p1);
    const b = this.toXY(d.p2);
    if (!a || !b) return;

    if (d.kind === 'trend' || d.kind === 'measure') {
      line(g, a.x, a.y, b.x, b.y, stroke, sw, dash);
      circle(g, a.x, a.y, 3, stroke);
      circle(g, b.x, b.y, 3, stroke);
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
      circle(g, a.x, a.y, 3, stroke);
      circle(g, b.x, b.y, 3, stroke);
      return;
    }

    if (d.kind === 'rect') {
      const x = Math.min(a.x, b.x);
      const y = Math.min(a.y, b.y);
      const rw = Math.abs(b.x - a.x);
      const rh = Math.abs(b.y - a.y);
      const r = el(g, 'rect', {
        x: String(x),
        y: String(y),
        width: String(rw),
        height: String(rh),
        fill: 'rgba(147, 159, 255, 0.08)',
        stroke,
        'stroke-width': String(sw),
        ...(dash ? { 'stroke-dasharray': dash } : {}),
      });
      void r;
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
) {
  el(g, 'line', {
    x1: String(x1),
    y1: String(y1),
    x2: String(x2),
    y2: String(y2),
    stroke,
    'stroke-width': String(sw),
    'stroke-linecap': 'round',
    ...(dash ? { 'stroke-dasharray': dash } : {}),
  });
}

function circle(g: SVGElement, cx: number, cy: number, r: number, stroke: string) {
  el(g, 'circle', {
    cx: String(cx),
    cy: String(cy),
    r: String(r),
    fill: stroke,
    stroke: '#0a0b10',
    'stroke-width': '1',
  });
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
  });
  t.textContent = text;
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
