# SPDX-License-Identifier: Apache-2.0
"""Q32c-i workflow preset catalog validator, byte ledger, and economics comparator.

Executable catalog validator, reachable-graph steady+transition peak byte ledger,
reclamation-economics comparator (`FrozenResident` vs `SemanticHibernation` vs
`FixedPoolReuse`), and toggle-burst simulator matching
[WorkflowPresets.v](../../proofs/WorkflowPresets.v) (`R-08-046`, `R-11-018`,
`R-11-018a`, `R-13-027a`, `R-18-004`, `R-18-004a`).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum


class WorkflowPresetError(ValueError):
    """A preset recipe, reachable mode graph, ledger, comparison, or toggle burst failed."""


class PresetRecipe(Enum):
    """The six preconfigured product workflow preset recipes (`R-11-018a`)."""

    EVERYDAY = "everyday"
    WRITING = "writing"
    BROWSING = "browsing"
    IMAGE_EDITING = "image_editing"
    MESSAGING = "messaging"
    DEVELOPMENT = "development"


class PowerMode(Enum):
    """Admitted global power/operating-point modes (`R-11-018`)."""

    BALANCED = "balanced"
    PERFORMANCE = "performance"
    LOW_POWER = "low_power"


class FocusRung(Enum):
    """Discretionary focus/population rungs (`R-11-018a`)."""

    COMPACT = "compact"
    STANDARD = "standard"
    EXPANDED = "expanded"


class DevBuildMode(Enum):
    """Development build form (`R-13-027a`, `R-18-004e`)."""

    ELASTIC = "elastic"
    COMPOSITION = "composition"


class ReclamationStrategy(Enum):
    """Reclamation-economics comparison strategies on identical useful state."""

    FROZEN_RESIDENT = "frozen_resident"
    SEMANTIC_HIBERNATION = "semantic_hibernation"
    FIXED_POOL_REUSE = "fixed_pool_reuse"


def _require_nat(value: int, field: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < int(positive):
        kind = "positive" if positive else "nonnegative"
        raise WorkflowPresetError(f"{field}: {kind} integer required")
    return value


def _require_bool(value: bool, field: str) -> bool:
    if type(value) is not bool:
        raise WorkflowPresetError(f"{field}: boolean required")
    return value


def _require_name(value: str, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise WorkflowPresetError(f"{field}: nonempty identifier required")
    return value


@dataclass(frozen=True)
class StandingServices:
    """Required standing service reservations across modes and transitions."""

    audio: bool = True
    radio: bool = True
    display: bool = True
    storage: bool = True
    revocation: bool = True
    consent: bool = True
    inference: bool = True

    def missing_relative_to(self, required: "StandingServices") -> tuple[str, ...]:
        fields = ("audio", "radio", "display", "storage", "revocation", "consent", "inference")
        missing: list[str] = []
        for name in fields:
            req_val = _require_bool(getattr(required, name), f"required.{name}")
            act_val = _require_bool(getattr(self, name), f"actual.{name}")
            if req_val and not act_val:
                missing.append(name)
        return tuple(missing)


@dataclass(frozen=True)
class SelectionTriple:
    """Three separate selections (`PowerMode`, `PresetRecipe`, `FocusRung`)."""

    power: PowerMode
    profile: PresetRecipe
    rung: FocusRung


@dataclass(frozen=True)
class ByteLedger:
    """Exact steady/transition byte ledger (`workflow-profiles.md`, `WorkflowPresets.v`)."""

    resident_permanent: int
    live_or_frozen_private: int
    checkpoint_workspace: int
    quarantined: int
    metadata: int
    store_checkpoint: int = 0
    store_scratch: int = 0
    reusable_proved: bool = False
    overlap_credit: int = 0

    def validate(self, context: str) -> None:
        _require_nat(self.resident_permanent, f"{context}.resident_permanent")
        _require_nat(self.live_or_frozen_private, f"{context}.live_or_frozen_private")
        _require_nat(self.checkpoint_workspace, f"{context}.checkpoint_workspace")
        _require_nat(self.quarantined, f"{context}.quarantined")
        _require_nat(self.metadata, f"{context}.metadata")
        _require_nat(self.store_checkpoint, f"{context}.store_checkpoint")
        _require_nat(self.store_scratch, f"{context}.store_scratch")
        _require_bool(self.reusable_proved, f"{context}.reusable_proved")
        _require_nat(self.overlap_credit, f"{context}.overlap_credit")
        if self.overlap_credit > 0 and not self.reusable_proved:
            raise WorkflowPresetError(
                f"{context}: overlap credit ({self.overlap_credit}) claimed before Reusable"
            )
        if self.overlap_credit > self.live_or_frozen_private:
            raise WorkflowPresetError(
                f"{context}: overlap credit ({self.overlap_credit}) exceeds "
                f"live/frozen private backing ({self.live_or_frozen_private})"
            )

    @property
    def raw_ram(self) -> int:
        return (
            self.resident_permanent
            + self.live_or_frozen_private
            + self.checkpoint_workspace
            + self.quarantined
            + self.metadata
        )

    def effective_ram(self, context: str = "ledger") -> int:
        self.validate(context)
        credit = self.overlap_credit if self.reusable_proved else 0
        return self.raw_ram - credit

    @property
    def store_total(self) -> int:
        return self.store_checkpoint + self.store_scratch


@dataclass(frozen=True)
class RecipeSpec:
    """Concrete preset instance or explicit unavailable entry (`R-11-018a`)."""

    recipe: PresetRecipe
    enabled: bool
    unavailable_reason: str | None
    port_available: bool
    browser_port_qualified: bool
    dev_mode: DevBuildMode
    dev_exec_successor_only: bool
    borrows_composition_for_floor: bool
    laptop_floor_ok: bool
    standing: StandingServices
    companions: tuple[str, ...]
    continuing_services: tuple[str, ...]
    implicit_authority: bool
    strategy: ReclamationStrategy
    useful_state_bytes: int
    ledger: ByteLedger
    ram_budget: int
    store_budget: int


@dataclass(frozen=True)
class CatalogReport:
    """Validation summary across all six preset recipes."""

    enabled_recipes: tuple[PresetRecipe, ...]
    unavailable_recipes: dict[PresetRecipe, str]
    peak_ram: int
    peak_store: int


@dataclass(frozen=True)
class SteadyNode:
    """Reachable steady-state node in `ModeGraph`."""

    node_id: str
    selection: SelectionTriple
    standing: StandingServices
    implicit_authority: bool
    floor_ok: bool
    ledger: ByteLedger


@dataclass(frozen=True)
class TransitionEdge:
    """Directed transition certificate between two `SteadyNode`s (`R-11-018`)."""

    src_id: str
    dst_id: str
    local_only: bool
    power_unchanged: bool
    root_attested: bool
    explicit_authority: bool
    standing: StandingServices
    ledger: ByteLedger
    old_last_gap: int
    mid_gap: int
    new_first_gap: int
    continuing_deadline: int
    work_cost: int
    deadline: int
    recovery_reserved: bool
    cert_valid: bool

    @property
    def service_chain(self) -> int:
        return self.old_last_gap + self.mid_gap + self.new_first_gap


@dataclass(frozen=True)
class ModeGraph:
    """Explicit finite graph of reachable steady states and directed edges."""

    required_standing: StandingServices
    nodes: tuple[SteadyNode, ...]
    edges: tuple[TransitionEdge, ...]
    ram_capacity: int
    store_capacity: int


@dataclass(frozen=True)
class GraphPeakReport:
    """Steady, transition, and overall peak RAM/store ledger for `ModeGraph`."""

    steady_peak_ram: int
    transition_peak_ram: int
    overall_peak_ram: int
    steady_peak_store: int
    transition_peak_store: int
    overall_peak_store: int
    reachable_pairs: tuple[tuple[SelectionTriple, SelectionTriple], ...]


@dataclass(frozen=True)
class StrategyMeasurement:
    """Reclamation measurement for one strategy on a fixed useful state."""

    strategy: ReclamationStrategy
    useful_state_bytes: int
    steady_ledger: ByteLedger
    transition_ledger: ByteLedger
    endurance_writes_per_switch: int
    resume_latency: int


@dataclass(frozen=True)
class StrategyComparisonReport:
    """Side-by-side comparison of `FrozenResident`, `SemanticHibernation`, and `FixedPoolReuse`."""

    useful_state_bytes: int
    steady_ram_by_strategy: dict[ReclamationStrategy, int]
    peak_ram_by_strategy: dict[ReclamationStrategy, int]
    store_by_strategy: dict[ReclamationStrategy, int]
    endurance_by_strategy: dict[ReclamationStrategy, int]
    resume_latency_by_strategy: dict[ReclamationStrategy, int]
    steady_saving_hibernation_vs_frozen: int
    transition_overhead_hibernation_vs_frozen: int


@dataclass(frozen=True)
class TogglePolicy:
    """Repeated-toggling dwell, quarantine, endurance, and foreground-service bounds."""

    min_dwell: int
    quarantine_cap: int
    endurance_limit: int
    cp_store_cap: int
    fg_service_floor: int
    fg_slot_budget: int
    sweep_rate: int


@dataclass(frozen=True)
class ToggleEvent:
    """One tick or profile-switch request in a toggle-burst trace."""

    kind: str
    fg_work: int
    retire_bytes: int = 0
    cp_bytes: int = 0
    writes_needed: int = 0


@dataclass(frozen=True)
class ToggleSimState:
    """Simulator state matching `WorkflowPresets.ToggleSimState`."""

    ticks_since_switch: int
    quarantined_bytes: int
    quarantine_high_water: int
    endurance_writes: int
    cp_store_used: int
    fg_served: int
    switches_completed: int
    refused_count: int


@dataclass(frozen=True)
class ToggleReport:
    """Outcome of simulating a repeated-toggling trace."""

    final_state: ToggleSimState
    refusal_reasons: tuple[str, ...]


def validate_recipe(
    recipe: RecipeSpec, required_standing: StandingServices | None = None
) -> tuple[int, int]:
    """Validate one `RecipeSpec` and return `(effective_ram, store_demand)`."""
    req = required_standing or StandingServices()
    ctx = f"recipe.{recipe.recipe.value}"
    _require_bool(recipe.enabled, f"{ctx}.enabled")
    _require_bool(recipe.port_available, f"{ctx}.port_available")
    _require_bool(recipe.browser_port_qualified, f"{ctx}.browser_port_qualified")
    _require_bool(recipe.dev_exec_successor_only, f"{ctx}.dev_exec_successor_only")
    _require_bool(recipe.borrows_composition_for_floor, f"{ctx}.borrows_composition_for_floor")
    _require_bool(recipe.laptop_floor_ok, f"{ctx}.laptop_floor_ok")
    _require_bool(recipe.implicit_authority, f"{ctx}.implicit_authority")
    _require_nat(recipe.useful_state_bytes, f"{ctx}.useful_state_bytes")
    _require_nat(recipe.ram_budget, f"{ctx}.ram_budget")
    _require_nat(recipe.store_budget, f"{ctx}.store_budget")

    if recipe.implicit_authority:
        raise WorkflowPresetError(f"{ctx}: workflow profile selection cannot grant authority")

    missing_svc = recipe.standing.missing_relative_to(req)
    if missing_svc:
        raise WorkflowPresetError(
            f"{ctx}: dropped required standing services {', '.join(missing_svc)}"
        )

    if recipe.borrows_composition_for_floor:
        raise WorkflowPresetError(
            f"{ctx}: cannot borrow composition-mode grants to meet R-18-004a floor"
        )

    eff_ram = recipe.ledger.effective_ram(f"{ctx}.ledger")
    store_used = recipe.ledger.store_total

    if not recipe.enabled:
        if not recipe.unavailable_reason or not recipe.unavailable_reason.strip():
            raise WorkflowPresetError(f"{ctx}: disabled recipe must state unavailable_reason")
        return eff_ram, store_used

    if recipe.recipe is PresetRecipe.BROWSING and not recipe.browser_port_qualified:
        raise WorkflowPresetError(
            f"{ctx}: browser recipe deferred under R-18-004 without qualified port"
        )
    if not recipe.port_available:
        raise WorkflowPresetError(f"{ctx}: enabled recipe requires available port")
    if not recipe.laptop_floor_ok:
        raise WorkflowPresetError(f"{ctx}: enabled recipe must preserve R-18-004a laptop floor")
    if recipe.recipe is PresetRecipe.DEVELOPMENT and not recipe.dev_exec_successor_only:
        raise WorkflowPresetError(
            f"{ctx}: development outputs execute only in successor generation (R-13-027a)"
        )
    if eff_ram > recipe.ram_budget:
        raise WorkflowPresetError(
            f"{ctx}: effective RAM {eff_ram} exceeds budget {recipe.ram_budget}"
        )
    if store_used > recipe.store_budget:
        raise WorkflowPresetError(
            f"{ctx}: store demand {store_used} exceeds budget {recipe.store_budget}"
        )
    return eff_ram, store_used


def validate_catalog(
    catalog: Sequence[RecipeSpec],
    required_standing: StandingServices | None = None,
) -> CatalogReport:
    """Validate completeness and admission of all six preset recipes."""
    req = required_standing or StandingServices()
    seen: set[PresetRecipe] = set()
    enabled: list[PresetRecipe] = []
    unavailable: dict[PresetRecipe, str] = {}
    peak_ram = 0
    peak_store = 0

    for spec in catalog:
        if spec.recipe in seen:
            raise WorkflowPresetError(f"duplicate preset recipe {spec.recipe.value}")
        seen.add(spec.recipe)
        eff_ram, store_used = validate_recipe(spec, req)
        if spec.enabled:
            enabled.append(spec.recipe)
            peak_ram = max(peak_ram, eff_ram)
            peak_store = max(peak_store, store_used)
        else:
            unavailable[spec.recipe] = spec.unavailable_reason or ""

    missing = [r.value for r in PresetRecipe if r not in seen]
    if missing:
        raise WorkflowPresetError(f"catalog missing required recipes: {', '.join(missing)}")

    return CatalogReport(
        enabled_recipes=tuple(enabled),
        unavailable_recipes=unavailable,
        peak_ram=peak_ram,
        peak_store=peak_store,
    )


def validate_mode_graph(graph: ModeGraph) -> GraphPeakReport:
    """Validate every reachable node and directed transition edge without Cartesian product."""
    _require_nat(graph.ram_capacity, "graph.ram_capacity")
    _require_nat(graph.store_capacity, "graph.store_capacity")
    if not graph.nodes:
        raise WorkflowPresetError("graph must declare at least one reachable node")

    node_map: dict[str, SteadyNode] = {}
    steady_peak_ram = 0
    steady_peak_store = 0
    for node in graph.nodes:
        _require_name(node.node_id, "node.node_id")
        if node.node_id in node_map:
            raise WorkflowPresetError(f"duplicate node_id {node.node_id}")
        _require_bool(node.implicit_authority, f"{node.node_id}.implicit_authority")
        _require_bool(node.floor_ok, f"{node.node_id}.floor_ok")
        if node.implicit_authority:
            raise WorkflowPresetError(f"{node.node_id}: node selection grants implicit authority")
        if not node.floor_ok:
            raise WorkflowPresetError(f"{node.node_id}: node fails R-18-004a laptop floor")
        missing = node.standing.missing_relative_to(graph.required_standing)
        if missing:
            raise WorkflowPresetError(
                f"{node.node_id}: dropped standing services {', '.join(missing)}"
            )
        ram_used = node.ledger.effective_ram(f"node.{node.node_id}")
        store_used = node.ledger.store_total
        if ram_used > graph.ram_capacity:
            raise WorkflowPresetError(
                f"{node.node_id}: steady RAM {ram_used} exceeds capacity {graph.ram_capacity}"
            )
        if store_used > graph.store_capacity:
            raise WorkflowPresetError(
                f"{node.node_id}: steady store {store_used} exceeds capacity {graph.store_capacity}"
            )
        steady_peak_ram = max(steady_peak_ram, ram_used)
        steady_peak_store = max(steady_peak_store, store_used)
        node_map[node.node_id] = node

    transition_peak_ram = 0
    transition_peak_store = 0
    reachable_pairs: list[tuple[SelectionTriple, SelectionTriple]] = []

    for idx, edge in enumerate(graph.edges):
        ctx = f"edge[{idx}]({edge.src_id}->{edge.dst_id})"
        _require_bool(edge.local_only, f"{ctx}.local_only")
        _require_bool(edge.power_unchanged, f"{ctx}.power_unchanged")
        _require_bool(edge.root_attested, f"{ctx}.root_attested")
        _require_bool(edge.explicit_authority, f"{ctx}.explicit_authority")
        _require_bool(edge.recovery_reserved, f"{ctx}.recovery_reserved")
        _require_bool(edge.cert_valid, f"{ctx}.cert_valid")
        for fld in (
            "old_last_gap",
            "mid_gap",
            "new_first_gap",
            "continuing_deadline",
            "work_cost",
            "deadline",
        ):
            _require_nat(getattr(edge, fld), f"{ctx}.{fld}")

        if edge.src_id not in node_map or edge.dst_id not in node_map:
            raise WorkflowPresetError(f"{ctx}: unknown endpoint node")
        src = node_map[edge.src_id]
        dst = node_map[edge.dst_id]

        if not edge.cert_valid:
            raise WorkflowPresetError(f"{ctx}: missing valid transition certificate")
        if not edge.explicit_authority:
            raise WorkflowPresetError(f"{ctx}: transition lacks explicit authority")
        if edge.local_only:
            if not edge.power_unchanged or src.selection.power != dst.selection.power:
                raise WorkflowPresetError(
                    f"{ctx}: local profile switch cannot change power/fabric settings"
                )
        elif not edge.root_attested:
            raise WorkflowPresetError(
                f"{ctx}: global mode switch requires RoT-attested path (R-11-018)"
            )

        missing = edge.standing.missing_relative_to(graph.required_standing)
        if missing:
            raise WorkflowPresetError(
                f"{ctx}: edge dropped standing services {', '.join(missing)}"
            )
        if edge.service_chain > edge.continuing_deadline:
            raise WorkflowPresetError(
                f"{ctx}: continuing service chain {edge.service_chain} exceeds "
                f"deadline {edge.continuing_deadline}"
            )
        if edge.work_cost > edge.deadline:
            raise WorkflowPresetError(
                f"{ctx}: work cost {edge.work_cost} exceeds deadline {edge.deadline}"
            )
        if not edge.recovery_reserved:
            raise WorkflowPresetError(f"{ctx}: edge lacks reserved failure recovery")

        edge_ram = edge.ledger.effective_ram(ctx)
        edge_store = edge.ledger.store_total
        if edge_ram > graph.ram_capacity:
            raise WorkflowPresetError(
                f"{ctx}: transition peak RAM {edge_ram} exceeds capacity {graph.ram_capacity}"
            )
        if edge_store > graph.store_capacity:
            raise WorkflowPresetError(
                f"{ctx}: transition store {edge_store} exceeds capacity {graph.store_capacity}"
            )
        transition_peak_ram = max(transition_peak_ram, edge_ram)
        transition_peak_store = max(transition_peak_store, edge_store)
        reachable_pairs.append((src.selection, dst.selection))

    return GraphPeakReport(
        steady_peak_ram=steady_peak_ram,
        transition_peak_ram=transition_peak_ram,
        overall_peak_ram=max(steady_peak_ram, transition_peak_ram),
        steady_peak_store=steady_peak_store,
        transition_peak_store=transition_peak_store,
        overall_peak_store=max(steady_peak_store, transition_peak_store),
        reachable_pairs=tuple(reachable_pairs),
    )


def check_transition_reachable(
    graph: ModeGraph, src: SelectionTriple, dst: SelectionTriple
) -> TransitionEdge:
    """Require an explicit admitted directed edge between `src` and `dst` (never Cartesian product)."""
    validate_mode_graph(graph)
    node_map = {n.node_id: n for n in graph.nodes}
    for edge in graph.edges:
        if node_map[edge.src_id].selection == src and node_map[edge.dst_id].selection == dst:
            return edge
    raise WorkflowPresetError(
        f"no admitted transition edge from {src} to {dst} (Cartesian product not assumed)"
    )


def compare_strategies(
    measurements: Sequence[StrategyMeasurement],
) -> StrategyComparisonReport:
    """Compare `FrozenResident`, `SemanticHibernation`, and `FixedPoolReuse` on identical state."""
    by_strategy: dict[ReclamationStrategy, StrategyMeasurement] = {}
    for meas in measurements:
        _require_nat(meas.useful_state_bytes, f"{meas.strategy.value}.useful_state_bytes")
        _require_nat(
            meas.endurance_writes_per_switch,
            f"{meas.strategy.value}.endurance_writes_per_switch",
        )
        _require_nat(meas.resume_latency, f"{meas.strategy.value}.resume_latency")
        if meas.strategy in by_strategy:
            raise WorkflowPresetError(f"duplicate strategy measurement {meas.strategy.value}")
        meas.steady_ledger.validate(f"{meas.strategy.value}.steady")
        meas.transition_ledger.validate(f"{meas.strategy.value}.transition")
        by_strategy[meas.strategy] = meas

    missing = [s.value for s in ReclamationStrategy if s not in by_strategy]
    if missing:
        raise WorkflowPresetError(f"comparison missing strategies: {', '.join(missing)}")

    useful_values = {m.useful_state_bytes for m in by_strategy.values()}
    if len(useful_values) != 1:
        raise WorkflowPresetError(
            "strategies must be compared on identical useful_state_bytes"
        )
    useful_state = next(iter(useful_values))

    steady_ram: dict[ReclamationStrategy, int] = {}
    peak_ram: dict[ReclamationStrategy, int] = {}
    store_map: dict[ReclamationStrategy, int] = {}
    endurance_map: dict[ReclamationStrategy, int] = {}
    latency_map: dict[ReclamationStrategy, int] = {}

    for strat, meas in by_strategy.items():
        s_ram = meas.steady_ledger.effective_ram(f"{strat.value}.steady")
        t_ram = meas.transition_ledger.effective_ram(f"{strat.value}.transition")
        steady_ram[strat] = s_ram
        peak_ram[strat] = max(s_ram, t_ram)
        store_map[strat] = max(meas.steady_ledger.store_total, meas.transition_ledger.store_total)
        endurance_map[strat] = meas.endurance_writes_per_switch
        latency_map[strat] = meas.resume_latency

    frozen_steady = steady_ram[ReclamationStrategy.FROZEN_RESIDENT]
    hib_steady = steady_ram[ReclamationStrategy.SEMANTIC_HIBERNATION]
    hib_peak = peak_ram[ReclamationStrategy.SEMANTIC_HIBERNATION]

    return StrategyComparisonReport(
        useful_state_bytes=useful_state,
        steady_ram_by_strategy=steady_ram,
        peak_ram_by_strategy=peak_ram,
        store_by_strategy=store_map,
        endurance_by_strategy=endurance_map,
        resume_latency_by_strategy=latency_map,
        steady_saving_hibernation_vs_frozen=frozen_steady - hib_steady,
        transition_overhead_hibernation_vs_frozen=hib_peak - hib_steady,
    )


def simulate_toggle_burst(
    policy: TogglePolicy,
    events: Sequence[ToggleEvent],
    *,
    initial_state: ToggleSimState | None = None,
    strict: bool = False,
) -> ToggleReport:
    """Simulate repeated toggling under dwell, quarantine, endurance, and foreground floors."""
    _require_nat(policy.min_dwell, "policy.min_dwell")
    _require_nat(policy.quarantine_cap, "policy.quarantine_cap")
    _require_nat(policy.endurance_limit, "policy.endurance_limit")
    _require_nat(policy.cp_store_cap, "policy.cp_store_cap")
    _require_nat(policy.fg_service_floor, "policy.fg_service_floor")
    _require_nat(policy.fg_slot_budget, "policy.fg_slot_budget")
    _require_nat(policy.sweep_rate, "policy.sweep_rate")

    state = initial_state or ToggleSimState(
        ticks_since_switch=policy.min_dwell,
        quarantined_bytes=0,
        quarantine_high_water=0,
        endurance_writes=0,
        cp_store_used=0,
        fg_served=0,
        switches_completed=0,
        refused_count=0,
    )
    if state.quarantined_bytes > state.quarantine_high_water:
        raise WorkflowPresetError("initial quarantine exceeds high water")
    if state.quarantine_high_water > policy.quarantine_cap:
        raise WorkflowPresetError("initial quarantine high water exceeds quarantine_cap")
    if state.endurance_writes > policy.endurance_limit:
        raise WorkflowPresetError("initial endurance exceeds endurance_limit")
    if state.cp_store_used > policy.cp_store_cap:
        raise WorkflowPresetError("initial checkpoint store exceeds cp_store_cap")

    refusals: list[str] = []
    for idx, ev in enumerate(events):
        fg_work = _require_nat(ev.fg_work, f"events[{idx}].fg_work")
        if fg_work > policy.fg_slot_budget:
            raise WorkflowPresetError(
                f"events[{idx}]: fg_work {fg_work} exceeds fg_slot_budget {policy.fg_slot_budget}"
            )
        if ev.kind == "tick":
            state = replace(
                state,
                ticks_since_switch=state.ticks_since_switch + 1,
                quarantined_bytes=max(0, state.quarantined_bytes - policy.sweep_rate),
                fg_served=state.fg_served + fg_work,
            )
        elif ev.kind == "switch":
            retire = _require_nat(ev.retire_bytes, f"events[{idx}].retire_bytes")
            cp_bytes = _require_nat(ev.cp_bytes, f"events[{idx}].cp_bytes")
            writes = _require_nat(ev.writes_needed, f"events[{idx}].writes_needed")

            reason: str | None = None
            if state.ticks_since_switch < policy.min_dwell:
                reason = f"events[{idx}]: dwell {state.ticks_since_switch} < min_dwell {policy.min_dwell}"
            elif state.quarantined_bytes + retire > policy.quarantine_cap:
                reason = (
                    f"events[{idx}]: quarantine {state.quarantined_bytes + retire} > "
                    f"quarantine_cap {policy.quarantine_cap}"
                )
            elif state.endurance_writes + writes > policy.endurance_limit:
                reason = (
                    f"events[{idx}]: endurance {state.endurance_writes + writes} > "
                    f"endurance_limit {policy.endurance_limit}"
                )
            elif state.cp_store_used + cp_bytes > policy.cp_store_cap:
                reason = (
                    f"events[{idx}]: checkpoint store {state.cp_store_used + cp_bytes} > "
                    f"cp_store_cap {policy.cp_store_cap}"
                )
            elif fg_work < policy.fg_service_floor:
                reason = (
                    f"events[{idx}]: fg_work {fg_work} < fg_service_floor {policy.fg_service_floor}"
                )

            if reason is not None:
                if strict:
                    raise WorkflowPresetError(reason)
                refusals.append(reason)
                state = replace(state, refused_count=state.refused_count + 1)
            else:
                new_q = state.quarantined_bytes + retire
                state = replace(
                    state,
                    ticks_since_switch=0,
                    quarantined_bytes=new_q,
                    quarantine_high_water=max(state.quarantine_high_water, new_q),
                    endurance_writes=state.endurance_writes + writes,
                    cp_store_used=state.cp_store_used + cp_bytes,
                    fg_served=state.fg_served + fg_work,
                    switches_completed=state.switches_completed + 1,
                )
        else:
            raise WorkflowPresetError(f"events[{idx}]: unknown event kind {ev.kind!r}")

    return ToggleReport(final_state=state, refusal_reasons=tuple(refusals))


def default_preset_catalog() -> tuple[RecipeSpec, ...]:
    """Return the six product preset recipes matching `WorkflowPresets.default_catalog`."""
    standing = StandingServices()
    return (
        RecipeSpec(
            recipe=PresetRecipe.EVERYDAY,
            enabled=True,
            unavailable_reason=None,
            port_available=True,
            browser_port_qualified=False,
            dev_mode=DevBuildMode.ELASTIC,
            dev_exec_successor_only=True,
            borrows_composition_for_floor=False,
            laptop_floor_ok=True,
            standing=standing,
            companions=("launcher", "notes"),
            continuing_services=("audio", "radio", "display", "storage", "revocation", "consent"),
            implicit_authority=False,
            strategy=ReclamationStrategy.SEMANTIC_HIBERNATION,
            useful_state_bytes=64,
            ledger=ByteLedger(48, 64, 16, 16, 8, store_checkpoint=32, store_scratch=16, reusable_proved=True, overlap_credit=32),
            ram_budget=160,
            store_budget=64,
        ),
        RecipeSpec(
            recipe=PresetRecipe.WRITING,
            enabled=True,
            unavailable_reason=None,
            port_available=True,
            browser_port_qualified=False,
            dev_mode=DevBuildMode.ELASTIC,
            dev_exec_successor_only=True,
            borrows_composition_for_floor=False,
            laptop_floor_ok=True,
            standing=standing,
            companions=("spellcheck", "messaging"),
            continuing_services=("audio", "radio", "display", "storage", "revocation", "consent"),
            implicit_authority=False,
            strategy=ReclamationStrategy.SEMANTIC_HIBERNATION,
            useful_state_bytes=96,
            ledger=ByteLedger(48, 96, 24, 16, 8, store_checkpoint=48, store_scratch=16, reusable_proved=True, overlap_credit=48),
            ram_budget=192,
            store_budget=80,
        ),
        RecipeSpec(
            recipe=PresetRecipe.BROWSING,
            enabled=False,
            unavailable_reason="browser deferred under R-18-004 until Q29 port qualification",
            port_available=False,
            browser_port_qualified=False,
            dev_mode=DevBuildMode.ELASTIC,
            dev_exec_successor_only=True,
            borrows_composition_for_floor=False,
            laptop_floor_ok=True,
            standing=standing,
            companions=("origin_compartment",),
            continuing_services=("audio", "download", "notification"),
            implicit_authority=False,
            strategy=ReclamationStrategy.FROZEN_RESIDENT,
            useful_state_bytes=128,
            ledger=ByteLedger(48, 128, 0, 0, 12),
            ram_budget=256,
            store_budget=64,
        ),
        RecipeSpec(
            recipe=PresetRecipe.IMAGE_EDITING,
            enabled=True,
            unavailable_reason=None,
            port_available=True,
            browser_port_qualified=False,
            dev_mode=DevBuildMode.ELASTIC,
            dev_exec_successor_only=True,
            borrows_composition_for_floor=False,
            laptop_floor_ok=True,
            standing=standing,
            companions=("export_task",),
            continuing_services=("audio", "radio", "display", "storage", "revocation", "consent"),
            implicit_authority=False,
            strategy=ReclamationStrategy.SEMANTIC_HIBERNATION,
            useful_state_bytes=128,
            ledger=ByteLedger(48, 128, 32, 24, 12, store_checkpoint=64, store_scratch=24, reusable_proved=True, overlap_credit=64),
            ram_budget=224,
            store_budget=96,
        ),
        RecipeSpec(
            recipe=PresetRecipe.MESSAGING,
            enabled=True,
            unavailable_reason=None,
            port_available=True,
            browser_port_qualified=False,
            dev_mode=DevBuildMode.ELASTIC,
            dev_exec_successor_only=True,
            borrows_composition_for_floor=False,
            laptop_floor_ok=True,
            standing=standing,
            companions=("receive_notification",),
            continuing_services=("audio", "radio", "display", "storage", "revocation", "consent"),
            implicit_authority=False,
            strategy=ReclamationStrategy.FIXED_POOL_REUSE,
            useful_state_bytes=48,
            ledger=ByteLedger(48, 48, 0, 16, 8, reusable_proved=True, overlap_credit=16),
            ram_budget=128,
            store_budget=32,
        ),
        RecipeSpec(
            recipe=PresetRecipe.DEVELOPMENT,
            enabled=True,
            unavailable_reason=None,
            port_available=True,
            browser_port_qualified=False,
            dev_mode=DevBuildMode.ELASTIC,
            dev_exec_successor_only=True,
            borrows_composition_for_floor=False,
            laptop_floor_ok=True,
            standing=standing,
            companions=("editor", "compiler", "prover"),
            continuing_services=("audio", "radio", "display", "storage", "revocation", "consent"),
            implicit_authority=False,
            strategy=ReclamationStrategy.FIXED_POOL_REUSE,
            useful_state_bytes=128,
            ledger=ByteLedger(48, 128, 16, 24, 12, store_checkpoint=32, store_scratch=16, reusable_proved=True, overlap_credit=32),
            ram_budget=224,
            store_budget=64,
        ),
    )
