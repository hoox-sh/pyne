// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

import { COMMANDS } from './commands';
import { state } from './state';

const DOWN_HINT =
  'Click for output. Command Palette: PYNE: Install Language Server or PYNE: Restart Language Server.';

export function log(msg: string): void {
  const line = `[PYNE] ${msg}`;
  state.output?.appendLine(line);
}

/** Update the status bar. Click always opens the LSP output channel. */
export function setStatus(text: string, tooltip?: string, down = false): void {
  if (!state.statusBar) return;
  state.statusBar.text = text;
  state.statusBar.command = COMMANDS.showLspOutput;
  const detail = tooltip || text;
  state.statusBar.tooltip = down ? `${detail}\n${DOWN_HINT}` : detail;
  state.statusBar.show();
}
