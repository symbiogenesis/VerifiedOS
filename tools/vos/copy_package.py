# SPDX-License-Identifier: Apache-2.0
"""Prepare the [standalone copy source recipe](../../docs/implementation/contracts/fixed-packages.md#standalone-copy-service-source-recipe)."""

import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Final

from vos import copy_notification, copy_service, copy_target
from vos.atomic import atomic_path
from vos.copy_package_sources import ADAPTERS, C_FILES, DATA_INPUTS, source_paths
from vos.jsonutil import unique_object
from vos.receipts import digest

FORMAT: Final = "verifiedos-copy-package-sources-1"
RECORD: Final = "source-record.json"
LIMITS: Final = (
    "Source preparation only: no target emission, installed activation or wiring, "
    "fixed artifact, correspondence, TAL/CIC or production-admission verdict."
)
_INCLUDE: Final = re.compile(r'^\s*#\s*include\s*(?:<([^>"\r\n]+)>|"([^>"\r\n]+)")\s*$')
_COMMENTS: Final = re.compile(r'''(?P<literal>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|/\*.*?\*/|//[^\r\n]*''', re.DOTALL)


class PackageError(ValueError):
    """The standalone source preparation cannot be reproduced safely."""


def _capture(root: Path) -> dict[str, bytes]:
    initial = {name: (root / "copy-service" / name).read_bytes() for name in C_FILES}
    _includes({**initial, "include/copy_service_config.h": b""})
    captured: dict[str, bytes] = {}
    for relative in source_paths(root):
        path = root / relative
        if path.resolve() != path or not path.is_file():
            raise PackageError(f"source must be an unredirected regular file: {relative}")
        captured[relative] = path.read_bytes()
    if set(source_paths(root)) != set(captured):
        raise PackageError("copy package helper closure changed during capture")
    return captured


def _stable(root: Path, captured: dict[str, bytes], *, verify_closure: bool = False) -> None:
    if verify_closure and set(source_paths(root)) != set(captured):
        raise PackageError("copy package helper closure changed during preparation")
    for relative, raw in captured.items():
        path = root / relative
        if path.resolve() != path or not path.is_file() or path.read_bytes() != raw:
            raise PackageError(f"copy package source changed during preparation: {relative}")


def _includes(outputs: dict[str, bytes]) -> None:
    """Reject undeclared or dynamic includes in the complete prepared C population."""
    for relative, raw in outputs.items():
        if not relative.endswith((".c", ".h")):
            continue
        text = raw.decode("utf-8")
        if "\0" in text:
            raise PackageError(f"embedded NUL in C source: {relative}")
        text = text.removeprefix("\ufeff")
        if "\ufeff" in text:
            raise PackageError(f"embedded BOM in C source: {relative}")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if re.search(r"\?\?[=/'()!<>-]", text) or "%:" in text:
            raise PackageError(f"unsupported C preprocessing spelling in {relative}")
        if re.search(r"\\[ \t\v\f]+\n", text):
            raise PackageError(f"unsupported whitespace after escaped C newline in {relative}")
        text = text.replace("\\\n", "")
        if re.search(r"\?\?[=/'()!<>-]", text) or "%:" in text:
            raise PackageError(f"unsupported C preprocessing spelling in {relative}")
        text = _COMMENTS.sub(lambda match: match[0] if match["literal"] is not None else
                             "".join(char if char in "\r\n" else " " for char in match[0]), text)
        for line in text.splitlines():
            directive = re.match(r"^\s*#\s*(\w+)", line)
            if directive is None:
                continue
            if directive[1] not in {"include", "define", "if", "ifdef", "ifndef", "elif", "else", "endif", "error"}:
                raise PackageError(f"unsupported C directive in {relative}: {line.strip()}")
            if directive[1] != "include":
                continue
            match = _INCLUDE.fullmatch(line)
            if match is None:
                raise PackageError(f"unsupported C include in {relative}: {line.strip()}")
            standard, local = match.groups()
            if standard is not None:
                name = standard
                if name not in {"stddef.h", "stdint.h", "stdatomic.h"}:
                    raise PackageError(f"unbound standard header in {relative}: {name}")
                continue
            name = local
            if Path(name).is_absolute() or "\\" in name or ".." in Path(name).parts:
                raise PackageError(f"escaping local C include in {relative}: {name}")
            candidates = (str(Path(relative).parent / name).replace("\\", "/"), f"include/{name}")
            if not any(candidate in outputs for candidate in candidates):
                raise PackageError(f"unbound local C include in {relative}: {name}")


def _outputs(captured: dict[str, bytes], staging: Path) -> dict[str, bytes]:
    for relative in DATA_INPUTS:
        path = staging / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(captured[relative])
    for relative in ADAPTERS:
        path = staging / "copy-service" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(captured[f"copy-service/{relative}"])
    outputs = {name: captured[f"copy-service/{name}"] for name in C_FILES}
    config = copy_service.configuration(staging)
    outputs["include/copy_service_config.h"] = copy_service.configuration_header(config).encode("utf-8")
    outputs[ADAPTERS[0]] = copy_target.adapter(staging).encode("utf-8")
    outputs[ADAPTERS[1]] = copy_notification.adapter(staging).encode("utf-8")
    _includes(outputs)
    return outputs


def _record(captured: dict[str, bytes], outputs: dict[str, bytes]) -> dict[str, object]:
    return {
        "format": FORMAT, "member": "copy-service",
        "sources": {name: hashlib.sha256(raw).hexdigest() for name, raw in captured.items()},
        "outputs": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(outputs.items())},
        "recipe": {"translation_unit": "src/package_unit.c", "include_directories": ["include"],
                   "compiler_arguments": ["-S", "-fverifiedos-typed"], "assembly_adapters": list(ADAPTERS),
                   "dead_elimination": False, "comparison_wrapper": False},
        "native_output": None, "producer_qualification": None, "installed_entry_set": None,
        "production_admission": False, "limits": LIMITS,
    }


def _encoded(record: dict[str, object]) -> bytes:
    return (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _destinations(output: Path, names: set[str], inputs: list[Path]) -> dict[str, Path]:
    if output.resolve() != output or any(path.is_relative_to(output) for path in inputs):
        raise PackageError("copy package output redirects or contains consumed inputs")
    if output.exists() and not output.is_dir():
        raise PackageError("copy package output must be a directory")
    if output.exists():
        for path in output.rglob("*"):
            if path.is_symlink() or path.is_junction() or (path.is_file() and path.relative_to(output).as_posix() not in names):
                raise PackageError(f"unexpected prepared output: {path}")
    identities: set[tuple[int, int]] = set()
    for source in inputs:
        metadata = source.stat()
        identities.add((metadata.st_dev, metadata.st_ino))
    selected: dict[str, Path] = {}
    for name in sorted(names):
        path = output / name
        if path.resolve() != path or path.is_dir():
            raise PackageError(f"prepared output redirects or is a directory: {name}")
        if path.exists():
            metadata = path.stat()
            identity = (metadata.st_dev, metadata.st_ino)
            if identity in identities:
                raise PackageError(f"prepared output aliases an input or peer: {name}")
            identities.add(identity)
        selected[name] = path
    return selected


def _render(root: Path, output: Path, captured: dict[str, bytes]) -> dict[str, bytes]:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".copy-package-", dir=output.parent) as temporary:
        outputs = _outputs(captured, Path(temporary))
    _stable(root, captured)
    return outputs


def prepare(root: Path, output: Path) -> dict[str, object]:
    """Publish a replayable source snapshot, without invoking a target producer."""
    root, output = root.resolve(), output.absolute()
    captured = _capture(root)
    names = {*C_FILES, *ADAPTERS, "include/copy_service_config.h", RECORD}
    paths = _destinations(output, names, [root / name for name in captured])
    outputs = _render(root, output, captured)
    record = _record(captured, outputs)
    _destinations(output, names, [root / name for name in captured])
    _stable(root, captured, verify_closure=True)
    for name, raw in outputs.items():
        path = paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        with atomic_path(path) as pending:
            pending.write_bytes(raw)
    _stable(root, captured)
    for name, raw in outputs.items():
        if paths[name].read_bytes() != raw:
            raise PackageError(f"prepared output changed before record publication: {name}")
    with atomic_path(paths[RECORD]) as pending:
        pending.write_bytes(_encoded(record))
    return record


def check(root: Path, output: Path) -> dict[str, object]:
    """Recompute the recipe and refuse any changed input, record or output population."""
    root, output = root.resolve(), output.absolute()
    captured = _capture(root)
    names = {*C_FILES, *ADAPTERS, "include/copy_service_config.h", RECORD}
    paths = _destinations(output, names, [root / name for name in captured])
    raw = paths[RECORD].read_bytes()
    record = json.loads(raw, object_pairs_hook=unique_object)
    outputs = _render(root, output, captured)
    expected = _record(captured, outputs)
    if record != expected or raw != _encoded(expected):
        raise PackageError("prepared copy package record differs from the current source recipe")
    for name, blob in outputs.items():
        if not paths[name].is_file() or digest(paths[name]) != hashlib.sha256(blob).hexdigest():
            raise PackageError(f"prepared copy package output differs: {name}")
    _stable(root, captured, verify_closure=True)
    if paths[RECORD].read_bytes() != raw:
        raise PackageError("prepared copy package record changed during checking")
    return expected
