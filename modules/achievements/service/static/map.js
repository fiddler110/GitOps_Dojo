(function () {
  'use strict';
  // The cyber map (plan 8.3): a world view plus a Canada inset, both drawn on <canvas> from the
  // bundled Natural Earth outline in mapdata.js (no network, no CDN). Arcs run from the swarm's
  // flavor origin cities to the student's coarse region; nothing here knows about IP addresses,
  // only the city-level points achievements hands over. Text on the canvas is fillText, so a
  // student-chosen string can never become markup.
  var D = window.DOJO_MAP || { world: [], land: [], lakes: [], borders: [] };
  var OCEAN = '#0b1220', LAND = '#26385a', COAST = '#4d658f', GRID = 'rgba(148,163,184,0.08)';
  var SEV_COLOR = { CRITICAL: '#ef4444', WARN: '#f59e0b', INFO: '#38bdf8' };
  // Attacker origins are synthetic flavor (personas.py ORIGINS), never a real IP, so they are drawn as
  // unlabelled glints at a rough country-centroid position. A string not listed here lands on a stable
  // pseudo-position (hash of the string) over the populated land. [lat, lon].
  var ORIGINS = {   // ISO country code -> [lat, lon] near the country's centroid
    CN: [35, 103], RU: [58, 60], UA: [49, 32], US: [38, -97], NG: [9, 8], ZA: [-29, 25], BR: [-10, -52],
    AR: [-36, -64], AU: [-25, 134], AE: [24, 54], IR: [32, 53], TR: [39, 35], IN: [22, 79], VN: [15, 106]
  };

  var SPOTS = [[48, 10], [60, 100], [25, 100], [-5, 20], [-15, -60], [40, -100], [30, 45], [-25, 135], [15, 100], [50, 70]];
  function originPos(key) {
    key = String(key == null ? '' : key);
    if (Object.prototype.hasOwnProperty.call(ORIGINS, key)) { return ORIGINS[key]; }
    var h = 5381, i;
    for (i = 0; i < key.length; i++) { h = ((h * 33) ^ key.charCodeAt(i)) >>> 0; }
    var base = SPOTS[h % SPOTS.length];
    return [base[0] + ((h >>> 8) % 11) - 5, base[1] + ((h >>> 16) % 15) - 7];
  }
  var WORLD = { lonC: 0, latC: 5, lonSpan: 360, latSpan: 150, k: 1, contain: true };
  var INSET = { lonC: -94, latC: 49.5, lonSpan: 66, latSpan: 24, k: 0.66, contain: false };

  function View(canvas, spec) {
    this.canvas = canvas; this.spec = spec; this.ctx = canvas.getContext('2d');
    this.layer = document.createElement('canvas');
    this.w = 0; this.h = 0; this.s = 1; this.latC = spec.latC;
  }
  View.prototype.resize = function () {
    var dpr = window.devicePixelRatio || 1;
    var w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    if (!w || !h) { return false; }
    this.w = w; this.h = h; this.dpr = dpr;
    this.canvas.width = Math.round(w * dpr); this.canvas.height = Math.round(h * dpr);
    this.layer.width = this.canvas.width; this.layer.height = this.canvas.height;
    var sp = this.spec;
    var sx = w / (sp.lonSpan * sp.k), sy = h / sp.latSpan;
    this.s = sp.contain ? Math.min(sx, sy) : sx;       // the inset fits the width; the world fits both
    this.latC = sp.latC;
    if (!sp.contain) { this.latC = Math.max(sp.latC, 33 + h / (2 * this.s)); }   // the outline is trustworthy from about 30N
    this.paintLayer();
    return true;
  };
  View.prototype.x = function (lon) { return this.w / 2 + (lon - this.spec.lonC) * this.s * this.spec.k; };
  View.prototype.y = function (lat) { return this.h / 2 - (lat - this.latC) * this.s; };
  View.prototype.path = function (ctx, rings, close) {
    var self = this;
    ctx.beginPath();
    rings.forEach(function (r) {
      for (var i = 0; i < r.length; i += 2) {
        var px = self.x(r[i] / 100), py = self.y(r[i + 1] / 100);
        if (i === 0) { ctx.moveTo(px, py); } else { ctx.lineTo(px, py); }
      }
      if (close) { ctx.closePath(); }
    });
  };
  View.prototype.paintLayer = function () {
    var c = this.layer.getContext('2d');
    c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    c.fillStyle = OCEAN; c.fillRect(0, 0, this.w, this.h);
    // graticule
    var step = this.spec.contain ? 20 : 5, lon, lat;
    c.strokeStyle = GRID; c.lineWidth = 1; c.beginPath();
    for (lon = -180; lon <= 180; lon += step) { c.moveTo(this.x(lon), 0); c.lineTo(this.x(lon), this.h); }
    for (lat = -80; lat <= 80; lat += step) { c.moveTo(0, this.y(lat)); c.lineTo(this.w, this.y(lat)); }
    c.stroke();
    c.lineJoin = 'round';
    if (this.spec.contain) {
      this.path(c, D.world, true);
      c.fillStyle = LAND; c.fill(); c.strokeStyle = COAST; c.lineWidth = 0.8; c.stroke();
    } else {
      this.path(c, D.land, true);
      c.fillStyle = LAND; c.fill(); c.strokeStyle = COAST; c.lineWidth = 1; c.stroke();
      this.path(c, D.lakes, true);
      c.fillStyle = OCEAN; c.fill(); c.strokeStyle = COAST; c.stroke();
      this.path(c, D.borders, false);
      c.setLineDash([4, 3]); c.strokeStyle = '#51668a'; c.lineWidth = 1; c.stroke(); c.setLineDash([]);
    }
  };

  var world, inset, students = [], status = {}, arcs = [], ripples = [], byLabel = {};
  var labelCache = null;

  function init(worldCanvas, insetCanvas) {
    world = new View(worldCanvas, WORLD);
    inset = new View(insetCanvas, INSET);
    function relayout() { world.resize(); inset.resize(); }
    window.addEventListener('resize', relayout);
    if (window.ResizeObserver) {
      var ro = new ResizeObserver(relayout);
      ro.observe(worldCanvas); ro.observe(insetCanvas);
    }
    relayout();
    requestAnimationFrame(frame);
  }

  function setStudents(list) {
    students = list || [];
    byLabel = {};
    students.forEach(function (s) { byLabel[s.user] = s; });
    labelCache = null;
  }
  function setStatus(map) { status = map || {}; }
  function addArc(originKey, user, severity) {
    var from = originPos(originKey), to = byLabel[user];
    if (!to) { return; }
    arcs.push({ from: from, to: to, color: SEV_COLOR[severity] || '#94a3b8', start: performance.now(), dur: 1500 });
  }
  function ripple(user, color) {
    var to = byLabel[user];
    if (to) { ripples.push({ to: to, color: color, start: performance.now() }); }
  }

  function dotColor(s) {
    var st = status[s.user];
    return st === 'breach' ? '#ef4444' : st === 'siege' ? '#f59e0b' : '#38bdf8';
  }
  function bez(a, b, bulge, t) {
    var mx = (a[0] + b[0]) / 2, my = Math.min(a[1], b[1]) - bulge;
    return [(1 - t) * (1 - t) * a[0] + 2 * (1 - t) * t * mx + t * t * b[0],
            (1 - t) * (1 - t) * a[1] + 2 * (1 - t) * t * my + t * t * b[1]];
  }
  function groups(view) {
    // Students sharing a place label share one caption (centroid, with a count).
    var g = {};
    students.forEach(function (s) {
      var e = g[s.place] || (g[s.place] = { place: s.place, n: 0, lat: 0, lon: 0 });
      e.n += 1; e.lat += s.lat; e.lon += s.lon;
    });
    return Object.keys(g).map(function (k) { var e = g[k]; return { place: e.place, n: e.n, lat: e.lat / e.n, lon: e.lon / e.n }; })
      .sort(function (a, b) { return b.n - a.n; });
  }

  function drawWorld(now) {
    var v = world, c = v.ctx;
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.drawImage(v.layer, 0, 0);
    c.setTransform(v.dpr, 0, 0, v.dpr, 0, 0);
    // the inset's footprint
    c.strokeStyle = 'rgba(56,189,248,0.55)'; c.lineWidth = 1; c.setLineDash([3, 3]);
    c.strokeRect(v.x(-127), v.y(56), v.x(-61) - v.x(-127), v.y(41) - v.y(56));
    c.setLineDash([]);
    Object.keys(ORIGINS).forEach(function (k, i) {
      var o = ORIGINS[k], px = v.x(o[1]), py = v.y(o[0]);
      var t = ((now / 1800) + i * 0.37) % 1;
      c.beginPath(); c.arc(px, py, 1.5 + t * 6, 0, Math.PI * 2);
      c.strokeStyle = '#94a3b8'; c.globalAlpha = 0.5 * (1 - t); c.lineWidth = 1; c.stroke(); c.globalAlpha = 1;
      c.beginPath(); c.arc(px, py, 2, 0, Math.PI * 2); c.fillStyle = '#cbd5e1'; c.fill();
    });
    arcs = arcs.filter(function (a) {
      var t = (now - a.start) / a.dur;
      if (t >= 1) { ripples.push({ to: a.to, color: a.color, start: now }); return false; }
      return true;
    });
    arcs.forEach(function (a) {
      var t = (now - a.start) / a.dur, p0 = [v.x(a.from[1]), v.y(a.from[0])], p1 = [v.x(a.to.lon), v.y(a.to.lat)];
      var bulge = Math.abs(p1[0] - p0[0]) * 0.18 + 20, head = bez(p0, p1, bulge, t);
      c.beginPath(); c.moveTo(p0[0], p0[1]);
      for (var i = 1; i <= 16; i++) { var q = bez(p0, p1, bulge, t * i / 16); c.lineTo(q[0], q[1]); }
      c.strokeStyle = a.color; c.globalAlpha = 0.85 * (1 - t * 0.6); c.lineWidth = 1.5; c.stroke(); c.globalAlpha = 1;
      c.beginPath(); c.arc(head[0], head[1], 2.8, 0, Math.PI * 2); c.fillStyle = a.color; c.fill();
    });
    students.forEach(function (s) {
      c.beginPath(); c.arc(v.x(s.lon), v.y(s.lat), 2.6, 0, Math.PI * 2); c.fillStyle = dotColor(s); c.fill();
    });
    drawRipples(v, now, 14);
  }

  function drawInset(now) {
    var v = inset, c = v.ctx;
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.drawImage(v.layer, 0, 0);
    c.setTransform(v.dpr, 0, 0, v.dpr, 0, 0);
    students.forEach(function (s) {
      var px = v.x(s.lon), py = v.y(s.lat);
      c.beginPath(); c.arc(px, py, 4, 0, Math.PI * 2); c.fillStyle = dotColor(s); c.globalAlpha = 0.9; c.fill(); c.globalAlpha = 1;
      c.strokeStyle = '#0b1220'; c.lineWidth = 1; c.stroke();
    });
    // captions: one per place, skipping any that would sit on top of a bigger one
    c.font = '600 12px sans-serif';
    var placed = [];
    groups(v).forEach(function (g) {
      var text = g.place + ' (' + g.n + ')', w = c.measureText(text).width;
      var px = v.x(g.lon) - w / 2, py = v.y(g.lat) - 12;
      px = Math.max(4, Math.min(v.w - w - 4, px));
      var clash = placed.some(function (r) { return px < r[0] + r[2] + 4 && px + w + 4 > r[0] && Math.abs(py - r[1]) < 14; });
      if (clash) { return; }
      placed.push([px, py, w]);
      c.fillStyle = 'rgba(11,18,32,0.75)'; c.fillRect(px - 3, py - 11, w + 6, 15);
      c.fillStyle = '#e2e8f0'; c.fillText(text, px, py);
    });
    drawRipples(v, now, 26);
  }

  function drawRipples(v, now, size) {
    var c = v.ctx;
    ripples.forEach(function (r) {
      var t = (now - r.start) / 900;
      if (t >= 1) { return; }
      c.beginPath(); c.arc(v.x(r.to.lon), v.y(r.to.lat), 3 + t * size, 0, Math.PI * 2);
      c.strokeStyle = r.color; c.globalAlpha = 1 - t; c.lineWidth = 2; c.stroke(); c.globalAlpha = 1;
    });
  }

  function frame(now) {
    if (world.w) { drawWorld(now); }
    if (inset.w) { drawInset(now); }
    ripples = ripples.filter(function (r) { return now - r.start < 900; });
    requestAnimationFrame(frame);
  }

  window.DojoMap = { init: init, setStudents: setStudents, setStatus: setStatus, addArc: addArc, ripple: ripple };
})();
