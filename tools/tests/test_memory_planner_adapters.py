# SPDX-License-Identifier: Apache-2.0
"""Adapter contract fixtures; these are not an installed-framework benchmark."""

import copy
from dataclasses import dataclass, field
from enum import Enum
from types import SimpleNamespace
from typing import Any, cast, override
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import memory_planner_adapters as adapter
from vos.memory_planner import Instance, plan


@dataclass
class Interval:
    lower: int
    upper: int


@dataclass
class Gap:
    lifespan: adapter.MiniInterval
    window: adapter.MiniInterval | None


@dataclass
class Buffer:
    id: str
    lifespan: adapter.MiniInterval
    size: int
    alignment: int
    gaps: list[adapter.MiniGap]
    offset: int | None
    hint: int | None


@dataclass
class Problem:
    buffers: list[adapter.MiniBuffer]
    capacity: int


@dataclass
class Solution:
    offsets: list[int]
    height: int


def mini_module() -> adapter.MiniModule:
    return cast(adapter.MiniModule, cast(object, SimpleNamespace(
        Interval=Interval, Gap=Gap, Buffer=Buffer, Problem=Problem, Solution=Solution)))


@dataclass
class Baseline:
    offsets: list[int]
    height: int
    mutate: bool = False
    timeout: bool = False

    def solve(self, problem: adapter.MiniProblem) -> adapter.MiniSolution | None:
        if self.timeout:
            raise TimeoutError("baseline deadline expired")
        if self.mutate:
            problem.buffers[0].size = 0
            problem.buffers[0].gaps.clear()
        return Solution(list(self.offsets), self.height)


def gap_fixed_alignment_and_identity() -> None:
    module = mini_module()
    problem = module.Problem([
        module.Buffer("first", Interval(-3, 4), 6, 3,
                      [Gap(Interval(-1, 2), None)], 0, 99),
        module.Buffer("second", Interval(-1, 2), 6, 3, [], 0, None),
    ], 6)
    original = copy.deepcopy(problem)
    solver = adapter.MiniMallocSolver(module, Baseline([0, 0], 6, mutate=True))
    result = solver.solve(problem)
    ensure(result is not None and result.offsets == [0, 0] and result.height == 6,
           f"inactive gap or fixed offset changed: {solver.last_evidence}")
    ensure(problem == original, "baseline mutation reached caller data")
    ensure(solver.last_evidence["status"] == "checked feasible", "feasibility not checked")
    model = adapter.minimalloc_instance(problem)
    ensure(model.buffers[0].intervals == ((0, 2), (5, 7)), "signed times lost ordering")


def rejected_mini_models_and_bad_baseline() -> None:
    module = mini_module()
    problem = module.Problem([module.Buffer("a", Interval(0, 4), 4, 1,
                                           [Gap(Interval(1, 2), Interval(0, 1))], None, None)], 8)
    solver = adapter.MiniMallocSolver(module, Baseline([0], 4))
    ensure(solver.solve(problem) is None, "spatial gap window was discarded")
    problem.buffers[0].gaps.clear()
    solver = adapter.MiniMallocSolver(module, Baseline([1], 4))
    ensure(solver.solve(problem) is None, "wrong declared height accepted")
    solver = adapter.MiniMallocSolver(module, Baseline([0], 4, timeout=True))
    ensure(solver.solve(problem) is None and solver.last_evidence["status"] == "unknown",
           "timeout became infeasibility")
    problem.buffers[0].lifespan = Interval(adapter.INT64_MIN, adapter.INT64_MAX)
    ensure(solver.solve(problem) is None, "normalization overflow accepted")


def csv_preserves_fields_and_legacy_endpoints() -> None:
    text = "buffer_id,start,end,size,alignment,hint,gaps,offset\na,0,3,4,2,-1,1-2,0\n"
    problem = adapter.minimalloc_from_csv(text, mini_module(), 4)
    ensure(problem.buffers[0].lifespan.upper == 4 and
           problem.buffers[0].gaps[0].lifespan.upper == 3, "inclusive endpoints lost")
    solver = adapter.MiniMallocSolver(mini_module(), Baseline([0], 4))
    result = solver.solve(problem)
    ensure(result is not None, f"CSV fields failed: {solver.last_evidence}")
    if result is None:
        raise AssertionError("result unexpectedly absent")
    ensure(adapter.minimalloc_to_csv(text, result) == text, "CSV fields changed")
    inputs = ["id,start,end,size\na,0,9223372036854775807,1\n",
              "id,lower,upper,size,pool\na,0,1,1,2\n",
              "id,lower,upper,size\na,0,1,1\n\nb,0,1,1\n"]
    for malformed in inputs:
        try:
            adapter.minimalloc_from_csv(malformed, mini_module(), 4)
        except adapter.UnsupportedAdapterError:
            continue
        raise AssertionError("unsafe CSV conversion accepted")


def minimalloc_zero_endpoints_do_not_inherit_extent_optimality() -> None:
    module = mini_module()
    problem = module.Problem([
        module.Buffer("positive", Interval(0, 1), 4, 1, [], None, None),
        module.Buffer("zero", Interval(0, 1), 0, 1, [], None, None),
    ], 100)
    solver = adapter.MiniMallocSolver(module, Baseline([0, 100], 100), certify=True)
    result = solver.solve(problem)
    ensure(result is not None and result.height == 100, "ordinary zero endpoint was lost")
    ensure(solver.last_evidence["status"] == "checked feasible",
           "core extent optimum was claimed for a different ordinary arena height")
    objective = cast(dict[str, object], solver.last_evidence["ordinary_objective"])
    ensure(objective["baseline_height"] == objective["selected_height"] == 100,
           "ordinary before/after heights were not recorded")
    certification = cast(dict[str, object], solver.last_evidence["certification"])
    ensure(certification["status"] == "checked optimal", "scoped core evidence was discarded")


def minimalloc_rejects_an_ordinary_height_regression() -> None:
    module = mini_module()
    problem = module.Problem([
        module.Buffer("positive", Interval(0, 1), 4, 1, [], None, None),
        module.Buffer("zero", Interval(0, 1), 0, 1, [], None, None),
    ], 100)

    def candidate_result(instance: Instance, baseline: object, *, work_budget: int = 0,
                         certify: bool = False) -> dict[str, Any]:
        # A valid core improvement (12 to 4 occupied bytes) with a worse ordinary
        # height (12 to 100). The real core checker accepts this objective change.
        candidates = [[{"id": "positive", "pool": "arena", "offset": 0},
                       {"id": "zero", "pool": "arena", "offset": 100}]] if work_budget else []
        return plan(instance, baseline, candidates=candidates, certify=certify)

    solver = adapter.MiniMallocSolver(module, Baseline([8, 0], 12), work_budget=1)
    with patch.object(adapter, "plan", side_effect=candidate_result):
        result = solver.solve(problem)
    ensure(result is not None and result.height == 12 and result.offsets == [8, 0],
           "adapter deployed an ordinary height regression instead of retaining its baseline")
    objective = cast(dict[str, object], solver.last_evidence["ordinary_objective"])
    ensure(objective["non_regression"] is True and objective["rejected_candidate_height"] == 100,
           "rejected ordinary regression is not diagnosed")


class Dynamism(Enum):
    STATIC = 0
    DYNAMIC_BOUND = 1
    DYNAMIC_UNBOUND = 2


@dataclass(eq=False)
class Spec:
    size: int
    lifetime: list[int | None]
    mem_id: int | None = None
    mem_offset: int | None = None
    mem_obj_id: int | None = None
    alignment: int = 1
    storage_base: adapter.TensorSpec | None = None
    storage_base_offset: int = 0
    shape_dynamism: object = Dynamism.STATIC

    @property
    def allocated_memory(self) -> int:
        return (self.size + self.alignment - 1) // self.alignment * self.alignment

    def realign(self, new_alignment: int) -> int:
        self.alignment = new_alignment
        return self.allocated_memory


@dataclass
class Allocation:
    mem_id: int
    mem_obj_id: int
    mem_offset: int


@dataclass
class AlgoResult:
    spec_dict: dict[adapter.TensorSpec, adapter.SpecAllocation]
    bufsizes: list[int]


@dataclass
class Graph:
    nodes: list[object]


@dataclass
class Module:
    graph: Graph
    input_mem_buffer_sizes: list[int] = field(default_factory=lambda: [0, 0])


class Upstream:
    """Own contract fixture, never substituted for external operational evidence."""

    def __init__(self, mutate: bool = False) -> None:
        self.mutate = mutate

    def get_node_tensor_specs(self, node: object) -> list[adapter.TensorSpec]:
        return [cast(adapter.TensorSpec, node)]

    def greedy(self, alignment: int, specs: set[adapter.TensorSpec],
               graph_module: adapter.GraphModule, graph_signature: object,
               extra_padding: int = 0) -> adapter.ExecuTorchResult:
        ordered = [cast(adapter.TensorSpec, node) for node in graph_module.graph.nodes
                   if node in specs]
        sizes = list(cast(Module, graph_module).input_mem_buffer_sizes)
        results: dict[adapter.TensorSpec, adapter.SpecAllocation] = {}
        for spec in ordered:
            spec.realign(alignment)
            if spec.storage_base is not None:
                root = results[spec.storage_base]
                results[spec] = Allocation(root.mem_id, 0, root.mem_offset + spec.storage_base_offset)
                continue
            mem_id = spec.mem_id or 1
            sizes.extend([0] * max(0, mem_id - len(sizes) + 1))
            offset = sizes[mem_id]
            sizes[mem_id] += spec.allocated_memory
            results[spec] = Allocation(mem_id, 0, offset)
        for mem_id in {result.mem_id for result in results.values()}:
            sizes[mem_id] += extra_padding
        if self.mutate and len(ordered) > 1:
            ordered[1].lifetime = [100, 100]
            results[ordered[1]].mem_offset = results[ordered[0]].mem_offset
        return AlgoResult(results, sizes)

    # Preserve actual framework factory names in the fixture.
    def SpecAllocResult(self, mem_id: int, mem_obj_id: int,  # noqa: N802
                        mem_offset: int) -> adapter.SpecAllocation:
        return Allocation(mem_id, mem_obj_id, mem_offset)

    def MemoryAlgoResult(self, spec_dict: dict[adapter.TensorSpec, adapter.SpecAllocation],  # noqa: N802
                         bufsizes: list[int]) -> adapter.ExecuTorchResult:
        return AlgoResult(spec_dict, bufsizes)


def suite_return_identity_pools_padding_and_policy() -> None:
    first, second = Spec(16, [0, 0]), Spec(16, [1, 1])
    other = Spec(16, [0, 1], mem_id=2, shape_dynamism=Dynamism.DYNAMIC_BOUND)
    excluded = Spec(32, [0, 1])
    module = Module(Graph([first, excluded, second, other]), [0, 16, 32])
    specs: set[adapter.TensorSpec] = {first, second, other}
    callback = adapter.ExecuTorchAlgorithm(Upstream(), work_budget=30000)
    result = callback(16, specs, module, None, 4)
    ensure(set(result.spec_dict) == specs and excluded.mem_offset is None,
           "input/output policy or result keys changed")
    ensure(result.bufsizes == [0, 36, 52], f"pool prefix/padding changed: {result.bufsizes}")
    ensure(result.spec_dict[first].mem_offset == result.spec_dict[second].mem_offset == 16,
           "disjoint lifetimes did not reuse backing")
    ensure(first.mem_offset is None and second.mem_offset is None and first.alignment == 16,
           "callback applied suite-owned output mutations")
    ensure(module.input_mem_buffer_sizes == [0, 16, 32], "baseline mutated graph prefix")


def aliases_and_unsupported_views() -> None:
    root = Spec(32, [0, 2], mem_id=2)
    view = Spec(16, [1, 1], storage_base=root, storage_base_offset=16)
    module = Module(Graph([root, view]), [0, 0, 0])
    callback = adapter.ExecuTorchAlgorithm(Upstream())
    result = callback(16, {root, view}, module, None, 0)
    ensure(result.spec_dict[view].mem_id == 2 and
           result.spec_dict[view].mem_offset == result.spec_dict[root].mem_offset + 16,
           "view root or relative offset changed")
    sibling = Spec(16, [1, 1], storage_base=root, storage_base_offset=16)
    module.graph.nodes.append(sibling)
    try:
        callback(16, {root, view, sibling}, module, None, 0)
    except adapter.UnsupportedAdapterError:
        ensure(callback.last_evidence["status"] == "unknown", "unsupported has a checked claim")
    else:
        raise AssertionError("overlapping sibling views accepted against ExecuTorch contract")


def lifetime_mutation_and_unbounded_shapes_fail_closed() -> None:
    first, second = Spec(16, [0, 2]), Spec(16, [0, 2])
    module = Module(Graph([first, second]))
    callback = adapter.ExecuTorchAlgorithm(Upstream(mutate=True))
    try:
        callback(16, {first, second}, module, None, 0)
    except adapter.UnsupportedAdapterError:
        ensure(second.lifetime == [0, 2], "baseline mutation reached caller lifetime")
    else:
        raise AssertionError("baseline altered the instance being checked")
    second.shape_dynamism = Dynamism.DYNAMIC_UNBOUND
    callback = adapter.ExecuTorchAlgorithm(Upstream())
    try:
        callback(16, {first, second}, module, None, 0)
    except adapter.UnsupportedAdapterError:
        return
    raise AssertionError("unbounded tensor acquired a finite plan")


def inclusive_lifetimes_and_overflow() -> None:
    first, second = Spec(16, [0, 1]), Spec(16, [1, 2])
    module = Module(Graph([first, second]))
    callback = adapter.ExecuTorchAlgorithm(Upstream(), work_budget=5000)
    result = callback(16, {first, second}, module, None, 0)
    ensure(result.spec_dict[first].mem_offset != result.spec_dict[second].mem_offset,
           "inclusive touching lifetimes treated as disjoint")
    second.lifetime = [1, adapter.INT64_MAX]
    try:
        callback(16, {first, second}, module, None, 0)
    except adapter.UnsupportedAdapterError:
        return
    raise AssertionError("inclusive endpoint conversion overflow accepted")


class ZeroEndpointUpstream(Upstream):
    @override
    def greedy(self, alignment: int, specs: set[adapter.TensorSpec],
               graph_module: adapter.GraphModule, graph_signature: object,
               extra_padding: int = 0) -> adapter.ExecuTorchResult:
        result = super().greedy(alignment, specs, graph_module, graph_signature, extra_padding)
        for spec, allocation in result.spec_dict.items():
            if spec.allocated_memory == 0:
                allocation.mem_offset = 100
        result.bufsizes[1] = 100 + extra_padding
        return result


def executorch_zero_endpoints_remain_inside_returned_pool() -> None:
    positive, zero = Spec(4, [0, 1]), Spec(0, [0, 1])
    module = Module(Graph([positive, zero]))
    callback = adapter.ExecuTorchAlgorithm(ZeroEndpointUpstream())
    result = callback(1, {positive, zero}, module, None, 4)
    ensure(result.bufsizes == [0, 104], "ordinary pool omits zero endpoint or padding")
    ensure(result.spec_dict[zero].mem_offset == 100, "baseline zero endpoint changed")
    ensure(all(allocation.mem_offset + spec.allocated_memory <= result.bufsizes[allocation.mem_id]
               for spec, allocation in result.spec_dict.items()),
           "returned tensor endpoint lies outside its returned pool")
    objective = cast(dict[str, object], callback.last_evidence["ordinary_objective"])
    ensure(objective["baseline_pool_sizes"] == objective["selected_pool_sizes"] == [0, 104],
           "ordinary pool sizes were not recorded separately from core extents")


def cases() -> list[Case]:
    return [Case("MiniMalloc gap/fixed/alignment/identity", gap_fixed_alignment_and_identity),
            Case("MiniMalloc unsupported and invalid baseline", rejected_mini_models_and_bad_baseline),
            Case("MiniMalloc CSV endpoint and field preservation", csv_preserves_fields_and_legacy_endpoints),
            Case("MiniMalloc zero endpoint optimality scope", minimalloc_zero_endpoints_do_not_inherit_extent_optimality),
            Case("MiniMalloc ordinary height non-regression", minimalloc_rejects_an_ordinary_height_regression),
            Case("ExecuTorch suite identity/pools/padding/policy", suite_return_identity_pools_padding_and_policy),
            Case("ExecuTorch storage view constraints", aliases_and_unsupported_views),
            Case("ExecuTorch mutation isolation and bounds", lifetime_mutation_and_unbounded_shapes_fail_closed),
            Case("ExecuTorch inclusive endpoint overflow", inclusive_lifetimes_and_overflow),
            Case("ExecuTorch zero endpoint pool bounds", executorch_zero_endpoints_remain_inside_returned_pool)]
