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
    if (d.mode === 'approve') { $('what').textContent = 'Approves each pull request that adds or removes only its author\'s own records; merging stays with the student.'; }
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
  function el(tag, text, cls) { var e = document.createElement(tag); if (text !== undefined) { e.textContent = text; } if (cls) { e.className = cls; } return e; }
  function drawHelp(d) {
    var box = $('help'); while (box.firstChild) { box.removeChild(box.firstChild); }
    $('helpcount').textContent = d.open ? '(' + d.open + ' waiting)' : '';
    if (!d.requests.length) { box.textContent = 'Nobody has asked for help.'; box.className = 'dim'; return; }
    box.className = '';
    d.requests.forEach(function (r) {
      var card = el('div', undefined, 'help');
      card.appendChild(el('strong', '#' + r.id + ' ' + r.user, r.status === 'open' ? 'neg' : ''));
      card.appendChild(el('span', '  ' + r.minutes + ' min, ' + r.status, 'dim'));
      card.appendChild(el('div', r.text));
      var auto = r.auto || {};
      if (auto.why) { card.appendChild(el('div', 'Sensei recognised: ' + auto.why.title + ' (' + (auto.why.fix || auto.why.explain) + ')', 'dim')); }
      if (auto.ask && auto.ask.length) { card.appendChild(el('div', 'The labs cover it in ' + auto.ask[0].file + ' > ' + auto.ask[0].heading, 'dim')); }
      r.replies.forEach(function (x) { card.appendChild(el('div', x.from + ': ' + x.text, 'dim')); });
      if (r.context) {
        var det = el('details'); det.appendChild(el('summary', 'Their screen'));
        det.appendChild(el('pre', r.context)); card.appendChild(det);
      }
      var input = el('input'); input.type = 'text'; input.placeholder = 'Reply to ' + r.user; input.maxLength = 1000;
      var send = el('button', 'Reply'), done = el('button', 'Close');
      send.addEventListener('click', function () {
        if (!input.value.trim()) { return; }
        post('help/reply', { id: r.id, text: input.value }).then(function () { say('Replied to #' + r.id + '.'); loadHelp(); }).catch(function (e) { say(e.message, true); });
      });
      done.addEventListener('click', function () { post('help/close', { id: r.id }).then(loadHelp).catch(function (e) { say(e.message, true); }); });
      var row = el('div'); row.appendChild(input); row.appendChild(send); row.appendChild(done);
      card.appendChild(row); box.appendChild(card);
    });
  }
  function loadHelp() {
    fetch('api/help', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { if (d) { drawHelp(d); } }).catch(function () {});
  }
  function drawRadar(d) {
    var box = $('radar'); while (box.firstChild) { box.removeChild(box.firstChild); }
    if (!d.available) { box.textContent = 'No scoreboard in this workshop, so no activity to watch.'; box.className = 'dim'; $('radarcount').textContent = ''; return; }
    $('radarcount').textContent = d.students.length ? '(' + d.students.length + ')' : '';
    if (!d.students.length) { box.textContent = 'Nobody looks stuck.'; box.className = 'dim'; return; }
    box.className = '';
    d.students.forEach(function (s) {
      var row = el('div', undefined, 'help');
      row.appendChild(el('strong', s.user, s.level === 'failing' ? 'neg' : ''));
      row.appendChild(el('span', '  ' + s.level + ': ' + s.why.join('; ') + '  (' + s.percent + '% done)' + (s.hand ? '  \u270B hand up' : ''), 'dim'));
      box.appendChild(row);
    });
  }
  function loadRadar() {
    fetch('api/radar', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { if (d) { drawRadar(d); } }).catch(function () {});
  }
  function load() {
    loadHelp();
    loadRadar();
    fetch('api/prs', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { if (d) { draw(d); } }).catch(function () {});
  }
  $('toggle').addEventListener('click', function () { post('enabled', { on: !enabled }).then(load); });
  $('scan').addEventListener('click', function () { post('scan').then(function () { say('Scanned.'); load(); }); });
  load(); setInterval(load, 5000);
})();
