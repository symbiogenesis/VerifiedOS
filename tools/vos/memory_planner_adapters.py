# SPDX-License-Identifier: Apache-2.0
"""Pinned optional planner interfaces; the optimizer never owns caller objects.

These adapters check the supplied allocation model, not the frontend's lifetimes.
Unsupported semantics produce no ordinary solution and diagnostics out of band.
External packages are optional and are never imported by the ordinary host gates.
"""

import copy
import hashlib
import importlib
import json
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, cast
from urllib.request import urlopen

from vos.memory_planner import Instance, parse_instance, plan, pool_heights

MINIMALLOC_COMMIT = "9f5cf810fec4494df473c23cffd0567989e81b69"
EXECUTORCH_COMMIT = "420948be0b6895244a7f63742222d2d72d84a31c"
EXECUTORCH_SHA256 = "f141012f46c9a2d409fe22d1629b6bede532fcbc4f6405e0dfef6178c8a32550"
INT64_MAX = (1 << 63) - 1
INT64_MIN = -(1 << 63)


class UnsupportedAdapterError(ValueError):
    """The caller's semantics have no admitted conversion at this boundary."""


def _integer(value: object, label: str, minimum: int = 0,
             maximum: int = INT64_MAX) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise UnsupportedAdapterError(f"{label} must be an integer in [{minimum}, {maximum}]")
    return value


def _failure(message: str, adapter: str) -> dict[str, object]:
    return {"status": "unknown", "adapter": adapter, "findings": [message]}


class MiniInterval(Protocol):
    @property
    def lower(self) -> int: ...
    @property
    def upper(self) -> int: ...


class MiniGap(Protocol):
    lifespan: MiniInterval
    window: MiniInterval | None


class MiniBuffer(Protocol):
    id: str
    lifespan: MiniInterval
    size: int
    alignment: int
    gaps: list[MiniGap]
    offset: int | None
    hint: int | None


class MiniProblem(Protocol):
    buffers: list[MiniBuffer]
    capacity: int


class MiniSolution(Protocol):
    offsets: list[int]
    height: int


class MiniBackend(Protocol):
    def solve(self, problem: MiniProblem) -> MiniSolution | None: ...


class MiniModule(Protocol):
    # Names and keyword arguments deliberately match the pinned pybind API.
    def Interval(self, lower: int, upper: int) -> MiniInterval: ...  # noqa: N802
    def Gap(self, lifespan: MiniInterval, window: MiniInterval | None) -> MiniGap: ...  # noqa: N802
    def Buffer(self, id: str, lifespan: MiniInterval, size: int, alignment: int,  # noqa: A002, N802
               gaps: list[MiniGap], offset: int | None, hint: int | None) -> MiniBuffer: ...
    def Problem(self, buffers: list[MiniBuffer], capacity: int) -> MiniProblem: ...  # noqa: N802
    def Solution(self, offsets: list[int], height: int) -> MiniSolution: ...  # noqa: N802


def _mini_times(interval: MiniInterval) -> tuple[int, int]:
    lower = _integer(interval.lower, "lifespan.lower", INT64_MIN)
    upper = _integer(interval.upper, "lifespan.upper", lower)
    return lower, upper


def minimalloc_instance(problem: MiniProblem) -> Instance:
    """Preserve half-open inactive gaps, fixed positions, order, and any alignment.

Gap windows have spatial semantics that a union of live intervals cannot encode;
they are explicitly unsupported. Hints are advisory and recorded as assumptions.
"""
    capacity = _integer(problem.capacity, "capacity")
    starts = [_mini_times(buffer.lifespan)[0] for buffer in problem.buffers]
    origin = min(starts, default=0)
    buffers: list[dict[str, object]] = []
    for buffer in problem.buffers:
        lower, upper = _mini_times(buffer.lifespan)
        _integer(upper - origin, "normalized lifetime")
        intervals = [(lower, upper)] if lower < upper else []
        for gap in buffer.gaps:
            if gap.window is not None:
                raise UnsupportedAdapterError(f"{buffer.id}: spatial gap windows are unsupported")
            gap_lower, gap_upper = _mini_times(gap.lifespan)
            if gap_lower < lower or gap_upper > upper:
                raise UnsupportedAdapterError(f"{buffer.id}: gap escapes lifespan")
            remaining: list[tuple[int, int]] = []
            for start, end in intervals:
                if gap_upper <= start or gap_lower >= end:
                    remaining.append((start, end))
                else:
                    if start < gap_lower:
                        remaining.append((start, gap_lower))
                    if gap_upper < end:
                        remaining.append((gap_upper, end))
            intervals = remaining
        if buffer.hint is not None:
            _integer(buffer.hint, "hint")
        if buffer.offset is not None:
            _integer(buffer.offset, "offset")
        buffers.append({
            "id": buffer.id, "size": _integer(buffer.size, "size"),
            "alignment": _integer(buffer.alignment, "alignment", 1),
            "intervals": [[start - origin, end - origin] for start, end in intervals],
            "allowed_pools": ["arena"], "fixed_offset": buffer.offset,
            "fixed_pool": "arena" if buffer.offset is not None else None,
        })
    return parse_instance({
        "name": "minimalloc", "pools": [{"id": "arena", "capacity": capacity}],
        "buffers": buffers,
        "assumptions": ["Caller lifetimes and inactive gaps are sound.",
                        "Hints are advisory, never constraints.",
                        f"Time origin is translated by {origin}.",
                        f"MiniMalloc interface commit {MINIMALLOC_COMMIT}."],
    })


def _copy_minimalloc(module: MiniModule, problem: MiniProblem) -> MiniProblem:
    def interval(value: MiniInterval) -> MiniInterval:
        return module.Interval(value.lower, value.upper)
    buffers = [module.Buffer(
        buffer.id, interval(buffer.lifespan), buffer.size, buffer.alignment,
        [module.Gap(interval(gap.lifespan),
                    interval(gap.window) if gap.window is not None else None)
         for gap in buffer.gaps], buffer.offset, buffer.hint,
    ) for buffer in problem.buffers]
    return module.Problem(buffers, problem.capacity)


def minimalloc_from_csv(text: str, module: MiniModule, capacity: int) -> MiniProblem:
    """Read the pinned MiniMalloc columns, including legacy inclusive end values.

Like upstream, this is an unquoted comma-separated format. Unknown columns and
blank interior records are rejected rather than silently discarding information.
Capacity is an external parameter; MiniMalloc CSV does not encode it.
"""
    rows = text.splitlines()
    if not rows:
        raise UnsupportedAdapterError("empty MiniMalloc CSV")
    aliases = {"buffer": "id", "buffer_id": "id", "begin": "lower",
               "start": "lower", "end": "upper"}
    original_columns = rows[0].split(",")
    columns = [aliases.get(name, name) for name in original_columns]
    required = {"id", "lower", "upper", "size"}
    if len(columns) != len(set(columns)) or not required <= set(columns):
        raise UnsupportedAdapterError("duplicate or missing MiniMalloc CSV columns")
    if set(columns) - required - {"alignment", "hint", "gaps", "offset"}:
        raise UnsupportedAdapterError("unknown MiniMalloc CSV columns")
    addend = int("end" in original_columns)
    buffers: list[MiniBuffer] = []
    for line in rows[1:]:
        fields = line.split(",")
        if len(fields) != len(columns):
            raise UnsupportedAdapterError("MiniMalloc CSV record cardinality changed")
        row = dict(zip(columns, fields, strict=True))
        lower = _integer(int(row["lower"]), "lower", INT64_MIN)
        upper = _integer(int(row["upper"]), "upper", INT64_MIN, INT64_MAX - addend) + addend
        gaps: list[MiniGap] = []
        for gap in row.get("gaps", "").split():
            matched = re.fullmatch(r"(\d+)-(\d+)(?:@(\d+):(\d+))?", gap)
            if matched is None:
                raise UnsupportedAdapterError("malformed MiniMalloc gap")
            start = _integer(int(matched[1]), "gap lower")
            end = _integer(int(matched[2]), "gap upper", 0, INT64_MAX - addend) + addend
            window = None
            if matched[3] is not None:
                window = module.Interval(_integer(int(matched[3]), "window lower"),
                                         _integer(int(matched[4]), "window upper"))
            gaps.append(module.Gap(module.Interval(start, end), window))
        hint = _integer(int(row.get("hint", "-1")), "hint", INT64_MIN)
        offset = _integer(int(row["offset"]), "offset") if "offset" in row else None
        buffers.append(module.Buffer(
            row["id"], module.Interval(lower, upper), _integer(int(row["size"]), "size"),
            _integer(int(row.get("alignment", "1")), "alignment", 1), gaps,
            offset, hint if hint >= 0 else None,
        ))
    return module.Problem(buffers, _integer(capacity, "capacity"))


def minimalloc_to_csv(original: str, solution: MiniSolution) -> str:
    """Append or replace only the placement column, retaining all input fields."""
    rows = original.splitlines()
    if not rows or len(rows) - 1 != len(solution.offsets):
        raise UnsupportedAdapterError("solution cardinality differs from original CSV")
    columns = rows[0].split(",")
    existing = columns.index("offset") if "offset" in columns else None
    output = [rows[0] if existing is not None else rows[0] + ",offset"]
    for row, offset in zip(rows[1:], solution.offsets, strict=True):
        _integer(offset, "output offset")
        fields = row.split(",")
        if len(fields) != len(columns):
            raise UnsupportedAdapterError("original CSV cardinality changed")
        if existing is None:
            fields.append(str(offset))
        else:
            fields[existing] = str(offset)
        output.append(",".join(fields))
    return "\n".join(output) + "\n"


class MiniMallocSolver:
    """Replacement for ``solver.solve(problem)`` returning the upstream Solution.

Supply the pinned MiniMalloc module and an existing Solver as the baseline.
Constructor/search controls, cancellation, and timing are not ABI replacements.
The baseline keeps its configured timeout; work_budget bounds additional search.
"""

    def __init__(self, module: MiniModule, baseline: MiniBackend, *,
                 work_budget: int = 0, certify: bool = False) -> None:
        self.module = module
        self.baseline = baseline
        self.work_budget = _integer(work_budget, "work_budget")
        self.certify = certify
        self.last_evidence: dict[str, object] = {}

    def solve(self, problem: MiniProblem) -> MiniSolution | None:
        self.last_evidence = _failure("planning has not completed", "minimalloc")
        try:
            return self._solve(problem)
        except Exception as error:  # Backend errors/timeouts never become infeasibility.
            self.last_evidence = _failure(str(error), "minimalloc")
            return None

    def _solve(self, problem: MiniProblem) -> MiniSolution | None:
        instance = minimalloc_instance(problem)
        baseline = self.baseline.solve(_copy_minimalloc(self.module, problem))
        if baseline is None:
            self.last_evidence = _failure("baseline returned no solution", "minimalloc")
            return None
        if len(baseline.offsets) != len(problem.buffers):
            raise UnsupportedAdapterError("baseline changed buffer cardinality")
        layout = [{"id": buffer.id, "pool": "arena", "offset": offset}
                  for buffer, offset in zip(problem.buffers, baseline.offsets, strict=True)]
        height = _integer(baseline.height, "baseline.height")
        actual_height = max((offset + buffer.size for buffer, offset in
                             zip(problem.buffers, baseline.offsets, strict=True)), default=0)
        if height != actual_height:
            raise UnsupportedAdapterError("baseline height does not match its offsets")
        result = plan(instance, layout, work_budget=self.work_budget, certify=self.certify)
        self.last_evidence = dict(result["evidence"])
        self.last_evidence["adapter"] = f"minimalloc@{MINIMALLOC_COMMIT}"
        placement = result["placement"]
        if placement is None:
            return None
        by_id = {entry["id"]: entry["offset"] for entry in placement}
        output_height = max((by_id[buffer.id] + buffer.size for buffer in problem.buffers), default=0)
        return self.module.Solution([by_id[buffer.id] for buffer in problem.buffers], output_height)


class TensorSpec(Protocol):
    lifetime: list[int | None]
    mem_id: int | None
    mem_offset: int | None
    mem_obj_id: int | None
    alignment: int
    storage_base: TensorSpec | None
    storage_base_offset: int
    shape_dynamism: object
    @property
    def allocated_memory(self) -> int: ...
    def realign(self, new_alignment: int) -> int: ...


class SpecAllocation(Protocol):
    mem_id: int
    mem_obj_id: int
    mem_offset: int


class ExecuTorchResult(Protocol):
    spec_dict: dict[TensorSpec, SpecAllocation]
    bufsizes: list[int]


class Graph(Protocol):
    @property
    def nodes(self) -> Iterable[object]: ...


class GraphModule(Protocol):
    @property
    def graph(self) -> Graph: ...


class ExecuTorchModule(Protocol):
    def greedy(self, alignment: int, specs: set[TensorSpec], graph_module: GraphModule,
               graph_signature: object, extra_padding: int = 0) -> ExecuTorchResult: ...
    def get_node_tensor_specs(self, node: object) -> Iterable[TensorSpec]: ...
    def SpecAllocResult(self, mem_id: int, mem_obj_id: int,  # noqa: N802
                        mem_offset: int) -> SpecAllocation: ...
    def MemoryAlgoResult(self, spec_dict: dict[TensorSpec, SpecAllocation],  # noqa: N802
                         bufsizes: list[int]) -> ExecuTorchResult: ...


class ExecuTorchAlgorithm:
    """Current MemoryPlanningAlgorithmSuite callback, with evidence on the object.

The suite's supplied spec set already applies input/output/mutable-buffer policy.
We never add excluded tensors. Direct storage views are preserved; chains fail
explicitly. The unmodified greedy generator operates on a private graph copy.
"""

    def __init__(self, upstream: ExecuTorchModule, *, work_budget: int = 0) -> None:
        self.upstream = upstream
        self.work_budget = _integer(work_budget, "work_budget")
        self.last_evidence: dict[str, object] = {}
        self.__name__ = "verifiedos_checked_planner"

    def __call__(self, alignment: int, specs: set[TensorSpec],
                 graph_module: GraphModule, graph_signature: object,
                 extra_padding: int = 0) -> ExecuTorchResult:
        self.last_evidence = _failure("planning has not completed", "executorch")
        try:
            return self._plan(alignment, specs, graph_module, graph_signature, extra_padding)
        except Exception as error:  # This legacy callback has no non-success result type.
            self.last_evidence = _failure(str(error), "executorch")
            raise UnsupportedAdapterError(str(error)) from error

    def _plan(self, alignment: int, specs: set[TensorSpec], graph_module: GraphModule,
              graph_signature: object, extra_padding: int) -> ExecuTorchResult:
        _integer(alignment, "alignment", 1)
        _integer(extra_padding, "extra_padding")
        ordered: list[TensorSpec] = []
        for node in graph_module.graph.nodes:
            for spec in self.upstream.get_node_tensor_specs(node):
                if spec in specs and spec not in ordered:
                    ordered.append(spec)
        if set(ordered) != specs:
            raise UnsupportedAdapterError("spec identity is absent from the graph's stable node order")
        # Copy these together: shared references between graph, specs, and aliases
        # must remain shared in the generator's isolated snapshot.
        baseline_order, clone_graph, clone_signature = copy.deepcopy(
            (ordered, graph_module, graph_signature))
        clone_order = copy.deepcopy(ordered)
        for spec in clone_order:
            spec.realign(alignment)
        for index, view in enumerate(clone_order):
            if view.storage_base is None:
                continue
            for other in clone_order[:index]:
                if other.storage_base is not view.storage_base:
                    continue
                if (len(view.lifetime) != 2 or len(other.lifetime) != 2 or
                        any(value is None for value in [*view.lifetime, *other.lifetime])):
                    raise UnsupportedAdapterError("view lifetime is incomplete")
                start, end = (_integer(value, "view lifetime") for value in view.lifetime)
                other_start, other_end = (_integer(value, "view lifetime") for value in other.lifetime)
                spatial = (view.allocated_memory > 0 and other.allocated_memory > 0 and
                           view.storage_base_offset < other.storage_base_offset + other.allocated_memory and
                           other.storage_base_offset < view.storage_base_offset + view.allocated_memory)
                if spatial and start <= other_end and other_start <= end:
                    raise UnsupportedAdapterError("concurrent overlapping sibling views are unsupported by ExecuTorch")
        baseline = self.upstream.greedy(alignment, set(baseline_order), clone_graph,
                                        clone_signature, extra_padding)
        if set(baseline.spec_dict) != set(baseline_order):
            raise UnsupportedAdapterError("baseline changed the policy-filtered spec set")
        allocations = {model_spec: baseline.spec_dict[baseline_spec]
                       for model_spec, baseline_spec in
                       zip(clone_order, baseline_order, strict=True)}
        if not baseline.bufsizes or baseline.bufsizes[0] != 0:
            raise UnsupportedAdapterError("memory pool zero must remain reserved")
        pool_sizes = [_integer(size, "pool size") for size in baseline.bufsizes]
        raw_prefixes = getattr(graph_module, "input_mem_buffer_sizes", None)
        if raw_prefixes is not None and not isinstance(raw_prefixes, list):
            raise UnsupportedAdapterError("input_mem_buffer_sizes must be a list")
        prefixes = [_integer(size, "input pool prefix") for size in (raw_prefixes or [])]
        identifiers = {spec: f"tensor-{index}" for index, spec in enumerate(clone_order)}
        buffers: list[dict[str, object]] = []
        layout: list[dict[str, object]] = []
        active_pools: set[int] = set()
        for spec in clone_order:
            allocation = allocations[spec]
            mem_id = _integer(allocation.mem_id, "mem_id", 1, len(pool_sizes) - 1)
            expected_pool = 1 if spec.mem_id is None else _integer(spec.mem_id, "spec.mem_id", 1)
            if spec.storage_base is not None and spec.mem_id is None:
                parent_pool = spec.storage_base.mem_id
                expected_pool = 1 if parent_pool is None else _integer(parent_pool, "root.mem_id", 1)
            if mem_id != expected_pool:
                raise UnsupportedAdapterError("baseline changed a tensor's assigned pool")
            active_pools.add(mem_id)
            if getattr(spec.shape_dynamism, "name", "") not in ("STATIC", "DYNAMIC_BOUND"):
                raise UnsupportedAdapterError("unbounded or unknown dynamic tensor shape")
            if len(spec.lifetime) != 2:
                raise UnsupportedAdapterError("tensor lifetime must have two endpoints")
            first = _integer(spec.lifetime[0], "first use")
            last = _integer(spec.lifetime[1], "last use", first, INT64_MAX - 1)
            record: dict[str, object] = {
                "id": identifiers[spec], "size": _integer(spec.allocated_memory, "allocated_memory"),
                "alignment": alignment, "intervals": [[first, last + 1]],
                "allowed_pools": [str(mem_id)],
            }
            if spec.storage_base is not None:
                if spec.storage_base not in identifiers or spec.storage_base.storage_base is not None:
                    raise UnsupportedAdapterError("external storage roots and chained views are unsupported")
                record["alias_of"] = identifiers[spec.storage_base]
                record["alias_offset"] = _integer(spec.storage_base_offset, "storage_base_offset")
            elif spec.storage_base_offset != 0:
                raise UnsupportedAdapterError("storage_base_offset has no root")
            buffers.append(record)
            layout.append({"id": identifiers[spec], "pool": str(mem_id),
                           "offset": _integer(allocation.mem_offset, "mem_offset")})
        pools: list[dict[str, object]] = []
        for mem_id in range(1, len(pool_sizes)):
            prefix = prefixes[mem_id] if mem_id < len(prefixes) else 0
            padding = extra_padding if mem_id in active_pools else 0
            capacity = pool_sizes[mem_id] - padding
            if capacity < prefix:
                raise UnsupportedAdapterError("baseline omitted an input pool prefix or padding")
            pools.append({"id": str(mem_id), "capacity": capacity,
                          "reserved": [[0, prefix]] if prefix else []})
        if any(prefixes[len(pool_sizes):]):
            raise UnsupportedAdapterError("baseline omitted a reserved input pool")
        instance = parse_instance({"name": "executorch", "pools": pools, "buffers": buffers,
                                   "assumptions": ["Caller tensor bounds and lifetimes are sound.",
                                                   "The suite already applied input/output policy.",
                                                   f"ExecuTorch interface {EXECUTORCH_COMMIT}."]})
        result = plan(instance, layout, work_budget=self.work_budget)
        self.last_evidence = dict(result["evidence"])
        self.last_evidence["adapter"] = f"executorch@{EXECUTORCH_COMMIT}"
        placement = result["placement"]
        if placement is None:
            raise UnsupportedAdapterError("baseline failed independent placement validation")
        heights = pool_heights(instance, placement)
        offsets = {entry["id"]: entry["offset"] for entry in placement}
        output_sizes = [0] + [heights[str(index)] +
                              (extra_padding if index in active_pools else 0)
                              for index in range(1, len(pool_sizes))]
        if any(new > old for new, old in zip(output_sizes, pool_sizes, strict=True)):
            raise UnsupportedAdapterError("adapter padding worsened an input pool")
        results: dict[TensorSpec, SpecAllocation] = {}
        # A pool is one shared storage object: overlapping placements therefore
        # always share mem_obj_id as required by the upstream verifier.
        for original, cloned in zip(ordered, clone_order, strict=True):
            allocation = allocations[cloned]
            results[original] = self.upstream.SpecAllocResult(
                allocation.mem_id, 0, offsets[identifiers[cloned]])
        # This is the upstream alignment side effect, committed only on success.
        for original in ordered:
            original.realign(alignment)
        return self.upstream.MemoryAlgoResult(results, output_sizes)


def executorch_algorithm(*, work_budget: int = 0) -> ExecuTorchAlgorithm:
    """Load the optional installed package only if its pinned interface matches."""
    upstream = importlib.import_module("executorch.exir.memory_planning")
    if upstream.__file__ is None:
        raise UnsupportedAdapterError("ExecuTorch interface has no inspectable source")
    actual = hashlib.sha256(Path(upstream.__file__).read_bytes()).hexdigest()
    if actual != EXECUTORCH_SHA256:
        raise UnsupportedAdapterError(f"ExecuTorch memory_planning.py must match {EXECUTORCH_COMMIT}")
    return ExecuTorchAlgorithm(cast(ExecuTorchModule, cast(object, upstream)),
                              work_budget=work_budget)


def tflm_demo(root: Path, output: Path) -> dict[str, object]:
    """Compile and run against the real pinned TFLM header, never a stub.

The CLI supplies its native guest output directory. Only the reviewed, hashed
header closure and license are fetched; no upstream source is vendored.
"""
    root, output = root.resolve(), output.resolve()
    if output.is_relative_to(root) or not output.is_relative_to(Path("/root/build")):
        raise ValueError("TFLM guest outputs must stay below /root/build and outside the checkout")
    metadata = json.loads((root / "tools/memory-planner/interfaces.json").read_text(encoding="utf-8"))
    pin = metadata["tflite_micro"]
    output.mkdir(parents=True, exist_ok=True)
    base = f"https://raw.githubusercontent.com/tensorflow/tflite-micro/{pin['commit']}/"
    entries = [{"path": "LICENSE", "sha256": pin["license_sha256"]}, *pin["headers"]]
    for entry in entries:
        relative = Path(entry["path"])
        target = (output / "upstream" / relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(output / "upstream"):
            raise ValueError("upstream manifest path escapes output")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
            # The URL is a repository-owned immutable HTTPS upstream pin.
            with urlopen(base + relative.as_posix(), timeout=30) as response:  # noqa: S310
                content = response.read()
            if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                raise ValueError(f"upstream content hash mismatch: {relative}")
            target.write_bytes(content)
    executable = output / "tflm-demo"
    source = root / "tools/memory-planner/tflm_demo.cpp"
    command = ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
               "-I", str(output / "upstream"), str(source), "-o", str(executable)]
    compiled = subprocess.run(command, cwd=output, capture_output=True, text=True,
                              check=False, timeout=60)
    (output / "compile.log").write_text(compiled.stdout + compiled.stderr,
                                       encoding="utf-8", newline="")
    if compiled.returncode:
        raise ValueError(f"TFLM compilation failed: {compiled.stderr.strip()}")
    executed = subprocess.run([str(executable)], cwd=output, capture_output=True,
                              text=True, check=False, timeout=15)
    (output / "run.log").write_text(executed.stdout + executed.stderr,
                                   encoding="utf-8", newline="")
    if executed.returncode:
        raise ValueError(f"TFLM demo failed: {executed.stderr.strip()}")
    return {"status": "passed", "upstream_commit": pin["commit"],
            "boundary": "compiled MicroMemoryPlanner subclass; no model inference run",
            "output": executed.stdout.strip(), "output_directory": str(output),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "authored_sources_sha256": {
                str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [source, source.with_name("tflm_checked_plan.h"),
                             source.with_name("interfaces.json")]},
            "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()}
