# SPDX-License-Identifier: Apache-2.0
"""Reproduce the reviewed Fiat inclusion headers with the recorded generator.

Run in the guest with native --work-dir. The generator is an external build input;
this command does not fetch, compile or distribute it. --emit records an actual
run; --check repeats the generator and compares all current header bytes.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

PIN = "e6946985c9165b3270eae457c0fae887cd7b7b76"
RECIPES = {
    "25519_32.h": ["unsaturated-solinas", "25519", "32", "10", "2^255 - 19",
                   "carry_mul", "carry_square", "carry_scmul121666", "carry",
                   "add", "sub", "opp", "selectznz", "to_bytes", "from_bytes", "--static"],
    "p256_32.h": ["word-by-word-montgomery", "p256", "32",
                  "2^256 - 2^224 + 2^192 + 2^96 - 1", "--static"],
}
DESTINATION = "tools/generated/fiat-crypto"
EMITTER = "tools/fiat_crypto_emit.py"
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
    command = recorded.get("build_command")
    if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
        raise ValueError("Fiat build command is missing or malformed")
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
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
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
    for name, recipe in RECIPES.items():
        runs = [subprocess.run(["fiat_crypto", *recipe], executable=binary,
                               cwd=work, capture_output=True, check=True) for _ in range(2)]
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
        recorded = {"schema": 1, "source_pin": PIN, "sources": sources,
                    "owners": {EMITTER: digest((folder.parents[2] / EMITTER).read_bytes())},
                    "recipes": RECIPES, "generator_sha256": binary_hash,
                    "build_command": build["command"],
                    "outputs": {name: {"raw_sha256": digest(raw),
                                       "header_sha256": digest(wrap(name, raw))}
                                for name, raw in generated.items()}}
        folder.mkdir(parents=True, exist_ok=True)
        for name, raw in generated.items():
            (folder / name).write_bytes(wrap(name, raw))
        manifest_path.write_text(json.dumps(recorded, indent=2) + "\n", encoding="utf-8")
    elif args.source_receipt is not None and recorded.get("sources") != source_receipt(args.source_receipt):
        raise ValueError("source archive identities differ from the reviewed emission")
    verify_outputs(folder, recorded, generated)
    verify_record(folder.parents[2], PIN)


if __name__ == "__main__":
    raise SystemExit(main())
