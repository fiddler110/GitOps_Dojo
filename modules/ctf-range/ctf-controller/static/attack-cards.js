// Per-target attack-range cards rendered inline on the student landing page
// (plan §4, CTF-D20). An attack pack adds this via extensions.json's
// `scripts` kind; the engine's /workspace/extra.js loader appends a <script>
// pointing here with data-surface=<page>. We act only on data-surface=portal
// (the landing page); on every other surface this file is a no-op.
//
// Why cards and not an iframe widget: the user asked for native landing-page
// cards with Start/Stop/Reset inline, rather than opening a separate page to
// click a button. The same /attack/status, /attack/start, /attack/stop and
// /attack/reset endpoints the static /ctf-attack/ page uses are driven from
// here, so one source of truth stays in the controller.
//
// CSP: the landing page is served under the allocator's strict CSP
// (default-src 'self', script-src 'self', style-src 'self' + two hashes),
// so the stylesheet is loaded as an external same-origin <link> and every
// string shown comes from textContent only (no innerHTML, no inline style).
(function () {
  "use strict";

  var me = document.currentScript;
  var surface = me && me.getAttribute("data-surface");
  if (surface !== "portal") return;

  var STATUS_URL = "/ctf-attack/attack/status";
  var POLL_MS = 3000;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function stylesheet() {
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/ctf-attack/attack-cards.css";
    document.head.appendChild(link);
  }

  function api(path, opts) {
    return fetch(path, opts).then(function (r) { return r.json(); });
  }

  function post(path, body) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  function section(cards) {
    // Our own grid under the engine's .cards grid. One row per target on
    // desktop, stacked on mobile -- same breakpoint as the engine's cards.
    var wrap = el("div", "attack-range");
    var head = el("div", "attack-range-head");
    head.appendChild(el("span", "attack-range-title", "Attack range"));
    head.appendChild(el("span", "attack-range-hint",
      "One target runs at a time. Starting a new target stops the current one."));
    // The scan-target line is filled in by setScan() once /attack/status
    // comes back with the pinned ctf_net subnet + ctf-host address.
    var scan = el("div", "attack-range-scan");
    scan.id = "attack-range-scan";
    head.appendChild(scan);
    wrap.appendChild(head);
    var grid = el("div", "attack-range-grid");
    wrap.appendChild(grid);
    cards.appendChild(wrap);
    return grid;
  }

  // The latest net doc from /attack/status (host / subnet / addr). Kept so
  // the scan-header render can lean on it after target IPs land in doc.targets.
  var currentNet = null;
  var scanShown = false;
  function setScan(targets) {
    if (scanShown) return;
    var scan = document.getElementById("attack-range-scan");
    if (!scan) return;
    while (scan.firstChild) scan.removeChild(scan.firstChild);
    // Prefer the student's own target IPs if we have them. Each target has
    // its own IP within the student's reserved block (HackTheBox-style,
    // 2026-10-07); nmap any of them to find the one you Started.
    var ips = (targets || []).map(function (t) { return t.addr; }).filter(Boolean);
    scan.appendChild(el("span", "attack-range-scan-label", "Your boxes: "));
    if (ips.length) {
      ips.forEach(function (ip, i) {
        if (i) scan.appendChild(el("span", "attack-sep", ", "));
        scan.appendChild(el("code", "attack-addr", ip));
      });
      scan.appendChild(el("span", "attack-range-scan-hint",
        " -- one IP per attack box, scan with nmap. Only the one you Start answers; the firewall drops everything else."));
    } else {
      // Fallback: no per-target IPs (older stack or disabled subnet).
      var host = currentNet && currentNet.host ? currentNet.host : "ctf-host";
      scan.appendChild(el("code", "attack-addr", host));
      if (currentNet && currentNet.addr) {
        scan.appendChild(el("span", "attack-sep", " "));
        scan.appendChild(el("code", "attack-addr", currentNet.addr));
      }
      if (currentNet && currentNet.subnet) {
        scan.appendChild(el("span", "attack-sep", " in "));
        scan.appendChild(el("code", "attack-addr", currentNet.subnet));
      }
      scan.appendChild(el("span", "attack-range-scan-hint",
        " -- the firewall drops everything else, so nmap only finds your own target's ports."));
    }
    scanShown = true;
  }

  function stateLabel(slot) {
    if (slot.state === "queued" && slot.queue_position) {
      return "queued, position " + slot.queue_position;
    }
    return slot.state;
  }

  function iconRocket() {
    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    var paths = [
      "M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z",
      "M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z",
      "M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0",
      "M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5",
    ];
    paths.forEach(function (d) {
      var p = document.createElementNS(ns, "path");
      p.setAttribute("d", d);
      svg.appendChild(p);
    });
    return svg;
  }

  var busy = false;

  function render(grid, doc) {
    while (grid.firstChild) grid.removeChild(grid.firstChild);
    if (doc.facilitator) {
      grid.appendChild(el("p", "attack-range-note",
        "Facilitator account: no attack slot of your own. Use the admin Attack Range tab."));
      return;
    }
    var targets = doc.targets || [];
    if (!targets.length) {
      grid.appendChild(el("p", "attack-range-note",
        "No targets wired into this range yet."));
      return;
    }
    var slot = doc.slot || { target: null, state: "stopped", error: "" };
    targets.forEach(function (t) {
      var here = slot.target === t.id;
      var state = here ? slot.state : "stopped";
      var pending = state === "queued" || state === "starting";
      var card = el("div",
        "card attack-card" +
        (state === "live" ? " live" : "") +
        (pending ? " pending" : "") +
        (state === "error" ? " error" : ""));

      var icon = el("span", "card-icon");
      icon.appendChild(iconRocket());
      card.appendChild(icon);

      var textWrap = el("span", "card-text");
      // Title line: target id + its own reserved IP (2026-10-07, HTB-style).
      // t.addr is the per-(student,target) IP from /attack/status; the IP
      // only responds when this specific target is Started (CTF-D20: one
      // live per student at a time). Every student uid can nmap all K of
      // their reserved IPs; only the live one answers.
      var title = el("span", "card-title");
      title.appendChild(document.createTextNode(t.id));
      if (t.addr) {
        title.appendChild(el("span", "attack-sep", " "));
        title.appendChild(el("code", "attack-addr", t.addr));
      }
      textWrap.appendChild(title);
      var meta = el("span", "card-desc attack-meta");
      meta.appendChild(el("span", "attack-state", stateLabel({ state: state, queue_position: slot.queue_position })));
      textWrap.appendChild(meta);
      if (here && state === "error" && slot.error) {
        textWrap.appendChild(el("span", "attack-err", slot.error));
      }
      card.appendChild(textWrap);

      var actions = el("div", "attack-actions");
      actions.appendChild(button("Start", !here || state === "stopped" || state === "error",
        function () { return post("/ctf-attack/attack/start", { target: t.id }); }));
      actions.appendChild(button("Stop", here && state !== "stopped",
        function () { return post("/ctf-attack/attack/stop", {}); }));
      actions.appendChild(button("Reset", here && state === "live",
        function () { return post("/ctf-attack/attack/reset", {}); }));
      if (here && state === "live") {
        var open = el("a", "attack-btn", "Open");
        open.href = "/ctf-view/" + t.id + "/";
        open.target = "_blank";
        open.rel = "noopener";
        actions.appendChild(open);
      }
      card.appendChild(actions);

      grid.appendChild(card);
    });
  }

  function button(label, enabled, onClick) {
    var b = el("button", "attack-btn", label);
    b.type = "button";
    b.disabled = !enabled || busy;
    b.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      if (busy) return;
      busy = true;
      onClick().catch(function () {}).then(function () { poll(); });
    });
    return b;
  }

  var grid = null;

  function poll() {
    return api(STATUS_URL).then(function (doc) {
      if (!grid) return;
      if (doc && doc.net) currentNet = doc.net;
      if (doc && doc.targets) setScan(doc.targets);
      render(grid, doc);
    }).catch(function () {
      if (!grid) return;
      while (grid.firstChild) grid.removeChild(grid.firstChild);
      grid.appendChild(el("p", "attack-range-note",
        "Could not reach the attack range controller."));
    }).then(function () { busy = false; });
  }

  function start() {
    var cards = document.querySelector(".cards");
    if (!cards) return;
    stylesheet();
    grid = section(cards);
    grid.appendChild(el("p", "attack-range-note", "Loading attack targets..."));
    poll();
    setInterval(function () { if (!busy) poll(); }, POLL_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
