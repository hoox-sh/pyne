# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# PyneScript Performance Optimizations

## Summary

This document describes the performance optimizations applied to PyneScript core features to improve parsing, evaluation, and AST manipulation efficiency.

## Profiling Results

### Initial Analysis
- **Test Suite**: 859 tests in ~50.0 seconds
- **Main Bottleneck**: ANTLR4 parser (ParserATNSimulator) accounts for ~85% of parsing time
- **Our Code**: ~15% of total parse time

### Post-Optimization Results
- **Test Suite**: 859 tests in ~48.9 seconds (~2.2% improvement)
- **All tests pass**: 100% compatibility maintained

## Performance Benchmarks

```
Parse/Unparse Test (complex script):
  Per iteration: 7.75ms
  Ops/sec: 129.1

Expression Evaluation Test:
  Per iteration: 1.949ms
  Ops/sec: 513.1

Simple Parse Test:
  Per iteration: 0.667ms
  Ops/sec: 1500.1
```

## Optimizations Implemented

### 1. AST Location Setting (builder.py)
**Change**: Optimized `_setLocations` to directly set attributes instead of creating intermediate dictionary.

**Before**:
```python
def _setLocations(self, node: ast.AST, ctx: ParserRuleContext) -> ast.AST:
    for name, value in self._getLocations(ctx).items():
        setattr(node, name, value)
    return node
```

**After**:
```python
def _setLocations(self, node: ast.AST, ctx: ParserRuleContext) -> ast.AST:
    start = ctx.start
    stop = ctx.stop
    stop_len = stop.stop - stop.start + 1
    stop_nls = stop.text.count("\n")
    
    node.lineno = start.line
    node.col_offset = start.column
    node.end_lineno = stop.line + stop_nls
    # ... optimized end_col_offset calculation
    return node
```

**Impact**: Eliminates dictionary creation overhead in hot path (~3800 calls per 100 iterations)

### 2. Operator Reference Caching (evaluator/expressions.py)
**Change**: Pre-cache operator function references at module level.

**Before**:
```python
def visit_Eq(self: EvaluatorProtocol, _node: ast.Eq):
    return operator.eq  # Attribute lookup on every call
```

**After**:
```python
# Module level
_OPERATOR_EQ = operator.eq

def visit_Eq(self: EvaluatorProtocol, _node: ast.Eq):
    return _OPERATOR_EQ  # Direct reference
```

**Impact**: Eliminates module attribute lookups for all operator comparisons

### 3. Math Constants Pre-computation (evaluator/base.py)
**Change**: Pre-compute math constants at module level instead of per-evaluator.

**Before**:
```python
def __init__(self, context: dict[str, Any] | None = None):
    self.context = context or {}
    self.context.update({
        "math.pi": math.pi,
        "math.e": math.e,
        "math.phi": (1 + math.sqrt(5)) / 2,  # Computed every time
        # ...
    })
```

**After**:
```python
# Module level
_MATH_CONSTANTS = {
    "math.pi": math.pi,
    "math.e": math.e,
    "math.phi": (1 + math.sqrt(5)) / 2,  # Computed once
    # ...
}

def __init__(self, context: dict[str, Any] | None = None):
    self.context = context or {}
    self.context.update(_MATH_CONSTANTS)
```

**Impact**: Eliminates repeated math.sqrt() calls

### 4. Comment Processing Optimizations (helper.py)
**Change**: Added early exit for empty comment lists and cached type lookups.

**Before**:
```python
def _collect_comment_nodes(builder, token_stream):
    comments = []
    for token in token_stream.tokens:
        if token is None or token.type != PinescriptLexer.COMMENT:
            continue
        # ...
        comment.end_col_offset = token.column + len(text)
```

**After**:
```python
def _collect_comment_nodes(builder, token_stream):
    comments = []
    comment_type = PinescriptLexer.COMMENT  # Cache lookup
    for token in token_stream.tokens:
        if token is None or token.type != comment_type:
            continue
        # ...
        text_len = len(text)  # Cache length
        comment.end_col_offset = token.column + text_len
```

**Impact**: Reduces attribute lookups and redundant len() calls

### 5. Visitor Method Caching (visitor.py)
**Change**: Cache visitor method lookups to avoid repeated getattr calls.

**Before**:
```python
def visit(self, node: AST):
    method = "visit_" + node.__class__.__name__
    visitor = getattr(self, method, self.generic_visit)
    return visitor(node)
```

**After**:
```python
def __init__(self):
    self._visitor_cache: dict[str, callable] = {}

def visit(self, node: AST):
    node_class = node.__class__.__name__
    visitor = self._visitor_cache.get(node_class)
    if visitor is None:
        method = "visit_" + node_class
        visitor = getattr(self, method, self.generic_visit)
        self._visitor_cache[node_class] = visitor
    return visitor(node)
```

**Impact**: Caches visitor method lookups after first access, reducing getattr overhead

### 6. Annotation Processing (helper.py)
**Change**: Added early exit when no comments exist.

**Before**:
```python
def _add_annotations(script, statements, comments):
    comments_and_statements_iter = itertools.chain(comments, statements)
    # ... always processes even if comments is empty
```

**After**:
```python
def _add_annotations(script, statements, comments):
    if not comments:
        return  # Early exit
    # ... rest of processing
```

**Impact**: Avoids unnecessary processing when no annotations present

## Why ANTLR Parser Cannot Be Easily Optimized

The ANTLR4 parser (ParserATNSimulator) is the dominant bottleneck, accounting for ~85% of parse time:

### Main Hotspots in ANTLR
1. `closure_()` - 16.2s tottime in 100 iterations
2. `adaptivePredict()` - 0.8s tottime, 122s cumtime
3. `execATN()` - State machine execution
4. `PredictionContext` operations - Context merging and hashing

### Why We Can't Optimize ANTLR Easily
1. **Generated Code**: Parser is auto-generated from grammar
2. **Grammar Complexity**: Pine Script v5-v6 has complex syntax
3. **ANTLR Design**: Adaptive LL(*) algorithm requires extensive lookahead
4. **Trade-offs**: Any grammar simplification risks breaking compatibility

### Potential Future Optimizations (High Risk)
- Simplify grammar rules (risky - may break existing scripts)
- Use SLL prediction mode (may reduce accuracy)
- Implement custom lexer for simple cases (major effort)
- Profile-guided grammar optimization (requires extensive testing)

## Optimization Guidelines

### Do's
✅ Cache computed values at module/class level  
✅ Eliminate intermediate object creation in hot paths  
✅ Use early exits to skip unnecessary work  
✅ Cache method/attribute lookups when repeated  
✅ Pre-compute constants and invariants  

### Don'ts
❌ Modify generated ANTLR code (will be overwritten)  
❌ Add slots to dataclass-based nodes (incompatible)  
❌ Cache mutable objects between instances  
❌ Optimize cold paths at expense of code clarity  
❌ Skip testing after "performance improvements"  

## Impact Analysis

### Test Suite Performance
- **Before**: ~50.0 seconds for 859 tests
- **After**: ~48.9 seconds for 859 tests
- **Improvement**: ~2.2% faster
- **Reliability**: 100% test pass rate maintained

### Memory Impact
- **Visitor caching**: ~200 bytes per visitor instance (minimal)
- **Module constants**: ~100 bytes total (one-time)
- **Overall**: Negligible memory increase

### Code Maintainability
- **Lines changed**: ~100 lines across 6 files
- **Complexity**: No significant increase
- **Documentation**: Added comments explaining optimizations
- **Linting**: All code passes ruff checks

## Recommendations

### For Current Codebase
The optimizations provide measurable improvements without compromising code quality. The 2.2% speedup is modest but worthwhile given the minimal complexity increase.

### For Future Work
1. **Profile before optimizing**: Always profile to identify real bottlenecks
2. **Measure impact**: Benchmark before and after changes
3. **Maintain tests**: Never sacrifice correctness for speed
4. **Document rationale**: Explain why optimizations were chosen
5. **Consider alternatives**: ANTLR alternatives (tree-sitter, custom parser) for major gains

### For Users
- Parser performance is already quite good (~1500 ops/sec for simple scripts)
- Most real-world scripts parse in <10ms
- Evaluator performance is excellent (~500 ops/sec for expressions)
- No user-facing API changes from these optimizations

## Conclusion

These optimizations provide a solid ~2% performance improvement while maintaining 100% backward compatibility. The ANTLR parser remains the dominant bottleneck, but further optimization would require risky changes to the grammar or parser implementation. The current balance of performance, correctness, and maintainability is appropriate for the project's needs.
