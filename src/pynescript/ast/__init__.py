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

"""Pine Script AST (Abstract Syntax Tree) manipulation module.

Core public API for parsing, analyzing, and transforming Pine Script code:

Key Functions:
- parse(source, filename, mode): Parse Pine Script source into AST
- dump(node, ...): Generate string representation of AST
- unparse(node): Convert AST back to source code
- literal_eval(node_or_string): Evaluate literal expressions
- walk(node): Depth-first traversal of AST nodes
- copy_location(new_node, old_node): Copy position info between nodes

Key Classes:
- All AST node classes (Script, FunctionDef, Assign, etc.)
- Error handling and visitors
"""

from __future__ import annotations

# ruff: noqa: F403
from .error import *
from .helper import *
from .node import *
from .transformer import *
from .visitor import *
