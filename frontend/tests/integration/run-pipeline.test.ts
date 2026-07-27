/**
 * Engine active path → runScript with mocked /run.
 */

import '../setup';
import { describe, expect, it, beforeEach, afterEach } from 'bun:test';
import { mockFetch, jsonResponse } from '../helpers/mock-fetch';
import { registry } from '../../src/plugins/registry';
import { ensureBuiltins, _resetBootstrapFlag } from '../../src/plugins/bootstrap';
import { _resetSourceRegistrationFlag } from '../../src/sources/catalog';
import { _resetStreamRegistrationFlag } from '../../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../../src/engines/catalog';
import { _resetStorageRegistrationFlag } from '../../src/storage/catalog';
import { setStore, setActivePlugin, clearLogs } from '../../src/store';
import { runScript } from '../../src/indicators/runner';
import { SAMPLE_BARS } from '../fixtures/bars';

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
  setActivePlugin('engine', 'server');
});

afterEach(() => {
  restoreFetch?.();
  restoreFetch = null;
});

describe('run pipeline', () => {
  it('server engine success via runScript', async () => {
    restoreFetch = mockFetch(async (input) => {
      expect(String(input)).toContain('run.test:5002');
      return jsonResponse({
        status: 'success',
        plots: SAMPLE_BARS.map((_, i) => i),
        series: {},
        events: [],
        meta: { script_name: 'demo', overlay: true },
      });
    });
    const r = await runScript('//@version=5\nindicator("t")\nplot(close)', { silent: true });
    expect(r.status).toBe('success');
    expect(r.plots.length).toBe(SAMPLE_BARS.length);
  });

  it('server engine error path', async () => {
    restoreFetch = mockFetch(async () =>
      jsonResponse({ status: 'error', message: 'parse error' }, 400),
    );
    const r = await runScript('bad', { silent: true });
    expect(r.status).toBe('error');
    expect(r.error).toMatch(/parse error|HTTP/);
  });
});
