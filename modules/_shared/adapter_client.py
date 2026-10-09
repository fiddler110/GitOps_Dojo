"""How a module tells the achievements service what a student did: one signed POST per
event to its adapter endpoint, best effort.

One copy, here, shared like dojo_http.py: a module lists it in its module.env
(SHARED="<context>/adapter_client.py") and ./dojo copies it into <context>/_shared/.

Off unless both the URL and the secret are set (ACHIEVEMENTS_ADAPTER_URL and
ACHIEVEMENTS_ADAPTER_SECRET). Each event is {"source": <module>, "event", "user", ...},
compact JSON, signed with the shared secret (HMAC-SHA256 of the raw body, hex, header
X-Adapter-Signature). Posts go through one bounded queue and one worker thread that
swallows every error: reporting must never slow down or break the request that caused
it, so a full queue drops the event instead of waiting. Stdlib only.
"""
import hashlib
import hmac
import json
import queue
import threading
import urllib.request


class AdapterClient:
    def __init__(self, url, secret, source, timeout=2, send=None, size=500):
        """SEND(raw, sig) replaces the HTTP POST (tests). SIZE: events held before new ones drop."""
        self.url, self.secret, self.source, self.timeout = url, secret, source, timeout
        self.enabled = bool(url and secret)
        self._send = send or self._post
        self.queue = queue.Queue(maxsize=size)
        self._lock = threading.Lock()
        self._worker = None

    def _post(self, raw, sig):
        req = urllib.request.Request(self.url, data=raw, method="POST", headers={
            "Content-Type": "application/json", "X-Adapter-Signature": sig})
        urllib.request.urlopen(req, timeout=self.timeout).read()

    def sign(self, raw):
        return hmac.new(self.secret.encode(), raw, hashlib.sha256).hexdigest()

    def _run(self):
        while True:
            raw = self.queue.get()
            try:
                self._send(raw, self.sign(raw))
            except Exception:  # noqa: BLE001 - reporting is best effort
                pass
            finally:
                self.queue.task_done()

    def _start(self):
        with self._lock:
            if self._worker is None:
                self._worker = threading.Thread(target=self._run, name="adapter-client", daemon=True)
                self._worker.start()

    def post(self, doc):
        """Queue one event (DOC plus "source"). True if queued; never raises, never blocks."""
        if not self.enabled:
            return False
        try:
            raw = json.dumps(dict(doc, source=self.source), separators=(",", ":")).encode()
            self._start()
            self.queue.put_nowait(raw)
            return True
        except Exception:  # noqa: BLE001 - queue.Full, or a doc that isn't JSON
            return False

    def flush(self):
        """Wait until every queued event has been sent or given up on (tests, shutdown)."""
        if self._worker is not None:
            self.queue.join()
