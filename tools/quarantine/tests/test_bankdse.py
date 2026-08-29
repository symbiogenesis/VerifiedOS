# SPDX-License-Identifier: Apache-2.0
"""bank-dse.py against a fixture composition, and the live tree's standing facts.

The tool's design point is self-restraint: it scores what the composition fixes and
admits nothing while the droop coefficients are pending, and its verdict sentence
says so. No checker rule holds that sentence, so this module is its gate: the exact
wording is pinned against a fixture whose arithmetic is derivable by hand, one row
per candidate, with the strict-below deadline boundary and the divides-region test
each sat exactly on their edge. The two FAIL paths are pinned too: a configuration
short of a figure is named figure by figure (all eight are guarded), and a contract
with no candidate set is a finding rather than an empty table.

The fixture cases run a copy of the live sources materialized into a sandbox tree,
because the tool derives its root from its own file; the live-tree case runs the
tool where it stands and only reads.
"""

import subprocess
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from tests.harness import TOOLS, Case, ensure, sandbox_tree

# The live sources the sandbox copy of the tool runs on, relative to the root.
_SOURCES = ("tools/quarantine/bank-dse.py", "tools/quarantine/__init__.py",
            "tools/quarantine/banks.py", "tools/vos/__init__.py",
            "tools/vos/config.py", "tools/vos/jsonc.py", "tools/vos/corpus.py")

# The composition, small enough to score by hand. The region is 60000h + 40000h =
# 100,000 bytes across two second-class regions (the summation is part of what is
# tested), the deadline is 8 us at 100 MHz = 800 cycles, and the dialect's comment
# and trailing comma are left in because the model's own configuration carries both.
_CONFIG = """\
{
  // fixture configuration for the bank-dse tests
  "platform": {
    "clock_frequency": 100000000,
    "memory_sequencer": {
      "banks_per_refresh_phase": 4,
      "refresh_phase_cycles": 100,
      "banks_per_discharge_phase": 8,
      "discharge_phase_cycles": 50,
    }
  },
  "memory": {
    "classes": {
      "second": {
        "banks": 16,
        "qualified": false,
        "retention_floor_us": 8,
        "refresh_cycles": 100,
        "discharge_cycles": 50
      }
    },
    "regions": [
      {
        "attributes": { "memory_class": { "Some": "FirstClass" } },
        "size": { "len": 64, "value": "0x10000" }
      },
      {
        "attributes": { "memory_class": { "Some": "SecondClass" } },
        "size": { "len": 64, "value": "60000" }
      },
      {
        "attributes": { "memory_class": { "Some": "SecondClass" } },
        "size": { "len": 64, "value": "40000" }
      }
    ]
  }
}
"""

_CONTRACT = """\
# Bank-count DSE contract (fixture)

The configuration declares **16 banks** for the second class.
The candidate set is **8 through 64** banks.

| Symbol | What it scales | Units | Source | Status |
| --- | --- | --- | --- | --- |
| `I_bank_peak` | peak bank current | A | measurement | pending |
| `I_pdn_max` | PDN ceiling | A | measurement | pending |
| `W_bank` | bank bandwidth | B/s | measurement | pending |
| `s_island` | island share | n/a | measurement | pending |
| `C_bl_per_row` | bitline capacitance | F | measurement | pending |
| `t_fix` | a stated figure | us | datasheet | stated |
"""

# The whole table, by hand: phases are ceilings over the cadences (4 per refresh
# phase at 100 cycles, 8 per discharge phase at 50), the deadline is 800 cycles, and
# the region is 100,000 bytes. 32 banks sweep in exactly 800 cycles and sit ON the
# deadline, which the strict `<` refuses; 64 banks leave 100,000 // 64 = 1,562 bytes
# whose product falls short of the region, so the division test refuses them too.
_ROWS = {
    "8": ["8", "12,500", "2", "200", "800", "True", "50", "True", "n/a"],
    "16": ["16", "6,250", "4", "400", "800", "True", "100", "True", "n/a",
           "<--", "declared"],
    "32": ["32", "3,125", "8", "800", "800", "False", "200", "True", "n/a"],
    "64": ["64", "1,562", "16", "1,600", "800", "False", "400", "False", "n/a"],
}

_VERDICT = ("ok: 2 of 4 candidates clear the shape constraints the composition "
            "fixes, and none is admitted: the droop envelope is the hard constraint "
            "and both of its coefficients are pending (R-15-247p, R-15-247g).")


def _sources() -> dict[str, str]:
    root = TOOLS.parent
    return {rel: (root / rel).read_text(encoding="utf-8") for rel in _SOURCES}


def _fixture(config: str | None, contract: str) -> dict[str, str]:
    files = _sources()
    files["docs/requirements-register.md"] = "# register stub for find_root\n"
    if config is not None:
        files["model/config/verifiedos.json"] = config
    files["docs/bank-count-dse-contract.md"] = contract
    return files


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "tools" / "quarantine" / "bank-dse.py")],
        capture_output=True, encoding="utf-8", errors="replace", check=False,
        timeout=120)


@dataclass
class _Flow:
    stack: ExitStack | None = None
    out: str = ""
    code: int | None = None


_FLOW = _Flow()


def _report() -> tuple[int, str]:
    if _FLOW.code is None:
        raise AssertionError("the sandbox setup case did not run or did not survive")
    return _FLOW.code, _FLOW.out


def _scored_run() -> None:
    stack = ExitStack()
    _FLOW.stack = stack
    root = stack.enter_context(sandbox_tree(_fixture(_CONFIG, _CONTRACT)))
    done = _run(root)
    _FLOW.code, _FLOW.out = done.returncode, done.stdout
    ensure(done.returncode == 0, f"a consistent fixture exits 0, got "
                                 f"{done.returncode}: {done.stderr!r}")
    ensure(done.stdout.startswith(
        "=== second-class bank count, over 4 candidates ===\n"),
        f"the header names the candidate count, got {done.stdout!r}")


def _per_row_arithmetic() -> None:
    _, out = _report()
    rows = {line.split()[0]: line.split() for line in out.splitlines()
            if line.split() and line.split()[0] in _ROWS}
    ensure(list(rows) == list(_ROWS), f"one row per candidate, in candidate order, "
                                      f"got {list(rows)!r}")
    for banks, expected in _ROWS.items():
        ensure(rows[banks] == expected,
               f"the {banks}-bank row must read {expected}, got {rows[banks]}")


def _pending_columns() -> None:
    _, out = _report()
    ensure("--- columns no candidate carries a value in ---" in out,
           f"the pending-columns section must stand, got {out!r}")
    for line in ("droop headroom         pending on I_bank_peak, I_pdn_max",
                 "island bandwidth       pending on W_bank, s_island",
                 "read energy per bit    pending on C_bl_per_row"):
        ensure(f"  {line}" in out, f"missing pending column line {line!r} in {out!r}")


def _residuals() -> None:
    _, out = _report()
    ensure("  5 pending coefficient(s): I_bank_peak, I_pdn_max, W_bank, s_island, "
           "C_bl_per_row" in out,
           f"the pending residual must list the five symbols, got {out!r}")
    ensure("  1 stated coefficient(s): t_fix" in out,
           f"the stated residual must list its symbol, got {out!r}")
    ensure("  the composition's own qualification flag is False" in out,
           f"the qualification flag is reported as it stands, got {out!r}")


def _admits_nothing_verdict() -> None:
    # The load-bearing sentence: the module docstring says a report that quietly
    # stopped saying it would be the instrument turning into the answer, and no
    # checker rule reads this output, so the exact wording is pinned here.
    code, out = _report()
    ensure(code == 0 and out.rstrip().endswith(_VERDICT),
           f"the verdict sentence must close the report verbatim, got {out!r}")


def _teardown() -> None:
    if _FLOW.stack is not None:
        _FLOW.stack.close()
        _FLOW.stack = None
        _FLOW.code = None
        _FLOW.out = ""


def _missing_all_figures() -> None:
    # No configuration at all: every one of the eight figures the arithmetic needs is
    # reported by name, in the table's own order.
    with sandbox_tree(_fixture(None, _CONTRACT)) as root:
        done = _run(root)
        ensure(done.returncode == 1, f"a figureless composition is a finding, got "
                                     f"{done.returncode}")
        ensure(done.stdout.rstrip() == (
            "FAIL: model/config/verifiedos.json no longer declares "
            "the second class's bank count, its retention floor, "
            "the sequencer's cadence, its refresh phase cycles, "
            "its discharge cadence, its discharge phase cycles, "
            "the clock frequency, the second-class region"),
            f"all eight figures are named, got {done.stdout!r}")


def _missing_sequencer_figures() -> None:
    # The sequencer's three later figures are guarded like the first five: short of
    # them the run refuses by name rather than reporting every candidate unscoreable.
    config = _CONFIG.replace('      "refresh_phase_cycles": 100,\n', "") \
                    .replace('      "banks_per_discharge_phase": 8,\n', "") \
                    .replace('      "discharge_phase_cycles": 50,\n', "")
    with sandbox_tree(_fixture(config, _CONTRACT)) as root:
        done = _run(root)
        ensure(done.returncode == 1
               and done.stdout.rstrip() == (
                   "FAIL: model/config/verifiedos.json no longer declares "
                   "its refresh phase cycles, its discharge cadence, "
                   "its discharge phase cycles"),
               f"the missing sequencer figures are named, got {done.returncode}: "
               f"{done.stdout!r}")


def _no_candidate_set() -> None:
    contract = _CONTRACT.replace(
        "The candidate set is **8 through 64** banks.\n", "")
    with sandbox_tree(_fixture(_CONFIG, contract)) as root:
        done = _run(root)
        ensure(done.returncode == 1
               and done.stdout.rstrip() == (
                   "FAIL: docs/bank-count-dse-contract.md declares no candidate set "
                   "this tool reads"),
               f"a contract with no candidate set is a finding, got "
               f"{done.returncode}: {done.stdout!r}")


def _live_tree_facts() -> None:
    # Golden values from the live contract and configuration as of 2026-08-22:
    # 11 candidates (64 through 65,536), 8 clearing the shape constraints, 4,096
    # declared. Rerecord by running `python tools/quarantine/bank-dse.py` after a
    # deliberate change to docs/bank-count-dse-contract.md or
    # model/config/verifiedos.json and carrying the new figures here.
    done = subprocess.run(
        [sys.executable, str(TOOLS / "quarantine" / "bank-dse.py")],
        capture_output=True, encoding="utf-8", errors="replace", check=False,
        timeout=120)
    ensure(done.returncode == 0, f"the live tree scores clean, got "
                                 f"{done.returncode}: {done.stdout!r}")
    ensure(done.stdout.startswith(
        "=== second-class bank count, over 11 candidates ===\n"),
        f"the live candidate set holds 11, got {done.stdout!r}")
    ensure("ok: 8 of 11 candidates clear the shape constraints" in done.stdout,
           f"8 of the live candidates clear, got {done.stdout!r}")
    declared = [line for line in done.stdout.splitlines() if "<-- declared" in line]
    ensure(len(declared) == 1 and declared[0].split()[0] == "4096",
           f"the declared point is 4096 banks, got {declared!r}")


def cases() -> list[Case]:
    # the first case stands the shared sandbox up and its teardown takes it down; the
    # cases between read the one captured report
    return [
        Case("scored-run", _scored_run, lane="host"),
        Case("per-row-arithmetic", _per_row_arithmetic, lane="host"),
        Case("pending-columns", _pending_columns, lane="host"),
        Case("residuals", _residuals, lane="host"),
        Case("admits-nothing-verdict", _admits_nothing_verdict, lane="host"),
        Case("sandbox-teardown", _teardown, lane="host"),
        Case("missing-all-figures", _missing_all_figures, lane="host"),
        Case("missing-sequencer-figures", _missing_sequencer_figures, lane="host"),
        Case("no-candidate-set", _no_candidate_set, lane="host"),
        Case("live-tree-facts", _live_tree_facts, lane="host"),
    ]
