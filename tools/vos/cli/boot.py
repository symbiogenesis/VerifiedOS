# SPDX-License-Identifier: Apache-2.0
"""M7.1's boot harness: compose a roster image, boot it on the golden emulator, digest it.

    python tools/run.py boot roster [--roster PATH]          the roster and what blocks it
    python tools/run.py boot compose RECIPE [--out DIR]      the image and its boot record
    python tools/run.py boot run RECIPE [--out DIR]          boot a composed image, digest it

`roster` reads this checkout and answers on either lane. `compose` and `run` are the
guest's: `run.py` re-launches them in WSL from the host, so the record `compose` writes
under the lane's guest output and the emulator `run` boots it on are in one place.
`run` boots the image a previous `compose` wrote, after re-reading every input the
record binds; it takes this lane's emulator, and `--simulator PATH` names another.
Exit 0 is a composition or boot that met every check, 1 a refusal the contract names (a
missing, statement-only or misplaced member, a stale component, a digest or boot-order
mismatch, no HTIF exit, an emulator that did not exit 0), and 2 an input the harness
cannot read, an output it cannot write, a missing or malformed boot record, or an
emulator it cannot find or start. Every report says what it does not establish: a
fixture member is not the real producer, and no record here is M7.1's acceptance while
the joins it lists are open. The rules are
[the roster and boot-recipe contract](../../../docs/implementation/contracts/boot-roster.md)'s.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from vos import boot, corpus, env

SCOPE = ("boot harness evidence at the composed boundary; M7.1 acceptance stays open "
         "while any listed join is open")


def _out(name: str, given: str | None) -> Path:
    if given:
        return Path(given)
    # The guest's outputs are the lane's; a host composition is derived output under the
    # ignored build tree, on freeze-emit's precedent.
    if sys.platform == "win32":
        return corpus.find_root() / "build" / "boot" / name
    return env.load(toolchain=False).lane_root / "boot" / name


def cmd_roster(args: argparse.Namespace) -> int:
    root = corpus.find_root()
    try:
        roster = boot.load_roster(root, args.roster)
    except boot.RecipeError as exc:
        print(f"FAIL boot roster: {exc}")
        return 2
    width = max(len(m.id) for m in roster.members)
    for m in roster.members:
        rank = "n/a" if m.rank is None else str(m.rank)
        print(f"  {m.id:<{width}}  {m.kind:<7} rank {rank:<3} {m.status:<14} owner {m.owner}")
    blocking = roster.blocking()
    counts = {s: sum(1 for m in roster.members if m.status == s) for s in boot.STATUSES}
    summary = ", ".join(f"{n} {s}" for s, n in counts.items() if n)
    print(f"{'ok' if not blocking else 'OPEN'} boot roster: {len(roster.members)} member(s) in "
          f"{roster.source}: {summary}")
    if blocking:
        print(f"  acceptance is blocked until {len(blocking)} member(s) have an executable "
              f"product: {', '.join(m.id for m in blocking)}")
    # Reading the roster succeeds whatever it says; a blocked roster is the state of the
    # work and not a malformed input, so the verdict line carries it and the code does not.
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    root = corpus.find_root()
    try:
        recipe = boot.load_recipe(root, args.recipe)
        out = _out(recipe.name, args.out)
        record = boot.compose(root, recipe, out)
    except (boot.RecipeError, OSError) as exc:
        print(f"FAIL boot compose: {exc}")
        return 2
    except boot.RefusalError as exc:
        print(f"FAIL boot compose: {exc}")
        return 1
    picture = cast("dict[str, object]", record["image"])
    print(f"ok boot compose: {recipe.name}, {len(recipe.members)} member(s), image "
          f"{picture['sha256']} ({picture['bytes']} bytes), composition "
          f"{record['composition_sha256']}")
    print(f"  wrote {out / 'record.json'}")
    for join in cast("list[str]", record["open"]):
        print(f"  open: {join}")
    return 0


def _simulator(args: argparse.Namespace) -> Path | None:
    if args.simulator:
        return Path(args.simulator)
    if sys.platform == "win32":
        return None
    return env.load(toolchain=False).simulator


def cmd_run(args: argparse.Namespace) -> int:
    root = corpus.find_root()
    try:
        recipe = boot.load_recipe(root, args.recipe)
        out = _out(recipe.name, args.out)
        record = boot.load_record(out)
        composed = cast("dict[str, str]", record["recipe"])["path"]
        if composed != recipe.path:
            print(f"FAIL boot run: {out / 'record.json'} was composed from {composed}, "
                  f"not {recipe.path}")
            return 1
        findings = boot.stale(root, record, out)
    except (boot.RecipeError, OSError) as exc:
        print(f"FAIL boot run: {exc}")
        return 2
    if findings:
        for finding in findings:
            print(f"FAIL boot run: {finding}")
        print("  compose the recipe again after reviewing what changed")
        return 1

    simulator = _simulator(args)
    if simulator is None or not simulator.is_file():
        where = "on this lane" if simulator is None else f"at {simulator}"
        print(f"FAIL boot run: no golden emulator {where}; run it in the guest after "
              f"`python tools/run.py model build`, or pass --simulator PATH")
        return 2
    try:
        return _boot(args, root, recipe, record, out, simulator)
    except OSError as exc:
        print(f"FAIL boot run: {exc}")
        return 2


def _boot(args: argparse.Namespace, root: Path, recipe: boot.Recipe, record: dict[str, object],
          out: Path, simulator: Path) -> int:
    console_path = out / "console.log"
    image_sha = cast("dict[str, str]", record["image"])["sha256"]
    argv = [str(simulator), "--config", str(root / recipe.configuration), "--trace-commit",
            "--terminal-log", str(console_path), "--inst-limit", str(recipe.inst_limit),
            str(out / "image.elf")]
    observation = boot.boot_image(argv, console_path, boot.entries_of(record),
                                  int(cast("str", record["tohost"]), 16), args.timeout,
                                  out / "trace.log" if args.keep_trace else None)
    projection = observation.projection
    (out / "events.log").write_bytes(projection.event_log())

    findings = boot.run_findings(observation, record)
    refreshed: bool | None = None
    if args.refresh:
        # A reference is taken from a clean run or not at all: a failing boot written into
        # the recipe would make the next identical failure read as a match.
        if findings:
            findings.append("--refresh refused: the expected digests are taken from a clean "
                            "run only")
        else:
            refreshed = boot.refresh_expected(root, recipe,
                                              boot.expected_block(observation, image_sha))
    else:
        findings += boot.against_expected(observation, image_sha, recipe.expected)

    identity, withheld = boot.roster_identity(record)
    result: dict[str, object] = {
        "schema_version": boot.SCHEMA_VERSION,
        "record_sha256": boot.digest_file(out / "record.json"),
        "image_sha256": image_sha,
        "simulator_sha256": boot.digest_file(simulator),
        "returncode": observation.returncode,
        "timed_out": observation.timed_out,
        "wall_seconds": round(observation.wall_seconds, 3),
        "emulator_verdict": projection.verdict,
        "htif_exit": projection.htif_exit,
        **boot.expected_block(observation, image_sha),
        "records": projection.records,
        "roster_identity": identity,
        "roster_identity_withheld": withheld,
        "findings": findings,
        "scope": SCOPE,
    }
    (out / "run.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8",
                                  newline="\n")
    print(f"{'FAIL' if findings else 'ok'} boot run: {recipe.name}, HTIF exit "
          f"{'none' if projection.htif_exit is None else projection.htif_exit}, "
          f"{len(projection.events)} events {projection.event_sha256}, console "
          f"{observation.console_sha256}, {projection.retired} I records, commit "
          f"trace {projection.trace_digest}, {observation.wall_seconds:.2f} s")
    for finding in findings:
        print(f"  {finding}")
    if withheld is not None:
        print(f"  roster identity withheld: {withheld}")
    if refreshed is not None:
        print(f"REFRESH {recipe.path} expected digests {'rewritten' if refreshed else 'unchanged'}")
    print(f"  wrote {out / 'run.json'}; {SCOPE}")
    return 1 if findings else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py boot", description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    roster = sub.add_parser("roster", help="the contract's roster, and what blocks accepting it")
    roster.add_argument("--roster", default=boot.CONTRACT,
                        help="a roster table or fixture roster (default: the contract's)")
    roster.set_defaults(run=cmd_roster)
    compose = sub.add_parser("compose", help="compose a recipe's image and boot record")
    run = sub.add_parser("run", help="boot a composed image on the golden emulator and digest it")
    for command, handler in ((compose, cmd_compose), (run, cmd_run)):
        command.add_argument("recipe", help="a recipe JSON, relative to the repository root")
        command.add_argument("--out", help="where the image and records are written and read")
        command.set_defaults(run=handler)
    run.add_argument("--simulator", help="the emulator to boot on (default: this lane's)")
    run.add_argument("--refresh", action="store_true",
                     help="write this run's digests into the recipe, from a clean run only")
    run.add_argument("--keep-trace", action="store_true",
                     help="keep the whole commit trace beside the record as trace.log")
    run.add_argument("--timeout", type=float, default=900.0,
                     help="seconds before a boot counts as never having reported")
    args = parser.parse_args(argv)
    return cast("int", args.run(args))
