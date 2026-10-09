(function () {
  'use strict';
  // The one-page SOC: live alerts, the cyber map and the incident summary on one screen
  // (plan 8.2, 8.3, 8.9). Students see their own feed and incident; the facilitator page
  // (soc-admin.html, data-mode="admin") sees the whole room and picks a student for the incident
  // panel. Every string that came from a student goes in through textContent.
  var admin = document.body.getAttribute('data-mode') === 'admin';
  var FEED_MAX = 40;
  var pickedUser = '';
  var timerCard = document.getElementById('timer-card');
  var timerLabel = document.getElementById('timer-label');
  var timerClock = document.getElementById('timer-clock');
  var PHASE_TEXT = admin
    ? { waiting: 'Not started - walk through the briefing, then press Start', green: 'Recon only - quiet for now',
        yellow: 'Escalating - probes getting closer', red: 'DETONATED - the real payload is live' }
    : { waiting: 'Not started yet', green: 'Recon only - quiet for now',
        yellow: 'Escalating - probes getting closer', red: 'DETONATED - the real payload is live' };

  function $(id) { return document.getElementById(id); }
  function cell(text, cls) { var td = document.createElement('td'); td.textContent = text == null ? '' : text; if (cls) { td.className = cls; } td.title = text == null ? '' : String(text); return td; }
  function clear(el) { while (el.firstChild) { el.removeChild(el.firstChild); } }
  function ago(seconds) { return seconds < 60 ? Math.floor(seconds) + 's ago' : Math.floor(seconds / 60) + 'm ago'; }
  function sevClass(sev) { return sev === 'CRITICAL' || sev === 'BREACH' ? 'neg' : sev === 'WARN' ? 'warn' : 'dim'; }
  function when(ts) { return ts == null ? '-' : new Date(ts * 1000).toLocaleTimeString(); }
  function duration(seconds) {
    if (seconds == null) { return '-'; }
    return Math.floor(seconds / 60) + 'm ' + Math.round(seconds % 60) + 's';
  }
  // Drop trailing rows until the panel shows no half-cut row (the projector layout never scrolls).
  function fit(box, tbody) {
    if (window.innerWidth <= 900) { return; }
    while (tbody.lastChild && box.scrollHeight > box.clientHeight + 1) { tbody.removeChild(tbody.lastChild); }
  }
  function show(el, on) { el.classList.toggle('hidden', !on); }

  function renderTimer(timer) {
    if (!timer) { return; }
    timerCard.className = 'card timer ' + timer.phase;
    timerLabel.textContent = PHASE_TEXT[timer.phase] || timer.phase;
    if (timer.phase === 'waiting') { timerClock.textContent = '--:--'; }
    else if (timer.phase === 'red') { timerClock.textContent = 'LIVE'; }
    else {
      var m = Math.floor(timer.seconds_remaining / 60), s = timer.seconds_remaining % 60;
      timerClock.textContent = m + ':' + (s < 10 ? '0' : '') + s;
    }
    if (api.onTimer) { api.onTimer(timer); }
  }

  // -- alert feed --------------------------------------------------------------------------
  var head = $('feed-head'), rows = $('rows');
  (admin ? ['When', 'Student', 'Severity', 'Persona', 'Origin', 'Target'] : ['When', 'Severity', 'Persona', 'Origin', 'Target', 'Path'])
    .forEach(function (h) { var th = document.createElement('th'); th.textContent = h; head.appendChild(th); });
  function loadFeed() {
    return fetch('api/soc', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) { return; }
        renderTimer(d.timer);
        var list = (d.rows || []).slice(0, FEED_MAX);
        show($('empty'), !list.length);
        show($('soc-card'), list.length > 0);
        $('feed-count').textContent = list.length ? list.length + ' recent' : '';
        clear(rows);
        var now = Date.now() / 1000;
        list.forEach(function (r) {
          var tr = document.createElement('tr');
          if (r.severity === 'BREACH') { tr.className = 'breach'; }
          tr.appendChild(cell(ago(now - r.at), 'dim'));
          if (admin) { tr.appendChild(cell(r.user)); }
          tr.appendChild(cell(r.severity, sevClass(r.severity)));
          tr.appendChild(cell(r.persona));
          tr.appendChild(cell(r.origin, 'dim'));
          tr.appendChild(cell(r.challenge));
          if (!admin) { tr.appendChild(cell(r.path || '-', 'dim')); }
          rows.appendChild(tr);
        });
        fit(rows.parentNode.parentNode, rows);
      })
      .catch(function () {});
  }

  // -- map + lists -------------------------------------------------------------------------
  var seenAt = 0, seenBreach = 0, firstMap = true;
  function loadMap() {
    return fetch('api/map', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) { return; }
        renderTimer(d.timer);
        var status = {};
        (d.top || []).forEach(function (r) { status[r.user] = 'siege'; });
        var breaches = d.breaches || [];
        breaches.forEach(function (b) { status[b.user] = 'breach'; });
        window.DojoMap.setStudents(d.students || []);
        window.DojoMap.setStatus(status);
        var arcs = d.arcs || [];
        arcs.forEach(function (row) {
          if (row.at > seenAt && !firstMap) { window.DojoMap.addArc(row.origin, row.user, row.severity); }
        });
        if (arcs.length) { seenAt = Math.max.apply(null, arcs.map(function (r) { return r.at; })); }
        breaches.forEach(function (b) { if (b.recent && b.breached_at > seenBreach && !firstMap) { window.DojoMap.ripple(b.user, '#ef4444'); } });
        if (breaches.length) { seenBreach = Math.max.apply(null, breaches.map(function (b) { return b.breached_at; })); }
        firstMap = false;
        if (d.window) { $('top-window').textContent = 'last ' + (d.window >= 60 ? Math.round(d.window / 60) + ' min' : Math.round(d.window) + ' s'); }
        var top = (d.top || []).slice(0, 8);
        show($('top-empty'), !top.length); show($('top-card'), top.length > 0);
        clear($('top-rows'));
        top.forEach(function (r) {
          var tr = document.createElement('tr');
          tr.appendChild(cell(r.user)); tr.appendChild(cell(r.challenge)); tr.appendChild(cell(r.hits));
          $('top-rows').appendChild(tr);
        });
        fit($('top-card').parentNode, $('top-rows'));
        show($('breach-empty'), !breaches.length); show($('breach-card'), breaches.length > 0);
        clear($('breach-rows'));
        var now = Date.now() / 1000;
        breaches.slice(0, 8).forEach(function (b) {
          var tr = document.createElement('tr');
          tr.appendChild(cell(b.user)); tr.appendChild(cell(b.challenge)); tr.appendChild(cell(ago(now - b.breached_at), 'dim'));
          $('breach-rows').appendChild(tr);
        });
        fit($('breach-card').parentNode, $('breach-rows'));
      })
      .catch(function () {});
  }

  // -- incident summary --------------------------------------------------------------------
  function loadIncident() {
    if (admin && !pickedUser) {
      $('inc-empty').textContent = 'Pick a student in the facilitator bar to see their incident summary.';
      show($('inc-empty'), true); show($('targets-card'), false); show($('timeline-card'), false);
      $('inc-who').textContent = '';
      return Promise.resolve();
    }
    var q = admin ? '?user=' + encodeURIComponent(pickedUser) : '';
    return fetch('api/incident' + q, { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) { return; }
        var targets = d.targets || [], timeline = (d.timeline || []).slice(0, 12);
        $('inc-who').textContent = admin ? d.user || '' : '';
        $('inc-empty').textContent = 'No activity recorded yet.';
        show($('inc-empty'), !(targets.length || timeline.length));
        show($('targets-card'), targets.length > 0);
        show($('timeline-card'), timeline.length > 0);
        clear($('target-rows'));
        targets.forEach(function (t) {
          var tr = document.createElement('tr');
          tr.appendChild(cell(t.challenge));
          tr.appendChild(cell(t.status, t.status === 'red' ? 'neg' : 'warn'));
          tr.appendChild(cell(when(t.breached_at), 'dim'));
          tr.appendChild(cell(when(t.fixed_at), 'dim'));
          tr.appendChild(cell(duration(t.mttp)));
          tr.appendChild(cell(t.retries));
          $('target-rows').appendChild(tr);
        });
        clear($('timeline-rows'));
        timeline.forEach(function (r) {
          var tr = document.createElement('tr');
          if (r.severity === 'BREACH') { tr.className = 'breach'; }
          tr.appendChild(cell(when(r.at), 'dim'));
          tr.appendChild(cell(r.severity, sevClass(r.severity)));
          tr.appendChild(cell(r.persona));
          tr.appendChild(cell(r.origin, 'dim'));
          tr.appendChild(cell(r.challenge));
          $('timeline-rows').appendChild(tr);
        });
        fit($('timeline-card').parentNode, $('timeline-rows'));
      })
      .catch(function () {});
  }

  function refresh() { return Promise.all([loadFeed(), loadMap(), loadIncident()]); }
  var api = {
    onTimer: null,
    refresh: refresh,
    setUser: function (u) { pickedUser = u || ''; loadIncident(); }
  };
  window.DojoSOC = api;
  // Legacy links: /incident?user=NAME redirects here with the query intact.
  var qs = /[?&]user=([^&]+)/.exec(location.search);
  if (admin && qs) { try { pickedUser = decodeURIComponent(qs[1]); } catch (e) { pickedUser = ''; } }
  window.DojoMap.init($('world-canvas'), $('inset-canvas'));
  refresh();
  setInterval(loadFeed, 3000);
  setInterval(loadMap, 3000);
  setInterval(loadIncident, 6000);
})();
