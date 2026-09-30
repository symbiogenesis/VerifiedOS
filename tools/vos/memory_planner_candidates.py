# SPDX-License-Identifier: Apache-2.0
"""Optional pinned idealloc search behind the portable feasibility checker.

The upstream algorithm is stochastic and untrusted. This module neither changes
lifetimes nor infers them. Exact rank conversion preserves interval coexistence.
Downloads, compiler output and subprocess files stay in the native guest lane.
"""

import copy
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import time
import tomllib
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.request import urlopen

from vos import memory_planner as planner
from vos import rust_toolchain

MAX_OBJECTS = 4096
MAX_TOTAL_SIZE = (1 << 31) - 1
PIN_PATH = "tools/memory-planner/idealloc.json"
PIN_SCHEMA = "vos-idealloc-pin-v3"
BRIDGE_PATH = "tools/memory-planner/idealloc/bridge.rs"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def supported(instance: planner.Instance) -> planner.Instance:
    """Refuse richer models; never erase their constraints to fit an upstream API."""
    instance = planner.parse_instance(asdict(instance))
    if len(instance.pools) != 1 or instance.pools[0].reserved or instance.conflicts:
        raise planner.UnsupportedError("idealloc requires one unreserved pool and interval-only conflicts")
    if not 1 <= len(instance.buffers) <= MAX_OBJECTS:
        raise planner.UnsupportedError(f"idealloc requires 1..{MAX_OBJECTS} buffers")
    for buffer in instance.buffers:
        if (buffer.size == 0 or buffer.alignment != 1 or len(buffer.intervals) != 1
                or buffer.fixed_offset is not None or buffer.alias_of is not None):
            raise planner.UnsupportedError("idealloc requires positive unit-aligned single-interval buffers without fixed offsets or aliases")
    if sum(b.size for b in instance.buffers) > MAX_TOTAL_SIZE:
        raise planner.UnsupportedError("idealloc adapter's reviewed numerical range exceeded")
    return instance


def encode_jobs(instance: planner.Instance) -> str:
    """[start,end) becomes (2*rank(start),2*rank(end)) over discrete open time.

Every nonempty interval has an interior point. Strict endpoint ordering and
equality are preserved, hence so is pairwise coexistence, including adjacency.
Only logical time is compressed; byte sizes are unchanged.
"""
    instance = supported(instance)
    points = sorted({point for b in instance.buffers for point in b.intervals[0]})
    rank = {point: index * 2 for index, point in enumerate(points)}
    return "".join(f"{b.size}\t{rank[b.intervals[0][0]]}\t{rank[b.intervals[0][1]]}\n"
                   for b in instance.buffers)


def decode_jobs(instance: planner.Instance, text: str) -> planner.Placement:
    instance = supported(instance)
    rows: dict[int, int] = {}
    for line in text.splitlines():
        values = line.split("\t")
        if len(values) != 2 or any(not value.isascii() or not value.isdecimal() for value in values):
            raise ValueError("malformed idealloc result row")
        index, offset = map(int, values)
        if index in rows or not 0 <= index < len(instance.buffers):
            raise ValueError("duplicate or unknown idealloc identity")
        rows[index] = offset
    if set(rows) != set(range(len(instance.buffers))):
        raise ValueError("missing idealloc identity")
    return [{"id": b.id, "pool": instance.pools[0].id, "offset": rows[index]}
            for index, b in enumerate(instance.buffers)]


def greedy_candidate(instance: planner.Instance) -> planner.Placement:
    """Authored deterministic size-descending first fit, no exact-optimality claim."""
    instance = supported(instance)
    placed: list[tuple[planner.Buffer, int]] = []
    for buffer in sorted(instance.buffers, key=lambda b: (-b.size, b.id)):
        start, end = buffer.intervals[0]
        occupied = sorted((offset, offset + other.size) for other, offset in placed
                          if start < other.intervals[0][1] and other.intervals[0][0] < end)
        offset = 0
        for left, right in occupied:
            if offset + buffer.size <= left:
                break
            offset = max(offset, right)
        placed.append((buffer, offset))
    return [{"id": b.id, "pool": instance.pools[0].id, "offset": offset}
            for b, offset in placed]


def separate_baseline(instance: planner.Instance) -> planner.Placement:
    instance = supported(instance)
    offset = 0
    result: planner.Placement = []
    for buffer in instance.buffers:
        result.append({"id": buffer.id, "pool": instance.pools[0].id, "offset": offset})
        offset += buffer.size
    return result


def native_output(root: Path, output: Path) -> Path:
    root, output = root.resolve(), output.resolve()
    if output.is_relative_to(root) or not output.is_relative_to(Path("/root/build")):
        raise ValueError("idealloc outputs must stay under /root/build outside the checkout")
    output.mkdir(parents=True, exist_ok=True)
    return output


def rust_target() -> str:
    triple = {"x86_64": "x86_64-unknown-linux-gnu",
              "aarch64": "aarch64-unknown-linux-gnu"}.get(platform.machine())
    if platform.system() != "Linux" or triple is None:
        raise ValueError("idealloc demonstration requires a supported 64-bit Linux Rust toolchain")
    return triple


def _fetch_component(url: str, expected: str, archive: Path) -> None:
    """Keep only an archive whose SHA-256 is the pinned component hash."""
    if archive.is_file() and digest(archive) == expected:
        return
    if not url.startswith(rust_toolchain.DIST):
        raise ValueError("Rust components come only from the HTTPS distribution server")
    archive.parent.mkdir(parents=True, exist_ok=True)
    part = archive.with_name(archive.name + ".part")
    with (urlopen(url, timeout=120) as response,  # noqa: S310 -- HTTPS origin checked above; hash-pinned bytes.
          part.open("wb") as stream):
        shutil.copyfileobj(response, stream)
    if digest(part) != expected:
        part.unlink()
        raise ValueError("pinned Rust component hash mismatch")
    part.replace(archive)


def rust_environment(root: Path, output: Path) -> tuple[str, dict[str, str], dict[str, str]]:
    """Install the shared pinned Rust component archives in this lane, without rustup or profile changes.

The pin is the checkout's shared Rust toolchain owner, also read by the optional
Isla tools. Each archive is checked against its channel-manifest xz_hash before
extraction, so the installed compiler is bound to the pin rather than to a live
manifest. Returns Cargo, its process environment and the installed component hashes.
"""
    triple = rust_target()
    pin = rust_toolchain.load(root)
    version, components = pin["version"], pin["components"][triple]
    prefix = output / "rust"
    stamp = prefix / "vos-rust-components.json"
    wanted = {"version": version, "target": triple, "components": components}
    try:
        installed = json.loads(stamp.read_text(encoding="utf-8")) == wanted
    except (OSError, ValueError):
        installed = False
    if not installed or not (prefix / "bin/cargo").is_file():
        shutil.rmtree(prefix, ignore_errors=True)
        downloads = output / "rust-dist"
        rows = rust_toolchain.archives(pin, triple)
        for name, url, expected in rows:
            _fetch_component(url, expected, downloads / f"{name}.tar.xz")
        with (output / "rust-install.log").open("w", encoding="utf-8", newline="") as log:
            for name, _, _ in rows:
                with tarfile.open(downloads / f"{name}.tar.xz") as stream:
                    stream.extractall(downloads, filter="data")
                subprocess.run(["sh", str(downloads / name / "install.sh"), f"--prefix={prefix}",
                                "--disable-ldconfig"], cwd=output, stdout=log, stderr=subprocess.STDOUT,
                               timeout=600, check=True)
        stamp.write_text(json.dumps(wanted, indent=2), encoding="utf-8", newline="")
    process_env = dict(os.environ, CARGO_HOME=str(output / "cargo-home"),
                       RUSTC=str(prefix / "bin/rustc"), CARGO_TARGET_DIR=str(output / "target"))
    process_env["PATH"] = str(prefix / "bin") + os.pathsep + process_env.get("PATH", "")
    return str(prefix / "bin/cargo"), process_env, components


def verify_crate(package_root: Path, archive: Path, checksum: str) -> None:
    """Recheck Cargo's unpacked inputs against the lock-bound crate on every build.

This reads archive members and never extracts them. Paths and entry kinds are
checked before addressing local files; unexpected source files are also refused.
"""
    if digest(archive) != checksum:
        raise ValueError("Cargo dependency archive differs from pinned lock checksum")
    expected: set[str] = set()
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != package_root.name:
                raise ValueError("Cargo archive path escapes its package")
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError("unsupported Cargo archive entry kind")
            relative = Path(*path.parts[1:])
            target = (package_root / relative).resolve()
            if not target.is_relative_to(package_root.resolve()):
                raise ValueError("Cargo source path escapes package")
            data = stream.extractfile(member)
            if data is None or hashlib.sha256(data.read()).hexdigest() != digest(target):
                raise ValueError("unpacked Cargo source differs from locked archive")
            expected.add(relative.as_posix())
    actual = {path.relative_to(package_root).as_posix() for path in package_root.rglob("*") if path.is_file()}
    if actual - expected - {".cargo-ok", ".cargo-checksum.json"}:
        raise ValueError("unexpected source file in Cargo package")


def build_idealloc(root: Path, output: Path) -> dict[str, Any]:
    """Build only a hash-bound upstream core and this repository's authored bridge."""
    output = native_output(root, output)
    pin = json.loads((root / PIN_PATH).read_text(encoding="utf-8"))
    # Version 3 moved the Rust pin to the shared rust_toolchain owner.
    if pin.get("schema") != PIN_SCHEMA or "rust" in pin:
        raise ValueError(f"unsupported idealloc pin manifest; expected {PIN_SCHEMA}")
    source = output / "upstream"
    for entry in pin["files"]:
        relative = Path(entry["path"])
        target = (source / relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(source):
            raise ValueError("idealloc manifest path escapes source root")
        if not target.is_file() or digest(target) != entry["sha256"]:
            url = f"https://raw.githubusercontent.com/cappadokes/idealloc/{pin['commit']}/{relative.as_posix()}"
            with urlopen(url, timeout=30) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError(f"idealloc source digest mismatch: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    # Preserve the workspace so its original lock remains valid. Build only coreba;
    # the only guest manifest change adds our bin to that crate.
    workspace = source / "Cargo.toml"
    bridge = source / "coreba/src/bin/vos_bridge.rs"
    bridge.write_bytes((root / BRIDGE_PATH).read_bytes())
    manifest = source / "coreba/Cargo.toml"
    with manifest.open("a", encoding="utf-8", newline="") as stream:
        stream.write('\n[[bin]]\nname = "vos-idealloc"\npath = "src/bin/vos_bridge.rs"\n')
    cargo, cargo_env, rust_components = rust_environment(root, output)
    command = [cargo, "build", "--locked", "--release", "--jobs", "2", "-p", "coreba", "--bin", "vos-idealloc"]
    begin = time.perf_counter()
    # On a cold Cargo home, metadata downloads every locked crate to read its manifest.
    metadata = subprocess.run([cargo, "metadata", "--locked", "--format-version", "1"],
                              cwd=source, env=cargo_env, capture_output=True, text=True, check=True, timeout=600)
    resolved = json.loads(metadata.stdout)
    packages = resolved["packages"]
    root_id = next(p["id"] for p in packages if p["name"] == "coreba")
    nodes = {node["id"]: node for node in resolved["resolve"]["nodes"]}
    reachable, pending = set(), [root_id]
    while pending:
        identifier = pending.pop()
        if identifier not in reachable:
            reachable.add(identifier)
            pending.extend(dep["pkg"] for dep in nodes[identifier]["deps"])
    closure: list[dict[str, str]] = []
    lock = tomllib.loads((source / "Cargo.lock").read_text(encoding="utf-8"))
    checksums = {(p["name"], p["version"]): p["checksum"] for p in lock["package"] if "checksum" in p}
    for package in packages:
        if package["id"] not in reachable:
            continue
        package_root = Path(package["manifest_path"]).parent
        if package["source"] is not None:
            filename = f"{package['name']}-{package['version']}.crate"
            archives = list((output / "cargo-home/registry/cache").glob("*/" + filename))
            if len(archives) != 1:
                raise ValueError("Cargo dependency archive absent or ambiguous")
            verify_crate(package_root, archives[0], checksums[package["name"], package["version"]])
        records = [(p.relative_to(package_root).as_posix(), digest(p))
                   for p in sorted(package_root.rglob("*")) if p.is_file()]
        closure.append({"id": package["id"], "license": package.get("license") or "unspecified",
                        "source_tree_sha256": hashlib.sha256(json.dumps(records).encode()).hexdigest()})
    with (output / "compile.log").open("w", encoding="utf-8", newline="") as log:
        done = subprocess.run(command, cwd=source, env=cargo_env, stdout=log, stderr=subprocess.STDOUT,
                              check=False, timeout=600)
    if done.returncode:
        raise ValueError(f"idealloc build failed; inspect {output / 'compile.log'}")
    executable = output / "target/release/vos-idealloc"
    rustc = Path(cargo_env["RUSTC"])
    receipt = {"schema": "vos-idealloc-build-v3", "commit": pin["commit"], "license": pin["license"],
               "manifest_sha256": digest(root / PIN_PATH), "bridge_sha256": digest(root / BRIDGE_PATH),
               "rust_pin_sha256": digest(root / rust_toolchain.PATH),
               "workspace_sha256": digest(workspace), "patched_crate_manifest_sha256": digest(manifest),
               "lock_sha256": digest(source / "Cargo.lock"), "dependency_closure": closure,
               "command": command, "build_seconds": time.perf_counter() - begin,
               "executable": str(executable), "executable_sha256": digest(executable),
               "compiler": subprocess.run([str(rustc), "-vV"], cwd=output, env=cargo_env,
                                          capture_output=True, text=True, check=True).stdout.strip(),
               "rustc_sha256": digest(rustc), "cargo_sha256": digest(Path(cargo)),
               "rust_component_sha256": rust_components,
               "compile_log_sha256": digest(output / "compile.log")}
    (output / "build-evidence.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8", newline="")
    return receipt


class IdeallocCandidate:
    """A subprocess candidate with explicit timeout and full rejection diagnostics."""

    def __init__(self, executable: Path, executable_sha256: str, output: Path,
                 *, timeout: float = 30, iterations: int = 1) -> None:
        if not 0 < timeout <= 300 or not 1 <= iterations <= 100:
            raise ValueError("invalid idealloc process limits")
        self.executable = executable
        self.executable_sha256 = executable_sha256
        self.output = output
        self.timeout = timeout
        self.iterations = iterations
        self.last_evidence: dict[str, Any] = {}

    def __call__(self, instance: planner.Instance) -> planner.Placement:
        self.last_evidence = {"status": "unsupported", "stochastic_search": True,
                              "timeout_seconds": self.timeout, "iterations": self.iterations}
        try:
            return self._invoke(instance)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.last_evidence.update(status="rejected/unsupported", reason=str(error))
            raise

    def _invoke(self, instance: planner.Instance) -> planner.Placement:
        encoded = encode_jobs(instance)
        if digest(self.executable) != self.executable_sha256:
            raise ValueError("idealloc executable identity changed")
        self.output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="candidate-", dir=self.output) as temporary:
            directory = Path(temporary)
            source, result, log = directory / "input.tsv", directory / "output.tsv", directory / "run.log"
            source.write_text(encoded, encoding="utf-8", newline="")
            begin = time.perf_counter()
            command = [str(self.executable), str(source), str(result), str(self.iterations)]
            # One upstream Rayon thread limits the large per-thread stack reservation.
            with log.open("w", encoding="utf-8", newline="") as stream:
                done = subprocess.run(command, cwd=directory, env=dict(os.environ, RAYON_NUM_THREADS="1"),
                                      stdout=stream, stderr=subprocess.STDOUT, check=False, timeout=self.timeout)
            self.last_evidence.update(status="candidate returned", seconds=time.perf_counter() - begin,
                                      returncode=done.returncode, input_sha256=digest(source),
                                      log_sha256=digest(log), executable_sha256=self.executable_sha256)
            if done.returncode or digest(self.executable) != self.executable_sha256:
                raise ValueError("idealloc process failed or executable identity changed")
            if result.stat().st_size > MAX_OBJECTS * 64:
                raise ValueError("idealloc result exceeds protocol bound")
            candidate = decode_jobs(instance, result.read_text(encoding="utf-8"))
            self.last_evidence["output_sha256"] = digest(result)
            findings = planner.check_placement(instance, candidate)
            self.last_evidence.update(status="checked candidate" if not findings else "rejected candidate", findings=findings)
            if findings:
                raise ValueError("idealloc candidate violates original portable instance")
            self.last_evidence["pool_heights"] = planner.pool_heights(instance, candidate)
            return candidate


def comparison_corpus() -> list[planner.Instance]:
    """Declared synthetic traces; no production-workload or universal scaling claim."""
    definitions = [
        ("adjacent", [(3, 0, 1), (2, 1, 2), (4, 2, 3)]),
        ("equal-overlap", [(2, 0, 2), (2, 1, 3), (2, 2, 4)]),
        ("mixed-crossing", [(3, 0, 3), (2, 2, 4), (1, 1, 2), (2, 3, 5)]),
        ("nested", [(1, 0, 7), (3, 1, 3), (2, 4, 6)]),
    ]
    definitions.extend((f"moving-window-{count}", [(1 + (i * 7) % 17, i, i + 7) for i in range(count)])
                       for count in (32, 128, 512))
    definitions.extend((f"mixed-durations-{count}",
                        [(1 + (i * 29) % 31, (i * 37) % 113, (i * 37) % 113 + 1 + (i * 19) % 47)
                         for i in range(count)]) for count in (32, 128))
    return [planner.parse_instance({"name": name, "pools": [{"id": "arena", "capacity": sum(r[0] for r in rows)}],
                                    "buffers": [{"id": f"buffer-{index}", "size": size,
                                                 "allowed_pools": ["arena"], "intervals": [[start, end]]}
                                                for index, (size, start, end) in enumerate(rows)],
                                    "assumptions": ["Synthetic single-pool trace; declared intervals are the complete reuse horizon."]})
            for name, rows in definitions]


def compare(executable: Path, executable_sha256: str, output: Path, *,
            timeout: float = 30, iterations: int = 1) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for instance in comparison_corpus():
        events: dict[int, int] = {}
        for buffer in instance.buffers:
            start, end = buffer.intervals[0]
            events[start] = events.get(start, 0) + buffer.size
            events[end] = events.get(end, 0) - buffer.size
        live = peak = 0
        for point in sorted(events):
            live += events[point]
            peak = max(peak, live)
        baseline = separate_baseline(instance)
        begin = time.perf_counter()
        greedy = planner.plan(instance, baseline, candidates=(greedy_candidate,))
        greedy_seconds = time.perf_counter() - begin
        candidate = IdeallocCandidate(executable, executable_sha256, output, timeout=timeout, iterations=iterations)
        begin = time.perf_counter()
        selected = planner.plan(instance, greedy["placement"], candidates=(candidate,))
        total_seconds = time.perf_counter() - begin
        exact: dict[str, Any] = {"status": "not requested: larger synthetic trace"}
        if len(instance.buffers) <= 4:
            exact = planner.plan(instance, selected["placement"], work_budget=10000,
                                 certify=True, replay_budget=100000)["evidence"]
        corrupted = copy.deepcopy(selected["placement"])
        corrupted[0]["offset"] = instance.pools[0].capacity + 1
        refusal = planner.plan(instance, selected["placement"], candidates=(corrupted,))
        if refusal["placement"] != selected["placement"] or not refusal["evidence"]["rejected"]:
            raise ValueError("corrupted candidate was not rejected with baseline retained")
        results.append({"instance": asdict(instance), "instance_digest": planner.instance_digest(instance),
                        "objects": len(instance.buffers), "separate_span": sum(planner.pool_heights(instance, baseline).values()),
                        "live_load_lower_bound": peak,
                        "greedy_span": sum(planner.pool_heights(instance, greedy["placement"]).values()),
                        "upstream_span": sum(candidate.last_evidence["pool_heights"].values())
                        if "pool_heights" in candidate.last_evidence else None,
                        "selected_span": sum(planner.pool_heights(instance, selected["placement"]).values()),
                        "greedy_seconds": greedy_seconds, "idealloc_and_check_seconds": total_seconds,
                        "candidate": candidate.last_evidence, "selected": selected,
                        "exact_small_instance": exact, "corrupted_candidate_rejected": True})
    failures = [row["instance"]["name"] for row in results if row["candidate"]["status"] != "checked candidate"]
    return {"schema": "vos-idealloc-comparison-v1", "status": "failed" if failures else "passed", "failures": failures,
            "scope": "synthetic interval corpus; host elapsed measurements include independent checks; no target or million-buffer claim",
            "results": results}
