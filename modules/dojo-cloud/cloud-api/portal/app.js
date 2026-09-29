/*
 * Dojo Portal SPA - vanilla ES2020, no build step, no libraries, no external assets.
 * Served by cloud-api at /cloud/ under a strict CSP (script-src 'self'; style-src 'self').
 *
 * SECURITY RULE (read before editing this file):
 *   Every value that comes from the API - names, tags, messages, images, FQDNs, log text,
 *   event text, owners, resource ids - is controlled by students and is shown to OTHER
 *   students (Class view). It is therefore rendered ONLY with textContent / text nodes,
 *   createElement, and setAttribute on attributes from a fixed allow-list (see h()).
 *   NEVER use innerHTML, outerHTML, insertAdjacentHTML, document.write, eval,
 *   new Function, string timers, inline event-handler attributes, or javascript: URLs.
 *   Links are only ever built by this file: hash links from encodeURIComponent'ed parts,
 *   and the "Browse" link, whose href must match SITE_RE (else no link is rendered).
 *   CSS class names are never taken from data; they come from fixed lookup tables.
 */
(function () {
  'use strict';

  // ------------------------------------------------------------------ constants
  const POLL_MS = 3000;
  const FETCH_TIMEOUT_MS = 10000;
  const SITE_RE = /^\/cloud\/site\/[a-z][a-z0-9-]{2,40}\/$/;
  const HASH_RE = /^#\/[\w\/%.~!*'()-]*$/;
  const ATTR_OK = /^(?:class|id|type|role|title|for|name|value|placeholder|colspan|scope|tabindex|rel|target|href|disabled|readonly|hidden|autocomplete|maxlength|max|min|selected|checked|spellcheck|aria-[a-z]+|data-[a-z-]+)$/;
  const GATEWAY_HINT = 'Open the portal through the workshop gateway while signed in.';
  const NOTHING_YET = 'Nothing here yet';
  const WRITE_DISABLED_NOTE = 'Write actions are disabled by your facilitator.';

  // ------------------------------------------------------------------ global state
  const S = {
    me: null,
    scope: 'mine',      // facilitator overview scope: mine | class
    actScope: 'mine',   // facilitator activity scope: mine | all
    filters: { class: '', containers: '', resources: '' },
    progressSort: 'roster',   // facilitator class progress board: roster | attention | recent
  };
  let current = null;       // mounted view
  let routeToken = 0;       // increments per navigation; stale responses are dropped
  let inflight = null;      // AbortController of the running refresh
  let pollTimer = null;
  let waitingForVisible = false;
  let activeDialog = null;
  let firstRoute = true;

  const $ = (id) => document.getElementById(id);
  const el = {
    view: $('view'), main: $('main'), updated: $('updated'), paused: $('paused'),
    banner: $('banner'), bannerMsg: $('banner-msg'), live: $('live'),
    nav: $('sidenav'), navToggle: $('nav-toggle'),
  };

  // ------------------------------------------------------------------ safe DOM helpers
  function isSafeHref(v) {
    return typeof v === 'string' && (HASH_RE.test(v) || SITE_RE.test(v));
  }

  /** h(tag, attrs, ...children): createElement + allow-listed setAttribute + text nodes only. */
  function h(tag, attrs, ...kids) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const k of Object.keys(attrs)) {
        const v = attrs[k];
        if (v === false || v == null) continue;
        if (k === 'on') {
          for (const ev of Object.keys(v)) node.addEventListener(ev, v[ev]);
          continue;
        }
        if (!ATTR_OK.test(k)) throw new Error('attribute not allowed: ' + k);
        if (k === 'href' && !isSafeHref(v)) continue;
        node.setAttribute(k, v === true ? '' : String(v));
      }
    }
    append(node, kids);
    return node;
  }
  function append(node, kids) {
    for (const k of kids.flat(Infinity)) {
      if (k == null || k === false) continue;
      node.append(k instanceof Node ? k : document.createTextNode(String(k)));
    }
    return node;
  }
  function setText(node, text) {
    const t = text == null ? '' : String(text);
    if (node.textContent !== t) node.textContent = t;
  }
  /** Replace a slot's children only when its signature changes (keeps focus/selection stable). */
  function setSlot(slot, sig, build) {
    if (slot.getAttribute('data-sig') === sig) return;
    slot.setAttribute('data-sig', sig);
    slot.replaceChildren(...[].concat(build()).filter(Boolean));
  }

  // ------------------------------------------------------------------ data normalisation
  const str = (v, max = 500) => {
    if (v == null) return '';
    const s = typeof v === 'string' ? v : (typeof v === 'number' || typeof v === 'boolean') ? String(v) : '';
    return s.length > max ? s.slice(0, max) + '\u2026' : s;
  };
  const logText = (v) => (typeof v === 'string' && v !== '' ? v.slice(-300000) : '(no log output yet)');
  const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
  const objs = (v) => (Array.isArray(v) ? v.filter((x) => x && typeof x === 'object') : []);
  function tagPairs(v) {
    if (!v || typeof v !== 'object' || Array.isArray(v)) return [];
    return Object.keys(v).slice(0, 100).sort().map((k) => [str(k, 128), str(v[k], 300)]);
  }
  function normCG(x) {
    return {
      id: str(x.id, 400), name: str(x.name, 200), resourceGroup: str(x.resourceGroup, 200),
      subscriptionId: str(x.subscriptionId, 64), owner: str(x.owner, 100), location: str(x.location, 40),
      state: str(x.state, 30), fqdn: str(x.fqdn, 300), ip: str(x.ip, 64), image: str(x.image, 300),
      cpu: num(x.cpu), memoryGb: num(x.memoryGb), tags: tagPairs(x.tags), dnsLabel: str(x.dnsLabel, 100),
      siteUrl: typeof x.siteUrl === 'string' && SITE_RE.test(x.siteUrl) ? x.siteUrl : '',
      isMine: x.isMine === true,
    };
  }
  function normRG(x) {
    return {
      id: str(x.id, 400), name: str(x.name, 200), subscriptionId: str(x.subscriptionId, 64),
      owner: str(x.owner, 100), location: str(x.location, 40), tags: tagPairs(x.tags),
      containerCount: num(x.containerCount), isMine: x.isMine === true,
    };
  }
  function normEvent(x) {
    return {
      time: str(x.time, 64), subscription: str(x.subscription, 64), caller: str(x.caller, 100),
      operation: str(x.operation, 200), resourceId: str(x.resourceId, 400), status: str(x.status, 60),
      message: str(x.message, 1000),
    };
  }
  function normOverview(o) {
    o = o && typeof o === 'object' ? o : {};
    return { rgs: objs(o.resourceGroups).map(normRG), cgs: objs(o.containerGroups).map(normCG) };
  }
  function normMe(m) {
    m = m && typeof m === 'object' ? m : {};
    const q = m.quota && m.quota.containerGroups ? m.quota.containerGroups : {};
    return {
      user: str(m.user, 100), subscriptionId: str(m.subscriptionId, 64), isFacilitator: m.isFacilitator === true,
      writeActions: m.writeActions !== false, used: num(q.used), limit: num(q.limit),
    };
  }

  // Class progress board (TOFU-BASICS-PLAN.md 5.6a). Stage names are validated against STAGES, never used as-is.
  const STAGES = {
    attention:  { label: 'Needs attention', summary: 'needs attention', pill: 'pill-err', rank: 0 },
    inProgress: { label: 'In progress', summary: 'in progress', pill: 'pill-warn', rank: 1 },
    running:    { label: 'Running', summary: 'running', pill: 'pill-ok', rank: 2 },
    notStarted: { label: 'Not started', summary: 'not started', pill: 'pill-neutral', rank: 3 },
  };
  const STAGE_KEYS = ['running', 'inProgress', 'attention', 'notStarted'];   // order of the summary strip
  const isStage = (v) => typeof v === 'string' && Object.prototype.hasOwnProperty.call(STAGES, v);
  function normProgressStudent(x) {
    const sub = str(x.subscriptionId, 64);
    const ev = x.lastEvent && typeof x.lastEvent === 'object' ? x.lastEvent : null;
    return {
      user: str(x.user, 100), subscriptionId: sub, stage: isStage(x.stage) ? x.stage : 'notStarted',
      resourceGroups: num(x.resourceGroups) || 0, failures: num(x.failures) || 0,
      containerGroups: objs(x.containerGroups).slice(0, 50).map((c) => ({
        name: str(c.name, 200), resourceGroup: str(c.resourceGroup, 200), subscriptionId: sub, state: str(c.state, 30),
        siteUrl: typeof c.siteUrl === 'string' && SITE_RE.test(c.siteUrl) ? c.siteUrl : '',
      })),
      lastEvent: ev ? { time: str(ev.time, 64), operation: str(ev.operation, 200), status: str(ev.status, 60), message: str(ev.message, 200) } : null,
    };
  }
  function normProgress(o) {
    o = o && typeof o === 'object' ? o : {};
    const students = objs(o.students).map(normProgressStudent);
    const sm = o.summary && typeof o.summary === 'object' ? o.summary : {};
    const summary = { total: num(sm.total) ?? students.length };
    for (const k of STAGE_KEYS) summary[k] = num(sm[k]) ?? students.filter((s) => s.stage === k).length;
    return { generatedAt: str(o.generatedAt, 64), summary, students };
  }

  // ------------------------------------------------------------------ formatting
  const enc = encodeURIComponent;
  const pad2 = (n) => String(n).padStart(2, '0');
  function clock(d) { return pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds()); }
  function fmtTime(iso) {
    const d = new Date(iso);
    if (!iso || Number.isNaN(d.getTime())) return iso || '\u2014';
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' + clock(d);
  }
  /** "12s ago" / "3m ago" / "2h ago" / "4d ago"; nowMs is the server's generatedAt, so browser clock skew does not show. */
  function fmtAgo(iso, nowMs) {
    const t = Date.parse(iso);
    if (!iso || Number.isNaN(t)) return '';
    const sec = Math.max(0, Math.round((nowMs - t) / 1000));
    if (sec < 60) return sec + 's ago';
    if (sec < 3600) return Math.floor(sec / 60) + 'm ago';
    if (sec < 86400) return Math.floor(sec / 3600) + 'h ago';
    return Math.floor(sec / 86400) + 'd ago';
  }
  const dash = (v) => (v === '' || v == null ? '\u2014' : v);
  function fmtSize(cg) {
    if (cg.cpu == null && cg.memoryGb == null) return '\u2014';
    return (cg.cpu == null ? '?' : cg.cpu) + ' vCPU / ' + (cg.memoryGb == null ? '?' : cg.memoryGb) + ' GB';
  }
  function shortResource(id) {
    const m = /\/resourceGroups\/([^/]+)(?:\/providers\/[^/]+\/[^/]+\/([^/]+))?/i.exec(id);
    if (!m) return id;
    return m[2] ? m[1] + ' / ' + m[2] : m[1];
  }
  const hashCG = (cg) => '#/containers/' + enc(cg.subscriptionId) + '/' + enc(cg.resourceGroup) + '/' + enc(cg.name);
  const hashRG = (rg) => '#/rg/' + enc(rg.subscriptionId) + '/' + enc(rg.name);
  const canOpen = (item) => item.isMine || !!(S.me && S.me.isFacilitator);

  const STATE_CLASS = { Running: 'pill-ok', Terminated: 'pill-warn' };
  function statePill(state) {
    return h('span', { class: 'pill ' + (STATE_CLASS[state] || 'pill-neutral') },
      h('span', { class: 'pill-dot', 'aria-hidden': 'true' }), state || 'Unknown');
  }
  function statusClass(status) {
    const s = status.toLowerCase();
    if (/fail|denied|disallow|error|reject|quota|forbidden|invalid|conflict|\b[45]\d\d\b/.test(s)) return 'pill-err';
    if (/succe|\bok\b|accept|complete|created|deleted|updated|\b2\d\d\b/.test(s)) return 'pill-ok';
    if (/start|progress|pending|running/.test(s)) return 'pill-warn';
    return 'pill-neutral';
  }
  function statusPill(status) {
    return h('span', { class: 'pill ' + statusClass(status) },
      h('span', { class: 'pill-dot', 'aria-hidden': 'true' }), status || 'Unknown');
  }
  function chips(pairs, limit = 12) {
    if (!pairs.length) return h('span', { class: 'muted' }, 'No tags');
    const shown = pairs.slice(0, limit);
    const ul = h('ul', { class: 'chips' }, shown.map(([k, v]) => h('li', { class: 'chip' }, k + '=' + v)));
    if (pairs.length > limit) ul.append(h('li', { class: 'muted small' }, '+' + (pairs.length - limit) + ' more'));
    return ul;
  }
  const CLIP = 60;
  const clip = (s) => (typeof s === 'string' && s.length > CLIP ? s.slice(0, CLIP) + '\u2026' : s);
  function link(text, hash, extra) {
    const t = clip(text);
    return h('a', Object.assign({ href: hash, title: t !== text ? text : null }, extra || {}), t);
  }
  /** Long attacker-controlled strings are clipped in table cells (full text in the title). */
  function clipNode(content) {
    if (typeof content === 'string' && content.length > CLIP) return h('span', { title: content }, clip(content));
    return content;
  }
  function browseLink(cg, extraClass) {
    if (!cg.siteUrl) return h('span', { class: 'muted', title: 'No site URL available' }, '\u2014');
    return h('a', {
      href: cg.siteUrl, target: '_blank', rel: 'noopener noreferrer', 'data-fk': 'browse',
      class: extraClass || null,
    }, 'Browse', h('span', { class: 'sr-only' }, ' ' + cg.name + ' (opens in a new tab)'), ' \u2197');
  }
  function you() { return h('span', { class: 'you' }, 'You'); }

  // ------------------------------------------------------------------ announcements
  let liveTimer = null;
  function announce(msg) {
    clearTimeout(liveTimer);
    el.live.textContent = '';
    liveTimer = setTimeout(() => { el.live.textContent = msg; }, 60);
  }

  // ------------------------------------------------------------------ API
  class ApiError extends Error {
    constructor(status, code, message) { super(message); this.status = status; this.code = code; }
  }
  async function api(path, opts = {}) {
    const ctrl = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; ctrl.abort(); }, FETCH_TIMEOUT_MS);
    if (opts.signal) {
      if (opts.signal.aborted) ctrl.abort();
      else opts.signal.addEventListener('abort', () => ctrl.abort(), { once: true });
    }
    const init = {
      method: opts.method || 'GET', credentials: 'same-origin', cache: 'no-store', signal: ctrl.signal,
      headers: { Accept: 'application/json' },
    };
    if (opts.body !== undefined) {
      init.body = JSON.stringify(opts.body);
      init.headers['Content-Type'] = 'application/json';
    }
    let res, text;
    try {
      res = await fetch('api/' + path, init);
      text = await res.text();
    } catch (e) {
      if (opts.signal && opts.signal.aborted) throw e;
      if (timedOut) throw new ApiError(0, 'Timeout', 'The portal API did not answer in time.');
      throw new ApiError(0, 'NetworkError', 'Could not reach the portal API.');
    } finally {
      clearTimeout(timer);
    }
    let data = null;
    if (text) { try { data = JSON.parse(text); } catch (e) { data = null; } }
    if (!res.ok) {
      const err = data && typeof data === 'object' ? data.error : null;
      throw new ApiError(res.status, str(err && err.code, 80) || 'HTTP' + res.status,
        str(err && err.message, 600) || res.statusText || 'The request failed.');
    }
    if (res.status === 204 || text === '') return {};
    if (data === null || typeof data !== 'object') {
      throw new ApiError(res.status, 'BadResponse',
        'The portal API returned an unexpected response.' + (res.redirected ? ' ' + GATEWAY_HINT : ''));
    }
    return data;
  }
  const isAbort = (e) => e && e.name === 'AbortError';

  function errText(e) {
    if (e instanceof ApiError) return e.code && e.code !== 'BadResponse' && e.code !== 'NetworkError' && e.code !== 'Timeout'
      ? e.code + ': ' + e.message : e.message;
    return 'Something went wrong.';
  }
  function bannerText(e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      return GATEWAY_HINT + ' (' + errText(e) + ')';
    }
    return errText(e);
  }

  async function loadMe(signal) {
    const me = normMe(await api('me', { signal }));
    S.me = me;
    renderTopbar(me);
    return me;
  }
  const currentScope = () => (S.scope === 'class' && S.me && S.me.isFacilitator ? 'class' : 'mine');

  // ------------------------------------------------------------------ top bar / banner / status
  function renderTopbar(me) {
    setText($('meta-user'), me.user || 'Unknown user');
    $('meta-facilitator').hidden = !me.isFacilitator;
    $('nav-progress').hidden = !me.isFacilitator;
    const sub = $('meta-sub');
    sub.hidden = !me.subscriptionId;
    setText($('meta-sub-full'), me.subscriptionId);
    setText($('meta-sub-short'), me.subscriptionId ? me.subscriptionId.slice(0, 8) + '\u2026' : '');
    sub.title = me.subscriptionId ? 'Subscription ' + me.subscriptionId : '';
  }
  function showError(e) {
    const msg = bannerText(e);
    if (el.bannerMsg.textContent !== msg) el.bannerMsg.textContent = msg;
    el.banner.hidden = false;
    if (!S.me) setText($('meta-user'), 'Not signed in');
  }
  function hideError() { el.banner.hidden = true; }
  function stampUpdated() { setText(el.updated, 'Last updated: ' + clock(new Date())); }
  function setPaused(p) { el.paused.hidden = !p; }

  // ------------------------------------------------------------------ polling
  function isTyping(root) {
    const a = document.activeElement;
    if (!a || !root || !root.contains(a) || a.hasAttribute('data-live')) return false;
    return (a.tagName === 'INPUT' && a.type !== 'checkbox' && a.type !== 'radio') || a.tagName === 'TEXTAREA' || a.tagName === 'SELECT';
  }
  function busyEditing() {
    if (activeDialog) return true;
    return !!(current && (isTyping(el.view) || (current.isEditing && current.isEditing())));
  }
  function schedule() {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(tick, POLL_MS);
  }
  function tick() {
    if (document.visibilityState !== 'visible') { waitingForVisible = true; return; }
    if (busyEditing()) { setPaused(true); schedule(); return; }
    setPaused(false);
    refresh();
  }
  async function refresh() {
    if (inflight || !current) return;
    const token = routeToken, view = current;
    const ctrl = new AbortController();
    inflight = ctrl;
    try {
      const data = await view.load(ctrl.signal);
      if (token !== routeToken) return;
      hideError();
      view.update(data);
      stampUpdated();
    } catch (e) {
      if (token !== routeToken || isAbort(e)) return;
      clearLoading(el.view);
      showError(e);
    } finally {
      if (inflight === ctrl) inflight = null;
      if (token === routeToken) schedule();
    }
  }
  /** Drop any in-flight request and reload now (after a user action). */
  function reload() {
    if (inflight) { inflight.abort(); inflight = null; }
    clearTimeout(pollTimer);
    refresh();
  }

  // ------------------------------------------------------------------ dialogs
  function focusables(root) {
    return Array.from(root.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'))
      .filter((n) => !n.disabled && !n.hidden && n.offsetParent !== null);
  }
  function closeActiveDialog() { if (activeDialog) activeDialog.close(); }

  function confirmDialog(opts) {
    const opener = document.activeElement;
    const dlg = h('dialog', { class: 'dialog', 'aria-labelledby': 'dlg-title', 'aria-describedby': 'dlg-body' });
    const errEl = h('p', { class: 'form-error', role: 'alert', hidden: true });
    const cancel = h('button', { type: 'button', class: 'btn' }, 'Cancel');
    const ok = h('button', { type: 'button', class: 'btn ' + (opts.danger ? 'btn-danger' : 'btn-primary') }, opts.confirmLabel);
    append(dlg, [
      h('h2', { id: 'dlg-title' }, opts.title),
      h('div', { id: 'dlg-body', class: 'dialog-body' }, opts.body),
      errEl,
      h('div', { class: 'dialog-actions' }, cancel, ok),
    ]);
    document.body.append(dlg);
    let busy = false;
    const api_ = {
      close() {
        if (activeDialog !== api_) return;
        activeDialog = null;
        if (dlg.open) dlg.close();
        dlg.remove();
        if (opener && opener.isConnected && typeof opener.focus === 'function') opener.focus();
      },
    };
    cancel.addEventListener('click', () => { if (!busy) api_.close(); });
    dlg.addEventListener('cancel', (ev) => { ev.preventDefault(); if (!busy) api_.close(); });
    dlg.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') { ev.preventDefault(); if (!busy) api_.close(); return; }
      if (ev.key !== 'Tab') return;
      const f = focusables(dlg);
      if (!f.length) { ev.preventDefault(); return; }
      const first = f[0], last = f[f.length - 1];
      if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
      else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
    });
    ok.addEventListener('click', async () => {
      if (busy) return;
      busy = true; ok.disabled = true; cancel.disabled = true; errEl.hidden = true;
      const label = ok.textContent; ok.textContent = 'Working\u2026';
      try {
        await opts.run();
        busy = false;
        api_.close();
      } catch (e) {
        busy = false; ok.disabled = false; cancel.disabled = false; ok.textContent = label;
        errEl.textContent = errText(e); errEl.hidden = false;
      }
    });
    closeActiveDialog();
    activeDialog = api_;
    dlg.showModal();
    cancel.focus();
    return api_;
  }

  // ------------------------------------------------------------------ small widgets
  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return true; }
    } catch (e) { /* fall through */ }
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.className = 'sr-only';
      document.body.append(ta);
      ta.select();
      const ok = document.execCommand('copy');
      ta.remove();
      return ok;
    } catch (e) { return false; }
  }
  function copyButton(getText, label) {
    const b = h('button', { type: 'button', class: 'btn btn-small', 'aria-label': label }, 'Copy');
    let t = null;
    b.addEventListener('click', async () => {
      const ok = await copyText(getText());
      b.textContent = ok ? 'Copied' : 'Copy failed';
      announce(ok ? 'Copied to clipboard' : 'Could not copy');
      clearTimeout(t);
      t = setTimeout(() => { b.textContent = 'Copy'; }, 1800);
    });
    return b;
  }
  function segmented(label, options, getValue, onPick) {
    const wrap = h('div', { class: 'segmented', role: 'group', 'aria-label': label });
    const btns = options.map(([value, text]) => {
      const b = h('button', { type: 'button', 'data-live': 'true' }, text);
      b.addEventListener('click', () => { onPick(value); sync(); });
      wrap.append(b);
      return [value, b];
    });
    function sync() { for (const [v, b] of btns) b.setAttribute('aria-pressed', String(getValue() === v)); }
    sync();
    return { el: wrap, sync };
  }
  function pageHeader(title, opts = {}) {
    const h1 = h('h1', { tabindex: '-1' }, title);
    const grow = h('div', { class: 'grow' }, opts.crumb ? h('p', { class: 'breadcrumb' }, opts.crumb) : null, h1,
      opts.subtitle ? h('p', { class: 'subtitle' }, opts.subtitle) : null);
    const actions = h('div', { class: 'actions' }, opts.actions || []);
    return { el: h('div', { class: 'page-header' }, grow, actions), h1, actions };
  }
  function emptyState(title, extra) {
    return h('div', { class: 'empty' }, h('h2', null, title),
      h('p', null, 'Run ', h('code', null, 'terraform apply'), ' in your lab repository (', h('code', null, 'tofu apply'),
        ' works too) to create a resource group and a container instance. It will show up here within a few seconds.'),
      extra ? h('p', null, extra) : null);
  }
  function card(title, ...kids) {
    return h('section', { class: 'card' }, title ? h('h2', null, title) : null, kids);
  }
  function loadingNode() { return h('p', { class: 'loading', 'data-loading': 'true' }, 'Loading\u2026'); }
  function clearLoading(root) { root.querySelectorAll('[data-loading]').forEach((n) => n.remove()); }

  // ------------------------------------------------------------------ keyed table
  /**
   * makeTable({label, columns:[{label, cell(item)->Node|string, rowHeader, cls}], keyOf, rowClass})
   * Rows are keyed; a row is rebuilt only when its serialised item (plus ctx) changes, so the
   * table never flickers, keeps its scroll position, and keeps focus on unchanged rows.
   */
  function makeTable(cfg) {
    const wrap = h('div', { class: 'table-wrap', role: 'region', 'aria-label': cfg.label, tabindex: '0' });
    const tbody = h('tbody');
    const table = h('table', { class: 'grid' },
      h('caption', { class: 'sr-only' }, cfg.label),
      h('thead', null, h('tr', null, cfg.columns.map((c) => h('th', { scope: 'col', class: c.cls || null }, c.label)))),
      tbody);
    wrap.append(table);
    const rows = new Map();

    function buildRow(item) {
      const tr = h('tr', { class: cfg.rowClass ? cfg.rowClass(item) || null : null });
      cfg.columns.forEach((c) => {
        const content = c.full ? c.cell(item) : clipNode(c.cell(item));
        tr.append(c.rowHeader ? h('th', { scope: 'row', class: c.cls || null }, content) : h('td', { class: c.cls || null }, content));
      });
      return tr;
    }
    function update(items, ctx) {
      const seen = new Set();
      const dupes = new Map();
      let prev = null;
      for (const item of items) {
        let key = cfg.keyOf(item);
        const n = dupes.get(key) || 0;
        dupes.set(key, n + 1);
        if (n) key += '#' + n;
        seen.add(key);
        const sig = (ctx || '') + '|' + JSON.stringify(item);
        let rec = rows.get(key);
        if (!rec || rec.sig !== sig) {
          const tr = buildRow(item);
          if (rec) {
            const a = document.activeElement;
            const fk = a && rec.tr.contains(a) ? a.getAttribute('data-fk') : null;
            rec.tr.replaceWith(tr);
            if (fk) { const t = tr.querySelector('[data-fk="' + fk + '"]'); if (t) t.focus(); }
          }
          rec = { sig, tr };
          rows.set(key, rec);
        }
        const ref = prev ? prev.nextSibling : tbody.firstChild;
        if (rec.tr !== ref) tbody.insertBefore(rec.tr, ref);
        prev = rec.tr;
      }
      for (const [k, rec] of rows) {
        if (!seen.has(k)) { rec.tr.remove(); rows.delete(k); }
      }
    }
    return { el: wrap, update };
  }

  // ------------------------------------------------------------------ column sets
  function ownerCol() {
    return { label: 'Owner', cls: 'nowrap', cell: (i) => (i.isMine ? [i.owner, you()] : i.owner) };
  }
  function cgNameCell(cg) {
    return canOpen(cg) ? link(cg.name, hashCG(cg), { 'data-fk': 'open' }) : cg.name;
  }
  function rgNameCell(rg) {
    return canOpen(rg) ? link(rg.name, hashRG(rg), { 'data-fk': 'open' }) : rg.name;
  }
  function activityColumns(compact) {
    const cols = [
      { label: 'Time', cls: 'nowrap', cell: (e) => h('span', { title: e.time }, fmtTime(e.time)) },
      { label: 'Operation', full: true, cell: (e) => e.operation || '\u2014' },
    ];
    if (!compact) cols.push({ label: 'Caller', cls: 'nowrap', cell: (e) => dash(e.caller) });
    cols.push({ label: 'Status', cls: 'nowrap', cell: (e) => statusPill(e.status) });
    cols.push({ label: 'Resource', cell: (e) => (e.resourceId ? h('span', { class: 'mono', title: e.resourceId }, shortResource(e.resourceId)) : '\u2014') });
    if (!compact) cols.push({ label: 'Message', cls: 'msg', full: true, cell: (e) => dash(e.message) });
    return cols;
  }
  const eventKey = (e) => [e.time, e.operation, e.caller, e.resourceId, e.status].join('|');

  function sortBy(items, ...fields) {
    return items.slice().sort((a, b) => {
      for (const f of fields) { const c = String(a[f]).localeCompare(String(b[f])); if (c) return c; }
      return 0;
    });
  }
  function matcher(text) {
    const q = text.trim().toLowerCase();
    if (!q) return () => true;
    return (item) => Object.values(item).some((v) => typeof v === 'string' && v.toLowerCase().includes(q))
      || (Array.isArray(item.tags) && item.tags.some(([k, v]) => (k + '=' + v).toLowerCase().includes(q)));
  }

  // ------------------------------------------------------------------ scope switch (facilitator)
  function scopeSwitch() {
    return segmented('Overview scope', [['mine', 'My subscription'], ['class', 'Whole class']],
      () => S.scope, (v) => { S.scope = v; reload(); });
  }

  // =================================================================== VIEWS
  // A view is {title, nav, mount(root), load(signal)->data, update(data), isEditing?(), dispose?()}

  // ---- generic list view: resource groups, all resources, containers, class ----
  function listView(cfg) {
    let root, host, filterInput, countEl, empty, noMatch, table, tableSig, scopeCtl, filterVal = '';
    const noun = cfg.noun;
    return {
      title: cfg.title, nav: cfg.nav,
      mount(r) {
        root = r;
        const ph = pageHeader(cfg.title, { subtitle: cfg.subtitle });
        r.append(ph.el);
        const tb = h('div', { class: 'toolbar' });
        if (!cfg.forceClass) { scopeCtl = scopeSwitch(); scopeCtl.el.hidden = true; tb.append(scopeCtl.el); }
        if (cfg.filterKey) {
          filterInput = h('input', { type: 'text', class: 'filter', 'aria-label': 'Filter ' + noun, placeholder: 'Filter ' + noun + '\u2026', 'data-live': 'true', autocomplete: 'off', spellcheck: 'false' });
          filterInput.value = S.filters[cfg.filterKey] || '';
          filterInput.addEventListener('input', () => {
            S.filters[cfg.filterKey] = filterInput.value;
            if (current && current.lastData) current.update(current.lastData);
          });
          tb.append(filterInput);
        }
        countEl = h('p', { class: 'muted small grow', role: 'status' });
        tb.append(countEl);
        r.append(tb);
        host = h('div');
        empty = emptyState(NOTHING_YET);
        empty.hidden = true;
        noMatch = h('p', { class: 'muted', hidden: true }, 'No items match the filter.');
        r.append(loadingNode(), empty, noMatch, host);
      },
      async load(signal) {
        const scope = cfg.forceClass ? 'class' : currentScope();
        const [me, ov] = await Promise.all([loadMe(signal), api('overview?scope=' + scope, { signal })]);
        return { me, scope, ov: normOverview(ov) };
      },
      update(d) {
        this.lastData = d;
        clearLoading(root);
        if (scopeCtl) { scopeCtl.el.hidden = !d.me.isFacilitator; scopeCtl.sync(); }
        const showOwner = cfg.forceClass || d.scope === 'class';
        const sig = cfg.nav + '|' + showOwner + '|' + d.me.isFacilitator;
        if (sig !== tableSig) {
          tableSig = sig;
          table = makeTable({ label: cfg.title, columns: cfg.columns(showOwner), keyOf: cfg.keyOf, rowClass: cfg.rowClass });
          host.replaceChildren(table.el);
        }
        let items = cfg.items(d.ov);
        const total = items.length;
        if (cfg.filterKey) items = items.filter(matcher(S.filters[cfg.filterKey] || ''));
        table.update(items, sig);
        empty.hidden = total !== 0;
        noMatch.hidden = !(total > 0 && items.length === 0);
        host.hidden = items.length === 0;
        setText(countEl, cfg.count ? cfg.count(items, total, d) : (total ? items.length + (items.length !== total ? ' of ' + total : '') + ' ' + noun : ''));
      },
    };
  }

  const rgListView = () => listView({
    nav: 'rg', title: 'Resource groups', noun: 'resource groups', filterKey: null,
    subtitle: 'Containers for related resources. Delete a resource group with tofu destroy.',
    items: (ov) => sortBy(ov.rgs, 'owner', 'name'),
    keyOf: (rg) => rg.id || rg.subscriptionId + '/' + rg.name,
    rowClass: () => null,
    columns: (owner) => [
      { label: 'Name', rowHeader: true, cell: rgNameCell },
      { label: 'Location', cls: 'nowrap', cell: (r) => dash(r.location) },
      { label: 'Container instances', cls: 'nowrap', cell: (r) => (r.containerCount == null ? '\u2014' : String(r.containerCount)) },
      { label: 'Tags', cell: (r) => chips(r.tags, 6) },
    ].concat(owner ? [ownerCol()] : []),
  });

  const resourcesView = () => listView({
    nav: 'resources', title: 'All resources', noun: 'resources', filterKey: 'resources',
    subtitle: 'Every resource group and container instance in the subscription.',
    items: (ov) => sortBy(
      ov.rgs.map((r) => Object.assign({ kind: 'Resource group', resourceGroup: r.name }, r))
        .concat(ov.cgs.map((c) => Object.assign({ kind: 'Container instance' }, c))), 'owner', 'resourceGroup', 'kind', 'name'),
    keyOf: (i) => i.kind + '|' + (i.id || i.subscriptionId + '/' + i.name),
    rowClass: () => null,
    columns: (owner) => [
      { label: 'Name', rowHeader: true, cell: (i) => (i.kind === 'Resource group' ? rgNameCell(i) : cgNameCell(i)) },
      { label: 'Type', cls: 'nowrap', cell: (i) => i.kind },
      { label: 'Resource group', cell: (i) => i.resourceGroup },
      { label: 'Location', cls: 'nowrap', cell: (i) => dash(i.location) },
      { label: 'Status', cls: 'nowrap', cell: (i) => (i.kind === 'Container instance' ? statePill(i.state) : '\u2014') },
    ].concat(owner ? [ownerCol()] : []),
  });

  const containersView = () => listView({
    nav: 'containers', title: 'Container instances', noun: 'container instances', filterKey: 'containers',
    subtitle: 'Azure Container Instances-style container groups.',
    items: (ov) => sortBy(ov.cgs, 'owner', 'resourceGroup', 'name'),
    keyOf: (c) => c.id || c.subscriptionId + '/' + c.resourceGroup + '/' + c.name,
    rowClass: () => null,
    columns: (owner) => [
      { label: 'Name', rowHeader: true, cell: cgNameCell },
      { label: 'Resource group', cell: (c) => c.resourceGroup },
      { label: 'Location', cls: 'nowrap', cell: (c) => dash(c.location) },
      { label: 'Status', cls: 'nowrap', cell: (c) => statePill(c.state) },
      { label: 'IP address', cls: 'nowrap', cell: (c) => dash(c.ip) },
      { label: 'FQDN', cell: (c) => dash(c.fqdn) },
      { label: 'Image', cell: (c) => dash(c.image) },
      { label: 'Browse', cls: 'nowrap', cell: (c) => browseLink(c) },
    ].concat(owner ? [ownerCol()] : []),
  });

  const classView = () => listView({
    nav: 'class', title: 'Class view', noun: 'container instances', filterKey: 'class', forceClass: true,
    subtitle: 'Everyone\u2019s container instances (read-only). Use Browse to visit a site.',
    items: (ov) => sortBy(ov.cgs, 'owner', 'name'),
    keyOf: (c) => c.id || c.subscriptionId + '/' + c.resourceGroup + '/' + c.name,
    rowClass: (c) => (c.isMine ? 'is-mine' : null),
    count: (items, total) => {
      const owners = new Set(items.map((c) => c.owner));
      return total ? items.length + ' container instance' + (items.length === 1 ? '' : 's') + ' from ' + owners.size + ' student' + (owners.size === 1 ? '' : 's') : '';
    },
    columns: () => [
      { label: 'Owner', rowHeader: true, cls: 'nowrap', cell: (c) => (c.isMine ? [c.owner, you()] : c.owner) },
      { label: 'Name', cell: (c) => (canOpen(c) ? link(c.name, hashCG(c), { 'data-fk': 'open' }) : c.name) },
      { label: 'Location', cls: 'nowrap', cell: (c) => dash(c.location) },
      { label: 'State', cls: 'nowrap', cell: (c) => statePill(c.state) },
      { label: 'Browse', cls: 'nowrap', cell: (c) => browseLink(c) },
    ],
  });

  // ---- class progress board (facilitator only; TOFU-BASICS-PLAN.md 5.6a) ----
  const PROGRESS_SORTS = [['roster', 'Roster order'], ['attention', 'Needs attention first'], ['recent', 'Most recently active']];
  const MAX_TILE_CGS = 6;
  const FLASH_MS = 2500;

  function stagePill(stage) {
    return h('span', { class: 'pill ' + STAGES[stage].pill },
      h('span', { class: 'pill-dot', 'aria-hidden': 'true' }), STAGES[stage].label);
  }
  /** Run fn (which rebuilds part of box) and put focus back on the same link if it was inside box. */
  function keepFocus(box, fn) {
    const a = document.activeElement;
    const inside = !!(a && box.contains(a));
    const fk = inside ? a.getAttribute('data-fk') : null;
    const idx = inside ? Array.from(box.querySelectorAll('li')).indexOf(a.closest('li')) : -1;
    fn();
    if (fk && idx >= 0) {
      const t = box.querySelectorAll('li')[idx];
      const n = t && t.querySelector('[data-fk="' + fk + '"]');
      if (n) n.focus({ preventScroll: true });
    }
  }
  function cgListNodes(s) {
    if (!s.containerGroups.length) return h('p', { class: 'muted small' }, 'No container instances yet');
    const shown = s.containerGroups.slice(0, MAX_TILE_CGS);
    const ul = h('ul', { class: 'pcgs', role: 'list' }, shown.map((cg) => {
      const canLink = cg.subscriptionId && cg.resourceGroup && cg.name;
      return h('li', null,
        h('span', { class: 'pcg-name' }, canLink ? link(cg.name, hashCG(cg), { 'data-fk': 'open' }) : clip(cg.name)),
        statePill(cg.state),
        cg.siteUrl ? browseLink(cg) : null);
    }));
    if (s.containerGroups.length > MAX_TILE_CGS) {
      ul.append(h('li', { class: 'muted small' }, '+' + (s.containerGroups.length - MAX_TILE_CGS) + ' more'));
    }
    return ul;
  }

  /**
   * Why a tile says "Needs attention": the failed event's message, else the terminated container names.
   * label is a text label (never colour alone); text is clamped by CSS, full is for the title attribute.
   */
  function attentionReason(s) {
    if (s.stage !== 'attention') return null;
    const ev = s.lastEvent;
    if (ev && ev.status.toLowerCase() === 'failed' && ev.message) return { label: 'Failed:', text: ev.message, full: ev.message };
    const dead = s.containerGroups.filter((c) => c.state === 'Terminated' && c.name).map((c) => c.name);
    if (!dead.length) return null;
    const text = dead.slice(0, 3).map(clip).join(', ') + (dead.length > 3 ? ' +' + (dead.length - 3) + ' more' : '');
    return { label: 'Container terminated:', text, full: dead.join(', ') };
  }

  function progressView() {
    let root, body, strip, stripRefs, sortCtl, grid, empty, gone = false, last = null, lastSummary = null;
    const tiles = new Map();   // user -> {li, r (refs), stage, sig, flashT}

    function buildTile() {
      const r = {
        name: h('h3', { class: 'ptile-name' }), badge: h('span', { class: 'ptile-badge' }), cgs: h('div', { class: 'ptile-cgs' }),
        rgs: h('p', { class: 'muted small ptile-meta' }), main: h('span'), ago: h('span'), fail: h('p', { class: 'ptile-fail', hidden: true }),
        reasonLabel: h('strong', { class: 'reason-label' }), reasonText: h('span', { class: 'reason-text' }),
      };
      r.reason = h('p', { class: 'ptile-reason', hidden: true }, r.reasonLabel, r.reasonText);
      r.last = h('p', { class: 'small ptile-last' }, r.main, r.ago);
      const li = h('li', { class: 'ptile' }, h('div', { class: 'ptile-head' }, r.name, r.badge), r.cgs, r.rgs, r.last, r.reason, r.fail);
      return { li, r, stage: null, sig: null, flashT: null };
    }
    function fillTile(rec, s, nowMs) {
      const r = rec.r;
      setText(r.name, clip(s.user));
      if (s.user.length > CLIP) r.name.title = s.user; else r.name.removeAttribute('title');
      rec.li.setAttribute('data-stage', s.stage);
      setSlot(r.badge, s.stage, () => stagePill(s.stage));
      const sig = JSON.stringify(s.containerGroups);
      if (sig !== rec.sig) { rec.sig = sig; keepFocus(r.cgs, () => r.cgs.replaceChildren(cgListNodes(s))); }
      setText(r.rgs, s.resourceGroups === 1 ? '1 resource group' : s.resourceGroups + ' resource groups');
      const ev = s.lastEvent;
      if (ev) {
        setText(r.main, 'Last: ' + [clip(ev.operation), ev.status].filter(Boolean).join(' · '));
        const ago = fmtAgo(ev.time, nowMs);
        setText(r.ago, ago ? ' · ' + ago : '');
        r.last.title = ev.operation + (ev.message ? ' — ' + ev.message : '');   // full text on hover
      } else {
        setText(r.main, 'No activity yet'); setText(r.ago, ''); r.last.removeAttribute('title');
      }
      const why = attentionReason(s);
      r.reason.hidden = !why;
      if (why) { setText(r.reasonLabel, why.label); setText(r.reasonText, why.text); r.reason.title = why.label + ' ' + why.full; }
      else { setText(r.reasonLabel, ''); setText(r.reasonText, ''); r.reason.removeAttribute('title'); }
      r.fail.hidden = s.failures <= 0;
      setText(r.fail, s.failures === 1 ? '1 failure in the last 15 minutes' : s.failures + ' failures in the last 15 minutes');
    }
    function flash(rec) {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      rec.li.classList.remove('pflash');
      void rec.li.offsetWidth;            // restart the animation if it is still running
      rec.li.classList.add('pflash');
      clearTimeout(rec.flashT);
      rec.flashT = setTimeout(() => rec.li.classList.remove('pflash'), FLASH_MS);
    }
    function ordered(students) {
      const items = students.map((s, i) => ({ s, i, t: Date.parse(s.lastEvent ? s.lastEvent.time : '') }));
      const mode = S.progressSort;
      if (mode === 'attention') items.sort((a, b) => STAGES[a.s.stage].rank - STAGES[b.s.stage].rank || a.i - b.i);
      else if (mode === 'recent') items.sort((a, b) => (Number.isNaN(b.t) ? -1 : b.t) - (Number.isNaN(a.t) ? -1 : a.t) || a.i - b.i);
      return items.map((x) => x.s);
    }
    /** Keyed in-place update: tiles are created once, edited field by field, and only moved when the order changes. */
    function renderTiles(p) {
      const nowMs = Number.isNaN(Date.parse(p.generatedAt)) ? Date.now() : Date.parse(p.generatedAt);
      const active = document.activeElement;
      const seen = new Set(), dupes = new Map();
      let prev = null;
      for (const s of ordered(p.students)) {
        let key = s.user;
        const n = dupes.get(key) || 0;
        dupes.set(key, n + 1);
        if (n) key += '#' + n;
        seen.add(key);
        let rec = tiles.get(key);
        const fresh = !rec;
        if (fresh) { rec = buildTile(); tiles.set(key, rec); }
        fillTile(rec, s, nowMs);
        if (!fresh && rec.stage !== s.stage) flash(rec);
        rec.stage = s.stage;
        const ref = prev ? prev.nextSibling : grid.firstChild;
        if (rec.li !== ref) grid.insertBefore(rec.li, ref);
        prev = rec.li;
      }
      for (const [k, rec] of tiles) {
        if (!seen.has(k)) { clearTimeout(rec.flashT); rec.li.remove(); tiles.delete(k); }
      }
      // moving a node drops focus in some browsers; put it back where it was
      if (active && active !== document.body && active.isConnected && document.activeElement !== active) active.focus({ preventScroll: true });
      empty.hidden = p.students.length !== 0;
      grid.hidden = p.students.length === 0;
      sortCtl.el.parentNode.hidden = p.students.length === 0;
    }
    function renderStrip(sm) {
      const parts = [];
      for (const k of STAGE_KEYS) {
        const text = k === 'running' ? sm[k] + ' of ' + sm.total + ' running' : sm[k] + ' ' + STAGES[k].summary;
        setText(stripRefs[k], text);
        parts.push(text);
      }
      // announced only when the numbers change, not on every poll
      const sentence = parts.join(' · ');
      if (lastSummary !== null && sentence !== lastSummary) announce('Class progress: ' + sentence);
      lastSummary = sentence;
    }

    return {
      title: 'Class progress', nav: 'progress',
      mount(r) {
        root = r;
        r.append(pageHeader('Class progress', { subtitle: 'Every student’s deployment, live. Facilitator only.' }).el);
        stripRefs = {};
        strip = h('ul', { class: 'pstrip', role: 'list', 'aria-label': 'Class summary' }, STAGE_KEYS.map((k) => {
          stripRefs[k] = h('span');
          return h('li', null, h('span', { class: 'pill ' + STAGES[k].pill }, h('span', { class: 'pill-dot', 'aria-hidden': 'true' }), stripRefs[k]));
        }));
        sortCtl = segmented('Sort students', PROGRESS_SORTS, () => S.progressSort, (v) => { S.progressSort = v; if (last) renderTiles(last); });
        grid = h('ul', { class: 'pgrid', role: 'list', 'aria-label': 'Students' });
        empty = h('div', { class: 'empty', hidden: true }, h('h2', null, 'No students yet'),
          h('p', null, 'The class roster is empty. Students appear here as soon as they are on the roster.'));
        body = h('div', { hidden: true },
          h('h2', { class: 'sr-only' }, 'Summary'), strip,
          h('div', { class: 'toolbar' }, h('span', { class: 'muted small', 'aria-hidden': 'true' }, 'Sort by'), sortCtl.el),
          h('h2', { class: 'sr-only' }, 'Students'), empty, grid);
        r.append(loadingNode(), body);
      },
      async load(signal) {
        const me = await loadMe(signal);
        if (!me.isFacilitator) return { me, forbidden: true };
        try {
          return { me, progress: normProgress(await api('admin/progress', { signal })) };
        } catch (e) {
          if (e instanceof ApiError && e.status === 403) return { me, forbidden: true };
          throw e;
        }
      },
      update(d) {
        clearLoading(root);
        if (d.forbidden) {
          // a student who typed #/progress by hand: the ordinary not-found page, not a broken board
          if (!gone) {
            gone = true;
            root.replaceChildren(...notFoundBody());
            setNav('');
            document.title = 'Page not found – Dojo Portal';
            const hd = root.querySelector('h1');
            if (hd && (!document.activeElement || document.activeElement === document.body)) hd.focus({ preventScroll: true });
          }
          return;
        }
        last = d.progress;
        body.hidden = false;
        sortCtl.sync();
        renderStrip(last.summary);
        renderTiles(last);
      },
      dispose() { for (const rec of tiles.values()) clearTimeout(rec.flashT); },
    };
  }

  // ---- activity log ----
  function activityView() {
    let root, table, countEl, empty, scopeCtl, host;
    return {
      title: 'Activity log', nav: 'activity',
      mount(r) {
        root = r;
        const ph = pageHeader('Activity log', { subtitle: 'Recent operations on your subscription, including changes made by OpenTofu and by this portal.' });
        r.append(ph.el);
        const tb = h('div', { class: 'toolbar' });
        scopeCtl = segmented('Activity scope', [['mine', 'Mine'], ['all', 'All students']], () => S.actScope, (v) => { S.actScope = v; reload(); });
        scopeCtl.el.hidden = true;
        countEl = h('p', { class: 'muted small grow', role: 'status' });
        tb.append(scopeCtl.el, countEl);
        host = h('div');
        empty = h('div', { class: 'empty', hidden: true }, h('h2', null, NOTHING_YET),
          h('p', null, 'Operations appear here as soon as you run ', h('code', null, 'terraform apply'), ' or change something in the portal.'));
        r.append(tb, loadingNode(), empty, host);
      },
      async load(signal) {
        const me = await loadMe(signal);
        const scope = me.isFacilitator ? S.actScope : 'mine';
        const a = await api('activity?scope=' + scope + '&limit=200', { signal });
        return { me, scope, events: objs(a.events).map(normEvent) };
      },
      update(d) {
        clearLoading(root);
        scopeCtl.el.hidden = !d.me.isFacilitator;
        scopeCtl.sync();
        if (!table) {
          table = makeTable({ label: 'Activity log', columns: activityColumns(false), keyOf: eventKey });
          host.append(table.el);
        }
        table.update(d.events, d.scope);
        empty.hidden = d.events.length !== 0;
        host.hidden = d.events.length === 0;
        setText(countEl, d.events.length ? d.events.length + ' event' + (d.events.length === 1 ? '' : 's') + ', newest first' : '');
      },
    };
  }

  // ---- home ----
  function homeView() {
    let root, refs = {}, recentTable, actTable, fac;
    return {
      title: 'Home', nav: 'home',
      mount(r) {
        root = r;
        r.append(pageHeader('Home', { subtitle: 'Your Dojo Cloud subscription at a glance.' }).el);
        refs.user = h('span', { class: 'big' });
        refs.subId = h('code');
        refs.subCopy = copyButton(() => refs.subId.textContent, 'Copy subscription id');
        refs.role = h('p', { class: 'muted small' });
        refs.qBig = h('p', { class: 'big', 'aria-hidden': 'true' });
        refs.qBar = h('progress', { class: 'quota', max: '1', value: '0', 'aria-label': 'Container groups used' });
        refs.qText = h('p', { class: 'muted small' });
        refs.rgCount = h('span', { class: 'big' });
        refs.cgCount = h('span', { class: 'big' });
        refs.runCount = h('p', { class: 'muted small' });
        refs.body = h('div', { hidden: true });
        refs.resTitle = h('h2', null, 'Resources');
        refs.body.append(h('div', { class: 'cards' },
          card('Subscription', refs.user, h('p', { class: 'small' }, 'Subscription ID'), h('div', { class: 'with-copy' }, refs.subId, ' ', refs.subCopy), refs.role),
          card('Quota', refs.qBig, refs.qBar, refs.qText),
          h('section', { class: 'card' }, refs.resTitle,
            h('p', null, refs.rgCount, ' ', h('span', { class: 'muted' }, 'resource groups')),
            h('p', null, refs.cgCount, ' ', h('span', { class: 'muted' }, 'container instances')),
            refs.runCount)));
        refs.empty = emptyState(NOTHING_YET);
        refs.empty.hidden = true;
        refs.body.append(refs.empty);

        recentTable = makeTable({
          label: 'Recent resources', keyOf: (i) => i.kind + '|' + i.id,
          columns: [
            { label: 'Name', rowHeader: true, cell: (i) => (i.kind === 'Resource group' ? rgNameCell(i) : cgNameCell(i)) },
            { label: 'Type', cls: 'nowrap', cell: (i) => i.kind },
            { label: 'Location', cls: 'nowrap', cell: (i) => dash(i.location) },
            { label: 'Status', cls: 'nowrap', cell: (i) => (i.kind === 'Container instance' ? statePill(i.state) : '\u2014') },
          ],
        });
        refs.recentSec = h('section', { class: 'card', hidden: true },
          h('div', { class: 'card-head' }, h('h2', null, 'Recent resources'), link('View all resources', '#/resources')), recentTable.el);
        actTable = makeTable({ label: 'Latest activity', columns: activityColumns(true), keyOf: eventKey });
        refs.actEmpty = h('p', { class: 'muted' }, 'No activity yet.');
        refs.actSec = h('section', { class: 'card' },
          h('div', { class: 'card-head' }, h('h2', null, 'Latest activity'), link('Open activity log', '#/activity')), refs.actEmpty, actTable.el);
        refs.facHost = h('div');
        refs.body.append(refs.recentSec, refs.actSec, refs.facHost);
        r.append(loadingNode(), refs.body);
      },
      async load(signal) {
        const scope = currentScope();
        const [me, ov, act] = await Promise.all([
          loadMe(signal), api('overview?scope=' + scope, { signal }),
          api('activity?scope=mine&limit=50', { signal }),
        ]);
        let cls = ov;
        if (me.isFacilitator && scope !== 'class') cls = await api('overview?scope=class', { signal });
        return { me, scope, ov: normOverview(ov), cls: normOverview(cls), events: objs(act.events).map(normEvent) };
      },
      update(d) {
        clearLoading(root);
        const { me, ov } = d;
        refs.body.hidden = false;
        setText(refs.resTitle, d.scope === 'class' ? 'Resources (whole class)' : 'Resources');
        setText(refs.user, me.user || '\u2014');
        setText(refs.subId, me.subscriptionId || '\u2014');
        setText(refs.role, me.isFacilitator ? 'You are signed in as the facilitator.' : 'Signed in as a student.');
        const used = me.used, limit = me.limit;
        if (used != null && limit != null && limit > 0) {
          setText(refs.qBig, used + ' / ' + limit);
          refs.qBar.max = limit; refs.qBar.value = Math.min(used, limit);
          refs.qBar.classList.toggle('full', used >= limit);
          setText(refs.qText, used + ' of ' + limit + ' container groups used' + (used >= limit ? ' \u2014 the quota is full; destroy something before creating more.' : '.'));
        } else {
          setText(refs.qBig, '\u2014'); refs.qBar.value = 0; setText(refs.qText, 'Quota information is not available.');
        }
        const running = ov.cgs.filter((c) => c.state === 'Running').length;
        setText(refs.rgCount, ov.rgs.length);
        setText(refs.cgCount, ov.cgs.length);
        setText(refs.runCount, ov.cgs.length ? running + ' running, ' + (ov.cgs.length - running) + ' not running' : '');
        const none = ov.rgs.length === 0 && ov.cgs.length === 0;
        refs.empty.hidden = !none;
        refs.recentSec.hidden = none;
        // recent = most recently touched in the activity log first, then the rest by name
        const order = new Map();
        d.events.forEach((e, i) => { const k = e.resourceId.toLowerCase(); if (k && !order.has(k)) order.set(k, i); });
        const all = ov.rgs.map((r) => Object.assign({ kind: 'Resource group' }, r)).concat(ov.cgs.map((c) => Object.assign({ kind: 'Container instance' }, c)));
        const rank = (i) => (order.has(i.id.toLowerCase()) ? order.get(i.id.toLowerCase()) : 1e6);
        all.sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
        recentTable.update(all.slice(0, 6), d.scope + me.isFacilitator);
        actTable.update(d.events.slice(0, 6), '');
        refs.actEmpty.hidden = d.events.length !== 0;
        actTable.el.hidden = d.events.length === 0;
        if (me.isFacilitator) {
          if (!fac) { fac = facilitatorPanel(); refs.facHost.append(fac.el); }
          fac.update(d);
        } else if (fac) { fac.el.remove(); fac = null; }
      },
      isEditing() { return !!(fac && fac.isEditing()); },
    };
  }

  // ---- facilitator panel (Home, facilitator only) ----
  function facilitatorPanel() {
    const scopeCtl = scopeSwitch();
    const sw = h('input', { type: 'checkbox', role: 'switch', id: 'fac-write', 'data-live': 'true' });
    const swMsg = h('p', { class: 'form-error', role: 'alert', hidden: true });
    const select = h('select', { id: 'fac-purge-sub', 'aria-describedby': 'fac-purge-help' });
    const purgeBtn = h('button', { type: 'button', class: 'btn btn-danger' }, 'Purge subscription\u2026');
    const purgeMsg = h('p', { class: 'form-ok', role: 'status', hidden: true });
    let optSig = '', swBusy = false, options = [];

    sw.addEventListener('change', async () => {
      const want = sw.checked;
      swBusy = true; sw.disabled = true; swMsg.hidden = true;
      try {
        const res = await api('admin/settings', { method: 'PUT', body: { writeActions: want } });
        const val = res && typeof res.writeActions === 'boolean' ? res.writeActions : want;
        if (S.me) S.me.writeActions = val;
        sw.checked = val;
        announce('Portal write actions ' + (val ? 'enabled' : 'disabled'));
      } catch (e) {
        sw.checked = !want;
        swMsg.textContent = errText(e); swMsg.hidden = false;
      } finally { swBusy = false; sw.disabled = false; }
    });

    function selected() { return options.find((o) => o.sub === select.value) || null; }
    purgeBtn.addEventListener('click', () => {
      const o = selected();
      if (!o) { select.focus(); return; }
      confirmDialog({
        title: 'Purge subscription?', danger: true, confirmLabel: 'Purge subscription',
        body: [
          h('p', null, 'This removes ', h('strong', null, o.cgs + ' container group' + (o.cgs === 1 ? '' : 's')), ' and ',
            h('strong', null, o.rgs + ' resource group' + (o.rgs === 1 ? '' : 's')), ' owned by ', h('strong', null, o.owner || 'this student'), '.'),
          h('p', { class: 'small muted' }, 'Subscription ' + o.sub),
          h('p', null, 'Their OpenTofu state will still list the deleted resources, so their next plan will show them as missing. This cannot be undone.'),
        ],
        run: async () => {
          const res = await api('admin/purge', { method: 'POST', body: { subscriptionId: o.sub } });
          const r = res && res.removed && typeof res.removed === 'object' ? res.removed : {};
          const msg = 'Purged ' + (num(r.containerGroups) ?? 0) + ' container groups and ' + (num(r.resourceGroups) ?? 0) + ' resource groups from ' + (o.owner || o.sub) + '.';
          purgeMsg.textContent = msg; purgeMsg.hidden = false;
          announce(msg);
          reload();
        },
      });
    });

    const node = h('section', { class: 'card facilitator-panel', 'aria-labelledby': 'fac-title' },
      h('div', { class: 'card-head' }, h('h2', { id: 'fac-title' }, 'Facilitator panel'), h('span', { class: 'badge' }, 'Facilitator')),
      h('div', { class: 'panel-grid' },
        h('div', null, h('h3', null, 'Whole-class overview'),
          h('p', { class: 'muted small' }, 'Switch the Home, resource, and container lists between your subscription and everyone\u2019s.'), scopeCtl.el),
        h('div', null, h('h3', null, 'Portal write actions'),
          h('p', { class: 'muted small' }, 'When off, students cannot delete containers or edit tags in the portal (tofu is unaffected).'),
          h('label', { class: 'inline-field', for: 'fac-write' }, sw, 'Students may delete and edit tags'), swMsg),
        h('div', null, h('h3', null, 'Purge subscription'),
          h('p', { class: 'muted small', id: 'fac-purge-help' }, 'Removes every container group and resource group in a student\u2019s subscription, e.g. after they deleted their state file.'),
          h('div', { class: 'field' }, h('label', { for: 'fac-purge-sub' }, 'Student subscription'), select), purgeBtn, h('div', null, purgeMsg))));

    return {
      el: node,
      isEditing: () => document.activeElement === select,
      update(d) {
        scopeCtl.sync();
        if (!swBusy) sw.checked = d.me.writeActions;
        const by = new Map();
        const get = (sub, owner) => { if (!by.has(sub)) by.set(sub, { sub, owner, cgs: 0, rgs: 0 }); const o = by.get(sub); if (!o.owner) o.owner = owner; return o; };
        d.cls.cgs.forEach((c) => { get(c.subscriptionId, c.owner).cgs++; });
        d.cls.rgs.forEach((r) => { get(r.subscriptionId, r.owner).rgs++; });
        options = sortBy(Array.from(by.values()), 'owner', 'sub');
        const sig = JSON.stringify(options);
        if (sig !== optSig) {
          optSig = sig;
          const keep = select.value;
          select.replaceChildren(h('option', { value: '' }, options.length ? 'Choose a student\u2026' : 'No student resources'),
            ...options.map((o) => h('option', { value: o.sub }, (o.owner || 'unknown') + ' \u2014 containers: ' + o.cgs + ', groups: ' + o.rgs)));
          if (options.some((o) => o.sub === keep)) select.value = keep;
        }
        purgeBtn.disabled = options.length === 0;
      },
    };
  }

  // ---- resource group blade ----
  function rgDetailView(p) {
    let root, refs = {}, table;
    return {
      title: 'Resource group ' + p.name, nav: 'rg',
      mount(r) {
        root = r;
        const ph = pageHeader(p.name, { crumb: h('span', null, link('Resource groups', '#/rg'), ' / Resource group') });
        refs.body = h('div', null, loadingNode());
        r.append(ph.el, refs.body);
      },
      async load(signal) {
        const scope = S.me && S.me.isFacilitator && (S.scope === 'class' || p.sub !== S.me.subscriptionId) ? 'class' : 'mine';
        const [me, ov] = await Promise.all([loadMe(signal), api('overview?scope=' + scope, { signal })]);
        return { me, ov: normOverview(ov) };
      },
      update(d) {
        const rg = d.ov.rgs.find((x) => x.subscriptionId === p.sub && x.name === p.name);
        if (!rg) {
          if (!refs.missing) {
            refs.missing = h('div', { class: 'empty' }, h('h2', null, 'Resource group not found'),
              h('p', null, 'It may have been destroyed, or it belongs to another subscription. '), link('Back to resource groups', '#/rg'));
            refs.body.replaceChildren(refs.missing); refs.content = null;
          }
          return;
        }
        if (!refs.content) {
          refs.dl = {};
          const dl = h('dl', { class: 'kv' });
          [['name', 'Name'], ['location', 'Location'], ['owner', 'Owner'], ['sub', 'Subscription'], ['tags', 'Tags']].forEach(([k, label]) => {
            refs.dl[k] = h('dd'); dl.append(h('dt', null, label), refs.dl[k]);
          });
          table = makeTable({
            label: 'Container instances in this resource group', keyOf: (c) => c.id || c.name,
            columns: [
              { label: 'Name', rowHeader: true, cell: cgNameCell },
              { label: 'Location', cls: 'nowrap', cell: (c) => dash(c.location) },
              { label: 'Status', cls: 'nowrap', cell: (c) => statePill(c.state) },
              { label: 'FQDN', cell: (c) => dash(c.fqdn) },
              { label: 'Browse', cls: 'nowrap', cell: (c) => browseLink(c) },
            ],
          });
          refs.none = h('p', { class: 'muted' }, 'This resource group has no container instances.');
          refs.content = h('div', null, card('Essentials', dl), card('Container instances', refs.none, table.el));
          refs.body.replaceChildren(refs.content); refs.missing = null;
        }
        setText(refs.dl.name, rg.name); setText(refs.dl.location, dash(rg.location));
        setText(refs.dl.owner, dash(rg.owner)); setText(refs.dl.sub, dash(rg.subscriptionId));
        setSlot(refs.dl.tags, JSON.stringify(rg.tags), () => chips(rg.tags, 30));
        const cgs = sortBy(d.ov.cgs.filter((c) => c.subscriptionId === p.sub && c.resourceGroup === p.name), 'name');
        table.update(cgs, String(d.me.isFacilitator));
        refs.none.hidden = cgs.length !== 0; table.el.hidden = cgs.length === 0;
      },
    };
  }

  // ---- tag editor ----
  function tagEditor(opts) {
    const rowsEl = h('div', { class: 'tag-rows' });
    const errEl = h('p', { class: 'form-error', role: 'alert', hidden: true });
    const okEl = h('p', { class: 'form-ok', role: 'status', hidden: true });
    const addBtn = h('button', { type: 'button', class: 'btn' }, 'Add tag');
    const saveBtn = h('button', { type: 'submit', class: 'btn btn-primary' }, 'Save tags');
    const resetBtn = h('button', { type: 'button', class: 'btn' }, 'Discard changes');
    const fieldset = h('fieldset', null, rowsEl, h('div', { class: 'form-actions' }, saveBtn, addBtn, resetBtn));
    const form = h('form', { 'aria-label': 'Edit tags', autocomplete: 'off' }, fieldset, errEl, okEl);
    let dirty = false, synced = '', saving = false, count = 0, serverTags = [];

    function addRow(k, v, focus) {
      count += 1;
      const kid = 'tag-k-' + count, vid = 'tag-v-' + count;
      const ki = h('input', { type: 'text', id: kid, 'aria-label': 'Tag name', placeholder: 'name', maxlength: '128', spellcheck: 'false', autocomplete: 'off' });
      const vi = h('input', { type: 'text', id: vid, 'aria-label': 'Tag value', placeholder: 'value', maxlength: '256', spellcheck: 'false', autocomplete: 'off' });
      ki.value = k; vi.value = v;
      const rm = h('button', { type: 'button', class: 'btn btn-small', 'aria-label': 'Remove tag' }, 'Remove');
      const row = h('div', { class: 'tag-row' }, ki, vi, rm);
      rm.addEventListener('click', () => {
        const next = row.nextElementSibling || row.previousElementSibling;
        row.remove(); markDirty();
        (next ? next.querySelector('input') : addBtn).focus();
      });
      ki.addEventListener('input', markDirty); vi.addEventListener('input', markDirty);
      rowsEl.append(row);
      if (focus) ki.focus();
    }
    function markDirty() { dirty = true; okEl.hidden = true; }
    function readRows() {
      return Array.from(rowsEl.children).map((r) => { const i = r.querySelectorAll('input'); return [i[0].value.trim(), i[1].value]; })
        .filter(([k, v]) => k !== '' || v !== '');
    }
    function fill(pairs) {
      rowsEl.replaceChildren();
      pairs.forEach(([k, v]) => addRow(k, v, false));
      if (!pairs.length) addRow('', '', false);
      dirty = false;
    }
    addBtn.addEventListener('click', () => { markDirty(); addRow('', '', true); });
    resetBtn.addEventListener('click', () => { fill(serverTags); errEl.hidden = true; okEl.hidden = true; announce('Changes discarded'); });
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      if (saving) return;
      const pairs = readRows();
      const keys = pairs.map(([k]) => k);
      if (pairs.some(([k]) => k === '')) { errEl.textContent = 'Every tag needs a name.'; errEl.hidden = false; return; }
      if (new Set(keys).size !== keys.length) { errEl.textContent = 'Tag names must be unique.'; errEl.hidden = false; return; }
      saving = true; saveBtn.disabled = true; errEl.hidden = true; okEl.hidden = true;
      try {
        const tags = await opts.save(Object.fromEntries(pairs));
        fill(tags); serverTags = tags; synced = JSON.stringify(tags);
        okEl.textContent = 'Tags saved.'; okEl.hidden = false; announce('Tags saved');
      } catch (e) {
        errEl.textContent = errText(e); errEl.hidden = false; // e.g. RequestDisallowedByPolicy ...
      } finally { saving = false; saveBtn.disabled = false; }
    });
    fill([]);
    return {
      el: form,
      isEditing() {
        const a = document.activeElement;
        return dirty || saving || (!!a && form.contains(a) && a.tagName === 'INPUT');
      },
      setTags(pairs) {
        serverTags = pairs;
        const sig = JSON.stringify(pairs);
        if (sig === synced || this.isEditing()) return;
        synced = sig; fill(pairs);
      },
      setEnabled(on) { fieldset.disabled = !on; },
    };
  }

  // ---- container instance blade ----
  function containerView(p) {
    const base = 'containers/' + enc(p.sub) + '/' + enc(p.rg) + '/' + enc(p.name);
    let root, r = {}, tab = 'overview', editor, logsSeq = 0, lastJson = '', cgKnown = null;

    function setLogs(text) {
      const pre = r.logsPre;
      if (pre.textContent === text) return;
      const atBottom = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 24;
      const top = pre.scrollTop;
      pre.textContent = text;
      pre.scrollTop = atBottom ? pre.scrollHeight : top;
    }
    async function fetchLogs(signal) {
      const seq = ++logsSeq;
      try {
        const res = await api(base + '/logs?tail=' + encodeURIComponent(r.tail.value), { signal });
        if (seq === logsSeq) { setLogs(logText(res.logs)); r.logsErr.hidden = true; setText(r.logsAt, 'Logs fetched ' + clock(new Date())); }
      } catch (e) {
        if (isAbort(e) || seq !== logsSeq) return;
        setText(r.logsErr, 'Could not load logs: ' + errText(e)); r.logsErr.hidden = false;
      }
    }
    function selectTab(id) {
      tab = id;
      r.tabs.forEach(([tid, btn, panel]) => {
        btn.setAttribute('aria-selected', String(tid === id));
        btn.tabIndex = tid === id ? 0 : -1;
        panel.hidden = tid !== id;
      });
      if (id === 'logs') fetchLogs();
    }

    return {
      title: 'Container instance ' + p.name, nav: 'containers',
      mount(rt) {
        root = rt;
        r.h1 = h('h1', { tabindex: '-1' }, p.name);
        r.pillSlot = h('span');
        r.browseSlot = h('span');
        r.delBtn = h('button', { type: 'button', class: 'btn btn-danger', 'aria-describedby': 'write-note' }, 'Delete');
        r.delBtn.addEventListener('click', openDelete);
        r.actions = h('div', { class: 'actions' }, r.browseSlot, r.delBtn);
        r.header = h('div', { class: 'page-header' },
          h('div', { class: 'grow' }, h('p', { class: 'breadcrumb' }, link('Container instances', '#/containers'), ' / Container instance'),
            h('div', { class: 'toolbar' }, r.h1, r.pillSlot)),
          r.actions);
        r.note = h('p', { class: 'note note-page', id: 'write-note', hidden: true }, WRITE_DISABLED_NOTE);
        r.problem = h('div', { class: 'empty', hidden: true }, h('h2', null, 'Container instance unavailable'));
        r.problemText = h('p'); r.problem.append(r.problemText, link('Back to container instances', '#/containers'));

        // overview
        const fields = {};
        const dl = h('dl', { class: 'kv' });
        [['rg', 'Resource group'], ['location', 'Location'], ['owner', 'Owner'], ['sub', 'Subscription'], ['fqdn', 'FQDN'], ['ip', 'IP address'],
          ['size', 'Size'], ['image', 'Image'], ['dns', 'DNS name label']].forEach(([k, label]) => { fields[k] = h('dd'); dl.append(h('dt', null, label), fields[k]); });
        fields.id = h('code', { class: 'mono' });
        dl.append(h('dt', null, 'Resource ID'), h('dd', null, h('div', { class: 'with-copy' }, fields.id, copyButton(() => fields.id.textContent, 'Copy resource ID'))));
        r.fields = fields;
        r.tagsRead = h('div');
        editor = tagEditor({ save: saveTags });
        r.tagsCard = card('Tags', h('p', { class: 'muted small' }, 'Policy requires the tags ', h('code', null, 'owner'), ' and ', h('code', null, 'env'), '. Saving replaces the whole tag set.'), r.tagsRead, editor.el);
        const overview = h('div', null, card('Essentials', dl), r.tagsCard);

        // json
        r.jsonPre = h('pre', { class: 'code', role: 'region', 'aria-label': 'Resource JSON', tabindex: '0' });
        const jsonPanel = h('div', null, h('div', { class: 'toolbar' },
          copyButton(() => r.jsonPre.textContent, 'Copy JSON'), h('span', { class: 'muted small' }, 'The ARM representation returned by the Dojo Cloud API.')), r.jsonPre);

        // logs
        r.tail = h('select', { id: 'logs-tail', 'data-live': 'true' }, [50, 100, 200, 500].map((n) => h('option', { value: n, selected: n === 200 }, String(n))));
        r.auto = h('input', { type: 'checkbox', id: 'logs-auto', checked: true, 'data-live': 'true' });
        r.logsErr = h('p', { class: 'form-error', role: 'alert', hidden: true });
        r.logsAt = h('span', { class: 'muted small' });
        const refreshBtn = h('button', { type: 'button', class: 'btn btn-small' }, 'Refresh logs');
        refreshBtn.addEventListener('click', () => { fetchLogs(); });
        r.tail.addEventListener('change', () => fetchLogs());
        r.logsPre = h('pre', { class: 'code wrap', role: 'region', 'aria-label': 'Container logs', tabindex: '0' });
        const logsPanel = h('div', null, h('div', { class: 'toolbar' }, refreshBtn,
          h('label', { class: 'inline-field', for: 'logs-tail' }, 'Lines', r.tail),
          h('label', { class: 'inline-field', for: 'logs-auto' }, r.auto, 'Auto-refresh'), r.logsAt), r.logsErr, r.logsPre);

        // tabs
        const defs = [['overview', 'Overview', overview], ['json', 'JSON view', jsonPanel], ['logs', 'Logs', logsPanel]];
        const tablist = h('div', { class: 'tablist', role: 'tablist', 'aria-label': 'Container instance sections' });
        r.tabs = defs.map(([id, label, panelBody]) => {
          const btn = h('button', { type: 'button', role: 'tab', id: 'tab-' + id, 'aria-controls': 'panel-' + id, 'aria-selected': 'false', tabindex: '-1' }, label);
          const panel = h('div', { role: 'tabpanel', id: 'panel-' + id, 'aria-labelledby': 'tab-' + id, hidden: true }, panelBody);
          btn.addEventListener('click', () => selectTab(id));
          tablist.append(btn);
          return [id, btn, panel];
        });
        tablist.addEventListener('keydown', (ev) => {
          const i = r.tabs.findIndex(([id]) => id === tab);
          let n = -1;
          if (ev.key === 'ArrowRight') n = (i + 1) % r.tabs.length;
          else if (ev.key === 'ArrowLeft') n = (i + r.tabs.length - 1) % r.tabs.length;
          else if (ev.key === 'Home') n = 0;
          else if (ev.key === 'End') n = r.tabs.length - 1;
          if (n < 0) return;
          ev.preventDefault(); selectTab(r.tabs[n][0]); r.tabs[n][1].focus();
        });
        r.content = h('div', { hidden: true }, tablist, r.tabs.map((t) => t[2]));
        rt.append(r.header, r.note, r.problem, loadingNode(), r.content);
        selectTab('overview');
      },
      async load(signal) {
        const meP = loadMe(signal);
        meP.catch(() => {});
        let detail = null, problem = null;
        try { detail = await api(base, { signal }); } catch (e) {
          if (isAbort(e)) throw e;
          if (e instanceof ApiError && (e.status === 404 || e.status === 403)) problem = e; else throw e;
        }
        const me = await meP;
        let logs;
        if (detail && tab === 'logs' && r.auto.checked) {
          const seq = ++logsSeq;
          try { logs = { seq, text: logText((await api(base + '/logs?tail=' + encodeURIComponent(r.tail.value), { signal })).logs) }; } catch (e) { if (isAbort(e)) throw e; logs = { seq, error: errText(e) }; }
        }
        return { me, detail, problem, logs };
      },
      update(d) {
        clearLoading(root);
        if (!d.detail) {
          r.content.hidden = true; r.actions.hidden = true; r.pillSlot.replaceChildren(); r.pillSlot.removeAttribute('data-sig');
          r.problem.hidden = false;
          setText(r.problemText, d.problem && d.problem.status === 403
            ? 'Details are only available to the owner of this container instance.'
            : 'This container instance does not exist (any more). It may have been removed by tofu destroy or by a facilitator.');
          return;
        }
        r.problem.hidden = true; r.content.hidden = false; r.actions.hidden = false;
        const cg = normCG(d.detail.summary && typeof d.detail.summary === 'object' ? d.detail.summary : {});
        cgKnown = cg;
        setSlot(r.pillSlot, cg.state, () => statePill(cg.state));
        setSlot(r.browseSlot, cg.siteUrl, () => browseLink(cg, 'btn btn-primary'));
        const f = r.fields;
        setSlot(f.rg, cg.resourceGroup + '|' + cg.subscriptionId, () => link(cg.resourceGroup, '#/rg/' + enc(cg.subscriptionId) + '/' + enc(cg.resourceGroup)));
        setText(f.location, dash(cg.location)); setText(f.owner, dash(cg.owner)); setText(f.sub, dash(cg.subscriptionId));
        setText(f.fqdn, dash(cg.fqdn)); setText(f.ip, dash(cg.ip)); setText(f.size, fmtSize(cg)); setText(f.image, dash(cg.image));
        setText(f.dns, dash(cg.dnsLabel)); setText(f.id, cg.id || '\u2014');
        const canWrite = cg.isMine || d.me.isFacilitator;
        const enabled = canWrite && (d.me.writeActions || d.me.isFacilitator);
        r.delBtn.hidden = !canWrite; r.delBtn.disabled = !enabled;
        r.note.hidden = !(canWrite && !enabled);
        editor.el.hidden = !canWrite;
        editor.setEnabled(enabled);
        setSlot(r.tagsRead, canWrite ? 'x' : JSON.stringify(cg.tags), () => (canWrite ? null : chips(cg.tags, 50)));
        if (canWrite) editor.setTags(cg.tags);
        const json = JSON.stringify(d.detail.arm === undefined ? null : d.detail.arm, null, 2);
        if (json !== lastJson) { lastJson = json; r.jsonPre.textContent = json; }
        if (d.logs && d.logs.seq === logsSeq) {
          if (d.logs.error) { setText(r.logsErr, 'Could not load logs: ' + d.logs.error); r.logsErr.hidden = false; }
          else { setLogs(d.logs.text); r.logsErr.hidden = true; setText(r.logsAt, 'Logs fetched ' + clock(new Date())); }
        }
      },
      isEditing() { return !!editor && editor.isEditing(); },
      dispose() { logsSeq += 1; },
    };

    async function saveTags(tags) {
      const res = await api(base, { method: 'PATCH', body: { tags } });
      reloadSoon();
      return res.summary && typeof res.summary === 'object' ? normCG(res.summary).tags : tagPairs(tags);
    }
    function reloadSoon() { setTimeout(() => { if (current && current.title === 'Container instance ' + p.name) reload(); }, 300); }
    function openDelete() {
      if (!cgKnown) return;
      confirmDialog({
        title: 'Delete container instance?', danger: true, confirmLabel: 'Delete container instance',
        body: [
          h('p', null, 'You are about to delete ', h('strong', null, p.name), ' in resource group ', h('strong', null, p.rg), '.'),
          h('p', null, 'This creates drift: your OpenTofu code and state still describe this container, so OpenTofu will notice on the next plan and offer to create it again.'),
        ],
        run: async () => {
          await api(base, { method: 'DELETE' });
          announce('Deleted container instance ' + p.name);
          location.hash = '#/containers';
        },
      });
    }
  }

  // ---- not found ----
  function notFoundBody() {
    return [pageHeader('Page not found').el, h('p', null, 'There is no such page. ', link('Go to Home', '#/'))];
  }
  function notFoundView() {
    return {
      title: 'Page not found', nav: '',
      mount(r) { r.append(...notFoundBody()); },
      async load(signal) { await loadMe(signal); return {}; },
      update() {},
    };
  }

  // =================================================================== router
  const SEG = /^[^/]+$/;
  const bad = (s) => !s || s === '.' || s === '..' || !SEG.test(s);
  function parseHash() {
    let hash = location.hash;
    if (!hash.startsWith('#/')) hash = '#/';
    const parts = hash.slice(2).split('/').map((s) => { try { return decodeURIComponent(s); } catch (e) { return s; } });
    while (parts.length && parts[parts.length - 1] === '') parts.pop();
    return parts;
  }
  function resolve(parts) {
    const [a, b, c, d] = parts;
    if (!a && parts.length === 0) return homeView();
    if (a === 'rg' && parts.length === 1) return rgListView();
    if (a === 'rg' && parts.length === 3 && !bad(b) && !bad(c)) return rgDetailView({ sub: b, name: c });
    if (a === 'resources' && parts.length === 1) return resourcesView();
    if (a === 'containers' && parts.length === 1) return containersView();
    if (a === 'containers' && parts.length === 4 && !bad(b) && !bad(c) && !bad(d)) return containerView({ sub: b, rg: c, name: d });
    if (a === 'activity' && parts.length === 1) return activityView();
    if (a === 'class' && parts.length === 1) return classView();
    if (a === 'progress' && parts.length === 1) return progressView();
    return notFoundView();
  }
  function setNav(key) {
    el.nav.querySelectorAll('a[data-nav]').forEach((a) => {
      if (a.getAttribute('data-nav') === key) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
  }
  function navigate() {
    closeActiveDialog();
    if (inflight) { inflight.abort(); inflight = null; }
    clearTimeout(pollTimer);
    if (current && current.dispose) current.dispose();
    routeToken += 1;
    const view = resolve(parseHash());
    current = view;
    el.view.replaceChildren();
    view.mount(el.view);
    setNav(view.nav);
    document.title = view.title + ' \u2013 Dojo Portal';
    setPaused(false);
    closeMenu();
    window.scrollTo(0, 0);
    const heading = el.view.querySelector('h1');
    if (heading && !firstRoute) heading.focus({ preventScroll: true });
    if (!firstRoute) announce(view.title);
    firstRoute = false;
    refresh();
  }

  // =================================================================== chrome wiring
  function closeMenu() {
    el.nav.classList.remove('open');
    el.navToggle.setAttribute('aria-expanded', 'false');
  }
  function init() {
    el.navToggle.addEventListener('click', () => {
      const open = !el.nav.classList.contains('open');
      el.nav.classList.toggle('open', open);
      el.navToggle.setAttribute('aria-expanded', String(open));
      if (open) { const a = el.nav.querySelector('a'); if (a) a.focus(); }
    });
    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && el.nav.classList.contains('open') && !activeDialog) { closeMenu(); el.navToggle.focus(); }
    });
    $('skip-link').addEventListener('click', (ev) => { ev.preventDefault(); el.main.focus(); });
    $('refresh-btn').addEventListener('click', () => reload());
    $('banner-retry').addEventListener('click', () => reload());
    window.addEventListener('hashchange', navigate);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible' && waitingForVisible) { waitingForVisible = false; if (!busyEditing()) refresh(); else schedule(); }
    });
    navigate();
  }

  init();
})();
