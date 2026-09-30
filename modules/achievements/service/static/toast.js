// Achievement toasts. Include with <script src="/achievements/toast.js" data-surface="portal">.
// Polls for this student's toasts (each is shown once, on the first page to ask) and shows
// them one after another. Student-visible text goes in with textContent only, and styling is
// applied through the CSSOM, so it works under a page's strict CSP with no stylesheet.
(function () {
  'use strict';
  var me = document.currentScript;
  var surface = (me && me.getAttribute('data-surface')) || 'page';
  var base = me ? me.src.replace(/toast\.js.*$/, '') : '/achievements/';
  var box = null, queue = [], showing = false;

  function put(el, css) { for (var k in css) { el.style[k] = css[k]; } return el; }
  function container() {
    if (box) { return box; }
    box = put(document.createElement('div'), { position: 'fixed', right: '1rem', bottom: '1rem', zIndex: 2147483647,
      display: 'flex', flexDirection: 'column', gap: '0.5rem', maxWidth: 'min(22rem, 90vw)', pointerEvents: 'none' });
    box.setAttribute('role', 'status');
    box.setAttribute('aria-live', 'polite');
    document.body.appendChild(box);
    return box;
  }
  function pointsText(t) {
    if (t.kind === 'summary') { return t.points ? '+' + t.points : ''; }
    if (t.points > 0) { return '+' + t.points; }
    if (t.points < 0) { return String(t.points); }
    return '';
  }
  function render(t) {
    var funny = t.kind === 'funny';
    var card = put(document.createElement('div'), { background: funny ? '#7c3aed' : '#1d4ed8', color: '#fff',
      borderRadius: '0.7rem', padding: '0.7rem 0.9rem', boxShadow: '0 6px 20px rgba(0,0,0,0.35)',
      font: '14px/1.35 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', opacity: '0',
      transform: 'translateY(0.5rem)', transition: 'opacity 0.25s, transform 0.25s' });
    var head = put(document.createElement('div'), { fontWeight: '700', display: 'flex', gap: '0.6rem', justifyContent: 'space-between' });
    var title = document.createElement('span');
    title.textContent = (funny ? '😜 ' : '🏆 ') + (t.title || '');
    var pts = document.createElement('span');
    pts.textContent = pointsText(t);
    head.appendChild(title); head.appendChild(pts);
    card.appendChild(head);
    if (t.joke) {
      var joke = put(document.createElement('div'), { marginTop: '0.25rem', opacity: '0.92' });
      joke.textContent = t.joke;
      card.appendChild(joke);
    }
    return card;
  }
  function next() {
    if (!queue.length) { showing = false; return; }
    showing = true;
    var t = queue.shift(), card = render(t);
    container().appendChild(card);
    requestAnimationFrame(function () { card.style.opacity = '1'; card.style.transform = 'none'; });
    setTimeout(function () {
      card.style.opacity = '0';
      setTimeout(function () { if (card.parentNode) { card.parentNode.removeChild(card); } next(); }, 300);
    }, t.ms || 4000);
  }
  function poll() {
    fetch(base + 'api/toasts?surface=' + encodeURIComponent(surface), { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : { toasts: [] }; })
      .then(function (d) { (d.toasts || []).forEach(function (t) { queue.push(t); }); if (!showing) { next(); } })
      .catch(function () {});
  }
  // The landing page frames the widget: grow the frame to fit what it reports.
  window.addEventListener('message', function (e) {
    if (e.origin !== window.location.origin || !e.data || e.data.type !== 'dojo-widget-height') { return; }
    var h = parseInt(e.data.height, 10), frames = document.getElementsByTagName('iframe');
    if (!(h > 0)) { return; }
    for (var i = 0; i < frames.length; i++) {
      if (frames[i].contentWindow === e.source) { frames[i].style.height = Math.min(h + 4, 2000) + 'px'; }
    }
  });
  poll();
  setInterval(poll, 4000);
})();
