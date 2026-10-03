# SPDX-License-Identifier: Apache-2.0
"""Split the probe's straight-line driver into programs that fit compiler-diff's text window.

`compiler-diff program` places a program's text between 0x80000000 and its data section
at 0x80008000, so a driver whose `main` checks every row in one straight line does not
fit (F-473). This reads the driver [probe.py](probe.py) emits, unchanged, and writes
programs that each check a consecutive run of its rows. Each program is the driver's
own lines: its prologue up to the first row, `--rows` of its row blocks, and its
epilogue. The node the probe drives has no memory, so a row's answer does not depend
on the rows before it, and no program needs a reset or a replayed row.

A row block is the lines from one call of the step function to the next, and the split
refuses a driver of any other layout. The record binds the source driver, each program
and its rows, and states that the programs' row blocks, rejoined between the one
prologue and epilogue, give back the source driver byte for byte.

    python3 split_probe.py DRIVER.c --step F --rows N --out-dir DIR [--record FILE.json]
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

EPILOGUE = ["    return 0;", "}", ""]


def split(driver: str, step: str, rows: int) -> tuple[str, list[list[str]], str]:
    """The prologue, the row blocks, and the epilogue of a straight-line driver."""
    if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", step) is None:
        raise ValueError("the step function must be a C identifier")
    if rows < 1:
        raise ValueError("each program needs at least one row")
    lines = driver.split("\n")
    call = f"    {step}(&state, &answer,"
    starts = [k for k, line in enumerate(lines) if line.startswith(call)]
    if not starts:
        raise ValueError(f"the driver never calls {step}")
    if lines[-len(EPILOGUE):] != EPILOGUE:
        raise ValueError("the driver does not end in `return 0;` and a closing brace")
    end = len(lines) - len(EPILOGUE)
    blocks = [lines[a:b] for a, b in zip(starts, [*starts[1:], end], strict=True)]
    width = {len(block) for block in blocks}
    if len(width) != 1:
        raise ValueError(f"row blocks of differing lengths {sorted(width)}")
    for block in blocks:
        if not block[-1].endswith(") return 1;") or any(
                line.startswith(call) for line in block[1:]):
            raise ValueError(f"a row block that is not one call and its checks: {block}")
    prologue = "\n".join(lines[:starts[0]]) + "\n"
    if "int main(void)" not in prologue:
        raise ValueError("the driver's prologue defines no main")
    return prologue, blocks, "\n".join(EPILOGUE)


def programs(driver: str, step: str, rows: int) -> list[tuple[int, int, str]]:
    """(first row, row count, text) for each program, in row order."""
    prologue, blocks, epilogue = split(driver, step, rows)
    out = []
    for first in range(0, len(blocks), rows):
        chunk = blocks[first:first + rows]
        body = "".join("\n".join(block) + "\n" for block in chunk)
        out.append((first, len(chunk), prologue + body + epilogue))
    rejoined = prologue + "".join("\n".join(b) + "\n" for b in blocks) + epilogue
    if rejoined != driver:
        raise ValueError("the row blocks do not rejoin into the driver")
    return out


def _identity(data: bytes) -> dict[str, object]:
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("driver", type=Path)
    parser.add_argument("--step", required=True)
    parser.add_argument("--rows", required=True, type=int)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--record", type=Path)
    args = parser.parse_args(argv)
    raw = args.driver.read_bytes()
    try:
        made = programs(raw.decode("utf-8"), args.step, args.rows)
    except (UnicodeDecodeError, ValueError) as err:
        print(f"refused: {args.driver}: {err}", file=sys.stderr)
        return 2
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.driver.stem
    width = len(str(len(made) - 1))
    listed = []
    for index, (first, count, text) in enumerate(made):
        path = args.out_dir / f"{stem}-{index:0{width}d}.c"
        data = text.encode("utf-8")
        path.write_bytes(data)
        listed.append({"path": str(path), **_identity(data), "first_row": first,
                       "rows": count})
    record = {
        "splitter": "supervisor/route/split_probe.py",
        "driver": {"path": str(args.driver), **_identity(raw)},
        "step": args.step,
        "rows_per_program": args.rows,
        "row_count": sum(count for _, count, _ in made),
        "programs": listed,
        "rejoins_byte_for_byte": True,
    }
    if args.record is not None:
        args.record.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8",
                               newline="\n")
    print(f"split {record['row_count']} rows into {len(listed)} program(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
