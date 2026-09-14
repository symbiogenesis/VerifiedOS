# SPDX-License-Identifier: Apache-2.0
"""Bounded finite placement encoding for the existing LRAT certificate ecosystem.

Each buffer selects one legal pool/offset. Binary clauses exclude conflicting
placements and inconsistent alias views. A final finite group selects a vector
of pool heights satisfying the requested total objective; binary clauses require
every chosen extent to fit it. Both encoding directions matter for UNSAT transfer.

Search and certificate acceptance are external: pinned CaDiCaL produces LRAT and
pinned lrat_isa checks it. No Python LRAT checker is implemented here. Ordinary
placements always pass the independent portable checker. These tools are optional
off-device research, outside the production optimizer restrictions' admission path.
"""

import hashlib
import itertools
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from vos import env
from vos import memory_planner as planner

ENCODING_VERSION = "portable-placement-one-hot-height-vector-v1"
MANIFEST = "tools/memory-planner/certificates.json"


class CertificateError(ValueError):
    """Malformed input or rejected certificate cannot establish a checked claim."""


class EncodingLimitError(CertificateError):
    """Finite encoding exceeds a declared budget; the original question is unknown."""


@dataclass(frozen=True)
class Limits:
    max_domain_values: int = 4096
    max_variables: int = 20000
    max_clauses: int = 200000
    max_work: int = 1000000
    max_certificate_bytes: int = 32 * 1024 * 1024


DEFAULT_LIMITS = Limits()
# Short public name retained for callers that treat a budget stop as a category.
EncodingLimit = EncodingLimitError


@dataclass(frozen=True)
class Encoding:
    instance_digest: str
    objective_bound: int | None
    pool_limits: tuple[tuple[str, int], ...]
    buffer_choices: tuple[tuple[tuple[str, int], ...], ...]
    groups: tuple[tuple[int, ...], ...]
    height_vectors: tuple[tuple[int, ...], ...]
    clauses: tuple[tuple[int, ...], ...]
    variable_count: int
    work: int

    def dimacs(self) -> str:
        return (f"p cnf {self.variable_count} {len(self.clauses)}\n" +
                "".join(" ".join(map(str, clause)) + (" " if clause else "") + "0\n"
                        for clause in self.clauses))

    def identity(self) -> dict[str, Any]:
        binding = asdict(self)
        binding["version"] = ENCODING_VERSION
        binding["cnf_sha256"] = _sha(self.dimacs().encode())
        return {**binding, "encoding_sha256": _sha(_json(binding))}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _number(value: object, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > planner.MAX_INTEGER:
        raise CertificateError(f"{name}: expected integer in [{minimum}, {planner.MAX_INTEGER}]")
    return value


def _snapshot(instance: planner.Instance) -> planner.Instance:
    return planner.parse_instance(asdict(instance))


def _pool_limits(instance: planner.Instance, limits: dict[str, int] | None) -> dict[str, int]:
    capacities = {pool.id: pool.capacity for pool in instance.pools}
    if limits is None:
        return capacities
    if set(limits) != set(capacities):
        raise CertificateError("pool_limits must name every pool exactly once")
    result = {key: _number(limits[key], "pool limit") for key in capacities}
    if any(result[key] > capacity for key, capacity in capacities.items()):
        raise CertificateError("pool limit exceeds physical capacity")
    return result


def encode(instance: planner.Instance, *, objective_bound: int | None = None,
           pool_limits: dict[str, int] | None = None, limits: Limits = DEFAULT_LIMITS) -> Encoding:
    """Encode ALL legal layouts at the explicit bound; never truncate a domain.

    objective_bound is a nonnegative upper bound on the SUM of pool extents.
    None asks pure feasibility. Reservations charge extent even in empty pools;
    zero-sized buffer addresses remain observable and range to physical capacity.
    """
    instance = _snapshot(instance)
    for name, value in asdict(limits).items():
        _number(value, name, 1)
    if objective_bound is not None:
        _number(objective_bound, "objective_bound", -1)
    caps = _pool_limits(instance, pool_limits)
    pools = {pool.id: pool for pool in instance.pools}
    work = 0
    clauses: list[tuple[int, ...]] = []
    groups: list[tuple[int, ...]] = []
    next_variable = 1

    def charge(amount: int = 1) -> None:
        nonlocal work
        work += amount
        if work > limits.max_work:
            raise EncodingLimit("encoding exceeds max_work; no partial CNF is returned")

    def clause(*literals: int) -> None:
        charge(len(literals) + 1)
        if len(clauses) >= limits.max_clauses:
            raise EncodingLimit("encoding exceeds max_clauses")
        clauses.append(literals)

    def group(count: int) -> tuple[int, ...]:
        nonlocal next_variable
        if next_variable - 1 + count > limits.max_variables:
            raise EncodingLimit("encoding exceeds max_variables")
        variables = tuple(range(next_variable, next_variable + count))
        next_variable += count
        groups.append(variables)
        clause(*variables)
        for left, right in itertools.combinations(variables, 2):
            clause(-left, -right)
        return variables

    all_choices: list[tuple[tuple[str, int], ...]] = []
    for buffer in instance.buffers:
        choices: list[tuple[str, int]] = []
        for pool_id in buffer.allowed_pools:
            charge()
            if buffer.fixed_pool not in (None, pool_id):
                continue
            maximum = (caps[pool_id] if buffer.size else pools[pool_id].capacity) - buffer.size
            if maximum < 0:
                continue
            if buffer.fixed_offset is not None:
                candidates: range | tuple[int, ...] = ((buffer.fixed_offset,)
                    if buffer.fixed_offset <= maximum else ())
                count = len(candidates)
            else:
                count = maximum // buffer.alignment + 1
                candidates = range(0, maximum + 1, buffer.alignment)
            # Charge the full domain before traversing it, including values that
            # will be rejected by reservations. Large capacities fail promptly.
            if count > limits.max_domain_values or len(choices) + count > limits.max_domain_values:
                raise EncodingLimit(f"{buffer.id}: complete placement domain exceeds max_domain_values")
            charge(count)
            for offset in candidates:
                if offset % buffer.alignment:
                    continue
                charge(len(pools[pool_id].reserved))
                if buffer.size and any(max(offset, start) < min(offset + buffer.size, end)
                                       for start, end in pools[pool_id].reserved):
                    continue
                choices.append((pool_id, offset))
        all_choices.append(tuple(choices))
        group(len(choices))
    for i, left in enumerate(instance.buffers):
        for j in range(i):
            right = instance.buffers[j]
            charge(1 + len(left.intervals) * len(right.intervals))
            same_storage = (left.alias_of or left.id) == (right.alias_of or right.id)
            coexist = tuple(sorted((left.id, right.id))) in instance.conflicts or any(
                max(ls, rs) < min(le, re)
                for ls, le in left.intervals for rs, re in right.intervals)
            for left_index, (lp, lo) in enumerate(all_choices[i]):
                for right_index, (rp, ro) in enumerate(all_choices[j]):
                    charge()
                    inconsistent_alias = ((left.alias_of == right.id and
                                           (lp != rp or lo != ro + left.alias_offset)) or
                                          (right.alias_of == left.id and
                                           (lp != rp or ro != lo + right.alias_offset)))
                    conflict = (not same_storage and coexist and lp == rp and left.size > 0
                                and right.size > 0 and max(lo, ro) < min(lo + left.size, ro + right.size))
                    if inconsistent_alias or conflict:
                        clause(-groups[i][left_index], -groups[j][right_index])
    vectors: list[tuple[int, ...]] = []
    if objective_bound is not None:
        height_domains: list[tuple[int, ...]] = []
        count = 1
        for pool in instance.pools:
            minimum = max((end for _, end in pool.reserved), default=0)
            values = {minimum} if minimum <= caps[pool.id] else set()
            for buffer, domain_choices in zip(instance.buffers, all_choices, strict=True):
                charge(len(domain_choices))
                if buffer.size:
                    values.update(offset + buffer.size for chosen_pool, offset in domain_choices
                                  if chosen_pool == pool.id and offset + buffer.size >= minimum)
            height_domains.append(tuple(sorted(values)))
            count *= len(values)
            if count > limits.max_domain_values:
                raise EncodingLimit("complete pool-height product exceeds max_domain_values")
        charge(count * max(1, len(instance.pools)))
        vectors = [vector for vector in itertools.product(*height_domains)
                   if sum(vector) <= objective_bound]
        height_variables = group(len(vectors))
        for i, buffer in enumerate(instance.buffers):
            for choice_index, (pool_id, offset) in enumerate(all_choices[i]):
                if not buffer.size:
                    continue
                pool_index = next(k for k, pool in enumerate(instance.pools) if pool.id == pool_id)
                for height_variable, vector in zip(height_variables, vectors, strict=True):
                    charge()
                    if offset + buffer.size > vector[pool_index]:
                        clause(-groups[i][choice_index], -height_variable)
    elif any(max((end for _, end in pool.reserved), default=0) > caps[pool.id]
             for pool in instance.pools):
        clause()
    return Encoding(planner.instance_digest(instance), objective_bound, tuple(caps.items()),
                    tuple(all_choices), tuple(groups), tuple(vectors), tuple(clauses),
                    next_variable - 1, work)


def assignment_for_placement(instance: planner.Instance, encoding: Encoding,
                             placement: object) -> tuple[int, ...]:
    """Construct the completeness witness, including exact attained pool heights."""
    instance = _snapshot(instance)
    if encoding.instance_digest != planner.instance_digest(instance):
        raise CertificateError("encoding belongs to a different instance")
    findings = planner.check_placement(instance, placement)
    if findings:
        raise CertificateError("invalid placement: " + "; ".join(findings))
    if not isinstance(placement, list):
        raise CertificateError("placement must be a list")
    rows = {row["id"]: row for row in placement}
    selected = set()
    for i, buffer in enumerate(instance.buffers):
        value = (rows[buffer.id]["pool"], rows[buffer.id]["offset"])
        try:
            index = encoding.buffer_choices[i].index(value)
        except ValueError as error:
            raise CertificateError("placement exceeds encoded pool limits") from error
        selected.add(encoding.groups[i][index])
    heights = planner.pool_heights(instance, placement)
    if encoding.objective_bound is not None:
        vector = tuple(heights[pool.id] for pool in instance.pools)
        try:
            index = encoding.height_vectors.index(vector)
        except ValueError as error:
            raise CertificateError("placement exceeds encoded objective") from error
        selected.add(encoding.groups[-1][index])
    return tuple(variable if variable in selected else -variable
                 for variable in range(1, encoding.variable_count + 1))


def decode_assignment(instance: planner.Instance, encoding: Encoding,
                      literals: list[int]) -> planner.Placement:
    """Decode an untrusted SAT witness and independently check its actual layout."""
    instance = _snapshot(instance)
    if encoding.instance_digest != planner.instance_digest(instance):
        raise CertificateError("encoding belongs to a different instance")
    values: dict[int, bool] = {}
    for literal in literals:
        if type(literal) is not int or not 0 < abs(literal) <= encoding.variable_count:
            raise CertificateError("SAT assignment contains an invalid literal")
        if abs(literal) in values and values[abs(literal)] != (literal > 0):
            raise CertificateError("SAT assignment contradicts itself")
        values[abs(literal)] = literal > 0
    if set(values) != set(range(1, encoding.variable_count + 1)):
        raise CertificateError("SAT assignment is incomplete")
    if any(not any(values[abs(literal)] == (literal > 0) for literal in clause)
           for clause in encoding.clauses):
        raise CertificateError("SAT assignment does not satisfy the encoded clauses")
    placement = []
    for i, buffer in enumerate(instance.buffers):
        selected = [j for j, variable in enumerate(encoding.groups[i]) if values[variable]]
        if len(selected) != 1:
            raise CertificateError("SAT assignment does not choose exactly one position")
        pool_id, offset = encoding.buffer_choices[i][selected[0]]
        placement.append({"id": buffer.id, "pool": pool_id, "offset": offset})
    findings = planner.check_placement(instance, placement)
    heights = planner.pool_heights(instance, placement) if not findings else {}
    if findings or any(heights[p] > cap for p, cap in encoding.pool_limits):
        raise CertificateError("decoded candidate failed independent placement validation")
    if encoding.objective_bound is not None and sum(heights.values()) > encoding.objective_bound:
        raise CertificateError("decoded candidate exceeds the actual objective")
    return placement


def workspace(root: Path) -> Path:
    result = (env.lane_root(env.lane_of(root)) / "memory-certificates").resolve()
    if not result.is_relative_to(Path("/root/build")) or result.is_relative_to(root.resolve()):
        raise CertificateError("external checker outputs require this lane's native /root/build directory")
    return result


def _run(command: list[str], cwd: Path, log: str, *, timeout: int = 60,
         accepted: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            check=False, timeout=timeout)
    (cwd / log).write_text(result.stdout + result.stderr, encoding="utf-8", newline="")
    if result.returncode not in accepted:
        raise CertificateError(f"command failed with {result.returncode}: {command[0]}; "
                               f"{result.stderr[-2000:]}; see {cwd / log}")
    return result


def setup(root: Path) -> dict[str, Any]:
    """Fetch pinned MIT-licensed upstreams into this lane and compile native tools."""
    root = root.resolve()
    output = workspace(root)
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    checker = manifest["checker"]
    checker_dir = output / "lrat_isa"
    for entry in checker["files"]:
        relative = Path(entry["path"])
        target = (checker_dir / relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(checker_dir):
            raise CertificateError("upstream checker path escapes owned output")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and _sha(target.read_bytes()) == entry["sha256"]:
            continue
        address = f"https://raw.githubusercontent.com/lammich/lrat_isa/{checker['commit']}/{relative.as_posix()}"
        with urlopen(address, timeout=30) as response:
            data = response.read(1024 * 1024)
        if _sha(data) != entry["sha256"]:
            raise CertificateError(f"upstream checker hash mismatch: {relative}")
        target.write_bytes(data)
    clang = shutil.which("clang++")
    if clang is None:
        raise CertificateError("clang++ is required to compile the verified LLVM checker")
    code = checker_dir / "code"
    harness = root / "tools/memory-planner/certificates/checker_main.cpp"
    _run([clang, "-std=c++20", "-O2", "-I", str(code), str(harness),
          "lib_isabelle_llvm.cpp", "lrat_isa_export.ll", "-o", "lrat_isa"], code, "build.log")
    producer = manifest["producer"]
    producer_dir = output / "cadical"
    if not producer_dir.exists():
        producer_dir.mkdir()
        _run(["git", "init", "--quiet"], producer_dir, "init.log")
        _run(["git", "remote", "add", "origin", producer["repository"]], producer_dir, "remote.log")
        _run(["git", "fetch", "--depth", "1", "origin", producer["commit"]], producer_dir, "fetch.log")
        _run(["git", "checkout", "--detach", "FETCH_HEAD"], producer_dir, "checkout.log")
    head = _run(["git", "rev-parse", "HEAD"], producer_dir, "head.log").stdout.strip()
    if head != producer["commit"] or _sha((producer_dir / "LICENSE").read_bytes()) != producer["license_sha256"]:
        raise CertificateError("producer checkout or license does not match reviewed pin")
    _run(["git", "diff", "--exit-code", "HEAD", "--"], producer_dir, "source-check.log")
    _run(["./configure"], producer_dir, "configure.log")
    _run(["make", "-j2"], producer_dir, "build.log", timeout=180)
    executables = {"checker": code / "lrat_isa", "producer": producer_dir / "build/cadical"}
    result = {"manifest_sha256": _sha((root / MANIFEST).read_bytes()),
              "pins": {"checker": checker["commit"], "producer": producer["commit"]},
              "executables": {key: {"path": str(path), "sha256": _sha(path.read_bytes())}
                              for key, path in executables.items()},
              "compiler": {"path": clang, "sha256": _sha(Path(clang).resolve().read_bytes())},
              "harness_sha256": _sha(harness.read_bytes()),
              "checker_endpoint": checker["proof_endpoint"]}
    (output / "toolchain.json").write_bytes(_json(result))
    return result


def _tools(root: Path) -> dict[str, Any]:
    """Check all immutable checker inputs and recorded binaries again at every use."""
    output = workspace(root)
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    receipt = json.loads((output / "toolchain.json").read_text(encoding="utf-8"))
    if receipt["manifest_sha256"] != _sha((root / MANIFEST).read_bytes()):
        raise CertificateError("toolchain manifest changed; run setup")
    if receipt["checker_endpoint"] != manifest["checker"]["proof_endpoint"]:
        raise CertificateError("checker endpoint differs from the reviewed manifest")
    if receipt["harness_sha256"] != _sha((root / "tools/memory-planner/certificates/checker_main.cpp").read_bytes()):
        raise CertificateError("checker I/O harness changed; run setup")
    for entry in manifest["checker"]["files"]:
        path = output / "lrat_isa" / entry["path"]
        if _sha(path.read_bytes()) != entry["sha256"]:
            raise CertificateError(f"pinned checker source changed: {entry['path']}")
    expected = {"checker": output / "lrat_isa/code/lrat_isa",
                "producer": output / "cadical/build/cadical"}
    for role, path in expected.items():
        item = receipt["executables"][role]
        if item["path"] != str(path) or item["sha256"] != _sha(path.read_bytes()):
            raise CertificateError(f"{role} executable differs from checked build receipt")
        if receipt["pins"][role] != manifest[role]["commit"]:
            raise CertificateError(f"{role} pin changed")
    return receipt


def _process(command: list[str], directory: Path, log: str, *, timeout: int,
             file_limit: int) -> subprocess.CompletedProcess[str]:
    """Bound native solver/checker memory, output file size, CPU, and wall time."""
    limiter = shutil.which("prlimit")
    if limiter is None:
        raise CertificateError("prlimit is required for bounded optional external work")
    args = [limiter, "--as=1073741824", f"--fsize={file_limit}", f"--cpu={timeout}", "--", *command]
    # A file bounds output too: capture_output would let a failing external tool
    # allocate unlimited Python memory before its resource limit takes effect.
    path = directory / log
    with path.open("wb") as output:
        completed = subprocess.run(args, cwd=directory, stdout=output, stderr=subprocess.STDOUT,
                                   check=False, timeout=timeout + 2)
    data = path.read_bytes()
    if len(data) > file_limit:
        raise EncodingLimit("external log exceeds bounded output size")
    return subprocess.CompletedProcess(command, completed.returncode,
                                       data.decode("utf-8", errors="replace"), "")


def _source_identity(root: Path) -> dict[str, str]:
    names = ("tools/vos/memory_planner.py", "tools/vos/memory_planner_certificates.py",
             "tools/memory-planner/certificates/checker_main.cpp")
    return {name: _sha((root / name).read_bytes()) for name in names}


def certify(instance: planner.Instance, candidate: object, root: Path, *,
            certificate_path: Path | None = None, pool_limits: dict[str, int] | None = None,
            limits: Limits = DEFAULT_LIMITS, conflict_budget: int = 10000,
            timeout: int = 30) -> dict[str, Any]:
    """Keep checked feasibility while asking the real LRAT checker about optimality.

    None asks pure feasibility of the given pools; a supplied candidate asks to
    refute every strictly smaller SUM of extents. A supplied LRAT file bypasses
    search but never encoding regeneration or independent certificate checking.
    SAT counterexamples are decoded and independently checked, never deployed.
    """
    instance = _snapshot(instance)
    root = root.resolve()
    _number(conflict_budget, "conflict_budget")
    _number(timeout, "timeout", 1)
    caps = _pool_limits(instance, pool_limits)
    objective: dict[str, Any] = {"metric": "sum-pool-extents-in-bytes", "pool_limits": caps}
    base_evidence: dict[str, Any] = {
        "status": "unknown", "certificate_status": "unknown",
        "instance_digest": planner.instance_digest(instance), "encoding_version": ENCODING_VERSION,
        "objective": objective,
        "limits": asdict(limits), "conflict_budget": conflict_budget, "timeout_seconds": timeout,
        "assumptions": [*instance.assumptions,
                        "Caller size, alias and coexistence facts are sound.",
                        "Python domain extraction and DIMACS emission implement the finite encoding.",
                        "Authored I/O, native compiler retargeting and runtime preserve upstream LLVM semantics.",
                        "This is optional off-device research, not production optimizer admission."],
    }
    retained = None
    bound = None
    if candidate is not None:
        findings = planner.check_placement(instance, candidate)
        if findings:
            return {"placement": None, "evidence": {**base_evidence,
                    "findings": findings, "reason": "invalid candidate refused before optional work"}}
        if not isinstance(candidate, list):
            raise CertificateError("candidate must be a list")
        retained = [dict(row) for row in candidate]
        heights = planner.pool_heights(instance, retained)
        if any(heights[pool] > cap for pool, cap in caps.items()):
            raise CertificateError("candidate exceeds specified pool limits")
        bound = sum(heights.values()) - 1
        base_evidence.update(status="checked feasible", pool_heights=heights)
    objective["strictly_better_query_bound"] = bound
    result: dict[str, Any] = {"placement": retained, "evidence": base_evidence}
    try:
        encoding = encode(instance, objective_bound=bound, pool_limits=caps, limits=limits)
        identity = encoding.identity()
        base_evidence.update(encoding_sha256=identity["encoding_sha256"],
                             cnf_sha256=identity["cnf_sha256"],
                             variables=encoding.variable_count, clauses=len(encoding.clauses),
                             encoding_work=encoding.work, source_sha256=_source_identity(root))
        toolchain = _tools(root)
        base_evidence["toolchain"] = toolchain
        output = workspace(root)
        directory = Path(tempfile.mkdtemp(prefix=identity["encoding_sha256"][:12] + "-", dir=output))
        cnf_path, lrat_path = directory / "instance.cnf", directory / "proof.lrat"
        cnf_path.write_text(encoding.dimacs(), encoding="utf-8", newline="")
        (directory / "encoding.json").write_bytes(_json(identity))
        base_evidence["artifacts"] = {"directory": str(directory), "cnf": str(cnf_path),
                                      "lrat": str(lrat_path)}
        if certificate_path is not None:
            if certificate_path.stat().st_size > limits.max_certificate_bytes:
                raise EncodingLimit("supplied certificate exceeds max_certificate_bytes")
            with certificate_path.open("rb") as stream:
                certificate = stream.read(limits.max_certificate_bytes + 1)
            if len(certificate) > limits.max_certificate_bytes:
                raise EncodingLimit("supplied certificate grew beyond its byte budget")
            lrat_path.write_bytes(certificate)
        else:
            producer = toolchain["executables"]["producer"]["path"]
            solved = _process([producer, "-q", "--lrat", "-c",
                               str(conflict_budget), str(cnf_path), str(lrat_path)],
                              directory, "producer.log", timeout=timeout,
                              file_limit=limits.max_certificate_bytes)
            base_evidence["producer_returncode"] = solved.returncode
            if solved.returncode == 10 and "s SATISFIABLE" in solved.stdout.splitlines():
                literals = [int(word) for line in solved.stdout.splitlines() if line.startswith("v ")
                            for word in line[2:].split() if word != "0"]
                result["counterexample"] = decode_assignment(instance, encoding, literals)
                base_evidence["reason"] = "independently checked satisfying layout refutes the requested bound"
                if retained is None:
                    result["placement"] = result["counterexample"]
                    base_evidence["status"] = "checked feasible"
                return result
            if solved.returncode != 20 or "s UNSATISFIABLE" not in solved.stdout.splitlines():
                base_evidence["reason"] = "producer stopped without a certificate; infeasibility is unknown"
                return result
        if lrat_path.stat().st_size > limits.max_certificate_bytes:
            raise EncodingLimit("produced certificate exceeds max_certificate_bytes")
        base_evidence["certificate_sha256"] = _sha(lrat_path.read_bytes())
        # Recompute CNF after external work; producer mutation cannot change the
        # formula whose identity and placement encoding this receipt certifies.
        if _sha(cnf_path.read_bytes()) != identity["cnf_sha256"]:
            raise CertificateError("producer changed the encoded formula")
        if _tools(root) != toolchain:
            raise CertificateError("toolchain build receipt changed during external work")
        checker = toolchain["executables"]["checker"]["path"]
        checked = _process([checker, str(cnf_path), str(lrat_path)], directory, "checker.log",
                           timeout=timeout, file_limit=limits.max_certificate_bytes)
        base_evidence["checker_returncode"] = checked.returncode
        base_evidence["checker_output"] = checked.stdout[:4096]
        if checked.returncode != 0 or checked.stdout.splitlines() != ["s VERIFIED UNSAT"]:
            base_evidence["reason"] = "external LRAT checker rejected the certificate"
            return result
        if _sha(cnf_path.read_bytes()) != identity["cnf_sha256"] or _sha(lrat_path.read_bytes()) != base_evidence["certificate_sha256"]:
            raise CertificateError("checker input changed during verification")
        if _tools(root) != toolchain or _source_identity(root) != base_evidence["source_sha256"]:
            raise CertificateError("toolchain or implementation sources changed during verification")
        base_evidence.update(status="checked optimal" if retained is not None else "checked infeasible",
                             certificate_status="checked LRAT refutation",
                             proof_endpoint=toolchain["checker_endpoint"])
        (directory / "receipt.json").write_bytes(_json(result))
    except (ValueError, OSError, subprocess.TimeoutExpired, KeyError, TypeError) as error:
        base_evidence["reason"] = str(error)
        return result
    else:
        return result


def replay(instance: planner.Instance, report: object, root: Path) -> dict[str, Any]:
    """Regenerate objective, model and CNF before replaying a serialized certificate."""
    if not isinstance(report, dict) or not isinstance(report.get("evidence"), dict):
        raise CertificateError("expected a complete certificate result")
    evidence = report["evidence"]
    if evidence.get("status") not in {"checked optimal", "checked infeasible"}:
        raise CertificateError("result contains no checked optimality or infeasibility claim")
    instance = _snapshot(instance)
    if evidence.get("instance_digest") != planner.instance_digest(instance):
        raise CertificateError("instance digest mismatch")
    if evidence.get("encoding_version") != ENCODING_VERSION:
        raise CertificateError("unsupported encoding version")
    if evidence.get("source_sha256") != _source_identity(root):
        raise CertificateError("encoding or checker source changed")
    limits = Limits(**evidence["limits"])
    candidate = report.get("placement")
    if evidence["status"] == "checked infeasible" and candidate is not None:
        raise CertificateError("infeasibility receipt carries a placement")
    if evidence["status"] == "checked optimal" and candidate is None:
        raise CertificateError("optimality receipt is missing its feasible witness")
    findings = planner.check_placement(instance, candidate) if candidate is not None else []
    if findings:
        raise CertificateError("receipt candidate failed independent validation")
    bound = sum(planner.pool_heights(instance, candidate).values()) - 1 if candidate is not None else None
    if evidence["objective"]["metric"] != "sum-pool-extents-in-bytes" or evidence["objective"]["strictly_better_query_bound"] != bound:
        raise CertificateError("objective does not match the candidate")
    encoding = encode(instance, objective_bound=bound,
                      pool_limits=evidence["objective"]["pool_limits"], limits=limits)
    identity = encoding.identity()
    if any(evidence.get(key) != identity[key] for key in ("encoding_sha256", "cnf_sha256")):
        raise CertificateError("encoded formula or binding mismatch")
    path = Path(evidence["artifacts"]["lrat"])
    if path.stat().st_size > limits.max_certificate_bytes:
        raise CertificateError("certificate exceeds byte budget")
    with path.open("rb") as stream:
        data = stream.read(limits.max_certificate_bytes + 1)
    if len(data) > limits.max_certificate_bytes or _sha(data) != evidence["certificate_sha256"]:
        raise CertificateError("certificate bytes changed")
    return certify(instance, candidate, root, certificate_path=path,
                   pool_limits=evidence["objective"]["pool_limits"], limits=limits,
                   timeout=_number(evidence["timeout_seconds"], "timeout_seconds", 1))


def demo(root: Path) -> dict[str, Any]:
    """Exercise real producer/checker, invalid LRAT, and a feasible smaller layout."""
    instance = planner.parse_instance({"name": "three-conflicting-two-byte-buffers",
        "pools": [{"id": "arena", "capacity": 8}],
        "buffers": [{"id": str(i), "size": 2, "allowed_pools": ["arena"], "intervals": [[0, 2]]}
                    for i in range(3)]})
    candidate = [{"id": str(i), "pool": "arena", "offset": 2 * i} for i in range(3)]
    good = certify(instance, candidate, root)
    if good["evidence"]["status"] != "checked optimal":
        raise CertificateError(f"real LRAT optimality check failed: {good['evidence']}")
    directory = Path(good["evidence"]["artifacts"]["directory"])
    corrupt = directory / "corrupt.lrat"
    corrupt.write_text("999999 0 0\n", encoding="ascii")
    bad = certify(instance, candidate, root, certificate_path=corrupt)
    if bad["evidence"]["certificate_status"] != "unknown":
        raise CertificateError("corrupt LRAT proof was accepted")
    oversized = [*candidate[:-1], {"id": "2", "pool": "arena", "offset": 6}]
    counterexample = certify(instance, oversized, root)
    if "counterexample" not in counterexample or counterexample["evidence"]["status"] != "checked feasible":
        raise CertificateError("false optimum was not refuted by a checked smaller layout")
    repeated = replay(instance, good, root)
    if repeated["evidence"]["status"] != "checked optimal":
        raise CertificateError("saved certificate did not replay")
    result = {"status": "passed", "instance": asdict(instance), "optimality": good,
              "corrupt_certificate": bad, "false_optimum": counterexample, "replayed": repeated,
              "measurement_scope": "finite synthetic placement; no source or target refinement"}
    (workspace(root) / "demo.json").write_bytes(_json(result))
    return result


def proof(root: Path) -> dict[str, Any]:
    """Focused native Rocq compilation for this lane's encoding theorem only."""
    directory = workspace(root) / "proof"
    directory.mkdir(parents=True, exist_ok=True)
    source = root / "proofs/MemoryPlannerCertificates.v"
    copied = directory / source.name
    copied.write_bytes(source.read_bytes())
    compiled = _run([*env.rocq_command(), "-q", str(copied)], directory, "compile.log")
    _run([*env.rocqchk_command(), "-silent", "-Q", str(directory), "", "MemoryPlannerCertificates"],
         directory, "recheck.log")
    return {"status": "passed", "source_sha256": _sha(source.read_bytes()),
            "vo_sha256": _sha(copied.with_suffix(".vo").read_bytes()),
            "assumptions": compiled.stdout, "scope": "one-hot finite constraint model; no Python refinement"}
