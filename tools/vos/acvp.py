# SPDX-License-Identifier: Apache-2.0
"""The pinned NIST ACVP-Server revision and the identity of every file taken from it.

The ML-KEM and ML-DSA campaigns under `proofs/campaigns/` and the boot-signature
comparison fetch official inputs from one immutable commit of `usnistgov/ACVP-Server`.
This module is the one place that commit and each fetched file's SHA-256 are written,
so a revision advance or a re-measured file is one edit here and every consumer moves
with it. The campaigns import it and restate neither.

A fetch goes through `receipts.download`, which refuses a cached copy whose bytes are
not the pinned ones and publishes a new download only after verifying it, so an
interrupted transfer never leaves a partial file behind. The bytes a caller receives
are verified again after they are read, and a read of a file some earlier step placed
is held to the same digest, so no consumer parses an input it has not authenticated.
"""

import hashlib
from pathlib import Path

from vos import receipts

REVISION = "975de31eb83d87039ec88934fdc47d8c312b892d"
BASE = f"https://raw.githubusercontent.com/usnistgov/ACVP-Server/{REVISION}/"

# The repository README, which states the terms the downloaded test data carry and
# which the campaigns retain beside their inputs.
NOTICE = "README.md"
NOTICE_SHA = "d5a569884ee83bd1c4737042d0a2cc7d68c6950690f75a73ef14f505a9aa3555"

# Each consumed family's `internalProjection.json`, keyed by its directory under
# `gen-val/json-files/`.
VECTORS: dict[str, str] = {
    "ML-KEM-keyGen-FIPS203": "d7a62a2c3476957f56dd8d24f9004ea6776ccfe995ffe71a65bb9506dc9c7b1b",
    "ML-KEM-encapDecap-FIPS203": "a556952ce869bb89c3a3196a701dad89647c193a34c86eafb61a9d710d5b810f",
    "ML-DSA-keyGen-FIPS204": "e67ee6540d40e11506c3c4e3b1f79fc1cefcd49820db99fc61f87cc8ba463baf",
    "ML-DSA-sigGen-FIPS204": "72dcaf5f69853ca267ccd16af9cb40949786aca0fcfbf05d1ebeba132b93af22",
    "ML-DSA-sigVer-FIPS204": "47cdd6314c7f746d02421ffcba89d4dbc7bb875ac49e07a029fdfc26fba55437",
    "SLH-DSA-sigVer-FIPS205": "a013fc2104f4ed4799d96d51141f65b965969b2cf10646626a021b6d456ce792",
}


def vector_path(family: str) -> str:
    """A pinned family's internal projection, relative to the revision's root."""
    if family not in VECTORS:
        raise ValueError(f"{family} is not a pinned ACVP family")
    return f"gen-val/json-files/{family}/internalProjection.json"


def pinned() -> dict[str, str]:
    """Every pinned file, relative to the revision's root, with its SHA-256."""
    return {NOTICE: NOTICE_SHA,
            **{vector_path(family): digest for family, digest in VECTORS.items()}}


def url(relative: str) -> str:
    """The immutable address of one pinned file."""
    _expected(relative)
    return BASE + relative


def _expected(relative: str) -> str:
    expected = pinned().get(relative)
    if expected is None:
        raise ValueError(f"{relative} is not a pinned ACVP file")
    return expected


def read(relative: str, path: Path) -> bytes:
    """The bytes at `path`, refused unless they are the pinned file's."""
    expected = _expected(relative)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"{path}: SHA256 is not the pinned {relative} ({expected})")
    return data


def fetch(relative: str, target: Path) -> bytes:
    """One pinned file's verified bytes, downloaded once to `target` and reused after."""
    receipts.download(url(relative), target, _expected(relative))
    return read(relative, target)
