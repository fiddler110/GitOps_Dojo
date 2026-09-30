"""Tests for the catalog editor: load, save (valid, refused, formatting, only changed files) and
the HTTP layer. Every test works on a temporary copy of the real catalogs, never the repo."""

import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import catalog_edit as ce  # noqa: E402
import server  # noqa: E402

cat = ce.cat
GF = "workshops/git-fundamentals/achievements"


def copy_repo():
    """A throwaway root holding every workshop's achievements, ACHIEVEMENTS.md and shared.json."""
    root = tempfile.mkdtemp(prefix="editor-test-")
    for name in ce.workshops(REPO):
        src = os.path.join(REPO, "workshops", name)
        shutil.copytree(os.path.join(src, "achievements"), os.path.join(root, "workshops", name, "achievements"))
        shutil.copy(os.path.join(src, "ACHIEVEMENTS.md"), os.path.join(root, "workshops", name, "ACHIEVEMENTS.md"))
    os.makedirs(os.path.join(root, os.path.dirname(ce.SHARED_REL)))
    shutil.copy(os.path.join(REPO, ce.SHARED_REL), os.path.join(root, ce.SHARED_REL))
    return root


def snapshot(root):
    out = {}
    for d, _, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            with open(p, encoding="utf-8") as fh:
                out[os.path.relpath(p, root)] = fh.read()
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.root = copy_repo()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.data = ce.load_all(self.root, "all")
        self.before = snapshot(self.root)

    def row(self, iid, ws="git-fundamentals"):
        w = next(w for w in self.data["workshops"] if w["name"] == ws)
        return next(r for g in w["groups"] for r in g["rows"] if r["id"] == iid)

    def save(self, *changes, scope="all", bases=None):
        return ce.save(self.root, scope, list(changes), bases or self.data["bases"])

    def changed_files(self):
        after = snapshot(self.root)
        return sorted(k for k in after if after[k] != self.before.get(k))


class Load(Base):
    def test_every_workshop_and_shared_with_groups(self):
        names = [w["name"] for w in self.data["workshops"]]
        self.assertEqual(names, ce.workshops(REPO) + ["shared"])
        self.assertEqual(self.data["errors"], [])
        gf = self.data["workshops"][names.index("git-fundamentals")]
        labels = [g["label"] for g in gf["groups"]]
        self.assertEqual(labels[0], "Lab 1: the core workflow")
        self.assertEqual(labels[-3:], ["Funny unlocks", "Challenges", "Capstone"])
        # a base hash for every JSON file except catalog.json, which the editor never writes
        self.assertIn(f"{GF}/labs/lab1.json", self.data["bases"])
        self.assertIn(ce.SHARED_REL, self.data["bases"])
        self.assertNotIn(f"{GF}/catalog.json", self.data["bases"])

    def test_row_shape(self):
        r = self.row("l1-clone")
        self.assertEqual((r["kind"], r["file"]), ("milestone", f"{GF}/labs/lab1.json"))
        self.assertEqual(set(r["fields"]), {"enabled", "title", "joke", "when", "points", "core"})
        self.assertTrue(r["fields"]["enabled"])
        self.assertIn('"git clone"', r["match"])
        c = self.row("c1")
        self.assertEqual(set(c["fields"]), {"enabled", "title", "goal", "hints", "answer", "points"})
        self.assertEqual(len(c["fields"]["hints"]), 2)
        cheat = self.row("cheat-forged", "shared")
        self.assertEqual((cheat["kind"], cheat["fields"]["points"]), ("cheat", -1))

    def test_one_workshop_scope(self):
        d = ce.load_all(self.root, "git-fundamentals")
        self.assertEqual([w["name"] for w in d["workshops"]], ["git-fundamentals", "shared"])
        with self.assertRaises(ce.EditError) as e:
            ce.load_all(self.root, "nope")
        self.assertEqual(e.exception.status, 404)

    def test_house_format_round_trips_every_file(self):
        for rel in self.data["bases"]:
            text = self.before[rel]
            self.assertEqual(ce.dump(json.loads(text), text), text, rel)


class Save(Base):
    def test_valid_edit_writes_one_file_minimal_diff_and_markdown(self):
        res = self.save({"file": f"{GF}/labs/lab1.json", "id": "l1-clone", "set": {"title": "Clone Wars"}})
        self.assertEqual(res["written"], [f"{GF}/labs/lab1.json"])
        self.assertEqual(res["rendered"], ["workshops/git-fundamentals/ACHIEVEMENTS.md"])
        self.assertEqual(self.changed_files(), sorted(res["written"] + res["rendered"]))
        old, new = self.before[res["written"][0]].splitlines(), snapshot(self.root)[res["written"][0]].splitlines()
        self.assertEqual(len(old), len(new))
        self.assertEqual([(a, b) for a, b in zip(old, new) if a != b],
                         [('      "title": "Cloned Around",', '      "title": "Clone Wars",')])
        md = snapshot(self.root)["workshops/git-fundamentals/ACHIEVEMENTS.md"]
        self.assertIn("| l1-clone | Clone Wars |", md)

    def test_disable_adds_one_key_and_enable_removes_it(self):
        rel = f"{GF}/labs/lab1.json"
        self.save({"file": rel, "id": "l1-clone", "set": {"enabled": False}})
        c, _ = cat.load(os.path.join(self.root, "workshops", "git-fundamentals"), os.path.join(self.root, ce.SHARED_REL))
        self.assertIn("l1-clone", cat.disabled_ids(c))
        self.assertNotIn("l1-clone", [m["id"] for m in cat.milestones(c)])
        self.assertIn("| l1-clone (off) |", snapshot(self.root)["workshops/git-fundamentals/ACHIEVEMENTS.md"])
        text = snapshot(self.root)[rel]
        self.assertEqual(len(text.splitlines()), len(self.before[rel].splitlines()) + 1)
        fresh = ce.load_all(self.root, "all")
        self.assertFalse(next(r for g in fresh["workshops"][2]["groups"] for r in g["rows"]
                              if r["id"] == "l1-clone")["fields"]["enabled"])
        ce.save(self.root, "all", [{"file": rel, "id": "l1-clone", "set": {"enabled": True}}], fresh["bases"])
        self.assertEqual(self.changed_files(), [])      # byte for byte back where it started

    def test_points_and_challenge_fields(self):
        rel = f"{GF}/challenges/c1.json"
        self.save({"file": rel, "id": "c1", "set": {"points": 150, "hints": ["one", "two"], "goal": "G", "answer": "A"}},
                  {"file": f"{GF}/labs/lab1.json", "id": "l1-clone", "set": {"points": None, "core": False}})
        doc = json.loads(snapshot(self.root)[rel])
        self.assertEqual((doc["points"], doc["hints"], doc["goal"], doc["answer"]), (150, ["one", "two"], "G", "A"))
        self.assertEqual(list(doc)[:3], list(json.loads(self.before[rel]))[:3])   # key order kept
        self.assertIn("150", snapshot(self.root)["workshops/git-fundamentals/ACHIEVEMENTS.md"])

    def test_catalog_validator_refuses_and_nothing_is_written(self):
        with self.assertRaises(ce.EditError) as e:
            self.save({"file": f"{GF}/labs/lab1.json", "id": "l1-clone", "set": {"title": "ok"}},
                      {"file": f"{GF}/funny.json", "id": "f-wrongdir", "set": {"points": 5}})
        self.assertEqual(e.exception.status, 422)
        self.assertTrue(any("funny unlocks are worth 0 points" in p for p in e.exception.errors), e.exception.errors)
        self.assertEqual(self.changed_files(), [])

    def test_type_checks_refuse(self):
        bad = [
            ({"title": ""}, "can't be empty"),
            ({"points": 1.5}, "whole number"),
            ({"points": 5000}, "whole number"),
            ({"enabled": "no"}, "true or false"),
            ({"id": "x"}, "can't be edited"),
            ({"match": {}}, "can't be edited"),
            ({"goal": "g"}, "can't be edited"),   # not a milestone field
        ]
        for change, msg in bad:
            with self.assertRaises(ce.EditError) as e:
                self.save({"file": f"{GF}/labs/lab1.json", "id": "l1-clone", "set": change})
            self.assertEqual(e.exception.status, 422, change)
            self.assertTrue(any(msg in p for p in e.exception.errors), (change, e.exception.errors))
        with self.assertRaises(ce.EditError):
            self.save({"file": f"{GF}/challenges/c1.json", "id": "c1", "set": {"hints": ["only one"]}})
        self.assertEqual(self.changed_files(), [])

    def test_only_loaded_catalog_files(self):
        for rel in ("../../etc/passwd", f"{GF}/catalog.json", "workshops/git-fundamentals/ACHIEVEMENTS.md"):
            with self.assertRaises(ce.EditError) as e:
                self.save({"file": rel, "id": "x", "set": {"title": "t"}})
            self.assertEqual(e.exception.status, 422)
        with self.assertRaises(ce.EditError):     # another workshop is out of a one-workshop scope
            self.save({"file": "workshops/tofu-basics/achievements/funny.json", "id": "x", "set": {"title": "t"}},
                      scope="git-fundamentals")
        with self.assertRaises(ce.EditError):
            self.save({"file": f"{GF}/labs/lab1.json", "id": "nope", "set": {"title": "t"}})
        self.assertEqual(self.changed_files(), [])

    def test_changed_on_disk_is_a_conflict(self):
        rel = f"{GF}/funny.json"
        with open(os.path.join(self.root, rel), "a", encoding="utf-8") as fh:
            fh.write("\n")
        with self.assertRaises(ce.EditError) as e:
            self.save({"file": rel, "id": "f-wrongdir", "set": {"title": "t"}})
        self.assertEqual(e.exception.status, 409)

    def test_shared_edit_validates_every_workshop(self):
        res = self.save({"file": ce.SHARED_REL, "id": "cheat-forged", "set": {"enabled": False}},
                        scope="git-fundamentals")
        self.assertEqual(res["written"], [ce.SHARED_REL])
        self.assertEqual(res["rendered"], [])     # shared items are not in the per-workshop markdown
        with self.assertRaises(ce.EditError) as e:
            self.save({"file": ce.SHARED_REL, "id": "cheat-client", "set": {"points": 3}},
                      bases=ce.load_all(self.root, "all")["bases"])
        self.assertTrue(all(p.split(":")[0] in ce.workshops(self.root) for p in e.exception.errors))
        self.assertEqual(len({p.split(":")[0] for p in e.exception.errors}), len(ce.workshops(self.root)))

    def test_unchanged_value_writes_nothing(self):
        r = self.row("l1-clone")
        res = self.save({"file": r["file"], "id": "l1-clone", "set": {"title": r["fields"]["title"]}})
        self.assertEqual((res["written"], res["rendered"]), ([], []))
        self.assertEqual(self.changed_files(), [])


class Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = copy_repo()
        cls.httpd, cls.editor = server.make_server(cls.root, "git-fundamentals", 0)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.root, True)

    def req(self, method, path, body=None, headers=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        h.update(headers or {})
        data = json.dumps(body).encode() if body is not None else None
        if data is not None:
            h["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=h)
        res = conn.getresponse()
        out = res.status, dict(res.getheaders()), res.read()
        conn.close()
        return out

    def test_page_and_assets_have_strict_csp(self):
        for path in ("/", "/editor.js", "/editor.css"):
            status, headers, body = self.req("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
            self.assertNotIn("unsafe-inline", headers["Content-Security-Policy"])
        _, _, page = self.req("GET", "/")
        self.assertNotIn(b"<script>", page)
        self.assertNotIn(b"style=", page)

    def test_wrong_host_and_missing_token(self):
        self.assertEqual(self.req("GET", "/api/catalog", host="evil.example:80")[0], 421)
        self.assertEqual(self.req("POST", "/api/save", {"changes": []})[0], 403)
        self.assertEqual(self.req("GET", "/nope")[0], 404)

    def test_save_round_trip(self):
        status, _, body = self.req("GET", "/api/catalog")
        data = json.loads(body)
        tok = {"X-Editor-Token": data["token"]}
        change = {"file": f"{GF}/funny.json", "id": "f-wrongdir", "set": {"joke": "Where are you?"}}
        status, _, body = self.req("POST", "/api/save", {"changes": [change], "bases": data["bases"]}, tok)
        self.assertEqual(status, 200, body)
        res = json.loads(body)
        self.assertEqual(res["written"], [f"{GF}/funny.json"])
        self.assertIn("catalog", res)
        bad = {"file": f"{GF}/funny.json", "id": "f-wrongdir", "set": {"points": 2}}
        status, _, body = self.req("POST", "/api/save", {"changes": [bad], "bases": res["catalog"]["bases"]}, tok)
        self.assertEqual(status, 422)
        self.assertTrue(json.loads(body)["errors"])
        status, _, _ = self.req("POST", "/api/save", {"changes": [change], "bases": data["bases"]}, tok)
        self.assertEqual(status, 409)       # stale bases from before the first save


if __name__ == "__main__":
    unittest.main()
