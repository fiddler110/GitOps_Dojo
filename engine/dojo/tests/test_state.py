"""RunLock: one build or start at a time, and a lock left by a crash is reclaimed."""
import os
import tempfile
import time
import unittest
from pathlib import Path

from dojo import state


class RunLockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "lock"

    def tearDown(self):
        self.tmp.cleanup()

    def lock(self, what="test"):
        lk = state.RunLock(what)
        lk.dir = self.dir
        return lk

    def test_second_holder_is_refused_then_free_after_release(self):
        first = self.lock()
        first.acquire()
        with self.assertRaises(state.LockBusy):
            self.lock().acquire()
        first.release()
        self.assertFalse(self.dir.exists())
        with self.lock():
            self.assertTrue((self.dir / "pid").is_file())

    def test_dead_pid_is_reclaimed(self):
        self.dir.mkdir()
        (self.dir / "pid").write_text("999999999\n")  # no such process
        with self.lock() as lk:
            self.assertEqual((lk.dir / "pid").read_text().strip(), str(os.getpid()))

    def test_fresh_pidless_lock_is_busy_old_one_is_reclaimed(self):
        self.dir.mkdir()
        with self.assertRaises(state.LockBusy):
            self.lock().acquire()
        old = time.time() - state.STALE_EMPTY_LOCK - 5
        os.utime(self.dir, (old, old))
        with self.lock():
            pass


if __name__ == "__main__":
    unittest.main()
