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
 * AXIS icon set — Lucide (https://lucide.dev)
 *
 * Why Lucide: tree-shakable stroke icons, consistent 24×24 grid, ISC license,
 * solid-js package (`lucide-solid`), strong default for modern UIs (shadcn, etc.).
 */

import type { Component, JSX } from 'solid-js';
import {
  Activity,
  AlertCircle,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Download,
  Eraser,
  FileJson,
  FileSpreadsheet,
  FolderOpen,
  List,
  Loader2,
  Minus,
  Moon,
  MousePointer2,
  PanelRight,
  Play,
  Ruler,
  Settings,
  Square,
  Sun,
  Trash2,
  TrendingUp,
  Type,
  Upload,
  X,
  ExternalLink,
  SquareArrowOutUpRight,
  ScrollText,
  Wifi,
  WifiOff,
  MoveUpRight,
  Layers,
  type LucideProps,
} from 'lucide-solid';

export type IconProps = LucideProps & { class?: string };

const defaults: Partial<LucideProps> = {
  size: 14,
  strokeWidth: 2,
  absoluteStrokeWidth: false,
};

function withDefaults(Icon: Component<LucideProps>): Component<IconProps> {
  return (props) => <Icon {...defaults} {...props} />;
}

export const Icons = {
  play: withDefaults(Play),
  settings: withDefaults(Settings),
  sun: withDefaults(Sun),
  moon: withDefaults(Moon),
  list: withDefaults(List),
  panelRight: withDefaults(PanelRight),
  upload: withDefaults(Upload),
  download: withDefaults(Download),
  copy: withDefaults(Copy),
  check: withDefaults(Check),
  x: withDefaults(X),
  chevronDown: withDefaults(ChevronDown),
  chevronUp: withDefaults(ChevronUp),
  externalLink: withDefaults(ExternalLink),
  popout: withDefaults(SquareArrowOutUpRight),
  fileJson: withDefaults(FileJson),
  fileCsv: withDefaults(FileSpreadsheet),
  folder: withDefaults(FolderOpen),
  loader: withDefaults(Loader2),
  alert: withDefaults(AlertCircle),
  activity: withDefaults(Activity),
  scrollText: withDefaults(ScrollText),
  wifi: withDefaults(Wifi),
  wifiOff: withDefaults(WifiOff),
  // Drawing tools
  cursor: withDefaults(MousePointer2),
  minus: withDefaults(Minus),
  trend: withDefaults(TrendingUp),
  ray: withDefaults(MoveUpRight),
  square: withDefaults(Square),
  fib: withDefaults(Layers),
  ruler: withDefaults(Ruler),
  type: withDefaults(Type),
  trash: withDefaults(Trash2),
  eraser: withDefaults(Eraser),
};

/** Inline icon row helper for buttons */
export function IconLabel(props: {
  icon: Component<IconProps>;
  children?: JSX.Element;
  class?: string;
}) {
  const I = props.icon;
  return (
    <span class={`inline-flex items-center gap-1.5 ${props.class || ''}`}>
      <I class="flex-shrink-0 opacity-90" />
      {props.children}
    </span>
  );
}
