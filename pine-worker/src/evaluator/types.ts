/** NA sentinel — Pine Script's "not available" value for out-of-bounds series access */
export const NA: unique symbol = Symbol("na");
export type NA = typeof NA;

/**
 * BreakSignal — thrown to break out of a loop.
 * Inspired by Python's approach of using exceptions for loop control flow.
 */
export class BreakSignal extends Error {
  override name = "BreakSignal" as const;
  constructor() {
    super("break");
  }
}

/**
 * ContinueSignal — thrown to skip to the next loop iteration.
 * Caught by the loop body executor to continue the loop.
 */
export class ContinueSignal extends Error {
  override name = "ContinueSignal" as const;
  constructor() {
    super("continue");
  }
}

/**
 * ReturnSignal — thrown to return a value from a user-defined function.
 * Caught by the function call wrapper to capture the returned value.
 */
export class ReturnSignal extends Error {
  override name = "ReturnSignal" as const;
  value: any;
  constructor(value: any) {
    super("return");
    this.value = value;
  }
}

/**
 * VisitorFn — signature for each visitor in the dispatch map.
 * Receives the AST node and the evaluator instance (so it can call
 * evaluator.visit(child) on sub-nodes).
 */
export type VisitorFn = (node: any, evaluator: any) => any;

/**
 * BuiltinRegistry — interface for the builtin function registry.
 * The evaluator delegates builtin dispatch to this interface.
 */
export interface BuiltinRegistry {
  call(name: string, args: any[], kwargs: Record<string, any>): any;
  isRegistered(name: string): boolean;
}
