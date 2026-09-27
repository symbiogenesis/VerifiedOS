# SPDX-License-Identifier: Apache-2.0
"""Offline controls for selection, refusal, receipt freshness and native C."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import boot_crypto as b
from vos import boot_crypto_target as target
from vos import toolenv
from vos.cli import boot_crypto as cli


def selected_interfaces() -> None:
    def group(interface: str, prehash: str, mu: bool = False) -> dict[str, object]:
        return {"tgId": 1, "parameterSet": "ML-DSA-87", "signatureInterface": interface,
                "preHash": prehash, "externalMu": mu, "tests": [
                    {"tcId": i, "testPassed": bool(i), "pk": "00", "message": "01", "mu": "02",
                     "context": "", "signature": "03"} for i in range(2)]}
    rows, omitted = b.cases({"testGroups": [group("external", "pure"), group("internal", "none"),
                            group("internal", "none", True), group("external", "preHash")]}, "mldsa")
    ensure({c.mode for c in rows} == {"mldsa", "mldsa-internal", "mldsa-mu"}, "interface selection")
    ensure(len(rows) == 6 and len(omitted) == 2, "prehash exclusion is visible")
    ensure(next(c for c in rows if c.mode.endswith("-mu")).message == b"\x02", "mu uses its own input")
    try:
        b.cases({"testGroups": []}, "mldsa")
    except ValueError:
        return
    raise AssertionError("empty campaign was accepted")


def controls_preserve_positive() -> None:
    original = b.Case("authored", "mldsa", bytes(2592), b"message", b"", bytes(4627), True)
    cases = b.refusals(original)
    ensure(original.expected and original.signature == bytes(4627), "positive mutated")
    ensure(all(not case.expected for case in cases), "refusal expected value")
    names = {c.name.removeprefix("authored-") for c in cases}
    ensure({"wrong-root", "signature-flipped", "positive-z-bound", "negative-z-bound",
            "hint-end-overflow", "message-overlong", "context-overlong"} <= names, "missing refusal family")
    for label, expected in (("positive-z-bound", 524168), ("negative-z-bound", -524168)):
        data = next(c.signature for c in cases if c.name.endswith(label))
        value = int.from_bytes(data[64:67], "little") & ((1 << 20)-1)
        ensure(524288-value == expected, "incorrect strict boundary control")


def drift_refuses() -> None:
    with patch.object(b, "input_snapshot", return_value={"source": "changed"}):
        try:
            b.require_unchanged(TOOLS.parent, {"source": "before"})
        except ValueError:
            return
    raise AssertionError("changed source kept valid evidence")


def operational_failure_is_not_refusal() -> None:
    case = b.Case("control", "slh", bytes(64), b"message", b"", bytes(29792), False)
    with tempfile.TemporaryDirectory() as name:
        work = Path(name)
        with patch.object(b, "run", return_value="garbage"):
            try:
                b.invoke(work / "unused", work, case)
            except ValueError:
                pass
            else:
                raise AssertionError("malformed driver verdict became signature refusal")
        with patch.object(b.subprocess, "run", return_value=subprocess.CompletedProcess([], 2, "", "error")):
            try:
                b.openssl_verify(work, case)
            except ValueError:
                return
    raise AssertionError("OpenSSL operational failure became signature refusal")


def failed_rerun_replaces_pass() -> None:
    with tempfile.TemporaryDirectory() as name:
        work = Path(name)
        report = work / "report.json"
        report.write_text('{"passed": true}', encoding="utf-8")
        args = argparse.Namespace(out=str(work), gallina=False, first=False)
        with (patch.object(cli.env, "load", return_value=SimpleNamespace(root=TOOLS.parent, lane_root=work)),
              patch.object(cli.env, "hold_lock", return_value=nullcontext()),
              patch.object(b, "campaign", side_effect=ValueError("failed control"))):
            ensure(cli.cmd_run(args) == 1, "failed campaign returned success")
        after = json.loads(report.read_text(encoding="utf-8"))
        ensure(after["passed"] is False and after["status"] == "failed", "stale pass survived failure")


def native_controls() -> None:
    work = toolenv.environment(TOOLS.parent, sys.platform).parent / "boot-crypto-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-", dir=work) as name:
        output = Path(name)
        binary = b.build(TOOLS.parent, output)
        ensure(b.run([str(binary), "bounds"], output) == "0", "invalid length reached input read")
        for mode, p, s in (("slh", 64, 29792), ("mldsa", 2592, 4627)):
            case = b.Case("all-zero-refusal", mode, bytes(p), b"message", b"", bytes(s), False)
            ensure(not b.invoke(binary, output, case), "all-zero signature accepted")
        for case in b.offline_fixtures(TOOLS.parent):
            ensure(b.invoke(binary, output, case), f"{case.mode} positive refused")
            ensure(not b.invoke(binary, output, b.refusals(case)[0]), f"{case.mode} corrupt neighbor accepted")
        ensure(all(row["passed"] for row in b.shake_cases(binary, output, None)),
               "streaming SHAKE rate boundaries disagree")


def target_requires_a_real_verdict() -> None:
    ensure(not target.target_verdict("", None, False)[0], "timeout became refusal")
    ensure(not target.target_verdict("", 0, True)[0], "missing HTIF verdict became acceptance")
    ensure(not target.target_verdict("FAILURE: 256 (0x00000100)\n", 1, False)[0],
           "trap became signature refusal")
    refused = "FAILURE: 1 (0x00000001)\n"
    ensure(target.target_verdict(refused, 1, False)[0], "real refusal rejected")
    ensure(target.target_verdict("SUCCESS\n", 0, True)[0], "real acceptance rejected")
    for spoiled in ("SUCCESS\n" + refused, refused * 2, "diagnostic " + refused,
                    "FAILURE: 1 (0x00000002)\n"):
        ensure(not target.target_verdict(spoiled, 1, False)[0], "ambiguous HTIF line accepted")
    ensure(not target.target_verdict(refused, 0, False)[0], "process mismatch accepted")


def target_bounds_bind_lengths() -> None:
    case = b.Case("test", "mldsa", bytes(2592), b"", b"ctx", bytes(4627), True)
    source = target.compose("main:\n        ret\n", case)
    ensure("li x11, 2592" in source and "li x13, 0" in source and
           "li x15, 3" in source and "li x17, 4627" in source, "target ABI lost exact lengths")
    ensure(".balign 4096\nvos_crypto_pk:" in source and
           ".balign 8192\nvos_crypto_signature:" in source, "unrepresentable input bounds")
    ensure(source.count("candperm c") >= 4, "input capabilities lack read-only narrowing")
    ensure("li      t1, 32768" in source and ".space  32768" in source
           and ".balign 32768\n__vos_stack:" in source, "stack allocation/bounds disagree")


def compiler_source_drift_refuses() -> None:
    with tempfile.TemporaryDirectory() as name:
        work = Path(name)
        compiler, source = work / "ccomp", work / "source.v"
        compiler.write_bytes(b"compiler fixture")
        source.write_bytes(b"source fixture")
        result = {"passed": True, "inputs_unchanged": True, "revision": "fixture-revision",
                  "compiler_sha256": b.receipts.digest(compiler)}
        (work / "build-result.json").write_text(json.dumps(result), encoding="utf-8")
        (work / "build-inputs.json").write_text(json.dumps({"source.v": {
            "canonical_sha256": b.receipts.digest(source)}}), encoding="utf-8")
        ensure(target.compiler_provenance(compiler)[0]["source_count"] == 1, "compiler receipt refused")
        alias = work / "path-alias"
        alias.mkdir()
        ensure(target.compiler_provenance(alias / ".." / "ccomp") == target.compiler_provenance(compiler),
               "compiler directory alias changed source containment")
        source.write_bytes(b"changed source")
        try:
            target.compiler_provenance(compiler)
        except ValueError:
            return
        raise AssertionError("changed retained compiler source accepted")


# One accepted function of a real stream: a single frame and only dialect mnemonics.
_STREAM = ("# source-profile: verifiedos-scalar-source-v1; no pointer round-trip integer types\n\n"
           ".text\n.globl rotl\nrotl:\n\tcmove c30, c2\n\tcincoffsetimm c2, c2, -16\n"
           "\tsc c30, 0(c2)\n\tsc c1, 8(c2)\n\tmv\tx15, x10\n\tsll\tx15, x15, x11\n"
           "\tmv\tx10, x15\n\tlc c1, 8(c2)\n\tlc c2, 0(c2)\n\tcjalr cnull, cra, 0\n")
_SOURCES = {target.SOURCE: b"int main(void) { return 0; }\n",
            "firmware/include/vos_fixture.h": b"#define VOS_FIXTURE 1\n"}


def _staged_root(root: Path) -> None:
    """A checkout holding one source, one header and a consistent staged directory."""
    for name, data in _SOURCES.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
    directory = root / target.STAGED
    directory.mkdir(parents=True)
    raw = _STREAM.encode("utf-8")
    modes: dict[str, object] = {}
    for mode in target.MODES:
        (directory / f"{mode}.s").write_bytes(target.HEADER.encode("utf-8") + raw)
        modes[mode] = {"file": f"{mode}.s", "assembly_sha256": b.sha(raw), "argv": ["ccomp"],
                       "sum_of_function_frames": 16, "lines": len(_STREAM.splitlines())}
    (root / target.MANIFEST).write_text(json.dumps({
        "schema": 1, "source": target.SOURCE, "stack_bytes": target.STACK_BYTES,
        "compiler_provenance": {"revision": "fixture"}, "compiler_inputs_sha256": {},
        "sources_sha256": {name: b.sha(data) for name, data in _SOURCES.items()},
        "search_directories": {"firmware/crypto": ["signature_target.c"],
                               "firmware/include": ["vos_fixture.h"]},
        "modes": modes}), encoding="utf-8")


def _restream(root: Path, mode: str, stream: str, frames: int) -> None:
    """Replace one staged stream and its manifest entry consistently, so that only the
    stream-content checks can refuse it."""
    raw = stream.encode("utf-8")
    (root / target.STAGED / f"{mode}.s").write_bytes(target.HEADER.encode("utf-8") + raw)
    _edit_json(root / target.MANIFEST, lambda data: data["modes"][mode].update(
        assembly_sha256=b.sha(raw), sum_of_function_frames=frames))


def _edit_json(path: Path, change: Callable[[dict[str, Any]], None]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def staged_streams_bind_manifest_and_sources() -> None:
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        _staged_root(root)
        manifest, streams = target.staged(root)
        ensure(set(streams) == set(target.MODES) and streams["slh"] == _STREAM
               and manifest["modes"]["slh"]["sum_of_function_frames"] == 16,
               "consistent staged streams refused")
    staged = Path(target.STAGED)

    def outside(root: Path) -> None:
        # A real file with its true digest, so only containment can refuse it.
        escaped = root.parent / f"{root.name}-outside.c"
        escaped.write_bytes(b"int outside;\n")
        _edit_json(root / target.MANIFEST, lambda data: data["sources_sha256"].update(
            {f"../{escaped.name}": b.sha(escaped.read_bytes())}))

    def inside(root: Path) -> None:
        data = (root / staged / "slh.s").read_bytes()
        _edit_json(root / target.MANIFEST, lambda manifest: manifest["sources_sha256"].update(
            {f"{target.STAGED}/slh.s": b.sha(data)}))

    unbound = _SOURCES["firmware/include/vos_fixture.h"]
    controls: list[tuple[str, Callable[[Path], object], str]] = [
        ("stale source", lambda root: (root / target.SOURCE).write_bytes(b"int changed;\n"),
         f"{target.SOURCE} changed since staging"),
        ("removed header", lambda root: (root / "firmware/include/vos_fixture.h").unlink(),
         "vos_fixture.h changed since staging"),
        ("a header shadowing one beside the source",
         lambda root: (root / "firmware/crypto/vos_fixture.h").write_bytes(b"#error shadow\n"),
         "the files in firmware/crypto changed"),
        ("a system header shadowed in an include directory",
         lambda root: (root / "firmware/include/stdint.h").write_bytes(b"#error shadow\n"),
         "the files in firmware/include changed"),
        ("no recorded search directories", lambda root: _edit_json(root / target.MANIFEST,
            lambda data: data.pop("search_directories")), "every include search directory"),
        ("a bound source's directory left unsearched", lambda root: _edit_json(root / target.MANIFEST,
            lambda data: data["search_directories"].pop("firmware/include")),
         "every include search directory"),
        ("no bound sources", lambda root: _edit_json(root / target.MANIFEST,
            lambda data: data.update(sources_sha256={})), "binds no source"),
        ("the source itself unbound", lambda root: _edit_json(root / target.MANIFEST,
            lambda data: data.update(sources_sha256={"firmware/include/vos_fixture.h": b.sha(unbound)})),
         "binds no source"),
        ("escaping source", outside, "invalid staged source"),
        ("source inside the staged tree", inside, "invalid staged source"),
        ("changed stream", lambda root: (root / staged / "slh.s").write_bytes(
            (root / staged / "slh.s").read_bytes().replace(b"x11", b"x12")), "differs from its manifest"),
        ("damaged header", lambda root: (root / staged / "mldsa.s").write_bytes(
            (root / staged / "mldsa.s").read_bytes()[1:]), "lacks its generated header"),
        ("unowned staged file", lambda root: (root / staged / "extra.s").write_bytes(b""), "must hold exactly"),
        ("missing interface", lambda root: (root / staged / "mldsa-mu.s").unlink(), "must hold exactly"),
        ("misstated frame sum", lambda root: _edit_json(root / target.MANIFEST, lambda data:
            data["modes"]["slh"].update(sum_of_function_frames=32)), "frame sum differs"),
        ("an instruction outside the dialect", lambda root: _restream(
            root, "slh", _STREAM.replace("\tsll\tx15, x15, x11\n", "\tfadd.d f0, f1, f2\n"), 16),
         "outside the accepted dialect"),
        ("a frame beyond the stack", lambda root: _restream(root, "mldsa", _STREAM.replace(
            "\tcincoffsetimm c2, c2, -16\n", "\tli x5, -40000\n\tcincoffset c2, c2, x5\n"), 40000),
         "exceeds stack"),
        ("an entry without compile arguments", lambda root: _edit_json(root / target.MANIFEST,
            lambda data: data["modes"]["slh-internal"].pop("argv")), "records no compile arguments"),
        ("another campaign's stack", lambda root: _edit_json(root / target.MANIFEST, lambda data:
            data.update(stack_bytes=16384)), "does not describe this campaign"),
    ]
    for label, change, reason in controls:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            _staged_root(root)
            change(root)
            try:
                target.staged(root)
            except ValueError as error:
                ensure(reason in str(error), f"{label} refused for another reason: {error}")
                continue
            finally:
                (root.parent / f"{root.name}-outside.c").unlink(missing_ok=True)
            raise AssertionError(f"{label} accepted as a staged stream")


def _stage_fixture(root: Path, shift: str | None = None) -> Callable[..., object]:
    """compile_mode's stand-in: it writes the stream and a unit whose markers name the
    source and the header, and with `shift` edits the source before that interface."""
    def compile_mode(root_: Path, out: Path, ccomp: Path, arguments: list[str],
                     mode: str) -> tuple[object, str, int]:
        if mode == shift:
            (root / target.SOURCE).write_bytes(b"int shifted;\n")
        compiled = out / mode / "compiled"
        compiled.mkdir(parents=True, exist_ok=True)
        (compiled / "signature_target.s").write_bytes(_STREAM.encode("utf-8"))
        unit_path = compiled / "signature_target.i"
        unit_path.write_text(f'# 1 "signature_target.c"\n'
                             f'# 1 "{(root / "firmware/include/vos_fixture.h").as_posix()}" 1\n',
                             encoding="utf-8")
        unit = SimpleNamespace(stream_sha256=b.sha(_STREAM.encode("utf-8")),
            argv=("/native/ccomp", "-I" + str(root / "firmware/include"), "-S", "signature_target.i"),
            preprocessed=SimpleNamespace(sha256="unit", path=unit_path, cwd=str(root / "firmware/crypto")))
        return unit, _STREAM, 16
    return compile_mode


def staging_writes_what_staged_accepts() -> None:
    provenance = ({"revision": "fixture"}, {"/native/build-result.json": "r", "/native/build-inputs.json": "i"})
    with tempfile.TemporaryDirectory() as name:
        root = Path(name).resolve()
        for source, data in _SOURCES.items():
            (root / source).parent.mkdir(parents=True, exist_ok=True)
            (root / source).write_bytes(data)
        out = root.parent / f"{root.name}-out"

        def staging(check: bool, shift: str | None = None,
                    inputs: dict[str, str] | None = None) -> dict[str, Any]:
            with (patch.object(target, "compile_mode", _stage_fixture(root, shift)),
                  patch.object(target, "compiler_provenance", return_value=provenance),
                  patch.object(target.boot_target, "compiler_inputs",
                               return_value=inputs or {"/native/compcert.ini": "c"})):
                return target.stage(root, out, Path("ccomp"), ["-conf", "/native/compcert.ini"], check)
        try:
            written = staging(check=False)
            manifest, _ = target.staged(root)
            ensure(written["passed"] and manifest == written["manifest"], "staging wrote an unaccepted manifest")
            ensure(manifest["search_directories"] == {"firmware/crypto": ["signature_target.c"],
                                                      "firmware/include": ["vos_fixture.h"]}
                   and manifest["compiler_inputs_sha256"] == {"compcert.ini": "c"}
                   and manifest["modes"]["slh"]["argv"] == ["ccomp", "-Ifirmware/include", "-S",
                                                            "signature_target.i"],
                   "staged manifest kept machine paths or missed a search directory")
            ensure(staging(check=True)["differences"] == [], "an unchanged staging differs from itself")
            (root / target.STAGED / "slh.s").write_bytes(b"# edited\n")
            ensure(staging(check=True)["differences"] == ["slh.s"], "--check missed an edited stream")
            (root / target.STAGED / "extra.s").write_bytes(b"")
            try:
                staging(check=False)
            except ValueError as error:
                ensure("does not own" in str(error), f"unowned file refused for another reason: {error}")
            else:
                raise AssertionError("staging wrote beside a file it does not own")
            (root / target.STAGED / "extra.s").unlink()
            refusals: list[tuple[str, Callable[[], object], str]] = [
                ("a source edited between interfaces", lambda: staging(check=False, shift="mldsa"),
                 "changed between interfaces"),
                ("two compiler inputs with one name",
                 lambda: staging(check=False, inputs={"/a/x.ini": "1", "/b/x.ini": "2"}), "distinct file names")]
            for label, attempt, reason in refusals:
                try:
                    attempt()
                except ValueError as error:
                    ensure(reason in str(error), f"{label} refused for another reason: {error}")
                    (root / target.SOURCE).write_bytes(_SOURCES[target.SOURCE])
                    continue
                raise AssertionError(f"staging accepted {label}")
        finally:
            shutil.rmtree(out, ignore_errors=True)


def staging_reads_marked_sources() -> None:
    with tempfile.TemporaryDirectory() as name:
        root = Path(name).resolve()
        _staged_root(root)
        (root / "firmware/crypto/keccak.c").write_bytes(b"static int keccak;\n")
        unit_path = root / "unit.i"
        unit_path.write_text(
            '# 1 "signature_target.c"\n# 1 "<built-in>" 1\n# 1 "<command line>" 1\n'
            '# 1 "./keccak.c" 1\n'
            f'# 1 "{(root / "firmware/include/vos_fixture.h").as_posix()}" 1\n'
            f'# 1 "{(root.parent / "outside-compiler/include/stddef.h").as_posix()}" 1\n',
            encoding="utf-8")
        unit = SimpleNamespace(preprocessed=SimpleNamespace(path=unit_path, cwd=str(root / "firmware/crypto")))
        found = target.read_sources(root, cast("Any", unit))
        ensure(set(found) == {target.SOURCE, "firmware/crypto/keccak.c", "firmware/include/vos_fixture.h"},
               f"marked checkout sources misread: {sorted(found)}")
        unit_path.write_text('# 1 "./keccak.c" 1\n', encoding="utf-8")
        try:
            target.read_sources(root, cast("Any", unit))
        except ValueError:
            pass
        else:
            raise AssertionError("a unit that never names its source was accepted")
        argv = ("/native/ccomp", "-conf", "/native/lane/compcert.ini", "-fverifiedos-typed",
                "-I" + str(root / "firmware/include"), "-DVOS_TARGET_SCHEME=1", "-S", "unit.i")
        ensure(target.portable(argv, root) == ["ccomp", "-conf", "compcert.ini", "-fverifiedos-typed",
                                               "-Ifirmware/include", "-DVOS_TARGET_SCHEME=1", "-S", "unit.i"],
               "staged compile argv kept machine paths")


def interfaces_select_their_population() -> None:
    population = [b.Case(f"{mode}-{kind}", mode, b"", b"", b"", b"", kind == "positive")
                  for mode in target.MODES for kind in ("positive", "refusal")]
    chosen = target.select(population, ("mldsa-mu", "slh"), first=False)
    ensure([case.name for case in chosen] == ["slh-positive", "slh-refusal", "mldsa-mu-positive",
                                              "mldsa-mu-refusal"], "interface selection or order")
    ensure([case.name for case in target.select(population, ("slh",), first=True)] == ["slh-positive"],
           "positive-only selection")
    for modes, arguments in (((), []), (("slh", "slh"), []), (("rsa",), []), (("slh",), ["-conf", "x"])):
        try:
            target.run(TOOLS.parent, Path("unused"), None, arguments, Path("sim"), Path("receipt"),
                       1, 1, modes=modes)
        except ValueError:
            continue
        raise AssertionError(f"target accepted modes {modes} with arguments {arguments}")


def _shard(mode: str, **changes: object) -> dict[str, Any]:
    names = [f"{mode}-positive", f"{mode}-refusal"]
    report: dict[str, Any] = {
        "status": "passed", "passed": True, "first_positive_only": False, "modes": [mode],
        "selection": {mode: names}, "unexecuted_cases": [], "compiled": {mode: {"assembly_sha256": mode}},
        "cases": [{"case": case, "mode": mode, "expected": case == names[0], "passed": True}
                  for case in names],
        "seconds": 1.0, "jobs": 4, "inputs_sha256": {"simulator": mode},
        **{key: f"shared {key}" for key in target.SHARED}}
    report.update(changes)
    return report


def joined_campaigns_are_complete_and_consistent() -> None:
    shards = {mode: _shard(mode) for mode in reversed(target.MODES)}
    joined = target.join(shards)
    ensure(joined["passed"] and joined["complete_selected_population"] and not joined["unexecuted_cases"],
           "consistent shards refused")
    ensure([row["case"] for row in joined["cases"]] ==
           [f"{mode}-{kind}" for mode in target.MODES for kind in ("positive", "refusal")],
           "joined cases leave population order")
    failed = _shard("slh", status="failed", passed=False)
    failed["cases"][1]["passed"] = False
    ensure(not target.join({**shards, "slh": failed})["passed"], "a failed case joined as success")
    skipped = _shard("mldsa", status="failed", passed=False, unexecuted_cases=["mldsa-refusal"])
    skipped["cases"] = skipped["cases"][:1]
    joined = target.join({**shards, "mldsa": skipped})
    ensure(not joined["passed"] and joined["unexecuted_cases"] == ["mldsa-refusal"],
           "an unexecuted refusal disappeared from the joined campaign")
    duplicate = _shard("slh")
    duplicate["cases"].append(dict(duplicate["cases"][0]))
    outside = _shard("slh")
    outside["cases"][1] = {**outside["cases"][1], "case": "slh-invented"}
    wrong_mode = _shard("slh")
    wrong_mode["cases"][1] = {**wrong_mode["cases"][1], "mode": "mldsa"}
    misstated = _shard("slh")
    misstated["cases"][1] = {**misstated["cases"][1], "passed": False}
    controls: list[tuple[str, dict[str, Any], str]] = [
        ("a missing interface", {mode: shards[mode] for mode in target.MODES[1:]}, "no shard ran slh"),
        ("a repeated interface", {**shards, "again": _shard("slh")}, "repeats or invents"),
        ("different sources", {**shards, "slh": _shard("slh", source_sha256={"changed": "x"})},
         "differs from the other shards in source_sha256"),
        ("a different staged manifest", {**shards, "slh": _shard("slh", staged_manifest_sha256="other")},
         "in staged_manifest_sha256"),
        ("a positives-only shard", {**shards, "slh": _shard("slh", first_positive_only=True)},
         "selected positives only"),
        ("an incomplete shard", {**shards, "slh": _shard("slh", status="incomplete")},
         "not a completed target report"),
        ("a shard that stopped", {**shards, "slh": {"passed": False, "status": "failed", "error": "no model"}},
         "stopped before its cases completed: no model"),
        ("a duplicated case", {**shards, "slh": duplicate}, "executed a case twice"),
        ("a case outside the selection", {**shards, "slh": outside}, "outside its selection"),
        ("a case under another interface", {**shards, "slh": wrong_mode}, "outside its selection"),
        ("a success its cases contradict", {**shards, "slh": misstated}, "verdict its cases do not support"),
        ("a misstated unexecuted list", {**shards, "slh": _shard("slh", unexecuted_cases=["slh-refusal"])},
         "misstates its unexecuted cases"),
        ("an empty selection", {**shards, "slh": _shard("slh", selection={"slh": []}, cases=[])},
         "selected nothing for slh"),
    ]
    for label, reports, reason in controls:
        try:
            target.join(reports)
        except ValueError as error:
            ensure(reason in str(error), f"{label} refused for another reason: {error}")
            continue
        raise AssertionError(f"{label} joined into a complete campaign")


def target_takes_one_stream_source() -> None:
    required = ["target", "--simulator", "sim", "--build-receipt", "receipt"]
    def parsed(args: argparse.Namespace) -> int:
        raise AssertionError(f"target parsed stream sources {args.ccomp!r} and {args.staged!r}")
    for extra in ([], ["--staged", "--ccomp", "ccomp"]):
        with patch.dict(cli.TABLE, {"target": (parsed, "fixture")}):
            try:
                cli.main([*required, *extra])
            except SystemExit:
                continue
        raise AssertionError(f"target accepted stream sources {extra}")
    # An empty --ccomp names a compiler that does not exist; it never selects the streams.
    chosen: list[object] = []
    with tempfile.TemporaryDirectory() as name:
        work = Path(name)
        with (patch.object(cli.env, "load", return_value=SimpleNamespace(root=TOOLS.parent, lane_root=work)),
              patch.object(cli.env, "hold_lock", return_value=nullcontext()),
              patch.object(cli.boot_crypto_target, "run",
                           side_effect=lambda *arguments: chosen.append(arguments[2]) or {"passed": False})):
            cli.main([*required, "--ccomp", "", "--out", str(work)])
    ensure(chosen == [Path()], f"an empty --ccomp selected {chosen!r}")


def cases() -> list[Case]:
    return [Case("pure internal and mu selection", selected_interfaces),
            Case("corruption and strict boundary controls", controls_preserve_positive),
            Case("source drift invalidates evidence", drift_refuses),
            Case("operational failures are not refusals", operational_failure_is_not_refusal),
            Case("failed rerun replaces previous success", failed_rerun_replaces_pass),
            Case("target timeout and trap never mean refusal", target_requires_a_real_verdict),
            Case("target byte extents and scalar lengths", target_bounds_bind_lengths),
            Case("target compiler source drift", compiler_source_drift_refuses),
            Case("staged streams bind their manifest and sources", staged_streams_bind_manifest_and_sources),
            Case("staging reads the preprocessor's checkout sources", staging_reads_marked_sources),
            Case("staging writes what the staged check accepts", staging_writes_what_staged_accepts),
            Case("interfaces select their own population", interfaces_select_their_population),
            Case("joined shards form one consistent campaign", joined_campaigns_are_complete_and_consistent),
            Case("target takes exactly one stream source", target_takes_one_stream_source),
            Case("sanitized native bounds and refusals", native_controls, lane="guest")]
