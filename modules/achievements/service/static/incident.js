(function () {
  'use strict';
  // Served at both /achievements/incident (a student's own, no query needed) and
  // /achievements-admin/incident?user=NAME (the facilitator's view of any student) - the fetch
  // below just forwards whatever query string got it here (plan §8.9).
  var empty = document.getElementById('empty');
  var targetsCard = document.getElementById('targets-card');
  var targetRows = document.getElementById('target-rows');
  var timelineCard = document.getElementById('timeline-card');
  var timelineRows = document.getElementById('timeline-rows');

  function cell(text, cls) { var td = document.createElement('td'); td.textContent = text == null ? '' : text; if (cls) { td.className = cls; } return td; }
  function when(ts) { return ts == null ? '-' : new Date(ts * 1000).toLocaleTimeString(); }
  function duration(seconds) {
    if (seconds == null) { return '-'; }
    var m = Math.floor(seconds / 60), s = Math.round(seconds % 60);
    return m + 'm ' + s + 's';
  }
  function sevClass(sev) {
    if (sev === 'CRITICAL') { return 'neg'; }
    if (sev === 'WARN') { return 'warn'; }
    return 'dim';
  }

  function load() {
    fetch('api/incident' + location.search, { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) { return; }
        var targets = d.targets || [], timeline = d.timeline || [];
        empty.className = (targets.length || timeline.length) ? 'card incident-card hidden' : 'card incident-card';
        targetsCard.className = targets.length ? 'card incident-card' : 'card incident-card hidden';
        timelineCard.className = timeline.length ? 'card' : 'card hidden';
        while (targetRows.firstChild) { targetRows.removeChild(targetRows.firstChild); }
        targets.forEach(function (t) {
          var tr = document.createElement('tr');
          tr.appendChild(cell(t.challenge));
          tr.appendChild(cell(t.status, t.status === 'red' ? 'neg' : 'warn'));
          tr.appendChild(cell(when(t.breached_at), 'dim'));
          tr.appendChild(cell(when(t.fixed_at), 'dim'));
          tr.appendChild(cell(duration(t.mttp)));
          tr.appendChild(cell(t.retries));
          targetRows.appendChild(tr);
        });
        while (timelineRows.firstChild) { timelineRows.removeChild(timelineRows.firstChild); }
        timeline.forEach(function (r) {
          var tr = document.createElement('tr');
          tr.appendChild(cell(when(r.at), 'dim'));
          tr.appendChild(cell(r.severity, sevClass(r.severity)));
          tr.appendChild(cell(r.persona));
          tr.appendChild(cell(r.origin, 'dim'));
          tr.appendChild(cell(r.challenge));
          timelineRows.appendChild(tr);
        });
      })
      .catch(function () {});
  }
  load();
})();
