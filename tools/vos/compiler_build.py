# SPDX-License-Identifier: Apache-2.0
"""Public framing for the private contained-compiler build driver.

The private validator owns compiler and kernel semantics. The lane-local index is
only a candidate hint; no receipt here makes a pending audit reusable.
"""

import ast
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vos import env
from vos.jsonutil import finite_float, unique_object

PROTOCOL = "verifiedos-contained-compiler-build/1"
INDEX_PROTOCOL = "verifiedos-contained-compiler-index/1"
MAX_JSON = 4 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}")
REVISION = re.compile(r"[0-9a-f]{40}")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON:
        raise ValueError("missing, linked or oversized JSON artifact")
    raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                     parse_float=finite_float,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")))
    if not isinstance(raw, dict):
        raise TypeError("JSON artifact must be an object")
    return raw


def _absolute(path: Path) -> Path:
    if not path.is_absolute() or "%" in str(path):
        raise ValueError("paths must be absolute and expanded")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("symlink paths are unsupported")
    return path.resolve()


def contained(path: Path, root: Path, *, equal: bool = False) -> Path:
    selected, boundary = _absolute(path), _absolute(root)
    if not selected.is_relative_to(boundary) or (selected == boundary and not equal):
        raise ValueError("path escapes its declared root")
    return selected


def _atomic(path: Path, value: dict[str, Any]) -> None:
    contained(path, path.parent)
    data = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     prefix=".compiler-build-", dir=path.parent,
                                     delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _review_imports(root: Path, files: dict[str, str]) -> None:
    """Refuse undeclared local modules, packages and dynamic import targets before launch."""
    for name in files:
        path = contained(root / name, root)
        if path.suffix != ".py":
            raise ValueError("unsupported driver closure file")
        modules: list[str] = []
        try:
            syntax = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as error:
            raise ValueError("driver closure contains invalid Python") from error
        for node in ast.walk(syntax):
            if isinstance(node, ast.Import):
                if any(alias.name.split(".")[0] == "importlib" for alias in node.names):
                    raise ValueError("dynamic driver import tooling is unsupported")
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level or node.module is None:
                    raise ValueError("relative driver imports are unsupported")
                if node.module.split(".")[0] == "importlib":
                    raise ValueError("dynamic driver import tooling is unsupported")
                modules.append(node.module)
                modules.extend(node.module + "." + alias.name for alias in node.names
                               if alias.name != "*")
            elif isinstance(node, ast.Call) and (
                    (isinstance(node.func, ast.Name) and node.func.id == "__import__")
                    or (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")):
                if (not node.args or not isinstance(node.args[0], ast.Constant)
                        or not isinstance(node.args[0].value, str)
                        or node.args[0].value.startswith(".")):
                    raise ValueError("dynamic driver import target is unsupported")
                modules.append(node.args[0].value)
        for module in modules:
            parts = module.split(".")
            for length in range(1, len(parts) + 1):
                member = root.joinpath(*parts[:length])
                for imported in (member.with_suffix(".py"), member / "__init__.py"):
                    checked = contained(imported, root)
                    if checked.is_file() and checked.relative_to(root).as_posix() not in files:
                        raise ValueError("unreviewed project-local driver import")


def driver_identity(root: Path, manifest: Path) -> dict[str, str]:
    """Read a reviewed closure manifest; never import private helper code here."""
    boundary = _absolute(root)
    manifest = _absolute(manifest)
    raw = read_json(manifest)
    files = raw.get("files")
    if (raw.get("schema") != "verifiedos-contained-compiler-driver/1"
            or raw.get("helper_root") != str(boundary)
            or not isinstance(files, dict)
            or not {"build.py", "qualify.py", "audit.py", "reuse.py"} <= files.keys()):
        raise ValueError("driver manifest must enumerate its reviewed root and closure")
    identities = {"manifest_sha256": digest(manifest)}
    for name, expected in files.items():
        if (not isinstance(name, str) or not name or "\\" in name
                or Path(name).is_absolute() or ".." in Path(name).parts
                or not isinstance(expected, str) or SHA256.fullmatch(expected) is None):
            raise ValueError("unsupported driver manifest entry")
        path = contained(boundary / name, boundary)
        if not path.is_file() or digest(path) != expected:
            raise ValueError("reviewed driver closure bytes differ")
        identities[name] = expected
    _review_imports(boundary, files)
    return identities


def _identity(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def _seconds(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


@dataclass(frozen=True)
class Settings:
    source: Path
    source_revision: str
    lane_root: Path
    out: Path
    cache: Path
    driver_root: Path
    driver_manifest: Path
    opam_root: Path
    switch: str
    lock: Path
    configuration: Path
    kernel_profile: str
    jobs: int = 1
    profile: bool = False
    fresh: bool = False
    reuse_from: Path | None = None

    def validate(self, checkout: Path, *, status: bool = False) -> None:
        if REVISION.fullmatch(self.source_revision) is None:
            raise ValueError("source revision must be an immutable full Git object id")
        if type(self.jobs) is not int or self.jobs < 1:
            raise ValueError("job limit must be positive")
        if self.kernel_profile not in {"standard", "vm"} or not self.switch.strip():
            raise ValueError("unsupported kernel profile or missing switch")
        if self.fresh and self.reuse_from is not None:
            raise ValueError("--fresh cannot also request an explicit reuse candidate")
        lane = _absolute(self.lane_root)
        out, cache = contained(self.out, lane), contained(self.cache, lane)
        if out == cache or out.is_relative_to(cache) or cache.is_relative_to(out):
            raise ValueError("output and cache roots must be separate")
        for path in (lane, self.source, self.driver_root, self.opam_root):
            actual = _absolute(path)
            if actual.is_relative_to(checkout.resolve()):
                raise ValueError("native compiler paths must remain outside this checkout")
        for path in (self.lock, self.configuration, self.driver_manifest):
            _absolute(path)
            if not path.is_file():
                raise ValueError("required input artifact is absent")
        if not self.source.is_dir() or not self.driver_root.is_dir():
            raise ValueError("source and driver roots must exist")
        if self.reuse_from is not None:
            _absolute(self.reuse_from)
        if not status and out.exists():
            raise ValueError("output collision; choose a new owned output directory")


def context(settings: Settings, driver: dict[str, str]) -> dict[str, Any]:
    """Scheduling limits do not change the compilation or acceptance profile."""
    return {"source": str(_absolute(settings.source)), "source_revision": settings.source_revision,
            "lock_sha256": digest(settings.lock), "configuration": read_json(settings.configuration),
            "kernel_profile": settings.kernel_profile, "driver": driver,
            "opam_root": str(_absolute(settings.opam_root)), "switch": settings.switch}


def candidate(settings: Settings, key: str) -> tuple[Path | None, str]:
    if settings.fresh:
        return None, "fresh: both reuse tiers and index bypassed"
    if settings.reuse_from is not None:
        return _absolute(settings.reuse_from), "explicit candidate requires backend validation"
    index = settings.cache / "index.json"
    if not index.exists():
        return None, "default: no prior controller output"
    try:
        return _index_candidate(settings, key, index)
    except (OSError, ValueError, TypeError):
        return None, "default: stale or invalid index candidate; execute necessary phases"


def _index_candidate(settings: Settings, key: str, index: Path) -> tuple[Path | None, str]:
    raw = read_json(index)
    if raw.get("protocol") != INDEX_PROTOCOL or not isinstance(raw.get("entries"), dict):
        raise ValueError("unsupported cache index")
    entry = raw["entries"].get(key)
    if entry is None:
        return None, "default: no matching source/lock/configuration/profile/driver context"
    if not isinstance(entry, dict) or set(entry) != {"out", "receipt_sha256"}:
        raise ValueError("malformed index entry")
    if not isinstance(entry["out"], str) or not isinstance(entry["receipt_sha256"], str):
        raise TypeError("malformed index entry")
    previous = contained(Path(entry["out"]), settings.lane_root)
    if previous.is_relative_to(settings.cache) or settings.cache.is_relative_to(previous):
        raise ValueError("index candidate overlaps cache")
    receipt = previous / "controller-result.json"
    if digest(receipt) != entry["receipt_sha256"]:
        raise ValueError("prior controller receipt differs")
    report = read_json(receipt)
    if (report.get("protocol") != PROTOCOL or report.get("context_sha256") != key
            or report.get("operation") != "build" or report.get("status") != "passed"):
        raise ValueError("prior controller result does not match")
    target = report.get("cache_candidate")
    if not isinstance(target, str):
        raise TypeError("prior controller result lacks a backend candidate")
    return _absolute(Path(target)), "default: prior validated output requires backend revalidation"


def _index(settings: Settings, key: str, receipt: Path) -> None:
    """Only a current successful controller operation may introduce an output."""
    index = settings.cache / "index.json"
    entries: dict[str, Any] = {}
    if index.exists():
        try:
            raw = read_json(index)
            if raw.get("protocol") == INDEX_PROTOCOL and isinstance(raw.get("entries"), dict):
                entries = raw["entries"]
        except (OSError, ValueError, TypeError):
            pass
    entries[key] = {"out": str(settings.out.resolve()), "receipt_sha256": digest(receipt)}
    _atomic(index, {"protocol": INDEX_PROTOCOL, "entries": entries})


def _result(raw: dict[str, Any], request: dict[str, Any], *, code: int) -> None:
    """Check protocol relationships, leaving proof and artifact semantics private."""
    for name in ("protocol", "operation", "source_revision", "driver_manifest_sha256", "policy"):
        if raw.get(name) != request[name]:
            raise ValueError("driver result disagrees with its request")
    if raw.get("outcome") not in {"complete", "status", "unavailable", "refused"}:
        raise ValueError("unsupported driver outcome")
    if raw.get("effective_policy") not in {"fresh", "complete-reuse", "compilation-reuse", "unavailable"}:
        raise ValueError("unsupported effective policy")
    phases = raw.get("phases")
    if not isinstance(phases, dict) or set(phases) != {"compile", "queries", "kernel", "classification"}:
        raise ValueError("driver result must name all four phases")
    actions: dict[str, str] = {}
    for name, phase in phases.items():
        if (not isinstance(phase, dict) or phase.get("action") not in {"executed", "reused", "not_run"}
                or phase.get("status") not in {"passed", "not_run"}):
            raise ValueError("unsupported phase record")
        action = phase["action"]
        actions[name] = action
        if not _seconds(phase.get("seconds")) or (action != "executed" and phase["seconds"] != 0):
            raise ValueError("historical or absent phases cannot report new execution time")
        basis, seconds = phase.get("basis"), phase.get("original_seconds")
        if action == "reused":
            if (not isinstance(basis, str) or SHA256.fullmatch(basis) is None
                    or (seconds is not None and not _seconds(seconds))
                    or phase["status"] != "passed"):
                raise ValueError("reused phase lacks complete historical basis and timing")
        elif basis is not None or seconds is not None:
            raise ValueError("phase has invalid basis or timing")
        if (action == "not_run") != (phase["status"] == "not_run"):
            raise ValueError("phase status contradicts its action")
    if not isinstance(raw.get("reuse_reason"), str) or type(raw.get("inputs_stable")) is not bool:
        raise ValueError("driver result lacks validation status")
    if actions["kernel"] == "reused" and set(actions.values()) != {"reused"}:
        raise ValueError("whole-set kernel reuse must reuse all qualification phases")
    if request["operation"] == "status":
        if "executed" in actions.values() or raw["outcome"] == "complete":
            raise ValueError("status attempted execution")
        if raw["outcome"] == "status" and (code != 0 or raw["inputs_stable"] is not True):
            raise ValueError("status has no successful stable validation")
    elif raw["outcome"] == "status":
        raise ValueError("build returned a status-only result")
    if raw["outcome"] == "complete":
        if code != 0 or raw["inputs_stable"] is not True or "not_run" in actions.values():
            raise ValueError("complete result has no stable successful whole operation")
        if request["fresh"] and set(actions.values()) != {"executed"}:
            raise ValueError("fresh request reused earlier execution")
        if request["profile"] and actions["kernel"] != "executed":
            raise ValueError("new profile output requires kernel execution")
        if actions["kernel"] == "executed" and any(actions[name] != "executed"
                                                    for name in ("queries", "classification")):
            raise ValueError("new kernel execution needs new queries and classification")
        if "reused" in actions.values() and not isinstance(raw.get("basis"), dict):
            raise ValueError("reuse result lacks retained original basis")
        expected_policy = ("complete-reuse" if actions["kernel"] == "reused" else
                           "compilation-reuse" if actions["compile"] == "reused" else "fresh")
        if raw["effective_policy"] != expected_policy:
            raise ValueError("effective policy contradicts executed phases")
        for name in ("compiler", "receipt"):
            value = raw.get(name)
            if not isinstance(value, str) or not _absolute(Path(value)).is_file():
                raise ValueError("complete result lacks retained native artifact")
        receipt = contained(Path(raw["receipt"]), Path(request["out"]))
        if read_json(receipt) != raw:
            raise ValueError("retained operation receipt differs from driver response")
        qualified = raw.get("qualification_receipt")
        if (not isinstance(qualified, str) or raw.get("cache_candidate") != qualified
                or not _absolute(Path(qualified)).is_file()):
            raise ValueError("complete result lacks its retained qualification candidate")


def run(settings: Settings, checkout: Path, *, status: bool = False) -> dict[str, Any]:
    settings.validate(checkout, status=status)
    before = driver_identity(settings.driver_root, settings.driver_manifest)
    snapshot = context(settings, before)
    key = _identity(snapshot)
    started = time.perf_counter()

    def invoke() -> dict[str, Any]:
        selected, reason = candidate(settings, key)
        policy = "fresh" if settings.fresh else "explicit" if settings.reuse_from is not None else "default"
        with tempfile.TemporaryDirectory(prefix="vos-compiler-build-") as temporary:
            scratch = Path(temporary).resolve()
            response = scratch / "response.json"
            request = {"protocol": PROTOCOL, "operation": "status" if status else "build",
                       "source": str(settings.source.resolve()), "source_revision": settings.source_revision,
                       "out": str(settings.out.resolve()), "lane_root": str(settings.lane_root.resolve()),
                       "cache": str(settings.cache.resolve()), "driver_manifest": str(settings.driver_manifest.resolve()),
                       "driver_manifest_sha256": before["manifest_sha256"],
                       "opam_root": str(settings.opam_root.resolve()), "switch": settings.switch,
                       "lock": str(settings.lock.resolve()), "configuration": snapshot["configuration"],
                       "kernel_profile": settings.kernel_profile, "jobs": settings.jobs,
                       "profile": settings.profile, "fresh": settings.fresh,
                       "reuse_from": str(selected) if selected is not None else None,
                       "policy": policy, "response_json": str(response)}
            request_path = scratch / "request.json"
            _atomic(request_path, request)
            # No shell, environment replacement or exposure of private diagnostics.
            done = subprocess.run([sys.executable, str(settings.driver_root / "build.py"),
                                   "--request-json", str(request_path)], cwd=scratch,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            raw = read_json(response)
            _result(raw, request, code=done.returncode)
        if before != driver_identity(settings.driver_root, settings.driver_manifest) or snapshot != context(settings, before):
            raise ValueError("driver or request inputs changed during the operation")
        validation = raw.get("validation_seconds")
        if ((not _seconds(validation) and not (
                validation is None and raw["outcome"] in {"refused", "unavailable"}))
                or not _seconds(raw.get("operation_seconds"))):
            raise ValueError("driver result lacks current validation/operation timing")
        report = {**raw, "context_sha256": key, "controller_policy": policy,
                  "candidate_reason": reason, "controller_operation_seconds": time.perf_counter() - started,
                  "driver_identity": before, "status": "passed" if raw["outcome"] == "complete" else raw["outcome"]}
        if not status:
            receipt = settings.out / "controller-result.json"
            _atomic(receipt, report)
            if raw["outcome"] == "complete":
                _index(settings, key, receipt)
        return report

    if status:
        return invoke()
    settings.lane_root.mkdir(parents=True, exist_ok=True)
    for path in (settings.out, settings.cache):
        contained(path.parent / (path.name + ".lock"), settings.lane_root)
    with (env.hold_lock(settings.cache, "contained compiler cache operation"),
          env.hold_lock(settings.out, "contained compiler output operation")):
        settings.validate(checkout)
        settings.cache.mkdir(parents=True, exist_ok=True)
        settings.out.mkdir(parents=True)
        return invoke()

