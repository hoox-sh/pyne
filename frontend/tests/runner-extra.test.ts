/**
 * Extra runner coverage (runAndApply without chart manager).
 */

import './setup';
import { describe, expect, it, beforeEach, afterEach } from 'bun:test';
import { mockFetch, jsonResponse } from './helpers/mock-fetch';
import { registry } from '../src/plugins/registry';
import { ensureBuiltins, _resetBootstrapFlag } from '../src/plugins/bootstrap';
import { _resetSourceRegistrationFlag } from '../src/sources/catalog';
import { _resetStreamRegistrationFlag } from '../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../src/engines/catalog';
import { _resetStorageRegistrationFlag } from '../src/storage/catalog';
import { setStore, setActivePlugin, clearLogs, store } from '../src/store';
import { runAndApply, probeEndpoint } from '../src/indicators/runner';
import { SAMPLE_BARS } from './fixtures/bars';

let restoreFetch: (() => void) | null = null;

beforeEach(() => {
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  ensureBuiltins();
  clearLogs();
  setStore('bars', SAMPLE_BARS);
  setStore('endpoint', 'http://run.test:5002');
  setStore('scripts', []);
  setStore('resultsPanel', { open: false, height: 220 });
  setActivePlugin('engine', 'server');
});

afterEach(() => {
  restoreFetch?.();
  restoreFetch = null;
});

describe('runAndApply', () => {
  it('opens results on success when no manager', async () => {
    restoreFetch = mockFetch(async () =>
      jsonResponse({
        status: 'success',
        plots: SAMPLE_BARS.map(() => 1),
        series: { s: SAMPLE_BARS.map(() => 2) },
        events: [],
        meta: { overlay: true, script_name: 'demo' },
      }),
    );
    const r = await runAndApply('plot(close)');
    expect(r.status).toBe('success');
    expect(store.resultsPanel.open).toBe(true);
    // Without a chart manager, overlays/indicators are skipped after result is stored
    expect(store.lastRun).toBeTruthy();
  });

  it('returns error without adding indicator', async () => {
    restoreFetch = mockFetch(async () =>
      jsonResponse({ status: 'error', message: 'nope' }, 500),
    );
    const before = store.scripts.length;
    const r = await runAndApply('bad', undefined, { openResults: false });
    expect(r.status).toBe('error');
    expect(store.scripts.length).toBe(before);
  });
});

describe('probeEndpoint', () => {
  it('ok on healthy json', async () => {
    restoreFetch = mockFetch(async () =>
      jsonResponse({ status: 'ok', endpoints: ['/run'] }),
    );
    const r = await probeEndpoint('http://run.test:5002');
    expect(r.ok).toBe(true);
  });

  it('fails on network', async () => {
    restoreFetch = mockFetch(async () => {
      throw new Error('down');
    });
    const r = await probeEndpoint('http://run.test:5002');
    expect(r.ok).toBe(false);
    expect(r.message).toMatch(/down/);
  });
});
