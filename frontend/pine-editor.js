// CodeMirror 6 Pine Script editor for SuperChart Lite.
// Bare imports resolve via importmap in index.html so @lezer/highlight is a
// single instance (required for tag-based syntax colors to work).

import {
    EditorView,
    keymap,
    lineNumbers,
    highlightActiveLine,
    highlightActiveLineGutter,
    drawSelection,
    rectangularSelection,
} from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands';
import {
    StreamLanguage,
    syntaxHighlighting,
    HighlightStyle,
    bracketMatching,
    foldGutter,
    foldKeymap,
    indentOnInput,
    defaultHighlightStyle,
} from '@codemirror/language';
import { tags } from '@lezer/highlight';
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search';
import { closeBrackets, closeBracketsKeymap, autocompletion, completionKeymap } from '@codemirror/autocomplete';

/** @type {EditorView | null} */
let editorView = null;
/** @type {HTMLTextAreaElement | null} */
let fallbackTextarea = null;
/** @type {((script: string) => void) | null} */
let onRun = null;
/** @type {((script: string) => void) | null} */
let onDocChange = null;

// --- Pine stream language (aligned with vscode-extension tmLanguage) ---
// Token *names* must match tokenTable keys (or CM default token table).

const KEYWORDS = new Set([
    'if', 'else', 'for', 'while', 'switch', 'case', 'default', 'break', 'continue', 'return',
    'import', 'export', 'from', 'as', 'type', 'method', 'enum', 'var', 'varip', 'const',
    'strategy', 'indicator', 'library',
    'and', 'or', 'not', 'in', 'to', 'by',
]);

const ATOMS = new Set(['true', 'false', 'na', 'void']);

const TYPES = new Set([
    'color', 'series', 'input', 'simple', 'bool', 'int', 'float', 'string',
    'array', 'matrix', 'map', 'line', 'label', 'box', 'table', 'polyline', 'chart',
]);

const BUILTIN_NS = new Set([
    'ta', 'math', 'str', 'array', 'map', 'matrix', 'strategy', 'input', 'plot',
    'request', 'ticker', 'timeframe', 'session', 'syminfo', 'barstate',
    'color', 'line', 'label', 'box', 'table', 'polyline', 'chart', 'runtime',
    'log', 'alert',
]);

const BUILTIN_FUNCS = new Set([
    'plot', 'plotshape', 'plotchar', 'plotarrow', 'plotbar', 'plotcandle',
    'hline', 'fill', 'bgcolor', 'barcolor', 'alert', 'alertcondition',
    'max_bars_back', 'timestamp', 'time', 'time_close', 'year', 'month', 'dayofmonth',
    'dayofweek', 'hour', 'minute', 'second', 'open', 'high', 'low', 'close', 'volume',
    'hl2', 'hlc3', 'ohlc4', 'bar_index', 'nz', 'na',
]);

const pineLanguage = StreamLanguage.define({
    name: 'pine',
    startState() {
        return { inBlockComment: false };
    },
    token(stream, state) {
        if (stream.eatSpace()) return null;

        if (state.inBlockComment) {
            if (stream.match(/.*?\*\//)) state.inBlockComment = false;
            else stream.skipToEnd();
            return 'comment';
        }

        // //@version / //@description before plain //
        if (stream.match(/\/\/@.*/)) return 'meta';
        if (stream.match('//')) {
            stream.skipToEnd();
            return 'comment';
        }
        if (stream.match('/*')) {
            state.inBlockComment = true;
            return 'comment';
        }

        // Triple-quoted strings (v6)
        if (stream.match('"""') || stream.match("'''")) {
            const q = stream.current();
            while (!stream.eol()) {
                if (stream.match(q)) break;
                stream.next();
            }
            return 'string';
        }

        if (stream.match('"') || stream.match("'")) {
            const q = stream.current();
            let escaped = false;
            while (!stream.eol()) {
                const ch = stream.next();
                if (!escaped && ch === q) break;
                escaped = !escaped && ch === '\\';
            }
            return 'string';
        }

        if (stream.match(/0[xX][0-9a-fA-F]+/) || stream.match(/\d+\.\d+([eE][+-]?\d+)?/) || stream.match(/\d+/)) {
            return 'number';
        }

        // color literals
        if (stream.match(/#[0-9a-fA-F]{3,8}\b/)) return 'atom';

        if (stream.match(/[=!<>]=|=>|\?\?|[+\-*/%]=?|[=<>!&|?:]/)) return 'operator';
        if (stream.match(/[{}[\](),.;]/)) return 'bracket';

        // .member
        if (stream.match(/\.[A-Za-z_][\w]*/)) return 'property';

        if (stream.match(/[A-Za-z_][\w]*/)) {
            const word = stream.current();
            if (ATOMS.has(word)) return 'atom';
            if (KEYWORDS.has(word)) return 'keyword';
            if (TYPES.has(word)) return 'type';
            if (BUILTIN_FUNCS.has(word)) return 'builtin';
            if (stream.peek() === '.' && BUILTIN_NS.has(word)) return 'builtin';
            return 'variable';
        }

        stream.next();
        return null;
    },
    languageData: {
        commentTokens: { line: '//', block: { open: '/*', close: '*/' } },
        closeBrackets: { brackets: ['(', '[', '{', "'", '"'] },
    },
    // Explicit token → Tag map (same @lezer/highlight instance via importmap)
    tokenTable: {
        keyword: tags.keyword,
        atom: tags.atom,
        number: tags.number,
        string: tags.string,
        comment: tags.comment,
        operator: tags.operator,
        bracket: tags.bracket,
        type: tags.typeName,
        builtin: tags.function(tags.variableName),
        variable: tags.variableName,
        property: tags.propertyName,
        meta: tags.meta,
    },
});

// High-contrast One-Dark-ish palette (TV dark bg)
const pineHighlight = HighlightStyle.define([
    { tag: tags.keyword, color: '#c678dd', fontWeight: '600' },
    { tag: tags.atom, color: '#d19a66' },
    { tag: tags.number, color: '#d19a66' },
    { tag: tags.string, color: '#98c379' },
    { tag: tags.comment, color: '#7f848e', fontStyle: 'italic' },
    { tag: tags.operator, color: '#56b6c2' },
    { tag: tags.bracket, color: '#abb2bf' },
    { tag: tags.typeName, color: '#e5c07b' },
    { tag: tags.function(tags.variableName), color: '#61afef' },
    { tag: tags.variableName, color: '#e06c75' },
    { tag: tags.propertyName, color: '#61afef' },
    { tag: tags.meta, color: '#7f848e' },
]);

const pineTheme = EditorView.theme(
    {
        '&': {
            backgroundColor: '#161a26',
            color: '#d1d4dc',
            height: '100%',
            fontSize: '13px',
        },
        '.cm-scroller': {
            overflow: 'auto',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            lineHeight: '1.45',
        },
        '.cm-content': {
            caretColor: '#d1d4dc',
            padding: '8px 0',
            minHeight: '100%',
        },
        '.cm-cursor, .cm-dropCursor': { borderLeftColor: '#d1d4dc' },
        '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
            backgroundColor: 'rgba(41, 98, 255, 0.35)',
        },
        '.cm-activeLine': { backgroundColor: 'rgba(41, 98, 255, 0.08)' },
        '.cm-gutters': {
            backgroundColor: '#1a1f2e',
            color: '#787b86',
            border: 'none',
            borderRight: '1px solid #363c4e',
            minWidth: '2.5em',
        },
        '.cm-lineNumbers .cm-gutterElement': {
            padding: '0 8px 0 6px',
        },
        '.cm-activeLineGutter': { backgroundColor: '#1e222d', color: '#d1d4dc' },
        '.cm-foldPlaceholder': {
            backgroundColor: '#2a3042',
            border: 'none',
            color: '#787b86',
        },
        '.cm-tooltip': {
            backgroundColor: '#1e222d',
            border: '1px solid #363c4e',
            color: '#d1d4dc',
        },
    },
    { dark: true },
);

export function getScript() {
    if (editorView) return editorView.state.doc.toString();
    if (fallbackTextarea) return fallbackTextarea.value;
    return '';
}

export function setScript(text) {
    const value = text ?? '';
    if (editorView) {
        editorView.dispatch({
            changes: { from: 0, to: editorView.state.doc.length, insert: value },
        });
        return;
    }
    if (fallbackTextarea) fallbackTextarea.value = value;
}

export function focusEditor() {
    if (editorView) editorView.focus();
    else if (fallbackTextarea) fallbackTextarea.focus();
}

/** @returns {boolean} */
export function isCodeMirrorActive() {
    return !!editorView;
}

/**
 * @param {{
 *   parent: HTMLElement,
 *   initialDoc?: string,
 *   onRun?: (script: string) => void,
 *   onDocChange?: (script: string) => void,
 * }} opts
 * @returns {Promise<'codemirror' | 'textarea'>}
 */
export async function initPineEditor(opts) {
    const { parent, initialDoc = '', onRun: runCb, onDocChange: changeCb } = opts;
    onRun = runCb || null;
    onDocChange = changeCb || null;

    if (!parent) throw new Error('initPineEditor: parent required');
    parent.innerHTML = '';

    try {
        const runKeymap = keymap.of([
            {
                key: 'Mod-Enter',
                run: () => {
                    if (onRun) onRun(getScript());
                    return true;
                },
            },
        ]);

        const state = EditorState.create({
            doc: initialDoc,
            extensions: [
                lineNumbers(),
                highlightActiveLine(),
                highlightActiveLineGutter(),
                drawSelection(),
                rectangularSelection(),
                history(),
                foldGutter(),
                indentOnInput(),
                bracketMatching(),
                closeBrackets(),
                autocompletion(),
                highlightSelectionMatches(),
                pineLanguage,
                // Pine colors first; default as fallback for unmatched tags
                syntaxHighlighting(pineHighlight, { fallback: false }),
                syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
                pineTheme,
                EditorView.lineWrapping,
                keymap.of([
                    ...closeBracketsKeymap,
                    ...defaultKeymap,
                    ...searchKeymap,
                    ...historyKeymap,
                    ...foldKeymap,
                    ...completionKeymap,
                    indentWithTab,
                ]),
                runKeymap,
                EditorView.updateListener.of((update) => {
                    if (update.docChanged && onDocChange) {
                        onDocChange(update.state.doc.toString());
                    }
                }),
            ],
        });

        editorView = new EditorView({
            state,
            parent,
        });

        requestAnimationFrame(() => {
            try {
                editorView?.requestMeasure();
            } catch (_) { /* ignore */ }
        });

        // Dev aid: confirm highlighting produced mark spans
        try {
            const marks = parent.querySelectorAll('.cm-line span');
            if (!marks.length) {
                console.warn(
                    '[pine-editor] CodeMirror mounted but no highlight spans yet. ' +
                    'If this persists, @lezer/highlight may be duplicated (check importmap).',
                );
            } else {
                console.info('[pine-editor] highlight spans:', marks.length);
            }
        } catch (_) { /* ignore */ }

        return 'codemirror';
    } catch (err) {
        console.warn('CodeMirror init failed, falling back to textarea', err);
        const ta = document.createElement('textarea');
        ta.id = 'pine-script-input';
        ta.spellcheck = false;
        ta.placeholder = "//@version=5\nstrategy('My Strategy', overlay=true)\n...";
        ta.value = initialDoc;
        ta.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                if (onRun) onRun(ta.value);
            }
        });
        ta.addEventListener('input', () => {
            if (onDocChange) onDocChange(ta.value);
        });
        parent.appendChild(ta);
        fallbackTextarea = ta;
        editorView = null;
        return 'textarea';
    }
}
