# SPDX-License-Identifier: Apache-2.0
"""The instrument route's provisioning: its prerequisites, the side's declarations, the
recipe each build runs, the closure it records and the refusals before any build."""

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from ci import bootstrap_instrument as bootstrap
from ci import instrument_route as route
from tests.harness import Case, ensure
from vos import opam_client

_INSTALL = [["opam", "switch", "create", "verifiedos-quickchick-9.1.1-ocaml-5.4.1",
             "--repos=rocq-released,default", "--empty", "--no-switch", "-y"],
            ["opam", "switch", "import", "/side/tools/opam/quickchick.lock",
             "--switch=verifiedos-quickchick-9.1.1-ocaml-5.4.1", "-y"]]
_RECIPE = [["opam", "switch", "create", "verifiedos-quickchick-9.3.0-ocaml-5.4.1",
            "--repos=rocq-released,default", "--no-switch", "-y"],
           ["opam", "pin", "add", "--switch=verifiedos-quickchick-9.3.0-ocaml-5.4.1",
            "coq-quickchick.dev", "git+https://github.com/QuickChick/QuickChick.git#3d4d"],
           ["opam", "install", "--switch=verifiedos-quickchick-9.3.0-ocaml-5.4.1", "-y",
            "coq-quickchick.dev"]]


def _decl(**changes: object) -> dict[str, object]:
    found: dict[str, object] = {
        "install": _INSTALL, "recipe": _RECIPE,
        "switch": "verifiedos-quickchick-9.1.1-ocaml-5.4.1",
        "recipe_switch": "verifiedos-quickchick-9.3.0-ocaml-5.4.1",
        "subject": "proofs/CyclicExecutive.v"}
    found.update(changes)
    return found


def _prerequisites() -> None:
    ensure(set(opam_client.ROOT_PREREQUISITES) <= set(bootstrap.PACKAGES)
           and {"build-essential", "git", "libgmp-dev"} <= set(bootstrap.PACKAGES)
           and len(set(bootstrap.PACKAGES)) == len(bootstrap.PACKAGES),
           f"the prerequisites are the root's and the build's, once each: {bootstrap.PACKAGES}")


def _builds_choose_their_recipe() -> None:
    name, steps, switch, flag = bootstrap.plan_build(_decl(), "install", None)
    ensure(name == "INSTALL" and steps == _INSTALL and flag == ""
           and switch == "verifiedos-quickchick-9.1.1-ocaml-5.4.1",
           "an install build runs INSTALL into QUICKCHICK_SWITCH, checked without a flag")
    name, steps, switch, flag = bootstrap.plan_build(_decl(), "recipe", None)
    ensure(name == "RECIPE" and steps == _RECIPE and flag == "--recipe"
           and switch == "verifiedos-quickchick-9.3.0-ocaml-5.4.1",
           "a recipe build runs RECIPE into QUICKCHICK_RECIPE_SWITCH, checked with --recipe")
    export = Path("build") / "export" / "quickchick.lock"
    name, steps, switch, flag = bootstrap.plan_build(_decl(), "recipe", export)
    ensure(steps == [["opam", "switch", "create", switch, "--repos=rocq-released,default",
                      "--empty", "--no-switch", "-y"],
                     ["opam", "switch", "import", str(export), f"--switch={switch}", "-y"]]
           and flag == "--recipe" and switch == "verifiedos-quickchick-9.3.0-ocaml-5.4.1",
           f"an import fills the build recipe's switch by create-and-import: {steps!r}")


def _builds_refuse_what_they_cannot_run() -> None:
    cases: list[tuple[dict[str, object], str, str]] = [
        (_decl(recipe=None), "recipe", "declares no `quickchick.RECIPE`"),
        (_decl(install=[]), "install", "declares no `quickchick.INSTALL`"),
        (_decl(install=[["sh", "-c", "true"], *_INSTALL]), "install", "not an opam command"),
        (_decl(install=[*_INSTALL, _INSTALL[0]]), "install", "creates 2 switches"),
        (_decl(install=_INSTALL[1:]), "install", "creates 0 switches"),
        (_decl(switch="another"), "install", "not the declared 'another'"),
        (_decl(recipe_switch=None), "recipe", "not the declared None"),
        (_decl(), "certirocq", "no build"),
    ]
    for decl, build, fragment in cases:
        try:
            bootstrap.plan_build(decl, build, None)
        except ValueError as error:
            ensure(fragment in str(error), f"{fragment!r} in {error}")
            continue
        raise AssertionError(f"a recipe the route cannot run must be refused ({fragment!r})")


def _declarations_are_the_sides() -> None:
    files = {
        "tools/vos/__init__.py": "",
        "tools/vos/cli/__init__.py": "",
        "tools/vos/gallina.py": 'QUICKCHICK_SWITCH = "qc-9.1.1"\n'
                                'QUICKCHICK_RECIPE_SWITCH = "qc-9.3.0"\n',
        "tools/vos/cli/quickchick.py": (
            "from vos import gallina\n"
            'INSTALL = (("opam", "switch", "create", gallina.QUICKCHICK_SWITCH),)\n'),
        "tools/vos/cli/seed.py": 'COQ_SUBJECT = "proofs/CyclicExecutive.v"\n',
    }
    with tempfile.TemporaryDirectory() as scratch:
        side = Path(scratch)
        for rel, text in files.items():
            (side / rel).parent.mkdir(parents=True, exist_ok=True)
            (side / rel).write_text(text, encoding="utf-8")
        found = bootstrap.declarations(side)
        ensure(found == {"install": [["opam", "switch", "create", "qc-9.1.1"]], "recipe": None,
                         "switch": "qc-9.1.1", "recipe_switch": "qc-9.3.0",
                         "subject": "proofs/CyclicExecutive.v"},
               f"the side's own declarations are read, RECIPE absent as null: {found!r}")
        (side / "tools/vos/cli/quickchick.py").write_text("raise SystemExit(3)\n",
                                                          encoding="utf-8")
        try:
            bootstrap.declarations(side)
        except ValueError as error:
            ensure("did not load" in str(error), str(error))
        else:
            raise AssertionError("a side whose declarations do not load is refused")


def _closure_and_reexport() -> None:
    text = ("coq-quickchick  dev  git+https://github.com/QuickChick/QuickChick.git#3d4d6c0e9f\n"
            "ocaml  5.4.1\n\nrocq-core 9.3.0\n")
    found = bootstrap.parse_closure(text)
    ensure(found == [{"name": "coq-quickchick", "version": "dev",
                      "pin": "git+https://github.com/QuickChick/QuickChick.git#3d4d6c0e9f"},
                     {"name": "ocaml", "version": "5.4.1", "pin": ""},
                     {"name": "rocq-core", "version": "9.3.0", "pin": ""}],
           f"each installed package with its pin: {found!r}")
    pins = route.pins_of(route.closure_of({"closure": found}) or [])
    ensure(pins == {"coq-quickchick": ("git+https://github.com/QuickChick/QuickChick.git",
                                       "3d4d6c0e9f")},
           f"a pin's URL and commit are read from the closure: {pins!r}")
    for bad in ("", "ocaml\n"):
        try:
            bootstrap.parse_closure(bad)
        except ValueError:
            continue
        raise AssertionError(f"an empty or versionless closure is refused: {bad!r}")
    same = bootstrap.reexport_observation(b"a\n", b"a\n")
    moved = bootstrap.reexport_observation(b"a\nb\n", b"a\nc\n")
    ensure(same["identical"] is True and same["sha256"] == hashlib.sha256(b"a\n").hexdigest()
           and moved["identical"] is False and "+c" in route.as_list(moved["difference"]),
           f"the re-export's byte difference is recorded: {moved!r}")


def _refusals_before_any_build() -> None:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        export = root / "quickchick.lock"
        export.write_text("opam-version: \"2.0\"\n", encoding="utf-8")
        digest = hashlib.sha256(export.read_bytes()).hexdigest()
        args = argparse.Namespace(root=root, side=root, build="install", import_export=export,
                                  expect_sha256="0" * 64, install_system=False,
                                  github_env=None, github_path=None)
        with patch.object(sys, "platform", "linux"), \
                patch("platform.machine", return_value="x86_64"):
            for expected, fragment in (("0" * 64, "not the build job's recorded"),
                                       ("", "not the build job's recorded")):
                args.expect_sha256 = expected
                try:
                    bootstrap.provision(args, runner=lambda argv, environment: 0)
                except ValueError as error:
                    ensure(fragment in str(error) and digest in str(error), str(error))
                    continue
                raise AssertionError("an export at another SHA-256 must be refused")
            (root / "opam").mkdir()
            try:
                bootstrap.provision(args, runner=lambda argv, environment: 0)
            except ValueError as error:
                ensure("fresh root" in str(error), str(error))
            else:
                raise AssertionError("a root that already stands must be refused")
    with patch.object(bootstrap, "missing_packages", return_value=["bubblewrap"]):
        try:
            bootstrap.system_packages(False)
        except ValueError as error:
            ensure("bubblewrap" in str(error) and "--install-system" in str(error), str(error))
        else:
            raise AssertionError("a missing prerequisite is refused without --install-system")
    with patch.object(bootstrap, "missing_packages", return_value=[]):
        found = bootstrap.system_packages(False)
        ensure(found["missing"] == [] and found["installed"] == [],
               f"no prerequisite missing installs nothing: {found!r}")
    try:
        bootstrap.export_environment({"OPAMROOT": "a\nb"}, Path("bin"), None, None)
    except ValueError:
        pass
    else:
        raise AssertionError("an environment value with a line break is refused")


def cases() -> list[Case]:
    return [Case("prerequisites", _prerequisites),
            Case("builds-choose-their-recipe", _builds_choose_their_recipe),
            Case("builds-refuse-what-they-cannot-run", _builds_refuse_what_they_cannot_run),
            Case("declarations-are-the-sides", _declarations_are_the_sides),
            Case("closure-and-reexport", _closure_and_reexport),
            Case("refusals-before-any-build", _refusals_before_any_build)]
