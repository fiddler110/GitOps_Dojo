(function () {
  'use strict';
  var KEY = 'dojo-cert-name';
  function $(id) { return document.getElementById(id); }
  function show(id, on) { $(id).classList[on ? 'remove' : 'add']('hidden'); }
  function cell(text, cls) { var td = document.createElement('td'); td.textContent = text; if (cls) { td.className = cls; } return td; }
  function day(at) { return new Date(at * 1000).toLocaleDateString(); }
  function store(v) { try { if (v === undefined) { return localStorage.getItem(KEY); } localStorage.setItem(KEY, v); } catch (e) { return null; } }
  function fill(id, rows, build) {
    var b = $(id); while (b.firstChild) { b.removeChild(b.firstChild); }
    rows.forEach(function (r) { var tr = document.createElement('tr'); build(tr, r); b.appendChild(tr); });
  }
  var doc = null;
  function chosen() {
    var typed = $('typed').value.trim();
    return document.querySelector('input[name=who]:checked').value === 'typed' && typed ? typed : doc.board_name;
  }
  function suggest() {
    var v = $('typed').value.trim(), at = v.indexOf('@');
    $('suggest').textContent = at > 0 ? 'Use just "' + v.slice(0, at) + '"? Click here.' : '';
    $('suggest').style.cursor = at > 0 ? 'pointer' : '';
  }
  function draw() {
    var name = chosen();
    $('c-name').textContent = name;
    store(document.querySelector('input[name=who]:checked').value === 'typed' ? $('typed').value.trim() : '');
    $('badge-img').src = window.dojoBadge($('badge-canvas'), doc.workshop, doc.tier).toDataURL('image/png');
  }
  function start(d) {
    doc = d;
    if (!d.tier) {
      $('gate').textContent = 'Not yet: the certificate unlocks at workshop completion (' + d.completion.done + ' of ' +
        d.completion.total + ' core milestones so far). Keep going.';
      show('gate', true); return;
    }
    $('opt-board').textContent = 'My leaderboard name (' + d.board_name + ')';
    var saved = store(); if (saved) { $('typed').value = saved; document.querySelector('input[name=who][value=typed]').checked = true; }
    $('c-workshop').textContent = d.workshop;
    $('c-facts').textContent = d.score + ' points · rank ' + d.rank + ' of ' + d.of + (d.tier === 'capstone' ? ' · capstone cleared' : '');
    $('c-sig').textContent = d.signature ? 'Facilitator: ' + d.signature : 'Facilitator';
    $('c-date').textContent = d.class_date || new Date().toLocaleDateString();
    fill('s-unlocks', d.unlocks, function (tr, u) {
      var how = u.kind === 'challenge' || u.kind === 'capstone'
        ? u.kind + (u.revealed ? ', answer revealed' : u.hints ? ', ' + u.hints + ' hint' + (u.hints === 1 ? '' : 's') : ', no hints') : u.kind;
      tr.appendChild(cell(u.title)); tr.appendChild(cell(how, 'dim')); tr.appendChild(cell(u.points)); tr.appendChild(cell(day(u.at), 'dim'));
    });
    show('s-moments-wrap', d.moments.length);
    fill('s-moments', d.moments, function (tr, m) { tr.appendChild(cell(m.title)); tr.appendChild(cell(m.when, 'dim')); tr.appendChild(cell(day(m.at), 'dim')); });
    show('s-cheats-wrap', d.cheats.length);
    fill('s-cheats', d.cheats, function (tr, c) { tr.appendChild(cell(c.title)); tr.appendChild(cell(c.points, c.points < 0 ? 'neg' : 'dim')); tr.appendChild(cell(day(c.at), 'dim')); });
    ['tools', 'page1', 'page2'].forEach(function (id) { show(id, true); });
    draw();
  }
  document.addEventListener('change', function (e) { if (doc && e.target.name === 'who') { draw(); } });
  $('typed').addEventListener('input', function () { suggest(); if (doc) { document.querySelector('input[name=who][value=typed]').checked = true; draw(); } });
  $('suggest').addEventListener('click', function () {
    var v = $('typed').value, at = v.indexOf('@'); if (at > 0) { $('typed').value = v.slice(0, at); suggest(); draw(); }
  });
  $('print').addEventListener('click', function () { window.print(); });
  $('png').addEventListener('click', function () {
    var a = document.createElement('a'); a.download = 'badge.png'; a.href = $('badge-canvas').toDataURL('image/png');
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  });
  fetch('api/certificate', { credentials: 'same-origin', cache: 'no-store' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) { if (d) { start(d); } else { $('gate').textContent = 'Sign in through the lab first.'; show('gate', true); } })
    .catch(function () { $('gate').textContent = 'Could not load.'; show('gate', true); });
})();
