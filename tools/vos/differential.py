# SPDX-License-Identifier: Apache-2.0
"""The differential corpus: its manifest, and assembling the programs it names.

The corpus is versioned (M0.12) because it is evidence rather than scaffolding:
every executor of the frozen profile is checked against it, and a member added
or changed after a milestone reported a figure against it changes what that
figure said. So the manifest carries a version, one row per member, and what
each member exercises; [docs/differential-corpus.md](../../docs/differential-corpus.md)
carries the same rows in prose and `tools/check.py` holds the two equal in both
directions.

This module is the parse. The runner is `model.py corpus`, which needs a built
emulator; the checker only assembles, which needs nothing but Python, so a
corpus that has stopped assembling is a finding on the host rather than a
surprise in WSL.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

CORPUS_DIR = "corpus"
MANIFEST = "manifest.json"


@dataclass(frozen=True)
class Member:
    name: str
    source: str
    # Everything below is *measured* rather than declared, which is why the
    # manifest carries no prose: what each member exercises is the document's,
    # said once. `checks` is the highest check number the program sets, and
    # `records`/`digest` are its commit trace's length and fingerprint. All
    # three move together under `model.py corpus --refresh`.
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


# A member sets the number of the check in flight into `gp` before running it,
# so the exit code names the check that failed; the highest such number is how
# many checks the program carries. Zero is the pass marker and not a check.
CHECK_RE = re.compile(r"^\s*li\s+gp\s*,\s*(\d+)", re.MULTILINE)


def count_checks(source: str) -> int:
    return max((int(n) for n in CHECK_RE.findall(source)), default=0)


def rewrite(corpus: Corpus, measured: dict[str, tuple[int, int, str]]) -> None:
    """Write the measured fields back into the manifest.

    Every other field is left as it was: a manifest row declares a member and
    where its source is, and a tool that rewrote the whole document would be
    reformatting declarations to repair a measurement.
    """
    path = corpus.directory / MANIFEST
    raw = json.loads(path.read_text(encoding="utf-8"))
    for row in raw["members"]:
        if row["name"] in measured:
            row["checks"], row["records"], row["digest"] = measured[row["name"]]
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8", newline="\n")


def assemble(corpus: Corpus, member: Member, out_dir: Path) -> Path:
    from . import asm
    out_dir.mkdir(parents=True, exist_ok=True)
    elf = out_dir / f"{member.name}.elf"
    asm.assemble_file(corpus.source(member), elf)
    return elf
