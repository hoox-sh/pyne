from __future__ import annotations

import sys

from pynescript.ast.evaluator import NodeLiteralEvaluator


print(f"Python executable: {sys.executable}")
print(f"sys.path: {sys.path}")
print(f"NodeLiteralEvaluator file: {sys.modules['pynescript.ast.evaluator'].__file__}")
print(f"Has evaluate_script: {hasattr(NodeLiteralEvaluator, 'evaluate_script')}")

evaluator = NodeLiteralEvaluator()
print(f"Instance has evaluate_script: {hasattr(evaluator, 'evaluate_script')}")
