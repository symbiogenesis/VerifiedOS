# SPDX-License-Identifier: Apache-2.0
"""Generate the control node's seeded rows and emit its native and target driver.

The rows begin with every combination of 0, 1, 2^32 and 2^64-1 in each of the three
64-bit inputs `a`, `b` and `s` and of 0, 1, 2^31 and 2^32-1 in the 32-bit input `c`,
256 rows, and continue with seeded rows drawn uniformly or from values beside those
edges until `--count`, at least 576. Expected answers come from this module's own
reading of [control.lus](control.lus) and of the `mix64` body the driver defines, not
from Vélus or a C compiler; the state `held` carries across rows from one reset.

Generated C includes the normalized Clight dump verbatim and takes the printed
interface names as explicit inputs, as [probe.py](probe.py) does. The same driver is
compiled natively and by the accepted purecap backend. `--perturb` moves the first
row's expected `sum` by one, so a correct build must fail that comparison.

    python3 control.py --seed N --count N --emitted FILE --memory T --output T \
        --step F --reset F --out DRIVER.c [--summary FILE.json] [--perturb]
"""

import argparse
import hashlib
import itertools
import json
import random
import re
from pathlib import Path
from typing import NamedTuple

M32 = (1 << 32) - 1
M64 = (1 << 64) - 1
MIX = 0x9E3779B97F4A7C15
EDGES64 = (0, 1, 1 << 32, M64)
EDGES32 = (0, 1, 1 << 31, M32)
NEAR64 = (2, (1 << 31) - 1, 1 << 31, M32, (1 << 32) + 1, (1 << 63) - 1, 1 << 63,
          (1 << 63) + 1, M64 - 1)
NEAR32 = (2, (1 << 31) - 1, (1 << 31) + 1, M32 - 1)
MINIMUM_ROWS = 576


class Row(NamedTuple):
    a: int
    b: int
    c: int
    s: int  # the int64 input's two's-complement bits


class Answer(NamedTuple):
    sum: int
    mixed: int
    held: int
    low: int
    sx: int  # two's-complement bits
    wrapped: int


def _draw(rng: random.Random, near: tuple[int, ...], bits: int) -> int:
    if rng.getrandbits(1):
        return rng.getrandbits(bits)
    return near[rng.getrandbits(8) % len(near)]


def rows(seed: int, count: int) -> list[Row]:
    """The edge product followed by seeded rows, `count` in all."""
    if count < MINIMUM_ROWS:
        raise ValueError(f"the trial needs at least {MINIMUM_ROWS} rows, not {count}")
    edge = [Row(a, b, c, s) for a, b, s, c in
            itertools.product(EDGES64, EDGES64, EDGES64, EDGES32)]
    rng = random.Random(seed)
    seeded = [Row(_draw(rng, NEAR64, 64), _draw(rng, NEAR64, 64), _draw(rng, NEAR32, 32),
                  _draw(rng, NEAR64, 64)) for _ in range(count - len(edge))]
    return edge + seeded


def coverage(table: list[Row]) -> dict[str, list[int]]:
    """Each 64-bit position's edge values, refusing a table that misses one."""
    covered = {name: sorted({getattr(row, name) for row in table} & set(EDGES64))
               for name in ("a", "b", "s")}
    for name, values in covered.items():
        if values != sorted(EDGES64):
            raise ValueError(f"64-bit input {name} misses edge values")
    return covered


def mix64(x: int, y: int) -> int:
    return ((x * MIX) & M64) ^ ((y + (x >> 29)) & M64)


def answers(table: list[Row]) -> list[Answer]:
    """control.lus read directly: widen, the sum, mix64, the fby state and the casts."""
    held = 0
    out = []
    for a, b, c, s in table:
        t = ((c ^ a) + 1) & M64
        total = (t + b) & M64
        out.append(Answer(total, mix64(a, b ^ t), held, ((a >> 32) ^ c) & M32, s ^ c,
                          int(total < b)))
        held = a
    return out


def signed(bits: int) -> str:
    """A C expression of type long long for 64 two's-complement bits."""
    value = bits - (1 << 64) if bits >> 63 else bits
    if value == -(1 << 63):
        return "(-9223372036854775807LL - 1LL)"
    return f"{value}LL" if value >= 0 else f"(-{-value}LL)"


def emit(table: list[Row], emitted: Path, memory: str, output: str, step: str, reset: str,
         perturb: bool = False) -> str:
    for identifier in (memory, output, step, reset):
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", identifier) is None:
            raise ValueError("the emitted interface must be a C identifier")
    lines = ["// SPDX-License-Identifier: Apache-2.0",
             f"#include {json.dumps(emitted.resolve().as_posix())}",
             "unsigned long long mix64(unsigned long long x, unsigned long long y)",
             "{", f"    return (x * 0x{MIX:X}ULL) ^ (y + (x >> 29));", "}",
             "int main(void)", "{", f"    struct {memory} state;",
             f"    struct {output} answer;", f"    {reset}(&state);"]
    for index, (row, answer) in enumerate(zip(table, answers(table), strict=True)):
        total = (answer.sum + 1) & M64 if perturb and index == 0 else answer.sum
        lines += [f"    {step}(&state, &answer, {row.a}ULL, {row.b}ULL, {row.c}U, "
                  f"{signed(row.s)});",
                  f"    if (answer.sum != {total}ULL || answer.mixed != {answer.mixed}ULL ||",
                  f"        answer.held != {answer.held}ULL || answer.low != {answer.low}U ||",
                  f"        answer.sx != {signed(answer.sx)} || "
                  f"answer.wrapped != {answer.wrapped}) return 1;"]
    lines += ["    return 0;", "}", ""]
    return "\n".join(lines)


def table_text(table: list[Row]) -> str:
    """The rows and expected answers one per line, the bytes the summary digests."""
    return "".join(" ".join(map(str, (*row, *answer))) + "\n"
                   for row, answer in zip(table, answers(table), strict=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--count", required=True, type=int)
    parser.add_argument("--emitted", required=True, type=Path)
    for name in ("memory", "output", "step", "reset"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--perturb", action="store_true")
    args = parser.parse_args(argv)
    if not args.emitted.is_file():
        parser.error("the emitted Clight file is missing")
    table = rows(args.seed, args.count)
    covered = coverage(table)
    driver = emit(table, args.emitted, args.memory, args.output, args.step, args.reset,
                  args.perturb)
    args.out.write_text(driver, encoding="utf-8", newline="\n")
    if args.summary is not None:
        summary = {
            "generator": "supervisor/route/control.py", "seed": args.seed,
            "count": len(table), "edge_rows": len(EDGES64) ** 3 * len(EDGES32),
            "seeded_rows": len(table) - len(EDGES64) ** 3 * len(EDGES32),
            "edges_64": covered,
            "rows_sha256": hashlib.sha256(table_text(table).encode()).hexdigest(),
            "driver_sha256": hashlib.sha256(driver.encode()).hexdigest(),
            "perturb": args.perturb,
        }
        args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8",
                                newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
