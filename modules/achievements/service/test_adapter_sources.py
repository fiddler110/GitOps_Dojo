"""The generic adapter sources (cloud, bao, ca), `requires_not`, the Forgejo `fork` event and the
`verify` state milestones that the service runs itself."""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog as cat  # noqa: E402
import challenges  # noqa: E402
import ledger as lg  # noqa: E402
import matcher as mt  # noqa: E402
from store import Store  # noqa: E402


class Err(Exception):
    pass


def item(iid, match, core=True):
    return {"id": iid, "title": iid, "joke": "j", "when": "w", "core": core, "match": match}


def workshop(items, funny=()):
    """A throwaway workshop folder with one lab holding `items`."""
    root = tempfile.mkdtemp()
    base = os.path.join(root, "w", "achievements")
    os.makedirs(os.path.join(base, "labs"))
    import json
    json.dump({"workshop": "w", "title": "W", "labs": [{"id": "lab1", "title": "L"}]},
              open(os.path.join(base, "catalog.json"), "w"))
    json.dump({"milestones": items}, open(os.path.join(base, "labs", "lab1.json"), "w"))
    json.dump({"unlocks": list(funny)}, open(os.path.join(base, "funny.json"), "w"))
    json.dump({"id": "capstone", "title": "T", "space": "own `{user}/x`", "goal": "g", "verify_text": "v",
               "hints": ["h1", "h2"], "answer": "a", "seed": "s", "isolation": "i", "badge_tier": "capstone",
               "verify": [{"verb": "branch_exists", "branch": "b-{user}"}]},
              open(os.path.join(base, "capstone.json"), "w"))
    return root, os.path.join(root, "w")


class Sources(unittest.TestCase):
    def setUp(self):
        self.items = [
            item("denied", {"source": "cloud", "event": "policy_denied", "reason": "tag"}),
            item("login", {"source": "bao", "event": "login", "mount": "jwt-ci", "ok": False}),
            item("kv404", {"source": "bao", "event": "request", "status": 404, "path_prefix": "kv/"}),
            item("fork", {"source": "forgejo", "event": "fork"}),
            item("first", {"source": "shell", "cmd": "tofu destroy", "requires_not": ["denied"]}),
            item("limited", {"source": "ca", "event": "rate_limited"}),
        ]
        self.root, self.path = workshop(self.items)
        c = cat.load(self.path, check_name=False)[0]
        self.m = mt.Matcher(lg.Ledger(c, lg.Config()).index)

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_cloud_event(self):
        ev = mt.adapter_event({"source": "cloud", "event": "policy_denied", "user": "amy", "reason": "tag"})
        self.assertEqual(self.m.match(ev), ["denied"])
        ev["reason"] = "size"
        self.assertEqual(self.m.match(ev), [])

    def test_bao_fields(self):
        ev = mt.adapter_event({"source": "bao", "event": "login", "user": "amy", "mount": "jwt-ci", "ok": False})
        self.assertEqual(self.m.match(ev), ["login"])
        ev["ok"] = True
        self.assertEqual(self.m.match(ev), [])
        ev = mt.adapter_event({"source": "bao", "event": "request", "user": "amy", "status": 404, "path": "kv/data/x"})
        self.assertEqual(self.m.match(ev), ["kv404"])
        ev["path"] = "sys/policies"
        self.assertEqual(self.m.match(ev), [])

    def test_ca_event(self):
        self.assertEqual(self.m.match(mt.adapter_event({"source": "ca", "event": "rate_limited", "user": "amy"})),
                         ["limited"])

    def test_bad_adapter_events_are_dropped(self):
        for body in ({"source": "cloud", "event": "nope", "user": "a"}, {"source": "x", "event": "login", "user": "a"},
                     {"source": "bao", "event": "login"}, {"source": "bao", "event": "login", "user": ""}, []):
            self.assertIsNone(mt.adapter_event(body))

    def test_fork(self):
        ev = mt.forgejo_event("fork", {"forkee": {"full_name": "t/sample"}, "repository": {"full_name": "amy/sample"},
                                       "sender": {"login": "amy"}})
        self.assertEqual((ev["user"], ev["repo"]), ("amy", "amy/sample"))
        self.assertEqual(self.m.match(ev), ["fork"])

    def test_requires_not(self):
        ev = mt.shell_event({"cmd": "tofu destroy", "exit": 0})
        self.assertEqual(self.m.match(ev, have=()), ["first"])
        self.assertEqual(self.m.match(ev, have=("denied",)), [])


class ShellOutput(unittest.TestCase):
    def setUp(self):
        self.root, self.path = workshop([
            item("lock", {"source": "shell", "cmd": "tofu", "out_regex": "Error acquiring the state lock"}),
            item("either", {"source": "shell", "out_regex": ["NXDOMAIN", "SERVFAIL"]}),
        ])
        c = cat.load(self.path, check_name=False)[0]
        self.m = mt.Matcher(lg.Ledger(c, lg.Config()).index)

    def tearDown(self):
        shutil.rmtree(self.root)

    def sh(self, cmd, out, exit=1):
        return self.m.match(mt.shell_event({"cmd": cmd, "exit": exit, "out": out}))

    def test_output_matches_with_the_command(self):
        self.assertEqual(self.sh("tofu apply", "x\nError acquiring the state lock\n"), ["lock"])
        self.assertEqual(self.sh("tofu apply", "Error acquiring the state lock"), ["lock"])
        self.assertEqual(self.sh("echo hi", "Error acquiring the state lock"), [])
        self.assertEqual(self.sh("tofu apply", "all good"), [])

    def test_no_output_never_matches_an_output_item(self):
        self.assertEqual(mt.shell_event({"cmd": "tofu apply", "exit": 1})["out"], "")
        self.assertEqual(self.m.match(mt.shell_event({"cmd": "tofu apply", "exit": 1})), [])

    def test_list_and_multiline(self):
        self.assertEqual(self.sh("dig x", "a\nstatus: SERVFAIL"), ["either"])
        self.assertEqual(self.sh("dig x", "a\nstatus: NOERROR"), [])

    def test_output_is_capped_to_its_tail(self):
        out = mt.shell_event({"cmd": "x", "exit": 0, "out": "a" * 9000 + "TAIL"})["out"]
        self.assertEqual((len(out), out[-4:]), (mt.MAX_OUT, "TAIL"))

    def test_bad_out_regex_is_rejected(self):
        root, path = workshop([item("x", {"source": "shell", "out_regex": "("})])
        try:
            with self.assertRaises(cat.CatalogError):
                cat.load(path, check_name=False)
        finally:
            shutil.rmtree(root)


class Validation(unittest.TestCase):
    def check(self, match):
        root, path = workshop([item("x", match)])
        try:
            return cat.load(path, check_name=False)
        finally:
            shutil.rmtree(root)

    def test_good(self):
        self.check({"source": "cloud", "event": "container_replaced"})
        self.check({"source": "bao", "event": "login", "status": [403, 400], "root": False, "requires_not": "y"})
        self.check({"source": "verify", "verify": [{"verb": "v", "a": 1}]})

    def test_bad(self):
        for match in ({"source": "cloud", "event": "login"}, {"source": "bao", "event": "login", "status": 99},
                      {"source": "cloud", "reason": "tag"}, {"source": "verify", "verify": []},
                      {"source": "verify", "verify": ["x"]}, {"source": "ca", "event": "rate_limited", "ok": 1}):
            with self.assertRaises(cat.CatalogError, msg=match):
                self.check(match)

    def test_verify_verbs_are_checked(self):
        root, path = workshop([item("x", {"source": "verify", "verify": [{"verb": "nope"}]})])
        try:
            with self.assertRaises(cat.CatalogError):
                cat.load(path, check_name=False, known_verbs={"yes", "branch_exists"})
            cat.load(path, check_name=False, known_verbs={"nope", "branch_exists"})
        finally:
            shutil.rmtree(root)


class FakeRunner:
    def __init__(self, results):
        self.results, self.calls = results, []

    def verify(self, ch, user, seed=None):
        self.calls.append((ch["id"], user))
        r = self.results.get((ch["id"], user), True)
        if isinstance(r, Exception):
            raise r
        return {"passed": r, "message": ""}


class Sweep(unittest.TestCase):
    def setUp(self):
        self.items = [item("a", {"source": "verify", "verify": [{"verb": "v"}]}),
                      item("b", {"source": "verify", "verify": [{"verb": "v"}], "requires": ["a"]})]
        self.root, self.path = workshop(self.items)
        self.now = [1000.0]
        self.store = Store(cat.load(self.path, check_name=False)[0], lg.Config(), None, "s", clock=lambda: self.now[0])
        for u in ("amy", "bob"):
            self.store.ledger.register(u)

    def tearDown(self):
        shutil.rmtree(self.root)

    def have(self, u):
        return self.store.ledger.unlocked_ids(u)

    def test_passes_unlock_and_requires_orders_them(self):
        r = FakeRunner({("a", "bob"): False})
        self.assertEqual(self.store.sweep_state(r, (Err,)), 1)       # amy: a (b waits for a)
        self.assertEqual((self.have("amy"), self.have("bob")), ({"a"}, set()))
        self.now[0] += 25
        self.assertEqual(self.store.sweep_state(r, (Err,)), 1)       # amy: b
        self.assertIn("b", self.have("amy"))

    def test_gap_and_budget(self):
        r = FakeRunner({("a", "amy"): False, ("a", "bob"): False})
        self.store.sweep_state(r, (Err,))
        n = len(r.calls)
        self.store.sweep_state(r, (Err,))                              # too soon: nothing runs
        self.assertEqual(len(r.calls), n)
        self.now[0] += 25
        self.store.sweep_state(r, (Err,), budget=1)
        self.assertEqual(len(r.calls), n + 1)

    def test_backend_down_skips_the_student(self):
        r = FakeRunner({("a", "amy"): Err("down"), ("a", "bob"): True})
        self.assertEqual(self.store.sweep_state(r, (Err,)), 1)
        self.assertEqual((self.have("amy"), self.have("bob")), (set(), {"a"}))

    def test_not_checkable_is_skipped(self):
        r = FakeRunner({("a", "amy"): challenges.NotCheckable("x"), ("a", "bob"): False})
        self.assertEqual(self.store.sweep_state(r, (Err,)), 0)

    def test_facilitator_and_ignored_are_not_checked(self):
        self.store.ledger.register(self.store.facilitator)
        r = FakeRunner({})
        self.store.sweep_state(r, (Err,))
        self.assertNotIn(self.store.facilitator, {u for _, u in r.calls})


if __name__ == "__main__":
    unittest.main()
