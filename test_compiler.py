import numpy as np
from pynescript.ast.helper import parse
from pynescript.compiler.compiler import CompilerVisitor

script = """//@version=5
indicator("My Script")
my_sma = ta.sma(close, 14)
my_ema = ta.ema(close, 14)
plot(my_sma, "SMA")
plot(my_ema, "EMA")
"""

tree = parse(script, mode="exec")
compiler = CompilerVisitor()
code = compiler.visit(tree)

print("--- GENERATED COMPILED CODE ---")
print(code)
print("-------------------------------")

# Now let's try to execute it
import numpy as np
import numba
from pynescript.compiler.numba_builtins import *

# Execute the generated code string in current context
exec(code, globals())

# Create some dummy data
n_bars = 100
close_arr = np.linspace(100, 200, n_bars)
open_arr = close_arr - 1
high_arr = close_arr + 1
low_arr = close_arr - 2
vol_arr = np.random.randint(100, 1000, n_bars)

# Run the compiled function
result = execute_script_compiled(open_arr, high_arr, low_arr, close_arr, vol_arr)

print("--- EXECUTION RESULT ---")
for k, v in result.items():
    print(f"{k}: shape={v.shape}, first 15 values=\n{v[:15]}")
