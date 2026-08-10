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

/**
 * Small parity smoke: pine-worker series offsets vs Python Runtime SoT.
 *
 * Documents expected offsets from:
 *   - pynescript.runtime.series.PineSeries.__getitem__
 *       "series[0] is current, series[1] is previous"
 *   - pynescript.ast.evaluator.series_buffer module docstring
 *       series[0] current / series[1] one bar ago / OOB+negative → na
 *
 * Not a full Runtime port — series polarity + one synthetic-bar e2e only.
 */

import { describe, expect, test } from "bun:test";

import { Evaluator } from "../src/evaluator/evaluator";
import { PineSeries } from "../src/evaluator/series";
import { NA } from "../src/evaluator/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function lit(value: any) {
  return { type: "Literal", value };
}

function id(name: string) {
  return { type: "Identifier", name };
}

/** AST for `close[offset]` */
function closeAt(offset: number) {
  return {
    type: "Subscript",
    value: id("close"),
    index: lit(offset),
  };
}

// ---------------------------------------------------------------------------
// SoT offset contract (matches Python comments)
// ---------------------------------------------------------------------------

describe("Python SoT series offset contract", () => {
  // Chronological host array (oldest first) — pine-worker simulation layout.
  // Python RingPineSeries / ChronologicalSeriesBuffer use the same offset
  // meaning even when storage is newest-first vs oldest-first.
  const closes = [10, 20, 30, 40, 50];
  const series = new PineSeries("close", closes);

  test("series[0] is current bar (runtime.series / series_buffer)", () => {
    // Python: "series[0] is current"
    const bar = 3; // value 40
    expect(series.get(0, bar)).toBe(40);
    expect(series.get(0, bar)).toBe(closes[bar]);
  });

  test("series[1] is previous bar (one bar ago)", () => {
    // Python: "series[1] is previous" / "one bar ago"
    const bar = 3;
    expect(series.get(1, bar)).toBe(30);
    expect(series.get(1, bar)).toBe(closes[bar - 1]);
  });

  test("series[n] is n bars ago", () => {
    const bar = 4; // 50
    expect(series.get(2, bar)).toBe(30); // 2 bars ago
    expect(series.get(4, bar)).toBe(10); // first bar
  });

  test("OOB / negative offsets → na (never invent 0)", () => {
    // Python series_buffer: "OOB / negative / na → None (never invent 0)"
    expect(series.get(1, 0)).toBe(NA);
    expect(series.get(5, 4)).toBe(NA);
    expect(series.get(-1, 2)).toBe(NA);
    // Soft-fail must not return 0 as a fake price
    expect(series.get(-1, 2)).not.toBe(0);
    expect(series.get(99, 0)).not.toBe(0);
  });
});

// ---------------------------------------------------------------------------
// End-to-end: evaluator over synthetic bars
// ---------------------------------------------------------------------------

describe("Evaluator series smoke (synthetic bars)", () => {
  test("close[1] over bars matches previous close (Python polarity)", () => {
    // Bars: index 0..4 → closes 10,20,30,40,50
    const close = new PineSeries("close", [10, 20, 30, 40, 50]);
    const prevCloseExpr = closeAt(1);

    const expected = [NA, 10, 20, 30, 40];
    for (let bar = 0; bar < 5; bar++) {
      const eval_ = new Evaluator({ close, bar_index: bar });
      expect(eval_.visit(prevCloseExpr)).toBe(expected[bar]);
    }
  });

  test("close - close[1] change over synthetic bars", () => {
    const close = new PineSeries("close", [10, 20, 30, 40, 50]);
    // AST: close[0] - close[1]  (current minus previous)
    const changeExpr = {
      type: "BinOp",
      left: closeAt(0),
      op: "-",
      right: closeAt(1),
    };

    // bar0: 10 - na → na; bar1: 20-10=10; bar2: 30-20=10; ...
    const eval_ = new Evaluator({ close, bar_index: 0 });
    expect(eval_.visit(changeExpr)).toBe(NA);

    for (let bar = 1; bar < 5; bar++) {
      eval_.context.bar_index = bar;
      expect(eval_.visit(changeExpr)).toBe(10);
    }
  });

  test("sma-like for-to sum of close[i] lookbacks on one bar", () => {
    // At bar 4 (close=50), SMA-3 style: (close[0]+close[1]+close[2]) / 3
    // = (50+40+30)/3 = 40 — same offset polarity as Python history refs.
    const close = new PineSeries("close", [10, 20, 30, 40, 50]);
    const length = 3;
    const bar = 4;

    // sum = 0
    // for i = 0 to length-1
    //   sum := sum + close[i]
    // sum / length
    const ast = {
      type: "Script",
      body: [
        {
          type: "Assign",
          targets: [id("sum")],
          value: lit(0),
          mode: null,
        },
        {
          type: "ForTo",
          target: id("i"),
          start: lit(0),
          end: lit(length - 1),
          step: lit(1),
          body: [
            {
              type: "ReAssign",
              target: id("sum"),
              value: {
                type: "BinOp",
                left: id("sum"),
                op: "+",
                right: {
                  type: "Subscript",
                  value: id("close"),
                  index: id("i"),
                },
              },
            },
          ],
        },
        {
          type: "Expr",
          value: {
            type: "BinOp",
            left: id("sum"),
            op: "/",
            right: lit(length),
          },
        },
      ],
    };

    const eval_ = new Evaluator({ close, bar_index: bar });
    expect(eval_.visit(ast)).toBe(40);
  });
});
