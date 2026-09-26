#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fresh, source-bound reference IPC comparison on the legacy Wasm environment.

Run in WSL with --out in the assigned native lane. This does not install or
qualify the intended oracle bootstrap. See compiler-component.md for scope.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vos import asm, image, trace
from vos import compiler_component as cc
from vos.cli import compiler_diff as cd


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def require(test: bool, why: str) -> None:
    if not test:
        raise ValueError(why)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("compiler", "compiler-config", "model-snapshot", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--switch", default="certirocq-0.9.1")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    out = Path(args.out).resolve()
    require(sys.platform != "win32" and out.is_relative_to(Path("/root/build"))
            and any(part.startswith("lane-") for part in out.parts), "use a dedicated native lane")
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    steps: list[dict[str, object]] = []

    def execute(name: str, command: list[str], cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess[str]:
        before = time.monotonic()
        done = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
        (out / (name + ".stdout")).write_text(done.stdout, encoding="utf-8", newline="\n")
        (out / (name + ".stderr")).write_text(done.stderr, encoding="utf-8", newline="\n")
        steps.append({"name": name, "argv": command, "cwd": str(cwd), "exit": done.returncode,
                      "seconds": time.monotonic() - before,
                      "stdout_sha256": sha(out / (name + ".stdout")),
                      "stderr_sha256": sha(out / (name + ".stderr"))})
        save(out / "steps.json", steps)
        require(done.returncode == 0, f"{name} failed: {done.stderr[-1500:]}")
        return done

    selected = [root / name for name in (
        "proofs/EndpointIPC.v", "tools/wasm-oracle/ipc_oracle.v", "tools/wasm-oracle/ipc_oracle.c",
        "tools/wasm-oracle/compare_component.py", "tools/wasm-oracle/run_vector.mjs",
        "tools/wasm-oracle/node.sh", "tools/vos/compiler_component.py", "tools/vos/cli/compiler_diff.py",
        "tools/generated/dialect-table.json", "docs/implementation/contracts/compiler-component.md")]
    selected += sorted((root / "tools/vos").rglob("*.py"))
    sources = {str(path): sha(path) for path in selected}
    compiler = Path(args.compiler).resolve()
    config = out / "compcert.ini"
    config.write_bytes(args.compiler_config.read_bytes())
    snapshot = Path(args.model_snapshot).resolve()
    simulator = snapshot / "sail_riscv_sim"
    model = json.loads((snapshot / "model-build.json").read_text())
    require(model.get("exit_code") == 0 and model.get("stages") ==
            {"configure": 0, "build": 0, "ctest": 0}, "model build did not pass")
    require(sha(simulator) == model["artifacts"]["c_emulator/sail_riscv_sim"], "model binary drift")
    for name, digest in model["identity"]["inputs"].items():
        if name.startswith("model/"):
            require(sha(root / name) == digest, "model source changed: " + name)
    profile = out / "profile.json"
    profile.write_bytes((root / "model/config/verifiedos.json").read_bytes())
    producer = out / "producer"
    producer.mkdir()
    execute("package-export", ["opam", "switch", "export", "--switch=" + args.switch,
                               str(producer / "packages.export")], out)
    prefix = Path(execute("switch-prefix", ["opam", "var", "prefix", "--switch=" + args.switch], out).stdout.strip())
    require(prefix.is_absolute() and prefix.is_dir(), "invalid oracle switch prefix")
    coqc = prefix / "bin/coqc"
    tool_paths = [coqc, prefix / "bin/ocamlrun"]
    libraries = {str(path.relative_to(prefix)): sha(path) for path in sorted((prefix / "lib").rglob("*"))
                 if path.is_file() and path.suffix in (".vo", ".cmxs", ".so", ".cma", ".cmxa")}
    require(bool(libraries) and any("CertiRocq" in name for name in libraries), "missing Wasm producer libraries")
    save(producer / "libraries.json", libraries)
    tool_ids = {str(path): sha(path) for path in tool_paths}
    execute("prover-version", ["opam", "exec", "--switch=" + args.switch, "--", str(coqc), "--version"], out)
    node_sh = root / "tools/wasm-oracle/node.sh"
    node_probe = execute("node-identity", ["sh", str(node_sh), "-p", "process.execPath"], out)
    node = Path(node_probe.stdout.strip())
    tool_ids.update({str(node): sha(node), str(compiler): sha(compiler), str(simulator): sha(simulator),
                     str(config): sha(config), str(profile): sha(profile)})
    representation = prefix / "lib/coq/user-contrib/CertiRocq/CodegenWasm/LambdaANF_to_Wasm.v"
    shutil.copy2(representation, producer / "LambdaANF_to_Wasm.v")
    save(producer / "identity.json", {"switch": args.switch, "tools": tool_ids,
        "package_export_sha256": sha(producer / "packages.export"), "libraries_sha256": sha(producer / "libraries.json"),
        "representation_sha256": sha(representation), "scope": "existing legacy environment; intended bootstrap remains open"})
    gallina = (root / "tools/wasm-oracle/ipc_oracle.v").read_text(encoding="utf-8")
    c_source = (root / "tools/wasm-oracle/ipc_oracle.c").read_text(encoding="utf-8")
    endpoint = (root / "proofs/EndpointIPC.v").read_bytes()
    observed_g, observed_c, ids = cc.wrappers(gallina, c_source)
    save(out / "population.json", ids)
    observations: dict[str, tuple[cc.Observation, cc.Observation]] = {}
    rows: list[dict[str, object]] = []
    for mutant in (False, True):
        label = "mask-mutant" if mutant else "positive"
        stage = out / label
        stage.mkdir()
        g, c = observed_g, observed_c
        if mutant:
            require(g.count("(upto 31).") == 1 and c.count("upto(31, masks)") == 1,
                    "semantic mutation site missing or ambiguous")
            g, c = g.replace("(upto 31).", "(upto 32)."), c.replace("upto(31, masks)", "upto(32, masks)")
        (stage / "EndpointIPC.v").write_bytes(endpoint)
        (stage / "ipc_oracle.v").write_text(g, encoding="utf-8", newline="\n")
        source = stage / "ipc_vector.c"
        source.write_text(c, encoding="utf-8", newline="\n")
        for stem in ("EndpointIPC", "ipc_oracle"):
            execute(label + "-" + stem, ["opam", "exec", "--switch=" + args.switch, "--", str(coqc), stem + ".v"], stage)
        wasm = stage / "ipc_oracle.ipc_checks.wasm"
        require(wasm.is_file() and wasm.stat().st_size > 0, "Wasm compiler emitted no current module")
        host = execute(label + "-wasm", [str(node), "--stack-size=10000000", str(root / "tools/wasm-oracle/run_vector.mjs"),
                                         str(wasm), str(out / "population.json")], stage)
        host_observation = cc.decode(host.stdout, ids)
        compiled = cd.compile_c([str(compiler), "-conf", str(config), "-fverifiedos-typed"], source, stage / "compiled")
        save(stage / "compile.json", cd._compiled_json(compiled))
        require(compiled.stream is not None and compiled.exit_code == 0, "component C lowering failed: " + compiled.said)
        if compiled.stream is None:
            raise ValueError("missing compiler stream")
        setup = "        li t0, __vos_observed\n        csetaddr ca0, c4, t0\n        call main\n"
        prologue = cd.PROLOGUE.replace("        call    main\n", setup)
        stream = cd.compose(compiled.stream, prologue) + f"\n.align 3\n__vos_observed:\n.space {(len(ids)+1)*8}\n"
        (stage / "composed.s").write_text(stream, encoding="utf-8", newline="\n")
        sections, symbols, entry = asm.Assembler(stream, label).assemble()
        elf = stage / "ipc_vector.elf"
        image.write_elf(elf, sections, symbols, entry)
        argv = [str(simulator), "--config", str(profile), "--trace-commit", "--inst-limit", "10000000", str(elf)]
        before = time.monotonic()
        target = subprocess.run(argv, cwd=stage, text=True, capture_output=True, timeout=180, check=False)
        raw = target.stdout + target.stderr
        (stage / "trace.log").write_text(raw, encoding="utf-8", newline="\n")
        verdict, code, _ = cd.htif_verdict(raw, target.returncode)
        require(code is not None and verdict in ("pass", "fail") and code < cd.TRAP_BASE, "target fault or incomplete output")
        start_address = symbols["__vos_observed"][1]
        slots: dict[int, int] = {}
        for record in trace.normalize_commit(raw.splitlines()):
            words = record.split()
            if words[0] != "W":
                continue
            address, width = int(words[1], 16), int(words[2])
            if address < start_address + (len(ids)+1)*8 and address + width > start_address:
                require(width == 8 and address % 8 == 0 and words[3] == "0", "malformed component output store")
                index = (address - start_address) // 8
                require(index not in slots, "duplicate component output store")
                slots[index] = int(words[4], 16)
        require(set(slots) == set(range(len(ids)+1)) and slots[len(ids)] == len(ids), "missing or extra target observation")
        require(all(slots[i] in (0, 1) for i in range(len(ids))), "non-Boolean target observation")
        if code is None:
            raise ValueError("missing target first failure")
        target_text = cc.encode(ids, tuple(bool(slots[i]) for i in range(len(ids))), code)
        (stage / "target.json").write_text(target_text, encoding="utf-8", newline="\n")
        (stage / "host.json").write_text(host.stdout, encoding="utf-8", newline="\n")
        target_observation = cc.decode(target_text, ids)
        cc.compare(host_observation, target_observation)
        require(bool(host_observation.first_failure) == mutant, "semantic control failed to distinguish the positive")
        observations[label] = host_observation, target_observation
        rows.append({"name": label, "population": len(ids), "first_failure": code,
                     "false_positions": [i for i, value in enumerate(host_observation.values, 1) if not value],
                     "target_argv": argv, "target_exit": target.returncode, "target_seconds": time.monotonic()-before,
                     "files": {str(path.relative_to(stage)): sha(path) for path in stage.rglob("*") if path.is_file()}})
        print(label, "agrees at", len(ids), "positions; first failure", code, flush=True)
    cross_controls: list[str] = []
    for name, left, right in (("mutated-host", observations["mask-mutant"][0], observations["positive"][1]),
                              ("mutated-target", observations["positive"][0], observations["mask-mutant"][1])):
        try:
            cc.compare(left, right)
        except ValueError as err:
            cross_controls.append(name + ": " + str(err))
        else:
            raise ValueError("cross control survived")
    for i in range(len(ids)):
        values = list(observations["positive"][0].values)
        values[i] = not values[i]
        wrong = cc.decode(cc.encode(ids, tuple(values), i+1), ids)
        try:
            cc.compare(observations["positive"][0], wrong)
        except ValueError:
            pass
        else:
            raise ValueError(f"coordinate control survived: {i+1}")
    require(all(sha(Path(path)) == digest for path, digest in sources.items()), "source changed during comparison")
    require(all(sha(Path(path)) == digest for path, digest in tool_ids.items()), "tool changed during comparison")
    require(all(sha(prefix / name) == digest for name, digest in libraries.items()), "oracle library changed during comparison")
    save(out / "result.json", {"schema": "verifiedos-reference-component-comparison-v1", "passed": True,
        "sources": sources, "tools": tool_ids, "producer_identity_sha256": sha(producer / "identity.json"),
        "population_sha256": sha(out / "population.json"), "rows": rows, "cross_controls": cross_controls,
        "coordinate_controls": len(ids), "model_source_identity": model["identity"],
        "steps_sha256": sha(out / "steps.json"), "seconds": time.monotonic()-started,
        "scope": "finite authored-C reference comparison; no extraction/refinement proof; legacy bootstrap not qualified"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
