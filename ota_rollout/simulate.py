"""Simulate a fleet rollout:  python -m ota_rollout.simulate [--bad]"""
from __future__ import annotations

import argparse

from .device import Device
from .manifest import build_manifest
from .rollout import RolloutController


def run(fleet_size: int, bad: bool) -> None:
    image = b"firmware-v1.1.0" * 100
    manifest = build_manifest("1.1.0", image)
    fleet = [Device(f"esp32-{i:04d}") for i in range(fleet_size)]
    ctl = RolloutController([5, 25, 100], max_failure_rate=0.05, min_reports=5)
    self_test = (lambda d: False) if bad else (lambda d: True)  # a bad release fails its post-boot self-test

    for rnd in range(1, 8):
        for d in fleet:
            if ctl.eligible(d.device_id) and d.device_id not in ctl.reports:
                ctl.report(d.device_id, d.apply(manifest, image, self_test) == "updated")
        stage_pct = ctl.percent
        verdict = ctl.evaluate()
        updated = sum(d.version == "1.1.0" for d in fleet)
        print(f"round {rnd}: stage={stage_pct:>3}% reports={len(ctl.reports):>3} updated={updated:>3} -> {verdict}")
        if verdict in ("halt", "complete"):
            break
    on_old = sum(d.version == "1.0.0" for d in fleet)
    print(f"result: {len(fleet) - on_old}/{len(fleet)} on 1.1.0, {on_old} still on 1.0.0, halted={ctl.halted}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bad", action="store_true", help="release that fails its self-test")
    ap.add_argument("--fleet", type=int, default=200)
    a = ap.parse_args()
    run(a.fleet, a.bad)
