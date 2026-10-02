// The badge: one design per workshop (hue from its name), two tiers. Drawn on a canvas, no images.
(function () {
  'use strict';
  function hue(text) { var h = 0; for (var i = 0; i < text.length; i++) { h = (h * 31 + text.charCodeAt(i)) % 360; } return h; }
  function star(g, cx, cy, r) {
    g.beginPath();
    for (var i = 0; i < 10; i++) {
      var a = -Math.PI / 2 + i * Math.PI / 5, rad = i % 2 ? r * 0.45 : r;
      g[i ? 'lineTo' : 'moveTo'](cx + Math.cos(a) * rad, cy + Math.sin(a) * rad);
    }
    g.closePath(); g.fill();
  }
  // tier: 'complete' or 'capstone' (adds three stars). Returns the canvas.
  window.dojoBadge = function (canvas, workshop, tier) {
    var S = 480, h = hue(workshop), g = canvas.getContext('2d');
    canvas.width = canvas.height = S;
    g.clearRect(0, 0, S, S);
    var ring = tier === 'capstone' ? '#d4a017' : '#94a3b8';
    g.beginPath(); g.arc(S / 2, S / 2, S / 2 - 8, 0, Math.PI * 2); g.fillStyle = ring; g.fill();
    g.beginPath(); g.arc(S / 2, S / 2, S / 2 - 30, 0, Math.PI * 2); g.fillStyle = 'hsl(' + h + ',55%,32%)'; g.fill();
    g.beginPath(); g.arc(S / 2, S / 2, S / 2 - 46, 0, Math.PI * 2);
    g.strokeStyle = 'hsla(0,0%,100%,0.5)'; g.lineWidth = 3; g.stroke();
    g.fillStyle = '#fff'; g.textAlign = 'center';
    g.font = 'bold 150px sans-serif'; g.fillText(workshop.replace(/[^A-Za-z0-9]/g, '').slice(0, 1).toUpperCase() || 'D', S / 2, S / 2 + 30);
    g.font = 'bold 30px sans-serif';
    var words = workshop.split(' '), line = '', y = S / 2 + 80;
    words.forEach(function (w) {
      if ((line + ' ' + w).length > 16 && line) { g.fillText(line, S / 2, y); y += 34; line = w; } else { line = (line ? line + ' ' : '') + w; }
    });
    g.fillText(line, S / 2, y);
    g.font = '22px sans-serif'; g.fillStyle = 'hsla(0,0%,100%,0.8)';
    g.fillText(tier === 'capstone' ? 'CAPSTONE' : 'COMPLETE', S / 2, S - 70);
    if (tier === 'capstone') { g.fillStyle = '#facc15'; [-60, 0, 60].forEach(function (dx) { star(g, S / 2 + dx, 95, 24); }); }
    return canvas;
  };
})();
