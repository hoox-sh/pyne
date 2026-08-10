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

import { NA } from "./types";

/**
 * PineSeries — Pine Script's historical bar access pattern.
 *
 * Matches Python SoT (`pynescript.runtime.series.PineSeries`) and TradingView:
 * offsets are **bars ago**, not signed array deltas.
 *
 *   series.get(0, currentBar)  → data[currentBar]           (current bar)  // series[0]
 *   series.get(1, currentBar)  → data[currentBar - 1]       (previous bar) // series[1]
 *   series.get(N, currentBar)  → data[currentBar - N]       (N bars ago)   // series[N]
 *
 * Negative offsets are invalid Pine history refs and return {@link NA}
 * (same soft-fail as Python Runtime). Out-of-range lookbacks also return NA.
 *
 * Since we run in simulation mode, all bar data is available upfront.  The
 * series wraps an array and translates Pine Script offsets into absolute
 * array lookups.
 */
export class PineSeries<T = any> {
  readonly name: string;
  private data: T[];

  constructor(name: string, data: T[]) {
    this.name = name;
    this.data = data;
  }

  /**
   * Get the value at a Pine history offset from the current bar.
   *
   * @param offset     Bars ago: 0 = current bar, 1 = previous bar, N = N bars ago.
   *                   Negative offsets are invalid and return NA.
   * @param currentBar Absolute index of the current bar being processed.
   * @returns The value at that position, or {@link NA} when the index is
   *          out of bounds or the offset is negative.
   */
  get(offset: number, currentBar: number): T | typeof NA {
    // Pine: series[n] is n bars back. Negative history refs → na (Python parity).
    if (offset < 0) {
      return NA;
    }
    const absoluteIndex = currentBar - offset;
    if (absoluteIndex < 0 || absoluteIndex >= this.data.length) {
      return NA;
    }
    return this.data[absoluteIndex];
  }

  /**
   * Set the value for the current bar (offset 0).
   * Used by mutable builtins such as `var` declarations.
   */
  set(value: T, currentBar: number): void {
    this.data[currentBar] = value;
  }

  /** Total number of bars in the series. */
  get length(): number {
    return this.data.length;
  }

  /** Snapshot of all data (for inspection / debug). */
  values(): T[] {
    return [...this.data];
  }
}
