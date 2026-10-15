(function () {
  'use strict';
  var QS = [['pace', 'The pace was right for me'], ['clarity', 'The labs were clear'],
            ['useful', 'I can use this in my own work'], ['overall', 'Overall, I would recommend this class']];
  function $(id) { return document.getElementById(id); }
  function say(t, bad) { $('msg').textContent = t; $('msg').className = bad ? 'err' : 'dim'; }
  QS.forEach(function (q) {
    var box = document.createElement('div'), p = document.createElement('div'), scale = document.createElement('div');
    box.className = 'card'; p.textContent = q[1]; scale.className = 'scale';
    for (var n = 1; n <= 5; n++) {
      var l = document.createElement('label'), r = document.createElement('input');
      r.type = 'radio'; r.name = q[0]; r.value = String(n);
      l.appendChild(r); l.appendChild(document.createTextNode(' ' + n)); scale.appendChild(l);
    }
    box.appendChild(p); box.appendChild(scale); $('qs').appendChild(box);
  });
  fetch('api/mine', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
    if (!d.mine) { return; }
    QS.forEach(function (q) {
      var v = d.mine.ratings[q[0]];
      if (v) { document.querySelector('input[name=' + q[0] + '][value="' + v + '"]').checked = true; }
    });
    $('comment').value = d.mine.comment || '';
    say('You answered already; you can change it.');
  });
  $('form').addEventListener('submit', function (e) {
    e.preventDefault();
    var ratings = {};
    QS.forEach(function (q) {
      var c = document.querySelector('input[name=' + q[0] + ']:checked');
      if (c) { ratings[q[0]] = parseInt(c.value, 10); }
    });
    fetch('api/submit', { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'dojo-feedback' },
      body: JSON.stringify({ ratings: ratings, comment: $('comment').value }) })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) { throw new Error(d.error || r.status); } return d; }); })
      .then(function () { say('Thank you! Sent.'); })
      .catch(function (err) { say(err.message, true); });
  });
}());
