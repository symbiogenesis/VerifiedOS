# SPDX-License-Identifier: Apache-2.0
"""The opam client's owner reads a root's repositories from its own files, in each
layout a reviewed client leaves them, and refuses to vouch for an incomplete reading.

Roots are written here in opam's layouts rather than made by a client, so the cases run
on any lane: a repository's metadata unpacked in a directory, tarred under a directory
named for it as a 2.2-format root keeps it, and tarred flat, its `repo` file at the top
of the archive, as the 2.6 format rewrites it.
"""

import io
import tarfile
import tempfile
from pathlib import Path

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


def cases() -> list[Case]:
    return [
        Case("reads-every-layout", _reads_every_layout),
        Case("reports-what-it-could-not-read", _reports_what_it_could_not_read),
        Case("initialized-root-is-complete", _initialized_root_is_complete),
    ]
