# SPDX-License-Identifier: Apache-2.0
"""Bounded Sail repair journals and byte-preserving compiler process receipts.

The journal records an agent's work; it does not edit sources, infer diagnostics,
accept behavior or authenticate an adversarially modified checkpoint. Linux/WSL
owns persistent journals and compiler logs so both entry paths share one lane.
"""

import base64
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from vos import env, receipts
from vos.cli import entry

SCHEMA = Path(__file__).resolve().parents[1] / "sail-assist.schema.json"
FROZEN = ("docs/requirements-register.md", "docs/hardware/isa-profile.md",
          "model/config/verifiedos.json")
INPUTS = ("model", "tools/opam/sail.lock", "tools/run.py", "tools/vos/env.py",
          "tools/vos/cli/model.py", "tools/vos/sailassist.py", "tools/vos/cli/sail_assist.py",
          "tools/vos/cli/__init__.py", "tools/vos/toolenv.py", "tools/uv.lock",
          "tools/pyproject.toml", "tools/sail-assist.schema.json")
SESSION = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")


def now_text() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError(f"invalid JSON number: {value}")


def _float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"JSON number exceeds finite precision: {value}")
    return parsed


def read_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                     parse_constant=_constant, parse_float=_float)
    if not isinstance(raw, dict):
        raise TypeError(f"{path}: expected a JSON object")
    return raw


def validate(value: dict[str, Any], kind: str) -> None:
    schema = read_json(SCHEMA)
    view = {"$schema": schema["$schema"], "$defs": schema["$defs"],
            "$ref": f"#/$defs/{kind}"}
    failure = next(iter(Draft202012Validator(view).iter_errors(value)), None)
    if failure:
        raise ValueError(f"{kind}: {failure.json_path}: {failure.message}")


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], cwd=root,
                          env={**os.environ, **env.git_env(root)}, capture_output=True,
                          check=False, timeout=60)
    if done.returncode:
        raise ValueError(done.stderr.decode("utf-8", errors="replace").strip())
    return done.stdout.decode("utf-8").strip()


def local_file(root: Path, relative: str) -> Path:
    if (not relative or "\\" in relative or ":" in relative or relative.startswith("/")
            or any(part in ("", ".", "..") for part in relative.split("/"))):
        raise ValueError(f"expected a checkout-relative regular file: {relative}")
    current = root
    for part in relative.split("/"):
        current /= part
        if current.is_symlink() or current.is_junction():
            raise ValueError(f"linked input is not supported: {relative}")
    if not current.is_file() or not current.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"missing local input: {relative}")
    return current


def manifest(root: Path) -> dict[str, str]:
    found = receipts.inputs(root, *INPUTS)
    for rel in found:
        if found[rel].startswith("gitlink:"):
            continue
        local_file(root, rel)
    return found


def frozen(root: Path, extra: list[str]) -> dict[str, str]:
    return {name: receipts.digest(local_file(root, name)) for name in sorted(set(FROZEN) | set(extra))}


def toolchain(scratch: Path) -> dict[str, Any]:
    """The selected binaries and Sail's own reported installed library bytes."""
    binaries = {name: receipts.digest(Path(found)) for name in ("sail", "z3")
                if (found := shutil.which(name)) is not None}
    binaries["python"] = receipts.digest(Path(sys.executable))
    libraries: dict[str, str] = {}
    library: str | None = None
    if compiler := shutil.which("sail"):
        result = subprocess.run([compiler, "--dir"], cwd=scratch, capture_output=True, check=False, timeout=15)
        if result.returncode:
            raise ValueError("cannot identify the selected Sail library with sail --dir")
        directory = Path(result.stdout.decode("utf-8").strip()).resolve()
        if not directory.is_dir():
            raise ValueError(f"Sail reported a missing library directory: {directory}")
        library = str(directory.parent)
        roots = (directory, directory.parent / "libsail/plugins")
        libraries = {path.relative_to(directory.parent).as_posix(): receipts.digest(path)
                     for owner in roots for path in sorted(owner.rglob("*")) if path.is_file()}
        if not libraries:
            raise ValueError("selected Sail library directory contains no files")
    return {"binaries": binaries, "library_root": library, "libraries": libraries}


def session_dir(lane: Path, name: str) -> Path:
    if not SESSION.fullmatch(name):
        raise ValueError("session must be 1..64 lowercase letters/digits/hyphens, starting with a letter")
    parent = lane / "sail-assist"
    result = parent / name
    for path in (lane, parent, result):
        if path.is_symlink() or path.is_junction():
            raise ValueError("session directories must not be links")
    return result


def save(directory: Path, journal: dict[str, Any]) -> None:
    validate(journal, "checkpoint")
    receipts.write(directory / "checkpoint.json", journal)


def load(directory: Path) -> dict[str, Any]:
    path = directory / "checkpoint.json"
    if path.is_symlink() or path.is_junction():
        raise ValueError("checkpoint must not be linked")
    journal = read_json(path)
    validate(journal, "checkpoint")
    if [attempt["number"] for attempt in journal["attempts"]] != list(range(1, len(journal["attempts"]) + 1)):
        raise ValueError("checkpoint attempt numbers must be consecutive")
    if len(journal["attempts"]) > journal["attempt_limit"]:
        raise ValueError("checkpoint exceeds its attempt budget")
    pending = [a["number"] for a in journal["attempts"] if a["outcome"] == "running"]
    expected = [len(journal["attempts"])] if journal["state"] == "running" else []
    if pending != expected or (journal["active_since"] is None) != (journal["state"] in ("paused", "closed")):
        raise ValueError("checkpoint state and active attempt disagree")
    replans = [r["after_attempt"] for r in journal["replans"]]
    if replans != sorted(replans) or any(n > len(journal["attempts"]) for n in replans):
        raise ValueError("checkpoint replans must refer to completed attempt positions")
    return journal


def active_seconds(journal: dict[str, Any], at: float | None = None) -> float:
    elapsed = float(journal["active_seconds"])
    if journal["active_since"] is not None:
        delta = (time.time() if at is None else at) - journal["active_since"]
        if delta < 0:
            raise ValueError("clock moved backwards; review the checkpoint before continuing")
        elapsed += delta
    return elapsed


def refusal(journal: dict[str, Any], at: float | None = None) -> str | None:
    if journal["state"] == "running":
        return "an attempt is running or was interrupted; inspect its logs and use recover"
    if journal["state"] in ("paused", "closed"):
        return f"session is {journal['state']}"
    if len(journal["attempts"]) >= journal["attempt_limit"]:
        return "attempt budget exhausted"
    if active_seconds(journal, at) >= journal["active_seconds_limit"]:
        return "active-time budget exhausted"
    after = journal["replans"][-1]["after_attempt"] if journal["replans"] else 0
    failures = 0
    for attempt in reversed(journal["attempts"][after:]):
        if attempt["outcome"] == "passed":
            break
        failures += 1
    if failures >= 3:
        return "three consecutive failures require a recorded replan"
    return None


def status(journal: dict[str, Any]) -> dict[str, Any]:
    elapsed = active_seconds(journal)
    reason = refusal(journal)
    return {"version": 1, "advisory_only": True, "checkpoint": journal,
            "active_seconds_now": elapsed, "remaining_seconds": max(0, journal["active_seconds_limit"] - elapsed),
            "can_check": reason is None, "reason": reason}


def initialize(root: Path, directory: Path, plan: dict[str, Any], attempt_limit: int = 12,
               seconds_limit: int = 1800) -> dict[str, Any]:
    validate(plan, "plan")
    if not 1 <= attempt_limit <= 1000 or not 1 <= seconds_limit <= 86400:
        raise ValueError("attempt limit must be 1..1000 and active seconds 1..86400")
    if (directory / "checkpoint.json").exists():
        raise ValueError("session already exists; use a new name")
    register = (root / FROZEN[0]).read_text(encoding="utf-8")
    known = set(re.findall(r"\bR-\d+-\d+[a-z]?\b", register))
    if missing := set(plan["requirements"]) - known:
        raise ValueError(f"unknown requirements: {sorted(missing)}")
    for name in plan["affected_paths"]:
        local_file(root, name)
    journal: dict[str, Any] = {
        "version": 1, "advisory_only": True, "state": "ready",
        "base_revision": _git(root, "rev-parse", "HEAD"), "created_at": now_text(),
        "plan": plan, "frozen_inputs": frozen(root, plan.get("frozen_paths", [])),
        "initial_inputs": manifest(root), "attempt_limit": attempt_limit,
        "active_seconds_limit": seconds_limit, "active_seconds": 0.0,
        "active_since": time.time(), "attempts": [], "replans": [],
        "next_action": "retrieve context and prepare one candidate", "completion": None,
    }
    save(directory, journal)
    return journal


def check_frozen(root: Path, journal: dict[str, Any]) -> None:
    if frozen(root, journal["plan"].get("frozen_paths", [])) != journal["frozen_inputs"]:
        raise ValueError("frozen requirement/profile inputs changed; review the contract and start a new session")
    _git(root, "merge-base", "--is-ancestor", journal["base_revision"], "HEAD")


def transition(root: Path, directory: Path, action: str, note: str) -> dict[str, Any]:
    journal = load(directory)
    if not note.strip():
        raise ValueError("a transition needs a nonempty reason or next action")
    if action == "recover":
        if journal["state"] != "running":
            raise ValueError("only an interrupted running attempt can be recovered")
        attempt = journal["attempts"][-1]
        attempt["outcome"] = "interrupted"
        attempt["finished_at"] = now_text()
        attempt["note"] = note
        # An unobserved process cannot refund an unknown duration. Preserve its
        # reserved remainder and require a separately reviewed new session.
        journal["active_seconds"] = float(journal["active_seconds_limit"])
        journal["active_since"] = None
        journal["state"] = "closed"
    else:
        if journal["state"] in ("running", "closed"):
            raise ValueError(f"cannot {action} a {journal['state']} session")
        check_frozen(root, journal)
        elapsed = active_seconds(journal)
        if action == "pause":
            journal.update(state="paused", active_seconds=elapsed, active_since=None)
        elif action == "resume":
            if journal["state"] != "paused":
                raise ValueError("only a paused session can resume")
            if elapsed >= journal["active_seconds_limit"] or len(journal["attempts"]) >= journal["attempt_limit"]:
                raise ValueError("session budget exhausted")
            journal.update(state="ready", active_since=time.time())
        elif action == "replan":
            journal["replans"].append({"after_attempt": len(journal["attempts"]), "at": now_text(), "reason": note})
        elif action == "finish":
            journal.update(state="closed", active_seconds=elapsed, active_since=None,
                           completion={"at": now_text(), "note": note, "acceptance_established": False})
        else:
            raise ValueError(f"unknown transition: {action}")
    journal["next_action"] = note
    save(directory, journal)
    return journal


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            if sys.platform == "win32":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def process(argv: list[str], cwd: Path, logs: Path, timeout: float) -> dict[str, Any]:
    """Run a fixed command, retaining exact bytes even on timeout/cancellation."""
    logs.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    started = now_text()
    code: int | None = None
    outcome = "completed"
    error: str | None = None
    with (logs.joinpath("stdout.bin").open("wb") as stdout,
          logs.joinpath("stderr.bin").open("wb") as stderr):
        try:
            child = subprocess.Popen(argv, cwd=cwd, stdout=stdout, stderr=stderr,
                                     start_new_session=sys.platform != "win32")
        except OSError as exc:
            outcome, error = "launch_error", str(exc)
        else:
            try:
                code = child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _stop(child)
                outcome, code = "timeout", child.wait()
            except KeyboardInterrupt:
                _stop(child)
                outcome, code = "cancelled", child.wait()
    elapsed = time.perf_counter() - start
    streams: dict[str, Any] = {}
    for name in ("stdout", "stderr"):
        path = logs / f"{name}.bin"
        size = path.stat().st_size
        inline = size <= 2_097_152
        streams[name] = {"path": str(path), "sha256": receipts.digest(path), "bytes": size,
                         "base64": base64.b64encode(path.read_bytes()).decode("ascii") if inline else None,
                         "inline_truncated": not inline}
    return {"command": argv, "cwd": str(cwd), "started_at": started, "finished_at": now_text(),
            "outcome": outcome, "exit_code": code, "elapsed_seconds": elapsed,
            "timeout_seconds": timeout, "launch_error": error, **streams}


def typecheck(root: Path, directory: Path, log_root: Path, change: str,
              timeout: float = 600) -> tuple[dict[str, Any], int]:
    if not change.strip() or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("a candidate needs a change description and a finite positive timeout")
    journal = load(directory)
    check_frozen(root, journal)
    if reason := refusal(journal):
        raise ValueError(reason)
    before = manifest(root)
    number = len(journal["attempts"]) + 1
    # Resolving binaries is diagnostic here: the child still records a missing
    # compiler as its actual failed invocation, rather than inventing an exit code.
    selected = toolchain(directory)
    remaining = journal["active_seconds_limit"] - active_seconds(journal)
    if remaining <= 0:
        raise ValueError("active-time budget exhausted")
    attempt: dict[str, Any] = {
        "number": number, "change": change, "started_at": now_text(), "finished_at": None,
        "outcome": "running", "inputs_before": before, "inputs_after": None,
        "toolchain_before": selected, "toolchain_after": None,
        "process": None, "reserved_seconds": remaining, "note": None,
    }
    journal["attempts"].append(attempt)
    journal["state"] = "running"
    save(directory, journal)  # reserve the attempt before launch, including hard interruption
    report = process(entry("model", "typecheck"), root, log_root / directory.name / f"attempt-{number:04d}",
                     min(timeout, remaining))
    attempt["process"] = report
    attempt["finished_at"] = report["finished_at"]
    try:
        after = manifest(root)
        attempt["inputs_after"] = after
        attempt["toolchain_after"] = toolchain(directory)
        check_frozen(root, journal)
        unchanged = before == after and selected == attempt["toolchain_after"]
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        unchanged = False
        attempt["note"] = str(exc)
    if not unchanged:
        attempt["outcome"] = "inputs_changed"
    elif report["outcome"] != "completed":
        attempt["outcome"] = report["outcome"]
    else:
        attempt["outcome"] = "passed" if report["exit_code"] == 0 else "failed"
    journal["active_seconds"] = active_seconds(journal)
    journal["active_since"] = time.time()
    journal["state"] = "ready"
    journal["next_action"] = "inspect diagnostics and run the required acceptance gates" if attempt["outcome"] == "passed" else "inspect diagnostics and revise or replan"
    save(directory, journal)
    if attempt["outcome"] == "passed":
        code = 0
    elif report["outcome"] == "timeout":
        code = 124
    elif report["outcome"] == "cancelled":
        code = 130
    elif report["exit_code"] is not None and report["exit_code"] > 0:
        code = report["exit_code"]
    else:
        code = 1
    return status(journal), code
