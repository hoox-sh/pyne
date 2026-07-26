import { describe, expect, it } from 'bun:test';
import { FIB_LEVELS, needsTwoPoints, toolLabel } from '../src/chart/drawing-types.ts';
import { fibPrices as computeFib } from '../src/chart/drawing-layer.ts';

describe('drawing tools helpers', () => {
  it('needsTwoPoints for multi-click tools', () => {
    expect(needsTwoPoints('hline')).toBe(false);
    expect(needsTwoPoints('text')).toBe(false);
    expect(needsTwoPoints('cursor')).toBe(false);
    expect(needsTwoPoints('trend')).toBe(true);
    expect(needsTwoPoints('ray')).toBe(true);
    expect(needsTwoPoints('rect')).toBe(true);
    expect(needsTwoPoints('fib')).toBe(true);
    expect(needsTwoPoints('measure')).toBe(true);
  });

  it('toolLabel covers all tools', () => {
    expect(toolLabel('hline')).toMatch(/Horizontal/i);
    expect(toolLabel('fib')).toMatch(/Fib/i);
  });

  it('fibPrices from high to low (retracement)', () => {
    const levels = computeFib(100, 0);
    expect(levels).toHaveLength(FIB_LEVELS.length);
    expect(levels[0]).toBeCloseTo(100); // 0%
    expect(levels[levels.length - 1]).toBeCloseTo(0); // 100%
    expect(levels[3]).toBeCloseTo(50); // 50%
  });

  it('fibPrices from low to high', () => {
    const levels = computeFib(0, 100);
    expect(levels[0]).toBeCloseTo(0);
    expect(levels[levels.length - 1]).toBeCloseTo(100);
  });
});
