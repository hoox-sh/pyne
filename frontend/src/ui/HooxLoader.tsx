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
 * HOOX logo loader — CRT path flicker in three sizes (xs / m / l).
 * Effect inspired by hoox-landing-page logo-flicker + crt-flicker.
 */

import { Component, JSX, Show, splitProps } from 'solid-js';
import { HooxLogo, type HooxLogoSize, resolveLogoSize } from './HooxLogo';

export type HooxLoaderProps = {
  size?: HooxLogoSize;
  /** Optional caption under / beside the mark */
  label?: string;
  /** layout: icon only | row with label | stacked */
  layout?: 'icon' | 'inline' | 'stack';
  class?: string;
  'data-testid'?: string;
} & JSX.HTMLAttributes<HTMLSpanElement>;

export const HooxLoader: Component<HooxLoaderProps> = (props) => {
  const [local, rest] = splitProps(props, [
    'size',
    'label',
    'layout',
    'class',
    'data-testid',
  ]);
  const size = () => local.size ?? 'm';
  const layout = () => local.layout ?? (local.label ? 'inline' : 'icon');
  const px = () => resolveLogoSize(size());

  return (
    <span
      class={`hoox-loader inline-flex items-center justify-center gap-1.5 text-accent ${
        layout() === 'stack' ? 'flex-col gap-2' : ''
      } ${local.class || ''}`}
      role="status"
      aria-live="polite"
      aria-busy="true"
      data-testid={local['data-testid'] || 'hoox-loader'}
      data-size={typeof size() === 'string' ? size() : String(px())}
      {...rest}
    >
      <span
        class="hoox-loader-plate relative inline-flex items-center justify-center"
        style={{ width: `${px()}px`, height: `${px()}px` }}
      >
        <HooxLogo size={size()} animate hoverFlicker={false} class="hoox-loader-mark" />
        {/* soft phosphor glow ring */}
        <span class="hoox-loader-glow pointer-events-none absolute inset-0" aria-hidden="true" />
      </span>
      <Show when={local.label && layout() !== 'icon'}>
        <span
          class={`font-mono uppercase tracking-[0.18em] text-text-faint ${
            size() === 'xs' ? 'text-[9px]' : size() === 'l' ? 'text-[11px]' : 'text-[10px]'
          }`}
        >
          {local.label}
        </span>
      </Show>
      <span class="sr-only">{local.label || 'Loading'}</span>
    </span>
  );
};

/** Convenience aliases */
export const HooxLoaderXs: Component<Omit<HooxLoaderProps, 'size'>> = (p) => (
  <HooxLoader {...p} size="xs" />
);
export const HooxLoaderM: Component<Omit<HooxLoaderProps, 'size'>> = (p) => (
  <HooxLoader {...p} size="m" />
);
export const HooxLoaderL: Component<Omit<HooxLoaderProps, 'size'>> = (p) => (
  <HooxLoader {...p} size="l" />
);
