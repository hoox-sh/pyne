import { describe, expect, test } from "bun:test";

import { PineSeries } from "../src/evaluator/series";
import { NA } from "../src/evaluator/types";

function setup() {
  return new PineSeries("close", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
}

describe("PineSeries", () => {
  test("get(0, N) returns data[N] (current bar)", () => {
    const series = setup();
    // currentBar=5 → 6th element (0-indexed)
    expect(series.get(0, 5)).toBe(6);
    // currentBar=0 → 1st element
    expect(series.get(0, 0)).toBe(1);
    // currentBar=9 → 10th element (last)
    expect(series.get(0, 9)).toBe(10);
  });

  test("get(-N, currentBar) returns historical values", () => {
    const series = setup();
    expect(series.get(-1, 5)).toBe(5); // bar 4
    expect(series.get(-2, 5)).toBe(4); // bar 3
    expect(series.get(-4, 5)).toBe(2); // bar 1
    expect(series.get(-5, 5)).toBe(1); // bar 0 (first)
  });

  test("get(+N, currentBar) returns future values", () => {
    const series = setup();
    expect(series.get(1, 5)).toBe(7);  // bar 6
    expect(series.get(3, 5)).toBe(9);  // bar 8
    expect(series.get(4, 5)).toBe(10); // bar 9 (last)
  });

  test("out-of-bounds historical access returns NA", () => {
    const series = setup();
    // Trying to go before bar 0
    expect(series.get(-6, 5)).toBe(NA);  // would be index -1
    expect(series.get(-10, 0)).toBe(NA); // would be index -10
    // currentBar=0, offset=-1 → index -1
    expect(series.get(-1, 0)).toBe(NA);
  });

  test("out-of-bounds future access returns NA", () => {
    const series = setup();
    // Trying to go past the last bar
    expect(series.get(5, 5)).toBe(NA);  // would be index 10 (past end)
    expect(series.get(1, 9)).toBe(NA);  // would be index 10 (past end)
    expect(series.get(10, 0)).toBe(NA); // would be index 10
  });

  test("set() writes value at currentBar position", () => {
    const series = setup();
    series.set(42, 5);
    // get should reflect the new value
    expect(series.get(0, 5)).toBe(42);
    // other bars are unchanged
    expect(series.get(0, 4)).toBe(5);
    expect(series.get(0, 6)).toBe(7);
  });

  test("length property returns number of bars", () => {
    const series = setup();
    expect(series.length).toBe(10);

    const empty = new PineSeries("empty", []);
    expect(empty.length).toBe(0);
  });

  test("multiple series are independent", () => {
    const close = new PineSeries("close", [10, 20, 30]);
    const high = new PineSeries("high", [15, 25, 35]);

    expect(close.get(0, 1)).toBe(20);
    expect(high.get(0, 1)).toBe(25);

    // Mutating one does not affect the other
    close.set(99, 1);
    expect(close.get(0, 1)).toBe(99);
    expect(high.get(0, 1)).toBe(25);
  });

  test("values() returns a copy of the data", () => {
    const series = setup();
    const snapshot = series.values();

    // Snapshot matches data
    expect(snapshot).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);

    // Modifying the snapshot does not affect the series
    snapshot[0] = 999;
    expect(series.get(0, 0)).toBe(1);
  });

  test("name property reflects constructor arg", () => {
    const series = new PineSeries("volume", [100, 200]);
    expect(series.name).toBe("volume");
  });
});
