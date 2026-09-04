# SPDX-License-Identifier: Apache-2.0
"""blast-radius.py against a fixture apex statement, end to end.

The tool answers what an edit re-opens, so what is pinned is the answer's whole
mechanical chain over a record small enough to derive by hand: the consumers map,
the seam-conclusion rule (the last field read in body order), the conditional BFS
trail, and the exit codes. The wave-1 contract gets its own cases: a `none yet`
cell matches nothing, an artifact matches only as a whole token, and a missing
input file or a drifted bindings row is a worded finding rather than a traceback.

The subprocess runs a copy of the live sources materialized into a sandbox tree,
because the tool derives its root from its own file and the fixture must be that
root; the copy is read from the live tree at run time, so it is this checkout's
code that is tested.
"""

import subprocess
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from tests.harness import TOOLS, Case, ensure, sandbox_tree

# The live sources the sandbox copy of the tool runs on, relative to the root.
_SOURCES = ("tools/run.py", "tools/vos/cli/__init__.py", "tools/vos/cli/blast.py",
            "tools/vos/__init__.py", "tools/vos/apex.py",
            "tools/vos/fieldbindings.py", "tools/vos/corpus.py", "tools/vos/env.py")

# Small enough to derive by hand: witness consumes alpha and beta through its type,
# seam_one concludes beta from alpha, seam_two concludes gamma from beta, and
# uses_alpha is a consumer that is not a seam.
_APEX = """\
(* a fixture apex statement (* with a nested comment *) *)
Record Vocabulary : Type := {
  alpha : Prop;
  beta : Prop;
  gamma : Prop;
  witness : alpha -> beta;
}.

Definition seam_one (v : Vocabulary) : Prop := v.(alpha) -> v.(beta).
Definition seam_two (v : Vocabulary) : Prop := v.(beta) -> v.(gamma).
Definition uses_alpha (v : Vocabulary) : Prop := v.(alpha).
"""

# One instantiated row, two `none yet` rows, and one row naming a field the record
# does not carry, for the drifted-row finding.
_BINDINGS = """\
# Field bindings (fixture)

| Field | Consumed by | Semantics | Instantiated by |
| --- | --- | --- | --- |
| `alpha` | seam_one | prose | [proofs/Alpha.v](../proofs/Alpha.v) (`AlphaProof`) |
| `beta` | seam_one, seam_two | prose | none yet |
| `gamma` | seam_two | prose | none yet |
| `delta` | seam_one | prose | [proofs/Delta.v](../proofs/Delta.v) (`DeltaProof`) |
"""


def _sources() -> dict[str, str]:
    root = TOOLS.parent
    return {rel: (root / rel).read_text(encoding="utf-8") for rel in _SOURCES}


def _fixture() -> dict[str, str]:
    files = _sources()
    files["docs/requirements-register.md"] = "# register stub for find_root\n"
    files["proofs/ApexTheorem.v"] = _APEX
    files["docs/field-bindings.md"] = _BINDINGS
    return files


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "tools" / "run.py"), "blast", *args],
        capture_output=True, encoding="utf-8", errors="replace", check=False,
        timeout=120)


@dataclass
class _Flow:
    stack: ExitStack | None = None
    root: Path | None = None


_FLOW = _Flow()


def _root() -> Path:
    if _FLOW.root is None:
        raise AssertionError("the sandbox setup case did not run or did not survive")
    return _FLOW.root


def _bare_consumers_map() -> None:
    stack = ExitStack()
    _FLOW.stack = stack
    _FLOW.root = stack.enter_context(sandbox_tree(_fixture()))

    done = _run(_root())
    ensure(done.returncode == 0, f"bare mode on a readable record exits 0, got "
                                 f"{done.returncode}: {done.stderr!r}")
    ensure(done.stdout == (
        "the Vocabulary record's Prop fields and their consumers:\n"
        "  alpha  <=  witness, seam_one, uses_alpha\n"
        "  beta  <=  witness, seam_one, seam_two\n"
        "  gamma  <=  seam_two\n"
        "query one with --field <name>, or an instantiating artifact with "
        "--artifact <path>\n"),
        f"the consumers map read {done.stdout!r}")


def _field_trail() -> None:
    done = _run(_root(), "--field", "alpha")
    ensure(done.returncode == 0, f"--field on a live field exits 0, got {done.returncode}")
    ensure(done.stdout == (
        "field alpha\n"
        "  consumed by:\n"
        "    witness\n"
        "    seam_one (a premise)\n"
        "    uses_alpha\n"
        "  downstream, only if a re-proved seam's conclusion statement must change:\n"
        "    seam_one concludes beta\n"
        "    seam_two concludes gamma\n"
        "  and last, always: composition_meta_lemma, the R-18-031(b) linking theorem\n"),
        f"the field report read {done.stdout!r}")


def _field_conclusion_role() -> None:
    # gamma is only ever a conclusion, so its report carries the role marker and no
    # downstream section at all.
    done = _run(_root(), "--field", "gamma")
    ensure(done.returncode == 0, f"--field gamma exits 0, got {done.returncode}")
    ensure(done.stdout == (
        "field gamma\n"
        "  consumed by:\n"
        "    seam_two (its conclusion)\n"
        "  and last, always: composition_meta_lemma, the R-18-031(b) linking theorem\n"),
        f"the conclusion-only report read {done.stdout!r}")


def _field_unknown() -> None:
    done = _run(_root(), "--field", "nope")
    ensure(done.returncode == 1, f"an unknown field is a finding, got {done.returncode}")
    ensure(done.stdout.startswith("no Prop field 'nope' in the Vocabulary record")
           and "  alpha\n" in done.stdout and "  gamma\n" in done.stdout,
           f"the refusal must list the fields that exist, got {done.stdout!r}")


def _none_yet_matches_nothing() -> None:
    # `none yet` is the named absence of an artifact: no fragment of it, nor the
    # cell itself, may read as an instantiating artifact.
    for query in ("one", "none", "yet", "none yet"):
        done = _run(_root(), "--artifact", query)
        ensure(done.returncode == 1
               and f"binds no field to an artifact matching '{query}'" in done.stdout,
               f"--artifact {query!r} must match nothing, got {done.returncode}: "
               f"{done.stdout!r}")


def _whole_token_artifact() -> None:
    done = _run(_root(), "--artifact", "proofs/Alpha.v")
    ensure(done.returncode == 0
           and done.stdout.startswith("artifact proofs/Alpha.v instantiates: alpha\n")
           and "field alpha" in done.stdout,
           f"a whole token of the cell identifies the artifact, got {done.returncode}: "
           f"{done.stdout!r}")
    # fragments of the cell's tokens are no identification
    for fragment in ("Alpha", "Alpha.v"):
        done = _run(_root(), "--artifact", fragment)
        ensure(done.returncode == 1, f"--artifact {fragment!r} is a bare substring "
                                     f"and must not match, got {done.returncode}")


def _drifted_row() -> None:
    done = _run(_root(), "--artifact", "proofs/Delta.v")
    ensure(done.returncode == 1
           and "FAIL: docs/field-bindings.md row(s) naming no Prop field of the "
               "record: delta" in done.stdout,
           f"a bindings row naming no field is a worded finding, got {done.returncode}: "
           f"{done.stdout!r}")


def _missing_apex() -> None:
    files = _sources()
    files["docs/requirements-register.md"] = "# register stub for find_root\n"
    with sandbox_tree(files) as root:
        done = _run(root)
        ensure(done.returncode == 1
               and "FAIL: proofs/ApexTheorem.v is not in the repository" in done.stdout,
               f"a missing apex file is a worded finding, got {done.returncode}: "
               f"{done.stdout!r} {done.stderr!r}")


def _missing_bindings() -> None:
    files = _sources()
    files["docs/requirements-register.md"] = "# register stub for find_root\n"
    files["proofs/ApexTheorem.v"] = _APEX
    with sandbox_tree(files) as root:
        done = _run(root, "--artifact", "proofs/Alpha.v")
        ensure(done.returncode == 1
               and "FAIL: docs/field-bindings.md is not in the repository" in done.stdout,
               f"a missing bindings view is a worded finding, got {done.returncode}: "
               f"{done.stdout!r} {done.stderr!r}")


def _teardown() -> None:
    if _FLOW.stack is not None:
        _FLOW.stack.close()
        _FLOW.stack = None
        _FLOW.root = None


def cases() -> list[Case]:
    # the first case stands the shared sandbox up and the last takes it down; the
    # cases between read it only
    return [
        Case("bare-consumers-map", _bare_consumers_map, lane="host"),
        Case("field-trail", _field_trail, lane="host"),
        Case("field-conclusion-role", _field_conclusion_role, lane="host"),
        Case("field-unknown", _field_unknown, lane="host"),
        Case("none-yet-matches-nothing", _none_yet_matches_nothing, lane="host"),
        Case("whole-token-artifact", _whole_token_artifact, lane="host"),
        Case("drifted-row", _drifted_row, lane="host"),
        Case("missing-apex", _missing_apex, lane="host"),
        Case("missing-bindings", _missing_bindings, lane="host"),
        Case("teardown", _teardown, lane="host"),
    ]
