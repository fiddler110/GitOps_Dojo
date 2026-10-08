"""Unit tests for image change detection, the terminal chain, superseded-image
clean-up and MODULES resolution (RV16). No container engine: a fake runtime
stands in for podman/docker.
    python3 -B -m unittest discover -s engine/dojo/tests -t engine
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dojo import build, envfiles, paths
from dojo.build import Builder, hash_dir


class FakeRuntime:
    """Just the image queries build.py makes. images: id -> repo (None = untagged)."""

    def __init__(self, cli="podman", images=None, labels=None, stuck=()):
        self.cli = cli
        self.images = dict(images or {})
        self.labels = dict(labels or {})      # image name -> dojo.src-hash
        self.ids = {}                         # image name -> id
        self.stuck = set(stuck)               # ids rmi refuses (in use)
        self.removed = []

    def out(self, *args):
        if args[0] == "images":
            dangling = "dangling=true" in args
            rows = [(i, r) for i, r in self.images.items() if (r is None) == dangling]
            if "{{.ID}} {{.Repository}}" in args:
                return "".join(f"{i} {r}\n" for i, r in rows)
            return "".join(f"{i}\n" for i, _ in rows)
        if args[0] == "inspect":
            image = args[-1]
            return self.ids.get(image, "") if args[2] == "{{.Id}}" else self.labels.get(image, "")
        raise AssertionError(args)

    def run(self, *args):
        assert args[0] == "rmi", args
        i = args[1]
        if i in self.stuck:
            return subprocess.CompletedProcess(args, 1)
        self.removed.append(i)
        self.images.pop(i, None)
        return subprocess.CompletedProcess(args, 0)


class Quiet(unittest.TestCase):
    def setUp(self):
        for name in ("ok", "changed", "console"):
            p = mock.patch.object(build, name)
            p.start()
            self.addCleanup(p.stop)


class HashDir(unittest.TestCase):
    """The hash text must stay what the shell run.sh produced, or every image rebuilds."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        p = mock.patch.object(paths, "ENGINE", self.root)
        p.start()
        self.addCleanup(p.stop)
        ctx = self.root / "ctx"
        (ctx / "sub").mkdir(parents=True)
        (ctx / "Dockerfile").write_text("FROM scratch\n")
        (ctx / "a.py").write_text("print('a')\n")
        (ctx / "sub" / "run.sh").write_text("#!/bin/sh\n")
        os.chmod(ctx / "sub" / "run.sh", 0o755)

    def test_golden_value(self):
        self.assertEqual(hash_dir("./ctx"), "79580a342993ec9ad09c9a0c1fb34ba201cfa2cbdf8458bd187d8c6dc9670e46")

    def test_matches_a_shell_find_and_sha256sum(self):
        script = ('cd "$1" && find ./ctx -type f ! -name "*.pyc" ! -path "*/__pycache__/*" | LC_ALL=C sort | '
                  'while read -r f; do sha256sum "$f"; [ -x "$f" ] && echo "exec $f"; done; '
                  '[ -n "$2" ] && echo "$2"; true')
        for salt in ("", "podman-build-format-docker"):
            text = subprocess.run(["sh", "-c", script, "sh", str(self.root), salt],
                                  capture_output=True, text=True, check=True).stdout
            self.assertEqual(hash_dir("./ctx", salt), hashlib.sha256(text.encode()).hexdigest(), salt)

    def test_ignores_bytecode_and_symlinks_but_not_content_or_mode(self):
        before = hash_dir("./ctx")
        ctx = self.root / "ctx"
        (ctx / "__pycache__").mkdir()
        (ctx / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"x")
        (ctx / "b.pyc").write_bytes(b"x")
        os.symlink(ctx / "a.py", ctx / "link.py")
        os.symlink(ctx / "sub", ctx / "linkdir")
        self.assertEqual(hash_dir("./ctx"), before)
        os.chmod(ctx / "a.py", 0o755)
        self.assertNotEqual(hash_dir("./ctx"), before)
        os.chmod(ctx / "a.py", 0o644)
        (ctx / "a.py").write_text("print('b')\n")
        self.assertNotEqual(hash_dir("./ctx"), before)
        self.assertNotEqual(hash_dir("./ctx", "salt"), hash_dir("./ctx"))


class TerminalChain(Quiet):
    LINKS = [("gitopsdojo/web-terminal:w.mod-a", "../modules/mod-a/terminal"),
             ("gitopsdojo/web-terminal:w", "../workshops/w/compose/terminal")]

    def setUp(self):
        super().setUp()
        self.hashes = {"./web-terminal": "h-base", "../modules/mod-a/terminal": "h-mod",
                       "../workshops/w/compose/terminal": "h-ws"}
        p = mock.patch.object(build, "hash_dir", side_effect=lambda ctx, salt="": f"{self.hashes[ctx]}|{salt}")
        p.start()
        self.addCleanup(p.stop)

    def builder(self, rt, dry_run=False):
        b = Builder(rt, dry_run=dry_run)
        b.tracking = mock.MagicMock()      # no image listing around each build
        return b

    def test_builds_base_then_each_link_on_the_one_before(self):
        rt = FakeRuntime(cli="docker")
        rt.ids = {"gitopsdojo/web-terminal:core": "id-base", "gitopsdojo/web-terminal:w.mod-a": "id-mod"}
        with mock.patch.object(build.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.builder(rt).terminal_chain(self.LINKS)
        cmds = [c[0][0] for c in run.call_args_list]
        self.assertEqual([c[c.index("-t") + 1] for c in cmds],
                         ["gitopsdojo/web-terminal:core", "gitopsdojo/web-terminal:w.mod-a", "gitopsdojo/web-terminal:w"])
        self.assertNotIn("--build-arg", cmds[0])
        self.assertIn("BASE=gitopsdojo/web-terminal:core", cmds[1])
        self.assertIn("BASE=gitopsdojo/web-terminal:w.mod-a", cmds[2])
        # a child's hash includes its parent's image ID, so a rebuilt parent rebuilds it
        self.assertIn("dojo.src-hash=h-mod|id-base", cmds[1])
        self.assertIn("dojo.src-hash=h-ws|id-mod", cmds[2])

    def test_unchanged_chain_builds_nothing(self):
        rt = FakeRuntime(cli="docker")
        rt.ids = {"gitopsdojo/web-terminal:core": "id-base", "gitopsdojo/web-terminal:w.mod-a": "id-mod"}
        rt.labels = {"gitopsdojo/web-terminal:core": "h-base|", "gitopsdojo/web-terminal:w.mod-a": "h-mod|id-base",
                     "gitopsdojo/web-terminal:w": "h-ws|id-mod"}
        with mock.patch.object(build.subprocess, "run") as run:
            self.builder(rt).terminal_chain(self.LINKS)
        run.assert_not_called()

    def test_dry_run_marks_children_of_a_changed_parent(self):
        rt = FakeRuntime(cli="docker")
        rt.labels = {"gitopsdojo/web-terminal:core": "h-base|"}       # base unchanged
        rt.ids = {"gitopsdojo/web-terminal:core": "id-base"}
        b = self.builder(rt, dry_run=True)
        with mock.patch.object(build.subprocess, "run") as run:
            b.terminal_chain(self.LINKS)                               # mod-a changed -> w follows
        run.assert_not_called()
        self.assertEqual(b.would_build, {"gitopsdojo/web-terminal:w.mod-a", "gitopsdojo/web-terminal:w"})

    def test_podman_salts_the_hash_and_builds_docker_format(self):
        rt = FakeRuntime(cli="podman")
        with mock.patch.object(build.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.builder(rt).terminal_chain([])
        self.assertIn("dojo.src-hash=h-base|podman-build-format-docker", run.call_args[0][0])
        self.assertEqual(run.call_args[1]["env"]["BUILDAH_FORMAT"], "docker")

    def test_failed_build_stops_the_chain(self):
        rt = FakeRuntime(cli="docker")
        with mock.patch.object(build.subprocess, "run", return_value=subprocess.CompletedProcess([], 2)) as run:
            with self.assertRaises(build.BuildError):
                self.builder(rt).terminal_chain(self.LINKS)
        self.assertEqual(run.call_count, 1)


class ConcurrentImages(Quiet):
    """images(): the engine images build alongside the chain, quietly, and every build finishes."""
    LINKS = TerminalChain.LINKS
    builder = TerminalChain.builder

    def setUp(self):
        super().setUp()
        self.hashes = {"./web-terminal": "h-base", "../modules/mod-a/terminal": "h-mod",
                       "../workshops/w/compose/terminal": "h-ws", **{ctx: f"h-{ctx[2:]}" for _, ctx in build.ENGINE_IMAGES}}
        p = mock.patch.object(build, "hash_dir", side_effect=lambda ctx, salt="": f"{self.hashes[ctx]}|{salt}")
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(build.tempfile, "gettempdir", return_value=tempfile.mkdtemp())
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, build.tempfile.gettempdir())

    def run_images(self, fail=()):
        def fake(cmd, **kw):
            image = cmd[cmd.index("-t") + 1]
            if kw.get("stdout"):
                kw["stdout"].write(f"step 1 of {image}\n")
            return subprocess.CompletedProcess(cmd, 2 if image in fail else 0)
        rt = FakeRuntime(cli="docker")
        with mock.patch.object(build.subprocess, "run", side_effect=fake) as run:
            self.builder(rt).images(self.LINKS)
        return run

    def test_all_images_build_and_only_engine_ones_are_quiet(self):
        run = self.run_images()
        by_image = {c[0][0][c[0][0].index("-t") + 1]: c[1] for c in run.call_args_list}
        self.assertEqual(len(by_image), 3 + len(build.ENGINE_IMAGES))
        for image, _ in build.ENGINE_IMAGES:
            self.assertIsNotNone(by_image[image]["stdout"])
        self.assertIsNone(by_image["gitopsdojo/web-terminal:core"]["stdout"])
        self.assertEqual(list(Path(build.tempfile.gettempdir()).glob("dojo-build.*")), [])  # logs of good builds go

    def test_a_failure_waits_for_the_others_and_keeps_its_log(self):
        with self.assertRaisesRegex(build.BuildError, "gateway:local failed.*dojo-build.gateway-local"):
            self.run_images(fail={"gitopsdojo/gateway:local"})
        logs = list(Path(build.tempfile.gettempdir()).glob("dojo-build.*"))
        self.assertEqual(len(logs), 1)
        self.assertIn("step 1 of gitopsdojo/gateway:local", logs[0].read_text())

    def test_dry_run_reports_in_order(self):
        rt = FakeRuntime(cli="docker")
        b = self.builder(rt, dry_run=True)
        with mock.patch.object(build.subprocess, "run") as run:
            b.images(self.LINKS)
        run.assert_not_called()
        self.assertEqual(len(b.would_build), 3 + len(build.ENGINE_IMAGES))


class Superseded(Quiet):
    def setUp(self):
        super().setUp()
        self.state = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.state)
        p = mock.patch.object(paths, "STATE", self.state)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(build, "SUPERSEDED", self.state / "superseded-images")
        p.start()
        self.addCleanup(p.stop)

    def recorded(self):
        return build.SUPERSEDED.read_text().split() if build.SUPERSEDED.exists() else []

    def test_tracking_records_what_the_build_left_untagged(self):
        """Ours that lost a tag, and anything newly untagged (build stages, a re-pulled base);
        never what was untagged before, nor what kept its tag."""
        rt = FakeRuntime(images={"old": "gitopsdojo/allocator", "theirs": "docker.io/library/python",
                                 "stray": None, "ovl": "localhost/engine_step-ca", "kept": "gitopsdojo/gateway"})
        b = Builder(rt)
        with b.tracking():
            rt.images.update({"old": None, "theirs": None, "ovl": None, "stage": None,
                              "new": "gitopsdojo/allocator"})
        self.assertEqual(sorted(self.recorded()), ["old", "ovl", "stage", "theirs"])   # not "stray"

    def test_interrupted_build_still_records(self):
        rt = FakeRuntime(images={"old": "gitopsdojo/gateway"})
        with self.assertRaises(KeyboardInterrupt):
            with Builder(rt).tracking():
                rt.images["old"] = None
                raise KeyboardInterrupt
        self.assertEqual(self.recorded(), ["old"])

    def test_reap_removes_untagged_retries_parents_and_skips_retagged(self):
        build.SUPERSEDED.write_text("parent\nchild\nretagged\nparent\n")
        rt = FakeRuntime(images={"parent": None, "child": None, "retagged": "gitopsdojo/x"})
        order = []

        def rmi(*args):
            i = args[1]
            if i == "parent" and "child" in rt.images:      # a parent goes only after its child
                return subprocess.CompletedProcess(args, 1)
            order.append(i)
            rt.images.pop(i)
            return subprocess.CompletedProcess(args, 0)
        rt.run = rmi
        Builder(rt).reap()
        self.assertEqual(order, ["child", "parent"])
        self.assertFalse(build.SUPERSEDED.exists())
        self.assertIn("retagged", rt.images)

    def test_reap_keeps_what_is_still_in_use(self):
        build.SUPERSEDED.write_text("busy\ngone\n")
        rt = FakeRuntime(images={"busy": None, "gone": None}, stuck={"busy"})
        Builder(rt).reap()
        self.assertEqual(self.recorded(), ["busy"])
        self.assertEqual(rt.removed, ["gone"])


class Modules(unittest.TestCase):
    """MODULES= resolution: order kept, module.env loaded, but engine/.env and workshop.env win."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.ws = self.root / "workshops" / "w"
        self.ws.mkdir(parents=True)
        for m, env in (("mod-a", "A_ONLY=from-a\nSHARED=from-a\nWS_WINS=from-a\nOP_WINS=from-a\n"),
                       ("mod-b", "SHARED=from-b\nFROM_A_SEEN=${A_ONLY:-unset}\n"), ("mod-c", None)):
            (self.root / "modules" / m).mkdir(parents=True)
            if env:
                (self.root / "modules" / m / "module.env").write_text(env)
        (self.root / ".env").write_text("OP_WINS=operator\nACHIEVEMENTS_ENABLED=0\n")
        saved = (paths.WORKSHOPS, paths.MODULES, paths.ENV_FILE, paths.CONFIG, paths.LOCAL_CONFIG)
        paths.WORKSHOPS, paths.MODULES, paths.ENV_FILE, paths.CONFIG, paths.LOCAL_CONFIG = (
            self.root / "workshops", self.root / "modules", self.root / ".env",
            self.root / "dojo.toml", self.root / "dojo.local.toml")
        self.addCleanup(lambda: [setattr(paths, n, v) for n, v in zip(
            ("WORKSHOPS", "MODULES", "ENV_FILE", "CONFIG", "LOCAL_CONFIG"), saved)])

    def resolve(self, workshop_env, **shell):
        (self.ws / "workshop.env").write_text(workshop_env)
        return envfiles.resolve("w", base={"PATH": os.environ["PATH"], **shell})

    def test_order_and_precedence(self):
        res = self.resolve('MODULES="mod-a mod-b mod-c"\nWS_WINS=workshop\n')
        self.assertEqual(res.modules, ["mod-a", "mod-b", "mod-c"])
        e = res.env
        self.assertEqual((e["A_ONLY"], e["SHARED"], e["FROM_A_SEEN"]), ("from-a", "from-b", "from-a"))
        self.assertEqual((e["WS_WINS"], e["OP_WINS"]), ("workshop", "operator"))
        self.assertTrue(res.source_of("SHARED").endswith("modules/mod-b/module.env"))
        self.assertTrue(res.source_of("OP_WINS").endswith(".env:1"))

    def test_no_modules(self):
        res = self.resolve("WORKSHOP_NAME=w\n")
        self.assertEqual((res.modules, res.warnings), ([], []))
        self.assertNotIn("A_ONLY", res.env)

    def test_unknown_or_badly_named_module_stops_the_start(self):
        with self.assertRaisesRegex(envfiles.EnvError, "no such module 'mod-z'"):
            self.resolve('MODULES="mod-a mod-z"\n')
        with self.assertRaisesRegex(envfiles.EnvError, "not a module name"):
            self.resolve('MODULES="../mod-a"\n')

    def test_achievements_added_last_once_and_only_with_a_catalog(self):
        (self.root / "modules" / "achievements").mkdir()
        res = self.resolve('MODULES="mod-a"\n', ACHIEVEMENTS_ENABLED="1")
        self.assertEqual(res.modules, ["mod-a"])
        self.assertIn("no achievements/catalog.json", res.warnings[0])
        (self.ws / "achievements").mkdir()
        (self.ws / "achievements" / "catalog.json").write_text("{}")
        self.assertEqual(self.resolve('MODULES="mod-a"\n', ACHIEVEMENTS_ENABLED="1").modules, ["mod-a", "achievements"])
        self.assertEqual(self.resolve('MODULES="achievements mod-a"\n', ACHIEVEMENTS_ENABLED="1").modules,
                         ["achievements", "mod-a"])
        self.assertEqual(self.resolve('MODULES="mod-a"\n').modules, ["mod-a"])     # .env says 0



class SharedFiles(unittest.TestCase):
    """SHARED= in a module's own module.env copies modules/_shared/ files into <context>/_shared/."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "_shared").mkdir()
        (self.root / "_shared" / "dojo_http.py").write_text("v1\n")
        (self.root / "_shared" / "run.sh").write_text("#!/bin/sh\n")
        os.chmod(self.root / "_shared" / "run.sh", 0o755)
        for m, ctxs in (("mod-a", ("gate",)), ("mod-b", ("api", "ui"))):
            for c in ctxs:
                (self.root / m / c).mkdir(parents=True)
        self.env("mod-a", 'SHARED="gate/dojo_http.py gate/run.sh"\n')
        self.env("mod-b", "SHARED=api/dojo_http.py\n")
        saved = paths.MODULES
        paths.MODULES = self.root
        self.addCleanup(setattr, paths, "MODULES", saved)

    def env(self, m, text):
        (self.root / m / "module.env").write_text(text)

    def test_each_module_gets_its_own_list(self):
        build.sync_shared(["mod-a", "mod-b"])
        self.assertEqual((self.root / "mod-a/gate/_shared/dojo_http.py").read_text(), "v1\n")
        self.assertTrue(os.access(self.root / "mod-a/gate/_shared/run.sh", os.X_OK))
        self.assertEqual(sorted(p.name for p in (self.root / "mod-b/api/_shared").iterdir()), ["dojo_http.py"])
        self.assertFalse((self.root / "mod-b/ui/_shared").exists())

    def test_a_change_reaches_the_copy_and_its_hash(self):
        build.sync_shared(["mod-a"])
        (self.root / "engine").mkdir()
        with mock.patch.object(paths, "ENGINE", self.root / "engine"):
            before = hash_dir("../mod-a/gate")
            (self.root / "_shared" / "dojo_http.py").write_text("v2\n")
            build.sync_shared(["mod-a"])
            self.assertNotEqual(hash_dir("../mod-a/gate"), before)
        self.assertEqual((self.root / "mod-a/gate/_shared/dojo_http.py").read_text(), "v2\n")

    def test_dropped_entries_are_removed(self):
        build.sync_shared(["mod-a", "mod-b"])
        self.env("mod-a", "SHARED=gate/dojo_http.py\n")
        self.env("mod-b", "# none now\n")
        build.sync_shared(["mod-a", "mod-b"])
        self.assertEqual([p.name for p in (self.root / "mod-a/gate/_shared").iterdir()], ["dojo_http.py"])
        self.assertFalse((self.root / "mod-b/api/_shared").exists())

    def test_bad_entries_stop_the_start(self):
        for entry, msg in (("dojo_http.py", "must be <context>/<file>"), ("../mod-b/api/dojo_http.py", "inside"),
                           ("gate/nope.py", "no modules/_shared/nope.py"), ("web/dojo_http.py", "no folder")):
            self.env("mod-a", f"SHARED={entry}\n")
            with self.assertRaisesRegex(build.BuildError, msg):
                build.sync_shared(["mod-a"])


if __name__ == "__main__":
    unittest.main()
