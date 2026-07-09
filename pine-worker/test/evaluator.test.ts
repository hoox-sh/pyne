import { describe, expect, test } from "bun:test";

import { Evaluator } from "../src/evaluator/evaluator";
import { NA, BreakSignal, ContinueSignal } from "../src/evaluator/types";
import type { BuiltinRegistry } from "../src/evaluator/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create a Literal AST node. */
function lit(value: any) {
  return { type: "Literal", value };
}

/** Create an Identifier AST node. */
function id(name: string) {
  return { type: "Identifier", name };
}

/** Create a Script node wrapping body statements. */
function script(body: any[]) {
  return { type: "Script", body };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Evaluator — Basic", () => {
  test("1. Script with literal expression", () => {
    const ast = script([{ type: "Expr", value: lit(42) }]);
    const eval_ = new Evaluator();
    expect(eval_.visit(ast)).toBe(42);
  });

  test("2. Variable assignment and lookup", () => {
    const ast = script([
      {
        type: "Assign",
        targets: [{ type: "Identifier", name: "x" }],
        value: lit(10),
        mode: null,
      },
      { type: "Expr", value: id("x") },
    ]);
    const eval_ = new Evaluator();
    expect(eval_.visit(ast)).toBe(10);
  });
});

describe("Evaluator — Binary operations", () => {
  test("3a. BinOp addition", () => {
    const eval_ = new Evaluator();
    const result = eval_.visit({
      type: "BinOp",
      left: lit(3),
      op: "+",
      right: lit(4),
    });
    expect(result).toBe(7);
  });

  test("3b. BinOp subtraction", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: lit(10), op: "-", right: lit(3) })).toBe(7);
  });

  test("3c. BinOp multiplication", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: lit(6), op: "*", right: lit(7) })).toBe(42);
  });

  test("3d. BinOp division", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: lit(10), op: "/", right: lit(3) })).toBeCloseTo(3.333, 2);
  });

  test("3e. BinOp modulo", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: lit(10), op: "%", right: lit(3) })).toBe(1);
  });

  test("3f. BinOp with compound expression", () => {
    const eval_ = new Evaluator();
    const ast = {
      type: "BinOp",
      left: { type: "BinOp", left: lit(2), op: "*", right: lit(3) },
      op: "+",
      right: lit(1),
    };
    expect(eval_.visit(ast)).toBe(7); // (2 * 3) + 1
  });
});

describe("Evaluator — Unary operations", () => {
  test("4a. Unary minus", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "UnaryOp", op: "-", operand: lit(5) })).toBe(-5);
  });

  test("4b. Unary plus", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "UnaryOp", op: "+", operand: lit(3) })).toBe(3);
  });

  test("4c. Unary not", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "UnaryOp", op: "not", operand: lit(true) })).toBe(false);
    expect(eval_.visit({ type: "UnaryOp", op: "not", operand: lit(false) })).toBe(true);
  });

  test("4d. Double negation", () => {
    const eval_ = new Evaluator();
    const ast = {
      type: "UnaryOp",
      op: "-",
      operand: { type: "UnaryOp", op: "-", operand: lit(5) },
    };
    expect(eval_.visit(ast)).toBe(5);
  });
});

describe("Evaluator — Comparisons", () => {
  test("5a. Equality", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: lit(3), op: "==", right: lit(3) })).toBe(true);
    expect(eval_.visit({ type: "BinOp", left: lit(3), op: "==", right: lit(4) })).toBe(false);
  });

  test("5b. Inequality", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: lit(3), op: "!=", right: lit(4) })).toBe(true);
    expect(eval_.visit({ type: "BinOp", left: lit(3), op: "!=", right: lit(3) })).toBe(false);
  });

  test("5c. Less than / greater than", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: lit(1), op: "<", right: lit(2) })).toBe(true);
    expect(eval_.visit({ type: "BinOp", left: lit(2), op: "<", right: lit(1) })).toBe(false);
    expect(eval_.visit({ type: "BinOp", left: lit(2), op: ">", right: lit(1) })).toBe(true);
  });

  test("5d. Chained comparison via Compare node", () => {
    const eval_ = new Evaluator();
    // 1 < 5 < 10 → true
    const ast = {
      type: "Compare",
      left: lit(1),
      ops: ["<", "<"],
      comparators: [lit(5), lit(10)],
    };
    expect(eval_.visit(ast)).toBe(true);
  });

  test("5e. Chained comparison short-circuit", () => {
    const eval_ = new Evaluator();
    // 1 > 5 < 10 — first comparison false, short-circuit
    const ast = {
      type: "Compare",
      left: lit(1),
      ops: [">", "<"],
      comparators: [lit(5), lit(10)],
    };
    expect(eval_.visit(ast)).toBe(false);
  });
});

describe("Evaluator — Logical operators (and / or)", () => {
  test("BinOp 'and' short-circuits", () => {
    const eval_ = new Evaluator();
    let sideEffect = false;
    eval_.context["never"] = {
      type: "Literal",
      get value() {
        sideEffect = true;
        return 99;
      },
    };
    // false and <anything> → false (short-circuit, never evaluates right)
    const ast = {
      type: "BinOp",
      left: lit(false),
      op: "and",
      right: id("never"),
    };
    expect(eval_.visit(ast)).toBe(false);
    expect(sideEffect).toBe(false);
  });

  test("BinOp 'or' short-circuits", () => {
    const eval_ = new Evaluator();
    let sideEffect = false;
    eval_.context["never"] = {
      type: "Literal",
      get value() {
        sideEffect = true;
        return 99;
      },
    };
    // true or <anything> → true (short-circuit)
    const ast = {
      type: "BinOp",
      left: lit(true),
      op: "or",
      right: id("never"),
    };
    expect(eval_.visit(ast)).toBe(true);
    expect(sideEffect).toBe(false);
  });
});

describe("Evaluator — Function call", () => {
  test("6. Builtin function call via registry", () => {
    const registry: BuiltinRegistry = {
      call(name: string, args: any[], _kwargs: Record<string, any>) {
        if (name === "sma") {
          // Mock: return sum / count
          const sum = args.reduce((a: number, b: number) => a + b, 0);
          return sum / args.length;
        }
        return NA;
      },
      isRegistered(name: string) {
        return name === "sma";
      },
    };

    const eval_ = new Evaluator({}, registry);
    const ast = {
      type: "Call",
      func: { type: "Identifier", name: "sma" },
      args: [lit(10), lit(20), lit(30)],
      kwargs: [],
    };
    expect(eval_.visit(ast)).toBe(20); // (10 + 20 + 30) / 3
  });

  test("6b. Direct callable function", () => {
    const eval_ = new Evaluator();
    eval_.context["double"] = (x: number) => x * 2;
    const ast = {
      type: "Call",
      func: id("double"),
      args: [lit(21)],
      kwargs: [],
    };
    expect(eval_.visit(ast)).toBe(42);
  });
});

describe("Evaluator — Attribute access", () => {
  test("7. Attribute access on object", () => {
    const eval_ = new Evaluator();
    eval_.context["strategy"] = { long: "long", short: "short" };
    const ast = {
      type: "Attribute",
      value: id("strategy"),
      attr: "long",
    };
    expect(eval_.visit(ast)).toBe("long");
  });

  test("7b. Attribute on missing value returns NA", () => {
    const eval_ = new Evaluator();
    const ast = {
      type: "Attribute",
      value: lit(null),
      attr: "something",
    };
    expect(eval_.visit(ast)).toBe(NA);
  });

  test("7c. Attribute on NA returns NA", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "Attribute", value: id("missing"), attr: "foo" })).toBe(NA);
  });
});

describe("Evaluator — Subscript", () => {
  test("Subscript access", () => {
    const eval_ = new Evaluator();
    eval_.context["arr"] = [10, 20, 30];
    const ast = {
      type: "Subscript",
      value: id("arr"),
      index: lit(1),
    };
    expect(eval_.visit(ast)).toBe(20);
  });

  test("Subscript on null returns NA", () => {
    const eval_ = new Evaluator();
    const ast = {
      type: "Subscript",
      value: lit(null),
      index: lit(0),
    };
    expect(eval_.visit(ast)).toBe(NA);
  });
});

describe("Evaluator — If/else statement", () => {
  test("8a. If true executes body", () => {
    const eval_ = new Evaluator();
    const ast = script([
      {
        type: "Assign",
        targets: [id("x")],
        value: lit(0),
        mode: null,
      },
      {
        type: "If",
        test: lit(true),
        body: [
          {
            type: "Assign",
            targets: [id("x")],
            value: lit(1),
            mode: null,
          },
        ],
        orelse: [],
      },
      { type: "Expr", value: id("x") },
    ]);
    expect(eval_.visit(ast)).toBe(1);
  });

  test("8b. If false executes orelse", () => {
    const eval_ = new Evaluator();
    const ast = script([
      {
        type: "Assign",
        targets: [id("x")],
        value: lit(0),
        mode: null,
      },
      {
        type: "If",
        test: lit(false),
        body: [
          {
            type: "Assign",
            targets: [id("x")],
            value: lit(1),
            mode: null,
          },
        ],
        orelse: [
          {
            type: "Assign",
            targets: [id("x")],
            value: lit(2),
            mode: null,
          },
        ],
      },
      { type: "Expr", value: id("x") },
    ]);
    expect(eval_.visit(ast)).toBe(2);
  });

  test("8c. Conditional expression (ternary)", () => {
    const eval_ = new Evaluator();
    const ast = {
      type: "Conditional",
      test: lit(true),
      body: lit("yes"),
      orelse: lit("no"),
    };
    expect(eval_.visit(ast)).toBe("yes");
  });
});

describe("Evaluator — For-to loop", () => {
  test("9. For-to numeric range loop", () => {
    const eval_ = new Evaluator();
    const ast = script([
      {
        type: "Assign",
        targets: [id("sum")],
        value: lit(0),
        mode: null,
      },
      {
        type: "ForTo",
        target: id("i"),
        start: lit(1),
        end: lit(5),
        step: lit(1),
        body: [
          {
            type: "ReAssign",
            target: id("sum"),
            value: {
              type: "BinOp",
              left: id("sum"),
              op: "+",
              right: id("i"),
            },
          },
        ],
      },
      { type: "Expr", value: id("sum") },
    ]);
    // sum = 0 + 1 + 2 + 3 + 4 + 5 = 15
    expect(eval_.visit(ast)).toBe(15);
  });
});

describe("Evaluator — For-in loop", () => {
  test("For-in iterates over array", () => {
    const eval_ = new Evaluator();
    eval_.context["items"] = [10, 20, 30];
    const ast = script([
      {
        type: "Assign",
        targets: [id("sum")],
        value: lit(0),
        mode: null,
      },
      {
        type: "For",
        var: id("x"),
        iter: id("items"),
        body: [
          {
            type: "ReAssign",
            target: id("sum"),
            value: {
              type: "BinOp",
              left: id("sum"),
              op: "+",
              right: id("x"),
            },
          },
        ],
      },
      { type: "Expr", value: id("sum") },
    ]);
    expect(eval_.visit(ast)).toBe(60);
  });
});

describe("Evaluator — While loop with break/continue", () => {
  test("While loop with break", () => {
    const eval_ = new Evaluator();
    const ast = script([
      {
        type: "Assign",
        targets: [id("i")],
        value: lit(0),
        mode: null,
      },
      {
        type: "While",
        test: lit(true),
        body: [
          {
            type: "ReAssign",
            target: id("i"),
            value: {
              type: "BinOp",
              left: id("i"),
              op: "+",
              right: lit(1),
            },
          },
          {
            type: "If",
            test: {
              type: "BinOp",
              left: id("i"),
              op: ">=",
              right: lit(5),
            },
            body: [{ type: "Break" }],
            orelse: [],
          },
        ],
      },
      { type: "Expr", value: id("i") },
    ]);
    expect(eval_.visit(ast)).toBe(5);
  });

  test("Continue skips to next iteration", () => {
    const eval_ = new Evaluator();

    // For-to: sum only even numbers from 1 to 5
    const ast = script([
      {
        type: "Assign",
        targets: [id("sum")],
        value: lit(0),
        mode: null,
      },
      {
        type: "ForTo",
        target: id("i"),
        start: lit(1),
        end: lit(5),
        step: lit(1),
        body: [
          {
            // Skip odd numbers
            type: "If",
            test: {
              type: "BinOp",
              left: id("i"),
              op: "%",
              right: lit(2),
            },
            body: [{ type: "Continue" }],
            orelse: [],
          },
          {
            type: "ReAssign",
            target: id("sum"),
            value: {
              type: "BinOp",
              left: id("sum"),
              op: "+",
              right: id("i"),
            },
          },
        ],
      },
      { type: "Expr", value: id("sum") },
    ]);
    // 2 + 4 = 6
    expect(eval_.visit(ast)).toBe(6);
  });
});

describe("Evaluator — Var declaration", () => {
  test("10a. Var declaration executes on first bar (bar_index = 0)", () => {
    const eval_ = new Evaluator({ bar_index: 0 });
    const ast = script([
      {
        type: "Assign",
        targets: [id("x")],
        value: lit(100),
        mode: "var",
      },
      { type: "Expr", value: id("x") },
    ]);
    expect(eval_.visit(ast)).toBe(100);
  });

  test("10b. Var declaration skipped on subsequent bars", () => {
    const eval_ = new Evaluator({ bar_index: 5 });
    // Even without x in context, the var assignment is skipped
    const ast = script([
      {
        type: "Assign",
        targets: [id("x")],
        value: lit(100),
        mode: "var",
      },
      { type: "Expr", value: id("x") },
    ]);
    // x was not set because bar_index != 0, so lookup returns NA
    expect(eval_.visit(ast)).toBe(NA);
  });

  test("10c. Non-var assignment always executes regardless of bar_index", () => {
    const eval_ = new Evaluator({ bar_index: 5 });
    const ast = script([
      {
        type: "Assign",
        targets: [id("x")],
        value: lit(200),
        mode: null,
      },
      { type: "Expr", value: id("x") },
    ]);
    expect(eval_.visit(ast)).toBe(200);
  });
});

describe("Evaluator — Reassign (:=)", () => {
  test("11. ReAssign updates context", () => {
    const eval_ = new Evaluator();
    const ast = script([
      {
        type: "Assign",
        targets: [id("x")],
        value: lit(1),
        mode: null,
      },
      {
        type: "ReAssign",
        target: id("x"),
        value: { type: "BinOp", left: id("x"), op: "+", right: lit(1) },
      },
      { type: "Expr", value: id("x") },
    ]);
    expect(eval_.visit(ast)).toBe(2);
  });
});

describe("Evaluator — NA propagation", () => {
  test("12a. NA + number = NA", () => {
    const eval_ = new Evaluator();
    expect(
      eval_.visit({ type: "BinOp", left: id("undefined"), op: "+", right: lit(5) }),
    ).toBe(NA);
  });

  test("12b. number + NA = NA", () => {
    const eval_ = new Evaluator();
    expect(
      eval_.visit({ type: "BinOp", left: lit(5), op: "+", right: id("undefined") }),
    ).toBe(NA);
  });

  test("12c. NA - * / % = NA", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: "*", right: lit(2) })).toBe(NA);
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: "/", right: lit(2) })).toBe(NA);
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: "%", right: lit(2) })).toBe(NA);
  });

  test("12d. NA == x is always false", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: "==", right: lit(5) })).toBe(false);
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: "==", right: id("missing2") })).toBe(false);
  });

  test("12e. NA != x is always true", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: "!=", right: lit(5) })).toBe(true);
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: "!=", right: id("missing2") })).toBe(true);
  });

  test("12f. NA < x / > x / <= x / >= x is false", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: "<", right: lit(5) })).toBe(false);
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: ">", right: lit(5) })).toBe(false);
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: "<=", right: lit(5) })).toBe(false);
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: ">=", right: lit(5) })).toBe(false);
  });

  test("12g. Unary - on NA returns NA", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "UnaryOp", op: "-", operand: id("missing") })).toBe(NA);
  });

  test("12h. Missing identifier returns NA", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit(id("nonexistent"))).toBe(NA);
  });

  test("12i. not NA returns true (NA is falsy in Pine Script)", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "UnaryOp", op: "not", operand: id("missing") })).toBe(true);
  });

  test("12j. NA and true short-circuits to NA (NA is falsy)", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: "and", right: lit(true) })).toBe(NA);
  });

  test("12k. NA or true evaluates to true (NA is falsy, short-circuit evaluates right)", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "BinOp", left: id("missing"), op: "or", right: lit(true) })).toBe(true);
  });

  test("12l. Subscript on NA returns NA", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit({ type: "Subscript", value: id("missing"), index: lit(0) })).toBe(NA);
  });

  test("12m. If (na) executes orelse block", () => {
    const eval_ = new Evaluator();
    const ast = {
      type: "Script",
      body: [
        { type: "Assign", targets: [id("x")], value: lit("body"), mode: null },
        {
          type: "If",
          test: id("missing"),
          body: [
            { type: "ReAssign", target: id("x"), value: lit("executed") },
          ],
          orelse: [
            { type: "ReAssign", target: id("x"), value: lit("orelse") },
          ],
        },
        { type: "Expr", value: id("x") },
      ],
    };
    expect(new Evaluator().visit(ast)).toBe("orelse");
  });

  test("12n. While (na) does not enter loop body", () => {
    const eval_ = new Evaluator();
    eval_.context["x"] = 0;
    const ast = {
      type: "While",
      test: id("missing"),
      body: [
        { type: "ReAssign", target: id("x"), value: lit(99) },
      ],
    };
    eval_.visit(ast);
    expect(eval_.context["x"]).toBe(0);
  });
});

describe("Evaluator — Return", () => {
  test("Return evaluates and throws", () => {
    const eval_ = new Evaluator();
    expect(() => {
      eval_.visit({ type: "Return", value: lit(99) });
    }).toThrow();
  });
});

describe("Evaluator — Identifier fallback", () => {
  test("Undefined identifier returns NA", () => {
    const eval_ = new Evaluator();
    expect(eval_.visit(id("unknownVar"))).toBe(NA);
  });

  test("Defined identifier returns its value", () => {
    const eval_ = new Evaluator({ pi: 3.14 });
    expect(eval_.visit(id("pi"))).toBe(3.14);
  });
});

describe("Evaluator — Nested expression evaluation", () => {
  test("Complex arithmetic: (2 + 3) * (10 - 4) / 3 % 4", () => {
    const eval_ = new Evaluator();
    const ast = {
      type: "BinOp",
      left: {
        type: "BinOp",
        left: lit(2),
        op: "+",
        right: lit(3),
      },
      op: "*",
      right: {
        type: "BinOp",
        left: {
          type: "BinOp",
          left: lit(10),
          op: "-",
          right: lit(4),
        },
        op: "/",
        right: lit(3),
      },
    };
    // (2+3)*(10-4)/3 = 5*6/3 = 30/3 = 10... wait, the AST is:
    // (2+3) * ((10-4)/3) = 5 * (6/3) = 5*2 = 10
    expect(eval_.visit(ast)).toBe(10);
  });
});

describe("Evaluator — Mock builtin call with kwargs", () => {
  test("Builtin call with keyword arguments", () => {
    const registry: BuiltinRegistry = {
      call(name: string, _args: any[], kwargs: Record<string, any>) {
        if (name === "strategy.entry") {
          return `entry:${kwargs["id"] ?? "?"}:${kwargs["direction"] ?? "?"}`;
        }
        return NA;
      },
      isRegistered(name: string) {
        return name === "strategy.entry";
      },
    };

    const eval_ = new Evaluator({ strategy: "strategy" }, registry);
    const ast = {
      type: "Call",
      func: {
        type: "Attribute",
        value: id("strategy"),
        attr: "entry",
      },
      args: [],
      kwargs: [
        { name: "id", value: lit("buy") },
        { name: "direction", value: lit("long") },
      ],
    };
    expect(eval_.visit(ast)).toBe("entry:buy:long");
  });
});
