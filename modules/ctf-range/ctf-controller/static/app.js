// Attack Range card (plan §4 "Student-controlled targets, one live per
// slot", decision CTF-D20). Polls GET attack/status and drives
// POST attack/start|stop|reset. Every string on the page is set with
// textContent only (CLAUDE.md "student-controlled strings"), and the strict
// CSP this page serves under forbids inline script, so everything lives here.
(function () {
  "use strict";

  var POLL_MS = 3000;
  var noteEl = document.getElementById("note");
  var targetsEl = document.getElementById("targets");
  var busy = false; // one in-flight mutating call at a time, matches "one request per student"

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

  function button(label, enabled, onClick) {
    var b = document.createElement("button");
    b.textContent = label;
    b.disabled = !enabled || busy;
    b.addEventListener("click", function () {
      busy = true;
      onClick().catch(function () {}).then(poll);
    });
    return b;
  }

  function clear(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  function render(doc) {
    clear(targetsEl);
    if (doc.facilitator) {
      noteEl.textContent = "Facilitator account: this page has no attack slot of " +
        "its own. A per-student roster view is tracked separately (plan §5).";
      return;
    }
    noteEl.textContent = "At most one target runs at a time; starting a different " +
      "one stops the current target. Reachable at ctf-host on your terminal's " +
      "ctf_net — find your port with nmap.";
    if (!doc.targets || !doc.targets.length) {
      var p = document.createElement("p");
      p.textContent = "No targets are wired into this range yet.";
      targetsEl.appendChild(p);
      return;
    }
    var slot = doc.slot || { target: null, state: "stopped", error: "" };
    doc.targets.forEach(function (t) {
      var here = slot.target === t.id;
      var state = here ? slot.state : "stopped";
      var card = document.createElement("div");
      card.className = "card" + (state === "live" ? " live" : "") + (state === "error" ? " error" : "");

      var idEl = document.createElement("div");
      idEl.className = "id";
      idEl.textContent = t.id;
      card.appendChild(idEl);

      var stateEl = document.createElement("div");
      stateEl.className = "state";
      stateEl.textContent = (state === "queued" && slot.queue_position)
        ? "queued, position " + slot.queue_position
        : state;
      card.appendChild(stateEl);

      if (here && state === "error" && slot.error) {
        var errEl = document.createElement("div");
        errEl.className = "err";
        errEl.textContent = slot.error;
        card.appendChild(errEl);
      }

      var idle = !here || state === "stopped" || state === "error";
      card.appendChild(button("Start", idle, function () { return post("attack/start", { target: t.id }); }));
      card.appendChild(button("Stop", here && state !== "stopped", function () { return post("attack/stop", {}); }));
      card.appendChild(button("Reset", here && state === "live", function () { return post("attack/reset", {}); }));
      targetsEl.appendChild(card);
    });
  }

  function poll() {
    return api("attack/status").then(render).catch(function () {
      noteEl.textContent = "Could not reach the attack range controller.";
    }).then(function () { busy = false; });
  }

  poll();
  setInterval(function () { if (!busy) poll(); }, POLL_MS);
})();
