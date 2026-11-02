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

import * as fs from 'fs';
import * as path from 'path';
import { ConfigurationTarget, workspace } from 'vscode';
import { cfg } from './config';
import { log } from './log';
import { state } from './state';

/** PYNE product themes (contributed color themes under `themes/`). */
const PYNE_THEMES: Record<string, { label: string; file: string; description: string }> = {
  void: { label: 'AXIS Void', file: 'axis-void', description: 'Periwinkle accent · dark grey surfaces' },
  signal: { label: 'Hoox Signal', file: 'hoox-signal', description: 'Signal-orange accent · near-black surfaces' },
  volt: { label: 'PYNE Volt', file: 'pyne-volt', description: 'Lime accent · neutral near-black surfaces' },
};

/** Legacy ids kept working for users who saved them before the rename. */
const THEME_ALIASES: Record<string, string> = { orange: 'signal' };

function normalizeThemeId(value: string | undefined, fallback: string): string {
  const raw = (value || fallback).toLowerCase();
  const id = THEME_ALIASES[raw] ?? raw;
  return id === 'none' || id in PYNE_THEMES ? id : fallback;
}

/** Quick-pick items: None first, then the three product themes. */
export function themeChoices() {
  return [
    { id: 'none', label: 'None', description: 'Use user/system settings' },
    ...Object.entries(PYNE_THEMES).map(([id, theme]) => ({
      id,
      label: theme.label,
      description: theme.description,
    })),
  ];
}

// Workbench theme switching is intentionally not automatic. The extension
// never writes workbench.colorTheme; users pick AXIS Void / Hoox Signal /
// PYNE Volt from the VS Code Color Theme picker.

function currentSyntaxId() {
  return normalizeThemeId(cfg<string>('syntaxHighlighting'), 'void');
}

/** Read the bundled `themes/<file>-color-theme.json`. */
function loadThemeJson(
  id: string,
): { tokenColors?: unknown[]; semanticTokenColors?: Record<string, unknown> } | undefined {
  const theme = PYNE_THEMES[id];
  if (!state.extensionPath || !theme) {
    return undefined;
  }
  const file = path.join(state.extensionPath, 'themes', `${theme.file}-color-theme.json`);
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (err) {
    log(`Could not read ${file}: ${err instanceof Error ? err.message : String(err)}`);
    return undefined;
  }
}

/** Grammar root scope — used to keep the token rules Pine-only. */
const PINE_SCOPE = 'source.pinescript';
/** Semantic token selectors are language-scoped with a `:language` suffix. */
const PINE_SEMANTIC_SUFFIX = ':pinescript';

type TextMateRule = { scope?: unknown; settings?: unknown };

/**
 * Prefix TextMate selectors with the Pine grammar root so the rules only
 * match Pine files. `editor.tokenColorCustomizations` is application-scoped
 * (VS Code rejects language overrides for it), but descendant selectors like
 * `source.pinescript keyword` are matched against the token's scope stack.
 */
function pineTextMateRules(rules: TextMateRule[]) {
  return rules.map((rule) => {
    const raw = Array.isArray(rule.scope) ? rule.scope : [rule.scope];
    const scope = raw
      .filter((value): value is string => typeof value === 'string')
      .map((value) => (value.startsWith(PINE_SCOPE) ? value : `${PINE_SCOPE} ${value}`));
    return { ...rule, scope };
  });
}

function isPineTextMateRule(rule: TextMateRule) {
  const raw = Array.isArray(rule.scope) ? rule.scope : [rule.scope];
  return raw.some((value) => typeof value === 'string' && value.startsWith(PINE_SCOPE));
}

function pineSemanticRules(rules: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(rules).map(([selector, value]) => [
      selector.endsWith(PINE_SEMANTIC_SUFFIX) ? selector : `${selector}${PINE_SEMANTIC_SUFFIX}`,
      value,
    ]),
  );
}

/**
 * Pine syntax highlighting, independent of the workbench theme.
 *
 * Adds Pine-scoped rules to the global `editor.tokenColorCustomizations` /
 * `editor.semanticTokenColorCustomizations`, leaving any other language's
 * rules untouched. `none` removes only the Pine rules so the active theme's
 * colors apply again.
 */
export async function applyPyneSyntax() {
  const id = currentSyntaxId();
  const editor = workspace.getConfiguration('editor');

  const tokens = editor.get<Record<string, unknown>>('tokenColorCustomizations') ?? {};
  const semantic = editor.get<Record<string, unknown>>('semanticTokenColorCustomizations') ?? {};

  const otherTokenRules = ((tokens.textMateRules as TextMateRule[] | undefined) ?? []).filter(
    (rule) => !isPineTextMateRule(rule),
  );
  const otherSemanticRules = Object.fromEntries(
    Object.entries((semantic.rules as Record<string, unknown> | undefined) ?? {}).filter(
      ([selector]) => !selector.endsWith(PINE_SEMANTIC_SUFFIX),
    ),
  );

  const nextTokens: Record<string, unknown> = { ...tokens, textMateRules: otherTokenRules };
  const nextSemantic: Record<string, unknown> = { ...semantic, rules: otherSemanticRules };

  if (id === 'none') {
    if (otherTokenRules.length === 0) {
      delete nextTokens.textMateRules;
    }
    if (Object.keys(otherSemanticRules).length === 0) {
      delete nextSemantic.rules;
    }
  } else {
    const theme = loadThemeJson(id);
    if (!theme) {
      return;
    }
    nextTokens.textMateRules = [
      ...otherTokenRules,
      ...pineTextMateRules((theme.tokenColors ?? []) as TextMateRule[]),
    ];
    nextSemantic.rules = {
      ...otherSemanticRules,
      ...pineSemanticRules(theme.semanticTokenColors ?? {}),
    };
  }

  try {
    await editor.update(
      'tokenColorCustomizations',
      Object.keys(nextTokens).length ? nextTokens : undefined,
      ConfigurationTarget.Global,
    );
    await editor.update(
      'semanticTokenColorCustomizations',
      Object.keys(nextSemantic).length ? nextSemantic : undefined,
      ConfigurationTarget.Global,
    );
    log(
      id === 'none'
        ? 'Cleared Pine token rules (using the active theme).'
        : `Applied Pine syntax highlighting: ${id}`,
    );
  } catch (err) {
    log(`Could not apply Pine syntax ${id}: ${err instanceof Error ? err.message : String(err)}`);
  }
}
