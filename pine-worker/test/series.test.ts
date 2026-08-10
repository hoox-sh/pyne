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

import { describe, expect, test } from "bun:test";

import { PineSeries } from "../src/evaluator/series";
import { NA } from "../src/evaluator/types";

function setup() {
  // Chronological bar data: index 0 = oldest, index 9 = newest sample in array.
  // At currentBar=5, Pine series[0] → 6, series[1] → 5 (previous bar).
  return new PineSeries("close", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
}

describe("PineSeries", () => {
  test("get(0, N) returns data[N] (current bar) — Pine series[0]", () => {
    const series = setup();
    // currentBar=5 → 6th element (0-indexed)
    expect(series.get(0, 5)).toBe(6);
    // currentBar=0 → 1st element
    expect(series.get(0, 0)).toBe(1);
    // currentBar=9 → 10th element (last)
    expect(series.get(0, 9)).toBe(10);
  });

  test("get(+N, currentBar) returns historical values — Pine series[N] = N bars ago", () => {
    const series = setup();
    // Matches pynescript.runtime.series / TV: positive offset = lookback
    expect(series.get(1, 5)).toBe(5); // bar 4 — previous bar
    expect(series.get(2, 5)).toBe(4); // bar 3
    expect(series.get(4, 5)).toBe(2); // bar 1
    expect(series.get(5, 5)).toBe(1); // bar 0 (first)
  });

  test("Pine series[1] is previous bar (SoT polarity)", () => {
    // Explicit parity with Python Runtime: series[0] current, series[1] previous.
    const series = new PineSeries("close", [10, 20, 30, 40]);
    const bar = 2; // value 30 is current
    expect(series.get(0, bar)).toBe(30);
    expect(series.get(1, bar)).toBe(20);
    expect(series.get(2, bar)).toBe(10);
    expect(series.get(3, bar)).toBe(NA); // beyond available history
  });

  test("negative offsets return NA (invalid Pine history refs)", () => {
    const series = setup();
    // Python Runtime soft-fails negative offsets to na
    expect(series.get(-1, 5)).toBe(NA);
    expect(series.get(-2, 5)).toBe(NA);
    expect(series.get(-1, 0)).toBe(NA);
    expect(series.get(-10, 0)).toBe(NA);
  });

  test("out-of-bounds lookback returns NA", () => {
    const series = setup();
    // currentBar=5, offset=6 → absolute index -1
    expect(series.get(6, 5)).toBe(NA);
    // currentBar=0, offset=1 → before first bar
    expect(series.get(1, 0)).toBe(NA);
    expect(series.get(10, 0)).toBe(NA);
  });

  test("set() writes value at currentBar position", () => {
    const series = setup();
    series.set(42, 5);
    // get should reflect the new value
    expect(series.get(0, 5)).toBe(42);
    // other bars are unchanged
    expect(series.get(0, 4)).toBe(5);
    expect(series.get(0, 6)).toBe(7);
    // previous-bar lookback from bar 6 sees the set value
    expect(series.get(1, 6)).toBe(42);
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
    expect(close.get(1, 1)).toBe(10); // previous close
    expect(high.get(1, 1)).toBe(15); // previous high

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
