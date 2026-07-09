import sys
import traceback
import json

from src.pynescript.ast.linter import lint_file

try:
    print("Linting grid.gemini.pine...")
    warnings = lint_file("/home/jango/Git/Grid/Grid/grid.gemini.pine")
    
    if warnings:
        print("Lint errors/warnings found:")
        for w in warnings:
            print(w)
    else:
        print("No lint errors found!")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
