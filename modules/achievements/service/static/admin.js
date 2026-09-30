(function () {
  'use strict';
  var HDR = { 'Content-Type': 'application/json', 'X-Requested-With': 'dojo-admin' };
  function $(id) { return document.getElementById(id); }
  function cell(text) { var td = document.createElement('td'); td.textContent = text; return td; }
  function say(t, bad) { $('msg').textContent = t; $('msg').className = bad ? 'err' : 'dim'; }
  function post(path, body) {
    return fetch('api/' + path, { method: 'POST', headers: HDR, credentials: 'same-origin', body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) { throw new Error(d.error || r.status); } return d; }); });
  }
  function clear(el) { while (el.firstChild) { el.removeChild(el.firstChild); } }
  function draw(d) {
    clear($('rows'));
    d.students.forEach(function (s) {
      var tr = document.createElement('tr');
      [s.rank, s.user, s.name, s.score, s.percent + '%' + (s.complete ? ' ✓' : ''), s.moments.join(', '), s.cheats.join(', ')]
        .forEach(function (v) { tr.appendChild(cell(v)); });
      var td = document.createElement('td'), b = document.createElement('button');
      b.textContent = 'Reset'; b.className = 'danger';
      b.addEventListener('click', function () {
        if (window.confirm('Reset all achievements for ' + s.user + '?')) { post('reset', { user: s.user }).then(load).catch(function (e) { say(e.message, true); }); }
      });
      td.appendChild(b); tr.appendChild(td); $('rows').appendChild(tr);
    });
    clear($('log'));
    d.log.slice().reverse().forEach(function (e) {
      var tr = document.createElement('tr');
      tr.appendChild(cell(new Date(e.at * 1000).toLocaleTimeString()));
      tr.appendChild(cell(e.action + ' ' + e.user + (e.points !== undefined ? ' ' + e.points : '') + (e.reason ? ' (' + e.reason + ')' : '')));
      $('log').appendChild(tr);
    });
    clear($('checks'));
    (d.checks || []).slice().reverse().forEach(function (c) {
      var tr = document.createElement('tr');
      [new Date(c.at * 1000).toLocaleTimeString(), c.user, c.id, c.passed ? 'pass' : 'not yet',
        c.hints + ' hint' + (c.hints === 1 ? '' : 's'), c.points === null || c.points === undefined ? '' : '+' + c.points]
        .forEach(function (v) { tr.appendChild(cell(v)); });
      $('checks').appendChild(tr);
    });
  }
  function load() {
    fetch('api/state', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { if (d) { draw(d); } }).catch(function () {});
  }
  $('a-go').addEventListener('click', function () {
    post('award', { user: $('a-user').value.trim(), points: parseInt($('a-pts').value, 10), reason: $('a-why').value })
      .then(function () { say('Awarded.'); load(); }).catch(function (e) { say(e.message, true); });
  });
  $('reload').addEventListener('click', function () {
    post('reload', {}).then(function () { say('Catalog reloaded.'); load(); }).catch(function (e) { say(e.message, true); });
  });
  load();
  setInterval(load, 5000);
})();
