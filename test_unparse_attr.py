from pynescript.ast.helper import parse, unparse

src = "x = (myVar[10]).myMethod()"
tree = parse(src)
print("Unparsed:")
print(unparse(tree))
