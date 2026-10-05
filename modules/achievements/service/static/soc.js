(function () {
  'use strict';
  var body = document.getElementById('rows');
  var empty = document.getElementById('empty');
  var card = document.getElementById('soc-card');
  var timerCard = document.getElementById('timer-card');
  var timerLabel = document.getElementById('timer-label');
  var timerClock = document.getElementById('timer-clock');
  function cell(text, cls) { var td = document.createElement('td'); td.textContent = text == null ? '' : text; if (cls) { td.className = cls; } return td; }
  function ago(seconds) {
    if (seconds < 60) { return Math.floor(seconds) + 's ago'; }
    return Math.floor(seconds / 60) + 'm ago';
  }
  function sevClass(sev) {
    if (sev === 'CRITICAL') { return 'neg'; }
    if (sev === 'WARN') { return 'warn'; }
    return 'dim';
  }
  var PHASE_TEXT = { green: 'Recon only - quiet for now', yellow: 'Escalating - probes getting closer',
                    red: 'DETONATED - the real payload is live' };
  function renderTimer(timer) {
    if (!timer) { return; }
    timerCard.className = 'card timer ' + timer.phase;
    timerLabel.textContent = PHASE_TEXT[timer.phase] || timer.phase;
    if (timer.phase === 'red') {
      timerClock.textContent = 'LIVE';
    } else {
      var m = Math.floor(timer.seconds_remaining / 60);
      var s = timer.seconds_remaining % 60;
      timerClock.textContent = m + ':' + (s < 10 ? '0' : '') + s;
    }
  }
  function load() {
    fetch('api/soc', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) { return; }
        renderTimer(d.timer);
        var rows = d.rows || [];
        empty.className = rows.length ? 'card hidden' : 'card';
        card.className = rows.length ? 'card' : 'card hidden';
        while (body.firstChild) { body.removeChild(body.firstChild); }
        var now = Date.now() / 1000;
        rows.forEach(function (r) {
          var tr = document.createElement('tr');
          tr.appendChild(cell(ago(now - r.at), 'dim'));
          tr.appendChild(cell(r.severity, sevClass(r.severity)));
          tr.appendChild(cell(r.persona));
          tr.appendChild(cell(r.origin, 'dim'));
          tr.appendChild(cell(r.challenge));
          body.appendChild(tr);
        });
      })
      .catch(function () {});
  }
  load();
  setInterval(load, 4000);
})();
