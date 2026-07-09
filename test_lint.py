import sys
from src.pynescript.parser.parser import Parser
from src.pynescript.lexer.lexer import Lexer
from src.pynescript.parser.visitors.linter import LinterVisitor
from src.pynescript.parser.exceptions import ParseError
import traceback

with open("/home/jango/Git/Grid/Grid/grid.gemini.pine", "r") as f:
    code = f.read()

try:
    print("Lexing...")
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    
    print("Parsing...")
    parser = Parser(tokens)
    ast = parser.parse()
    
    print("Linting...")
    linter = LinterVisitor()
    linter.visit(ast)
    
    if linter.errors:
        print("Lint errors found:")
        for err in linter.errors:
            print(err)
    else:
        print("No lint errors found!")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()

