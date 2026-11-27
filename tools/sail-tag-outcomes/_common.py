# SPDX-License-Identifier: Apache-2.0
"""Shared input-identity, path-isolation, assumption-audit, and kernel-check helpers."""

import argparse
import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from vos import proofaudit
from vos.jsonutil import unique_object


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


def output_path(
    value: str,
    protected: tuple[Path, ...],
    *,
    allow_empty_existing: bool = False,
) -> Path:
    """Require an expanded absolute, non-symlink output directory not overlapping `protected`."""
    path = Path(value)
    if not path.is_absolute() or "%" in value or path.is_symlink():
        raise ValueError("output must be an expanded absolute, non-symlink directory")
    if any(parent.is_symlink() for parent in path.parents):
        raise ValueError("output ancestors must not be symlinks")
    if path.exists():
        if not allow_empty_existing:
            raise ValueError("output must be an expanded absolute, new directory")
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


def load_json(path: Path) -> dict[str, object]:
    """Decode a UTF-8 JSON object file while rejecting duplicate object keys."""
    return cast(
        "dict[str, object]",
        json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object),
    )


def write_json(path: Path, payload: object) -> None:
    """Write `payload` as sorted, indented UTF-8 JSON with a trailing newline."""
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def check_no_dir_symlinks(root: Path) -> None:
    """Refuse directory symlinks beneath an input tree."""
    if any(p.is_symlink() and p.is_dir() for p in root.rglob("*")):
        raise ValueError(f"input directory may not contain directory symlinks: {root}")


def retained_stdpp(evidence: Path) -> dict[str, str]:
    """Load the frozen private `stdpp` file-digest map from `library-inputs-before.json`."""
    libraries = cast("dict[str, dict[str, str]]", cast("object", load_json(evidence)))
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
    """Refuse any change to the installed prefixes."""
    if not changes or any(changes.values()):
        raise ValueError(f"installed paths changed: {changes}")


def inventory_query_from_spec(
    module: str,
    spec_fn: Callable[[str], tuple[str, str]],
) -> tuple[str, str]:
    """Build a `proofaudit.inventory_query` script for `module` using `spec_fn`."""
    target, preamble = spec_fn(module)
    base = proofaudit.inventory_query(target)
    prefix = f"Require {target}.\n"
    if not base.startswith(prefix):
        raise ValueError(f"unexpected inventory_query prefix for {target}")
    return target, preamble + base[len(prefix):]


def assumption_query_from_spec(
    module: str,
    symbols: list[proofaudit.Symbol],
    spec_fn: Callable[[str], tuple[str, str]],
) -> str:
    """Build a `proofaudit.assumption_query` script for `symbols` under `module`."""
    target, preamble = spec_fn(module)
    base = proofaudit.assumption_query(target, symbols)
    prefix = f"Require {target}.\n"
    if not base.startswith(prefix):
        raise ValueError(f"unexpected assumption_query prefix for {target}")
    return preamble + base[len(prefix):]


def audit_module_assumptions(
    module: str,
    query: Callable[[str, str], str],
    spec_fn: Callable[[str], tuple[str, str]],
    *,
    kind_label: str,
) -> dict[str, object]:
    """Enumerate `module` declarations and require `Closed under the global context`."""
    target, inv_script = inventory_query_from_spec(module, spec_fn)
    inv_stdout = query(f"AssumptionsInventory_{module}", inv_script)
    symbols = proofaudit.inventory(inv_stdout, target)
    if not symbols:
        raise ValueError(f"empty native inventory for {kind_label} module {module}")
    assump_script = assumption_query_from_spec(module, symbols, spec_fn)
    assump_stdout = query(f"AssumptionsCheck_{module}", assump_script)
    proofaudit.assumptions(assump_stdout, symbols)
    non_closed = {
        symbol["name"]: list(symbol["assumptions"])
        for symbol in symbols if symbol["assumptions"]
    }
    if non_closed:
        raise ValueError(
            f"{kind_label} module {module} has non-closed declaration(s): {non_closed}",
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


def audit_assumptions(
    modules: tuple[str, ...],
    query: Callable[[str, str], str],
    spec_fn: Callable[[str], tuple[str, str]],
    *,
    schema: str,
    kind_label: str,
) -> dict[str, object]:
    """Audit native `Print Assumptions` across every enumerated declaration of `modules`."""
    per_module: dict[str, dict[str, object]] = {
        mod: audit_module_assumptions(mod, query, spec_fn, kind_label=kind_label)
        for mod in modules
    }
    total = sum(cast("int", per_module[mod]["declaration_count"]) for mod in modules)
    return {
        "schema": schema,
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


def validate_kernel_run(
    label: str,
    argv: list[str],
    returncode: int,
    stdout: str,
    stderr: str,
    expected_axioms: Sequence[str],
    *,
    portable_flags: list[str],
    required_token: str | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Validate one recursive `rocqchk -silent -o` execution and return sorted axioms/indices."""
    if "-norec" in argv or "-norec" in portable_flags:
        raise ValueError(f"{label} must not pass -norec")
    if "-silent" not in argv or "-o" not in argv:
        raise ValueError(f"{label} requires -silent -o")
    if "-silent" not in portable_flags or "-o" not in portable_flags:
        raise ValueError(f"{label} portable_flags must include -silent -o")
    if required_token is not None and required_token not in argv:
        raise ValueError(f"{label} argv must name {required_token}")
    if returncode != 0 or stdout.strip():
        diagnostic = (stderr.strip() or stdout.strip()) or "no diagnostic"
        raise ValueError(f"{label} failed (exit {returncode}): {diagnostic}")
    axioms, indices = parse_kernel_summary(stderr)
    if len(axioms) != len(set(axioms)):
        raise ValueError(f"{label} reported duplicate axioms: {axioms}")
    actual_set = set(axioms)
    expected_set = set(expected_axioms)
    if len(expected_set) != len(expected_axioms):
        raise ValueError("expected_axioms contains duplicates")
    unexpected = sorted(actual_set - expected_set)
    missing = sorted(expected_set - actual_set)
    if unexpected or missing:
        raise ValueError(
            f"{label} axioms mismatch: unexpected={unexpected}, missing={missing}",
        )
    return sorted(axioms), sorted(expected_axioms), indices


def verify_frozen_assumptions(
    fresh: dict[str, object],
    frozen_doc: dict[str, object],
    *,
    bundle_label: str,
) -> None:
    """Compare a fresh `assumptions.json` report against its frozen bundle counterpart."""
    if fresh.get("all_closed") is not True:
        raise ValueError(f"fresh {bundle_label} report is not closed")
    for key in ("schema", "all_closed", "modules_audited", "total_declarations"):
        if fresh.get(key) != frozen_doc.get(key):
            raise ValueError(f"{bundle_label} {key} differs from frozen closure bundle")
    fresh_mods = cast("dict[str, dict[str, object]]", fresh["modules"])
    frozen_mods = cast("dict[str, dict[str, object]]", frozen_doc["modules"])
    if set(fresh_mods) != set(frozen_mods):
        raise ValueError(f"{bundle_label} module keys differ from frozen closure bundle")
    for mod in fresh_mods:
        f_mod = fresh_mods[mod]
        r_mod = frozen_mods[mod]
        if (f_mod.get("all_closed") is not True or f_mod.get("non_closed") != []
                or cast("int", f_mod.get("declaration_count", 0)) <= 0):
            raise ValueError(f"fresh {bundle_label} invalid for module {mod}")
        for field in (
            "module", "query_target", "instantiated_functor",
            "declaration_count", "closed_count", "all_closed", "non_closed", "symbols",
        ):
            if f_mod.get(field) != r_mod.get(field):
                raise ValueError(
                    f"{bundle_label} {mod}.{field} differs from frozen closure bundle",
                )
