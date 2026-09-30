# SPDX-License-Identifier: Apache-2.0
"""The reviewed opam client, and the package repositories every project switch reads.

Guest bootstrap downloads a client and a developer's guest carries one of its own, and
the two have to agree for a reason no switch lock records: a Sail switch reports the
client that built it in its version string, `sail @ opam-v<client> <release>`, so one
lock built under two clients yields two identities. This module is the one owner of
the client's reviewed release and its per-architecture SHA-256 values, which
[guest bootstrap](../ci/bootstrap_guest.py) verifies its download against and
[`run.py provision`](cli/provision.py) holds the installed client to, of the one
route both take to install it, and of the one route both take to create a root on the
package repositories. A client is
replaced deliberately rather than repaired: a client rewrites a root whose format is
older than its own to its own format, one way, after which an earlier client cannot
read it. Not every release raises the format, so the reviewed client's is recorded
here beside its release rather than inferred from the version.

The locks fix package versions but not the metadata they were resolved from, which the
repositories publish and revise in place. What a root was resolved against is its
repositories' URLs and the `stamp` each one's `repo` file carries, and both readers
record them. They are read from the root's own files rather than by running opam,
because a client newer than the root's format would upgrade the root to answer.

The route has system prerequisites of its own, which this module also owns, because
`opam init` refuses to create a root without them and every switch recipe then fails
in a root that does not stand.

Guest CI's download and installed-toolchain caches must hash this file, because an
opam root restored under another client is another root.
"""

import re
import tarfile
from pathlib import Path

from vos import receipts

OPAM_VERSION = "2.6.0"

# The root format the reviewed client writes, the `opam-root-version` a root it creates
# or rewrites declares; 2.6.0's release notes record raising it to 2.6. Guest bootstrap
# holds a root it initializes to this, and `run.py provision` reads it to say whether
# moving a developer's root to the reviewed client rewrites that root.
OPAM_ROOT_FORMAT = "2.6"

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

# The one route that creates a root, in the root `OPAMROOT` names: a bare `opam init`
# on the first repository, with no shell setup and no opamrc, then every other
# repository added unselected, each switch naming the repositories it resolves from.
# Guest bootstrap runs it in its private root, and `run.py provision --install-opam`
# where no root stands or where `root_resumable` reads one the route stopped partway
# through. Repeating it over a root it made finishes that root and changes a finished
# one in nothing: `opam init` reports the root already initialized and exits 0, and
# adding a repository the root already carries at that URL reports no changes and
# exits 0, as the reviewed client did over a private root on the guest.
CREATE_ROOT: tuple[tuple[str, ...], ...] = (
    ("opam", "init", "--bare", "--no-setup", "--no-opamrc", "-y", *OPAM_REPOSITORIES[0]),
    *(("opam", "repository", "add", name, url, "--dont-select", "-y")
      for name, url in OPAM_REPOSITORIES[1:]),
)

# The Debian and Ubuntu packages `CREATE_ROOT` needs on the machine it runs on. The
# reviewed client's `opam init` refuses to create a root, exiting 50 before it writes
# one, unless curl or wget, tar, unzip and bwrap are on PATH: bwrap because the root it
# creates sandboxes package builds. curl is the download tool here, and it fetches the
# HTTPS repositories against the certificate store `ca-certificates` carries, which the
# distribution's curl library only recommends. GNU patch, diff and getconf are not
# among them, because this client computes and applies patches itself and no longer
# requires getconf. Guest bootstrap installs these, and `run.py provision` probes and
# installs each ahead of the opam row.
ROOT_PREREQUISITES: tuple[str, ...] = ("bubblewrap", "ca-certificates", "curl", "tar", "unzip")

_CONFIGURED_RE = re.compile(r'"([^"\r\n]+)"\s*\{\s*"([^"\r\n]+)"')
_STAMP_RE = re.compile(r'(?m)^stamp:\s*"([^"\r\n]*)"')
_FORMAT_RE = re.compile(r'(?m)^opam-root-version:\s*"([^"\r\n]*)"')


def release_url(architecture: str) -> str:
    """Where the reviewed release's binary for one asset suffix is published."""
    return (f"https://github.com/ocaml/opam/releases/download/{OPAM_VERSION}/"
            f"opam-{OPAM_VERSION}-{architecture}-linux")


def install(destination: Path, machine: str) -> None:
    """Put the reviewed client for `machine` at `destination`, executable.

    The one install route, which guest bootstrap takes into its private root and
    `run.py provision --install-opam` onto a machine with no client. The download is
    verified against the reviewed SHA-256 before it is published at `destination`, and
    a file already there is kept only when it is that client: any other is refused
    rather than replaced.
    """
    if machine not in OPAM_HASHES:
        raise ValueError(f"no reviewed opam binary for {machine}")
    architecture, expected = OPAM_HASHES[machine]
    receipts.download(release_url(architecture), destination, expected)
    destination.chmod(0o755)


def root_format(root: Path) -> str:
    """The format a root's own `config` declares, empty where it states none."""
    try:
        found = _FORMAT_RE.search((root / "config").read_text(encoding="utf-8"))
    except OSError:
        return ""
    return str(found.group(1)) if found else ""


def root_exists(root: Path) -> bool:
    """Whether a root stands at `root`, which opam marks by the root's `config` file:
    `opam init` initializes a directory without one, and every other command refuses it
    as no root."""
    return (root / "config").is_file()


def format_key(fmt: str) -> tuple[int, ...]:
    """A root format's release numbers, for ordering two formats: `2.6~alpha` reads as
    2.6, which is as near as a report needs to come to opam's own ordering."""
    return tuple(int(part) for part in re.findall(r"\d+", fmt.partition("~")[0]))


def newer_than_reviewed(fmt: str) -> bool:
    """Whether a stated root format is newer than `OPAM_ROOT_FORMAT`. The reviewed
    client still reads such a root, but refuses every command that takes its write lock
    as "more recent than this version of opam", a switch creation among them."""
    return bool(fmt) and format_key(fmt) > format_key(OPAM_ROOT_FORMAT)


def root_gaps(root: Path) -> list[str]:
    """What a root that stands lacks of one the reviewed client can use as `CREATE_ROOT`
    makes it, as clauses: a stated format no newer than `OPAM_ROOT_FORMAT`, each of
    `OPAM_REPOSITORIES` at its URL, and each of those with its metadata stamp read, as
    `initialized_repositories` holds a root just created. Empty for a complete root."""
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
    """Whether a standing root is one `CREATE_ROOT` stopped partway through, which
    running the route again finishes: in `OPAM_ROOT_FORMAT`, configured with exactly the
    route's leading repositories, at least the one `opam init` fetched and not every
    one, each at its owned URL and with its stamp read.

    A root whose first repository's stamp is unread is not one: `opam init` over a
    root that stands reports it initialized without fetching anything, so the route run
    again would leave that repository unread and the root as incomplete as it found it.
    """
    if not root_exists(root) or root_format(root) != OPAM_ROOT_FORMAT:
        return False
    found = repositories(root)
    if any(not repo["stamp"] for repo in found):
        return False
    configured = {(repo["name"], repo["url"]) for repo in found}
    return any(configured == set(OPAM_REPOSITORIES[:count])
               for count in range(1, len(OPAM_REPOSITORIES)))


def initialized_format(root: Path) -> str:
    """The format of a root the reviewed client just initialized, refused unless it is
    `OPAM_ROOT_FORMAT`, so the recorded format cannot drift from the client unseen."""
    found = root_format(root)
    if found != OPAM_ROOT_FORMAT:
        raise ValueError(f"{root} declares root format {found or 'none'}, not the "
                         f"reviewed client's {OPAM_ROOT_FORMAT}")
    return found


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
    metadata carries, in the root's own order. Empty where the root configures none,
    and a stamp is empty where it cannot be read, because a report on a developer's root
    says what it found rather than refusing."""
    try:
        text = (root / "repo" / "repos-config").read_text(encoding="utf-8")
    except OSError:
        return []
    found: list[dict[str, str]] = []
    for name, url in _CONFIGURED_RE.findall(text):
        stamp = _STAMP_RE.search(_repo_file(root, name))
        found.append({"name": name, "url": url, "stamp": stamp.group(1) if stamp else ""})
    return found


def initialized_repositories(root: Path) -> list[dict[str, str]]:
    """`repositories` over a root just initialized on `OPAM_REPOSITORIES`, refused unless
    it is configured with exactly those names and URLs and every one's stamp was read.

    A record of what the snapshots were resolved against is evidence only when it is
    complete; `repositories` reads an unreadable configuration as none and an unread
    stamp as empty, which a record would otherwise carry as though it were the answer.
    """
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
