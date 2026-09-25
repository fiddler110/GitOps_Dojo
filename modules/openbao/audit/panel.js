// Vault audit tab (openbao-audit). Polls api/entries with the filters and
// draws the rows. Every string from the audit log (paths, display names,
// errors: students choose many of them) goes in with textContent only.
"use strict";

const $ = (id) => document.getElementById(id);
const FIELDS = ["student", "op", "path", "accessor"];
let timer = null;
let seq = 0;

function cell(tr, cls, text) {
  const td = document.createElement("td");
  if (cls) td.className = cls;
  td.textContent = text || "";
  tr.appendChild(td);
  return td;
}

function clock(iso) {
  const d = new Date(iso);
  return isNaN(d) ? String(iso || "") : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function accessorButton(td, value) {
  if (!value) return;
  const b = document.createElement("button");
  b.type = "button";
  b.className = "acc";
  b.textContent = value;
  b.title = "Show only this token (and what it created)";
  b.addEventListener("click", () => { $("accessor").value = value; refresh(); });
  td.appendChild(b);
}

function row(e) {
  const tr = document.createElement("tr");
  if (e.error) tr.className = "bad";
  cell(tr, "time", clock(e.time));
  cell(tr, "ns", e.namespace || "(root)");
  cell(tr, "who", e.display_name);
  cell(tr, "op", e.operation);
  cell(tr, "path", e.path);
  const acc = cell(tr, "accessor", "");
  accessorButton(acc, e.accessor);
  if (e.created_accessor) {
    acc.appendChild(document.createTextNode(" → "));
    accessorButton(acc, e.created_accessor);
  }
  cell(tr, "result", e.error || "ok");
  return tr;
}

function students(names) {
  const sel = $("student");
  const have = new Set(Array.from(sel.options, (o) => o.value));
  for (const n of names) {
    if (have.has(n)) continue;
    const o = document.createElement("option");
    o.value = n;
    o.textContent = n;
    sel.appendChild(o);
  }
}

async function refresh() {
  const q = new URLSearchParams();
  for (const f of FIELDS) {
    const v = $(f).value.trim();
    if (v) q.set(f, v);
  }
  if ($("errors").checked) q.set("errors", "1");
  const mine = ++seq;
  try {
    const r = await fetch("api/entries?" + q.toString(), { cache: "no-store", credentials: "same-origin" });
    const doc = await r.json();
    if (mine !== seq) return;
    if (!r.ok) throw new Error(doc.error || r.status);
    $("error").hidden = true;
    students(doc.students || []);
    $("rows").replaceChildren(...doc.entries.map(row));
    $("empty").hidden = doc.entries.length > 0;
    $("summary").textContent = `Showing ${doc.entries.length} of ${doc.total} recent requests.`;
  } catch (err) {
    if (mine !== seq) return;
    $("error").textContent = "Could not load the audit log: " + err.message;
    $("error").hidden = false;
  }
}

function schedule() {
  clearInterval(timer);
  timer = $("live").checked ? setInterval(refresh, 5000) : null;
}

for (const f of FIELDS) $(f).addEventListener(f === "path" || f === "accessor" ? "input" : "change", refresh);
$("errors").addEventListener("change", refresh);
$("live").addEventListener("change", schedule);
$("filters").addEventListener("submit", (ev) => { ev.preventDefault(); refresh(); });
$("clear").addEventListener("click", () => {
  $("filters").reset();
  refresh();
  schedule();
});
refresh();
schedule();
