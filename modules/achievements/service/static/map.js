(function () {
  'use strict';
  // A classic "attack map" cliche (arcs sweeping in from flavor origin points toward a central
  // SOC hub), built entirely from the same `soc` events the admin tab's feed already shows -
  // this widget invents nothing, it only renders what the swarm tagged (plan §8.3).
  var canvas = document.getElementById('map-canvas');
  var ctx = canvas.getContext('2d');
  var W = canvas.width, H = canvas.height;
  var HUB = [W * 0.72, H * 0.55];
  // Rough relative placement only - flavor, never real geography (see the dim line on the page).
  var ORIGINS = {
    CN: [W * 0.86, H * 0.28], RU: [W * 0.62, H * 0.12], 'Eastern Europe': [W * 0.52, H * 0.22],
    US: [W * 0.14, H * 0.30], Other: [W * 0.30, H * 0.62]
  };
  var timerCard = document.getElementById('timer-card');
  var timerLabel = document.getElementById('timer-label');
  var timerClock = document.getElementById('timer-clock');
  var PHASE_TEXT = { waiting: 'Not started yet', green: 'Recon only - quiet for now',
                    yellow: 'Escalating - probes getting closer', red: 'DETONATED - the real payload is live' };
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
  }

  var SEV_COLOR = { CRITICAL: '#dc2626', WARN: '#b45309', INFO: '#2563eb' };
  var particles = [];   // {x0,y0,x1,y1,color,start,dur}
  var flashes = [];     // {x,y,start}
  var seenAt = 0;        // newest arc timestamp already turned into a particle

  function addArc(row) {
    var from = ORIGINS[row.origin] || ORIGINS.Other;
    particles.push({ x0: from[0], y0: from[1], x1: HUB[0], y1: HUB[1],
                    color: SEV_COLOR[row.severity] || '#999', start: performance.now(), dur: 1400 });
  }
  function addFlash() { flashes.push({ start: performance.now() }); }

  function draw() {
    var now = performance.now();
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#0b1220';
    ctx.fillRect(0, 0, W, H);
    // origin dots + labels
    ctx.font = '11px sans-serif';
    Object.keys(ORIGINS).forEach(function (name) {
      var p = ORIGINS[name];
      ctx.beginPath();
      ctx.arc(p[0], p[1], 4, 0, Math.PI * 2);
      ctx.fillStyle = '#64748b';
      ctx.fill();
      ctx.fillStyle = '#9fb0c3';
      ctx.fillText(name, p[0] + 7, p[1] + 4);
    });
    // hub
    ctx.beginPath();
    ctx.arc(HUB[0], HUB[1], 7, 0, Math.PI * 2);
    ctx.fillStyle = '#e5e7eb';
    ctx.fill();
    ctx.fillStyle = '#e5e7eb';
    ctx.fillText('student targets', HUB[0] - 40, HUB[1] + 22);
    // arcs
    particles = particles.filter(function (p) { return now - p.start < p.dur; });
    particles.forEach(function (p) {
      var t = (now - p.start) / p.dur;
      var mx = (p.x0 + p.x1) / 2, my = Math.min(p.y0, p.y1) - 40;
      var bx = (1 - t) * (1 - t) * p.x0 + 2 * (1 - t) * t * mx + t * t * p.x1;
      var by = (1 - t) * (1 - t) * p.y0 + 2 * (1 - t) * t * my + t * t * p.y1;
      ctx.beginPath();
      ctx.moveTo(p.x0, p.y0);
      ctx.quadraticCurveTo(mx, my, bx, by);
      ctx.strokeStyle = p.color;
      ctx.globalAlpha = 1 - t;
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.arc(bx, by, 2.5, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.fill();
    });
    // breach flashes on the hub
    flashes = flashes.filter(function (f) { return now - f.start < 900; });
    flashes.forEach(function (f) {
      var t = (now - f.start) / 900;
      ctx.beginPath();
      ctx.arc(HUB[0], HUB[1], 7 + t * 30, 0, Math.PI * 2);
      ctx.strokeStyle = '#dc2626';
      ctx.globalAlpha = 1 - t;
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.globalAlpha = 1;
    });
    requestAnimationFrame(draw);
  }

  function cell(text, cls) { var td = document.createElement('td'); td.textContent = text == null ? '' : text; if (cls) { td.className = cls; } return td; }
  function ago(seconds) { return seconds < 60 ? Math.floor(seconds) + 's ago' : Math.floor(seconds / 60) + 'm ago'; }

  var topEmpty = document.getElementById('top-empty'), topCard = document.getElementById('top-card'), topRows = document.getElementById('top-rows');
  var breachEmpty = document.getElementById('breach-empty'), breachCard = document.getElementById('breach-card'), breachRows = document.getElementById('breach-rows');
  var seenBreach = 0;

  function load() {
    fetch('api/map', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) { return; }
        renderTimer(d.timer);
        (d.arcs || []).forEach(function (row) {
          if (row.at > seenAt) { addArc(row); }
        });
        if (d.arcs && d.arcs.length) { seenAt = Math.max.apply(null, d.arcs.map(function (r) { return r.at; })); }
        var top = d.top || [];
        topEmpty.className = top.length ? 'dim hidden' : 'dim';
        topCard.className = top.length ? '' : 'hidden';
        while (topRows.firstChild) { topRows.removeChild(topRows.firstChild); }
        top.forEach(function (r) {
          var tr = document.createElement('tr');
          tr.appendChild(cell(r.user));
          tr.appendChild(cell(r.challenge));
          tr.appendChild(cell(r.hits));
          topRows.appendChild(tr);
        });
        var breaches = d.breaches || [];
        breaches.forEach(function (b) { if (b.breached_at > seenBreach) { addFlash(); } });
        if (breaches.length) { seenBreach = Math.max.apply(null, breaches.map(function (b) { return b.breached_at; })); }
        breachEmpty.className = breaches.length ? 'dim hidden' : 'dim';
        breachCard.className = breaches.length ? '' : 'hidden';
        while (breachRows.firstChild) { breachRows.removeChild(breachRows.firstChild); }
        var now = Date.now() / 1000;
        breaches.forEach(function (b) {
          var tr = document.createElement('tr');
          tr.appendChild(cell(b.user));
          tr.appendChild(cell(b.challenge));
          tr.appendChild(cell(ago(now - b.breached_at), 'dim'));
          breachRows.appendChild(tr);
        });
      })
      .catch(function () {});
  }
  load();
  setInterval(load, 3000);
  requestAnimationFrame(draw);
})();
