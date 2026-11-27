# SPDX-License-Identifier: Apache-2.0
"""Verify recursive kernel and native assumption closure over the canonical hart-0 term."""

import argparse
import hashlib
import importlib
import re
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vos import proofaudit, python_dependencies

_common = importlib.import_module("sail-tag-outcomes._common")

DEFAULT_WHOLE_TERM_DIR = (
    "/root/build/fanout-retained/4b3b843a3b9fe80d0323"
    "/holdfast-20261124-canonical/lane/whole-term-diagnostic"
)
DEFAULT_CANONICAL_SUPPORT = (
    "/root/build/fanout-retained/4b3b843a3b9fe80d0323"
    "/holdfast-20261124-canonical/lane/replay-inputs/canonical-support"
)
DEFAULT_STDPP = (
    "/root/build/fanout-retained/4b3b843a3b9fe80d0323"
    "/holdfast-20261124-canonical/lane/replay-inputs/private/lib/coq/user-contrib/stdpp"
)
DEFAULT_ROCQ_PREFIX = "/root/.opam/verifiedos-rocq-9.3.0-ocaml-5.4.1"

TAG_INTERPRETER_SHA256 = "6a4d74e55548aeb86647031f24297365233541f2c20991a80f744f636fc24d40"
TAG_CONSERVATIVITY_SHA256 = "ce05b0dceac920e0fb46e569b93300905f3461d84242a14c6964118950753a63"
CANONICAL_BRIDGE_SHA256 = "420b764eef05c2d2cf392975b67afcd7242b82f241bc1100e3b74edad6f51112"
CANONICAL_TAG_CONSERVATIVITY_SHA256 = (
    "62e5d9b57293ddb44b2c7586fd5aba0c8e9c82f35ae724e8079a5cace0c10015"
)

CANONICAL_BRIDGE_REL = (
    "docs/implementation/retained-evidence/"
    "q35p-canonical-callers-20261125/CanonicalPhysicalCallerBridge.v.txt"
)
CANONICAL_CALLERS_MANIFEST_REL = (
    "docs/implementation/retained-evidence/q35p-canonical-callers-20261125/manifest.json"
)
CANONICAL_DIAGNOSTIC_MANIFEST_REL = (
    "docs/implementation/retained-evidence/q35-holdfast-canonical-20261124/manifest.json"
)

WHOLE_TERM_MODULES = ("riscv_extras", "rv64d_types", "rv64d")
AUTHORED_CANONICAL_MODULES = (
    "TagInterpreter",
    "TagConservativity",
    "CanonicalPhysicalCallerBridge",
    "CanonicalTagConservativity",
)
KERNEL_CHECK_MODULES = ("CanonicalPhysicalCallerBridge", "CanonicalTagConservativity")
CANONICAL_TAG_PLANE_INST = "CanonicalTagPlaneInst"
CANONICAL_OLD_OUTCOMES_INST = "CanonicalOldOutcomesInst"

# Classified floating-point axioms declared by the canonical hart-0 emission:
# [canonical-machine-term.md](../../docs/assurance/canonical-machine-term.md#the-31-the-emission-declares).
EXPECTED_CANONICAL_FP_AXIOMS: tuple[str, ...] = (
    "rv64d.riscv_f32Add",
    "rv64d.riscv_f32Div",
    "rv64d.riscv_f32Mul",
    "rv64d.riscv_f32MulAdd",
    "rv64d.riscv_f32Sqrt",
    "rv64d.riscv_f32Sub",
    "rv64d.riscv_f32ToBF16",
    "rv64d.riscv_f32ToF64",
    "rv64d.riscv_f32ToI32",
    "rv64d.riscv_f32ToI64",
    "rv64d.riscv_f32ToUi32",
    "rv64d.riscv_f32ToUi64",
    "rv64d.riscv_f64Add",
    "rv64d.riscv_f64Div",
    "rv64d.riscv_f64Mul",
    "rv64d.riscv_f64MulAdd",
    "rv64d.riscv_f64Sqrt",
    "rv64d.riscv_f64Sub",
    "rv64d.riscv_f64ToF32",
    "rv64d.riscv_f64ToI32",
    "rv64d.riscv_f64ToI64",
    "rv64d.riscv_f64ToUi32",
    "rv64d.riscv_f64ToUi64",
    "rv64d.riscv_i32ToF32",
    "rv64d.riscv_i32ToF64",
    "rv64d.riscv_i64ToF32",
    "rv64d.riscv_i64ToF64",
    "rv64d.riscv_ui32ToF32",
    "rv64d.riscv_ui32ToF64",
    "rv64d.riscv_ui64ToF32",
    "rv64d.riscv_ui64ToF64",
)

STRICT_COMPILE_TIMEOUT_SECONDS = 180
KERNEL_CHECK_TIMEOUT_SECONDS = 600


sha = _common.sha
tree_sha = _common.tree_sha
absolute = _common.absolute
require_sha = _common.require_sha
_load_json = _common.load_json
retained_stdpp = _common.retained_stdpp
compare_installed_inventories = _common.compare_installed_inventories
verify_installed_unchanged = _common.verify_installed_unchanged
parse_kernel_summary = _common.parse_kernel_summary
_check_no_dir_symlinks = _common.check_no_dir_symlinks
_write_json = _common.write_json


def output_path(value: str, protected: tuple[Path, ...]) -> Path:
    """Require an expanded absolute empty/new output directory not overlapping protected inputs."""
    return cast("Path", _common.output_path(value, protected, allow_empty_existing=True))


def verify_whole_term_inputs(
    whole_term_dir: Path,
    compile_result_path: Path,
) -> dict[str, dict[str, str]]:
    """Verify `riscv_extras`, `rv64d_types`, and `rv64d` sources and `.vo` objects."""
    compile_doc = _load_json(compile_result_path)
    results = cast("list[dict[str, object]]", compile_doc["results"])
    by_name = {cast("str", entry["name"]): entry for entry in results}
    verified: dict[str, dict[str, str]] = {}
    for mod in WHOLE_TERM_MODULES:
        key = f"{mod}.v"
        if key not in by_name:
            raise ValueError(f"compile-result missing whole-term entry for {key}")
        record = by_name[key]
        src = whole_term_dir / f"{mod}.v"
        obj = whole_term_dir / f"{mod}.vo"
        expected_src = cast("str", record["source_sha256"])
        expected_obj = cast("str", record["object_sha256"])
        require_sha(src, expected_src)
        require_sha(obj, expected_obj)
        verified[mod] = {
            "source_sha256": expected_src,
            "object_sha256": expected_obj,
        }
    return verified


def verify_canonical_support_inputs(
    support_dir: Path,
    closure_reading_path: Path,
    expected_modules: list[str],
) -> dict[str, dict[str, str]]:
    """Verify all 29 `SailStdpp` `.v` and `.vo` files against the canonical closure reading."""
    closure_doc = _load_json(closure_reading_path)
    recorded = cast("dict[str, dict[str, object]]", closure_doc["candidate_support_modules"])
    if sorted(recorded) != sorted(expected_modules):
        raise ValueError(
            "canonical support module list does not match qualification support_modules",
        )
    verified: dict[str, dict[str, str]] = {}
    for mod in expected_modules:
        record = recorded[mod]
        expected_src = cast("str", record["source_sha256"])
        expected_obj = cast("str", record["object_sha256"])
        require_sha(support_dir / f"{mod}.v", expected_src)
        require_sha(support_dir / f"{mod}.vo", expected_obj)
        verified[mod] = {
            "source_sha256": expected_src,
            "object_sha256": expected_obj,
        }
    return verified


def canonical_assumption_spec(module: str) -> tuple[str, str]:
    """Return `(search_target, preamble)` for a canonical-closure authored module."""
    if module == "TagInterpreter":
        return (
            CANONICAL_TAG_PLANE_INST,
            f"Require rv64d_types TagInterpreter.\n"
            f"Module {CANONICAL_TAG_PLANE_INST} := TagInterpreter.TagPlane "
            f"rv64d_types.Arch rv64d_types.Interface.\n",
        )
    if module == "TagConservativity":
        return (
            CANONICAL_OLD_OUTCOMES_INST,
            f"Require rv64d_types TagConservativity.\n"
            f"Module {CANONICAL_OLD_OUTCOMES_INST} := TagConservativity.OldOutcomes "
            f"rv64d_types.Arch rv64d_types.Interface.\n",
        )
    if module in ("CanonicalPhysicalCallerBridge", "CanonicalTagConservativity"):
        return module, f"Require {module}.\n"
    raise ValueError(f"unsupported canonical closure module: {module}")


def canonical_inventory_query(module: str) -> tuple[str, str]:
    """Build a `proofaudit.inventory_query` script for `module`, instantiating `TagPlane`."""
    return cast("tuple[str, str]", _common.inventory_query_from_spec(module, canonical_assumption_spec))


def canonical_assumption_query(module: str, symbols: list[proofaudit.Symbol]) -> str:
    """Build a `proofaudit.assumption_query` script for `symbols` under `module`."""
    return cast(
        "str",
        _common.assumption_query_from_spec(module, symbols, canonical_assumption_spec),
    )


def audit_canonical_module_assumptions(
    module: str,
    query: Callable[[str, str], str],
) -> dict[str, object]:
    """Enumerate all declarations of `module` and require `Closed under the global context`."""
    return cast(
        "dict[str, object]",
        _common.audit_module_assumptions(
            module, query, canonical_assumption_spec, kind_label="canonical",
        ),
    )


def audit_canonical_assumptions(
    modules: tuple[str, ...],
    query: Callable[[str, str], str],
) -> dict[str, object]:
    """Audit native `Print Assumptions` across every enumerated declaration of `modules`."""
    return cast(
        "dict[str, object]",
        _common.audit_assumptions(
            modules, query, canonical_assumption_spec,
            schema="verifiedos-canonical-tag-assumptions/1",
            kind_label="canonical",
        ),
    )


def verify_canonical_kernel_check(
    argv: list[str],
    returncode: int,
    stdout: str,
    stderr: str,
    *,
    target_module: str = "CanonicalPhysicalCallerBridge",
    portable_flags: list[str],
    expected_axioms: tuple[str, ...] = EXPECTED_CANONICAL_FP_AXIOMS,
    elapsed_seconds: float | None = None,
) -> dict[str, object]:
    """Validate full recursive `rocqchk -silent -o` on `CanonicalPhysicalCallerBridge`."""
    axioms, expected, indices = _common.validate_kernel_run(
        "canonical recursive kernel check",
        argv,
        returncode,
        stdout,
        stderr,
        expected_axioms,
        portable_flags=portable_flags,
        required_token=target_module,
    )
    report: dict[str, object] = {
        "schema": "verifiedos-canonical-tag-kernel-check/1",
        "recursive": True,
        "norec_absent": True,
        "norec_present": False,
        "target_module": target_module,
        "argv": list(argv),
        "portable_flags": list(portable_flags),
        "exit_code": returncode,
        "expected_axioms": expected,
        "axioms": axioms,
        "axiom_count": len(axioms),
        "unexpected_axioms": [],
        "missing_expected_axioms": [],
        "indices_not_mattering": indices,
    }
    if elapsed_seconds is not None:
        report["elapsed_seconds"] = elapsed_seconds
    return report


def build_canonical_kernel_report(
    targets: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Assemble the multi-target recursive `rocqchk -silent -o` kernel report."""
    if list(targets) != list(KERNEL_CHECK_MODULES):
        raise ValueError(f"unexpected canonical kernel target order: {list(targets)}")
    for mod, report in targets.items():
        if (
            report.get("recursive") is not True
            or report.get("norec_absent") is not True
            or report.get("norec_present") is not False
            or report.get("target_module") != mod
            or report.get("exit_code") != 0
            or report.get("unexpected_axioms") != []
            or report.get("missing_expected_axioms") != []
            or sorted(cast("list[str]", report.get("axioms", [])))
            != sorted(EXPECTED_CANONICAL_FP_AXIOMS)
        ):
            raise ValueError(f"canonical kernel target {mod} violated recursive invariants")
    total_elapsed = sum(
        cast("float", report.get("elapsed_seconds", 0.0))
        for report in targets.values()
    )
    return {
        "schema": "verifiedos-canonical-tag-kernel-check/2",
        "recursive": True,
        "norec_absent": True,
        "norec_present": False,
        "target_modules": list(KERNEL_CHECK_MODULES),
        "expected_axioms": sorted(EXPECTED_CANONICAL_FP_AXIOMS),
        "axiom_count": len(EXPECTED_CANONICAL_FP_AXIOMS),
        "total_elapsed_seconds": total_elapsed,
        "targets": targets,
    }


def _verify_frozen_assumptions(
    fresh: dict[str, object],
    frozen_doc: dict[str, object],
) -> None:
    _common.verify_frozen_assumptions(fresh, frozen_doc, bundle_label="canonical assumptions")


def _verify_frozen_single_kernel_target(
    fresh: dict[str, object],
    frozen_doc: dict[str, object],
) -> None:
    if (fresh.get("recursive") is not True or fresh.get("norec_absent") is not True
            or fresh.get("norec_present") is not False):
        raise ValueError("fresh canonical kernel-check report must be recursive without -norec")
    if ("-norec" in cast("list[str]", fresh.get("portable_flags", []))
            or "-norec" in cast("list[str]", fresh.get("argv", []))
            or fresh.get("exit_code") != 0):
        raise ValueError("fresh canonical kernel-check violated recursive check invariants")
    if (fresh.get("unexpected_axioms") != []
            or fresh.get("missing_expected_axioms") != []
            or sorted(cast("list[str]", fresh.get("axioms", [])))
            != sorted(EXPECTED_CANONICAL_FP_AXIOMS)):
        raise ValueError("fresh canonical kernel-check axioms do not equal the 31 FP axioms")
    for field in (
        "schema", "recursive", "norec_absent", "norec_present", "target_module",
        "portable_flags", "exit_code", "expected_axioms", "axioms", "axiom_count",
        "unexpected_axioms", "missing_expected_axioms", "indices_not_mattering",
    ):
        if fresh.get(field) != frozen_doc.get(field):
            raise ValueError(
                f"canonical kernel-check {field} differs from frozen closure bundle",
            )


def _verify_frozen_kernel_check(
    fresh: dict[str, object],
    frozen_doc: dict[str, object],
) -> None:
    if fresh.get("schema") == "verifiedos-canonical-tag-kernel-check/2":
        if (fresh.get("recursive") is not True or fresh.get("norec_absent") is not True
                or fresh.get("norec_present") is not False):
            raise ValueError("fresh canonical kernel-check report must be recursive without -norec")
        for field in (
            "schema", "recursive", "norec_absent", "norec_present",
            "target_modules", "expected_axioms", "axiom_count",
        ):
            if fresh.get(field) != frozen_doc.get(field):
                raise ValueError(
                    f"canonical kernel-check {field} differs from frozen closure bundle",
                )
        fresh_targets = cast("dict[str, dict[str, object]]", fresh["targets"])
        frozen_targets = cast("dict[str, dict[str, object]]", frozen_doc["targets"])
        if list(fresh_targets) != list(frozen_targets):
            raise ValueError("canonical kernel-check target keys differ from frozen closure bundle")
        for mod in fresh_targets:
            _verify_frozen_single_kernel_target(fresh_targets[mod], frozen_targets[mod])
        return
    _verify_frozen_single_kernel_target(fresh, frozen_doc)


def verify_frozen_canonical_closure(
    frozen_manifest: Path,
    expected_manifest_sha: str,
    assumptions_report: dict[str, object],
    kernel_report: dict[str, object],
    installed_comparison: dict[str, list[str]] | None = None,
) -> None:
    """Verify canonical closure outputs and bundle member hashes against `frozen_manifest`."""
    require_sha(frozen_manifest, expected_manifest_sha)
    members = cast(
        "dict[str, dict[str, object]]",
        _load_json(frozen_manifest)["files"],
    )
    for required_member in (
        "assumptions.json", "commands.json", "inputs.json",
        "installed-comparison.json", "kernel-check.json",
    ):
        if required_member not in members:
            raise ValueError(f"frozen canonical closure manifest missing {required_member}")
        info = members[required_member]
        member_path = frozen_manifest.parent / cast("str", info["path"])
        require_sha(member_path, cast("str", info["sha256"]))
    frozen_assumptions = _load_json(
        frozen_manifest.parent / cast("str", members["assumptions.json"]["path"]),
    )
    _verify_frozen_assumptions(assumptions_report, frozen_assumptions)
    frozen_kernel = _load_json(
        frozen_manifest.parent / cast("str", members["kernel-check.json"]["path"]),
    )
    _verify_frozen_kernel_check(kernel_report, frozen_kernel)
    if installed_comparison is not None:
        verify_installed_unchanged(installed_comparison)


def main() -> None:
    """Run strict compile, native Print Assumptions audit, and recursive rocqchk."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--whole-term-dir", default=DEFAULT_WHOLE_TERM_DIR, type=absolute)
    parser.add_argument("--canonical-support", default=DEFAULT_CANONICAL_SUPPORT, type=absolute)
    parser.add_argument("--stdpp", default=DEFAULT_STDPP, type=absolute)
    parser.add_argument("--rocq-prefix", default=DEFAULT_ROCQ_PREFIX, type=absolute)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    recipe_path = repo / "tools/sail-tag-outcomes/candidate.json"
    support_recipe_path = repo / "tools/opam/sail-support-qualification.json"
    recipe = _load_json(recipe_path)
    support_recipe = _load_json(support_recipe_path)

    diag_manifest_path = repo / CANONICAL_DIAGNOSTIC_MANIFEST_REL
    diag_manifest = _load_json(diag_manifest_path)
    diag_files = cast("dict[str, dict[str, object]]", diag_manifest["files"])
    compile_result_path = (
        diag_manifest_path.parent / cast("str", diag_files["compile-result.json"]["path"])
    )
    closure_reading_path = (
        diag_manifest_path.parent / cast("str", diag_files["closure-reading.json"]["path"])
    )
    require_sha(compile_result_path, cast("str", diag_files["compile-result.json"]["sha256"]))
    require_sha(closure_reading_path, cast("str", diag_files["closure-reading.json"]["sha256"]))

    callers_manifest_path = repo / CANONICAL_CALLERS_MANIFEST_REL
    callers_manifest = _load_json(callers_manifest_path)
    callers_files = cast("dict[str, dict[str, object]]", callers_manifest["files"])
    bridge_source = (
        callers_manifest_path.parent
        / cast("str", callers_files["CanonicalPhysicalCallerBridge.v.txt"]["path"])
    )
    require_sha(bridge_source, CANONICAL_BRIDGE_SHA256)
    require_sha(
        bridge_source,
        cast("str", callers_files["CanonicalPhysicalCallerBridge.v.txt"]["sha256"]),
    )

    tag_interpreter_source = repo / "tools/sail-tag-outcomes/TagInterpreter.v"
    tag_conservativity_source = repo / "tools/sail-tag-outcomes/TagConservativity.v"
    canonical_conservativity_source = (
        repo / "tools/sail-tag-outcomes/CanonicalTagConservativity.v"
    )
    require_sha(tag_interpreter_source, TAG_INTERPRETER_SHA256)
    require_sha(tag_conservativity_source, TAG_CONSERVATIVITY_SHA256)
    require_sha(canonical_conservativity_source, CANONICAL_TAG_CONSERVATIVITY_SHA256)

    closure_doc = _load_json(closure_reading_path)
    recorded_fp = sorted(cast("list[str]", closure_doc["emitted_axioms"]))
    if recorded_fp != sorted(EXPECTED_CANONICAL_FP_AXIOMS):
        raise ValueError("recorded canonical FP axioms do not match expected 31 axioms")

    frozen_conservativity = cast(
        "dict[str, str] | None", recipe.get("frozen_canonical_conservativity_manifest"),
    )
    if frozen_conservativity is not None:
        require_sha(repo / frozen_conservativity["path"], frozen_conservativity["sha256"])

    try:
        out = output_path(
            args.out,
            (repo, args.whole_term_dir, args.canonical_support, args.stdpp, args.rocq_prefix),
        )
    except ValueError as error:
        parser.error(str(error))

    native = Path("/root/build")
    if not out.is_relative_to(native) or not any(p.name.startswith("lane-") for p in out.parents):
        parser.error("--out must be below the assigned /root/build/lane-* root")

    for input_dir in (args.whole_term_dir, args.canonical_support, args.stdpp):
        _check_no_dir_symlinks(input_dir)

    whole_term_verified = verify_whole_term_inputs(args.whole_term_dir, compile_result_path)
    support_modules = cast("list[str]", support_recipe["support_modules"])
    support_verified = verify_canonical_support_inputs(
        args.canonical_support, closure_reading_path, support_modules,
    )
    expected_stdpp = retained_stdpp(repo / cast("str", recipe["retained_library_evidence"]))
    actual_stdpp = tree_sha(args.stdpp)
    if actual_stdpp != expected_stdpp:
        raise ValueError("private stdpp files do not match the retained library identities")

    rocq_bin = args.rocq_prefix / "bin/rocq"
    rocqchk_bin = args.rocq_prefix / "bin/rocqchk"
    if not rocq_bin.is_file() or not rocqchk_bin.is_file():
        raise ValueError(f"missing rocq/rocqchk under {args.rocq_prefix}")

    out.mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, object]] = []

    def inventory() -> dict[str, dict[str, str]]:
        return {
            str(args.rocq_prefix): {
                str(p.relative_to(args.rocq_prefix)): sha(p)
                for tree in (args.rocq_prefix / "bin", args.rocq_prefix / "lib")
                for p in sorted(tree.rglob("*")) if p.is_file()
            },
        }

    before = inventory()
    _write_json(out / "installed-before.json", before)

    inputs_doc: dict[str, object] = {
        "schema": "verifiedos-canonical-tag-inputs/1",
        "driver_sha256": sha(Path(__file__)),
        "reading_sources_sha256": {
            name: sha(repo / name) for name in python_dependencies.sources(
                repo, ("tools/vos/proofaudit.py",),
            )
        },
        "candidate_recipe_sha256": sha(recipe_path),
        "support_recipe_sha256": sha(support_recipe_path),
        "canonical_diagnostic_manifest_sha256": sha(diag_manifest_path),
        "canonical_callers_manifest_sha256": sha(callers_manifest_path),
        "frozen_canonical_conservativity_manifest_sha256": (
            frozen_conservativity["sha256"] if frozen_conservativity is not None else None
        ),
        "tag_interpreter_source_sha256": TAG_INTERPRETER_SHA256,
        "tag_conservativity_source_sha256": TAG_CONSERVATIVITY_SHA256,
        "canonical_bridge_source_sha256": CANONICAL_BRIDGE_SHA256,
        "canonical_tag_conservativity_source_sha256": CANONICAL_TAG_CONSERVATIVITY_SHA256,
        "rocq_sha256": sha(rocq_bin),
        "rocqchk_sha256": sha(rocqchk_bin),
        "whole_term_files": whole_term_verified,
        "canonical_support_modules": support_verified,
        "stdpp_sha256": actual_stdpp,
    }
    _write_json(out / "inputs.json", inputs_doc)

    def run(
        label: str,
        argv: list[str | Path],
        *,
        cwd: Path = out,
        timeout: int = STRICT_COMPILE_TIMEOUT_SECONDS,
    ) -> tuple[subprocess.CompletedProcess[str], float]:
        started = time.monotonic()
        result = subprocess.run(
            list(map(str, argv)),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        elapsed = time.monotonic() - started
        safe_label = re.sub(r"[^A-Za-z0-9._-]+", "_", label)
        log = out / f"{safe_label}.log"
        log.write_text(result.stdout + result.stderr, encoding="utf-8", newline="\n")
        commands.append({
            "label": label,
            "argv": list(map(str, argv)),
            "cwd": str(cwd),
            "exit": result.returncode,
            "seconds": elapsed,
            "log": log.name,
            "sha256": sha(log),
            "stdout_sha256": hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
        })
        if result.returncode:
            raise RuntimeError(f"{label} refused (exit {result.returncode}); see {log}")
        return result, elapsed

    try:
        tag_dest = out / "TagInterpreter.v"
        conserv_dest = out / "TagConservativity.v"
        bridge_dest = out / "CanonicalPhysicalCallerBridge.v"
        canon_conserv_dest = out / "CanonicalTagConservativity.v"
        tag_dest.write_bytes(tag_interpreter_source.read_bytes())
        conserv_dest.write_bytes(tag_conservativity_source.read_bytes())
        bridge_dest.write_bytes(bridge_source.read_bytes())
        canon_conserv_dest.write_bytes(canonical_conservativity_source.read_bytes())
        require_sha(tag_dest, TAG_INTERPRETER_SHA256)
        require_sha(conserv_dest, TAG_CONSERVATIVITY_SHA256)
        require_sha(bridge_dest, CANONICAL_BRIDGE_SHA256)
        require_sha(canon_conserv_dest, CANONICAL_TAG_CONSERVATIVITY_SHA256)

        strict_flags = cast("list[str]", support_recipe["strict_flags"])
        base_loadpaths: list[str | Path] = [
            "-boot",
            "-R", args.rocq_prefix / "lib/coq/theories", "Corelib",
            "-Q", args.rocq_prefix / "lib/coq/user-contrib/Stdlib", "Stdlib",
            "-Q", args.stdpp, "stdpp",
            "-R", args.canonical_support, "SailStdpp",
            "-R", args.whole_term_dir, "",
            "-R", out, "",
        ]
        compile_prefix: list[str | Path] = [
            rocq_bin,
            "c",
            *base_loadpaths,
            *strict_flags,
            "-output-directory", out,
        ]
        for mod, src_path in (
            ("TagInterpreter", tag_dest),
            ("TagConservativity", conserv_dest),
            ("CanonicalPhysicalCallerBridge", bridge_dest),
            ("CanonicalTagConservativity", canon_conserv_dest),
        ):
            res, _ = run(f"compile-{mod}", [*compile_prefix, src_path], cwd=out)
            if res.stdout or res.stderr:
                raise RuntimeError(f"strict compile of {mod} emitted a diagnostic")

        assump_stage = out / "assumptions-queries"
        assump_stage.mkdir()
        assump_compiler: list[str | Path] = [
            rocq_bin,
            "c",
            *base_loadpaths,
            "-R", assump_stage, "",
            *strict_flags,
            "-output-directory", assump_stage,
        ]

        def assumption_query(name: str, content: str) -> str:
            qsrc = assump_stage / f"{name}.v"
            qsrc.write_text(content, encoding="utf-8", newline="")
            res, _ = run(f"assumptions-{name}", [*assump_compiler, qsrc], cwd=assump_stage)
            if res.stderr:
                raise RuntimeError(f"assumption query {name} emitted a diagnostic")
            return res.stdout

        assumptions_report = audit_canonical_assumptions(
            AUTHORED_CANONICAL_MODULES, assumption_query,
        )
        _write_json(out / "assumptions.json", assumptions_report)

        portable_kernel_flags = [
            "-silent",
            "-o",
            "-boot",
            "-R", "<rocq_prefix>/lib/coq/theories", "Corelib",
            "-Q", "<rocq_prefix>/lib/coq/user-contrib/Stdlib", "Stdlib",
            "-Q", "<stdpp>", "stdpp",
            "-R", "<canonical_support>", "SailStdpp",
            "-R", "<whole_term_dir>", "",
            "-R", "<out>", "",
        ]
        kernel_targets: dict[str, dict[str, object]] = {}
        for target_mod in KERNEL_CHECK_MODULES:
            kernel_argv: list[str | Path] = [
                rocqchk_bin,
                "-silent",
                "-o",
                *base_loadpaths,
                target_mod,
            ]
            kernel_res, target_elapsed = run(
                f"kernel-{target_mod}",
                kernel_argv,
                cwd=out,
                timeout=KERNEL_CHECK_TIMEOUT_SECONDS,
            )
            kernel_targets[target_mod] = verify_canonical_kernel_check(
                list(map(str, kernel_argv)),
                kernel_res.returncode,
                kernel_res.stdout,
                kernel_res.stderr,
                target_module=target_mod,
                portable_flags=portable_kernel_flags,
                expected_axioms=EXPECTED_CANONICAL_FP_AXIOMS,
                elapsed_seconds=target_elapsed,
            )
        kernel_report = build_canonical_kernel_report(kernel_targets)
        kernel_elapsed = cast("float", kernel_report["total_elapsed_seconds"])
        _write_json(out / "kernel-check.json", kernel_report)

        # Re-verify input digests after compilation and kernel checking.
        verify_whole_term_inputs(args.whole_term_dir, compile_result_path)
        verify_canonical_support_inputs(
            args.canonical_support, closure_reading_path, support_modules,
        )
        if tree_sha(args.stdpp) != expected_stdpp:
            raise ValueError("private stdpp files changed during canonical closure check")
    finally:
        after = inventory()
        changes = compare_installed_inventories(before, after)
        _write_json(out / "commands.json", commands)
        _write_json(out / "installed-after.json", after)
        _write_json(out / "installed-comparison.json", changes)
        verify_installed_unchanged(changes)

    if frozen_conservativity is not None:
        verify_frozen_canonical_closure(
            repo / frozen_conservativity["path"],
            frozen_conservativity["sha256"],
            assumptions_report,
            kernel_report,
            changes,
        )

    print(
        f"PASS canonical closure: {out} "
        f"(declarations={assumptions_report['total_declarations']}, "
        f"axioms={kernel_report['axiom_count']}, "
        f"rocqchk_seconds={kernel_elapsed:.3f})",
    )


if __name__ == "__main__":
    main()
