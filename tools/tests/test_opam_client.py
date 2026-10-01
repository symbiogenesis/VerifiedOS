# SPDX-License-Identifier: Apache-2.0
"""The opam client's owner reads a root's repositories from its own files, in each
layout a reviewed client leaves them, refuses to vouch for an incomplete reading, names
what a standing root lacks of the one its root-creation route makes, and installs the
client only as the reviewed bytes and never over another file.

Roots are written here in opam's layouts rather than made by a client, so the cases run
on any lane: a repository's metadata unpacked in a directory, tarred under a directory
named for it as a 2.2-format root keeps it, and tarred flat, its `repo` file at the top
of the archive, as the 2.6 format rewrites it.
"""

import io
import re
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


def _root_creation_is_the_owners_route() -> None:
    """`CREATE_ROOT` initializes a bare root on the first owned repository, with no shell
    setup and no opamrc, and adds every other one unselected, in the owner's order."""
    (default, url), *others = opam_client.OPAM_REPOSITORIES
    want = (("opam", "init", "--bare", "--no-setup", "--no-opamrc", "-y", default, url),
            *(("opam", "repository", "add", name, address, "--dont-select", "-y")
              for name, address in others))
    ensure(want == opam_client.CREATE_ROOT,
           f"the route is derived from OPAM_REPOSITORIES, got {opam_client.CREATE_ROOT}")


def _root_prerequisites_are_packages() -> None:
    """The route's system prerequisites are distribution package names, each once, so
    guest bootstrap's query and provision's rows can take them as they stand."""
    packages = opam_client.ROOT_PREREQUISITES
    ensure(bool(packages) and len(set(packages)) == len(packages),
           f"the prerequisites are a nonempty list without repeats: {packages}")
    ensure(all(re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", package) for package in packages),
           f"each prerequisite is a Debian package name: {packages}")


def _root_gaps_name_what_a_root_lacks() -> None:
    """A root stands where its `config` does, and one that stands is complete only when
    it states a format and carries every owned repository at its URL."""
    (default, url), *others = opam_client.OPAM_REPOSITORIES
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        absent = Path(td) / "absent"
        ensure(not opam_client.root_exists(absent), "a missing directory is no root")
        absent.mkdir()
        ensure(not opam_client.root_exists(absent), "a directory without config is no root")
        for layout in ("flat", "nested"):
            root = Path(td) / layout
            opam_root(root, layout)
            ensure(opam_client.root_exists(root) and opam_client.root_gaps(root) == [],
                   f"a complete {layout} root has no gaps: {opam_client.root_gaps(root)}")
        unformatted = Path(td) / "unformatted"
        opam_root(unformatted, "flat")
        (unformatted / "config").write_bytes(b'opam-version: "2.0"\n')
        ensure(opam_client.root_gaps(unformatted) == ["states no format"],
               f"a config naming no format is a gap: {opam_client.root_gaps(unformatted)}")
        partial = Path(td) / "partial"
        opam_root(partial, "flat", configured=((default, url),))
        missing = ", ".join(f"{name} {address}" for name, address in others)
        ensure(opam_client.root_gaps(partial) == [f"lacks {missing}"],
               f"a missing repository is named: {opam_client.root_gaps(partial)}")
        moved = Path(td) / "moved"
        opam_root(moved, "flat", configured=((default, url + "/elsewhere"), *others))
        ensure(opam_client.root_gaps(moved) == [f"lacks {default} {url}"],
               f"a repository at another URL is not the owned one: "
               f"{opam_client.root_gaps(moved)}")
        bare = Path(td) / "bare"
        bare.mkdir()
        (bare / "config").write_bytes(b"")
        ensure(opam_client.root_gaps(bare) == [
                   "states no format",
                   "lacks " + ", ".join(f"{name} {address}"
                                        for name, address in opam_client.OPAM_REPOSITORIES)],
               f"an empty root lacks everything: {opam_client.root_gaps(bare)}")
        newer = Path(td) / "newer"
        opam_root(newer, "flat")
        (newer / "config").write_bytes(b'opam-version: "2.0"\nopam-root-version: "99.0"\n')
        ensure(opam_client.root_gaps(newer) == [
                   f"is in format 99.0, newer than the reviewed client's "
                   f"{opam_client.OPAM_ROOT_FORMAT}, which refuses to write to it"],
               f"a format newer than the reviewed client's is a gap: "
               f"{opam_client.root_gaps(newer)}")
        unstamped = Path(td) / "unstamped"
        opam_root(unstamped, "flat", stamps={name: "s" for name, _ in others})
        ensure(opam_client.root_gaps(unstamped) == [f"records no metadata stamp for {default}"],
               f"an owned repository whose stamp is unread is a gap: "
               f"{opam_client.root_gaps(unstamped)}")
        foreign = Path(td) / "foreign"
        opam_root(foreign, "flat", stamps={name: "s" for name, _ in opam_client.OPAM_REPOSITORIES},
                  configured=(*opam_client.OPAM_REPOSITORIES, ("mine", "https://example.invalid")))
        ensure(opam_client.root_gaps(foreign) == [],
               f"a repository the owner does not name is the developer's, stamped or not: "
               f"{opam_client.root_gaps(foreign)}")


def _resumable_roots_are_the_routes_own() -> None:
    """A root reads as in the shape `CREATE_ROOT` leaves after its leading steps only
    where running the route again completes it: the reviewed client's format, the
    route's leading repositories and no other, each at its owned URL with its stamp
    read."""
    (default, url), *others = opam_client.OPAM_REPOSITORIES
    leading = opam_client.OPAM_REPOSITORIES[:1]
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        roots: dict[str, bool] = {}

        def root(name: str, resumable: bool, layout: str = "flat",
                 stamps: dict[str, str] | None = None,
                 configured: tuple[tuple[str, str], ...] = leading) -> Path:
            at = Path(td) / name
            opam_root(at, layout, stamps, configured)
            roots[name] = resumable
            return at

        root("first-step", True)
        root("complete", False, configured=opam_client.OPAM_REPOSITORIES)
        root("older", False, layout="nested")
        root("unstamped", False, stamps={})
        root("not-leading", False, configured=tuple(others))
        root("moved", False, configured=((default, url + "/elsewhere"),))
        root("foreign", False, configured=(*leading, ("mine", "https://example.invalid")))
        newer = root("newer", False)
        (newer / "config").write_bytes(b'opam-root-version: "99.0"\n')
        roots["absent"] = False
        for name, resumable in roots.items():
            ensure(opam_client.root_resumable(Path(td) / name) is resumable,
                   f"the {name} root reads resumable={not resumable}")


def _remaining_route_never_reinitializes() -> None:
    """Where no root stands the remaining route is the whole route; over a root that
    stands it is each repository the root does not configure at its owned URL, added
    unselected, and never `opam init`, so a root in the shape the route leaves after its
    leading steps is completed without its shell setup being rewritten."""
    route = opam_client.CREATE_ROOT
    leading = opam_client.OPAM_REPOSITORIES[:1]
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        absent = Path(td) / "absent"
        ensure(opam_client.remaining_route(absent) == route,
               "with no root the whole route remains")
        absent.mkdir()
        ensure(opam_client.remaining_route(absent) == route,
               "a directory without config is no root, so the whole route remains")
        first_step = Path(td) / "first-step"
        opam_root(first_step, "flat", configured=leading)
        ensure(opam_client.root_resumable(first_step)
               and opam_client.remaining_route(first_step) == route[1:],
               f"a resumable root lacks the adds alone: "
               f"{opam_client.remaining_route(first_step)}")
        foreign = Path(td) / "foreign"
        opam_root(foreign, "flat", configured=(*leading, ("mine", "https://example.invalid")))
        ensure(opam_client.remaining_route(foreign) == route[1:],
               "a repository the owner does not name changes nothing that remains")
        complete = Path(td) / "complete"
        opam_root(complete, "nested")
        ensure(opam_client.remaining_route(complete) == (),
               "a root configuring every owned repository has nothing left to run")
        for root in (first_step, foreign, complete):
            ensure(route[0] not in opam_client.remaining_route(root),
                   f"opam init never runs over the standing {root.name} root")


def _versions_are_ordered_as_opam_orders_them() -> None:
    """The port of `OpamVersionCompare.compare` answers its Debian ordering: numbers by
    value, `~` before everything, even before the end of a part, letters before other
    characters, and the revision after the last `-` only on a tie."""
    for lower, higher in (("2.9", "2.10"), ("2.6~alpha", "2.6"), ("2.6~alpha1", "2.6~alpha2"),
                          ("2.6~~", "2.6~"), ("2.6", "2.6.0"), ("2.6", "2.6+x"),
                          ("2.6", "2.6a"), ("2.6a", "2.6+"), ("2.6", "x"), ("1.0-1", "1.0-2"),
                          ("1.0-9", "1.0-10"), ("1.0-z", "1.1-a"), ("2.6~", "2.6")):
        ensure(opam_client.compare_versions(lower, higher) == -1
               and opam_client.compare_versions(higher, lower) == 1,
               f"{lower!r} precedes {higher!r}: "
               f"{opam_client.compare_versions(lower, higher)}")
    for left, right in (("2.6", "2.6"), ("2.06", "2.6"), ("1.0", "1.00"), ("1.", "1.0"),
                        ("", "0")):
        ensure(opam_client.compare_versions(left, right) == 0
               and opam_client.compare_versions(right, left) == 0,
               f"{left!r} and {right!r} order as one version")


def _newer_formats_are_ordered() -> None:
    """A stated format is newer or older than the reviewed client's by opam's own
    ordering, which decides whether that client upgrades a root or refuses to write to
    it: a prerelease of the reviewed format is older, and a format opam orders after it
    is newer whatever its spelling. None stated is neither."""
    reviewed = opam_client.OPAM_ROOT_FORMAT
    for fmt, newer, older in (("99.0", True, False), (f"{reviewed}.1", True, False),
                              (f"{reviewed}.0", True, False), (f"{reviewed}+x", True, False),
                              ("x", True, False), (reviewed, False, False),
                              (f"{reviewed}~alpha1", False, True), ("2.2", False, True),
                              ("2.0", False, True), ("", False, False)):
        ensure(opam_client.newer_than_reviewed(fmt) is newer,
               f"format {fmt!r} reads newer={opam_client.newer_than_reviewed(fmt)}")
        ensure(opam_client.older_than_reviewed(fmt) is older,
               f"format {fmt!r} reads older={opam_client.older_than_reviewed(fmt)}")


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
        Case("root-creation-is-the-owners-route", _root_creation_is_the_owners_route),
        Case("root-prerequisites-are-packages", _root_prerequisites_are_packages),
        Case("root-gaps-name-what-a-root-lacks", _root_gaps_name_what_a_root_lacks),
        Case("versions-are-ordered-as-opam-orders-them",
             _versions_are_ordered_as_opam_orders_them),
        Case("newer-formats-are-ordered", _newer_formats_are_ordered),
        Case("resumable-roots-are-the-routes-own", _resumable_roots_are_the_routes_own),
        Case("remaining-route-never-reinitializes", _remaining_route_never_reinitializes),
        Case("install-verifies-and-never-replaces", _install_verifies_and_never_replaces),
    ]
