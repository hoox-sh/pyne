export interface Bar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface Pane {
  id: string;
  type: 'price' | 'volume' | 'indicator' | 'equity';
  height: number;
  order: number;
  visible: boolean;
  label?: string;
}

export interface Indicator {
  id: string;
  name: string;
  code: string;
  paneId: string;
  visible: boolean;
  plots: Record<string, { color: string }>;
}

export type AppStatus = 'ready' | 'loading' | 'running' | 'error' | 'connected' | 'disconnected';

export interface AppState {
  bars: Bar[];
  symbol: string;
  interval: string;
  exchange: string;
  engine: string;
  endpoint: string;

  scripts: Indicator[];
  panes: Pane[];

  live: {
    active: boolean;
    needsRerun: boolean;
    lastBarTime: number;
    streamId: string;
  };

  theme: 'dark' | 'light';
  editor: { open: boolean; width: number };
  indicatorPanel: { open: boolean };
  stream: { status: 'connected' | 'disconnected' | 'error' };
  status: AppStatus;
  statusMessage: string;
  lastRunMs: number | null;
}
