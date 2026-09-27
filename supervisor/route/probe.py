# SPDX-License-Identifier: Apache-2.0
"""Emit the small-node trial driver from the actual C planner's answers.

This does not compute a reference result. Generated C includes the Vélus Clight
dump verbatim; the printed interface names are explicit command-line inputs.
Both the native C compiler and compiler-diff consume this same driver.
"""

import argparse
import json
import re
from pathlib import Path


def emit(fixtures: str, emitted: Path, memory: str, output: str, step: str,
         perturb: bool = False) -> str:
    for identifier in (memory, output, step):
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", identifier) is None:
            raise ValueError("the emitted interface must be a C identifier")
    rows = []
    for index, line in enumerate(fixtures.splitlines()):
        fields = line.split()
        if len(fields) != 13 or any(not field.isascii() or not field.isdecimal()
                                    for field in fields):
            raise ValueError(f"malformed oracle row {index}")
        row = tuple(map(int, fields))
        limits = (2**32, 2**32, 2**64, 2**64, 2, 2, 17, 2**16, 2**32, 2**16, 16, 16, 16)
        if any(value >= limit for value, limit in zip(row, limits, strict=True)):
            raise ValueError(f"out-of-domain oracle row {index}")
        rows.append(row)
    if not rows or not any(row[5] for row in rows) or not any(not row[5] for row in rows):
        raise ValueError("the trial needs accepted and refused lifecycle fixtures")
    lines = ["// SPDX-License-Identifier: Apache-2.0",
             f"#include {json.dumps(emitted.resolve().as_posix())}",
             "int main(void)", "{", f"    struct {memory} state;",
             f"    struct {output} answer;"]
    changed = False
    for row in rows:
        (restart, attempts, snapshot, current, retired, accepted, count, stop,
         delay, grant, first, second, third) = row
        if perturb and accepted and not changed:
            count += 1
            changed = True
        lines += [f"    {step}(&state, &answer, {restart}U, {attempts}U,",
                  f"        {snapshot}ULL, {current}ULL, {retired});",
                  f"    if (answer.accepted != {accepted} || answer.count != {count}U ||",
                  f"        answer.stop_members != {stop}U || answer.delay != {delay}U ||",
                  f"        answer.storage_grant != {grant}U || answer.first_unit != {first}U ||",
                  f"        answer.second_unit != {second}U || answer.third_unit != {third}U) return 1;"]
    lines += ["    return 0;", "}", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", required=True, type=Path)
    parser.add_argument("--emitted", required=True, type=Path)
    parser.add_argument("--memory", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--perturb", action="store_true")
    args = parser.parse_args()
    if not args.emitted.is_file():
        parser.error("the emitted Clight file is missing")
    args.out.write_text(emit(args.fixtures.read_text(encoding="utf-8"), args.emitted,
                            args.memory, args.output, args.step, args.perturb),
                        encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
