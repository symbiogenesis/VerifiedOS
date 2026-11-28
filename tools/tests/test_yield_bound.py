# SPDX-License-Identifier: Apache-2.0
"""Q34d yield-point placement, strip-mining, sink lowering, cost-triple, and TAL-014 tests."""

import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from tests.harness import Case, ensure
from vos import yield_bound as yb

INDEPENDENT_CASES = True


def _refused(call: Callable[[], object], fragment: str) -> None:
    try:
        call()
    except yb.YieldBoundError as exc:
        ensure(fragment in str(exc), f"unexpected refusal {exc!r} (expected {fragment!r})")
    else:
        raise AssertionError(f"accepted without {fragment!r}")


def _unpolled_loop_cfg() -> yb.Cfg:
    return yb.Cfg(
        name="loop_fn",
        blocks=(
            yb.BasicBlock("entry", cost=2, is_entry=True),
            yb.BasicBlock("header", cost=1),
            yb.BasicBlock("body", cost=2),
            yb.BasicBlock("exit", cost=2, is_exit=True),
        ),
        edges=(
            yb.CfgEdge("entry", "header"),
            yb.CfgEdge("header", "body"),
            yb.CfgEdge("body", "header", is_back_edge=True),
            yb.CfgEdge("header", "exit"),
        ),
    )


def back_edge_poll_placement_and_refusal() -> None:
    unpolled = _unpolled_loop_cfg()
    errors = yb.verify_polls(unpolled)
    ensure(
        any("back-edge body->header" in err for err in errors),
        f"expected unpolled back-edge error, got {errors}",
    )
    _refused(lambda: yb.analyze_cfg_reactions(unpolled), "unpolled poll-free cycle")
    polled = yb.place_polls(unpolled)
    ensure(not yb.verify_polls(polled), "placed poll did not satisfy verify_polls")
    triple, reactions, fn_errors = yb.verify_function(polled, yield_bound=3)
    ensure(not fn_errors, f"expected clean loop verification, got {fn_errors}")
    ensure(triple.has_internal_poll and triple.entry_to_first_poll == 2, f"unexpected triple {triple}")
    ensure(max(r.cost for r in reactions) == 3, "unexpected max loop reaction cost")


def recursive_entry_poll_placement_and_refusal() -> None:
    rec_unpolled = yb.Cfg(
        name="rec_fn",
        blocks=(
            yb.BasicBlock("entry", cost=1, is_entry=True, is_recursive_entry=True),
            yb.BasicBlock("body", cost=3),
            yb.BasicBlock("poll_mid", cost=1, is_poll=True),
            yb.BasicBlock("exit", cost=2, is_exit=True),
        ),
        edges=(
            yb.CfgEdge("entry", "body"),
            yb.CfgEdge("body", "poll_mid"),
            yb.CfgEdge("poll_mid", "exit"),
        ),
    )
    errors = yb.verify_polls(rec_unpolled)
    ensure(
        any("recursive-call entry entry" in err for err in errors),
        f"expected unpolled recursive-entry error, got {errors}",
    )
    rec_polled = yb.place_polls(rec_unpolled)
    ensure(not yb.verify_polls(rec_polled), "placed recursive poll failed")
    triple, _, fn_errors = yb.verify_function(rec_polled, yield_bound=6)
    ensure(not fn_errors, f"expected clean recursive verification, got {fn_errors}")
    ensure(
        triple == yb.FnCostTriple(0, 4, 3, True),
        f"unexpected recursive triple {triple}",
    )


def strip_mining_bound_and_overhead_report() -> None:
    polled = yb.place_polls(_unpolled_loop_cfg())
    spec = yb.LoopTransformSpec(
        header="header",
        body_blocks=("body",),
        back_edge_source="body",
        factor=2,
    )
    transformed, report = yb.strip_mine_loop(polled, spec, yield_bound=6, iterations=10)
    ensure(report.admitted and report.factor == 2, f"bad strip-mine report {report}")
    ensure(report.unmodified_reaction_cost == 3, "wrong unmodified reaction cost")
    ensure(report.strip_mined_reaction_cost == 5, "wrong strip-mined reaction cost")
    ensure(report.unmodified_polls == 10 and report.strip_mined_polls == 5, "wrong poll counts")
    ensure(
        report.strip_mined_poll_overhead < report.unmodified_poll_overhead
        and report.overhead_saved == 5,
        f"expected overhead reduction, got {report}",
    )
    _, _, fn_errors = yb.verify_function(transformed, yield_bound=5)
    ensure(not fn_errors, f"transformed loop failed verification: {fn_errors}")

    _refused(
        lambda: yb.strip_mine_loop(polled, replace(spec, factor=0), yield_bound=6),
        "positive integer",
    )
    _refused(
        lambda: yb.strip_mine_loop(polled, replace(spec, factor=3), yield_bound=6),
        "exceeds yield_bound",
    )


def sink_before_yield_acceptance_and_refusal() -> None:
    unyielding = yb.Cfg(
        name="sink_loop",
        blocks=(
            yb.BasicBlock("entry", cost=2, is_entry=True),
            yb.BasicBlock("header", cost=1, is_poll=True),
            yb.BasicBlock("body", cost=4),
            yb.BasicBlock("exit", cost=1, is_exit=True),
            yb.BasicBlock("sink", cost=2, is_sink=True),
        ),
        edges=(
            yb.CfgEdge("entry", "header"),
            yb.CfgEdge("header", "body"),
            yb.CfgEdge("body", "header", is_back_edge=True),
            yb.CfgEdge("header", "exit"),
            yb.CfgEdge("header", "sink", is_switch_requested=True),
            yb.CfgEdge("sink", "header", is_back_edge=True),
        ),
    )
    sink_errors = yb.verify_sinks(unyielding)
    ensure(
        any("tentative poll header" in err for err in sink_errors),
        f"expected tentative-poll sink refusal, got {sink_errors}",
    )
    lowered = yb.lower_sink_before_yield(unyielding, yield_block_cost=1)
    ensure(not yb.verify_sinks(lowered), f"lowered sink failed: {yb.verify_sinks(lowered)}")
    _, _, fn_errors = yb.verify_function(lowered, yield_bound=5)
    ensure(not fn_errors, f"lowered CFG failed verification: {fn_errors}")

    non_sink = replace(
        unyielding,
        blocks=tuple(
            replace(b, is_sink=False) if b.id == "sink" else b for b in unyielding.blocks
        ),
    )
    ensure(
        any("does not enter a marked sink" in err for err in yb.verify_sinks(non_sink)),
        "expected switch-requested unmarked sink refusal",
    )


def cross_call_triple_exact_boundaries() -> None:
    caller_cfg = yb.Cfg(
        name="caller",
        blocks=(
            yb.BasicBlock("entry", cost=1, is_entry=True),
            yb.BasicBlock("pre", cost=2),
            yb.BasicBlock("post", cost=1),
            yb.BasicBlock("exit", cost=1, is_exit=True),
        ),
        edges=(
            yb.CfgEdge("entry", "pre"),
            yb.CfgEdge("pre", "post"),
            yb.CfgEdge("post", "exit"),
        ),
    )
    leaf_cfg = yb.Cfg(
        name="leaf",
        blocks=(
            yb.BasicBlock("l_entry", cost=1, is_entry=True),
            yb.BasicBlock("l_exit", cost=1, is_exit=True),
        ),
        edges=(yb.CfgEdge("l_entry", "l_exit"),),
    )
    rec_cfg = yb.place_polls(
        yb.Cfg(
            name="rec",
            blocks=(
                yb.BasicBlock("r_entry", cost=1, is_entry=True, is_recursive_entry=True),
                yb.BasicBlock("r_body", cost=3),
                yb.BasicBlock("r_poll", cost=1, is_poll=True),
                yb.BasicBlock("r_exit", cost=2, is_exit=True),
            ),
            edges=(
                yb.CfgEdge("r_entry", "r_body"),
                yb.CfgEdge("r_body", "r_poll"),
                yb.CfgEdge("r_poll", "r_exit"),
            ),
        )
    )
    # Direct call: pre(3) + leaf_full(2) + post(2) = 7. Admitted at 7, refused at 6.
    direct_prog = (
        yb.ProgramFunction(
            "caller",
            caller_cfg,
            (yb.CallSite("caller", "pre", "post", "leaf", is_recursive=False),),
        ),
        yb.ProgramFunction("leaf", leaf_cfg),
    )
    verdict_7 = yb.admit_program(direct_prog, yield_bound=7, call_interval=4)
    ensure(verdict_7.max_reaction_cost == 7 and verdict_7.call_bound == 11, f"bad verdict {verdict_7}")
    _refused(
        lambda: yb.admit_program(direct_prog, yield_bound=6, call_interval=4),
        "pre + callee_full + post (7) > yield_bound (6)",
    )
    # Cross-check concrete inlined CFG agrees with compositional verdict.
    inlined_direct = yb.inline_call_cfg(caller_cfg, "pre", "post", leaf_cfg)
    _, _, inlined_errs = yb.verify_function(inlined_direct, yield_bound=7)
    ensure(not inlined_errs, f"inlined direct CFG failed at 7: {inlined_errs}")
    _, _, inlined_errs_6 = yb.verify_function(inlined_direct, yield_bound=6)
    ensure(bool(inlined_errs_6), "inlined direct CFG unexpectedly passed at 6")

    # Recursive polled callee: pre(3)+0=3, poll_to_poll=4, last_poll_to_exit(3)+post(2)=5 <= 5.
    rec_prog = (
        yb.ProgramFunction(
            "caller",
            caller_cfg,
            (yb.CallSite("caller", "pre", "post", "rec", is_recursive=True),),
        ),
        yb.ProgramFunction("rec", rec_cfg),
    )
    verdict_5 = yb.admit_program(rec_prog, yield_bound=5, call_interval=4)
    ensure(verdict_5.max_reaction_cost == 5, f"unexpected rec max cost {verdict_5}")
    # Over-bound last_poll_to_exit + caller_post = 6 > 5 refused.
    over_rec_cfg = replace(
        rec_cfg,
        blocks=tuple(
            replace(b, cost=3) if b.id == "r_exit" else b for b in rec_cfg.blocks
        ),
    )
    _refused(
        lambda: yb.admit_program(
            (rec_prog[0], yb.ProgramFunction("rec", over_rec_cfg)),
            yield_bound=5,
            call_interval=4,
        ),
        "last_poll_to_exit + post (6) > yield_bound (5)",
    )
    # Over-bound pre + entry_to_first_poll refused directly.
    pre_err = yb.check_call_site(4, yb.FnCostTriple(3, 4, 2, True), 1, yield_bound=6)
    ensure(
        any("pre + entry_to_first_poll (7)" in err for err in pre_err),
        f"expected pre + entry_to_first refusal, got {pre_err}",
    )


def counter_invocation_gaps_and_tal014_expressiveness() -> None:
    gaps, acc = yb.simulate_invocation_gaps([2, 1, 2, 2, 1, 2], call_interval=4, yield_bound=2)
    ensure(gaps == [5, 5] and acc == 0, f"unexpected counter gaps {gaps}, acc={acc}")
    _refused(
        lambda: yb.simulate_invocation_gaps([2, 1, 3], call_interval=4, yield_bound=2),
        "exceeds yield_bound",
    )

    asym = yb.FnCostTriple(1, 6, 1, True)
    res_scalar = yb.check_tal014_expressiveness(
        yb.CostFacetSchema.SCALAR_REACTION, asym, crosses_call=True
    )
    ensure(
        not res_scalar.expressible and res_scalar.version_bump_required,
        f"expected scalar refusal for asymmetric call-crossing triple, got {res_scalar}",
    )
    res_triple = yb.check_tal014_expressiveness(
        yb.CostFacetSchema.TRIPLE_REACTION, asym, crosses_call=True
    )
    ensure(
        res_triple.expressible and not res_triple.version_bump_required,
        f"expected triple expressible, got {res_triple}",
    )
    res_leaf = yb.check_tal014_expressiveness(
        yb.CostFacetSchema.SCALAR_REACTION,
        yb.FnCostTriple(2, 0, 2, False),
        crosses_call=True,
    )
    ensure(
        res_leaf.expressible and not res_leaf.version_bump_required,
        f"expected poll-free leaf expressible in scalar facet, got {res_leaf}",
    )


def yield_bound_proof_surface() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "proofs" / "YieldBound.v").read_text(encoding="utf-8")
    for token in (
        "Require Import PartitionContext CyclicExecutive MemoryPlan ElasticDomain.",
        "witness_StripMineSpec",
        "witness_LoopSpec",
        "witness_FnCostTriple",
        "witness_CallSiteCheck",
        "witness_FnSummary",
        "witness_CounterState",
        "place_polls_covers_back_edges",
        "place_polls_covers_recursive_entries",
        "strip_mine_cfg_admitted",
        "lower_sink_establishes_sinks_yield",
        "compositional_soundness",
        "inline_call_cfg_admits",
        "compositional_program_invocation_gaps_bounded",
        "tal014_scalar_facet_is_insufficient_for_call_crossing",
        "refute_unpolled_back_edge",
        "refute_unpolled_recursive_entry",
        "refute_overbound_intra_reaction",
        "refute_overbound_cross_call_last_poll_post",
        "refute_sink_returning_to_tentative_poll",
        "refute_misconfigured_strip_mine_factor",
    ):
        ensure(token in text, f"YieldBound.v missing expected declaration {token!r}")
    ensure(not re.search(r"\bAdmitted\b", text), "YieldBound.v contains Admitted")


def cases() -> list[Case]:
    return [
        Case(fn.__name__, fn)
        for fn in (
            back_edge_poll_placement_and_refusal,
            recursive_entry_poll_placement_and_refusal,
            strip_mining_bound_and_overhead_report,
            sink_before_yield_acceptance_and_refusal,
            cross_call_triple_exact_boundaries,
            counter_invocation_gaps_and_tal014_expressiveness,
            yield_bound_proof_surface,
        )
    ]
