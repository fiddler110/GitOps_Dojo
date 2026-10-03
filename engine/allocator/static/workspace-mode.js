
// Remember, per browser, whether this student prefers the tabbed workspace or the
// separate pages ("split mode", which keeps Chrome's split screen usable).
(function () {
  var KEY = 'dojo-mode';
  function get() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function set(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  var page = document.documentElement.dataset.page;
  // The landing page goes straight to the workspace for anyone who chose it, unless they
  // just came back on purpose (?split).
  if (page === 'landing' && get() === 'workspace' && !/[?&]split(&|$)/.test(location.search)) {
    location.replace('/workspace');
    return;
  }
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('[data-mode]') : null;
    if (el) { set(el.dataset.mode); }
  });
})();
