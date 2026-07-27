/**
 * HOOX logo size map + loader helpers.
 */

import { describe, expect, it } from 'bun:test';
import { resolveLogoSize } from '../src/ui/HooxLogo';

describe('resolveLogoSize', () => {
  it('maps xs / m / l to pixel sizes', () => {
    expect(resolveLogoSize('xs')).toBe(14);
    expect(resolveLogoSize('m')).toBe(22);
    expect(resolveLogoSize('l')).toBe(40);
  });

  it('accepts custom numeric sizes', () => {
    expect(resolveLogoSize(32)).toBe(32);
  });

  it('defaults to m when omitted via default param', () => {
    expect(resolveLogoSize()).toBe(22);
  });
});
