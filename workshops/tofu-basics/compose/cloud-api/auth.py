"""Identity for Dojo Cloud: who is calling, and which subscription is theirs.

Every roster member (studentNN, botNN, the facilitator) gets:
  * a deterministic "service principal" client id (uuid5)   -> ARM_CLIENT_ID
  * a deterministic subscription id (uuid5)                  -> ARM_SUBSCRIPTION_ID
  * a client secret = HMAC(signing_key, username)            -> ARM_CLIENT_SECRET
The terminal-side broker (root-owned, SO_PEERCRED) hands each Linux user only
their own values; this side recomputes and verifies them. The signing key lives
in a root-only file in the cloud_secrets volume, never in a student-visible
environment.
"""
import base64
import hashlib
import hmac
import json
import time
import uuid

NAMESPACE = uuid.UUID("6f0d4a1e-5b1c-4d55-9a3e-0d0a0c10a1b1")
TENANT_ID = "5f2c1a40-7d3e-4b6a-9c11-3a7e2d9b8f10"
TOKEN_TTL = 3600


def app_id(username):
    return str(uuid.uuid5(NAMESPACE, "app:" + username))


def subscription_id(username):
    return str(uuid.uuid5(NAMESPACE, "sub:" + username))


def client_secret(key, username):
    digest = hmac.new(key, ("client-secret:" + username).encode(), hashlib.sha256)
    return "dojo~" + digest.hexdigest()[:40]


def roster(env):
    """All usernames that may hold credentials, from the same env the engine uses."""
    users = []
    for prefix_var, count_var, default_prefix in (
        ("STUDENT_PREFIX", "STUDENT_COUNT", "student"),
        ("BOT_PREFIX", "BOT_COUNT", "testuser"),
    ):
        prefix = env.get(prefix_var, default_prefix)
        try:
            count = int(env.get(count_var, "0") or 0)
        except ValueError:
            count = 0
        users += [f"{prefix}{n:02d}" for n in range(1, count + 1)]
    fac = env.get("FACILITATOR_USERNAME", "root")
    if fac:
        users.append(fac)
    return users


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Auth:
    def __init__(self, key, users, facilitator, issuer):
        self.key = key
        self.users = list(users)
        self.facilitator = facilitator
        self.issuer = issuer
        self.by_app_id = {app_id(u): u for u in self.users}
        self.by_subscription = {subscription_id(u): u for u in self.users}

    def is_facilitator(self, username):
        return bool(self.facilitator) and username == self.facilitator

    def authenticate_client(self, client_id, secret):
        user = self.by_app_id.get(client_id or "")
        if user is None:
            return None
        expected = client_secret(self.key, user)
        return user if hmac.compare_digest(expected, secret or "") else None

    def issue_token(self, username, audience):
        now = int(time.time())
        claims = {
            "aud": audience, "iss": self.issuer, "iat": now, "nbf": now,
            "exp": now + TOKEN_TTL, "tid": TENANT_ID, "oid": app_id(username),
            "appid": app_id(username), "sub": app_id(username),
            "preferred_username": username, "idtyp": "app",
        }
        head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        body = _b64(json.dumps(claims).encode())
        sig = hmac.new(self.key, f"{head}.{body}".encode(), hashlib.sha256).digest()
        return f"{head}.{body}.{_b64(sig)}"

    def verify_token(self, token):
        """Returns the username for a valid, unexpired token, else None."""
        try:
            head, body, sig = token.split(".")
            expected = hmac.new(self.key, f"{head}.{body}".encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, _unb64(sig)):
                return None
            claims = json.loads(_unb64(body))
            if claims.get("exp", 0) < time.time():
                return None
            user = claims.get("preferred_username")
            return user if user in self.users else None
        except (ValueError, TypeError, json.JSONDecodeError):
            return None
