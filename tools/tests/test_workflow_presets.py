# SPDX-License-Identifier: Apache-2.0
"""Q32c-i workflow preset catalog, reachable mode graph, economics, and proof tests."""

import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from tests.harness import Case, ensure
from vos import workflow_presets as wp

INDEPENDENT_CASES = True


def _refused(call: Callable[[], object], fragment: str) -> None:
    try:
        call()
    except wp.WorkflowPresetError as exc:
        ensure(fragment in str(exc), f"unexpected refusal {exc!r} (expected {fragment!r})")
    else:
        raise AssertionError(f"accepted without {fragment!r}")


def _sample_mode_graph() -> wp.ModeGraph:
    standing = wp.StandingServices()
    n0 = wp.SteadyNode(
        node_id="everyday_std",
        selection=wp.SelectionTriple(
            wp.PowerMode.BALANCED, wp.PresetRecipe.EVERYDAY, wp.FocusRung.STANDARD
        ),
        standing=standing,
        implicit_authority=False,
        floor_ok=True,
        ledger=wp.ByteLedger(48, 64, 0, 0, 8, store_checkpoint=32),
    )
    n1 = wp.SteadyNode(
        node_id="writing_std",
        selection=wp.SelectionTriple(
            wp.PowerMode.BALANCED, wp.PresetRecipe.WRITING, wp.FocusRung.STANDARD
        ),
        standing=standing,
        implicit_authority=False,
        floor_ok=True,
        ledger=wp.ByteLedger(48, 96, 0, 0, 8, store_checkpoint=48),
    )
    n2 = wp.SteadyNode(
        node_id="dev_perf_exp",
        selection=wp.SelectionTriple(
            wp.PowerMode.PERFORMANCE, wp.PresetRecipe.DEVELOPMENT, wp.FocusRung.EXPANDED
        ),
        standing=standing,
        implicit_authority=False,
        floor_ok=True,
        ledger=wp.ByteLedger(48, 128, 0, 0, 12, store_checkpoint=48),
    )
    e01 = wp.TransitionEdge(
        src_id="everyday_std",
        dst_id="writing_std",
        local_only=True,
        power_unchanged=True,
        root_attested=False,
        explicit_authority=True,
        standing=standing,
        ledger=wp.ByteLedger(
            48, 64, 16, 16, 8, store_checkpoint=32, store_scratch=16,
            reusable_proved=True, overlap_credit=32,
        ),
        old_last_gap=2,
        mid_gap=4,
        new_first_gap=2,
        continuing_deadline=8,
        work_cost=10,
        deadline=12,
        recovery_reserved=True,
        cert_valid=True,
    )
    e12 = wp.TransitionEdge(
        src_id="writing_std",
        dst_id="dev_perf_exp",
        local_only=False,
        power_unchanged=False,
        root_attested=True,
        explicit_authority=True,
        standing=standing,
        ledger=wp.ByteLedger(
            48, 96, 24, 16, 12, store_checkpoint=48, store_scratch=16,
            reusable_proved=True, overlap_credit=48,
        ),
        old_last_gap=2,
        mid_gap=4,
        new_first_gap=2,
        continuing_deadline=8,
        work_cost=12,
        deadline=14,
        recovery_reserved=True,
        cert_valid=True,
    )
    return wp.ModeGraph(
        required_standing=standing,
        nodes=(n0, n1, n2),
        edges=(e01, e12),
        ram_capacity=192,
        store_capacity=64,
    )


def default_catalog_covers_all_six_recipes() -> None:
    catalog = wp.default_preset_catalog()
    report = wp.validate_catalog(catalog)
    ensure(len(report.enabled_recipes) == 5, f"expected 5 enabled recipes, got {report}")
    ensure(
        wp.PresetRecipe.BROWSING in report.unavailable_recipes,
        "expected browsing to be explicitly unavailable under R-18-004",
    )
    ensure(report.peak_ram == 196, f"unexpected catalog peak_ram {report.peak_ram}")
    ensure(report.peak_store == 88, f"unexpected catalog peak_store {report.peak_store}")

    missing_one = catalog[:-1]
    _refused(lambda: wp.validate_catalog(missing_one), "missing required recipes")


def browser_deferral_and_development_distinction_enforced() -> None:
    by_kind = {r.recipe: r for r in wp.default_preset_catalog()}
    browsing = by_kind[wp.PresetRecipe.BROWSING]
    bad_browser = replace(
        browsing, enabled=True, unavailable_reason=None, port_available=True, browser_port_qualified=False
    )
    _refused(
        lambda: wp.validate_recipe(bad_browser),
        "browser recipe deferred under R-18-004",
    )
    qualified_browser = replace(
        bad_browser,
        browser_port_qualified=True,
        ledger=wp.ByteLedger(48, 128, 0, 0, 12),
    )
    ram, store = wp.validate_recipe(qualified_browser)
    ensure(ram == 188 and store == 0, f"unexpected qualified browser ledger {(ram, store)}")

    dev = by_kind[wp.PresetRecipe.DEVELOPMENT]
    _refused(
        lambda: wp.validate_recipe(replace(dev, borrows_composition_for_floor=True)),
        "cannot borrow composition-mode grants",
    )
    _refused(
        lambda: wp.validate_recipe(replace(dev, dev_exec_successor_only=False)),
        "successor generation (R-13-027a)",
    )
    comp_dev = replace(dev, dev_mode=wp.DevBuildMode.COMPOSITION)
    dev_ram, dev_store = wp.validate_recipe(comp_dev)
    ensure(dev_ram == 196 and dev_store == 48, f"unexpected dev ledger {(dev_ram, dev_store)}")


def standing_services_and_implicit_authority_refused() -> None:
    everyday = wp.default_preset_catalog()[0]
    _refused(
        lambda: wp.validate_recipe(replace(everyday, implicit_authority=True)),
        "cannot grant authority",
    )
    for svc_name in ("audio", "radio", "display", "storage", "revocation", "consent", "inference"):
        dropped = replace(everyday.standing, **{svc_name: False})
        _refused(
            lambda d=dropped: wp.validate_recipe(replace(everyday, standing=d)),
            f"dropped required standing services {svc_name}",
        )


def exact_byte_ledger_and_premature_overlap_refusal() -> None:
    premature = wp.ByteLedger(
        resident_permanent=48,
        live_or_frozen_private=128,
        checkpoint_workspace=32,
        quarantined=24,
        metadata=12,
        reusable_proved=False,
        overlap_credit=64,
    )
    _refused(lambda: premature.effective_ram("premature"), "claimed before Reusable")

    over_credit = replace(premature, reusable_proved=True, overlap_credit=129)
    _refused(lambda: over_credit.effective_ram("over"), "exceeds live/frozen private backing")

    valid = replace(premature, reusable_proved=True, overlap_credit=64)
    ensure(valid.raw_ram == 244, f"unexpected raw RAM {valid.raw_ram}")
    ensure(valid.effective_ram("valid") == 180, "expected single overlap credit after Reusable")


def reachable_mode_graph_and_cartesian_product_refusal() -> None:
    graph = _sample_mode_graph()
    report = wp.validate_mode_graph(graph)
    ensure(report.steady_peak_ram == 188, f"unexpected steady peak {report.steady_peak_ram}")
    ensure(report.transition_peak_ram == 148, f"unexpected transition peak {report.transition_peak_ram}")
    ensure(report.overall_peak_ram == 188, f"unexpected overall peak {report.overall_peak_ram}")
    ensure(report.overall_peak_store == 64, f"unexpected overall store {report.overall_peak_store}")

    # Direct edge exists from writing_std -> dev_perf_exp.
    edge = wp.check_transition_reachable(
        graph, graph.nodes[1].selection, graph.nodes[2].selection
    )
    ensure(edge.root_attested, "expected RoT-attested global mode edge")

    # Both everyday_std and dev_perf_exp are valid steady nodes (in Cartesian product),
    # yet no direct edge exists between them.
    _refused(
        lambda: wp.check_transition_reachable(
            graph, graph.nodes[0].selection, graph.nodes[2].selection
        ),
        "Cartesian product not assumed",
    )


def graph_refuses_unattested_global_and_endpoint_safe_overload() -> None:
    graph = _sample_mode_graph()
    unattested_global = replace(
        graph,
        edges=(graph.edges[0], replace(graph.edges[1], root_attested=False)),
    )
    _refused(
        lambda: wp.validate_mode_graph(unattested_global),
        "requires RoT-attested path",
    )

    uncertified_edge = replace(
        graph,
        edges=(replace(graph.edges[0], cert_valid=False), graph.edges[1]),
    )
    _refused(
        lambda: wp.validate_mode_graph(uncertified_edge),
        "missing valid transition certificate",
    )

    # Endpoint-safe nodes fit ram_capacity=155? Use nodes 0 (120) and 1 (152), edge without overlap = 152+...=160 > 155.
    endpoint_safe_overload = wp.ModeGraph(
        required_standing=graph.required_standing,
        nodes=(graph.nodes[0], graph.nodes[1]),
        edges=(
            replace(
                graph.edges[0],
                ledger=wp.ByteLedger(48, 96, 24, 16, 8, store_checkpoint=32, store_scratch=16),
            ),
        ),
        ram_capacity=160,
        store_capacity=64,
    )
    _refused(
        lambda: wp.validate_mode_graph(endpoint_safe_overload),
        "transition peak RAM 192 exceeds capacity 160",
    )


def strategy_comparison_identical_useful_state() -> None:
    frozen = wp.StrategyMeasurement(
        strategy=wp.ReclamationStrategy.FROZEN_RESIDENT,
        useful_state_bytes=64,
        steady_ledger=wp.ByteLedger(48, 128, 0, 0, 8),
        transition_ledger=wp.ByteLedger(48, 128, 0, 0, 8),
        endurance_writes_per_switch=0,
        resume_latency=1,
    )
    hibernation = wp.StrategyMeasurement(
        strategy=wp.ReclamationStrategy.SEMANTIC_HIBERNATION,
        useful_state_bytes=64,
        steady_ledger=wp.ByteLedger(48, 64, 0, 0, 12, store_checkpoint=32),
        transition_ledger=wp.ByteLedger(
            48, 64, 16, 16, 12, store_checkpoint=32, store_scratch=16,
            reusable_proved=True, overlap_credit=32,
        ),
        endurance_writes_per_switch=1,
        resume_latency=6,
    )
    fixed_pool = wp.StrategyMeasurement(
        strategy=wp.ReclamationStrategy.FIXED_POOL_REUSE,
        useful_state_bytes=64,
        steady_ledger=wp.ByteLedger(48, 96, 0, 0, 10),
        transition_ledger=wp.ByteLedger(
            48, 96, 0, 24, 10, reusable_proved=True, overlap_credit=32
        ),
        endurance_writes_per_switch=0,
        resume_latency=2,
    )
    rep = wp.compare_strategies((frozen, hibernation, fixed_pool))
    ensure(rep.useful_state_bytes == 64, "wrong useful_state_bytes")
    ensure(rep.steady_saving_hibernation_vs_frozen == 60, f"unexpected saving {rep}")
    ensure(
        rep.endurance_by_strategy[wp.ReclamationStrategy.SEMANTIC_HIBERNATION] == 1
        and rep.endurance_by_strategy[wp.ReclamationStrategy.FIXED_POOL_REUSE] == 0,
        f"unexpected endurance map {rep.endurance_by_strategy}",
    )

    mismatched = replace(fixed_pool, useful_state_bytes=96)
    _refused(
        lambda: wp.compare_strategies((frozen, hibernation, mismatched)),
        "identical useful_state_bytes",
    )


def toggle_burst_dwell_quarantine_endurance_bounds() -> None:
    policy = wp.TogglePolicy(
        min_dwell=2,
        quarantine_cap=48,
        endurance_limit=4,
        cp_store_cap=96,
        fg_service_floor=2,
        fg_slot_budget=4,
        sweep_rate=16,
    )
    ok_trace = (
        wp.ToggleEvent("switch", fg_work=3, retire_bytes=24, cp_bytes=16, writes_needed=1),
        wp.ToggleEvent("tick", fg_work=2),
        wp.ToggleEvent("tick", fg_work=2),
        wp.ToggleEvent("switch", fg_work=3, retire_bytes=24, cp_bytes=16, writes_needed=1),
    )
    ok_rep = wp.simulate_toggle_burst(policy, ok_trace)
    ensure(
        ok_rep.final_state.switches_completed == 2
        and ok_rep.final_state.refused_count == 0
        and ok_rep.final_state.quarantine_high_water == 24
        and ok_rep.final_state.endurance_writes == 2,
        f"unexpected ok toggle report {ok_rep}",
    )

    # Burst hitting dwell, quarantine overflow, and endurance exhaustion.
    burst_trace = (
        wp.ToggleEvent("switch", fg_work=3, retire_bytes=32, cp_bytes=16, writes_needed=2),
        wp.ToggleEvent("switch", fg_work=3, retire_bytes=32, cp_bytes=16, writes_needed=2),
        wp.ToggleEvent("tick", fg_work=2),
        wp.ToggleEvent("tick", fg_work=2),
        wp.ToggleEvent("switch", fg_work=3, retire_bytes=32, cp_bytes=16, writes_needed=2),
        wp.ToggleEvent("tick", fg_work=2),
        wp.ToggleEvent("tick", fg_work=2),
        wp.ToggleEvent("switch", fg_work=3, retire_bytes=32, cp_bytes=16, writes_needed=2),
    )
    burst_rep = wp.simulate_toggle_burst(policy, burst_trace)
    ensure(
        burst_rep.final_state.refused_count == 2
        and burst_rep.final_state.quarantine_high_water <= policy.quarantine_cap
        and burst_rep.final_state.endurance_writes <= policy.endurance_limit,
        f"burst breached bounds: {burst_rep}",
    )
    _refused(
        lambda: wp.simulate_toggle_burst(policy, burst_trace, strict=True),
        "min_dwell",
    )


def workflow_presets_proof_surface_and_audit() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "proofs" / "WorkflowPresets.v").read_text(encoding="utf-8")
    lines = text.splitlines()
    ensure(
        lines[0] == "(* SPDX-License-Identifier: Apache-2.0 *)",
        f"unexpected first line: {lines[0]!r}",
    )
    ensure("Require ProofSupport." in text, "missing Require ProofSupport.")
    ensure("From Stdlib" not in text, "WorkflowPresets.v must use prelude + ProofSupport only")
    ensure("(*| BEGIN derived: cited entries |*)" in text, "missing BEGIN derived header")
    ensure("(*| END derived |*)" in text, "missing END derived header")

    for forbidden in (
        "CoInductive",
        "CoFixpoint",
        "CoFix",
        "cofix",
        "Axiom",
        "Parameter",
        "Admitted",
        "Section",
        "Module Type",
    ):
        ensure(
            not re.search(rf"\b{re.escape(forbidden)}\b", text),
            f"WorkflowPresets.v contains forbidden token {forbidden!r}",
        )

    records = re.findall(r"(?m)^Record\s+(\w+)\b", text)
    ensure(len(records) >= 8, f"expected >= 8 Records, found {records}")
    for rec in records:
        ensure(
            f"Definition witness_{rec} : {rec}" in text,
            f"missing closed witness_{rec} for Record {rec}",
        )

    for decl in (
        "default_catalog_admitted",
        "enabled_browser_requires_qualified_port",
        "enabled_development_requires_successor_exec_and_no_floor_borrow",
        "admitted_graph_peak_fits_capacity",
        "admitted_graph_preserves_standing_services",
        "reachable_node_and_edge_within_graph_peak",
        "strategy_comparison_valid_identical_state",
        "toggle_step_preserves_bounds",
        "toggle_run_preserves_bounds",
        "refute_cartesian_edge_without_certificate",
        "refute_standing_service_drop",
        "refute_premature_overlap_credit",
        "refute_toggle_burst_overflow",
        "refute_deferred_browser_unqualified",
        "refute_dev_composition_borrowing_floor",
        "refute_endpoint_safe_transition_overload",
    ):
        ensure(decl in text, f"WorkflowPresets.v missing declaration {decl!r}")


def cases() -> list[Case]:
    return [
        Case(fn.__name__, fn)
        for fn in (
            default_catalog_covers_all_six_recipes,
            browser_deferral_and_development_distinction_enforced,
            standing_services_and_implicit_authority_refused,
            exact_byte_ledger_and_premature_overlap_refusal,
            reachable_mode_graph_and_cartesian_product_refusal,
            graph_refuses_unattested_global_and_endpoint_safe_overload,
            strategy_comparison_identical_useful_state,
            toggle_burst_dwell_quarantine_endurance_bounds,
            workflow_presets_proof_surface_and_audit,
        )
    ]
