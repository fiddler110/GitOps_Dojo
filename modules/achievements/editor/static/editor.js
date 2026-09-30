// Achievement catalog editor. Every catalog string goes into the page with textContent or
// an input's value, never innerHTML. Edits stay here until Save; the server validates them all.
"use strict";

const COLS = {
  milestone: ["title", "joke", "when", "points", "core", "match"],
  funny: ["title", "joke", "when", "points", "match"],
  cheat: ["title", "joke", "when", "points", "match"],
  challenge: ["title", "goal", "hint1", "hint2", "answer", "points"],
  capstone: ["title", "goal", "hint1", "hint2", "answer", "points"],
};
const HEAD = { title: "Title", joke: "Joke", when: "When", points: "Pts", core: "Core", match: "Match (read-only)",
  goal: "Goal", hint1: "Hint 1", hint2: "Hint 2", answer: "Answer" };
const REQUIRED = { milestone: ["title", "joke", "when"], funny: ["title", "joke", "when"],
  cheat: ["title", "joke", "when"], challenge: ["title", "goal"], capstone: ["title", "goal"] };

let token = "";
let bases = {};
let rows = [];          // {row, orig, cur, tr, ws, inputs: {field: element}, sw}
let sections = [];      // {ws, el, count, groups: [{el, rows}]}
let lastData = null;    // the catalog as last loaded or saved

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function changedFields(r) {
  return Object.keys(r.cur).filter((f) => !same(r.cur[f], r.orig[f]));
}

function problems(r) {
  const bad = new Set();
  for (const f of REQUIRED[r.row.kind]) if (!String(r.cur[f] || "").trim()) bad.add(f);
  if ("hints" in r.cur) r.cur.hints.forEach((h, i) => { if (!h.trim()) bad.add("hint" + (i + 1)); });
  const p = r.cur.points;
  if (p !== null && (!Number.isInteger(p) || p < -100 || p > 1000)) bad.add("points");
  if ((r.row.kind === "funny" || r.row.kind === "cheat") && Number.isInteger(p) && p > 0) bad.add("points");
  return bad;
}

function dirty() {
  return rows.some((r) => changedFields(r).length);
}

function refreshRow(r) {
  const bad = problems(r);
  for (const [f, input] of Object.entries(r.inputs)) input.classList.toggle("invalid", bad.has(f));
  r.tr.classList.toggle("changed", changedFields(r).length > 0);
  r.tr.classList.toggle("off", !r.cur.enabled);
  r.sw.checked = r.cur.enabled;
}

function refreshStatus() {
  const changed = rows.filter((r) => changedFields(r).length).length;
  const invalid = rows.filter((r) => problems(r).size).length;
  $("status").textContent = changed ? `${changed} row(s) changed` + (invalid ? `, ${invalid} invalid` : "") : "No changes";
  $("save").disabled = !changed || invalid > 0;
  $("discard").disabled = !changed;
  for (const s of sections) {
    const mine = rows.filter((r) => r.ws === s.ws);
    s.count.textContent = `${mine.filter((r) => r.cur.enabled).length} of ${mine.length} on`;
  }
}

function textCell(r, field, getter, setter) {
  const td = el("td");
  const t = el("textarea");
  t.rows = 2;
  t.value = getter();
  t.setAttribute("aria-label", `${r.row.id} ${field}`);
  t.addEventListener("input", () => { setter(t.value); changed(r); });
  r.inputs[field] = t;
  td.append(t);
  return td;
}

function cellFor(r, field) {
  const c = r.cur;
  if (field === "match") {
    const td = el("td", "match", r.row.match || "(none)");
    return td;
  }
  if (field === "points") {
    const td = el("td");
    const i = el("input");
    i.type = "number";
    i.step = "1";
    i.placeholder = String(r.row.default_points);
    i.title = `Empty means the default (${r.row.default_points})`;
    i.value = c.points === null || c.points === undefined ? "" : String(c.points);
    i.setAttribute("aria-label", `${r.row.id} points`);
    i.addEventListener("input", () => {
      const v = i.value.trim();
      c.points = v === "" ? null : Number(v);
      changed(r);
    });
    r.inputs.points = i;
    td.append(i);
    return td;
  }
  if (field === "core") {
    const td = el("td");
    const i = el("input");
    i.type = "checkbox";
    i.checked = !!c.core;
    i.setAttribute("aria-label", `${r.row.id} core`);
    i.addEventListener("change", () => { c.core = i.checked; changed(r); });
    r.inputs.core = i;
    td.append(i);
    return td;
  }
  if (field === "hint1" || field === "hint2") {
    const n = field === "hint1" ? 0 : 1;
    return textCell(r, field, () => c.hints[n], (v) => { c.hints = c.hints.slice(); c.hints[n] = v; });
  }
  return textCell(r, field, () => c[field], (v) => { c[field] = v; });
}

function changed(r) {
  refreshRow(r);
  refreshStatus();
  applyFilter();
}

function buildRow(row, ws) {
  const r = { row, ws, orig: row.fields, cur: JSON.parse(JSON.stringify(row.fields)), inputs: {} };
  const tr = el("tr");
  r.tr = tr;
  const tdSw = el("td", "toggle");
  const sw = el("input", "switch");
  sw.type = "checkbox";
  sw.setAttribute("role", "switch");
  sw.setAttribute("aria-label", `${row.id} enabled`);
  sw.title = "On: students can earn it. Off: hidden, never fires, not counted.";
  sw.addEventListener("change", () => { r.cur.enabled = sw.checked; changed(r); });
  r.sw = sw;
  tdSw.append(sw);
  tr.append(tdSw);
  const tdId = el("td", "id", row.id);
  if (row.retired) tdId.append(el("span", "badge", "retired"));
  tr.append(tdId);
  for (const f of COLS[row.kind]) tr.append(cellFor(r, f));
  r.search = [row.id, row.match, row.file].join(" ").toLowerCase();
  rows.push(r);
  refreshRow(r);
  return tr;
}

function render(data) {
  lastData = data;
  token = data.token;
  bases = data.bases;
  rows = [];
  sections = [];
  const main = $("main");
  main.replaceChildren();
  const pick = $("workshop");
  const keep = pick.value;
  pick.replaceChildren(el("option", "", "All workshops"));
  pick.firstChild.value = "";
  if (data.errors.length) showErrors(["Some files could not be read:"].concat(data.errors));
  for (const w of data.workshops) {
    const opt = el("option", "", w.title);
    opt.value = w.name;
    pick.append(opt);
    const sec = el("section");
    const h2 = el("h2");
    h2.append(el("span", "", w.title));
    if (w.name !== "shared") h2.append(el("span", "dim", w.name));
    const count = el("span", "dim");
    h2.append(count);
    const on = el("button", "small plain", "All on");
    const off = el("button", "small plain", "All off");
    on.type = off.type = "button";
    on.addEventListener("click", () => bulk(w.name, true));
    off.addEventListener("click", () => bulk(w.name, false));
    h2.append(on, off);
    sec.append(h2);
    const s = { ws: w.name, el: sec, count, groups: [] };
    for (const g of w.groups) {
      const gEl = el("div");
      gEl.append(el("h3", "", g.label));
      const wrap = el("div", "tablewrap");
      const table = el("table");
      const head = el("tr");
      head.append(el("th", "", "On"), el("th", "", "ID"));
      for (const f of COLS[g.kind]) head.append(el("th", "", HEAD[f]));
      const thead = el("thead");
      thead.append(head);
      const tbody = el("tbody");
      const mine = [];
      for (const row of g.rows) {
        tbody.append(buildRow(row, w.name));
        mine.push(rows[rows.length - 1]);
      }
      table.append(thead, tbody);
      wrap.append(table);
      gEl.append(wrap);
      sec.append(gEl);
      s.groups.push({ el: gEl, rows: mine });
    }
    sections.push(s);
    main.append(sec);
  }
  pick.value = [...pick.options].some((o) => o.value === keep) ? keep : "";
  refreshStatus();
  applyFilter();
}

function bulk(ws, value) {
  for (const r of rows) if (r.ws === ws) { r.cur.enabled = value; refreshRow(r); }
  refreshStatus();
  applyFilter();
}

function applyFilter() {
  const q = $("search").value.trim().toLowerCase();
  const ws = $("workshop").value;
  const st = $("state").value;
  for (const s of sections) {
    let any = false;
    for (const g of s.groups) {
      let shown = 0;
      for (const r of g.rows) {
        const text = r.search + " " + JSON.stringify(r.cur).toLowerCase();
        const ok = (!ws || s.ws === ws) && (!q || text.includes(q)) &&
          (st !== "on" || r.cur.enabled) && (st !== "off" || !r.cur.enabled) &&
          (st !== "changed" || changedFields(r).length > 0);
        r.tr.classList.toggle("hidden", !ok);
        if (ok) shown++;
      }
      g.el.classList.toggle("hidden", shown === 0);
      if (shown) any = true;
    }
    s.el.classList.toggle("hidden", !any);
  }
}

function showErrors(list) {
  const box = $("errors");
  box.replaceChildren();
  if (!list || !list.length) { box.classList.add("hidden"); return; }
  const ul = el("ul");
  for (const e of list) ul.append(el("li", "", e));
  box.append(el("strong", "", "Not saved."), ul);
  box.classList.remove("hidden");
}

function notice(text) {
  const n = $("notice");
  n.textContent = text;
  n.classList.toggle("hidden", !text);
}

async function load() {
  const res = await fetch("/api/catalog", { cache: "no-store" });
  const data = await res.json();
  if (!res.ok) { showErrors(data.errors || [res.statusText]); return; }
  showErrors([]);
  render(data);
}

async function save() {
  const changes = [];
  for (const r of rows) {
    const fields = changedFields(r);
    if (!fields.length) continue;
    const set = {};
    for (const f of fields) set[f] = r.cur[f];
    changes.push({ file: r.row.file, id: r.row.id, set });
  }
  if (!changes.length) return;
  $("save").disabled = true;
  notice("Saving...");
  try {
    const res = await fetch("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Editor-Token": token },
      body: JSON.stringify({ changes, bases }),
    });
    const data = await res.json();
    if (!res.ok) {
      notice("");
      showErrors(data.errors || [res.statusText]);
      refreshStatus();
      return;
    }
    showErrors([]);
    render(data.catalog);
    const wrote = data.written.length ? `Wrote ${data.written.join(", ")}` : "No file changed";
    const md = data.rendered.length ? `; regenerated ${data.rendered.join(", ")}` : "";
    notice(`${wrote}${md}. Catalog valid (${data.warnings} warning(s)).`);
  } catch (e) {
    notice("");
    showErrors([`Save failed: ${e}`]);
    refreshStatus();
  }
}

function discard() {
  // row.fields in lastData are the originals (edits live in copies), so re-rendering resets every input.
  render(lastData);
  notice("");
  showErrors([]);
}

document.addEventListener("DOMContentLoaded", () => {
  $("search").addEventListener("input", applyFilter);
  $("workshop").addEventListener("change", applyFilter);
  $("state").addEventListener("change", applyFilter);
  $("save").addEventListener("click", save);
  $("discard").addEventListener("click", () => {
    if (dirty() && !window.confirm("Discard every unsaved change?")) return;
    discard();
  });
  $("reload").addEventListener("click", () => {
    if (dirty() && !window.confirm("Reload from disk and lose unsaved changes?")) return;
    notice("");
    load();
  });
  window.addEventListener("beforeunload", (e) => {
    if (dirty()) { e.preventDefault(); e.returnValue = ""; }
  });
  load().catch((e) => showErrors([`Load failed: ${e}`]));
});
