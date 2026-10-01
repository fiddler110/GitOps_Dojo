(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }
  function say(t, bad) { $('msg').textContent = t; $('msg').className = bad ? 'err' : 'dim'; }
  function post(path, body) {
    return fetch('api/' + path, { method: 'POST', credentials: 'same-origin', body: JSON.stringify(body || {}),
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'dojo-admin' } })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) { throw new Error(d.error || r.status); } return d; }); });
  }
  function cell(t, cls) { var td = document.createElement('td'); td.textContent = t; if (cls) { td.className = cls; } return td; }
  function button(label, fn) {
    var td = document.createElement('td'), b = document.createElement('button');
    b.textContent = label; b.addEventListener('click', fn); td.appendChild(b); return td;
  }
  var enabled = true;
  function draw(d) {
    enabled = d.enabled;
    $('attn').textContent = d.attention ? d.attention + ' pull request' + (d.attention === 1 ? '' : 's') + ' need' + (d.attention === 1 ? 's' : '') + ' you' : 'Nothing needs you';
    $('attn').className = d.attention ? 'err' : 'dim';
    $('repo').textContent = d.watching === false ? 'not reviewing pull requests in this workshop' : d.repo; $('toggle').textContent = enabled ? 'Pause' : 'Resume';
    var body = $('rows'); while (body.firstChild) { body.removeChild(body.firstChild); }
    d.prs.forEach(function (p) {
      var tr = document.createElement('tr');
      tr.appendChild(cell(p.number)); tr.appendChild(cell(p.user)); tr.appendChild(cell(p.title));
      tr.appendChild(cell(p.status, p.status === 'needs-review' || p.status === 'error' ? 'neg' : 'dim'));
      tr.appendChild(cell(p.reason, 'dim')); tr.appendChild(cell(p.status === 'merged' ? '' : p.minutes, 'dim'));
      var td = document.createElement('td');
      if (p.status !== 'merged' && p.status !== 'closed') {
        td.appendChild(button('Merge anyway', function () {
          post('merge', { number: p.number }).then(function (r) { say('#' + p.number + ': ' + r.result); load(); }).catch(function (e) { say(e.message, true); });
        }).firstChild);
        td.appendChild(button('Comment', function () {
          var t = window.prompt('Comment on #' + p.number + ' (posted as Sensei):');
          if (t) { post('comment', { number: p.number, text: t }).then(function () { say('Posted.'); }).catch(function (e) { say(e.message, true); }); }
        }).firstChild);
      }
      tr.appendChild(td); body.appendChild(tr);
    });
  }
  function load() {
    fetch('api/prs', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { if (d) { draw(d); } }).catch(function () {});
  }
  $('toggle').addEventListener('click', function () { post('enabled', { on: !enabled }).then(load); });
  $('scan').addEventListener('click', function () { post('scan').then(function () { say('Scanned.'); load(); }); });
  load(); setInterval(load, 5000);
})();
