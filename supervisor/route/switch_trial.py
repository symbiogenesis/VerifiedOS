# SPDX-License-Identifier: Apache-2.0
"""Run M6.1b-iv's bounded switch-rewrite trial, one stage per check clause.

The trial repeats M6.1b-iii's exchange with a second rewrite, [switch_rewrite.py](
switch_rewrite.py), applied to the normalizer's output. Four commands run in order, each
refusing to run out of it, and every product, record and log goes under `--lane`:

    freeze     hash this script, every frozen input and every tool identity
    provision  re-read both selected licence files, printing each in full, as two
               timestamped and hashed stages; the two-hour bound starts here
    run        checks 1 to 5 as M6.1b-iv's cell lists them, each clause its own stage,
               stopping at the first clause that fails or once the bound is spent
    rehash     after a verdict that stopped short of check 5, rehash every identity

`run` refuses unless this script still hashes to what `freeze` recorded. Each stage
writes `state/<stage>.json` with its predicate, interval, verdict, failures and
evidence; `state/trial.json` holds the verdict and the first failed clause.

    python3 switch_trial.py COMMAND --lane DIR --worktree DIR --revision SHA \
        --profile FILE
"""

import argparse
import datetime
import hashlib
import importlib
import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

BUDGET_SECONDS = 7200
ROWS_PER_PROGRAM = 24
CONTROL_SEED = 20261002
CONTROL_COUNT = 576
NATIVE_FLAGS = ["-std=c11", "-O2", "-fsanitize=undefined", "-fno-sanitize-recover=undefined"]
NODE = {"memory": "start_restart", "output": "fun$step$start_restart",
        "step": "fun$step$start_restart"}
CONTROL = {"memory": "switch_control", "output": "fun$step$switch_control",
           "step": "fun$step$switch_control", "reset": "fun$reset$switch_control"}
VELUS_FLAGS = ["-nomain", "-lib", "-header", "-dclight"]

FROZEN = (
    "supervisor/route/start_restart.lus", "supervisor/route/oracle.c",
    "supervisor/route/probe.py", "supervisor/route/result.json",
    "supervisor/route/exchange-result.json", "supervisor/route/normalize.py",
    "supervisor/route/token_compare.py", "supervisor/route/control.lus",
    "supervisor/route/control.py", "supervisor/route/switch_rewrite.py",
    "supervisor/route/switch_compare.py", "supervisor/route/switch_control.lus",
    "supervisor/route/switch_control.py", "supervisor/route/split_probe.py",
    "supervisor/route/switch_trial.py",
    "supervisor/include/vos_supervisor.h", "supervisor/include/vos_supervisor_effects.h",
    "supervisor/src/supervisor.c", "supervisor/src/effects.c", "supervisor/src/manifest.c",
    "supervisor/test/host.c", "supervisor/test/effects.c", "proofs/SupervisionTree.v",
    "tools/vos/supervisor.py", "tools/vos/cli/supervisor.py",
    "tools/vos/cli/compiler_diff.py", "tools/vos/asm.py", "tools/vos/image.py",
    "tools/generated/dialect-table.json", "docs/assurance/differential-corpus.md",
    "docs/implementation/contracts/purecap-abi.md", "model/model/core/cap_common.sail",
    "kernel/src/context.c", "kernel/include/vos_kernel.h",
    "kernel/include/vos_platform.h", "model/config/verifiedos.json",
    "tools/tests/test_supervisor_route.py", "tools/tests/test_supervisor_switch.py",
)
# The tool identities M6.1b-iii's check 1 held, by their exchange-result.json names.
RECORDED_TOOLS = ("velus", "velus_license", "compcert_license", "ccomp", "compiler_config",
                  "simulator", "profile", "native_cc")

type Json = dict[str, Any]


def now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


def identity(path: Path) -> Json:
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run(argv: list[str], log: Path, cwd: Path | None = None, timeout: int = 3600,
        stdout: Path | None = None) -> Json:
    """Run one command, its output to `log` (stdout to `stdout` if named)."""
    log.parent.mkdir(parents=True, exist_ok=True)
    started = now()
    try:
        done = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout,
                              check=False)
        code: int | None = done.returncode
        out, err = done.stdout, done.stderr
    except subprocess.TimeoutExpired as expired:
        code = None
        out = expired.stdout if isinstance(expired.stdout, bytes) else b""
        err = (expired.stderr if isinstance(expired.stderr, bytes) else b"") \
            + f"\ntimed out after {timeout}s\n".encode()
    if stdout is not None:
        stdout.write_bytes(out)
        log.write_bytes(err)
    else:
        log.write_bytes(out + err)
    record: Json = {"argv": argv, "exit": code, "start_utc": started, "end_utc": now(),
                    "log": identity(log)}
    if stdout is not None:
        record["stdout"] = identity(stdout)
    return record


class Trial:
    def __init__(self, args: argparse.Namespace) -> None:
        self.lane: Path = args.lane
        self.wt: Path = args.worktree
        self.revision: str = args.revision
        self.profile: Path = args.profile
        self.state = self.lane / "state"
        self.route = self.wt / "supervisor" / "route"
        self.script = Path(__file__).resolve()
        self.exchange = json.loads((self.route / "exchange-result.json").read_text("utf-8"))
        self.prior = json.loads((self.route / "result.json").read_text("utf-8"))
        tools = self.exchange["tools"]
        self.velus = Path(tools["velus"]["path"])
        self.source = self.velus.parent
        self.ccomp = Path(tools["ccomp"]["path"])
        self.config = Path(tools["compiler_config"]["path"])
        self.simulator = Path(tools["simulator"]["path"])
        self.cc = Path(tools["native_cc"]["path"])
        self.clang = Path(tools["clang"]["path"])
        self.python = Path(tools["python3"]["path"])
        self.stages: list[Json] = []
        self.provisioned: datetime.datetime | None = None

    # -- identities ---------------------------------------------------------------

    def tool_paths(self) -> dict[str, Path]:
        cc1 = subprocess.run([str(self.cc), "-print-prog-name=cc1"], capture_output=True,
                             encoding="utf-8", check=True, timeout=60).stdout.strip()
        linked = subprocess.run(["ldd", str(self.clang.resolve())], capture_output=True,
                                encoding="utf-8", check=True, timeout=60).stdout
        found = re.search(r"libclang-cpp\S*\s+=>\s+(\S+)", linked)
        if found is None:
            raise ValueError("clang links no libclang-cpp")
        return {
            "velus": self.velus, "velus_license": self.source / "LICENSE",
            "compcert_license": self.source / "CompCert" / "LICENSE",
            "velus_site": self.source / "src" / "ObcToClight" / "Generation.v",
            "velus_printer": self.source / "CompCert" / "cfrontend" / "PrintClight.ml",
            "opam_switch": Path(self.prior["velus"]["opam_switch"]["path"]),
            "ccomp": self.ccomp, "compiler_config": self.config,
            "simulator": self.simulator, "profile": self.profile,
            "native_cc": self.cc, "native_cc1": Path(cc1),
            "clang": self.clang, "libclang_cpp": Path(found.group(1)),
            "python3": self.python,
        }

    def identities(self) -> tuple[dict[str, Json], dict[str, Json]]:
        inputs = {name: identity(self.wt / name) for name in FROZEN}
        tools: dict[str, Json] = {}
        for name, path in self.tool_paths().items():
            record = identity(path)
            resolved = path.resolve()
            if resolved != path:
                record["resolved"] = str(resolved)
            tools[name] = record
        return inputs, tools

    def versions(self) -> Json:
        def first(argv: list[str]) -> str:
            done = subprocess.run(argv, capture_output=True, encoding="utf-8", check=False,
                                  timeout=60)
            lines = (done.stdout or done.stderr).splitlines()
            return lines[0] if lines else ""
        return {"clang": first([str(self.clang), "--version"]),
                "native_cc": first([str(self.cc), "--version"]),
                "python3": first([str(self.python), "--version"])}

    # -- stage bookkeeping ----------------------------------------------------------

    def write(self, name: str, record: Json) -> None:
        self.state.mkdir(parents=True, exist_ok=True)
        (self.state / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n",
                                                 encoding="utf-8", newline="\n")

    def read(self, name: str) -> Json:
        return json.loads((self.state / f"{name}.json").read_text("utf-8"))

    def stage(self, check: int, name: str, predicate: str,
              body: Callable[[Json], list[str]]) -> bool:
        start = datetime.datetime.now(datetime.UTC)
        record: Json = {"check": check, "stage": name, "predicate": predicate,
                        "start_utc": start.isoformat(timespec="seconds")}
        evidence: Json = {}
        if self.provisioned is not None \
                and (start - self.provisioned).total_seconds() > BUDGET_SECONDS:
            failures = ["the two-hour bound after provisioning is spent"]
            record["bound_exhausted"] = True
        else:
            # A stage's own defect is that stage's failure, never a lost record.
            try:
                failures = body(evidence)
            except Exception as err:
                failures = [f"stage error: {err!r}"]
        record.update({"end_utc": now(), "verdict": "passed" if not failures else "failed",
                       "failures": failures, "evidence": evidence})
        self.write(f"stage-{len(self.stages) + 1:02d}-{name}", record)
        self.stages.append(record)
        print(f"[{record['end_utc']}] check {check} {name}: {record['verdict']}"
              + ("" if not failures else ": " + "; ".join(failures)), flush=True)
        return not failures

    # -- commands -----------------------------------------------------------------

    def freeze(self) -> int:
        if (self.state / "provision.json").exists():
            print("refused: provisioning has happened; a freeze must precede it")
            return 2
        start = now()
        inputs, tools = self.identities()
        self.write("freeze", {"stage": "freeze", "start_utc": start, "end_utc": now(),
                              "revision": self.revision, "worktree": str(self.wt),
                              "lane": str(self.lane), "script": identity(self.script),
                              "frozen_inputs": inputs, "tools": tools,
                              "versions": self.versions()})
        print(f"froze {len(inputs)} inputs and {len(tools)} tool identities")
        return 0

    def provision(self) -> int:
        if not (self.state / "freeze.json").exists():
            print("refused: no freeze")
            return 2
        if (self.state / "provision.json").exists():
            print("refused: already provisioned")
            return 2
        frozen = self.read("freeze")
        if identity(self.script)["sha256"] != frozen["script"]["sha256"]:
            print("refused: this script changed after the freeze")
            return 2
        reads: Json = {}
        directory = self.lane / "provision"
        directory.mkdir(parents=True, exist_ok=True)
        for name, path in (("velus", self.source / "LICENSE"),
                           ("compcert", self.source / "CompCert" / "LICENSE")):
            started = now()
            data = path.read_bytes()
            copy = directory / f"licence-{name}.txt"
            copy.write_bytes(data)
            print(f"===== {path} =====")
            print(data.decode("utf-8"))
            record = {"stage": f"licence-{name}", "path": str(path), "read_utc": started,
                      "end_utc": now(), "sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data), "copy": identity(copy)}
            self.write(f"licence-{name}", record)
            reads[name] = record
        self.write("provision", {"stage": "provision", "provisioned_utc": now(),
                                 "licence_reads": reads})
        print("provisioned; the two-hour bound runs from here")
        return 0

    def rehash(self) -> int:
        frozen = self.read("freeze")
        start = now()
        inputs, tools = self.identities()
        changed = [name for name, value in inputs.items()
                   if value["sha256"] != frozen["frozen_inputs"][name]["sha256"]]
        changed += [name for name, value in tools.items()
                    if value["sha256"] != frozen["tools"][name]["sha256"]]
        changed += [] if identity(self.script)["sha256"] == frozen["script"]["sha256"] \
            else ["switch_trial.py"]
        self.write("rehash", {"stage": "rehash", "start_utc": start, "end_utc": now(),
                              "inputs_rehashed": len(inputs), "tools_rehashed": len(tools),
                              "changed": changed,
                              "verdict": "unchanged" if not changed else "changed"})
        print(f"rehash: {changed or 'unchanged'}")
        return 0 if not changed else 1

    def run_checks(self) -> int:
        if not (self.state / "provision.json").exists():
            print("refused: not provisioned")
            return 2
        if (self.state / "trial.json").exists():
            print("refused: the trial has run")
            return 2
        frozen = self.read("freeze")
        if identity(self.script)["sha256"] != frozen["script"]["sha256"]:
            print("refused: this script changed after the freeze")
            return 2
        provision = self.read("provision")
        self.provisioned = datetime.datetime.fromisoformat(str(provision["provisioned_utc"]))
        checks = Checks(self, frozen)
        plan = checks.plan()
        first_failed = None
        for check, name, predicate, body in plan:
            if not self.stage(check, name, predicate, body):
                first_failed = f"check {check} {name}"
                break
        ended = now()
        verdict = "passed" if first_failed is None else "failed"
        not_run = [f"check {check} {name}" for check, name, _, _ in plan[len(self.stages):]]
        self.write("trial", {
            "verdict": verdict, "first_failed": first_failed,
            "provisioned_utc": provision["provisioned_utc"], "ended_utc": ended,
            "elapsed_seconds": int((datetime.datetime.fromisoformat(ended)
                                    - self.provisioned).total_seconds()),
            "budget_seconds": BUDGET_SECONDS,
            "stages": [f"state/stage-{k + 1:02d}-{s['stage']}.json"
                       for k, s in enumerate(self.stages)],
            "not_run": not_run})
        print(f"verdict: {verdict}" + (f" at {first_failed}" if first_failed else ""))
        return 0 if first_failed is None else 1


class Checks:
    """The clauses of checks 1 to 5, in the cell's order."""

    def __init__(self, trial: Trial, frozen: Json) -> None:
        self.t = trial
        self.frozen = frozen
        self.lane = trial.lane
        self.py = str(trial.python)
        self.products: dict[str, Path] = {}
        self.rewrite = load(trial.route / "switch_rewrite.py", "trial_switch_rewrite")

    def plan(self) -> list[tuple[int, str, str, Callable[[Json], list[str]]]]:
        return [
            (1, "identities", "After the fresh freeze, the Velus, licence, compiler, "
             "configuration, simulator, profile and native-compiler hashes match "
             "M6.1b-iii's recorded identities, the opam switch export matches M6.1b-i's, "
             "and the Velus translation site and printer hash to the values the rewrite "
             "declares.", self.identities),
            (1, "node-emits", "Velus re-emits the recorded printed Clight and header for "
             "the start/restart node.", self.node_emits),
            (1, "unnormalized-refused", "The probe driver over the unnormalized Clight is "
             "still refused, natively and by the accepted compiler for its alignment.",
             self.unnormalized),
            (2, "control-emits", "Velus emits the switch control program's Clight.",
             self.control_emits),
            (2, "normalize", "The normalizer accepts the node's and the control program's "
             "printed Clight.", self.normalize),
            (2, "rewrite", "The switch rewrite accepts both normalized programs.",
             self.rewrite_both),
            (2, "node-comparison", "An independent clang-token comparison shows the "
             "rewritten node differing from its normalized form only at declared switch "
             "groups.", self.node_comparison),
            (2, "control-comparison", "The same comparison shows the rewritten control "
             "program differing only at declared switch groups and carrying every declared "
             "shape, a nested group and labels out of plain order.",
             self.control_comparison),
            (2, "comparison-controls", "The comparison fails on a rewritten node with one "
             "comparison label moved and on one with a statement changed outside every "
             "group.", self.comparison_controls),
            (2, "refusals", "The rewrite refuses every authored undeclared-shape variant "
             "of the normalized node, writing nothing.", self.refusals),
            (2, "identity", "The rewrite returns switch-free input byte-identically: "
             "M6.1b-iii's normalized control program and both rewritten programs.",
             self.switch_free),
            (3, "node-compiles", "The rewritten node compiles through the accepted typed "
             "route.", self.node_compiles),
            (3, "control-compiles", "The rewritten control program compiles through the "
             "accepted typed route.", self.control_compiles),
            (4, "reference", "The reference comparison passes.", self.reference),
            (4, "fixtures", "The regenerated fixtures reproduce the recorded digest.",
             self.fixtures),
            (4, "probe-native", "The unchanged probe over the rewritten node, split into "
             "programs that fit the text window, agrees on every row natively.",
             self.probe_native),
            (4, "probe-target", "Every split probe program agrees on every row through "
             "compiler-diff program.", self.probe_target),
            (4, "perturbed", "The perturbed probe program holding the moved check fails "
             "natively and yields a failing comparison verdict on target.",
             self.perturbed),
            (4, "control-native", "The split control drivers agree natively on every row "
             "of the seeded generated set.", self.control_native),
            (4, "control-target", "Every split control program agrees on every row through "
             "compiler-diff program.", self.control_target),
            (5, "rehash", "Every frozen input and tool identity rehashes unchanged.",
             self.rehash),
        ]

    # -- helpers ------------------------------------------------------------------

    def subdir(self, name: str) -> Path:
        path = self.lane / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def velus(self, source: Path, out: Path) -> Json:
        argv = [str(self.t.velus), *VELUS_FLAGS, "-o", str(out), str(source)]
        record = run(argv, out.with_suffix(".velus.log"))
        for suffix, key in ((".light.c", "clight"), (".h", "header")):
            product = out.with_name(out.stem + suffix)
            if product.exists():
                record[key] = identity(product)
        return record

    def native(self, source: Path, evidence: Json) -> int | None:
        binary = source.with_suffix("")
        built = run([str(self.t.cc), *NATIVE_FLAGS, str(source), "-o", str(binary)],
                    source.with_suffix(".native.log"))
        evidence["compile"] = built
        if built["exit"] != 0:
            return None
        evidence["binary"] = identity(binary)
        ran = run([str(binary)], source.with_suffix(".run.log"))
        evidence["run"] = ran
        code = ran["exit"]
        return code if isinstance(code, int) else None

    def program_run(self, sources: list[Path], keep: Path, report: Path) -> tuple[Json, Json]:
        argv = [self.py, str(self.t.wt / "tools" / "run.py"), "compiler-diff", "program",
                "--ccomp", str(self.t.ccomp), "--ccomp-arg=-conf",
                f"--ccomp-arg={self.t.config}", "--ccomp-arg=-fverifiedos-typed",
                "--simulator", str(self.t.simulator), "--profile", str(self.t.profile),
                "--keep", str(keep), "--timeout", "900", "--run-timeout", "600", "--json",
                *map(str, sources)]
        record = run(argv, report.with_suffix(".log"), stdout=report, timeout=7200)
        payload = json.loads(report.read_text("utf-8"))
        return record, payload

    @staticmethod
    def summary(payload: Json) -> list[Json]:
        programs = payload.get("programs")
        out: list[Json] = []
        for entry in programs if isinstance(programs, list) else []:
            ccomp = entry.get("ccomp") or {}
            ran = entry.get("run") or {}
            out.append({"name": entry.get("name"), "verdict": entry.get("verdict"),
                        "detail": entry.get("detail"), "source_sha256": entry.get("source_sha256"),
                        "ccomp_exit": ccomp.get("exit"), "stream_lines": ccomp.get("lines"),
                        "stream_sha256": ccomp.get("stream_sha256"),
                        "preprocessed_sha256": ccomp.get("preprocessed_sha256"),
                        "image_bytes": entry.get("image_bytes"),
                        "refusals": entry.get("refusals"),
                        "run_code": ran.get("code"), "records": ran.get("records"),
                        "trace_digest": ran.get("digest")})
        return out

    # -- check 1 ------------------------------------------------------------------

    def identities(self, evidence: Json) -> list[str]:
        tools = self.frozen["tools"]
        recorded = self.t.exchange["tools"]
        failures = []
        matches: Json = {}
        for name in RECORDED_TOOLS:
            ok = tools[name]["sha256"] == recorded[name]["sha256"]
            matches[name] = ok
            if not ok:
                failures.append(f"{name} hashes to {tools[name]['sha256']}, "
                                f"recorded {recorded[name]['sha256']}")
        switch = self.t.prior["velus"]["opam_switch"]["sha256"]
        matches["opam_switch"] = tools["opam_switch"]["sha256"] == switch
        if not matches["opam_switch"]:
            failures.append("the opam switch export differs from M6.1b-i's")
        for name, declared in (("velus_site", self.rewrite.SITE),
                               ("velus_printer", self.rewrite.PRINTER)):
            matches[name] = tools[name]["sha256"] == declared["sha256"]
            if not matches[name]:
                failures.append(f"{name} does not hash to the declared {declared['sha256']}")
        evidence["recorded_hashes_match"] = matches
        evidence["freeze"] = identity(self.t.state / "freeze.json")
        prior = self.t.exchange["frozen_inputs"]
        evidence["changed_since_prior_freeze"] = {
            name: {"prior": prior[name], "frozen": value["sha256"]}
            for name, value in self.frozen["frozen_inputs"].items()
            if name in prior and prior[name] != value["sha256"]}
        return failures

    def node_emits(self, evidence: Json) -> list[str]:
        out = self.subdir("node") / "start_restart.lus"
        record = self.velus(self.t.route / "start_restart.lus", out)
        evidence["velus"] = record
        recorded = self.t.exchange["evidence"]["check1"]["velus_node"]
        failures = []
        if record["exit"] != 0:
            failures.append(f"Velus exited {record['exit']}")
        for key in ("clight", "header"):
            got = record.get(key)
            if not isinstance(got, dict) or got["sha256"] != recorded[key]["sha256"]:
                failures.append(f"the {key} differs from the recorded one")
        self.products["node_clight"] = out.with_name("start_restart.light.c")
        return failures

    def unnormalized(self, evidence: Json) -> list[str]:
        failures = []
        oracle_dir = self.subdir("oracle")
        binary = oracle_dir / "oracle"
        include = self.t.wt / "supervisor" / "include"
        built = run([str(self.t.cc), "-std=c11", "-O2", "-Wall", "-I", str(include),
                     str(self.t.route / "oracle.c"),
                     str(self.t.wt / "supervisor" / "src" / "supervisor.c"),
                     str(self.t.wt / "supervisor" / "src" / "manifest.c"), "-o", str(binary)],
                    oracle_dir / "build.log")
        evidence["oracle_build"] = built
        if built["exit"] != 0:
            return ["the oracle did not build"]
        evidence["oracle_binary"] = identity(binary)
        fixtures = oracle_dir / "fixtures.txt"
        evidence["oracle_run"] = run([str(binary)], oracle_dir / "run.log", stdout=fixtures)
        if evidence["oracle_run"]["exit"] != 0:
            return ["the oracle run failed"]
        self.products["fixtures"] = fixtures
        work = self.subdir("unnormalized")
        driver = work / "probe.c"
        emit = run([self.py, str(self.t.route / "probe.py"), "--fixtures", str(fixtures),
                    "--emitted", str(self.products["node_clight"]),
                    "--memory", NODE["memory"], "--output", NODE["output"],
                    "--step", NODE["step"], "--out", str(driver)], work / "emit.log")
        evidence["emit"] = emit
        if emit["exit"] != 0:
            return ["probe.py failed over the unnormalized Clight"]
        evidence["driver"] = identity(driver)
        native: Json = {}
        code = self.native(driver, native)
        evidence["native"] = native
        if code is not None:
            failures.append("the unnormalized driver compiled natively")
        record, payload = self.program_run([driver], work / "purecap",
                                             work / "purecap-report.json")
        evidence["target"] = record
        programs = self.summary(payload)
        evidence["target_programs"] = programs
        said = ""
        entries = payload.get("programs")
        if isinstance(entries, list) and entries and isinstance(entries[0].get("ccomp"), dict):
            said = str(entries[0]["ccomp"].get("said", ""))
        evidence["target_diagnostic"] = said
        if [p["verdict"] for p in programs] != ["ccomp-refused"] \
                or "alignment specified" not in said:
            failures.append("the accepted compiler did not refuse the unnormalized driver "
                            "for its alignment")
        return failures

    # -- check 2 ------------------------------------------------------------------

    def control_emits(self, evidence: Json) -> list[str]:
        out = self.subdir("control") / "switch_control.lus"
        record = self.velus(self.t.route / "switch_control.lus", out)
        evidence["velus"] = record
        self.products["control_clight"] = out.with_name("switch_control.light.c")
        return [] if record["exit"] == 0 and "clight" in record \
            else [f"Velus exited {record['exit']}"]

    def normalize(self, evidence: Json) -> list[str]:
        failures = []
        for key, source in (("node", self.products["node_clight"]),
                            ("control", self.products["control_clight"])):
            out = source.with_name(source.name.replace(".light.c", ".norm.c"))
            record = run([self.py, str(self.t.route / "normalize.py"), str(source),
                          "--out", str(out), "--record", str(out.with_suffix(".json"))],
                         out.with_suffix(".log"))
            evidence[key] = record
            if record["exit"] != 0:
                failures.append(f"the normalizer refused the {key}")
                continue
            record["output"] = identity(out)
            record["record"] = identity(out.with_suffix(".json"))
            self.products[f"{key}_norm"] = out
        if "node_norm" in self.products:
            recorded = self.t.exchange["erasure"]["node"]["output"]["sha256"]
            evidence["node_matches_m61biii_normalized"] = \
                identity(self.products["node_norm"])["sha256"] == recorded
        return failures

    def rewrite_both(self, evidence: Json) -> list[str]:
        failures = []
        for key in ("node", "control"):
            source = self.products[f"{key}_norm"]
            out = source.with_name(source.name.replace(".norm.c", ".rw.c"))
            record = run([self.py, str(self.t.route / "switch_rewrite.py"), str(source),
                          "--out", str(out), "--record", str(out.with_suffix(".json"))],
                         out.with_suffix(".log"))
            evidence[key] = record
            if record["exit"] != 0:
                failures.append(f"the rewrite refused the normalized {key}")
                continue
            record["output"] = identity(out)
            record["record"] = identity(out.with_suffix(".json"))
            written = json.loads(out.with_suffix(".json").read_text("utf-8"))
            record["by_shape"] = written["by_shape"]
            record["groups"] = written["groups"]
            self.products[f"{key}_rw"] = out
        return failures

    def compare(self, normalized: Path, rewritten: Path, mode: str, report: Path) -> Json:
        record = run([self.py, str(self.t.route / "switch_compare.py"), "--clang",
                      str(self.t.clang), "--normalized", str(normalized), "--rewritten",
                      str(rewritten), f"--{mode}", "--out", str(report)],
                     report.with_suffix(".log"))
        if report.exists():
            record["report"] = identity(report)
            written = json.loads(report.read_text("utf-8"))
            for key in ("verdict", "failures", "lowered", "by_shape", "groups"):
                record[key] = written.get(key)
        return record

    def node_comparison(self, evidence: Json) -> list[str]:
        record = self.compare(self.products["node_norm"], self.products["node_rw"], "node",
                              self.subdir("compare") / "node.json")
        evidence.update(record)
        return [] if record["exit"] == 0 and record.get("verdict") == "pass" \
            else [f"comparison: {record.get('failures')}"]

    def control_comparison(self, evidence: Json) -> list[str]:
        record = self.compare(self.products["control_norm"], self.products["control_rw"],
                              "control", self.subdir("compare") / "control.json")
        evidence.update(record)
        return [] if record["exit"] == 0 and record.get("verdict") == "pass" \
            else [f"comparison: {record.get('failures')}"]

    def comparison_controls(self, evidence: Json) -> list[str]:
        text = self.products["node_rw"].read_text("ascii")
        variants = {
            "label-moved": text.replace(") == 0) {", ") == 1) {", 1),
            "outside-changed": text.replace("(*obc2c$out).first_unit = 0U;",
                                            "(*obc2c$out).first_unit = 1U;", 1),
        }
        failures = []
        work = self.subdir("compare/controls")
        for name, variant in variants.items():
            if variant == text:
                failures.append(f"the {name} control changed nothing")
                continue
            path = work / f"{name}.c"
            path.write_text(variant, encoding="ascii", newline="\n")
            record = self.compare(self.products["node_norm"], path, "node",
                                  work / f"{name}.json")
            record["variant"] = identity(path)
            evidence[name] = record
            if record["exit"] != 1 or record.get("verdict") != "fail":
                failures.append(f"the comparison did not fail the {name} control")
        return failures

    def refusals(self, evidence: Json) -> list[str]:
        text = self.products["node_norm"].read_text("ascii")
        first_case = "    case 0:\n      (*obc2c$out).storage_grant = 0U;\n      break;\n"
        variants = {
            "fall-through": text.replace(
                "(*obc2c$out).storage_grant = 0U;\n      break;\n",
                "(*obc2c$out).storage_grant = 0U;\n", 1),
            "no-case": text.replace(first_case, "", 1),
            "case-after-default": text.replace(
                "(*obc2c$out).storage_grant = 1U;\n",
                "(*obc2c$out).storage_grant = 1U;\n    case 1:\n      break;\n", 1),
            "labels-out-of-order": text.replace(
                first_case, "    case 1:\n      (*obc2c$out).storage_grant = 0U;\n"
                "      break;\n" + first_case, 1),
            "hexadecimal-label": text.replace("    case 0:\n", "    case 0x0:\n", 1),
            "empty-case-in-chain": text.replace(
                first_case, "    case 0:\n      break;\n" + first_case.replace(
                    "case 0:", "case 1:"), 1),
            "break-in-default": text.replace(
                "(*obc2c$out).storage_grant = 1U;\n",
                "(*obc2c$out).storage_grant = 1U;\n      break;\n", 1),
            "brace-in-body": text.replace(
                "(*obc2c$out).storage_grant = 0U;\n",
                "{ (*obc2c$out).storage_grant = 0U; }\n", 1),
        }
        failures = []
        work = self.subdir("refusals")
        for name, variant in variants.items():
            if variant == text:
                failures.append(f"the {name} variant changed nothing")
                continue
            path = work / f"{name}.c"
            path.write_text(variant, encoding="ascii", newline="\n")
            out = work / f"{name}.out.c"
            out.unlink(missing_ok=True)
            record = run([self.py, str(self.t.route / "switch_rewrite.py"), str(path),
                          "--out", str(out)], work / f"{name}.log")
            record["variant"] = identity(path)
            record["said"] = (work / f"{name}.log").read_text("utf-8").strip()
            record["wrote_output"] = out.exists()
            evidence[name] = record
            if record["exit"] != 2 or record["wrote_output"]:
                failures.append(f"the rewrite did not refuse the {name} variant")
        return failures

    def switch_free(self, evidence: Json) -> list[str]:
        failures = []
        work = self.subdir("identity")
        old = work / "control.lus"
        emitted = self.velus(self.t.route / "control.lus", old)
        evidence["velus_old_control"] = emitted
        if emitted["exit"] != 0 or "clight" not in emitted:
            return ["Velus did not re-emit M6.1b-iii's control program"]
        old_clight = old.with_name("control.light.c")
        old_norm = work / "control.norm.c"
        normalized = run([self.py, str(self.t.route / "normalize.py"), str(old_clight),
                          "--out", str(old_norm)], work / "control.norm.log")
        evidence["normalize_old_control"] = normalized
        if normalized["exit"] != 0:
            return ["the normalizer refused M6.1b-iii's control program"]
        recorded = self.t.exchange["erasure"]["control"]["output"]["sha256"]
        evidence["old_control_matches_m61biii_normalized"] = \
            identity(old_norm)["sha256"] == recorded
        for name, source in (("old-control", old_norm), ("node", self.products["node_rw"]),
                             ("control", self.products["control_rw"])):
            out = work / f"{name}.identity.c"
            record = run([self.py, str(self.t.route / "switch_rewrite.py"), str(source),
                          "--out", str(out), "--record", str(work / f"{name}.identity.json")],
                         work / f"{name}.identity.log")
            record["input"] = identity(source)
            if record["exit"] == 0:
                record["output"] = identity(out)
                written = json.loads((work / f"{name}.identity.json").read_text("utf-8"))
                record["lowered"] = written["lowered"]
                record["byte_identical"] = out.read_bytes() == source.read_bytes()
            evidence[name] = record
            if record["exit"] != 0 or not record.get("byte_identical") or record.get("lowered"):
                failures.append(f"the rewrite did not return {name} byte-identically")
        return failures

    # -- check 3 ------------------------------------------------------------------

    def typed_compile(self, key: str, evidence: Json) -> list[str]:
        # compile_c is compiler-diff program's own front half, a frozen input.
        sys.path.insert(0, str(self.t.wt / "tools"))
        compiler_diff = importlib.import_module("vos.cli.compiler_diff")
        source = self.products[f"{key}_rw"]
        fresh = self.subdir(f"compile/{key}")
        ccomp = [str(self.t.ccomp), "-conf", str(self.t.config), "-fverifiedos-typed"]
        started = now()
        compiled = compiler_diff.compile_c(ccomp, source, fresh, 900)
        evidence.update({"start_utc": started, "end_utc": now(),
                         "argv": list(compiled.argv), "exit": compiled.exit_code,
                         "said": compiled.said, "stream_sha256": compiled.stream_sha256,
                         "lines": compiled.lines,
                         "preprocess_argv": list(compiled.preprocessed.argv),
                         "preprocessed_sha256": compiled.preprocessed.sha256,
                         "source": identity(source)})
        if compiled.stream is None:
            return [f"ccomp exited {compiled.exit_code}: {compiled.said}"]
        return []

    def node_compiles(self, evidence: Json) -> list[str]:
        return self.typed_compile("node", evidence)

    def control_compiles(self, evidence: Json) -> list[str]:
        return self.typed_compile("control", evidence)

    # -- check 4 ------------------------------------------------------------------

    def reference(self, evidence: Json) -> list[str]:
        work = self.subdir("reference")
        record = run([self.py, str(self.t.wt / "tools" / "run.py"), "supervisor", "check"],
                     work / "supervisor-check.log")
        evidence.update(record)
        said = (work / "supervisor-check.log").read_text("utf-8")
        evidence["output"] = said[-2000:]
        named = re.search(r"^report: (\S+)$", said, re.MULTILINE)
        if named is None:
            return [f"supervisor check exited {record['exit']} and named no report"]
        report = Path(named.group(1))
        evidence["report"] = identity(report)
        body = json.loads(report.read_text("utf-8"))
        evidence["report_body"] = body
        if record["exit"] != 0 or body.get("comparison") != "passed":
            return [f"supervisor check exited {record['exit']}, comparison "
                    f"{body.get('comparison')}"]
        return []

    def fixtures(self, evidence: Json) -> list[str]:
        fixtures = self.products["fixtures"]
        recorded = self.t.exchange["evidence"]["check4"]["fixtures"]["recorded_sha256"]
        got = identity(fixtures)
        rows = len(fixtures.read_text("utf-8").splitlines())
        evidence.update({"fixtures": got, "rows": rows, "recorded_sha256": recorded})
        return [] if got["sha256"] == recorded and rows == 576 \
            else ["the regenerated fixtures differ from the recorded digest"]

    def split(self, driver: Path, out_dir: Path, evidence: Json) -> list[Path]:
        record = run([self.py, str(self.t.route / "split_probe.py"), str(driver), "--step",
                      NODE["step"], "--rows", str(ROWS_PER_PROGRAM), "--out-dir", str(out_dir),
                      "--record", str(out_dir / "split.json")], out_dir / "split.log")
        evidence["split"] = record
        if record["exit"] != 0:
            raise ValueError("split_probe.py refused the driver")
        written = json.loads((out_dir / "split.json").read_text("utf-8"))
        evidence["split_record"] = identity(out_dir / "split.json")
        evidence["programs"] = written["programs"]
        return [Path(item["path"]) for item in written["programs"]]

    def probe_driver(self, work: Path, perturb: bool, evidence: Json) -> Path:
        driver = work / "probe.c"
        emit = run([self.py, str(self.t.route / "probe.py"), "--fixtures",
                    str(self.products["fixtures"]), "--emitted", str(self.products["node_rw"]),
                    "--memory", NODE["memory"], "--output", NODE["output"],
                    "--step", NODE["step"], "--out", str(driver),
                    *(["--perturb"] if perturb else [])], work / "emit.log")
        evidence["emit"] = emit
        if emit["exit"] != 0:
            raise ValueError("probe.py failed")
        evidence["driver"] = identity(driver)
        return driver

    def probe_native(self, evidence: Json) -> list[str]:
        work = self.subdir("probe")
        driver = self.probe_driver(work, False, evidence)
        failures = []
        whole: Json = {}
        if self.native(driver, whole) != 0:
            failures.append("the unsplit probe driver did not agree natively")
        evidence["unsplit_native"] = whole
        programs = self.split(driver, self.subdir("probe/split"), evidence)
        self.products["probe_programs"] = programs[0].parent
        runs: Json = {}
        for program in programs:
            one: Json = {}
            code = self.native(program, one)
            runs[program.name] = one
            if code != 0:
                failures.append(f"{program.name} did not agree natively (exit {code})")
        evidence["split_native"] = runs
        return failures

    def target(self, sources: list[Path], name: str, evidence: Json) -> list[str]:
        work = self.subdir(name)
        record, payload = self.program_run(sources, work / "purecap",
                                             work / "purecap-report.json")
        evidence["target"] = record
        evidence["green"] = payload.get("green")
        programs = self.summary(payload)
        evidence["programs"] = programs
        evidence["harness_sources_sha256"] = payload.get("sources_sha256")
        failures = [f"{p['name']}: {p['verdict']} ({p['detail']})" for p in programs
                    if p["verdict"] != "pass"]
        if len(programs) != len(sources):
            failures.append(f"{len(programs)} reports for {len(sources)} programs")
        if record["exit"] != 0 or payload.get("green") is not True:
            failures.append(f"compiler-diff exited {record['exit']}, green "
                            f"{payload.get('green')}")
        return failures

    def probe_target(self, evidence: Json) -> list[str]:
        programs = sorted(self.products["probe_programs"].glob("probe-*.c"))
        return self.target(programs, "probe-target", evidence)

    def perturbed(self, evidence: Json) -> list[str]:
        work = self.subdir("probe-perturbed")
        driver = self.probe_driver(work, True, evidence)
        programs = self.split(driver, self.subdir("probe-perturbed/split"), evidence)
        plain = sorted(self.products["probe_programs"].glob("probe-*.c"))
        moved = [p for p, q in zip(programs, plain, strict=True)
                 if p.read_bytes() != q.read_bytes()]
        evidence["programs_differing"] = [p.name for p in moved]
        if len(moved) != 1:
            return [f"{len(moved)} perturbed programs differ from the plain split"]
        native: Json = {}
        code = self.native(moved[0], native)
        evidence["native"] = native
        failures = [] if code == 1 else [f"the perturbed program exited {code} natively"]
        record, payload = self.program_run([moved[0]], work / "purecap",
                                             work / "purecap-report.json")
        evidence["target"] = record
        programs_run = self.summary(payload)
        evidence["target_programs"] = programs_run
        if [(p["verdict"], p["run_code"]) for p in programs_run] != [("fail", 1)]:
            failures.append(f"the perturbed program's target verdict is "
                            f"{[(p['verdict'], p['run_code']) for p in programs_run]}")
        return failures

    def control_native(self, evidence: Json) -> list[str]:
        work = self.subdir("control-driver")
        out_dir = self.subdir("control-driver/programs")
        emit = run([self.py, str(self.t.route / "switch_control.py"), "--seed",
                    str(CONTROL_SEED), "--count", str(CONTROL_COUNT), "--rows",
                    str(ROWS_PER_PROGRAM), "--emitted", str(self.products["control_rw"]),
                    "--memory", CONTROL["memory"], "--output", CONTROL["output"],
                    "--step", CONTROL["step"], "--reset", CONTROL["reset"],
                    "--out-dir", str(out_dir), "--summary", str(work / "summary.json")],
                   work / "emit.log")
        evidence["emit"] = emit
        if emit["exit"] != 0:
            return ["switch_control.py failed"]
        evidence["summary"] = json.loads((work / "summary.json").read_text("utf-8"))
        evidence["summary_identity"] = identity(work / "summary.json")
        programs = sorted(out_dir.glob("control-*.c"))
        self.products["control_programs"] = out_dir
        failures = []
        runs: Json = {}
        for program in programs:
            one: Json = {}
            code = self.native(program, one)
            runs[program.name] = one
            if code != 0:
                failures.append(f"{program.name} did not agree natively (exit {code})")
        evidence["native"] = runs
        return failures

    def control_target(self, evidence: Json) -> list[str]:
        programs = sorted(self.products["control_programs"].glob("control-*.c"))
        return self.target(programs, "control-target", evidence)

    # -- check 5 ------------------------------------------------------------------

    def rehash(self, evidence: Json) -> list[str]:
        inputs, tools = self.t.identities()
        frozen_inputs = self.frozen["frozen_inputs"]
        frozen_tools = self.frozen["tools"]
        changed = [n for n, v in inputs.items()
                   if v["sha256"] != frozen_inputs[n]["sha256"]]
        changed += [n for n, v in tools.items()
                    if v["sha256"] != frozen_tools[n]["sha256"]]
        if identity(self.t.script)["sha256"] != self.frozen["script"]["sha256"]:
            changed.append("switch_trial.py")
        evidence.update({"inputs_rehashed": len(inputs), "tools_rehashed": len(tools),
                         "changed": changed})
        return [f"{name} changed" for name in changed]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("freeze", "provision", "run", "rehash"))
    parser.add_argument("--lane", required=True, type=Path)
    parser.add_argument("--worktree", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--profile", required=True, type=Path)
    args = parser.parse_args(argv)
    trial = Trial(args)
    return {"freeze": trial.freeze, "provision": trial.provision, "run": trial.run_checks,
            "rehash": trial.rehash}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
