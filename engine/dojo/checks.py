"""Safety rules shared by `doctor` and the start: public passwords, loopback,
the published port and plain HTTP. Same rules dojo has always applied."""
from __future__ import annotations

from typing import Dict, List, Optional

# Passwords anyone can know: .env.example's placeholder and the values
# `./dojo setup --default` writes. Keep in step with engine/scripts/lib.sh
# (tests/test_checks.py compares the two).
DEFAULT_PASSWORDS = ("change-me", "student", "student123", "admin")


def is_default_password(value: str) -> bool:
    return value in DEFAULT_PASSWORDS


def url_parts(url: str):
    """(scheme, host, port-or-None) of a URL, IPv6 brackets removed."""
    scheme, _, rest = url.partition("://")
    if not rest:
        scheme, rest = "http", url
    hostport = rest.split("/", 1)[0]
    if hostport.startswith("["):
        host, _, tail = hostport[1:].partition("]")
        port = tail[1:] if tail.startswith(":") else None
    elif ":" in hostport:
        host, port = hostport.rsplit(":", 1)
    else:
        host, port = hostport, None
    return scheme, host, port


def local_only(env: Dict[str, str]) -> bool:
    """Only this machine can reach the gateway: a loopback PUBLIC_BASE_URL host
    and a loopback LAB_HOST_IP."""
    _, host, _ = url_parts(env.get("PUBLIC_BASE_URL", ""))
    return host in ("localhost", "127.0.0.1", "::1") and env.get("LAB_HOST_IP", "") in ("127.0.0.1", "::1")


def default_passwords(env: Dict[str, str]) -> List[str]:
    """Which secrets still hold a public value. Without STUDENT_PASSWORD_SEED the
    shared STUDENT_PASSWORD is every student's Forgejo password, so it counts."""
    pairs = [("TTYD_PASSWORD", env.get("TTYD_PASSWORD", ""))]
    if env.get("STUDENT_PASSWORD_SEED"):
        pairs.append(("STUDENT_PASSWORD_SEED", env["STUDENT_PASSWORD_SEED"]))
    else:
        pairs.append(("STUDENT_PASSWORD", env.get("STUDENT_PASSWORD", "student123")))
    pairs += [("FACILITATOR_PASSWORD", env.get("FACILITATOR_PASSWORD", "")),
              ("FORGEJO_ADMIN_PASSWORD", env.get("FORGEJO_ADMIN_PASSWORD", ""))]
    return [k for k, v in pairs if is_default_password(v)]


def gateway_port(env: Dict[str, str]) -> int:
    """The host port the gateway is published on, for the address it serves."""
    scheme, _, _ = url_parts(env.get("GATEWAY_LISTEN") or env.get("PUBLIC_BASE_URL", ""))
    key, default = ("GATEWAY_HTTPS_PORT", 8443) if scheme == "https" else ("GATEWAY_HTTP_PORT", 8080)
    try:
        return int(env.get(key) or default)
    except ValueError:
        return default


def port_mismatch(env: Dict[str, str]) -> Optional[str]:
    """PUBLIC_BASE_URL (or GATEWAY_LISTEN behind a proxy) must name the published
    port, or the links the lab prints won't load. None when they agree."""
    listen = env.get("GATEWAY_LISTEN") or env.get("PUBLIC_BASE_URL", "")
    scheme, host, port = url_parts(listen)
    url_port = int(port) if port and port.isdigit() else (443 if scheme == "https" else 80)
    published = gateway_port(env)
    if url_port == published:
        return None
    return (f"{listen} points at port {url_port}, but the gateway is published on {published}. "
            f"Set PUBLIC_BASE_URL={scheme}://{host}:{published} in dojo.local.toml ([network] public_base_url).")


def plain_http_offbox(env: Dict[str, str]) -> bool:
    scheme, host, _ = url_parts(env.get("PUBLIC_BASE_URL", ""))
    return scheme == "http" and host not in ("localhost", "127.0.0.1", "::1")
