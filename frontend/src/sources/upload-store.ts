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
