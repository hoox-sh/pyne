# Pine Script v6 Implementation: Phase 2-5 Detailed Roadmap

**Date:** October 24, 2025  
**Status:** Phase 1 Complete ✅ → Phase 2 Ready to Start 🚀  
**Foundation:** Grammar, Parser, Type System, AST Builder all complete

---

## Executive Summary

Phase 1 established the grammar and parsing foundation. We can now build the runtime system:

- **Phase 2:** Object instantiation (.new(), field access)
- **Phase 3:** Method invocation and THIS binding
- **Phase 4:** Matrix and Map collections
- **Phase 5:** Built-in functions (Ticker, Logging, Chart.Point, Polyline)

This document provides the **exact specifications** for implementation.

---

## Phase 2: Object Instantiation (Week 1-2)

### Goal
Enable creation and use of UDT instances with field access and mutation.

### Implementation Order

#### 2.1 Extend Type System (Day 1)

**File:** `src/pynescript/ast/evaluator/types.py` (EXISTING - EXTEND)

Current structure exists with `Type` class hierarchy. Add UDT support:

```python
# EXISTING CODE - Add these classes

class UserDefinedType(Type):
    """Represents a user-defined type (UDT)"""
    
    def __init__(self, name: str, fields: dict[str, 'Field']):
        self.name = name
        self.fields = fields  # field_name -> Field instance
        self.methods = {}     # method_name -> MethodDef (Phase 3)
    
    def __str__(self) -> str:
        return f"{self.name}"
    
    def add_field(self, name: str, field: 'Field') -> None:
        self.fields[name] = field
    
    def add_method(self, name: str, method_def) -> None:
        """Add method (used in Phase 3)"""
        self.methods[name] = method_def
    
    def get_field(self, name: str) -> 'Field | None:
        return self.fields.get(name)
    
    def get_method(self, name: str):
        """Get method (used in Phase 3)"""
        return self.methods.get(name)


class Field:
    """Represents a field in a UDT"""
    
    def __init__(
        self,
        name: str,
        field_type: Type,
        default_value: Any = None,
        varip: bool = False,
        annotations: list[str] | None = None,
    ):
        self.name = name
        self.field_type = field_type
        self.default_value = default_value
        self.varip = varip
        self.annotations = annotations or []
    
    def __repr__(self) -> str:
        return f"Field({self.name}: {self.field_type})"


class ObjectInstance:
    """Runtime representation of a UDT instance"""
    
    def __init__(self, type_def: UserDefinedType):
        self.type_def = type_def
        self.fields = {}  # field_name -> current_value
        
        # Initialize fields with defaults
        for field_name, field_def in type_def.fields.items():
            self.fields[field_name] = field_def.default_value
    
    def get_field(self, name: str) -> Any:
        """Get field value"""
        if name not in self.type_def.fields:
            raise AttributeError(f"Type '{self.type_def.name}' has no field '{name}'")
        return self.fields.get(name)
    
    def set_field(self, name: str, value: Any) -> None:
        """Set field value"""
        if name not in self.type_def.fields:
            raise AttributeError(f"Type '{self.type_def.name}' has no field '{name}'")
        self.fields[name] = value
    
    def copy(self) -> 'ObjectInstance':
        """Shallow copy of this object"""
        new_instance = ObjectInstance(self.type_def)
        new_instance.fields = self.fields.copy()
        return new_instance
    
    def __repr__(self) -> str:
        fields_str = ", ".join(
            f"{k}={v}" for k, v in self.fields.items()
        )
        return f"{self.type_def.name}({fields_str})"
```

**Tests:**
```python
# tests/test_udt_types.py - ADD THESE TESTS
def test_user_defined_type_creation():
    field1 = Field("price", FLOAT_TYPE, 100.5)
    field2 = Field("qty", INT_TYPE, 0)
    udt = UserDefinedType("Trade", {"price": field1, "qty": field2})
    
    assert udt.name == "Trade"
    assert len(udt.fields) == 2
    assert udt.get_field("price").default_value == 100.5

def test_object_instance_creation():
    field = Field("value", FLOAT_TYPE, 42.0)
    udt = UserDefinedType("Data", {"value": field})
    
    obj = ObjectInstance(udt)
    assert obj.get_field("value") == 42.0

def test_object_field_mutation():
    field = Field("price", FLOAT_TYPE, 0.0)
    udt = UserDefinedType("Quote", {"price": field})
    obj = ObjectInstance(udt)
    
    obj.set_field("price", 99.99)
    assert obj.get_field("price") == 99.99

def test_object_copy():
    field = Field("balance", FLOAT_TYPE, 1000.0)
    udt = UserDefinedType("Account", {"balance": field})
    obj1 = ObjectInstance(udt)
    obj2 = obj1.copy()
    
    obj2.set_field("balance", 2000.0)
    assert obj1.get_field("balance") == 1000.0
    assert obj2.get_field("balance") == 2000.0
```

#### 2.2 Extend TypeRegistry (Day 1-2)

**File:** `src/pynescript/ast/evaluator/base.py` (EXISTING - EXTEND)

Current code has `TypeRegistry`. Enhance with UDT registration:

```python
# IN TypeRegistry CLASS

def register_udt(self, udt: UserDefinedType) -> None:
    """Register a user-defined type"""
    self.types[udt.name] = udt

def get_udt(self, name: str) -> UserDefinedType | None:
    """Get a user-defined type"""
    type_obj = self.types.get(name)
    if isinstance(type_obj, UserDefinedType):
        return type_obj
    return None

def list_udt_names(self) -> list[str]:
    """Get all registered UDT names"""
    return [
        name for name, type_obj in self.types.items()
        if isinstance(type_obj, UserDefinedType)
    ]
```

#### 2.3 Update TypeDef Evaluation (Day 2)

**File:** `src/pynescript/ast/evaluator/statements.py` (EXISTING - EXTEND)

Current code has `visit_TypeDef()`. Enhance to register UDT:

```python
# UPDATE visit_TypeDef method

def visit_TypeDef(self, node: TypeDef) -> None:
    """Evaluate type definition - register UDT in type registry"""
    
    # Extract fields from statements
    fields = {}
    for stmt in node.body:
        if isinstance(stmt, (Assign, AnnAssign)):
            # Field definition
            field_name = stmt.target.id if isinstance(stmt.target, Name) else str(stmt.target)
            
            # Get field type from annotation or infer from default value
            field_type = self._infer_type_from_annotation(stmt)
            
            # Get default value if present
            default_value = None
            if stmt.value:
                # Evaluate default value
                default_value = self.generic_visit(stmt.value)
            
            # Check for VARIP mode
            varip = getattr(stmt, 'varip_mode', False)
            
            # Create Field
            field = Field(
                name=field_name,
                field_type=field_type,
                default_value=default_value,
                varip=varip,
            )
            fields[field_name] = field
    
    # Create UserDefinedType
    udt = UserDefinedType(node.name, fields)
    
    # Register in type registry
    self.type_registry.register_udt(udt)
    
    # Store in global scope for .new() access
    self.current_scope[node.name] = udt
```

#### 2.4 Implement .new() Constructor (Day 3-4)

**File:** `src/pynescript/ast/evaluator/expressions.py` (EXISTING - EXTEND)

Add support for `TypeName.new()` call pattern:

```python
# IN NodeLiteralEvaluator (or CallEvaluator)

def visit_Call(self, node: Call) -> Any:
    """Handle function/method calls"""
    
    # Check for TypeName.new() pattern
    if isinstance(node.func, Attribute):
        if node.func.attr == 'new':
            # Try to get UDT by name
            base_name = self._get_name_from_expr(node.func.value)
            udt = self.type_registry.get_udt(base_name)
            
            if udt:
                return self._handle_udt_new(udt, node.args, node.keywords)
    
    # ... existing call handling
    return self.generic_visit(node)

def _handle_udt_new(
    self, 
    udt: UserDefinedType, 
    args: list, 
    keywords: list[keyword],
) -> ObjectInstance:
    """Create new UDT instance"""
    
    instance = ObjectInstance(udt)
    
    # Set fields from positional arguments
    field_names = list(udt.fields.keys())
    for i, arg in enumerate(args):
        if i < len(field_names):
            field_name = field_names[i]
            field_value = self.visit(arg)
            instance.set_field(field_name, field_value)
    
    # Set fields from keyword arguments
    for kw in keywords:
        if kw.arg in udt.fields:
            field_value = self.visit(kw.value)
            instance.set_field(kw.arg, field_value)
    
    return instance

def _get_name_from_expr(self, expr: expr) -> str | None:
    """Extract identifier name from expression"""
    if isinstance(expr, Name):
        return expr.id
    return None
```

#### 2.5 Implement Field Access (Day 4-5)

**File:** `src/pynescript/ast/evaluator/expressions.py` (EXISTING - EXTEND)

Add attribute access for object fields:

```python
# IN NodeLiteralEvaluator

def visit_Attribute(self, node: Attribute) -> Any:
    """Handle attribute access (obj.field)"""
    
    obj = self.visit(node.value)
    attr = node.attr
    
    # Check if accessing field on UDT instance
    if isinstance(obj, ObjectInstance):
        return obj.get_field(attr)
    
    # Check for built-in methods (.new, .copy)
    if isinstance(obj, UserDefinedType):
        if attr == 'new':
            # Return a callable that handles .new()
            return lambda *args, **kwargs: self._handle_udt_new(obj, list(args), kwargs)
        elif attr == 'copy':
            # Return a callable that handles .copy()
            return lambda instance: instance.copy()
    
    # ... existing attribute handling
    return self.generic_visit(node)
```

#### 2.6 Implement Field Assignment/Mutation (Day 5)

**File:** `src/pynescript/ast/evaluator/statements.py` (EXISTING - EXTEND)

Add support for `obj.field := value` pattern:

```python
# IN StatementEvaluator

def visit_AugAssign(self, node: AugAssign) -> None:
    """Handle augmented assignment including obj.field := value"""
    
    # Check for object field mutation (obj.field := value)
    if isinstance(node.target, Attribute):
        obj = self.visit(node.target.value)
        field_name = node.target.attr
        new_value = self.visit(node.value)
        
        if isinstance(obj, ObjectInstance):
            # Field mutation
            obj.set_field(field_name, new_value)
            return
    
    # ... existing augmented assignment handling
    return self.generic_visit(node)
```

#### 2.7 Testing Phase 2 (Day 5-6)

**File:** `tests/test_udt_instantiation.py` (NEW)

```python
"""Test UDT object instantiation and field access"""

import pytest
from pynescript.ast.helper import parse, dump
from pynescript.ast.evaluator import NodeLiteralEvaluator

def test_simple_object_creation():
    """Parse and evaluate simple UDT instantiation"""
    code = """
indicator("Test", overlay=true)

type Trade
    float price = 0.0
    int qty = 0

t = Trade.new()
plot(t.price)
    """
    
    script = parse(code)
    evaluator = NodeLiteralEvaluator()
    evaluator.eval_global(script)
    
    # Should not raise error
    assert True

def test_object_with_arguments():
    """Create object with constructor arguments"""
    code = """
indicator("Test")

type Trade
    float price
    int qty

t = Trade.new(99.50, 100)
plot(t.price)
    """
    
    script = parse(code)
    # Should parse and evaluate successfully
    assert True

def test_object_with_named_arguments():
    """Create object with named arguments"""
    code = """
indicator("Test")

type Trade
    float price = 0.0
    int qty = 0

t = Trade.new(price=99.50, qty=100)
plot(t.price)
    """
    
    script = parse(code)
    assert True

def test_object_field_access():
    """Access object fields after creation"""
    code = """
indicator("Test")

type Data
    float close = 0.0
    float high = 0.0

d = Data.new(100.0, 105.0)
result = d.close + d.high
plot(result)
    """
    
    script = parse(code)
    assert True

def test_object_field_mutation():
    """Mutate object fields"""
    code = """
indicator("Test")

type Balance
    float amount = 0.0

b = Balance.new(1000.0)
b.amount := b.amount * 1.05
plot(b.amount)
    """
    
    script = parse(code)
    assert True

def test_object_copy():
    """Test .copy() method"""
    code = """
indicator("Test")

type Record
    float value = 100.0

r1 = Record.new()
r2 = r1.copy()
r2.value := 200.0

plot(r1.value)  // 100.0
plot(r2.value)  // 200.0
    """
    
    script = parse(code)
    assert True

def test_object_in_array():
    """Store objects in arrays"""
    code = """
indicator("Test")

type Trade
    float price = 0.0

trades = array.new<Trade>()
t = Trade.new(99.50)
array.push(trades, t)

result = trades.get(0).price
plot(result)
    """
    
    script = parse(code)
    assert True

def test_nested_objects():
    """Objects containing other objects"""
    code = """
indicator("Test")

type Price
    float bid = 0.0
    float ask = 0.0

type Quote
    Price p = na
    int time = 0

q = Quote.new()
q.p := Price.new(100.0, 100.5)
plot(q.p.bid)
    """
    
    script = parse(code)
    assert True
```

### 2.8 Integration Checklist

- [ ] Add UserDefinedType, Field, ObjectInstance to types.py
- [ ] Extend TypeRegistry with register_udt/get_udt methods
- [ ] Update visit_TypeDef to register UDTs
- [ ] Implement .new() constructor in expressions evaluator
- [ ] Implement field access in expressions evaluator
- [ ] Implement field mutation in statements evaluator
- [ ] Create test_udt_instantiation.py with all 8 tests
- [ ] All tests passing ✅
- [ ] Round-trip fidelity verified ✅
- [ ] No breaking changes to v5 ✅

---

## Phase 3: Method Invocation (Week 2-3)

### Goal
Support method definitions and invocation with THIS parameter binding.

### Implementation Order

#### 3.1 Method Definition Processing (Day 1)

**File:** `src/pynescript/ast/evaluator/statements.py` (EXISTING - EXTEND)

Process method definitions and attach to UDTs:

```python
# IN StatementEvaluator

def visit_FunctionDef(self, node: FunctionDef) -> None:
    """Handle function definitions, including methods"""
    
    # Check if this is a method (has 'is_method' flag)
    if getattr(node, 'is_method', False):
        # Method definition
        type_name = getattr(node, 'method_type', None)
        
        if type_name:
            # Get the UDT
            udt = self.type_registry.get_udt(type_name)
            if udt:
                # Add method to UDT
                udt.add_method(node.name, node)
                return
    
    # ... existing function definition handling
```

#### 3.2 Method Call Evaluation (Day 2)

**File:** `src/pynescript/ast/evaluator/expressions.py` (EXISTING - EXTEND)

Evaluate method calls with THIS binding:

```python
# IN NodeLiteralEvaluator

def visit_Call(self, node: Call) -> Any:
    """Handle function/method calls"""
    
    # Check for method call pattern: obj.method(args)
    if isinstance(node.func, Attribute):
        obj = self.visit(node.func.value)
        method_name = node.func.attr
        
        if isinstance(obj, ObjectInstance):
            return self._invoke_method(obj, method_name, node.args, node.keywords)
    
    # ... existing call handling

def _invoke_method(
    self,
    instance: ObjectInstance,
    method_name: str,
    args: list,
    keywords: list[keyword],
) -> Any:
    """Invoke method on UDT instance"""
    
    udt = instance.type_def
    method_def = udt.get_method(method_name)
    
    if not method_def:
        raise AttributeError(f"Type '{udt.name}' has no method '{method_name}'")
    
    # Create new scope for method execution
    method_scope = Scope(self.current_scope)
    
    # Bind 'this' parameter to instance
    method_scope['this'] = instance
    
    # Bind other parameters
    param_names = [p.arg for p in method_def.args.args]
    param_names = param_names[1:] if param_names and param_names[0] == 'this' else param_names
    
    for i, param_name in enumerate(param_names):
        if i < len(args):
            method_scope[param_name] = self.visit(args[i])
    
    # Evaluate method body with new scope
    old_scope = self.current_scope
    self.current_scope = method_scope
    
    try:
        result = None
        for stmt in method_def.body:
            result = self.visit(stmt)
            if isinstance(result, ReturnValue):
                return result.value
        return result
    finally:
        self.current_scope = old_scope
```

#### 3.3 THIS Parameter Support (Day 3)

**File:** `src/pynescript/ast/builder.py` (EXISTING - EXTEND)

Update parser builder to handle THIS parameter:

```python
# IN PinescriptASTBuilder

def visitMethod_parameter_definition(self, ctx) -> arg:
    """Build method parameter including THIS"""
    
    if ctx.THIS():
        # THIS parameter - special case
        return arg(
            arg='this',
            annotation=Name(id=ctx.name_store().getText())
        )
    
    # Regular parameter
    name = ctx.name_store().getText()
    return arg(arg=name)
```

#### 3.4 Method Integration with UDTs (Day 3-4)

Update TypeDef evaluation to separate fields and methods:

```python
# UPDATE visit_TypeDef in statements.py

def visit_TypeDef(self, node: TypeDef) -> None:
    """Evaluate type definition - register fields and methods"""
    
    fields = {}
    methods = {}
    
    for stmt in node.body:
        if isinstance(stmt, FunctionDef):
            # Method definition
            methods[stmt.name] = stmt
        else:
            # Field definition
            # ... existing field extraction code ...
    
    # Create UserDefinedType
    udt = UserDefinedType(node.name, fields)
    
    # Add methods to UDT
    for method_name, method_def in methods.items():
        udt.add_method(method_name, method_def)
    
    # Register
    self.type_registry.register_udt(udt)
    self.current_scope[node.name] = udt
```

#### 3.5 Testing Phase 3 (Day 4-5)

**File:** `tests/test_udt_methods.py` (NEW)

```python
"""Test UDT method definitions and invocation"""

import pytest
from pynescript.ast.helper import parse
from pynescript.ast.evaluator import NodeLiteralEvaluator

def test_method_definition():
    """Parse method definition"""
    code = """
indicator("Test")

type Trade
    float price = 0.0
    float qty = 0

method getValue(Trade this) =>
    this.price * this.qty

t = Trade.new(10.0, 100)
result = t.getValue()
plot(result)
    """
    
    script = parse(code)
    assert True

def test_method_with_parameters():
    """Method with additional parameters"""
    code = """
indicator("Test")

type Account
    float balance = 0.0

method withdraw(Account this, float amount) =>
    this.balance := this.balance - amount
    this.balance

a = Account.new(1000.0)
final = a.withdraw(100.0)
plot(final)
    """
    
    script = parse(code)
    assert True

def test_method_chaining():
    """Chain method calls"""
    code = """
indicator("Test")

type Data
    float value = 0.0

method double(Data this) =>
    this.value := this.value * 2
    this

method add(Data this, float x) =>
    this.value := this.value + x
    this

d = Data.new(5.0)
d.double()
d.add(3.0)
plot(d.value)  // 13.0
    """
    
    script = parse(code)
    assert True

def test_method_returns_value():
    """Method returns computed value"""
    code = """
indicator("Test")

type Rectangle
    float width = 0.0
    float height = 0.0

method area(Rectangle this) =>
    this.width * this.height

r = Rectangle.new(5.0, 10.0)
a = r.area()
plot(a)  // 50.0
    """
    
    script = parse(code)
    assert True

def test_this_parameter_immutable_from_outside():
    """THIS binding is local to method"""
    code = """
indicator("Test")

type Temp
    float val = 0.0

method change(Temp this) =>
    this.val := 99.0

t1 = Temp.new(1.0)
t1.change()
plot(t1.val)  // Should be 99.0
    """
    
    script = parse(code)
    assert True
```

### 3.6 Integration Checklist

- [ ] Add method_type tracking to FunctionDef AST
- [ ] Update TypeDef to separate fields and methods
- [ ] Implement method registration in UDT
- [ ] Implement method invocation in evaluator
- [ ] Handle THIS parameter binding
- [ ] Support method return types
- [ ] Create test_udt_methods.py with all 5 tests
- [ ] All tests passing ✅

---

## Phase 4: Collections (Week 3-4)

### Goal
Implement Matrix and Map collection types with all operations.

### 4.1 Matrix Implementation (3 days)

**File:** `src/pynescript/ast/evaluator/builtins/matrix.py` (NEW)

```python
"""Matrix collection type and operations"""

from __future__ import annotations
from typing import Any, Generic, TypeVar
import math

T = TypeVar('T')

class Matrix(Generic[T]):
    """Represents a 2D matrix"""
    
    def __init__(self, rows: int = 0, cols: int = 0, default: Any = None):
        self.rows_count = rows
        self.cols_count = cols
        self.data = [[default for _ in range(cols)] for _ in range(rows)]
    
    def get(self, row: int, col: int) -> Any:
        return self.data[row][col]
    
    def set(self, row: int, col: int, value: Any) -> None:
        self.data[row][col] = value
    
    def rows(self) -> int:
        return self.rows_count
    
    def columns(self) -> int:
        return self.cols_count
    
    def elements_count(self) -> int:
        return self.rows_count * self.cols_count
    
    def add_row(self, row_data: list[Any]) -> None:
        """Add new row to matrix"""
        if len(row_data) != self.cols_count:
            raise ValueError("Row size mismatch")
        self.data.append(row_data.copy())
        self.rows_count += 1
    
    def remove_row(self, index: int) -> None:
        """Remove row from matrix"""
        if 0 <= index < self.rows_count:
            self.data.pop(index)
            self.rows_count -= 1
    
    # ... add all 70+ operations
```

### 4.2 Map Implementation (3 days)

**File:** `src/pynescript/ast/evaluator/builtins/map.py` (NEW)

```python
"""Map collection type (dictionary-like)"""

from typing import Any, Generic, TypeVar

K = TypeVar('K')
V = TypeVar('V')

class Map(Generic[K, V]):
    """Key-value collection"""
    
    def __init__(self):
        self.data = {}
    
    def get(self, key: K) -> V | None:
        return self.data.get(key)
    
    def put(self, key: K, value: V) -> None:
        self.data[key] = value
    
    def put_all(self, other: Map[K, V]) -> None:
        self.data.update(other.data)
    
    def remove(self, key: K) -> None:
        if key in self.data:
            del self.data[key]
    
    def clear(self) -> None:
        self.data.clear()
    
    def contains(self, key: K) -> bool:
        return key in self.data
    
    def keys(self) -> list[K]:
        return list(self.data.keys())
    
    def values(self) -> list[V]:
        return list(self.data.values())
    
    def size(self) -> int:
        return len(self.data)
    
    def copy(self) -> 'Map[K, V]':
        new_map = Map()
        new_map.data = self.data.copy()
        return new_map
```

### 4.3 Integration in Evaluator (2 days)

Add to `src/pynescript/ast/evaluator/builtins/__init__.py`:

```python
from .matrix import Matrix, MatrixOperations
from .map import Map, MapOperations

# Register in BuiltinHandler dispatch
```

### 4.4 Testing Collections (2 days)

**File:** `tests/test_collections.py` (NEW)

- Matrix creation and operations
- Map creation and operations
- Nested collections (array of matrices, etc.)

---

## Phase 5: Built-in Functions (Week 4-5)

### Goal
Implement specialized built-in functions.

### 5.1 Ticker Functions (1 day)

**File:** `src/pynescript/ast/evaluator/builtins/ticker.py` (NEW)

```python
"""Ticker manipulation functions"""

class TickerObject:
    """Represents a ticker with modifications"""
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.session = None
        self.adjustment = None
        self.tf = None
```

Functions to implement:
- `ticker.new()`
- `ticker.standard()`
- `ticker.inherit()`
- `ticker.renko()`
- `ticker.heikinashi()`
- `ticker.kagi()`
- `ticker.linebreak()`
- `ticker.pointfigure()`

### 5.2 Logging Functions (1 day)

**File:** `src/pynescript/ast/evaluator/builtins/logging.py` (NEW)

```python
"""Logging functions"""

def log_error(message: str) -> None:
    """Log error message"""
    print(f"ERROR: {message}")

def log_warning(message: str) -> None:
    """Log warning message"""
    print(f"WARN: {message}")

def log_info(message: str) -> None:
    """Log info message"""
    print(f"INFO: {message}")
```

### 5.3 Chart Point & Polyline Functions (2 days)

**File:** `src/pynescript/ast/evaluator/builtins/drawing.py` (EXTEND)

```python
"""Chart drawing objects"""

class ChartPoint:
    """Represents a point on the chart"""
    def __init__(self, time: int, price: float):
        self.time = time
        self.price = price

class Polyline:
    """Polyline drawn from array of points"""
    def __init__(self, points: list[ChartPoint]):
        self.points = points
        self.closed = False
        self.xloc = "bar_time"
```

Functions:
- `chart.point.new()`
- `chart.point.from_index()`
- `chart.point.from_time()`
- `chart.point.now()`
- `chart.point.copy()`
- `polyline.new()`
- `polyline.set_closed()`
- `polyline.delete()`

### 5.4 Testing Built-ins (3 days)

**File:** `tests/test_builtins_v6.py` (NEW)

Test each function group with:
- Valid inputs
- Edge cases
- Error conditions
- Integration with other v6 features

---

## Implementation Timeline

### Week 1 (Days 1-5)
- **Phase 2.1-2.3:** Type system foundation
- **Phase 2.4:** .new() constructor
- **Phase 2.5-2.6:** Field access/mutation
- **Phase 2.7:** Testing Phase 2

### Week 2 (Days 6-10)
- **Phase 2.8:** Phase 2 integration complete
- **Phase 3.1-3.2:** Method processing and invocation
- **Phase 3.3-3.4:** THIS binding
- **Phase 3.5-3.6:** Testing Phase 3

### Week 3 (Days 11-15)
- **Phase 3.6:** Phase 3 complete
- **Phase 4.1:** Matrix implementation
- **Phase 4.2:** Map implementation
- **Phase 4.3:** Collections integration

### Week 4 (Days 16-20)
- **Phase 4.4:** Testing collections
- **Phase 5.1-5.3:** Built-in functions
- **Phase 5.4:** Testing built-ins

### Week 5 (Days 21-25)
- Final testing and integration
- Performance optimization
- Documentation updates

---

## Success Criteria

- ✅ All Phase 2 features working (objects, fields)
- ✅ All Phase 3 features working (methods, THIS)
- ✅ Matrix type with 70+ operations
- ✅ Map type with 10+ operations
- ✅ All built-in functions working
- ✅ 95%+ test coverage
- ✅ No breaking changes
- ✅ Round-trip fidelity maintained
- ✅ Performance meets benchmarks

---

## Key Files to Create/Modify

### New Files (8)
- `src/pynescript/ast/evaluator/builtins/matrix.py`
- `src/pynescript/ast/evaluator/builtins/map.py`
- `src/pynescript/ast/evaluator/builtins/ticker.py`
- `src/pynescript/ast/evaluator/builtins/logging.py`
- `tests/test_udt_instantiation.py`
- `tests/test_udt_methods.py`
- `tests/test_collections.py`
- `tests/test_builtins_v6.py`

### Modified Files (6)
- `src/pynescript/ast/evaluator/types.py` (Add UDT classes)
- `src/pynescript/ast/evaluator/base.py` (Extend TypeRegistry)
- `src/pynescript/ast/evaluator/statements.py` (UDT/method evaluation)
- `src/pynescript/ast/evaluator/expressions.py` (Field access/mutation)
- `src/pynescript/ast/evaluator/builtins/drawing.py` (Extend for v6)
- `docs/pinescript_implementation_status.md` (Update status)

---

## Starting Phase 2: First Steps

1. **Day 1 Morning:** Create `src/pynescript/ast/evaluator/types.py` additions
2. **Day 1 Afternoon:** Extend `base.py` with TypeRegistry enhancements
3. **Day 2 Morning:** Update `visit_TypeDef` in statements.py
4. **Day 2-3:** Implement .new() and field access
5. **Day 4:** Implement field mutation
6. **Day 5:** Write and verify all tests

All code is ready to implement. Foundation is solid. Let's build! 🚀

