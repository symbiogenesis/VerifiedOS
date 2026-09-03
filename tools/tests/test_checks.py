# SPDX-License-Identifier: Apache-2.0
"""Single check groups over fixture corpora, at Context altitude.

Each case builds a Context by hand over a sandbox tree and runs one group's
`run(ctx)`, asserting on that group's lines and on `ctx.fixed` alone: a small
fixture cannot satisfy every rule the checker carries at once, so other rules'
findings are tolerated rather than fought, and the count is left out of this
sentence rather than hand-copied into it. What is pinned here is the wave the
selftest's single-defect mutants cannot reach: a `--fix` whose only edit is
refused writes nothing, a repair reaches its fixpoint in one application, a
truncated table row is a finding rather than a crash, an overgrown quantity is a
finding rather than a stopped run, K-67 fails closed on a pin site it cannot read,
and K-75 decides the one floor site its single mutant does not seed.
"""

from pathlib import Path

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos.checks import Context, bindings, counts, estimates, meta
from vos.register import read_artifacts, read_register
from vos.report import Reporter

# enough register for read_register to parse; the groups under test never read it
_REGISTER_MIN = "# Register\n\n## §1\n\n**R-01-001** MUST x.\n· Trace: t\n"

PLAN = estimates.PLAN


def _context(root: Path, fix: bool = False) -> Context:
    corpus = corpus_mod.load(root)
    reg = read_register(corpus)
    art = read_artifacts(corpus)
    return Context(root=root, corpus=corpus, reg=reg, art=art, rep=Reporter(), fix=fix)


def _findings_under(ctx: Context, rule: str) -> list[str]:
    """The indented findings under one rule's FAIL line."""
    out: list[str] = []
    collecting = False
    for line in ctx.rep.out:
        if line.startswith(f"FAIL {rule}:"):
            collecting = True
        elif collecting and line.startswith("       "):
            out.append(line.strip())
        elif collecting:
            break
    return out


def _estimates_refused_edit_writes_nothing() -> None:
    # two identical stale item lines: each edit matches two sites, so both are
    # refused as unrewritable, and a refusal must leave nothing to flush, or
    # --fix writes a byte-identical file and reports a rewrite on every run
    plan = ("# Plan\n\n"
            "* [ ] **A** · 3 h, range 2–4 · 100.0%\n"
            "* [ ] **A** · 3 h, range 2–4 · 100.0%\n\n"
            "**S subtotal:** 6 h · 100% · open range 4–8 h.\n")
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                       PLAN: plan}) as root:
        ctx = _context(root, fix=True)
        estimates.run(ctx)
        ensure(ctx.fixed == {},
               f"a refused edit staged a write anyway: {list(ctx.fixed)!r}")
        ensure("not unique enough to rewrite"
               in " ".join(_findings_under(ctx, "K-36")),
               f"the refusal is K-36's finding: {ctx.rep.out!r}")
        ensure(not any(line.startswith("fixed:") for line in ctx.rep.out),
               "nothing was rewritten, so nothing may report as fixed")


def _estimates_repair_reaches_fixpoint() -> None:
    # one stale share: the first --fix rewrites it, and a second --fix over the
    # repaired text computes the same cells and stages nothing, which is the
    # one-application fixpoint the ground rules ask every mutating path to prove
    plan = ("# Plan\n\n"
            "* [ ] **A** · 3 h, range 2–4 · 99.0%\n\n"
            "**S subtotal:** 3 h · 100% · open range 2–4 h.\n")
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                       PLAN: plan}) as root:
        ctx = _context(root, fix=True)
        estimates.run(ctx)
        ensure(list(ctx.fixed) == [PLAN], f"the stale cell repairs: {list(ctx.fixed)!r}")
        repaired = ctx.fixed[PLAN]
        ensure("· 3 h, range 2–4 · 100.0%" in repaired,
               f"the share is recomputed over the items: {repaired!r}")
        ensure(any(line.startswith("fixed: A:") for line in ctx.rep.out),
               f"the rewrite reports itself: {ctx.rep.out!r}")

    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                       PLAN: repaired}) as root:
        again = _context(root, fix=True)
        estimates.run(again)
        ensure(again.fixed == {},
               f"the second --fix must stage nothing: {list(again.fixed)!r}")
        ensure(not any(line.startswith("fixed:") for line in again.rep.out),
               f"and report no rewrite: {again.rep.out!r}")


def _bindings_truncated_row_is_a_finding() -> None:
    # a row too narrow for the view's cells was an IndexError that aborted the
    # whole run before wave 1; it is K-42's finding now, and the group must still
    # decide K-43 and K-44 past it
    apex_v = ("Record Vocabulary : Type := {\n"
              "  spatial_safety : Prop ;\n"
              "  temporal_safety : Prop\n"
              "}.\n\n"
              "Definition uses (v : Vocabulary) : Prop := v.(spatial_safety).\n")
    bind_md = ("# Field bindings\n\n"
               "| Field | Consumed by | Owner | Instantiated by |\n"
               "| --- | --- | --- | --- |\n"
               "| `spatial_safety` | `uses` | r | none yet |\n"
               "| `temporal_safety` | truncated |\n")
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                       "proofs/ApexTheorem.v": apex_v,
                       "docs/field-bindings.md": bind_md}) as root:
        ctx = _context(root)
        bindings.run(ctx)
        found = _findings_under(ctx, "K-42")
        ensure(any("too narrow to carry the view's cells" in f for f in found),
               f"the truncated row is a K-42 finding, not a crash: {found!r}")
        ensure(any(line.startswith(("ok K-43:", "FAIL K-43:")) for line in ctx.rep.out)
               and any(line.startswith(("ok K-44:", "FAIL K-44:"))
                       for line in ctx.rep.out),
               f"the group decides its other rules past the bad row: {ctx.rep.out!r}")


def _counts_overflow_is_a_finding() -> None:
    # a words-style quantity past ninety-nine has no word form; before wave 1 the
    # whole run stopped on figures.words' ValueError, and the exit code could not
    # tell that crash from a verdict
    absences = "# Absences\n\n" + "".join(f"| **A-{n}** | row |\n"
                                          for n in range(1, 101))
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                       "docs/absence-contract.md": absences}) as root:
        ctx = _context(root)
        # the shared keys confers and views would have produced; counts reads
        # them positionally and this test runs counts alone
        ctx.shared.update(cj_confer=[], fc_seams=[], fc_confer=[], rf_confer=[],
                          dispositions=0, rot_cases=0)
        counts.run(ctx)
        ensure("absences is 100, which has no word form; the claim in README.md "
               "must state it in digits" in _findings_under(ctx, "K-24"),
               f"the overflow is K-24's finding, naming the claim owed digits: "
               f"{_findings_under(ctx, 'K-24')!r}")


# K-67's fixture pin sites: the constants as typecheck.py spells them, the four
# README sites the rule holds against them, and the workflow's two install lines,
# which are the copy a hosted runner resolves rather than one a reader opens.
_TYPECHECK_PINNED = 'TY_VERSION = "1.2.3"\nRUFF_VERSION = "4.5.6"\n'
_WORKFLOW_PINNED = ("name: host gates\njobs:\n  gates:\n    steps:\n"
                    "      - run: |\n"
                    "          uv tool install ty==1.2.3\n"
                    "          uv tool install ruff==4.5.6\n")
_README_PINNED = ("# Tools\n\n"
                  "| Checker | Pin | What |\n| --- | --- | --- |\n"
                  "| [ty](https://x) | 1.2.3 | types |\n"
                  "| [ruff](https://x) | 4.5.6 | lint |\n\n"
                  "Install with `uv tool install ty==1.2.3` and "
                  "`uv tool install ruff==4.5.6`.\n")


def _k67(readme: str, typecheck: str | None,
         workflow: str = _WORKFLOW_PINNED) -> Context:
    files = {"docs/requirements-register.md": _REGISTER_MIN,
             "tools/README.md": readme,
             ".github/workflows/host-gates.yml": workflow}
    if typecheck is not None:
        files["tools/vos/cli/typecheck.py"] = typecheck
    with sandbox_tree(files) as root:
        ctx = _context(root)
        meta.run(ctx)
        return ctx


def _k67_agreement_is_ok() -> None:
    ctx = _k67(_README_PINNED, _TYPECHECK_PINNED)
    ensure("ok K-67: the six pin sites state ty 1.2.3 and "
           "ruff 4.5.6, the versions tools/vos/cli/typecheck.py fixes" in ctx.rep.out,
           f"six agreeing sites are one ok line naming both pins: {ctx.rep.out!r}")


def _k67_workflow_drift_is_a_finding() -> None:
    # the copy a runner resolves rather than one a reader opens: a pin stale here
    # runs the gate under a checker the tools do not fix, with every readable site
    # still agreeing
    ctx = _k67(_README_PINNED, _TYPECHECK_PINNED,
               _WORKFLOW_PINNED.replace("ruff==4.5.6", "ruff==4.5.5"))
    ensure(".github/workflows/host-gates.yml's ruff workflow install line states "
           "4.5.5, tools/vos/cli/typecheck.py pins 4.5.6"
           in _findings_under(ctx, "K-67"),
           f"a drifted workflow pin names the two figures: "
           f"{_findings_under(ctx, 'K-67')!r}")


def _k67_disagreement_names_both_figures() -> None:
    ctx = _k67(_README_PINNED.replace("| 1.2.3 |", "| 9.9.9 |"), _TYPECHECK_PINNED)
    found = _findings_under(ctx, "K-67")
    ensure("tools/README.md's ty checker-table row states 9.9.9, "
           "tools/vos/cli/typecheck.py pins 1.2.3" in found,
           f"a drifted site names the two figures and nothing else: {found!r}")


def _k67_unreadable_source_fails_closed() -> None:
    # the source side gone: a rule that cannot read its ground reports, never
    # passes over nothing, however clean the README side looks
    ctx = _k67(_README_PINNED, "# no pins here\n")
    found = _findings_under(ctx, "K-67")
    ensure(any("no longer states TY_VERSION and RUFF_VERSION" in f for f in found),
           f"an unreadable source side is the finding: {found!r}")
    ensure(not any(line.startswith("ok K-67:") for line in ctx.rep.out),
           "fail-closed: no ok line stands beside the unread side")


# K-75's newest site: the floor as `run.py provision` restates it, which is the one
# site that could not have been an import, a TOML setting being no module. The
# selftest's single mutant for this rule seeds `tools/ruff.toml`, so without these two
# the claim that the rule bites at the provisioner's site would rest on a hand seed
# nobody reruns. Only that one site is asserted on; the fixture states no other, so
# the rest of `_FLOOR_SITES` reports missing and is tolerated exactly as this file's
# other cases tolerate the rules a small fixture cannot satisfy.
_TY_CONF = 'python-version = "3.14"\n'
_PROVISION_AT = 'INTERPRETER_FLOOR = "3.14"\n'
_PROVISION_DRIFTED = 'INTERPRETER_FLOOR = "3.13"\n'
_FLOOR_SITE = "tools/vos/cli/provision.py's provisioned floor states "


def _k75(provision: str) -> Context:
    files = {"docs/requirements-register.md": _REGISTER_MIN,
             "tools/README.md": _README_PINNED,
             "tools/ty.toml": _TY_CONF,
             "tools/vos/cli/provision.py": provision}
    with sandbox_tree(files) as root:
        ctx = _context(root)
        meta.run(ctx)
        return ctx


def _k75_provisioned_floor_at_the_pin_is_not_a_finding() -> None:
    found = _findings_under(_k75(_PROVISION_AT), "K-75")
    ensure(not any(f.startswith(_FLOOR_SITE) for f in found),
           f"the provisioner's floor agrees, so its site names nothing: {found!r}")


def _k75_provisioned_floor_drifted_is_a_finding() -> None:
    found = _findings_under(_k75(_PROVISION_DRIFTED), "K-75")
    ensure(f"{_FLOOR_SITE}3.13, tools/ty.toml fixes 3.14" in found,
           f"a drifted provisioned floor names the two figures: {found!r}")


def _k75_unreadable_provisioner_fails_closed() -> None:
    # the site gone rather than wrong: a rule that cannot find a site it enumerates
    # reports it, never drops it and passes over the sites it could still read
    found = _findings_under(_k75("# no floor here\n"), "K-75")
    ensure("tools/vos/cli/provision.py no longer states the floor in its provisioned "
           "floor, in a form this rule reads" in found,
           f"an unreadable site is the finding: {found!r}")


def cases() -> list[Case]:
    return [
        Case("estimates-refused-edit-writes-nothing",
             _estimates_refused_edit_writes_nothing),
        Case("estimates-repair-reaches-fixpoint", _estimates_repair_reaches_fixpoint),
        Case("bindings-truncated-row-is-a-finding",
             _bindings_truncated_row_is_a_finding),
        Case("counts-overflow-is-a-finding", _counts_overflow_is_a_finding),
        Case("k67-agreement-is-ok", _k67_agreement_is_ok),
        Case("k67-disagreement-names-both-figures",
             _k67_disagreement_names_both_figures),
        Case("k67-workflow-drift-is-a-finding", _k67_workflow_drift_is_a_finding),
        Case("k67-unreadable-source-fails-closed", _k67_unreadable_source_fails_closed),
        Case("k75-provisioned-floor-at-the-pin-is-not-a-finding",
             _k75_provisioned_floor_at_the_pin_is_not_a_finding),
        Case("k75-provisioned-floor-drifted-is-a-finding",
             _k75_provisioned_floor_drifted_is_a_finding),
        Case("k75-unreadable-provisioner-fails-closed",
             _k75_unreadable_provisioner_fails_closed),
    ]
