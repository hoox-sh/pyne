# docs/pyne/runtime

# Concepts

* [Alerts](alerts.md) - alert() / alertcondition() engine, host export, and L2 HTTP webhooks (Pro API + pyne-worker).
* [Strategy events](events.md) - StrategyEvent shape, emission points, parity corpus, and host serialization.
* [Expressions and statements](expressions-statements.md) - How the AST walker evaluates operations, calls, control flow, assignments, and user definitions.
* [Runtime](index.md) - Bar-loop evaluator — series caps, incremental TA, alerts, fill export, foreign request.security → na, and interpret↔compile parity.
* [Libraries](libraries.md) - In-process library export/import, LibraryRegistry, and evaluate-order requirements.
* [Series and history](series-and-history.md) - Pine series model: history operator, na propagation, var/varip persistence, and bar-mode scalars.

# Nested

* [builtins](builtins/) - Nested concepts.
* [compiler](compiler/) - Nested concepts.
