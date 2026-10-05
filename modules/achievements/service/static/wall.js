(function () {
  'use strict';
  var body = document.getElementById('rows');
  var empty = document.getElementById('empty');
  var card = document.getElementById('wall-card');
  function cell(text, cls) { var td = document.createElement('td'); td.textContent = text; if (cls) { td.className = cls; } return td; }
  function ago(seconds) {
    if (seconds < 60) { return Math.floor(seconds) + 's ago'; }
    return Math.floor(seconds / 60) + 'm ago';
  }
  function load() {
    fetch('api/wall', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) { return; }
        var rows = d.rows || [];
        empty.className = rows.length ? 'card hidden' : 'card';
        card.className = rows.length ? 'card' : 'card hidden';
        while (body.firstChild) { body.removeChild(body.firstChild); }
        var now = Date.now() / 1000;
        rows.forEach(function (r) {
          var tr = document.createElement('tr');
          tr.appendChild(cell(r.user));
          tr.appendChild(cell(r.challenge));
          tr.appendChild(cell(r.state, r.state === 'LIVE' ? 'neg' : 'dim'));
          tr.appendChild(cell(ago(now - r.last_seen), 'dim'));
          body.appendChild(tr);
        });
      })
      .catch(function () {});
  }
  load();
  setInterval(load, 3000);
})();
