# Pine Script v6 UDT & Methods Implementation Guide

**Date:** October 21, 2025  
**Status:** Planning & Implementation  
**Overall Completion:** 0% (Planning phase)

## Executive Summary

This document outlines the complete implementation of Pine Script v6's User Defined Types (UDTs) and methods system, along with complementary v6 features and remaining built-in functions.

### Key v6 Features to Implement

1. **User Defined Types (UDTs)** - Core OOP structure
2. **Methods** - Function binding to types and instances
3. **Dynamic Request Calls** - Series string arguments for request.*()
4. **Enhanced Collections** - Matrix and Map types with full operation sets
5. **Built-in Functions** - Ticker, Logging, Chart Points, Polylines
6. **v6-Specific Improvements** - Scope limit removal, improved for loops, bid/ask variables

---

## Part 1: User Defined Types (UDTs)

### 1.1 Syntax & Grammar

#### Type Declaration Syntax

```pine
//@type MyCustomType - holds information about a trading event
type MyCustomType
    int timestamp
    float price
    string name = "default"
    bool active = true
```

**ANTLR Grammar Rules to Add/Modify:**

```antlr
type_declaration
    : EXPORT? TYPE name NEWLINE INDENT type_field_definitions DEDENT
    ;

type_field_definitions
    : type_field_definition+
    ;

type_field_definition
    : type_specification? name_store (EQUAL expression)? NEWLINE
    | VARIP type_specification? name_store (EQUAL expression)? NEWLINE
    ;

type_specification
    : type_name type_qualifier?
    ;

type_name
    : BUILTIN_TYPE
    | name
    | array_type_specification
    | matrix_type_specification
    | map_type_specification
    ;

array_type_specification
    : ARRAY LT type_name GT
    ;

matrix_type_specification
    : MATRIX LT type_name GT
    ;

map_type_specification
    : MAP LT type_name COMMA type_name GT
    ;

type_qualifier
    : SIMPLE
    | SERIES
    | CONST
    | INPUT
    ;
```

#### Object Creation Syntax

```pine
// Create with default values
obj = MyType.new()

// Create with arguments
obj = MyType.new(123, 45.67, "test")

// Create with named arguments
obj = MyType.new(timestamp=123, price=45.67, name="test")

// Copy existing object (shallow copy)
obj2 = MyType.copy(obj)
```

#### Field Access & Mutation

```pine
// Read field
value = obj.timestamp

// Mutate field
obj.price := 99.99
```

#### Method Call Syntax

```pine
// Call instance method
result = obj.myMethod(arg1, arg2)

// Call type method
result = MyType.myStaticMethod(arg1)
```

### 1.2 AST Node Definitions (ASDL)

**New ASDL Nodes:**

```asdl
-- Type declaration
TypeDecl(
    identifier name,
    Field* fields,
    annotation* annotations,
    expr? export
)

-- Field definition
Field(
    identifier name,
    expr type,
    expr? default_value,
    bool varip
)

-- Object instantiation
ObjectNew(
    expr type,
    keyword* args,
    expr* values
)

-- Field access
FieldAccess(
    expr value,
    identifier field,
    bool is_call
)

-- Field assignment
FieldAssign(
    expr target,
    identifier field,
    expr value
)

-- Method definition (extends current function)
MethodDef(
    identifier name,
    identifier type_name,  -- Type this method belongs to
    arguments args,
    stmt* body,
    annotation* annotations,
    expr? return_type
)

-- Method call
MethodCall(
    expr target,
    identifier method_name,
    argument* args
)

-- Object Copy
ObjectCopy(
    expr target
)
```

### 1.3 Type System Integration

**Key Type Classes to Add:**

```python
# src/pynescript/ast/type_system.py (new file)

class UserDefinedType(Type):
    """Represents a user-defined type"""
    def __init__(self, name: str, fields: Dict[str, Field]):
        self.name = name
        self.fields = fields
        self.methods = {}  # method_name -> MethodDef
    
    def add_method(self, method_def: MethodDef):
        self.methods[method_def.name] = method_def
    
    def get_field(self, name: str) -> Field:
        return self.fields.get(name)
    
    def get_method(self, name: str) -> MethodDef:
        return self.methods.get(name)

class Field:
    """Represents a field in a UDT"""
    def __init__(self, name: str, field_type: Type, default_value=None, varip=False):
        self.name = name
        self.field_type = field_type
        self.default_value = default_value
        self.varip = varip

class ObjectInstance:
    """Runtime representation of a UDT instance"""
    def __init__(self, type_def: UserDefinedType):
        self.type_def = type_def
        self.fields = {}  # field_name -> current_value
        
        # Initialize fields with defaults
        for field_name, field_def in type_def.fields.items():
            self.fields[field_name] = field_def.default_value
    
    def get_field(self, name: str):
        return self.fields.get(name)
    
    def set_field(self, name: str, value):
        if name in self.type_def.fields:
            self.fields[name] = value
    
    def copy(self):
        """Create shallow copy of this object"""
        new_instance = ObjectInstance(self.type_def)
        new_instance.fields = self.fields.copy()
        return new_instance
```

### 1.4 Parser Implementation

**Update PinescriptASTBuilder to:**

1. Track type definitions in global scope
2. Create TypeDecl nodes from type_declaration rules
3. Parse field definitions with proper type specifications
4. Handle default values for fields
5. Create ObjectNew nodes for `TypeName.new()` calls
6. Parse method definitions within type scope
7. Track object field access and mutations

**Key Methods to Add:**

```python
def visitType_declaration(self, ctx):
    """Build TypeDecl node"""
    type_name = ctx.name().getText()
    fields = []
    
    for field_ctx in ctx.type_field_definitions().type_field_definition():
        field = self.visitType_field_definition(field_ctx)
        fields.append(field)
    
    type_decl = TypeDecl(
        name=type_name,
        fields=fields,
        annotations=self.collect_annotations(ctx),
        export=self.is_export(ctx)
    )
    return type_decl

def visitType_field_definition(self, ctx):
    """Build Field node"""
    name = ctx.name_store().getText()
    type_spec = self.visitType_specification(ctx.type_specification()) if ctx.type_specification() else None
    default_val = self.visit(ctx.expression()) if ctx.expression() else None
    varip = ctx.VARIP() is not None
    
    return Field(name=name, type=type_spec, default_value=default_val, varip=varip)
```

---

## Part 2: Methods System

### 2.1 User-Defined Methods

#### Syntax

```pine
//@type DataPoint
type DataPoint
    float value
    float previous = 0

//@method Calculate changes since previous value
//@param this DataPoint - implicit self parameter
//@returns float - the change value
method change(DataPoint this) =>
    this.value - this.previous

// Usage:
point = DataPoint.new(100, 95)
delta = point.change()  // Returns 5
```

#### Grammar Rules

```antlr
method_declaration
    : EXPORT? METHOD name LPAR (THIS type_name)? (COMMA parameter_definition)* RPAR
      (RARROW type_specification)? local_block
    ;
```

### 2.2 Built-in Methods

#### .new() Constructor

```pine
// Implicit built-in for all UDTs
obj = MyType.new()
obj = MyType.new(field1_val, field2_val)
obj = MyType.new(field1=val1, field2=val2)
```

#### .copy() Method

```pine
// Shallow copy - references to complex types are shared
obj2 = obj1.copy()

// Deep copy example (user-defined):
method deepCopy(MyType this) =>
    MyType.new(
        primitiveField=this.primitiveField,
        arrayField=this.arrayField.copy()  // Explicit copy of array
    )
```

### 2.3 Method Binding Implementation

**In Evaluator:**

```python
class UDTMethodResolver:
    """Resolves method calls on UDT instances"""
    
    def resolve_method(self, instance: ObjectInstance, method_name: str, args: List):
        """Find and execute method"""
        type_def = instance.type_def
        
        # Check for built-in methods first
        if method_name == 'new':
            return self._handle_new(type_def, args)
        elif method_name == 'copy':
            return self._handle_copy(instance, args)
        
        # Check for user-defined methods
        method_def = type_def.get_method(method_name)
        if method_def:
            # Bind 'this' to instance and execute
            return self._execute_method(instance, method_def, args)
        
        raise AttributeError(f"Method '{method_name}' not found on type '{type_def.name}'")
    
    def _handle_new(self, type_def: UserDefinedType, args: List):
        """Create new instance of UDT"""
        instance = ObjectInstance(type_def)
        
        # Set fields from arguments
        field_names = list(type_def.fields.keys())
        for i, arg in enumerate(args):
            if i < len(field_names):
                instance.set_field(field_names[i], arg)
        
        return instance
    
    def _handle_copy(self, instance: ObjectInstance, args: List):
        """Create shallow copy of instance"""
        return instance.copy()
    
    def _execute_method(self, instance: ObjectInstance, method_def: MethodDef, args: List):
        """Execute user-defined method with bound 'this'"""
        # Create new local scope
        # Bind 'this' to instance
        # Execute method body
        # Return result
        pass
```

---

## Part 3: Collections (Matrix & Map)

### 3.1 Matrix Type

#### Syntax & Grammar

```pine
// Create 3x3 float matrix
m = matrix.new<float>(3, 3, 0.0)

// Create dynamic matrix
m = matrix.new<int>()

// Type specification
matrix<float>
matrix<MyCustomType>
```

#### Operations

```pine
matrix.get(m, row, col)
matrix.set(m, row, col, value)
matrix.rows(m)
matrix.columns(m)
matrix.elements_count(m)

matrix.add_row(m, array_values)
matrix.remove_row(m, row_index)
matrix.add_col(m, array_values)
matrix.remove_col(m, col_index)

// Mathematical operations
matrix.transpose(m)
matrix.mult(m1, m2)
matrix.add(m1, m2)
matrix.diff(m1, m2)
matrix.inv(m)
matrix.pinv(m)
matrix.det(m)
matrix.rank(m)
matrix.trace(m)

// Analysis
matrix.min(m)
matrix.max(m)
matrix.avg(m)
matrix.sum(m)
matrix.median(m)
matrix.mode(m)

// Utilities
matrix.fill(m, value, from_col, to_col, from_row, to_row)
matrix.copy(m)
matrix.reshape(m, rows, cols)
matrix.submatrix(m, from_row, to_row, from_col, to_col)
matrix.concat(m1, m2)
matrix.reverse(m)
matrix.sort(m, column)
matrix.swap_rows(m, row1, row2)
matrix.swap_columns(m, col1, col2)

// Predicates
matrix.is_square(m)
matrix.is_diagonal(m)
matrix.is_identity(m)
matrix.is_triangular(m)
matrix.is_symmetric(m)
matrix.is_antisymmetric(m)
matrix.is_zero(m)
matrix.is_stochastic(m)
matrix.is_binary(m)
matrix.is_antidiagonal(m)

// Eigenvalue/eigenvector
matrix.eigenvalues(m)
matrix.eigenvectors(m)
matrix.kron(m1, m2)
```

**ASDL Nodes:**

```asdl
Matrix(type_name element_type)
MatrixOp(str operation, expr matrix, expr* args)
```

### 3.2 Map Type

#### Syntax & Grammar

```pine
// Create map with string keys and int values
m = map.new<string, int>()

// Type specification
map<string, float>
map<int, MyCustomType>
```

#### Operations

```pine
// Basic operations
map.get(m, key)
map.put(m, key, value)
map.put_all(m1, m2)  // Copy all key-value pairs
map.remove(m, key)
map.clear(m)

// Query
map.contains(m, key)
map.keys(m)    // Returns array of keys
map.values(m)  // Returns array of values
map.size(m)

// Copy
map.copy(m)
```

**ASDL Nodes:**

```asdl
Map(type_name key_type, type_name value_type)
MapOp(str operation, expr map, expr* args)
```

---

## Part 4: Remaining Built-in Functions

### 4.1 Ticker Functions (8 functions)

```pine
// Create modified ticker
ticker = ticker.new("EURUSD", session = session.extended, adjustment = adjustment.splits)

// Modify existing ticker
ticker.renko("ATR", 0.5)
ticker.heikinashi()
ticker.kagi(10)
ticker.linebreak(3)
ticker.pointfigure(10)
ticker.renko("PercentageLTP", 1.5)  // NEW in v6 April 2025

ticker.standard()
ticker.inherit(syminfo.main_tickerid)
```

**Module:** `src/pynescript/ast/evaluator/builtins/ticker.py`

### 4.2 Logging Functions (3 functions)

```pine
log.error("Error occurred: " + error_msg)
log.warning("Warning: calculation took too long")
log.info("Processing bar " + str.tostring(bar_index))
```

**Module:** `src/pynescript/ast/evaluator/builtins/logging.py`

### 4.3 Chart Point Functions (5 functions)

```pine
// Create chart point
pt = chart.point.new(time, price)
pt = chart.point.from_index(bar_index, price)
pt = chart.point.from_time(timestamp, price)
pt = chart.point.now(price)
pt_copy = chart.point.copy(pt)
```

**Module:** `src/pynescript/ast/evaluator/builtins/drawing.py` (extend)

### 4.4 Polyline Functions (3 functions)

```pine
// Create polyline from array of chart points
points = array.new<chart.point>()
array.push(points, chart.point.new(time, high))
array.push(points, chart.point.new(time, low))

polyline = polyline.new(points, closed = false, xloc = xloc.bar_time)
polyline.set_closed(polyline, true)
polyline.delete(polyline)
```

**Module:** `src/pynescript/ast/evaluator/builtins/drawing.py` (extend)

---

## Part 5: v6-Specific Features

### 5.1 Dynamic Request Calls

**Feature:** `request.*()` functions accept series string arguments

```pine
// Dynamically change requested symbol per bar
symbol_series = input("BTCUSDT")
higher_tf_series = input("D")

data = request.security(symbol_series, higher_tf_series, close)
```

**Implementation:**
- Update request.* handlers to accept str | float (not just const)
- Track dynamic context per bar
- Return series instead of single value for dynamic calls

### 5.2 Scope Limit Removal

**Feature:** v6 removed the 550-scope limit

**Implementation:**
- Remove scope counting logic from compiler
- Update validation to not check scope count

### 5.3 Improved For Loop Boundaries

**Feature:** `to_num` boundary evaluated dynamically

```pine
arr = array.from(1, 2, 3, 4, 5)
n = 3
for i = 0 to n
    n := n - 1  // This now affects remaining iterations
    plot(arr.get(i))
```

**Implementation:**
- For loops re-evaluate `to` expression before each iteration
- v5: `to` expression evaluated once at start

### 5.4 New Built-in Variables

```pine
bid   // Highest price active buyer will pay (1T timeframe only)
ask   // Lowest price active seller will accept (1T timeframe only)

syminfo.current_contract  // Underlying contract for continuous futures
```

---

## Implementation Roadmap

### Phase 1: Grammar & Parser (Week 1)
- [ ] Update ANTLR grammar for UDTs and methods
- [ ] Regenerate parser artifacts
- [ ] Update PinescriptASTBuilder

### Phase 2: Type System (Week 2)
- [ ] Create Type class hierarchy
- [ ] Implement UserDefinedType and Field classes
- [ ] Integrate with symbol table

### Phase 3: Core UDT Support (Week 2-3)
- [ ] Parse type declarations
- [ ] Implement .new() constructor
- [ ] Support field access/mutation
- [ ] Implement .copy() method

### Phase 4: Methods (Week 3)
- [ ] Parse method declarations
- [ ] Implement method binding
- [ ] Support `this` parameter
- [ ] Handle method calls

### Phase 5: Collections (Week 4)
- [ ] Implement Matrix type
- [ ] Implement Map type
- [ ] Add all matrix operations
- [ ] Add all map operations

### Phase 6: Built-in Functions (Week 4-5)
- [ ] Ticker functions
- [ ] Logging functions
- [ ] Chart point functions
- [ ] Polyline functions

### Phase 7: v6 Features (Week 5)
- [ ] Dynamic request calls
- [ ] Scope limit removal
- [ ] Improved for loops
- [ ] New bid/ask variables

### Phase 8: Testing & Documentation (Week 6)
- [ ] Unit tests for all features
- [ ] Integration tests
- [ ] Documentation updates
- [ ] Performance optimization

---

## File Changes Summary

### New Files
- `src/pynescript/ast/type_system.py` - Type class hierarchy
- `src/pynescript/ast/udt_manager.py` - UDT registry and management
- `src/pynescript/ast/evaluator/builtins/matrix.py` - Matrix operations
- `src/pynescript/ast/evaluator/builtins/map.py` - Map operations
- `src/pynescript/ast/evaluator/builtins/ticker.py` - Ticker functions
- `src/pynescript/ast/evaluator/builtins/logging.py` - Logging functions
- `tests/test_udt_methods.py` - UDT/method tests
- `tests/test_matrix.py` - Matrix collection tests
- `tests/test_map.py` - Map collection tests

### Modified Files
- `src/pynescript/ast/grammar/antlr4/resource/PinescriptParser.g4` - Grammar updates
- `src/pynescript/ast/builder.py` - Parser visitor updates
- `src/pynescript/ast/evaluator.py` - Evaluator core updates
- `src/pynescript/ast/evaluator/builtins/drawing.py` - Add chart.point and polyline
- `src/pynescript/ast/unparser.py` - Unparser updates for new syntax
- `docs/pinescript_implementation_status.md` - Status tracking

---

## Testing Strategy

### Unit Tests
- Type declaration parsing
- Field definition parsing
- Object instantiation
- Field access/mutation
- Method definitions and calls
- Built-in methods (.new(), .copy())
- Matrix/Map operations
- Built-in function behaviors

### Integration Tests
- Parse + unparse round-trip
- Complete scripts with UDTs
- Scripts mixing UDTs with regular types
- Collection nesting (array of matrices, etc.)
- All v6 features together

### Performance Tests
- Large UDT collections
- Deep object hierarchies
- Matrix math operations
- Map lookups at scale

---

## References

- Official v6 Docs: https://www.tradingview.com/pine-script-docs/
- Objects Page: https://www.tradingview.com/pine-script-docs/language/objects/
- Methods Page: https://www.tradingview.com/pine-script-docs/language/methods/
- Release Notes: https://www.tradingview.com/pine-script-docs/release-notes/
- Migration Guide: https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-6/

---

## Success Criteria

- [ ] Parse all v6 UDT syntax correctly
- [ ] Create and access objects in evaluator
- [ ] Support method definitions and calls
- [ ] All matrix operations working
- [ ] All map operations working
- [ ] Ticker/logging/chart.point/polyline functions implemented
- [ ] Dynamic request calls supported
- [ ] For loop boundary improvement working
- [ ] 95%+ test coverage
- [ ] All tests passing
- [ ] Complete documentation
- [ ] No breaking changes to v5 compatibility
