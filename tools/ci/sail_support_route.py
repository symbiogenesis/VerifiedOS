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
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path
from typing import Any

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


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("expected JSON object")
    return value


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8", newline="")


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
    if {row["name"]: row["version"] for row in actual} != expected or any(row["pin"] for row in actual):
        raise ValueError("installed dependency closure differs from reviewed versions")


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
            timeout: int = 10800) -> subprocess.CompletedProcess[str]:
        start = time.monotonic()
        with subprocess.Popen(argv, cwd=cwd, env=self.environment, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              encoding="utf-8", errors="replace", start_new_session=sys.platform == "linux") as process:
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
        log = self.upload / (label + ".log")
        log.write_text(result.stdout + result.stderr, encoding="utf-8", newline="")
        self.report["commands"].append({"label": label, "argv": argv, "cwd": str(cwd),
            "exit": result.returncode, "seconds": time.monotonic() - start,
            "log": log.name, "log_sha256": receipts.digest(log), "strict": strict,
            "timed_out": limited})
        self.save()
        if result.returncode or (strict and (result.stdout.strip() or result.stderr.strip())):
            raise ValueError("command failed or strict diagnostic: " + label)
        return result

    def opam(self, label: str, args: list[str]) -> subprocess.CompletedProcess[str]:
        return self.run(label, [str(self.root / "bin/opam"), *args], self.root)

    def executable(self, argv: list[str]) -> list[str]:
        return [str(self.root / "bin/opam"), "exec", "--switch=" + SWITCH, "--", *argv]


def identity_tree(roots: list[Path]) -> dict[str, str]:
    identities: dict[str, str] = {}
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                identities[str(path)] = receipts.digest(path)
    if not identities:
        raise ValueError("input identity population is empty")
    return identities


def audit_sources(campaign: Campaign, found: dict[str, Any], selected: list[Path],
                  candidate_map: list[str]) -> None:
    root = campaign.root
    audits: dict[str, object] = {}
    for index, source in enumerate(selected):
        module = "SailStdpp." + source.stem
        query = root / ("Assumption_" + str(index) + ".v")
        query.write_text(proofaudit.inventory_query(module), encoding="utf-8", newline="")
        listed_symbols = campaign.run("inventory-" + str(index), campaign.executable(
            ["rocq", "c", *candidate_map, *STRICT, str(query)]), root)
        if listed_symbols.stderr.strip():
            raise ValueError("native inventory printed a diagnostic")
        symbols = proofaudit.inventory(listed_symbols.stdout, module)
        query.write_text(proofaudit.assumption_query(module, symbols), encoding="utf-8", newline="")
        checked = campaign.run("assumptions-" + str(index), campaign.executable(
            ["rocq", "c", *candidate_map, *STRICT, str(query)]), root)
        if checked.stderr.strip():
            raise ValueError("native assumption audit printed a diagnostic")
        proofaudit.assumptions(checked.stdout, symbols)
        for symbol in symbols:
            names = {entry.split(" : ", 1)[0] for entry in symbol["assumptions"]}
            if not names <= set(found["support_axioms"]):
                raise ValueError("native declaration has an undeclared assumption")
        audits[module] = symbols
    if not any(audits.values()):
        raise ValueError("native source inventory enumerated no declaration")
    write(campaign.upload / "native-assumptions.json", audits)


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
    listed = campaign.opam("closure", ["list", "--switch=" + SWITCH, "--installed", "--short",
                                      "--columns=name,version,pin", "--color=never"])
    closure = bootstrap_instrument.parse_closure(listed.stdout)
    expected_closure = dict(package.split(".", 1) for package in compiler_component.installed(
        base_lock.read_text(encoding="utf-8")))
    expected_closure.update({"rocq-stdpp-bitvector": "1.13.0", "rocq-sail-stdpp": "0.20.3"})
    same_closure(closure, expected_closure)
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
    audit_sources(campaign, found, selected, candidate_map)
    freeze_sources(campaign, found, pristine, candidate, mappings)
    probes = root / "probes"
    probes.mkdir()
    for name, entry in found["probes"].items():
        source = probes / (name + ".v")
        source.write_bytes(asset(side, entry).read_bytes())
        campaign.run("probe-compile-" + name, campaign.executable(["rocq", "c", *candidate_map,
                     "-Q", str(probes), "Qualification", *STRICT, str(source)]), root, strict=True)
    input_roots = [installed / "bin", installed / "lib", installed / ".opam-switch/build",
                   candidate / "src-stdpp", probes]
    inputs = identity_tree(input_roots)
    write(campaign.upload / "input-identities.json", inputs)
    for name, roots, expected in [("support", ["SailStdpp." + path.stem for path in selected], found["support_axioms"]),
                                *[(name, ["Qualification." + name], entry["expected_axioms"])
                                  for name, entry in found["probes"].items()]]:
        result = campaign.run("kernel-" + name, campaign.executable(["rocqchk", "-silent", "-o",
                              *candidate_map, "-Q", str(probes), "Qualification", *roots]), root)
        names = kernel_reading(result.returncode, result.stdout, result.stderr, expected)
        campaign.report.setdefault("kernel_contexts", {})[name] = names
    if inputs != identity_tree(input_roots):
        raise ValueError("kernel input population changed")
    exported = campaign.upload / "sail-support.lock"
    campaign.opam("export", ["switch", "export", "--full", "--freeze", "--switch=" + SWITCH, str(exported)])
    snapshot_metadata(exported.read_text(encoding="utf-8"), extra_files, found["source"]["sha256"])
    if imported is not None and imported.read_bytes() != exported.read_bytes():
        raise ValueError("independent full frozen re-export is not byte-identical")
    evidence = {name: {"sha256": receipts.digest(campaign.upload / name),
                       "bytes": (campaign.upload / name).stat().st_size}
                for name in ("input-identities.json", "native-assumptions.json", "package-metadata.txt",
                             "Sail-Support-LICENSE", "sail-support.lock")}
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
            "kernel-support", "kernel-term", "kernel-eqdep", "kernel-real", "kernel-notation", "export",
            *("probe-compile-" + name for name in ("term", "eqdep", "real", "notation")),
            *(label + str(index) for index in range(29)
              for label in ("strict-", "inventory-", "assumptions-")),
            *("frozen-" + str(index) + "-" + side_name for index in range(frozen_count)
              for side_name in ("baseline", "candidate")), *phases[phase]}


def join(artifacts: Path | None, side: Path, revision: str, root: Path) -> None:
    if artifacts is None:
        raise ValueError("join needs same-run artifacts")
    needs = json.loads(os.environ["CAMPAIGN_NEEDS"])
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
        evidence = row.get("evidence")
        expected_files = {"input-identities.json", "native-assumptions.json", "package-metadata.txt",
                          "Sail-Support-LICENSE", "sail-support.lock"}
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
        labels = [entry["label"] for entry in commands]
        required = required_labels(row["phase"], frozen_count)
        if len(labels) != len(set(labels)) or not required <= set(labels):
            raise ValueError("artifact lacks complete strict/recursive checks")
        for command in commands:
            log = path.parent / command["log"]
            if (log.parent != path.parent or command["exit"] != 0
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
        if output := os.environ.get("GITHUB_OUTPUT"):
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
