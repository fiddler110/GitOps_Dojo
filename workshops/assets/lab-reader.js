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

  function render(markdownSource, file) {
    var md = window.markdownit({ html: false, linkify: true, breaks: false });
    contentEl.innerHTML = md.render(markdownSource);
    rewriteLabLinks(contentEl);
    var heading = contentEl.querySelector('h1');
    document.title = (heading ? heading.textContent : file) + ' — Lab';
  }

  var file = labFileFromQuery();
  if (!file) {
    showError('No lab file specified. Open this page from the lab overview’s links.');
    return;
  }

  fetch('../lab/' + file, { credentials: 'same-origin' })
    .then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.text();
    })
    .then(function (text) { render(text, file); })
    .catch(function (err) {
      showError('Could not load ' + file + ' (' + err.message + ').');
    });
})();
