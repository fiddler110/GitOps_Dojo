"""WSGI entry point gunicorn loads instead of ``powerdnsadmin:create_app()``.

Three jobs, done here instead of by patching PowerDNS-Admin's own source:

1. Mount the real app under ``PATH_PREFIX`` (default ``/dns-admin``) using
   Werkzeug's ``DispatcherMiddleware``, which rewrites ``SCRIPT_NAME``/
   ``PATH_INFO`` per request. Because PowerDNS-Admin builds every link,
   redirect and static-asset URL with Flask's ``url_for()``, and ``url_for``
   always honours the request's ``SCRIPT_NAME``, this is what actually makes
   the app usable behind a gateway that does *not* strip the prefix -- no
   template or JS edits needed. (A prior spike proxying the stock app with
   plain path-stripping found redirects and CSS/JS coming back rooted at
   ``/`` instead of the mount point; mounting it this way is the fix.)

2. Enforce the gateway's contract before any request reaches the app:
   every request must carry a valid ``X-Gateway-Token`` (except the health
   check), and is trusted as the facilitator only if ``X-Auth-User`` matches
   ``FACILITATOR_USERNAME`` exactly. Any client-supplied ``REMOTE_USER`` is
   dropped first, then set ourselves from the validated header, which is
   what PowerDNS-Admin's own "trusted remote user" login
   (``routes/base.py``) reads.

3. Answer ``{PATH_PREFIX}/healthz`` with a plain 200, without touching the
   database or going through auth, so the container's HEALTHCHECK doesn't
   need the gateway token.

This module intentionally does not import anything from ``powerdnsadmin``
at parse time other than ``create_app`` -- by the time gunicorn imports this
file, the entrypoint has already run migrations and the seed script, so
building the real app here is safe.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# dojo_http: modules/_shared/ in the source tree, ./_shared/ once ./dojo has copied it (SHARED= in module.env).
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared")]
import dojo_http  # noqa: E402
from flask import session
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from powerdnsadmin import create_app

PATH_PREFIX = (os.environ.get('PATH_PREFIX', '/dns-admin') or '/dns-admin').rstrip('/')
if not PATH_PREFIX.startswith('/'):
    PATH_PREFIX = '/' + PATH_PREFIX

GATEWAY_TOKEN = os.environ.get('GATEWAY_TOKEN', '')
FACILITATOR_USERNAME = os.environ.get('FACILITATOR_USERNAME', 'root')
HEALTHZ_PATH = PATH_PREFIX + '/healthz'

# Built once, at worker-import time (after migrations + seeding, per the
# entrypoint). If this raises, the gunicorn worker fails to boot and the
# HEALTHCHECK correctly sees a closed port instead of a false "ok".
_inner_app = create_app()


@_inner_app.before_request
def _default_authentication_type():
    # routes/index.py's login() view sets session['authentication_type']
    # before handing off to authenticate_user(); our trusted-header login
    # goes through flask_login's lighter request_loader path instead
    # (routes/base.py's login_via_authorization_header_or_remote_user) and
    # never touches the session at all. At least one endpoint --
    # routes/user.py's avatar image -- reads session['authentication_type']
    # with no default and 500s without it. setdefault() only fills the gap
    # our path leaves; it never overrides a value a real form/OAuth/LDAP
    # login already set.
    session.setdefault('authentication_type', 'LOCAL')


def _plain(status, body=b''):
    def responder(environ, start_response):
        start_response(status, [
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Length', str(len(body))),
        ])
        return [body]
    return responder


_not_found = _plain('404 Not Found', b'not found')
_forbidden = _plain('403 Forbidden', b'forbidden')
_ok = _plain('200 OK', b'ok')

_mounted = DispatcherMiddleware(_not_found, {PATH_PREFIX: _inner_app})


def _redirect_to_slash(environ, start_response):
    start_response('302 Found', [('Location', PATH_PREFIX + '/'), ('Content-Length', '0')])
    return [b'']


def _token_ok(environ):
    if not GATEWAY_TOKEN:
        # Fail closed: an unset token must never be treated as "no check".
        return False
    return dojo_http.token_ok(environ.get('HTTP_X_GATEWAY_TOKEN', ''), GATEWAY_TOKEN)


# Added to every response, ours and PowerDNS-Admin's: dojo_http's set, but not its
# full CSP, since PowerDNS-Admin's pages use inline scripts and styles (it's reachable
# only by the facilitator through the gateway). Its Referrer-Policy stays same-origin.
SECURITY_HEADERS = list(dojo_http.headers({
    'Content-Security-Policy': "frame-ancestors 'self'; base-uri 'self'; form-action 'self'",
    'Referrer-Policy': 'same-origin',
}).items())
_SECURITY_HEADER_NAMES = {name.lower() for name, _ in SECURITY_HEADERS}


def application(environ, start_response):
    def secured_start_response(status, headers, exc_info=None):
        headers = [(k, v) for k, v in headers if k.lower() not in _SECURITY_HEADER_NAMES] + SECURITY_HEADERS
        return start_response(status, headers, exc_info)
    return _route(environ, secured_start_response)


def _route(environ, start_response):
    # Always strip any client-supplied REMOTE_USER before anything else,
    # regardless of what path or method this turns out to be.
    environ.pop('REMOTE_USER', None)

    path = environ.get('PATH_INFO') or '/'
    method = environ.get('REQUEST_METHOD', 'GET')

    # Token-free health check: exact path, GET only, no auth.
    if method == 'GET' and path == HEALTHZ_PATH:
        return _ok(environ, start_response)

    # Outside our mount point entirely: 404, no need to even look at auth.
    if path != PATH_PREFIX and not path.startswith(PATH_PREFIX + '/'):
        return _not_found(environ, start_response)

    # Everything else within the mount must carry a valid gateway token.
    if not _token_ok(environ):
        return _forbidden(environ, start_response)

    # ... and be the one named facilitator account, or it's a 403 too --
    # this container has no student-visible identity at all.
    auth_user = environ.get('HTTP_X_AUTH_USER', '')
    if not auth_user or auth_user != FACILITATOR_USERNAME:
        return _forbidden(environ, start_response)

    environ['REMOTE_USER'] = auth_user

    if path == PATH_PREFIX:
        return _redirect_to_slash(environ, start_response)

    return _mounted(environ, start_response)
