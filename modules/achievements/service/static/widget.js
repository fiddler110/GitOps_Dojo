(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }
  function cell(text, cls) { var td = document.createElement('td'); td.textContent = text; if (cls) { td.className = cls; } return td; }
  function when(ts) { return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  function fill(body, rows, build) {
    while (body.firstChild) { body.removeChild(body.firstChild); }
    rows.forEach(function (r) { var tr = document.createElement('tr'); build(tr, r); body.appendChild(tr); });
  }
  function draw(d) {
    var c = d.completion;
    $('score').textContent = d.score;
    $('rank').textContent = 'rank ' + d.rank + ' of ' + d.of;
    $('who').textContent = 'You are ' + d.name;
    $('fill').style.width = c.percent + '%';
    $('fill').className = 'fill' + (c.complete ? ' done' : '');
    $('completion').textContent = c.done + ' of ' + c.total + ' steps (' + c.percent + '%), ' + c.needed + ' needed to complete';
    $('banner').className = c.complete ? 'banner' : 'banner hidden';
    $('recent-card').className = d.recent.length ? 'card' : 'card hidden';
    fill($('recent'), d.recent.slice(0, 10), function (tr, r) {
      tr.appendChild(cell(r.title)); tr.appendChild(cell(r.points > 0 ? '+' + r.points : '', 'dim')); tr.appendChild(cell(when(r.at), 'dim'));
    });
    $('moments-card').className = d.moments.length ? 'card' : 'card hidden';
    fill($('moments'), d.moments, function (tr, m) {
      var t = cell(m.title); var j = document.createElement('div'); j.className = 'joke dim'; j.textContent = m.joke; t.appendChild(j);
      tr.appendChild(t); tr.appendChild(cell(m.when)); tr.appendChild(cell(when(m.at), 'dim'));
    });
  }
  // Tell the page around us how tall we are, so the landing page can size the frame (toast.js
  // does the resizing); ignored when we are opened on our own.
  function report() {
    if (window.parent !== window) {
      window.parent.postMessage({ type: 'dojo-widget-height', height: document.documentElement.scrollHeight }, window.location.origin);
    }
  }
  function load() {
    fetch('api/me', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d) { draw(d); report(); } })
      .catch(function () {});
  }
  load();
  setInterval(load, 5000);
})();
