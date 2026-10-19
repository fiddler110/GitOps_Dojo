// Notes page: loads ~/lab/notes.md, saves as you type, and notices when the terminal changed the file.
(function () {
  "use strict";
  var API = "api/notes";
  var text = document.getElementById("text");
  var status = document.getElementById("status");
  var save = document.getElementById("save");
  var banner = document.getElementById("banner");
  var bannerText = document.getElementById("banner-text");
  var base = null;       // mtime of the version this editor last saw
  var dirty = false;
  var saving = false;
  var timer = null;
  var conflict = false;
  var who = document.getElementById("who");   // the facilitator's picker; "" = their own notes
  var viewing = "";

  function api() { return viewing ? API + "?user=" + encodeURIComponent(viewing) : API; }

  function say(msg) { status.textContent = msg; }
  function hideBanner() { banner.hidden = true; conflict = false; }
  function showBanner(msg) { bannerText.textContent = msg; banner.hidden = false; conflict = true; }

  function call(method, body) {
    var opts = { method: method, headers: { "Content-Type": "application/json" } };
    if (body) opts.body = JSON.stringify(body);
    return fetch(method === "GET" ? api() : API, opts).then(function (r) {
      return r.json().then(function (doc) { return { status: r.status, doc: doc }; });
    });
  }

  function load() {
    return call("GET").then(function (r) {
      if (r.status !== 200) { say(r.doc.error || "could not load"); return; }
      text.value = r.doc.text;
      base = r.doc.mtime;
      dirty = false;
      hideBanner();
      say(viewing ? "read-only" : "loaded");
    }).catch(function () { say("could not reach the notes service"); });
  }

  function persist(force) {
    if (viewing || saving || (conflict && !force)) return;
    saving = true;
    clearTimeout(timer);
    say("saving...");
    call("PUT", { text: text.value, base: force ? null : base }).then(function (r) {
      if (r.status === 200) {
        base = r.doc.mtime;
        dirty = false;
        hideBanner();
        say("saved");
      } else if (r.status === 409 && r.doc.conflict) {
        showBanner("The file changed in your terminal since you opened it.");
        say("not saved");
      } else {
        say(r.doc.error || "not saved");
      }
    }).catch(function () { say("could not reach the notes service"); })
      .then(function () { saving = false; });
  }

  // Pick up edits made in the terminal while the page is open.
  function poll() {
    if (saving) return;
    call("GET").then(function (r) {
      if (r.status !== 200 || r.doc.mtime === base) return;
      if (!dirty) {
        text.value = r.doc.text;
        base = r.doc.mtime;
        say(viewing ? "updated by " + viewing : "updated from your terminal");
      } else if (!conflict) {
        showBanner("The file changed in your terminal while you have unsaved edits.");
      }
    }).catch(function () {});
  }

  text.addEventListener("input", function () {
    dirty = true;
    say("editing...");
    clearTimeout(timer);
    timer = setTimeout(function () { persist(false); }, 1200);
  });
  save.addEventListener("click", function () { persist(false); });
  document.getElementById("take-theirs").addEventListener("click", load);
  document.getElementById("keep-mine").addEventListener("click", function () { persist(true); });
  window.addEventListener("keydown", function (ev) {
    if ((ev.ctrlKey || ev.metaKey) && ev.key === "s") { ev.preventDefault(); persist(false); }
  });

  function view(name) {
    viewing = name;
    text.readOnly = !!name;
    save.disabled = !!name;
    document.getElementById("readonly").hidden = !name;
    document.getElementById("own-hint").hidden = !!name;
    text.value = "";
    base = null;
    load();
  }

  // Only the facilitator gets a list (403 for everyone else): pick a student to read their notes.
  fetch(API.replace("notes", "students")).then(function (r) {
    if (r.status !== 200) return null;
    return r.json();
  }).then(function (doc) {
    if (!doc || !doc.students) return;
    doc.students.forEach(function (name) {
      var o = document.createElement("option");
      o.value = name;
      o.textContent = name;
      who.appendChild(o);
    });
    document.getElementById("picker").hidden = false;
    who.addEventListener("change", function () {
      if (dirty && !viewing) persist(false);
      view(who.value);
    });
  }).catch(function () {});

  load();
  setInterval(poll, 4000);
})();
