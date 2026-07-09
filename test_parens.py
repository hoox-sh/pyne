from pynescript.ast.helper import parse, unparse
import pynescript.ast.unparser as u

# Patch it back to the old version
def old_visit_Attribute(self, node):
    self.set_precedence(u.Precedence.ATOM, node.value)
    self.traverse(node.value)
    self.write(".")
    self.write(node.attr)
    
u.NodeUnparser.visit_Attribute = old_visit_Attribute

print(unparse(parse("(myVar[10]).round()")))
