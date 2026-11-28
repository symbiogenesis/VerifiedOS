# SPDX-License-Identifier: Apache-2.0
"""Q34d yield-point placement, strip-mining, sink lowering, and cost checking.

Executable reference pass and verifier matching [YieldBound.v](../../proofs/YieldBound.v)
and [ElasticDomain.v](../../proofs/ElasticDomain.v) (`R-07-037h`, `R-05-102`,
`R-11-015`, `TAL-014`).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum


class YieldBoundError(ValueError):
    """A CFG, loop transformation, sink lowering, or cost check failed admission."""


class CostFacetSchema(Enum):
    """Pinned TAL cost-facet schema (`TAL-014`)."""

    SCALAR_REACTION = "scalar_reaction"
    TRIPLE_REACTION = "triple_reaction"


def _require_nat(value: int, field: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < int(positive):
        kind = "positive" if positive else "nonnegative"
        raise YieldBoundError(f"{field}: {kind} integer required")
    return value


def _require_bool(value: bool, field: str) -> bool:
    if type(value) is not bool:
        raise YieldBoundError(f"{field}: boolean required")
    return value


def _require_name(value: str, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise YieldBoundError(f"{field}: nonempty identifier required")
    return value


@dataclass(frozen=True)
class BasicBlock:
    """One basic block in a function's control-flow graph (`ElasticDomain.Cfg`)."""

    id: str
    cost: int
    is_entry: bool = False
    is_exit: bool = False
    is_poll: bool = False
    is_real_yield: bool = False
    is_sink: bool = False
    is_recursive_entry: bool = False


@dataclass(frozen=True)
class CfgEdge:
    """Directed CFG edge, optionally marked as a loop back-edge or switch-requested."""

    source: str
    target: str
    is_back_edge: bool = False
    is_switch_requested: bool = False


@dataclass(frozen=True)
class Cfg:
    """Finite control-flow graph corresponding to `ElasticDomain.Cfg`."""

    name: str
    blocks: tuple[BasicBlock, ...]
    edges: tuple[CfgEdge, ...]

    def block_map(self) -> dict[str, BasicBlock]:
        return {b.id: b for b in self.blocks}

    def entry_block(self) -> BasicBlock:
        entries = [b for b in self.blocks if b.is_entry]
        if len(entries) != 1:
            raise YieldBoundError(f"{self.name}: exactly one entry block required")
        return entries[0]

    def outgoing(self, block_id: str) -> tuple[CfgEdge, ...]:
        return tuple(e for e in self.edges if e.source == block_id)


@dataclass(frozen=True)
class LoopTransformSpec:
    """Strip-mining parameters for one natural loop."""

    header: str
    body_blocks: tuple[str, ...]
    back_edge_source: str
    factor: int
    poll_cost: int | None = None


@dataclass(frozen=True)
class StripMineReport:
    """Admissibility and poll-overhead comparison for a strip-mined loop."""

    factor: int
    unmodified_reaction_cost: int
    strip_mined_reaction_cost: int
    unmodified_polls: int
    strip_mined_polls: int
    unmodified_poll_overhead: int
    strip_mined_poll_overhead: int
    overhead_saved: int
    admitted: bool


@dataclass(frozen=True)
class FnCostTriple:
    """Per-function compositional reaction-cost summary (`YieldBound.FnCostTriple`)."""

    entry_to_first_poll: int
    poll_to_poll: int
    last_poll_to_exit: int
    has_internal_poll: bool

    @property
    def full_cost(self) -> int:
        if self.has_internal_poll:
            raise YieldBoundError("full_cost applies only when has_internal_poll is False")
        return self.entry_to_first_poll


@dataclass(frozen=True)
class CallSite:
    """A call site inside a caller CFG between `pre_block` and `post_block`."""

    caller_fn: str
    pre_block: str
    post_block: str
    callee_fn: str
    is_recursive: bool = False


@dataclass(frozen=True)
class ProgramFunction:
    """Function CFG together with its outgoing call sites."""

    name: str
    cfg: Cfg
    calls: tuple[CallSite, ...] = ()


@dataclass(frozen=True)
class ReactionPath:
    """A concrete poll-free reaction path and its cost."""

    start: str
    inner: tuple[str, ...]
    end: str | None
    is_exit: bool
    cost: int


@dataclass(frozen=True)
class YieldBoundVerdict:
    """Whole-program Q34d verification outcome."""

    admitted: bool
    yield_bound: int
    call_interval: int
    call_bound: int
    max_reaction_cost: int
    triples: dict[str, FnCostTriple]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class Tal014ExpressivenessResult:
    """TAL-014 cost-facet expressiveness verdict for a function/call profile."""

    schema: CostFacetSchema
    expressible: bool
    version_bump_required: bool
    reason: str


def validate_cfg(cfg: Cfg) -> dict[str, BasicBlock]:
    """Validate structural invariants of `cfg` and return its block map."""
    _require_name(cfg.name, "cfg.name")
    if not cfg.blocks:
        raise YieldBoundError(f"{cfg.name}: CFG has no blocks")
    blocks: dict[str, BasicBlock] = {}
    entries = 0
    for blk in cfg.blocks:
        _require_name(blk.id, "block.id")
        if blk.id in blocks:
            raise YieldBoundError(f"{cfg.name}: duplicate block {blk.id}")
        _require_nat(blk.cost, f"{cfg.name}.{blk.id}.cost")
        for flag_name, flag in (
            ("is_entry", blk.is_entry),
            ("is_exit", blk.is_exit),
            ("is_poll", blk.is_poll),
            ("is_real_yield", blk.is_real_yield),
            ("is_sink", blk.is_sink),
            ("is_recursive_entry", blk.is_recursive_entry),
        ):
            _require_bool(flag, f"{cfg.name}.{blk.id}.{flag_name}")
        if blk.is_real_yield and not blk.is_poll:
            raise YieldBoundError(f"{cfg.name}.{blk.id}: real yield must be a poll site")
        if blk.is_entry:
            entries += 1
        blocks[blk.id] = blk
    if entries != 1:
        raise YieldBoundError(f"{cfg.name}: expected 1 entry block, found {entries}")
    seen_edges: set[tuple[str, str]] = set()
    for edge in cfg.edges:
        if edge.source not in blocks or edge.target not in blocks:
            raise YieldBoundError(
                f"{cfg.name}: edge {edge.source}->{edge.target} names unknown block"
            )
        _require_bool(edge.is_back_edge, "edge.is_back_edge")
        _require_bool(edge.is_switch_requested, "edge.is_switch_requested")
        key = (edge.source, edge.target)
        if key in seen_edges:
            raise YieldBoundError(f"{cfg.name}: duplicate edge {edge.source}->{edge.target}")
        seen_edges.add(key)
    return blocks


def place_polls(cfg: Cfg) -> Cfg:
    """Place poll sites on every loop back-edge target and every recursive-call entry."""
    validate_cfg(cfg)
    back_targets = {e.target for e in cfg.edges if e.is_back_edge}
    new_blocks = tuple(
        replace(
            blk,
            is_poll=blk.is_poll or (blk.id in back_targets) or blk.is_recursive_entry,
        )
        for blk in cfg.blocks
    )
    return replace(cfg, blocks=new_blocks)


def _ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator if numerator > 0 else 0


def strip_mine_loop(
    cfg: Cfg,
    loop: LoopTransformSpec,
    yield_bound: int,
    iterations: int = 10,
) -> tuple[Cfg, StripMineReport]:
    """Strip-mine one loop by factor `k >= 1` and enforce `k * body + poll <= yield_bound`."""
    blocks = validate_cfg(cfg)
    _require_nat(yield_bound, "yield_bound")
    _require_nat(iterations, "iterations")
    factor = _require_nat(loop.factor, "strip_mine.factor", positive=True)
    if loop.header not in blocks:
        raise YieldBoundError(f"{cfg.name}: unknown loop header {loop.header}")
    if not loop.body_blocks:
        raise YieldBoundError(f"{cfg.name}: strip-mine loop requires nonempty body_blocks")
    if loop.back_edge_source not in loop.body_blocks:
        raise YieldBoundError(
            f"{cfg.name}: back_edge_source {loop.back_edge_source} must be in body_blocks"
        )
    if not any(
        e.source == loop.back_edge_source and e.target == loop.header and e.is_back_edge
        for e in cfg.edges
    ):
        raise YieldBoundError(
            f"{cfg.name}: missing back-edge {loop.back_edge_source}->{loop.header}"
        )
    body_set = set(loop.body_blocks)
    if len(body_set) != len(loop.body_blocks):
        raise YieldBoundError(f"{cfg.name}: duplicate block in body_blocks")
    for bid in loop.body_blocks:
        if bid not in blocks:
            raise YieldBoundError(f"{cfg.name}: unknown loop body block {bid}")
        if bid == loop.header:
            raise YieldBoundError(f"{cfg.name}: header {bid} cannot appear in body_blocks")
        if blocks[bid].is_poll:
            raise YieldBoundError(f"{cfg.name}: body block {bid} already carries a poll")

    header_blk = blocks[loop.header]
    poll_cost = header_blk.cost if loop.poll_cost is None else _require_nat(
        loop.poll_cost, "strip_mine.poll_cost"
    )
    body_cost = sum(blocks[bid].cost for bid in loop.body_blocks)
    unmodified_reaction = poll_cost + body_cost
    strip_mined_reaction = poll_cost + factor * body_cost
    unmod_polls = iterations
    strip_polls = _ceil_div(iterations, factor)
    unmod_overhead = unmod_polls * poll_cost
    strip_overhead = strip_polls * poll_cost
    admitted = strip_mined_reaction <= yield_bound
    report = StripMineReport(
        factor=factor,
        unmodified_reaction_cost=unmodified_reaction,
        strip_mined_reaction_cost=strip_mined_reaction,
        unmodified_polls=unmod_polls,
        strip_mined_polls=strip_polls,
        unmodified_poll_overhead=unmod_overhead,
        strip_mined_poll_overhead=strip_overhead,
        overhead_saved=unmod_overhead - strip_overhead,
        admitted=admitted,
    )
    if not admitted:
        raise YieldBoundError(
            f"{cfg.name}: strip-mined loop reaction {strip_mined_reaction} exceeds "
            f"yield_bound {yield_bound}"
        )

    # Collapse the unrolled body into its single loop-body block (retaining header ->
    # first_body ... -> back_edge_source -> header with cost scaled by `factor`).
    anchor = loop.body_blocks[0]
    new_blocks: list[BasicBlock] = []
    for blk in cfg.blocks:
        if blk.id == loop.header:
            new_blocks.append(replace(blk, is_poll=True, cost=poll_cost))
        elif blk.id == anchor:
            new_blocks.append(replace(blk, cost=factor * body_cost))
        elif blk.id in body_set:
            new_blocks.append(replace(blk, cost=0))
        else:
            new_blocks.append(blk)
    return replace(cfg, blocks=tuple(new_blocks)), report


def lower_sink_before_yield(cfg: Cfg, yield_block_cost: int = 1) -> Cfg:
    """Lower every `switch-requested` sink so it enters a real yield before resuming."""
    blocks = validate_cfg(cfg)
    _require_nat(yield_block_cost, "yield_block_cost")
    existing_ids = set(blocks.keys())
    sink_targets = {e.target for e in cfg.edges if e.is_switch_requested}
    for blk in cfg.blocks:
        if blk.is_sink:
            sink_targets.add(blk.id)

    updated_blocks: dict[str, BasicBlock] = dict(blocks)
    added_blocks: list[BasicBlock] = []
    new_edges: list[CfgEdge] = list(cfg.edges)

    for sink_id in sorted(sink_targets):
        sink_blk = updated_blocks[sink_id]
        updated_blocks[sink_id] = replace(
            sink_blk, is_sink=True, is_poll=False, is_real_yield=False, is_exit=False
        )
        outgoing = [e for e in new_edges if e.source == sink_id]
        if (
            len(outgoing) == 1
            and updated_blocks[outgoing[0].target].is_poll
            and updated_blocks[outgoing[0].target].is_real_yield
        ):
            continue

        yield_id = f"{sink_id}__yield"
        while yield_id in existing_ids:
            yield_id += "_"
        existing_ids.add(yield_id)

        resume_targets = [e.target for e in outgoing]
        if not resume_targets:
            resume_targets = [
                e.source for e in cfg.edges if e.target == sink_id and e.is_switch_requested
            ]
        new_edges = [e for e in new_edges if e.source != sink_id]
        new_edges.append(CfgEdge(sink_id, yield_id, is_back_edge=False))
        added_blocks.append(
            BasicBlock(
                id=yield_id,
                cost=yield_block_cost,
                is_poll=True,
                is_real_yield=True,
            )
        )
        for resume in resume_targets:
            was_back = any(
                e.source == sink_id and e.target == resume and e.is_back_edge
                for e in outgoing
            )
            new_edges.append(CfgEdge(yield_id, resume, is_back_edge=was_back))

    final_blocks = tuple(updated_blocks[b.id] for b in cfg.blocks) + tuple(added_blocks)
    return replace(cfg, blocks=final_blocks, edges=tuple(new_edges))


def verify_polls(cfg: Cfg) -> list[str]:
    """Check `PollsEveryBackEdge` and `PollsEveryRecursiveEntry`."""
    blocks = validate_cfg(cfg)
    errors = [
        f"{cfg.name}: back-edge {edge.source}->{edge.target} target lacks poll site"
        for edge in cfg.edges
        if edge.is_back_edge and not blocks[edge.target].is_poll
    ]
    errors.extend(
        f"{cfg.name}: recursive-call entry {blk.id} lacks poll site"
        for blk in cfg.blocks
        if blk.is_recursive_entry and not blk.is_poll
    )
    return errors


def verify_sinks(cfg: Cfg) -> list[str]:
    """Check `SinksYieldWithinOneReaction` and `switch-requested` sink invariants."""
    blocks = validate_cfg(cfg)
    errors = [
        f"{cfg.name}: switch-requested edge {edge.source}->{edge.target} "
        "does not enter a marked sink block"
        for edge in cfg.edges
        if edge.is_switch_requested and not blocks[edge.target].is_sink
    ]

    for blk in cfg.blocks:
        if not blk.is_sink:
            continue
        if blk.is_poll:
            if not blk.is_real_yield:
                errors.append(
                    f"{cfg.name}: sink {blk.id} is a tentative poll without real yield"
                )
            continue
        # DFS over poll-free paths starting at sink `blk.id`.
        stack: list[tuple[str, frozenset[str]]] = [(blk.id, frozenset({blk.id}))]
        while stack:
            cur, path = stack.pop()
            cur_blk = blocks[cur]
            if cur_blk.is_exit:
                errors.append(
                    f"{cfg.name}: sink {blk.id} reaches exit {cur} without yielding"
                )
                continue
            outgoing = cfg.outgoing(cur)
            if not outgoing:
                errors.append(
                    f"{cfg.name}: sink {blk.id} stalls at {cur} without reaching a yield"
                )
                continue
            for edge in outgoing:
                nxt = blocks[edge.target]
                if nxt.is_poll:
                    if not nxt.is_real_yield:
                        errors.append(
                            f"{cfg.name}: sink {blk.id} returns to tentative poll "
                            f"{nxt.id} without real yield"
                        )
                elif nxt.id in path:
                    errors.append(
                        f"{cfg.name}: sink {blk.id} loops poll-free through {nxt.id} "
                        "without yielding"
                    )
                else:
                    stack.append((nxt.id, path | {nxt.id}))
    return errors


def _enumerate_poll_free_reactions(
    cfg: Cfg, blocks: dict[str, BasicBlock], start: str
) -> list[ReactionPath]:
    """Enumerate all simple poll-free reactions starting at `start` (refusing cycles)."""
    results: list[ReactionPath] = []
    start_blk = blocks[start]
    # Stack item: (current_id, path_nodes_after_start, visited_inner, running_cost)
    stack: list[tuple[str, tuple[str, ...], frozenset[str], int]] = [
        (start, (), frozenset(), start_blk.cost)
    ]
    while stack:
        cur, inner, visited, cost = stack.pop()
        cur_blk = blocks[cur]
        if cur_blk.is_exit:
            results.append(ReactionPath(start, inner, None, True, cost))
        for edge in cfg.outgoing(cur):
            nxt_blk = blocks[edge.target]
            if nxt_blk.is_poll:
                results.append(ReactionPath(start, inner, nxt_blk.id, False, cost))
            elif nxt_blk.id in visited:
                raise YieldBoundError(
                    f"{cfg.name}: unpolled poll-free cycle reaching {nxt_blk.id}"
                )
            else:
                stack.append(
                    (
                        nxt_blk.id,
                        (*inner, nxt_blk.id),
                        visited | {nxt_blk.id},
                        cost + nxt_blk.cost,
                    )
                )
    return results


def analyze_cfg_reactions(cfg: Cfg) -> tuple[list[ReactionPath], FnCostTriple]:
    """Compute all intra-function reactions and the function's `FnCostTriple`."""
    blocks = validate_cfg(cfg)
    entry = cfg.entry_block()
    starts = [entry.id] + [
        b.id for b in cfg.blocks if b.is_poll and b.id != entry.id
    ]
    all_reactions: list[ReactionPath] = []
    for start in starts:
        all_reactions.extend(_enumerate_poll_free_reactions(cfg, blocks, start))

    entry_to_poll = [r for r in all_reactions if r.start == entry.id and not r.is_exit]
    entry_to_exit = [r for r in all_reactions if r.start == entry.id and r.is_exit]
    poll_to_poll = [
        r for r in all_reactions if blocks[r.start].is_poll and not r.is_exit
    ]
    poll_to_exit = [
        r for r in all_reactions if blocks[r.start].is_poll and r.is_exit
    ]

    if entry.is_poll:
        triple = FnCostTriple(
            entry_to_first_poll=0,
            poll_to_poll=max((r.cost for r in poll_to_poll), default=0),
            last_poll_to_exit=max((r.cost for r in poll_to_exit), default=0),
            has_internal_poll=True,
        )
        return all_reactions, triple

    if entry_to_poll and entry_to_exit:
        raise YieldBoundError(
            f"{cfg.name}: mixed poll-free exit and internal poll from entry {entry.id}"
        )
    if entry_to_poll or poll_to_poll or poll_to_exit:
        triple = FnCostTriple(
            entry_to_first_poll=max((r.cost for r in entry_to_poll), default=0),
            poll_to_poll=max((r.cost for r in poll_to_poll), default=0),
            last_poll_to_exit=max((r.cost for r in poll_to_exit), default=0),
            has_internal_poll=True,
        )
        return all_reactions, triple

    full = max((r.cost for r in entry_to_exit), default=0)
    triple = FnCostTriple(
        entry_to_first_poll=full,
        poll_to_poll=0,
        last_poll_to_exit=full,
        has_internal_poll=False,
    )
    return all_reactions, triple


def check_call_site(
    caller_pre_cost: int,
    callee_triple: FnCostTriple,
    caller_post_cost: int,
    yield_bound: int,
    *,
    is_recursive: bool = False,
) -> list[str]:
    """Check one call site's compositional reaction-cost bounds against `yield_bound`."""
    _require_nat(caller_pre_cost, "caller_pre_cost")
    _require_nat(caller_post_cost, "caller_post_cost")
    _require_nat(yield_bound, "yield_bound")
    _require_bool(is_recursive, "is_recursive")
    errors: list[str] = []
    if callee_triple.has_internal_poll:
        pre_sum = caller_pre_cost + callee_triple.entry_to_first_poll
        if pre_sum > yield_bound:
            errors.append(
                f"cross-call pre + entry_to_first_poll ({pre_sum}) > yield_bound ({yield_bound})"
            )
        if callee_triple.poll_to_poll > yield_bound:
            errors.append(
                f"callee poll_to_poll ({callee_triple.poll_to_poll}) > yield_bound ({yield_bound})"
            )
        post_sum = callee_triple.last_poll_to_exit + caller_post_cost
        if post_sum > yield_bound:
            errors.append(
                f"cross-call last_poll_to_exit + post ({post_sum}) > yield_bound ({yield_bound})"
            )
    else:
        if is_recursive:
            errors.append("recursive call target lacks internal/entry poll site")
        full_sum = caller_pre_cost + callee_triple.full_cost + caller_post_cost
        if full_sum > yield_bound:
            errors.append(
                f"cross-call pre + callee_full + post ({full_sum}) > yield_bound ({yield_bound})"
            )
    return errors


def _max_poll_free_cost_to(
    cfg: Cfg, blocks: dict[str, BasicBlock], target_id: str
) -> int:
    """Maximum poll-free reaction cost from entry or any poll site ending at `target_id`."""
    entry = cfg.entry_block()
    starts = [entry.id] + [
        b.id for b in cfg.blocks if b.is_poll and b.id != entry.id
    ]
    best = 0
    found = False
    for start in starts:
        start_blk = blocks[start]
        if start == target_id and not start_blk.is_poll:
            best = max(best, start_blk.cost)
            found = True
        stack: list[tuple[str, frozenset[str], int]] = [
            (start, frozenset(), start_blk.cost)
        ]
        while stack:
            cur, visited, cost = stack.pop()
            for edge in cfg.outgoing(cur):
                nxt = blocks[edge.target]
                if nxt.is_poll:
                    continue
                if nxt.id == target_id:
                    best = max(best, cost + nxt.cost)
                    found = True
                elif nxt.id not in visited:
                    stack.append((nxt.id, visited | {nxt.id}, cost + nxt.cost))
    if not found:
        raise YieldBoundError(
            f"{cfg.name}: call pre_block {target_id} is unreachable poll-free"
        )
    return best


def _max_poll_free_cost_from(
    cfg: Cfg, blocks: dict[str, BasicBlock], post_id: str, pre_id: str
) -> int:
    """Maximum poll-free reaction cost starting at `post_id` to next poll or exit."""
    post_blk = blocks[post_id]
    if post_blk.is_poll:
        return 0
    best = 0
    found = False
    stack: list[tuple[str, frozenset[str], int]] = [
        (post_id, frozenset({post_id}), post_blk.cost)
    ]
    while stack:
        cur, visited, cost = stack.pop()
        cur_blk = blocks[cur]
        if cur_blk.is_exit:
            best = max(best, cost)
            found = True
        for edge in cfg.outgoing(cur):
            nxt = blocks[edge.target]
            if nxt.id == pre_id and not nxt.is_poll:
                raise YieldBoundError(
                    f"{cfg.name}: poll-free path from {post_id} re-enters call {pre_id}"
                )
            if nxt.is_poll:
                best = max(best, cost)
                found = True
            elif nxt.id not in visited:
                stack.append((nxt.id, visited | {nxt.id}, cost + nxt.cost))
    if not found:
        raise YieldBoundError(
            f"{cfg.name}: call post_block {post_id} reaches neither poll nor exit"
        )
    return best


def verify_function(
    cfg: Cfg, yield_bound: int
) -> tuple[FnCostTriple, list[ReactionPath], list[str]]:
    """Verify polls, sinks, and intra-function reaction bounds for `cfg`."""
    _require_nat(yield_bound, "yield_bound")
    errors = verify_polls(cfg) + verify_sinks(cfg)
    reactions, triple = analyze_cfg_reactions(cfg)
    for rx in reactions:
        if rx.cost > yield_bound:
            errors.append(
                f"{cfg.name}: reaction from {rx.start} costs {rx.cost} > "
                f"yield_bound {yield_bound}"
            )
    return triple, reactions, errors


def verify_program(
    functions: Sequence[ProgramFunction],
    yield_bound: int,
    call_interval: int,
) -> YieldBoundVerdict:
    """Verify a multi-function program and compute its `YieldBoundVerdict`."""
    _require_nat(yield_bound, "yield_bound")
    _require_nat(call_interval, "call_interval")
    if not functions:
        raise YieldBoundError("program must contain at least one function")

    fn_map: dict[str, ProgramFunction] = {}
    for fn in functions:
        _require_name(fn.name, "function.name")
        if fn.name != fn.cfg.name:
            raise YieldBoundError(
                f"function name {fn.name} disagrees with CFG name {fn.cfg.name}"
            )
        if fn.name in fn_map:
            raise YieldBoundError(f"duplicate function {fn.name}")
        fn_map[fn.name] = fn

    triples: dict[str, FnCostTriple] = {}
    errors: list[str] = []
    max_cost = 0
    for fn in functions:
        triple, reactions, fn_errors = verify_function(fn.cfg, yield_bound)
        triples[fn.name] = triple
        errors.extend(fn_errors)
        for rx in reactions:
            max_cost = max(max_cost, rx.cost)

    for fn in functions:
        blocks = validate_cfg(fn.cfg)
        for cs in fn.calls:
            if cs.caller_fn != fn.name:
                errors.append(
                    f"call site in {fn.name} declares caller_fn={cs.caller_fn}"
                )
                continue
            if cs.callee_fn not in triples:
                errors.append(f"{fn.name}: unknown callee {cs.callee_fn}")
                continue
            if cs.pre_block not in blocks or cs.post_block not in blocks:
                errors.append(
                    f"{fn.name}: call site blocks ({cs.pre_block}, {cs.post_block}) missing"
                )
                continue
            callee_triple = triples[cs.callee_fn]
            if cs.is_recursive and not blocks[fn.cfg.entry_block().id].is_poll and not (
                blocks[cs.pre_block].is_poll or fn_map[cs.callee_fn].cfg.entry_block().is_poll
            ):
                errors.append(
                    f"{fn.name}: recursive call to {cs.callee_fn} lacks recursive-entry poll"
                )
            pre_cost = _max_poll_free_cost_to(fn.cfg, blocks, cs.pre_block)
            post_cost = _max_poll_free_cost_from(
                fn.cfg, blocks, cs.post_block, cs.pre_block
            )
            cs_errors = check_call_site(
                pre_cost,
                callee_triple,
                post_cost,
                yield_bound,
                is_recursive=cs.is_recursive,
            )
            errors.extend(f"{fn.name}->{cs.callee_fn}: {msg}" for msg in cs_errors)
            if callee_triple.has_internal_poll:
                max_cost = max(
                    max_cost,
                    pre_cost + callee_triple.entry_to_first_poll,
                    callee_triple.poll_to_poll,
                    callee_triple.last_poll_to_exit + post_cost,
                )
            else:
                max_cost = max(
                    max_cost, pre_cost + callee_triple.full_cost + post_cost
                )

    return YieldBoundVerdict(
        admitted=not errors,
        yield_bound=yield_bound,
        call_interval=call_interval,
        call_bound=call_interval + yield_bound,
        max_reaction_cost=max_cost,
        triples=triples,
        errors=tuple(errors),
    )


def admit_program(
    functions: Sequence[ProgramFunction],
    yield_bound: int,
    call_interval: int,
) -> YieldBoundVerdict:
    """Verify `functions` and raise `YieldBoundError` if any obligation fails."""
    verdict = verify_program(functions, yield_bound, call_interval)
    if not verdict.admitted:
        raise YieldBoundError("; ".join(verdict.errors))
    return verdict


def simulate_invocation_gaps(
    reactions: Sequence[int], call_interval: int, yield_bound: int
) -> tuple[list[int], int]:
    """Simulate the static cost counter matching `ElasticDomain.invocation_gaps`."""
    _require_nat(call_interval, "call_interval")
    _require_nat(yield_bound, "yield_bound")
    call_bound = call_interval + yield_bound
    acc = 0
    gaps: list[int] = []
    for idx, reaction in enumerate(reactions):
        cost = _require_nat(reaction, f"reactions[{idx}]")
        if cost > yield_bound:
            raise YieldBoundError(
                f"reactions[{idx}]={cost} exceeds yield_bound {yield_bound}"
            )
        acc += cost
        if acc >= call_interval:
            if acc > call_bound:
                raise YieldBoundError(
                    f"invocation gap {acc} exceeds call_bound {call_bound}"
                )
            gaps.append(acc)
            acc = 0
    return gaps, acc


def check_tal014_expressiveness(
    schema: CostFacetSchema,
    triple: FnCostTriple,
    *,
    crosses_call: bool,
) -> Tal014ExpressivenessResult:
    """Decide whether `schema` can faithfully express `triple` under `TAL-014`."""
    _require_bool(crosses_call, "crosses_call")
    if schema is CostFacetSchema.TRIPLE_REACTION:
        return Tal014ExpressivenessResult(
            schema=schema,
            expressible=True,
            version_bump_required=False,
            reason="3-tuple (entry_to_first_poll, poll_to_poll, last_poll_to_exit) facet expresses all call shapes",
        )
    if not crosses_call or not triple.has_internal_poll:
        return Tal014ExpressivenessResult(
            schema=schema,
            expressible=True,
            version_bump_required=False,
            reason="no internal-poll call crossing: single scalar cost is exact",
        )
    uniform = (
        triple.entry_to_first_poll == triple.poll_to_poll
        and triple.poll_to_poll == triple.last_poll_to_exit
    )
    if uniform:
        return Tal014ExpressivenessResult(
            schema=schema,
            expressible=True,
            version_bump_required=False,
            reason="uniform triple reduces to a single scalar reaction bound",
        )
    return Tal014ExpressivenessResult(
        schema=schema,
        expressible=False,
        version_bump_required=True,
        reason=(
            "call-crossing internal-poll triple "
            f"({triple.entry_to_first_poll}, {triple.poll_to_poll}, {triple.last_poll_to_exit}) "
            "requires TAL-014 version bump to TripleReactionFacet"
        ),
    )


def inline_call_cfg(
    caller: Cfg, pre_block: str, post_block: str, callee: Cfg
) -> Cfg:
    """Inline `callee` between `pre_block` and `post_block` in `caller` (matching `YieldBound.v`)."""
    c_blocks = validate_cfg(caller)
    validate_cfg(callee)
    if pre_block not in c_blocks or post_block not in c_blocks:
        raise YieldBoundError(f"unknown call-site blocks ({pre_block}, {post_block})")

    callee_entry = callee.entry_block().id
    blocks = tuple(
        replace(b, id=f"caller::{b.id}") for b in caller.blocks
    ) + tuple(
        replace(b, id=f"callee::{b.id}", is_entry=False, is_exit=False)
        for b in callee.blocks
    )

    edges: list[CfgEdge] = [
        replace(e, source=f"caller::{e.source}", target=f"caller::{e.target}")
        for e in caller.edges
        if not (e.source == pre_block and e.target == post_block)
    ]
    edges.append(
        CfgEdge(f"caller::{pre_block}", f"callee::{callee_entry}", is_back_edge=False)
    )
    edges.extend(
        replace(e, source=f"callee::{e.source}", target=f"callee::{e.target}")
        for e in callee.edges
    )
    edges.extend(
        CfgEdge(f"callee::{b.id}", f"caller::{post_block}", is_back_edge=False)
        for b in callee.blocks
        if b.is_exit
    )
    return Cfg(
        name=f"{caller.name}__{callee.name}",
        blocks=blocks,
        edges=tuple(edges),
    )
