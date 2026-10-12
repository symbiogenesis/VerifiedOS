#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reproduce this historical snapshot's summary offline; never qualify a compiler."""

import argparse
import gzip
import hashlib
import io
import json
import math
import re
import stat
from pathlib import Path, PurePosixPath
from typing import cast

Record = dict[str, object]
LIMIT = 32 * 1024 * 1024
LABELS = ("standard-source", "standard-import", "vm-source", "vm-import")
STAGES = ("export", "configure", "clean", "depend", "proof", "extraction", "ccomp")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def record(value: object) -> Record:
    require(isinstance(value, dict), "expected JSON object")
    return cast(Record, value)


def array(value: object) -> list[object]:
    require(isinstance(value, list), "expected JSON array")
    return cast(list[object], value)


def string(value: object) -> str:
    require(isinstance(value, str), "expected string")
    return cast(str, value)


def unique_object(pairs: list[tuple[str, object]]) -> Record:
    result: Record = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> object:
    raise ValueError(f"nonfinite JSON number: {value}")


def finite_float(value: str) -> float:
    number = float(value)
    require(math.isfinite(number), "nonfinite JSON number")
    return number


def load(raw: bytes) -> Record:
    return record(json.loads(raw, object_pairs_hook=unique_object,
                             parse_constant=reject_constant, parse_float=finite_float))


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: Record) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def read_relative(root: Path, name: str) -> bytes:
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and ".." not in relative.parts
            and "\\" not in name and ":" not in name, "unsafe bundle path")
    path = root.joinpath(*relative.parts)
    require(path.resolve().is_relative_to(root.resolve()), "escaping bundle path")
    require(all(not root.joinpath(*relative.parts[:i]).is_symlink()
                for i in range(1, len(relative.parts) + 1)), "symlink in bundle path")
    attributes = path.stat()
    require(stat.S_ISREG(attributes.st_mode), "payload is not a regular file")
    require(attributes.st_size <= LIMIT, "oversized payload")
    return path.read_bytes()


def progress(raw: bytes) -> Record:
    # Count only complete emitted lines; retain a partial tail without interpreting it.
    complete, _, tail = raw.rpartition(b"\n")
    lines = complete.decode("utf-8").splitlines()
    markers = [i for i, line in enumerate(lines) if line == "Ordered list:"]
    require(len(markers) == 1, "missing or repeated ordered list")
    ordered: list[str] = []
    index = markers[0] + 1
    while index < len(lines) and re.fullmatch(r"  [A-Za-z_][A-Za-z0-9_.]*", lines[index]):
        ordered.append(lines[index][2:])
        index += 1
    headers = [line.removeprefix("Checking library: ")
               for line in lines if line.startswith("Checking library: ")]
    require(bool(ordered) and len(ordered) == len(set(ordered)), "invalid library order")
    require(bool(headers) and headers == ordered[:len(headers)], "headers are not an ordered prefix")
    require(not any(line.startswith("Admitting library: ") for line in lines), "admitted library")
    return {"ordered_libraries": len(ordered), "entered_libraries": len(headers),
            "advanced_past_library_lower_bound": len(headers) - 1,
            "library_count_fraction": (len(headers) - 1) / len(ordered),
            "current_entered_library": headers[-1], "headers_exact_prefix": True,
            "last_complete_emitted_line": lines[-1],
            "complete_line_cutoff_bytes": len(complete) + 1,
            "partial_tail_bytes": len(tail), "partial_tail_sha256": digest(tail),
            "runtime_percentage_or_eta": None}


def derive(root: Path) -> Record:
    manifest = load(read_relative(root, "manifest.json"))
    require(manifest["schema"] == "verifiedos-q39-pending-audit-bundle/1", "unsupported bundle")
    payloads: dict[str, bytes] = {}
    for key, value in record(manifest["files"]).items():
        item = record(value)
        raw = read_relative(root, string(item["path"]))
        require(len(raw) == item["stored_bytes"] and digest(raw) == item["stored_sha256"],
                f"stored digest/size mismatch: {key}")
        if item["encoding"] == "gzip":
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
                raw = stream.read(LIMIT + 1)
            require(len(raw) <= LIMIT, "oversized decompressed payload")
        else:
            require(item["encoding"] == "identity", "unsupported encoding")
        require(len(raw) == item["bytes"] and digest(raw) == item["sha256"],
                f"decoded digest/size mismatch: {key}")
        payloads[key] = raw
    capture = load(payloads["capture"])
    stages = load(payloads["stage-capture"])
    require(set(record(capture["results"])) == set(LABELS), "wrong audit population")
    runs: Record = {}
    for label in LABELS:
        original = record(record(capture["results"])[label])
        receipt = load(payloads[f"{label}/build-result.json"])
        seal = load(payloads[f"{label}/compile-seal.json"])
        population = record(seal["population"])
        require(population["compiler/build-result.json"] == digest(payloads[f"{label}/build-result.json"]),
                "receipt is not bound by captured seal")
        require(population["compiler/build-inputs.json"] == digest(payloads[f"{label}/build-inputs.json"]),
                "source inventory is not bound by captured seal")
        receipt_observation = record(record(capture["snapshots"])[f"{label}/build-result.json"])
        require(seal["original"] == string(receipt_observation["source"]).removesuffix("/compiler/build-result.json"),
                "seal native root does not match receipt observation")
        require(receipt["revision"] == original["revision"], "source revision mismatch")
        require(receipt["passed"] is False and receipt["kernel"] is None
                and original["fresh_kernel_receipt_exists"] is False, "snapshot is not pending")
        gates = [record(gate) for gate in array(receipt["gates"])]
        require(tuple(gate["name"] for gate in gates) == STAGES, "wrong stage population/order")
        seconds = 0.0
        for gate in gates:
            require(type(gate["exit"]) is int and gate["exit"] == 0, "unsuccessful stage")
            duration = gate["seconds"]
            require(type(duration) in (int, float), "invalid stage duration")
            duration = cast(float, duration)
            require(math.isfinite(duration) and duration >= 0, "invalid stage duration")
            seconds += duration
            stage = record(record(stages["files"])[f"{label}/{gate['name']}"])
            require(stage["sha256"] == gate["log_sha256"]
                    and stage["matches_original_stage_log_digest"] is True
                    and stage["metadata_stable_during_capture"] is True,
                    "stage log catalog mismatch")
        process = record(record(capture["processes"])[str(original["checker_pid"])])
        require(process["exists"] is True and process["identity_stable_during_read"] is True,
                "checker identity not observed stable")
        argv = [string(token) for token in array(process["argv"])]
        require(not any(token in ("-admit", "-norec", "-silent") for token in argv),
                "unsupported checker scope")
        require(digest(b"\0".join(token.encode() for token in argv) + b"\0")
                == process["argv_bytes_sha256"], "checker argv framing mismatch")
        options = ["-o", "-bytecode-compiler", "yes"] if label.startswith("vm-") else ["-o"]
        require(argv[1:1 + len(options)] == options, "checker profile mismatch")
        index = 1 + len(options)
        include_tokens: list[str] = []
        while index < len(argv) and argv[index] == "-R":
            require(index + 2 < len(argv), "truncated checker include")
            include_tokens.extend(argv[index:index + 3])
            index += 3
        roots = argv[index:]
        require(bool(roots) and len(roots) == len(set(roots))
                and all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", name) for name in roots),
                "invalid explicit Make roots")
        identity = record(record(stages["compact_original_identities"])[label])
        require(len(roots) == identity["root_count"]
                and digest(json.dumps(roots, separators=(",", ":")).encode()) == identity["root_argv_sha256"],
                "checker roots differ from captured original roster")
        for population_name in ("original-make", "copied-make"):
            make_lines = payloads[f"{label}/{population_name}/make.log"].decode().splitlines()
            require(len(make_lines) == 2 and make_lines[0].split() == include_tokens
                    and make_lines[1].split() == [name.rsplit(".", 1)[-1] + ".v" for name in roots],
                    "checker includes/roots differ from captured Make output")
        observations = record(capture["snapshots"])
        for name in ("build-result.json", "compile-seal.json", "kernel-environment.log"):
            item = record(observations[f"{label}/{name}"])
            require(item["metadata_stable_during_capture"] is True
                    and item["snapshot_digest_verified"] is True, "unstable capture")
            require(item["sha256"] == digest(payloads[f"{label}/{name}"]), "capture digest mismatch")
        counts = progress(payloads[f"{label}/kernel-environment.log"])
        require(counts["ordered_libraries"] == original["ordered_libraries"]
                and counts["advanced_past_library_lower_bound"] == original["fully_advanced_past_libraries"],
                "original count mismatch")
        runs[label] = {"source_revision": receipt["revision"],
                       "compiler_sha256": receipt["compiler_sha256"],
                       "successful_stages": list(STAGES), "compilation_seconds": seconds,
                       "seal_schema": seal["schema"], "seal_origin": seal["origin"],
                       "seal_native_root": seal["original"], "lock_sha256": seal["lock_sha256"],
                       "original_helpers": seal["helpers"],
                       "driver_pid": original["driver_pid"], "checker_pid": original["checker_pid"],
                       "checker_argv_sha256": process["argv_bytes_sha256"],
                       "kernel_profile": "vm" if label.startswith("vm-") else "standard",
                       "explicit_make_roots": len(roots), "include_tokens": len(include_tokens),
                       "checker_state_at_capture": process["state"], "progress": counts,
                       "complete_kernel_verdict": "pending",
                       "whole_environment_classification": "pending",
                       "final_input_stability": "pending"}
    return {"schema": "verifiedos-q39-pending-audit-summary/1",
            "capture_started_at": capture["started_utc"], "capture_completed_at": capture["completed_utc"],
            "capture_is_globally_atomic": False, "runs": runs,
            "scope": "Offline captured-byte consistency and library traversal; no native input revalidation.",
            "complete_kernel_acceptance": False, "checker_resume_checkpoint": False,
            "complete_default_reuse_basis": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-summary", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    try:
        summary = encoded(derive(root))
        if args.write_summary:
            (root / "summary.json").write_bytes(summary)
        else:
            require(read_relative(root, "summary.json") == summary, "derived summary differs")
    except (OSError, ValueError, TypeError, KeyError, EOFError, OverflowError) as error:
        print(f"REFUSED: {error}")
        return 1
    print("Captured bytes and derived summary agree; all four kernel verdicts remain pending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
