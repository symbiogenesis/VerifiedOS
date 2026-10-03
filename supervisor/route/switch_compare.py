# SPDX-License-Identifier: Apache-2.0
"""Compare normalized and switch-rewritten Clight token by token, independently of the rewrite.

The token streams come from clang's lexer (`-Xclang -dump-tokens`), not from
`switch_rewrite.py`, and this module neither imports nor repeats that module's parser.
Each `switch` in the normalized stream is read here by its own grammar, the layout
Vélus's one Obc `Switch` translation site prints:

    switch ( E ) { case K1 : B1 break ; ... case Kn : Bn break ; default : D }

with n at least 1, each K a decimal integer greater than the one before, and no
`break`, label, brace, `if`, loop, `goto`, `continue` or `return` in a body except
inside a nested switch of the same grammar. Each group is classified into one of the
declared shapes by its case count and empty bodies:

    if-else      one case with a non-empty body, a non-empty default
    if-only      one case with a non-empty body, an empty default
    else-only    one case labelled 0 with an empty body, a non-empty default
    chain-else   two or more cases with non-empty bodies, a non-empty default
    chain-only   two or more cases with non-empty bodies, an empty default

and a group of no declared shape is a failure. The rewritten stream must equal the
normalized one outside the groups, and each group must appear as

    if ( ( E ) == K1 ) { B1 } else if ( ( E ) == K2 ) { B2 } ... else { D }

with each body compared the same way. The bytes outside the top-level groups must also
be equal, and no `switch`, `case`, `default` or `break` may remain.

`--node` is the node's predicate: at least one group, every group declared. `--control`
is the control program's: every declared shape occurs, a group nests inside another
group's body, and some group's labels are not 0, 1, ... in order.

    python3 switch_compare.py --clang CLANG --normalized A --rewritten B \
        (--node | --control) --out REPORT.json

Exit 0 when the predicate holds, 1 when it does not, 2 when the input is unusable.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

SHAPES = ("if-else", "if-only", "else-only", "chain-else", "chain-only")
_DUMP = re.compile(r"^(?P<kind>\w+) '(?P<text>[^']*)'\t.*Loc=<.*:(?P<line>\d+):(?P<col>\d+)>$")
_DECIMAL = re.compile(r"0|[1-9][0-9]*")
# Token kinds a body holds only as part of a nested switch, or never.
_BODY_REFUSED = frozenset({"case", "default", "colon", "question", "l_brace", "r_brace",
                           "if", "else", "while", "for", "do", "goto", "continue",
                           "return"})
_GONE = frozenset({"switch", "case", "default", "break"})

type Tok = tuple[str, str, int, int]


class MismatchError(ValueError):
    """The rewritten stream is not the declared lowering of the normalized one."""


def parse_dump(text: str) -> list[Tok]:
    """clang's token dump as (kind, spelling, line, column), stopping at `eof`."""
    tokens: list[Tok] = []
    for line in text.splitlines():
        match = _DUMP.match(line)
        if match is None:
            raise ValueError(f"unreadable token dump line: {line!r}")
        if match["kind"] == "eof":
            return tokens
        tokens.append((match["kind"], match["text"], int(match["line"]), int(match["col"])))
    raise ValueError("token dump has no eof")


def lex(clang: str, source: Path) -> list[Tok]:
    done = subprocess.run([clang, "-std=c11", "-fsyntax-only", "-Xclang", "-dump-tokens",
                           "-x", "c", str(source)], capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=120)
    if done.returncode != 0:
        raise ValueError(f"clang exited {done.returncode} on {source}: {done.stdout[-400:]}")
    return parse_dump(done.stderr)


@dataclass
class Group:
    """One normalized switch, by token index."""

    start: int
    scrutinee: tuple[int, int]          # [first, stop) of E
    cases: list[tuple[str, int, int]]   # label spelling, body [first, stop)
    default: tuple[int, int]            # body [first, stop)
    close: int                          # the closing brace
    depth: int
    shape: str = ""
    owner: str = ""
    children: list[Group] = field(default_factory=list)


class _Reader:
    """The normalized stream's switch groups, by this module's own grammar."""

    def __init__(self, toks: list[Tok]) -> None:
        self.toks = toks
        self.failures: list[str] = []

    def kind(self, index: int) -> str:
        return self.toks[index][0] if 0 <= index < len(self.toks) else "eof"

    def at(self, index: int) -> str:
        line, col = (self.toks[index][2], self.toks[index][3]) if index < len(self.toks) \
            else (0, 0)
        return f"line {line} column {col}"

    def need(self, index: int, kind: str) -> None:
        if self.kind(index) != kind:
            raise MismatchError(f"{self.at(index)}: expected {kind}, found {self.kind(index)}")

    def group(self, index: int, depth: int) -> Group:
        self.need(index + 1, "l_paren")
        level, close = 0, index + 1
        for close in range(index + 1, len(self.toks)):
            level += (self.kind(close) == "l_paren") - (self.kind(close) == "r_paren")
            if level == 0:
                break
        if level != 0 or close == index + 2:
            raise MismatchError(f"{self.at(index)}: a switch scrutinee is unbalanced or empty")
        if any(self.kind(k) in _BODY_REFUSED | _GONE | {"semi"}
               for k in range(index + 2, close)):
            raise MismatchError(f"{self.at(index)}: a statement token in a switch scrutinee")
        self.need(close + 1, "l_brace")
        group = Group(index, (index + 2, close), [], (0, 0), 0, depth)
        k = close + 2
        while self.kind(k) == "case":
            label = self.toks[k + 1][1] if k + 1 < len(self.toks) else ""
            if self.kind(k + 1) != "numeric_constant" or _DECIMAL.fullmatch(label) is None:
                raise MismatchError(f"{self.at(k + 1)}: case label {label!r} is not decimal")
            if group.cases and int(label) <= int(group.cases[-1][0]):
                raise MismatchError(f"{self.at(k + 1)}: case label {label} does not increase")
            self.need(k + 2, "colon")
            stop = self.body(k + 3, group, case=True)
            self.need(stop + 1, "semi")
            if self.kind(stop + 2) not in ("case", "default"):
                raise MismatchError(f"{self.at(stop)}: a break that does not precede a label")
            group.cases.append((label, k + 3, stop))
            k = stop + 2
        if not group.cases:
            raise MismatchError(f"{self.at(index)}: a switch with no case")
        self.need(k, "default")
        self.need(k + 1, "colon")
        group.close = self.body(k + 2, group, case=False)
        group.default = (k + 2, group.close)
        group.shape = self.shape(group)
        return group

    def body(self, k: int, group: Group, case: bool) -> int:
        while True:
            kind = self.kind(k)
            if kind == "eof":
                raise MismatchError(f"{self.at(group.start)}: an unterminated switch")
            if kind == "switch":
                inner = self.group(k, group.depth + 1)
                group.children.append(inner)
                k = inner.close + 1
                continue
            if kind == "break":
                if not case:
                    raise MismatchError(f"{self.at(k)}: a break in a default body")
                return k
            if kind == "r_brace" and not case:
                return k
            if kind in _BODY_REFUSED:
                raise MismatchError(f"{self.at(k)}: {kind} in a switch body")
            k += 1

    def shape(self, group: Group) -> str:
        empty = [label for label, first, stop in group.cases if first == stop]
        default_empty = group.default[0] == group.default[1]
        if empty:
            if len(group.cases) == 1 and empty == ["0"] and not default_empty:
                return "else-only"
            raise MismatchError(f"{self.at(group.start)}: an empty case body outside else-only")
        if len(group.cases) == 1:
            return "if-only" if default_empty else "if-else"
        return "chain-only" if default_empty else "chain-else"


class _Matcher:
    """Walk both streams together; every difference must be a declared lowering."""

    def __init__(self, normalized: list[Tok], rewritten: list[Tok]) -> None:
        self.n = normalized
        self.r = rewritten
        self.reader = _Reader(normalized)
        self.groups: list[Group] = []
        self.spans: list[tuple[int, int, int, int]] = []  # n start, n close, r start, r close

    def expect(self, j: int, kind: str, text: str | None = None) -> int:
        got = self.r[j][:2] if j < len(self.r) else ("eof", "")
        if got[0] != kind or (text is not None and got[1] != text):
            line = self.r[j][2] if j < len(self.r) else 0
            raise MismatchError(f"rewritten line {line}: expected {kind} "
                           f"{text or ''}, found {got[0]} {got[1]!r}")
        return j + 1

    def region(self, i: int, stop: int, j: int, depth: int) -> int:
        """Match normalized tokens [i, stop) against the rewritten stream from j."""
        while i < stop:
            if self.n[i][0] == "switch":
                group = self.reader.group(i, depth)
                start = j
                j = self.group(group, j)
                if depth == 0:
                    self.spans.append((group.start, group.close, start, j - 1))
                i = group.close + 1
                continue
            if self.n[i][0] in ("case", "default", "break"):
                raise MismatchError(f"normalized line {self.n[i][2]}: {self.n[i][0]} outside "
                               "a switch")
            if j >= len(self.r) or self.r[j][:2] != self.n[i][:2]:
                got = self.r[j][:2] if j < len(self.r) else ("eof", "")
                raise MismatchError(f"normalized line {self.n[i][2]} {self.n[i][:2]} differs "
                               f"from rewritten {got}")
            i += 1
            j += 1
        return j

    def scrutinee(self, group: Group, j: int) -> int:
        j = self.expect(j, "l_paren")
        for k in range(*group.scrutinee):
            j = self.expect(j, self.n[k][0], self.n[k][1])
        return self.expect(j, "r_paren")

    def group(self, group: Group, j: int) -> int:
        self.groups.append(group)
        for index, (label, first, stop) in enumerate(group.cases):
            if index:
                j = self.expect(j, "else")
            j = self.expect(j, "if")
            j = self.expect(j, "l_paren")
            j = self.scrutinee(group, j)
            j = self.expect(j, "equalequal")
            j = self.expect(j, "numeric_constant", label)
            j = self.expect(j, "r_paren")
            j = self.expect(j, "l_brace")
            j = self.nested(first, stop, j, group)
            j = self.expect(j, "r_brace")
        j = self.expect(j, "else")
        j = self.expect(j, "l_brace")
        j = self.nested(*group.default, j, group)
        return self.expect(j, "r_brace")

    def nested(self, first: int, stop: int, j: int, group: Group) -> int:
        return self.region(first, stop, j, group.depth + 1)


def _offsets(text: str) -> list[int]:
    starts = [0]
    starts.extend(at + 1 for at, char in enumerate(text) if char == "\n")
    return starts


def _byte(starts: list[int], tok: Tok) -> int:
    return starts[tok[2] - 1] + tok[3] - 1


def outside_bytes(normalized: list[Tok], rewritten: list[Tok], normalized_text: str,
                  rewritten_text: str, spans: list[tuple[int, int, int, int]]) -> list[str]:
    """Differences between the two texts outside the top-level groups."""
    ns, rs = _offsets(normalized_text), _offsets(rewritten_text)
    pieces_n: list[str] = []
    pieces_r: list[str] = []
    at_n = at_r = 0
    for n0, n1, r0, r1 in spans:
        pieces_n.append(normalized_text[at_n:_byte(ns, normalized[n0])])
        pieces_r.append(rewritten_text[at_r:_byte(rs, rewritten[r0])])
        at_n = _byte(ns, normalized[n1]) + 1
        at_r = _byte(rs, rewritten[r1]) + 1
    pieces_n.append(normalized_text[at_n:])
    pieces_r.append(rewritten_text[at_r:])
    return [f"bytes outside the groups differ in segment {k}"
            for k, (a, b) in enumerate(zip(pieces_n, pieces_r, strict=True)) if a != b]


def _owner(tokens: list[Tok], index: int) -> str:
    """The function a top-level token sits in: the name before the last `(` that a
    file-scope `{` followed."""
    depth, name, current = 0, "", ""
    for k in range(index + 1):
        kind = tokens[k][0]
        if depth == 0 and kind == "identifier" and k + 1 < len(tokens) \
                and tokens[k + 1][0] == "l_paren":
            name = tokens[k][1]
        if kind == "l_brace":
            if depth == 0:
                current = name
            depth += 1
        elif kind == "r_brace":
            depth -= 1
    return current


def compare(normalized: list[Tok], rewritten: list[Tok], normalized_text: str,
            rewritten_text: str, control: bool) -> dict[str, object]:
    """The comparison's findings and every group's placement; empty failures is a pass."""
    matcher = _Matcher(normalized, rewritten)
    try:
        end = matcher.region(0, len(normalized), 0, 0)
    except MismatchError as err:
        return {"failures": [f"not a declared lowering: {err}"]}
    if end != len(rewritten):
        return {"failures": [f"not a declared lowering: the rewritten stream has "
                             f"{len(rewritten) - end} extra token(s)"]}
    failures = outside_bytes(normalized, rewritten, normalized_text, rewritten_text,
                             matcher.spans)
    left = sorted({tok[0] for tok in rewritten if tok[0] in _GONE})
    failures += [f"the rewritten stream still holds {kind}" for kind in left]
    groups = []
    for group in sorted(matcher.groups, key=lambda g: g.start):
        labels = [int(label) for label, _, _ in group.cases]
        groups.append({"line": normalized[group.start][2],
                       "column": normalized[group.start][3],
                       "owner": _owner(normalized, group.start), "depth": group.depth,
                       "shape": group.shape, "labels": labels,
                       "in_order": labels == list(range(len(labels)))})
    if not groups:
        failures.append("no switch group was lowered")
    by_shape = {shape: sum(g["shape"] == shape for g in groups) for shape in SHAPES}
    if control:
        failures += [f"no {shape} group" for shape, count in by_shape.items() if not count]
        if not any(g["depth"] for g in groups):
            failures.append("no group nests inside another group's body")
        if all(g["in_order"] for g in groups):
            failures.append("every group's labels are 0, 1, ... in order")
    return {"failures": failures, "lowered": len(groups), "by_shape": by_shape,
            "groups": groups}


def _identity(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clang", required=True)
    parser.add_argument("--normalized", required=True, type=Path)
    parser.add_argument("--rewritten", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--node", action="store_true")
    mode.add_argument("--control", action="store_true")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        normalized = lex(args.clang, args.normalized)
        rewritten = lex(args.clang, args.rewritten)
        normalized_text = args.normalized.read_text(encoding="ascii")
        rewritten_text = args.rewritten.read_text(encoding="ascii")
    except (OSError, ValueError, subprocess.TimeoutExpired) as err:
        print(f"unusable input: {err}", file=sys.stderr)
        return 2
    version = subprocess.run([args.clang, "--version"], capture_output=True,
                             encoding="utf-8", check=False, timeout=60).stdout.splitlines()
    result = compare(normalized, rewritten, normalized_text, rewritten_text, args.control)
    failures = result["failures"]
    if not isinstance(failures, list):
        raise TypeError("the comparison's failures are not a list")
    report = {
        "predicate": "control" if args.control else "node",
        "lexer": {**_identity(Path(args.clang).resolve()),
                  "version": version[0] if version else "",
                  "argv": [args.clang, "-std=c11", "-fsyntax-only", "-Xclang",
                           "-dump-tokens", "-x", "c"]},
        "normalized": {**_identity(args.normalized), "tokens": len(normalized)},
        "rewritten": {**_identity(args.rewritten), "tokens": len(rewritten)},
        **result,
        "verdict": "pass" if not failures else "fail",
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{report['verdict']}: {report.get('lowered', 0)} group(s) lowered; "
          + "; ".join(map(str, failures)))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
