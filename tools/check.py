#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check every derived fact in this repository against the artifact that owns it.

Check groups are registered in [vos/checks/__init__.py](vos/checks/__init__.py#GROUPS) and
bound to `K-nn` rules in [check-registry.json](check-registry.json), which generates
[check-rules.md](check-rules.md). Each clean group's actual verdicts are verified against
its registry declarations, and [`meta`](vos/checks/meta.py#run) checks the registry and
its generated views.

Run with `--fix` to repair derived artifacts and arithmetic figures (generated views,
asserted counts, compounded products, coverage-matrix standing cells, and checklist
totals and shares) from their owners. All other findings require manual edits.

`--through K-nn` stops after the group that decides that rule. Because each group reads
only what earlier groups computed, the rule's verdict matches a full run;
[`selftest`](vos/cli/selftest.py#main) uses this to evaluate one rule's mutant at a time.

When [`timings.claim`](vos/timings.py#claim) is active (under `run.py --summary`), wall
and CPU durations for each fixed phase, check group, and generated-artifact row are
written to the timing record file.

Exit 0 clean, 1 on any finding. The repository root is resolved from this file's path
rather than the working directory.
"""

import argparse
import io
import re
import sys
from pathlib import Path

# Put `tools/` on `sys.path` so `vos` can be imported without package installation.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import pyversion

if __name__ == "__main__":
    try:
        pyversion.require_supported(Path(__file__).resolve().parents[1])
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error

from vos import checkregistry, timings, toolenv
from vos import corpus as corpus_mod

if __name__ == "__main__":
    code = toolenv.bootstrap(corpus_mod.find_root(), ["check", *sys.argv[1:]])
    if code is not None:
        sys.exit(code)

_IMPORTING = timings.reading()

from vos.checks import GROUPS, Context  # noqa: E402  (timed by the readings either side)
from vos.register import read_artifacts, read_register  # noqa: E402
from vos.report import Reporter  # noqa: E402

_IMPORTED = timings.reading()


def _utf8_output() -> None:
    """Reconfigure stdout and stderr to UTF-8 when backed by `io.TextIOWrapper`."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


def run(root: Path, fix: bool = False, through: str | None = None,
        clock: timings.Clock | None = None) -> Reporter:
    """Run the corpus checker and return its [`Reporter`](vos/report.py#Reporter).

    `through` stops the run after the group that decides that rule. `clock` records
    durations for the pre-group phases, each executed group, and sub-steps measured
    within a group.
    """
    measured = clock or timings.Clock()
    with measured.timing("phase", "corpus load"):
        corpus = corpus_mod.load(root)
    with measured.timing("phase", "register read"):
        reg = read_register(corpus)
    with measured.timing("phase", "artifacts read"):
        art = read_artifacts(corpus)
    ctx = Context(root=root, corpus=corpus, reg=reg, art=art, rep=Reporter(), fix=fix,
                  clock=measured)
    try:
        ctx.registry = checkregistry.read(root)
        groups = ctx.registry.bind((group.__name__.rpartition(".")[2], group.run)
                                   for group in GROUPS)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        ctx.rep.report("K-00", "invalid executable rule registry:", [str(exc)])
        return ctx.rep
    decided = re.compile(rf"\s*(?:ok|FAIL) {re.escape(through)}:") if bool(through) else None
    skipped = 0
    for index, group in enumerate(groups):
        start = len(ctx.rep.out)
        ctx.group_start = len(ctx.rep.decisions)
        ctx.group_findings = ctx.rep.findings
        with measured.timing("group", group.name):
            group.run(ctx)
        if group.name != "meta":
            ctx.registry_faults += checkregistry.verdict_faults(
                group.rules, ctx.rep.decisions[ctx.group_start:],
                clean=ctx.rep.findings == ctx.group_findings)
        if decided is not None and any(decided.match(line) for line in ctx.rep.out[start:]):
            skipped = len(GROUPS) - index - 1
            break

    if fix:
        for name, text in ctx.fixed.items():
            # Preserve existing line endings (`newline=""`) when writing repaired text.
            (root / name).write_text(text, encoding="utf-8", newline="")
        ctx.rep.line(f"rewrote {len(ctx.fixed)} file(s)." if ctx.fixed
                     else "nothing to rewrite.")

    if skipped:
        ctx.rep.line(f"stopped after the group deciding {through}; "
                     f"the {skipped} later group(s) decided nothing.")
    if ctx.rep.findings:
        ctx.rep.line(f"{ctx.rep.findings} finding(s).")
    elif not skipped:
        ctx.rep.line("every derived fact agrees with its artifact.")
    return ctx.rep


def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    parser = argparse.ArgumentParser(
        description="Check every derived fact against the artifact that owns it.")
    parser.add_argument("--fix", action="store_true",
                        help="rewrite the figures that are arithmetic over an artifact")
    parser.add_argument("--through", metavar="RULE",
                        help="stop after the group that decides RULE (a K- id)")
    args = parser.parse_args(argv)
    if args.fix and args.through:
        parser.error("--fix repairs the whole run; it cannot stop at one rule's group")

    # Claim the timing record path before running groups so child processes do not inherit it.
    record = timings.claim()
    clock = timings.Clock(cpu=True, origin=_IMPORTING.wall)
    clock.span("phase", "imports", _IMPORTING, _IMPORTED)
    report = run(corpus_mod.find_root(), fix=args.fix, through=args.through, clock=clock)
    print("\n".join(report.out))
    timings.write(record, clock.units())
    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())
