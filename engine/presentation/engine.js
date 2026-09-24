// Marp engine hook (`marp --engine`, see Dockerfile ENTRYPOINT): leaves the
// stock Marp renderer as-is and only teaches its highlight.js a few grammars:
//   - HCL, which highlight.js doesn't ship. Without it, ```terraform / ```hcl
//     fences in slides render as plain text.
//   - bash/sh with command names and flags coloured. Stock highlight.js
//     colours only strings, comments and $VARS, so `git checkout -b x`
//     rendered as one flat colour.
//   - gitignore and cron, which highlight.js doesn't ship either.
// The lab reader (workshops/assets/lab-reader.js) uses Prism for the same
// fences, which already colours commands; this keeps slides close to it.
//
// marp-core keeps a private highlight.js instance (marp.highlightjs, made
// with newInstance()), so the grammar is registered on that, not on the
// global highlight.js module.
'use strict';

function hcl(hljs) {
  const INTERPOLATION = {
    className: 'subst',
    begin: /[$%]\{/,
    end: /\}/,
    contains: [] // filled in below: expressions can nest strings
  };
  const STRING = {
    className: 'string',
    begin: /"/,
    end: /"/,
    contains: [hljs.BACKSLASH_ESCAPE, INTERPOLATION]
  };
  const HEREDOC = {
    className: 'string',
    begin: /<<-?\s*([A-Za-z_][\w]*)\s*$/,
    end: /^\s*[A-Za-z_][\w]*\s*$/,
    contains: [INTERPOLATION]
  };
  const NUMBER = { className: 'number', begin: /\b\d+(\.\d+)?([eE][+-]?\d+)?\b/, relevance: 0 };
  const FUNCTION_CALL = { className: 'built_in', begin: /\b[a-z_][\w]*(?=\()/, relevance: 0 };
  const LITERALS = { literal: ['true', 'false', 'null'] };
  INTERPOLATION.contains = [STRING, NUMBER, FUNCTION_CALL];
  INTERPOLATION.keywords = LITERALS;

  return {
    name: 'HCL',
    aliases: ['terraform', 'tf', 'tofu'],
    keywords: {
      keyword: ['for', 'in', 'if', 'else', 'endif', 'endfor'],
      literal: LITERALS.literal
    },
    contains: [
      hljs.HASH_COMMENT_MODE,
      hljs.C_LINE_COMMENT_MODE,
      hljs.C_BLOCK_COMMENT_MODE,
      // Block header: `resource "type" "name" {`, `lifecycle {`, ...
      {
        begin: [/^\s*/, /[A-Za-z_][\w-]*/, /(?=(\s+("[^"]*"|[A-Za-z_][\w-]*))*\s*\{)/],
        beginScope: { 2: 'keyword' }
      },
      // Attribute name: `key =` (not `==`)
      {
        begin: [/[A-Za-z_][\w-]*/, /\s*/, /=(?!=)/],
        beginScope: { 1: 'attr' },
        relevance: 0
      },
      HEREDOC,
      STRING,
      NUMBER,
      FUNCTION_CALL
    ]
  };
}

// Stock bash plus two modes tried first: the command word at the start of a
// line or after | ; & ( and $( (scoped like a function name), and -f /
// --flag options (scoped like an attribute). Output lines pasted into a
// ```sh block get their first word coloured too, as in the lab reader.
const stockBash = require('highlight.js/lib/languages/bash');

function shell(hljs) {
  const lang = stockBash(hljs);
  const COMMAND = {
    begin: [
      /(?:^|[|;&(]|\$\()[ \t]*/,
      /(?!(?:if|then|else|elif|fi|for|while|until|do|done|case|esac|in|function|select)(?![\w.+-]))(?:sudo[ \t]+)?[A-Za-z_][\w.+-]*(?=[ \t]|$)/
    ],
    beginScope: { 2: 'title.function' },
    relevance: 0
  };
  // An assignment (`FOO=bar`) is not a command.
  const ASSIGNMENT = { begin: /(?:^|[ \t])[A-Za-z_]\w*=/, relevance: 0 };
  const FLAG = { scope: 'attr', begin: /(?<=[ \t])--?[A-Za-z][\w-]*/, relevance: 0 };
  lang.contains = [ASSIGNMENT, COMMAND, FLAG, ...lang.contains];
  return lang;
}

function gitignore(hljs) {
  return {
    name: '.gitignore',
    contains: [
      hljs.HASH_COMMENT_MODE,
      { scope: 'keyword', begin: /^!/ },         // negation: re-include
      { scope: 'attr', begin: /\*\*|\*|\?/ },  // globs
      { scope: 'title.function', begin: /\/$/ } // trailing slash: folders only
    ]
  };
}

function cron(hljs) {
  return {
    name: 'crontab',
    contains: [
      hljs.HASH_COMMENT_MODE,
      // The five schedule fields, then the command.
      { scope: 'number', begin: /^(?:[\d*,\/-]+[ \t]+){5}/ },
      { scope: 'number', begin: /^@\w+/ }
    ]
  };
}

module.exports = ({ marp }) => {
  marp.highlightjs.registerLanguage('hcl', hcl);
  marp.highlightjs.registerLanguage('bash', shell);
  marp.highlightjs.registerLanguage('gitignore', gitignore);
  marp.highlightjs.registerLanguage('cron', cron);
  return marp;
};
