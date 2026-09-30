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
finding rather than a stopped run, K-67 fails closed on an owner it cannot read,
and K-75 decides the one floor site its single mutant does not seed.
"""

import json
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos import device_regs, rtl_width, sailbundle, workorder
from vos.checks import Context, bindings, compounds, counts, estimates, generated, meta, pins
from vos.register import read_artifacts, read_register
from vos.report import Reporter

# enough register for read_register to parse; the groups under test never read it
_REGISTER_MIN = "# Register\n\n## §1\n\n**R-01-001** MUST x.\n· Trace: t\n"

PLAN = estimates.PLAN


def _work_files(plan: str, m8a: tuple[str, ...] = (),
                m8b: tuple[str, ...] = ()) -> dict[str, str]:
    items, _, _ = estimates._parse(plan)
    assigned = set(m8a + m8b)
    owner = {
        "version": 1,
        "buckets": {"m8a": list(m8a), "m8b": list(m8b), "committed": [],
                    "conditional": [], "option": [i.label for i in items if not i.done
                        and estimates._head(i.label) not in assigned]},
        "dispatch": [{"item": key, "start": [],
                      "artifacts": ["docs/requirements-register.md"], "unmet": [], "join": []}
                     for key in m8a],
        "unpriced": ["docs/requirements-register.md"],
    }
    return {"docs/requirements-register.md": _REGISTER_MIN, PLAN: plan,
            workorder.OWNER: json.dumps(owner)}


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
    # one legacy share: the first --fix removes it, and a second --fix over the
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
        ensure("· 3 h, range 2–4\n" in repaired,
               f"the obsolete share is removed: {repaired!r}")
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


def _estimate_summary() -> str:
    values = {key: "999–999" if "range" in key else "999"
              for key in estimates.SUMMARY_FIELDS}
    return (estimates.SUMMARY_START + "\n" + estimates._summary_table(values)
            + "\n" + estimates.SUMMARY_END + "\n\n")


def _nested_estimates_use_explicit_leaves() -> None:
    plan = ("# Plan\n\n" + _estimate_summary() +
            "* [ ] **M1.2 · Backend**\n"
            "  * [ ] **M1.2g · Carrier**\n"
            "    * [ ] **M1.2g-i · Memory** · 1.5 h, range 1–2 · 0.0% · X\n"
            "    * [ ] **M1.2g-ii · Integration** · 7.5 h, range 4–11 · 0.0% · X\n"
            "  * [ ] **M1.2f · Campaign** · 7 h, range 4–10 · 0.0% · X\n"
            "* [ ] **M1.7 · Boot** · 9 h, range 6–12 · 0.0% · I\n"
            "**M1 subtotal:** 25 h · 100% · open range 15–35 h.\n")
    items, _, malformed = estimates._parse(plan)
    ensure(not malformed, f"nested cell-less parents are legal: {malformed}")
    ensure([item.ancestors for item in items] == [
        ("M1.2", "M1.2g"), ("M1.2", "M1.2g"), ("M1.2",), ()],
        "grandchildren retain the outer parent and the next sibling restores it")
    with sandbox_tree(_work_files(plan, ("M1.2g-i", "M1.2g-ii", "M1.2f", "M1.7"))) as root:
        ctx = _context(root, fix=True)
        estimates.run(ctx)
        ensure("| Committed M8a open h | 25 |" in ctx.fixed[PLAN]
               and "| Committed M8a open range h | 15–35 |" in ctx.fixed[PLAN],
               "only explicitly listed nested leaves enter the committed effort")


def _retained_estimates_are_scope_not_actuals() -> None:
    plan = ("# Plan\n\n" + _estimate_summary() +
            "* [x] **M1.2b · Accepted** · 6 h retained estimate, actual n/a · 99.0%"
            " · agent-parallel\n"
            "* [ ] **M1.2g · Open** · 9 h, range 5–13 · 60.0% · X\n\n"
            "**M1 subtotal:** 15 h · 100% · 6 h complete · open range 5–13 h.\n\n"
            "#### The agent-parallel series\n\n"
            "| Item | Pool | Estimate |\n| --- | --- | --- |\n"
            "| M1.2b | n/a | n/a |\n")
    with sandbox_tree(_work_files(plan, ("M1.2g",))) as root:
        ctx = _context(root, fix=True)
        estimates.run(ctx)
        repaired = ctx.fixed[PLAN]
        ensure("6 h retained estimate, actual n/a · agent-parallel" in repaired,
               f"repair must preserve the unavailable actual: {repaired!r}")
        ensure("| Retained completion estimate h | 6 |" in repaired
               and "| Unmeasured completed items | 1 |" in repaired,
               "retained scope must be reported separately")
        ensure("| Committed M8a open h | 9 |" in repaired
               and "| Committed M8a open class X h | 9 |" in repaired,
               "completed estimated scope must leave the remaining-work budget")
        ensure(not _findings_under(ctx, "K-34"), "the completed form must be readable")
    items, _, malformed = estimates._parse(repaired)
    ensure(not malformed, f"the repaired plan must parse: {malformed!r}")
    completed = {"M1.2b": items[0]}
    findings: list[str] = []
    fit = estimates._fit([("M1.2b", "n/a", "n/a")], completed,
                         "record", "completed item", findings)
    ensure(not findings and not any(fit.values()), "unmeasured work cannot enter a fit")
    estimates._fit([("M1.2b", "X-authored", "6")], completed,
                   "record", "completed item", findings)
    ensure(any("not a measured actual" in f for f in findings),
           "a retained estimate cannot masquerade as a calibration measurement")
    _, _, malformed = estimates._parse(repaired.replace("* [x]", "* [ ]"))
    ensure(any("completed checkbox" in f for f in malformed),
           "an open checkbox cannot carry completed unmeasured work")
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                       PLAN: repaired}) as root:
        again = _context(root, fix=True)
        estimates.run(again)
        ensure(not again.fixed, "retained-cell repair must reach its fixpoint")


def _optional_work_never_enters_gates_by_default() -> None:
    plan = ("# Plan\n\n" + _estimate_summary() +
            "* [ ] **M1.7 · Software fixture** · 10 h, range 8–12 · I\n"
            "* [ ] **R2 · RTL fixture** · 20 h, range 16–24 · I\n"
            "* [ ] **Q3b · Conditional fault evidence** · 17 h, range 10–24 · X\n"
            "* [ ] **New · Uncommissioned option** · 100 h, range 50–150 · X\n"
            "**S subtotal:** 147 h · 100% · open range 84–210 h.\n")
    with sandbox_tree(_work_files(plan, ("M1.7",), ("R2",))) as root:
        ctx = _context(root, fix=True)
        estimates.run(ctx)
        repaired = ctx.fixed[PLAN]
        ensure("| Committed M8a open h | 10 |" in repaired
               and "| Committed M8b open h | 20 |" in repaired
               and "| Unfunded option open h | 117 |" in repaired,
               "an option changes full scope, not either committed gate")


def _explicitly_deferred_checklist_leaves_leave_early_gates() -> None:
    root = Path(__file__).resolve().parents[2]
    items, _, malformed = estimates._parse((root / PLAN).read_text(encoding="utf-8"))
    ensure(not malformed, f"the shipped plan must parse: {malformed!r}")
    deferred = {estimates._head(item.label) for item in items
                if not item.done and "after the M8a gate" in item.tail}
    owner = json.loads((root / workorder.OWNER).read_text(encoding="utf-8"))
    early = set(owner["buckets"]["m8a"] + owner["buckets"]["m8b"])
    ensure(bool(deferred) and not deferred & early,
           "explicitly deferred leaves must not enlarge an early gate")


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
                       "docs/assurance/field-bindings.md": bind_md}) as root:
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
    register = "# Register\n\n## §15\n\n" + "".join(
        f"**R-15-{n:03}** MUST: Absence (fixture {n}).\n· Trace: t\n"
        for n in range(1, 101))
    language = "# Typed assembly language\n\n### 7.1 The ninety-nine absences\n"
    with sandbox_tree({counts.REGISTER: register, counts.TAL: language}) as root:
        ctx = _context(root, fix=True)
        # the shared keys confers and views would have produced; counts reads
        # them positionally and this test runs counts alone
        ctx.shared.update(cj_confer=[], fc_seams=[], fc_confer=[], rf_confer=[],
                          dispositions=0, rot_cases=0)
        # This fixture deliberately registers a word count; narrative absence
        # counts in the real documents are optional and no longer registered.
        claim = (counts.TAL, "frozen-absences", "words",
                 r"(?<=### 7\.1 The )[\w-]+(?= absences)")
        with patch.object(counts, "CLAIMS", [claim]):
            counts.run(ctx)
        ensure("frozen-absences is 100, which has no word form; the claim in "
               f"{counts.TAL} must state it in digits" in _findings_under(ctx, "K-24"),
               f"the overflow is K-24's finding, naming the claim owed digits: "
               f"{_findings_under(ctx, 'K-24')!r}")
        ensure(counts.TAL not in ctx.fixed,
               "a quantity with no word form must not stage a repair")
        ensure(ctx.text(counts.TAL) == language,
               "the unresolved language claim must retain its original content")


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
_README_REFERENCES = "# Tools\n\nThe project manifest owns the checker pins.\n"


def _k67(readme: str | None, project: str | None,
         lock: str = _LOCK_PINNED) -> Context:
    files = {"docs/requirements-register.md": _REGISTER_MIN,
             "tools/uv.lock": lock}
    if readme is not None:
        files["tools/README.md"] = readme
    if project is not None:
        files["tools/pyproject.toml"] = project
    with sandbox_tree(files) as root:
        ctx = _context(root)
        meta.run(ctx)
        return ctx


def _k67_agreement_is_ok() -> None:
    ctx = _k67(_README_REFERENCES, _PROJECT_PINNED)
    ensure("ok K-67: the lockfile states ty 1.2.3 and "
           "ruff 4.5.6, the versions tools/pyproject.toml fixes" in ctx.rep.out,
           f"agreement names both pins: {ctx.rep.out!r}")


def _k67_lock_drift_is_a_finding() -> None:
    ctx = _k67(_README_REFERENCES, _PROJECT_PINNED,
               _LOCK_PINNED.replace('version = "4.5.6"', 'version = "4.5.5"'))
    ensure("tools/uv.lock's ruff versions are ['4.5.5'], tools/pyproject.toml pins 4.5.6"
           in _findings_under(ctx, "K-67"),
           f"a drifted lock pin names the two figures: "
           f"{_findings_under(ctx, 'K-67')!r}")


def _k67_does_not_require_prose_pins() -> None:
    for readme in (None, _README_REFERENCES, "# Checking tools\n\nRead the manifest.\n"):
        ctx = _k67(readme, _PROJECT_PINNED)
        ensure(not _findings_under(ctx, "K-67"),
               f"checker prose is not a required copy of the pins: {ctx.rep.out!r}")


def _k67_unreadable_source_fails_closed() -> None:
    for project in (None, "# no pins here\n", "[broken\n",
                    _PROJECT_PINNED.replace('"ty==1.2.3"', '"ty>=1.2.3"'),
                    _PROJECT_PINNED.replace('"ty==1.2.3"', '"ty==1.2.3", "ty==1.2.3"')):
        ctx = _k67(_README_REFERENCES, project)
        found = _findings_under(ctx, "K-67")
        ensure(any("cannot supply exact ty and ruff pins" in item for item in found),
               f"an unreadable source side is the finding: {found!r}")
        ensure(not any(line.startswith("ok K-67:") for line in ctx.rep.out),
               "fail-closed: no ok line stands beside the unread side")


def _k67_unreadable_lock_fails_closed() -> None:
    for lock in ("", "[broken\n", 'package = "not a table array"\n',
                 '[[package]]\nname = "ty"\nversion = "1.2.3"\n',
                 _LOCK_PINNED + '[[package]]\nname = "ty"\nversion = "1.2.3"\n'):
        ctx = _k67(_README_REFERENCES, _PROJECT_PINNED, lock)
        ensure(bool(_findings_under(ctx, "K-67")),
               f"missing, malformed or duplicate resolved pins must fail: {ctx.rep.out!r}")


_TY_CONF = 'python-version = "3.14"\n'
_PROVISION_AT = 'INTERPRETER_FLOOR = "3.14"\n'
_PROVISION_DRIFTED = 'INTERPRETER_FLOOR = "3.13"\n'
_FLOOR_SITE = "tools/vos/cli/provision.py's provisioned floor states "


_CAMPAIGN_JOBS = '  a:\n    python-version: "3.14"\n  b:\n    python-version: "3.14"\n'


def _k75(provision: str, project: str =
         '[project]\nrequires-python = ">=3.14,<3.15"\n',
         readme: str = "# Tools\n\nUse `uv python install --no-config 3.14`.\n",
         campaign: str = _CAMPAIGN_JOBS) -> Context:
    files = {"docs/requirements-register.md": _REGISTER_MIN,
             "tools/README.md": readme,
             "tools/ty.toml": _TY_CONF,
             "tools/ruff.toml": 'target-version = "py314"\n',
             "tools/pyproject.toml": project,
             ".github/workflows/host-gates.yml": 'python-version: "3.14"\n',
             ".github/workflows/guest-gates.yml": 'python-version: "3.14"\n',
             ".github/workflows/boot-crypto-target.yml": campaign,
             "tools/vos/cli/provision.py": provision}
    with sandbox_tree(files) as root:
        ctx = _context(root)
        meta.run(ctx)
        return ctx


def _k75_provisioned_floor_at_the_pin_is_not_a_finding() -> None:
    found = _findings_under(_k75(_PROVISION_AT), "K-75")
    ensure(not found,
           f"configuration and install command agree without prose copies: {found!r}")


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


def _k75_install_command_still_uses_supported_version() -> None:
    for command in ("Install Python from the project manifest.\n",
                    "Use `uv python install --no-config 3.13`.\n"):
        found = _findings_under(_k75(_PROVISION_AT, readme=command), "K-75")
        ensure(any("manual interpreter install" in item for item in found),
               f"an executable example must stay present and supported: {found!r}")


def _k75_every_workflow_job_is_held() -> None:
    # A site read only at its first match would pass the second job's interpreter.
    drifted = _CAMPAIGN_JOBS.replace('b:\n    python-version: "3.14"', 'b:\n    python-version: "3.13"')
    found = _findings_under(_k75(_PROVISION_AT, campaign=drifted), "K-75")
    ensure(".github/workflows/boot-crypto-target.yml's workflow interpreter states 3.13, "
           "tools/ty.toml fixes 3.14" in found,
           f"a later job's interpreter below the floor must report: {found!r}")


def _k97_reviewed_pin_is_required_without_prose_copies() -> None:
    source = 'VERILATOR_PIN = "9.999"\n'
    record = ("# Components\n\n| Tool | License | Standing |\n| --- | --- | --- |\n"
              "| Verilator | example terms | pinned at **9.999**. |\n")
    for owner, reviewed, accepted in (
            (source, record, True),
            (source, record.replace("9.999", "9.998"), False),
            ("", record, False),
            (source, "# Components\n", False),
            (source, "", False)):
        with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                           pins.VERILATOR_SRC: owner, "THIRD-PARTY.md": reviewed}) as root:
            ctx = _context(root, fix=True)
            pins._version_pin(ctx)
            found = _findings_under(ctx, "K-97")
            ensure(bool(found) != accepted,
                   f"only an exact reviewed row and pin can pass: {ctx.rep.out!r}")
            ensure(not ctx.fixed, "a version edit cannot manufacture a licence review")


_K115_SHA = "0123456789abcdef0123456789abcdef01234567"
_K115_RECORD = (
    "# Components\n\n### Development tools, contained by use\n\n"
    "| Tool | License | Standing |\n| --- | --- | --- |\n"
    f"| example/action | `MIT` | The reviewed v1.2.3 revision `{_K115_SHA}` has terms. |\n"
    "| zizmor | `MIT` | The reviewed **9.8.7** release's terms. |\n"
    "| actionlint | `MIT` | The reviewed **6.5.4** release's terms. |\n\n## Next\n")
_K115_WORKFLOW = (f"steps:\n  - uses: example/action@{_K115_SHA} # v1.2.3\n"
                  f"  - uses: example/action/restore@{_K115_SHA} # v1.2.3\n")
_K115_OWNERS = {"tools/pyproject.toml": '[dependency-groups]\nworkflows = ["zizmor==9.8.7"]\n',
                "tools/ci/actionlint.sh": "#!/bin/sh\nactionlint_version=6.5.4\n"}


def _k115(files: dict[str, str | None]) -> list[str]:
    base: dict[str, str | None] = {"docs/requirements-register.md": _REGISTER_MIN,
                                   "THIRD-PARTY.md": _K115_RECORD,
                                   ".github/workflows/a.yml": _K115_WORKFLOW, **_K115_OWNERS}
    merged = {path: text for path, text in {**base, **files}.items() if text is not None}
    with sandbox_tree(merged) as root:
        ctx = _context(root, fix=True)
        pins._workflow_pins(ctx)
        ensure(not ctx.fixed, "a pin edit cannot manufacture a licence review")
        return _findings_under(ctx, "K-115")


def _k115_agreement_and_sub_actions_pass() -> None:
    found = _k115({})
    ensure(not found, f"an action and its sub-action at the reviewed commit agree: {found!r}")


def _k115_moved_or_movable_references_fail() -> None:
    other = "f" * 40
    for workflow, fragment in (
            (_K115_WORKFLOW.replace(f"{_K115_SHA} # v1.2.3\n  -", f"{other} # v1.2.3\n  -"),
             "runs example/action at ffffffffffff (v1.2.3)"),
            (_K115_WORKFLOW.replace("# v1.2.3\n  -", "# v1.2.4\n  -"), "(v1.2.4)"),
            (_K115_WORKFLOW.replace(f"example/action@{_K115_SHA} # v1.2.3", "example/action@v1"),
             "uses `example/action@v1`, which is not"),
            (_K115_WORKFLOW.replace(f"@{_K115_SHA} # v1.2.3\n  -", f"@{_K115_SHA}\n  -"),
             "which is not owner/repo")):
        found = _k115({".github/workflows/a.yml": workflow})
        ensure(any(fragment in item for item in found),
               f"a moved or movable reference must report {fragment!r}: {found!r}")


def _k115_membership_is_held_both_ways() -> None:
    found = _k115({".github/workflows/b.yaml":
                   f"steps:\n  - uses: other/action@{_K115_SHA} # v1.2.3\n"})
    ensure(any("runs other/action, which" in item for item in found),
           f"an action with no reviewed row must report: {found!r}")
    found = _k115({".github/workflows/a.yml": f"steps:\n  - uses: other/action@{_K115_SHA} # v1.2.3\n",
                   "THIRD-PARTY.md": _K115_RECORD.replace(
                       "| zizmor |", f"| other/action | `MIT` | The reviewed v1.2.3 revision "
                                     f"`{_K115_SHA}`. |\n| zizmor |")})
    ensure(any("reviews example/action, which no workflow runs" in item for item in found),
           f"a row no workflow runs must report: {found!r}")


def _k115_analyzer_rows_follow_their_owners() -> None:
    cases: tuple[tuple[dict[str, str | None], str], ...] = (
        ({"tools/pyproject.toml": '[dependency-groups]\nworkflows = ["zizmor==9.8.8"]\n'},
         "states zizmor's reviewed release as 9.8.7, tools/pyproject.toml installs 9.8.8"),
        ({"tools/ci/actionlint.sh": "#!/bin/sh\nactionlint_version=6.5.5\n"},
         "states actionlint's reviewed release as 6.5.4"),
        ({"tools/ci/actionlint.sh": None}, "does not state actionlint_version"),
        ({"tools/pyproject.toml": "[dependency-groups]\n"}, "cannot supply"))
    for files, fragment in cases:
        found = _k115(files)
        ensure(any(fragment in item for item in found),
               f"an analyzer row must agree with its owner ({fragment!r}): {found!r}")


def _k115_unreadable_readings_fail_closed() -> None:
    duplicate = (f"| example/action | x | The reviewed v1.2.3 revision `{_K115_SHA}`. |\n"
                 "| zizmor |")
    cases: tuple[tuple[dict[str, str | None], str], ...] = (
        ({"THIRD-PARTY.md": None}, "is not in the repository"),
        ({"THIRD-PARTY.md": "# Components\n"}, "carries no `### Development tools"),
        ({"THIRD-PARTY.md": _K115_RECORD.replace(" v1.2.3 revision", " revision")},
         "0 times"),
        ({"THIRD-PARTY.md": _K115_RECORD.replace("| zizmor |", duplicate)},
         "is a second row for example/action"),
        ({".github/workflows/a.yml": None}, "carries no workflow"),
        ({".github/workflows/a.yml": "jobs: {}\n"}, "states an action reference"))
    for files, fragment in cases:
        found = _k115(files)
        ensure(any(fragment in item for item in found),
               f"an unreadable reading must report ({fragment!r}): {found!r}")


_K115_UNREAD = "states an action reference in a form K-115 does not read"


def _k115_every_uses_key_is_read_or_reported() -> None:
    # GitHub runs a reference written in a flow mapping, under a quoted key or as an
    # explicit key, and the block reading takes none of them. Each shape stands beside
    # the agreeing block lines, so a census that missed it would leave the rule reporting
    # agreement over an action with no row or a commit nobody reviewed.
    shapes = ("  - {{name: step, uses: {ref}}}\n",
              "  - {{uses: {ref}, with: {{a: b}}}}\n",
              '  - "uses": {ref} # v1.2.3\n',
              "  - 'uses': {ref} # v1.2.3\n",
              '  - name: step\n    "uses": {ref} # v1.2.3\n',
              "  - ? uses\n    : {ref} # v1.2.3\n",
              "  - uses : {ref} # v1.2.3\n")
    refs = (f"example/action@{_K115_SHA}",   # the reviewed commit
            f"other/action@{_K115_SHA}",     # an action with no row
            f"example/action@{'f' * 40}")    # a commit the row never reviewed
    for shape in shapes:
        offset = next(n for n, text in enumerate(shape.split("\n")) if "uses" in text)
        for ref in refs:
            found = _k115({".github/workflows/a.yml": _K115_WORKFLOW + shape.format(ref=ref)})
            ensure(len(found) == 1 and f"a.yml:{4 + offset} {_K115_UNREAD}" in found[0],
                   f"an unread shape is one finding at its line ({shape!r}, {ref}): {found!r}")
    # The only reference unread: its line is the finding, and neither the empty-subject
    # nor the row-runs-nothing direction speaks about a reference it could not read.
    found = _k115({".github/workflows/a.yml": f"steps:\n  - {{uses: example/action@{_K115_SHA}}}\n"})
    ensure(len(found) == 1 and f"a.yml:2 {_K115_UNREAD}" in found[0],
           f"an unread sole reference is one finding: {found!r}")


def _k115_census_counts_the_read_key_once() -> None:
    # The controls: a key the reading took is not counted again, a flow mapping whose
    # `uses:` opens its own line is read and held, and neither a comment nor a word
    # ending in the key's letters is a key.
    control = (_K115_WORKFLOW + "  # - {uses: other/action@v1}\n"
               "  - run: echo reuses: nothing\n")
    found = _k115({".github/workflows/a.yml": control})
    ensure(not found, f"comments and other words are not keys: {found!r}")
    flow = (_K115_WORKFLOW + "  - {\n      name: step,\n"
            f"      uses: example/action@{'f' * 40} # v1.2.3\n    }}\n")
    found = _k115({".github/workflows/a.yml": flow})
    ensure(len(found) == 1 and "a.yml:6 runs example/action at ffffffffffff" in found[0],
           f"a read key is held against its row and not also counted unread: {found!r}")


def _k116(files: dict[str, str], gitlinks: dict[str, str]) -> list[str]:
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN, **files}) as root:
        ctx = _context(root, fix=True)
        ctx.corpus.gitlinks.clear()
        ctx.corpus.gitlinks.update(gitlinks)
        pins._bindings(ctx)
        ensure(not ctx.fixed, "a consumed binding is re-derived, never rewritten")
        return _findings_under(ctx, "K-116")


def _k116_consumed_bindings_are_held_whole_and_fail_closed() -> None:
    core = "c" * 40
    registry = json.dumps({"schema": "vos.rtl-width-transforms/1", "pin": core})
    files = {rtl_width.REGISTRY: registry}
    links = {rtl_width.CORE: core}
    ensure(not _k116(files, links), "a binding recording its gitlink's commit passes")
    for changed, gitlinks, needle in (
            # a moved gitlink with the registry not re-derived
            (files, {rtl_width.CORE: "e" * 40}, "carries upstream/cva6-cheri at eeee"),
            # the whole id is held, not the abbreviation a finding quotes
            (files, {rtl_width.CORE: core[:39] + "e"}, "carries upstream/cva6-cheri at cccc"),
            ({rtl_width.REGISTRY: json.dumps({"pin": core[:8]})},
             links, "registry pin cannot be read"),
            ({}, links, "is not in the repository"),
            (files, {}, "carries no gitlink")):
        found = _k116(changed, gitlinks)
        ensure(len(found) == 1 and needle in found[0],
               f"each broken binding is one finding naming it: {found!r}")
    # The device-register stamp is a generated artifact's binding, held by its K-88
    # row; holding it here too would price one moved gitlink as two findings.
    ensure(all(file not in generated.paths() for _, file, _, _ in pins.BINDINGS),
           "K-116 holds no binding inside an artifact K-88 already holds")


def _k88_device_regs(files: dict[str, str], gitlinks: dict[str, str],
                     edit: str | None = None) -> list[str]:
    """The device-register row's findings, its header edited after staging if asked."""
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN, **files}) as root:
        if edit is not None:
            (root / device_regs.ARTIFACT).write_text(edit, encoding="utf-8", newline="")
        ctx = _context(root, fix=True)
        ctx.corpus.gitlinks.clear()
        ctx.corpus.gitlinks.update(gitlinks)
        row = next(row for row in generated.GENERATED if row.path == device_regs.ARTIFACT)
        staged = corpus_mod.staged_blobs(root, [row.path])[row.path]
        if row.inspect is None or row.lane != "guest":
            raise AssertionError("the device-register package is a guest row with a host "
                                 "inspector")
        reading = row.inspect(ctx, row, staged)
        ensure(not ctx.fixed and not reading.fixed,
               "a device-register finding is a regeneration, never a rewrite")
        return reading.findings


def _k88_device_register_stamp_is_held_whole_and_fail_closed() -> None:
    mocha = "d" * 40
    header = f"// generated\n{device_regs.STAMP}{mocha}\npackage p;\nendpackage\n"
    files = {device_regs.ARTIFACT: header}
    links = {device_regs.UPSTREAM: mocha}
    ensure(not _k88_device_regs(files, links),
           "an indexed header recording its gitlink's commit passes")
    cases: tuple[tuple[dict[str, str], dict[str, str], str | None, str], ...] = (
        # the gitlink moved and the header, still what the index holds, was not
        # regenerated: the whole id is held, not the abbreviation a finding quotes
        (files, {device_regs.UPSTREAM: mocha[:39] + "e"}, None,
         "carries upstream/mocha at dddd"),
        # a hand edit leaves the stamp agreeing and the bytes off the index
        (files, links, header.replace("package p;", "package q;"),
         "differs from its indexed emission"),
        ({device_regs.ARTIFACT: header.replace(device_regs.STAMP, "// ")}, links, None,
         "records no readable owner revision"),
        ({}, links, None, "the git index does not carry it"),
        (files, {}, None, "carries no gitlink"))
    for changed, gitlinks, edit, needle in cases:
        found = _k88_device_regs(changed, gitlinks, edit)
        ensure(len(found) == 1 and needle in found[0],
               f"each broken reading is one finding naming it: {found!r}")


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


def _k81_generated_device_package_is_outside_the_window() -> None:
    # The same line in a tracked document is a restatement; in the generated device
    # package it is the generator's record, held by K-88 and read by nothing here.
    line = "// UART owner revision: example-core at deadbeef\n"
    ctx = _k81({device_regs.ARTIFACT: line, "docs/current.md": line}, {})
    found = _findings_under(ctx, "K-81")
    ensure(len(found) == 1 and "docs/current.md:1 states" in found[0],
           f"only the tracked document's restatement is read: {found!r}")


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



def _wasm_fixture() -> str:
    return (
        "# Performance\n\n"
        "| General scalar | **−20% to −40%** | fixture |\n"
        "| Wasm applications covered by whole-loop handlers or native-service batches | "
        "**−1% to −2%** | fixture |\n\n"
        "<!-- wasm-model-inputs -->\n" + compounds.WASM_INPUT_HEADER + "\n"
        "| Broad coverage | 0.95 | 5 / 10 | 0.03 / 0.05 |\n"
        "| Very high coverage | 0.99 | 5 / 10 | 0.02 / 0.05 |\n"
        "<!-- /wasm-model-inputs -->\n\n"
        "<!-- wasm-model-results -->\nstale\n<!-- /wasm-model-results -->\n")


def _wasm_model_repair_and_comparator() -> None:
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                       compounds.PERF: _wasm_fixture()}) as root:
        ctx = _context(root, fix=True)
        compounds._wasm(ctx)
        fixed = ctx.fixed[compounds.PERF]
        ensure("| Broad coverage | −80% to −90% | −19% to −33% | −35% to −60% |" in fixed,
               "native-work coverage must use the fixture's conventional comparator")
        ensure("| Very high coverage | −80% to −90% | −6% to −12% | −25% to −47% |" in fixed,
               "high coverage must retain residual interpreter and overhead costs")
        ensure("**−25% to −60%**" in fixed, "archetype must cover both scenarios")
        ensure("| Broad coverage | 0.95 | 5 / 10 | 0.03 / 0.05 |" in fixed,
               "repair must not alter engineering assumptions")
        (root / compounds.PERF).write_text(fixed, encoding="utf-8", newline="")
        again = _context(root, fix=True)
        compounds._wasm(again)
        ensure(not again.fixed and not _findings_under(again, "K-111"),
               f"Wasm repair must reach a fixpoint: {again.rep.out!r}")


def _wasm_model_bad_inputs_refuse_repair() -> None:
    good = _wasm_fixture()
    row = "| Broad coverage | 0.95 | 5 / 10 | 0.03 / 0.05 |"
    mutations = [
        good.replace(row, ""),
        good.replace(row, row + "\n" + row),
        good.replace("wasm-model-inputs", "wasm-model-lost"),
        good.replace("<!-- /wasm-model-results -->", ""),
        good.replace("| General scalar |", "| Removed native comparator |"),
        good.replace("| Wasm applications covered", "| Lost Wasm applications covered"),
        good.replace("0.95", "nan"),
        good.replace("0.95", "inf"),
        good.replace("0.95", "1.01"),
        good.replace("0.95", "-0.1"),
        good.replace("| 5 / 10 |", "| 10 / 5 |"),
        good.replace("| 0.03 / 0.05 |", "| 0.05 / 0.03 |"),
        good.replace("| 0.03 / 0.05 |", "| -0.03 / 0.05 |"),
        good.replace(row, "| Broad coverage | broken |"),
        good.replace("−20% to −40%", "−40% to −20%"),
    ]
    for bad in mutations:
        with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                           compounds.PERF: bad}) as root:
            ctx = _context(root, fix=True)
            compounds._wasm(ctx)
            ensure(bool(_findings_under(ctx, "K-111")), "bad model input must fail closed")
            ensure(not ctx.fixed, "bad model input must never rewrite derived results")


def _wasm_model_native_limit() -> None:
    raw = (_wasm_fixture()
           .replace("0.95 | 5 / 10 | 0.03 / 0.05", "1 | 5 / 10 | 0 / 0")
           .replace("0.99 | 5 / 10 | 0.02 / 0.05", "0 | 5 / 10 | 0 / 0"))
    with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                       compounds.PERF: raw}) as root:
        ctx = _context(root, fix=True)
        compounds._wasm(ctx)
        fixed = ctx.fixed[compounds.PERF]
        ensure("| Broad coverage | −80% to −90% | −0% to −0% | −20% to −40% |" in fixed,
               "full coverage without overhead must equal native, not erase hardware cost")
        ensure("| Very high coverage | −80% to −90% | −80% to −90% | −84% to −94% |" in fixed,
               "zero coverage must preserve interpreter cost and compound hardware cost")


def _wasm_scalar_fixture() -> str:
    return (
        "# Performance\n\n"
        "| General scalar | **−45% to −70%** | fixture |\n"
        "| Core µarch | Prepared Wasm scalar execution (§14) | Substituted | "
        "**−1% to −2%** | fixture | notes |\n"
        "| Wasm scalar execution, unchanged Core 3.0 modules (conditional target) | "
        "**−1% to −2%** | fixture |\n\n"
        "<!-- wasm-scalar-inputs -->\n" + compounds.WASM_SCALAR_HEADER + "\n"
        "| 60 / 90 | 2 / 1.5 |\n<!-- /wasm-scalar-inputs -->\n")


def _wasm_scalar_comparator_and_repair() -> None:
    # Hand-computed independent cases: cap at native, no improvement, and a
    # changed native comparator. The reference already contains hardware cost.
    for raw, expected in (
        (_wasm_scalar_fixture(), "**−45% to −85%**"),
        (_wasm_scalar_fixture().replace("2 / 1.5", "1 / 1"), "**−60% to −90%**"),
        (_wasm_scalar_fixture().replace("−45% to −70%", "−20% to −40%"), "**−20% to −85%**"),
    ):
        with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                           compounds.PERF: raw}) as root:
            ctx = _context(root, fix=True)
            compounds._wasm_scalar(ctx)
            fixed = ctx.fixed[compounds.PERF]
            # Count only the two Wasm rows; the native band can match the result.
            rows = [line for line in fixed.splitlines() if "Wasm scalar" in line]
            ensure(len(rows) == 2 and all(expected in row for row in rows),
                   "both headlines must use the same comparator without a second hardware cost")
            ensure(raw.split("<!-- wasm-scalar-inputs -->")[1]
                   == fixed.split("<!-- wasm-scalar-inputs -->")[1],
                   "repair must preserve authored assumptions")
            (root / compounds.PERF).write_text(fixed, encoding="utf-8", newline="")
            again = _context(root, fix=True)
            compounds._wasm_scalar(again)
            ensure(not again.fixed and not _findings_under(again, "K-112"),
                   "scalar target repair must reach a fixpoint")


def _wasm_scalar_bad_inputs() -> None:
    raw = _wasm_scalar_fixture()
    row = "| 60 / 90 | 2 / 1.5 |"
    mutations = [raw.replace(row, value) for value in (
        "", row + "\n" + row, "| 90 / 60 | 2 / 1.5 |",
        "| 60 / 100 | 2 / 1.5 |", "| -1 / 90 | 2 / 1.5 |",
        "| 60 / 90 | 1.5 / 2 |", "| 60 / 90 | 2 / 0.9 |",
        "| nan / 90 | 2 / 1.5 |", "| 60 / 90 | inf / 1.5 |",
        "| 20 / 90 | 2 / 1.5 |", "| broken |",
    )]
    mutations += [
        raw.replace("<!-- /wasm-scalar-inputs -->", ""),
        raw + "<!-- wasm-scalar-inputs -->\n",
        raw.replace("| General scalar |", "| Lost comparator |"),
        raw.replace("−45% to −70%", "−70% to −45%"),
        raw.replace("Prepared Wasm scalar execution", "Lost headline"),
        raw.replace("(conditional target)", "(lost target)"),
        raw + raw,
    ]
    for bad in mutations:
        with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                           compounds.PERF: bad}) as root:
            ctx = _context(root, fix=True)
            compounds._wasm_scalar(ctx)
            ensure(bool(_findings_under(ctx, "K-112")) and not ctx.fixed,
                   "malformed scalar inputs or missing/duplicate sites must refuse repair")


def _k84_retired_holders_are_historical_only() -> None:
    registry = "# Rules\n\n| ~~K-999~~ | retired | n/a | Removed subject. |\n"
    for name, accepted in ((meta.LOG, True), (PLAN, False), ("docs/current.md", False)):
        files = {"docs/requirements-register.md": _REGISTER_MIN,
                 meta.RULES: registry, PLAN: "# Plan\n", meta.LOG: "# Log\n"}
        files[name] = "# Evidence\n\nLanded: Tier B under **K-999**.\n"
        with sandbox_tree(files) as root:
            ctx = _context(root)
            meta._landings(ctx, {"K-00"})
            found = _findings_under(ctx, "K-84")
            ensure(bool(found) != accepted,
                   f"retired holder acceptance must be scoped to the log: {name}: {found}")


def _k84_retirement_needs_an_unfenced_registry_row() -> None:
    for registry in ("# Rules\n", "# Rules\n\n```\n| ~~K-999~~ | retired | n/a | Gone. |\n```\n"):
        with sandbox_tree({"docs/requirements-register.md": _REGISTER_MIN,
                           meta.RULES: registry, PLAN: "# Plan\n",
                           meta.LOG: "# Log\n\nLanded: Tier B under **K-999**.\n"}) as root:
            ctx = _context(root)
            meta._landings(ctx, {"K-00"})
            ensure(bool(_findings_under(ctx, "K-84")),
                   "a historical citation needs a real retirement record")


def cases() -> list[Case]:
    return [
        Case("wasm-scalar-comparator-and-repair", _wasm_scalar_comparator_and_repair),
        Case("wasm-scalar-bad-inputs", _wasm_scalar_bad_inputs),
        Case("wasm-model-repair-and-comparator", _wasm_model_repair_and_comparator),
        Case("wasm-model-bad-inputs-refuse-repair", _wasm_model_bad_inputs_refuse_repair),
        Case("wasm-model-native-limit", _wasm_model_native_limit),
        Case("estimates-refused-edit-writes-nothing",
             _estimates_refused_edit_writes_nothing),
        Case("estimates-repair-reaches-fixpoint", _estimates_repair_reaches_fixpoint),
        Case("nested-estimates-use-explicit-leaves", _nested_estimates_use_explicit_leaves),
        Case("retained-estimates-are-scope-not-actuals", _retained_estimates_are_scope_not_actuals),
        Case("optional-work-never-enters-gates-by-default",
             _optional_work_never_enters_gates_by_default),
        Case("explicitly-deferred-checklist-leaves-leave-early-gates",
             _explicitly_deferred_checklist_leaves_leave_early_gates),
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
        Case("k67-does-not-require-prose-pins", _k67_does_not_require_prose_pins),
        Case("k67-lock-drift-is-a-finding", _k67_lock_drift_is_a_finding),
        Case("k67-unreadable-source-fails-closed", _k67_unreadable_source_fails_closed),
        Case("k67-unreadable-lock-fails-closed", _k67_unreadable_lock_fails_closed),
        Case("k75-provisioned-floor-at-the-pin-is-not-a-finding",
             _k75_provisioned_floor_at_the_pin_is_not_a_finding),
        Case("k75-provisioned-floor-drifted-is-a-finding",
             _k75_provisioned_floor_drifted_is_a_finding),
        Case("k75-unreadable-provisioner-fails-closed",
             _k75_unreadable_provisioner_fails_closed),
        Case("k75-project-floor-is-held", _k75_project_floor_is_held),
        Case("k75-install-command-still-uses-supported-version",
             _k75_install_command_still_uses_supported_version),
        Case("k75-every-workflow-job-is-held", _k75_every_workflow_job_is_held),
        Case("k97-reviewed-pin-is-required-without-prose-copies",
             _k97_reviewed_pin_is_required_without_prose_copies),
        Case("k115-agreement-and-sub-actions-pass", _k115_agreement_and_sub_actions_pass),
        Case("k115-moved-or-movable-references-fail", _k115_moved_or_movable_references_fail),
        Case("k115-membership-is-held-both-ways", _k115_membership_is_held_both_ways),
        Case("k115-analyzer-rows-follow-their-owners", _k115_analyzer_rows_follow_their_owners),
        Case("k115-unreadable-readings-fail-closed", _k115_unreadable_readings_fail_closed),
        Case("k115-every-uses-key-is-read-or-reported", _k115_every_uses_key_is_read_or_reported),
        Case("k115-census-counts-the-read-key-once", _k115_census_counts_the_read_key_once),
        Case("k81-historical-residue-is-scoped", _k81_historical_residue_is_scoped),
        Case("k81-unused-historical-residue-fails", _k81_unused_historical_residue_fails),
        Case("k81-historical-residue-cannot-exempt-table",
             _k81_historical_residue_cannot_exempt_table),
        Case("k81-historical-residue-requires-reason", _k81_historical_residue_requires_reason),
        Case("k81-generated-device-package-is-outside-the-window",
             _k81_generated_device_package_is_outside_the_window),
        Case("k116-consumed-bindings-are-held-whole-and-fail-closed",
             _k116_consumed_bindings_are_held_whole_and_fail_closed),
        Case("k88-device-register-stamp-is-held-whole-and-fail-closed",
             _k88_device_register_stamp_is_held_whole_and_fail_closed),
        Case("k88-foreign-library-is-a-finding", _k88_foreign_library_is_a_finding),
        Case("k84-retired-holders-are-historical-only", _k84_retired_holders_are_historical_only),
        Case("k84-retirement-needs-an-unfenced-registry-row",
             _k84_retirement_needs_an_unfenced_registry_row),
    ]
