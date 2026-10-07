// Lab Info reader. Renders a .md file from /docs/<file> as scrolling long-form
// HTML with markdown-it, highlights fenced code blocks with Prism, and
// rewrites same-directory .md links so they stay inside this viewer.
//
// Query string: ?file=<name>.md (safe characters only -- rejected if the
// pattern does not match). Default when nothing is given: README.md.
//
// The lab-info Caddy serves this reader at /, the vendored libraries at
// /vendor/, and the markdown source at /docs/. No external CDNs; nothing
// here reads cookies, local storage or anything beyond the fetched doc.
(function () {
  "use strict";

  var DEFAULT_FILE = "README.md";
  var FILE_RE = /^[A-Za-z0-9][A-Za-z0-9_.-]*\.md$/;

  var contentEl = document.getElementById("content");
  var pagerEl = document.getElementById("pager");

  function fileFromQuery() {
    var p = new URLSearchParams(window.location.search);
    var f = p.get("file");
    if (!f) return DEFAULT_FILE;
    if (!FILE_RE.test(f)) return null;
    return f;
  }

  function setPagerHere(name) {
    while (pagerEl.firstChild) pagerEl.removeChild(pagerEl.firstChild);
    var span = document.createElement("span");
    span.className = "here";
    span.textContent = name;
    pagerEl.appendChild(span);
  }

  function showError(msg) {
    while (contentEl.firstChild) contentEl.removeChild(contentEl.firstChild);
    var box = document.createElement("div");
    box.className = "reader-error";
    box.textContent = msg;
    contentEl.appendChild(box);
  }

  // Prism aliases + extra grammars. Same shape as workshops/assets/lab-reader.js
  // so a student bouncing between the lab reader and here sees the same colours.
  var prism = window.Prism;
  if (prism) {
    prism.languages.terraform = prism.languages.tf = prism.languages.hcl;
    prism.languages.insertBefore("bash", "function", {
      "lab-command": {
        pattern: /(^|[\s;|&]|[<>]\()(?:nmap|sqlmap|ffuf|john|ncat|nc|dig|dnsrecon|tcpdump|tshark|whois|jq|opa|httpie|http|https|rego|batcat)(?=$|[)\s;|&])/,
        lookbehind: true,
        alias: "function",
      },
    });
    prism.languages.rego = {
      comment: /#.*/,
      string: { pattern: /"(?:\\.|[^"\\\n])*"|`[^`]*`/, greedy: true },
      keyword: /\b(?:package|import|default|not|with|as|some|every|in|if|contains|else)\b/,
      builtin: /\b(?:input|data)\b/,
      boolean: /\b(?:true|false|null)\b/,
      function: /\b[a-z_][\w.]*(?=\()/i,
      number: /\b\d+(?:\.\d+)?\b/,
      operator: /:=|==|!=|<=|>=|[<>|&=+\-*\/%]/,
      punctuation: /[{}[\](),.;:]/,
    };
  }

  function escapeHtml(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function highlight(code, lang) {
    var grammar = prism && lang && prism.languages[lang.toLowerCase()];
    return grammar ? prism.highlight(code, grammar, lang) : "";
  }

  var md = window.markdownit({ html: false, linkify: true, typographer: false, highlight: highlight });

  // Rewrite in-page .md links (e.g. "nmap.md") so they open in this viewer
  // instead of fetching the raw .md file from Caddy.
  function rewriteLabLinks(container) {
    var links = container.querySelectorAll("a[href]");
    for (var i = 0; i < links.length; i++) {
      var href = links[i].getAttribute("href");
      if (FILE_RE.test(href)) {
        links[i].setAttribute("href", "?file=" + encodeURIComponent(href));
      }
    }
  }

  function load(file) {
    setPagerHere(file);
    fetch("docs/" + file, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.text();
    }).then(function (text) {
      var html = md.render(text);
      while (contentEl.firstChild) contentEl.removeChild(contentEl.firstChild);
      // markdown-it output is sanitized (html: false); Prism output in the
      // code blocks is already escaped by Prism itself.
      var holder = document.createElement("div");
      holder.innerHTML = html;
      while (holder.firstChild) contentEl.appendChild(holder.firstChild);
      rewriteLabLinks(contentEl);
      document.title = "Lab Info — " + file.replace(/\.md$/, "");
      window.scrollTo(0, 0);
    }).catch(function (err) {
      showError("Could not load " + file + ": " + (err && err.message ? err.message : "error"));
    });
  }

  var file = fileFromQuery();
  if (!file) {
    showError("Invalid file name. Return to the index.");
    return;
  }
  load(file);

  window.addEventListener("popstate", function () {
    var f = fileFromQuery();
    if (f) load(f);
  });

  // Intercept clicks on same-page ?file= links so navigation stays SPA-like.
  document.addEventListener("click", function (ev) {
    var a = ev.target && ev.target.closest ? ev.target.closest("a[href^='?file=']") : null;
    if (!a) return;
    var href = a.getAttribute("href");
    ev.preventDefault();
    history.pushState({}, "", href);
    var f = fileFromQuery();
    if (f) load(f);
  });
})();
