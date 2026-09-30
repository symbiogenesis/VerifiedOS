# SPDX-License-Identifier: Apache-2.0
"""The opam client's owner reads a root's repositories from its own files, in each
layout a reviewed client leaves them, refuses to vouch for an incomplete reading, and
installs the client only as the reviewed bytes and never over another file.

Roots are written here in opam's layouts rather than made by a client, so the cases run
on any lane: a repository's metadata unpacked in a directory, tarred under a directory
named for it as a 2.2-format root keeps it, and tarred flat, its `repo` file at the top
of the archive, as the 2.6 format rewrites it.
"""

import io
import sys
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import opam_client

# How each layout stores one repository's metadata.
LAYOUTS = ("unpacked", "nested", "flat")


def opam_root(root: Path, layout: str, stamps: dict[str, str] | None = None,
              configured: tuple[tuple[str, str], ...] = opam_client.OPAM_REPOSITORIES) -> None:
    """A root configured with `configured`, each repository's metadata in `layout` and
    carrying the stamp `stamps` names for it, or no stamp line where it names none."""
    stamps = {name: f"{name}-stamp" for name, _ in configured} if stamps is None else stamps
    fmt = "2.6" if layout == "flat" else "2.2"
    root.mkdir(parents=True, exist_ok=True)
    (root / "config").write_bytes(
        f'opam-version: "2.0"\nopam-root-version: "{fmt}"\n'.encode())
    repo = root / "repo"
    repo.mkdir()
    listing = "".join(f'  "{name}" {{"{url}"}}\n' for name, url in configured)
    (repo / "repos-config").write_bytes(
        f'opam-version: "2.0"\nrepositories: [\n{listing}]\n'.encode())
    for name, _ in configured:
        stamp = f'stamp: "{stamps[name]}"\n' if stamps.get(name) else ""
        payload = f'opam-version: "2.0"\nupstream: "https://example.invalid"\n{stamp}'.encode()
        package = b'opam-version: "2.0"\n'
        if layout == "unpacked":
            (repo / name / "packages" / "p" / "p.1").mkdir(parents=True)
            (repo / name / "repo").write_bytes(payload)
            (repo / name / "packages" / "p" / "p.1" / "opam").write_bytes(package)
            continue
        prefix = "" if layout == "flat" else f"{name}/"
        with tarfile.open(repo / f"{name}.tar.gz", "w:gz") as archive:
            for member_name, data in ((f"{prefix}packages/p/p.1/opam", package),
                                      (f"{prefix}repo", payload)):
                member = tarfile.TarInfo(member_name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))


def _reads_every_layout() -> None:
    """Each layout yields every configured repository with its URL and its stamp."""
    for layout in LAYOUTS:
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            root = Path(td) / "opam"
            opam_root(root, layout)
            found = opam_client.repositories(root)
            ensure(found == [{"name": name, "url": url, "stamp": f"{name}-stamp"}
                             for name, url in opam_client.OPAM_REPOSITORIES],
                   f"the {layout} layout reads every repository and its stamp, got {found}")
            ensure(opam_client.root_format(root) == ("2.6" if layout == "flat" else "2.2"),
                   f"the {layout} root's format is its config's")


def _reports_what_it_could_not_read() -> None:
    """`repositories` is the report's reading: it answers with what it found."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td) / "opam"
        ensure(opam_client.repositories(root) == [] and opam_client.root_format(root) == "",
               "a root that does not exist configures nothing and states no format")
        opam_root(root, "flat", stamps={})
        ensure(all(repo["stamp"] == "" for repo in opam_client.repositories(root)),
               "a repository whose metadata states no stamp reads as unstamped")


def _initialized_root_is_complete() -> None:
    """A record vouches for a root only when every owned repository and stamp is read."""
    owned = opam_client.OPAM_REPOSITORIES

    def refusal(*, built: bool = True, stamps: dict[str, str] | None = None,
                configured: tuple[tuple[str, str], ...] = owned) -> str:
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            root = Path(td) / "opam"
            if built:
                opam_root(root, "flat", stamps, configured)
            try:
                found = opam_client.initialized_repositories(root)
            except ValueError as err:
                return str(err)
            ensure([repo["name"] for repo in found]
                   == [name for name, _ in opam_client.OPAM_REPOSITORIES],
                   f"an accepted root yields every repository, got {found}")
            return ""

    ensure(refusal() == "", "a complete 2.6 root is accepted")
    ensure("no repositories" in refusal(built=False),
           "an unreadable listing is refused, not recorded as []")
    ensure("no repositories" in refusal(configured=()),
           "a configuration naming no repository is refused")
    (default, url), *others = owned
    ensure("is configured with" in refusal(configured=((default, url),)),
           "a root missing an owned repository is refused")
    ensure("is configured with" in refusal(configured=((default, url + "/elsewhere"),
                                                       *others)),
           "a repository at another URL is refused")
    ensure(f"no metadata stamp for {default}" in refusal(
               stamps={name: "s" for name, _ in others}),
           "an unread stamp is refused, not recorded as ''")


def _initialized_format_is_the_clients() -> None:
    """A root just initialized declares the reviewed client's format, or is refused."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        for layout in ("flat", "nested"):
            root = Path(td) / layout
            opam_root(root, layout)
            try:
                found = opam_client.initialized_format(root)
            except ValueError as err:
                found = str(err)
            want = (opam_client.OPAM_ROOT_FORMAT if layout == "flat" else
                    f"format 2.2, not the reviewed client's {opam_client.OPAM_ROOT_FORMAT}")
            ensure(want in found, f"a {layout} root's format reads {found!r}")
        try:
            opam_client.initialized_format(Path(td) / "absent")
        except ValueError as err:
            ensure("format none" in str(err), f"an absent root states no format: {err}")
        else:
            raise AssertionError("a root that states no format was accepted")


def _install_verifies_and_never_replaces() -> None:
    """The one install route fetches the reviewed asset against its reviewed digest,
    leaves it executable, and refuses a different file already at the destination."""
    architecture, expected = opam_client.OPAM_HASHES["x86_64"]
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        target = Path(td) / "bin" / "opam"
        fetched: list[tuple[str, str]] = []

        def download(url: str, destination: Path, digest: str) -> None:
            fetched.append((url, digest))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"client")

        with patch.object(opam_client.receipts, "download", side_effect=download):
            opam_client.install(target, "x86_64")
        ensure(fetched == [(opam_client.release_url(architecture), expected)]
               and target.read_bytes() == b"client",
               f"the reviewed asset is fetched against its digest, got {fetched}")
        ensure(sys.platform == "win32" or target.stat().st_mode & 0o111 == 0o111,
               "the installed client is executable")
        try:
            opam_client.install(target, "riscv64")
        except ValueError as err:
            ensure("no reviewed opam binary for riscv64" in str(err), f"said {err}")
        else:
            raise AssertionError("a machine with no reviewed binary was installed for")
        other = Path(td) / "usr" / "opam"
        other.parent.mkdir()
        other.write_bytes(b"a distribution's client")
        try:
            opam_client.install(other, "x86_64")
        except ValueError as err:
            ensure("does not match" in str(err), f"said {err}")
        else:
            raise AssertionError("a different client at the destination was accepted")
        ensure(other.read_bytes() == b"a distribution's client",
               "a different file at the destination is kept, not replaced")


def cases() -> list[Case]:
    return [
        Case("reads-every-layout", _reads_every_layout),
        Case("reports-what-it-could-not-read", _reports_what_it_could_not_read),
        Case("initialized-root-is-complete", _initialized_root_is_complete),
        Case("initialized-format-is-the-clients", _initialized_format_is_the_clients),
        Case("install-verifies-and-never-replaces", _install_verifies_and_never_replaces),
    ]
