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
  FileJson,
  FileSpreadsheet,
  FolderOpen,
  List,
  Loader2,
  Moon,
  PanelRight,
  Play,
  Settings,
  Sun,
  Upload,
  X,
  ExternalLink,
  SquareArrowOutUpRight,
  ScrollText,
  Wifi,
  WifiOff,
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
