
// -- roster grid ------------------------------------------------------
const grid = document.getElementById('grid');
const tiles = {};
let enlarged = null;

// The watch iframe is laid out at one fixed, generous pixel size -- not
// the tile's actual (usually much smaller) visible size -- then shrunk
// (or, enlarged, grown) to fit with a CSS transform (see updateScale).
// xterm.js inside sizes its terminal from that *unscaled* layout box, so
// tmux always sees a client at least as big as most real single-terminal
// panes; a client smaller than the real pane is what makes tmux clip to
// that corner instead of reflowing (see tmux.conf's window-size comment).
//
// This view is read-only and just for a facilitator's at-a-glance check,
// not a pixel-perfect mirror, so it deliberately does NOT track each
// student's actual pane size to match it exactly -- an earlier version
// did, but a session nobody else ever attaches to (every demo bot, always
// -- see tmux.conf) has nothing real to anchor that size against, so this
// page's own size guess fed back into itself every 5s poll and grew
// without bound. One fixed reference size, comfortably bigger than almost
// any single terminal pane, sidesteps that whole problem.
//
// A smaller per-tile-only reference (more legible text, less content
// visible) was tried and reverted -- shrinking a small tile's *content*,
// not just its text, isn't the tradeoff wanted here; a small tile should
// show as much of the real pane as an enlarged one does, just smaller.
const FRAME_W = 1120;
const FRAME_H = 800;

function initFrameSize(frame) {
  frame.dataset.w = FRAME_W;
  frame.dataset.h = FRAME_H;
  frame.style.width = FRAME_W + 'px';
  frame.style.height = FRAME_H + 'px';
}

// A floor on how far a tile will shrink the frame to fit -- without one,
// a tile still mid-layout (0 width/height for a tick after being added)
// or an unusually large real pane would render text at an illegibly tiny
// scale. Below this floor .tile-frame-wrap's overflow: hidden just crops
// to whatever corner fits, same as tmux would show a too-small client
// anyway (see above) -- a legible fraction beats all of it unreadable.
const MIN_SCALE = 0.3;

function updateScale(wrap) {
  const frame = wrap.querySelector('iframe');
  if (!frame || !frame.dataset.w) return;
  const rect = wrap.getBoundingClientRect();
  const scale = Math.min(rect.width / frame.dataset.w, rect.height / frame.dataset.h);
  frame.style.transform = `scale(${Math.max(scale, MIN_SCALE)})`;
}

const frameObserver = new ResizeObserver(entries => {
  for (const entry of entries) updateScale(entry.target);
});

// Builds one element; any text goes in via textContent (student names and
// the like are data, never markup).
function make(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function setStatus(el, active) {
  el.textContent = active ? '\u25CF active' : '\u25CF inactive';
  el.classList.toggle('st-on', !!active);
  el.classList.toggle('st-off', !active);
}

// Connects a tile's iframe to its watch endpoint the first time the
// student becomes watchable (see updateRoster) -- a no-op if already
// connected, so it's safe to call on every poll.
function activateWatch(tile, sid) {
  const frame = tile.querySelector('iframe');
  if (frame.src) return;
  frame.src = '/admin/watch/' + encodeURIComponent(sid) + '/';
  tile.classList.add('watching');
}

function reloadTile(sid) {
  const frame = tiles[sid].querySelector('iframe');
  if (!frame.src) return;  // not watchable yet -- nothing to reload
  const src = frame.src;
  frame.src = 'about:blank';
  frame.src = src;
}

function releaseTile(sid, btn) {
  btn.disabled = true;
  fetch('/admin/release/' + encodeURIComponent(sid), {
    method: 'POST',
    headers: { 'X-Requested-With': 'dojo-admin' },
  }).then(refresh);
}

// Roster "Release unused": free every slot taken a while ago whose student
// never started VS Code or a terminal (e.g. slots a script grabbed).
function releaseUnused(btn, out) {
  if (!confirm('Release every slot taken over 2 minutes ago with no VS Code or terminal running?')) return;
  btn.disabled = true;
  fetch('/admin/release-unused', {
    method: 'POST',
    headers: { 'X-Requested-With': 'dojo-admin' },
  }).then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(d => { out.textContent = d.released.length ? 'Released: ' + d.released.join(', ') : 'Nothing to release'; })
    .catch(() => { out.textContent = 'Release failed'; })
    .finally(() => { btn.disabled = false; refresh(); });
}
document.getElementById('release-unused').onclick = (e) =>
  releaseUnused(e.currentTarget, document.getElementById('release-unused-out'));

// Roster "Password": fetch one student's Forgejo password on demand and show
// it in the tile (textContent only); a second click hides it again.
function togglePassword(sid, btn, out) {
  if (out.textContent) { out.textContent = ''; btn.textContent = 'Password'; return; }
  fetch('/admin/api/forgejo-password/' + encodeURIComponent(sid), {
    headers: { 'X-Requested-With': 'dojo-admin' },
  }).then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(d => { out.textContent = d.password; btn.textContent = 'Hide'; })
    .catch(() => { out.textContent = 'unavailable'; });
}

function toggleEnlarge(sid) {
  if (enlarged === sid) { closeEnlarge(); return; }
  if (enlarged && tiles[enlarged]) tiles[enlarged].classList.remove('enlarged');
  tiles[sid].classList.add('enlarged');
  grid.classList.add('has-enlarged');
  enlarged = sid;
}

function closeEnlarge() {
  if (enlarged && tiles[enlarged]) tiles[enlarged].classList.remove('enlarged');
  grid.classList.remove('has-enlarged');
  enlarged = null;
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeEnlarge(); });

// Roster "Reset" (student reset, allocator/reset.py): puts one student or
// bot back as at stack start. The facilitator types the id to enable the
// button; progress comes back in each /admin/api/sessions row's `reset`.
// Every string goes in through textContent: step details can echo
// student input.
const RESET_WHAT = [
  'their VS Code and terminal are stopped',
  'their open pull requests are closed and their branches deleted',
  'their Forgejo account, repositories and forks are deleted and the account made again',
  'their home folder and lab files are deleted and set up fresh',
].concat(__RESET_HOOK_LABELS__.map(l => l + ': theirs is removed and set up again'));
// Optional hooks ({id, label}): a checkbox each, off by default.
const RESET_OPTIONAL = __RESET_HOOK_OPTIONAL__;
let resetDialog = null;

function resetDialogFor(sid) {
  if (!resetDialog) {
    const d = document.createElement('dialog');
    d.id = 'reset-dialog';
    const h = make('h2');
    const p1 = make('p', '', 'This cannot be undone:');
    const ul = make('ul');
    RESET_WHAT.forEach(t => ul.appendChild(make('li', '', t)));
    const opts = RESET_OPTIONAL.map(o => {
      const label = make('label', 'rd-opt');
      const box = make('input');
      box.type = 'checkbox';
      box.value = o.id;
      label.append(box, document.createTextNode(' ' + o.label));
      return label;
    });
    const p2 = make('p', '', 'Their seat stays theirs; everyone else carries on. Type the id to confirm:');
    const input = make('input');
    input.autocomplete = 'off';
    input.spellcheck = false;
    const err = make('p', 'rd-error');
    const actions = make('div', 'rd-actions');
    const cancel = make('button', '', 'Cancel');
    const go = make('button', 'rd-go', 'Reset');
    cancel.type = go.type = 'button';
    actions.append(cancel, go);
    d.append(h, p1, ul, ...opts, p2, input, err, actions);
    document.body.appendChild(d);
    cancel.onclick = () => d.close();
    input.oninput = () => { go.disabled = input.value.trim() !== d.dataset.sid; };
    input.onkeydown = (e) => { if (e.key === 'Enter' && !go.disabled) go.click(); };
    go.onclick = () => {
      const target = d.dataset.sid;
      go.disabled = true;
      fetch('/admin/reset/' + encodeURIComponent(target), {
        method: 'POST',
        headers: { 'X-Requested-With': 'dojo-admin', 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'confirm=' + encodeURIComponent(input.value.trim()) + '&optional='
          + encodeURIComponent(opts.map(l => l.firstChild).filter(b => b.checked).map(b => b.value).join(',')),
      }).then(r => r.json().catch(() => ({})).then(j => ({ ok: r.ok, j })))
        .then(({ ok, j }) => {
          if (ok) { d.close(); refresh(); return; }
          err.textContent = String(j.error || 'Reset refused');
          go.disabled = false;
        })
        .catch(() => { err.textContent = 'Reset request failed'; go.disabled = false; });
    };
    resetDialog = { d, h, input, go, err, opts };
  }
  const rd = resetDialog;
  rd.d.dataset.sid = sid;
  rd.h.textContent = 'Reset ' + sid + '?';
  rd.input.value = '';
  rd.input.placeholder = sid;
  rd.err.textContent = '';
  rd.opts.forEach(l => { l.firstChild.checked = false; });
  rd.go.disabled = true;
  rd.d.showModal();
  rd.input.focus();
}

function resetBusy(reset) {
  return !!reset && (reset.state === 'queued' || reset.state === 'running');
}

const RESET_MARK = { done: '✓', failed: '✗', running: '…', pending: '·' };

// The tile's reset line: nothing until a reset is asked for, then one mark
// per step (detail on hover), the failing step's error and Retry.
function updateReset(tile, sid, reset) {
  const box = tile.querySelector('.tile-reset');
  const btn = tile.querySelector('.tile-reset-btn');
  const key = reset ? JSON.stringify(reset) : '';
  if (box.dataset.key === key) return;
  box.dataset.key = key;
  box.textContent = '';
  const busy = resetBusy(reset);
  btn.disabled = busy;
  if (busy) {
    // Their terminal is about to go; watch again once the reset is over.
    const frame = tile.querySelector('iframe');
    frame.removeAttribute('src');
    tile.classList.remove('watching');
  }
  if (!reset) return;
  const word = { queued: 'Reset queued', running: 'Resetting', done: 'Reset done', failed: 'Reset failed' };
  const head = make('span', 'rs-' + (reset.state === 'queued' ? 'pending' : reset.state),
                    word[reset.state] || String(reset.state));
  box.appendChild(head);
  let failed = null;
  (Array.isArray(reset.steps) ? reset.steps : []).forEach(st => {
    const status = RESET_MARK[st.status] ? st.status : 'pending';
    const el = make('span', 'rs-' + status, RESET_MARK[status] + ' ' + String(st.label));
    if (st.detail) el.title = String(st.detail);
    box.appendChild(el);
    if (status === 'failed') failed = st;
  });
  if (reset.state === 'failed') {
    const retry = make('button', '', 'Retry');
    retry.type = 'button';
    retry.onclick = (e) => { e.stopPropagation(); resetDialogFor(sid); };
    box.appendChild(retry);
    if (failed && failed.detail) {
      const errEl = make('span', 'rs-error', String(failed.detail));
      errEl.title = String(failed.detail);
      box.appendChild(errEl);
    }
  }
}

function buildTile(r) {
  const tile = document.createElement('div');
  tile.className = 'tile';
  const head = document.createElement('div');
  head.className = 'tile-head';
  const title = make('div', 'tile-title');
  const label = make('span', 'tile-label', String(r.studentId) + ' \u2014 ' + String(r.name));
  const reload = make('button', 'tile-reload', '\u21BB');
  reload.title = 'Reload (follow current terminal)';
  title.append(label, reload);
  const meta = make('div', 'tile-meta');
  const status = make('span', 'tile-status');
  setStatus(status, r.active);
  const pw = make('code', 'tile-pw');
  const pwBtn = make('button', 'tile-pw-btn', 'Password');
  const release = make('button', 'tile-release', 'Release');
  const resetBtn = make('button', 'tile-reset-btn', 'Reset');
  resetBtn.title = 'Put this account back as at stack start';
  meta.append(make('span', 'tile-ip', String(r.ip)), status, pw, pwBtn, release, resetBtn);
  const resetLine = make('div', 'tile-reset');
  head.append(title, meta, resetLine);
  resetBtn.onclick = (e) => { e.stopPropagation(); resetDialogFor(r.studentId); };
  label.onclick = () => toggleEnlarge(r.studentId);
  reload.onclick = (e) => { e.stopPropagation(); reloadTile(r.studentId); };
  release.onclick = (e) => { e.stopPropagation(); releaseTile(r.studentId, e.currentTarget); };
  // Bots sign in with BOT_PASSWORD, not a derived one: no button.
  if (r.ip === 'bot') pwBtn.remove();
  else pwBtn.onclick = (e) => { e.stopPropagation(); togglePassword(r.studentId, e.currentTarget, pw); };
  const wrap = document.createElement('div');
  wrap.className = 'tile-frame-wrap';
  const waiting = document.createElement('div');
  waiting.className = 'tile-waiting';
  waiting.textContent = 'Waiting for a terminal session to watch…';
  const frame = document.createElement('iframe');
  frame.loading = 'lazy';
  wrap.appendChild(waiting);
  wrap.appendChild(frame);
  initFrameSize(frame);
  tile.appendChild(head);
  tile.appendChild(wrap);
  frameObserver.observe(wrap);
  updateReset(tile, r.studentId, r.reset);
  if (r.watchable && !resetBusy(r.reset)) activateWatch(tile, r.studentId);
  return tile;
}

function updateRoster(rows) {
  const seen = new Set();
  for (const r of rows) {
    seen.add(r.studentId);
    if (tiles[r.studentId]) {
      setStatus(tiles[r.studentId].querySelector('.tile-status'), r.active);
      updateReset(tiles[r.studentId], r.studentId, r.reset);
      if (r.watchable && !resetBusy(r.reset)) activateWatch(tiles[r.studentId], r.studentId);
      continue;
    }
    const tile = buildTile(r);
    grid.appendChild(tile);
    tiles[r.studentId] = tile;
  }
  for (const sid of Object.keys(tiles)) {
    if (seen.has(sid)) continue;
    frameObserver.unobserve(tiles[sid].querySelector('.tile-frame-wrap'));
    tiles[sid].remove();
    delete tiles[sid];
    if (enlarged === sid) enlarged = null;
  }
  document.getElementById('empty').style.display = rows.length ? 'none' : 'block';
}

// -- service status strip ---------------------------------------------
// One chip per service: coloured dot + name + a word, so colour is never
// the only signal. Chips are updated in place (never rebuilt) and all text
// goes in via textContent/title -- names and details are data.
const statusEl = document.getElementById('status');
const svcChips = [];
const STATE_WORD = { green: 'Ready', yellow: 'Starting', red: 'Down' };

function buildChip() {
  const el = document.createElement('span');
  const dot = document.createElement('span');
  dot.className = 'svc-dot';
  dot.setAttribute('aria-hidden', 'true');
  const name = document.createElement('span');
  name.className = 'svc-name';
  const word = document.createElement('span');
  word.className = 'svc-word';
  el.append(dot, name, word);
  return el;
}

function updateStatus(data) {
  const services = Array.isArray(data.services) ? data.services : [];
  services.forEach((s, i) => {
    if (!svcChips[i]) {
      svcChips[i] = buildChip();
      statusEl.appendChild(svcChips[i]);
    }
    const el = svcChips[i];
    const state = STATE_WORD[s.state] ? s.state : 'red';
    el.className = 'svc ' + state;
    el.querySelector('.svc-name').textContent = String(s.name);
    el.querySelector('.svc-word').textContent = STATE_WORD[state];
    el.title = s.detail ? String(s.name) + ': ' + String(s.detail) : String(s.name) + ': ' + STATE_WORD[state];
  });
  while (svcChips.length > services.length) svcChips.pop().remove();
  statusEl.classList.remove('stale');
}

async function refreshStatus() {
  try {
    updateStatus(await (await fetch('/admin/api/status')).json());
  } catch {
    statusEl.classList.add('stale');  // keep the last known chips, greyed out
  }
}

async function refresh() {
  refreshStatus();
  let rows;
  try {
    rows = await (await fetch('/admin/api/sessions')).json();
  } catch {
    return;  // transient fetch failure -- try again next poll, don't tear down tiles
  }
  updateRoster(rows);
}
refresh();
setInterval(refresh, 5000);
