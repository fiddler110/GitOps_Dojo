(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }
  function clear(el) { while (el.firstChild) { el.removeChild(el.firstChild); } }
  function draw(d) {
    $('n').textContent = d.responses + ' response' + (d.responses === 1 ? '' : 's') + '.';
    clear($('rows'));
    d.questions.forEach(function (q) {
      var tr = document.createElement('tr');
      [q.text, q.mean === null ? '-' : q.mean, q.count].concat(q.counts).forEach(function (v) {
        var td = document.createElement('td'); td.textContent = v; tr.appendChild(td);
      });
      $('rows').appendChild(tr);
    });
    clear($('comments'));
    d.comments.forEach(function (c) {
      var b = document.createElement('blockquote'); b.textContent = c; $('comments').appendChild(b);
    });
  }
  function load() {
    fetch('api/summary', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(draw);
  }
  load();
  setInterval(load, 10000);
}());
