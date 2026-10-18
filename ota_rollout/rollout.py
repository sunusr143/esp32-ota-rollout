from __future__ import annotations

import hashlib
from typing import Dict, List


def bucket(device_id: str) -> int:
    """Stable 0..99 bucket for a device. The same device always lands in the same cohort."""
    return int.from_bytes(hashlib.sha256(device_id.encode()).digest()[:4], "big") % 100


class RolloutController:
    """Health-gated staged rollout (for example 5% -> 25% -> 100%).

    A stage only advances when enough devices in it have reported and the failure rate is below
    the threshold. If the failure rate is above the threshold the rollout halts and no further
    devices become eligible. Devices that already failed rolled themselves back on-device.
    """

    def __init__(self, stages: List[int] = None, max_failure_rate: float = 0.05, min_reports: int = 5):
        self.stages = stages or [5, 25, 100]
        if self.stages != sorted(set(self.stages)) or self.stages[-1] != 100 or self.stages[0] < 1:
            raise ValueError("stages must be increasing percentages ending at 100")
        if not 0 <= max_failure_rate < 1:
            raise ValueError("max_failure_rate must be in [0, 1)")
        self.max_failure_rate, self.min_reports = max_failure_rate, min_reports
        self.stage = 0
        self.halted = False
        self.reports: Dict[str, bool] = {}

    @property
    def percent(self) -> int:
        return self.stages[self.stage]

    def eligible(self, device_id: str) -> bool:
        return not self.halted and bucket(device_id) < self.percent

    def report(self, device_id: str, success: bool) -> None:
        self.reports[device_id] = success

    def _stage_reports(self) -> List[bool]:
        return [ok for d, ok in self.reports.items() if bucket(d) < self.percent]

    def evaluate(self) -> str:
        """'halt', 'hold' (not enough data yet), 'advance', or 'complete'."""
        if self.halted:
            return "halt"
        got = self._stage_reports()
        failures = got.count(False)
        if got and failures / len(got) > self.max_failure_rate and len(got) >= min(self.min_reports, 2):
            self.halted = True
            return "halt"
        if len(got) < self.min_reports:
            return "hold"
        if self.stage == len(self.stages) - 1:
            return "complete"
        self.stage += 1
        return "advance"
