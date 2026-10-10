(function () {
  'use strict';
  // The one-page SOC (facilitator) and the student SIEM page: live alerts, the cyber map and the incident summary on one screen
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

  // -- request log -------------------------------------------------------------------------
  // One SIEM-style line per event; click (or Enter/Space) opens the full record as pretty JSON.
  // What a record contains was decided by the server for THIS caller (store.py's _present): a
  // student's lines carry only method, path, status and rule until their own target is breached.
  var log = $('log'), logScroll = $('log-scroll');
  var expanded = {};      // event id -> true while its JSON is open (survives the 3 s refresh)
  var DEFAULT_NOTE = 'Click a line for the full record.';
  function span(cls, text) { var s = document.createElement('span'); s.className = cls; s.textContent = text == null ? '' : text; return s; }
  function clock(r) { return r.at == null ? '--:--:--' : new Date(r.at * 1000).toLocaleTimeString([], { hour12: false }); }
  function size(n) { return n == null ? '' : n < 1024 ? n + ' B' : (n / 1024).toFixed(n < 10240 ? 1 : 0) + ' KB'; }
  function statusClass(n) { return n >= 500 ? 'neg' : n >= 400 ? 'warn' : 'dim'; }
  function toggle(entry, line, pre, id) {
    var open = pre.classList.toggle('hidden') === false;
    line.setAttribute('aria-expanded', open ? 'true' : 'false');
    entry.classList.toggle('open', open);
    if (open) { expanded[id] = true; } else { delete expanded[id]; }
    logScroll.classList.toggle('has-open', Object.keys(expanded).length > 0);
  }
  function entryFor(r, detail) {
    var entry = document.createElement('div'); entry.className = 'entry' + (r.severity === 'BREACH' ? ' breach' : '');
    entry.setAttribute('role', 'listitem');
    var line = document.createElement('div'); line.className = 'line';
    if (admin) { line.appendChild(span('who', r.user)); }
    var tm = span('t dim', clock(r)); if (r.count > 1) { tm.title = 'last seen ' + clock(r); }
    line.appendChild(tm);
    line.appendChild(span('cc', r.origin));
    if (r.method) {
      var target = r.path + (r.query ? '?' + r.query : '');
      line.appendChild(span('m', r.method));
      var p = span('p', target); p.title = target; line.appendChild(p);
      line.appendChild(span('st ' + statusClass(r.status), r.status));
      line.appendChild(span('sz dim', size(r.bytes)));
      var tg = span('tag ' + sevClass(r.severity), r.tag || r.event);
      if (r.count > 1) {
        var bd = span('badge', 'x' + r.count); bd.title = r.count + ' identical requests, first ' + clock({ at: r.first_at });
        tg.appendChild(bd);
      }
      line.appendChild(tg);
    } else {     // an older record, or CTF_SIEM_DETAIL=off: the plain alert
      line.appendChild(span('m', r.severity));
      var q = span('p', (r.persona || '') + (r.path ? '  ' + r.path : '')); q.title = q.textContent; line.appendChild(q);
      line.appendChild(span('st', ''));
      line.appendChild(span('sz', ''));
      line.appendChild(span('tag ' + sevClass(r.severity), r.challenge));
    }
    entry.appendChild(line);
    if (detail) {
      var pre = document.createElement('pre'); pre.className = 'json hidden';
      pre.textContent = JSON.stringify(r, null, 2);
      entry.appendChild(pre);
      line.tabIndex = 0; line.setAttribute('role', 'button'); line.setAttribute('aria-expanded', 'false');
      line.addEventListener('click', function () { toggle(entry, line, pre, r.id); });
      line.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(entry, line, pre, r.id); }
      });
      if (expanded[r.id]) { pre.classList.remove('hidden'); line.setAttribute('aria-expanded', 'true'); entry.classList.add('open'); }
    }
    return entry;
  }
  function loadFeed() {
    return fetch('api/soc', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) { return; }
        renderTimer(d.timer);
        var list = (d.rows || []).slice(0, FEED_MAX);
        var detail = d.siem !== 'off';
        show($('empty'), !list.length);
        show(log, list.length > 0);
        $('feed-count').textContent = list.length ? list.length + ' recent' : '';
        var note = $('feed-note');
        note.textContent = !detail ? '' : d.unlocked ? DEFAULT_NOTE + ' Your target was breached: payloads and sizes are shown.'
          : DEFAULT_NOTE + ' Payload and size detail unlocks once your target is breached.';
        show(note, detail && !admin);
        var keep = {};
        clear(log);
        list.forEach(function (r) { keep[r.id] = true; log.appendChild(entryFor(r, detail)); });
        Object.keys(expanded).forEach(function (id) { if (!keep[id]) { delete expanded[id]; } });
        logScroll.classList.toggle('has-open', Object.keys(expanded).length > 0);
        // Nothing open: trim whole lines until none is half-cut (the projector layout never scrolls).
        if (window.innerWidth > 900 && !Object.keys(expanded).length) {
          while (log.lastChild && logScroll.scrollHeight > logScroll.clientHeight + 1) { log.removeChild(log.lastChild); }
        }
      })
      .catch(function () {});
  }

  // -- map + lists -------------------------------------------------------------------------
  var hasMap = !!$('world-canvas');
  var seenAt = 0, seenBreach = 0, firstMap = true;
  function loadMap() {
    if (!hasMap) { return Promise.resolve(); }
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

  // -- breach banner (student page) --------------------------------------------------------
  // Red while their own target is breached; then a calm "Contained" with the time to patch.
  // It names what happened and where to look, never the fix.
  function renderBanner(targets) {
    var bn = $('banner'); if (!bn) { return; }
    var red = null, fixed = null;
    targets.forEach(function (t) { if (t.status === 'red') { red = red || t; } else if (t.fixed_at != null) { fixed = fixed || t; } });
    var main = $('banner-main'), sub = $('banner-sub');
    if (red) {
      bn.className = 'banner breached';
      main.textContent = 'BREACHED - customer data left your ' + red.challenge + ' at ' + clock({ at: red.breached_at });
      sub.textContent = 'Find the request in the log below that caused it.';
    } else if (fixed) {
      bn.className = 'banner contained';
      main.textContent = 'Contained - ' + fixed.challenge + ' patched in ' + duration(fixed.mttp);
      sub.textContent = 'Breached ' + clock({ at: fixed.breached_at }) + ', fixed ' + clock({ at: fixed.fixed_at }) + '.';
    } else {
      bn.className = 'banner watch';
      main.textContent = 'Monitoring';
      sub.textContent = '';
    }
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
        renderBanner(targets);
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
  if (hasMap) { window.DojoMap.init($('world-canvas'), $('inset-canvas')); }
  refresh();
  setInterval(loadFeed, 3000);
  setInterval(loadMap, 3000);
  setInterval(loadIncident, admin ? 6000 : 3000);
})();
