# Pine Script Implementation: High-Priority Functions

## 📌 Quick Start

**You are here:** Ready to implement 63 high-priority Pine Script functions  
**Current Status:** 50-55% complete (150+ functions)  
**Target Status:** 70%+ complete (213+ functions)  

### Three Documents, One Goal:

1. **START HERE** → `IMPLEMENTATION_SUMMARY.md` (Executive overview, 5 min read)
2. **THEN READ** → `IMPLEMENTATION_ROADMAP.txt` (Detailed specifications, 30 min read)
3. **WHILE CODING** → Reference examples and patterns in this file

---

## 🎯 The 63 Functions at a Glance

### Group 1: INPUT (15 functions) - Week 1
```
input() input.bool() input.int() input.float() input.price()
input.string() input.symbol() input.session() input.source()
input.time() input.timeframe() input.color() input.enum()
```

**Why**: Indicators/strategies need user configuration  
**Impact**: Can't use any input() without this  
**Module**: `src/pynescript/ast/evaluator/builtins/input.py` (NEW)  

---

### Group 2: REQUEST (10 functions) - Week 1-2
```
request.security() request.security_lower_tf() request.dividends()
request.earnings() request.splits() request.financial()
request.quandl() request.economic() request.currency_rate()
request.seed()
```

**Why**: Multi-timeframe analysis and fundamental data  
**Impact**: Multi-symbol strategies impossible without this  
**Module**: `src/pynescript/ast/evaluator/builtins/request.py` (NEW)  

---

### Group 3: DRAWING (18 functions) - Week 2-3
```
line.new/delete/copy/set_*/get_*
box.new/delete/copy/set_*/get_*
label.new/delete/copy/set_*/get_*
table.new/delete/cell/clear/merge_cells
```

**Why**: Visual chart annotations and dashboards  
**Impact**: Can't see strategy results without visualization  
**Module**: `src/pynescript/ast/evaluator/builtins/drawing.py` (NEW)  

---

### Group 4: STRATEGY (20 functions) - Week 3-4
```
strategy.entry() strategy.exit() strategy.close() strategy.close_all()
strategy.cancel() strategy.cancel_all() strategy.order()
strategy.risk.* strategy.convert_to_* strategy.default_entry_qty()
strategy.closedtrades.* strategy.opentrades.*
```

**Why**: Backtesting and trade execution  
**Impact**: Can't run strategies without entry/exit/position management  
**Module**: `src/pynescript/ast/evaluator/builtins/strategy.py` (EXTEND)  

---

## 🏗️ How to Implement Each Function

### The Standard Pattern

1. **Create handler method** in your module
2. **Register in dispatch map** with full namespace
3. **Write tests** with all parameter combinations
4. **Update status doc** when complete

### Example: `input.bool()`

**Step 1: Create handler in `input.py`**
```python
def _handle_input_bool(self, args: list[Any]) -> dict[str, Any]:
    """
    input.bool(defval, title, tooltip, inline, group, confirm)
    Returns dict with parameter metadata
    """
    defval = args[0] if len(args) > 0 else False
    title = args[1] if len(args) > 1 else ""
    tooltip = args[2] if len(args) > 2 else ""
    
    return {
        "type": "bool",
        "default": defval,
        "title": title,
        "tooltip": tooltip,
    }
```

**Step 2: Register in dispatch map**
```python
def _build_builtin_map(self) -> dict[str, BuiltinHandler]:
    return {
        "input": self._handle_input,
        "input.bool": self._handle_input_bool,
        "input.int": self._handle_input_int,
        # ...
    }
```

**Step 3: Write test**
```python
def test_input_bool():
    evaluator = NodeLiteralEvaluator()
    result = evaluator.eval_call("input.bool", [True, "Enable", "Check to enable"])
    assert result["type"] == "bool"
    assert result["default"] == True
    assert result["title"] == "Enable"
```

**Step 4: Update status doc**
```markdown
- ✅ input.bool    # Change from ❌ to ✅
```

---

## 📚 Key Implementation Patterns

### Pattern 1: Simple Parameter Return
```python
# input() returns metadata
return {"default": defval, "title": title, "type": "float"}
```

### Pattern 2: Series Data (List of Values)
```python
# request.security() returns historical data
return [100.0, 101.5, 102.3, 101.8, ...]  # List of prices
```

### Pattern 3: Object Creation & Registry
```python
# line.new() creates drawing object
class Line:
    def __init__(self, x1, y1, x2, y2, **props):
        self.x1 = x1
        self.y1 = y1
        # ...
        self.deleted = False

# Store in global registry
line = Line(x1, y1, x2, y2)
DrawingRegistry.lines.append(line)
return line
```

### Pattern 4: Property Getters/Setters
```python
# line.set_color() modifies existing object
def _handle_line_set_color(self, args):
    line = args[0]  # First arg is the line object
    color = args[1]
    line.color = color
    return line
```

### Pattern 5: Tuples/Multiple Returns
```python
# request.security() with tuple expression
# Pine: [close, volume] = request.security(...)
def _handle_request_security(self, args):
    expr = args[2]  # Third arg is the expression
    if expr == "[close, volume]":
        return (
            [100.0, 101.0, 102.0],  # close series
            [1000, 1100, 1200]       # volume series
        )
```

---

## 🧪 Testing Strategy

### For Each Function:

**Unit Test** - Test function in isolation
```python
def test_input_int():
    evaluator = NodeLiteralEvaluator()
    result = evaluator.eval_call("input.int", [50, "Value", 10, 100])
    assert result["default"] == 50
    assert result["min"] == 10
    assert result["max"] == 100
```

**Integration Test** - Test with Pine Script code
```python
def test_parse_and_eval_with_input():
    code = """
    len = input.int(14, "Length", 1, 100)
    close = close[len]
    plot(close)
    """
    script = parse(code)
    result = evaluate(script)
    # Verify parameter was created correctly
```

### Coverage Target: 95%+

---

## 📋 Implementation Checklist

### Phase 1: INPUT FUNCTIONS
- [ ] Create `input.py` module
- [ ] Implement `input()` handler
- [ ] Implement `input.bool()` handler
- [ ] Implement `input.int()` handler
- [ ] Implement `input.float()` handler
- [ ] Implement `input.price()` handler
- [ ] Implement `input.string()` handler
- [ ] Implement `input.symbol()` handler
- [ ] Implement `input.session()` handler
- [ ] Implement `input.source()` handler
- [ ] Implement `input.time()` handler
- [ ] Implement `input.timeframe()` handler
- [ ] Implement `input.color()` handler
- [ ] Implement `input.enum()` handler
- [ ] Write comprehensive tests (95%+)
- [ ] Update status doc
- [ ] Create PR with results

### Phase 2: REQUEST FUNCTIONS
- [ ] Create `request.py` module
- [ ] Implement `request.security()` handler
- [ ] Implement `request.security_lower_tf()` handler
- [ ] Implement `request.dividends()` handler
- [ ] Implement `request.earnings()` handler
- [ ] Implement `request.splits()` handler
- [ ] Implement `request.financial()` handler
- [ ] Implement `request.quandl()` handler
- [ ] Implement `request.economic()` handler
- [ ] Implement `request.currency_rate()` handler
- [ ] Implement `request.seed()` handler
- [ ] Write comprehensive tests
- [ ] Update status doc
- [ ] Create PR

### Phase 3: DRAWING FUNCTIONS
- [ ] Create `drawing.py` module
- [ ] Create Line, Box, Label, Table dataclasses
- [ ] Implement line.new/delete/copy
- [ ] Implement line.set_* and line.get_* handlers
- [ ] Implement box.new/delete/copy
- [ ] Implement box.set_* and box.get_* handlers
- [ ] Implement label.new/delete/copy
- [ ] Implement label.set_* and label.get_* handlers
- [ ] Implement table.new/delete/cell/clear/merge_cells
- [ ] Create DrawingRegistry for .all collections
- [ ] Write comprehensive tests
- [ ] Update status doc
- [ ] Create PR

### Phase 4: STRATEGY FUNCTIONS
- [ ] Create Position and Trade dataclasses
- [ ] Implement strategy.entry() handler
- [ ] Implement strategy.exit() handler
- [ ] Implement strategy.close() handler
- [ ] Implement strategy.close_all() handler
- [ ] Implement strategy.cancel() handler
- [ ] Implement strategy.cancel_all() handler
- [ ] Implement strategy.order() handler
- [ ] Implement strategy.risk.* handlers
- [ ] Implement strategy.convert_to_* handlers
- [ ] Implement strategy.default_entry_qty() handler
- [ ] Implement strategy.closedtrades.* handlers
- [ ] Implement strategy.opentrades.* handlers
- [ ] Write comprehensive tests
- [ ] Update status doc
- [ ] Create PR

---

## 🔗 Related Files

**Architecture & Design**
- `copilot-instructions.md` - Full architecture overview
- `src/pynescript/ast/evaluator/builtins/base.py` - Base classes & patterns

**Implementation References**
- `src/pynescript/ast/evaluator/builtins/numeric.py` - Math function examples
- `src/pynescript/ast/evaluator/builtins/arrays.py` - Array function examples
- `src/pynescript/ast/evaluator/builtins/technical.py` - TA function examples

**Testing**
- `tests/test_evaluator.py` - Test patterns and examples
- `tests/data/builtin_scripts/` - Pine Script fixtures

**Documentation**
- `docs/pinescript_implementation_status.md` - Current status tracker
- `IMPLEMENTATION_ROADMAP.txt` - Detailed specifications (30+ pages)
- `IMPLEMENTATION_SUMMARY.md` - Executive summary with timelines

---

## ❓ Common Questions

**Q: Do I need to implement all 63 at once?**  
A: No! Do them in groups (Input → Request → Drawing → Strategy). Each group is independent.

**Q: What if a function is complex?**  
A: Start with a simple version. You can add features later. See IMPLEMENTATION_ROADMAP.txt for complexity notes.

**Q: How do I handle errors?**  
A: Use try/except in handlers, raise ValueError with clear messages.

**Q: What about documentation?**  
A: Add docstrings to handlers explaining parameters and return types.

**Q: When do I test?**  
A: Write tests as you write functions. Don't wait until the end.

**Q: How do I verify my work?**  
A: Run `pytest tests/test_evaluator.py` to ensure all tests pass.

---

## 🚀 Getting Started Now

### Option 1: Start with INPUT (Recommended)
1. Open `IMPLEMENTATION_ROADMAP.txt` → "GROUP 1: INPUT FUNCTIONS"
2. Read the detailed specs and data structures
3. Create `src/pynescript/ast/evaluator/builtins/input.py`
4. Implement 3-5 functions and test

### Option 2: Review Strategy First
1. Open `IMPLEMENTATION_SUMMARY.md`
2. Read "Why These 4 Groups?" section
3. Understand the overall architecture
4. Then pick your starting group

### Option 3: Deep Dive on a Specific Group
1. Search `IMPLEMENTATION_ROADMAP.txt` for your group
2. Read all specs, patterns, and data structures
3. Study existing function examples in the codebase
4. Begin implementation

---

**Ready to get started? Pick a function above and begin! 🎉**

For questions or blocked issues, refer to the full IMPLEMENTATION_ROADMAP.txt or project architecture in copilot-instructions.md.
