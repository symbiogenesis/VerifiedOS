# SPDX-License-Identifier: Apache-2.0
"""Optional, isolated Isla campaign over the curated permission functions.

The two symbolic calls enumerate path witnesses from the real Sail-generated IR.
The complete five-bit input roster is required; duplicate/missing witnesses fail.
isla-testgen executes those concrete witnesses through its helper-function API.
This does not implement an RV64 instruction Target, instruction generation, memory
or concurrency testing. Narrowing is checked only on the 32 expanded permission
masks. The primary Sail C oracle remains separate from the development compiler.
"""

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request
from contextlib import chdir
from pathlib import Path
from typing import Literal, TypedDict, cast

from vos import env, oracle, sailrig

ASSETS = Path("tools/sail-isla")
NOTICE = ("Finite advisory differential campaign, not a proof. Scope: perms_expand "
          "over 32 codes and perms_narrow over their expanded masks. No instruction, "
          "memory, concurrency or full 4096-mask narrowing campaign.")
PRESERVE = ("vos_expand_local", "vos_expand_global", "perms_narrow", "vos_pc")


class SourcePin(TypedDict):
    url: str
    revision: str


class TestgenPin(SourcePin):
    isla_revision: str


class SailPin(SourcePin):
    sha256: str


class RustPin(TypedDict):
    version: str
    components: dict[str, dict[str, str]]


class Lock(TypedDict):
    version: int
    isla: SourcePin
    testgen: TestgenPin
    sail: SailPin
    rust: RustPin


class Stamp(TypedDict):
    version: int
    assets_sha256: str
    binaries: dict[str, str]


class Case(TypedDict):
    code: int
    expanded: int
    narrowed: int


class Control(TypedDict):
    name: str
    status: Literal["killed", "survived", "build_rejected"]
    mismatches: list[int]
    log: str


class Invocation(TypedDict):
    argv: list[str]
    cwd: str
    returncode: int
    seconds: float
    log: str


class Report(TypedDict):
    version: Literal[1]
    advisory_only: Literal[True]
    notice: str
    passed: bool
    source_sha256: dict[str, str]
    tool_sha256: dict[str, str]
    assets_sha256: str
    ir_sha256: str
    cases: list[Case]
    symbolic_paths: list[int]
    baseline_matches: int
    testgen_matches: int
    controls: list[Control]
    invocations: list[Invocation]
    directory: str


class IslaError(ValueError):
    """A prerequisite, generation or replay failure with no partial verdict."""


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def asset_digest(root: Path) -> str:
    paths = sorted(p for p in (root / ASSETS).rglob("*") if p.is_file())
    paths += [root / "tools/opam/sail.lock", Path(__file__)]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


class Runner:
    """Commands have explicit directories, bounded execution and persistent logs."""

    def __init__(self, environment: env.Environment, label: str) -> None:
        self.environment = environment
        self.label = label
        self.invocations: list[Invocation] = []

    def run(self, argv: list[str], cwd: Path, process_env: dict[str, str] | None = None,
            timeout: int = 1800) -> str:
        number = len(self.invocations)
        log = self.environment.log(f"sail-isla-{self.label}-{number:02d}")
        log.parent.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        try:
            done = subprocess.run(argv, cwd=cwd, env=process_env, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            _write(log, f"Timed out after {timeout}s: {argv!r}\n")
            raise IslaError(f"command timed out; see {log}") from exc
        _write(log, json.dumps(argv) + "\n" + done.stdout + "\n" + done.stderr)
        self.invocations.append({"argv": argv, "cwd": str(cwd),
                                 "returncode": done.returncode,
                                 "seconds": round(time.monotonic() - start, 3), "log": str(log)})
        if done.returncode:
            raise IslaError(f"command exited {done.returncode}; see {log}")
        return done.stdout


def _load_lock(root: Path) -> Lock:
    lock = cast(Lock, json.loads((root / ASSETS / "lock.json").read_text(encoding="utf-8")))
    if lock["version"] != 1:
        raise IslaError("unsupported optional tool lock version")
    return lock


def _download(url: str, expected: str, destination: Path) -> None:
    if not url.startswith("https://"):
        raise IslaError("optional tool downloads require HTTPS")
    if not destination.is_file() or sha(destination) != expected:
        destination.parent.mkdir(parents=True, exist_ok=True)
        part = destination.with_suffix(destination.suffix + ".part")
        # All callers use locked HTTPS URLs, with a digest verified before install.
        with urllib.request.urlopen(url, timeout=120) as response, part.open("wb") as output:  # noqa: S310
            shutil.copyfileobj(response, output)
        if sha(part) != expected:
            part.unlink()
            raise IslaError(f"download SHA-256 mismatch: {url}")
        part.replace(destination)


def _fetch(pin: SourcePin, destination: Path, runner: Runner) -> None:
    if not destination.exists():
        destination.mkdir(parents=True)
        runner.run(["git", "-C", str(destination), "init"], destination)
        runner.run(["git", "-C", str(destination), "fetch", "--depth=1",
                    pin["url"], pin["revision"]], destination)
        runner.run(["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"],
                   destination)
    found = runner.run(["git", "-C", str(destination), "rev-parse", "HEAD"], destination)
    dirty = runner.run(["git", "-C", str(destination), "status", "--porcelain",
                        "--untracked-files=no"], destination)
    if found.strip() != pin["revision"] or dirty.strip():
        raise IslaError(f"optional source checkout has wrong revision or edits: {destination}")


def _prerequisites(e: env.Environment, runner: Runner) -> Path:
    for tool in ("opam", "git", "cc", "ar"):
        if shutil.which(tool) is None:
            raise IslaError(f"missing {tool}; provision the repository's baseline Sail toolchain")
    lock_text = (e.root / "tools/opam/sail.lock").read_text(encoding="utf-8")
    block = re.search(r"installed:\s*\[(.*?)\]", lock_text, re.DOTALL)
    if block is None:
        raise IslaError("cannot read baseline opam inventory")
    expected = set(re.findall(r'"([^"]+)"', block[1]))
    listing = runner.run(["opam", "list", f"--switch={env.SAIL_SWITCH}", "--installed",
                          "--short", "--columns=name,version", "--color=never"], e.root)
    actual = {".".join(line.split()) for line in listing.splitlines() if line.strip()}
    if actual != expected:
        raise IslaError("installed baseline opam inventory differs from tools/opam/sail.lock")
    z3 = Path(shutil.which("z3") or "")
    if not z3.is_file() or runner.run([str(z3), "--version"], e.root).strip() != (
            f"Z3 version {env.Z3_VERSION} - 64 bit"):
        raise IslaError(f"the baseline Z3 {env.Z3_VERSION} must be on PATH")
    libraries = sorted(z3.resolve().parent.parent.rglob("libz3.so"))
    if len(libraries) != 1:
        raise IslaError("cannot uniquely locate the baseline Z3 shared library")
    return libraries[0].parent


def _process_env(base: Path, z3_lib: Path) -> dict[str, str]:
    process = os.environ.copy()
    process.update({
        "PATH": str(base / "rust/bin") + os.pathsep + process.get("PATH", ""),
        "CARGO_HOME": str(base / "cargo-home"),
        "RUSTFLAGS": f"-L native={z3_lib}",
        "LD_LIBRARY_PATH": str(z3_lib),
    })
    return process


def _binaries(base: Path, lane: Path, z3_lib: Path) -> list[Path]:
    baseline = Path(shutil.which("sail") or "")
    directory = subprocess.run([str(baseline), "--dir"], cwd=base, check=True,
                               capture_output=True, encoding="utf-8", timeout=30)
    runtime = Path(directory.stdout.strip()) / "lib"
    return [base / "sail-prefix/bin/sail",
            lane / "sources/isla/isla-sail/_build/default/sail_plugin_isla.cmxs",
            base / "target-isla/release/isla-execute-function",
            base / "target-testgen/release/vos-isla-testgen",
            base / "rust/bin/rustc", base / "rust/bin/cargo", z3_lib / "libz3.so",
            baseline, Path(shutil.which("cc") or ""), Path(shutil.which("z3") or ""),
            *(runtime / name for name in sailrig.RUNTIME),
            *sorted(runtime.glob("*.h"))]


def provision(e: env.Environment, jobs: int = 2) -> Stamp:
    """Explicit downloads and builds; never installs into the baseline opam switch."""
    if not 1 <= jobs <= 16:
        raise IslaError("jobs must be in 1..16")
    base = e.lane_root / "sail-isla"
    base.mkdir(parents=True, exist_ok=True)
    with env.hold_lock(base, "optional Isla provisioning"):
        runner = Runner(e, "provision")
        z3_lib = _prerequisites(e, runner)
        lock = _load_lock(e.root)
        triple = {"aarch64": "aarch64-unknown-linux-gnu",
                  "x86_64": "x86_64-unknown-linux-gnu"}.get(platform.machine())
        if platform.system() != "Linux" or triple is None:
            raise IslaError("optional native tools support Linux aarch64 and x86_64")
        for component, expected in lock["rust"]["components"][triple].items():
            name = f"{component}-{lock['rust']['version']}-{triple}"
            archive = base / f"{name}.tar.xz"
            _download(f"https://static.rust-lang.org/dist/{name}.tar.xz", expected, archive)
            with tarfile.open(archive) as compressed:
                compressed.extractall(base, filter="data")
            runner.run(["sh", str(base / name / "install.sh"), f"--prefix={base / 'rust'}",
                        "--disable-ldconfig"], base)
        process = _process_env(base, z3_lib)
        sources = e.lane_root / "sources"
        isla, testgen = sources / "isla", sources / "isla-testgen"
        _fetch(lock["isla"], isla, runner)
        _fetch(lock["testgen"], testgen, runner)
        runner.run(["git", "-C", str(testgen), "submodule", "update", "--init", "--depth=1",
                    "isla"], testgen)
        _fetch({"url": lock["isla"]["url"], "revision": lock["testgen"]["isla_revision"]},
               testgen / "isla", runner)
        archive = base / "sail.tar.gz"
        _download(lock["sail"]["url"], lock["sail"]["sha256"], archive)
        with tarfile.open(archive) as compressed:
            compressed.extractall(base, filter="data")
        sail_source = base / f"sail-{lock['sail']['revision']}"
        prefix = base / "sail-prefix"
        opam = ["opam", "exec", f"--switch={env.SAIL_SWITCH}", "--"]
        runner.run([*opam, "dune", "build", "-p", "sail,sail_maker,libsail", "@install",
                    "-j", str(jobs)], sail_source, process)
        runner.run([*opam, "dune", "install", "--prefix", str(prefix),
                    "sail", "sail_maker", "libsail"], sail_source, process)
        (prefix / "share/libsail/plugins").mkdir(parents=True, exist_ok=True)
        switch = runner.run(["opam", "var", "prefix", f"--switch={env.SAIL_SWITCH}"],
                            sail_source).strip()
        plugin_env = {**process, "OCAMLPATH": f"{prefix / 'lib'}:{switch}/lib"}
        runner.run([*opam, "dune", "build", "--release", "-j", str(jobs)],
                   isla / "isla-sail", plugin_env)
        runner.run(["cargo", "build", "--release", "--locked", "--bin",
                    "isla-execute-function", "-j", str(jobs)], isla,
                   {**process, "CARGO_TARGET_DIR": str(base / "target-isla")})
        driver = base / "build/driver"
        shutil.copytree(e.root / ASSETS / "driver", driver, dirs_exist_ok=True)
        runner.run(["cargo", "build", "--release", "--locked", "-j", str(jobs)], driver,
                   {**process, "CARGO_TARGET_DIR": str(base / "target-testgen")})
        stamp: Stamp = {"version": 1, "assets_sha256": asset_digest(e.root),
                        "binaries": {str(path): sha(path)
                                     for path in _binaries(base, e.lane_root, z3_lib)}}
        _write(base / "provision.json", json.dumps(stamp, indent=2) + "\n")
        return stamp


def parse_symbolic(text: str, global_bit: int) -> dict[int, int]:
    """Only complete, unique 17-bit path witnesses count as generated cases."""
    rows: dict[int, int] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"Result: #b([01]{17})", line)
        if match is None:
            if line.strip():
                raise IslaError(f"unexpected symbolic result: {line[:160]}")
            continue
        number = int(match[1], 2)
        code, expanded = number >> 12, number & 4095
        if code in rows:
            raise IslaError(f"duplicate symbolic witness for code {code}")
        rows[code] = expanded
    if set(rows) != set(range(global_bit * 16, (global_bit + 1) * 16)):
        raise IslaError("symbolic execution did not cover the required 16 code witnesses")
    return rows


def parse_cases(text: str, codes: set[int]) -> list[Case]:
    rows: dict[int, Case] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"case (\d+) (\d+) (\d+)", line)
        if match is None:
            if line.strip():
                raise IslaError(f"unexpected replay result: {line[:160]}")
            continue
        code, expanded, narrowed = map(int, match.groups())
        if code in rows or code not in codes or expanded >= 4096 or narrowed >= 32:
            raise IslaError("duplicate, unexpected or out-of-range replay result")
        rows[code] = {"code": code, "expanded": expanded, "narrowed": narrowed}
    if set(rows) != codes:
        raise IslaError("replay omitted generated cases")
    return [rows[code] for code in sorted(rows)]


def harness(codes: list[int]) -> str:
    lines = ["$include <string.sail>", "function main() -> unit = {"]
    for code in codes:
        lines.extend([f"  let code : bits(5) = 0b{code:05b};",
                      "  let expanded = perms_expand(code);",
                      f'  print_endline("case {code} " ^ dec_str(unsigned(expanded))',
                      '    ^ " " ^ dec_str(unsigned(perms_narrow(expanded))));'])
    lines.append("  ()\n}\n")
    return "\n".join(lines)


def mismatch_codes(left: list[Case], right: list[Case]) -> list[int]:
    if [row["code"] for row in left] != [row["code"] for row in right]:
        raise IslaError("cannot compare different case rosters")
    return [a["code"] for a, b in zip(left, right, strict=True) if a != b]


def _replay(sources: list[Path], work: Path, codes: list[int],
            log: Path) -> list[Case] | None:
    work.mkdir(parents=True, exist_ok=True)
    harness_path = work / "harness.sail"
    _write(harness_path, harness(codes))
    messages: list[str] = []
    # Sail also creates its memo file for --dir; sailrig's runtime query inherits
    # this cwd. Keep that query inside native scratch alongside the compilation.
    with chdir(work):
        binary = sailrig.build([*sources, harness_path], work, messages)
    if binary is None:
        _write(log, "\n".join(messages))
        return None
    output = work / "cases.txt"
    if not sailrig.emit(binary, output, messages, timeout=120):
        _write(log, "\n".join(messages))
        raise IslaError(f"oracle execution failed; see {log}")
    _write(log, "\n".join(messages) + "\n" + output.read_text(encoding="utf-8"))
    return parse_cases(output.read_text(encoding="utf-8"), set(codes))


def _mutate(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise IslaError("control mutation no longer has exactly one source anchor")
    return source.replace(old, new, 1)


def control_result(name: str, baseline: list[Case], result: list[Case] | None,
                   log: Path) -> Control:
    """A failed compilation is never a semantic kill."""
    differences = [] if result is None else mismatch_codes(baseline, result)
    status: Literal["killed", "survived", "build_rejected"] = (
        "build_rejected" if result is None else "killed" if differences else "survived")
    return {"name": name, "status": status, "mismatches": differences, "log": str(log)}


def qualify(e: env.Environment) -> Report:
    """Generate fresh witnesses, independently replay, then qualify defect controls."""
    base = e.lane_root / "sail-isla"
    with env.hold_lock(base, "optional Isla qualification"):
        work = base / "campaign"
        work.mkdir(parents=True, exist_ok=True)
        report_path = work / "report.json"
        report_path.unlink(missing_ok=True)
        runner = Runner(e, "qualify")
        z3_lib = _prerequisites(e, runner)
        stamp_path = base / "provision.json"
        if not stamp_path.is_file():
            raise IslaError("optional tools are absent; run sail-isla provision")
        stamp = cast(Stamp, json.loads(stamp_path.read_text(encoding="utf-8")))
        expected_tools = {str(path): sha(path) for path in _binaries(base, e.lane_root, z3_lib)}
        if (stamp["version"] != 1 or stamp["assets_sha256"] != asset_digest(e.root)
                or stamp["binaries"] != expected_tools):
            raise IslaError("optional tools or build inputs changed; run sail-isla provision")
        names = oracle.load(e.root, "capformat").sources
        snapshots: dict[str, bytes] = {}
        for name in names:
            path = e.root / name
            if not path.resolve().is_relative_to(e.root.resolve()):
                raise IslaError(f"source escapes this checkout: {name}")
            snapshots[name] = path.read_bytes()
        sources: list[Path] = []
        for name, raw in snapshots.items():
            target = work / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            sources.append(target)
        process = _process_env(base, z3_lib)
        process["SAIL_DIR"] = str(base / "sail-prefix/share/sail")
        command = [str(base / "sail-prefix/bin/sail"), "--plugin",
                   str(e.lane_root / "sources/isla/isla-sail/_build/default/sail_plugin_isla.cmxs"),
                   "--isla"]
        for name in PRESERVE:
            command += ["--isla-preserve", name]
        command += ["-o", "campaign", *map(str, sources),
                    str(e.root / ASSETS / "campaign.sail")]
        runner.run(command, work, process)
        ir = work / "campaign.ir"
        config = str(e.root / ASSETS / "campaign.toml")
        generated: dict[int, int] = {}
        paths: list[int] = []
        for global_bit, wrapper in enumerate(PRESERVE[:2]):
            output = runner.run([str(base / "target-isla/release/isla-execute-function"),
                                 "-A", str(ir), "-C", config, "-T", "1", "--model",
                                 "--timeout", "60", wrapper, "_"], work, process, timeout=90)
            witnesses = parse_symbolic(output, global_bit)
            paths.append(len(witnesses))
            generated.update(witnesses)
        codes = sorted(generated)
        concrete = runner.run([str(base / "target-testgen/release/vos-isla-testgen"),
                               "-A", str(ir), "-C", config, *map(str, codes)],
                              work, process, timeout=180)
        testgen = parse_cases(concrete, set(codes))
        baseline = _replay(sources, work / "baseline", codes, e.log("sail-isla-baseline"))
        if baseline is None:
            raise IslaError(f"primary Sail oracle failed to build; see {e.log('sail-isla-baseline')}")
        if any(generated[row["code"]] != row["expanded"] for row in baseline):
            raise IslaError("symbolic expansion differs from the primary Sail oracle")
        mismatches = mismatch_codes(baseline, testgen)
        if mismatches:
            raise IslaError(f"isla-testgen differs from the primary Sail oracle: {mismatches}")
        common = "model/model/core/cap_common.sail"
        controls: list[Control] = []
        changes = (
            ("semantic-defect", "0b0001 => 0b000_0000_0001", "0b0001 => 0b000_0000_0011"),
            ("outside-scope", "let E = min(cap_max_E, unsigned(c.E));",
             "let E = min(cap_max_E, unsigned(c.E) + 1);"),
            ("rejected-build", "shape @ code[4 .. 4]", "vos_missing_control_name"),
        )
        for name, old, new in changes:
            mutation = _mutate(snapshots[common].decode("utf-8"), old, new)
            mutated = work / name / "cap_common.sail"
            _write(mutated, mutation)
            inputs = [mutated if key == common else path
                      for key, path in zip(names, sources, strict=True)]
            log = e.log(f"sail-isla-{name}")
            result = _replay(inputs, work / name, codes, log)
            controls.append(control_result(name, baseline, result, log))
        passed = [row["status"] for row in controls] == [
            "killed", "survived", "build_rejected"]
        report: Report = {
            "version": 1, "advisory_only": True, "notice": NOTICE, "passed": passed,
            "source_sha256": {name: hashlib.sha256(raw).hexdigest()
                              for name, raw in snapshots.items()},
            "tool_sha256": expected_tools, "assets_sha256": stamp["assets_sha256"],
            "ir_sha256": sha(ir), "cases": baseline, "symbolic_paths": paths,
            "baseline_matches": len(codes), "testgen_matches": len(codes),
            "controls": controls, "invocations": runner.invocations, "directory": str(work),
        }
        _write(report_path, json.dumps(report, indent=2) + "\n")
        return report
