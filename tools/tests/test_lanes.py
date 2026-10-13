# SPDX-License-Identifier: Apache-2.0
"""The two lanes as one command surface, held to the declaration that makes it one.

[vos/commands.py](../vos/commands.py) says which subcommands of a guest
command answer on either lane, and `run.py` reads that `host_ok` set to decide whether
to re-launch into WSL. A declaration like that is worth having only if the command it
names answers where it says it does, and for as long as `model.py` loaded the build
environment before it dispatched, the set was true of `run.py` and false of the module
behind it: three of its members printed *the model loops run inside WSL* on the lane the
table declared them answerable on. What is held here is that claim at the seam where it
broke, for every member of every set: each declared subcommand is dispatched in this
process, on whichever lane this process is, and has to answer.

Operational declarations are exercised with arguments that reach their handlers:
argparse's successful help exit alone cannot establish a handler's lane. Explicit
help-only declarations are checked for their usage text and successful exit, which
establishes only that help answers on the declared lane.

The command modules are imported once in this test module's worker process. The
runner isolates its patches and redirected streams from other test modules.
"""

import io
import json
import shutil
import tempfile
from collections.abc import Callable
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from functools import partial
from importlib import import_module
from itertools import product
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from tests.test_boot_attachments import _attached_recipe
from tests.test_boot_chain import _chain_reports
from tests.test_boot_crypto import _shard, _staged_root
from vos import (
    admission,
    boot_crypto_target,
    composer,
    kernelrun,
    memory_planner,
    rtltrace,
    rvfi,
    vector_bitcount,
)
from vos import composition as production
from vos.commands import COMMANDS, LANE_REFERENCE, help_declarations, lane_reference

_ROOT = TOOLS.parent
_README = TOOLS / "README.md"

# Every command carrying a `host_ok` set, imported once here. The dispatch a case makes
# is this module's `main(argv)`, which is exactly what `run.py` calls once it has
# declined to hop.
_MODULES: dict[str, ModuleType] = {
    command.name: import_module(command.module)
    for command in COMMANDS if command.host_ok
}

# What one declared subcommand has to be handed to reach its handler. A scratch
# directory is passed in because three of them write something, and a run that wrote
# into the checkout would be a test with a side effect on the tree every other case
# reads.
type Argv = Callable[[Path], list[str]]


def _trivial_schema(scratch: Path) -> list[str]:
    """A schema and a config that agree, authored here rather than taken from the tree.

    The shipped configurations are validated against the *generated* schema, which is a
    build artifact and so absent on a lane that has never built. What this case decides
    is that the subcommand answers at all, and a two-key pair decides that without
    making the case depend on a tree the host cannot produce.
    """
    schema = scratch / "schema.json"
    config = scratch / "config.json"
    schema.write_text(
        json.dumps({"type": "object", "properties": {"a": {"type": "integer"}}}),
        encoding="utf-8", newline="")
    config.write_text(json.dumps({"a": 1}), encoding="utf-8", newline="")
    return [str(schema), str(config)]


def _placement_export(scratch: Path) -> list[str]:
    (scratch / "proofs").mkdir(exist_ok=True)
    (scratch / "tools" / "generated").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_ROOT / "proofs" / "MemoryPlan.v", scratch / "proofs" / "MemoryPlan.v")
    return []


def _portable_plan(action: str, scratch: Path) -> list[str]:
    raw = {"name": "lane-route", "pools": [{"id": "p", "capacity": 4}],
           "buffers": [{"id": "a", "size": 2, "allowed_pools": ["p"],
                        "intervals": [[0, 1]]}]}
    placement = [{"id": "a", "pool": "p", "offset": 0}]
    instance = scratch / "portable-instance.json"
    candidate = scratch / "portable-placement.json"
    evidence = scratch / "portable-evidence.json"
    instance.write_text(json.dumps(raw), encoding="utf-8", newline="")
    candidate.write_text(json.dumps(placement), encoding="utf-8", newline="")
    evidence.write_text(json.dumps(memory_planner.plan(
        memory_planner.parse_instance(raw), placement)), encoding="utf-8", newline="")
    common = ["--instance", str(instance)]
    if action == "plan":
        return [*common, "--baseline", str(candidate)]
    if action == "check":
        return [*common, "--candidate", str(candidate)]
    if action == "verify":
        return [*common, "--evidence", str(evidence)]
    return [*common, "--work-budget", "8"]


def _rtl_frame(scratch: Path) -> list[str]:
    """One retirement, as the golden trace and as an RTL frame that agree on it."""
    reference = scratch / "golden.trace"
    frame = scratch / "rtl.frame"
    reference.write_text("I 0 0000000080000000 00100293\nX 5 0 0000000000000001\n",
                         encoding="utf-8", newline="")
    frame.write_text(rtltrace.encode([rtltrace.Retire(rvfi.Execution(
        wire=rtltrace.WIRE, pc_rdata=0x80000000, pc_wdata=0x80000004, insn=0x00100293,
        rd_addr=5, rd_wdata=1))]), encoding="utf-8", newline="")
    return [str(frame), str(reference)]


def _kernel_vectors(scratch: Path) -> list[str]:
    """One line of each `kt` family the reader decides, over one declared frame and image.

    The verdict bits are the reader's own, found by trying each assignment, because
    this run asks whether `kernel reader` answers on this lane; whether the reader
    agrees with KernelInstance.v is `kernel check`'s question, over generated vectors.
    """
    regs = " ".join("0/0" for _ in range(kernelrun.REGISTER_COUNT))
    head = ["kt d 0 1 10:20 0:30:40 1:50:60 2:70:80", "kt r 0:1:0 1:1:1 2:0:0",
            f"kt s 1 {regs} | 11 12 13"]
    lines = list(head)
    for family, body, width in (("c", "1 - -", 3), ("b", "1 -", 5), ("f", "0 -", 5),
                                ("run", "0 1 1 - - | - | -", 1)):
        for bits in product("01", repeat=width):
            line = f"kt {family} {body} -> {' '.join(bits)}"
            if not kernelrun.check_vectors([*head, line])[1]:
                lines.append(line)
                break
        else:
            raise AssertionError(f"no verdict assignment agrees with the reader on kt {family}")
    vectors = scratch / "kernel-vectors.txt"
    vectors.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return ["--vectors", str(vectors)]


def _memory_encoding(scratch: Path) -> list[str]:
    instance = scratch / "encoding-instance.json"
    instance.write_text(json.dumps({
        "name": "lane-encoding", "pools": [{"id": "a", "capacity": 1}],
        "buffers": [{"id": "x", "size": 1, "allowed_pools": ["a"], "intervals": [[0, 1]]}],
    }), encoding="utf-8", newline="")
    return ["--instance", str(instance), "--bound", "0", "--json"]


def _composition_fixture(scratch: Path) -> list[str]:
    composition = composer.reference_fixture(_ROOT)
    (scratch / "descriptors.json").write_bytes(composer.canonical_bytes(composer.document(composition)))
    return ["descriptors.json", "--output", "out/graph.json"]


def _production_fixture(action: str, scratch: Path) -> list[str]:
    """Exercise host dispatch using bound declarations with unresolved target slots."""
    raw = json.loads((_ROOT / production.EXAMPLE).read_bytes())
    paths = {production.EXAMPLE, raw["roster"], raw["configuration"]["path"], *production.PRODUCERS}
    for member in raw["members"]:
        paths.update(ref["path"] for ref in member["sources"])
        for ref in (member["descriptor"], member["derivation"]["source"]):
            if ref is not None:
                paths.add(ref["path"])
    for producer in raw["producers"]:
        paths.update(ref["path"] for ref in producer["sources"])
    for relative in paths:
        destination = scratch / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_ROOT / relative, destination)
    if action == "promote":
        return [production.EXAMPLE]
    if action == "check-project":
        production.emit(scratch, production.EXAMPLE, "out/production-projections")
    return [production.EXAMPLE, "--output", "out/production-projections"]


def _production_build_fixture(action: str, scratch: Path) -> list[str]:
    """Drive the file-backed handler with explicitly synthetic byte products."""
    _production_fixture("project", scratch)
    raw = json.loads((scratch / production.EXAMPLE).read_bytes())
    relative = f"out/lane-{action}"
    directory = scratch / relative
    directory.mkdir(parents=True)
    raw["graph"] = {"type_count": 0, "intent_count": 0, "world_count": 0,
                    "inventory": [], "verified_parsers": [], "ring_depth_ceiling": 0}
    artifacts = {}
    for member in raw["members"]:
        descriptor = f"{relative}/{member['id']}.json"
        (scratch / descriptor).write_bytes(composer.canonical_bytes({
            "package_id": member["package_id"], "desc_manifest": 0, "desc_edges": []}))
        member["descriptor"] = production.reference(scratch, descriptor)
        if member["id"] not in {"composer", "admission"}:
            path = f"{relative}/{member['id']}.bin"
            (scratch / path).write_bytes(f"test-only lane bytes for {member['id']}".encode())
            artifacts[member["artifact_slot"]] = path
    (scratch / production.EXAMPLE).write_bytes(composer.canonical_bytes(raw))
    outputs = production.emit(scratch, production.EXAMPLE, f"{relative}/projections")
    graph_input = json.loads((directory / "projections/graph-input.json").read_bytes())["payload"]["document"]
    graph = composer.graph_bytes(composer.parse_document(graph_input))
    (directory / "graph.json").write_bytes(graph)
    (directory / "image.bin").write_bytes(b"test-only lane image")
    (directory / "artifact-paths.json").write_bytes(composer.canonical_bytes(artifacts))
    args = [production.EXAMPLE, "--projections", f"{relative}/projections",
            "--graph", f"{relative}/graph.json", "--image", f"{relative}/image.bin"]
    if action == "build-record":
        return [*args, "--artifacts", f"{relative}/artifact-paths.json", "--output", f"{relative}/record.json"]
    record = production.build_record(scratch, production.EXAMPLE,
        {name: (directory / "projections" / name).read_bytes() for name in outputs},
        {slot: production.reference(scratch, path) for slot, path in artifacts.items()},
        production.reference(scratch, f"{relative}/image.bin"), graph)
    (directory / "record.json").write_bytes(composer.canonical_bytes(record))
    return [*args, "--record", f"{relative}/record.json"]


def _admission_fixture(scratch: Path) -> list[str]:
    shutil.copytree(_ROOT / "tools" / "boot", scratch / "tools" / "boot", dirs_exist_ok=True)
    _attached_recipe(scratch)
    (scratch / "image.bin").write_bytes(b"fixture image")
    (scratch / "graph.json").write_bytes(b"fixture graph")
    return ["tools/boot/admission-request.json", "--roster", "tools/boot/fixture-roster.json",
            "--image", str(scratch / "image.bin"), "--graph", str(scratch / "graph.json"),
            "--out", str(scratch / "admission-record.json")]


def _signature_shards(scratch: Path) -> list[str]:
    """One consistent interface receipt per signature interface, for `join` to compose."""
    reports: list[str] = []
    for mode in boot_crypto_target.MODES:
        report = scratch / "signature-shards" / mode / "report.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(_shard(mode)), encoding="utf-8", newline="")
        reports.append(str(report))
    return ["--out", str(scratch / "signature-campaign"), *reports]


def _python_preparation(scratch: Path) -> list[str]:
    """A standalone owner with the reviewed formatter settings and one sorted file."""
    tools = scratch / "tools"
    tools.mkdir(exist_ok=True)
    for name in ("pyproject.toml", "ruff.toml"):
        shutil.copyfile(TOOLS / name, tools / name)
    (tools / "selected.py").write_text("import os\n", encoding="utf-8")
    return ["--check", "--path", "tools/selected.py"]


def _vector_artifacts(scratch: Path) -> list[str]:
    """Only command portability is checked here; oracle behavior has its own controls."""
    for artifact, emit in ((vector_bitcount.SAIL, vector_bitcount.emit_sail),
                           (vector_bitcount.CORPUS, vector_bitcount.emit_corpus)):
        path = scratch / artifact
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(emit(scratch), encoding="utf-8", newline="\n")
    return []


_RUNS: dict[tuple[str, str], Argv] = {
    ("prepare", "python"): _python_preparation,
    ("vector-bitcount", "emit"): _vector_artifacts,
    ("vector-bitcount", "check"): _vector_artifacts,
    ("model", "config-keys"): lambda _: [
        str(_ROOT / "model" / "config" / "verifiedos.json"),
        str(_ROOT / "model" / "config" / "verifiedos-v.json")],
    ("model", "validate-config"): _trivial_schema,
    # `cmd_asm` and `cmd_config_keys` take the paths as the caller spells them, so
    # these are absolute: a case's working directory is the runner's, not the root's.
    ("model", "asm"): lambda scratch: [
        str(_ROOT / "corpus" / "atomics.s"), str(scratch / "atomics.elf")],
    ("model", "freeze-emit"): lambda scratch: [
        "base-integer", "--out", str(scratch / "freeze")],
    ("rtl", "provenance"): lambda _: [],
    ("rtl", "filelist"): lambda _: [],
    ("oracle", "list"): lambda _: [],
    ("oracle", "emit"): lambda _: ["--spec", "capformat"],
    # `seed list` resolves its file against the root it finds for itself, so this one
    # is repository-relative by the subcommand's own contract.
    ("seed", "list"): lambda _: ["--file", "model/model/core/cap_common.sail"],
    ("testrig", "protocol"): lambda _: [],
    ("testrig", "adapt"): _rtl_frame,
    ("testrig", "bmc"): lambda _: [],
    ("placement", "export"): _placement_export,
    ("placement", "check"): lambda _: [],
    ("placement", "admit"): lambda _: [],
    ("placement", "search"): lambda _: ["--max-leaves", "1"],
    ("proofs", "headers"): lambda _: [],
    ("memory-planner", "plan"): partial(_portable_plan, "plan"),
    ("memory-planner", "check"): partial(_portable_plan, "check"),
    ("memory-planner", "solve"): partial(_portable_plan, "solve"),
    ("memory-planner", "verify"): partial(_portable_plan, "verify"),
    ("memory-planner", "demo"): lambda _: [],
    ("memory-planner", "contracts"): lambda _: [],
    ("memory-planner", "resources"): lambda _: [],
    ("memory-planner", "resource-proof"): lambda _: [],
    ("memory-certificates", "encode"): _memory_encoding,
    ("boot", "roster"): lambda _: [],
    ("composer", "compose"): _composition_fixture,
    ("composer", "fixture"): lambda _: ["--output", "out/descriptor-fixture.json"],
    ("composer", "compare"): lambda _: [],
    ("composer", "project"): partial(_production_fixture, "project"),
    ("composer", "check-project"): partial(_production_fixture, "check-project"),
    ("composer", "build-record"): partial(_production_build_fixture, "build-record"),
    ("composer", "check-build-record"): partial(_production_build_fixture, "check-build-record"),
    ("composer", "promote"): partial(_production_fixture, "promote"),
    ("admission", "record"): _admission_fixture,
    ("admission", "emit-reference"): lambda scratch: ["--out", str(scratch / "AdmissionComparison.v")],
    ("kernel", "reader"): _kernel_vectors,
    ("boot-handoff", "layout"): lambda _: [],
    # `chain-join` composes shard receipts written here, one per campaign job.
    ("boot-handoff", "chain-join"): lambda scratch: [
        "--out", str(scratch / "chain-campaign"), *_chain_reports(scratch)],
    # `verify` reads an isolated complete fixture, independent of historical staging.
    ("boot-crypto", "verify"): lambda _: [],
    ("boot-crypto", "join"): _signature_shards,
}


# Help flags are metadata rather than handwritten operational test fixtures.
_HELP_ONLY = help_declarations()
_RUNS.update({declaration: lambda _: [] for declaration in _HELP_ONLY})


# The one run whose subject is a gitlink. `rtl filelist` reads the imported core's
# manifest, which a checkout that has initialized no submodule does not hold, and the CI
# clone is that checkout by design. Its answer there is the absence named and exit 1,
# which is an answer given on this lane about the tree and not a refusal of the lane, so
# the case accepts it in that one form only: any other nonzero exit, from this run or
# any other, is still the failure it always was.
_ABSENT_GITLINK = "is not in this checkout"
_READS_A_GITLINK: frozenset[tuple[str, str]] = frozenset({("rtl", "filelist")})


def _declared() -> set[tuple[str, str]]:
    return {(command.name, sub) for command in COMMANDS for sub in command.host_ok}


def _every_declaration_has_a_run() -> None:
    # The table is the case's subject and not its fixture: a subcommand declared
    # answerable on either lane and given no run here would be a declaration this
    # module reports green about and never exercises.
    declared, covered = _declared(), set(_RUNS)
    ensure(declared == covered,
           f"every declared subcommand needs a run and every run a declaration; "
           f"declared and unrun: {sorted(declared - covered)}, "
           f"run and undeclared: {sorted(covered - declared)}")


def _declared_subcommands_answer_on_this_lane() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        scratch = Path(td).resolve()
        for (name, sub), argv in sorted(_RUNS.items()):
            out, err = io.StringIO(), io.StringIO()
            # Export is the only newly declared command that writes a fixed path.
            # Redirect its module's root provider, without changing the shared parser.
            if (name, sub) == ("placement", "export"):
                isolated = patch.object(_MODULES[name], "corpus_mod",
                                        SimpleNamespace(find_root=lambda: scratch))
            elif (name, sub) == ("boot-crypto", "verify"):
                fixture = scratch / "signature-fixture"
                _staged_root(fixture)
                isolated = patch.object(_MODULES[name], "env", SimpleNamespace(
                    load=lambda fixture=fixture, **_: SimpleNamespace(root=fixture)))
            elif name == "prepare":
                isolated = patch.object(_MODULES[name], "corpus", SimpleNamespace(find_root=lambda: scratch))
            elif name == "vector-bitcount":
                isolated = patch.object(_MODULES[name], "find_root", lambda: scratch)
            elif name in {"composer", "admission"}:
                (scratch / "proofs").mkdir(exist_ok=True)
                for relative in (composer.REFERENCE, admission.SOURCE):
                    shutil.copyfile(_ROOT / relative, scratch / relative)
                isolated = patch.object(_MODULES[name], "corpus",
                                        SimpleNamespace(find_root=lambda: scratch))
            else:
                isolated = nullcontext()
            try:
                with isolated, redirect_stdout(out), redirect_stderr(err):
                    # cast because `main` crosses a dynamic import and answers `Any`;
                    # the convention it is being held to is that it returns an exit code
                    code = cast("int", _MODULES[name].main([sub, *argv(scratch)]))
            except SystemExit as exc:
                if (name, sub) not in _HELP_ONLY or type(exc.code) is not int or exc.code != 0:
                    raise AssertionError(
                        f"`run.py {name} {sub}` is declared answerable on either lane and "
                        f"refused this one: {exc}") from exc
                code = 0
            said = out.getvalue() + err.getvalue()
            if (name, sub) in _HELP_ONLY:
                ensure(f"usage: run.py {name}" in said,
                       f"`run.py {name} {sub}` printed no command usage: {said!r}")
            ensure("runs inside WSL" not in said and "run inside WSL" not in said,
                   f"`run.py {name} {sub}` answered with the guest refusal: {said!r}")
            if code != 0 and (name, sub) in _READS_A_GITLINK and _ABSENT_GITLINK in said:
                continue
            if (name, sub) == ("composer", "promote"):
                ensure(code == 1 and "production promotion refused:" in said,
                       f"incomplete composition must reach its semantic refusal: {said!r}")
                continue
            ensure(code == 0,
                   f"`run.py {name} {sub}` exited {code}: {said[-400:]!r}")


def _run_py_hops_on_exactly_the_rest() -> None:
    for command in COMMANDS:
        for sub in sorted(command.host_ok):
            ensure(not command.guest_only([sub]),
                   f"`run.py {command.name} {sub}` is declared answerable here and "
                   f"must not be re-launched into the guest")
        ensure(command.guest_only([]) == (command.lane == "guest"),
               f"a bare `run.py {command.name}` hops exactly when its lane is the "
               f"guest's, and this one does not")
    ensure(next(c for c in COMMANDS if c.name == "model").guest_only(["build"]),
           "a guest subcommand outside the set still hops")


def _readme_names_every_declaration() -> None:
    """The reader's pointer reaches the exact generated dispatch reference."""
    text = _README.read_text(encoding="utf-8")
    relative = Path(LANE_REFERENCE).relative_to("tools").as_posix()
    ensure(f"]({relative})" in text, "tools/README.md must link the generated lane reference")
    ensure((_ROOT / LANE_REFERENCE).read_text(encoding="utf-8") == lane_reference(),
           "generated command lane reference differs from its dispatch owner")


def cases() -> list[Case]:
    return [
        Case("every-declaration-has-a-run", _every_declaration_has_a_run),
        Case("declared-subcommands-answer", _declared_subcommands_answer_on_this_lane),
        Case("hops-on-exactly-the-rest", _run_py_hops_on_exactly_the_rest),
        Case("readme-names-every-declaration", _readme_names_every_declaration),
    ]
