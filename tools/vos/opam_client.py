# SPDX-License-Identifier: Apache-2.0
"""The reviewed opam client, and the package repositories every project switch reads.

Guest bootstrap downloads a client and a developer's guest carries one of its own, and
the two have to agree for a reason no switch lock records: a Sail switch reports the
client that built it in its version string, `sail @ opam-v<client> <release>`, so one
lock built under two clients yields two identities. This module is the one owner of
the client's reviewed release and its per-architecture SHA-256 values, which
[guest bootstrap](../ci/bootstrap_guest.py) verifies its download against and
[`run.py provision`](cli/provision.py) holds the installed client to. A client is
replaced deliberately rather than repaired: each release upgrades the root's format
one way, after which an earlier client cannot read it.

The locks fix package versions but not the metadata they were resolved from, which the
repositories publish and revise in place. What a root was resolved against is its
repositories' URLs and the `stamp` each one's `repo` file carries, and both readers
record them. They are read from the root's own files rather than by running opam,
because a client newer than the root's format would upgrade the root to answer.

Guest CI's download and installed-toolchain caches must hash this file, because an
opam root restored under another client is another root.
"""

import re
import tarfile
from pathlib import Path

OPAM_VERSION = "2.6.0"

# The release's asset suffix and its SHA-256, per `platform.machine()`. Each matches
# the digest GitHub publishes for the asset and the opam dev team's signature over
# it, which THIRD-PARTY.md records as reviewed.
OPAM_HASHES: dict[str, tuple[str, str]] = {
    "aarch64": ("arm64", "aeaeb4294a9abaa7d37844d9138230125933c648e631da2eec888b5e4ce55bde"),
    "x86_64": ("x86_64", "a59184447f881005dae70b2ae455c3a7e9549834a41c635c49a5a28235eca758"),
}

# The repositories a root is initialized with, the first as `opam init`'s default and
# the rest added unselected; the prover switch names both in its `--repos`.
OPAM_REPOSITORIES: tuple[tuple[str, str], ...] = (
    ("default", "https://opam.ocaml.org"),
    ("rocq-released", "https://rocq-prover.org/opam/released"),
)

_CONFIGURED_RE = re.compile(r'"([^"\r\n]+)"\s*\{\s*"([^"\r\n]+)"')
_STAMP_RE = re.compile(r'(?m)^stamp:\s*"([^"\r\n]*)"')
_FORMAT_RE = re.compile(r'(?m)^opam-root-version:\s*"([^"\r\n]*)"')


def release_url(architecture: str) -> str:
    """Where the reviewed release's binary for one asset suffix is published."""
    return (f"https://github.com/ocaml/opam/releases/download/{OPAM_VERSION}/"
            f"opam-{OPAM_VERSION}-{architecture}-linux")


def root_format(root: Path) -> str:
    """The format a root's own `config` declares, empty where it states none."""
    try:
        found = _FORMAT_RE.search((root / "config").read_text(encoding="utf-8"))
    except OSError:
        return ""
    return str(found.group(1)) if found else ""


def _repo_file(root: Path, name: str) -> str:
    """One repository's `repo` file, kept as a directory or as opam's tarred form."""
    unpacked = root / "repo" / name / "repo"
    if unpacked.is_file():
        return unpacked.read_text(encoding="utf-8", errors="replace")
    packed = root / "repo" / f"{name}.tar.gz"
    if not packed.is_file():
        return ""
    try:
        with tarfile.open(packed, "r:gz") as archive:
            for member in archive.getmembers():
                if member.isfile() and Path(member.name).name == "repo" and (
                        len(Path(member.name).parts) <= 2):
                    stream = archive.extractfile(member)
                    if stream is not None:
                        return stream.read().decode("utf-8", errors="replace")
    except (OSError, tarfile.TarError):
        return ""
    return ""


def repositories(root: Path) -> list[dict[str, str]]:
    """Every repository a root is configured with: its name, its URL and the stamp its
    metadata carries, in the root's own order. Empty where the root configures none."""
    try:
        text = (root / "repo" / "repos-config").read_text(encoding="utf-8")
    except OSError:
        return []
    found: list[dict[str, str]] = []
    for name, url in _CONFIGURED_RE.findall(text):
        stamp = _STAMP_RE.search(_repo_file(root, name))
        found.append({"name": name, "url": url, "stamp": stamp.group(1) if stamp else ""})
    return found
