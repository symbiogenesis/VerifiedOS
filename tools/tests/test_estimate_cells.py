# SPDX-License-Identifier: Apache-2.0
"""Estimate cells stay local; calibration results remain owned and fail closed."""

from pathlib import Path

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus
from vos.checks import Context, estimates
from vos.register import read_artifacts, read_register
from vos.report import Reporter

PLAN = estimates.PLAN
REGISTER = "# Register\n\n## §1\n\n**R-01-001** MUST x.\n· Trace: t\n"


def _context(root: Path, fix: bool = False) -> Context:
    docs = corpus.load(root)
    return Context(root=root, corpus=docs, reg=read_register(docs),
                   art=read_artifacts(docs), rep=Reporter(), fix=fix)


def _files(plan: str) -> dict[str, str]:
    return {"docs/requirements-register.md": REGISTER, PLAN: plan}


def _parse_cells_without_shares() -> None:
    plan = ("* [ ] **A** · 1,200 h, range 800–1,600 · X · Parallel with B\n"
            "* [x] **B** · 3 h actual · agent-parallel\n"
            "* [x] **C** · 6 h retained estimate, actual n/a · agent-parallel\n"
            "**S subtotal:** 1,209 h · 100% · 9 h complete · open range 800–1,600 h.\n")
    items, _, malformed = estimates._parse(plan)
    ensure(not malformed, f"canonical cells must parse: {malformed!r}")
    ensure([(i.hours, i.done, i.measured_actual, i.cls, i.tail) for i in items] == [
        (1200, False, False, "X", " · X · Parallel with B"),
        (3, True, True, None, " · agent-parallel"),
        (6, True, False, None, " · agent-parallel")],
        "hours, classes, measurement status and authored annotations must survive")


def _legacy_cells_migrate_once() -> None:
    plan = ("* [ ] **A** · 99 h, range 2–4 · 123.45% · X · Parallel with B\n"
            "* [x] **B** · 3 h actual · 20.0% · agent-parallel\n"
            "* [x] **C** · 6 h retained estimate, actual n/a · 40.0% · agent-parallel\n"
            "**S subtotal:** 12 h · 100% · 9 h complete · open range 2–4 h.\n")
    expected = ("* [ ] **A** · 3 h, range 2–4 · X · Parallel with B\n"
                "* [x] **B** · 3 h actual · agent-parallel\n"
                "* [x] **C** · 6 h retained estimate, actual n/a · agent-parallel\n"
                "**S subtotal:** 12 h · 100% · 9 h complete · open range 2–4 h.\n")
    with sandbox_tree(_files(plan)) as root:
        ctx = _context(root, fix=True)
        estimates.run(ctx)
        ensure(ctx.fixed.get(PLAN) == expected,
               f"migration must remove only shares and repair the midpoint: {ctx.fixed!r}")
    with sandbox_tree(_files(expected)) as root:
        ctx = _context(root, fix=True)
        estimates.run(ctx)
        ensure(not ctx.fixed, "a migrated cell must reach its fixpoint in one repair")


def _grand_total_change_keeps_other_cells() -> None:
    # Reprice A after this section's subtotal was generated. B and C must retain
    # their exact text even though their shares of the grand total have changed.
    unchanged = ("* [x] **B** · 3 h actual · agent-parallel\n"
                 "* [ ] **C** · 6 h, range 4–8 · X · Parallel with A\n")
    plan = ("* [ ] **A** · 12 h, range 8–16 · I\n" + unchanged
            + "**S subtotal:** 12 h · 100% · 3 h complete · open range 6–12 h.\n")
    with sandbox_tree(_files(plan)) as root:
        ctx = _context(root, fix=True)
        estimates.run(ctx)
        repaired = ctx.fixed[PLAN]
        ensure(unchanged in repaired, "a new grand total must not touch another item cell")
        ensure("21 h · 100% · 3 h complete · open range 12–24 h." in repaired,
               "aggregate scope must still follow the changed estimate")
        ensure(not any(line.startswith(("fixed: A:", "fixed: B:", "fixed: C:"))
                       for line in ctx.rep.out), "only the aggregate needs repair")


def _malformed_cells_report_instead_of_crashing() -> None:
    for cell in ("· 1..5 h actual", "· 1,2 h actual", "· 3 h actual · 20%%",
                 "· 3 h, range 2–4", "· 3 h, range 2–4 · X · 20%",
                 "· 3 h, range 2–4 · 20% · X · 20%", "· 3 h actual typo"):
        plan = f"* [ ] **A** {cell}\n**S subtotal:** 3 h · 100%.\n"
        _, _, malformed = estimates._parse(plan)
        ensure(bool(malformed), f"malformed cell must be a finding: {cell}")
    for checkbox, cell in ((" ", "· 3 h actual"),
                           (" ", "· 3 h retained estimate, actual n/a"),
                           ("x", "· 3 h, range 2–4 · X")):
        _, _, malformed = estimates._parse(
            f"* [{checkbox}] **A** {cell}\n**S subtotal:** 3 h · 100%.\n")
        ensure(bool(malformed), "completion status must agree with the cell's measurement status")


def _fits() -> dict[str, estimates.Fit]:
    return {
        "attended": {"I": [("a", 10, 8)], "X-read": [("b", 10, 5)],
                     "X-authored": [("c", 10, 20)]},
        "agent-parallel": {"I": [("p", 10, 2)], "X-read": [("q", 10, 3)],
                           "X-authored": [("r", 10, 4)]},
    }


def _marked(table: str) -> str:
    return ("# Plan\n\nInterpretation is authored and can be reworded.\n\n"
            + estimates.CALIBRATION_START + "\n" + table + "\n"
            + estimates.CALIBRATION_END + "\n\nHistorical evidence stays here.\n")


def _calibration_repairs_once_without_pooling() -> None:
    fits = _fits()
    table = estimates._calibration_table(fits)
    ensure("| attended | All | 3 | 30 | 33 | 1.10 |" in table,
           "attended totals must fit only attended evidence")
    ensure("| agent-parallel | All | 3 | 30 | 9 | 0.30 |" in table,
           "agent-parallel totals must fit only that clock")
    plan = _marked(table.replace("| 33 | 1.10 |", "| 999 | 999 |"))
    with sandbox_tree(_files(plan)) as root:
        ctx = _context(root)
        result = estimates._calibration_results(ctx, fits)
        ensure(bool(result.findings) and not ctx.fixed, "a stale table must be reported")
        ctx.fix = True
        result = estimates._calibration_results(ctx, fits)
        ensure(not result.findings and ctx.fixed.get(PLAN) == _marked(table),
               "repair must regenerate only the owned table")
        result = estimates._calibration_results(ctx, fits)
        ensure(not result.findings and not result.fixed, "repair must reach its fixpoint")


def _calibration_table_fails_closed() -> None:
    table = estimates._calibration_table(_fits())
    plan = _marked(table)
    row = "| attended | I | 1 | 10 | 8 | 0.80 |"
    broken = [
        plan.replace(estimates.CALIBRATION_START, ""),
        plan.replace(estimates.CALIBRATION_END, ""),
        plan + estimates.CALIBRATION_START + "\n",
        plan + estimates.CALIBRATION_END + "\n",
        estimates.CALIBRATION_END + "\n" + estimates.CALIBRATION_START + "\n",
        plan.replace(estimates.CALIBRATION_HEADER, "| Different header |"),
        plan.replace(row + "\n", ""),
        plan.replace(row, row + "\n" + row),
        plan.replace(row, "| attended | I | 1 | 10 | 8 |"),
        plan.replace(row, "| attended | I | 1 | 10 | 8 | unreadable |"),
        plan.replace(row, "| attended | Missing pool | 1 | 10 | 8 | 0.80 |"),
        plan.replace(row, row + "\nAn authored note inside the table."),
    ]
    for malformed in broken:
        with sandbox_tree(_files(malformed)) as root:
            ctx = _context(root, fix=True)
            result = estimates._calibration_results(ctx, _fits())
            ensure(bool(result.findings) and not result.fixed and not ctx.fixed,
                   f"a malformed table must fail without replacement: {malformed!r}")


def _calibration_has_no_count_width_cliff() -> None:
    fits = _fits()
    fits["attended"]["I"] = [(f"a{i}", 10, 8) for i in range(123)]
    table = estimates._calibration_table(fits)
    ensure("| attended | I | 123 | 1,230 | 984 | 0.80 |" in table,
           "counts and hours must survive decimal and comma width changes")
    with sandbox_tree(_files(_marked(table))) as root:
        result = estimates._calibration_results(_context(root), fits)
        ensure(not result.findings, f"a grown pool must still be readable: {result.findings!r}")


def cases() -> list[Case]:
    return [
        Case("parse-cells-without-shares", _parse_cells_without_shares),
        Case("legacy-cells-migrate-once", _legacy_cells_migrate_once),
        Case("grand-total-change-keeps-other-cells", _grand_total_change_keeps_other_cells),
        Case("malformed-cells-report-instead-of-crashing", _malformed_cells_report_instead_of_crashing),
        Case("calibration-repairs-once-without-pooling", _calibration_repairs_once_without_pooling),
        Case("calibration-table-fails-closed", _calibration_table_fails_closed),
        Case("calibration-has-no-count-width-cliff", _calibration_has_no_count_width_cliff),
    ]
