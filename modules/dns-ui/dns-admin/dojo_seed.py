"""Idempotent seed step, run by the entrypoint after migrations, before
gunicorn starts serving.

Settings (pdns_api_url, pdns_api_key, signup_enabled, local_db_enabled,
remote_user_enabled, remote_user_logout_url) are actually enforced by the
matching environment variables the entrypoint exports (PDNS_API_URL,
PDNS_API_KEY, ...): PowerDNS-Admin's ``Setting.get()``
(powerdnsadmin/models/setting.py) checks ``current_app.config`` *before* the
database row, and ``AppSettings.load_environment()`` (lib/settings.py)
copies any environment variable named after a setting straight into
``current_app.config`` at app-creation time. So the env vars are what
actually wins on every request, for as long as this container runs --which
is the point: it means a curious facilitator poking at the admin settings
UI can't accidentally repoint this at a different PowerDNS server or turn
signup back on. This script still writes the same values into the
`setting` table below, purely so the database reflects reality if anyone
inspects it directly or the env-vs-db precedence ever changes upstream; it
is not what enforces anything.

The one thing that *has* to be a real database row is the facilitator's
user account: PowerDNS-Admin has no environment-variable equivalent for
"create this user". Its password is random and discarded immediately --
login only ever happens through the trusted X-Auth-User path (see
dojo_wsgi.py / dojo_config.py), which bypasses the password check
entirely (`trust_user=True`), so no one, including this script, needs to
know it.
"""
import os
import secrets
import sys

from powerdnsadmin import create_app
from powerdnsadmin.models.base import db
from powerdnsadmin.models.role import Role
from powerdnsadmin.models.setting import Setting
from powerdnsadmin.models.user import User


def _settings_snapshot(app):
    """Mirror the env-var-derived config into the setting table (see module
    docstring: this is a record, not the enforcement mechanism)."""
    return {
        'pdns_api_url': app.config.get('PDNS_API_URL', ''),
        'pdns_api_key': app.config.get('PDNS_API_KEY', ''),
        'signup_enabled': 'False',
        'local_db_enabled': 'False',
        'remote_user_enabled': 'True',
        'remote_user_logout_url': app.config.get('REMOTE_USER_LOGOUT_URL', '/admin'),
    }


def main():
    app = create_app()
    with app.app_context():
        for name, value in _settings_snapshot(app).items():
            row = Setting.query.filter_by(name=name).first()
            if row is None:
                db.session.add(Setting(name=name, value=str(value)))
            else:
                row.value = str(value)
        db.session.commit()

        facilitator_username = os.environ.get('FACILITATOR_USERNAME', 'root')
        admin_role = Role.query.filter_by(name='Administrator').first()
        if admin_role is None:
            print('dojo_seed: no Administrator role found; did migrations run?',
                  file=sys.stderr)
            sys.exit(1)

        random_password = secrets.token_hex(32)
        user = User.query.filter_by(username=facilitator_username).first()
        if user is None:
            user = User(username=facilitator_username)
            db.session.add(user)
        user.password = user.get_hashed_password(random_password)
        user.firstname = 'Facilitator'
        user.lastname = ''
        user.email = None
        user.confirmed = 1
        user.role_id = admin_role.id
        db.session.commit()
        del random_password

        print('dojo_seed: settings recorded, facilitator user "{0}" is Administrator'
              .format(facilitator_username), flush=True)


if __name__ == '__main__':
    main()
