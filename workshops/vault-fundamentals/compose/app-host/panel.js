// The Apps page (app-host's apphost.py, behind the gateway's /apps route).
// Every string from the API is set with textContent: slot logs and commit
// authors come from students.
"use strict";

const LIGHTS = { running: "green", starting: "yellow", restarting: "yellow", crashed: "red", failed: "red" };
const open = new Set();

function ago(t, now) {
  const s = Math.max(0, Math.round(now - t));
  if (s < 60) return s + " s ago";
  if (s < 3600) return Math.round(s / 60) + " min ago";
  return Math.round(s / 3600) + " h ago";
}

function render(doc) {
  document.getElementById("error").hidden = true;
  if (doc.facilitator) {
    document.getElementById("title").textContent = "Apps";
    document.getElementById("sub").textContent =
      "Every student's slot on app-host, the platform their pipelines deploy to (Labs 10-12).";
  }
  document.getElementById("empty").hidden = doc.slots.length > 0;
  const box = document.getElementById("slots");
  const tpl = document.getElementById("slot-card");
  box.querySelectorAll("details").forEach((d) => {
    if (d.open) open.add(d.dataset.slot); else open.delete(d.dataset.slot);
  });
  box.replaceChildren();
  for (const s of doc.slots) {
    const card = tpl.content.cloneNode(true);
    const q = (sel) => card.querySelector(sel);
    q(".light").className = "light " + (LIGHTS[s.state] || "");
    q(".name").textContent = s.name;
    q(".state").textContent = s.state + " · " + ago(s.since, doc.now);
    q(".open").href = s.name + "/";
    q(".open").hidden = s.state !== "running";
    const d = s.deployed;
    q(".deployed").textContent = d ? ((d.sha || "").slice(0, 10) + " · " + ago(d.at, doc.now)) : "never";
    q(".actor").textContent = d ? (d.actor || "–") : "–";
    q(".token").textContent = s.token_expires > doc.now
      ? "valid " + Math.round((s.token_expires - doc.now) / 60) + " more min" : "expired";
    q(".restarts").textContent = String(s.restarts);
    q(".log").textContent = (s.log || []).join("\n") || "(nothing yet)";
    const det = q("details");
    det.dataset.slot = s.name;
    // A student's own log starts open; after that, whatever they left open.
    det.open = open.has(s.name) || (!doc.facilitator && !render.done);
    box.appendChild(card);
  }
  render.done = true;
}

async function refresh() {
  try {
    const r = await fetch("api/status", { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    render(await r.json());
  } catch (e) {
    const el = document.getElementById("error");
    el.textContent = "Can't reach app-host: " + e.message;
    el.hidden = false;
  }
}

refresh();
setInterval(refresh, 5000);
