// Pops up the facilitator's answer to a raised hand in VS Code (sensei module).
// Runs in the student's own code-server, which shares the terminal's network and home, so it asks Sensei the
// way the `sensei` command does: with the student's own Forgejo token from ~/.git-credentials. It long-polls
// /api/student/notify for surface "vscode" (held open up to 25 s, answered the moment the facilitator replies),
// shows each reply as a message with a Reply button, and posts the student's answer to /api/student/reply.
// The text is shown through VS Code's message API only, never as HTML. Never throws.
'use strict';
const vscode = require('vscode');
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');

const BASE = new URL(process.env.SENSEI_URL || 'http://sensei:8080');
const HOST = 'git-server:3000';

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

function post(tok, route, body, timeoutMs, cb) {
  const data = JSON.stringify(body);
  const req = http.request({ hostname: BASE.hostname, port: BASE.port || 80, path: route, method: 'POST', timeout: timeoutMs,
    headers: { Authorization: 'token ' + tok, 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } }, (res) => {
    let out = '';
    res.setEncoding('utf8');
    res.on('data', (d) => { out += d; if (out.length > 65536) { req.destroy(); } });
    res.on('end', () => {
      try { cb(res.statusCode === 200 ? JSON.parse(out) : null); } catch (e) { cb(null); }
    });
  });
  req.on('timeout', () => req.destroy());
  req.on('error', () => cb(null));
  req.end(data);
}

function show(tok, r) {
  vscode.window.showInformationMessage('🥋 The facilitator answered your request #' + r.id + ': ' + r.text, 'Reply').then((pick) => {
    if (pick !== 'Reply') { return; }
    vscode.window.showInputBox({ prompt: 'Your reply to the facilitator (request #' + r.id + ')', placeHolder: r.text.slice(0, 80) }).then((text) => {
      if (!text || !text.trim()) { return; }
      post(tok, '/api/student/reply', { id: r.id, text: text.trim() }, 5000, (doc) => {
        if (doc && doc.ok) { vscode.window.showInformationMessage('🥋 Sent. The facilitator will see it.'); }
        else { vscode.window.showWarningMessage('🥋 Couldn\'t send that. Try `sensei reply ' + r.id + ' "..."` in the terminal.'); }
      });
    });
  });
}

function activate(context) {
  let stopped = false, timer = null;
  const loop = () => {
    if (stopped) { return; }
    const tok = token();
    if (!tok) { timer = setTimeout(loop, 10000); return; }
    post(tok, '/api/student/notify', { surface: 'vscode', wait: 25 }, 30000, (doc) => {
      if (doc && Array.isArray(doc.replies)) {
        doc.replies.slice(0, 5).forEach((r) => show(tok, r));
        timer = setTimeout(loop, 200);
      } else {
        timer = setTimeout(loop, 10000);  // Sensei absent or not ready: back off
      }
    });
  };
  loop();
  context.subscriptions.push({ dispose: () => { stopped = true; if (timer) { clearTimeout(timer); } } });
}

function deactivate() {}

module.exports = { activate, deactivate };
