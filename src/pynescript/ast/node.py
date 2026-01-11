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

"""AST Node Class Definitions.

Auto-generated ASDL-based node classes for the Pine Script Abstract Syntax Tree.
Each node type represents a language construct:

- Script: Root module node
- FunctionDef/TypeDef/EnumDef: Definitions
- Assign/AugAssign/Return: Statements
- If/While/For: Control flow
- BinOp/UnaryOp/Compare: Expressions
- Call/Subscript/Attribute: Member access
- Constant/Name/Tuple: Literals and names
"""

from __future__ import annotations

from .grammar.asdl.generated import *  # noqa: F403
