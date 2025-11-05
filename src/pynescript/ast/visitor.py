# Copyright 2024 Yunseong Hwang
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

from __future__ import annotations

from pynescript.ast.helper import iter_fields
from pynescript.ast.node import AST


class NodeVisitor:
    def __init__(self):
        # Optimize: cache visitor methods to avoid repeated getattr calls
        self._visitor_cache: dict[str, callable] = {}
    
    def visit(self, node: AST):
        node_class = node.__class__.__name__
        # Try cache first
        visitor = self._visitor_cache.get(node_class)
        if visitor is None:
            # Cache miss, look up and cache the method
            method = "visit_" + node_class
            visitor = getattr(self, method, self.generic_visit)
            self._visitor_cache[node_class] = visitor
        return visitor(node)

    def generic_visit(self, node: AST):
        for _field, value in iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, AST):
                        self.visit(item)
            elif isinstance(value, AST):
                self.visit(value)
