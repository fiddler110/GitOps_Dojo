import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import personas as p  # noqa: E402


class PickStyleTests(unittest.TestCase):
    def test_always_a_known_style(self):
        rng = random.Random(1)
        for _ in range(100):
            self.assertIn(p.pick_style(rng), p.STYLES)

    def test_benign_is_the_minority(self):
        rng = random.Random(2)
        styles = [p.pick_style(rng) for _ in range(2000)]
        frac = styles.count("benign") / len(styles)
        self.assertAlmostEqual(frac, p.BENIGN_FRACTION, delta=0.03)


class PickOriginTests(unittest.TestCase):
    def test_always_one_of_the_table(self):
        rng = random.Random(42)
        valid = {o for o, _ in p.ORIGINS}
        for _ in range(50):
            self.assertIn(p.pick_origin(rng), valid)

    def test_pool_spans_every_inhabited_region(self):
        names = {o for o, _ in p.ORIGINS}
        for want in ("NG", "ZA", "BR", "AR", "AU", "AE", "IR", "TR", "IN", "VN", "CN", "US", "RU", "UA"):
            self.assertIn(want, names)

    def test_deterministic_per_seed(self):
        a = [p.pick_origin(random.Random(7)) for _ in range(3)]
        self.assertEqual(a, [p.pick_origin(random.Random(7)) for _ in range(3)])


class RoomPhaseTests(unittest.TestCase):
    def test_green_during_dwell(self):
        self.assertEqual(p.room_phase(-100), "green")
        self.assertEqual(p.room_phase(0), "green")

    def test_yellow_during_ramp(self):
        self.assertEqual(p.room_phase(1), "yellow")
        self.assertEqual(p.room_phase(p.RAMP_SECONDS - 1), "yellow")

    def test_red_after_ramp(self):
        self.assertEqual(p.room_phase(p.RAMP_SECONDS), "red")
        self.assertEqual(p.room_phase(p.RAMP_SECONDS * 10), "red")


class RoomTimerTests(unittest.TestCase):
    def test_green_counts_down_the_whole_window(self):
        t = p.room_timer(now=1000.0, started_at=1000.0)
        self.assertEqual(t["phase"], "green")
        self.assertEqual(t["seconds_remaining"], p.DWELL_SECONDS + p.RAMP_SECONDS)

    def test_counts_down_to_zero_at_detonation(self):
        now = 1000.0 + p.DWELL_SECONDS + p.RAMP_SECONDS
        t = p.room_timer(now=now, started_at=1000.0)
        self.assertEqual(t["phase"], "red")
        self.assertEqual(t["seconds_remaining"], 0)

    def test_never_negative(self):
        t = p.room_timer(now=1000.0 + p.DWELL_SECONDS + p.RAMP_SECONDS + 99999, started_at=1000.0)
        self.assertEqual(t["seconds_remaining"], 0)


class AttackerDelayTests(unittest.TestCase):
    def test_holds_base_delay_until_dwell_ends(self):
        a = p.Attacker("student01", "repeat-exploit", random.Random(1))
        self.assertEqual(a.delay(-100), a.base_delay)
        self.assertEqual(a.delay(0), a.base_delay)

    def test_ramps_down_toward_floor(self):
        a = p.Attacker("student01", "repeat-exploit", random.Random(1))
        a.base_delay = 100.0
        self.assertAlmostEqual(a.delay(0), 100.0)
        halfway = a.delay(p.RAMP_SECONDS / 2)
        self.assertLess(halfway, 100.0)
        self.assertGreater(halfway, p.RAMP_FLOOR)
        self.assertAlmostEqual(a.delay(p.RAMP_SECONDS), p.RAMP_FLOOR)
        self.assertAlmostEqual(a.delay(p.RAMP_SECONDS * 10), p.RAMP_FLOOR)  # never overshoots

    def test_benign_never_ramps(self):
        a = p.Attacker("student01", "benign", random.Random(1))
        self.assertEqual(a.delay(p.RAMP_SECONDS * 5), a.base_delay)

    def test_unknown_style_rejected(self):
        with self.assertRaises(ValueError):
            p.Attacker("student01", "nonsense")


class ShouldExploitTests(unittest.TestCase):
    def test_benign_never_exploits(self):
        a = p.Attacker("student01", "benign", random.Random(1))
        for elapsed in (0, 1, p.RAMP_SECONDS, p.RAMP_SECONDS * 100):
            self.assertFalse(a.should_exploit(elapsed))

    def test_never_exploits_during_dwell(self):
        a = p.Attacker("student01", "repeat-exploit", random.Random(1))
        self.assertFalse(a.should_exploit(-1))
        self.assertFalse(a.should_exploit(0))

    def test_ceiling_climbs_during_ramp(self):
        rng = random.Random(7)
        a = p.Attacker("student01", "repeat-exploit", rng)
        early = sum(a.should_exploit(0.01) for _ in range(500))
        late = sum(a.should_exploit(p.RAMP_SECONDS * 0.9) for _ in range(500))
        self.assertLess(early, 50)
        self.assertGreater(late, 200)

    def test_always_exploits_once_detonated(self):
        a = p.Attacker("student01", "recon-heavy", random.Random(1))  # even the low-ceiling style
        a.detonate_jitter = 0.0
        for _ in range(20):
            self.assertTrue(a.should_exploit(p.RAMP_SECONDS + 1))


class AttemptTests(unittest.TestCase):
    def test_recon_during_dwell_never_touches_exploit_fn(self):
        a = p.Attacker("student01", "repeat-exploit", random.Random(1))
        calls = []
        outcome, extra = a.attempt(-5, lambda: calls.append(1) or True)
        self.assertEqual(outcome, "recon")
        self.assertEqual(calls, [])

    def test_dump_success_once_detonated_and_vulnerable(self):
        a = p.Attacker("student01", "recon-heavy", random.Random(1))
        a.detonate_jitter = 0.0
        outcome, _ = a.attempt(p.RAMP_SECONDS + 1, lambda: True)
        self.assertEqual(outcome, "dump_success")
        self.assertTrue(a.breached)

    def test_exploit_attempt_once_detonated_and_patched(self):
        a = p.Attacker("student01", "recon-heavy", random.Random(1))
        a.detonate_jitter = 0.0
        outcome, _ = a.attempt(p.RAMP_SECONDS + 1, lambda: False)
        self.assertEqual(outcome, "exploit_attempt")

    def test_contained_fires_once_after_a_breach_is_patched(self):
        a = p.Attacker("student01", "recon-heavy", random.Random(1))
        a.detonate_jitter = 0.0
        a.breached = True
        outcome, _ = a.attempt(p.RAMP_SECONDS + 1, lambda: False)
        self.assertEqual(outcome, "contained")
        self.assertFalse(a.breached)
        outcome2, _ = a.attempt(p.RAMP_SECONDS + 1, lambda: False)
        self.assertEqual(outcome2, "exploit_attempt")

    def test_benign_never_leaves_recon_or_probe(self):
        a = p.Attacker("student01", "benign", random.Random(1))
        outcomes = {a.attempt(elapsed, lambda: True)[0] for elapsed in (-1, 1, p.RAMP_SECONDS * 5)}
        self.assertTrue(outcomes <= {"recon", "probe"})


class SwarmTests(unittest.TestCase):
    def test_dwell_elapsed_before_and_after(self):
        swarm = p.Swarm(["student01", "student02"], rng=random.Random(1), started_at=1000.0)
        self.assertEqual(swarm.dwell_elapsed(1000.0), -p.DWELL_SECONDS)
        self.assertEqual(swarm.dwell_elapsed(1000.0 + p.DWELL_SECONDS), 0)

    def test_one_attacker_per_user(self):
        users = ["student01", "student02", "student03"]
        swarm = p.Swarm(users, rng=random.Random(1), started_at=0.0)
        self.assertEqual([a.user for a in swarm.attackers], users)

    def test_deterministic_given_the_same_rng_seed(self):
        swarm1 = p.Swarm(["s1", "s2", "s3", "s4"], rng=random.Random(99), started_at=0.0)
        swarm2 = p.Swarm(["s1", "s2", "s3", "s4"], rng=random.Random(99), started_at=0.0)
        self.assertEqual([a.style for a in swarm1.attackers], [a.style for a in swarm2.attackers])
        self.assertEqual([round(a.base_delay, 6) for a in swarm1.attackers],
                         [round(a.base_delay, 6) for a in swarm2.attackers])

    def test_timer_matches_room_timer(self):
        swarm = p.Swarm(["student01"], rng=random.Random(1), started_at=500.0)
        self.assertEqual(swarm.timer(500.0), p.room_timer(500.0, 500.0))


class TimeScaleTests(unittest.TestCase):
    def test_default_and_bad_values_are_real_time(self):
        for env in ({}, {"CTF_TIME_SCALE": ""}, {"CTF_TIME_SCALE": "abc"}, {"CTF_TIME_SCALE": "0"},
                    {"CTF_TIME_SCALE": "-1"}, {"CTF_TIME_SCALE": "999"}):
            self.assertEqual(p.time_scale(env), 1.0, env)

    def test_reads_the_scale(self):
        self.assertEqual(p.time_scale({"CTF_TIME_SCALE": "0.1"}), 0.1)

    def test_attacker_pacing_scales_but_defaults_do_not_change(self):
        a1 = p.Attacker("s", "repeat-exploit", random.Random(7))
        a10 = p.Attacker("s", "repeat-exploit", random.Random(7), scale=0.1)
        self.assertAlmostEqual(a10.base_delay, a1.base_delay * 0.1)
        self.assertAlmostEqual(a10.detonate_jitter, a1.detonate_jitter * 0.1)
        self.assertAlmostEqual(a10.ramp_floor, p.RAMP_FLOOR * 0.1)
        self.assertEqual(a1.ramp_floor, p.RAMP_FLOOR)
        self.assertTrue(p.DELAY_MIN <= a1.base_delay <= p.DELAY_MAX)

    def test_swarm_passes_scale_to_every_attacker(self):
        sw = p.Swarm(["a", "b"], rng=random.Random(1), scale=0.1, dwell_seconds=48, ramp_seconds=60)
        self.assertTrue(all(a.scale == 0.1 and a.base_delay <= p.DELAY_MAX * 0.1 for a in sw.attackers))


if __name__ == "__main__":
    unittest.main()
