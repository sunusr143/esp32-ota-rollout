from __future__ import annotations

import hashlib
from typing import Dict, Optional, Tuple


class IntegrityError(Exception):
    pass


def parse_version(v: str) -> Tuple[int, int, int]:
    try:
        major, minor, patch = (int(x) for x in v.split("."))
    except ValueError:
        raise ValueError(f"version must look like 1.2.3, got {v!r}") from None
    return major, minor, patch


def build_manifest(version: str, image: bytes, min_version: Optional[str] = None) -> Dict[str, object]:
    parse_version(version)
    if min_version:
        parse_version(min_version)
    return {"version": version, "size": len(image), "sha256": hashlib.sha256(image).hexdigest(), "min_version": min_version}


def verify_image(manifest: Dict[str, object], image: bytes) -> None:
    """Integrity check: size and SHA-256 must match the manifest.

    This is integrity only. Authenticity (a signature over the manifest, checked against a key
    baked into the device) is the next layer and is not implemented here.
    """
    if len(image) != manifest["size"]:
        raise IntegrityError("size mismatch")
    if hashlib.sha256(image).hexdigest() != manifest["sha256"]:
        raise IntegrityError("checksum mismatch")
