# SPDX-License-Identifier: Apache-2.0
"""The supervisor route's Clight exchange normalizer, token comparison and control rows.

[supervisor/route/](../../supervisor/route/README.md) holds three authored tools that
M6.1b-iii's bounded exchange trial runs: `normalize.py` erases the alignment groups C11
forbids from Vélus's printed library Clight, `token_compare.py` checks a normalization
through clang's lexer without reading the normalizer, and `control.py` generates the
control node's seeded rows, its expected answers and its driver. The fixture below is
authored in the printer's layout for a hypothetical node; it is not Vélus output.
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

STRUCTS = """struct demo;
struct fun$step$demo;
struct gain;
struct demo {
  unsigned long long _Alignas(8) last$m;
  struct gain g;
};

struct fun$step$demo {
  unsigned long long _Alignas(8) y;
  long long _Alignas(8) z;
  unsigned int k;
};

struct gain {
};

"""
FUNCTIONS = """extern unsigned long long _Alignas(8) scale(unsigned long long _Alignas(8), unsigned int);
unsigned long long _Alignas(8) fun$step$gain(struct gain *, unsigned long long _Alignas(8));
void fun$step$demo(struct demo *, struct fun$step$demo *, unsigned long long _Alignas(8), long long _Alignas(8), unsigned int);
void fun$reset$demo(struct demo *);
unsigned long long _Alignas(8) fun$step$gain(struct gain *obc2c$self, unsigned long long _Alignas(8) u)
{
  register unsigned long long _Alignas(8) v;
  v = u + 1LLU;
  return v;
}

void fun$step$demo(struct demo *obc2c$self, struct fun$step$demo *obc2c$out, unsigned long long _Alignas(8) x, long long _Alignas(8) q, unsigned int n)
{
  register unsigned long long _Alignas(8) step$v;
  register unsigned long long _Alignas(8) e$r;
  step$v = fun$step$gain(&(*obc2c$self).g, x);
  e$r = scale(step$v, n);
  (*obc2c$out).y = e$r ^ (unsigned long long _Alignas(8)) n;
  (*obc2c$out).z = q ^ (long long _Alignas(8)) n;
  (*obc2c$out).k = (unsigned int) x;
  (*obc2c$self).last$m = x;
  return;
}

void fun$reset$demo(struct demo *obc2c$self)
{
  (*obc2c$self).last$m = 0LLU;
  /*skip*/;
  return;
}

"""
FIXTURE = STRUCTS + FUNCTIONS
# Every group outside the structures goes; the three members keep theirs.
EXPECTED = STRUCTS + FUNCTIONS.replace(" _Alignas(8)", "")


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"supervisor_route_{name}",
                                                  ROUTE / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load supervisor/route/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


NORMALIZE = _load("normalize")
COMPARE = _load("token_compare")
CONTROL = _load("control")


def _refused(text: str, words: str) -> None:
    try:
        NORMALIZE.normalize(text)
    except NORMALIZE.RefusalError as err:
        ensure(words in str(err), f"refusal {err} does not say {words!r}")
    else:
        raise AssertionError(f"accepted input that should mention {words!r}")


def _positions() -> None:
    out, sites = NORMALIZE.normalize(FIXTURE)
    ensure(out == EXPECTED, "only the enumerated groups may be removed, byte for byte")
    kinds = sorted((s.kind, s.declaration) for s in sites if s.action == "removed")
    ensure(kinds == sorted([("return", "extern"), ("parameter", "extern"),
                            ("return", "prototype"), ("parameter", "prototype"),
                            ("parameter", "prototype"), ("parameter", "prototype"),
                            ("return", "definition"), ("parameter", "definition"),
                            ("register", "body"), ("parameter", "definition"),
                            ("parameter", "definition"), ("register", "body"),
                            ("register", "body"), ("cast", "body"), ("cast", "body")]),
           f"removed sites are not the fixture's fifteen: {kinds}")
    kept = [(s.owner, s.type) for s in sites if s.action == "kept"]
    ensure(kept == [("struct demo", "unsigned long long"),
                    ("struct fun$step$demo", "unsigned long long"),
                    ("struct fun$step$demo", "long long")], f"kept members: {kept}")
    first = sites[0]
    ensure((first.line, first.column, first.kind) == (5, 22, "member"),
           f"sites carry the group's own line and column: {first}")


def _identity() -> None:
    free = EXPECTED.replace(" _Alignas(8)", "")
    out, sites = NORMALIZE.normalize(free)
    ensure(out == free and sites == [], "alignment-free input must come back byte-identical")
    again, sites = NORMALIZE.normalize(EXPECTED)
    ensure(again == EXPECTED and all(s.action == "kept" for s in sites),
           "a normalized dump must normalize to itself")


def _refusals() -> None:
    definition = "unsigned long long _Alignas(8) x, long long"
    cases = {
        "alignment 16": FIXTURE.replace(definition, definition.replace("(8) x", "(16) x")),
        "`unsigned int`": FIXTURE.replace("unsigned int n)", "unsigned int _Alignas(4) n)"),
        "file-scope alignment on `g`": FIXTURE + "unsigned long long _Alignas(8) g;\n",
        "file-scope alignment on `struct gain`":
            FIXTURE.replace("struct gain {", "struct gain _Alignas(8) {"),
        "file-scope object `self$`": FIXTURE + "struct demo self$;\n",
        "a `main` function": FIXTURE + "int main(void)\n{\n  return 0;\n}\n",
        "only main-node compilation prints it":
            FIXTURE.replace("unsigned int k;", "volatile unsigned int k;"),
        "only the 8": FIXTURE.replace("_Alignas(8) y;", "_Alignas(16) y;"),
        "on `unsigned int`": FIXTURE.replace("unsigned int k;", "unsigned int _Alignas(8) k;"),
        "neither a register temporary nor a cast":
            FIXTURE.replace("register unsigned long long _Alignas(8) v;",
                            "unsigned long long _Alignas(8) v;"),
        "neither a register": FIXTURE.replace("(unsigned int) x", "sizeof(long long _Alignas(8))"),
        "on a pointer": FIXTURE.replace("struct gain *obc2c$self, unsigned long long _Alignas(8) u",
                                        "struct gain * _Alignas(8) obc2c$self"),
        "printer's": FIXTURE.replace("_Alignas(8) q", "_Alignas( 8 ) q"),
        "after `int`": FIXTURE.replace("(unsigned int) x", "(unsigned int _Alignas(8)) x"),
        "unexpected character '#'": "#include <x.h>\n" + FIXTURE,
        "unexpected character '\"'": FIXTURE.replace("0LLU", '"0"'),
        "line comment": FIXTURE.replace("/*skip*/", "// skip"),
        "unterminated comment": FIXTURE + "/* open\n",
        "non-ASCII": FIXTURE.replace("demo;", "démo;", 1),
        "no function definition": STRUCTS,
    }
    for words, text in cases.items():
        _refused(text, words)
    _refused("", "no function definition")
    # A group before a pointer declarator qualifies a pointer, at every position.
    pointers = {
        "named parameter": ("unsigned long long _Alignas(8) u)",
                            "unsigned long long _Alignas(8) *u)"),
        "unnamed parameter": ("*, unsigned long long _Alignas(8));",
                              "*, unsigned long long _Alignas(8) *);"),
        "return": ("unsigned long long _Alignas(8) fun$step$gain(struct gain *obc2c$self",
                   "unsigned long long _Alignas(8) *fun$step$gain(struct gain *obc2c$self"),
        "member": ("unsigned long long _Alignas(8) last$m;",
                   "unsigned long long _Alignas(8) *last$m;"),
    }
    for label, (printed, pointer) in pointers.items():
        text = FIXTURE.replace(printed, pointer)
        ensure(text != FIXTURE, f"the {label} pointer variant changed nothing")
        _refused(text, "before a pointer declarator")


def _cli() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-route-") as tmp:
        root = Path(tmp)
        (root / "in.light.c").write_bytes(FIXTURE.encode("ascii"))
        code = NORMALIZE.main([str(root / "in.light.c"), "--out", str(root / "out.c"),
                               "--record", str(root / "record.json")])
        record = json.loads((root / "record.json").read_text(encoding="utf-8"))
        ensure(code == 0 and (root / "out.c").read_bytes() == EXPECTED.encode("ascii"),
               "the command writes the normalized bytes")
        ensure((record["removed"], record["kept"], len(record["sites"])) == (15, 3, 18),
               f"the record counts every group: {record['removed']}, {record['kept']}")
        (root / "bad.c").write_bytes((FIXTURE + "struct demo self$;\n").encode("ascii"))
        code = NORMALIZE.main([str(root / "bad.c"), "--out", str(root / "bad.out"),
                               "--record", str(root / "bad.json")])
        ensure(code == 2 and not (root / "bad.out").exists()
               and not (root / "bad.json").exists(), "a refusal writes nothing and exits 2")


_KINDS = {"(": "l_paren", ")": "r_paren", "{": "l_brace", "}": "r_brace", ";": "semi",
          ",": "comma", "*": "star", "&": "amp", ".": "period", "^": "caret", "=": "equal",
          "+": "plus"}
_WORDS = frozenset({"struct", "unsigned", "long", "int", "void", "extern", "register",
                    "return", "_Alignas", "sizeof"})


def _dump(text: str) -> str:
    """clang's `-dump-tokens` layout for the fixture's vocabulary."""
    lines = []
    for number, line in enumerate(text.splitlines(), 1):
        for match in re.finditer(r"/\*.*?\*/|[A-Za-z_$][A-Za-z0-9_$]*|[0-9][0-9A-Za-z]*|\S",
                                 line):
            tok = match.group()
            if tok.startswith("/*"):
                continue
            kind = (tok if tok in _WORDS else "numeric_constant" if tok[0].isdigit()
                    else _KINDS.get(tok, "identifier"))
            flags = " [StartOfLine]" if match.start() == 0 else ""
            lines.append(f"{kind} '{tok}'\t{flags}\tLoc=<x.c:{number}:{match.start() + 1}>")
    return "\n".join([*lines, "eof ''\t\tLoc=<x.c:1:1>"]) + "\n"


def _compare(original: str, normalized: str, step: str | None) -> tuple[list[str], str]:
    """The comparison's failures and its per-position counts, as text."""
    result = COMPARE.compare(COMPARE.parse_dump(_dump(original)),
                             COMPARE.parse_dump(_dump(normalized)), original, normalized, step)
    counts = f"{result.get('deleted')} {result.get('retained')} {result.get('by_position')}"
    return [str(failure) for failure in result["failures"]], counts


def _token_comparison() -> None:
    failures, counts = _compare(FIXTURE, EXPECTED, None)
    ensure(failures == [], f"the control predicate holds: {failures}")
    ensure(counts.startswith("15 3 "), f"placements: {counts}")
    failures, _ = _compare(FIXTURE, EXPECTED, "fun$step$demo")
    ensure(any("return" in f for f in failures),
           "the step predicate refuses deletions outside the step parameters")
    only = FIXTURE.replace("_Alignas(8) x,", "x,").replace(" _Alignas(8), long", ", long")
    failures, counts = _compare(FIXTURE, only, "fun$step$demo")
    ensure(counts.startswith("2 16 ") and bool(failures)
           and all(f.startswith("retained group") for f in failures),
           f"only retained groups fail this step predicate: {counts} {failures}")
    member = EXPECTED.replace("long long _Alignas(8) z;", "long long z;")
    failures, _ = _compare(FIXTURE, member, None)
    ensure(any(f.endswith("is member") for f in failures),
           f"a deleted member fails the control predicate: {failures}")
    failures, _ = _compare(FIXTURE, EXPECTED.replace("v = u + 1LLU;", "v = u + 2LLU;"), None)
    ensure(any("differ" in f for f in failures), "any other token change fails the comparison")
    pointer = FIXTURE.replace("_Alignas(8) u)", "_Alignas(8) *u)")
    failures, _ = _compare(pointer, EXPECTED.replace("long long u)", "long long *u)"), None)
    ensure(pointer != FIXTURE and any(f.endswith("is other") for f in failures),
           f"a deleted group before a pointer declarator is at no enumerated position: {failures}")
    ensure(COMPARE.byte_removals("a _Alignas(8) b _Alignas(8) c", "a b c") == 2,
           "byte spans are counted")
    for bad in ("a b  c", "a _Alignas(8) b c x"):
        try:
            COMPARE.byte_removals("a _Alignas(8) b _Alignas(8) c", bad)
        except ValueError:
            continue
        raise AssertionError(f"byte change {bad!r} was accepted")
    for bad_dump in ("identifier 'x'\t\tLoc=<x.c:1:1>\n", "garbage\n"):
        try:
            COMPARE.parse_dump(bad_dump)
        except ValueError:
            continue
        raise AssertionError(f"dump {bad_dump!r} was accepted")


def _rows() -> None:
    table = CONTROL.rows(7, 640)
    ensure(table == CONTROL.rows(7, 640) and len(table) == 640, "rows are seeded and counted")
    ensure(table[:256] == CONTROL.rows(8, 640)[:256] and table != CONTROL.rows(8, 640),
           "the edge product is fixed and the seed moves only the seeded rows")
    covered = CONTROL.coverage(table)
    ensure(all(values == [0, 1, 1 << 32, (1 << 64) - 1] for values in covered.values()),
           "each 64-bit input takes 0, 1, 2^32 and 2^64-1")
    try:
        CONTROL.rows(7, 575)
    except ValueError:
        pass
    else:
        raise AssertionError("fewer than 576 rows were generated")
    m64, m32, mix = (1 << 64) - 1, (1 << 32) - 1, 0x9E3779B97F4A7C15
    answers = CONTROL.answers([CONTROL.Row(0, 0, 0, 0), CONTROL.Row(m64, 1, 0, m64),
                               CONTROL.Row(1, m64, m32, 0)])
    ensure(answers == [CONTROL.Answer(1, 1, 0, 0, 0, 0),
                       CONTROL.Answer(1, ((1 << 64) - mix) ^ (1 << 35), 0, m32, m64, 0),
                       CONTROL.Answer(m32 - 1, CONTROL.mix64(1, m64 ^ m32), m64, m32, m32, 1)],
           f"hand-computed answers: {answers}")
    ensure((CONTROL.signed(m64), CONTROL.signed(1 << 63), CONTROL.signed(5))
           == ("(-1LL)", "(-9223372036854775807LL - 1LL)", "5LL"), "signed literals")
    names = ("control", "fun$step$control", "fun$step$control", "fun$reset$control")
    plain = CONTROL.emit(table, Path("/x/control.light.c"), *names)
    moved = CONTROL.emit(table, Path("/x/control.light.c"), *names, perturb=True)
    changed = [a for a, b in zip(plain.splitlines(), moved.splitlines(), strict=True) if a != b]
    ensure(len(changed) == 1 and "answer.sum" in changed[0], "perturbation moves one check")
    ensure(plain.count("fun$step$control(&state, &answer,") == 640
           and "fun$reset$control(&state);" in plain, "one step per row after one reset")


def cases() -> list[Case]:
    return [Case("normalizer-erases-only-enumerated-positions", _positions),
            Case("normalizer-returns-alignment-free-input-unchanged", _identity),
            Case("normalizer-refuses-every-other-form", _refusals),
            Case("normalizer-command-writes-or-refuses", _cli),
            Case("token-comparison-places-each-group", _token_comparison),
            Case("control-rows-are-seeded-and-cover-edges", _rows)]
