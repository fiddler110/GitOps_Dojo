// Marp engine hook (`marp --engine`, see Dockerfile ENTRYPOINT): leaves the
// stock Marp renderer as-is and only teaches its highlight.js an HCL grammar,
// which highlight.js doesn't ship. Without it, ```terraform / ```hcl fences
// in slides render as plain text while every other language is coloured.
// The lab reader (workshops/assets/lab-reader.js) uses Prism's HCL grammar
// for the same fences.
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

module.exports = ({ marp }) => {
  marp.highlightjs.registerLanguage('hcl', hcl);
  return marp;
};
