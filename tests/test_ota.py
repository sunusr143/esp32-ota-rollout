import unittest

from ota_rollout.device import Device
from ota_rollout.manifest import IntegrityError, build_manifest, parse_version, verify_image
from ota_rollout.rollout import RolloutController, bucket

IMG = b"fw" * 500


class ManifestTests(unittest.TestCase):
    def test_roundtrip_and_tamper_detection(self):
        m = build_manifest("1.2.0", IMG)
        verify_image(m, IMG)
        with self.assertRaisesRegex(IntegrityError, "checksum"):
            verify_image(m, b"xx" * 500)
        with self.assertRaisesRegex(IntegrityError, "size"):
            verify_image(m, IMG[:-1])

    def test_version_parsing(self):
        self.assertGreater(parse_version("1.10.0"), parse_version("1.9.9"))
        with self.assertRaises(ValueError):
            parse_version("1.2")


class DeviceTests(unittest.TestCase):
    def test_successful_update_flips_slot(self):
        d = Device("d1")
        self.assertEqual(d.apply(build_manifest("1.1.0", IMG), IMG), "updated")
        self.assertEqual((d.version, d.running), ("1.1.0", "B"))

    def test_failed_self_test_reverts_to_old_slot(self):
        d = Device("d1")
        self.assertEqual(d.apply(build_manifest("1.1.0", IMG), IMG, lambda dev: False), "rolled_back")
        self.assertEqual((d.version, d.running), ("1.0.0", "A"))
        self.assertEqual(d.slots["B"], "")

    def test_corrupt_image_rejected_and_running_slot_untouched(self):
        d = Device("d1")
        out = d.apply(build_manifest("1.1.0", IMG), b"corrupt")
        self.assertTrue(out.startswith("rejected:"))
        self.assertEqual((d.version, d.running), ("1.0.0", "A"))

    def test_downgrade_and_same_version_rejected(self):
        d = Device("d1", version="1.5.0")
        self.assertEqual(d.apply(build_manifest("1.4.0", IMG), IMG), "rejected:not_newer")
        self.assertEqual(d.apply(build_manifest("1.5.0", IMG), IMG), "rejected:not_newer")

    def test_min_version_requires_intermediate_update(self):
        d = Device("d1")
        self.assertEqual(d.apply(build_manifest("2.0.0", IMG, min_version="1.5.0"), IMG), "rejected:needs_intermediate_update")

    def test_two_sequential_updates_alternate_slots(self):
        d = Device("d1")
        d.apply(build_manifest("1.1.0", IMG), IMG)
        d.apply(build_manifest("1.2.0", IMG), IMG)
        self.assertEqual((d.version, d.running), ("1.2.0", "A"))


class RolloutTests(unittest.TestCase):
    def test_bucket_is_stable_and_in_range(self):
        self.assertEqual(bucket("esp32-0001"), bucket("esp32-0001"))
        self.assertTrue(all(0 <= bucket(f"d{i}") < 100 for i in range(500)))

    def test_cohorts_are_nested(self):
        c = RolloutController([5, 25, 100])
        ids = [f"d{i}" for i in range(300)]
        first = {i for i in ids if c.eligible(i)}
        c.stage = 1
        second = {i for i in ids if c.eligible(i)}
        self.assertTrue(first <= second and len(second) > len(first))

    def test_holds_until_enough_reports_then_advances(self):
        c = RolloutController([5, 25, 100], min_reports=3)
        ids = [f"d{i}" for i in range(400) if bucket(f"d{i}") < 5]
        for i in ids[:2]:
            c.report(i, True)
        self.assertEqual(c.evaluate(), "hold")
        c.report(ids[2], True)
        self.assertEqual(c.evaluate(), "advance")
        self.assertEqual(c.percent, 25)

    def test_halts_on_failures_and_stops_new_devices(self):
        c = RolloutController([5, 25, 100], max_failure_rate=0.05, min_reports=5)
        ids = [f"d{i}" for i in range(400) if bucket(f"d{i}") < 5]
        for i in ids[:4]:
            c.report(i, i != ids[0])
        self.assertEqual(c.evaluate(), "halt")
        self.assertTrue(c.halted)
        self.assertFalse(any(c.eligible(f"d{i}") for i in range(400)))

    def test_invalid_config(self):
        with self.assertRaises(ValueError):
            RolloutController([25, 5, 100])
        with self.assertRaises(ValueError):
            RolloutController([5, 25])


if __name__ == "__main__":
    unittest.main()
