from pynescript.ast.helper import parse, unparse
import pynescript.ast.unparser as u
from pynescript.ast import node as ast

original_visit_Call = u.NodeUnparser.visit_Call

def custom_visit_Call(self, node: ast.Call):
    if isinstance(node.func, ast.Attribute) and node.func.attr in {"round", "floor", "ceil", "abs", "pow", "max", "min", "sqrt", "exp", "log", "log10", "sign"}:
        if not (isinstance(node.func.value, ast.Name) and node.func.value.id == "math"):
            self.write("math.")
            self.write(node.func.attr)
            with self.delimit("(", ")"):
                self.traverse(node.func.value)
                if node.args:
                    self.write(", ")
                    self.items_view(self.traverse, node.args)
            return

    original_visit_Call(self, node)

u.NodeUnparser.visit_Call = custom_visit_Call

print(unparse(parse("myVar[10].round()")))
print(unparse(parse("math.round(myVar[10])")))
print(unparse(parse("time.floor()")))
