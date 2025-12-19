#!/usr/bin/env python3
"""Update copyright headers in all common files."""

from __future__ import annotations

import os
from pathlib import Path


PYTHON_COPYRIGHT = """# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
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
"""

GRAMMAR_COPYRIGHT = """// Copyright 2024-2025 Yunseong Hwang, jango_blockchained
//
// Licensed under the GNU Lesser General Public License Version 3.0 (the "License"); you may not use this file except in
// compliance with the License. You may obtain a copy of the License at
//
// https://www.gnu.org/licenses/lgpl-3.0.en.html
//
// Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
// an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
// specific language governing permissions and limitations under the License.
//
// SPDX-License-Identifier: LGPL-3.0-or-later
"""

MD_COPYRIGHT = """# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
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
"""


def get_copyright_header(filepath: str) -> str:
    """Get appropriate copyright header for file type."""
    if filepath.endswith('.g4'):
        return GRAMMAR_COPYRIGHT
    elif filepath.endswith('.md'):
        return MD_COPYRIGHT
    elif filepath.endswith('.py'):
        return PYTHON_COPYRIGHT
    return ""


def has_copyright_header(content: str) -> bool:
    """Check if file already has a copyright header."""
    return content.strip().startswith(('# Copyright', '// Copyright'))


def remove_old_copyright(content: str) -> str:
    """Remove the old copyright header."""
    lines = content.split('\n')
    i = 0

    for i, line in enumerate(lines):
        if line.startswith(('# Copyright', '// Copyright')):
            break
    
    # Find end of copyright block
    for j in range(i, len(lines)):
        if 'SPDX-License-Identifier' in lines[j]:
            i = j + 1
            break

    # Skip empty lines after copyright
    while i < len(lines) and not lines[i].strip():
        i += 1

    return '\n'.join(lines[i:])


def update_file(filepath: str) -> bool:
    """Update copyright in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.strip():
            return False

        new_header = get_copyright_header(filepath)
        if not new_header:
            return False

        if has_copyright_header(content):
            content = remove_old_copyright(content)

        updated_content = new_header + '\n' + content

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        return True
    except Exception as e:
        print(f"Error updating {filepath}: {e}")
        return False


def find_files(directory: str, extensions: list[str]) -> list[str]:
    """Find all files with given extensions."""
    files = []
    for root, dirs, filenames in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', '_build', 'node_modules', 'venv', '.venv')]
        for filename in filenames:
            if any(filename.endswith(ext) for ext in extensions):
                filepath = os.path.join(root, filename)
                if 'generated' not in filepath:
                    files.append(filepath)
    return sorted(files)


def main():
    """Update copyright headers in all common files."""
    project_root = Path(__file__).parent.parent
    py_files = find_files(str(project_root / 'src'), ['.py'])
    test_files = find_files(str(project_root / 'tests'), ['.py'])
    example_files = find_files(str(project_root / 'examples'), ['.py'])
    g4_files = find_files(str(project_root / 'src'), ['.g4'])
    md_files = find_files(str(project_root / 'docs'), ['.md'])

    all_files = py_files + test_files + example_files + g4_files + md_files

    print(f"Found {len(all_files)} files to update")
    print(f"  - Python (src): {len(py_files)}")
    print(f"  - Python (tests): {len(test_files)}")
    print(f"  - Python (examples): {len(example_files)}")
    print(f"  - ANTLR grammar: {len(g4_files)}")
    print(f"  - Markdown (docs): {len(md_files)}")

    updated = 0
    skipped = 0
    for filepath in all_files:
        if update_file(filepath):
            updated += 1
        else:
            skipped += 1

    print(f"\nUpdated {updated} files, skipped {skipped}")


if __name__ == '__main__':
    main()
