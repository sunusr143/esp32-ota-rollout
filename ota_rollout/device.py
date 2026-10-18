from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from .manifest import IntegrityError, parse_version, verify_image


@dataclass
class Device:
    """A device with two firmware slots, like an ESP32 using two OTA partitions.

    The running slot is never touched during an update. The new image goes to the other slot,
    is verified, booted once as 'pending', and only committed if the self-test passes.
    """

    device_id: str
    version: str = "1.0.0"
    slots: Dict[str, str] = field(default_factory=lambda: {"A": "1.0.0", "B": ""})
    running: str = "A"
    history: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.slots[self.running] = self.version

    @property
    def inactive(self) -> str:
        return "B" if self.running == "A" else "A"

    def apply(self, manifest: Dict[str, object], image: bytes, self_test: Callable[["Device"], bool] = lambda d: True) -> str:
        """Return 'updated', 'rolled_back' or 'rejected:<reason>'. Always ends on a bootable image."""
        target = str(manifest["version"])
        if parse_version(target) <= parse_version(self.version):
            return self._log("rejected:not_newer")
        minimum: Optional[str] = manifest.get("min_version")  # type: ignore[assignment]
        if minimum and parse_version(self.version) < parse_version(minimum):
            return self._log("rejected:needs_intermediate_update")
        try:
            verify_image(manifest, image)
        except IntegrityError as e:
            return self._log(f"rejected:{e}")

        previous = self.running
        self.slots[self.inactive] = target          # write to the inactive slot
        self.running = self.inactive                # boot into it once, pending verification
        if self_test(self):
            self.version = target                   # commit: mark the new slot valid
            return self._log("updated")
        self.running = previous                     # revert: bootloader returns to the old slot
        self.slots[self.inactive] = ""
        return self._log("rolled_back")

    def _log(self, outcome: str) -> str:
        self.history.append(outcome)
        return outcome
