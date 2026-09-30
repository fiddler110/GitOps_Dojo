(function () {
  'use strict';
  var body = document.getElementById('rows');
  function cell(text) { var td = document.createElement('td'); td.textContent = text; return td; }
  function load() {
    fetch('api/board', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) { return; }
        while (body.firstChild) { body.removeChild(body.firstChild); }
        d.rows.forEach(function (r) {
          var tr = document.createElement('tr');
          if (r.you) { tr.className = 'you'; }
          tr.appendChild(cell(r.rank)); tr.appendChild(cell(r.you ? r.name + ' (you)' : r.name)); tr.appendChild(cell(r.score));
          body.appendChild(tr);
        });
      })
      .catch(function () {});
  }
  load();
  setInterval(load, 5000);
})();
