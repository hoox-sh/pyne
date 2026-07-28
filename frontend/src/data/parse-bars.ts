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
 * Parse user-uploaded OHLCV from CSV or JSON into Bar[].
 *
 * CSV: header optional; columns time,open,high,low,close[,volume]
 *   time = unix seconds, unix ms, or ISO date string
 * JSON: array of objects or array of [t,o,h,l,c,v?]
 */

import type { Bar } from '../store/types';

function toUnixSeconds(raw: unknown): number | null {
  if (raw == null || raw === '') return null;
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    // ms if > year 2100 in seconds (~4e9)
    return raw > 1e12 ? Math.floor(raw / 1000) : Math.floor(raw);
  }
  const s = String(raw).trim();
  if (!s) return null;
  if (/^\d+(\.\d+)?$/.test(s)) {
    const n = parseFloat(s);
    return n > 1e12 ? Math.floor(n / 1000) : Math.floor(n);
  }
  const ms = Date.parse(s);
  if (!Number.isNaN(ms)) return Math.floor(ms / 1000);
  return null;
}

function num(raw: unknown): number | null {
  if (raw == null || raw === '') return null;
  const n = typeof raw === 'number' ? raw : parseFloat(String(raw).replace(/,/g, ''));
  return Number.isFinite(n) ? n : null;
}

function rowToBar(row: Record<string, unknown> | unknown[]): Bar | null {
  if (Array.isArray(row)) {
    if (row.length < 5) return null;
    const time = toUnixSeconds(row[0]);
    const open = num(row[1]);
    const high = num(row[2]);
    const low = num(row[3]);
    const close = num(row[4]);
    const volume = row.length > 5 ? num(row[5]) ?? undefined : undefined;
    if (time == null || open == null || high == null || low == null || close == null) return null;
    return { time, open, high, low, close, volume: volume ?? undefined };
  }

  const lower: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) lower[k.toLowerCase()] = v;

  const time = toUnixSeconds(
    lower.time ?? lower.timestamp ?? lower.date ?? lower.datetime ?? lower.t,
  );
  const open = num(lower.open ?? lower.o);
  const high = num(lower.high ?? lower.h);
  const low = num(lower.low ?? lower.l);
  const close = num(lower.close ?? lower.c);
  const volume = num(lower.volume ?? lower.vol ?? lower.v) ?? undefined;
  if (time == null || open == null || high == null || low == null || close == null) return null;
  return { time, open, high, low, close, volume };
}

function parseCsv(text: string): Bar[] {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0 && !l.startsWith('#'));
  if (!lines.length) return [];

  const first = lines[0].toLowerCase();
  const hasHeader =
    first.includes('time') ||
    first.includes('date') ||
    first.includes('open') ||
    first.includes('close');

  let headers: string[] | null = null;
  let start = 0;
  if (hasHeader) {
    headers = splitCsvLine(lines[0]).map((h) => h.trim().toLowerCase());
    start = 1;
  }

  const bars: Bar[] = [];
  for (let i = start; i < lines.length; i++) {
    const cells = splitCsvLine(lines[i]);
    let bar: Bar | null;
    if (headers) {
      const obj: Record<string, unknown> = {};
      headers.forEach((h, idx) => {
        obj[h] = cells[idx];
      });
      bar = rowToBar(obj);
    } else {
      bar = rowToBar(cells);
    }
    if (bar) bars.push(bar);
  }
  // Ensure ascending time
  bars.sort((a, b) => a.time - b.time);
  return bars;
}

/** Minimal CSV split (handles quoted fields). */
function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = '';
  let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQ) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQ = false;
        }
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      inQ = true;
    } else if (ch === ',' || ch === ';' || ch === '\t') {
      out.push(cur.trim());
      cur = '';
    } else {
      cur += ch;
    }
  }
  out.push(cur.trim());
  return out;
}

function parseJson(text: string): Bar[] {
  const data = JSON.parse(text);
  const rows = Array.isArray(data) ? data : data?.bars ?? data?.data ?? data?.candles;
  if (!Array.isArray(rows)) {
    throw new Error('JSON must be an array of bars or { bars: [...] }');
  }
  const bars: Bar[] = [];
  for (const row of rows) {
    const bar = rowToBar(row);
    if (bar) bars.push(bar);
  }
  bars.sort((a, b) => a.time - b.time);
  return bars;
}

export function parseOhlcvText(text: string, fileName = ''): Bar[] {
  const trimmed = text.trim();
  if (!trimmed) throw new Error('File is empty');
  const lower = fileName.toLowerCase();
  const asJson =
    lower.endsWith('.json') || trimmed.startsWith('[') || trimmed.startsWith('{');
  const bars = asJson ? parseJson(trimmed) : parseCsv(trimmed);
  if (!bars.length) {
    throw new Error('No valid OHLCV rows found (need time,open,high,low,close)');
  }
  return bars;
}

export async function parseOhlcvFile(file: File): Promise<Bar[]> {
  const text = await file.text();
  return parseOhlcvText(text, file.name);
}
