# SPDX-License-Identifier: Apache-2.0
"""Unknown work cannot enter a commitment; readiness never invents acceptance."""

import copy
import json

from tests.harness import Case, ensure, sandbox_tree
from tests.test_estimate_cells import REGISTER, _context, _summary_values
from vos import workorder
from vos.checks import estimates

LEAVES = {"A · Accepted": True, "B · Consumer": False,
          "C · Producer": False, "D · Later prerequisite": False}


def _owner() -> dict[str, object]:
    return {
        "version": 1,
        "buckets": {"m8a": ["B", "C"], "m8b": [], "committed": ["D"],
                    "conditional": [], "option": []},
        "dispatch": [
            {"item": "B", "start": ["A"], "artifacts": ["proofs/input.v"], "unmet": [],
             "join": [{"item": "C", "output": "actual target service"}]},
            {"item": "C", "start": ["D"], "artifacts": [], "unmet": ["review the format"],
             "join": []}],
        "unpriced": ["docs/missing.md"],
    }


def _files(owner: object) -> dict[str, str]:
    return {"docs/requirements-register.md": REGISTER,
            workorder.OWNER: json.dumps(owner), "proofs/input.v": "(* input *)\n",
            "docs/missing.md": "# Unpriced obligations\n"}


def _readiness_distinguishes_authoring_and_join() -> None:
    with sandbox_tree(_files(_owner())) as root:
        order = workorder.read(root, LEAVES)
        ensure(not order.findings, str(order.findings))
        ensure(order.rows == [
            ("B", "available for authoring", "C: actual target service"),
            ("C", "blocked: D; review the format", "n/a")],
            "a reviewed input opens authoring but does not complete the real join")
        done = LEAVES | {"C · Producer": True, "D · Later prerequisite": True}
        order = workorder.read(root, done)
        ensure(order.rows == [("B", "available for authoring", "n/a")],
               "completed producers remove open joins without manufacturing consumer acceptance")
        (root / "proofs/input.v").unlink()
        ensure("blocked: proofs/input.v" in workorder.read(root, LEAVES).table(),
               "missing authored input must block authoring")


def _membership_fails_closed() -> None:
    with sandbox_tree(_files(_owner())) as root:
        unknown = workorder.read(root, LEAVES | {"New · Newly priced": False})
        ensure(any("unclassified" in f for f in unknown.findings),
               "a new priced leaf cannot enter M8a by exclusion-list omission")
        missing = workorder.read(root, {k: v for k, v in LEAVES.items() if not k.startswith("D")})
        ensure(bool(missing.findings), "a deleted owner must be a finding")
        ambiguous = workorder.read(root, LEAVES | {"B · Another leaf": False})
        ensure(any("found 2" in f for f in ambiguous.findings),
               "ambiguous heads require full leaf labels, never a parent expansion")
    owner = _owner()
    owner["buckets"] = {"m8a": ["B", "C"], "m8b": ["B"], "committed": ["D"],
                        "conditional": [], "option": []}
    with sandbox_tree(_files(owner)) as root:
        ensure(any("multiple buckets" in f for f in workorder.read(root, LEAVES).findings),
               "one leaf cannot be charged to two dispositions")


def _malformed_owner_never_supplies_a_verdict() -> None:
    owner = _owner()
    bad = [dict(owner, version=True), dict(owner, unpriced=[]), dict(owner, dispatch=[])]
    duplicate = json.dumps(owner).replace('"version": 1', '"version": 1, "version": 1')
    for candidate in bad:
        with sandbox_tree(_files(candidate)) as root:
            ensure(bool(workorder.read(root, LEAVES).findings), "malformed owner must fail")
    files = _files(owner) | {workorder.OWNER: duplicate}
    with sandbox_tree(files) as root:
        ensure(any("duplicate JSON" in f for f in workorder.read(root, LEAVES).findings),
               "duplicate JSON keys cannot silently replace the chosen disposition")


def _view_repair_is_bounded_and_reaches_fixpoint() -> None:
    files = _files(_owner())
    table = workorder.HEADER + "\n" + workorder.RULE
    plan = "# Plan\n\n" + workorder.START + "\n" + table + "\n" + workorder.END + "\n"
    files[estimates.PLAN] = plan
    with sandbox_tree(files) as root:
        order = workorder.read(root, LEAVES)
        ctx = _context(root, fix=True)
        result = estimates._work_order_results(ctx, order)
        ensure(not result.findings and bool(result.fixed), "valid view regenerates from owners")
        result = estimates._work_order_results(ctx, order)
        ensure(not result.findings and not result.fixed, "repair reaches its fixpoint")
        good = ctx.fixed[estimates.PLAN]
        ctx.fixed[estimates.PLAN] = good.replace(workorder.RULE, workorder.RULE + "\nAuthored text")
        result = estimates._work_order_results(ctx, order)
        ensure(bool(result.findings) and "Authored text" in ctx.fixed[estimates.PLAN],
               "repair must never erase material outside the generated table schema")
        ctx.fixed[estimates.PLAN] = good
        invalid = copy.deepcopy(order)
        invalid.findings.append("invalid owner")
        invalid.rows.clear()
        estimates._work_order_results(ctx, invalid)
        ensure(ctx.fixed[estimates.PLAN] == good, "invalid owner cannot rewrite the last valid view")


def _summary_migration_requires_all_new_owners() -> None:
    values = _summary_values()
    legacy = {k: "0–0" if "range" in k else "0" for k in estimates.LEGACY_SUMMARY_FIELDS}
    table = "\n".join([estimates.SUMMARY_HEADER, estimates.SUMMARY_RULE,
                       *(f"| {k} | {v} |" for k, v in legacy.items())])
    plan = estimates.SUMMARY_START + "\n" + table + "\n" + estimates.SUMMARY_END + "\n"
    with sandbox_tree({estimates.PLAN: plan, "docs/requirements-register.md": REGISTER}) as root:
        ctx = _context(root, fix=True)
        result = estimates._summary_results(ctx, {"Remaining h": "99"})
        ensure(bool(result.findings) and not ctx.fixed, "partial owners cannot migrate a commitment")
        result = estimates._summary_results(ctx, values)
        ensure(not result.findings and bool(result.fixed), "valid owners migrate the summary once")
        ensure("critical chain" not in ctx.fixed[estimates.PLAN], "obsolete chain fields retire")
        result = estimates._summary_results(ctx, values)
        ensure(not result.findings and not result.fixed, "migration reaches its fixpoint")


def cases() -> list[Case]:
    return [
        Case("readiness-distinguishes-authoring-and-join", _readiness_distinguishes_authoring_and_join),
        Case("membership-fails-closed", _membership_fails_closed),
        Case("malformed-owner-never-supplies-a-verdict", _malformed_owner_never_supplies_a_verdict),
        Case("view-repair-is-bounded-and-reaches-fixpoint", _view_repair_is_bounded_and_reaches_fixpoint),
        Case("summary-migration-requires-all-new-owners", _summary_migration_requires_all_new_owners),
    ]
