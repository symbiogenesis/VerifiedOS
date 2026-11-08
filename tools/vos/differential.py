# SPDX-License-Identifier: Apache-2.0
"""Differential corpus manifest loader, check/word scanner, and ELF assembler; see
[docs/assurance/differential-corpus.md](../../docs/assurance/differential-corpus.md)."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import asm

CORPUS_DIR = "corpus"
MANIFEST = "manifest.json"


@dataclass(frozen=True)
class Member:
    name: str
    source: str
    # Measured check count, commit-trace record count, and SHA-256 digest (`run.py model corpus --refresh`).
    checks: int = 0
    records: int = 0
    digest: str = ""


@dataclass(frozen=True)
class Corpus:
    version: int
    trace_schema: int
    members: tuple[Member, ...]
    directory: Path

    def source(self, member: Member) -> Path:
        return self.directory / member.source


def load(root: Path) -> Corpus:
    directory = root / CORPUS_DIR
    raw = json.loads((directory / MANIFEST).read_text(encoding="utf-8"))
    members = tuple(Member(m["name"], m["source"], m.get("checks", 0),
                           m.get("records", 0), m.get("digest", ""))
                    for m in raw["members"])
    return Corpus(raw["version"], raw["trace_schema"], members, directory)


# Each check loads its 1-based check number into `gp` before executing (`0` marks pass).
CHECK_RE = re.compile(r"^\s*li\s+gp\s*,\s*(\d+)", re.MULTILINE)


def count_checks(source: str) -> int:
    return max((int(n) for n in CHECK_RE.findall(source)), default=0)


# Raw `.word` directives checked against [docs/assurance/differential-corpus.md](../../docs/assurance/differential-corpus.md).
WORD_RE = re.compile(r"^\s*\.word\s+(\S+)\s*$", re.MULTILINE)


def hand_written_words(source: str) -> list[str]:
    """Return all `.word` operand strings in `source` in source order."""
    return [str(operand) for operand in WORD_RE.findall(source)]


def rewrite(corpus: Corpus, measured: dict[str, tuple[int, int, str]]) -> None:
    """Update `(checks, records, digest)` in `corpus/manifest.json` when values change."""
    path = corpus.directory / MANIFEST
    before = path.read_text(encoding="utf-8", newline="")
    raw = json.loads(before)
    for row in raw["members"]:
        if row["name"] in measured:
            row["checks"], row["records"], row["digest"] = measured[row["name"]]
    text = json.dumps(raw, indent=2) + "\n"
    if text != before:
        path.write_text(text, encoding="utf-8", newline="\n")


def assemble(corpus: Corpus, member: Member, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    elf = out_dir / f"{member.name}.elf"
    asm.assemble_file(corpus.source(member), elf)
    return elf
