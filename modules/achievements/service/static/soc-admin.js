(function () {
  'use strict';
  // Facilitator controls on the one-page SOC (soc-admin.html): start/re-arm the swarm, inject or
  // hint-probe a student (or everyone), and override a student's map point. The dashboard itself
  // (feed, map, incident) is soc.js; picking a student here also selects their incident summary.
  var startBtn = document.getElementById('start-btn');
  var resetBtn = document.getElementById('reset-btn');
  var pickSel = document.getElementById('student-pick');
  var injectOne = document.getElementById('inject-one-btn');
  var hintOne = document.getElementById('hint-one-btn');
  var regionInput = document.getElementById('region-input');
  var regionBtn = document.getElementById('region-btn');
  var msg = document.getElementById('admin-msg');
  var picked = '';
  function say(text) { msg.textContent = text || ''; }
  function post(path, body) {
    var opts = { method: 'POST', credentials: 'same-origin', headers: { 'X-Requested-With': 'dojo-admin' } };
    if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    return fetch(path, opts);
  }
  window.DojoSOC.onTimer = function (timer) {
    startBtn.className = timer.phase === 'waiting' ? 'start' : 'start hidden';
    resetBtn.className = timer.phase === 'waiting' ? 'danger hidden' : 'danger';
  };
  startBtn.addEventListener('click', function () {
    startBtn.disabled = true;
    post('api/soc/start').then(window.DojoSOC.refresh).finally(function () { startBtn.disabled = false; });
  });
  resetBtn.addEventListener('click', function () {
    if (!window.confirm('Re-arm the countdown? The swarm stops until Start is pressed again.')) { return; }
    post('api/soc/reset').then(window.DojoSOC.refresh);
  });
  pickSel.addEventListener('change', function () {
    picked = pickSel.value;
    injectOne.disabled = hintOne.disabled = regionBtn.disabled = !picked;
    window.DojoSOC.setUser(picked);
  });
  injectOne.addEventListener('click', function () { if (picked) { post('api/soc/inject', { user: picked }); } });
  hintOne.addEventListener('click', function () { if (picked) { post('api/soc/hint', { user: picked }); } });
  document.getElementById('inject-all-btn').addEventListener('click', function () { post('api/soc/inject', { user: 'all' }); });
  document.getElementById('hint-all-btn').addEventListener('click', function () { post('api/soc/hint', { user: 'all' }); });
  regionBtn.addEventListener('click', function () {
    if (!picked) { return; }
    post('api/region', { user: picked, region: regionInput.value }).then(function (r) {
      return r.json().then(function (d) { say(r.ok ? (regionInput.value ? 'Location set.' : 'Location cleared.') : (d.error || 'Failed')); });
    }).then(window.DojoSOC.refresh).catch(function () { say('Failed'); });
  });
  function loadStudents() {
    fetch('api/state', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) { return; }
        var keep = pickSel.value;
        while (pickSel.options.length > 1) { pickSel.remove(1); }
        (d.students || []).forEach(function (s) {
          var o = document.createElement('option');
          o.value = s.user; o.textContent = s.name;
          pickSel.appendChild(o);
        });
        pickSel.value = keep;
      })
      .catch(function () {});
  }
  loadStudents();
  setInterval(loadStudents, 15000);
})();
