# SPDX-License-Identifier: Apache-2.0
"""Reviewed opam client release, root format, and repository initialization.

Both [guest bootstrap](../ci/bootstrap_guest.py) and [`run.py provision`](cli/provision.py)
share this module's pinned release, per-architecture SHA-256 digests, root format, package
repositories, and initialization commands so that Sail switches (`sail @ opam-v<client>`)
and opam roots stay identical across CI and developer environments.
"""

import re
import tarfile
from itertools import zip_longest
from pathlib import Path

from vos import receipts

OPAM_VERSION = "2.6.1"

# Root format (`opam-root-version`) written by the reviewed client.
OPAM_ROOT_FORMAT = "2.6"

# Per-architecture release asset suffix and reviewed SHA-256 digest (`THIRD-PARTY.md`).
OPAM_HASHES: dict[str, tuple[str, str]] = {
    "aarch64": ("arm64", "8b24ef2f3f44a31763f54878454fb52afa1f2db7e00abed58b8d4e7ee7e290a6"),
    "x86_64": ("x86_64", "b533d393a6967150d6ef41cb3d71e147e93ecbabeb59e921aa412c0ae79ebe3d"),
}

# Repositories configured on root initialization (`default` selected, others `--dont-select`).
OPAM_REPOSITORIES: tuple[tuple[str, str], ...] = (
    ("default", "https://opam.ocaml.org"),
    ("rocq-released", "https://rocq-prover.org/opam/released"),
)

# Commands to initialize a fresh opam root at `OPAMROOT` and register repositories.
CREATE_ROOT: tuple[tuple[str, ...], ...] = (
    ("opam", "init", "--bare", "--no-setup", "--no-opamrc", "-y", *OPAM_REPOSITORIES[0]),
    *(("opam", "repository", "add", name, url, "--dont-select", "-y")
      for name, url in OPAM_REPOSITORIES[1:]),
)

# Debian/Ubuntu packages required on PATH/system before running `CREATE_ROOT`.
ROOT_PREREQUISITES: tuple[str, ...] = ("bubblewrap", "ca-certificates", "curl", "tar", "unzip")

_CONFIGURED_RE = re.compile(r'"([^"\r\n]+)"\s*\{\s*"([^"\r\n]+)"')
_STAMP_RE = re.compile(r'(?m)^stamp:\s*"([^"\r\n]*)"')
_FORMAT_RE = re.compile(r'(?m)^opam-root-version:\s*"([^"\r\n]*)"')


def release_url(architecture: str) -> str:
    """Return the GitHub release URL for the reviewed opam binary on `architecture`."""
    return (f"https://github.com/ocaml/opam/releases/download/{OPAM_VERSION}/"
            f"opam-{OPAM_VERSION}-{architecture}-linux")


def install(destination: Path, machine: str) -> None:
    """Download, SHA-256-verify, and mark executable the reviewed opam binary for `machine`."""
    if machine not in OPAM_HASHES:
        raise ValueError(f"no reviewed opam binary for {machine}")
    architecture, expected = OPAM_HASHES[machine]
    receipts.download(release_url(architecture), destination, expected)
    destination.chmod(0o755)


def root_format(root: Path) -> str:
    """Read `opam-root-version` from `<root>/config` (or `""` if absent/unreadable)."""
    try:
        found = _FORMAT_RE.search((root / "config").read_text(encoding="utf-8"))
    except OSError:
        return ""
    return str(found.group(1)) if found else ""


def root_exists(root: Path) -> bool:
    """Return True if `<root>/config` exists."""
    return (root / "config").is_file()


_RUN_RE = re.compile(r"([^0-9]*)([0-9]*)")


def _weight(char: str) -> int:
    """Return the Debian version-ordering weight for a non-digit character."""
    if char == "~":
        return -1
    if "A" <= char <= "Z" or "a" <= char <= "z":
        return ord(char)
    return 0x100 + ord(char)


def _compare_text(x: str, y: str) -> int:
    """Compare non-digit runs `x` and `y` under Debian version ordering (-1, 0, or 1)."""
    a, b = [*map(_weight, x), 0], [*map(_weight, y), 0]
    return (a > b) - (a < b)


def _compare_number(x: str, y: str) -> int:
    """Compare ASCII digit runs `x` and `y` numerically (-1, 0, or 1), with `""` as 0."""
    a, b = x.lstrip("0"), y.lstrip("0")
    return ((len(a), a) > (len(b), b)) - ((len(a), a) < (len(b), b))


def _compare_part(x: str, y: str) -> int:
    """Compare version components `x` and `y` across alternating non-digit and digit runs."""
    for (x_text, x_digits), (y_text, y_digits) in zip_longest(
            _RUN_RE.findall(x), _RUN_RE.findall(y), fillvalue=("", "")):
        if order := _compare_text(x_text, y_text) or _compare_number(x_digits, y_digits):
            return order
    return 0


def _components(version: str) -> tuple[str, str]:
    """Split `version` at the last `-` into `(upstream, revision)`."""
    upstream, hyphen, revision = version.rpartition("-")
    return (upstream, revision) if hyphen else (version, "")


def compare_versions(x: str, y: str) -> int:
    """Compare version strings `x` and `y` using opam/Debian Policy 5.6.12 ordering (-1, 0, 1)."""
    for x_part, y_part in zip(_components(x), _components(y), strict=True):
        if order := _compare_part(x_part, y_part):
            return order
    return 0


def newer_than_reviewed(fmt: str) -> bool:
    """Return True if root format `fmt` is newer than `OPAM_ROOT_FORMAT`."""
    return bool(fmt) and compare_versions(fmt, OPAM_ROOT_FORMAT) > 0


def older_than_reviewed(fmt: str) -> bool:
    """Return True if root format `fmt` is older than `OPAM_ROOT_FORMAT`."""
    return bool(fmt) and compare_versions(fmt, OPAM_ROOT_FORMAT) < 0


def root_gaps(root: Path) -> list[str]:
    """List format, repository, or metadata-stamp gaps in an existing opam root."""
    fmt = root_format(root)
    gaps: list[str] = []
    if not fmt:
        gaps.append("states no format")
    elif newer_than_reviewed(fmt):
        gaps.append(f"is in format {fmt}, newer than the reviewed client's "
                    f"{OPAM_ROOT_FORMAT}, which refuses to write to it")
    found = repositories(root)
    configured = {(repo["name"], repo["url"]) for repo in found}
    missing = [f"{name} {url}" for name, url in OPAM_REPOSITORIES
               if (name, url) not in configured]
    if missing:
        gaps.append(f"lacks {', '.join(missing)}")
    unstamped = [repo["name"] for repo in found
                 if (repo["name"], repo["url"]) in OPAM_REPOSITORIES and not repo["stamp"]]
    if unstamped:
        gaps.append(f"records no metadata stamp for {', '.join(unstamped)}")
    return gaps


def root_resumable(root: Path) -> bool:
    """Return True if `root` is a partially initialized `OPAM_ROOT_FORMAT` root that
    `remaining_route` can complete without running `opam init`."""
    if not root_exists(root) or root_format(root) != OPAM_ROOT_FORMAT:
        return False
    found = repositories(root)
    configured = {(repo["name"], repo["url"]) for repo in found}
    fetched = {(repo["name"], repo["url"]) for repo in found if repo["stamp"]}
    return (OPAM_REPOSITORIES[0] in fetched and fetched != set(OPAM_REPOSITORIES)
            and any(configured == set(OPAM_REPOSITORIES[:count])
                    for count in range(1, len(OPAM_REPOSITORIES) + 1)))


def remaining_route(root: Path) -> tuple[tuple[str, ...], ...]:
    """Return the `CREATE_ROOT` commands still needed to complete `root`."""
    if not root_exists(root):
        return CREATE_ROOT
    fetched = {(repo["name"], repo["url"]) for repo in repositories(root) if repo["stamp"]}
    return tuple(argv for argv in CREATE_ROOT[1:] if (argv[3], argv[4]) not in fetched)


def initialized_format(root: Path) -> str:
    """Verify and return `root`'s format after initialization (`OPAM_ROOT_FORMAT`)."""
    found = root_format(root)
    if found != OPAM_ROOT_FORMAT:
        raise ValueError(f"{root} declares root format {found or 'none'}, not the "
                         f"reviewed client's {OPAM_ROOT_FORMAT}")
    return found


def _repo_file(root: Path, name: str) -> str:
    """Read `<root>/repo/<name>/repo` or its `<name>.tar.gz` archive member."""
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
    except OSError, tarfile.TarError:
        return ""
    return ""


def repositories(root: Path) -> list[dict[str, str]]:
    """Read configured repositories (`name`, `url`, `stamp`) from `<root>/repo/repos-config`."""
    try:
        text = (root / "repo" / "repos-config").read_text(encoding="utf-8")
    except OSError:
        return []
    found: list[dict[str, str]] = []
    for name, url in _CONFIGURED_RE.findall(text):
        stamp = _STAMP_RE.search(_repo_file(root, name))
        found.append({"name": name, "url": url, "stamp": stamp.group(1) if stamp else ""})
    return found


_SWITCHES_RE = re.compile(r'(?m)^installed-switches:\s*(\[[^\]]*\]|"[^"\r\n]*")')
_QUOTED_RE = re.compile(r'"([^"\r\n]*)"')


def root_switches(root: Path) -> list[str]:
    """Read `installed-switches` from `<root>/config` without invoking opam."""
    try:
        found = _SWITCHES_RE.search((root / "config").read_text(encoding="utf-8"))
    except OSError:
        return []
    return [str(name) for name in _QUOTED_RE.findall(found.group(1))] if found else []


def initialized_repositories(root: Path) -> list[dict[str, str]]:
    """Verify that `root` has `OPAM_REPOSITORIES` configured with non-empty metadata stamps."""
    found = repositories(root)
    configured = sorted((repo["name"], repo["url"]) for repo in found)
    if configured != sorted(OPAM_REPOSITORIES):
        listed = ", ".join(f"{name} {url}" for name, url in configured) or "no repositories"
        raise ValueError(f"{root} is configured with {listed}, not "
                         f"{', '.join(f'{name} {url}' for name, url in OPAM_REPOSITORIES)}")
    unstamped = [repo["name"] for repo in found if not repo["stamp"]]
    if unstamped:
        raise ValueError(f"{root} records no metadata stamp for {', '.join(unstamped)}")
    return found
