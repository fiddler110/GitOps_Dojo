(function () {
  'use strict';
  // Wall of shame projector page (plan 8.12). Rows come from achievements' existing
  // /achievements/api/wall (LIVE while fresh dump_success events keep arriving, else
  // DISCONNECTED); this page only draws them, and only when CTF_WALL_OF_SHAME is on.
  var body = document.getElementById('rows');
  var table = document.getElementById('wall');
  var empty = document.getElementById('empty');
  var off = document.getElementById('off');
  var note = document.getElementById('note');
  var ageOff = 300;
  function show(el, on) { el.className = (el.className || '').replace(/\bhidden\b/g, '').trim() + (on ? '' : ' hidden'); }
  function cell(text, cls) { var td = document.createElement('td'); td.textContent = text; if (cls) { td.className = cls; } return td; }
  function ago(s) { return s < 60 ? Math.max(0, Math.floor(s)) + 's ago' : Math.floor(s / 60) + 'm ago'; }
  function draw(rows) {
    var now = Date.now() / 1000;
    // A disconnected entry is a contained one: keep it up briefly as the reward, then age it off.
    var keep = rows.filter(function (r) { return r.state === 'LIVE' || now - r.last_seen <= ageOff; });
    while (body.firstChild) { body.removeChild(body.firstChild); }
    keep.sort(function (a, b) { return (a.state === 'LIVE' ? 0 : 1) - (b.state === 'LIVE' ? 0 : 1) || b.last_seen - a.last_seen; });
    keep.forEach(function (r) {
      var tr = document.createElement('tr');
      tr.appendChild(cell(r.user));
      tr.appendChild(cell(r.challenge));
      tr.appendChild(r.state === 'LIVE' ? cell('LIVE', 'live') : cell('DISCONNECTED (contained)', 'cut'));
      tr.appendChild(cell(ago(now - r.last_seen), 'dim'));
      body.appendChild(tr);
    });
    show(table, keep.length > 0);
    show(empty, keep.length === 0);
  }
  function load() {
    fetch('/achievements/api/wall', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d) { draw(d.rows || []); } })
      .catch(function () {});
  }
  fetch('/ctf-wall/config', { credentials: 'same-origin', cache: 'no-store' })
    .then(function (r) { return r.json(); })
    .then(function (c) {
      if (!c.enabled) { show(off, true); show(note, false); return; }
      ageOff = c.age_off;
      load();
      setInterval(load, 3000);
    })
    .catch(function () { show(off, true); });
})();
