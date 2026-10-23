#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Cold Sail support carriage, with an independent portable-snapshot rebuild.

Only the guarded dispatch revision's reviewed recipe is executed. This standalone
campaign does not change Guest CI, QuickChick or the project's proof allowlist.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import runpy
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Protocol, cast

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from ci import bootstrap_instrument  # noqa: E402
from vos import compiler_component, opam_client, proofaudit, receipts  # noqa: E402

SCHEMA = "verifiedos-sail-support-qualification/1"
RECIPE = "tools/opam/sail-support-qualification.json"
SWITCH = "sail-support-qualification"
REVISION = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
STRICT = ["-q", "-w", "+default,-abstract-large-number", "-set",
          "Default Goal Selector=!", "-disallow-sprop"]
NATIVE_SCHEMA = "verifiedos-sail-support-native-qualification/1"
ENVIRONMENT_BOUNDARY = "Launcher and protected native populations; distro runtime outside these roots is a runner observation."
MAX_REQUEST_BYTES = 64 * 1024 * 1024
REQUEST_VARIABLES = ("VOS_CENSUS_RESOLVE", "VOS_CENSUS_RESOLVE_FILE")
OUTPUT_VARIABLE = "VOS_CENSUS_OUTPUT_FILE"
PROGRESS_VARIABLE = "VOS_CENSUS_PROGRESS_FILE"
OUTPUT_SCHEMA = "verifiedos-native-census-output/1"
CENSUS_SCHEMA = "verifiedos-sail-support-census/1"


class CensusAPI(Protocol):
    def parse_search_requests(self, searches: dict[str, str], *,
                              expected_modules: list[str]) -> list[dict[str, Any]]: ...

    def reading_targets(self, metadata: object) -> list[tuple[str, str]]: ...

    def census(self, metadata: object, searches: dict[str, str], readings: dict[str, str], *,
               expected_modules: list[str]) -> dict[str, dict[str, Any]]: ...

    def qualify_controls(self, metadata: object, searches: dict[str, str],
                         readings: dict[str, str]) -> dict[str, Any]: ...


def census_api(side: Path) -> CensusAPI:
    return cast("CensusAPI", SimpleNamespace(**runpy.run_path(str(side / "tools/rocq-census/census.py"))))


def json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def decode(text: str) -> object:
    return json.loads(text, object_pairs_hook=json_object)


def load(path: Path) -> dict[str, Any]:
    value = decode(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("expected JSON object")
    return cast("dict[str, Any]", value)


def json_chunks(value: object) -> Iterator[str]:
    yield from json.JSONEncoder(indent=2, sort_keys=True, allow_nan=False).iterencode(value)
    yield "\n"


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.writelines(json_chunks(value))


def require_canonical_json(path: Path, value: object) -> None:
    digest = hashlib.sha256()
    size = 0
    for chunk in json_chunks(value):
        encoded = chunk.encode("utf-8")
        size += len(encoded)
        digest.update(encoded)
    if path.stat().st_size != size or receipts.digest(path) != digest.hexdigest():
        raise ValueError("retained JSON bytes differ from the exact canonical audit")


def select_requests(environment: dict[str, str], *, direct: str | None = None,
                    source: Path | None = None) -> None:
    if (direct is None) == (source is None):
        raise ValueError("select exactly one native resolution-request source")
    for variable in REQUEST_VARIABLES:
        environment.pop(variable, None)
    if source is not None:
        environment["VOS_CENSUS_RESOLVE_FILE"] = str(source)
    elif direct is not None:
        environment["VOS_CENSUS_RESOLVE"] = direct


def request_source(environment: dict[str, str], private_root: Path) -> dict[str, Any] | None:
    present = [name for name in REQUEST_VARIABLES if name in environment]
    if not present:
        return None
    if len(present) != 1:
        raise ValueError("ambiguous native resolution-request source")
    if present[0] == "VOS_CENSUS_RESOLVE":
        contents = environment[present[0]].encode("utf-8")
        return {"kind": "environment", "bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}
    path = Path(environment[present[0]])
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or not path.resolve(strict=True).is_relative_to(private_root.resolve(strict=True))
            or path.stat().st_size > MAX_REQUEST_BYTES):
        raise ValueError("native request file must be a private absolute regular file within 64 MiB")
    with path.open("rb") as stream:
        contents = stream.read(MAX_REQUEST_BYTES + 1)
    if len(contents) > MAX_REQUEST_BYTES:
        raise ValueError("native request file exceeds 64 MiB")
    return {"kind": "file", "path": str(path), "bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}


def output_intent(environment: dict[str, str], private_root: Path) -> dict[str, Any] | None:
    if OUTPUT_VARIABLE not in environment:
        return None
    path = Path(environment[OUTPUT_VARIABLE])
    if (not path.is_absolute() or path.exists() or path.is_symlink() or not path.parent.is_dir()
            or path.parent.is_symlink()
            or not path.parent.resolve(strict=True).is_relative_to(private_root.resolve(strict=True))):
        raise ValueError("native census output must be a fresh absolute private path")
    return {"path": str(path), "absent": True}


def output_identity(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("native census output must be a regular file")
    before = path.stat()
    digest = hashlib.blake2b(digest_size=32)
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        closed = os.fstat(stream.fileno())
    after = path.stat()
    cuts = [(row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns) for row in (before, opened, closed, after)]
    if path.is_symlink() or len(set(cuts)) != 1:
        raise ValueError("native census output identity changed while reading")
    return {"path": str(path), "bytes": after.st_size, "blake2b_256": digest.hexdigest(),
            "device": after.st_dev, "inode": after.st_ino, "mtime_ns": after.st_mtime_ns}


def output_envelope(stdout: str, expected_path: str) -> dict[str, Any]:
    value = decode(stdout)
    if (not isinstance(value, dict) or set(value) != {"schema", "census_schema", "path", "bytes", "blake2b_256"}
            or value["schema"] != OUTPUT_SCHEMA or value["census_schema"] != CENSUS_SCHEMA
            or value["path"] != expected_path or type(value["bytes"]) is not int or value["bytes"] <= 0
            or not isinstance(value["blake2b_256"], str) or SHA256.fullmatch(value["blake2b_256"]) is None):
        raise ValueError("native census output envelope differs from the exact file protocol")
    return value


def census_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream, object_pairs_hook=json_object)
    if not isinstance(value, dict) or value.get("schema") != CENSUS_SCHEMA:
        raise ValueError("native census output file contains no census object")
    return cast("dict[str, Any]", value)


def retain_census_output(stdout: str, source: Path, retained: Path, command: dict[str, Any]) -> dict[str, Any]:
    envelope = output_envelope(stdout, str(source))
    if (command.get("status") != "completed" or command.get("exit") != 0
            or command.get("process_completed") is not True or command.get("timed_out") is not False
            or command.get("expected_refusal") is not False
            or command.get("native_environment", {}).get(OUTPUT_VARIABLE) != str(source)
            or command.get("output_file_before") != {"path": str(source), "absent": True}
            or command.get("output_file_after") != output_identity(source)):
        raise ValueError("native census output lacks unchanged launch/file identities")
    identity = command["output_file_after"]
    if any(identity[key] != envelope[key] for key in ("bytes", "blake2b_256")):
        raise ValueError("native census output bytes differ from its native envelope")
    metadata = census_file(source)
    if output_identity(source) != identity or retained.exists() or retained.is_symlink():
        raise ValueError("native census output changed during parsing or would overwrite retained evidence")
    shutil.copyfile(source, retained)
    copied = output_identity(retained)
    if (output_identity(source) != identity
            or any(copied[key] != envelope[key] for key in ("bytes", "blake2b_256"))):
        raise ValueError("native census output changed during evidence copy")
    command.update(output_file_verified=identity, output_retained=retained.name)
    return metadata


def asset(side: Path, entry: dict[str, Any]) -> Path:
    name, expected = entry.get("path"), entry.get("sha256")
    if (not isinstance(name, str) or "\\" in name or Path(name).is_absolute()
            or ".." in Path(name).parts or not isinstance(expected, str)
            or SHA256.fullmatch(expected) is None):
        raise ValueError("unsupported recipe asset")
    path = side / name
    if path.is_symlink() or not path.resolve().is_relative_to(side.resolve()):
        raise ValueError("escaping recipe asset")
    if receipts.digest(path) != expected:
        raise ValueError("recipe asset bytes differ: " + name)
    return path


def guarded_revision(checkout: Path, revision: str, dispatch: str, ref: str) -> None:
    if ref != "refs/heads/main" or not all(REVISION.fullmatch(x) for x in (revision, dispatch)):
        raise ValueError("dispatch and tested revision must be full main commits")
    actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                                     text=True).strip()
    if actual != revision:
        raise ValueError("checkout differs from guarded revision")
    subprocess.run(["git", "-C", str(checkout), "merge-base", "--is-ancestor",
                    revision, dispatch], check=True)


def recipe(side: Path) -> dict[str, Any]:
    found = load(side / RECIPE)
    if found.get("schema") != SCHEMA or found.get("strict_support_modules") != 29:
        raise ValueError("unsupported source-carriage recipe")
    if found.get("strict_flags") != STRICT:
        raise ValueError("consumer strict settings changed")
    for entry in [found["base_lock"], found["frozen_inventory"], *found["patches"],
                  *found["probes"].values()]:
        asset(side, entry)
    if set(found["probes"]) != {"term", "eqdep", "real", "notation"}:
        raise ValueError("missing independently expected probe controls")
    return found


def extract(archive: Path, destination: Path) -> Path:
    """Preserve contained upstream symlinks, refusing other special members."""
    if destination.exists():
        raise ValueError("source destination already exists")
    destination.mkdir(parents=True)
    with tarfile.open(archive) as source:
        members = source.getmembers()
        roots: set[str] = set()
        for member in members:
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("escaping source archive member")
            roots.add(path.parts[0])
            target = destination / path
            if member.issym():
                link = Path(member.linkname)
                if link.is_absolute() or not (target.parent / link).resolve().is_relative_to(destination / path.parts[0]):
                    raise ValueError("escaping source archive symlink")
            elif not (member.isfile() or member.isdir()):
                raise ValueError("unsupported source archive member")
        if len(roots) != 1:
            raise ValueError("source archive requires one root")
        source.extractall(destination, filter="data")
    return destination / roots.pop()


def download(entry: dict[str, Any], target: Path) -> None:
    url, expected = entry.get("url"), entry.get("sha256")
    if (not isinstance(url, str) or not url.startswith("https://")
            or not isinstance(expected, str) or SHA256.fullmatch(expected) is None):
        raise ValueError("source requires HTTPS and exact checksum")
    # The reviewed recipe and this guard admit HTTPS only; archive bytes are
    # independently authenticated before extraction or package execution.
    with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as stream:  # noqa: S310
        shutil.copyfileobj(response, stream)
    if receipts.digest(target) != expected:
        raise ValueError("source archive checksum differs")


def same_closure(actual: list[dict[str, str]], expected: dict[str, str]) -> None:
    if (len(actual) != len(expected) or {row["name"]: row["version"] for row in actual} != expected
            or any(row["pin"] for row in actual)):
        raise ValueError("installed dependency closure differs from reviewed versions")


def expected_closure(side: Path, found: dict[str, Any]) -> dict[str, str]:
    expected = dict(package.split(".", 1) for package in compiler_component.installed(
        asset(side, found["base_lock"]).read_text(encoding="utf-8")))
    return expected | {"rocq-stdpp-bitvector": "1.13.0", "rocq-sail-stdpp": "0.20.3"}


def kernel_reading(code: int, stdout: str, stderr: str, expected: list[str]) -> list[str]:
    if code != 0 or stdout.strip():
        raise ValueError("kernel did not provide successful whole-environment summary")
    names = proofaudit.kernel_context(stderr)
    if sorted(names) != sorted(expected) or len(names) != len(set(names)):
        raise ValueError("whole-environment assumptions differ from exact expected set")
    return names


def snapshot_metadata(text: str, patch_files: dict[str, bytes], source_sha: str) -> None:
    """Fail closed before import; actual independent import still proves portability."""
    if re.search(r'(?:file://|/home/runner/|/tmp/|/mnt/|/root/)', text):
        raise ValueError("snapshot contains local native source paths")
    if source_sha not in text or "extra-files:" not in text:
        raise ValueError("snapshot omits source checksum or embedded patch metadata")
    # The export can escape binary extra-file payloads; the import must subsequently
    # recover the exact metadata/patches and rebuild them. Names and their hashes
    # must be explicit before any imported package code executes.
    for name, contents in patch_files.items():
        if name not in text or hashlib.sha256(contents).hexdigest() not in text:
            raise ValueError("snapshot omits a reviewed patch identity")


class Campaign:
    def __init__(self, root: Path, side: Path, phase: str) -> None:
        if root.exists() or not root.is_absolute():
            raise ValueError("campaign requires a fresh absolute native root")
        root.mkdir(parents=True)
        self.root, self.side, self.phase = root, side, phase
        self.upload = root / "upload"
        self.upload.mkdir()
        self.environment = dict(os.environ, OPAMROOT=str(root / "opam"), OPAMYES="1",
                                OPAMROOTISOK="1", OPAMJOBS="2", OPAMCOLOR="never")
        self.environment.pop(OUTPUT_VARIABLE, None)
        self.environment.pop(PROGRESS_VARIABLE, None)
        self.report: dict[str, Any] = {"schema": SCHEMA, "phase": phase, "status": "pending",
            "run_id": os.environ.get("GITHUB_RUN_ID"), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "revision": os.environ["TESTED_REVISION"], "dispatch_revision": os.environ["GITHUB_SHA"],
            "recipe_sha256": receipts.digest(side / RECIPE), "commands": [],
            "strict_support_modules": 29, "dependency_source_settings": "unchanged package settings",
            "cold": True, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self.save()

    def save(self) -> None:
        write(self.upload / "receipt.json", self.report)

    def run(self, label: str, argv: list[str], cwd: Path, *, strict: bool = False,
            timeout: int = 10800, refusal: bool = False) -> subprocess.CompletedProcess[str]:
        start = time.monotonic()
        record: dict[str, Any] = {"label": label, "argv": argv, "cwd": str(cwd), "status": "pending",
            "process_completed": False, "exit": None, "strict": strict, "timed_out": False,
            "expected_refusal": refusal, "native_environment": {name: self.environment[name] for name in
                ("OPAMROOT", "OPAMSWITCH", "OPAM_SWITCH_PREFIX", "VOS_CENSUS_MODE", "VOS_CENSUS_TARGETS",
                 *REQUEST_VARIABLES, OUTPUT_VARIABLE, PROGRESS_VARIABLE, "OCAMLPATH") if name in self.environment},
            "request_source_before": request_source(self.environment, self.root), "request_source_after": None,
            "output_file_before": output_intent(self.environment, self.root), "output_file_after": None}
        self.report["commands"].append(record)
        self.save()
        launched = False
        completed = False
        try:
            with subprocess.Popen(argv, cwd=cwd, env=self.environment, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  encoding="utf-8", errors="replace", start_new_session=sys.platform == "linux") as process:
                launched = True
                limited = False
                try:
                    stdout, stderr = process.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    limited = True
                    if sys.platform == "linux":
                        os.killpg(process.pid, signal.SIGTERM)
                    else:
                        process.terminate()
                    try:
                        stdout, stderr = process.communicate(timeout=60)
                    except subprocess.TimeoutExpired:
                        if sys.platform == "linux":
                            os.killpg(process.pid, signal.SIGKILL)
                        else:
                            process.kill()
                        stdout, stderr = process.communicate()
                result = subprocess.CompletedProcess(argv, 124 if limited else process.returncode, stdout, stderr)
            completed = True
            record.update(status="timed-out" if limited else "completed", process_completed=completed,
                          exit=result.returncode, timed_out=limited)
            log = self.upload / (label + ".log")
            log.write_text(result.stdout + result.stderr, encoding="utf-8", newline="")
            streams: dict[str, dict[str, str]] = {}
            for name, value in (("stdout", result.stdout), ("stderr", result.stderr)):
                retained = self.upload / (label + "." + name + ".log")
                retained.write_text(value, encoding="utf-8", newline="")
                streams[name] = {"path": retained.name, "sha256": receipts.digest(retained)}
            record.update(seconds=time.monotonic() - start, log=log.name,
                          log_sha256=receipts.digest(log), streams=streams)
            record["request_source_after"] = request_source(self.environment, self.root)
            output = self.environment.get(OUTPUT_VARIABLE)
            if output is not None and (Path(output).exists() or Path(output).is_symlink()):
                record["output_file_after"] = output_identity(Path(output))
                if result.returncode != 0:
                    partial = self.upload / ("partial-" + Path(output).name)
                    shutil.copyfile(output, partial)
                    record["output_partial"] = partial.name
            self.save()
        except BaseException as error:
            status = ("interrupted" if not isinstance(error, Exception) else
                      "recording-error" if completed else "execution-error" if launched else "launch-error")
            record.update(status=status, seconds=time.monotonic() - start,
                          error_type=type(error).__name__, error=str(error))
            self.save()
            raise
        if record["request_source_before"] != record["request_source_after"]:
            raise ValueError("native resolution-request input changed during execution: " + label)
        if (limited or (result.returncode != 1 if refusal else result.returncode != 0)
                or (strict and (result.stdout.strip() or result.stderr.strip()))):
            raise ValueError("command failed or strict diagnostic: " + label)
        return result

    def opam(self, label: str, args: list[str]) -> subprocess.CompletedProcess[str]:
        return self.run(label, [str(self.root / "bin/opam"), *args], self.root)

    def executable(self, argv: list[str]) -> list[str]:
        return [str(self.root / "bin/opam"), "exec", "--switch=" + SWITCH, "--", *argv]


def identity_tree(roots: list[Path]) -> dict[str, str]:
    """Bind complete membership, bytes and symlink destinations, including empty directories."""
    identities: dict[str, str] = {}

    def visit(path: Path, ancestors: frozenset[Path]) -> None:
        resolved = path.resolve(strict=True)
        if path.is_symlink():
            identities[str(path) + "#symlink"] = hashlib.sha256(str(path.readlink()).encode()).hexdigest()
        if path.is_dir():
            if resolved in ancestors:
                raise ValueError("cyclic protected input directory")
            identities[str(path) + "/."] = hashlib.sha256(str(resolved).encode()).hexdigest()
            for child in sorted(path.iterdir()):
                visit(child, ancestors | {resolved})
        elif path.is_file():
            identities[str(path)] = receipts.digest(path)
        else:
            raise ValueError("unsupported protected input member: " + str(path))

    for root in roots:
        if not root.is_absolute() or not root.is_dir():
            raise ValueError("protected input root is not an existing absolute directory: " + str(root))
        if root.is_symlink():
            identities[str(root) + "#root-symlink"] = hashlib.sha256(str(root.readlink()).encode()).hexdigest()
        visit(root.resolve(strict=True), frozenset())
    if not identities:
        raise ValueError("input identity population is empty")
    return identities


def retained_member(root: Path, name: str) -> Path:
    if (not name or Path(name).name != name or "\\" in name
            or name in {".", ".."} or (root / name).is_symlink()):
        raise ValueError("escaping or ambiguous native evidence member")
    path = root / name
    if not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError("escaping native evidence member")
    return path


def native_path(value: object) -> str:
    if (not isinstance(value, str) or "\\" in value or not PurePosixPath(value).is_absolute()
            or ".." in PurePosixPath(value).parts or PurePosixPath(value).as_posix() != value):
        raise ValueError("native identity path must be a canonical absolute POSIX spelling")
    return value


def replay_request_source(command: dict[str, Any], artifact_root: Path, native_root: PurePosixPath) -> None:
    environment = command.get("native_environment", {})
    present = [name for name in REQUEST_VARIABLES if name in environment]
    before, after = command.get("request_source_before"), command.get("request_source_after")
    if len(present) > 1 or before != after:
        raise ValueError("native resolution-request source is ambiguous or changed")
    if not present:
        if before is not None:
            raise ValueError("native command records an unexplained resolution-request input")
        return
    if not isinstance(before, dict):
        raise TypeError("native request invocation lacks its source identity")
    if present[0] == "VOS_CENSUS_RESOLVE":
        contents = environment[present[0]].encode("utf-8")
        expected = {"kind": "environment", "bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}
    else:
        path = PurePosixPath(native_path(environment[present[0]]))
        if (path.name not in {"support-requests.json", "control-requests.json"}
                or path != native_root / "native-request-inputs" / path.name):
            raise ValueError("native request file escaped its private invocation input")
        retained = retained_member(artifact_root, path.name)
        if retained.stat().st_size > MAX_REQUEST_BYTES:
            raise ValueError("retained native request file exceeds 64 MiB")
        with retained.open("rb") as stream:
            contents = stream.read(MAX_REQUEST_BYTES + 1)
        if len(contents) > MAX_REQUEST_BYTES:
            raise ValueError("retained native request file exceeds 64 MiB")
        expected = {"kind": "file", "path": path.as_posix(), "bytes": len(contents),
                    "sha256": hashlib.sha256(contents).hexdigest()}
    if before != expected:
        raise ValueError("native resolution-request input differs from its retained bytes")


def replay_census_output(command: dict[str, Any], stdout: str, artifact_root: Path,
                         native_root: PurePosixPath, prefix: str) -> dict[str, Any]:
    expected = (native_root / "native-census-outputs" / (prefix + "-census.json")).as_posix()
    envelope = output_envelope(stdout, expected)
    identity = command.get("output_file_after")
    if (command.get("native_environment", {}).get(OUTPUT_VARIABLE) != expected
            or command.get("output_file_before") != {"path": expected, "absent": True}
            or not isinstance(identity, dict)
            or set(identity) != {"path", "bytes", "blake2b_256", "device", "inode", "mtime_ns"}
            or command.get("output_file_verified") != identity
            or any(identity[key] != envelope[key] for key in ("path", "bytes", "blake2b_256"))
            or any(type(identity[key]) is not int or identity[key] < 0 for key in ("device", "inode", "mtime_ns"))
            or command.get("output_retained") != prefix + "-census.json"):
        raise ValueError("native census output lacks exact retained invocation/file identities")
    retained = retained_member(artifact_root, command["output_retained"])
    before = output_identity(retained)
    if any(before[key] != envelope[key] for key in ("bytes", "blake2b_256")):
        raise ValueError("retained census bytes differ from the original native output envelope")
    metadata = census_file(retained)
    if output_identity(retained) != before:
        raise ValueError("retained native census changed during replay parsing")
    return metadata


def command_streams(root: Path, command: dict[str, Any]) -> tuple[str, str]:
    streams = command.get("streams")
    if not isinstance(streams, dict) or set(streams) != {"stdout", "stderr"}:
        raise ValueError("native command lacks separately bound streams")
    values: list[str] = []
    for name in ("stdout", "stderr"):
        entry = streams[name]
        path = retained_member(root, entry["path"])
        if receipts.digest(path) != entry["sha256"]:
            raise ValueError("native command stream bytes differ")
        values.append(path.read_text(encoding="utf-8"))
    combined = retained_member(root, command["log"])
    if (receipts.digest(combined) != command["log_sha256"]
            or combined.read_text(encoding="utf-8") != "".join(values)):
        raise ValueError("native combined log differs from its streams")
    return values[0], values[1]


def query(campaign: Campaign, label: str, text: str, mappings: list[str], *,
          refusal: bool = False, source_name: str | None = None,
          census_output: Path | None = None) -> subprocess.CompletedProcess[str]:
    campaign.environment.pop(OUTPUT_VARIABLE, None)
    campaign.environment.pop(PROGRESS_VARIABLE, None)
    folder = campaign.root / "native-queries"
    folder.mkdir(exist_ok=True)
    name = source_name or label.replace("-", "_").title() + ".v"
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.v", name) is None:
        raise ValueError("native query requires one valid Rocq source name")
    source = folder / name
    source.write_text(text, encoding="utf-8", newline="")
    (campaign.upload / ("query-" + label + ".v")).write_bytes(source.read_bytes())
    if census_output is not None:
        campaign.environment[OUTPUT_VARIABLE] = str(census_output)
    try:
        result = campaign.run(label, campaign.executable(["rocq", "c", *mappings,
                              *STRICT, str(source)]), campaign.root, refusal=refusal)
    finally:
        campaign.environment.pop(OUTPUT_VARIABLE, None)
        campaign.environment.pop(PROGRESS_VARIABLE, None)
    campaign.report["commands"][-1].update(query_source="query-" + label + ".v",
        query_sha256=receipts.digest(source), native_source_name=source.name)
    campaign.save()
    if not refusal and result.stderr.strip():
        raise ValueError("native query printed a diagnostic: " + label)
    return result


def native_readings(campaign: Campaign, api: CensusAPI, metadata: object,
                    roots: list[str], mappings: list[str], prefix: str) -> dict[str, str]:
    readings: dict[str, str] = {}
    targets = api.reading_targets(metadata)
    if len(targets) != len(set(targets)):
        raise ValueError("native reading targets repeat")
    for index, (kind, name) in enumerate(targets):
        if kind not in {"module", "module-type"}:
            raise ValueError("unsupported native reading kind")
        command = "Print Module " if kind == "module" else "Print Module Type "
        text = "Require " + " ".join(roots) + ".\n" + proofaudit.SETTINGS + command + name + ".\n"
        readings[kind + ":" + name] = query(campaign, prefix + "-reading-" + str(index),
                                          text, mappings).stdout
    return readings


def native_dataset(campaign: Campaign, api: CensusAPI, roots: list[str],
                   mappings: list[str], prefix: str) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    searches = {module: query(campaign,
        ("inventory-" if prefix == "support" else "control-inventory-") + str(index),
        proofaudit.inventory_query(module), mappings).stdout for index, module in enumerate(roots)}
    requests = api.parse_search_requests(searches, expected_modules=roots)
    retained = campaign.upload / (prefix + "-requests.json")
    write(retained, requests)
    inputs = campaign.root / "native-request-inputs"
    inputs.mkdir(exist_ok=True)
    source = inputs / retained.name
    shutil.copy2(retained, source)
    select_requests(campaign.environment, source=source)
    campaign.environment.update(VOS_CENSUS_MODE="census", VOS_CENSUS_TARGETS=",".join(roots))
    outputs = campaign.root / "native-census-outputs"
    outputs.mkdir(mode=0o700, exist_ok=True)
    output = outputs / (prefix + "-census.json")
    emitted = query(campaign, prefix + "-native-census",
                    "Require " + " ".join(roots) + '.\nDeclare ML Module "vos_rocq_census".\n', mappings,
                    census_output=output)
    metadata = retain_census_output(emitted.stdout, output, campaign.upload / (prefix + "-census.json"),
                                    campaign.report["commands"][-1])
    campaign.save()
    readings = native_readings(campaign, api, metadata, roots, mappings, prefix)
    for suffix, value in (("search", searches), ("readings", readings)):
        write(campaign.upload / (prefix + "-" + suffix + ".json"), value)
    return metadata, searches, readings


def native_sources(side: Path) -> dict[str, str]:
    paths = ["tools/ci/sail_support_route.py", "tools/ci/bootstrap_instrument.py",
             "tools/vos/compiler_component.py", "tools/vos/opam_client.py", "tools/vos/proofaudit.py",
             "tools/vos/receipts.py", "tools/rocq-census/census.py", "tools/rocq-census/census-schema.json",
             "tools/rocq-census/vos_rocq_census.ml", "tools/rocq-census/CensusControls.v",
             "tools/rocq-census/SignatureFieldRefusal.v", "tools/rocq-census/UnsupportedShapeRefusal.v",
             "tools/rocq-census/HiddenAssumptions.v", "tools/rocq-census/control-spec.json"]
    tracked = subprocess.check_output(["git", "-C", str(side), "ls-files", "-z", "--", "tools"],
                                     text=True, encoding="utf-8").split("\0")
    python_sources = {name for name in tracked if name.endswith(".py")}
    if not {name for name in paths if name.endswith(".py")} <= python_sources:
        raise ValueError("native qualification implementation entrypoint is not tracked")
    found = recipe(side)
    paths += [RECIPE, ".github/workflows/sail-support-qualification.yml", "tools/pyproject.toml", "tools/uv.lock",
              found["base_lock"]["path"], found["frozen_inventory"]["path"],
              *(entry["path"] for entry in found["patches"]),
              *(entry["path"] for entry in found["probes"].values())]
    return {name: receipts.digest(side / name) for name in sorted(set(paths) | python_sources)}


def native_runtime(campaign: Campaign) -> dict[str, dict[str, str]]:
    installed = campaign.root / "opam" / SWITCH
    launchers = {"python": Path(sys.executable), "opam": campaign.root / "bin/opam",
                 **{name: installed / "bin" / name for name in ("rocq", "rocqchk", "ocamlfind", "ocamlopt")}}
    return {name: {"path": str(path), "resolved_path": str(path.resolve(strict=True)),
                   "sha256": receipts.digest(path)} for name, path in launchers.items()}


def prepare_native(campaign: Campaign, mappings: list[str]) -> tuple[Path, Path]:
    source = campaign.side / "tools/rocq-census"
    package = campaign.root / "native-plugin" / "vos_rocq_census"
    package.mkdir(parents=True)
    shutil.copy2(source / "vos_rocq_census.ml", package)
    (package / "META").write_text('description = "Original Q35q census producer"\n'
        'requires = "rocq-runtime.vernac"\nplugin(native) = "vos_rocq_census.cmxs"\n', encoding="utf-8", newline="")
    campaign.environment["OCAMLPATH"] = (str(package.parent) + os.pathsep
        + str(campaign.root / "opam" / SWITCH / "lib") + os.pathsep
        + campaign.environment.get("OCAMLPATH", ""))
    campaign.run("native-plugin-build", campaign.executable(["ocamlfind", "ocamlopt", "-rectypes",
        "-thread", "-shared", "-package", "rocq-runtime.vernac", "-w", "+8", "-warn-error", "+8",
        "-o", str(package / "vos_rocq_census.cmxs"), str(package / "vos_rocq_census.ml")]), campaign.root)
    controls = campaign.root / "native-control-inputs"
    controls.mkdir()
    shutil.copy2(source / "CensusControls.v", controls)
    campaign.run("native-control-compile", campaign.executable(["rocq", "c", *mappings,
        "-Q", str(controls), "", *STRICT, str(controls / "CensusControls.v")]), campaign.root, strict=True)
    return package.parent, controls


def audit_sources(campaign: Campaign, found: dict[str, Any], selected: list[Path],
                  candidate_map: list[str]) -> None:
    api = census_api(campaign.side)
    modules = ["SailStdpp." + source.stem for source in selected]
    metadata, searches, readings = native_dataset(campaign, api, modules, candidate_map, "support")
    classified = api.census(metadata, searches, readings, expected_modules=modules)
    del metadata, searches, readings
    write(campaign.upload / "support-census-audit.json", classified)
    audits: dict[str, object] = {}
    alias_audits: dict[str, object] = {}
    for index, source in enumerate(selected):
        module = "SailStdpp." + source.stem
        symbols = classified[module]["symbols"]
        checked = query(campaign, "assumptions-" + str(index), proofaudit.assumption_query(module, symbols), candidate_map)
        proofaudit.assumptions(checked.stdout, symbols)
        for symbol in symbols:
            names = {entry.split(" : ", 1)[0] for entry in symbol["assumptions"]}
            if not names <= set(found["support_axioms"]):
                raise ValueError("native declaration has an undeclared assumption")
        audits[module] = symbols
        bindings = classified[module]["alias_audits"]
        aliases = alias_symbols(bindings)
        checked = query(campaign, "alias-assumptions-" + str(index),
                         proofaudit.assumption_query(module, aliases), candidate_map)
        proofaudit.assumptions(checked.stdout, aliases)
        if any({entry.split(" : ", 1)[0] for entry in symbol["assumptions"]} - set(found["support_axioms"])
               for symbol in aliases):
            raise ValueError("native alias target has an undeclared assumption")
        alias_audits[module] = {"bindings": bindings, "audits": aliases}
    if not any(audits.values()):
        raise ValueError("native source inventory enumerated no declaration")
    write(campaign.upload / "native-assumptions.json", audits)
    write(campaign.upload / "native-alias-assumptions.json", alias_audits)


def alias_symbols(bindings: list[dict[str, Any]]) -> list[proofaudit.Symbol]:
    """Transport exact native targets to the assumption oracle, without a type/ownership claim."""
    return [{"name": name, "type": "", "claims": [], "assumptions": []}
            for name in sorted({binding["audit_query_name"] for binding in bindings})]


def control_spec(side: Path) -> dict[str, Any]:
    spec = load(side / "tools/rocq-census/control-spec.json")
    if (spec.get("schema") != "verifiedos-rocq-census-controls/1"
            or spec.get("positive", {}).get("root") != "CensusControls"
            or spec.get("positive", {}).get("targets") != ["CensusControls", "SailStdpp.TypeCasts", "SailStdpp.State_monad"]
            or [entry.get("name") for entry in spec.get("hidden_assumptions", {}).get("symbols", [])] !=
                ["CensusControls.HiddenSealed.witness", "CensusControls.HiddenAlias.witness"]):
        raise ValueError("unsupported native control specification")
    unsupported = spec["unsupported_refusal"]
    hidden = spec["hidden_assumptions"]
    return {"schema": spec["schema"], "root": spec["positive"]["root"],
        "targets": spec["positive"]["targets"], "required_modules": spec["positive"]["required_modules"],
        "refusals": {"signature": {"source": spec["signature_refusal"]["source"],
                "diagnostic": spec["signature_refusal"]["required_diagnostic"]},
            "unsupported": {"source": unsupported["source"], "diagnostic": unsupported["required_diagnostic"],
                "environment": {"VOS_CENSUS_MODE": unsupported["mode"],
                    "VOS_CENSUS_TARGETS": ",".join(unsupported["targets"]), "VOS_CENSUS_RESOLVE": "[]"}}},
        "hidden_assumptions": {"source": hidden["source"], "symbols": hidden["symbols"]}}


def hidden_assumption_audit(stdout: str, expected: list[dict[str, Any]]) -> list[proofaudit.Symbol]:
    symbols: list[proofaudit.Symbol] = [{"name": entry["name"], "type": "control", "claims": [], "assumptions": []}
                                      for entry in expected]
    proofaudit.assumptions(stdout, symbols)
    for symbol, declared in zip(symbols, expected, strict=True):
        names = [entry.split(" : ", 1)[0] for entry in symbol["assumptions"]]
        if sorted(names) != sorted(declared["expected_axioms"]) or len(names) != len(set(names)):
            raise ValueError("sealed/alias hidden-axiom native control differs from exact expected assumptions")
    return symbols


def control_census_join(classified: dict[str, dict[str, Any]], spec: dict[str, Any]) -> None:
    """Join the reviewed positive/hidden controls to the adapter's native classifications."""
    # The adapter has validated every query target against its native module path.
    modules = {module["query"]["target"] for root in classified.values() for module in root["modules"]
               if module["query"]["target_module_id"] == module["id"] and not module["query"]["coverage_path"]}
    if not set(spec["required_modules"]) <= modules:
        raise ValueError("native positive-control census omits a required module")
    controls = classified[spec["root"]]
    guarded = {symbol["name"] for symbol in controls["symbols"]}
    exported: set[str] = set()
    for declaration in controls["declarations"]:
        if declaration["classification"] != "owned":
            continue
        reference, connection = declaration["native_reference"], declaration["implementation_connection"]
        if (reference["exported_name"] != declaration["exported_name"]
                or reference["canonical_name"] not in guarded
                or connection["audit_query_name"] != reference["canonical_name"]):
            raise ValueError("native hidden-control ownership lacks its exact guarded audit binding")
        exported.add(declaration["exported_name"])
    aliases = {name for binding in controls["alias_audits"]
               for name in (binding["exported_spelling"], binding["audit_query_name"])}
    if any(entry["name"] not in exported | aliases for entry in spec["hidden_assumptions"]["symbols"]):
        raise ValueError("native hidden-assumption query has no owned or alias census binding")


def native_controls(campaign: Campaign, mappings: list[str]) -> None:
    api, spec = census_api(campaign.side), control_spec(campaign.side)
    metadata, searches, readings = native_dataset(campaign, api, spec["targets"], mappings, "control")
    control_census_join(api.census(metadata, searches, readings, expected_modules=spec["targets"]), spec)
    report = api.qualify_controls(metadata, searches, readings)
    del metadata, searches, readings
    write(campaign.upload / "control-adapter-verdicts.json", report)
    source = campaign.side / "tools/rocq-census"
    for name, entry in spec["refusals"].items():
        environment = entry.get("environment", {})
        if "VOS_CENSUS_RESOLVE" in environment:
            select_requests(campaign.environment, direct=environment["VOS_CENSUS_RESOLVE"])
        else:
            select_requests(campaign.environment, source=Path(campaign.environment["VOS_CENSUS_RESOLVE_FILE"]))
        campaign.environment.update(environment)
        result = query(campaign, "native-" + name + "-refusal",
                       (source / entry["source"]).read_text(encoding="utf-8"), mappings,
                       refusal=True, source_name=entry["source"])
        if entry["diagnostic"] not in result.stdout + result.stderr:
            raise ValueError("native control did not provide its expected refusal: " + name)
    # The control axiom belongs to this expected reading alone, never the support allowlist.
    hidden = spec["hidden_assumptions"]
    result = query(campaign, "native-hidden-assumptions",
                   (source / hidden["source"]).read_text(encoding="utf-8"), mappings, source_name=hidden["source"])
    symbols = hidden_assumption_audit(result.stdout, hidden["symbols"])
    write(campaign.upload / "native-control-verdicts.json", {"schema": spec["schema"],
        "status": "passed", "adapter": report, "hidden_assumptions": symbols,
        "native_refusals": sorted(spec["refusals"])})


def publish_native_qualification(campaign: Campaign, modules: list[str], roots: list[Path]) -> None:
    if campaign.report["native_sources_before"] != native_sources(campaign.side):
        raise ValueError("native qualification source inputs changed during execution")
    runtime = native_runtime(campaign)
    if campaign.report["native_runtime_before"] != runtime:
        raise ValueError("native qualification launchers changed during execution")
    after = identity_tree(roots)
    before = load(campaign.upload / "input-identities-before.json")
    write(campaign.upload / "input-identities.json", after)
    if before != after:
        raise ValueError("census, assumption or kernel input population changed")
    names = [path.name for path in campaign.upload.iterdir() if path.is_file() and path.name != "receipt.json"]
    evidence = {name: {"sha256": receipts.digest(campaign.upload / name),
                       "bytes": (campaign.upload / name).stat().st_size} for name in sorted(names)}
    # These are the runner's case-sensitive environment variable spellings.
    image = {name: os.environ.get(name) for name in ("ImageOS", "ImageVersion")}
    qualified = {"schema": NATIVE_SCHEMA, "status": "passed", "modules": modules,
        "revision": campaign.report["revision"], "dispatch_revision": campaign.report["dispatch_revision"],
        "run_id": campaign.report["run_id"], "run_attempt": campaign.report["run_attempt"], "cold": True,
        "recipe_sha256": receipts.digest(campaign.side / RECIPE), "sources": native_sources(campaign.side),
        "protected_roots": [str(root.resolve(strict=True)) for root in roots],
        "load_paths": campaign.report["native_load_paths"],
        "opam_context": {"root": campaign.environment["OPAMROOT"], "switch": campaign.environment["OPAMSWITCH"],
                         "prefix": campaign.environment["OPAM_SWITCH_PREFIX"]},
        "runtime_before": campaign.report["native_runtime_before"], "runtime_after": runtime,
        "runner": {"platform": platform.platform(), "machine": platform.machine(), "python": sys.version,
            "image_os": image["ImageOS"], "image_version": image["ImageVersion"]},
        "environment_boundary": ENVIRONMENT_BOUNDARY,
        "commands": list(campaign.report["commands"]), "evidence": evidence}
    target = campaign.upload / "native-census-qualified.json"
    write(target, qualified)
    try:
        validate_native_qualification(campaign.upload, campaign.side, campaign.report["revision"],
            run_id=campaign.report["run_id"], run_attempt=campaign.report["run_attempt"],
            dispatch_revision=campaign.report["dispatch_revision"])
    except (OSError, ValueError, KeyError, TypeError):
        target.unlink(missing_ok=True)
        raise


def validate_native_qualification(artifact_root: Path, side: Path, revision: str, *,
                                  run_id: str | None = None,
                                  run_attempt: str | None = None,
                                  dispatch_revision: str | None = None) -> dict[str, Any]:
    """Replay the Q35q verdict independently of the later Q35n carriage decision."""
    row = load(retained_member(artifact_root, "native-census-qualified.json"))
    if (row.get("schema") != NATIVE_SCHEMA or row.get("status") != "passed" or row.get("cold") is not True
            or row.get("revision") != revision or REVISION.fullmatch(revision) is None
            or REVISION.fullmatch(row.get("dispatch_revision", "")) is None
            or re.fullmatch(r"[1-9][0-9]*", row.get("run_id", "")) is None
            or re.fullmatch(r"[1-9][0-9]*", row.get("run_attempt", "")) is None
            or (run_id is not None and row.get("run_id") != run_id)
            or (run_attempt is not None and row.get("run_attempt") != run_attempt)
            or (dispatch_revision is not None and row.get("dispatch_revision") != dispatch_revision)
            or row.get("recipe_sha256") != receipts.digest(side / RECIPE)
            or row.get("sources") != native_sources(side)):
        raise ValueError("native qualification does not bind the requested inputs/run")
    found, spec, api = recipe(side), control_spec(side), census_api(side)
    modules = row["modules"]
    if (not isinstance(modules, list) or len(modules) != 29 or len(set(modules)) != 29
            or set(modules) != {"SailStdpp." + name for name in found["support_modules"]}):
        raise ValueError("native qualification lacks exact selected support population")
    evidence = row.get("evidence")
    required_files = {"support-search.json", "support-census.json", "support-readings.json",
        "support-requests.json", "control-requests.json",
        "support-census-audit.json", "native-assumptions.json", "native-alias-assumptions.json", "control-search.json", "control-census.json",
        "control-readings.json", "control-adapter-verdicts.json", "native-control-verdicts.json",
        "input-identities-before.json", "input-identities.json"}
    if not isinstance(evidence, dict) or not required_files <= evidence.keys():
        raise ValueError("native qualification lacks complete raw evidence")
    for name, identity in evidence.items():
        path = retained_member(artifact_root, name)
        if receipts.digest(path) != identity["sha256"] or path.stat().st_size != identity["bytes"]:
            raise ValueError("native qualification evidence bytes differ")
    before = load(retained_member(artifact_root, "input-identities-before.json"))
    after = load(retained_member(artifact_root, "input-identities.json"))
    protected = row.get("protected_roots")
    if (not before or before != after or not isinstance(protected, list) or not protected
            or len(protected) != len(set(protected))
            or any(not isinstance(value, str) or SHA256.fullmatch(value) is None for value in before.values())
            or any(native_path(root) + "/." not in before for root in protected)):
        raise ValueError("native qualification input identities are absent, incomplete or changed")
    runtime = row.get("runtime_before")
    if (not isinstance(runtime, dict) or set(runtime) != {"python", "opam", "rocq", "rocqchk", "ocamlfind", "ocamlopt"}
            or runtime != row.get("runtime_after") or not isinstance(row.get("runner"), dict)
            or row.get("environment_boundary") != ENVIRONMENT_BOUNDARY
            or any(not isinstance(row["runner"].get(name), str) or not row["runner"][name]
                   for name in ("platform", "machine", "python"))):
        raise ValueError("native qualification lacks unchanged launcher identities and runner observations")
    for name, launcher in runtime.items():
        native_path(launcher["path"])
        native_path(launcher["resolved_path"])
        if (not isinstance(launcher.get("sha256"), str) or SHA256.fullmatch(launcher["sha256"]) is None
                or (name != "python" and before.get(launcher["path"]) != launcher["sha256"])):
            raise ValueError("native launcher identity differs from protected inputs")
    opam = row.get("opam_context")
    if (not isinstance(opam, dict) or set(opam) != {"root", "switch", "prefix"} or opam["switch"] != SWITCH
            or native_path(opam["prefix"]) != (PurePosixPath(native_path(opam["root"])) / SWITCH).as_posix()
            or any(runtime[name]["path"] != (PurePosixPath(opam["prefix"]) / "bin" / name).as_posix()
                   for name in ("rocq", "rocqchk", "ocamlfind", "ocamlopt"))):
        raise ValueError("native opam context does not select the hashed switch launchers")
    output_root = PurePosixPath(opam["root"]).parent / "native-census-outputs"
    if any(output_root.is_relative_to(PurePosixPath(root)) or PurePosixPath(root).is_relative_to(output_root)
           for root in protected):
        raise ValueError("native census output overlaps protected input roots")
    expected_opam_environment = {variable: opam[key] for variable, key in
        (("OPAMROOT", "root"), ("OPAMSWITCH", "switch"), ("OPAM_SWITCH_PREFIX", "prefix"))}
    commands: dict[str, dict[str, Any]] = {}
    streams: dict[str, tuple[str, str]] = {}
    native_refusals = {"native-" + name + "-refusal": entry for name, entry in spec["refusals"].items()}
    for command in row["commands"]:
        label = command["label"]
        if (label in commands or command.get("timed_out") is not False or command.get("status") != "completed"
                or command.get("process_completed") is not True):
            raise ValueError("native qualification repeats a command or records an unfinished launch")
        commands[label] = command
        streams[label] = command_streams(artifact_root, command)
        replay_request_source(command, artifact_root, PurePosixPath(opam["root"]).parent)
        if PROGRESS_VARIABLE in command.get("native_environment", {}):
            raise ValueError("hosted native command selected an unsupported progress destination")
        if label not in {"support-native-census", "control-native-census"} and (
                OUTPUT_VARIABLE in command.get("native_environment", {})
                or any(command.get(key) is not None for key in
                       ("output_file_before", "output_file_after", "output_file_verified", "output_retained"))):
            raise ValueError("non-census command retained an active census output destination")
        if label in native_refusals:
            if (command.get("expected_refusal") is not True or command["exit"] != 1
                    or native_refusals[label]["diagnostic"] not in "".join(streams[label])):
                raise ValueError("native control supplied no expected prover refusal")
        elif command["exit"] != 0 or command.get("expected_refusal") is not False:
            raise ValueError("native qualification includes a failed command")
        if command["strict"] and "".join(streams[label]).strip():
            raise ValueError("strict command printed a diagnostic")
        if "query_source" in command:
            source = retained_member(artifact_root, command["query_source"])
            if (source.name not in evidence or receipts.digest(source) != command["query_sha256"]
                    or Path(command["argv"][-1]).name != command["native_source_name"]
                    or command["argv"][-len(STRICT)-1:-1] != STRICT):
                raise ValueError("native query source or strict flags differ")
            if label not in native_refusals and streams[label][1].strip():
                raise ValueError("native query printed a diagnostic")
    required = {"native-plugin-build", "native-control-compile", "support-native-census", "control-native-census",
        "native-hidden-assumptions", "closure", *native_refusals,
        *(label + str(index) for index in range(29) for label in ("strict-", "inventory-", "assumptions-", "alias-assumptions-")),
        *("kernel-" + name for name in ("support", "term", "eqdep", "real", "notation")),
        *("probe-compile-" + name for name in ("term", "eqdep", "real", "notation"))}
    if not required <= commands.keys():
        raise ValueError("native qualification lacks complete strict/census/control/kernel commands")
    load_paths = row.get("load_paths")
    if not isinstance(load_paths, dict) or set(load_paths) != {"support", "probes", "controls"}:
        raise ValueError("native qualification lacks its exact load paths")
    support_map = load_paths["support"]
    if (not isinstance(support_map, list) or len(support_map) != 13
            or [support_map[index] for index in (0, 1, 3, 4, 6, 7, 9, 10, 12)] !=
                ["-boot", "-R", "Corelib", "-Q", "Stdlib", "-Q", "stdpp", "-R", "SailStdpp"]
            or any(native_path(support_map[index]) + "/." not in before for index in (2, 5, 8, 11))):
        raise ValueError("native support mappings differ from the protected input population")
    for name, logical in (("probes", "Qualification"), ("controls", "")):
        mapping = load_paths[name]
        if (not isinstance(mapping, list) or len(mapping) != 3 or mapping[0] != "-Q" or mapping[2] != logical
                or native_path(mapping[1]) not in protected):
            raise ValueError("native probe/control mapping differs from its protected root")

    def executable_tail(command: dict[str, Any]) -> list[str]:
        argv = command["argv"]
        if (not isinstance(argv, list) or len(argv) < 5 or argv[1:4] != ["exec", "--switch=" + SWITCH, "--"]
                or native_path(argv[0]) != runtime["opam"]["path"]):
            raise ValueError("native command does not use its protected locked executable route")
        if not all(isinstance(part, str) for part in argv):
            raise TypeError("native executable arguments must be strings")
        check_opam_environment(command)
        return cast("list[str]", argv[4:])

    def check_opam_environment(command: dict[str, Any]) -> None:
        environment = command.get("native_environment", {})
        if any(environment.get(variable) != value for variable, value in expected_opam_environment.items()):
            raise ValueError("native command selected a different opam root/switch")

    closure = commands["closure"]
    check_opam_environment(closure)
    if closure["argv"] != [runtime["opam"]["path"], "list", "--switch=" + SWITCH, "--installed",
                           "--short", "--columns=name,version,pin", "--color=never"]:
        raise ValueError("native closure command changed the selected package inventory")
    same_closure(bootstrap_instrument.parse_closure(streams["closure"][0]), expected_closure(side, found))

    for index, module in enumerate(modules):
        source = (PurePosixPath(support_map[11]) / (module.rsplit(".", 1)[-1] + ".v")).as_posix()
        if (source not in before or executable_tail(commands["strict-" + str(index)]) !=
                ["rocq", "c", *support_map, *STRICT, source]):
            raise ValueError("strict support compile differs from its exact protected source")
    for name, entry in found["probes"].items():
        source = (PurePosixPath(load_paths["probes"][1]) / (name + ".v")).as_posix()
        if (before.get(source) != receipts.digest(side / entry["path"])
                or executable_tail(commands["probe-compile-" + name]) !=
                    ["rocq", "c", *support_map, *load_paths["probes"], *STRICT, source]):
            raise ValueError("strict probe compile differs from its reviewed source")
    plugin_command = executable_tail(commands["native-plugin-build"])
    if (len(plugin_command) != 14 or plugin_command[:12] != ["ocamlfind", "ocamlopt", "-rectypes",
            "-thread", "-shared", "-package", "rocq-runtime.vernac", "-w", "+8", "-warn-error", "+8", "-o"]
            or plugin_command[12] not in before
            or before.get(plugin_command[13]) != row["sources"]["tools/rocq-census/vos_rocq_census.ml"]):
        raise ValueError("native producer build differs from its protected original source")
    control_source = (PurePosixPath(load_paths["controls"][1]) / "CensusControls.v").as_posix()
    if (before.get(control_source) != row["sources"]["tools/rocq-census/CensusControls.v"]
            or executable_tail(commands["native-control-compile"]) !=
                ["rocq", "c", *support_map, *load_paths["controls"], *STRICT, control_source]):
        raise ValueError("native positive controls differ from their protected original source")

    def check_query(label: str, expected: str) -> None:
        command = commands[label]
        if ("query_source" not in command or retained_member(artifact_root, command["query_source"])
                .read_text(encoding="utf-8") != expected):
            raise ValueError("native query differs from its exact reviewed purpose: " + label)
        mapping = [*support_map, *(load_paths["controls"] if label.startswith(("control-", "native-")) else [])]
        argv = executable_tail(command)
        if argv != ["rocq", "c", *mapping, *STRICT, native_path(command["argv"][-1])]:
            raise ValueError("native query does not use its exact compiler/load-path settings")
        environment = command.get("native_environment", {})
        ocamlpath = environment.get("OCAMLPATH")
        if (not isinstance(ocamlpath, str) or not ocamlpath
                or any(native_path(path) + "/." not in before for path in ocamlpath.split(":") if path)):
            raise ValueError("native plugin discovery includes an unprotected input directory")

    audited = load(artifact_root / "native-assumptions.json")
    aliases_audited = load(artifact_root / "native-alias-assumptions.json")
    if set(audited) != set(modules) or set(aliases_audited) != set(modules):
        raise ValueError("native assumptions lack the exact module population")

    def replay_dataset(prefix: str, requested: list[str]) -> dict[str, Any] | None:
        # Keep each complete native graph and every derived row in this call's
        # scope, so the next dataset is parsed only after these references die.
        searches = load(artifact_root / (prefix + "-search.json"))
        readings = load(artifact_root / (prefix + "-readings.json"))
        metadata = replay_census_output(commands[prefix + "-native-census"], streams[prefix + "-native-census"][0],
            artifact_root, PurePosixPath(opam["root"]).parent, prefix)
        check_query(prefix + "-native-census",
            "Require " + " ".join(requested) + '.\nDeclare ML Module "vos_rocq_census".\n')
        environment = commands[prefix + "-native-census"]["native_environment"]
        expected_requests = api.parse_search_requests(searches, expected_modules=requested)
        request_path = (PurePosixPath(opam["root"]).parent / "native-request-inputs" / (prefix + "-requests.json")).as_posix()
        if (environment.get("VOS_CENSUS_MODE") != "census"
                or environment.get("VOS_CENSUS_TARGETS") != ",".join(requested)
                or environment.get("VOS_CENSUS_RESOLVE_FILE") != request_path
                or "VOS_CENSUS_RESOLVE" in environment
                or decode((artifact_root / (prefix + "-requests.json")).read_text(encoding="utf-8")) != expected_requests
                or metadata.get("resolution_requests") != expected_requests):
            raise ValueError("native producer invocation differs from exact roots/Search resolution requests")
        for index, module in enumerate(requested):
            label = ("inventory-" if prefix == "support" else "control-inventory-") + str(index)
            if label not in streams or streams[label][0] != searches.get(module):
                raise ValueError("retained Search differs from original native output")
            check_query(label, proofaudit.inventory_query(module))
        for index, (kind, name) in enumerate(api.reading_targets(metadata)):
            label = prefix + "-reading-" + str(index)
            if label not in streams or streams[label][0] != readings.get(kind + ":" + name):
                raise ValueError("retained Print reading differs from original native output")
            command = "Print Module " if kind == "module" else "Print Module Type "
            check_query(label, "Require " + " ".join(requested) + ".\n" + proofaudit.SETTINGS + command + name + ".\n")
        classified = api.census(metadata, searches, readings, expected_modules=requested)
        if prefix == "control":
            control_census_join(classified, spec)
            del classified
            control_report = api.qualify_controls(metadata, searches, readings)
            if control_report != load(artifact_root / "control-adapter-verdicts.json"):
                raise ValueError("native adapter control replay differs")
            return control_report
        del metadata
        require_canonical_json(artifact_root / "support-census-audit.json", classified)
        for index, module in enumerate(modules):
            symbols = classified[module]["symbols"]
            check_query("assumptions-" + str(index), proofaudit.assumption_query(module, symbols))
            proofaudit.assumptions(streams["assumptions-" + str(index)][0], symbols)
            if symbols != audited[module] or any(
                {entry.split(" : ", 1)[0] for entry in symbol["assumptions"]} - set(found["support_axioms"])
                    for symbol in symbols):
                raise ValueError("native assumption replay differs from exact declaration audit")
            bindings = classified[module]["alias_audits"]
            aliases = alias_symbols(bindings)
            label = "alias-assumptions-" + str(index)
            check_query(label, proofaudit.assumption_query(module, aliases))
            proofaudit.assumptions(streams[label][0], aliases)
            if aliases_audited[module] != {"bindings": bindings, "audits": aliases} or any(
                {entry.split(" : ", 1)[0] for entry in symbol["assumptions"]} - set(found["support_axioms"])
                    for symbol in aliases):
                raise ValueError("native alias assumption replay differs or adds an undeclared assumption")
        return None

    replay_dataset("support", modules)
    control_report = replay_dataset("control", spec["targets"])
    hidden = spec["hidden_assumptions"]
    for label, entry in native_refusals.items():
        check_query(label, (side / "tools/rocq-census" / entry["source"]).read_text(encoding="utf-8"))
        for key, value in entry.get("environment", {}).items():
            if commands[label]["native_environment"].get(key) != value:
                raise ValueError("native refusal invocation differs from its reviewed control")
    check_query("native-hidden-assumptions", (side / "tools/rocq-census" / hidden["source"]).read_text(encoding="utf-8"))
    symbols = hidden_assumption_audit(streams["native-hidden-assumptions"][0], hidden["symbols"])
    if load(artifact_root / "native-control-verdicts.json") != {"schema": spec["schema"], "status": "passed",
            "adapter": control_report, "hidden_assumptions": symbols, "native_refusals": sorted(spec["refusals"])}:
        raise ValueError("native control verdict differs from raw replay")
    for name, expected in {"support": found["support_axioms"],
            **{name: entry["expected_axioms"] for name, entry in found["probes"].items()}}.items():
        command = commands["kernel-" + name]
        roots = modules if name == "support" else ["Qualification." + name]
        if executable_tail(command) != ["rocqchk", "-silent", "-o", *support_map, *load_paths["probes"], *roots]:
            raise ValueError("recursive kernel check omitted a root or changed its locked settings")
        kernel_reading(command["exit"], *streams["kernel-" + name], expected)
    return row


def freeze_sources(campaign: Campaign, found: dict[str, Any], pristine: Path,
                   candidate: Path, mappings: list[str]) -> None:
    root, side = campaign.root, campaign.side
    frozen = load(asset(side, found["frozen_inventory"]))
    for index, row in enumerate(frozen["queries"]):
        query = root / ("Frozen_" + str(index) + ".v")
        query.write_text(row["query"], encoding="utf-8", newline="")
        readings: list[str] = []
        for name, tree in (("baseline", pristine / "_build/default/src-stdpp"),
                           ("candidate", candidate / "src-stdpp")):
            result = campaign.run("frozen-" + str(index) + "-" + name,
                campaign.executable(["rocq", "c", *mappings, "-R", str(tree), "SailStdpp", "-q", str(query)]), root)
            readings.append(result.stdout + result.stderr)
            query.with_suffix(".vo").unlink(missing_ok=True)
        if hashlib.sha256(row["query"].encode()).hexdigest() != row["query_sha256"]:
            raise ValueError("frozen query text differs from reviewed query")
        if readings[0] != readings[1] or hashlib.sha256(readings[0].encode()).hexdigest() != row["baseline_sha256"]:
            raise ValueError("frozen elaborated reading differs")


def qualify(campaign: Campaign, found: dict[str, Any], imported: Path | None) -> None:
    root, side = campaign.root, campaign.side
    os.chdir(root)
    bootstrap_instrument.system_packages(True)
    (root / "bin").mkdir()
    opam_client.install(root / "bin/opam", platform.machine())
    campaign.environment["PATH"] = str(root / "bin") + os.pathsep + os.environ.get("PATH", "")
    for index, command in enumerate(opam_client.remaining_route(root / "opam")):
        campaign.run("root-" + str(index), list(command), root)
    base_lock = asset(side, found["base_lock"])
    campaign.opam("create", ["switch", "create", SWITCH, "--empty", "--no-switch",
                            "--repos=rocq-released,default", "-y"])
    patch_files = {Path(entry["path"]).name: asset(side, entry).read_bytes() for entry in found["patches"]}
    original_archive = root / "metadata-source.tar.gz"
    download(found["source"], original_archive)
    metadata_source = extract(original_archive, root / "metadata-source")
    license_path = metadata_source / "LICENSE"
    if receipts.digest(license_path) != found["source_license_sha256"]:
        raise ValueError("original source license differs")
    extra_files = {**patch_files, "Sail-Support-LICENSE": license_path.read_bytes()}
    (campaign.upload / "Sail-Support-LICENSE").write_bytes(license_path.read_bytes())
    if imported is None:
        campaign.opam("base-import", ["switch", "import", str(base_lock), "--switch=" + SWITCH, "--keep-build-dir", "-y"])
        compatibility = root / "compatibility-repository"
        package = compatibility / "packages/rocq-sail-stdpp/rocq-sail-stdpp.0.20.3"
        (package / "files").mkdir(parents=True)
        (compatibility / "repo").write_text('opam-version: "2.0"\n', encoding="utf-8")
        upstream_metadata = metadata_source / "rocq-sail-stdpp.opam"
        if receipts.digest(upstream_metadata) != found["package_metadata_source_sha256"]:
            raise ValueError("original source package metadata differs")
        metadata = upstream_metadata.read_text(encoding="utf-8")
        if any(re.search(r"(?m)^" + field + r"\s*:", metadata)
               for field in ("patches", "extra-files", "url")):
            raise ValueError("unsupported upstream package metadata fields")
        names = list(patch_files)
        metadata += '\npatches: [' + ' '.join(json.dumps(name) for name in names) + ']\n'
        metadata += 'extra-files: [' + ' '.join(
            '[' + json.dumps(name) + ' ' + json.dumps('sha256=' + hashlib.sha256(extra_files[name]).hexdigest()) + ']'
            for name in extra_files) + ']\n'
        metadata += 'url { src: ' + json.dumps(found["source"]["url"]) + ' checksum: ' + json.dumps(
            'sha256=' + found["source"]["sha256"]) + ' }\n'
        (package / "opam").write_text(metadata, encoding="utf-8", newline="")
        (campaign.upload / "package-metadata.txt").write_text(metadata, encoding="utf-8", newline="")
        for name, contents in extra_files.items():
            (package / "files" / name).write_bytes(contents)
        campaign.opam("repository", ["repository", "add", "source-compat", compatibility.as_uri(),
                                     "--switch=" + SWITCH, "--dont-select", "-y"])
        campaign.opam("repositories", ["repository", "set-repos", "source-compat", "rocq-released",
                                       "default", "--switch=" + SWITCH])
        campaign.opam("package-build-tests", ["install", "--switch=" + SWITCH, "--with-test", "--keep-build-dir",
                                              "rocq-stdpp-bitvector.1.13.0", "rocq-sail-stdpp.0.20.3", "-y"])
    else:
        snapshot_metadata(imported.read_text(encoding="utf-8"), extra_files, found["source"]["sha256"])
        campaign.opam("snapshot-import", ["switch", "import", str(imported), "--switch=" + SWITCH, "--keep-build-dir", "-y"])
        campaign.opam("imported-package-tests", ["reinstall", "--switch=" + SWITCH, "--with-test", "--keep-build-dir",
                                                 "rocq-sail-stdpp.0.20.3", "-y"])
    campaign.opam("invariant", ["switch", "set-invariant", "--switch=" + SWITCH,
                               "ocaml-base-compiler.5.4.1", "-y"])
    campaign.environment.update(OPAMSWITCH=SWITCH, OPAM_SWITCH_PREFIX=str(root / "opam" / SWITCH))
    listed = campaign.opam("closure", ["list", "--switch=" + SWITCH, "--installed", "--short",
                                      "--columns=name,version,pin", "--color=never"])
    closure = bootstrap_instrument.parse_closure(listed.stdout)
    same_closure(closure, expected_closure(side, found))
    campaign.report["installed_closure"] = closure
    archive = root / "support.tar.gz"
    download(found["source"], archive)
    pristine = extract(archive, root / "baseline-source")
    candidate = extract(archive, root / "candidate-source")
    for index, entry in enumerate(found["patches"]):
        patch = asset(side, entry)
        for tree in ([pristine, candidate] if entry["stage"] == "axiom" else [candidate]):
            campaign.run("patch-" + str(index) + "-" + tree.parent.name,
                         ["patch", "--fuzz=0", "-p1", "-i", str(patch)], tree)
    installed = root / "opam" / SWITCH
    native_metadata = installed / ".opam-switch/packages/rocq-sail-stdpp.0.20.3/opam"
    metadata_bytes = native_metadata.read_bytes()
    snapshot_metadata(metadata_bytes.decode("utf-8"), extra_files, found["source"]["sha256"])
    (campaign.upload / "package-metadata.txt").write_bytes(metadata_bytes)
    lib = Path(campaign.opam("lib", ["var", "lib", "--switch=" + SWITCH]).stdout.strip())
    where = Path(campaign.run("where", campaign.executable(["rocq", "c", "-where"]), root).stdout.strip())
    stdpp = lib / "coq/user-contrib/stdpp"
    corelib, stdlib = where / "theories", where / "user-contrib/Stdlib"
    mappings = ["-boot", "-R", str(corelib), "Corelib", "-Q", str(stdlib), "Stdlib",
                "-Q", str(stdpp), "stdpp"]
    if not all(path.is_dir() for path in (corelib, stdlib, stdpp)):
        raise ValueError("locked dependency load paths absent")
    # The baseline uses its package settings, including warnings; it supplies the
    # frozen reading alone. The candidate uses only the consumer's existing flags.
    campaign.run("baseline-build", campaign.executable(["dune", "build", "-p", "rocq-sail-stdpp",
                  "-j", "2", "@install"]), pristine)
    candidate_map = [*mappings, "-R", str(candidate / "src-stdpp"), "SailStdpp"]
    order = campaign.run("dependency-order", campaign.executable(["rocq", "dep", "-sort", *candidate_map,
                         *[str(path) for path in sorted((candidate / "src-stdpp").glob("*.v"))
                           if path.stem != "MachineWordTest"]]), root).stdout.split()
    selected = [Path(name) for name in order if Path(name).parent == candidate / "src-stdpp"]
    if (len(selected) != 29 or len(set(selected)) != 29
            or {path.stem for path in selected} != set(found["support_modules"])):
        raise ValueError("strict support dependency order does not cover exact selected closure")
    for index, source in enumerate(selected):
        campaign.run("strict-" + str(index), campaign.executable(["rocq", "c", *candidate_map,
                      *STRICT, str(source)]), root, strict=True)
    campaign.report["native_sources_before"] = native_sources(side)
    campaign.report["native_runtime_before"] = native_runtime(campaign)
    plugin, control_inputs = prepare_native(campaign, candidate_map)
    probes = root / "probes"
    probes.mkdir()
    for name, entry in found["probes"].items():
        source = probes / (name + ".v")
        source.write_bytes(asset(side, entry).read_bytes())
        campaign.run("probe-compile-" + name, campaign.executable(["rocq", "c", *candidate_map,
                     "-Q", str(probes), "Qualification", *STRICT, str(source)]), root, strict=True)
    input_roots = [installed / "bin", installed / "lib", installed / ".opam-switch/build",
                   candidate / "src-stdpp", probes, plugin, control_inputs, root / "bin"]
    campaign.report["native_load_paths"] = {"support": candidate_map,
        "probes": ["-Q", str(probes), "Qualification"], "controls": ["-Q", str(control_inputs), ""]}
    inputs = identity_tree(input_roots)
    write(campaign.upload / "input-identities-before.json", inputs)
    audit_sources(campaign, found, selected, candidate_map)
    freeze_sources(campaign, found, pristine, candidate, mappings)
    native_controls(campaign, [*candidate_map, "-Q", str(control_inputs), ""])
    for name, roots, expected in [("support", ["SailStdpp." + path.stem for path in selected], found["support_axioms"]),
                                *[(name, ["Qualification." + name], entry["expected_axioms"])
                                  for name, entry in found["probes"].items()]]:
        result = campaign.run("kernel-" + name, campaign.executable(["rocqchk", "-silent", "-o",
                              *candidate_map, "-Q", str(probes), "Qualification", *roots]), root)
        names = kernel_reading(result.returncode, result.stdout, result.stderr, expected)
        campaign.report.setdefault("kernel_contexts", {})[name] = names
    publish_native_qualification(campaign, ["SailStdpp." + path.stem for path in selected], input_roots)
    exported = campaign.upload / "sail-support.lock"
    campaign.opam("export", ["switch", "export", "--full", "--freeze", "--switch=" + SWITCH, str(exported)])
    snapshot_metadata(exported.read_text(encoding="utf-8"), extra_files, found["source"]["sha256"])
    if imported is not None and imported.read_bytes() != exported.read_bytes():
        raise ValueError("independent full frozen re-export is not byte-identical")
    evidence = {name: {"sha256": receipts.digest(campaign.upload / name),
                       "bytes": (campaign.upload / name).stat().st_size}
                for name in ("input-identities.json", "native-assumptions.json", "package-metadata.txt",
                             "Sail-Support-LICENSE", "sail-support.lock", "native-census-qualified.json")}
    campaign.report.update(status="passed", export_sha256=receipts.digest(exported),
                           export_bytes=exported.stat().st_size, reexport_identical=imported is not None,
                           evidence=evidence)
    campaign.save()


def required_labels(phase: str, frozen_count: int) -> set[str]:
    phases = {"build": {"base-import", "package-build-tests", "repository", "repositories"},
              "import": {"snapshot-import", "imported-package-tests"}}
    if phase not in phases:
        raise ValueError("unsupported campaign phase")
    return {"create", "invariant", "closure", "baseline-build", "dependency-order", "where", "lib",
            "native-plugin-build", "native-control-compile", "support-native-census", "control-native-census",
            "native-signature-refusal", "native-unsupported-refusal", "native-hidden-assumptions",
            "kernel-support", "kernel-term", "kernel-eqdep", "kernel-real", "kernel-notation", "export",
            *("probe-compile-" + name for name in ("term", "eqdep", "real", "notation")),
            *(label + str(index) for index in range(29)
              for label in ("strict-", "inventory-", "assumptions-", "alias-assumptions-")),
            *("frozen-" + str(index) + "-" + side_name for index in range(frozen_count)
              for side_name in ("baseline", "candidate")), *phases[phase]}


def join(artifacts: Path | None, side: Path, revision: str, root: Path) -> None:
    if artifacts is None:
        raise ValueError("join needs same-run artifacts")
    needs = decode(os.environ["CAMPAIGN_NEEDS"])
    if not isinstance(needs, dict):
        raise TypeError("campaign needs must be an object")
    if any(needs.get(name, {}).get("result") != "success" for name in ("plan", "build", "import")):
        raise ValueError("campaign job failed, skipped or supplied no success verdict")
    found = load(side / RECIPE)
    frozen_count = len(load(asset(side, found["frozen_inventory"]))["queries"])
    expected_contexts = {"support": found["support_axioms"],
                         **{name: entry["expected_axioms"] for name, entry in found["probes"].items()}}
    reports: list[dict[str, Any]] = []
    for path in artifacts.glob("*/receipt.json"):
        row = load(path)
        if (row["status"] != "passed" or row.get("cold") is not True or row["revision"] != revision
                or row["dispatch_revision"] != os.environ["GITHUB_SHA"]
                or row["run_id"] != os.environ["GITHUB_RUN_ID"]
                or row["run_attempt"] != os.environ["GITHUB_RUN_ATTEMPT"]
                or row["recipe_sha256"] != receipts.digest(side / RECIPE)):
            raise ValueError("artifact does not bind this passing campaign")
        if receipts.digest(path.parent / "sail-support.lock") != row["export_sha256"]:
            raise ValueError("artifact snapshot differs from recorded export")
        native = validate_native_qualification(path.parent, side, revision,
            run_id=os.environ["GITHUB_RUN_ID"], run_attempt=os.environ["GITHUB_RUN_ATTEMPT"],
            dispatch_revision=os.environ["GITHUB_SHA"])
        evidence = row.get("evidence")
        expected_files = {"input-identities.json", "native-assumptions.json", "package-metadata.txt",
                          "Sail-Support-LICENSE", "sail-support.lock", "native-census-qualified.json"}
        if not isinstance(evidence, dict) or set(evidence) != expected_files:
            raise ValueError("artifact lacks its complete source/tool/object identity evidence")
        for name, identity in evidence.items():
            retained = path.parent / name
            if (receipts.digest(retained) != identity["sha256"]
                    or retained.stat().st_size != identity["bytes"]):
                raise ValueError("artifact evidence bytes differ")
        if receipts.digest(path.parent / "Sail-Support-LICENSE") != found["source_license_sha256"]:
            raise ValueError("artifact license differs from the original source notice")
        identities = load(path.parent / "input-identities.json")
        if not identities or any(not isinstance(value, str) or SHA256.fullmatch(value) is None
                                 for value in identities.values()):
            raise ValueError("artifact input identity population is empty or malformed")
        commands = row["commands"]
        if commands[:len(native["commands"])] != native["commands"]:
            raise ValueError("full carriage receipt differs from its native qualification commands")
        labels = [entry["label"] for entry in commands]
        required = required_labels(row["phase"], frozen_count)
        if len(labels) != len(set(labels)) or not required <= set(labels):
            raise ValueError("artifact lacks complete strict/recursive checks")
        for command in commands:
            log = path.parent / command["log"]
            expected_refusal = command.get("expected_refusal") is True and command in native["commands"]
            if (log.parent != path.parent or (command["exit"] != 0 and not expected_refusal)
                    or receipts.digest(log) != command["log_sha256"]
                    or (command["strict"] and log.read_bytes().strip())):
                raise ValueError("artifact command or diagnostics disagree")
            if command["label"].startswith("kernel-"):
                name = command["label"].removeprefix("kernel-")
                kernel_reading(command["exit"], "", log.read_text(encoding="utf-8"), expected_contexts[name])
        reports.append(row)
    if (len(reports) != 2 or {row["phase"] for row in reports} != {"build", "import"}
            or len({row["export_sha256"] for row in reports}) != 1
            or not next(row for row in reports if row["phase"] == "import")["reexport_identical"]):
        raise ValueError("cold source carriage lacks matching successful independent evidence")
    write(root / "report.json", {"schema": SCHEMA, "status": "passed", "jobs": reports})


def checked_import(snapshot: Path | None, expected: str | None) -> None:
    if snapshot is None or receipts.digest(snapshot) != expected:
        raise ValueError("same-run snapshot checksum differs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "build", "import", "join"))
    parser.add_argument("--side", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args(argv)
    campaign: Campaign | None = None
    try:
        revision = os.environ["TESTED_REVISION"]
        guarded_revision(args.side, revision, os.environ["GITHUB_SHA"], os.environ["GITHUB_REF"])
        found = recipe(args.side)
        if args.command == "plan":
            write(args.root / "plan.json", {"schema": SCHEMA, "revision": revision,
                  "dispatch_revision": os.environ["GITHUB_SHA"], "recipe_sha256": receipts.digest(args.side / RECIPE)})
            return 0
        if args.command == "join":
            join(args.artifacts, args.side, revision, args.root)
            return 0
        if args.command == "import":
            checked_import(args.snapshot, args.expected_sha256)
        campaign = Campaign(args.root, args.side, args.command)
        qualify(campaign, found, args.snapshot if args.command == "import" else None)
        if bool(output := os.environ.get("GITHUB_OUTPUT")):
            with Path(output).open("a", encoding="utf-8", newline="") as stream:
                stream.write("snapshot_sha256=" + campaign.report["export_sha256"] + "\n")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        if campaign is not None:
            campaign.report.update(status="failed", reason=str(error))
            campaign.save()
        else:
            write(args.root / ("failure.json" if args.command in {"plan", "join"} else "upload/failure.json"),
                  {"schema": SCHEMA, "status": "failed", "reason": str(error)})
        print("FAIL sail-support-carriage: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
