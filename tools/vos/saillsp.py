# SPDX-License-Identifier: Apache-2.0
"""Optional native Sail LSP installation and finite, non-authoritative qualification."""

import hashlib
import json
import os
import re
import select
import shutil
import signal
import subprocess
import tarfile
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vos import env

NOTICE = "Experimental live feedback; the locked batch compiler and existing model gates remain authoritative."
LOCK = "tools/sail-lsp/sources.lock.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def home(e: env.Environment) -> Path:
    return e.lane_root / "sail-lsp"


def lock_identity(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in (LOCK, "tools/opam/sail.lock", "tools/vos/saillsp.py",
                     "tools/sail-lsp/dependency-refresh.patch"):
        digest.update(relative.encode())
        digest.update((root / relative).read_bytes())
    return digest.hexdigest()


def _base_inventory(root: Path) -> list[str]:
    """Refuse drift in every package of the existing compiler's transitive lock."""
    lock = (root / "tools/opam/sail.lock").read_text(encoding="utf-8")
    match = re.search(r"installed:\s*\[(.*?)\]", lock, re.DOTALL)
    if match is None:
        raise ValueError("the base Sail lock has no installed package closure")
    expected = sorted(re.findall(r'"([^"\n]+)"', match.group(1)))
    done = subprocess.run(["opam", "list", f"--switch={env.SAIL_SWITCH}", "--installed",
                           "--columns=name,version", "--short"], capture_output=True,
                          text=True, check=True)
    actual = sorted(".".join(line.split()) for line in done.stdout.splitlines() if line.strip())
    if actual != expected:
        raise ValueError("installed Sail dependency inventory differs from tools/opam/sail.lock")
    return actual


def _run(argv: list[str], cwd: Path, environ: dict[str, str], log: Path) -> None:
    with log.open("ab") as output:
        output.write(("\n" + json.dumps(argv) + "\n").encode())
        output.flush()
        done = subprocess.run(argv, cwd=cwd, env=environ, stdout=output,
                              stderr=subprocess.STDOUT, timeout=900, check=False)
    if done.returncode != 0:
        raise ValueError(f"build command exited {done.returncode}; see {log}")


def _source(spec: dict[str, Any], directory: Path) -> Path:
    archive = directory / (spec["name"] + ".archive")
    if not archive.exists():
        if not spec["url"].startswith("https://"):
            raise ValueError("source URLs must use HTTPS")
        with (urllib.request.urlopen(spec["url"], timeout=60) as response,  # noqa: S310 -- HTTPS checked above; tracked pins only.
              archive.open("wb") as output):
            shutil.copyfileobj(response, output)
    if sha256(archive) != spec["sha256"]:
        raise ValueError(f"source archive digest mismatch: {archive}")
    target = directory / str(spec["directory"])
    # Restore original archive members before a reproducible patch/build retry.
    with tarfile.open(archive) as source:
        source.extractall(directory, filter="data")
    return target


def status(e: env.Environment) -> dict[str, Any]:
    receipt = home(e) / "installation.json"
    result: dict[str, Any] = {"schema_version": 1, "operation": "status", "notice": NOTICE,
                              "installed": False, "home": str(home(e))}
    if not receipt.exists():
        return result
    raw = json.loads(receipt.read_text(encoding="utf-8"))
    if raw.get("lock_sha256") != lock_identity(e.root):
        raise ValueError("optional Sail LSP installation is stale; run sail-lsp install")
    for relative, digest in raw["artifacts"].items():
        path = home(e) / relative
        if not path.resolve().is_relative_to(home(e).resolve()) or sha256(path) != digest:
            raise ValueError(f"optional Sail LSP artifact changed: {relative}")
    result.update(installed=True, lock_sha256=raw["lock_sha256"],
                  server_sha256=raw["artifacts"]["prefix/bin/sail_lsp"],
                  artifact_count=len(raw["artifacts"]), receipt=str(receipt),
                  install_seconds=raw["elapsed_seconds"], log=raw["log"])
    return result


def install(e: env.Environment) -> dict[str, Any]:
    """Build only optional packages into a lane prefix, using the base lock read-only."""
    location = home(e)
    location.mkdir(parents=True, exist_ok=True)
    with env.hold_lock(location / "install", "an optional Sail LSP install"):
        inventory = _base_inventory(e.root)
        receipt_file = location / "installation.json"
        if receipt_file.exists():
            previous = json.loads(receipt_file.read_text(encoding="utf-8"))
            if previous.get("lock_sha256") == lock_identity(e.root):
                return status(e)
        specs = json.loads((e.root / LOCK).read_text(encoding="utf-8"))["sources"]
        sources = location / "sources"
        prefix = location / "prefix"
        sources.mkdir(exist_ok=True)
        prefix.mkdir(exist_ok=True)
        temporary = location / "tmp"
        temporary.mkdir(exist_ok=True)
        environ = dict(os.environ)
        environ.update(TMPDIR=str(temporary), DUNE_CACHE="disabled",
                       XDG_CACHE_HOME=str(location / "cache"),
                       OCAMLPATH=str(prefix / "lib") + os.pathsep + environ.get("OCAMLPATH", ""),
                       CAML_LD_LIBRARY_PATH=str(prefix / "lib/stublibs") + os.pathsep
                       + environ.get("CAML_LD_LIBRARY_PATH", ""))
        log = e.log("sail-lsp-install")
        log.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        paths: dict[str, Path] = {}
        licenses: dict[str, str] = {}
        for spec in specs:
            source = _source(spec, sources)
            paths[spec["name"]] = source
            licenses[spec["name"]] = sha256(source / spec["license_file"])
            packages = spec.get("packages", [spec["name"]])
            if spec["name"] in ("topkg", "uutf"):
                argv = ["ocaml", "pkg/pkg.ml", "build", "--dev-pkg", "false"]
                if spec["name"] == "uutf":
                    argv += ["--with-cmdliner", "false"]
                _run(argv, source, environ, log)
                _run(["opam-installer", "--prefix", str(prefix), spec["name"] + ".install"],
                     source, environ, log)
            else:
                if spec["name"] == "sail":
                    packages = ["sail_maker", "libsail"]
                    _run(["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-i",
                          str(e.root / "tools/sail-lsp/dependency-refresh.patch")], source, environ, log)
                _run(["dune", "build", "-p",
                      ",".join(packages), "-j", str(min(e.jobs, 4)), "@install"], source, environ, log)
                _run(["dune", "install", "--root", str(source), "--prefix", str(prefix), *packages],
                     source, environ, log)
        server_source = paths["sail"] / "src/sail_lsp"
        _run(["dune", "build", "--release", "-j", str(min(e.jobs, 4))],
             server_source, environ, log)
        _run(["dune", "install", "--root", str(server_source), "--prefix", str(prefix)],
             server_source, environ, log)
        config = location / "config/sail_lsp/config.json"
        _write_json(config, {"sail_dir": str(paths["sail"]), "highlight": False, "folding": False})
        artifacts = {path.relative_to(location).as_posix(): sha256(path)
                     for path in sorted(prefix.rglob("*")) if path.is_file()}
        artifacts[config.relative_to(location).as_posix()] = sha256(config)
        for path in sorted((paths["sail"] / "lib").rglob("*")):
            if path.is_file():
                artifacts[path.relative_to(location).as_posix()] = sha256(path)
        receipt = {"lock_sha256": lock_identity(e.root), "base_packages": inventory,
                   "sources": specs, "license_sha256": licenses, "artifacts": artifacts,
                   "elapsed_seconds": round(time.monotonic() - started, 6), "log": str(log)}
        _write_json(location / "installation.json", receipt)
    return status(e)


def server_environment(e: env.Environment) -> dict[str, str]:
    if not status(e)["installed"]:
        raise ValueError("optional Sail LSP is absent; run sail-lsp install")
    environ = dict(os.environ)
    environ["XDG_CONFIG_HOME"] = str(home(e) / "config")
    environ["TMPDIR"] = str(home(e) / "tmp")
    return environ


def serve(e: env.Environment) -> int:
    """Inherit stdio without injecting a banner, transforming frames or parsing code."""
    executable = home(e) / "prefix/bin/sail_lsp"
    log = e.log("sail-lsp-server")
    log.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run([str(executable), "--stdio", "--log-file", str(log)], cwd=e.root,
                          env=server_environment(e), check=False).returncode


MAX_FRAME = 8 * 1024 * 1024


def frame(message: dict[str, Any]) -> bytes:
    body = json.dumps(message, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode()
    if len(body) > MAX_FRAME:
        raise ValueError("LSP frame exceeds the 8 MiB bound")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def decode_frame(buffer: bytearray) -> dict[str, Any] | None:
    """Consume exactly one LSP frame; never treat stdout banners as JSON-RPC."""
    boundary = buffer.find(b"\r\n\r\n")
    if boundary < 0:
        if len(buffer) > 8192:
            raise ValueError("LSP header exceeds 8192 bytes")
        return None
    if boundary > 8192:
        raise ValueError("LSP header exceeds 8192 bytes")
    headers: dict[bytes, bytes] = {}
    for line in bytes(buffer[:boundary]).split(b"\r\n"):
        key, separator, value = line.partition(b":")
        key = key.lower()
        if not separator or key in headers:
            raise ValueError("malformed or repeated LSP header")
        headers[key] = value.strip()
    raw_length = headers.get(b"content-length", b"")
    if not raw_length.isdigit() or not 0 < int(raw_length) <= MAX_FRAME:
        raise ValueError("invalid LSP Content-Length")
    end = boundary + 4 + int(raw_length)
    if len(buffer) < end:
        return None
    body = bytes(buffer[boundary + 4:end])
    del buffer[:end]
    message = json.loads(body)
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        raise ValueError("expected a JSON-RPC 2.0 object")
    return message


class Session:
    """A finite stdio client used only by qualification, independent of any editor."""

    def __init__(self, e: env.Environment, directory: Path, name: str, timeout: float) -> None:
        self.timeout = timeout
        self.started = time.monotonic()
        self.next_id = 1
        self.buffer = bytearray()
        self.events: list[dict[str, Any]] = []
        self.peak_rss_kib = 0
        self.stderr = (directory / (name + ".stderr")).open("wb")
        self.transcript = directory / (name + ".json")
        self.process = subprocess.Popen(
            [str(home(e) / "prefix/bin/sail_lsp"), "--stdio", "--log-file",
             str(directory / (name + ".server.log"))], cwd=directory,
            env=server_environment(e), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.stderr, start_new_session=True)

    def sample(self) -> None:
        path = Path("/proc") / str(self.process.pid) / "status"
        try:
            match = re.search(r"^VmHWM:\s+(\d+) kB$", path.read_text(), re.MULTILINE)
        except OSError:
            return
        if match is not None:
            self.peak_rss_kib = max(self.peak_rss_kib, int(match.group(1)))

    def send(self, method: str, params: object = None, *, request: bool = False) -> int:
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        identifier = self.next_id
        if request:
            message["id"] = identifier
            self.next_id += 1
        if self.process.stdin is None:
            raise ValueError("LSP stdin is closed")
        self.process.stdin.write(frame(message))
        self.process.stdin.flush()
        self.events.append({"direction": "send", "message": message})
        return identifier

    def receive(self, accept: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        if self.process.stdout is None:
            raise ValueError("LSP stdout is closed")
        while time.monotonic() < deadline:
            message = decode_frame(self.buffer)
            if message is not None:
                self.sample()
                self.events.append({"direction": "receive", "message": message})
                if accept(message):
                    return message
                if "method" in message and "id" in message:
                    if self.process.stdin is None:
                        raise ValueError("LSP stdin is closed")
                    response = {"jsonrpc": "2.0", "id": message["id"],
                                "error": {"code": -32601, "message": "client method unsupported"}}
                    self.process.stdin.write(frame(response))
                    self.process.stdin.flush()
                continue
            readable, _, _ = select.select([self.process.stdout], [], [], max(0, deadline - time.monotonic()))
            if not readable:
                break
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise ValueError(f"LSP exited before its response (status {self.process.poll()})")
            self.buffer.extend(chunk)
        raise TimeoutError(f"LSP response exceeded {self.timeout:g} seconds")

    def request(self, method: str, params: object = None) -> dict[str, Any]:
        identifier = self.send(method, params, request=True)
        return self.receive(lambda message: message.get("id") == identifier)

    def initialize(self, root: Path) -> dict[str, Any]:
        response = self.request("initialize", {"processId": os.getpid(), "rootUri": root.as_uri(),
                                "capabilities": {"general": {"positionEncodings": ["utf-16"]}}})
        self.send("initialized", {})
        return response

    def diagnostics(self, path: Path, text: str, *, version: int = 1, opened: bool = False) -> dict[str, Any]:
        uri = path.as_uri()
        if opened:
            self.send("textDocument/didChange", {"textDocument": {"uri": uri, "version": version},
                                                "contentChanges": [{"text": text}]})
        else:
            self.send("textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "sail",
                                                              "version": version, "text": text}})
        return self.receive(lambda message: message.get("method") == "textDocument/publishDiagnostics"
                            and message.get("params", {}).get("uri") == uri)

    def close(self, *, terminate: bool = False) -> dict[str, Any]:
        self.sample()
        shutdown: dict[str, Any] | None = None
        if self.process.poll() is None:
            if not terminate:
                try:
                    shutdown = self.request("shutdown")
                    self.send("exit")
                    self.process.wait(timeout=5)
                except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired):
                    terminate = True
            if terminate and self.process.poll() is None:
                os.killpg(self.process.pid, signal.SIGTERM)
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait()
        self.stderr.close()
        if self.process.stdin is not None:
            self.process.stdin.close()
        if self.process.stdout is not None:
            self.process.stdout.close()
        _write_json(self.transcript, self.events)
        return {"exit_code": self.process.returncode, "shutdown": shutdown,
                "elapsed_seconds": round(time.monotonic() - self.started, 6),
                "peak_rss_kib": self.peak_rss_kib, "transcript": str(self.transcript)}


def _batch(e: env.Environment, project: Path, directory: Path, name: str, timeout: float) -> dict[str, Any]:
    log = directory / (name + ".batch.log")
    timing = directory / (name + ".batch.time")
    argv = ["sail", "--strict-var", "--strict-bitvector", "--strict-exponentials",
            "--just-check", "--all-modules", str(project)]
    if name == "curated":
        cache = directory / "curated.smt-cache"
        if e.primary_typecheck_cache.is_file():
            shutil.copyfile(e.primary_typecheck_cache, cache)
        argv[1:1] = ["--memo-z3", "--memo-z3-path", str(cache)]
    source_hashes = {str(path): sha256(path) for path in sorted(project.parent.rglob("*"))
                     if path.is_file() and path.suffix in (".sail", ".sail_project")}
    started = time.monotonic()
    with log.open("wb") as output:
        process = subprocess.Popen(["/usr/bin/time", "-f", "%e %M %U %S", "-o", str(timing), *argv],
                                   cwd=project.parent, stdout=output, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    values = timing.read_text().splitlines() if timing.exists() else []
    fields = values[-1].split() if values else []
    return {"command": argv, "exit_code": process.returncode, "timed_out": timed_out,
            "elapsed_seconds": round(time.monotonic() - started, 6),
            "peak_rss_kib": int(fields[1]) if len(fields) == 4 else None,
            "log": str(log), "log_sha256": sha256(log), "source_sha256": source_hashes}


def _has_diagnostic(message: dict[str, Any]) -> bool:
    return bool(message.get("params", {}).get("diagnostics", []))


def qualify(e: env.Environment, *, timeout: float = 90) -> dict[str, Any]:
    """Measure observed capabilities, including failures, against ordinary batch checks."""
    installation = status(e)
    if not installation["installed"]:
        raise ValueError("optional Sail LSP is absent; run sail-lsp install")
    directory = home(e) / ("qualification-" + time.strftime("%Y%m%dT%H%M%S"))
    directory.mkdir(parents=True, exist_ok=False)
    fixture = e.root / "tools/sail-lsp/fixtures"
    for source in fixture.iterdir():
        if source.is_file():
            shutil.copyfile(source, directory / source.name)
    project = directory / "qualification.sail_project"
    dependent = directory / "main.sail"
    dependency = directory / "dependency.sail"
    main_text = dependent.read_text(encoding="utf-8")
    dep_text = dependency.read_text(encoding="utf-8")
    cases: list[dict[str, Any]] = []
    sessions: list[dict[str, Any]] = []

    def record(name: str, response: dict[str, Any], passed: bool, started: float,
               batch: dict[str, Any] | None = None, *, required: bool = True,
               live_seconds: float | None = None) -> None:
        cases.append({"name": name, "passed": passed, "response": response, "batch": batch,
                      "required": required, "live_seconds": live_seconds,
                      "elapsed_seconds": round(time.monotonic() - started, 6)})

    def watched(session: Session, path: Path, change: int = 2) -> dict[str, Any]:
        session.send("workspace/didChangeWatchedFiles", {"changes": [{"uri": path.as_uri(), "type": change}]})
        return session.receive(lambda message: message.get("method") == "textDocument/publishDiagnostics"
                                and message.get("params", {}).get("uri") == dependent.as_uri())

    session = Session(e, directory, "fixture", timeout)
    interrupt = False
    try:
        started = time.monotonic()
        response = session.initialize(directory)
        record("initialize", response, response.get("result", {}).get("serverInfo", {}).get("name") == "sail_lsp", started)
        started = time.monotonic()
        response = session.diagnostics(dependent, main_text)
        live_seconds = time.monotonic() - started
        baseline = _batch(e, project, directory, "baseline", timeout)
        record("baseline-diagnostics", response, not _has_diagnostic(response) and baseline["exit_code"] == 0,
               started, baseline, live_seconds=live_seconds)
        position = {"textDocument": {"uri": dependent.as_uri()}, "position": {"line": 1, "character": 29}}
        for method in ("hover", "definition"):
            started = time.monotonic()
            response = session.request("textDocument/" + method, position)
            record(method, response, bool(response.get("result")), started)

        started = time.monotonic()
        invalid = main_text.replace("helper(4)", "helper(true)")
        response = session.diagnostics(dependent, invalid, opened=True, version=2)
        live_seconds = time.monotonic() - started
        dependent.write_text(invalid, encoding="utf-8")
        batch = _batch(e, project, directory, "unsaved-overlay", timeout)
        dependent.write_text(main_text, encoding="utf-8")
        record("unsaved-buffer", response, _has_diagnostic(response) and batch["exit_code"] != 0 and not batch["timed_out"],
               started, batch, live_seconds=live_seconds)
        session.diagnostics(dependent, main_text, opened=True, version=3)

        started = time.monotonic()
        changed_dep = dep_text.replace("int -> int", "int -> bool").replace("helper(x) = x", "helper(x) = true")
        dependency.write_text(changed_dep, encoding="utf-8")
        response = watched(session, dependency)
        live_seconds = time.monotonic() - started
        batch = _batch(e, project, directory, "changed-dependency", timeout)
        record("saved-dependency-change", response, _has_diagnostic(response) and batch["exit_code"] != 0 and not batch["timed_out"],
               started, batch, live_seconds=live_seconds)

        started = time.monotonic()
        unsaved = main_text.replace("helper(4)", "helper(unknown_live)")
        session.diagnostics(dependent, unsaved, opened=True, version=4)
        dependency.write_text(dep_text, encoding="utf-8")
        response = watched(session, dependency)
        record("dependency-refresh-preserves-unsaved-buffer", response,
               _has_diagnostic(response) and "unknown_live" in json.dumps(response), started)
        response = session.diagnostics(dependent, main_text, opened=True, version=5)
        record("repaired-dependency-clears-diagnostics", response, not _has_diagnostic(response), time.monotonic())

        started = time.monotonic()
        dependency.unlink()
        response = watched(session, dependency, 3)
        hover = session.request("textDocument/hover", position)
        batch = _batch(e, project, directory, "missing-dependency", timeout)
        record("deleted-dependency-refuses-stale-types", {"diagnostics": response, "hover": hover},
               _has_diagnostic(response) and hover.get("result") is None and "result" in hover
               and batch["exit_code"] != 0 and not batch["timed_out"], started, batch)
        dependency.write_text(changed_dep, encoding="utf-8")
        watched(session, dependency, 1)

        started = time.monotonic()
        identifier = session.send("textDocument/hover", position, request=True)
        session.send("$/cancelRequest", {"id": identifier})
        response = session.receive(lambda message: message.get("id") == identifier)
        valid = response.get("jsonrpc") == "2.0" and (("result" in response) != ("error" in response))
        record("cancellation-protocol-response", response, valid, started)
        record("request-work-interruption", response, response.get("error", {}).get("code") == -32800,
               started, required=False)
        # Push diagnostics have no cancellable request ID. Stopping this optional
        # process is the reliable cancellation fallback; a new process rereads disk.
        session.send("textDocument/didChange", {"textDocument": {"uri": dependent.as_uri(), "version": 6},
                                               "contentChanges": [{"text": main_text}]})
        interrupt = True
    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError) as exc:
        cases.append({"name": "fixture-session-error", "passed": False, "response": {"error": str(exc)},
                      "batch": None, "elapsed_seconds": 0.0, "required": True, "live_seconds": None})
    finally:
        measurement = session.close(terminate=interrupt)
        sessions.append(measurement)
        if interrupt:
            record("session-process-cancellation", measurement, measurement["exit_code"] < 0, time.monotonic())

    session = Session(e, directory, "restart", timeout)
    started = time.monotonic()
    try:
        session.initialize(directory)
        response = session.diagnostics(dependent, main_text)
        live_seconds = time.monotonic() - started
        batch = _batch(e, project, directory, "restart", timeout)
        record("restart-sees-dependency", response, _has_diagnostic(response) and batch["exit_code"] != 0 and not batch["timed_out"],
               started, batch, live_seconds=live_seconds)
    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError) as exc:
        record("restart-sees-dependency", {"error": str(exc)}, False, started)
    finally:
        measurement = session.close()
        sessions.append(measurement)
        record("shutdown-exit", measurement, measurement["exit_code"] == 0
               and measurement["shutdown"] == {"id": 2, "jsonrpc": "2.0", "result": None}, time.monotonic())

    curated = e.model / "model/extensions/CHERI/cheri_insts.sail"
    session = Session(e, directory, "curated", timeout)
    started = time.monotonic()
    try:
        session.initialize(e.model / "model")
        text = curated.read_text(encoding="utf-8")
        response = session.diagnostics(curated, text)
        live_seconds = time.monotonic() - started
        batch = _batch(e, e.model / "model/riscv.sail_project", directory, "curated", timeout)
        record("curated-project-diagnostics", response, not _has_diagnostic(response) and batch["exit_code"] == 0,
               started, batch, live_seconds=live_seconds)
        lines = text.splitlines()
        line = next(i for i, content in enumerate(lines) if "setCapAddr(PCC" in content)
        position = {"textDocument": {"uri": curated.as_uri()},
                    "position": {"line": line, "character": lines[line].index("setCapAddr") + 2}}
        for method in ("hover", "definition"):
            started = time.monotonic()
            response = session.request("textDocument/" + method, position)
            record("curated-" + method, response, bool(response.get("result")), started)
    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError) as exc:
        record("curated-session-error", {"error": str(exc)}, False, started)
    finally:
        sessions.append(session.close())
    result = {"schema_version": 1, "operation": "qualify", "notice": NOTICE,
              "installation": installation, "cases": cases, "sessions": sessions,
              "all_capabilities_passed": all(case["passed"] for case in cases),
              "all_required_checks_passed": all(case["passed"] for case in cases if case["required"]),
              "model_source_sha256": {str(path.relative_to(e.root)): sha256(path)
                                      for path in sorted((e.model / "model").rglob("*"))
                                      if path.is_file() and path.suffix in (".sail", ".sail_project")},
              "report": str(directory / "report.json")}
    _write_json(directory / "report.json", result)
    return result
