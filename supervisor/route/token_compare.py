# SPDX-License-Identifier: Apache-2.0
"""Compare printed and normalized Clight token by token, independently of the normalizer.

The token streams come from clang's lexer (`-Xclang -dump-tokens`), not from
`normalize.py`, and this module neither imports nor repeats that module's parser. The
normalized stream must equal the printed one with whole `_Alignas ( 8 )` groups deleted
and nothing inserted; each group, deleted or retained, is then placed by its own
bracket context in the printed stream, and a group before a pointer declarator is
placed at no enumerated position. The bytes must also differ by exactly one
` _Alignas(8)` span per deleted group.

`--step NAME` is the probe's predicate: every deleted group sits in a parameter
declarator of NAME's prototype or definition, and none is retained. `--control` is the
control node's: every deleted group sits at an enumerated position, every retained one
is a structure member, and each position (prototype, definition and extern parameters,
a return type, a register temporary and a cast) and a retained member occur at least
once.

    python3 token_compare.py --clang CLANG --original A --normalized B \
        (--step NAME | --control) --out REPORT.json

Exit 0 when the predicate holds, 1 when it does not, 2 when the input is unusable.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

GROUP = (("_Alignas", "_Alignas"), ("l_paren", "("), ("numeric_constant", "8"),
         ("r_paren", ")"))
TEXT = " _Alignas(8)"
_DUMP = re.compile(r"^(?P<kind>\w+) '(?P<text>[^']*)'\t.*Loc=<.*:(?P<line>\d+):(?P<col>\d+)>$")
# A parenthesis after one of these opens a call or an operand, never a cast.
_NOT_CAST = frozenset({"identifier", "numeric_constant", "r_paren", "r_square", "sizeof",
                       "_Alignof", "alignof", "__alignof"})
ENUMERATED = frozenset({"parameter:prototype", "parameter:definition", "parameter:extern",
                        "return:prototype", "return:definition", "return:extern",
                        "register", "cast"})
CONTROL_NEEDS = ("parameter:prototype", "parameter:definition", "parameter:extern",
                 "return", "register", "cast")

type Tok = tuple[str, str, int, int]


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


def _is_group(tokens: list[Tok], at: int) -> bool:
    return [t[:2] for t in tokens[at:at + 4]] == list(GROUP)


def align(original: list[Tok], normalized: list[Tok]) -> list[int]:
    """Indices in `original` of the groups deleted to give `normalized`, or ValueError."""
    deleted: list[int] = []
    i = j = 0
    while i < len(original):
        if _is_group(original, i) and not _is_group(normalized, j):
            if i + 4 < len(original) and _is_group(original, i + 4):
                raise ValueError(f"adjacent alignment groups at token {i}")
            deleted.append(i)
            i += 4
        elif j < len(normalized) and original[i][:2] == normalized[j][:2]:
            i += 1
            j += 1
        else:
            got = normalized[j][:2] if j < len(normalized) else "end"
            raise ValueError(f"token {i} {original[i][:2]} differs from normalized {got}")
    if j != len(normalized):
        raise ValueError(f"normalized stream has {len(normalized) - j} extra token(s)")
    return deleted


def byte_removals(original: str, normalized: str) -> int:
    """How many ` _Alignas(8)` spans delete `original` into `normalized`, or ValueError."""
    i = j = removed = 0
    while i < len(original):
        if original.startswith(TEXT, i) and not normalized.startswith(TEXT, j):
            removed += 1
            i += len(TEXT)
        elif j < len(normalized) and original[i] == normalized[j]:
            i += 1
            j += 1
        else:
            raise ValueError(f"byte {i} differs by more than an alignment span")
    if j != len(normalized):
        raise ValueError("normalized bytes carry an insertion")
    return removed


class _Context:
    """Brace depth, open parentheses and top-level item start before each token."""

    def __init__(self, tokens: list[Tok]) -> None:
        self.toks = tokens
        self.depth: list[int] = []
        self.opens: list[tuple[int, ...]] = []
        self.item: list[int] = []
        self.close: dict[int, int] = {}
        depth, item = 0, 0
        stack: list[int] = []
        for index, (kind, _, _, _) in enumerate(tokens):
            self.depth.append(depth)
            self.opens.append(tuple(stack))
            self.item.append(item)
            if kind == "l_brace":
                depth += 1
            elif kind == "r_brace":
                depth -= 1
                if depth == 0:
                    item = index + 1
            elif kind == "semi" and depth == 0:
                item = index + 1
            elif kind == "l_paren":
                stack.append(index)
            elif kind == "r_paren" and stack:
                self.close[stack.pop()] = index

    def kind(self, index: int) -> str:
        return self.toks[index][0] if 0 <= index < len(self.toks) else ""

    def declared(self, paren: int, extern: bool) -> str:
        after = self.kind(self.close.get(paren, -2) + 1)
        return "extern" if extern else {"l_brace": "definition", "semi": "prototype"}.get(
            after, "unknown")

    def function(self, item: int) -> str:
        for at in range(item, len(self.toks) - 1):
            if self.depth[at] == 0 and self.kind(at) == "identifier" \
                    and self.kind(at + 1) == "l_paren":
                return self.toks[at][1]
        return ""

    def place(self, k: int) -> tuple[str, str, str]:
        """(position label, owner, type) of the `_Alignas` group at token `k`."""
        spell = [t[1] for t in self.toks]
        if spell[k - 2:k] != ["long", "long"]:
            return "other", "", spell[k - 1]
        start = k - 3 if spell[k - 3] == "unsigned" else k - 2
        typename = " ".join(spell[start:k])
        item = self.item[k]
        extern = self.kind(item) == "extern"
        if self.depth[k] == 0:
            opens = self.opens[k]
            if len(opens) == 1 and self.kind(opens[0] - 1) == "identifier" \
                    and self.kind(start - 1) in ("l_paren", "comma") \
                    and self.kind(k + 4) in ("identifier", "comma", "r_paren"):
                name = spell[opens[0] - 1]
                return f"parameter:{self.declared(opens[0], extern)}", name, typename
            if not opens and self.kind(k + 4) == "identifier" \
                    and self.kind(k + 5) == "l_paren" and start == item + int(extern):
                return f"return:{self.declared(k + 5, extern)}", spell[k + 4], typename
            return "other", "", typename
        if self.depth[k] == 1 and self.kind(item) == "struct" \
                and self.kind(item + 2) == "l_brace" \
                and self.kind(start - 1) in ("l_brace", "semi") \
                and self.kind(k + 4) == "identifier" and self.kind(k + 5) == "semi":
            return "member", spell[item + 1], typename
        owner = self.function(item)
        if self.kind(start - 1) == "register" and self.kind(start - 2) in ("l_brace", "semi") \
                and self.kind(k + 4) == "identifier" and self.kind(k + 5) == "semi":
            return "register", owner, typename
        if self.kind(start - 1) == "l_paren" and self.kind(k + 4) == "r_paren" \
                and self.kind(start - 2) not in _NOT_CAST:
            return "cast", owner, typename
        return "other", owner, typename


def compare(original: list[Tok], normalized: list[Tok], original_text: str,
            normalized_text: str, step: str | None) -> dict[str, object]:
    """The comparison's findings and every group's placement; empty failures is a pass."""
    failures: list[str] = []
    try:
        deleted = align(original, normalized)
    except ValueError as err:
        return {"failures": [f"token streams differ beyond deleted groups: {err}"]}
    context = _Context(original)
    groups = [k for k, tok in enumerate(original) if tok[0] == "_Alignas"]
    placed = []
    for k in groups:
        label, owner, typename = context.place(k)
        placed.append({"line": original[k][2], "column": original[k][3], "position": label,
                       "owner": owner, "type": typename,
                       "value": original[k + 2][1] if k + 2 < len(original) else "",
                       "deleted": k in deleted})
    try:
        removed = byte_removals(original_text, normalized_text)
    except ValueError as err:
        failures.append(f"bytes differ beyond alignment spans: {err}")
        removed = -1
    if removed != len(deleted):
        failures.append(f"{removed} byte span(s) removed against {len(deleted)} token group(s)")
    gone = [g for g in placed if g["deleted"]]
    kept = [g for g in placed if not g["deleted"]]
    if not gone:
        failures.append("no alignment group was deleted")
    if step is not None:
        allowed = {("parameter:prototype", step), ("parameter:definition", step)}
        failures += [f"deleted group at line {g['line']} is {g['position']} of {g['owner']}"
                     for g in gone if (g["position"], g["owner"]) not in allowed]
        failures += [f"retained group at line {g['line']} ({g['position']})" for g in kept]
    else:
        failures += [f"deleted group at line {g['line']} is {g['position']}"
                     for g in gone if g["position"] not in ENUMERATED]
        failures += [f"retained group at line {g['line']} is {g['position']}, not a member"
                     for g in kept if g["position"] != "member"]
        labels = {str(g["position"]) for g in gone}
        failures += [f"no deleted group at a {need} position" for need in CONTROL_NEEDS
                     if not any(label == need or label.startswith(need + ":")
                                for label in labels)]
        if not kept:
            failures.append("no retained member alignment")
    counts: dict[str, int] = {}
    for g in placed:
        key = f"{'deleted' if g['deleted'] else 'retained'} {g['position']}"
        counts[key] = counts.get(key, 0) + 1
    return {"failures": failures, "deleted": len(gone), "retained": len(kept),
            "byte_spans_removed": removed, "by_position": dict(sorted(counts.items())),
            "groups": placed}


def _identity(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clang", required=True)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--normalized", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--step")
    mode.add_argument("--control", action="store_true")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        original = lex(args.clang, args.original)
        normalized = lex(args.clang, args.normalized)
        original_text = args.original.read_text(encoding="ascii")
        normalized_text = args.normalized.read_text(encoding="ascii")
    except (OSError, ValueError, subprocess.TimeoutExpired) as err:
        print(f"unusable input: {err}", file=sys.stderr)
        return 2
    version = subprocess.run([args.clang, "--version"], capture_output=True,
                             encoding="utf-8", check=False, timeout=60).stdout.splitlines()
    clang = Path(args.clang)
    result = compare(original, normalized, original_text, normalized_text, args.step)
    failures = result["failures"]
    if not isinstance(failures, list):
        raise TypeError("the comparison's failures are not a list")
    report = {
        "predicate": f"step {args.step}" if args.step else "control",
        "lexer": {**_identity(clang.resolve()), "version": version[0] if version else "",
                  "argv": [args.clang, "-std=c11", "-fsyntax-only", "-Xclang",
                           "-dump-tokens", "-x", "c"]},
        "original": {**_identity(args.original), "tokens": len(original)},
        "normalized": {**_identity(args.normalized), "tokens": len(normalized)},
        **result,
        "verdict": "pass" if not failures else "fail",
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{report['verdict']}: {report.get('deleted', 0)} deleted, "
          f"{report.get('retained', 0)} retained; " + "; ".join(map(str, failures)))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
