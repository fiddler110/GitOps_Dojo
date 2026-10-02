// Site Inspector page. Everything shown here comes from a student's own server (headers, certificate
// fields, the page source) and is written with textContent only: never innerHTML. The page itself is shown
// in a sandboxed iframe from api/page/<id>, which the server sends with CSP `sandbox` (no scripts).
"use strict";

const $ = (id) => document.getElementById(id);

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = String(text);
  return n;
}

function clear(n) {
  while (n.firstChild) n.removeChild(n.firstChild);
}

function duration(s) {
  if (s === null || s === undefined) return "";
  const neg = s < 0;
  s = Math.abs(s);
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  const txt = d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : m ? `${m}m ${s % 60}s` : `${s}s`;
  return neg ? `expired ${txt} ago` : txt;
}

function row(dl, k, v) {
  if (v === null || v === undefined || v === "") return;
  dl.appendChild(el("dt", null, k));
  dl.appendChild(el("dd", null, v));
}

function renderTls(tls) {
  const box = el("div", "tls " + (tls.verified ? "good" : "bad"));
  box.appendChild(el("p", "verdict", tls.verified
    ? "Certificate verified: it chains to the lab CA and matches the name"
    : `Certificate NOT trusted: ${tls.error || "no certificate"}`));
  const dl = el("dl");
  row(dl, "Protocol", tls.version);
  row(dl, "Cipher", tls.cipher);
  const c = tls.cert;
  if (c) {
    row(dl, "Subject", c.subject);
    row(dl, "Names (SAN)", (c.names || []).join(", "));
    row(dl, "Issuer", c.issuer);
    row(dl, "Serial", c.serial);
    row(dl, "Valid", `${c.not_before} to ${c.not_after}`);
    row(dl, "Time left", duration(c.seconds_left));
  }
  if (tls.protocols) {
    row(dl, "Accepts", Object.entries(tls.protocols).map(([p, ok]) => `${p} ${ok ? "yes" : "no"}`).join(", ") +
      " (set for all of demo-app's port 443: nginx takes protocol versions from the default server, not per site)");
  }
  box.appendChild(dl);
  return box;
}

function renderHop(h) {
  const li = el("li", "hop " + (h.kind === "hsts" ? "hsts" : ""));
  const line = el("p", "line");
  if (h.kind === "hsts") {
    line.appendChild(el("span", "tag tag-hsts", "HSTS"));
    line.appendChild(el("span", "url", h.url));
    li.appendChild(line);
    li.appendChild(el("p", "note", h.note));
    return li;
  }
  line.appendChild(el("span", "method", "GET"));
  line.appendChild(el("span", "url", h.url));
  if (h.status !== null) {
    const cls = h.status >= 400 ? "bad" : h.status >= 300 ? "warn" : "good";
    line.appendChild(el("span", "tag tag-" + cls, `${h.status} ${h.reason || ""}`.trim()));
  }
  const loc = (h.headers || []).find(([k]) => k.toLowerCase() === "location");
  if (loc) line.appendChild(el("span", "loc", `→ ${loc[1]}`));
  li.appendChild(line);
  if (h.tls) li.appendChild(renderTls(h.tls));
  if (h.error) li.appendChild(el("p", "error", h.error));
  if (h.note) li.appendChild(el("p", "note", h.note));
  if (h.headers && h.headers.length) {
    const d = el("details");
    d.appendChild(el("summary", null, `Response headers (${h.headers.length})`));
    const pre = el("pre");
    pre.textContent = h.headers.map(([k, v]) => `${k}: ${v}`).join("\n");
    d.appendChild(pre);
    li.appendChild(d);
  }
  return li;
}

function renderHsts(list) {
  const ul = $("hsts");
  clear(ul);
  if (!list || !list.length) {
    ul.appendChild(el("li", "muted", "Nothing remembered yet."));
    return;
  }
  for (const e of list) ul.appendChild(el("li", null, `${e.host}: HTTPS only for ${duration(e.seconds_left)}`));
}

function renderResult(r) {
  $("result").hidden = false;
  const hops = $("hops");
  clear(hops);
  for (const n of r.notes || []) hops.appendChild(el("li", "hop note-only", n));
  for (const h of r.hops) hops.appendChild(renderHop(h));
  $("stopped").hidden = !r.stopped;
  $("stopped").textContent = r.stopped || "";
  const f = r.final;
  $("final").hidden = !f;
  if (f) {
    $("final-url").textContent = `for ${f.url}`;
    const tb = $("security");
    clear(tb);
    for (const s of f.security) {
      const tr = el("tr", s.ok ? "good" : "bad");
      tr.appendChild(el("td", "name", (s.ok ? "✓ " : "✗ ") + s.name));
      tr.appendChild(el("td", "value", s.value || "—"));
      tr.appendChild(el("td", null, s.note));
      tb.appendChild(tr);
    }
    $("page-note").textContent = `${f.status}, ${f.content_type}, ${f.bytes} bytes` +
      (f.truncated ? " (cut short)" : "") + ". Shown with scripts switched off.";
    const frame = $("preview");
    frame.hidden = !f.page;
    if (f.page) frame.src = `api/page/${f.page}`;
    $("source").textContent = f.source || "";
  }
  renderHsts(r.hsts);
}

async function visit(target) {
  const status = $("status");
  status.textContent = `Visiting ${target}…`;
  status.className = "status";
  $("visit").disabled = true;
  try {
    const res = await fetch(`api/visit?url=${encodeURIComponent(target)}`, { credentials: "same-origin" });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
    status.textContent = "";
    renderResult(body);
    try { history.replaceState(null, "", `?url=${encodeURIComponent(target)}`); } catch (e) { /* framed */ }
  } catch (e) {
    status.textContent = e.message;
    status.className = "status error";
  } finally {
    $("visit").disabled = false;
  }
}

async function init() {
  const res = await fetch("api/me", { credentials: "same-origin" });
  const me = await res.json();
  if (!res.ok) {
    $("status").textContent = me.error || "Not signed in";
    return;
  }
  const dl = $("names");
  for (const n of me.suggestions) dl.appendChild(el("option", null, n)).value = n;
  $("url").placeholder = me.suggestions[0];
  if (me.facilitator) {
    $("hint").textContent = `Facilitator: you can visit any name under ${me.zone}, e.g. student01.${me.zone}.`;
  }
  renderHsts(me.hsts);
  $("go").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const target = $("url").value.trim() || me.suggestions[0];
    $("url").value = target;
    visit(target);
  });
  $("forget").addEventListener("click", async () => {
    const r = await fetch("api/forget", { method: "POST", credentials: "same-origin",
      headers: { "X-Requested-With": "inspector" } });
    if (r.ok) renderHsts([]);
  });
  const q = new URLSearchParams(location.search).get("url");
  if (q) {
    $("url").value = q;
    visit(q);
  }
}

document.addEventListener("DOMContentLoaded", init);
