# SPDX-License-Identifier: Apache-2.0
"""The bank-grant parse and the coefficient-free arithmetic over it.

`banks.read` is exercised against the live tree on every `check.py` run, but
`score()` and the `Score` properties have no caller there: only `bank-dse.py`
runs them, and nothing held their arithmetic until this module. The fixture
figures are transcribed from the configuration's own placeholders, so the
near-deadline boundary here is the one the composition actually sits at today:
8192 banks sweep in 59.392 billion cycles against a 60 billion cycle floor.
"""

import json
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from tests.harness import Case, ensure
from vos import banks
from vos.jsonc import Json

# The configuration side, on the live file's own shapes: the second class, the
# sequencer cadence, the clock, and one SecondClass region of 8 GiB.
_CONFIG: Final[str] = """\
{
  "platform": {
    "clock_frequency": 1000000000,
    "memory_sequencer": {
      "banks_per_refresh_phase": 8,
      "refresh_phase_cycles": 58000000,
      "banks_per_discharge_phase": 4,
      "discharge_phase_cycles": 8192
    }
  },
  "memory": {
    "classes": {
      "second": {
        "qualified": false,
        "banks": 4096,
        "retention_floor_us": 60000000,
        "refresh_cycles": 20,
        "discharge_cycles": 4096
      }
    },
    "regions": [
      {
        "base": {"len": 64, "value": "0x100000000"},
        "size": {"len": 64, "value": "0x200000000"},
        "attributes": {"memory_class": {"Some": "SecondClass"}}
      }
    ]
  }
}
"""

# The contract side, with comma-spelled figures where the live document writes
# them bare, so the comma handling is pinned too.
_CONTRACT: Final[str] = (
    "The configuration declares **4,096 banks** over the second-class region.\n"
    "The candidate set is **64 through 65,536** banks.\n\n"
    "| Symbol | What it is | Role | Waits on | Status |\n"
    "| --- | --- | --- | --- | --- |\n"
    "| `I_bank_peak` | peak current | prunes | R5 | pending |\n"
    "| `I_pdn_max` | delivery ceiling | prunes | R5 | pending |\n"
    "| `W_bank` | transfer width | ranks | M0.8 | stated |\n")

# What `read` makes of the fixture pair, for the arithmetic cases to score.
_GRANT: Final[banks.Grant] = banks.Grant(
    banks=4096, qualified=False, retention_floor_us=60_000_000, refresh_cycles=20,
    discharge_cycles=4096, banks_per_refresh_phase=8, refresh_phase_cycles=58_000_000,
    banks_per_discharge_phase=4, discharge_phase_cycles=8192,
    clock_hz=1_000_000_000, region_bytes=0x2_0000_0000)

# The eight figures `complete()` names, each also a figure whose absence must
# make the grant incomplete. `banks` is the declared point and not `score`'s
# input, which takes its candidate as an argument; the other seven are exactly
# `score`'s refusal conditions.
_REQUIRED: Final[tuple[str, ...]] = (
    "banks", "retention_floor_us", "banks_per_refresh_phase", "refresh_phase_cycles",
    "banks_per_discharge_phase", "discharge_phase_cycles", "clock_hz", "region_bytes")


@contextmanager
def _tree(files: dict[str, str]) -> Iterator[Path]:
    """A throwaway root holding exactly `files`. No git: `read` opens paths and
    never the index, so the harness's tracked sandbox would buy nothing here."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
        yield root


def _grant_with(**overrides: int | None) -> banks.Grant:
    fields = {name: getattr(_GRANT, name) for name in _REQUIRED}
    fields.update(overrides)
    return banks.Grant(**fields)


def _read_both_sides() -> None:
    with _tree({banks.CONFIG: _CONFIG, banks.DOCUMENT: _CONTRACT}) as root:
        grant = banks.read(root)
    ensure(grant == banks.Grant(
        banks=4096, qualified=False, retention_floor_us=60_000_000,
        refresh_cycles=20, discharge_cycles=4096, banks_per_refresh_phase=8,
        refresh_phase_cycles=58_000_000, banks_per_discharge_phase=4,
        discharge_phase_cycles=8192, clock_hz=1_000_000_000,
        region_bytes=0x2_0000_0000, declared_banks=4096,
        candidates=[1 << e for e in range(6, 17)],
        pending=["I_bank_peak", "I_pdn_max"], stated=["W_bank"]),
        f"read gave {grant}: every figure, the comma-spelled declared point, the "
        f"eleven power-of-two candidates, and the status lists must all land")
    ensure(grant.complete(), "the full fixture grant must be complete")


def _read_absent_files() -> None:
    with _tree({}) as root:
        grant = banks.read(root)
    ensure(grant == banks.Grant(),
           f"an empty root must answer the all-None grant, got {grant}")
    ensure(not grant.complete(), "the all-None grant is not complete")


def _region_bytes() -> None:
    def region(size: Json, which: str = "SecondClass") -> Json:
        return {"size": size, "attributes": {"memory_class": {"Some": which}}}

    def total(regions: Json) -> int | None:
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            path = Path(td) / "c.json"
            path.write_text(json.dumps({"memory": {"regions": regions}}),
                            encoding="utf-8")
            return banks._region_bytes(path, "SecondClass")

    good: Json = {"len": 64, "value": "0x100"}
    bigger: Json = {"len": 64, "value": "0x200"}
    ensure(total([region(good), region(bigger)]) == 0x300,
           "two assigned regions must sum")
    ensure(total([region(good), region(bigger, "FirstClass")]) == 0x100,
           "another class's region is not this class's bytes")
    ensure(total([42, region(good)]) == 0x100,
           "a non-dict entry in the list is skipped, not fatal")
    ensure(total([region(bigger, "FirstClass")]) is None,
           "no region assigned to the class must answer None, not zero")
    # The strictness is deliberate: one malformed size among the class's regions
    # discards the whole total rather than reporting a sum that is silently short.
    short: Json = {"len": 64}
    ensure(total([region(good), region(short)]) is None,
           "a malformed size must discard the total, prior regions included")
    ensure(total(5) is None, "a non-list regions value must answer None")


def _grant_complete() -> None:
    ensure(_grant_with().complete(), "a grant carrying all eight figures is complete")
    for name in _REQUIRED:
        ensure(not _grant_with(**{name: None}).complete(),
               f"a grant short of {name} must not be complete")
    # The per-bank cycle figures are not the schedule arithmetic's inputs, so a
    # grant without them is still complete.
    bare = _grant_with()
    bare.refresh_cycles = None
    bare.discharge_cycles = None
    ensure(bare.complete(), "refresh/discharge per-bank cycles are not required")


def _score_refusals() -> None:
    ensure(banks.score(_GRANT, 0) is None, "zero banks is not a candidate")
    ensure(banks.score(_GRANT, -8) is None, "negative banks is not a candidate")
    for name in _REQUIRED[1:]:
        ensure(banks.score(_grant_with(**{name: None}), 8192) is None,
               f"a grant short of {name} must be refused, not scored around")
    # Zero is refused where it would divide and scored where it is a floor: a
    # zero-microsecond retention floor is a deadline of zero cycles that nothing
    # sweeps under, not a refusal.
    for name in ("banks_per_refresh_phase", "refresh_phase_cycles",
                 "banks_per_discharge_phase", "discharge_phase_cycles",
                 "clock_hz", "region_bytes"):
        ensure(banks.score(_grant_with(**{name: 0}), 8192) is None,
               f"a zero {name} must be refused before it reaches a denominator")
    at_zero_floor = banks.score(_grant_with(retention_floor_us=0), 8192)
    ensure(at_zero_floor is not None and at_zero_floor.refresh_deadline_cycles == 0
           and not at_zero_floor.meets_deadline,
           "a zero retention floor is scoreable, and nothing meets its deadline")


def _score_arithmetic() -> None:
    got = banks.score(_GRANT, 8192)
    ensure(got == banks.Score(
        banks=8192, bank_bytes=1_048_576, region_bytes=0x2_0000_0000,
        refresh_phases=1024, refresh_sweep_cycles=59_392_000_000,
        refresh_deadline_cycles=60_000_000_000, discharge_phases=2048,
        discharge_dwell_cycles=16_777_216),
        f"score(8192) gave {got}: ceil(8192/8) phases of 58e6 cycles against the "
        f"60e6 us floor at 1 GHz, and ceil(8192/4) discharge phases of 8192")
    ensure(got is not None and got.divides_region,
           "1 MiB banks must divide the 8 GiB region exactly")
    odd = banks.score(_GRANT, 3)
    ensure(odd is not None and not odd.divides_region,
           "three banks cannot divide the region and must say so")


def _meets_deadline_strict() -> None:
    # The live figures' own boundary: at 8192 banks the sweep is 59.392 billion
    # cycles against the 60 billion the retention floor sets, about one percent
    # under, and 16384 banks is twice over it.
    near = banks.score(_GRANT, 8192)
    over = banks.score(_GRANT, 16384)
    ensure(near is not None and near.meets_deadline,
           "59.392 billion cycles against 60 billion must meet the deadline")
    ensure(over is not None and over.refresh_sweep_cycles == 118_784_000_000
           and not over.meets_deadline,
           "twice the phases must sweep past the deadline")
    # And the comparison is strict: a cadence that lands exactly on the floor is
    # not under it. 1024 phases of 58,593,750 cycles is 60 billion on the nose.
    exact = banks.score(_grant_with(refresh_phase_cycles=58_593_750), 8192)
    ensure(exact is not None
           and exact.refresh_sweep_cycles == exact.refresh_deadline_cycles
           and not exact.meets_deadline,
           "a sweep equal to the deadline must not meet it: the floor is a floor")


def cases() -> list[Case]:
    return [
        Case("read-both-sides", _read_both_sides),
        Case("read-absent-files", _read_absent_files),
        Case("region-bytes", _region_bytes),
        Case("grant-complete", _grant_complete),
        Case("score-refusals", _score_refusals),
        Case("score-arithmetic", _score_arithmetic),
        Case("meets-deadline-strict", _meets_deadline_strict),
    ]
