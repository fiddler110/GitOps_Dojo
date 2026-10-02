// Runners panel (runner-controller). Polls api/state and draws it. Every
// string from the controller (runner names, repo names chosen by students,
// error text) goes in with textContent, never innerHTML.
"use strict";

const $ = (id) => document.getElementById(id);
let busy = false;

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function ago(ts) {
  if (!ts) return "";
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (s < 60) return s + " s";
  if (s < 3600) return Math.floor(s / 60) + " min " + (s % 60) + " s";
  return Math.floor(s / 3600) + " h " + Math.floor((s % 3600) / 60) + " min";
}

function clock(ts) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function list(ul, empty, items, render) {
  ul.replaceChildren(...items.map(render));
  empty.hidden = items.length > 0;
}

function draw(st) {
  $("alive").textContent = String(st.alive);
  $("count-label").textContent = st.alive === 1 ? "runner" : "runners";
  $("busy").textContent = String(st.busy);
  $("waiting-count").textContent = String(st.waiting.length);
  $("min").textContent = String(st.min_idle);
  $("max").textContent = String(st.max);
  $("max-minus").disabled = st.max <= 1;
  $("max-plus").disabled = st.max >= st.ceiling;
  $("max-plus").title = "Up to " + st.ceiling + " (the pool shares one memory limit)";
  $("mode-auto").classList.toggle("on", st.mode === "auto");
  $("mode-manual").classList.toggle("on", st.mode === "manual");
  $("mode-auto").setAttribute("aria-pressed", String(st.mode === "auto"));
  $("mode-manual").setAttribute("aria-pressed", String(st.mode === "manual"));
  $("help").textContent = st.mode === "auto"
    ? "Auto: − / + change how many idle runners are kept ready; more start by themselves when jobs wait, up to Max. " +
      "At the max, + raises Max too."
    : "Manual: nothing starts or stops by itself. + adds a runner (raising Max if needed), − removes an idle one " +
      "(never a busy one).";
  const err = st.error || (st.paused ? "Several runners failed to start: Auto is pausing new starts for a minute." : "");
  $("error").textContent = err;
  $("error").hidden = !err;

  const tbody = $("runners");
  tbody.replaceChildren(...st.runners.map((r) => {
    const tr = el("tr");
    const light = el("span", "light " + (r.state === "starting" ? "starting" : r.light));
    light.title = r.light;
    const td0 = el("td");
    td0.append(light);
    tr.append(td0, el("td", "name", r.name), el("td", "", r.detail), el("td", "repo", r.repo), el("td", "", ago(r.since)));
    return tr;
  }));
  $("no-runners").hidden = st.runners.length > 0;

  list($("waiting"), $("no-waiting"), st.waiting, (j) => el("li", "", j.repo + ": " + j.job));
  list($("problems"), $("no-problems"), st.problems, (p) => {
    const li = el("li");
    li.append(el("span", "when", clock(p.time)), document.createTextNode(p.runner + ": " + p.detail));
    return li;
  });
}

async function refresh() {
  try {
    const resp = await fetch("api/state", { cache: "no-store", credentials: "same-origin" });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    draw(await resp.json());
  } catch (e) {
    $("error").textContent = "Can't reach the runner controller (" + e.message + ").";
    $("error").hidden = false;
  }
}

async function post(path, body) {
  if (busy) return;
  busy = true;
  const msg = $("message");
  try {
    const resp = await fetch(path, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Requested-With": "dojo-runners" },
      body: JSON.stringify(body),
    });
    const doc = await resp.json();
    msg.textContent = doc.message || doc.error || "";
    msg.classList.toggle("bad", !doc.ok);
    if (doc.state) draw(doc.state);
  } catch (e) {
    msg.textContent = "Failed: " + e.message;
    msg.classList.add("bad");
  } finally {
    busy = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("plus").addEventListener("click", () => post("api/scale", { delta: 1 }));
  $("minus").addEventListener("click", () => post("api/scale", { delta: -1 }));
  $("max-plus").addEventListener("click", () => post("api/max", { delta: 1 }));
  $("max-minus").addEventListener("click", () => post("api/max", { delta: -1 }));
  for (const b of document.querySelectorAll(".mode button")) {
    b.addEventListener("click", () => post("api/mode", { mode: b.dataset.mode }));
  }
  refresh();
  setInterval(refresh, 2500);
});
