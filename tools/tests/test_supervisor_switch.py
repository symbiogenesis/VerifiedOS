# SPDX-License-Identifier: Apache-2.0
"""The supervisor route's Clight switch rewrite, its token comparison and its split drivers.

[supervisor/route/](../../supervisor/route/README.md) holds the authored tools M6.1b-iv's
bounded trial runs: `switch_rewrite.py` lowers the `switch` shapes Vélus's one Obc
`Switch` translation site prints into `if` chains, `switch_compare.py` checks a rewrite
through clang's lexer without reading the rewrite, `split_probe.py` splits the probe's
straight-line driver into programs that fit compiler-diff's text window, and
`switch_control.py` generates the switch control program's rows, answers and split
drivers. The fixture below is authored in the printer's layout for a hypothetical node;
it is not Vélus output.
"""

import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from types import ModuleType

from tests.harness import TOOLS, Case, ensure

ROUTE = TOOLS.parent / "supervisor" / "route"

HEAD = """struct demo;
struct fun$step$demo;
struct demo {
  unsigned char p;
};

struct fun$step$demo {
  unsigned int y;
  unsigned int z;
};

void fun$step$demo(struct demo *, struct fun$step$demo *, unsigned char, unsigned char, unsigned int);
void fun$step$demo(struct demo *obc2c$self, struct fun$step$demo *obc2c$out, unsigned char m, unsigned char go, unsigned int x)
{
"""
NESTED = """  switch (go) {
    case 0:
      (*obc2c$out).y = x;
      break;
    default:
      switch (x < 3U) {
        case 0:
          (*obc2c$out).z = 1U;
          break;
        default:
          (*obc2c$out).z = 2U;

      }
      (*obc2c$out).y = 0U;

  }
"""
CHAINS = """  switch (m) {
    case 0:
      (*obc2c$out).y = 4U;
      break;
    case 2:
      (*obc2c$out).y = 5U;
      break;
    default:
      (*obc2c$out).y = 6U;

  }
  switch (m) {
    case 1:
      (*obc2c$self).p = 1;
      break;
    case 3:
      (*obc2c$self).p = 3;
      break;
    default:

  }
  switch ((*obc2c$self).p) {
    case 2:
      (*obc2c$out).z = x;
      break;
    default:

  }
  switch (go) {
    case 0:
      break;
    default:
      (*obc2c$self).p = m;

  }
"""
TAIL = """  return;
}

"""
FIXTURE = HEAD + NESTED + CHAINS + TAIL
# Each label and `break` text replaced, every other byte kept.
LOWERED = (("switch (go) {\n    case 0:", "if ((go) == 0) {"),
           ("switch (x < 3U) {\n        case 0:", "if ((x < 3U) == 0) {"),
           ("break;\n        default:", "} else {"),
           ("switch (m) {\n    case 0:", "if ((m) == 0) {"),
           ("break;\n    case 2:", "} else if ((m) == 2) {"),
           ("switch (m) {\n    case 1:", "if ((m) == 1) {"),
           ("break;\n    case 3:", "} else if ((m) == 3) {"),
           ("switch ((*obc2c$self).p) {\n    case 2:", "if (((*obc2c$self).p) == 2) {"),
           ("break;\n    default:", "} else {"))


def _lowered(text: str) -> str:
    for before, after in LOWERED:
        text = text.replace(before, after)
    return text


EXPECTED = _lowered(FIXTURE)


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"supervisor_switch_{name}",
                                                  ROUTE / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load supervisor/route/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REWRITE = _load("switch_rewrite")
COMPARE = _load("switch_compare")
SPLIT = _load("split_probe")
CONTROL = _load("switch_control")
PROBE = _load("probe")


def _refused(text: str, words: str) -> None:
    try:
        REWRITE.rewrite(text)
    except REWRITE.RefusalError as err:
        ensure(words in str(err), f"refusal {err} does not say {words!r}")
    else:
        raise AssertionError(f"accepted input that should mention {words!r}")


def _lowers() -> None:
    out, sites = REWRITE.rewrite(FIXTURE)
    ensure(out == EXPECTED, "only the label and break text may change, byte for byte")
    shapes = [(site.shape, site.labels, site.depth) for site in sites]
    ensure(shapes == [("if-else", [0], 0), ("if-else", [0], 1), ("chain-else", [0, 2], 0),
                      ("chain-only", [1, 3], 0), ("if-only", [2], 0),
                      ("else-only", [0], 0)], f"groups in source order: {shapes}")
    ensure([site.owner for site in sites] == ["fun$step$demo"] * 6, "owners")
    ensure((sites[1].line, sites[1].column, sites[1].scrutinee) == (20, 7, "x < 3U"),
           f"a group carries its own line, column and scrutinee: {sites[1]}")
    ensure(set(REWRITE.SHAPES) == {s.shape for s in sites}, "the fixture holds every shape")


def _identity() -> None:
    free = HEAD + "  (*obc2c$out).y = x;\n" + TAIL
    for text in (free, EXPECTED, "struct a;\n/*skip*/\n"):
        out, sites = REWRITE.rewrite(text)
        ensure(out == text and sites == [], "switch-free input must come back byte-identical")
    _refused("int x = 'a';\n", "unexpected character")


def _refusals() -> None:
    first = "    case 0:\n      (*obc2c$out).y = x;\n      break;\n"
    cases = {
        "a fall-through": NESTED.replace("y = x;\n      break;\n", "y = x;\n"),
        "no case": NESTED.replace(first, ""),
        "after the default": NESTED.replace("y = 0U;\n", "y = 0U;\n    case 1:\n      break;\n"),
        "does not increase": CHAINS.replace("case 2:", "case 0:"),
        "is not the printer's decimal": CHAINS.replace("case 2:", "case 0x2:"),
        "not the printer's decimal": CHAINS.replace("case 2:", "case 02:"),
        "exceeds an enumeration tag": CHAINS.replace("case 2:", "case 4294967296:"),
        "empty case body outside": CHAINS.replace("(*obc2c$out).y = 4U;\n", ""),
        "outside the declared else-only": CHAINS.replace(
            "    case 0:\n      break;\n    default:\n      (*obc2c$self).p = m;",
            "    case 1:\n      break;\n    default:\n      (*obc2c$self).p = m;"),
        "else-only shape": CHAINS.replace("      (*obc2c$self).p = m;\n", ""),
        "a `break` in the default body":
            NESTED.replace("(*obc2c$out).y = 0U;\n", "(*obc2c$out).y = 0U;\n      break;\n"),
        "a brace in a switch body": NESTED.replace("(*obc2c$out).y = x;",
                                                   "{ (*obc2c$out).y = x; }"),
        "`if` in a switch body": NESTED.replace("(*obc2c$out).y = x;",
                                                "if (x) (*obc2c$out).y = x;"),
        "`return` in a switch body": NESTED.replace("(*obc2c$out).y = x;", "return;"),
        "`:` in a switch body": NESTED.replace("(*obc2c$out).y = x;",
                                               "here: (*obc2c$out).y = x;"),
        "`?` in a switch body": NESTED.replace("(*obc2c$out).y = x;",
                                               "(*obc2c$out).y = x ? 1U : 2U;"),
        "in a switch's scrutinee": NESTED.replace("switch (go)", "switch (go ? 1 : 0)"),
        "no scrutinee": NESTED.replace("switch (go)", "switch ()"),
        "outside a switch": CHAINS + "  break;\n",
        "does not end in `break`": NESTED.replace("(*obc2c$out).y = x;\n      break;\n",
                                                  "(*obc2c$out).y = x;\n  }\n"),
    }
    for words, body in cases.items():
        text = HEAD + body + TAIL
        ensure(text != FIXTURE, f"the {words!r} variant changed nothing")
        _refused(text, words)
    _refused(HEAD + "  switch (go) {\n    case 0:\n      x = 1;\n", "unterminated switch")
    _refused(FIXTURE.replace("demo;", "démo;", 1), "non-ASCII")
    _refused(FIXTURE + "// note\n", "line comment")


def _cli() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-switch-") as tmp:
        root = Path(tmp)
        (root / "in.c").write_bytes(FIXTURE.encode("ascii"))
        code = REWRITE.main([str(root / "in.c"), "--out", str(root / "out.c"),
                             "--record", str(root / "record.json")])
        record = json.loads((root / "record.json").read_text(encoding="utf-8"))
        ensure(code == 0 and (root / "out.c").read_bytes() == EXPECTED.encode("ascii"),
               "the command writes the rewritten bytes")
        ensure(record["lowered"] == 6 and record["identical"] is False
               and record["site"]["sha256"] == REWRITE.SITE["sha256"]
               and record["by_shape"]["if-else"] == 2, f"the record: {record['by_shape']}")
        bad = FIXTURE.replace("case 2:", "case 0x2:")
        (root / "bad.c").write_bytes(bad.encode("ascii"))
        code = REWRITE.main([str(root / "bad.c"), "--out", str(root / "bad.out"),
                             "--record", str(root / "bad.json")])
        ensure(code == 2 and not (root / "bad.out").exists()
               and not (root / "bad.json").exists(), "a refusal writes nothing and exits 2")


_KINDS = {"(": "l_paren", ")": "r_paren", "{": "l_brace", "}": "r_brace", ";": "semi",
          ",": "comma", "*": "star", "&": "amp", ".": "period", "^": "caret", "=": "equal",
          "+": "plus", ":": "colon", "==": "equalequal", "<": "less", "?": "question"}
_WORDS = frozenset({"struct", "unsigned", "char", "int", "void", "return", "switch", "case",
                    "default", "break", "if", "else"})


def _dump(text: str) -> str:
    """clang's `-dump-tokens` layout for the fixture's vocabulary."""
    lines = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in re.finditer(r"/\*.*?\*/|[A-Za-z_$][A-Za-z0-9_$]*|[0-9][0-9A-Za-z]*|==|\S",
                                 line):
            tok = match.group()
            if tok.startswith("/*"):
                continue
            kind = (tok if tok in _WORDS else "numeric_constant" if tok[0].isdigit()
                    else _KINDS.get(tok, "identifier"))
            flags = " [StartOfLine]" if match.start() == 0 else ""
            lines.append(f"{kind} '{tok}'\t{flags}\tLoc=<x.c:{number}:{match.start() + 1}>")
    return "\n".join([*lines, "eof ''\t\tLoc=<x.c:1:1>"]) + "\n"


def _compare(normalized: str, rewritten: str, control: bool) -> list[str]:
    result = COMPARE.compare(COMPARE.parse_dump(_dump(normalized)),
                             COMPARE.parse_dump(_dump(rewritten)), normalized, rewritten,
                             control)
    return [str(failure) for failure in result["failures"]]


def _comparison() -> None:
    ensure(_compare(FIXTURE, EXPECTED, True) == [], "the control predicate holds")
    ensure(_compare(FIXTURE, EXPECTED, False) == [], "the node predicate holds")
    result = COMPARE.compare(COMPARE.parse_dump(_dump(FIXTURE)),
                             COMPARE.parse_dump(_dump(EXPECTED)), FIXTURE, EXPECTED, False)
    placed = [(g["shape"], g["labels"], g["depth"], g["owner"]) for g in result["groups"]]
    ensure(placed[0] == ("if-else", [0], 0, "fun$step$demo") and len(placed) == 6
           and [p[0] for p in placed] == ["if-else", "if-else", "chain-else", "chain-only",
                                          "if-only", "else-only"], f"placements: {placed}")
    wrong = {
        "label": EXPECTED.replace("((m) == 2)", "((m) == 1)"),
        "body": EXPECTED.replace("(*obc2c$out).y = 4U;", "(*obc2c$out).y = 5U;"),
        "scrutinee": EXPECTED.replace("if ((m) == 1)", "if ((go) == 1)"),
        "kept switch": _lowered(HEAD + NESTED) + CHAINS + TAIL,
        "outside token": EXPECTED.replace("  return;", "  return x;"),
    }
    for label, text in wrong.items():
        ensure(text != EXPECTED, f"the {label} variant changed nothing")
        failures = _compare(FIXTURE, text, False)
        ensure(any("not a declared lowering" in f for f in failures),
               f"a moved {label} fails the comparison: {failures}")
    spaced = EXPECTED.replace("  return;", "    return;")
    ensure(any("bytes outside" in f for f in _compare(FIXTURE, spaced, False)),
           "a byte change outside the groups fails the comparison")
    only = HEAD + NESTED + TAIL
    failures = _compare(only, _lowered(only), True)
    ensure(sorted(failures) == sorted(["no chain-else group", "no chain-only group",
                                       "no if-only group", "no else-only group",
                                       "every group's labels are 0, 1, ... in order"]),
           f"the control predicate names what is missing: {failures}")
    ensure(_compare(only, _lowered(only), False) == [], "the node predicate is narrower")
    undeclared = (HEAD + NESTED + TAIL).replace("y = x;\n      break;\n", "y = x;\n")
    failures = _compare(undeclared, undeclared, False)
    ensure(any("not a declared lowering" in f for f in failures),
           f"an undeclared shape fails the comparison: {failures}")
    free = HEAD + TAIL
    ensure(_compare(free, free, False) == ["no switch group was lowered"],
           "a comparison with no group decides nothing")
    for bad_dump in ("identifier 'x'\t\tLoc=<x.c:1:1>\n", "garbage\n"):
        try:
            COMPARE.parse_dump(bad_dump)
        except ValueError:
            continue
        raise AssertionError(f"dump {bad_dump!r} was accepted")


FIXTURE_ROWS = "\n".join([
    "0 0 0 0 0 1 3 0 1 1 0 1 2",
    "1 2 5 5 1 1 3 7 3 0 0 1 2",
    "2 0 1 1 0 0 0 0 0 0 0 0 0",
    "0 1 1 0 0 0 0 0 0 0 0 0 0",
    "1 0 9 9 0 1 3 7 1 1 0 1 2"]) + "\n"


def _split() -> None:
    names = ("start_restart", "fun$step$start_restart", "fun$step$start_restart")
    driver = PROBE.emit(FIXTURE_ROWS, Path("/x/node.c"), *names)
    made = SPLIT.programs(driver, names[2], 2)
    ensure([(first, count) for first, count, _ in made] == [(0, 2), (2, 2), (4, 1)],
           f"consecutive runs of rows: {[(f, c) for f, c, _ in made]}")
    prologue, blocks, epilogue = SPLIT.split(driver, names[2], 2)
    ensure(len(blocks) == 5 and all(len(b) == 6 for b in blocks), "five six-line row blocks")
    for _, count, text in made:
        ensure(text.startswith(prologue) and text.endswith(epilogue)
               and text.count(f"    {names[2]}(&state, &answer,") == count,
               "each program is the prologue, its rows and the epilogue")
    rows = "".join(text[len(prologue):len(text) - len(epilogue)] for _, _, text in made)
    ensure(prologue + rows + epilogue == driver, "the programs' rows rejoin into the driver")
    moved = PROBE.emit(FIXTURE_ROWS, Path("/x/node.c"), *names, perturb=True)
    changed = [k for k, (a, b) in enumerate(zip(SPLIT.programs(moved, names[2], 2), made,
                                                strict=True)) if a != b]
    ensure(changed == [0], f"the perturbation lands in the first program only: {changed}")
    for label, text in {"no call": driver.replace(f"    {names[2]}(", "    other("),
                        "no epilogue": driver.replace("    return 0;\n", ""),
                        "uneven blocks": driver.replace(") return 1;\n", ") return 1;\n    ;\n",
                                                        1)}.items():
        try:
            SPLIT.programs(text, names[2], 2)
        except ValueError:
            continue
        raise AssertionError(f"the {label} driver was split")
    for rows_wanted in (0, -1):
        try:
            SPLIT.programs(driver, names[2], rows_wanted)
        except ValueError:
            continue
        raise AssertionError(f"{rows_wanted} rows per program was accepted")


def _control() -> None:
    table = CONTROL.rows(7, 576)
    ensure(table == CONTROL.rows(7, 576) and len(table) == 576, "rows are seeded and counted")
    ensure(table[:128] == CONTROL.rows(8, 576)[:128] and table != CONTROL.rows(8, 576),
           "the edge rows are fixed and the seed moves only the seeded rows")
    covered = CONTROL.coverage(table)
    ensure(covered["m"] == [0, 1, 2, 3] and covered["w"] == sorted(CONTROL.EDGES64),
           f"edges: {covered}")
    try:
        CONTROL.rows(7, 575)
    except ValueError:
        pass
    else:
        raise AssertionError("fewer than 576 rows were generated")
    m32, m64 = (1 << 32) - 1, (1 << 64) - 1
    row = CONTROL.Row
    got = CONTROL.answers([row(2, 1, 1, 0, 1, 5, 7, m64), row(3, 0, 1, 0, 0, 1, 2, 10),
                           row(3, 3, 2, 1, 1, m32, 1, 0)])
    answer = CONTROL.Answer
    ensure(got == [answer(5, 2, 5, 0, 7, 0, 5, 5, 12, m64, 1),
                   answer(2, 7, 9, 7, 9, 0, 1, 10, 6, 11, 0),
                   answer(m32, 7, 1, 0, 1, 6, m32 - 6, 2, 19, 0, 0)],
           f"hand-computed answers across three instants: {got}")
    parts = CONTROL.chunks(table, 24)
    ensure(len(parts) == 24 and all(len(p) == 24 for p in parts), "24 programs of 24 rows")
    names = ("switch_control", "fun$step$switch_control", "fun$step$switch_control",
             "fun$reset$switch_control")
    plain = CONTROL.emit(parts[1], Path("/x/control.c"), *names)
    moved = CONTROL.emit(parts[1], Path("/x/control.c"), *names, perturb=True)
    changed = [a for a, b in zip(plain.splitlines(), moved.splitlines(), strict=True) if a != b]
    ensure(len(changed) == 1 and "answer.b" in changed[0], "perturbation moves one check")
    ensure(plain.count("fun$step$switch_control(&state, &answer,") == 24
           and plain.count("fun$reset$switch_control(&state);") == 1,
           "one reset, then one step per row")
    first = CONTROL.answers(parts[1])[0]
    ensure(f"answer.e != {first.e}U" in plain, "each program's answers start from a reset")
    text = CONTROL.table_text(table, 24)
    ensure(len(text.splitlines()) == 576, "the digested table holds every row")


def cases() -> list[Case]:
    return [Case("switch-rewrite-lowers-declared-shapes", _lowers),
            Case("switch-rewrite-returns-switch-free-input-unchanged", _identity),
            Case("switch-rewrite-refuses-every-other-switch", _refusals),
            Case("switch-rewrite-command-writes-or-refuses", _cli),
            Case("switch-comparison-places-each-group", _comparison),
            Case("probe-split-rejoins-its-driver", _split),
            Case("switch-control-rows-answers-and-programs", _control)]
