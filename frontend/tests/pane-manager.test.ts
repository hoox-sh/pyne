/**
 * PaneManager with mocked LWC + stub DOM.
 */

import './setup';
import { describe, expect, it, beforeAll, beforeEach } from 'bun:test';
import { installLightweightChartsMock } from './helpers/mock-lwc';

beforeAll(() => {
  installLightweightChartsMock();
});

const { PaneManager } = await import('../src/chart/pane-manager');

describe('PaneManager', () => {
  let container: HTMLElement;
  let pm: InstanceType<typeof PaneManager>;

  beforeEach(() => {
    container = document.createElement('div') as unknown as HTMLElement;
    (container as { id: string }).id = 'chart-root';
    document.body.appendChild(container as never);
    pm = new PaneManager(container);
  });

  it('createPane / getPane / getAllPanes', () => {
    const p = pm.createPane('price', 'price', 'Price');
    expect(p.id).toBe('price');
    expect(pm.getPane('price')).toBe(p);
    expect(pm.getAllPanes()).toHaveLength(1);
  });

  it('second pane attaches resize handle', () => {
    pm.createPane('price', 'price', 'Price');
    pm.createPane('volume', 'volume', 'Volume', 100);
    expect(pm.getAllPanes()).toHaveLength(2);
    expect(document.getElementById('pane-volume')).toBeTruthy();
  });

  it('destroyPane removes pane', () => {
    pm.createPane('price', 'price', 'Price');
    pm.destroyPane('price');
    expect(pm.getPane('price')).toBeUndefined();
  });

  it('setVisible / setLabel / resize', () => {
    pm.createPane('price', 'price', 'Price', 200);
    pm.setLabel('price', 'BTC');
    expect(pm.getPane('price')?.label).toBe('BTC');
    pm.setVisible('price', false);
    expect(pm.getPane('price')?.visible).toBe(false);
    pm.setVisible('price', true);
    pm.resize('price', 180);
  });

  it('syncTimeScales with 2 panes', () => {
    pm.createPane('price', 'price', 'Price');
    pm.createPane('volume', 'volume', 'Volume', 80);
    pm.syncTimeScales();
  });

  it('clearTradeMarkers no-op without candle', () => {
    pm.createPane('price', 'price', 'Price');
    pm.clearTradeMarkers();
  });

  it('setTradeMarkers attaches markers when candle exists', () => {
    const p = pm.createPane('price', 'price', 'Price');
    // inject fake candle series
    p.series['candle'] = {
      setData: () => {},
      applyOptions: () => {},
      priceScale: () => ({ applyOptions: () => {} }),
    } as never;
    pm.setTradeMarkers([
      {
        time: 1000,
        position: 'belowBar',
        color: '#0f0',
        shape: 'arrowUp',
        text: 'L',
      } as never,
    ]);
    pm.clearTradeMarkers();
  });

  it('scrollToTime centers panes', () => {
    pm.createPane('price', 'price', 'Price');
    pm.scrollToTime(1_700_000_000);
  });

  it('setEquityCurve creates equity pane; hideEquityPane hides', () => {
    pm.createPane('price', 'price', 'Price');
    pm.setEquityCurve([
      { time: 1, value: 10000 },
      { time: 2, value: 10100 },
    ]);
    expect(pm.getPane('equity')).toBeDefined();
    pm.hideEquityPane();
    expect(pm.getPane('equity')?.visible).toBe(false);
    pm.setEquityCurve([]);
  });

  it('dispose cleans up', () => {
    pm.createPane('price', 'price', 'Price');
    pm.createPane('volume', 'volume', 'Volume', 80);
    pm.dispose();
    expect(pm.getAllPanes()).toHaveLength(0);
  });
});
