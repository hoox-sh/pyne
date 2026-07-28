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

/**
 * Register all built-in plugins with the unified registry.
 * Safe to call multiple times (idempotent).
 */

import { ensureSourcesRegistered } from '../sources/catalog';
import { ensureStreamsRegistered } from '../streams/catalog';
import { ensureEnginesRegistered } from '../engines/catalog';
import { ensureStoragesRegistered } from '../storage/catalog';

let done = false;

export function ensureBuiltins(): void {
  if (done) return;
  ensureSourcesRegistered();
  ensureStreamsRegistered();
  ensureEnginesRegistered();
  ensureStoragesRegistered();
  done = true;
}

/** Alias used at app entry */
export function registerBuiltins(): void {
  ensureBuiltins();
}

/** @internal test helper — does not clear registry; only resets local flag */
export function _resetBootstrapFlag() {
  done = false;
}
