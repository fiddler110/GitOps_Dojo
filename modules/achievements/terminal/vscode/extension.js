// Shows the student's achievement toasts in VS Code (achievements module, phase 8).
// Runs in the student's own code-server, which shares the terminal's network and home, so it
// asks the service the way `dojo-check` does: with the student's own Forgejo token from
// ~/.git-credentials (Forgejo confirms it). Read-only: it only claims toasts for surface "vscode",
// and each toast is delivered once, on the first surface that picks it up. Never throws.
'use strict';
const vscode = require('vscode');
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');

const BASE = process.env.ACHIEVEMENTS_URL || 'http://achievements:8080';
const HOST = 'git-server:3000';
const EVERY_MS = 4000;

function token() {
  try {
    const lines = fs.readFileSync(path.join(os.homedir(), '.git-credentials'), 'utf8').split('\n');
    for (const raw of lines) {
      const line = raw.trim().replace(/%3a/gi, ':');  // git may percent-encode the port
      if (line.startsWith('http://') && line.endsWith('@' + HOST)) {
        return line.slice('http://'.length, -('@' + HOST).length).split(':').slice(1).join(':');
      }
    }
  } catch (e) { /* not provisioned yet */ }
  return null;
}

function fetchToasts(tok, cb) {
  const req = http.get(BASE + '/api/toasts?surface=vscode', { headers: { Authorization: 'token ' + tok }, timeout: 3000 }, (res) => {
    let body = '';
    res.setEncoding('utf8');
    res.on('data', (d) => { body += d; if (body.length > 65536) { req.destroy(); } });
    res.on('end', () => {
      try { cb(res.statusCode === 200 ? (JSON.parse(body).toasts || []) : []); } catch (e) { cb([]); }
    });
  });
  req.on('timeout', () => req.destroy());
  req.on('error', () => cb([]));
}

function points(t) {
  if (t.points > 0) { return ' +' + t.points; }
  if (t.points < 0) { return ' ' + t.points; }
  return '';
}

function show(t) {
  const funny = t.kind === 'funny';
  const text = (funny ? '😜 ' : '🏆 ') + (t.title || 'Achievement') + points(t) + (t.joke ? ' — ' + t.joke : '');
  if (t.points < 0) { vscode.window.showWarningMessage(text); } else { vscode.window.showInformationMessage(text); }
}

function activate(context) {
  let busy = false;
  const timer = setInterval(() => {
    if (busy) { return; }
    const tok = token();
    if (!tok) { return; }
    busy = true;
    fetchToasts(tok, (toasts) => {
      busy = false;
      const list = toasts.slice(0, 5);
      list.forEach(show);
      if (toasts.length > 5) { vscode.window.showInformationMessage('🏆 ' + toasts.length + ' more achievements: see your landing page.'); }
    });
  }, EVERY_MS);
  context.subscriptions.push({ dispose: () => clearInterval(timer) });
}

function deactivate() {}

module.exports = { activate, deactivate };
