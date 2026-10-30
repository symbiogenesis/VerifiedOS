# SPDX-License-Identifier: Apache-2.0
"""Compare complete retained census replays on GitHub Actions, without native generation.

Missing native control evidence is recorded explicitly. A support-only diagnostic
never becomes complete performance acceptance or Q35q qualification.
"""

import argparse
import gc
import gzip
import hashlib
import json
import os
import platform
import re
import runpy
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

_CONTROLS = ["CensusControls", "SailStdpp.TypeCasts", "SailStdpp.State_monad"]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate native JSON key: " + key)
        result[key] = value
    return result


def relative(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("retained input path escapes its owner")
    return path


def prepare_dataset(root: Path, specification: dict[str, str], roots: list[str], scratch: Path) -> dict[str, Any]:
    """Authenticate retained bytes and expand the raw file without loading its graph."""
    if set(specification) != {"manifest", "raw", "provider", "readings"}:
        raise ValueError("unexpected census input descriptor members")
    manifest_path = relative(root, specification["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    hashes: dict[str, str] = {specification["manifest"]: digest(manifest_path)}

    def row(name: str) -> tuple[Path, dict[str, Any]]:
        record = manifest["files"][name]
        path = relative(manifest_path.parent, record["path"])
        encoding = record["encoding"]
        if encoding not in {"identity", "gzip"}:
            raise ValueError("unsupported retained input encoding")
        expected = record["stored_sha256"] if encoding == "gzip" else record["sha256"]
        expected_bytes = record["stored_bytes"] if encoding == "gzip" else record["bytes"]
        if path.stat().st_size != expected_bytes or digest(path) != expected:
            raise ValueError("retained input identity differs: " + name)
        hashes[path.relative_to(root).as_posix()] = expected
        return path, record

    def text(name: str) -> str:
        path, record = row(name)
        if record["encoding"] != "identity":
            raise ValueError("text provenance must retain its original identity encoding")
        return path.read_text(encoding="utf-8")

    source, record = row(specification["raw"])
    raw = scratch / "native-census.json"
    native_hash = hashlib.blake2b(digest_size=32)
    with (gzip.open(source, "rb") if record["encoding"] == "gzip" else source.open("rb")) as stream, raw.open("xb") as output:
        while block := stream.read(1024 * 1024):
            native_hash.update(block)
            output.write(block)
    if raw.stat().st_size != record["bytes"] or digest(raw) != record["sha256"]:
        raise ValueError("complete retained raw input differs after expansion")
    provider = specification["provider"]
    provenance = json.loads(text(provider + "/receipt.json"))
    # The provider's receipt and exact envelope remain provenance, never a new
    # claim that the old qualification or a current native/kernel run passed.
    envelope = json.loads(text(provider + "/native-query.stdout.log"), object_pairs_hook=unique)
    if (set(envelope) != {"schema", "census_schema", "path", "bytes", "blake2b_256"}
            or envelope["schema"] != "verifiedos-native-census-output/1"
            or envelope["census_schema"] != "verifiedos-sail-support-census/1"
            or envelope["bytes"] != record["bytes"] or envelope["blake2b_256"] != native_hash.hexdigest()
            or envelope != provenance["native_output_validation"]["envelope"]
            or any(type(provenance.get(key)) is not int or provenance[key] != 0 for key in ("exit", "native_exit"))
            or provenance.get("query_completed") is not True or provenance.get("metadata_validated") is not True
            or text(provider + "/native-query.stderr.log")):
        raise ValueError("native retained envelope or diagnostics differ")
    if provenance.get("search_targets") != roots:
        raise ValueError("native Search population differs from the complete requested roots")
    searches: dict[str, str] = {}
    for index, target in enumerate(roots):
        prefix = provider + f"/native-search-{index:02d}"
        if text(prefix + ".stderr.log"):
            raise ValueError("retained Search has diagnostics")
        searches[target] = text(prefix + ".stdout.log")
        text(provider + f"/Search{index:02d}.v")
    readings: dict[str, str] = {}
    directory = specification["readings"]
    targets = json.loads(text(directory + "/reading-targets.json"))
    reading_receipt = json.loads(text(directory + "/receipt.json"))
    commands = reading_receipt["commands"]
    if len(commands) != len(targets):
        raise ValueError("retained reading command population differs")
    for index, (kind, target) in enumerate(targets):
        prefix = directory + f"/Reading{index:03d}"
        command = commands[index]
        text(prefix + ".v")
        if (command["kind"] != kind or command["target"] != target or command["exit"] != 0
                or command["source_sha256_after"] != manifest["files"][prefix + ".v"]["sha256"]
                or text(prefix + ".stderr.log")):
            raise ValueError("retained native reading provenance differs")
        key = kind + ":" + target
        if key in readings:
            raise ValueError("duplicate retained reading target")
        readings[key] = text(prefix + ".stdout.log")
    return {"raw": str(raw), "raw_sha256": record["sha256"], "raw_bytes": record["bytes"],
            "roots": roots, "searches": searches, "readings": readings, "input_hashes": hashes}


def peak_rss() -> int | None:
    if sys.platform != "linux":
        return None
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def value_digest(value: object) -> str:
    """Hash complete decisions incrementally instead of allocating their JSON text."""
    result = hashlib.sha256()
    for fragment in json.JSONEncoder(ensure_ascii=False, separators=(",", ":")).iterencode(value):
        result.update(fragment.encode("utf-8"))
    return result.hexdigest()


def worker(tools: Path, prepared: Path, output: Path) -> int:
    started = time.perf_counter()
    write(output, {"status": "running", "phase": "load-tools", "peak_rss_kib": peak_rss()})
    sys.path.insert(0, str(tools))
    module = tools / "rocq-census/census.py"
    adapter = runpy.run_path(str(module))
    namespace = adapter["census"].__globals__
    schema = namespace["validate_schema"]
    replay = namespace["census"]
    inputs = json.loads(prepared.read_text(encoding="utf-8"))
    report: dict[str, Any] = {"status": "running", "phase": "start", "units": [], "decisions": {},
                              "prepared_sha256": digest(prepared), "peak_rss_kib": peak_rss(), "workers": 1}

    def checkpoint(phase: str) -> None:
        report.update(phase=phase, wall_seconds=time.perf_counter() - started, peak_rss_kib=peak_rss())
        write(output, report)
        print(phase, flush=True)

    def timed_schema(*args: Any, **kwargs: Any) -> Any:
        begin = time.perf_counter()
        try:
            return schema(*args, **kwargs)
        finally:
            report["units"].append({"kind": "schema", "seconds": time.perf_counter() - begin})

    def timed_census(*args: Any, **kwargs: Any) -> Any:
        checkpoint("census-" + str(sum(unit["kind"] == "census" for unit in report["units"]) + 1))
        begin = time.perf_counter()
        try:
            return replay(*args, **kwargs)
        finally:
            report["units"].append({"kind": "census", "seconds": time.perf_counter() - begin})
            checkpoint("census-completed")

    namespace.update(validate_schema=timed_schema, census=timed_census)
    try:
        for name in ("support", "controls"):
            dataset = inputs.get(name)
            if dataset is None:
                continue
            checkpoint(name + "-parse")
            raw = Path(dataset["raw"])
            if digest(raw) != dataset["raw_sha256"]:
                raise ValueError("raw evidence changed before replay")
            begin = time.perf_counter()
            with raw.open(encoding="utf-8") as stream:
                metadata = json.load(stream, object_pairs_hook=unique)
            report["units"].append({"kind": "parse", "dataset": name, "seconds": time.perf_counter() - begin})
            if name == "support":
                result = timed_census(metadata, dataset["searches"], dataset["readings"], expected_modules=dataset["roots"])
            else:
                result = adapter["qualify_controls"](metadata, dataset["searches"], dataset["readings"])
                if len(result["refusals"]) != 12 or len(result["positive"]) != 8:
                    raise ValueError("incomplete independent native control population")
            report["decisions"][name] = value_digest(result)
            del result, metadata
            gc.collect()
            if digest(raw) != dataset["raw_sha256"]:
                raise ValueError("raw evidence changed during replay")
            checkpoint(name + "-finished")
        if digest(prepared) != report["prepared_sha256"]:
            raise ValueError("prepared inputs changed during replay")
        expected_calls = 14 if inputs.get("controls") else 1
        if any(sum(unit["kind"] == kind for unit in report["units"]) != expected_calls for kind in ("census", "schema")):
            raise ValueError("each complete independent census must retain its full schema validation")
        report["status"] = "complete" if inputs.get("controls") else "support-only-diagnostic"
    except BaseException as error:
        report.update(status="refused", refusal={"type": type(error).__name__, "message": str(error)})
        checkpoint("refused")
        return 1
    checkpoint("finished")
    return 0


def compare(root: Path, base: str, descriptor: Path, output: Path, timeout: int) -> int:
    if re.fullmatch(r"[0-9a-f]{40}", base) is None:
        raise ValueError("performance base must be a full lowercase commit SHA")
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if revision == base:
        raise ValueError("performance base must properly precede the tested revision")
    subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", base, revision], check=True)
    if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True):
        raise ValueError("census comparison requires a clean indexed checkout")
    specification = json.loads(descriptor.read_text(encoding="utf-8"))
    if (specification.get("schema") != "verifiedos-census-benchmark-inputs/1" or not specification.get("support")
            or "controls" not in specification or specification.keys() - {"schema", "support", "controls", "unavailable"}):
        raise ValueError("unsupported census comparison input descriptor")
    recipe = json.loads((root / "tools/opam/sail-support-qualification.json").read_text(encoding="utf-8"))
    report: dict[str, Any] = {"status": "preparing", "scope": "retained Python replay only; no native, assumption or kernel qualification",
                              "baseline_revision": base, "candidate_revision": revision, "workers": 1, "repetitions": 2,
                              "python": sys.version, "platform": platform.platform(), "samples": {"baseline": [], "candidate": []},
                              "descriptor_sha256": digest(descriptor), "unavailable": specification.get("unavailable")}
    write(output, report)
    try:
        with tempfile.TemporaryDirectory(prefix="vos-census-comparison-") as temporary:
            scratch = Path(temporary)
            datasets: dict[str, Any] = {}
            for name, roots in (("support", ["CensusControls", *("SailStdpp." + name for name in recipe["support_modules"])]),
                                ("controls", _CONTROLS)):
                if specification.get(name) is not None:
                    directory = scratch / name
                    directory.mkdir()
                    datasets[name] = prepare_dataset(root, specification[name], roots, directory)
            report["input_hashes"] = {name: dataset["input_hashes"] for name, dataset in datasets.items()}
            report["temporary_raw_bytes"] = sum(dataset["raw_bytes"] for dataset in datasets.values())
            prepared = scratch / "inputs.json"
            write(prepared, datasets)
            archive = scratch / "tools.tar"
            subprocess.run(["git", "-C", str(root), "archive", "--format=tar", "-o", str(archive), base, "tools"], check=True)
            with tarfile.open(archive) as source:
                source.extractall(scratch / "baseline", filter="data")
            reference: object = None
            for repetition in range(2):
                for variant in (("baseline", "candidate") if repetition == 0 else ("candidate", "baseline")):
                    tools = scratch / "baseline/tools" if variant == "baseline" else root / "tools"
                    sample = output.with_name(output.stem + f"-{variant}-{repetition + 1}.json")
                    report.update(status="running", active={"variant": variant, "repetition": repetition + 1, "checkpoint": str(sample)})
                    write(output, report)
                    begin = time.perf_counter()
                    command = [sys.executable, str(Path(__file__).resolve()), "--worker-tools", str(tools),
                               "--prepared", str(prepared), "--output", str(sample)]
                    result = subprocess.run(command, check=False, timeout=timeout)
                    measurement = json.loads(sample.read_text(encoding="utf-8"))
                    measurement["process_seconds"] = time.perf_counter() - begin
                    report["samples"][variant].append(measurement)
                    if result.returncode or measurement["status"] == "refused":
                        raise ValueError("complete replay refused; retain child checkpoint and diagnostic")
                    if reference is None:
                        reference = measurement["decisions"]
                    if reference != measurement["decisions"]:
                        raise ValueError("baseline/candidate complete decisions or ordered diagnostics differ")
                    write(output, report)
            for dataset in datasets.values():
                for name, expected in dataset["input_hashes"].items():
                    if digest(root / name) != expected:
                        raise ValueError("retained indexed inputs changed during comparison")
            if digest(descriptor) != report["descriptor_sha256"]:
                raise ValueError("input selection changed during comparison")
            if (subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip() != revision
                    or subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True)):
                raise ValueError("indexed source revision changed during comparison")
            report.update(status="complete" if datasets.get("controls") else "incomplete-control-evidence",
                          decisions_identical=True, median_seconds={variant: statistics.median(
                              row["process_seconds"] for row in values) for variant, values in report["samples"].items()})
    except BaseException as error:
        report.update(status="refused", refusal={"type": type(error).__name__, "message": str(error)})
        write(output, report)
        return 1
    report.pop("active", None)
    write(output, report)
    return 0 if report["status"] == "complete" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=4200)
    parser.add_argument("--worker-tools", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--prepared", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("native census comparisons run only on GitHub Actions")
    if args.worker_tools is not None and args.prepared is not None:
        return worker(args.worker_tools.resolve(), args.prepared.resolve(), args.output.resolve())
    if args.base is None or args.timeout <= 0:
        parser.error("--base and a positive timeout are required")
    root = args.root.resolve()
    return compare(root, args.base, args.inputs or root / "tools/ci/census-benchmark-inputs.json", args.output.resolve(), args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
