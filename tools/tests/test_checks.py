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
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos import sailbundle
from vos.checks import Context, bindings, counts, estimates, generated, meta, pins
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


def _k96_record_is_held_total_in_both_directions() -> None:
    # There are two records and each is a totality claim over its own series, so the
    # fixture crosses them: the attended record carries a row naming no item and misses
    # the attended item, and the agent-parallel record carries the attended item and
    # misses the agent-parallel one. Four findings, and the pair of them is what says
    # the two records are read apart rather than as one table with a heading in it.
    plan = ("# Plan\n\n"
            "* [x] **A · Done** · 3 h actual · 50.0%\n"
            "* [x] **P · Fanned out** · 3 h actual · 50.0% · agent-parallel\n\n"
            "**S subtotal:** 6 h · 100% · 6 h complete.\n\n"
            "### Calibration record\n\n"
            "| Item | Pool | Estimate |\n"
            "| --- | --- | --- |\n"
            "| B | I | 4 |\n\n"
            "#### The agent-parallel series\n\n"
            "| Item | Pool | Estimate |\n"
            "| --- | --- | --- |\n"
            "| A | I | 4 |\n")
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                       PLAN: plan}) as root:
        ctx = _context(root)
        estimates.run(ctx)
        found = _findings_under(ctx, "K-96")
        ensure("A is a completed attended item the calibration record carries no row for"
               in found, f"the missing row is a finding: {found!r}")
        ensure("the calibration record carries B, which is not a completed attended item "
               "of the plan" in found, f"the stray row is a finding: {found!r}")
        ensure("P is a completed agent-parallel item the agent-parallel record carries "
               "no row for" in found, f"the missing parallel row is a finding: {found!r}")
        ensure("the agent-parallel record carries A, which is not a completed "
               "agent-parallel item of the plan" in found,
               f"an attended item is a stray row in the parallel record: {found!r}")
        ensure(ctx.shared.get("calibration_rows") == 1
               and ctx.shared.get("parallel_rows") == 1,
               f"each floor counts its own record's rows: "
               f"{ctx.shared.get('calibration_rows')!r} and "
               f"{ctx.shared.get('parallel_rows')!r}")


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


_PREREQ_REGISTER = (
    "# Register\n\n## §6\n\n"
    "**R-06-024** MUST: Four artifacts are hard prerequisites.\n"
    "· Accept: the list has four entries rather than five.\n· Trace: t\n")
_PREREQ_SPEC = (
    "# Specification\n\n## 6. Trusted Computing Base\n\n1. One TCB member.\n"
    'Prerequisites: <a id="r-06-024"></a><a id="r-06-025"></a>\n\n'
    "- (1) Verified compiler.\n- (2) Certifying compiler.\n"
    "- (3) Cost annotations.\n- (4) Constant-time verification.\n\n"
    '<a id="r-06-026"></a>\nAn unrelated enumeration: (1), (2).\n'
    "All four are untrusted evidence-producing machinery.\n")


def _counts_prereqs(spec: str, fix: bool = False) -> Context:
    with sandbox_tree({counts.REGISTER: _PREREQ_REGISTER,
                       counts.SPEC: spec}) as root:
        ctx = _context(root, fix=fix)
        ctx.shared.update(cj_confer=[], fc_seams=[], fc_confer=[], rf_confer=[],
                          dispositions=0, rot_cases=0)
        counts.run(ctx)
        return ctx


def _counts_multiline_prerequisites_keep_their_owner() -> None:
    ctx = _counts_prereqs(_PREREQ_SPEC)
    ensure(ctx.q["build-prereqs"] == 4,
           "the whole bookmarked list counts, and the next bookmark's markers do not")
    ensure(ctx.q["tcb-items"] == 1,
           "the prerequisite bullets must not become extra TCB members")
    found = _findings_under(ctx, "K-24")
    ensure(not any("build-prereqs" in f for f in found),
           f"all three prerequisite claims agree with the multiline owner: {found!r}")


def _counts_removed_prerequisite_is_a_finding() -> None:
    ctx = _counts_prereqs(_PREREQ_SPEC.replace("- (3) Cost annotations.\n", ""))
    found = _findings_under(ctx, "K-24")
    ensure(ctx.q["build-prereqs"] == 3
           and any("build-prereqs asserted as 'Four', the artifact gives 'three'" in f
                   for f in found),
           f"removing a member invalidates the declared count: {found!r}")


def _counts_unreadable_prerequisite_owner_is_not_repaired() -> None:
    for spec in (_PREREQ_SPEC.replace('id="r-06-024"', 'id="other-owner"'),
                 _PREREQ_SPEC.replace("(1)", "one").replace("(2)", "two")
                 .replace("(3)", "three").replace("(4)", "four")):
        ctx = _counts_prereqs(spec, fix=True)
        found = _findings_under(ctx, "K-24")
        ensure(ctx.q["build-prereqs"] == 0
               and any(f.startswith("build-prereqs's owner no longer states") for f in found),
               f"a missing bookmark or unreadable enumeration is a finding: {found!r}")
        ensure(counts.REGISTER not in ctx.fixed and counts.SPEC not in ctx.fixed,
               f"unresolved claims must not be repaired to zero: {ctx.fixed!r}")


_PROJECT_PINNED = '[dependency-groups]\ndev = ["ty==1.2.3", "ruff==4.5.6"]\n'
_LOCK_PINNED = ('[[package]]\nname = "ty"\nversion = "1.2.3"\n'
                '[[package]]\nname = "ruff"\nversion = "4.5.6"\n')
_README_PINNED = ("# Tools\n\n"
                  "| Checker | Pin | What |\n| --- | --- | --- |\n"
                  "| [ty](https://x) | 1.2.3 | types |\n"
                  "| [ruff](https://x) | 4.5.6 | lint |\n")


def _k67(readme: str, project: str | None,
         lock: str = _LOCK_PINNED) -> Context:
    files = {"docs/requirements-register.md": _REGISTER_MIN,
             "tools/README.md": readme,
             "tools/uv.lock": lock}
    if project is not None:
        files["tools/pyproject.toml"] = project
    with sandbox_tree(files) as root:
        ctx = _context(root)
        meta.run(ctx)
        return ctx


def _k67_agreement_is_ok() -> None:
    ctx = _k67(_README_PINNED, _PROJECT_PINNED)
    ensure("ok K-67: the README and lockfile state ty 1.2.3 and "
           "ruff 4.5.6, the versions tools/pyproject.toml fixes" in ctx.rep.out,
           f"agreement names both pins: {ctx.rep.out!r}")


def _k67_lock_drift_is_a_finding() -> None:
    ctx = _k67(_README_PINNED, _PROJECT_PINNED,
               _LOCK_PINNED.replace('version = "4.5.6"', 'version = "4.5.5"'))
    ensure("tools/uv.lock's ruff versions are ['4.5.5'], tools/pyproject.toml pins 4.5.6"
           in _findings_under(ctx, "K-67"),
           f"a drifted lock pin names the two figures: "
           f"{_findings_under(ctx, 'K-67')!r}")


def _k67_disagreement_names_both_figures() -> None:
    ctx = _k67(_README_PINNED.replace("| 1.2.3 |", "| 9.9.9 |"), _PROJECT_PINNED)
    found = _findings_under(ctx, "K-67")
    ensure("tools/README.md's ty checker-table row states 9.9.9, "
           "tools/pyproject.toml pins 1.2.3" in found,
           f"a drifted site names the two figures and nothing else: {found!r}")


def _k67_unreadable_source_fails_closed() -> None:
    ctx = _k67(_README_PINNED, "# no pins here\n")
    found = _findings_under(ctx, "K-67")
    ensure(any("cannot supply exact ty and ruff pins" in item for item in found),
           f"an unreadable source side is the finding: {found!r}")
    ensure(not any(line.startswith("ok K-67:") for line in ctx.rep.out),
           "fail-closed: no ok line stands beside the unread side")


_TY_CONF = 'python-version = "3.14"\n'
_PROVISION_AT = 'INTERPRETER_FLOOR = "3.14"\n'
_PROVISION_DRIFTED = 'INTERPRETER_FLOOR = "3.13"\n'
_FLOOR_SITE = "tools/vos/cli/provision.py's provisioned floor states "


def _k75(provision: str, project: str =
         '[project]\nrequires-python = ">=3.14,<3.15"\n') -> Context:
    files = {"docs/requirements-register.md": _REGISTER_MIN,
             "tools/README.md": _README_PINNED,
             "tools/ty.toml": _TY_CONF,
             "tools/pyproject.toml": project,
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


def _k75_project_floor_is_held() -> None:
       for project, fragment in (
                     ('[project]\nrequires-python = ">=3.13,<3.15"\n', "requires-python states"),
                     ("", "cannot supply requires-python")):
              found = _findings_under(_k75(_PROVISION_AT, project), "K-75")
              ensure(any(fragment in item for item in found),
                        f"a drifted or missing project constraint must report: {found!r}")


def _k81(files: dict[str, str], residues: dict[tuple[str, str], str],
         table_id: str = "1234abcd") -> Context:
    record = ("# Components\n\n## Pinned as submodules\n\n"
              "| Submodule | Upstream | Pin |\n| --- | --- | --- |\n"
              f"| `upstream/example-core` | `example/example-core` | `{table_id}` |\n")
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                       "THIRD-PARTY.md": record, **files}) as root:
        ctx = _context(root)
        ctx.corpus.gitlinks["upstream/example-core"] = "1234abcd" + "0" * 32
        ctx.shared["citation_window"] = []
        with (patch.object(pins, "RESIDUE", {}),
              patch.object(pins, "SITE_RESIDUE", residues)):
            pins._pins(ctx)
        return ctx


def _k81_historical_residue_is_scoped() -> None:
    site = ("docs/history.md", "abcd1234")
    recorded = {site[0]: "example-core measured at abcd1234\n"}
    residue = {site: "the completed fixture measurement"}
    ensure(not _findings_under(_k81(recorded, residue), "K-81"),
           "the declared historical edition is accepted at its own site")
    ctx = _k81({**recorded, "docs/current.md": "example-core pins abcd1234\n"}, residue)
    found = _findings_under(ctx, "K-81")
    ensure(len(found) == 1 and "docs/current.md:1 states" in found[0],
           f"the same id elsewhere must still fail: {found!r}")
    ensure(ctx.shared["pin_restatements"] == 1,
           "only current restatements contribute to the held-site count")
    changed = _k81({site[0]: "example-core measured at abcd1234 and deadbeef\n"}, residue)
    ensure(any("pin as deadbeef" in item for item in _findings_under(changed, "K-81")),
           "an exception for one id must not cover another id in the same file")


def _k81_unused_historical_residue_fails() -> None:
    site = ("docs/history.md", "abcd1234")
    for files in ({}, {site[0]: "```text\nexample-core measured at abcd1234\n```\n"}):
        found = _findings_under(_k81(files, {site: "the completed fixture measurement"}),
                                "K-81")
        ensure(len(found) == 1 and "no site outside the pin table states it" in found[0],
               f"a removed or displayed site must leave an unused residue: {found!r}")


def _k81_historical_residue_cannot_exempt_table() -> None:
    ctx = _k81({}, {("THIRD-PARTY.md", "abcd1234"): "an old fixture pin"},
               table_id="abcd1234")
    found = _findings_under(ctx, "K-81")
    ensure(any("pins upstream/example-core at abcd1234" in item for item in found),
           f"the current table is unconditionally held against the index: {found!r}")
    ensure(any("no site outside the pin table states it" in item for item in found),
           f"a table row cannot exercise a historical exception: {found!r}")


def _k81_historical_residue_requires_reason() -> None:
    ctx = _k81({"docs/history.md": "example-core measured at abcd1234\n"},
               {("docs/history.md", "abcd1234"): " "})
    found = _findings_under(ctx, "K-81")
    ensure(len(found) == 1 and "scoped residue with no reason" in found[0],
           f"a historical exception needs an explicit reading: {found!r}")


def _k88_foreign_library_is_a_finding() -> None:
    raw: dict[str, object] = {key: {} for key in sailbundle._TOP_LEVEL}
    raw.update(version=1, embedding="plain",
               hashes={"/root/.opam/unselected-switch/share/sail/lib/arith.sail":
                       {"md5": "0" * 32}})
    bundle = sailbundle.Bundle(raw)
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN}) as root:
        owners, findings = generated._owners(_context(root), generated.GENERATED[0], bundle)
    ensure(owners == 0 and len(findings) == 1 and "unselected-switch" in findings[0],
           f"a foreign Sail library must be a finding, not a crash or silent omission: {findings}")


def cases() -> list[Case]:
    return [
        Case("estimates-refused-edit-writes-nothing",
             _estimates_refused_edit_writes_nothing),
        Case("estimates-repair-reaches-fixpoint", _estimates_repair_reaches_fixpoint),
        Case("k96-record-is-held-total-in-both-directions",
             _k96_record_is_held_total_in_both_directions),
        Case("bindings-truncated-row-is-a-finding",
             _bindings_truncated_row_is_a_finding),
        Case("counts-overflow-is-a-finding", _counts_overflow_is_a_finding),
        Case("counts-multiline-prerequisites-keep-their-owner",
             _counts_multiline_prerequisites_keep_their_owner),
        Case("counts-removed-prerequisite-is-a-finding",
             _counts_removed_prerequisite_is_a_finding),
        Case("counts-unreadable-prerequisite-owner-is-not-repaired",
             _counts_unreadable_prerequisite_owner_is_not_repaired),
        Case("k67-agreement-is-ok", _k67_agreement_is_ok),
        Case("k67-disagreement-names-both-figures",
             _k67_disagreement_names_both_figures),
              Case("k67-lock-drift-is-a-finding", _k67_lock_drift_is_a_finding),
        Case("k67-unreadable-source-fails-closed", _k67_unreadable_source_fails_closed),
        Case("k75-provisioned-floor-at-the-pin-is-not-a-finding",
             _k75_provisioned_floor_at_the_pin_is_not_a_finding),
        Case("k75-provisioned-floor-drifted-is-a-finding",
             _k75_provisioned_floor_drifted_is_a_finding),
        Case("k75-unreadable-provisioner-fails-closed",
             _k75_unreadable_provisioner_fails_closed),
       Case("k75-project-floor-is-held", _k75_project_floor_is_held),
        Case("k81-historical-residue-is-scoped", _k81_historical_residue_is_scoped),
        Case("k81-unused-historical-residue-fails", _k81_unused_historical_residue_fails),
        Case("k81-historical-residue-cannot-exempt-table",
             _k81_historical_residue_cannot_exempt_table),
        Case("k81-historical-residue-requires-reason", _k81_historical_residue_requires_reason),
        Case("k88-foreign-library-is-a-finding", _k88_foreign_library_is_a_finding),
    ]
