#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Provision one side of the instrument switch route in a fresh private root.

The route's provisioning entry point, run from the dispatching commit's checkout by
every job of [instrument-switches.yml](../../.github/workflows/instrument-switches.yml)
that builds a switch. It installs its own distribution prerequisites, `PACKAGES`,
installs [the opam client's owner's](../vos/opam_client.py) reviewed client, creates a
fresh private root by that owner's route, and builds the side's QuickChick switch from
the side revision's own declarations: by `quickchick.RECIPE` into
`gallina.QUICKCHICK_RECIPE_SWITCH` where the build is `recipe`, and by
`quickchick.INSTALL` into `gallina.QUICKCHICK_SWITCH` where it is `install`, or, in the
import job, by the lock guide's create-and-import form from the build job's export into
the switch the build's recipe names. A build after which that switch does not stand is
refused. The job's receipt then records the side's subject and tested revision, the
recipe built, the switch and the flag its checks run with, the switch's installed
closure with each pin's URL and commit, the opam client's version and the
prerequisites installed. [The route's contract](README.md#instrument-switch-route)
states what a run decides.

The side's declarations are read by importing the side's own `vos.cli.quickchick` and
`vos.gallina` in an isolated interpreter: the side's instruments run at its revision in
any case, and the declarations are what the side would run. Nothing else of the side
runs here.
"""

import argparse
import difflib
import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from ci import instrument_route as route  # noqa: E402  (bootstrap precedes the locked env)
from vos import env, opam_client, receipts  # noqa: E402

# The distribution packages the route installs: the opam root's own prerequisites, from
# the client's owner, which states why `opam init` needs each, then the QuickChick
# build's: a C toolchain for the OCaml compiler, GMP and pkg-config for zarith, which
# Rocq requires, m4 for ocamlfind's configure, patch for packages that patch their
# sources, and git for a commit-pinned recipe's sources and an export carrying its pins.
PACKAGES: tuple[str, ...] = tuple(dict.fromkeys((
    *opam_client.ROOT_PREREQUISITES, "build-essential", "git", "libgmp-dev", "m4",
    "patch", "pkg-config",
)))
# The repositories a QuickChick switch resolves from, as the owner's recipes name them,
# which the create-and-import form names too.
REPOS = "--repos=rocq-released,default"
BUILDS: tuple[str, ...] = route.BUILDS

# Read in an isolated interpreter with the side's `tools/` first on the path: each
# declaration as the side states it, or null where the side declares none.
_DECLARATIONS = """
import json, sys
sys.path.insert(0, sys.argv[1])
from vos import gallina
from vos.cli import quickchick

def steps(value):
    return None if value is None else [list(step) for step in value]

print(json.dumps({
    "install": steps(getattr(quickchick, "INSTALL", None)),
    "recipe": steps(getattr(quickchick, "RECIPE", None)),
    "switch": getattr(gallina, "QUICKCHICK_SWITCH", None),
    "recipe_switch": getattr(gallina, "QUICKCHICK_RECIPE_SWITCH", None),
}))
"""


type Runner = Callable[[Sequence[str], dict[str, str]], int]


def declarations(side: Path, python: str = sys.executable) -> dict[str, object]:
    """The side revision's QuickChick declarations, and seed's default subject read
    from its source without running it."""
    done = subprocess.run((python, "-I", "-c", _DECLARATIONS, str(side / "tools")),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=False, timeout=120,
                          stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise ValueError(f"the side's declarations did not load: {done.stderr.strip()}")
    try:
        found = route.as_object(json.loads(done.stdout))
    except (ValueError, TypeError) as error:
        raise ValueError(f"the side's declarations are not a JSON object: {error}") from None
    seed = (side / route.SEED).read_text(encoding="utf-8")
    found["subject"] = route.string_constant(seed, "COQ_SUBJECT")
    return found


def _steps(value: object, name: str) -> list[list[str]]:
    """A recipe as argv lists, refused unless every step is an opam command."""
    if not isinstance(value, list) or not value:
        raise ValueError(f"the side declares no `{name}`")
    found: list[list[str]] = []
    for step in value:
        if (not isinstance(step, list) or not step
                or not all(isinstance(word, str) for word in step) or step[0] != "opam"):
            raise ValueError(f"`{name}` holds a step that is not an opam command: {step!r}")
        found.append([str(word) for word in step])
    return found


def created_switch(steps: Sequence[Sequence[str]], name: str) -> str:
    """The one switch a recipe creates, refused unless it creates exactly one."""
    created = [step[3] for step in steps
               if len(step) > 3 and list(step[1:3]) == ["switch", "create"]]
    if len(created) != 1:
        raise ValueError(f"`{name}` creates {len(created)} switches, not one")
    return created[0]


def plan_build(decl: dict[str, object], build: str,
               imported: Path | None) -> tuple[str, list[list[str]], str, str]:
    """What this side builds: the recipe's name, its steps, the switch it names and the
    flag the checks run with. An import takes the switch the build's recipe names and
    fills it from the export by the lock guide's create-and-import form."""
    if build not in BUILDS:
        raise ValueError(f"no build {build!r}")
    name = "RECIPE" if build == "recipe" else "INSTALL"
    steps = _steps(decl.get(name.lower()), f"quickchick.{name}")
    switch = created_switch(steps, f"quickchick.{name}")
    declared = decl.get("recipe_switch" if build == "recipe" else "switch")
    if switch != declared:
        raise ValueError(f"`quickchick.{name}` creates {switch!r}, not the declared "
                         f"{declared!r}")
    flag = "--recipe" if build == "recipe" else ""
    if imported is None:
        return name, steps, switch, flag
    form = [["opam", "switch", "create", switch, REPOS, "--empty", "--no-switch", "-y"],
            ["opam", "switch", "import", str(imported), f"--switch={switch}", "-y"]]
    return f"import into {name}'s switch", form, switch, flag


def missing_packages(packages: Sequence[str]) -> list[str]:
    """Read the package database once; exit 1 means some requested names are absent."""
    done = subprocess.run(("dpkg-query", "-W", "-f=${Package}\t${Status}\n", *packages),
                          capture_output=True, text=True, check=False, timeout=60,
                          stdin=subprocess.DEVNULL)
    if done.returncode not in (0, 1):
        done.check_returncode()
    statuses: dict[str, list[str]] = {}
    for line in done.stdout.splitlines():
        name, separator, status = line.partition("\t")
        if not separator:
            raise ValueError(f"unrecognized dpkg-query output: {line!r}")
        statuses.setdefault(name, []).append(status)
    return [name for name in packages if statuses.get(name) != ["install ok installed"]]


def _run(argv: Sequence[str], environment: dict[str, str]) -> int:
    print(f"== {shlex.join(argv)}", flush=True)
    return subprocess.run(argv, check=False, env=environment,
                          stdin=subprocess.DEVNULL).returncode


def _checked(runner: Runner, argv: Sequence[str], environment: dict[str, str]) -> None:
    code = runner(argv, environment)
    if code != 0:
        raise ValueError(f"`{shlex.join(argv)}` exited {code}")


def system_packages(install: bool, runner: Runner = _run) -> dict[str, list[str]]:
    """Install the prerequisites the runner lacks, and say which those were."""
    missing = missing_packages(PACKAGES)
    record: dict[str, list[str]] = {"required": list(PACKAGES), "missing": list(missing),
                                    "installed": []}
    if not missing:
        return record
    if not install:
        raise ValueError("missing distribution packages: " + " ".join(missing)
                         + "; use --install-system to install them")
    if sys.platform == "win32":
        raise ValueError("system packages are installed on the Linux runner")
    prefix = () if os.geteuid() == 0 else ("sudo", "-n")
    environment = dict(os.environ)
    _checked(runner, (*prefix, "apt-get", "update"), environment)
    _checked(runner, (*prefix, "env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install",
                      "-y", "--no-upgrade", "--no-install-recommends", *missing), environment)
    if still := missing_packages(PACKAGES):
        raise ValueError("packages still absent after installation: " + " ".join(still))
    record["installed"] = list(missing)
    return record


def _read(argv: Sequence[str]) -> str:
    """One opam read of the private root, answering no question it asks."""
    done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=False, timeout=600,
                          stdin=subprocess.DEVNULL, env=env.declining_environment())
    if done.returncode != 0:
        raise ValueError(f"`{shlex.join(argv)}` exited {done.returncode}: "
                         f"{done.stderr.strip()[-400:]}")
    return done.stdout


def parse_closure(text: str) -> list[dict[str, str]]:
    """`opam list --columns=name,version,pin --short` as package records, the pin empty
    where the package is not pinned, whether opam leaves that column blank or dashes it."""
    found: list[dict[str, str]] = []
    for line in text.splitlines():
        fields = line.split()
        if not fields or line.lstrip().startswith("#"):
            continue
        if len(fields) < 2:
            raise ValueError(f"an installed package without a version: {line!r}")
        pin = " ".join(fields[2:])
        found.append({"name": fields[0], "version": fields[1],
                      "pin": "" if pin in ("-", "--") else pin})
    if not found:
        raise ValueError("the switch lists no installed package")
    return sorted(found, key=lambda package: package["name"])


def closure(switch: str) -> list[dict[str, str]]:
    return parse_closure(_read(("opam", "list", f"--switch={switch}", "--installed",
                                "--short", "--columns=name,version,pin", "--color=never")))


def reexport_observation(original: bytes, again: bytes) -> dict[str, object]:
    """The byte difference between an imported export and the import's re-export,
    an observation the comparison records and never decides by."""
    found: dict[str, object] = {"identical": original == again,
                                "sha256": hashlib.sha256(again).hexdigest(),
                                "bytes": len(again)}
    if original != again:
        diff = difflib.unified_diff(
            original.decode("utf-8", errors="replace").splitlines(),
            again.decode("utf-8", errors="replace").splitlines(),
            "export", "reexport", lineterm="", n=0)
        found["difference"] = list(diff)[:200]
    return found


def environment(root: Path) -> dict[str, str]:
    """What the later steps run the side's instruments in: the private root, its build
    and log trees, a lane of its own, and no keepalive lease."""
    return {
        "OPAMROOT": str(root / "opam"), "VOS_BUILD_ROOT": str(root / "build"),
        "VOS_LOG_DIR": str(root / route.LOGS / "side"), "VOS_LANE": "",
        "TMPDIR": str(root / "tmp"), "VOS_KEEPALIVE_HOURS": "0",
    }


def export_environment(values: dict[str, str], path: Path,
                       github_env: Path | None, github_path: Path | None) -> None:
    if any(c in item for item in (*values.values(), str(path)) for c in "\r\n\0"):
        raise ValueError("environment values must not contain line breaks or NUL bytes")
    if github_env:
        with github_env.open("a", encoding="utf-8", newline="") as stream:
            stream.writelines(f"{key}={value}\n" for key, value in values.items())
    if github_path:
        with github_path.open("a", encoding="utf-8", newline="") as stream:
            stream.write(f"{path}\n")


def provision(args: argparse.Namespace, runner: Runner = _run) -> int:
    """Build the side's switch in a fresh root and record what was built."""
    if sys.platform != "linux":
        raise ValueError("the route provisions on its Linux runner")
    machine = platform.machine()
    if machine not in opam_client.OPAM_HASHES:
        raise ValueError(f"no reviewed opam binary for {machine}")
    root = Path(args.root)
    opam = root / "opam"
    if opam.exists():
        raise ValueError(f"{opam} already stands; the route builds every switch in a fresh "
                         "root")
    imported = Path(args.import_export) if args.import_export is not None else None
    source: dict[str, object] | None = None
    if imported is not None:
        if not imported.is_file():
            raise ValueError(f"no export at {imported}")
        digest = receipts.digest(imported)
        if not route.SHA256.fullmatch(args.expect_sha256 or "") or digest != args.expect_sha256:
            raise ValueError(f"the export's SHA-256 is {digest}, not the build job's recorded "
                             f"{args.expect_sha256!r}")
        source = {"sha256": digest, "bytes": imported.stat().st_size}
    side = Path(args.side)
    decl = declarations(side)
    name, steps, switch, flag = plan_build(decl, args.build, imported)
    revision = subprocess.run(("git", "-C", str(side), "rev-parse", "HEAD"),
                              capture_output=True, text=True, check=True, timeout=60,
                              stdin=subprocess.DEVNULL).stdout.strip()
    subject = decl.get("subject")
    route.update_inputs(root, subject=subject if isinstance(subject, str) else "")
    route.update_receipt(root, source_revision=revision, recipe=name, recipe_steps=steps,
                         switch=switch, flag=flag, import_source=source)

    prerequisites = system_packages(args.install_system, runner)
    route.update_receipt(root, prerequisites=prerequisites)
    binary = root / "bin"
    binary.mkdir(parents=True, exist_ok=True)
    opam_client.install(binary / "opam", machine)
    values = environment(root)
    for key in ("VOS_BUILD_ROOT", "VOS_LOG_DIR", "TMPDIR"):
        Path(values[key]).mkdir(parents=True, exist_ok=True)
    jobs = os.process_cpu_count() or 1
    os.environ.update(values)
    os.environ["PATH"] = f"{binary}{os.pathsep}{os.environ.get('PATH', '')}"
    build_env = dict(os.environ, OPAMJOBS=str(jobs), OPAMYES="1", OPAMCOLOR="never")
    reported = _read(("opam", "--version")).strip()
    route.update_receipt(root, opam_client=reported,
                         opam_client_reviewed=opam_client.OPAM_VERSION, opam_jobs=jobs)
    for argv in opam_client.remaining_route(opam):
        _checked(runner, argv, build_env)
    route.update_receipt(root, opam_root_format=opam_client.initialized_format(opam),
                         opam_repositories=opam_client.initialized_repositories(opam))
    for argv in steps:
        _checked(runner, argv, build_env)
    if switch not in opam_client.root_switches(opam) or not (opam / switch).is_dir():
        raise ValueError(f"after `{name}` the switch {switch} does not stand in {opam}")
    packages = closure(switch)
    pins = route.pins_of(route.closure_of({"closure": packages}) or [])
    route.update_receipt(root, closure=packages, pins={
        name: {"url": url, "commit": commit} for name, (url, commit) in pins.items()})
    if imported is not None:
        again = root / route.REEXPORT
        again.parent.mkdir(parents=True, exist_ok=True)
        _read(("opam", "switch", "export", f"--switch={switch}", str(again)))
        route.update_receipt(root, reexport=reexport_observation(
            imported.read_bytes(), again.read_bytes()))
    export_environment(values, binary, args.github_env, args.github_path)
    print(f"ok {switch} stands in {opam}, built by {name}")
    return 0


def export(args: argparse.Namespace) -> int:
    """Export the switch the provisioning built, and record its SHA-256 for the import
    job, which takes the export only at that digest."""
    root = Path(args.root)
    receipt = route.load_receipt(root)
    switch = receipt.get("switch")
    if not isinstance(switch, str) or not switch:
        raise ValueError("the receipt names no switch to export")
    target = root / route.EXPORT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    _read(("opam", "switch", "export", f"--switch={switch}", str(target)))
    digest = receipts.digest(target)
    route.update_receipt(root, export={"path": route.EXPORT, "sha256": digest,
                                       "bytes": target.stat().st_size})
    route.github_output({"sha256": digest}, args.github_output)
    print(f"ok {switch} exported to {target}, SHA-256 {digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", type=Path, default=route.ROOT,
                        help="the job's private root (default: ~/verifiedos-instrument)")
    subs = parser.add_subparsers(dest="command", required=True)
    building = subs.add_parser("provision", help="build the side's switch in a fresh root")
    building.add_argument("--side", type=Path, required=True,
                          help="the side revision's checkout, whose declarations are built")
    building.add_argument("--build", choices=BUILDS, required=True,
                          help="build by quickchick.INSTALL or quickchick.RECIPE")
    building.add_argument("--import", dest="import_export", type=Path,
                          help="fill the switch from this export instead of building it")
    building.add_argument("--expect-sha256", help="the export's SHA-256 the build recorded")
    building.add_argument("--install-system", action="store_true",
                          help="install absent distribution packages using passwordless sudo")
    building.add_argument("--github-env", type=Path)
    building.add_argument("--github-path", type=Path)
    exporting = subs.add_parser("export", help="export the switch the provisioning built")
    exporting.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "provision": provision, "export": export}
    try:
        return handlers[args.command](args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"FAIL {args.command}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
