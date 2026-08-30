# SPDX-License-Identifier: Apache-2.0
"""The seeded-defect generator's own reading of a source, and the three tools' host
entry points.

What is pinned here is that the loop **puts the tree back**: the `$[test]` oracle
writes into `model/`, which is a `-text` tree where a newline-translating round trip
rewrites every line of the file it touched. The verdict arithmetic this tool reports
through is `vos/seeded.py`'s and is held in [test_seeded.py](test_seeded.py), beside
the module that decides it and beside the loops that share it.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos.cli import seed

_ROOT = TOOLS.parent


def _run(command: str, *args: str) -> tuple[int, str]:
    done = subprocess.run([sys.executable, str(TOOLS / "run.py"), command, *args],
                          capture_output=True, encoding="utf-8", errors="replace",
                          check=False, timeout=300, cwd=_ROOT)
    return done.returncode, done.stdout + done.stderr


def _a_source_round_trips_byte_for_byte() -> None:
    """`model/` is `-text` in .gitattributes, so a read that translated newlines and a
    write that put them back as LF would rewrite every line of a CRLF file while the
    loop believed it had restored it."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        path = Path(td) / "crlf.sail"
        raw = b"function f() -> unit = ()\r\nfunction g() -> unit = ()\r\n"
        path.write_bytes(raw)
        text = seed.read_source(path)
        seed.write_source(path, text)
        ensure(path.read_bytes() == raw,
               f"the round trip rewrote the file: {path.read_bytes()!r}")


def _moved_counts_a_length_change() -> None:
    ensure(seed._moved(["a", "b"], ["a", "b"]) == 0,
           "two equal vector sets moved")
    ensure(seed._moved(["a", "b"], ["a", "c"]) == 1,
           "one changed line did not count as one")
    ensure(seed._moved(["a", "b", "c"], ["a"]) == 2,
           "a shortened answer did not count its missing lines")


def _oracle_list_runs() -> None:
    code, out = _run("oracle", "list")
    ensure(code == 0, f"the live specs do not parse: {out}")
    ensure("vector(s) in all" in out, f"the listing printed {out!r}")


def _oracle_emit_runs() -> None:
    code, out = _run("oracle", "emit", "--spec", "capformat")
    ensure(code == 0, f"the capformat harness did not emit: {out[-400:]}")
    ensure(out.startswith("// SPDX-License-Identifier"),
           "a generated Sail file does not open with the mark COPYRIGHT.md requires")
    ensure("function main() -> unit" in out, "the harness has no entry point")


def _seed_list_runs_over_a_live_source() -> None:
    code, out = _run("seed", "list", "--file",
                     "model/model/extensions/keccak/keccak_p1600.sail", "--limit", "3")
    ensure(code == 0, f"the live Sail source yields no population: {out[-400:]}")
    ensure("mutant(s) over" in out, f"the listing printed {out!r}")


def _seed_list_refuses_an_unmutable_kind() -> None:
    code, out = _run("seed", "list", "--file", "tools/vos/cli/seed.py")
    ensure(code != 0, "a Python file was given a lane")
    ensure("two lanes" in out, f"the refusal said {out!r}")


def cases() -> list[Case]:
    return [
        Case("a source round trips byte for byte", _a_source_round_trips_byte_for_byte),
        Case("a length change counts as movement", _moved_counts_a_length_change),
        Case("oracle list runs over the live specs", _oracle_list_runs, lane="host"),
        Case("oracle emit produces a marked harness", _oracle_emit_runs, lane="host"),
        Case("seed list runs over a live source",
             _seed_list_runs_over_a_live_source, lane="host"),
        Case("seed list refuses a kind it has no lane for",
             _seed_list_refuses_an_unmutable_kind, lane="host"),
    ]
