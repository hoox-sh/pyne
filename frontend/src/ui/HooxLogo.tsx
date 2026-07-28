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
 * HOOX geometric brand mark (from hoox-landing-page).
 * Pure SVG + CSS — no GSAP dependency.
 */

import { Component, JSX, onCleanup, onMount, splitProps } from 'solid-js';

export type HooxLogoSize = 'xs' | 'm' | 'l' | number;

const SIZE_PX: Record<'xs' | 'm' | 'l', number> = {
  xs: 14,
  m: 22,
  l: 40,
};

export function resolveLogoSize(size: HooxLogoSize = 'm'): number {
  return typeof size === 'number' ? size : SIZE_PX[size];
}

/** Shared geometric paths — order matches landing-page opposite pairs (1↔2, 3↔4) + center. */
export const HooxLogoPaths: Component<{ class?: string }> = (props) => (
  <g
    transform="matrix(2.2062294,0,0,2.2117592,-1506.9584,-1032.9513)"
    class={props.class}
    style={{ fill: 'currentColor' }}
  >
    {/* 0 — center interlocking form */}
    <path
      data-geom
      data-idx="0"
      d="m 1024.04,675.876 c 9.61,8.797 21.53,21.439 30.93,30.842 l 60.92,60.911 64.67,-64.663 119.79,-0.021 65.02,64.909 -65.07,65.008 -119.48,0.035 c -21.7,-21.207 -43.47,-43.36 -64.98,-64.832 l -91.24,91.236 c -5.86,-2.803 -80.868,-79.926 -92.266,-91.298 l -64.893,64.883 -119.277,-0.045 -65.117,-65.099 64.831,-64.765 119.814,-0.031 64.627,64.595 z"
    />
    {/* 1 — top-right arm */}
    <path
      data-geom
      data-idx="1"
      d="m 1232.94,467.045 92.02,10e-4 v 91.811 c -26.49,27.819 -56.93,57.065 -84.22,84.402 -24.41,1.422 -66.03,0.153 -92.08,0.169 l -0.01,-92.172 z"
    />
    {/* 2 — bottom-left arm (opposite of 1) */}
    <path
      data-geom
      data-idx="2"
      d="m 807.882,892.19 91.983,-0.005 -0.021,91.784 c -27.549,28.221 -56.511,56.651 -84.537,84.501 -29.899,0.53 -61.821,0.03 -91.855,0.03 l -0.006,-92.147 c 27.99,-28.21 56.136,-56.265 84.436,-84.163 z"
    />
    {/* 3 — top-left arm */}
    <path
      data-geom
      data-idx="3"
      d="m 723.569,467.027 91.556,0.002 c 28.133,26.948 57.059,56.938 84.669,84.614 l 0.052,91.703 -92.108,0.075 -84.298,-84.317 z"
    />
    {/* 4 — bottom-right accent edge (live path) */}
    <path
      data-geom
      data-accent
      data-idx="4"
      d="m 1148.68,892.158 91.71,-0.025 84.61,84.679 -0.01,91.668 c -30.37,0.36 -61.52,0.06 -91.94,0.09 l -84.38,-84.377 z"
      class="hoox-logo-accent"
    />
  </g>
);

export type HooxLogoProps = {
  size?: HooxLogoSize;
  /** Continuous CRT path flicker (loader mode). */
  animate?: boolean;
  /** One-shot hover flicker out→in (brand mark). Default true when not animating. */
  hoverFlicker?: boolean;
  class?: string;
  title?: string;
  'data-testid'?: string;
} & JSX.SvgSVGAttributes<SVGSVGElement>;

/**
 * CRT path-order flicker (port of landing `logo-flicker` opposite-pair stagger).
 * Uses CSS class toggles so we don't need GSAP.
 */
function runHoverFlicker(svg: SVGSVGElement): Promise<void> {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return Promise.resolve();
  }
  const paths = Array.from(svg.querySelectorAll<SVGPathElement>('path[data-geom]'));
  if (!paths.length) return Promise.resolve();

  // Opposite pairs like landing: [1,2] and [3,4], center 0 last out / first in
  const pairOrder = Math.random() > 0.5 ? ([0, 1] as const) : ([1, 0] as const);
  const pairs: [number, number][] = [
    [1, 2],
    [3, 4],
  ];
  const outOrder: number[] = [];
  for (const pi of pairOrder) {
    const [a, b] = pairs[pi]!;
    if (Math.random() > 0.5) outOrder.push(a, b);
    else outOrder.push(b, a);
  }
  outOrder.push(0);
  const inOrder = [0, ...outOrder.slice(0, -1).reverse()];

  // Slow CRT handoff (landing was ~46ms; keep ambient / readable)
  const STAGGER = 140;
  const FLASH = 70;
  const DIP = 110;
  const OFF = 180;

  const setOp = (el: SVGPathElement, o: number) => {
    el.style.opacity = String(o);
  };

  return new Promise((resolve) => {
    // Flicker out
    outOrder.forEach((idx, i) => {
      const p = paths[idx];
      if (!p) return;
      const t0 = i * STAGGER;
      window.setTimeout(() => setOp(p, 0.35), t0);
      window.setTimeout(() => setOp(p, 0.95), t0 + FLASH);
      window.setTimeout(() => setOp(p, 0.15), t0 + DIP);
      window.setTimeout(() => setOp(p, 0), t0 + OFF);
    });

    const outDone = outOrder.length * STAGGER + OFF + 80;
    window.setTimeout(() => {
      // Flicker in
      inOrder.forEach((idx, i) => {
        const p = paths[idx];
        if (!p) return;
        const t0 = i * STAGGER;
        window.setTimeout(() => setOp(p, 0.35), t0);
        window.setTimeout(() => setOp(p, 0.08), t0 + FLASH);
        window.setTimeout(() => setOp(p, 0.85), t0 + DIP);
        window.setTimeout(() => setOp(p, 1), t0 + OFF);
      });
      window.setTimeout(() => {
        for (const p of paths) {
          p.style.opacity = '';
        }
        resolve();
      }, inOrder.length * STAGGER + OFF + 100);
    }, outDone);
  });
}

export const HooxLogo: Component<HooxLogoProps> = (props) => {
  const [local, rest] = splitProps(props, [
    'size',
    'animate',
    'hoverFlicker',
    'class',
    'title',
    'data-testid',
  ]);
  let svgEl: SVGSVGElement | undefined;
  let flickering = false;

  const px = () => resolveLogoSize(local.size ?? 'm');
  const hoverOn = () => local.hoverFlicker ?? !local.animate;

  const onEnter = () => {
    if (!hoverOn() || !svgEl || flickering || local.animate) return;
    flickering = true;
    void runHoverFlicker(svgEl).finally(() => {
      flickering = false;
    });
  };

  onMount(() => {
    // ensure clean styles
  });
  onCleanup(() => {
    flickering = false;
  });

  return (
    <svg
      ref={(el) => {
        svgEl = el;
      }}
      viewBox="0 0 1505.3611 1330.7858"
      width={px()}
      height={px()}
      class={`hoox-logo block shrink-0 ${local.animate ? 'hoox-logo--loader' : ''} ${local.class || ''}`}
      role="img"
      aria-label={local.title || 'HOOX'}
      data-testid={local['data-testid'] || 'hoox-logo'}
      data-size={typeof local.size === 'string' ? local.size : undefined}
      onMouseEnter={onEnter}
      {...rest}
    >
      <title>{local.title || 'HOOX'}</title>
      <HooxLogoPaths />
    </svg>
  );
};
