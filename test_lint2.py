import sys
import traceback
import json

from src.pynescript.ast.linter import Linter
from src.pynescript.ast.helper import parse

with open("/home/jango/Git/Grid/Grid/grid.gemini.pine", "r") as f:
    code = f.read()

try:
    print("Parsing...")
    ast = parse(code)
    
    print("Linting...")
    linter = Linter()
    errors = linter.lint(ast)
    
    if errors:
        print("Lint errors found:")
        for err in errors:
            print(err)
    else:
        print("No lint errors found!")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
