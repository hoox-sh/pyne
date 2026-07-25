import { StreamLanguage, StreamParser } from '@codemirror/language';

const pineParser: StreamParser<{ inComment: boolean }> = {
  startState: () => ({ inComment: false }),
  token(stream, state) {
    if (stream.match('//@version=')) { stream.skipToEnd(); return 'meta'; }
    if (stream.match('//')) { stream.skipToEnd(); return 'comment'; }
    if (stream.match('/*')) { state.inComment = true; return 'comment'; }
    if (state.inComment) {
      if (stream.match('*/')) { state.inComment = false; return 'comment'; }
      stream.skipToEnd();
      return 'comment';
    }
    if (stream.match(/"[^"]*"/) || stream.match(/'[^']*'/)) return 'string';
    if (stream.match(/\b(indicator|strategy|plot|hline|fill|plotshape|plotchar|alertcondition)\b/)) return 'keyword';
    if (stream.match(/\b(input|int|float|bool|string|color|bar_index|close|open|high|low|volume|time|math|ta|array|matrix)\b/)) return 'variableName';
    if (stream.match(/\b(if|else|for|while|switch|true|false|na)\b/)) return 'controlKeyword';
    if (stream.match(/\b(var|varip|export|import|type|method|using)\b/)) return 'definitionKeyword';
    if (stream.match(/[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?/)) return 'number';
    if (stream.match(/[A-Z][A-Z0-9_]+/)) return 'constantName';
    if (stream.match(/[a-zA-Z_][a-zA-Z0-9_]*/)) return 'variableName';
    if (stream.match(/[+\-*/%=<>!&|^~?:]+/)) return 'operator';
    if (stream.match(/[{}()\[\],;.]/)) return 'punctuation';
    stream.next();
    return null;
  },
};

export const pineScript = StreamLanguage.define(pineParser);
