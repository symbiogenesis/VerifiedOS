# SPDX-License-Identifier: Apache-2.0
"""meta: the rule registry against the checks this package carries, both directions.

tools/check-rules.md enumerates what the checker checks, one row per rule, each
stating what passing means and on what ground, so the review gate can price the
tool's reach by reading a table instead of this source. The closure is the same shape
as every conferral the register uses: registry and code are two artifacts, and their
agreement is held mechanically in both directions, a K- id here with no registry row
and a registry row no check carries.

The scan is static, over the sources of `vos.checks` alone, so a check a repair branch
or an early return skips at runtime still counts as carried. It is deliberately not
the whole of `tools/`: the mutation selftest names every rule too, and scanning it
would make this agreement trivially true and stop deciding anything. What no scan
decides is whether a registered claim is the right claim, which is the same residue
every conferral declares.

K-67 is the same discipline pointed at the tools' own documentation. typecheck.py
fixes the ty and ruff pins, tools/README.md restates them four times over, in its
checker table's two rows and in the `uv tool install` line each checker carries, and
nothing owned the copy. The rule holds every site against the source and is
fail-closed in the reading: a side it cannot find is a finding, never a pass over
nothing.
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== meta: the rule registry against the checks carried ==="

RULES = "tools/check-rules.md"
RULE_ID_RE = re.compile(r"\bK-\d{2,3}\b")
REGISTRY_ROW_RE = re.compile(r"^\| (K-\d{2,3}) \|")

README = "tools/README.md"
TYPECHECK = "tools/typecheck.py"

# The pins as typecheck.py declares them, and the four README sites restating them.
# The version cell and the install argument are captured alone, so a disagreement
# names the two figures and nothing else. Each checker carries its own install line
# because `uv tool install` takes one tool per command, which is the same fact that
# makes the four sites two symmetrical pairs rather than two rows and a joint line.
_PIN_SRC_RE = re.compile(r'^(TY|RUFF)_VERSION = "([^"\r\n]*)"', re.MULTILINE)
_README_TY_ROW_RE = re.compile(r"(?m)^\| \[ty\]\([^)]*\) \| ([^ |]+) \|")
_README_RUFF_ROW_RE = re.compile(r"(?m)^\| \[ruff\]\([^)]*\) \| ([^ |]+) \|")
_README_TY_INSTALL_RE = re.compile(r"`uv tool install ty==([^\s`=]+)`")
_README_RUFF_INSTALL_RE = re.compile(r"`uv tool install ruff==([^\s`=]+)`")


def carried_rules() -> set[str]:
    """Every rule id the checks package names."""
    found: set[str] = set()
    for source in sorted(Path(__file__).parent.glob("*.py")):
        found.update(RULE_ID_RE.findall(source.read_text(encoding="utf-8")))
    return found


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    doc = ctx.corpus.get(RULES)
    if doc is None:
        rep.report("K-00", "missing artifact:", [f"{RULES} is not in the repository"])
    else:
        in_code = carried_rules()

        registered: list[str] = []
        for line in doc.lines:
            m = REGISTRY_ROW_RE.match(line)
            if m:
                registered.append(m.group(1))

        seen: set[str] = set()
        findings: list[str] = []
        for rule in registered:
            if rule in seen:
                findings.append(f"{rule} has more than one registry row")
            seen.add(rule)
        findings += [f"{r} is registered and no check here carries it"
                     for r in registered if r not in in_code]
        findings += [f"{r} is carried here and has no registry row"
                     for r in sorted(in_code) if r not in seen]

        rep.report("K-00", "rule id(s) the registry and the checks disagree on:", findings,
                   f"the registry's {len(seen)} rules and the checks agree, both directions")

    _pins(ctx)
    rep.line()


def _pins(ctx: Context) -> None:
    """K-67: tools/README.md's checker pins are the versions typecheck.py fixes.

    Fail-closed on the reading itself: the source constants and each of the three
    README sites either parse in the form written today or are findings, so a
    reworded README cannot take the comparison down with it and leave the rule green.
    """
    rep = ctx.rep
    findings: list[str] = []

    try:
        source = (ctx.root / TYPECHECK).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        source = ""
    pins = {m.group(1): m.group(2) for m in _PIN_SRC_RE.finditer(source)}
    ty, ruff = pins.get("TY"), pins.get("RUFF")
    if ty is None or ruff is None:
        findings.append(f"{TYPECHECK} no longer states TY_VERSION and RUFF_VERSION in "
                        "a form this rule reads")

    doc = ctx.corpus.get(README)
    if doc is None:
        findings.append(f"{README} is not in the repository")

    if not findings and doc is not None and ty is not None and ruff is not None:
        for label, pattern, checker, want in (
                ("checker-table row", _README_TY_ROW_RE, "ty", ty),
                ("checker-table row", _README_RUFF_ROW_RE, "ruff", ruff),
                ("install line", _README_TY_INSTALL_RE, "ty", ty),
                ("install line", _README_RUFF_INSTALL_RE, "ruff", ruff)):
            m = pattern.search(doc.raw)
            if m is None:
                findings.append(f"{README} no longer states {checker}'s pin in its "
                                f"{label}, in a form this rule reads")
            elif m.group(1) != want:
                findings.append(f"{README}'s {checker} {label} states {m.group(1)}, "
                                f"{TYPECHECK} pins {want}")

    rep.report("K-67", "README pin site(s) disagreeing with the versions typecheck.py "
               "fixes:", findings,
               f"tools/README.md's four pin sites state ty {ty} and ruff {ruff}, the "
               f"versions {TYPECHECK} fixes")
