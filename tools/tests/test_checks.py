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


# K-119's fixture: seven active rules and one struck row inside the name class's range,
# so the passing page already exercises a range skipping a struck id. A membership
# sentence in the section after the reach section must not be read as a class.
_K119_ROWS = ("# Rules\n\n| Rule | Group | Passing means | Ground |\n| --- | --- | --- | --- |\n"
              "| K-00 | meta | a | b |\n| K-01 | traces | a | b |\n| K-02 | traces | a | b |\n"
              "| ~~K-03~~ | retired | n/a | gone |\n| K-04 | traces | a | b |\n"
              "| K-05 | counts | a | b |\n| K-06 | floors | a | b |\n| K-07 | tables | a | b |\n")
_K119_NAME = ("Where the set is found by **name**, it resolves, which is what K-01 through "
              "K-04 are.")
_K119_COMPUTED = ("Where the set is a **computed value**, it is recomputed, which is what "
                  "K-05 are.")
_K119_PATTERN = ("Where the set is found by **pattern**, a regex, which is what K-06 are, "
                 "and it matches less.")
_K119_TOTAL = ("Where the set is **total**, nothing narrows. That is what K-00 and K-07 are: "
               "the registry.")


def _k119(name: str = _K119_NAME, computed: str = _K119_COMPUTED,
          pattern: str = _K119_PATTERN, total: str = _K119_TOTAL,
          heading: str = meta.REACH_HEADING,
          quarantined: str | None = None) -> tuple[list[str], list[str]]:
    page = (f"{_K119_ROWS}\n{heading}\n\n{name} {computed} {pattern}\n\n{total}\n\n"
            "## After\n\nA stray list, which is what K-09 are.\n")
    files = {"docs/requirements-register.md": _REGISTER_MIN, meta.RULES: page}
    if quarantined is not None:
        files[meta.Q_RULES] = quarantined
    with sandbox_tree(files) as root:
        ctx = _context(root)
        meta.run(ctx)
        return _findings_under(ctx, "K-119"), ctx.rep.out


def _k119_each_rule_in_one_class_passes() -> None:
    # an italic word between the lead and the bold name is crossed rather than read as
    # the end of the lead's reach
    for name in (_K119_NAME, _K119_NAME.replace("by **name**", "by *exact* **name**")):
        found, out = _k119(name=name)
        ensure(not found, f"every active rule named once is clean: {found!r}")
        ensure("ok K-119: each of the registry's 7 rules is named under exactly one of the "
               "four reach classes (name 3, computed value 1, pattern 1, total 2)" in out,
               f"the range places K-01, K-02 and K-04 and skips the struck row: {out!r}")


def _k119_unnamed_and_doubly_named_rules_are_findings() -> None:
    for kwargs, want in (
            ({"total": _K119_TOTAL.replace("K-00 and K-07", "K-00")},
             "K-07 is registered and named under no reach class"),
            ({"pattern": _K119_PATTERN.replace("K-06 are", "K-05 and K-06 are")},
             "K-05 is named under two reach classes, computed value and pattern, where the "
             "page says one"),
            ({"name": _K119_NAME.replace("K-01 through", "K-01, K-01 through")},
             "the 'name' class names K-01 more than once")):
        found, _ = _k119(**kwargs)
        ensure(want in found, f"{want!r} must be reported: {found!r}")


def _k119_ids_a_class_names_must_be_active_rules() -> None:
    held_apart = ("# Held apart\n\n| Rule | Group | Passing means | Ground |\n"
                  "| --- | --- | --- | --- |\n| K-58 | banks | a | b |\n")
    for kwargs, wants in (
            ({"total": _K119_TOTAL.replace("K-00 and K-07", "K-00, K-07 and K-09")},
             ["the 'total' class names K-09, which the registry does not carry"]),
            ({"total": _K119_TOTAL.replace("K-00 and K-07", "K-00, K-03 and K-07")},
             ["the 'total' class names K-03, which the registry carries struck, so no run "
              "reports it"]),
            ({"total": _K119_TOTAL.replace("K-00 and K-07", "K-00, K-07 and K-58"),
              "quarantined": held_apart},
             ["the 'total' class names K-58, which the quarantine's registry carries and "
              "its own gate runs"]),
            ({"pattern": _K119_PATTERN.replace("K-06 are", "K-09 are")},
             ["the 'pattern' class names K-09, which the registry does not carry",
              "the 'pattern' class names no rule the registry carries",
              "K-06 is registered and named under no reach class"])):
        found, _ = _k119(**kwargs)
        for want in wants:
            ensure(want in found, f"{want!r} must be reported: {found!r}")


def _k119_ranges_expand_over_active_rows() -> None:
    for kwargs, wants in (
            # the range reaches K-02, so naming it again elsewhere is a second class
            ({"computed": _K119_COMPUTED.replace("K-05 are", "K-02 and K-05 are")},
             ["K-02 is named under two reach classes, name and computed value, where the "
              "page says one"]),
            # an end on a struck row cannot stand in for the active rule past it
            ({"name": _K119_NAME.replace("K-01 through K-04", "K-01 through K-03")},
             ["the 'name' class closes a range at K-03, which the registry carries struck, "
              "so no run reports it"]),
            ({"name": _K119_NAME.replace("K-01 through K-04", "K-04 through K-01")},
             ["the 'name' class names the range K-04 through K-01, which runs backwards or "
              "spans one rule"])):
        found, _ = _k119(**kwargs)
        for want in wants:
            ensure(want in found, f"{want!r} must be reported: {found!r}")


def _k119_unreadable_class_sentences_fail_closed() -> None:
    for kwargs, want in (
            ({"name": _K119_NAME.replace("K-04 are", "K-04 and the rest are")},
             "the 'name' class lists 'K-01 through K-04 and the rest', which is not a list "
             "of rule ids and ranges this rule reads"),
            ({"computed": "Where the set is a **computed value**, it is recomputed."},
             "the 'computed value' class states no membership sentence(s) this rule reads"),
            ({"computed": _K119_COMPUTED + " That is what K-05 are."},
             "the 'computed value' class states two membership sentence(s) this rule reads"),
            # a class's region starts at its lead, so a membership sentence between the
            # lead and the bold name is the class's own second rather than read by none
            ({"computed": "Where the set is made of rules which is what K-01 are, and a "
                          "**computed value**, it is recomputed, which is what K-05 are."},
             "the 'computed value' class states two membership sentence(s)"),
            ({"total": _K119_TOTAL.replace("**total**", "**whole**")},
             "opens a reach class '**whole**' that is not one of the four this rule reads"),
            ({"total": _K119_TOTAL.replace("**total**", "**whole**")},
             "tools/check-rules.md opens no 'total' class in a form this rule reads"),
            # the lead is matched in any letter case and the class name exactly, so a name
            # differing in case alone is a fifth class
            ({"total": _K119_TOTAL.replace("**total**", "**Total**")},
             "opens a reach class '**Total**' that is not one of the four this rule reads"),
            ({"heading": "## What a run decides"},
             "tools/check-rules.md carries no '## What a passing run does not decide' "
             "section"),
            # ahead of the first class no class's region reaches, so a class introduced
            # there in other words is caught by its membership sentence alone
            ({"heading": meta.REACH_HEADING
              + "\n\nWhen the set is found by **marker**, which is what K-05 are."},
             "states a membership sentence ahead of the first reach class, so no class "
             "reads it"),
            # either word is read in either capitalization, so a lower-case `that` written
            # mid-sentence and a capital `Which` opening a sentence are membership
            # sentences too
            ({"heading": meta.REACH_HEADING
              + "\n\nThe marker rules come first; that is what K-05 are."},
             "states a membership sentence ahead of the first reach class, so no class "
             "reads it"),
            ({"computed": _K119_COMPUTED + " Which is what K-05 are."},
             "the 'computed value' class states two membership sentence(s) this rule reads")):
        found, out = _k119(**kwargs)
        ensure(any(want in item for item in found), f"{want!r} must be reported: {found!r}")
        ensure(not any("named under no reach class" in item for item in found),
               f"an unread class is one finding, not one per rule it held: {found!r}")
        ensure(not any(line.startswith("ok K-119:") for line in out),
               "fail-closed: no ok line stands beside an unread class")


_K119_LEAD_FINDING = "states 'Where the set is' in a form that opens no reach class"


def _k119_every_class_lead_is_read() -> None:
    # A fifth class opened by other words than the four use is still read and named, and
    # a lead naming no class in bold is reported rather than folded into the class before.
    for kwargs, want in (
            ({"total": "Where the set is located by **marker**, nothing narrows. "
                       + _K119_TOTAL},
             "opens a reach class '**marker**' that is not one of the four this rule reads"),
            # the lead is read in any letter case, so a class opened mid-sentence is read
            ({"computed": _K119_COMPUTED
              + " Past it, where the set is located by **marker**, nothing narrows."},
             "opens a reach class '**marker**' that is not one of the four this rule reads"),
            ({"computed": _K119_COMPUTED
              + " Where the set is located by a marker, nothing narrows."},
             _K119_LEAD_FINDING),
            # any `.` ends the lead's reach, a code span's included, so the bold name past
            # it opens nothing
            ({"computed": _K119_COMPUTED
              + " Where the set is located by `a.b` **marker**, nothing narrows."},
             _K119_LEAD_FINDING),
            # the lead is found in underscore italics, wrapped across a line or spaced
            # apart, none of which opens a class, so each is reported rather than read
            # as part of the class before it
            ({"computed": _K119_COMPUTED
              + " _Where the set is_ located by **marker**, nothing narrows."},
             _K119_LEAD_FINDING),
            ({"computed": _K119_COMPUTED
              + " Where the set\nis located by **marker**, nothing narrows."},
             _K119_LEAD_FINDING),
            ({"computed": _K119_COMPUTED
              + " Where the set  is located by **marker**, nothing narrows."},
             _K119_LEAD_FINDING)):
        found, out = _k119(**kwargs)
        ensure(any(want in item for item in found), f"{want!r} must be reported: {found!r}")
        ensure(not any(line.startswith("ok K-119:") for line in out),
               "fail-closed: no ok line stands beside an unread lead")


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
    f"| example/action | `MIT` | The reviewed v1.2.3 revision `{_K115_SHA}` has "
    f"[terms](https://github.com/example/action/blob/{_K115_SHA}/LICENSE). |\n"
    "| zizmor | `MIT` | The reviewed **9.8.7** release's terms. |\n"
    "| actionlint | `MIT` | The reviewed **6.5.4** release's terms. |\n\n## Next\n")
_K115_WORKFLOW = (f"steps:\n  - uses: example/action@{_K115_SHA} # v1.2.3\n"
                  f"  - uses: example/action/restore@{_K115_SHA} # v1.2.3\n")


def _k115(files: dict[str, str | None]) -> list[str]:
    base: dict[str, str | None] = {"docs/requirements-register.md": _REGISTER_MIN,
                                   "THIRD-PARTY.md": _K115_RECORD,
                                   ".github/workflows/a.yml": _K115_WORKFLOW}
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


def _k115_moved_reference_is_quoted_apart_from_its_row() -> None:
    # A reference off its row's commit is quoted beside that commit at twelve digits, or
    # as far as the two must run to differ, so a change in the last digit prints two
    # distinct ids; a reference at the row's commit under another release keeps twelve.
    last = f"{_K115_SHA[:-1]}8"
    middle = f"{_K115_SHA[:19]}f{_K115_SHA[20:]}"
    for sha, version, shown, reviewed in (
            (last, "v1.2.3", last, _K115_SHA),
            (middle, "v1.2.3", middle[:20], _K115_SHA[:20]),
            ("f" * 40, "v1.2.3", "ffffffffffff", "0123456789ab"),
            (_K115_SHA, "v1.2.4", "0123456789ab", "0123456789ab")):
        workflow = _K115_WORKFLOW.replace(f"{_K115_SHA} # v1.2.3\n  -", f"{sha} # {version}\n  -")
        found = _k115({".github/workflows/a.yml": workflow})
        quoted = (f"a.yml:2 runs example/action at {shown} ({version}), THIRD-PARTY.md:7 "
                  f"reviewed {reviewed} (v1.2.3);")
        ensure(len(found) == 1 and quoted in found[0],
               f"a moved reference is quoted apart from its row's commit ({quoted}): {found!r}")


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


def _k115_licence_link_names_the_reviewed_commit() -> None:
    # The row's licence link is the edition its terms were read at: every link into the
    # action's own repository, whatever the case of its owner and name, names the
    # reviewed commit, and one at another commit, a tag or a branch is one finding. The
    # finding quotes both at twelve digits, or as far as they must run to differ.
    link = f"example/action/blob/{_K115_SHA}/LICENSE"
    last = f"{_K115_SHA[:-1]}8"
    moved = f"example/action/blob/{last}/LICENSE"
    for edit, quoted in (
            (moved, f"{last}, the row reviewed {_K115_SHA}"),
            (f"example/action/blob/{_K115_SHA[:12]}/LICENSE",
             f"{_K115_SHA[:12]}, the row reviewed {_K115_SHA[:13]}"),
            ("example/action/blob/v1.2.3/LICENSE", "v1.2.3, the row reviewed 0123456789ab"),
            ("example/action/blob/main/LICENSE", "main, the row reviewed 0123456789ab"),
            (f"Example/Action/blob/{'f' * 40}/LICENSE",
             "ffffffffffff, the row reviewed 0123456789ab"),
            (f"{link}) and [a copy](https://github.com/{moved}",
             f"{last}, the row reviewed {_K115_SHA}")):
        found = _k115({"THIRD-PARTY.md": _K115_RECORD.replace(link, edit)})
        ensure(len(found) == 1
               and f"THIRD-PARTY.md:7 links example/action's licence at {quoted}" in found[0],
               f"a licence link off the reviewed commit is one finding ({edit}): {found!r}")
    # A link into another repository states no revision of this action.
    found = _k115({"THIRD-PARTY.md": _K115_RECORD.replace(
        link, f"{link}) and [its dependency](https://github.com/other/dep/blob/{'f' * 40}/LICENSE")})
    ensure(not found, f"another repository's link is not this row's revision: {found!r}")


def _k115_leaves_the_analyzer_rows_to_k118() -> None:
    # The analyzers' rows are K-118's, held against the lock and the script that
    # install them; K-115 reads action rows alone, so a moved analyzer release is one
    # finding under K-118 rather than one under each rule.
    found = _k115({"THIRD-PARTY.md": _K115_RECORD.replace("**9.8.7**", "**9.8.8**")})
    ensure(not found, f"K-115 does not read an analyzer row: {found!r}")
    ensure({"zizmor", "actionlint"} <= {row.cell for row in pins.DEV_TOOL_ROWS},
           "K-118 holds both analyzer rows")


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
    # YAML gives the step a `uses` key in each shape below and the block reading takes
    # none of them. Each stands beside the agreeing block lines, so a census that missed
    # it would leave the rule reporting agreement over an action with no row or a commit
    # nobody reviewed. The second item is the shape's line offset the finding names.
    shapes = (("  - {{name: step, uses: {ref}}}\n", 0),
              ("  - {{uses: {ref}, with: {{a: b}}}}\n", 0),
              ('  - "uses": {ref} # v1.2.3\n', 0),
              ("  - 'uses': {ref} # v1.2.3\n", 0),
              ('  - name: step\n    "uses": {ref} # v1.2.3\n', 1),
              ("  - ? uses\n    : {ref} # v1.2.3\n", 0),
              ("  - uses : {ref} # v1.2.3\n", 0),
              # an explicit key with a trailing comment, a tag or an anchor, or its key
              # standing on the next line
              ("  - ? uses # c\n    : {ref} # v1.2.3\n", 0),
              ("  - ? !!str uses\n    : {ref} # v1.2.3\n", 0),
              ("  - ? &k uses\n    : {ref} # v1.2.3\n", 0),
              ("  - ?\n      uses\n    : {ref} # v1.2.3\n", 0),
              # an alias of a `uses` scalar anchored elsewhere, used as the key: the
              # finding is the alias's line, not the anchor's
              ("  - name: step\n    id: &k uses\n    *k : {ref} # v1.2.3\n", 2),
              # a double-quoted key spelled with an escape
              ('  - "u\\x73es": {ref} # v1.2.3\n', 0),
              # an explicit key inside a flow mapping, two census hits on one line
              ("  - {{? uses : {ref}}}\n", 0),
              # an explicit key flush against its `?` in a flow collection, which PyYAML
              # reads as a key's indicator whatever follows it: after `{`, a blank, an
              # entry's `,` or `[`, quoted, escaped or an alias, and opening a line that
              # continues a flow mapping
              ("  - {{?uses: {ref}}}\n", 0),
              ("  - {{ ?uses : {ref}}}\n", 0),
              ("  - [?uses: {ref}]\n", 0),
              ("  - {{name: a, ?uses: {ref}}}\n", 0),
              ('  - {{?"uses": {ref}}}\n', 0),
              ('  - {{?"u\\x73es": {ref}}}\n', 0),
              ("  - name: step\n    id: &k uses\n  - {{?*k : {ref}}}\n", 2),
              ("  - {{name: step,\n    ?uses : {ref}}}\n", 1),
              # a key on a line opening with `#` that continues a quoted scalar, and on
              # one whose `#` follows a no-break or ideographic space, which YAML reads
              # as content rather than a blank
              ('  - {{name: "a\n    # b", uses: {ref}}}\n', 1),
              ("  - {{name: x,\n  \u00a0#x, uses: {ref}}}\n", 1),
              ("  - {{name: x,\n  \u3000#x, uses: {ref}}}\n", 1))
    refs = (f"example/action@{_K115_SHA}",   # the reviewed commit
            f"other/action@{_K115_SHA}",     # an action with no row
            f"example/action@{'f' * 40}")    # a commit the row never reviewed
    for shape, offset in shapes:
        for ref in refs:
            found = _k115({".github/workflows/a.yml": _K115_WORKFLOW + shape.format(ref=ref)})
            ensure(len(found) == 1 and f"a.yml:{4 + offset} {_K115_UNREAD}" in found[0],
                   f"an unread shape is one finding at its line ({shape!r}, {ref}): {found!r}")
    # A carriage return alone breaks a YAML line, so an explicit key after one opens a
    # line to the parser and is counted there.
    found = _k115({".github/workflows/a.yml": _K115_WORKFLOW
                   + f"  - ? uses\r    : example/action@{_K115_SHA} # v1.2.3\n"})
    ensure(len(found) == 1 and f"a.yml:4 {_K115_UNREAD}" in found[0],
           f"a lone carriage return is a YAML line break: {found!r}")
    # The only reference unread: its line is the finding, and neither the empty-subject
    # nor the row-runs-nothing direction speaks about a reference it could not read.
    found = _k115({".github/workflows/a.yml": f"steps:\n  - {{uses: example/action@{_K115_SHA}}}\n"})
    ensure(len(found) == 1 and f"a.yml:2 {_K115_UNREAD}" in found[0],
           f"an unread sole reference is one finding: {found!r}")


def _k115_census_counts_the_read_key_once() -> None:
    # The controls: a key the reading took is not counted again, a flow mapping whose
    # `uses:` opens its own line is read and held, and neither a comment's prose nor a
    # word ending in the key's letters is a key.
    control = (_K115_WORKFLOW + "  # every step uses a reviewed action\n"
               "  - run: echo reuses: nothing\n")
    found = _k115({".github/workflows/a.yml": control})
    ensure(not found, f"prose and other words are not keys: {found!r}")
    # A comment line is read like any other, so a key's shape in one is counted, as one
    # in a trailing comment is: the census errs toward a finding.
    found = _k115({".github/workflows/a.yml": _K115_WORKFLOW + "  # - {uses: other/action@v1}\n"})
    ensure(len(found) == 1 and f"a.yml:4 {_K115_UNREAD}" in found[0],
           f"a key's shape in a comment line is counted: {found!r}")
    # After a block indicator, a `?` flush against what follows opens a plain scalar,
    # `?uses`, which PyYAML reads as no `uses` key.
    found = _k115({".github/workflows/a.yml": _K115_WORKFLOW
                   + f"  - ?uses: other/action@{_K115_SHA}\n"})
    ensure(not found, f"a block plain scalar opening with ? is not a key: {found!r}")
    flow = (_K115_WORKFLOW + "  - {\n      name: step,\n"
            f"      uses: example/action@{'f' * 40} # v1.2.3\n    }}\n")
    found = _k115({".github/workflows/a.yml": flow})
    ensure(len(found) == 1 and "a.yml:6 runs example/action at ffffffffffff" in found[0],
           f"a read key is held against its row and not also counted unread: {found!r}")


# K-118's fixture: a section with a paragraph, a table of five rows, and a later
# subsection whose numerals lie outside the window. Each held release has an owner of
# its own kind: a uv lock package, one snapshot's package, the snapshots every lock
# carries, and a quoted constant.
_K118_TOOLS = "# Components\n\n### Development tools, contained by use\n\n"
_K118_RECORD = (
    _K118_TOOLS + "**Lib.** The reviewed V2.0.0 edition is the snapshots' own.\n\n"
    "| Tool | License | Standing |\n| --- | --- | --- |\n"
    "| alpha | `MIT` | The reviewed `v1.2.3` tag's terms, under licence version 2.1. |\n"
    "| beta | `LGPL-2.1-only` | Snapshot release **4.5.6**; constant 7.8.9. |\n"
    "| gamma | `MIT` | A distribution tool. |\n"
    "| delta | `MIT` | Measured at 3.3.3. |\n"
    "| owner/action | `MIT` | K-115's row, the reviewed v1.0.0 revision. |\n\n"
    "#### A measured run\n\nBuilt at 9.9.9.\n")
_K118_OWNERS = {
    "tools/uv.lock": '[[package]]\nname = "alpha"\nversion = "1.2.3"\n',
    "tools/opam/x.lock": 'opam-version: "2.0"\ninstalled: ["beta.4.5.6" "lib.2.0.0"]\n',
    "tools/opam/y.lock": 'opam-version: "2.0"\ninstalled: [\n  "lib.2.0.0"\n]\n',
    "tools/vos/x.py": 'BETA = "7.8.9"\n',
    # a hook configuration carrying no repository, which the census reads as none
    pins.HOOK_CONFIG: "repos: []\n"}
_K118_ROWS = (
    pins.DevTool("alpha", (pins.Site("the reviewed release", rf"The reviewed `v{pins._V}` tag's",
                                     (pins.Owner("uv", "tools/uv.lock", "alpha"),)),),
                 residues=(pins.Residue("licence version 2.1", "the licence's own version"),)),
    pins.DevTool("beta", (
        pins.Site("the snapshot release", rf"\*\*{pins._V}\*\*",
                  (pins.Owner("opam", "tools/opam/x.lock", "beta"),)),
        pins.Site("the constant", rf"constant {pins._V}\.",
                  (pins.Owner("assign", "tools/vos/x.py", "BETA"),)))))
_K118_DECLARED = {"gamma": pins.Declared("states no release", releases=False),
                  "delta": pins.Declared("a measured run")}
_K118_PROSE = pins.DevTool("the paragraphs", (
    pins.Site("Lib's edition", rf"The reviewed V{pins._V} edition",
              (pins.Owner("opam-every", "tools/opam/", "lib"),)),))


def _k118(files: dict[str, str | None], rows: tuple[pins.DevTool, ...] = _K118_ROWS,
          declared: dict[str, pins.Declared] | None = None,
          prose: pins.DevTool = _K118_PROSE) -> tuple[list[str], list[str]]:
    base: dict[str, str | None] = {"docs/requirements-register.md": _REGISTER_MIN,
                                   "THIRD-PARTY.md": _K118_RECORD, **_K118_OWNERS}
    merged = {path: text for path, text in {**base, **files}.items() if text is not None}
    with sandbox_tree(merged) as root:
        ctx = _context(root, fix=True)
        with (patch.object(pins, "DEV_TOOL_ROWS", rows),
              patch.object(pins, "DEV_TOOL_DECLARED",
                           _K118_DECLARED if declared is None else declared),
              patch.object(pins, "DEV_TOOL_PROSE", prose)):
            pins._dev_tools(ctx)
        ensure(not ctx.fixed, "a release edit cannot manufacture a licence review")
        return _findings_under(ctx, "K-118"), ctx.rep.out


def _k118_agreement_passes() -> None:
    found, out = _k118({})
    ensure(not found, f"rows and paragraphs at their owners' releases agree: {found!r}")
    # four sites compared; alpha's two numerals, beta's two past its licence identifier
    # and the paragraph's one read; gamma, delta and the action row declared
    ensure(any(line.startswith("ok K-118: the 4 release statements") and "the 5 release "
               "numerals" in line and "3 other rows" in line for line in out),
           f"the ok line counts what was compared, read and declared: {out!r}")


def _k118_drift_each_way_is_a_finding() -> None:
    cases: tuple[tuple[dict[str, str | None], str], ...] = (
        # a row moved without its owner, in each owner kind
        ({"THIRD-PARTY.md": _K118_RECORD.replace("`v1.2.3`", "`v1.2.4`")},
         "THIRD-PARTY.md:9 (alpha) states the reviewed release as 1.2.4, where tools/uv.lock's "
         "alpha fixes 1.2.3"),
        ({"THIRD-PARTY.md": _K118_RECORD.replace("**4.5.6**", "**4.5.7**")},
         "(beta) states the snapshot release as 4.5.7, where tools/opam/x.lock's beta fixes 4.5.6"),
        ({"THIRD-PARTY.md": _K118_RECORD.replace("V2.0.0", "V2.0.1")},
         "THIRD-PARTY.md:5 states Lib's edition as 2.0.1, where the lib every snapshot "
         "under tools/opam/ installs fixes 2.0.0"),
        # an owner moved without its row, in each owner kind
        ({"tools/uv.lock": _K118_OWNERS["tools/uv.lock"].replace("1.2.3", "1.2.5")},
         "as 1.2.3, where tools/uv.lock's alpha fixes 1.2.5"),
        ({"tools/vos/x.py": 'BETA = "7.8.10"\n'}, "tools/vos/x.py's BETA fixes 7.8.10"),
        ({"tools/opam/y.lock": _K118_OWNERS["tools/opam/y.lock"].replace("2.0.0", "2.0.2")},
         "installs fixes 2.0.0, 2.0.2"))
    for files, fragment in cases:
        found, _ = _k118(files)
        ensure(len(found) == 1 and fragment in found[0],
               f"one drift is one finding naming both releases ({fragment!r}): {found!r}")


def _k118_unreadable_owners_fail_closed() -> None:
    cases: tuple[tuple[dict[str, str | None], str], ...] = (
        ({"tools/uv.lock": None}, "tools/uv.lock is not in the repository"),
        ({"tools/uv.lock": "[broken\n"}, "cannot supply its resolved releases"),
        ({"tools/uv.lock": 'package = "not a table array"\n'}, "not an array of tables"),
        ({"tools/uv.lock": _K118_OWNERS["tools/uv.lock"] * 2}, "alpha is stated 2 times"),
        ({"tools/opam/x.lock": 'opam-version: "2.0"\n'}, "carries no installed closure"),
        ({"tools/opam/y.lock": 'installed: ["other.1.0"]\n'}, "y.lock's lib is stated 0 times"),
        ({"tools/vos/x.py": "BETA = 7\n"}, "tools/vos/x.py's BETA is stated 0 times"))
    for files, fragment in cases:
        found, out = _k118(files)
        ensure(any(fragment in item for item in found),
               f"an unreadable owner must report ({fragment!r}): {found!r}")
        ensure(not any(line.startswith("ok K-118:") for line in out),
               "fail-closed: no ok line stands beside an unread owner")
    # one fault per owner however many sites it owns
    two = (*_K118_ROWS, pins.DevTool("epsilon", (pins.Site(
        "reviewed release", rf"at {pins._V}\.", (pins.Owner("uv", "tools/uv.lock", "alpha"),)),)))
    record = _K118_RECORD.replace("| gamma |", "| epsilon | `MIT` | Read at 1.2.3. |\n| gamma |")
    found, _ = _k118({"tools/uv.lock": None, "THIRD-PARTY.md": record}, rows=two)
    ensure(sum("tools/uv.lock is not in the repository" in item for item in found) == 1,
           f"an unreadable lock is one finding, not one per row: {found!r}")


def _k118_unreadable_record_fails_closed() -> None:
    cases: tuple[tuple[dict[str, str | None], str], ...] = (
        ({"THIRD-PARTY.md": None}, "is not in the repository"),
        ({"THIRD-PARTY.md": "# Components\n"}, "carries no `### Development tools"),
        ({"THIRD-PARTY.md": _K118_RECORD.replace("| Tool | License | Standing |\n", "")},
         "carries 0 `| Tool | License | Standing |` headers"),
        ({"THIRD-PARTY.md": _K118_RECORD.replace("**4.5.6**", "4.5.6")},
         "(beta) states the snapshot release 0 times"),
        ({"THIRD-PARTY.md": _K118_RECORD.replace("| gamma |", "| alpha |")},
         "is a second row for alpha"),
        ({"THIRD-PARTY.md": _K118_RECORD.replace("| --- | --- | --- |\n", "")},
         "is the development-tools table's header with no rule under it"),
        ({"THIRD-PARTY.md": _K118_TOOLS + "| Tool | License | Standing |\n| --- | --- | --- |\n"
                            "\n## Next\n"},
         "development-tools table has no row"))
    for files, fragment in cases:
        found, out = _k118(files)
        ensure(any(fragment in item for item in found),
               f"an unreadable record must report ({fragment!r}): {found!r}")
        ensure(not any(line.startswith("ok K-118:") for line in out),
               "fail-closed: no ok line stands beside an unread record")


def _k118_every_row_is_held_or_declared() -> None:
    # a row neither held nor declared, as a newly locked package's row would arrive
    found, _ = _k118({"THIRD-PARTY.md": _K118_RECORD.replace(
        "| gamma |", "| zeta | `MIT` | Locked at **5.5.5**. |\n| gamma |")})
    ensure(any("row for zeta, which K-118 neither holds" in item for item in found),
           f"an unmapped row must report: {found!r}")
    # a declaration naming no row, each kind
    found, _ = _k118({"THIRD-PARTY.md": _K118_RECORD.replace("| delta | `MIT` | Measured at "
                                                             "3.3.3. |\n", "")})
    ensure(any("declares a development-tools row for delta, and the table has none" in item
               for item in found), f"a declaration holding nothing must report: {found!r}")
    found, _ = _k118({}, rows=(*_K118_ROWS, pins.DevTool("omega")))
    ensure(any("row for omega, and the table has none" in item for item in found),
           f"a held row the table lacks must report: {found!r}")
    # a row both held and declared is one finding: neither reading is also reported as
    # naming a row the table lacks
    found, _ = _k118({}, declared={**_K118_DECLARED, "alpha": pins.Declared("twice")})
    ensure(len(found) == 1 and "row for alpha, which K-118 reads 2 ways" in found[0],
           f"a row read two ways must report once: {found!r}")


def _k118_census_reads_every_numeral() -> None:
    # a release written into a held row that no site reads
    found, _ = _k118({"THIRD-PARTY.md": _K118_RECORD.replace("constant 7.8.9.",
                                                             "constant 7.8.9. Bundled 6.6.")})
    ensure(len(found) == 1
           and "THIRD-PARTY.md:10 states 6.6 in beta's row, which no K-118 site reads" in found[0],
           f"an unread numeral in a held row must report: {found!r}")
    # and one written into a paragraph
    found, _ = _k118({"THIRD-PARTY.md": _K118_RECORD.replace(
        "the snapshots' own.", "the snapshots' own, and v8.1 before it.")})
    ensure(len(found) == 1 and "THIRD-PARTY.md:5 states v8.1 in the paragraphs" in found[0],
           f"an unread numeral in a paragraph must report on its line: {found!r}")
    # an opam identifier's release after its name's dot, whether the name ends in a
    # letter or in digits a letter leads, one after an underscore, a release carrying a
    # letter suffix and one continuing past it are each read, whole; a name's digits are
    # not told from a release's, so `python3.6.6` reads 6.6, erring toward a finding
    for written, numeral in (("`coq-extra.6.6.6`", "6.6.6"), ("`base64.6.6.6`", "6.6.6"),
                             ("`x509.6.6.6`", "6.6.6"), ("`iso8601.6.6.6`", "6.6.6"),
                             ("`rocq_6.6.6`", "6.6.6"), ("`python3.6.6`", "6.6"),
                             ("6.6.6rc1", "6.6.6rc1"), ("v6.6.6a1.dev2", "v6.6.6a1.dev2")):
        found, _ = _k118({"THIRD-PARTY.md": _K118_RECORD.replace(
            "constant 7.8.9.", f"constant 7.8.9. Bundled {written}.")})
        ensure(len(found) == 1
               and f"THIRD-PARTY.md:10 states {numeral} in beta's row, which no" in found[0],
               f"a release written as {written} must be read: {found!r}")
    # a numeral joined to the word before it is a licence identifier's version or a
    # tag's prefix, left to the sites, and so is its continuation past its dot
    found, _ = _k118({"THIRD-PARTY.md": _K118_RECORD.replace(
        "constant 7.8.9.", "constant 7.8.9. Under GPL-6.6 or LGPL-6.6.6 at tag release-6.6.6.")})
    ensure(not found, f"a hyphen-joined numeral is not a release the census reads: {found!r}")
    # a residue that no longer stands, or covers no numeral, suppresses nothing
    found, _ = _k118({"THIRD-PARTY.md": _K118_RECORD.replace("licence version 2.1",
                                                             "the licence")})
    ensure(any("residue `licence version 2.1`" in item and "stands in it 0 times" in item
               for item in found), f"a residue whose fragment left must report: {found!r}")
    covered = (pins.DevTool("alpha", _K118_ROWS[0].sites,
                            residues=(pins.Residue("The reviewed", "covers nothing"),
                                      pins.Residue("licence version 2.1",
                                                   "the licence's own version"))),
               _K118_ROWS[1])
    found, _ = _k118({}, rows=covered)
    ensure(any("residue `The reviewed` (covers nothing) declared for alpha's row covers no "
               "release numeral" in item for item in found),
           f"a residue covering no numeral must report: {found!r}")


def _k118_each_tag_is_read_or_reported() -> None:
    # A list of tags read against the releases some snapshot installs: every item is
    # one tag the site reads whole, so a tag added or removed is drift, and one the site
    # cannot read is a finding rather than an item dropped from a list read as a whole.
    eps = pins.DevTool("eps", (pins.Site("the tags read", pins._TAGS_READ,
                                         (pins.Owner("opam-any", "tools/opam/", "eps"),),
                                         each=pins._TAG),))
    owners = {"tools/opam/x.lock": 'installed: ["beta.4.5.6" "lib.2.0.0" "eps.1.0.0"]\n',
              "tools/opam/y.lock": 'installed: ["lib.2.0.0" "eps.2.0.0"]\n'}
    tags = "`V1.0.0` and `v2.0.0`"

    def run(stated: str) -> list[str]:
        record = _K118_RECORD.replace(
            "| gamma |", f"| eps | `MIT` | Read byte-identical at the {stated} tags. |\n| gamma |")
        return _k118({**owners, "THIRD-PARTY.md": record}, rows=(*_K118_ROWS, eps))[0]

    found = run(tags)
    ensure(not found, f"a list naming each installed release, led by V or v, agrees: {found!r}")
    for stated, fragment in (
            ("`V1.0.0`, `v2.0.0` and `V3.0.0`", "(eps) states the tags read as 1.0.0, 2.0.0, "
                                                 "3.0.0, where the eps the snapshots"),
            ("`v2.0.0`", "(eps) states the tags read as 2.0.0, where"),
            ("`V1.0.0`, `release-1.5` and `v2.0.0`",
             "(eps) states a tag K-118 cannot read among the tags read, `release-1.5`")):
        found = run(stated)
        ensure(len(found) == 1 and fragment in found[0],
               f"a tag added, removed or unreadable is one finding ({fragment!r}): {found!r}")
    # An unreadable item's numeral is not covered by the list, so the census reads it.
    found = run("`V1.0.0`, `rocq 1.5` and `v2.0.0`")
    ensure(len(found) == 2 and "states 1.5 in eps's row, which no K-118 site reads" in found[1],
           f"an unreadable tag's numeral falls to the census: {found!r}")


def _k118_declarations_are_held() -> None:
    # a row declared to state no release that has come to state one
    found, _ = _k118({"THIRD-PARTY.md": _K118_RECORD.replace("A distribution tool.",
                                                             "A distribution tool, 1.0.")})
    ensure(any("declared as stating no dotted release of gamma" in item and "1.0" in item
               for item in found), f"a no-release row stating one must report: {found!r}")
    # a declared row, or K-115's action row, states the one release it was read at,
    # however often, and never a second or none
    for old, new, fragment in (
            ("Measured at 3.3.3.", "Measured at 3.3.3, then 3.3.4.",
             "states 2 distinct releases of delta: 3.3.3, 3.3.4, which K-118 declares"),
            ("Measured at 3.3.3.", "Measured.", "states 0 distinct releases of delta, which"),
            ("Measured at 3.3.3.", "Measured at 3.3.3, then 3.3.3rc1.",
             "states 2 distinct releases of delta: 3.3.3, 3.3.3rc1"),
            ("v1.0.0 revision.", "v1.0.0 revision, after v0.9.0.",
             "states 2 distinct releases of owner/action: 0.9.0, 1.0.0")):
        found, _ = _k118({"THIRD-PARTY.md": _K118_RECORD.replace(old, new)})
        ensure(len(found) == 1 and fragment in found[0],
               f"a declared row stating other than one release must report: {found!r}")
    found, _ = _k118({"THIRD-PARTY.md": _K118_RECORD.replace("Measured at 3.3.3.",
                                                             "Measured at 3.3.3, tag v3.3.3.")})
    ensure(not found, f"one release stated twice is one release: {found!r}")
    # an unowned declaration whose owner has arrived
    pending = {**_K118_DECLARED,
               "delta": pins.Declared("no snapshot yet", pending="tools/opam/z.lock")}
    ensure(not _k118({}, declared=pending)[0], "an owner still absent keeps the declaration")
    found, _ = _k118({"tools/opam/z.lock": 'installed: ["delta.3.3.3"]\n'}, declared=pending)
    ensure(any("until tools/opam/z.lock is carried, and the index now carries it" in item
               for item in found), f"an arrived owner must end the declaration: {found!r}")
    # a residue unowned until an owner arrives is held the same way
    rows = (pins.DevTool("alpha", _K118_ROWS[0].sites, residues=(pins.Residue(
        "licence version 2.1", "no snapshot yet", pending="tools/opam/z.lock"),)), _K118_ROWS[1])
    ensure(not _k118({}, rows=rows)[0], "a residue whose owner is still absent stands")
    found, _ = _k118({"tools/opam/z.lock": 'installed: ["lib.2.0.0"]\n'}, rows=rows)
    ensure(len(found) == 1 and "residue `licence version 2.1` (no snapshot yet) declared for "
           "alpha's row is unowned until tools/opam/z.lock is carried, and the index now "
           "carries it" in found[0], f"an arrived owner must end the residue: {found!r}")


# One owner of each kind K-118 reads, fixing kappa's release: its owner, the files
# that fix 1.2.3, and the edit that moves it to 1.2.4 without the row.
_K118_KINDS: dict[str, tuple[pins.Owner, dict[str, str | None], dict[str, str | None]]] = {
    "uv": (pins.Owner("uv", "tools/uv.lock", "kappa"),
           {"tools/uv.lock": '[[package]]\nname = "kappa"\nversion = "1.2.3"\n'},
           {"tools/uv.lock": '[[package]]\nname = "kappa"\nversion = "1.2.4"\n'}),
    "uv-required": (pins.Owner("uv-required", "tools/pyproject.toml", "tool.uv.required-version"),
                    {"tools/pyproject.toml": '[tool.uv]\nrequired-version = "==1.2.3"\n'},
                    {"tools/pyproject.toml": '[tool.uv]\nrequired-version = "==1.2.4"\n'}),
    "opam": (pins.Owner("opam", "tools/opam/x.lock", "kappa"),
             {"tools/opam/x.lock": 'installed: ["kappa.1.2.3"]\n'},
             {"tools/opam/x.lock": 'installed: ["kappa.1.2.4"]\n'}),
    "opam-every": (pins.Owner("opam-every", "tools/opam/", "kappa"),
                   {"tools/opam/x.lock": 'installed: ["kappa.1.2.3"]\n',
                    "tools/opam/y.lock": 'installed: ["kappa.1.2.3"]\n'},
                   {"tools/opam/y.lock": 'installed: ["kappa.1.2.4"]\n'}),
    "opam-any": (pins.Owner("opam-any", "tools/opam/", "kappa"),
                 {"tools/opam/x.lock": 'installed: ["kappa.1.2.3"]\n',
                  "tools/opam/y.lock": 'installed: ["other.1.0"]\n'},
                 {"tools/opam/x.lock": 'installed: ["kappa.1.2.4"]\n'}),
    "assign": (pins.Owner("assign", "tools/vos/x.py", "KAPPA"),
               {"tools/vos/x.py": 'KAPPA = "1.2.3"\n'}, {"tools/vos/x.py": 'KAPPA = "1.2.4"\n'}),
    "shell": (pins.Owner("shell", "tools/x.sh", "kappa_version"),
              {"tools/x.sh": "kappa_version=1.2.3\n"}, {"tools/x.sh": "kappa_version=1.2.4\n"}),
}
_K118_KAPPA = (_K118_TOOLS + "| Tool | License | Standing |\n| --- | --- | --- |\n"
               "| kappa | `MIT` | Reviewed at 1.2.3. |\n\n## Next\n")


def _k118_kappa(kind: str, edit: dict[str, str | None]) -> list[str]:
    """kappa's findings, its one release held against the owner of one kind."""
    owner, files, _ = _K118_KINDS[kind]
    row = pins.DevTool("kappa", (pins.Site("the release", rf"Reviewed at {pins._V}\.", (owner,)),))
    return _k118({**files, "THIRD-PARTY.md": _K118_KAPPA, **edit}, rows=(row,), declared={},
                 prose=pins.DevTool("the paragraphs"))[0]


def _k118_every_owner_kind_detects_drift() -> None:
    # The shipped tables use exactly the kinds the reader carries, and each kind agrees
    # at its owner's release and reports that owner moved without the row.
    kinds = {owner.kind for tool in (*pins.DEV_TOOL_ROWS, pins.DEV_TOOL_PROSE)
             for site in tool.sites for owner in site.owners}
    # The hook kinds hold a rev's commit and its frozen tag rather than kappa's release;
    # k118-hook-revisions-are-held moves each without its row.
    ensure(kinds == set(_K118_KINDS) | {"pre-commit", "pre-commit-rev"},
           f"every owner kind a shipped site uses has a drift case: {kinds!r}")
    for kind, (_, _, drift) in _K118_KINDS.items():
        found = _k118_kappa(kind, {})
        ensure(not found, f"a {kind} owner at the row's release agrees: {found!r}")
        found = _k118_kappa(kind, drift)
        ensure(len(found) == 1 and "(kappa) states the release as 1.2.3, where" in found[0]
               and "1.2.4" in found[0], f"a moved {kind} owner is one finding: {found!r}")
    # an owner stating no one exact release is a finding, never a release read loosely
    loose: tuple[tuple[str, dict[str, str | None], str], ...] = (
        ("uv-required", {"tools/pyproject.toml": '[tool.uv]\nrequired-version = ">=1.2.3"\n'},
         "is '>=1.2.3', which requires no one exact release"),
        ("shell", {"tools/x.sh": 'kappa_version="1.2.3"\n'}, "kappa_version is stated 0 times"))
    for kind, edit, fragment in loose:
        found = _k118_kappa(kind, edit)
        ensure(len(found) == 1 and fragment in found[0],
               f"an owner not stating one exact release must report ({fragment!r}): {found!r}")


def _k118_a_row_named_by_its_release_stays_one_row() -> None:
    # A row whose cell states the release is named by a pattern, so a cell that moves
    # is still that row, reported as drift rather than as a row nobody holds.
    row = pins.DevTool("Py", (pins.Site("the series", r"^\| Py (\d+\.\d+) \|",
                                        (pins.Owner("assign", "tools/vos/x.py", "PY"),)),),
                       cell_re=r"Py \d+\.\d+")
    record = (_K118_TOOLS + "| Tool | License | Standing |\n| --- | --- | --- |\n"
              "| Py 3.14 | `PSF-2.0` | Runs every tool. |\n\n## Next\n")

    def run(text: str) -> list[str]:
        return _k118({"THIRD-PARTY.md": text, "tools/vos/x.py": 'PY = "3.14"\n'}, rows=(row,),
                     declared={}, prose=pins.DevTool("the paragraphs"))[0]

    found = run(record)
    ensure(not found, f"a cell stating its owner's release agrees: {found!r}")
    found = run(record.replace("Py 3.14", "Py 3.15"))
    ensure(len(found) == 1 and "(Py 3.15) states the series as 3.15, where tools/vos/x.py's "
           "PY fixes 3.14" in found[0], f"a moved cell is its row's drift, once: {found!r}")


# Two hook repository entries as `pre-commit autoupdate --freeze` writes them, one rev
# bare and one quoted, and the rows holding each one's frozen release and commit.
_K118_HOOKS = ("repos:\n"
               "  - repo: https://github.com/example/hooks\n"
               f"    rev: {'a' * 40} # frozen: v1.0.0\n"
               "    hooks:\n      - id: first\n"
               "  - repo: https://github.com/example/other\n"
               f"    rev: \"{'b' * 40}\" # frozen: v2.0.0\n"
               "    hooks:\n      - id: second\n")
_K118_HOOK_RECORD = _K118_RECORD.replace(
    "| gamma |", f"| hooks | `MIT` | The reviewed `v1.0.0` revision `{'a' * 40}`. |\n"
    f"| other | `MIT` | The reviewed `v2.0.0` revision `{'b' * 40}` of it. |\n| gamma |")
_K118_HOOK_ROWS = (*_K118_ROWS, pins._hook("hooks", "example/hooks"),
                   pins._hook("other", "example/other"))


def _k118_hook(config: str | None = _K118_HOOKS,
               record: str = _K118_HOOK_RECORD) -> tuple[list[str], list[str]]:
    return _k118({"THIRD-PARTY.md": record, pins.HOOK_CONFIG: config}, rows=_K118_HOOK_ROWS)


def _k118_hook_revisions_are_held() -> None:
    found, out = _k118_hook()
    ensure(not found and any(line.startswith("ok K-118: the 8 release statements")
                             for line in out),
           f"hook rows at their configuration's release and commit agree: {found!r} {out!r}")
    owner = f"{pins.HOOK_CONFIG}'s https://github.com/example/hooks"
    cases: tuple[tuple[str | None, str, str], ...] = (
        # the configuration moved without its row, release and commit each
        (_K118_HOOKS.replace("frozen: v1.0.0", "frozen: v1.0.1"), _K118_HOOK_RECORD,
         f"(hooks) states the reviewed release as 1.0.0, where {owner} fixes 1.0.1"),
        (_K118_HOOKS.replace("a" * 40, "c" * 40), _K118_HOOK_RECORD,
         f"(hooks) states the reviewed commit as {'a' * 40}, where {owner} fixes {'c' * 40}"),
        # the row moved without its configuration
        (_K118_HOOKS, _K118_HOOK_RECORD.replace("`v2.0.0`", "`v2.0.1`"),
         "(other) states the reviewed release as 2.0.1, where"),
        # a rev left as a tag is its own release and is no commit
        (_K118_HOOKS.replace(f"{'a' * 40} # frozen: v1.0.0", "v1.0.0"), _K118_HOOK_RECORD,
         f"(hooks) states the reviewed commit as {'a' * 40}, where {owner} fixes v1.0.0"))
    for config, record, fragment in cases:
        found, _ = _k118_hook(config, record)
        ensure(len(found) == 1 and fragment in found[0],
               f"one hook drift is one finding naming both sides ({fragment!r}): {found!r}")
    unreadable: tuple[tuple[str | None, str], ...] = (
        (None, f"{pins.HOOK_CONFIG} is not in the repository"),
        (_K118_HOOKS.replace("example/hooks", "example/moved"),
         f"{owner}'s repository is stated 0 times"),
        (_K118_HOOKS + "  - repo: https://github.com/example/hooks\n",
         f"{owner}'s repository is stated 2 times"),
        (_K118_HOOKS.replace("    hooks:\n      - id: first\n",
                             f"    rev: {'a' * 40}\n    hooks:\n"), f"{owner} states its rev 2 times"),
        (_K118_HOOKS.replace(" # frozen: v1.0.0", " # a comment"),
         f"{owner} states its rev as `rev: {'a' * 40} # a comment`, which is not"))
    for config, fragment in unreadable:
        found, out = _k118_hook(config)
        ensure(any(fragment in item for item in found),
               f"an unreadable hook configuration must report ({fragment!r}): {found!r}")
        ensure(not any(line.startswith("ok K-118:") for line in out),
               "fail-closed: no ok line stands beside an unread hook configuration")


def _k118_hook_census_reads_every_entry() -> None:
    # Every repository entry the configuration carries is read at its line, so code
    # pre-commit installs from a repository no row names is a finding however it is
    # pinned, and the configuration is read with no hook row to hold as well.
    _, out = _k118_hook()
    ensure(any("each of the 2 repository entries" in line for line in out),
           f"the ok line counts the entries the census read: {out!r}")
    found, out = _k118({pins.HOOK_CONFIG: None})
    ensure(len(found) == 1 and f"{pins.HOOK_CONFIG} is not in the repository" in found[0]
           and not any(line.startswith("ok K-118:") for line in out),
           f"an absent configuration fails closed with no hook row: {found!r}")
    extra = ("  - repo: https://github.com/example/extra\n"
             f"    rev: {'d' * 40} # frozen: v3.0.0\n    hooks:\n      - id: third\n")
    where = f"{pins.HOOK_CONFIG}:10"
    found, _ = _k118_hook(_K118_HOOKS + extra)
    ensure(len(found) == 1 and f"{where} runs hooks from https://github.com/example/extra, "
           "which no development-tools row K-118 holds names" in found[0]
           and ", at `" not in found[0], f"an entry no row names is one finding: {found!r}")
    for old, new, rev in ((f"{'d' * 40} # frozen: v3.0.0", "v3.0.0", "v3.0.0"),
                          (" # frozen: v3.0.0", "", "d" * 40)):
        found, _ = _k118_hook(_K118_HOOKS + extra.replace(old, new))
        ensure(len(found) == 1 and "https://github.com/example/extra" in found[0]
               and f", at `{rev}`, which is not a full commit with the `# frozen:` tag"
               in found[0], f"an unnamed entry's movable rev is in its finding: {found!r}")
    # pre-commit's own meta hooks need no row; a local repository runs code none reviews
    found, out = _k118_hook(_K118_HOOKS + "  - repo: meta\n    hooks:\n"
                            "      - id: check-useless-excludes\n")
    ensure(not found and any("each of the 3 repository entries" in line for line in out),
           f"a meta entry is read and needs no row: {found!r}")
    found, _ = _k118_hook(_K118_HOOKS + "  - repo: local\n    hooks:\n      - id: mine\n"
                          "        entry: mine\n        language: system\n")
    ensure(len(found) == 1 and f"{where} is a local hook repository" in found[0],
           f"a local entry is a finding: {found!r}")
    # an entry in a shape the reading does not take is a finding at each line holding a
    # key it did not take, whatever the entry names
    for written, lines in ((f"  - {{repo: https://github.com/example/flow, rev: {'e' * 40}}}\n",
                            (10,)),
                           ('  - "repo": https://github.com/example/quoted\n', (10,)),
                           ("  - &k repo: https://github.com/example/anchored\n", (10,)),
                           (f"  - rev: {'e' * 40}\n    repo: https://github.com/example/late\n",
                            (10, 11))):
        found, _ = _k118_hook(_K118_HOOKS + written)
        ensure(len(found) == len(lines) and all(
            f"{pins.HOOK_CONFIG}:{line} states a hook repository's `repo` or `rev` key in a "
            "form K-118 does not read" in item for line, item in zip(lines, found, strict=True)),
               f"an entry K-118 cannot read is a finding at its line ({written!r}): {found!r}")


_K118_HOOK_UNREAD = "states a hook repository's `repo` or `rev` key in a form K-118 does not read"


def _k118_hook_rev_is_read_at_its_entry_column() -> None:
    # An entry's rev is the `rev` key at its `repo` key's column, read whole as
    # `rev: <value>` with at most its `# frozen:` tag. A rev there carrying another
    # comment, a tag or an anchor is unread, and a line of the row's commit and tag
    # standing deeper, as a hook's key or a block scalar's text, is not the entry's rev
    # though YAML loads the entry with the moved one: each is a finding at its line, and
    # the entry's owner fixes no revision rather than the stand-in's.
    owner = f"{pins.HOOK_CONFIG}'s https://github.com/example/hooks"
    entry = f"    rev: {'a' * 40} # frozen: v1.0.0\n    hooks:\n      - id: first\n"
    reviewed = f"rev: {'a' * 40} # frozen: v1.0.0"
    moved = "    rev: v9.9.9 # moved\n    hooks:\n      - id: first\n"
    for written, lines, stated in (
            (entry.replace("frozen: v1.0.0", "pinned"), (3,), f"rev: {'a' * 40} # pinned"),
            (entry.replace("rev: ", "rev: !!str "), (3,), f"rev: !!str {reviewed[5:]}"),
            (entry.replace("rev: ", "rev: &r "), (3,), f"rev: &r {reviewed[5:]}"),
            (f"{moved}        {reviewed}\n", (3, 6), "rev: v9.9.9 # moved"),
            (f"{moved}        description: |\n          {reviewed}\n", (3, 7),
             "rev: v9.9.9 # moved")):
        found, out = _k118_hook(_K118_HOOKS.replace(entry, written))
        ensure(len(found) == len(lines) + 1 and all(
            f"{pins.HOOK_CONFIG}:{line} {_K118_HOOK_UNREAD}" in item
            for line, item in zip(lines, found, strict=False))
               and f"{owner} states its rev as `{stated}`, which is not" in found[-1]
               and not any(line.startswith("ok K-118:") for line in out),
               f"a rev K-118 does not read at its entry's column is reported ({written!r}): "
               f"{found!r}")
    # A comment line stating a rev under the entry is no key; the fixture's quoted rev
    # at the column is read whole, as the agreement case shows.
    found, _ = _k118_hook(_K118_HOOKS.replace(entry, f"{entry}        # rev: v0.0.1\n"))
    ensure(not found, f"a comment stating a rev is not the entry's rev: {found!r}")


def _k118_shipped_readings_are_declared() -> None:
    # The shipped tables hold real rows, and every declaration states its reason;
    # `check` decides the agreement.
    ensure(all(tool.sites for tool in pins.DEV_TOOL_ROWS),
           "a held row with no site would hold nothing")
    ensure(all(why.why.strip() for why in pins.DEV_TOOL_DECLARED.values()),
           "every declaration states its reason")


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


_K88_BLOCK = "\n".join(
    f"| `0x{8 * i:02x}` | `{name}` | RO | value |" for i, name in enumerate(
        ("VERSION", "BLOCK_BYTES", "BLOCK_COUNT", "STATUS", "RESULT", "BLOCK", "COMMAND",
         "ACK"))) + "\n| `0x100 + 8*i`, `0 <= i < B/8` | `DATA[i]` | RW | staging |\n"
_K88_MODEL = ("let blkdev_max_bytes : int(8192) = 8192\n"
              "let blkdev_max_block_bytes : int(4096) = 4096\n")
_K88_OWNERS = {device_regs.BLOCK: _K88_BLOCK, device_regs.BLOCK_MODEL: _K88_MODEL}
# The Mocha owners, used only to emit the fixture package: the checks below run in a
# tree without them, as the host does.
_K88_UART_OWNERS = {
    device_regs.UART: "\n".join(f"parameter logic [5:0] UART_{name}_OFFSET = 6'h {offset};"
                                for name, offset in zip(device_regs.UART_OFFSETS,
                                                        ("14", "18", "1c"), strict=True)),
    device_regs.UART_SPEC: "\n".join(f'{{ bits: "{i}" name: "{name}" }}'
                                     for i, name in enumerate(device_regs.UART_BITS))}


def _k88_device_header(mocha: str) -> str:
    """The package the generator emits from the fixture's owners, stamped at `mocha`."""
    with sandbox_tree({**_K88_OWNERS, **_K88_UART_OWNERS}) as root:
        return device_regs.emit(root, mocha)


def _k88_device_register_stamp_is_held_whole_and_fail_closed() -> None:
    mocha = "d" * 40
    header = _k88_device_header(mocha)
    files = {**_K88_OWNERS, device_regs.ARTIFACT: header}
    links = {device_regs.UPSTREAM: mocha}
    ensure(not _k88_device_regs(files, links),
           "an indexed header recording its gitlink's commit passes")
    cases: tuple[tuple[dict[str, str], dict[str, str], str | None, str], ...] = (
        # the gitlink moved and the header, still what the index holds, was not
        # regenerated: the whole id is held, not the abbreviation a finding quotes
        (files, {device_regs.UPSTREAM: mocha[:39] + "e"}, None,
         "carries upstream/mocha at dddd"),
        # a hand edit of a UART value, which only the guest decides against its owner,
        # leaves the stamp and the rendering agreeing and the bytes off the index
        (files, links, header.replace("UART_WDATA = 64'h1c", "UART_WDATA = 64'h2c"),
         "differs from its indexed emission"),
        ({**files, device_regs.ARTIFACT: header.replace(device_regs.STAMP, "// ")}, links,
         None, "records no readable owner revision"),
        (_K88_OWNERS, links, None, "the git index does not carry it"),
        (files, {}, None, "carries no gitlink"))
    for changed, gitlinks, edit, needle in cases:
        found = _k88_device_regs(changed, gitlinks, edit)
        ensure(len(found) == 1 and needle in found[0],
               f"each broken reading is one finding naming it: {found!r}")


def _k88_device_register_is_decided_on_the_host_but_its_uart_values() -> None:
    mocha = "d" * 40
    header = _k88_device_header(mocha)
    files = {**_K88_OWNERS, device_regs.ARTIFACT: header}
    links = {device_regs.UPSTREAM: mocha}
    moved = "is not what `run.py rtl device-regs` renders"
    status = "  localparam logic [63:0] UART_STATUS = 64'h14;"
    ack = "  localparam logic [63:0] BLK_ACK = 64'h38;"

    def package(text: str) -> dict[str, str]:
        return {**files, device_regs.ARTIFACT: text}

    cases: tuple[tuple[dict[str, str], str], ...] = (
        # a block-contract offset moved and the package, still what the index holds,
        # was not regenerated: no Mocha checkout is needed to see it
        ({**files, device_regs.BLOCK: _K88_BLOCK.replace("`0x38` | `ACK`",
                                                         "`0x40` | `ACK`")}, moved),
        ({**files, device_regs.BLOCK_MODEL: _K88_MODEL.replace("= 4096", "= 2048")}, moved),
        # a constant edited in the tracked package itself agrees with its index
        (package(header.replace("BLK_ACK = 64'h38", "BLK_ACK = 64'h40")), moved),
        (package("\n".join(line for line in header.split("\n") if "BLK_DATA" not in line)),
         moved),
        # bytes no BLK_ line carries: a duplicate inside a block comment, a declaration
        # the generator does not write, a changed comment, the UART lines reordered
        (package(header.replace(ack, f"{ack}\n  /* localparam logic [63:0] BLK_ACK = "
                                     "64'h40; */")), moved),
        (package(header.replace("endpackage", "  localparam int unsigned EXTRA = 1;\n"
                                              "endpackage")), moved),
        (package(header.replace("// Generated by vos.device_regs", "// Written by hand")),
         moved),
        (package(header.replace(status + "\n", "").replace(
            "  localparam logic [63:0] UART_WDATA", f"{status}\n"
                                                    "  localparam logic [63:0] UART_WDATA")),
         moved),
        # a UART declaration outside the generator's form cannot be rendered around
        (package(header.replace(status, f"{status}\n/*\n{status}\n*/")),
         "UART constants are not the ones"),
        (package(header.replace(status, status.replace("64'h14", "64'h014"))),
         "UART constants are not the ones"),
        # an owner the block half reads is gone or ambiguous: refused, never passed
        ({device_regs.ARTIFACT: header, device_regs.BLOCK_MODEL: _K88_MODEL},
         "block constants cannot be derived"),
        ({**files, device_regs.BLOCK: _K88_BLOCK + _K88_BLOCK},
         "block constants cannot be derived"))
    for changed, needle in cases:
        found = _k88_device_regs(changed, links)
        ensure(len(found) == 1 and needle in found[0],
               f"each defect outside the UART values is one finding naming it: {found!r}")
    # a hand edit outside the UART values is off the index and off the generator both
    found = _k88_device_regs(files, links, header.replace("package vos_device_regs_pkg;",
                                                          "package q;"))
    ensure(len(found) == 2 and "differs from its indexed emission" in found[0]
           and moved in found[1],
           f"an unstaged edit is reported against the index and the generator: {found!r}")


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
        Case("k119-each-rule-in-one-class-passes", _k119_each_rule_in_one_class_passes),
        Case("k119-unnamed-and-doubly-named-rules-are-findings",
             _k119_unnamed_and_doubly_named_rules_are_findings),
        Case("k119-ids-a-class-names-must-be-active-rules",
             _k119_ids_a_class_names_must_be_active_rules),
        Case("k119-ranges-expand-over-active-rows", _k119_ranges_expand_over_active_rows),
        Case("k119-unreadable-class-sentences-fail-closed",
             _k119_unreadable_class_sentences_fail_closed),
        Case("k119-every-class-lead-is-read", _k119_every_class_lead_is_read),
        Case("k97-reviewed-pin-is-required-without-prose-copies",
             _k97_reviewed_pin_is_required_without_prose_copies),
        Case("k115-agreement-and-sub-actions-pass", _k115_agreement_and_sub_actions_pass),
        Case("k115-moved-or-movable-references-fail", _k115_moved_or_movable_references_fail),
        Case("k115-moved-reference-is-quoted-apart-from-its-row",
             _k115_moved_reference_is_quoted_apart_from_its_row),
        Case("k115-membership-is-held-both-ways", _k115_membership_is_held_both_ways),
        Case("k115-licence-link-names-the-reviewed-commit",
             _k115_licence_link_names_the_reviewed_commit),
        Case("k115-leaves-the-analyzer-rows-to-k118", _k115_leaves_the_analyzer_rows_to_k118),
        Case("k115-unreadable-readings-fail-closed", _k115_unreadable_readings_fail_closed),
        Case("k115-every-uses-key-is-read-or-reported", _k115_every_uses_key_is_read_or_reported),
        Case("k115-census-counts-the-read-key-once", _k115_census_counts_the_read_key_once),
        Case("k118-agreement-passes", _k118_agreement_passes),
        Case("k118-drift-each-way-is-a-finding", _k118_drift_each_way_is_a_finding),
        Case("k118-unreadable-owners-fail-closed", _k118_unreadable_owners_fail_closed),
        Case("k118-unreadable-record-fails-closed", _k118_unreadable_record_fails_closed),
        Case("k118-every-row-is-held-or-declared", _k118_every_row_is_held_or_declared),
        Case("k118-census-reads-every-numeral", _k118_census_reads_every_numeral),
        Case("k118-each-tag-is-read-or-reported", _k118_each_tag_is_read_or_reported),
        Case("k118-declarations-are-held", _k118_declarations_are_held),
        Case("k118-every-owner-kind-detects-drift", _k118_every_owner_kind_detects_drift),
        Case("k118-a-row-named-by-its-release-stays-one-row",
             _k118_a_row_named_by_its_release_stays_one_row),
        Case("k118-hook-revisions-are-held", _k118_hook_revisions_are_held),
        Case("k118-hook-census-reads-every-entry", _k118_hook_census_reads_every_entry),
        Case("k118-hook-rev-is-read-at-its-entry-column",
             _k118_hook_rev_is_read_at_its_entry_column),
        Case("k118-shipped-readings-are-declared", _k118_shipped_readings_are_declared),
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
        Case("k88-device-register-is-decided-on-the-host-but-its-uart-values",
             _k88_device_register_is_decided_on_the_host_but_its_uart_values),
        Case("k88-foreign-library-is-a-finding", _k88_foreign_library_is_a_finding),
        Case("k84-retired-holders-are-historical-only", _k84_retired_holders_are_historical_only),
        Case("k84-retirement-needs-an-unfenced-registry-row",
             _k84_retirement_needs_an_unfenced_registry_row),
    ]
