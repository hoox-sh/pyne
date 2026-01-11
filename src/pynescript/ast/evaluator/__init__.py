# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""AST Node Evaluators - Execute Pine Script AST Nodes.

Evaluators traverse and execute AST nodes to compute values. Composed of
mixin classes organized by AST node category:

- BaseEvaluator: Common visitor infrastructure, context, type registry
- LiteralEvaluator: Constants and literal values
- NameEvaluator: Variable names, attributes, subscript access
- ExpressionEvaluator: Operations (boolean, binary, unary, comparisons, calls)
- StatementEvaluator: Script, assignments, type/function definitions
- BuiltinEvaluator: Built-in functions (plot, ta.sma, etc.)

NodeLiteralEvaluator: Combined evaluator for safe literal evaluation
NodeEvaluator: Full evaluator with all features for complete script execution
"""

from __future__ import annotations

from .base import BaseEvaluator
from .builtins import BuiltinEvaluator
from .expressions import ExpressionEvaluator
from .literals import LiteralEvaluator
from .names import NameEvaluator
from .statements import StatementEvaluator


class NodeLiteralEvaluator(
    BaseEvaluator,
    LiteralEvaluator,
    ExpressionEvaluator,
    BuiltinEvaluator,
    StatementEvaluator,
    NameEvaluator,
):
    """Safe evaluator for literal expressions and built-in functions.

    Combines all evaluator mixins for flexible AST node evaluation.
    """
    pass
