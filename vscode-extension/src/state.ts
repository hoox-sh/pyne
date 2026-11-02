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

import type { LogOutputChannel, StatusBarItem } from 'vscode';
import type { LanguageClient } from 'vscode-languageclient/node';

/** Shared mutable host state. Avoids circular imports between lsp/install/log. */
export const state = {
  client: undefined as LanguageClient | undefined,
  statusBar: undefined as StatusBarItem | undefined,
  output: undefined as LogOutputChannel | undefined,
  /** Serialize start/stop so config changes and palette commands cannot race. */
  clientOp: Promise.resolve() as Promise<void>,
  /** Deduplicate concurrent pip installs (palette + activation prompt). */
  installInFlight: null as Promise<void> | null,
  /** Avoid re-prompting on every startClient in one session after "Later". */
  installPromptDismissed: false,
  /** Extension global storage (for the auto-created virtualenv). */
  globalStorageDir: undefined as string | undefined,
  /** Extension install root (to read the bundled `themes/*.json`). */
  extensionPath: undefined as string | undefined,
};
