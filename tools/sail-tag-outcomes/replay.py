# SPDX-License-Identifier: Apache-2.0
"""Replay the isolated canonical V1 tag candidate; supplies no production verdict."""
import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vos import proofaudit, proofreading, python_dependencies
from vos.jsonutil import unique_object

PATCHED_SUPPORT_SOURCES = frozenset({"ConcurrencyInterface.v", "ConcurrencyInterfaceBuiltins.v"})
AUTHORED_MODULES = (
    "TagInterpreter",
    "TagControls",
    "TagConservativity",
    "PhysicalCallerBridge",
)
VALUES_LEMMAS_AXIOMS = (
    "Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq",
    "Stdlib.Logic.FunctionalExtensionality.functional_extensionality_dep",
    "Stdlib.Logic.ProofIrrelevance.proof_irrelevance",
)
VALUES_LEMMAS_NOTE = (
    "Upstream coq-sail src/Values_lemmas.v imports Stdlib.Program and Stdlib.Program.Wf; "
    "outside the canonical term import closure and never admitted to the project allowlist."
)
_ABOUT_FOOTER = re.compile(
    r'\(use "About" for full details on the implicit arguments of ([^()]+)\)',
)
_SYNTACTICALLY_EQUAL = re.compile(
    r"^(Expands to: Constant \S+) \(syntactically equal to \S+\)$", re.MULTILINE,
)
_OPAQUE_BUT_TRANSPARENT = re.compile(
    r"^(\S+) is opaque but may be made transparent$", re.MULTILINE,
)


def sha(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def tree_sha(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha(path)
        for path in sorted(root.rglob("*")) if path.is_file() and path.suffix != ".glob"
    }


def absolute(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or "%" in value:
        raise argparse.ArgumentTypeError("an expanded absolute native path is required")
    return path.resolve(strict=True)


def output_path(value: str, protected: tuple[Path, ...]) -> Path:
    """Refuse canonical input overlap and aliases before any output mutation."""
    path = Path(value)
    if not path.is_absolute() or "%" in value or path.exists() or path.is_symlink():
        raise ValueError("output must be an expanded absolute, new directory")
    if any(p.is_symlink() for p in path.parents):
        raise ValueError("output ancestors must not be symlinks")
    path = path.resolve()
    for entry in protected:
        canonical = entry.resolve(strict=True)
        if path.is_relative_to(canonical) or canonical.is_relative_to(path):
            raise ValueError(f"output overlaps protected input: {canonical}")
    return path


def require_sha(path: Path, expected: str) -> None:
    if sha(path) != expected:
        raise ValueError(f"input digest mismatch: {path}")


def retained_emission_inputs(
    evidence: Path, plugin: Path, sail: Path, z3: Path,
) -> tuple[dict[Path, str], dict[str, str]]:
    reading = json.loads(evidence.read_text(encoding="utf-8"))
    if reading["checks"] != {"matched_retained_outputs": True, "unchanged_inputs": True}:
        raise ValueError("retained emission did not match the frozen inputs and outputs")
    recorded_hashes = cast(dict[str, str], reading["input_hashes"])
    input_hashes = {Path(name).name: digest for name, digest in recorded_hashes.items()}
    require_sha(plugin, input_hashes["sail_plugin_coq.cmxs"])
    require_sha(sail, input_hashes["sail"])
    require_sha(z3, input_hashes["z3"])
    plugins = {
        plugin.parent / name: digest for name, digest in input_hashes.items()
        if name.endswith(".cmxs")
    }
    for path, digest in plugins.items():
        require_sha(path, digest)
    return plugins, cast(dict[str, str], reading["expected"])


def retained_stdpp(evidence: Path) -> dict[str, str]:
    libraries = cast(dict[str, dict[str, str]], json.loads(evidence.read_text(encoding="utf-8")))
    stdpp, = (reading for path, reading in libraries.items() if Path(path).name == "stdpp")
    return stdpp


def match_v1_reading(query: Callable[[str, str], str], output: Path, expected: str) -> None:
    """Measure the instantiated V1 declarations against one side of the frozen comparison."""
    module = "bindings_types"
    owners = (f"{module}.Interface", f"{module}.Defs")
    inventory = query("Inventory", f"Require {module}.\n" + proofaudit.SETTINGS
                      + f"Print Table Search Blacklist.\nSearch _ inside {' '.join(owners)}.\n")
    names = [symbol["name"] for symbol in proofaudit.inventory(inventory, module)]
    prefixes = tuple(owner + "." for owner in owners)
    if not names or any(not name.startswith(prefixes) for name in names):
        raise ValueError("empty V1 inventory or unexpected declaration owner")

    facts = proofreading.answers(query("Facts", proofreading.facts_query(module, names)),
                                 [f"{name}|{field}" for name in names for field in ("check", "about")])
    abouts = {name: proofreading.parse_about(
        name, proofreading.fresh_universes(facts[name + "|about"], "Facts")) for name in names}
    printed = [name for name in names if abouts[name].printed]
    bodies = proofreading.answers(query("Bodies", proofreading.bodies_query(module, printed)),
                                  [name + "|print" for name in printed])
    reading = {name: proofreading.entry(
        proofreading.fresh_universes(facts[name + "|check"], "Facts"), abouts[name],
        proofreading.fresh_universes(bodies[name + "|print"], "Bodies") if abouts[name].printed else None,
    ) for name in names}
    output.write_text(json.dumps(reading, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    if sha(output) != expected:
        raise ValueError(f"V1 declarations differ from the frozen reading: {output}")


def parse_support_inventory(stdout: str, module: str) -> list[str]:
    """Parse `Search _ inside SailStdpp.<module>` stdout, admitting empty modules and trailing About notices."""
    lines = stdout.splitlines()
    cleaned: list[str] = []
    footer_spellings: list[str] | None = None
    for line in lines:
        if not line.strip():
            continue
        if footer_spellings is not None:
            raise proofaudit.AuditError(f"nonterminal native Search output after notice: {line}")
        if cleaned and (notice := _ABOUT_FOOTER.fullmatch(line)) is not None:
            footer_spellings = cast(list[str], re.split(r", | and ", notice.group(1)))
            continue
        cleaned.append(line)
    symbols = proofaudit.inventory("\n".join(cleaned) + ("\n" if cleaned else ""), module)
    if footer_spellings is not None:
        listed = {symbol["name"] for symbol in symbols}
        if (not symbols or len(set(footer_spellings)) != len(footer_spellings)
                or not set(footer_spellings) <= listed):
            raise proofaudit.AuditError("native Search notice names duplicate or unlisted declarations")
    return [f"SailStdpp.{symbol['name']}" for symbol in symbols]


def _trimmed_nonblank(lines: list[str]) -> str:
    start = next((index for index, line in enumerate(lines) if line.strip()), len(lines))
    end = len(lines)
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


def parse_support_about(name: str, text: str) -> tuple[proofreading.About, bool, str]:
    """Parse `About` output for a support symbol, preserving alias and Global Opaque notes."""
    try:
        about = proofreading.parse_about(name, text)
    except proofreading.ReadingError:
        adjusted = _SYNTACTICALLY_EQUAL.sub(r"\1", text)
        opaque_transparent = bool(_OPAQUE_BUT_TRANSPARENT.search(adjusted))
        if opaque_transparent:
            adjusted = _OPAQUE_BUT_TRANSPARENT.sub(r"\1 is transparent", adjusted)
        if adjusted == text:
            raise
        parsed = proofreading.parse_about(name, adjusted)
        kept_text = _trimmed_nonblank(
            [line for line in text.splitlines() if not line.startswith(proofreading.LOCATION)],
        )
        about = proofreading.About(
            kind=parsed.kind, opacity=parsed.opacity,
            universes=parsed.universes, text=kept_text,
        )
        opacity = "opaque but may be made transparent" if opaque_transparent else parsed.opacity
        return about, parsed.printed, opacity
    return about, about.printed, about.opacity


def read_support_module(
    query: Callable[[str, str], str], module: str,
) -> dict[str, dict[str, str | None]]:
    """Read all top-level declarations of `SailStdpp.<module>`, returning `{}` when empty."""
    proofreading.check_module(module)
    full = f"SailStdpp.{module}"
    inv_mod = proofreading.query_module("Inventory", module)
    inv_out = query(
        inv_mod,
        f"Require {full}.\n{proofaudit.SETTINGS}"
        f"Print Table Search Blacklist.\nSearch _ inside {full}.\n",
    )
    names = parse_support_inventory(inv_out, module)
    if not names:
        return {}
    facts_mod = proofreading.query_module("Facts", module)
    facts_out = query(facts_mod, proofreading.facts_query(full, names))
    facts = proofreading.answers(
        facts_out, [f"{name}|{field}" for name in names for field in ("check", "about")],
    )
    parsed = {
        name: parse_support_about(
            name, proofreading.fresh_universes(facts[f"{name}|about"], facts_mod),
        )
        for name in names
    }
    printed = [name for name in names if parsed[name][1]]
    bodies: dict[str, str] = {}
    bodies_mod = proofreading.query_module("Bodies", module)
    if printed:
        bodies_out = query(bodies_mod, proofreading.bodies_query(full, printed))
        bodies = proofreading.answers(bodies_out, [f"{name}|print" for name in printed])
    reading: dict[str, dict[str, str | None]] = {}
    for name in names:
        about_obj, is_printed, opacity = parsed[name]
        check_str = proofreading.fresh_universes(facts[f"{name}|check"], facts_mod)
        print_str = (
            proofreading.fresh_universes(bodies[f"{name}|print"], bodies_mod)
            if is_printed else None
        )
        entry = cast(dict[str, str | None], proofreading.entry(check_str, about_obj, print_str))
        if opacity != about_obj.opacity:
            entry["opacity"] = opacity
        reading[name] = entry
    return reading


def check_support_source_diff(
    baseline_dir: Path, candidate_dir: Path, modules: list[str],
) -> dict[str, dict[str, object]]:
    """Verify only `PATCHED_SUPPORT_SOURCES` differ across the selected support `.v` files."""
    diff: dict[str, dict[str, object]] = {}
    for mod in modules:
        base_src = baseline_dir / f"{mod}.v"
        cand_src = candidate_dir / f"{mod}.v"
        if not base_src.is_file() or not cand_src.is_file():
            raise ValueError(f"missing support source for {mod}")
        base_sha = sha(base_src)
        cand_sha = sha(cand_src)
        diff[mod] = {
            "baseline_sha256": base_sha,
            "candidate_sha256": cand_sha,
            "differs": base_sha != cand_sha,
        }
    differing = {f"{mod}.v" for mod, info in diff.items() if info["differs"]}
    if differing != PATCHED_SUPPORT_SOURCES:
        raise ValueError(
            f"support source diff mismatch: expected {sorted(PATCHED_SUPPORT_SOURCES)}, "
            f"got {sorted(differing)}",
        )
    return diff


def compare_support_readings(
    modules: list[str],
    baseline_readings: dict[str, dict[str, dict[str, str | None]]],
    candidate_readings: dict[str, dict[str, dict[str, str | None]]],
    source_diff: dict[str, dict[str, object]],
    baseline_objects: dict[str, str],
    candidate_objects: dict[str, str],
) -> dict[str, object]:
    """Compare baseline vs candidate elaborated readings across every support module."""
    expected = set(modules)
    if (len(expected) != len(modules) or set(baseline_readings) != expected
            or set(candidate_readings) != expected or set(source_diff) != expected
            or set(baseline_objects) != expected or set(candidate_objects) != expected):
        raise ValueError("support readings do not cover the exact selected module set")
    base_empty = [mod for mod in modules if not baseline_readings[mod]]
    cand_empty = [mod for mod in modules if not candidate_readings[mod]]
    per_module: dict[str, dict[str, object]] = {}
    differing_reading_modules: list[str] = []
    for mod in modules:
        old = baseline_readings[mod]
        new = candidate_readings[mod]
        added = sorted(new.keys() - old.keys())
        removed = sorted(old.keys() - new.keys())
        changed = {
            name: [field for field in proofreading.FIELDS if old[name][field] != new[name][field]]
            for name in sorted(old.keys() & new.keys()) if old[name] != new[name]
        }
        if added or removed or changed:
            differing_reading_modules.append(mod)
        base_reading_sha = hashlib.sha256(
            (json.dumps(old, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        ).hexdigest()
        cand_reading_sha = hashlib.sha256(
            (json.dumps(new, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        ).hexdigest()
        src_info = source_diff[mod]
        per_module[mod] = {
            "baseline_source_sha256": src_info["baseline_sha256"],
            "candidate_source_sha256": src_info["candidate_sha256"],
            "source_identical": not bool(src_info["differs"]),
            "baseline_object_sha256": baseline_objects[mod],
            "candidate_object_sha256": candidate_objects[mod],
            "object_identical": baseline_objects[mod] == candidate_objects[mod],
            "baseline_declaration_count": len(old),
            "candidate_declaration_count": len(new),
            "empty_top_level": len(old) == 0 and len(new) == 0,
            "baseline_reading_sha256": base_reading_sha,
            "candidate_reading_sha256": cand_reading_sha,
            "added": added,
            "removed": removed,
            "changed": changed,
        }
    return {
        "modules_checked": len(modules),
        "patched_sources": sorted(PATCHED_SUPPORT_SOURCES),
        "empty_top_level_modules": {"baseline": base_empty, "candidate": cand_empty},
        "total_declarations": {
            "baseline": sum(len(baseline_readings[mod]) for mod in modules),
            "candidate": sum(len(candidate_readings[mod]) for mod in modules),
        },
        "differing_reading_modules": differing_reading_modules,
        "modules": per_module,
    }


def verify_support_comparison(report: dict[str, object]) -> None:
    """Refuse if empty modules disagree, unexpected sources differ, or any top-level declaration changed."""
    empty = cast(dict[str, list[str]], report["empty_top_level_modules"])
    if empty["baseline"] != empty["candidate"]:
        raise ValueError(
            f"empty top-level support modules disagree: "
            f"baseline={empty['baseline']} candidate={empty['candidate']}",
        )
    modules = cast(dict[str, dict[str, object]], report["modules"])
    differing_sources = {f"{mod}.v" for mod, info in modules.items() if not info["source_identical"]}
    if differing_sources != PATCHED_SUPPORT_SOURCES:
        raise ValueError(
            f"support source diff mismatch: expected {sorted(PATCHED_SUPPORT_SOURCES)}, "
            f"got {sorted(differing_sources)}",
        )
    differing = cast(list[str], report["differing_reading_modules"])
    if differing:
        raise ValueError(
            f"support elaborated top-level declarations differ in module(s): {differing}",
        )


def verify_frozen_support(
    frozen_manifest: Path,
    expected_manifest_sha: str,
    baseline_payload: bytes,
    candidate_payload: bytes,
    comparison: dict[str, object],
) -> None:
    """Verify fresh 29-module support readings and comparison against a retained frozen manifest."""
    require_sha(frozen_manifest, expected_manifest_sha)
    members = cast(
        dict[str, dict[str, object]],
        json.loads(frozen_manifest.read_bytes(), object_pairs_hook=unique_object)["files"],
    )
    if (hashlib.sha256(baseline_payload).hexdigest()
            != members["support-baseline.json.gz"]["sha256"]):
        raise ValueError("support baseline reading differs from frozen manifest")
    if (hashlib.sha256(candidate_payload).hexdigest()
            != members["support-candidate.json.gz"]["sha256"]):
        raise ValueError("support candidate reading differs from frozen manifest")
    frozen_cmp_info = members["support-comparison.json"]
    frozen_cmp_path = frozen_manifest.parent / cast(str, frozen_cmp_info["path"])
    require_sha(frozen_cmp_path, cast(str, frozen_cmp_info["sha256"]))
    frozen_cmp = cast(
        dict[str, object],
        json.loads(frozen_cmp_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object),
    )
    for key in ("modules_checked", "patched_sources", "empty_top_level_modules",
                "total_declarations", "differing_reading_modules"):
        if comparison[key] != frozen_cmp[key]:
            raise ValueError(f"support comparison {key} differs from frozen bundle")
    fresh_mods = cast(dict[str, dict[str, object]], comparison["modules"])
    frozen_mods = cast(dict[str, dict[str, object]], frozen_cmp["modules"])
    if set(fresh_mods) != set(frozen_mods):
        raise ValueError("support comparison module keys differ from frozen bundle")
    comparable_fields = (
        "baseline_source_sha256", "candidate_source_sha256", "source_identical",
        "baseline_declaration_count", "candidate_declaration_count", "empty_top_level",
        "baseline_reading_sha256", "candidate_reading_sha256", "added", "removed", "changed",
    )
    for mod in fresh_mods:
        for field in comparable_fields:
            if fresh_mods[mod][field] != frozen_mods[mod][field]:
                raise ValueError(
                    f"support comparison {mod}.{field} differs from frozen bundle",
                )


def authored_assumption_spec(module: str) -> tuple[str, str]:
    """Return `(search_target, preamble)` for an authored Q35p module, instantiating functors."""
    if module == "TagInterpreter":
        return (
            "TagPlaneInst",
            "Require bindings_types TagInterpreter.\n"
            "Module TagPlaneInst := TagInterpreter.TagPlane "
            "bindings_types.Arch bindings_types.Interface.\n",
        )
    if module == "TagConservativity":
        return (
            "OldOutcomesInst",
            "Require bindings_types TagConservativity.\n"
            "Module OldOutcomesInst := TagConservativity.OldOutcomes "
            "bindings_types.Arch bindings_types.Interface.\n",
        )
    return module, f"Require {module}.\n"


def authored_inventory_query(module: str) -> tuple[str, str]:
    """Build a `proofaudit.inventory_query` script for `module`, instantiating functor-only sources."""
    target, preamble = authored_assumption_spec(module)
    base = proofaudit.inventory_query(target)
    prefix = f"Require {target}.\n"
    if not base.startswith(prefix):
        raise ValueError(f"unexpected inventory_query prefix for {target}")
    return target, preamble + base[len(prefix):]


def authored_assumption_query(module: str, symbols: list[proofaudit.Symbol]) -> str:
    """Build a `proofaudit.assumption_query` script for `symbols` under `module`."""
    target, preamble = authored_assumption_spec(module)
    base = proofaudit.assumption_query(target, symbols)
    prefix = f"Require {target}.\n"
    if not base.startswith(prefix):
        raise ValueError(f"unexpected assumption_query prefix for {target}")
    return preamble + base[len(prefix):]


def audit_module_assumptions(
    module: str,
    query: Callable[[str, str], str],
) -> dict[str, object]:
    """Enumerate `module` declarations and require `Closed under the global context` on every one."""
    target, inv_script = authored_inventory_query(module)
    inv_stdout = query(f"AssumptionsInventory_{module}", inv_script)
    symbols = proofaudit.inventory(inv_stdout, target)
    if not symbols:
        raise ValueError(f"empty native inventory for authored module {module}")
    assump_script = authored_assumption_query(module, symbols)
    assump_stdout = query(f"AssumptionsCheck_{module}", assump_script)
    proofaudit.assumptions(assump_stdout, symbols)
    non_closed = {
        symbol["name"]: list(symbol["assumptions"])
        for symbol in symbols if symbol["assumptions"]
    }
    if non_closed:
        raise ValueError(
            f"authored module {module} has non-closed declaration(s): {non_closed}",
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


def audit_authored_assumptions(
    modules: tuple[str, ...],
    query: Callable[[str, str], str],
) -> dict[str, object]:
    """Audit native `Print Assumptions` across every module in `modules`."""
    per_module: dict[str, dict[str, object]] = {
        mod: audit_module_assumptions(mod, query) for mod in modules
    }
    total = sum(cast(int, per_module[mod]["declaration_count"]) for mod in modules)
    return {
        "schema": "verifiedos-tag-assumptions/1",
        "all_closed": True,
        "modules_audited": list(modules),
        "total_declarations": total,
        "modules": per_module,
    }


def parse_kernel_summary(stderr: str) -> tuple[list[str], list[str]]:
    """Parse `rocqchk -silent -o` summary via `proofaudit.kernel_context`, also returning indices."""
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


def verify_kernel_partition(
    name: str,
    argv: list[str],
    returncode: int,
    stdout: str,
    stderr: str,
    modules: list[str],
    expected_axioms: list[str],
    *,
    portable_flags: list[str],
    note: str | None = None,
) -> dict[str, object]:
    """Validate one recursive `rocqchk -silent -o` partition, refusing `-norec` or axiom mismatch."""
    if "-norec" in argv or "-norec" in portable_flags:
        raise ValueError(f"kernel partition {name} must not pass -norec")
    if "-silent" not in argv or "-o" not in argv:
        raise ValueError(f"kernel partition {name} requires -silent -o")
    if returncode != 0 or stdout.strip():
        diagnostic = (stderr.strip() or stdout.strip()) or "no diagnostic"
        raise ValueError(
            f"kernel partition {name} failed (exit {returncode}): {diagnostic}",
        )
    axioms, indices = parse_kernel_summary(stderr)
    if len(axioms) != len(set(axioms)):
        raise ValueError(f"kernel partition {name} reported duplicate axioms: {axioms}")
    actual_sorted = sorted(axioms)
    expected_sorted = sorted(expected_axioms)
    if actual_sorted != expected_sorted:
        raise ValueError(
            f"kernel partition {name} axioms mismatch: "
            f"expected {expected_sorted}, got {actual_sorted}",
        )
    entry: dict[str, object] = {
        "modules": list(modules),
        "argv": list(argv),
        "portable_flags": list(portable_flags),
        "norec_present": False,
        "exit_code": returncode,
        "expected_axioms": expected_sorted,
        "axioms": actual_sorted,
        "indices_not_mattering": indices,
    }
    if note is not None:
        entry["note"] = note
    return entry


def build_kernel_report(partitions: dict[str, dict[str, object]]) -> dict[str, object]:
    """Assemble the four-partition recursive `rocqchk -silent -o` kernel report."""
    expected_order = [
        "authored_and_emitted",
        "support_axiom_free",
        "support_values_lemmas_control",
        "support_real_control",
    ]
    if list(partitions) != expected_order:
        raise ValueError(f"unexpected kernel partition order: {list(partitions)}")
    return {
        "schema": "verifiedos-tag-kernel-check/1",
        "recursive": True,
        "norec_absent": True,
        "partition_order": expected_order,
        "partitions": partitions,
    }


def _verify_frozen_assumptions(
    fresh: dict[str, object],
    frozen_doc: dict[str, object],
) -> None:
    if fresh.get("all_closed") is not True:
        raise ValueError("fresh assumptions report is not closed")
    for key in ("schema", "all_closed", "modules_audited", "total_declarations"):
        if fresh.get(key) != frozen_doc.get(key):
            raise ValueError(f"assumptions {key} differs from frozen closure bundle")
    fresh_mods = cast(dict[str, dict[str, object]], fresh["modules"])
    frozen_mods = cast(dict[str, dict[str, object]], frozen_doc["modules"])
    if set(fresh_mods) != set(frozen_mods):
        raise ValueError("assumptions module keys differ from frozen closure bundle")
    for mod in fresh_mods:
        f_mod = fresh_mods[mod]
        r_mod = frozen_mods[mod]
        if (f_mod.get("all_closed") is not True or f_mod.get("non_closed") != []
                or cast(int, f_mod.get("declaration_count", 0)) <= 0):
            raise ValueError(f"fresh assumptions invalid for module {mod}")
        for field in (
            "module", "query_target", "instantiated_functor",
            "declaration_count", "closed_count", "all_closed", "non_closed", "symbols",
        ):
            if f_mod.get(field) != r_mod.get(field):
                raise ValueError(
                    f"assumptions {mod}.{field} differs from frozen closure bundle",
                )


def _verify_frozen_kernel_check(
    fresh: dict[str, object],
    frozen_doc: dict[str, object],
) -> None:
    if fresh.get("recursive") is not True or fresh.get("norec_absent") is not True:
        raise ValueError("fresh kernel-check report must be recursive without -norec")
    for key in ("schema", "recursive", "norec_absent", "partition_order"):
        if fresh.get(key) != frozen_doc.get(key):
            raise ValueError(f"kernel-check {key} differs from frozen closure bundle")
    fresh_parts = cast(dict[str, dict[str, object]], fresh["partitions"])
    frozen_parts = cast(dict[str, dict[str, object]], frozen_doc["partitions"])
    if set(fresh_parts) != set(frozen_parts):
        raise ValueError("kernel-check partition keys differ from frozen closure bundle")
    for part in fresh_parts:
        f_part = fresh_parts[part]
        r_part = frozen_parts[part]
        if (f_part.get("norec_present") is not False
                or "-norec" in cast(list[str], f_part.get("portable_flags", []))
                or "-norec" in cast(list[str], f_part.get("argv", []))
                or f_part.get("exit_code") != 0):
            raise ValueError(f"fresh kernel partition {part} violated recursive check invariants")
        for field in (
            "modules", "portable_flags", "norec_present", "exit_code",
            "expected_axioms", "axioms", "indices_not_mattering",
        ):
            if f_part.get(field) != r_part.get(field):
                raise ValueError(
                    f"kernel-check {part}.{field} differs from frozen closure bundle",
                )


def verify_frozen_closure(
    frozen_manifest: Path,
    expected_manifest_sha: str,
    assumptions_report: dict[str, object],
    kernel_report: dict[str, object],
) -> None:
    """Verify assumptions.json and kernel-check.json normalized invariants against a frozen manifest."""
    require_sha(frozen_manifest, expected_manifest_sha)
    members = cast(
        dict[str, dict[str, object]],
        json.loads(frozen_manifest.read_bytes(), object_pairs_hook=unique_object)["files"],
    )
    for member_name, fresh, verifier in (
        ("assumptions.json", assumptions_report, _verify_frozen_assumptions),
        ("kernel-check.json", kernel_report, _verify_frozen_kernel_check),
    ):
        if member_name not in members:
            raise ValueError(f"frozen closure manifest missing {member_name}")
        info = members[member_name]
        member_path = frozen_manifest.parent / cast(str, info["path"])
        require_sha(member_path, cast(str, info["sha256"]))
        frozen_doc = cast(
            dict[str, object],
            json.loads(member_path.read_text(encoding="utf-8"), object_pairs_hook=unique_object),
        )
        verifier(fresh, frozen_doc)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-archive", required=True, type=absolute)
    parser.add_argument("--stdpp", required=True, type=absolute)
    parser.add_argument("--plugin", required=True, type=absolute)
    parser.add_argument("--rocq-prefix", required=True, type=absolute)
    parser.add_argument("--sail-prefix", required=True, type=absolute)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    recipe_path = repo / "tools/sail-tag-outcomes/candidate.json"
    support_recipe = repo / "tools/opam/sail-support-qualification.json"
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    q = json.loads(support_recipe.read_text(encoding="utf-8"))
    frozen = recipe["frozen_v1_manifest"]
    frozen_manifest = repo / frozen["path"]
    require_sha(frozen_manifest, frozen["sha256"])
    members = json.loads(frozen_manifest.read_bytes(), object_pairs_hook=unique_object)["files"]
    frozen_support = recipe.get("frozen_support_manifest")
    if frozen_support is not None:
        require_sha(repo / frozen_support["path"], frozen_support["sha256"])
    frozen_closure = recipe.get("frozen_closure_manifest")
    if frozen_closure is not None:
        require_sha(repo / frozen_closure["path"], frozen_closure["sha256"])
    try:
        out = output_path(args.out, (repo, args.source_archive, args.stdpp, args.plugin,
                                    args.rocq_prefix, args.sail_prefix))
    except ValueError as error:
        parser.error(str(error))
    native = Path("/root/build")
    if not out.is_relative_to(native) or not any(p.name.startswith("lane-") for p in out.parents):
        parser.error("--out must be below the assigned /root/build/lane-* root")
    require_sha(args.source_archive, q["source"]["sha256"])
    plugin_digest = sha(args.plugin)
    expected_outputs = None
    expected_stdpp = None
    solver = None
    if plugin_digest == recipe["syntax_plugin_sha256"]:
        plugin_inputs = {args.plugin: plugin_digest}
    else:
        z3 = shutil.which("z3", path=str(args.sail_prefix / "bin") + os.pathsep + os.environ["PATH"])
        if z3 is None:
            parser.error("the retained plugin population requires the recorded z3 on PATH")
        solver = Path(z3).resolve(strict=True)
        plugin_inputs, expected_outputs = retained_emission_inputs(
            repo / recipe["retained_replay_evidence"], args.plugin,
            args.sail_prefix / "bin/sail", solver,
        )
        expected_stdpp = retained_stdpp(repo / recipe["retained_library_evidence"])
    if out.is_relative_to(args.stdpp):
        parser.error("output may not be inside the dependency input")
    if any(p.is_symlink() and p.is_dir() for p in args.stdpp.rglob("*")):
        parser.error("dependency input may not contain directory symlinks")
    out.mkdir(parents=True)
    commands = []
    switches = [args.rocq_prefix, args.sail_prefix]
    solver_digest = sha(solver) if solver is not None else None
    inputs = {
        "replay_driver_sha256": sha(Path(__file__)),
        "reading_sources_sha256": {
            name: sha(repo / name) for name in python_dependencies.sources(
                repo, ("tools/vos/proofaudit.py", "tools/vos/proofreading.py"))
        },
        "candidate_recipe_sha256": sha(recipe_path),
        "support_recipe_sha256": sha(support_recipe),
        "frozen_v1_manifest_sha256": frozen["sha256"],
        "frozen_support_manifest_sha256": (
            frozen_support["sha256"] if frozen_support is not None else None
        ),
        "frozen_closure_manifest_sha256": (
            frozen_closure["sha256"] if frozen_closure is not None else None
        ),
        "source_archive_sha256": q["source"]["sha256"],
        "rocq_sha256": sha(args.rocq_prefix / "bin/rocq"),
        "rocqchk_sha256": sha(args.rocq_prefix / "bin/rocqchk"),
        "sail_sha256": sha(args.sail_prefix / "bin/sail"),
        "plugins_sha256": {path.name: digest for path, digest in plugin_inputs.items()},
        "z3_sha256": solver_digest,
    }

    def inventory() -> dict[str, dict[str, str]]:
        return {str(prefix): {str(p.relative_to(prefix)): sha(p)
                for tree in [prefix / "bin", prefix / "lib"]
                for p in sorted(tree.rglob("*")) if p.is_file()}
                for prefix in switches}

    before = inventory()
    (out / "installed-before.json").write_text(json.dumps(before, indent=2) + "\n")

    def run(label: str, argv: list[str | Path], env: dict[str, str] | None = None,
            *, cwd: Path = out) -> subprocess.CompletedProcess[str]:
        started = time.monotonic()
        result = subprocess.run(list(map(str, argv)), cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=180, check=False)
        log = out / (label + ".log")
        log.write_text(result.stdout + result.stderr)
        commands.append({"label": label, "argv": list(map(str, argv)), "cwd": str(cwd),
                         "exit": result.returncode, "seconds": time.monotonic() - started,
                         "log": log.name, "sha256": sha(log)})
        if result.returncode:
            raise RuntimeError(f"{label} refused; see {log}")
        return result

    try:
        with tarfile.open(args.source_archive) as archive:
            archive.extractall(out / "source", filter="data")
        source = out / "source/coq-sail-0.20.3"
        if sha(source / "LICENSE") != q["source_license_sha256"]:
            raise RuntimeError("source license identity mismatch")
        for index, entry in enumerate(q["patches"]):
            patch = repo / entry["path"]
            if sha(patch) != entry["sha256"]:
                raise RuntimeError("base support patch digest mismatch")
            run(f"base-patch-{index}", ["patch", "-p1", "-d", source, "-i", patch])
        patch = repo / recipe["patch"]["path"]
        if sha(patch) != recipe["patch"]["sha256"]:
            raise RuntimeError("semantic patch digest mismatch")
        shutil.copytree(args.stdpp, out / "stdpp", symlinks=False)
        stdpp = tree_sha(out / "stdpp")
        if expected_stdpp is not None and stdpp != expected_stdpp:
            raise RuntimeError("private stdpp files do not match the retained library identities")
        (out / "inputs.json").write_text(json.dumps({**inputs, "stdpp_sha256": stdpp}, indent=2) + "\n")
        for mode in ["baseline", "candidate"]:
            lane = out / mode
            lane.mkdir()
            for item in (source / "src-stdpp").glob("*.v"):
                shutil.copy2(item, lane / item.name)
        run("semantic-patch", ["patch", "-p2", "-d", out / "candidate", "-i", patch])
        flags = ["-q", "-boot", "-R", args.rocq_prefix / "lib/coq/theories", "Corelib",
                 "-Q", args.rocq_prefix / "lib/coq/user-contrib/Stdlib", "Stdlib",
                 "-Q", out / "stdpp", "stdpp"]
        for mode in ["baseline", "candidate"]:
            lane = out / mode
            maps = [*flags, "-R", lane, "SailStdpp"]
            selected = [lane / (name + ".v") for name in q["support_modules"]]
            result = run(mode + "-deps", [args.rocq_prefix / "bin/rocq", "dep", "-sort", *maps, *selected])
            order = [Path(p) for p in result.stdout.split() if Path(p) in selected]
            if len(order) != len(selected) or set(order) != set(selected):
                raise RuntimeError("dependency sort did not enumerate the exact selected closure")
            for item in order:
                if item.resolve().parent != lane:
                    raise RuntimeError("selected source escaped owned lane")
                result = run(mode + "-" + item.stem, [args.rocq_prefix / "bin/rocq", "c", *maps,
                             *q["strict_flags"][1:], item])
                if result.stdout or result.stderr:
                    raise RuntimeError("strict selected compile emitted a diagnostic")
        support_modules = cast(list[str], q["support_modules"])
        source_diff = check_support_source_diff(
            out / "baseline", out / "candidate", support_modules,
        )
        support_readings: dict[str, dict[str, dict[str, dict[str, str | None]]]] = {}
        support_objects: dict[str, dict[str, str]] = {}
        for mode in ["baseline", "candidate"]:
            lane = out / mode
            query_stage = out / f"support-queries-{mode}"
            query_stage.mkdir()
            query_flags = [
                *flags, "-R", lane, "SailStdpp", "-R", query_stage, "",
                *q["strict_flags"][1:],
            ]

            def support_query(
                name: str, content: str,
                *, _mode: str = mode, _stage: Path = query_stage,
                _flags: list[str | Path] = query_flags,
            ) -> str:
                qsrc = _stage / f"{name}.v"
                qsrc.write_text(content, encoding="utf-8", newline="")
                res = run(
                    f"{_mode}-support-{name}",
                    [args.rocq_prefix / "bin/rocq", "c", *_flags, qsrc],
                    cwd=_stage,
                )
                if res.stderr:
                    raise RuntimeError(f"{_mode} support {name} query emitted a diagnostic")
                return res.stdout

            support_readings[mode] = {
                mod: read_support_module(support_query, mod) for mod in support_modules
            }
            support_objects[mode] = {mod: sha(lane / f"{mod}.vo") for mod in support_modules}
        baseline_payload = (
            json.dumps(support_readings["baseline"], sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        candidate_payload = (
            json.dumps(support_readings["candidate"], sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        (out / "support-baseline.json.gz").write_bytes(gzip.compress(baseline_payload, mtime=0))
        (out / "support-candidate.json.gz").write_bytes(gzip.compress(candidate_payload, mtime=0))
        support_comparison = compare_support_readings(
            support_modules,
            support_readings["baseline"],
            support_readings["candidate"],
            source_diff,
            support_objects["baseline"],
            support_objects["candidate"],
        )
        (out / "support-comparison.json").write_text(
            json.dumps(support_comparison, sort_keys=True, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )
        verify_support_comparison(support_comparison)
        if frozen_support is not None:
            verify_frozen_support(
                repo / frozen_support["path"], frozen_support["sha256"],
                baseline_payload, candidate_payload, support_comparison,
            )
        plugins = out / "plugins"
        plugins.mkdir()
        for plugin_input, digest in plugin_inputs.items():
            name = "sail_plugin_coq.cmxs" if plugin_input == args.plugin else plugin_input.name
            staged = plugins / name
            shutil.copy2(plugin_input, staged)
            require_sha(staged, digest)
        reproducer = repo / recipe["reproducer"]
        require_sha(reproducer, recipe["reproducer_sha256"])
        env = os.environ.copy()
        env["SAIL_PLUGIN_DIR"] = str(plugins)
        env["PATH"] = str(args.sail_prefix / "bin") + os.pathsep + env["PATH"]
        outputs = []
        for name in ["emitted", "repeat"]:
            lane = out / name
            lane.mkdir()
            # Sail includes this input name verbatim in the emitted refusals.
            shutil.copy2(reproducer, lane / "bindings.sail")
            run(name + "-emit", [args.sail_prefix / "bin/sail", "--rocq", "-D", "CONCURRENCY_INTERFACE",
                "--rocq-lib-style", "stdpp", "--rocq-alt-modules",
                "SailStdpp.Base SailStdpp.ConcurrencyInterfaceTypes SailStdpp.ConcurrencyInterface SailStdpp.ConcurrencyInterfaceBuiltins",
                "--rocq-output-dir", lane, "-o", "bindings", "bindings.sail"], env, cwd=lane)
            outputs.append({p.name: sha(p) for p in lane.glob("bindings*.v")})
        if outputs[0] != outputs[1] or len(outputs[0]) != 2:
            raise RuntimeError("repeat emission changed or omitted an output")
        if expected_outputs is not None and outputs[0] != expected_outputs:
            raise RuntimeError("repeat emission does not match the retained output identities")
        for name in AUTHORED_MODULES:
            proof_source = repo / "tools/sail-tag-outcomes" / (name + ".v")
            shutil.copy2(proof_source, out / "emitted" / proof_source.name)

        def compile_and_read(mode: str, stage: Path, modules: tuple[str, ...], label: str) -> None:
            compiler = [args.rocq_prefix / "bin/rocq", "c", *flags, "-R", out / mode, "SailStdpp",
                        "-R", stage, "", *q["strict_flags"][1:]]
            for name in modules:
                result = run(f"{label}-{name}", [*compiler, stage / (name + ".v")], cwd=stage)
                if result.stdout or result.stderr:
                    raise RuntimeError("strict probe compile emitted a diagnostic")

            def query(name: str, content: str) -> str:
                source = stage / (name + ".v")
                source.write_text(content, encoding="utf-8")
                result = run(f"{mode}-v1-{name}", [*compiler, source], cwd=stage)
                if result.stderr:
                    raise RuntimeError(f"{mode} V1 {name} query emitted a diagnostic")
                return result.stdout

            match_v1_reading(query, out / f"v1-{mode}.json", members[f"{mode}.json.gz"]["sha256"])

        compile_and_read("baseline", out / "repeat", ("bindings_types",), "strict-baseline")
        compile_and_read("candidate", out / "emitted", ("bindings_types", "bindings", *AUTHORED_MODULES), "strict")

        assump_stage = out / "assumptions-queries"
        assump_stage.mkdir()
        assump_compiler = [
            args.rocq_prefix / "bin/rocq", "c", *flags,
            "-R", out / "candidate", "SailStdpp",
            "-R", out / "emitted", "",
            "-R", assump_stage, "",
            *q["strict_flags"][1:],
        ]

        def assumption_query(name: str, content: str) -> str:
            qsrc = assump_stage / f"{name}.v"
            qsrc.write_text(content, encoding="utf-8", newline="")
            res = run(f"assumptions-{name}", [*assump_compiler, qsrc], cwd=assump_stage)
            if res.stderr:
                raise RuntimeError(f"assumption query {name} emitted a diagnostic")
            return res.stdout

        assumptions_report = audit_authored_assumptions(AUTHORED_MODULES, assumption_query)
        (out / "assumptions.json").write_text(
            json.dumps(assumptions_report, sort_keys=True, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )

        kernel_base_argv = [
            str(args.rocq_prefix / "bin/rocqchk"), "-silent", "-o",
            "-boot",
            "-R", str(args.rocq_prefix / "lib/coq/theories"), "Corelib",
            "-Q", str(args.rocq_prefix / "lib/coq/user-contrib/Stdlib"), "Stdlib",
            "-Q", str(out / "stdpp"), "stdpp",
            "-R", str(out / "candidate"), "SailStdpp",
            "-R", str(out / "emitted"), "",
        ]
        portable_kernel_flags = [
            "-silent", "-o",
            "-boot",
            "-R", "<rocq_prefix>/lib/coq/theories", "Corelib",
            "-Q", "<rocq_prefix>/lib/coq/user-contrib/Stdlib", "Stdlib",
            "-Q", "<out>/stdpp", "stdpp",
            "-R", "<out>/candidate", "SailStdpp",
            "-R", "<out>/emitted", "",
        ]
        partition_specs: list[tuple[str, list[str], list[str], str | None]] = [
            (
                "authored_and_emitted",
                ["bindings_types", "bindings", *AUTHORED_MODULES],
                [],
                None,
            ),
            (
                "support_axiom_free",
                [f"SailStdpp.{mod}" for mod in support_modules if mod not in ("Real", "Values_lemmas")],
                [],
                None,
            ),
            (
                "support_values_lemmas_control",
                ["SailStdpp.Values_lemmas"],
                list(VALUES_LEMMAS_AXIOMS),
                VALUES_LEMMAS_NOTE,
            ),
            (
                "support_real_control",
                ["SailStdpp.Real"],
                list(cast(list[str], q["support_axioms"])),
                None,
            ),
        ]
        kernel_partitions: dict[str, dict[str, object]] = {}
        for part_name, part_modules, expected_axioms, part_note in partition_specs:
            part_argv: list[str | Path] = [*kernel_base_argv, *part_modules]
            res = run(f"kernel-{part_name}", part_argv, cwd=out)
            kernel_partitions[part_name] = verify_kernel_partition(
                part_name,
                list(map(str, part_argv)),
                res.returncode,
                res.stdout,
                res.stderr,
                part_modules,
                expected_axioms,
                portable_flags=portable_kernel_flags,
                note=part_note,
            )
        kernel_report = build_kernel_report(kernel_partitions)
        (out / "kernel-check.json").write_text(
            json.dumps(kernel_report, sort_keys=True, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )
        if frozen_closure is not None:
            verify_frozen_closure(
                repo / frozen_closure["path"], frozen_closure["sha256"],
                assumptions_report, kernel_report,
            )
        (out / "repeat-output-identities.json").write_text(json.dumps(outputs, indent=2) + "\n")
    finally:
        after = inventory()
        changes = {prefix: sorted(k for k in before[prefix].keys() | after[prefix].keys()
                                 if before[prefix].get(k) != after[prefix].get(k)) for prefix in before}
        (out / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        (out / "installed-after.json").write_text(json.dumps(after, indent=2) + "\n")
        (out / "installed-comparison.json").write_text(json.dumps(changes, indent=2) + "\n")
        if any(changes.values()):
            raise RuntimeError("installed paths changed; report them and do not self-restore")
        if solver is not None and sha(solver) != solver_digest:
            raise RuntimeError("recorded z3 changed during replay")
    print(f"PASS isolated tag candidate: {out}; production acceptance remains open")


if __name__ == "__main__":
    main()
