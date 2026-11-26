# SPDX-License-Identifier: Apache-2.0
"""Verify recursive kernel and native assumption closure over the canonical hart-0 term."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vos import proofaudit, python_dependencies
from vos.jsonutil import unique_object

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
CANONICAL_BRIDGE_SHA256 = "420b764eef05c2d2cf392975b67afcd7242b82f241bc1100e3b74edad6f51112"

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
AUTHORED_CANONICAL_MODULES = ("TagInterpreter", "CanonicalPhysicalCallerBridge")
CANONICAL_TAG_PLANE_INST = "CanonicalTagPlaneInst"

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


def sha(path: Path) -> str:
    """Return the lowercase SHA-256 hex digest of `path`."""
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def tree_sha(root: Path) -> dict[str, str]:
    """Return relative-POSIX-path -> SHA-256 for every non-`.glob` file under `root`."""
    return {
        path.relative_to(root).as_posix(): sha(path)
        for path in sorted(root.rglob("*")) if path.is_file() and path.suffix != ".glob"
    }


def absolute(value: str) -> Path:
    """Parse an expanded absolute native directory path."""
    path = Path(value)
    if not path.is_absolute() or "%" in value:
        raise argparse.ArgumentTypeError("an expanded absolute native path is required")
    return path.resolve(strict=True)


def output_path(value: str, protected: tuple[Path, ...]) -> Path:
    """Require an expanded absolute empty/new output directory not overlapping protected inputs."""
    path = Path(value)
    if not path.is_absolute() or "%" in value or path.is_symlink():
        raise ValueError("output must be an expanded absolute, non-symlink directory")
    if any(parent.is_symlink() for parent in path.parents):
        raise ValueError("output ancestors must not be symlinks")
    if path.exists():
        if not path.is_dir():
            raise ValueError("output path exists and is not a directory")
        if any(path.iterdir()):
            raise ValueError("output directory must be empty")
    resolved = path.resolve()
    for entry in protected:
        canonical = entry.resolve(strict=True)
        if resolved.is_relative_to(canonical) or canonical.is_relative_to(resolved):
            raise ValueError(f"output overlaps protected input: {canonical}")
    return resolved


def require_sha(path: Path, expected: str) -> None:
    """Raise `ValueError` unless `path` exists as a regular file with SHA-256 `expected`."""
    if not path.is_file():
        raise ValueError(f"missing required input file: {path}")
    if sha(path) != expected:
        raise ValueError(f"input digest mismatch: {path}")


def _load_json(path: Path) -> dict[str, object]:
    return cast(
        "dict[str, object]",
        json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object),
    )


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


def retained_stdpp(evidence: Path) -> dict[str, str]:
    """Load the frozen private `stdpp` file-digest map from `library-inputs-before.json`."""
    raw: object = json.loads(evidence.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    libraries = cast("dict[str, dict[str, str]]", raw)
    stdpp, = (reading for path, reading in libraries.items() if Path(path).name == "stdpp")
    return stdpp


def compare_installed_inventories(
    before: dict[str, dict[str, str]],
    after: dict[str, dict[str, str]],
) -> dict[str, list[str]]:
    """Return sorted added, removed, or modified relative paths per installed prefix."""
    if set(before) != set(after):
        raise ValueError("installed prefix keys changed between before and after snapshots")
    return {
        prefix: sorted(
            key for key in before[prefix].keys() | after[prefix].keys()
            if before[prefix].get(key) != after[prefix].get(key)
        )
        for prefix in before
    }


def verify_installed_unchanged(changes: dict[str, list[str]]) -> None:
    """Refuse any change to the installed Rocq prefix."""
    if not changes or any(changes.values()):
        raise ValueError(f"installed paths changed: {changes}")


def canonical_assumption_spec(module: str) -> tuple[str, str]:
    """Return `(search_target, preamble)` for a canonical-closure authored module."""
    if module == "TagInterpreter":
        return (
            CANONICAL_TAG_PLANE_INST,
            f"Require rv64d_types TagInterpreter.\n"
            f"Module {CANONICAL_TAG_PLANE_INST} := TagInterpreter.TagPlane "
            f"rv64d_types.Arch rv64d_types.Interface.\n",
        )
    if module == "CanonicalPhysicalCallerBridge":
        return module, f"Require {module}.\n"
    raise ValueError(f"unsupported canonical closure module: {module}")


def canonical_inventory_query(module: str) -> tuple[str, str]:
    """Build a `proofaudit.inventory_query` script for `module`, instantiating `TagPlane`."""
    target, preamble = canonical_assumption_spec(module)
    base = proofaudit.inventory_query(target)
    prefix = f"Require {target}.\n"
    if not base.startswith(prefix):
        raise ValueError(f"unexpected inventory_query prefix for {target}")
    return target, preamble + base[len(prefix):]


def canonical_assumption_query(module: str, symbols: list[proofaudit.Symbol]) -> str:
    """Build a `proofaudit.assumption_query` script for `symbols` under `module`."""
    target, preamble = canonical_assumption_spec(module)
    base = proofaudit.assumption_query(target, symbols)
    prefix = f"Require {target}.\n"
    if not base.startswith(prefix):
        raise ValueError(f"unexpected assumption_query prefix for {target}")
    return preamble + base[len(prefix):]


def audit_canonical_module_assumptions(
    module: str,
    query: Callable[[str, str], str],
) -> dict[str, object]:
    """Enumerate all declarations of `module` and require `Closed under the global context`."""
    target, inv_script = canonical_inventory_query(module)
    inv_stdout = query(f"AssumptionsInventory_{module}", inv_script)
    symbols = proofaudit.inventory(inv_stdout, target)
    if not symbols:
        raise ValueError(f"empty native inventory for canonical module {module}")
    assump_script = canonical_assumption_query(module, symbols)
    assump_stdout = query(f"AssumptionsCheck_{module}", assump_script)
    proofaudit.assumptions(assump_stdout, symbols)
    non_closed = {
        symbol["name"]: list(symbol["assumptions"])
        for symbol in symbols if symbol["assumptions"]
    }
    if non_closed:
        raise ValueError(
            f"canonical module {module} has non-closed declaration(s): {non_closed}",
        )
    return {
        "module": module,
        "query_target": target,
        "instantiated_functor": target != module,
        "declaration_count": len(symbols),
        "closed_count": len(symbols),
        "all_closed": True,
        "non_closed": [],
        "symbols": [symbol["name"] for symbol in symbols],
    }


def audit_canonical_assumptions(
    modules: tuple[str, ...],
    query: Callable[[str, str], str],
) -> dict[str, object]:
    """Audit native `Print Assumptions` across every enumerated declaration of `modules`."""
    per_module: dict[str, dict[str, object]] = {
        mod: audit_canonical_module_assumptions(mod, query) for mod in modules
    }
    total = sum(cast("int", per_module[mod]["declaration_count"]) for mod in modules)
    return {
        "schema": "verifiedos-canonical-tag-assumptions/1",
        "all_closed": True,
        "modules_audited": list(modules),
        "total_declarations": total,
        "modules": per_module,
    }


def parse_kernel_summary(stderr: str) -> tuple[list[str], list[str]]:
    """Parse `rocqchk -silent -o` context summary via `proofaudit.kernel_context`."""
    axioms = proofaudit.kernel_context(stderr)
    lines = [line.rstrip() for line in stderr.splitlines() if line.strip()]
    marker = f"* {proofaudit.KERNEL_INDICES}:"
    indices: list[str] = []
    in_indices = False
    for line in lines:
        if line.startswith(marker):
            in_indices = True
            rest = line[len(marker):].strip()
            if rest == "<none>":
                in_indices = False
            continue
        if in_indices:
            if line.startswith("* "):
                break
            indices.append(line.strip())
    return axioms, sorted(indices)


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
    if "-norec" in argv or "-norec" in portable_flags:
        raise ValueError("canonical recursive kernel check must not pass -norec")
    if "-silent" not in argv or "-o" not in argv:
        raise ValueError("canonical recursive kernel check requires -silent -o")
    if "-silent" not in portable_flags or "-o" not in portable_flags:
        raise ValueError("canonical kernel portable_flags must include -silent -o")
    if target_module not in argv:
        raise ValueError(f"canonical kernel argv must name {target_module}")
    if returncode != 0 or stdout.strip():
        diagnostic = (stderr.strip() or stdout.strip()) or "no diagnostic"
        raise ValueError(
            f"canonical recursive kernel check failed (exit {returncode}): {diagnostic}",
        )
    axioms, indices = parse_kernel_summary(stderr)
    if len(axioms) != len(set(axioms)):
        raise ValueError(f"canonical kernel check reported duplicate axioms: {axioms}")
    actual_set = set(axioms)
    expected_set = set(expected_axioms)
    if len(expected_set) != len(expected_axioms):
        raise ValueError("expected_axioms contains duplicates")
    unexpected = sorted(actual_set - expected_set)
    missing = sorted(expected_set - actual_set)
    if unexpected or missing:
        raise ValueError(
            f"canonical kernel axioms mismatch: unexpected={unexpected}, missing={missing}",
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
        "expected_axioms": sorted(expected_axioms),
        "axioms": sorted(axioms),
        "axiom_count": len(axioms),
        "unexpected_axioms": unexpected,
        "missing_expected_axioms": missing,
        "indices_not_mattering": indices,
    }
    if elapsed_seconds is not None:
        report["elapsed_seconds"] = elapsed_seconds
    return report


def _verify_frozen_assumptions(
    fresh: dict[str, object],
    frozen_doc: dict[str, object],
) -> None:
    if fresh.get("all_closed") is not True:
        raise ValueError("fresh canonical assumptions report is not closed")
    for key in ("schema", "all_closed", "modules_audited", "total_declarations"):
        if fresh.get(key) != frozen_doc.get(key):
            raise ValueError(f"canonical assumptions {key} differs from frozen closure bundle")
    fresh_mods = cast("dict[str, dict[str, object]]", fresh["modules"])
    frozen_mods = cast("dict[str, dict[str, object]]", frozen_doc["modules"])
    if set(fresh_mods) != set(frozen_mods):
        raise ValueError("canonical assumptions module keys differ from frozen closure bundle")
    for mod in fresh_mods:
        f_mod = fresh_mods[mod]
        r_mod = frozen_mods[mod]
        if (f_mod.get("all_closed") is not True or f_mod.get("non_closed") != []
                or cast("int", f_mod.get("declaration_count", 0)) <= 0):
            raise ValueError(f"fresh canonical assumptions invalid for module {mod}")
        for field in (
            "module", "query_target", "instantiated_functor",
            "declaration_count", "closed_count", "all_closed", "non_closed", "symbols",
        ):
            if f_mod.get(field) != r_mod.get(field):
                raise ValueError(
                    f"canonical assumptions {mod}.{field} differs from frozen closure bundle",
                )


def _verify_frozen_kernel_check(
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


def _check_no_dir_symlinks(root: Path) -> None:
    if any(p.is_symlink() and p.is_dir() for p in root.rglob("*")):
        raise ValueError(f"input directory may not contain directory symlinks: {root}")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


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
    require_sha(tag_interpreter_source, TAG_INTERPRETER_SHA256)

    closure_doc = _load_json(closure_reading_path)
    recorded_fp = sorted(cast("list[str]", closure_doc["emitted_axioms"]))
    if recorded_fp != sorted(EXPECTED_CANONICAL_FP_AXIOMS):
        raise ValueError("recorded canonical FP axioms do not match expected 31 axioms")

    frozen_canonical = cast("dict[str, str] | None", recipe.get("frozen_canonical_closure_manifest"))
    if frozen_canonical is not None:
        require_sha(repo / frozen_canonical["path"], frozen_canonical["sha256"])

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
        "frozen_canonical_closure_manifest_sha256": (
            frozen_canonical["sha256"] if frozen_canonical is not None else None
        ),
        "tag_interpreter_source_sha256": TAG_INTERPRETER_SHA256,
        "canonical_bridge_source_sha256": CANONICAL_BRIDGE_SHA256,
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
        bridge_dest = out / "CanonicalPhysicalCallerBridge.v"
        tag_dest.write_bytes(tag_interpreter_source.read_bytes())
        bridge_dest.write_bytes(bridge_source.read_bytes())
        require_sha(tag_dest, TAG_INTERPRETER_SHA256)
        require_sha(bridge_dest, CANONICAL_BRIDGE_SHA256)

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
            ("CanonicalPhysicalCallerBridge", bridge_dest),
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

        kernel_argv: list[str | Path] = [
            rocqchk_bin,
            "-silent",
            "-o",
            *base_loadpaths,
            "CanonicalPhysicalCallerBridge",
        ]
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
        kernel_res, kernel_elapsed = run(
            "kernel-CanonicalPhysicalCallerBridge",
            kernel_argv,
            cwd=out,
            timeout=KERNEL_CHECK_TIMEOUT_SECONDS,
        )
        kernel_report = verify_canonical_kernel_check(
            list(map(str, kernel_argv)),
            kernel_res.returncode,
            kernel_res.stdout,
            kernel_res.stderr,
            target_module="CanonicalPhysicalCallerBridge",
            portable_flags=portable_kernel_flags,
            expected_axioms=EXPECTED_CANONICAL_FP_AXIOMS,
            elapsed_seconds=kernel_elapsed,
        )
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

    if frozen_canonical is not None:
        verify_frozen_canonical_closure(
            repo / frozen_canonical["path"],
            frozen_canonical["sha256"],
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
