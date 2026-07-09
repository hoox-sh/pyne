import { z } from "zod";

// ---------------------------------------------------------------------------
// Literals & Identifiers
// ---------------------------------------------------------------------------

const LiteralSchema = z.object({
  type: z.literal("Literal"),
  value: z.union([z.string(), z.number(), z.boolean(), z.null()]),
});

const IdentifierSchema = z.object({
  type: z.literal("Identifier"),
  name: z.string(),
});

// ---------------------------------------------------------------------------
// Expressions (forward-declared via z.lazy to break circular references)
// ---------------------------------------------------------------------------

const ExpressionSchema: z.ZodType<unknown> = z.lazy(() =>
  z.union([
    LiteralSchema,
    IdentifierSchema,
    BinOpSchema,
    UnaryOpSchema,
    CallSchema,
    AttributeSchema,
    SubscriptSchema,
  ])
);

const BinOpSchema = z.object({
  type: z.literal("BinOp"),
  left: z.lazy(() => ExpressionSchema),
  op: z.enum([
    "+",
    "-",
    "*",
    "/",
    "%",
    "==",
    "!=",
    "<",
    ">",
    "<=",
    ">=",
    "and",
    "or",
  ]),
  right: z.lazy(() => ExpressionSchema),
});

const UnaryOpSchema = z.object({
  type: z.literal("UnaryOp"),
  op: z.enum(["+", "-", "not"]),
  operand: z.lazy(() => ExpressionSchema),
});

const CallSchema = z.object({
  type: z.literal("Call"),
  func: z.lazy(() => ExpressionSchema),
  args: z.array(z.lazy(() => ExpressionSchema)),
  kwargs: z.array(
    z.object({
      name: z.string(),
      value: z.lazy(() => ExpressionSchema),
    })
  ),
});

const AttributeSchema = z.object({
  type: z.literal("Attribute"),
  value: z.lazy(() => ExpressionSchema),
  attr: z.string(),
});

const SubscriptSchema = z.object({
  type: z.literal("Subscript"),
  value: z.lazy(() => ExpressionSchema),
  index: z.lazy(() => ExpressionSchema),
});

// ---------------------------------------------------------------------------
// Statements
// ---------------------------------------------------------------------------

const StatementSchema: z.ZodType<unknown> = z.lazy(() =>
  z.union([
    AssignSchema,
    ReAssignSchema,
    IfSchema,
    ForSchema,
    WhileSchema,
    ReturnSchema,
    ExpressionSchema,
  ])
);

const AssignSchema = z.object({
  type: z.literal("Assign"),
  targets: z.array(z.lazy(() => ExpressionSchema)),
  value: z.lazy(() => ExpressionSchema),
  mode: z.union([z.literal("var"), z.literal("varip"), z.null()]),
});

const ReAssignSchema = z.object({
  type: z.literal("ReAssign"),
  target: z.lazy(() => ExpressionSchema),
  value: z.lazy(() => ExpressionSchema),
});

const IfSchema = z.object({
  type: z.literal("If"),
  test: z.lazy(() => ExpressionSchema),
  body: z.array(z.lazy(() => StatementSchema)),
  orelse: z.array(z.lazy(() => StatementSchema)),
});

const ForSchema = z.object({
  type: z.literal("For"),
  var: z.lazy(() => IdentifierSchema),
  iter: z.lazy(() => ExpressionSchema),
  body: z.array(z.lazy(() => StatementSchema)),
});

const WhileSchema = z.object({
  type: z.literal("While"),
  test: z.lazy(() => ExpressionSchema),
  body: z.array(z.lazy(() => StatementSchema)),
});

const ReturnSchema = z.object({
  type: z.literal("Return"),
  value: z.lazy(() => ExpressionSchema).optional(),
});

// ---------------------------------------------------------------------------
// Top-level
// ---------------------------------------------------------------------------

const ScriptSchema = z.object({
  type: z.literal("Script"),
  body: z.array(z.lazy(() => StatementSchema)),
});

const PineASTSchema = ScriptSchema;

// ---------------------------------------------------------------------------
// Exports – schemas
// ---------------------------------------------------------------------------

export {
  LiteralSchema,
  IdentifierSchema,
  ExpressionSchema,
  BinOpSchema,
  UnaryOpSchema,
  CallSchema,
  AttributeSchema,
  SubscriptSchema,
  StatementSchema,
  AssignSchema,
  ReAssignSchema,
  IfSchema,
  ForSchema,
  WhileSchema,
  ReturnSchema,
  ScriptSchema,
  PineASTSchema,
};

// ---------------------------------------------------------------------------
// Exports – inferred types
// ---------------------------------------------------------------------------

export type Literal = z.infer<typeof LiteralSchema>;
export type Identifier = z.infer<typeof IdentifierSchema>;
export type Expression = z.infer<typeof ExpressionSchema>;
export type BinOp = z.infer<typeof BinOpSchema>;
export type UnaryOp = z.infer<typeof UnaryOpSchema>;
export type Call = z.infer<typeof CallSchema>;
export type Attribute = z.infer<typeof AttributeSchema>;
export type Subscript = z.infer<typeof SubscriptSchema>;
export type Statement = z.infer<typeof StatementSchema>;
export type Assign = z.infer<typeof AssignSchema>;
export type ReAssign = z.infer<typeof ReAssignSchema>;
export type If = z.infer<typeof IfSchema>;
export type For = z.infer<typeof ForSchema>;
export type While = z.infer<typeof WhileSchema>;
export type Return = z.infer<typeof ReturnSchema>;
export type Script = z.infer<typeof ScriptSchema>;
export type PineAST = z.infer<typeof PineASTSchema>;
