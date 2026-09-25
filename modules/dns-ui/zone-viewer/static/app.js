// DNS Zones: polls api/zones and renders every record, highlighting what has
// been added, changed or removed since the page was opened (or last cleared).
// Record values are student-controlled and shown to the whole class, so every
// string goes in through textContent, never innerHTML.
"use strict";

(function () {
  const POLL_MS = 3000;
  const $ = (id) => document.getElementById(id);

  let baseline = null;   // Map key -> row, as of page load / last clear
  let current = null;    // last snapshot's zones
  let lastZones = "";    // last snapshot's zones as JSON, to skip identical re-renders
  let updatedAt = null;
  let lastError = null;

  const rowKey = (zone, r) => [zone, r.name, r.type, r.content].join("\u0000");

  function flatten(zones) {
    const map = new Map();
    for (const z of zones) for (const r of z.records) map.set(rowKey(z.name, r), Object.assign({ zone: z.name }, r));
    return map;
  }

  function shortName(name, zone) {
    if (name === zone) return "@";
    return name.endsWith("." + zone) ? name.slice(0, -(zone.length + 1)) : name;
  }

  // Same order as the server: apex first, then names read right to left, then type.
  function sortKey(r) {
    return [r.name === r.zone ? "0" : "1", r.name.split(".").reverse().join("\u0001"), r.type, r.content].join("\u0000");
  }

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function matches(r, q) {
    if (!q) return true;
    return (r.name + " " + r.type + " " + r.content).toLowerCase().includes(q);
  }

  function render() {
    const main = $("zones");
    main.replaceChildren();
    if (!current) return;
    const q = $("filter").value.trim().toLowerCase();
    const now = flatten(current);

    // Zones from the current snapshot plus any that were in the baseline and have since gone.
    const zoneNames = new Set(current.map((z) => z.name));
    if (baseline) for (const r of baseline.values()) zoneNames.add(r.zone);
    const serials = new Map(current.map((z) => [z.name, z.serial]));

    if (zoneNames.size === 0) {
      main.append(el("p", "empty", "PowerDNS has no zones yet. They appear here after the first push."));
      return;
    }

    // Group by name + type. A set with one value before and after (an A record whose
    // address moved, the SOA whose serial bumps on every push) is one "changed" row;
    // otherwise values are compared one by one (new / removed).
    const groups = (map, zone) => {
      const g = new Map();
      for (const r of map.values()) {
        if (r.zone !== zone) continue;
        const k = r.name + "\u0000" + r.type;
        if (!g.has(k)) g.set(k, []);
        g.get(k).push(r);
      }
      return g;
    };
    const same = (a, b) => a.content === b.content && a.ttl === b.ttl && a.disabled === b.disabled;

    for (const zone of [...zoneNames].sort()) {
      const rows = [];
      const nowG = groups(now, zone);
      const beforeG = baseline ? groups(baseline, zone) : new Map();
      for (const k of new Set([...nowG.keys(), ...beforeG.keys()])) {
        const after = nowG.get(k) || [];
        const before = beforeG.get(k) || [];
        if (!baseline) { for (const r of after) rows.push({ r, state: "" }); continue; }
        if (after.length === 1 && before.length === 1) {
          rows.push({ r: after[0], state: same(after[0], before[0]) ? "" : "changed" });
          continue;
        }
        const beforeBy = new Map(before.map((r) => [r.content, r]));
        const afterBy = new Map(after.map((r) => [r.content, r]));
        for (const r of after) {
          const b = beforeBy.get(r.content);
          rows.push({ r, state: !b ? "new" : same(r, b) ? "" : "changed" });
        }
        for (const r of before) if (!afterBy.has(r.content)) rows.push({ r, state: "removed" });
      }
      rows.sort((a, b) => (sortKey(a.r) < sortKey(b.r) ? -1 : sortKey(a.r) > sortKey(b.r) ? 1 : 0));
      const shown = rows.filter((x) => matches(x.r, q));

      const section = el("section", "zone");
      const head = el("h2", "zone-name", zone);
      const meta = el("span", "zone-meta",
        serials.has(zone) ? `serial ${serials.get(zone)} · ${rows.filter((x) => x.state !== "removed").length} records`
                          : "zone removed");
      head.append(" ", meta);
      section.append(head);

      if (shown.length === 0) {
        section.append(el("p", "empty", q ? "No records match the filter." : "No records."));
        main.append(section);
        continue;
      }

      const wrap = el("div", "table-wrap");
      const table = el("table");
      const thead = el("thead");
      const hr = el("tr");
      for (const h of ["Name", "Type", "TTL", "Value", ""]) hr.append(el("th", null, h));
      thead.append(hr);
      const tbody = el("tbody");
      for (const { r, state } of shown) {
        const tr = el("tr", state ? "row-" + state : null);
        const name = el("td", "name", shortName(r.name, zone));
        name.title = r.name;
        tr.append(name, el("td", "type", r.type), el("td", "ttl", String(r.ttl)));
        const value = el("td", "value");
        value.append(el("code", null, r.content));
        if (r.disabled) value.append(" ", el("span", "tag tag-disabled", "disabled"));
        tr.append(value);
        const tagCell = el("td", "state");
        if (state) tagCell.append(el("span", "tag tag-" + state, state));
        tr.append(tagCell);
        tbody.append(tr);
      }
      table.append(thead, tbody);
      wrap.append(table);
      section.append(wrap);
      main.append(section);
    }
  }

  function renderStatus() {
    const status = $("status");
    status.classList.toggle("error", Boolean(lastError));
    if (lastError && !current) { status.textContent = lastError + ". Retrying…"; return; }
    const ago = updatedAt ? Math.max(0, Math.round(Date.now() / 1000 - updatedAt)) : null;
    let text = ago === null ? "Waiting for PowerDNS…" : `Updated ${ago}s ago`;
    if (lastError) text += ` · ${lastError}, showing the last good data`;
    status.textContent = text;
  }

  async function poll() {
    try {
      const resp = await fetch("api/zones", { cache: "no-store" });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const snap = await resp.json();
      lastError = snap.error || null;
      updatedAt = snap.updated;
      const zonesJson = JSON.stringify(snap.zones);
      if (snap.zones && zonesJson !== lastZones) {
        lastZones = zonesJson;
        current = snap.zones;
        if (!baseline) baseline = flatten(current);
        $("legend").hidden = false;
        render();
      }
    } catch (e) {
      lastError = "Can't reach the zone viewer";
    }
    renderStatus();
  }

  $("filter").addEventListener("input", render);
  $("clear").addEventListener("click", () => {
    if (current) { baseline = flatten(current); render(); }
  });
  poll();
  setInterval(poll, POLL_MS);
  setInterval(renderStatus, 1000);
})();
