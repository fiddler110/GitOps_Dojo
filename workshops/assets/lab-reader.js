// Renders one lab's plain-Markdown instructions as a normal scrolling
// document, for the "read it in the browser" path linked from each
// workshop's labs.md. Marp itself can't do this: its server (engine/
// presentation) treats every .md path as a slide deck and clips long-form
// text into fixed-size slide boxes -- see engine/run.sh's sync_lab_docs,
// which mirrors content/lab/*.md into content/slides/lab/*.md.txt (a
// non-.md extension so Marp's router passes it through unrendered) on every
// `./run.sh <workshop>`. content/lab/*.md stays the single source of
// truth; never hand-edit the generated *.md.txt copies.
(function () {
  'use strict';

  var contentEl = document.getElementById('lab-content');

  function showError(message) {
    contentEl.textContent = message;
  }

  function labFileFromQuery() {
    var params = new URLSearchParams(window.location.search);
    var file = params.get('file');
    // Same-directory generated file names only (labN.md.txt, README.md.txt,
    // cheat-sheet.md.txt, ...) -- never an absolute or parent-relative path.
    if (!file || !/^[A-Za-z0-9_-]+\.md\.txt$/.test(file)) {
      return null;
    }
    return file;
  }

  // Rewrite links between lab docs (e.g. "lab2.md", written for a reader
  // opening these files in an editor) to stay inside this viewer instead of
  // requesting the real .md path, which Marp would render as a slide deck.
  // Leaves external URLs, in-page anchors, and mailto: links untouched.
  function rewriteLabLinks(container) {
    var links = container.querySelectorAll('a[href]');
    for (var i = 0; i < links.length; i++) {
      var href = links[i].getAttribute('href');
      if (/^[A-Za-z0-9_-]+\.md$/.test(href)) {
        links[i].setAttribute('href', 'lab-reader.html?file=' + encodeURIComponent(href) + '.txt');
      }
    }
  }

  // Syntax highlighting for fenced code blocks (```terraform, ```sh, ...),
  // via the vendored Prism build (hcl, bash, javascript, json, yaml,
  // diff, gitignore, dockerfile, python). Prism
  // escapes the source itself, so the returned HTML is safe to insert.
  // Unknown or ```text fences return '' and markdown-it escapes them as
  // plain text.
  var prism = window.Prism;
  if (prism) {
    prism.languages.terraform = prism.languages.tf = prism.languages.hcl;
    // Prism's bash grammar only knows common Unix commands; colour the
    // workshop CLIs the same way so one-line steps aren't left plain.
    prism.languages.insertBefore('bash', 'function', {
      'lab-command': {
        pattern: /(^|[\s;|&]|[<>]\()(?:terraform|tofu|dnscontrol|batcat|step|python3|az)(?=$|[)\s;|&])/,
        lookbehind: true,
        alias: 'function'
      }
    });
  }

  function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function highlight(code, lang) {
    // ```mermaid fences become diagrams in drawMermaid(); until then (or if
    // Mermaid can't load) the escaped source shows as a plain code block.
    if (lang && lang.toLowerCase() === 'mermaid') {
      return '<pre class="mermaid">' + escapeHtml(code) + '</pre>';
    }
    var grammar = prism && lang && prism.languages[lang.toLowerCase()];
    return grammar ? prism.highlight(code, grammar, lang) : '';
  }

  // Same Mermaid build and colours as the slide decks. Loaded only when a
  // lab has a diagram.
  function drawMermaid(container) {
    var blocks = container.querySelectorAll('pre.mermaid');
    if (!blocks.length) return;
    import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs')
      .then(function (mod) {
        var mermaid = mod.default;
        mermaid.initialize({
          startOnLoad: false,
          theme: 'dark',
          fontFamily: 'Manrope, sans-serif',
          sequence: { mirrorActors: false, boxMargin: 8 },
          themeVariables: {
            fontSize: '16px',
            background: '#17171a',
            primaryColor: '#21313c',
            primaryTextColor: '#e8f0f2',
            primaryBorderColor: '#3dd6c3',
            lineColor: '#a9bac2',
            actorBkg: '#21313c',
            actorBorder: '#3dd6c3',
            actorTextColor: '#e8f0f2',
            signalColor: '#a9bac2',
            signalTextColor: '#e8f0f2',
            noteBkgColor: '#137f7a',
            noteTextColor: '#e8f0f2',
            noteBorderColor: '#3dd6c3'
          }
        });
        // Boxes are sized from measured text: measure in the real font.
        return document.fonts.ready.then(function () {
          return mermaid.run({ nodes: blocks });
        });
      })
      .catch(function () {});
  }

  function render(markdownSource, file) {
    var md = window.markdownit({ html: false, linkify: true, breaks: false, highlight: highlight });
    contentEl.innerHTML = md.render(markdownSource);
    rewriteLabLinks(contentEl);
    drawMermaid(contentEl);
    var heading = contentEl.querySelector('h1');
    document.title = (heading ? heading.textContent : file) + ' — Lab';
  }

  // Header links to the neighbouring labs (labN-1 / labN+1). Numbering
  // differs per workshop (tofu-basics starts at lab0, others at lab1), so
  // each neighbour is shown only if its generated file actually exists.
  // README and cheat-sheet get no pager.
  function renderPager(file) {
    var match = /^lab(\d+)\.md\.txt$/.exec(file);
    if (!match) return;
    var pager = document.getElementById('lab-pager');
    var n = parseInt(match[1], 10);
    var neighbours = [
      { n: n - 1, text: '\u2190 Lab ' + (n - 1) },
      { n: n + 1, text: 'Lab ' + (n + 1) + ' \u2192' }
    ];
    neighbours.forEach(function (item) {
      if (item.n < 0) return;
      var link = document.createElement('a');
      link.href = 'lab-reader.html?file=lab' + item.n + '.md.txt';
      link.textContent = item.text;
      link.hidden = true;
      pager.appendChild(link);
      fetch('../lab/lab' + item.n + '.md.txt', { method: 'HEAD', credentials: 'same-origin' })
        .then(function (res) { if (res.ok) link.hidden = false; })
        .catch(function () {});
    });
  }

  var file = labFileFromQuery();
  if (!file) {
    showError('No lab file specified. Open this page from the lab overview’s links.');
    return;
  }

  // Labs write "studentXX" wherever the reader's own username belongs, so
  // they still read correctly in an editor. Here it becomes the real name,
  // from the allocator's /whoami (null for the facilitator, or on any error,
  // which leaves the placeholder as it is).
  var whoami = fetch('/whoami', { credentials: 'same-origin', cache: 'no-store' })
    .then(function (res) { return res.ok ? res.json() : {}; })
    .then(function (data) {
      var user = data && data.user;
      return typeof user === 'string' && /^[a-z][a-z0-9]{0,30}$/.test(user) ? user : null;
    })
    .catch(function () { return null; });

  var lab = fetch('../lab/' + file, { credentials: 'same-origin' })
    .then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.text();
    });

  Promise.all([lab, whoami])
    .then(function (results) {
      var text = results[1] ? results[0].replace(/studentXX/g, results[1]) : results[0];
      render(text, file);
      renderPager(file);
    })
    .catch(function (err) {
      showError('Could not load ' + file + ' (' + err.message + ').');
    });
})();
