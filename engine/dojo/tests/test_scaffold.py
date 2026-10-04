"""new-workshop: the scaffold from workshops/assets/template/."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dojo import paths, scaffold, workshops
from dojo.scaffold import Scaffold, ScaffoldError, create, plan, prepare

REAL_TEMPLATE = scaffold.TEMPLATE


class NewWorkshop(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "first").mkdir()
        (self.root / "first" / "workshop.env").write_text('WORKSHOP_NAME="First"\nWORKSHOP_ORDER=4\n')
        for patch in (mock.patch.object(paths, "WORKSHOPS", self.root),
                      mock.patch.object(scaffold, "TEMPLATE", REAL_TEMPLATE)):
            patch.start()
            self.addCleanup(patch.stop)

    def make(self, **kw):
        s = prepare(Scaffold("new-one", **kw), ["status", "stop"])
        return s, create(s)

    def test_files_and_values(self):
        s, files = self.make(modules="sensei,dns-ui")
        dest = self.root / "new-one"
        self.assertEqual(sorted(str(f) for f in files),
                         sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file()))
        self.assertNotIn("compose", {f.parts[0] for f in files})
        for f in files:
            self.assertNotRegex((dest / f).read_text(), r"\{\{\w+\}\}", f)
        env = (dest / "workshop.env").read_text()
        self.assertIn('WORKSHOP_NAME="New One"', env)
        self.assertIn('MODULES="sensei dns-ui"', env)
        self.assertIn("WORKSHOP_CONTENT_DIR=../workshops/new-one/content", env)
        self.assertIn("training/new-one.git", (dest / "content/lab/lab1.md").read_text())
        self.assertIn('WORKSHOP_DURATION="TODO: e.g. ~2 h"', env)   # no --duration: a TODO like the description
        # It shows up in ./run.sh list, after the last workshop in the path.
        found = workshops.find("new-one")
        self.assertEqual((found.title, found.order, found.modules), ("New One", 5, ["sensei", "dns-ui"]))
        self.assertEqual(found.duration, "TODO: e.g. ~2 h")
        # A workshop.env written before WORKSHOP_DURATION existed still lists, with no duration.
        self.assertEqual(workshops.find("first").duration, "")
        self.assertFalse(list(self.root.glob(".*.new")))

    def test_options(self):
        s, files = self.make(title="My Lab", description="Learn things.", order=2, duration="~90 min",
                             org="acme", repo="practice", terminal=True)
        dest = self.root / "new-one"
        self.assertIn(Path("compose/terminal/Dockerfile"), files)
        self.assertIn("FROM ${BASE}", (dest / "compose/terminal/Dockerfile").read_text())
        env = (dest / "workshop.env").read_text()
        for line in ('WORKSHOP_NAME="My Lab"', 'WORKSHOP_DESCRIPTION="Learn things."', "WORKSHOP_ORDER=2",
                     'WORKSHOP_DURATION="~90 min"', "FORGEJO_ORG=acme", "FORGEJO_REPO=practice"):
            self.assertIn(line, env)
        self.assertEqual(workshops.find("new-one").duration, "~90 min")

    def test_refusals(self):
        bad = [Scaffold("Bad"), Scaffold("-x"), Scaffold("stop"), Scaffold("assets"), Scaffold("first"),
               Scaffold("ok", modules="no-such"), Scaffold("ok", title='a "quote"'),
               Scaffold("ok", description="$(id)"), Scaffold("ok", title="<b>"), Scaffold("ok", repo="Has Space"),
               Scaffold("ok", duration='2 "hours"')]
        for s in bad:
            with self.subTest(s=s), self.assertRaises(ScaffoldError):
                prepare(s, ["status", "stop"])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["first"])

    def test_dry_run_plan_writes_nothing(self):
        s = prepare(Scaffold("new-one", terminal=True), [])
        self.assertIn(Path("workshop.env"), plan(s))
        self.assertFalse((self.root / "new-one").exists())

    def test_failed_copy_leaves_nothing(self):
        s = prepare(Scaffold("new-one"), [])
        with mock.patch.object(scaffold.shutil, "copymode", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                create(s)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["first"])


if __name__ == "__main__":
    unittest.main()
