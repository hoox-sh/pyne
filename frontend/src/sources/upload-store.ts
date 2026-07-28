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
 * Shared stash for CSV/JSON uploads used by the `csv-upload` source.
 * Decoupled from legacy state.js so Solid store and plugins can both use it.
 */

import type { Bar } from '../store/types';

let uploadedBars: Bar[] | null = null;
let uploadedName: string | null = null;

export function setUploadedBars(bars: Bar[], fileName?: string) {
  uploadedBars = bars.length ? bars : null;
  uploadedName = fileName || null;
}

export function getUploadedBars(): Bar[] | null {
  return uploadedBars;
}

export function getUploadedFileName(): string | null {
  return uploadedName;
}

export function clearUploadedBars() {
  uploadedBars = null;
  uploadedName = null;
}
