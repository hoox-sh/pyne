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

import {
  NA,
  BreakSignal,
  ContinueSignal,
  ReturnSignal,
} from "./types";
import type { VisitorFn, BuiltinRegistry } from "./types";

// ---------------------------------------------------------------------------
// NA helpers
// ---------------------------------------------------------------------------

/** True when `v` is the Pine Script NA sentinel. */
function isNA(v: any): boolean {
  return v === NA;
}

/**
 * Wrapper for arithmetic binary ops: if either operand is NA, return NA.
 * Otherwise coerce both to numbers and apply `fn`.
 */
function withArithNA(
  a: any,
  b: any,
  fn: (x: number, y: number) => number,
): any {
  if (isNA(a) || isNA(b)) return NA;
  return fn(Number(a), Number(b));
}

/**
 * Wrapper for numeric comparisons: if either operand is NA, return false.
 * This matches Pine Script semantics — na compared with anything is false.
 */
function withCmpNA(
  a: any,
  b: any,
  fn: (x: number, y: number) => boolean,
): boolean {
  if (isNA(a) || isNA(b)) return false;
  return fn(Number(a), Number(b));
}

/** Equality that returns false when either side is NA (Pine Script semantics). */
function naSafeEq(a: any, b: any): boolean {
  if (isNA(a) || isNA(b)) return false;
  return a === b;
}

/** Inequality that returns true when either side is NA. */
function naSafeNeq(a: any, b: any): boolean {
  if (isNA(a) || isNA(b)) return true;
  return a !== b;
}

/**
 * Pine Script truthiness: NA is always falsy, unlike in JavaScript where
 * Symbol values are truthy.  Use this everywhere a boolean decision is
 * made on an evaluated value.
 */
function isTruthy(v: any): boolean {
  if (isNA(v)) return false;
  return !!v;
}

// ---------------------------------------------------------------------------
// Operator lookup tables
// ---------------------------------------------------------------------------

const ARITH_OPS: Record<string, (a: any, b: any) => any> = {
  "+": (a, b) => withArithNA(a, b, (x, y) => x + y),
  "-": (a, b) => withArithNA(a, b, (x, y) => x - y),
  "*": (a, b) => withArithNA(a, b, (x, y) => x * y),
  "/": (a, b) => withArithNA(a, b, (x, y) => x / y),
  "%": (a, b) => withArithNA(a, b, (x, y) => x % y),
};

const CMP_OPS: Record<string, (a: any, b: any) => boolean> = {
  "==": naSafeEq,
  "!=": naSafeNeq,
  "<": (a, b) => withCmpNA(a, b, (x, y) => x < y),
  ">": (a, b) => withCmpNA(a, b, (x, y) => x > y),
  "<=": (a, b) => withCmpNA(a, b, (x, y) => x <= y),
  ">=": (a, b) => withCmpNA(a, b, (x, y) => x >= y),
};

const UNARY_OPS: Record<string, (a: any) => any> = {
  "+": (a) => (isNA(a) ? NA : +Number(a)),
  "-": (a) => (isNA(a) ? NA : -Number(a)),
  not: (a) => (isNA(a) ? true : !a),
};

// ---------------------------------------------------------------------------
// Evaluator
// ---------------------------------------------------------------------------

/**
 * Main Evaluator for the Pine Script AST.
 *
 * Uses a string-keyed visitor pattern: each AST node type has a matching
 * entry in {@link visitors}.  The {@link visit} method looks up the visitor
 * by `node.type` and calls it.
 *
 * Expression visitors: Literal, Identifier, BinOp, UnaryOp, Compare,
 *   Conditional, Call, Attribute, Subscript.
 *
 * Statement visitors: Script, Assign, ReAssign, If, For (for-in), ForTo,
 *   While, Break, Continue, Expr, Return.
 */
export class Evaluator {
  /** Variable bindings and script-global state. */
  context: Record<string, any>;

  /** Optional builtin registry — used by the Call visitor. */
  builtins?: BuiltinRegistry;

  /** Visitor dispatch map keyed by AST node type. */
  private visitors: Map<string, VisitorFn>;

  constructor(context?: Record<string, any>, builtins?: BuiltinRegistry) {
    this.context = context ?? {};
    this.builtins = builtins;
    this.visitors = new Map<string, VisitorFn>();
    this._registerAll();
  }

  // -----------------------------------------------------------------------
  // Registration
  // -----------------------------------------------------------------------

  /** Register every expression and statement visitor. */
  private _registerAll(): void {
    // --- Expressions ---
    this.visitors.set("Literal", this._visitLiteral.bind(this));
    this.visitors.set("Identifier", this._visitIdentifier.bind(this));
    this.visitors.set("BinOp", this._visitBinOp.bind(this));
    this.visitors.set("UnaryOp", this._visitUnaryOp.bind(this));
    this.visitors.set("Compare", this._visitCompare.bind(this));
    this.visitors.set("Conditional", this._visitConditional.bind(this));
    this.visitors.set("Call", this._visitCall.bind(this));
    this.visitors.set("Attribute", this._visitAttribute.bind(this));
    this.visitors.set("Subscript", this._visitSubscript.bind(this));

    // --- Statements ---
    this.visitors.set("Script", this._visitScript.bind(this));
    this.visitors.set("Assign", this._visitAssign.bind(this));
    this.visitors.set("ReAssign", this._visitReAssign.bind(this));
    this.visitors.set("If", this._visitIf.bind(this));
    this.visitors.set("For", this._visitFor.bind(this));
    this.visitors.set("ForTo", this._visitForTo.bind(this));
    this.visitors.set("While", this._visitWhile.bind(this));
    this.visitors.set("Break", this._visitBreak.bind(this));
    this.visitors.set("Continue", this._visitContinue.bind(this));
    this.visitors.set("Expr", this._visitExpr.bind(this));
    this.visitors.set("Return", this._visitReturn.bind(this));
  }

  // -----------------------------------------------------------------------
  // Main dispatch
  // -----------------------------------------------------------------------

  /**
   * Evaluate an AST node.
   *
   * Looks up the visitor by `node.type` and invokes it.  Throws if the
   * node type is unknown.
   */
  visit(node: any): any {
    if (node == null || typeof node !== "object") return node;
    const fn = this.visitors.get(node.type);
    if (fn) return fn(node, this);
    throw new Error(`Unknown AST node type: ${node.type}`);
  }

  // -----------------------------------------------------------------------
  // Expression visitors
  // -----------------------------------------------------------------------

  /** Literal → return `node.value` as-is. */
  private _visitLiteral(node: any): any {
    return node.value;
  }

  /** Identifier → look up `node.name` in context; return NA if not found. */
  private _visitIdentifier(node: any): any {
    if (node.name in this.context) return this.context[node.name];
    return NA;
  }

  /** BinOp → arithmetic / comparison / boolean binary operations. */
  private _visitBinOp(node: any): any {
    const { left, op, right } = node;

    // Short-circuit for boolean operators: evaluate left first, then
    // conditionally evaluate right.  NA is always falsy in Pine Script.
    if (op === "and") {
      const l = this.visit(left);
      return isTruthy(l) ? this.visit(right) : l;
    }
    if (op === "or") {
      const l = this.visit(left);
      return isTruthy(l) ? l : this.visit(right);
    }

    // Arithmetic operators
    if (op in ARITH_OPS) {
      const l = this.visit(left);
      const r = this.visit(right);
      return ARITH_OPS[op](l, r);
    }

    // Comparison operators
    if (op in CMP_OPS) {
      const l = this.visit(left);
      const r = this.visit(right);
      return CMP_OPS[op](l, r);
    }

    throw new Error(`Unknown binary operator: ${op}`);
  }

  /** UnaryOp → unary plus / negate / boolean not. */
  private _visitUnaryOp(node: any): any {
    const operand = this.visit(node.operand);
    const fn = UNARY_OPS[node.op];
    if (!fn) throw new Error(`Unknown unary operator: ${node.op}`);
    return fn(operand);
  }

  /**
   * Compare → chained comparison with short-circuit.
   *
   * Supports the `Compare` AST shape:
   *   { type: "Compare", left: Expr, ops: string[], comparators: Expr[] }
   *
   * Each op/comparator pair is evaluated left-to-right.  If any comparison
   * fails the chain short-circuits and returns false.
   */
  private _visitCompare(node: any): boolean {
    let left = this.visit(node.left);
    const ops: string[] = node.ops;
    const comparators: any[] = node.comparators;

    for (let i = 0; i < ops.length; i++) {
      const opFn = CMP_OPS[ops[i]];
      if (!opFn) throw new Error(`Unknown compare operator: ${ops[i]}`);
      const right = this.visit(comparators[i]);
      if (!opFn(left, right)) return false;
      left = right;
    }
    return true;
  }

  /** Conditional → ternary if-else expression (a ? b : c). */
  private _visitConditional(node: any): any {
    const test = this.visit(node.test);
    if (isTruthy(test)) {
      return this.visit(node.body);
    }
    return this.visit(node.orelse);
  }

  /**
   * Call → function / builtin call.
   *
   * Dispatch priority:
   *   1. Qualified attribute builtin (e.g. strategy.entry) — checked
   *      before visiting `node.func` so the qualified name isn't lost.
   *   2. Direct builtin (e.g. sma) — `node.func` is an Identifier whose
   *      name is registered.
   *   3. Callable value — visit `node.func` and invoke the result.
   */
  private _visitCall(node: any): any {
    const funcNode = node.func;

    // --- 1. Qualified attribute builtin (e.g. strategy.entry) -----------
    if (funcNode?.type === "Attribute") {
      const qualifier = this.visit(funcNode.value);
      if (!isNA(qualifier) && typeof qualifier === "string") {
        const qualifiedName = `${qualifier}.${funcNode.attr}`;
        if (this.builtins?.isRegistered(qualifiedName)) {
          const { args, kwargs } = this._collectCallArgs(node);
          return this.builtins.call(qualifiedName, args, kwargs);
        }
      }
    }

    // --- 2. Direct builtin by name (e.g. sma, ta.sma) ------------------
    if (funcNode?.type === "Identifier") {
      const name = funcNode.name;
      if (this.builtins?.isRegistered(name)) {
        const { args, kwargs } = this._collectCallArgs(node);
        return this.builtins.call(name, args, kwargs);
      }
    }

    // --- 3. General callable -------------------------------------------
    const fn = this.visit(funcNode);
    const { args, kwargs } = this._collectCallArgs(node);

    if (typeof fn === "function") {
      return fn(...args);
    }

    if (typeof fn === "string" && this.builtins?.isRegistered(fn)) {
      return this.builtins.call(fn, args, kwargs);
    }

    throw new Error(
      `Cannot call ${typeof fn}: ${String(fn)}`,
    );
  }

  /** Collect positional and keyword args from a Call node. */
  private _collectCallArgs(node: any): {
    args: any[];
    kwargs: Record<string, any>;
  } {
    const args: any[] = [];
    const kwargs: Record<string, any> = {};

    // Positional args
    if (Array.isArray(node.args)) {
      for (const arg of node.args) {
        args.push(this.visit(arg));
      }
    }

    // Keyword args
    if (Array.isArray(node.kwargs)) {
      for (const kw of node.kwargs) {
        kwargs[kw.name] = this.visit(kw.value);
      }
    }

    return { args, kwargs };
  }

  /**
   * Attribute → property access (e.g. close.value, strategy.long).
   *
   * Visits the value, then returns `value[attr]`.  Returns NA if the
   * value is null/undefined or the property doesn't exist.
   */
  private _visitAttribute(node: any): any {
    const value = this.visit(node.value);
    if (isNA(value) || value == null) return NA;
    if (typeof value === "object" || typeof value === "function") {
      const prop = value[node.attr];
      return prop !== undefined ? prop : NA;
    }
    // For primitives, check if the property exists
    return value[node.attr] !== undefined ? value[node.attr] : NA;
  }

  /** Subscript → index access (e.g. array[0]). */
  private _visitSubscript(node: any): any {
    const value = this.visit(node.value);
    if (isNA(value) || value == null) return NA;
    const index = this.visit(node.index);
    return value[index];
  }

  // -----------------------------------------------------------------------
  // Statement visitors
  // -----------------------------------------------------------------------

  /** Script → evaluate each statement in order. */
  private _visitScript(node: any): any {
    let result: any;
    for (const stmt of node.body) {
      result = this.visit(stmt);
    }
    return result;
  }

  /**
   * Assign → variable assignment.
   *
   * - `mode: "var" | "varip"` — only assigns on the first bar
   *   (bar_index === 0).  On subsequent bars the declaration is skipped
   *   so the variable retains its value across bars.
   * - `mode: null` — always executes (regular assignment).
   */
  private _visitAssign(node: any): void {
    const mode: string | null = node.mode ?? null;
    const isVar = mode === "var" || mode === "varip";
    const firstBar = (this.context["bar_index"] ?? 0) === 0;

    if (isVar && !firstBar) {
      return; // Skip on subsequent bars
    }

    const value = this.visit(node.value);
    const targets: any[] = node.targets ?? [];

    for (const target of targets) {
      if (target?.type === "Identifier") {
        this.context[target.name] = value;
      }
    }
  }

  /** ReAssign → Pine Script `:=` operator (evaluate RHS, assign to target). */
  private _visitReAssign(node: any): void {
    const value = this.visit(node.value);
    const target = node.target;

    if (target?.type === "Identifier") {
      this.context[target.name] = value;
    }
  }

  /** If → conditional execution of body / orelse blocks. */
  private _visitIf(node: any): any {
    const test = this.visit(node.test);
    if (isTruthy(test)) {
      return this._executeBlock(node.body);
    }
    if (Array.isArray(node.orelse) && node.orelse.length > 0) {
      return this._executeBlock(node.orelse);
    }
    return undefined;
  }

  /**
   * For → for-in loop over an iterable (e.g. `for x in array`).
   *
   * AST shape: { type: "For", var: Identifier, iter: Expression, body: Statement[] }
   */
  private _visitFor(node: any): any {
    const targetName = node.var?.name;
    if (!targetName) throw new Error("For loop target must be an Identifier");

    const iterable = this.visit(node.iter);
    if (isNA(iterable) || iterable == null) return undefined;

    const items = Array.isArray(iterable)
      ? iterable
      : typeof iterable === "object" && typeof iterable[Symbol.iterator] === "function"
        ? [...iterable]
        : [iterable];

    return this._executeForLoopBody(targetName, items, node.body);
  }

  /**
   * ForTo → numeric range loop (e.g. `for i = 0 to 10`).
   *
   * AST shape:
   *   { type: "ForTo", target: Identifier, start: Expression,
   *     end: Expression, step?: Expression, body: Statement[] }
   */
  private _visitForTo(node: any): any {
    const targetName = node.target?.name;
    if (!targetName)
      throw new Error("ForTo loop target must be an Identifier");

    const start = Number(this.visit(node.start));
    const end = Number(this.visit(node.end));
    const step = node.step != null ? Number(this.visit(node.step)) : 1;

    // Build the range (inclusive of end, matching Pine Script semantics)
    const items: number[] = [];
    if (step > 0) {
      for (let i = start; i <= end; i += step) items.push(i);
    } else if (step < 0) {
      for (let i = start; i >= end; i += step) items.push(i);
    }

    return this._executeForLoopBody(targetName, items, node.body);
  }

  /** Shared for-loop body executor with break/continue handling. */
  private _executeForLoopBody(
    targetName: string,
    items: any[],
    body: any[],
  ): any {
    let lastResult: any;
    for (const item of items) {
      this.context[targetName] = item;
      try {
        lastResult = this._executeBlock(body);
      } catch (err) {
        if (err instanceof BreakSignal) break;
        if (err instanceof ContinueSignal) continue;
        throw err;
      }
    }
    return lastResult;
  }

  /** While → loop while test is truthy. */
  private _visitWhile(node: any): any {
    let lastResult: any;
    while (isTruthy(this.visit(node.test))) {
      try {
        lastResult = this._executeBlock(node.body);
      } catch (err) {
        if (err instanceof BreakSignal) break;
        if (err instanceof ContinueSignal) continue;
        throw err;
      }
    }
    return lastResult;
  }

  /** Break → throw a BreakSignal to exit the current loop. */
  private _visitBreak(_node: any): never {
    throw new BreakSignal();
  }

  /** Continue → throw a ContinueSignal to skip to the next iteration. */
  private _visitContinue(_node: any): never {
    throw new ContinueSignal();
  }

  /** Expr → evaluate the inner expression (expression statement wrapper). */
  private _visitExpr(node: any): any {
    return this.visit(node.value);
  }

  /** Return → evaluate and return a value (throws ReturnSignal). */
  private _visitReturn(node: any): any {
    const value = node.value != null ? this.visit(node.value) : NA;
    throw new ReturnSignal(value);
  }

  // -----------------------------------------------------------------------
  // Block execution helpers
  // -----------------------------------------------------------------------

  /**
   * Execute a block of statements and return the last expression's value.
   */
  _executeBlock(stmts: any[]): any {
    let result: any;
    for (const stmt of stmts) {
      result = this.visit(stmt);
      // If result is a thenable (promise), we'll still return it as-is
      // (the evaluator is synchronous unless a builtin returns a promise).
    }
    return result;
  }
}
