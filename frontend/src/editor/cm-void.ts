import { EditorView } from '@codemirror/view';
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { tags as t } from '@lezer/highlight';

/** Void canvas CodeMirror theme — matches AXIS void indigo tokens */
export const voidEditorTheme = EditorView.theme(
  {
    '&': {
      height: '100%',
      backgroundColor: '#111218',
      color: '#eceef4',
      fontSize: '13px',
    },
    '.cm-scroller': {
      overflow: 'auto',
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    },
    '.cm-content': {
      caretColor: '#939fff',
    },
    '.cm-cursor, .cm-dropCursor': {
      borderLeftColor: '#939fff',
    },
    '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
      backgroundColor: 'rgba(147, 159, 255, 0.22)',
    },
    '.cm-activeLine': {
      backgroundColor: 'rgba(147, 159, 255, 0.06)',
    },
    '.cm-activeLineGutter': {
      backgroundColor: 'rgba(147, 159, 255, 0.08)',
    },
    '.cm-gutters': {
      backgroundColor: '#0a0b10',
      color: '#5c5f6e',
      border: 'none',
      borderRight: '2px solid #3a3d4a',
    },
    '.cm-lineNumbers .cm-gutterElement': {
      padding: '0 8px 0 6px',
    },
    '.cm-panels': {
      backgroundColor: '#111218',
      color: '#eceef4',
    },
    '.cm-panels.cm-panels-top': {
      borderBottom: '2px solid #3a3d4a',
    },
    '.cm-panels.cm-panels-bottom': {
      borderTop: '2px solid #3a3d4a',
    },
    '.cm-searchMatch': {
      backgroundColor: 'rgba(232, 160, 58, 0.35)',
    },
    '.cm-searchMatch.cm-searchMatch-selected': {
      backgroundColor: 'rgba(232, 160, 58, 0.55)',
    },
    '.cm-selectionMatch': {
      backgroundColor: 'rgba(142, 245, 168, 0.15)',
    },
    '.cm-matchingBracket, .cm-nonmatchingBracket': {
      backgroundColor: 'rgba(147, 159, 255, 0.2)',
      outline: '1px solid #939fff',
    },
    '.cm-tooltip': {
      backgroundColor: '#171821',
      border: '2px solid #3a3d4a',
      color: '#eceef4',
    },
    '.cm-tooltip-autocomplete > ul > li[aria-selected]': {
      backgroundColor: 'rgba(147, 159, 255, 0.18)',
      color: '#939fff',
    },
  },
  { dark: true },
);

export const voidHighlightStyle = HighlightStyle.define([
  { tag: t.keyword, color: '#939fff' },
  { tag: t.operator, color: '#a7b4ff' },
  { tag: t.string, color: '#8ef5a8' },
  { tag: t.number, color: '#e8a03a' },
  { tag: t.bool, color: '#e8a03a' },
  { tag: t.null, color: '#e85d4c' },
  { tag: t.comment, color: '#5c5f6e', fontStyle: 'italic' },
  { tag: t.variableName, color: '#eceef4' },
  { tag: t.definition(t.variableName), color: '#939fff' },
  { tag: t.function(t.variableName), color: '#a7b4ff' },
  { tag: t.propertyName, color: '#8ec8d4' },
  { tag: t.typeName, color: '#939fff' },
  { tag: t.className, color: '#939fff' },
  { tag: t.meta, color: '#8b8e9c' },
  { tag: t.punctuation, color: '#8b8e9c' },
]);

export const voidEditorExtensions = [
  voidEditorTheme,
  syntaxHighlighting(voidHighlightStyle),
];
