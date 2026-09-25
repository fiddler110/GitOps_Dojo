"""Loaded via FLASK_CONF (see Dockerfile) on top of docker_config.py/env vars.

Only one setting needed here: REMOTE_AUTH_METHOD is not one of the
Setting-table-backed keys AppSettings.load_environment() reads from the
environment (grep powerdnsadmin/lib/settings.py -- it isn't in the
`defaults`/`types` dicts at all), so it can't be set the way every other
setting in this module is. routes/base.py's trusted-remote-user path picks
the auth method to validate with as
``'LOCAL' if session.get('remote_user') else current_app.config.get('REMOTE_AUTH_METHOD', 'LDAP')``,
and the request-loader path never populates that session key (only a full
form login does), so without this it would try to validate the facilitator
account via 'LDAP' on every request and fail closed. Forcing 'LOCAL' makes
it validate against the local `user` table row the seed script creates,
which is what we want: trust_user=True already skips the password check
entirely for that method.
"""
REMOTE_AUTH_METHOD = 'LOCAL'

# Hardening. Everything below overrides powerdnsadmin/default_config.py.
import os

# default_config.py ships one SECRET_KEY shared by every PowerDNS-Admin install
# (it signs sessions and CSRF tokens). dojo-entrypoint.sh makes a random one per
# container start, once, so every gunicorn worker shares it.
SECRET_KEY = os.environ['DOJO_SECRET_KEY']

# Own cookie names, scoped to our mount: the lab shares one origin, so a generic
# "session" on Path=/ would be sent to (and could be clobbered by) every other app.
SESSION_COOKIE_NAME = 'dns_admin_session'
SESSION_COOKIE_PATH = os.environ.get('PATH_PREFIX', '/dns-admin')
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
# CSRF cookie keeps its default name: Flask-SeaSurf uses CSRF_COOKIE_NAME as the
# form/JSON field name too, and PowerDNS-Admin's pages hard-code "_csrf_token"
# (renaming it made every save a 403). The path scoping is what matters.
CSRF_COOKIE_PATH = SESSION_COOKIE_PATH
CSRF_COOKIE_SAMESITE = 'Strict'
REMEMBER_COOKIE_NAME = 'dns_admin_remember'
REMEMBER_COOKIE_PATH = SESSION_COOKIE_PATH
