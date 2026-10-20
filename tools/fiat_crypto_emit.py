# SPDX-License-Identifier: Apache-2.0
"""Reproduce the reviewed Fiat inclusion headers with the recorded generator.

Run in the guest with native --work-dir. The generator is an external build input;
this command does not fetch, compile or distribute it. --emit records an actual
run; --check repeats the generator and compares all current header bytes.
"""

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

PIN = "1e721c6f18c43b90922e7bc57fd64848e5cff2be"
RECIPES = {
    "25519_32.h": ["unsaturated-solinas", "25519", "32", "10", "2^255 - 19",
                   "carry_mul", "carry_square", "carry_scmul121666", "carry",
                   "add", "sub", "opp", "selectznz", "to_bytes", "from_bytes", "--static"],
    "p256_32.h": ["word-by-word-montgomery", "p256", "32",
                  "2^256 - 2^224 + 2^192 + 2^96 - 1", "--static"],
}
DESTINATION = "tools/generated/fiat-crypto"
EMITTER = "tools/fiat_crypto_emit.py"
PROOF_LOCK = "tools/opam/rocq.lock"
MANIFEST = DESTINATION + "/manifest.json"
ARTIFACTS = (MANIFEST, *(DESTINATION + "/" + name for name in RECIPES))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def wrap(name: str, raw: bytes) -> bytes:
    """Only the recorded inclusion wrapper surrounds the unaltered generator body."""
    guard = "VERIFIEDOS_FIAT_" + name.replace(".", "_").upper()
    preamble = (
        "// SPDX-License-Identifier: Apache-2.0\n"
        "// Copyright 2015-2020 the fiat-crypto authors.\n"
        "// Authors: Andres Erbsen; Google Inc.; Jade Philipoom;\n"
        "// Massachusetts Institute of Technology; Zoe Paraskevopoulou.\n"
        "// Generated from Fiat-Crypto " + PIN + ".\n"
        "// Apache-2.0 elected from upstream COPYRIGHT; see ../../../COPYRIGHT.md.\n"
        "// Inclusion wrapper added by VerifiedOS; generated body below is unchanged.\n"
        "#ifndef " + guard + "\n#define " + guard + "\n"
    ).encode("utf-8")
    return preamble + raw + b"\n#endif\n"


def source_receipt(path: Path) -> list[dict[str, str]]:
    """Bind the actual Git archives used for the external build, including gitlinks."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict) \
            or rows[0].get("path") != "." \
            or rows[0].get("revision") != PIN:
        raise ValueError("source receipt does not name the reviewed Fiat revision")
    result: list[dict[str, str]] = []
    names: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) \
                or row["path"] in names:
            raise ValueError("source receipt has an invalid or duplicate member")
        names.add(row["path"])
        revision = row.get("revision", "")
        if not isinstance(revision, str) or len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("source receipt has no immutable member revision")
        archive = row.get("archive", "")
        if not isinstance(archive, str) or not archive or Path(archive).name != archive:
            raise ValueError("source archive must be a sibling basename")
        result.append({"path": row["path"], "revision": revision,
                       "archive_sha256": digest((path.parent / archive).read_bytes())})
    return result


def verify_source_tree(root: Path, receipt: Path) -> str:
    """The upstream build queries Git and must preserve every archived source byte."""
    source_receipt(receipt)
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if revision != PIN:
        raise ValueError("Fiat build source has no matching parent Git index")
    index = subprocess.run(["git", "-C", str(root), "diff-index", "--cached", "--quiet",
                            "HEAD", "--"], cwd=root, capture_output=True, check=False)
    if index.returncode != 0:
        raise ValueError("Fiat build parent Git index differs from its selected revision")
    for row in json.loads(receipt.read_text(encoding="utf-8")):
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Fiat source directory escapes its build tree")
        folder = root / relative
        with tarfile.open(receipt.parent / row["archive"]) as archive:
            for member in archive:
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts:
                    raise ValueError("Fiat archive member escapes its source directory")
                actual = folder / member.name
                if not actual.resolve().is_relative_to(root.resolve()):
                    raise ValueError("Fiat source member escapes its build tree")
                if member.isfile():
                    content = archive.extractfile(member)
                    if content is None or actual.is_symlink() or actual.read_bytes() != content.read():
                        raise ValueError("Fiat build changed archived source: " + str(actual))
                elif member.issym() and (not actual.is_symlink()
                                        or actual.readlink().as_posix() != member.linkname):
                    raise ValueError("Fiat build changed an archived source link")
    return revision


def verify_outputs(folder: Path, recorded: dict[str, Any], generated: dict[str, bytes]) -> None:
    if recorded.get("schema") != 1 or recorded.get("source_pin") != PIN \
            or recorded.get("recipes") != RECIPES \
            or set(recorded.get("outputs", {})) != set(RECIPES) or set(generated) != set(RECIPES):
        raise ValueError("manifest schema, source, recipes or output set differs")
    for name, raw in generated.items():
        if not raw:
            raise ValueError("empty generated body: " + name)
        wrapped = wrap(name, raw)
        expected = {"raw_sha256": digest(raw), "header_sha256": digest(wrapped)}
        if recorded["outputs"][name] != expected or (folder / name).read_bytes() != wrapped:
            raise ValueError("generated header or receipt differs: " + name)


def verify_build_environment(root: Path, environment: object) -> None:
    """Bind a measured external build to the unchanged installed proof lock."""
    if not isinstance(environment, dict) or set(environment) != {
            "switch", "prover", "ocaml", "lock_sha256", "export_before_sha256",
            "export_after_sha256"}:
        raise ValueError("Fiat build environment is missing or malformed")
    lock = (root / PROOF_LOCK).read_bytes()
    for field, package in (("prover", "rocq-core"), ("ocaml", "ocaml-base-compiler")):
        versions = set(re.findall(rb'"' + package.encode() + rb'\.([^"\s]+)"', lock))
        if len(versions) != 1 or environment[field] != next(iter(versions)).decode():
            raise ValueError("Fiat build " + field + " differs from the proof lock")
    if environment["switch"] != ("verifiedos-rocq-" + environment["prover"]
                                  + "-ocaml-" + environment["ocaml"]):
        raise ValueError("Fiat build does not identify the locked proof switch")
    for field in ("lock_sha256", "export_before_sha256", "export_after_sha256"):
        if environment[field] != digest(lock):
            raise ValueError("Fiat build lock or switch export differs: " + field)


def verify_build_identity(root: Path, recorded: dict[str, Any]) -> None:
    verify_build_environment(root, recorded.get("build_environment"))
    if recorded.get("source_index_revision") != PIN:
        raise ValueError("Fiat build parent Git index is missing or different")
    executable = recorded.get("generator_executable")
    if not isinstance(executable, str) or not executable.startswith("/root/build/") \
            or "\x00" in executable or ".." in PurePosixPath(executable).parts:
        raise ValueError("Fiat generator executable is missing or outside its native build lane")
    command = recorded.get("build_command")
    if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
        raise ValueError("Fiat build command is missing or malformed")
    switch = recorded["build_environment"]["switch"]
    expected = ["opam", "exec", f"--switch={switch}", "--", "make", "-j2", "SKIP_BEDROCK2=1",
                f"COQC=/root/.opam/{switch}/bin/rocq c", "standalone-unified-ocaml"]
    if command != expected:
        raise ValueError("Fiat build command differs from the reviewed locked-compiler recipe")


def verify_record(root: Path, source_pin: str | None) -> None:
    """Check host-readable provenance; only the native replay reruns Fiat itself."""
    recorded = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if not isinstance(recorded, dict) or source_pin != PIN:
        raise ValueError("Fiat manifest or indexed source pin differs")
    owners = {EMITTER: digest((root / EMITTER).read_bytes())}
    if recorded.get("owners") != owners:
        raise ValueError("Fiat emission wrapper/recipe owner changed; regenerate and review")
    sources = recorded.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Fiat source archive record is empty or malformed")
    names: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"path", "revision", "archive_sha256"}:
            raise ValueError("Fiat source archive row is malformed")
        name = source["path"]
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("Fiat source archive names are invalid or repeated")
        names.add(name)
        for key, length in (("revision", 40), ("archive_sha256", 64)):
            value = source[key]
            if not isinstance(value, str) or len(value) != length or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("Fiat source archive identity is invalid")
    if sources[0]["path"] != "." or sources[0]["revision"] != source_pin:
        raise ValueError("Fiat source archive root differs from its indexed pin")
    binary_hash = recorded.get("generator_sha256")
    if not isinstance(binary_hash, str) or len(binary_hash) != 64 or any(c not in "0123456789abcdef" for c in binary_hash):
        raise ValueError("Fiat generator identity is missing or invalid")
    verify_build_identity(root, recorded)
    generated = {}
    for name in RECIPES:
        header = (root / DESTINATION / name).read_bytes()
        # The sentinel is supplied only to recover this wrapper's two pieces.
        prefix, suffix = wrap(name, b"\x00").split(b"\x00")
        if not header.startswith(prefix) or not header.endswith(suffix):
            raise ValueError("Fiat inclusion wrapper differs: " + name)
        generated[name] = header[len(prefix):-len(suffix)]
    verify_outputs(root / DESTINATION, recorded, generated)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generator", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path)
    parser.add_argument("--build-receipt", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--emit", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    folder = root / DESTINATION
    try:
        _execute(args, folder)
    except (OSError, ValueError, subprocess.CalledProcessError, tarfile.TarError) as error:
        print("FAIL:", error)
        return 1
    print("PASS: both headers reproduce byte-for-byte; each generator invocation repeated")
    return 0


def _execute(args: argparse.Namespace, folder: Path) -> None:
    work = args.work_dir.resolve()
    if not work.is_relative_to(Path("/root/build")) or not work.is_dir():
        raise ValueError("--work-dir must be an existing native /root/build lane directory")
    binary = args.generator.resolve(strict=True)
    binary_hash = digest(binary.read_bytes())
    manifest_path = folder / "manifest.json"
    recorded = {} if args.emit else json.loads(manifest_path.read_text(encoding="utf-8"))
    if not args.emit and recorded.get("generator_sha256") != binary_hash:
        raise ValueError("generator binary differs from the reviewed emission")
    generated: dict[str, bytes] = {}
    invocations: list[dict[str, Any]] = []
    for name, recipe in RECIPES.items():
        runs = []
        for run in (1, 2):
            command = ["fiat_crypto", *recipe]
            result = subprocess.run(command, executable=binary, cwd=work, capture_output=True, check=False)
            prefix = name + f".run{run}"
            (work / (prefix + ".stdout")).write_bytes(result.stdout)
            (work / (prefix + ".stderr")).write_bytes(result.stderr)
            invocations.append({"command": command, "exit": result.returncode,
                                "stdout": prefix + ".stdout", "stdout_sha256": digest(result.stdout),
                                "stderr": prefix + ".stderr", "stderr_sha256": digest(result.stderr)})
            result.check_returncode()
            runs.append(result)
        if not runs[0].stdout or runs[0].stdout != runs[1].stdout:
            raise ValueError("empty or nondeterministic generator output: " + name)
        generated[name] = runs[0].stdout
    if args.emit:
        if args.source_receipt is None or args.build_receipt is None:
            raise ValueError("--emit requires the source and successful build receipts")
        sources = source_receipt(args.source_receipt)
        build = json.loads(args.build_receipt.read_text(encoding="utf-8"))
        if build.get("exit") != 0 or not build.get("command"):
            raise ValueError("build receipt is not a successful invocation")
        if build.get("source_pin") != PIN or build.get("generator_sha256") != binary_hash \
                or build.get("generator_executable") != str(binary):
            raise ValueError("build receipt identifies a different source or generator")
        build_identity = {"build_command": build["command"],
                          "build_environment": build.get("environment"),
                          "source_index_revision": verify_source_tree(binary.parents[2], args.source_receipt),
                          "generator_executable": str(binary)}
        verify_build_identity(folder.parents[2], build_identity)
        recorded = {"schema": 1, "source_pin": PIN, "sources": sources,
                    "owners": {EMITTER: digest((folder.parents[2] / EMITTER).read_bytes())},
                    "recipes": RECIPES, "generator_sha256": binary_hash,
                    **build_identity,
                    "outputs": {name: {"raw_sha256": digest(raw),
                                       "header_sha256": digest(wrap(name, raw))}
                                for name, raw in generated.items()}}
        folder.mkdir(parents=True, exist_ok=True)
        for name, raw in generated.items():
            (folder / name).write_bytes(wrap(name, raw))
        manifest_path.write_text(json.dumps(recorded, indent=2) + "\n", encoding="utf-8")
    elif args.source_receipt is not None:
        if recorded.get("sources") != source_receipt(args.source_receipt):
            raise ValueError("source archive identities differ from the reviewed emission")
        verify_source_tree(binary.parents[2], args.source_receipt)
    verify_outputs(folder, recorded, generated)
    verify_record(folder.parents[2], PIN)
    (work / "fiat-emission.json").write_text(json.dumps({
        "generator_executable": str(binary), "generator_sha256": binary_hash,
        "invocations": invocations, "outputs": recorded["outputs"]}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
