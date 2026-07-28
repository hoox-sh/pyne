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

import {
  LiteralSchema,
  IdentifierSchema,
  BinOpSchema,
  UnaryOpSchema,
  CallSchema,
  AttributeSchema,
  SubscriptSchema,
  AssignSchema,
  ReAssignSchema,
  IfSchema,
  ForSchema,
  WhileSchema,
  ReturnSchema,
  ScriptSchema,
} from "../src/ast/types";

describe("LiteralSchema", () => {
  test("parses a string literal", () => {
    const result = LiteralSchema.parse({ type: "Literal", value: "hello" });
    expect(result).toEqual({ type: "Literal", value: "hello" });
  });

  test("parses a number literal", () => {
    const result = LiteralSchema.parse({ type: "Literal", value: 42 });
    expect(result).toEqual({ type: "Literal", value: 42 });
  });

  test("parses a boolean literal", () => {
    const result = LiteralSchema.parse({ type: "Literal", value: true });
    expect(result).toEqual({ type: "Literal", value: true });
  });

  test("parses a null literal", () => {
    const result = LiteralSchema.parse({ type: "Literal", value: null });
    expect(result).toEqual({ type: "Literal", value: null });
  });

  test("rejects missing type field", () => {
    expect(() => LiteralSchema.parse({ value: "hello" })).toThrow();
  });

  test("rejects wrong type field", () => {
    expect(() =>
      LiteralSchema.parse({ type: "NotLiteral", value: "hello" })
    ).toThrow();
  });

  test("rejects unknown value type", () => {
    expect(() => LiteralSchema.parse({ type: "Literal", value: {} })).toThrow();
  });
});

describe("IdentifierSchema", () => {
  test("parses a valid identifier", () => {
    const result = IdentifierSchema.parse({
      type: "Identifier",
      name: "close",
    });
    expect(result).toEqual({ type: "Identifier", name: "close" });
  });

  test("rejects missing name", () => {
    expect(() => IdentifierSchema.parse({ type: "Identifier" })).toThrow();
  });
});

describe("BinOpSchema", () => {
  test("parses a binary operation", () => {
    const result = BinOpSchema.parse({
      type: "BinOp",
      left: { type: "Literal", value: 1 },
      op: "+",
      right: { type: "Literal", value: 2 },
    });
    expect(result).toEqual({
      type: "BinOp",
      left: { type: "Literal", value: 1 },
      op: "+",
      right: { type: "Literal", value: 2 },
    });
  });

  test("rejects invalid operator", () => {
    expect(() =>
      BinOpSchema.parse({
        type: "BinOp",
        left: { type: "Literal", value: 1 },
        op: "**",
        right: { type: "Literal", value: 2 },
      })
    ).toThrow();
  });
});

describe("UnaryOpSchema", () => {
  test("parses a unary operation", () => {
    const result = UnaryOpSchema.parse({
      type: "UnaryOp",
      op: "not",
      operand: { type: "Literal", value: true },
    });
    expect(result).toEqual({
      type: "UnaryOp",
      op: "not",
      operand: { type: "Literal", value: true },
    });
  });
});

describe("CallSchema", () => {
  test("parses a function call with args", () => {
    const result = CallSchema.parse({
      type: "Call",
      func: { type: "Identifier", name: "sma" },
      args: [
        { type: "Identifier", name: "close" },
        { type: "Literal", value: 14 },
      ],
      kwargs: [],
    });
    expect(result.type).toBe("Call");
    expect(result.func).toEqual({ type: "Identifier", name: "sma" });
    expect(result.args).toHaveLength(2);
  });

  test("parses a function call with kwargs", () => {
    const result = CallSchema.parse({
      type: "Call",
      func: { type: "Identifier", name: "strategy" },
      args: [],
      kwargs: [{ name: "overwrite", value: { type: "Literal", value: true } }],
    });
    expect(result.kwargs).toHaveLength(1);
    expect(result.kwargs[0].name).toBe("overwrite");
  });
});

describe("AttributeSchema", () => {
  test("parses an attribute access", () => {
    const result = AttributeSchema.parse({
      type: "Attribute",
      value: { type: "Identifier", name: "close" },
      attr: "value",
    });
    expect(result).toEqual({
      type: "Attribute",
      value: { type: "Identifier", name: "close" },
      attr: "value",
    });
  });
});

describe("SubscriptSchema", () => {
  test("parses a subscript expression", () => {
    const result = SubscriptSchema.parse({
      type: "Subscript",
      value: { type: "Identifier", name: "array" },
      index: { type: "Literal", value: 0 },
    });
    expect(result).toEqual({
      type: "Subscript",
      value: { type: "Identifier", name: "array" },
      index: { type: "Literal", value: 0 },
    });
  });
});

describe("AssignSchema", () => {
  test("parses a var assignment", () => {
    const result = AssignSchema.parse({
      type: "Assign",
      targets: [{ type: "Identifier", name: "x" }],
      value: { type: "Literal", value: 10 },
      mode: "var",
    });
    expect(result).toEqual({
      type: "Assign",
      targets: [{ type: "Identifier", name: "x" }],
      value: { type: "Literal", value: 10 },
      mode: "var",
    });
  });

  test("parses an assignment with null mode", () => {
    const result = AssignSchema.parse({
      type: "Assign",
      targets: [{ type: "Identifier", name: "x" }],
      value: { type: "Literal", value: 1 },
      mode: null,
    });
    expect(result.mode).toBeNull();
  });

  test("rejects invalid mode", () => {
    expect(() =>
      AssignSchema.parse({
        type: "Assign",
        targets: [{ type: "Identifier", name: "x" }],
        value: { type: "Literal", value: 1 },
        mode: "const",
      })
    ).toThrow();
  });
});

describe("ReAssignSchema", () => {
  test("parses a reassignment", () => {
    const result = ReAssignSchema.parse({
      type: "ReAssign",
      target: { type: "Identifier", name: "x" },
      value: {
        type: "BinOp",
        left: { type: "Identifier", name: "x" },
        op: "+",
        right: { type: "Literal", value: 1 },
      },
    });
    expect(result.type).toBe("ReAssign");
  });
});

describe("IfSchema", () => {
  test("parses an if statement", () => {
    const result = IfSchema.parse({
      type: "If",
      test: { type: "Literal", value: true },
      body: [
        {
          type: "Assign",
          targets: [{ type: "Identifier", name: "x" }],
          value: { type: "Literal", value: 1 },
          mode: null,
        },
      ],
      orelse: [],
    });
    expect(result.type).toBe("If");
    expect(result.body).toHaveLength(1);
    expect(result.orelse).toHaveLength(0);
  });

  test("parses if-else with nested if", () => {
    const result = IfSchema.parse({
      type: "If",
      test: { type: "Literal", value: true },
      body: [],
      orelse: [
        {
          type: "If",
          test: { type: "Literal", value: false },
          body: [],
          orelse: [],
        },
      ],
    });
    expect(result.orelse).toHaveLength(1);
    expect(result.orelse[0].type).toBe("If");
  });
});

describe("ForSchema", () => {
  test("parses a for loop", () => {
    const result = ForSchema.parse({
      type: "For",
      var: { type: "Identifier", name: "i" },
      iter: {
        type: "Call",
        func: { type: "Identifier", name: "array" },
        args: [],
        kwargs: [],
      },
      body: [],
    });
    expect(result.type).toBe("For");
    expect(result.var.name).toBe("i");
  });
});

describe("WhileSchema", () => {
  test("parses a while loop", () => {
    const result = WhileSchema.parse({
      type: "While",
      test: { type: "Literal", value: true },
      body: [],
    });
    expect(result.type).toBe("While");
  });
});

describe("ReturnSchema", () => {
  test("parses a return with value", () => {
    const result = ReturnSchema.parse({
      type: "Return",
      value: { type: "Identifier", name: "x" },
    });
    expect(result).toEqual({
      type: "Return",
      value: { type: "Identifier", name: "x" },
    });
  });

  test("parses a return without value", () => {
    const result = ReturnSchema.parse({ type: "Return" });
    expect(result).toEqual({ type: "Return" });
    expect(result.value).toBeUndefined();
  });
});

describe("ScriptSchema (PineAST)", () => {
  test("parses an empty script", () => {
    const result = ScriptSchema.parse({ type: "Script", body: [] });
    expect(result).toEqual({ type: "Script", body: [] });
  });

  test("parses a full script with nested statements", () => {
    const script = {
      type: "Script",
      body: [
        {
          type: "Assign",
          targets: [{ type: "Identifier", name: "x" }],
          value: { type: "Literal", value: 10 },
          mode: "var",
        },
        {
          type: "If",
          test: {
            type: "BinOp",
            left: { type: "Identifier", name: "x" },
            op: ">",
            right: { type: "Literal", value: 5 },
          },
          body: [
            {
              type: "ReAssign",
              target: { type: "Identifier", name: "x" },
              value: {
                type: "BinOp",
                left: { type: "Identifier", name: "x" },
                op: "*",
                right: { type: "Literal", value: 2 },
              },
            },
          ],
          orelse: [
            {
              type: "Return",
              value: { type: "Literal", value: 0 },
            },
          ],
        },
      ],
    };

    const result = ScriptSchema.parse(script);
    expect(result.type).toBe("Script");
    expect(result.body).toHaveLength(2);
  });

  test("rejects script without type field", () => {
    expect(() => ScriptSchema.parse({ body: [] })).toThrow();
  });

  test("rejects script with wrong type", () => {
    expect(() => ScriptSchema.parse({ type: "NotScript", body: [] })).toThrow();
  });

  test("rejects invalid nested data", () => {
    expect(() =>
      ScriptSchema.parse({
        type: "Script",
        body: [
          {
            type: "Assign",
            targets: "not-an-array",
            value: { type: "Literal", value: 1 },
            mode: null,
          },
        ],
      })
    ).toThrow();
  });
});
