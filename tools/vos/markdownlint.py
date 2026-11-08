# SPDX-License-Identifier: Apache-2.0
"""Standard table syntax validation, separate from semantic-rule mutation replay."""

import json
import platform
import re
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock

from vos import corpus, jsonutil, receipts
from vos.report import Reporter

VERSION = "0.3.2"
BASE = f"https://github.com/rvben/rumdl/releases/download/v{VERSION}"

_EXPECTED_CONFIG: dict[str, dict[str, object]] = {
    "global": {
        "enable": ["MD055", "MD056"],
        "cache": False,
        "editorconfig": False,
        "respect-gitignore": False,
    },
    "MD055": {
        "style": "leading_and_trailing",
    },
}
_DIRECTIVE_RE = re.compile(
    r"(<!--[\s>]*)[rmp](?=(?:umdl-|arkdownlint-|rettier-ignore))",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Asset:
    target: str
    archive_hash: str
    executable_hash: str

    @property
    def windows(self) -> bool:
        return self.target.endswith("windows-msvc")

    @property
    def executable(self) -> str:
        return "rumdl.exe" if self.windows else "rumdl"


ASSETS: dict[str, Asset] = {
    "windows": Asset("x86_64-pc-windows-msvc",
                     "87a632668c55969a7d916f214a28a7d365f6a68ec626b547bd1243e035b9c7ff",
                     "6d13f7a08ecc9a465bbe41c66335402ab63019f6e52f848686ed980582ba4fd9"),
    "linux-x64": Asset("x86_64-unknown-linux-gnu",
                       "f527d1374765d826c1627ceab3d1f46e548268731a495b5b12a3af529b3d79e8",
                       "0244cea37c25549d87cc66c1db6fcaf36384ce8b5fd7302857127d7797a7b5a6"),
    "linux-arm64": Asset("aarch64-unknown-linux-gnu",
                         "bdfca7a602f893fbe5d73d5e38f73b31f45a21d3bcf385b6ea819997d0449ec3",
                         "8d81f770523a6cab43b5034649960480a6ce0f09072f0089d1f762e95e629256"),
}


def asset_for(system: str, machine: str) -> Asset:
    architecture = machine.lower()
    if architecture not in {"amd64", "x86_64", "arm64", "aarch64"}:
        raise ValueError(f"rumdl has no reviewed executable for {system}/{machine}")
    if system == "win32":
        return ASSETS["windows"]
    if system == "linux":
        return ASSETS["linux-arm64" if architecture in {"arm64", "aarch64"} else "linux-x64"]
    raise ValueError(f"rumdl has no reviewed executable for {system}/{machine}")


def executable() -> Path:
    """Keep pinned bytes in the managed environment shared by mutant processes."""
    if sys.prefix == sys.base_prefix:
        raise ValueError("rumdl requires the project's managed Python environment")
    asset = asset_for(sys.platform, platform.machine())
    home = Path(sys.prefix) / f"rumdl-{VERSION}"
    home.mkdir(parents=True, exist_ok=True)
    with FileLock(home / ".install.lock", timeout=180,
                  fallback_to_soft=False, preserve_lock_file=True):
        return _install(home, asset)


def _install(home: Path, asset: Asset) -> Path:
    """Verify, download and publish under the shared environment's installation lock."""
    target = home / asset.executable
    if target.exists():
        if receipts.digest(target) != asset.executable_hash:
            raise ValueError(f"{target}: installed rumdl executable hash differs from its pin")
        return target
    extension = "zip" if asset.windows else "tar.gz"
    archive = home / f"rumdl-v{VERSION}-{asset.target}.{extension}"
    receipts.download(f"{BASE}/{archive.name}", archive, asset.archive_hash)
    member = asset.executable
    if asset.windows:
        with zipfile.ZipFile(archive) as bundle:
            contents = bundle.read(member)
    else:
        with tarfile.open(archive, "r:gz") as bundle:
            entry = bundle.getmember(member)
            if not entry.isfile() or (stream := bundle.extractfile(entry)) is None:
                raise ValueError(f"{archive}: pinned executable is not an ordinary file")
            with stream:
                contents = stream.read()
    with receipts.atomic_path(target) as pending:
        pending.write_bytes(contents)
        if receipts.digest(pending) != asset.executable_hash:
            raise ValueError(f"{archive}: extracted rumdl executable hash differs from its pin")
        if not asset.windows:
            pending.chmod(0o755)
    return target


def _validate_config(config: Path) -> Path:
    """Require the exact reviewed MD055/MD056 policy before invoking the linter."""
    resolved = config.resolve(strict=True)
    decoded = tomllib.loads(resolved.read_text(encoding="utf-8"))
    global_section = decoded.get("global")
    if (decoded != _EXPECTED_CONFIG
            or not isinstance(global_section, dict)
            or not all(type(global_section.get(key)) is bool
                       for key in ("cache", "editorconfig", "respect-gitignore"))):
        raise ValueError("Markdown table configuration differs from the reviewed MD055/MD056 policy")
    return resolved


def _prepare(raw: str) -> bytes:
    """Normalize CommonMark line endings and neutralize inline suppression comments."""
    if "\x00" in raw:
        raise ValueError("Markdown source cannot contain NUL bytes")
    normalized = (raw or "\n").replace("\r\n", "\n").replace("\r", "\n")
    if "<!--" in normalized:
        normalized = _DIRECTIVE_RE.sub(r"\1_", normalized)
    return normalized.encode("utf-8")


def read_result(count: int, code: int, output: str, error: str) -> list[list[str]]:
    """Accept only a complete structured success or reported MD055/MD056 table findings."""
    if code not in {0, 1}:
        raise ValueError(f"rumdl exited {code}: {(error or output).strip()[:500]}")
    data = json.loads(output, object_pairs_hook=jsonutil.unique_object)
    if not isinstance(data, list):
        raise TypeError("rumdl returned no diagnostic array")
    expected = {f"{index:08d}.md": index for index in range(count)}
    findings: list[list[str]] = [[] for _ in range(count)]
    total = 0
    for item in data:
        if not isinstance(item, dict):
            raise TypeError("rumdl returned an invalid diagnostic entry")
        source, line, rule, message = (item.get("file"), item.get("line"),
                                       item.get("rule"), item.get("message"))
        if (not isinstance(source, str) or source not in expected
                or type(line) is not int or line < 1
                or rule not in {"MD055", "MD056"}
                or not isinstance(message, str) or not message):
            raise ValueError("rumdl returned an incomplete or unexpected diagnostic")
        findings[expected[source]].append(f"{line}: {rule} {message}")
        total += 1
    if (code == 0) != (total == 0):
        raise ValueError("rumdl's exit status and diagnostic counts disagree")
    return findings


def _scan(documents: list[str], config: Path) -> list[list[str]]:
    """Lint an exact in-memory document sequence over NUL-framed stdin-batch."""
    resolved = _validate_config(config)
    if not documents:
        return []
    payload = b"".join(
        f"{index:08d}.md\0".encode("ascii") + _prepare(raw) + b"\0"
        for index, raw in enumerate(documents)
    )
    command = [str(executable()), "check", "--stdin-batch", "--no-cache",
               "--config", str(resolved), "--output-format", "json"]
    done = subprocess.run(command, input=payload, capture_output=True,
                          check=False, timeout=120)
    return read_result(len(documents), done.returncode,
                       done.stdout.decode("utf-8"),
                       done.stderr.decode("utf-8", errors="replace"))


def table_findings(raw: str, config: Path) -> list[str]:
    """Delegate table syntax to the pinned Markdown linter, without document pragmas."""
    return _scan([raw], config)[0]


def _batch(documents: list[str], config: Path) -> list[list[str]]:
    """Batch an exact in-memory document population with ordinal virtual names."""
    return _scan(documents, config)


def _batchable(raw: str) -> bool:
    if not raw.strip() or "\x00" in raw:
        return False
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def document_findings(documents: list[corpus.Document], config: Path, *,
                      metrics: dict[str, int] | None = None) -> list[str]:
    """Ordered decisions, with the per-document route as fallback on batch refusal."""
    if metrics is not None:
        metrics.update(workers=1, worker_limit=1, parallel_attempts=0, parallel_fallbacks=0)
    eligible = [(index, doc.raw) for index, doc in enumerate(documents) if _batchable(doc.raw)]
    batched: dict[int, list[str]] = {}
    if len(eligible) > 1:
        try:
            groups = _batch([raw for _, raw in eligible], config)
            batched = {index: group for (index, _), group in zip(eligible, groups, strict=True)}
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            pass
    findings: list[str] = []
    for index, doc in enumerate(documents):
        try:
            group = batched[index] if index in batched else table_findings(doc.raw, config)
            findings.extend(f"{doc.name}:{finding}" for finding in group)
        except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
            findings.append(f"{doc.name}: Markdown validation failed: {exc}")
    return findings


def run(root: Path, *, metrics: dict[str, int] | None = None) -> Reporter:
    """Validate indexed authored Markdown once per host wave, preserving its bytes."""
    rep = Reporter()
    rep.line("=== markdown: standard table syntax ===")
    findings: list[str] = []
    try:
        documents = corpus.load(root).docs
    except (OSError, ValueError, RuntimeError) as exc:
        findings.append(f"cannot read the indexed Markdown corpus: {exc}")
        documents = []
    if not documents and not findings:
        findings.append("the index supplies no Markdown documents to validate")
    findings.extend(document_findings([doc for doc in documents if "|" in doc.raw],
                                      root / ".rumdl.toml", metrics=metrics))
    rep.report("markdown", "table syntax finding(s):", findings,
               "the pinned MD055 and MD056 checks accept every indexed table")
    return rep
