# Features

PyneScript provides comprehensive support for parsing, analyzing, and transforming Pine Script™ code. This page details all available features.

## Core Features

### Complete Pine Script™ Parsing

PyneScript supports the full Pine Script™ v5-v6 grammar:

- **Version declarations**: `//@version=5`, `//@version=6`
- **All statement types**: assignments, function calls, if/else, for/while loops, switch statements
- **All expression types**: arithmetic, logical, comparison, ternary operators
- **Type annotations**: `int`, `float`, `bool`, `string`, `color`, `array`, `matrix`, `map`
- **Function definitions**: Including parameter types, default values, and return types
- **User-defined types**: Type declarations with `type` keyword
- **Method declarations**: Custom methods on user-defined types
- **Annotations**: `//@description`, `//@param`, `//@returns`, and more

### AST Manipulation

The Abstract Syntax Tree (AST) provides a structured representation of Pine Script™ code:

```python
from pynescript.ast.helper import parse, dump

script = """
//@version=5
indicator("Example")
plot(close)
"""

tree = parse(script)
print(dump(tree))
```

#### AST Features

- **Node types**: 50+ node types covering all Pine Script™ constructs
- **Tree traversal**: Walk the AST with `walk()`, `iter_fields()`, `iter_child_nodes()`
- **Pattern matching**: Find specific patterns in the code
- **Metadata preservation**: Line numbers, column positions, and comments

### Transformation

Transform AST nodes to modify scripts programmatically:

```python
from pynescript.ast.transformer import NodeTransformer
from pynescript.ast.helper import parse, unparse

class VariableRenamer(NodeTransformer):
    def visit_Name(self, node):
        if node.id == 'old_name':
            node.id = 'new_name'
        return node

script = "x = old_name + 1"
tree = parse(script)
new_tree = VariableRenamer().visit(tree)
print(unparse(new_tree))  # x = new_name + 1
```

### Round-Trip Fidelity

Parse and unparse scripts without losing information:

- **Preserves formatting**: Comments and whitespace are maintained
- **Maintains semantics**: The unparsed code is functionally equivalent
- **Annotation handling**: Special comments are preserved and associated with appropriate nodes

### Expression Evaluation

Evaluate Pine Script™ expressions directly in Python:

```python
from pynescript.ast.helper import literal_eval

# Basic arithmetic
result = literal_eval("1 + 2 * 3")  # 7

# Built-in functions
rsi_value = literal_eval("ta.rsi([100, 102, 101, 103, 105], 5)")

# String operations
text = literal_eval("'Hello' + ' ' + 'World'")  # "Hello World"
```

#### Supported Evaluations

- **Arithmetic operations**: `+`, `-`, `*`, `/`, `%`
- **Logical operations**: `and`, `or`, `not`
- **Comparison operations**: `==`, `!=`, `<`, `>`, `<=`, `>=`
- **Ternary operator**: `condition ? true_value : false_value`
- **Built-in constants**: `close`, `open`, `high`, `low`, `volume`
- **149+ built-in functions**: See [Built-in Functions](#built-in-functions)

## Built-in Functions

PyneScript implements 149+ Pine Script™ built-in functions with 997 tests (100% pass rate).

### Technical Analysis (`ta.*`)

#### Moving Averages
- `ta.sma()` - Simple Moving Average
- `ta.ema()` - Exponential Moving Average
- `ta.wma()` - Weighted Moving Average
- `ta.vwma()` - Volume-Weighted Moving Average
- `ta.alma()` - Arnaud Legoux Moving Average
- `ta.swma()` - Symmetrically Weighted Moving Average
- `ta.hma()` - Hull Moving Average

#### Oscillators
- `ta.rsi()` - Relative Strength Index
- `ta.stoch()` - Stochastic Oscillator
- `ta.macd()` - Moving Average Convergence Divergence
- `ta.cci()` - Commodity Channel Index
- `ta.mfi()` - Money Flow Index
- `ta.roc()` - Rate of Change
- `ta.tsi()` - True Strength Index
- `ta.cmo()` - Chande Momentum Oscillator

#### Volatility
- `ta.atr()` - Average True Range
- `ta.bb()` - Bollinger Bands
- `ta.bbw()` - Bollinger Bands Width
- `ta.kc()` - Keltner Channels
- `ta.kcw()` - Keltner Channels Width
- `ta.stdev()` - Standard Deviation
- `ta.variance()` - Variance
- `ta.tr()` - True Range

#### Volume
- `ta.obv()` - On-Balance Volume
- `ta.pvt()` - Price-Volume Trend
- `ta.vwap()` - Volume-Weighted Average Price
- `ta.ad()` - Accumulation/Distribution
- `ta.adosc()` - Accumulation/Distribution Oscillator

#### Core Indicators
- `ta.change()` - Difference between current and previous value
- `ta.mom()` - Momentum
- `ta.cross()` - Check if two series cross
- `ta.crossover()` - Check if first series crosses over second
- `ta.crossunder()` - Check if first series crosses under second
- `ta.highest()` - Highest value over a period
- `ta.lowest()` - Lowest value over a period
- `ta.valuewhen()` - Value when condition was true
- `ta.barssince()` - Bars since condition was true
- `ta.pivothigh()` - Pivot high detection
- `ta.pivotlow()` - Pivot low detection

#### Advanced
- `ta.sar()` - Parabolic SAR
- `ta.linreg()` - Linear Regression
- `ta.correlation()` - Correlation Coefficient
- `ta.median()` - Median value
- `ta.mode()` - Most common value
- `ta.percentile_linear_interpolation()` - Percentile with interpolation
- `ta.percentile_nearest_rank()` - Percentile with nearest rank
- `ta.percentrank()` - Percent rank
- `ta.supertrend()` - SuperTrend indicator

### Array Functions (`array.*`)

- `array.new()` - Create new array
- `array.from()` - Create array from values
- `array.get()` - Get element at index
- `array.set()` - Set element at index
- `array.push()` - Add element to end
- `array.pop()` - Remove and return last element
- `array.unshift()` - Add element to beginning
- `array.shift()` - Remove and return first element
- `array.size()` - Get array size
- `array.slice()` - Extract portion of array
- `array.reverse()` - Reverse array
- `array.sort()` - Sort array
- `array.concat()` - Concatenate arrays
- `array.copy()` - Create copy of array
- `array.clear()` - Remove all elements
- `array.includes()` - Check if value exists
- `array.indexof()` - Find index of value
- `array.lastindexof()` - Find last index of value
- `array.remove()` - Remove element at index
- `array.insert()` - Insert element at index
- `array.fill()` - Fill array with value
- `array.sum()` - Sum of elements
- `array.avg()` - Average of elements
- `array.min()` - Minimum value
- `array.max()` - Maximum value
- `array.median()` - Median value
- `array.mode()` - Most common value
- `array.stdev()` - Standard deviation
- `array.variance()` - Variance

### Matrix Functions (`matrix.*`)

- `matrix.new()` - Create new matrix
- `matrix.get()` - Get element at position
- `matrix.set()` - Set element at position
- `matrix.rows()` - Get number of rows
- `matrix.columns()` - Get number of columns
- `matrix.add_row()` - Add row
- `matrix.add_col()` - Add column
- `matrix.remove_row()` - Remove row
- `matrix.remove_col()` - Remove column
- `matrix.transpose()` - Transpose matrix
- `matrix.mult()` - Matrix multiplication
- `matrix.sum()` - Sum of all elements
- `matrix.avg()` - Average of all elements
- `matrix.min()` - Minimum value
- `matrix.max()` - Maximum value
- `matrix.fill()` - Fill matrix with value
- `matrix.copy()` - Create copy of matrix

### Map Functions (`map.*`)

- `map.new()` - Create new map
- `map.get()` - Get value by key
- `map.put()` - Set key-value pair
- `map.remove()` - Remove key-value pair
- `map.contains()` - Check if key exists
- `map.size()` - Get map size
- `map.keys()` - Get all keys
- `map.values()` - Get all values
- `map.clear()` - Remove all entries
- `map.copy()` - Create copy of map

### String Functions (`str.*`)

- `str.tonumber()` - Convert string to number
- `str.tostring()` - Convert value to string
- `str.format()` - Format string with placeholders
- `str.length()` - Get string length
- `str.upper()` - Convert to uppercase
- `str.lower()` - Convert to lowercase
- `str.startswith()` - Check if starts with substring
- `str.endswith()` - Check if ends with substring
- `str.contains()` - Check if contains substring
- `str.pos()` - Find position of substring
- `str.substring()` - Extract substring
- `str.replace()` - Replace substring
- `str.replace_all()` - Replace all occurrences
- `str.split()` - Split string into array
- `str.match()` - Match regular expression

### Math Functions (`math.*`)

- `math.abs()` - Absolute value
- `math.acos()` - Arc cosine
- `math.asin()` - Arc sine
- `math.atan()` - Arc tangent
- `math.ceil()` - Round up
- `math.floor()` - Round down
- `math.round()` - Round to nearest
- `math.cos()` - Cosine
- `math.sin()` - Sine
- `math.tan()` - Tangent
- `math.exp()` - Exponential
- `math.log()` - Natural logarithm
- `math.log10()` - Base-10 logarithm
- `math.pow()` - Power
- `math.sqrt()` - Square root
- `math.min()` - Minimum of values
- `math.max()` - Maximum of values
- `math.avg()` - Average of values
- `math.sum()` - Sum of values
- `math.sign()` - Sign of number
- `math.random()` - Random number

### Strategy Functions (`strategy.*`)

- `strategy.entry()` - Create entry order
- `strategy.exit()` - Create exit order
- `strategy.close()` - Close position
- `strategy.close_all()` - Close all positions
- `strategy.cancel()` - Cancel order
- `strategy.cancel_all()` - Cancel all orders
- `strategy.order()` - Create order
- `strategy.position_size` - Current position size
- `strategy.position_avg_price` - Average entry price
- `strategy.opentrades` - Number of open trades
- `strategy.closedtrades` - Number of closed trades
- `strategy.wintrades` - Number of winning trades
- `strategy.losstrades` - Number of losing trades
- `strategy.eventrades` - Number of break-even trades
- `strategy.grossprofit` - Gross profit
- `strategy.grossloss` - Gross loss
- `strategy.netprofit` - Net profit

### Plotting Functions (`plot.*`, `plotshape.*`, `plotchar.*`)

- `plot()` - Plot line
- `plotshape()` - Plot shape
- `plotchar()` - Plot character
- `plotarrow()` - Plot arrow
- `plotbar()` - Plot bar
- `plotcandle()` - Plot candle
- `bgcolor()` - Set background color
- `fill()` - Fill between plots
- `hline()` - Horizontal line

### Drawing Functions (`line.*`, `label.*`, `box.*`, `table.*`)

#### Lines
- `line.new()` - Create line
- `line.set_xy1()` - Set first point
- `line.set_xy2()` - Set second point
- `line.set_color()` - Set line color
- `line.set_width()` - Set line width
- `line.set_style()` - Set line style
- `line.delete()` - Delete line

#### Labels
- `label.new()` - Create label
- `label.set_xy()` - Set position
- `label.set_text()` - Set label text
- `label.set_color()` - Set label color
- `label.set_textcolor()` - Set text color
- `label.set_size()` - Set label size
- `label.delete()` - Delete label

#### Boxes
- `box.new()` - Create box
- `box.set_left()` - Set left coordinate
- `box.set_right()` - Set right coordinate
- `box.set_top()` - Set top coordinate
- `box.set_bottom()` - Set bottom coordinate
- `box.set_bgcolor()` - Set background color
- `box.set_border_color()` - Set border color
- `box.delete()` - Delete box

#### Tables
- `table.new()` - Create table
- `table.cell()` - Set cell content
- `table.set_cell()` - Update cell
- `table.clear()` - Clear table
- `table.delete()` - Delete table

### Input Functions (`input.*`)

- `input()` - Basic input
- `input.int()` - Integer input
- `input.float()` - Float input
- `input.bool()` - Boolean input
- `input.string()` - String input
- `input.color()` - Color input
- `input.source()` - Price source input
- `input.timeframe()` - Timeframe input
- `input.symbol()` - Symbol input
- `input.session()` - Session input

### Request Functions (`request.*`)

- `request.security()` - Request data from another symbol
- `request.dividends()` - Request dividend data
- `request.splits()` - Request split data
- `request.earnings()` - Request earnings data
- `request.quandl()` - Request Quandl data

### Color Functions (`color.*`)

- `color.new()` - Create color with transparency
- `color.rgb()` - Create RGB color
- `color.from_gradient()` - Interpolate between colors
- Color constants: `color.red`, `color.green`, `color.blue`, etc.

### Timeframe Functions (`timeframe.*`)

- `timeframe.period` - Current timeframe
- `timeframe.multiplier` - Timeframe multiplier
- `timeframe.isdaily` - Is daily timeframe
- `timeframe.isweekly` - Is weekly timeframe
- `timeframe.ismonthly` - Is monthly timeframe
- `timeframe.isintraday` - Is intraday timeframe

### Ticker Functions (`ticker.*`)

- `ticker.new()` - Create ticker identifier
- `ticker.standard()` - Standard ticker format
- `ticker.heikinashi()` - Heikin Ashi ticker
- `ticker.renko()` - Renko ticker
- `ticker.linebreak()` - Line break ticker
- `ticker.kagi()` - Kagi ticker
- `ticker.pointfigure()` - Point and figure ticker

### Utility Functions

- `na()` - Check if value is NA
- `nz()` - Replace NA with zero or default
- `bool()` - Convert to boolean
- `int()` - Convert to integer
- `float()` - Convert to float
- `string()` - Convert to string
- `color()` - Convert to color
- `timestamp()` - Create timestamp
- `alert()` - Create alert
- `log.info()` - Log information
- `log.warning()` - Log warning
- `log.error()` - Log error

## Extensions

### Pygments Lexer

Syntax highlighting for Pine Script™ in documentation and code editors:

- Full token support for Pine Script™ syntax
- Integration with Sphinx for documentation
- Compatible with any Pygments-based system

### Nautilus Trader Integration

Connect PyneScript with Nautilus Trader for backtesting and live trading:

- Strategy base class for Pine Script™ indicators
- Configuration hooks for parameters
- Event handling for trading signals

## Command-Line Interface

The `pynescript` CLI provides quick access to common operations:

### Commands

- `pynescript parse-and-dump` - Parse and display AST
- `pynescript parse-and-unparse` - Parse and regenerate code
- `pynescript download-builtin-scripts` - Download TradingView® reference scripts

### Examples

```bash
# Parse and display AST
pynescript parse-and-dump my_script.pine

# Verify round-trip stability
pynescript parse-and-unparse my_script.pine > output.pine

# Download test fixtures
pynescript download-builtin-scripts --script-dir fixtures/
```

## Test Coverage

PyneScript maintains comprehensive test coverage:

- **997 evaluation tests** - All built-in functions tested (100% pass rate)
- **Regression tests** - Every TradingView® built-in script parsed and unparsed
- **Round-trip tests** - Structural stability verified for all test fixtures
- **Type checking** - Full mypy coverage for type safety
- **Linting** - Ruff and Black enforce code quality

## Limitations

Some features are not yet implemented:

- **Methods on primitive types**: `array<int>.method()` syntax
- **Some v6-only features**: Certain newer Pine Script™ v6 constructs
- **Runtime evaluation**: Only deterministic expressions can be evaluated
- **Non-deterministic functions**: Functions requiring historical context

See [pinescript_implementation_status.md](pinescript_implementation_status.md) for detailed feature coverage.
