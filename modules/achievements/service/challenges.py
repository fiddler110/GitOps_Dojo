"""The challenge runner: module-owned verifier verbs and seed builders (A3, A18, A20, A22).

A module that owns a backend ships `achievements/verifiers.json` (verb names, what they check,
the Python file that implements them) and that file's VERBS and BUILDERS. This runner loads
them, fills a challenge's `{user}` and per-student values in, and runs them with the
service's own backend login. No state and no locks here: store.py records the outcome.

Per-student values come from the challenge's seed plan (`seed_plan`, a file in the
workshop's achievements/seeds/): each key in its "values" picks one entry by a hash of the
user name, so the same student always gets the same value and neighbours mostly differ.
Keys listed together in the plan's "linked" (e.g. [["role", "role_typo"]]) share one pick, so a
right spelling and its per-student typo stay a pair.
"""

import base64
import hashlib
import importlib.util
import json
import os
import re
import urllib.error
import urllib.request

PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


class NotCheckable(Exception):
    """The challenge has no structured verify, an unknown verb, or no seed plan."""


def load_plugins(dirs):
    """{verbs, builders, backends, problems} from every <dir>/verifiers.json that exists."""
    verbs, builders, problems, backends = {}, {}, [], []
    for d in dirs:
        spec_path = os.path.join(d, "verifiers.json")
        if not os.path.isfile(spec_path):
            continue
        try:
            with open(spec_path) as f:
                spec = json.load(f)
            impl = os.path.join(d, spec["impl"])
            mod_spec = importlib.util.spec_from_file_location(f"dojo_verifiers_{len(backends)}", impl)
            mod = importlib.util.module_from_spec(mod_spec)
            mod_spec.loader.exec_module(mod)
        except (OSError, ValueError, KeyError, ImportError, SyntaxError) as exc:
            problems.append(f"{spec_path}: {exc!r}")
            continue
        backends.append(spec.get("backend", d))
        for name in spec.get("verbs", {}):
            if name in verbs:
                problems.append(f"{spec_path}: verb '{name}' is declared twice")
            elif name not in getattr(mod, "VERBS", {}):
                problems.append(f"{spec_path}: verb '{name}' has no implementation")
            else:
                verbs[name] = (mod.VERBS[name], mod)
        for name in spec.get("builders", {}):
            if name not in getattr(mod, "BUILDERS", {}):
                problems.append(f"{spec_path}: builder '{name}' has no implementation")
            else:
                builders[name] = (mod.BUILDERS[name], mod)
    return {"verbs": verbs, "builders": builders, "backends": backends, "problems": problems}


def pick(user, key, options):
    h = int(hashlib.sha256(f"{key}:{user}".encode()).hexdigest(), 16)
    return options[h % len(options)]


def fill_text(text, values, escape=False):
    """Replace {name} with the value; unknown names are left as they are (a YAML brace)."""
    def sub(m):
        v = values.get(m.group(1))
        if v is None:
            return m.group(0)
        return re.escape(v) if escape else v
    return PLACEHOLDER.sub(sub, text)


def fill_args(obj, values, key=None):
    """Template an assertion; a `regex` argument gets its values regex-escaped."""
    if isinstance(obj, str):
        return fill_text(obj, values, escape=(key == "regex"))
    if isinstance(obj, list):
        return [fill_args(x, values, key) for x in obj]
    if isinstance(obj, dict):
        return {k: fill_args(v, values, k) for k, v in obj.items()}
    return obj


def repos_in(obj):
    """Every `repo` argument anywhere in an assertion."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "repo" and isinstance(v, str):
                yield v
            else:
                yield from repos_in(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from repos_in(x)


class Runner:
    def __init__(self, plugins, seeds_dir, api, clock):
        self.verbs = plugins["verbs"]
        self.builders = plugins["builders"]
        self.seeds_dir = seeds_dir
        self.api = api
        self.clock = clock

    # -- plans and values --------------------------------------------------------------
    def _seed_file(self, name):
        path = os.path.normpath(os.path.join(self.seeds_dir, name))
        if not path.startswith(os.path.normpath(self.seeds_dir) + os.sep):
            raise NotCheckable(f"seed file {name} is outside seeds/")
        with open(path) as f:
            return f.read()

    def plan(self, ch):
        name = ch.get("seed_plan")
        if not name:
            return None
        try:
            return json.loads(self._seed_file(name))
        except (OSError, ValueError) as exc:
            raise NotCheckable(f"seed plan {name}: {exc}")

    def values(self, ch, user):
        vals = {"user": user}
        plan = self.plan(ch)
        options = (plan or {}).get("values") or {}
        index = {}
        for group in (plan or {}).get("linked") or []:
            i = pick(user, group[0], range(len(options[group[0]])))
            for key in group:
                index[key] = i
        for key, opts in options.items():
            vals[key] = opts[index[key]] if key in index else pick(user, key, opts)
        return vals

    def render(self, ch, user, text):
        return fill_text(text or "", self.values(ch, user))

    def unknown_verbs(self, catalog):
        """[(challenge id, verb)] the loaded plug-ins don't provide."""
        out = []
        for ch in catalog["challenges"] + ([catalog["capstone"]] if catalog.get("capstone") else []):
            for a in (ch.get("verify") or []) + ((ch.get("then") or {}).get("verify") or []):
                if a.get("verb") not in self.verbs:
                    out.append((ch["id"], a.get("verb")))
        return out

    # -- checking ----------------------------------------------------------------------
    def verify(self, ch, user, seed=None, step_at=None):
        """{passed, message}. Raises NotCheckable, or the plug-in's Unavailable."""
        assertions = ch.get("verify")
        if not assertions:
            raise NotCheckable(f"{ch['id']} can't be checked yet")
        vals = self.values(ch, user)
        ctx = {"user": user, "seed": seed or {}, "now": self.clock(), "challenge": ch["id"], "step_at": step_at}
        for a in assertions:
            if a.get("verb") not in self.verbs:
                raise NotCheckable(f"{ch['id']}: no verifier '{a.get('verb')}' in this run")
            args = fill_args({k: v for k, v in a.items() if k not in ("verb", "restart")}, vals)
            # Isolation (A20): a check reads only the checking student's own space.
            for repo in repos_in(args):
                if not repo.startswith(user + "/"):
                    raise NotCheckable(f"{ch['id']}: assertion reads {repo}, not the student's own space")
            fn, _ = self.verbs[a["verb"]]
            passed, message = fn(self.api, args, ctx)
            if not passed:
                # restart (step 2 only): this failure can't be fixed from here, so step 1 starts over
                return {"passed": False, "message": message, "restart": bool(a.get("restart"))}
        return {"passed": True, "message": "passed"}

    # -- seeding -----------------------------------------------------------------------
    def seed(self, ch, user, reset=False):
        """Create (or with reset, re-create) the student's challenge space. Returns the
        builder's result plus the plan name. Raises NotCheckable or the plug-in's errors."""
        plan = self.plan(ch)
        if not plan:
            raise NotCheckable(f"{ch['id']} has no seed")
        builder = self.builders.get(plan.get("builder"))
        if not builder:
            raise NotCheckable(f"no seed builder '{plan.get('builder')}' in this run")
        vals = self.values(ch, user)
        repo = fill_text(plan.get("repo", ""), vals)
        if not repo.startswith(user + "/"):
            raise NotCheckable(f"seed plan writes {repo}, not the student's own space")
        fn, _ = builder
        res = fn(self.api, plan, lambda s: fill_text(s, vals), self._seed_file, self.clock(), reset=reset)
        res["plan"] = ch["seed_plan"]
        return res

    def errors(self):
        """Exception classes that mean "the backend failed" (try again), from every plug-in."""
        mods = {m for _, m in list(self.verbs.values()) + list(self.builders.values())}
        out = []
        for m in mods:
            out += [getattr(m, n) for n in ("Unavailable", "SeedError") if hasattr(m, n)]
        return tuple(out)


def forgejo_http(base_url, user, password, timeout=15):
    """The plug-ins' `api` for a real Forgejo, as the admin account (basic auth)."""
    auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
    root = base_url.rstrip("/") + "/api/v1"

    def api(method, path, body=None, raw=False):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(root + path, data=data, method=method,
                                     headers={"Authorization": auth, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = r.read().decode("utf-8", "replace")
                if raw:
                    return r.status, text
                return r.status, json.loads(text) if text.strip() else None
        except urllib.error.HTTPError as e:
            return e.code, None
        except (urllib.error.URLError, OSError, ValueError):
            return 0, None
    return api
