# SPDX-License-Identifier: Apache-2.0
"""Generate the switch control program's rows and emit its drivers, split to fit the target.

The rows begin with 128 edge rows, every combination of the four constructors of `m`
and of `k`, both values of `go` and 0, 1, 2^31 and 2^32-1 in `x`, with `j`, `n`, `y` and
`w` (0, 1, 2^63 or 2^64-1) stepped from the same index so each takes every constructor
or edge value; seeded rows drawn uniformly or from values beside those edges follow, up
to `--count`, at least 576. Expected answers come from this module's own reading of
[switch_control.lus](switch_control.lus), not from Vélus or a C compiler.

`compiler-diff program` places a program's text below its data section at 0x80008000, so
one straight-line `main` over every row does not fit (F-473). The rows are split into
programs of `--rows` consecutive rows each. Every program resets the node first, so the
state the node's `fby` equations keep starts afresh in each program, and the expected
answers are computed the same way: per program, from the reset state. Each program
includes the normalized and rewritten Clight dump verbatim and takes the printed
interface names as explicit inputs, as [probe.py](probe.py) does, and the same program
is compiled natively and by the accepted purecap backend. `--perturb` moves the first
row's expected `b` by one in the first program only, so a correct build of that program
must fail its first check.

    python3 switch_control.py --seed N --count N --rows N --emitted FILE --memory T \
        --output T --step F --reset F --out-dir DIR [--summary FILE.json] [--perturb]
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
EDGES32 = (0, 1, 1 << 31, M32)
EDGES64 = (0, 1, 1 << 63, M64)
NEAR32 = (2, (1 << 31) - 1, (1 << 31) + 1, M32 - 1, 9, 10, 11, 12)
NEAR64 = (2, M32, 1 << 32, (1 << 63) - 1, (1 << 63) + 1, M64 - 1)
IDLE, RUN, HOLD, FAULT = range(4)
MINIMUM_ROWS = 576


class Row(NamedTuple):
    m: int
    j: int
    k: int
    n: int
    go: int
    x: int
    y: int
    w: int


class Answer(NamedTuple):
    a: int
    b: int
    c: int
    q: int
    z: int
    s: int
    v: int
    h: int
    e: int
    f: int
    g: int


class State(NamedTuple):
    p: int = IDLE
    k1: int = 0
    r1: int = 0
    r2: int = 0
    r0: int = 5
    r3: int = 6


def rows(seed: int, count: int) -> list[Row]:
    """The edge rows followed by seeded rows, `count` in all."""
    if count < MINIMUM_ROWS:
        raise ValueError(f"the trial needs at least {MINIMUM_ROWS} rows, not {count}")
    edge = []
    for index, (m, k, go, x) in enumerate(itertools.product(range(4), range(4), (0, 1),
                                                            EDGES32)):
        edge.append(Row(m, (m + k + index) % 4, k, (index // 3) % 4, go, x,
                        EDGES32[(index // 5) % 4], EDGES64[(index // 7) % 4]))
    rng = random.Random(seed)  # noqa: S311 - reproducible trial rows, no secrets

    def draw(near: tuple[int, ...], bits: int) -> int:
        if rng.getrandbits(1):
            return rng.getrandbits(bits)
        return near[rng.getrandbits(8) % len(near)]

    seeded = [Row(rng.getrandbits(2), rng.getrandbits(2), rng.getrandbits(2),
                  rng.getrandbits(2), rng.getrandbits(1), draw(NEAR32, 32), draw(NEAR32, 32),
                  draw(NEAR64, 64)) for _ in range(count - len(edge))]
    return edge + seeded


def coverage(table: list[Row]) -> dict[str, list[int]]:
    """Each input's constructors or edge values, refusing a table that misses one."""
    need = {"m": range(4), "j": range(4), "k": range(4), "n": range(4), "go": (0, 1),
            "x": EDGES32, "y": EDGES32, "w": EDGES64}
    covered: dict[str, list[int]] = {}
    for name, values in need.items():
        seen = {getattr(row, name) for row in table}
        covered[name] = sorted(seen & set(values))
        if covered[name] != sorted(values):
            raise ValueError(f"input {name} misses an edge value")
    return covered


def step(state: State, row: Row) -> tuple[State, Answer]:
    """switch_control.lus read directly, one instant."""
    m, j, k, n, go, x, y, w = row
    a = x if go else y
    b = (0, (x + 1) & M32, y ^ x, 7)[m]
    c = {RUN: x, FAULT: y}.get(j, 9)
    f = (w + 1) & M64 if state.p == HOLD else w
    g = int(bool(go) and x < y)
    s = state.k1 if go else 0
    v = s ^ x
    q = (0, state.r1, state.r2, 1)[k]
    z = (q + y) & M32
    h = (state.r0, 2, 3, 4)[n]
    e = (10, 11, 12, state.r3)[m]
    after = State(p=m,
                  k1=(v + 1) & M32 if go else state.k1,
                  r1=z if k == RUN else state.r1,
                  r2=(z + 1) & M32 if k == HOLD else state.r2,
                  r0=(h + x) & M32 if n == IDLE else state.r0,
                  r3=(h + z) & M32 if m == FAULT else state.r3)
    return after, Answer(a, b, c, q, z, s, v, h, e, f, g)


def answers(table: list[Row]) -> list[Answer]:
    """The answers to `table` from one reset."""
    state = State()
    out = []
    for row in table:
        state, answer = step(state, row)
        out.append(answer)
    return out


def chunks(table: list[Row], per: int) -> list[list[Row]]:
    if per < 1:
        raise ValueError("each program needs at least one row")
    return [table[at:at + per] for at in range(0, len(table), per)]


def emit(table: list[Row], emitted: Path, memory: str, output: str, step_name: str,
         reset: str, perturb: bool = False) -> str:
    """One program over `table`, from a reset."""
    for identifier in (memory, output, step_name, reset):
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", identifier) is None:
            raise ValueError("the emitted interface must be a C identifier")
    lines = ["// SPDX-License-Identifier: Apache-2.0",
             f"#include {json.dumps(emitted.resolve().as_posix())}",
             "int main(void)", "{", f"    struct {memory} state;",
             f"    struct {output} answer;", f"    {reset}(&state);"]
    for index, (row, answer) in enumerate(zip(table, answers(table), strict=True)):
        b = (answer.b + 1) & M32 if perturb and index == 0 else answer.b
        lines += [f"    {step_name}(&state, &answer, {row.m}, {row.j}, {row.k}, {row.n}, "
                  f"{row.go}, {row.x}U, {row.y}U, {row.w}ULL);",
                  f"    if (answer.a != {answer.a}U || answer.b != {b}U ||",
                  f"        answer.c != {answer.c}U || answer.q != {answer.q}U ||",
                  f"        answer.z != {answer.z}U || answer.s != {answer.s}U ||",
                  f"        answer.v != {answer.v}U || answer.h != {answer.h}U ||",
                  f"        answer.e != {answer.e}U || answer.f != {answer.f}ULL ||",
                  f"        answer.g != {answer.g}) return 1;"]
    lines += ["    return 0;", "}", ""]
    return "\n".join(lines)


def table_text(table: list[Row], per: int) -> str:
    """Each program's rows and expected answers one per line, the bytes the summary
    digests."""
    return "".join(" ".join(map(str, (*row, *answer))) + "\n"
                   for part in chunks(table, per)
                   for row, answer in zip(part, answers(part), strict=True))


def _identity(data: bytes) -> dict[str, object]:
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--count", required=True, type=int)
    parser.add_argument("--rows", required=True, type=int)
    parser.add_argument("--emitted", required=True, type=Path)
    for name in ("memory", "output", "step", "reset"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--perturb", action="store_true")
    args = parser.parse_args(argv)
    if not args.emitted.is_file():
        parser.error("the emitted Clight file is missing")
    table = rows(args.seed, args.count)
    covered = coverage(table)
    parts = chunks(table, args.rows)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    width = len(str(len(parts) - 1))
    listed = []
    first = 0
    for index, part in enumerate(parts):
        if args.perturb and index:
            break
        text = emit(part, args.emitted, args.memory, args.output, args.step, args.reset,
                    args.perturb)
        path = args.out_dir / f"control-{index:0{width}d}.c"
        data = text.encode("utf-8")
        path.write_bytes(data)
        listed.append({"path": str(path), **_identity(data), "first_row": first,
                       "rows": len(part)})
        first += len(part)
    if args.summary is not None:
        summary = {
            "generator": "supervisor/route/switch_control.py", "seed": args.seed,
            "count": len(table), "edge_rows": 128, "seeded_rows": len(table) - 128,
            "rows_per_program": args.rows, "programs_split": len(parts),
            "reset_per_program": True, "edges": covered,
            "rows_sha256": hashlib.sha256(table_text(table, args.rows).encode()).hexdigest(),
            "perturb": args.perturb, "programs": listed,
        }
        args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8",
                                newline="\n")
    print(f"emitted {len(listed)} program(s) over {first} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
