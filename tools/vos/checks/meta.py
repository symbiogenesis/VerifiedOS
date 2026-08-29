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
fixes the ty and ruff pins, tools/README.md restates them in its checker table's two
rows and in the `uv tool install` line each checker carries, and nothing owned the
copy. The rule holds every site against the source and is fail-closed in the reading:
a side it cannot find is a finding, never a pass over nothing. The sites are
enumerated rather than counted here, because the count is `_README_SITES`' to state.

K-75 is that rule one figure over, on the version the tools are *written* to rather
than the versions they run. The interpreter floor decides what the two checkers admit
and what this directory's Python may say, and it is written twice as a setting, once
in ty's dialect and once in ruff's, and restated five times in prose; ty.toml's is the
source because it is the environment an editor's language server and this gate both
resolve against, and the only site that writes the figure bare. The two dialects are
why the rule is worth having rather than obvious: `3.14` and `py314` are one figure in
two spellings, so a bump applied to one of them does not read as a disagreement with
the other, and each of the five prose sites was a hand-copy nothing owned.

The window is `tools/` by decision rather than by reach. The plan restates the floor in
two of its own cells, and a rule about how this directory is written has no business
holding a sentence in a document about the build order; that pairing is the plan's to
own if anything is to own it.

K-83 is the third of them and the one that makes a directory a quarantine. S16 took
two whole instruments out of the landing loop, the profile-freeze analyzer and the
bank-count exploration, and moved them to `tools/quarantine/` with the two rules that
hold them. **Moving them is not what decouples them.** The quarantine is an ordinary
package on `tools/`, so `import quarantine.freeze` resolves for any tool that puts its
own directory on the path, exactly as `import vos.freeze` did before the move: without
a rule the whole act would be a rename, and the first landing-loop tool to reach back
in would restore the coupling with every gate still green. So the rule is the act, and
the move is what gives it something to say.

Two ways in are held rather than one, because the instruments' own entry points carry
hyphens no import statement can name: an `import` or `from ... import` that names the
package, and a path naming the directory, which is how a tool launches `bank-dse.py`
or `freeze-report.py` as a subprocess. Both are quantified over every source under
`tools/` that the index carries and the quarantine does not, so a file added tomorrow
is inside the rule the day it is staged and a module added to the quarantine is
protected the day it lands: neither side is a list anybody maintains. Fail-closed in
both readings, on K-67's and K-75's own ground: a quarantine carrying no module and a
window carrying no source are each a finding, never a pass over nothing. It owes the
floors group no member count for the same reason those two do not, its own reading
being the floor: an empty roster or an empty window reports here, on the day it
empties, rather than passing vacuously for as long as nobody looks.

The path half takes two carve-outs and both are declared rather than dodged: this module
names the quarantine's directory in order to find it, and check-selftest.py has to spell
the coupling in order to seed the mutant that proves this rule bites. The alternative was
to write both so the rule's own pattern would miss them, which is a rule written around
its own text. The *import* half takes no carve-out at all, so the two files the path half
excuses are still held against the coupling that matters, and it is the same reasoning
that keeps the selftest outside K-00's scan: a rule that read its own prover would decide
less rather than more.

What K-83 does not decide is whether the quarantine should still be one. That is the
condition `tools/quarantine/README.md` states per instrument and a person's to read at
the milestone that meets it.
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from vos import figures

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

# The pins as typecheck.py declares them, and the README sites restating them. The
# version cell and the install argument are captured alone, so a disagreement names
# the two figures and nothing else. Each checker carries its own install line because
# `uv tool install` takes one tool per command, which is what makes the sites two
# symmetrical pairs rather than two rows and a joint line.
_PIN_SRC_RE = re.compile(r'^(TY|RUFF)_VERSION = "([^"\r\n]*)"', re.MULTILINE)
_README_TY_ROW_RE = re.compile(r"(?m)^\| \[ty\]\([^)]*\) \| ([^ |]+) \|")
_README_RUFF_ROW_RE = re.compile(r"(?m)^\| \[ruff\]\([^)]*\) \| ([^ |]+) \|")
_README_TY_INSTALL_RE = re.compile(r"`uv tool install ty==([^\s`=]+)`")
_README_RUFF_INSTALL_RE = re.compile(r"`uv tool install ruff==([^\s`=]+)`")

# The sites, as the table every figure stated over them is read off rather than
# copied from. Each row names the constant it holds that site against, so a site and
# a pin cannot be paired wrongly and a site added here moves the ok line's count with
# it: the derived-fact discipline this rule enforces on the README, applied to the
# rule's own prose, which is where a hand-copied count last went stale.
_README_SITES: list[tuple[str, re.Pattern[str], str]] = [
    ("checker-table row", _README_TY_ROW_RE, "TY"),
    ("checker-table row", _README_RUFF_ROW_RE, "RUFF"),
    ("install line", _README_TY_INSTALL_RE, "TY"),
    ("install line", _README_RUFF_INSTALL_RE, "RUFF"),
]

TY_CONF = "tools/ty.toml"
RUFF_CONF = "tools/ruff.toml"

# The two trees K-83 stands between, and the kind of file it reads in each.
TOOLS_TREE = "tools/"
QUARANTINE_TREE = "tools/quarantine/"
SOURCE_SUFFIX = ".py"

# An import that names the quarantine, line-anchored so that a mutant seed carrying the
# statement inside a string literal is the case that seeds it and not a site that fails
# it. `quarantine` alone and any module under it are one pattern, because reaching the
# package at all is the coupling.
_Q_IMPORT_RE = re.compile(
    r"(?m)^[ \t]*(?:from[ \t]+(quarantine(?:\.[\w.]+)?)[ \t]+import\b"
    r"|import[ \t]+(quarantine(?:\.[\w.]+)?)\b)")

# The other way in: the directory named as a path or as a string, which is how a
# hyphenated entry point is launched and how a dynamic import spells one. The name has
# to be *delimited on both sides* rather than merely quoted, and that is not fussiness:
# the memory plan's own vocabulary carries a region class called `quarantine entries`,
# which the compounds group holds as a quoted literal, so a pattern reading any quoted
# occurrence would report a rule about second-class memory as a coupling to an
# instrument. A sentence saying *the quarantine* or *the quarantine's* names no file
# either, and neither is read.
_Q_PATH_RE = re.compile(
    r"""[/\\]quarantine\b|quarantine[/\\]|["']quarantine["']|["']quarantine\.""")

# The two sites the path half excuses, and the only two: this module has to name the
# directory in order to find it, and the mutation selftest has to spell the coupling in
# order to seed it. Both are declared rather than pattern-dodged, and both are files a
# reader auditing this rule is already reading; the import half excuses neither, so the
# coupling that matters is held at every site without exception.
_Q_PATH_EXEMPT = ("tools/vos/checks/meta.py", "tools/check-selftest.py")

# The interpreter floor, as the type checker's own environment fixes it.
_FLOOR_SRC_RE = re.compile(r'(?m)^python-version = "([^"\r\n]*)"')


def _plain(floor: str) -> str:
    """The floor as ty.toml writes it, which is how the prose writes it too."""
    return floor


def _packed(floor: str) -> str:
    """ruff's own spelling, the same figure with its separator dropped."""
    return "py" + floor.replace(".", "")


# The floor's sites, each with the file it is in, the pattern that reads it, and how
# that site spells the figure. Every group a pattern captures is held, which is what
# lets one row cover the interpreter table's two cells: they state the versions the two
# lanes actually carry, so what is held there is the major and minor each one is at and
# never the patch either has reached.
_FLOOR_SITES: list[tuple[str, str, re.Pattern[str], Callable[[str], str]]] = [
    ("target version", RUFF_CONF,
     re.compile(r'(?m)^target-version = "([^"\r\n]*)"'), _packed),
    ("modernization comment", RUFF_CONF,
     re.compile(r"constructs the (\S+) floor makes obsolete"), _plain),
    ("opening sentence", README,
     re.compile(r"in this directory is Python (\S+?)\.(?=\s)"), _plain),
    ("interpreter table", README,
     re.compile(r"(?m)^\| Python \| (\d+\.\d+)\.\d+ \| (\d+\.\d+)\.\d+ \|"), _plain),
    ("floor sentence", README,
     re.compile(r"The floor is \*\*([^*]+)\*\*"), _plain),
    ("lazy-annotations bullet", README,
     re.compile(r"Under (\S+) that import is the \*opt-out\*"), _plain),
    ("launcher spelling", README,
     re.compile(r"`py -([^`\s]+)`"), _plain),
]


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
    _floor(ctx)
    _quarantine(ctx)
    rep.line()


def _source(ctx: Context, rel: str) -> str:
    """A file under `tools/` that the document corpus does not carry, read off disk.

    A file that will not read is "", which makes every site in it a finding: the
    fail-closed reading both rules below want, and the reason this returns text rather
    than raising.
    """
    try:
        return (ctx.root / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _pins(ctx: Context) -> None:
    """K-67: tools/README.md's checker pins are the versions typecheck.py fixes.

    Fail-closed on the reading itself: the source constants and every site in
    `_README_SITES` either parse in the form written today or are findings, so a
    reworded README cannot take the comparison down with it and leave the rule green.
    """
    rep = ctx.rep
    findings: list[str] = []

    pins = {m.group(1): m.group(2)
            for m in _PIN_SRC_RE.finditer(_source(ctx, TYPECHECK))}
    ty, ruff = pins.get("TY"), pins.get("RUFF")
    if ty is None or ruff is None:
        findings.append(f"{TYPECHECK} no longer states TY_VERSION and RUFF_VERSION in "
                        "a form this rule reads")

    doc = ctx.corpus.get(README)
    if doc is None:
        findings.append(f"{README} is not in the repository")

    # An empty findings list here already means both pins parsed, so each row's own
    # key indexes them rather than a fourth pair of locals threaded through the loop.
    if not findings and doc is not None:
        for label, pattern, key in _README_SITES:
            checker, want = key.lower(), pins[key]
            m = pattern.search(doc.raw)
            if m is None:
                findings.append(f"{README} no longer states {checker}'s pin in its "
                                f"{label}, in a form this rule reads")
            elif m.group(1) != want:
                findings.append(f"{README}'s {checker} {label} states {m.group(1)}, "
                                f"{TYPECHECK} pins {want}")

    rep.report("K-67", "README pin site(s) disagreeing with the versions typecheck.py "
               "fixes:", findings,
               f"tools/README.md's {figures.words(len(_README_SITES))} pin sites state "
               f"ty {ty} and ruff {ruff}, the versions {TYPECHECK} fixes")


def _floor(ctx: Context) -> None:
    """K-75: every site under `tools/` states the interpreter floor ty.toml fixes.

    Fail-closed in the same two places K-67 is. The source either parses in the form it
    is written in today or is a finding, so a reworded setting cannot take the
    comparison down and leave the rule green; and a site whose pattern no longer matches
    is a finding rather than a site quietly dropped from the enumeration.

    The comparison is on the spelling each site owes rather than on the floor itself,
    because two of them do not write it the way ty.toml does: ruff packs it into one
    token of its own dialect, and the interpreter table states the running version of
    each lane, which is at the floor without being it.
    """
    rep = ctx.rep
    findings: list[str] = []

    stated = _FLOOR_SRC_RE.search(_source(ctx, TY_CONF))
    if stated is None:
        findings.append(f"{TY_CONF} no longer states python-version in a form this rule "
                        "reads, so there is no floor to hold the rest against")

    doc = ctx.corpus.get(README)
    if doc is None:
        findings.append(f"{README} is not in the repository")

    # Both guards above have to have passed before a site can be read: without the
    # source there is nothing to compare a site to, and without the README five of the
    # seven sites are missing for a reason that is not their own.
    floor = stated.group(1) if stated else ""
    if not findings and doc is not None:
        # one read per file the table names, the README's coming from the corpus the
        # run already holds rather than from a second trip to disk
        text: dict[str, str] = {README: doc.raw}
        for _, file, _, _ in _FLOOR_SITES:
            if file not in text:
                text[file] = _source(ctx, file)

        for label, file, pattern, spell in _FLOOR_SITES:
            want = spell(floor)
            hit = pattern.search(text[file])
            if hit is None:
                findings.append(f"{file} no longer states the floor in its {label}, in a "
                                "form this rule reads")
                continue
            findings += [f"{file}'s {label} states {found}, {TY_CONF} fixes {want}"
                         for found in hit.groups() if found != want]

    rep.report("K-75", "interpreter floor site(s) disagreeing with the version ty.toml "
               "fixes:", findings,
               f"the {figures.words(len(_FLOOR_SITES))} sites under tools/ that restate "
               f"the interpreter floor spell ty.toml's {floor}")


def _at(text: str, offset: int) -> int:
    """The 1-based line an offset falls on, for a finding somebody has to go and read."""
    return text.count("\n", 0, offset) + 1


def _reaches(path: str, text: str) -> list[str]:
    """Every way one source outside the quarantine reaches into it."""
    found: list[str] = []
    for hit in _Q_IMPORT_RE.finditer(text):
        named = hit.group(1) or hit.group(2)
        found.append(f"{path}:{_at(text, hit.start())} imports `{named}`, and the "
                     "quarantine is what the landing loop does not depend on")
    launch = None if path in _Q_PATH_EXEMPT else _Q_PATH_RE.search(text)
    if launch is not None:
        found.append(f"{path}:{_at(text, launch.start())} names the quarantine as a "
                     "path, which couples it to an instrument whose decision is "
                     "deferred exactly as an import would")
    return found


def _quarantine(ctx: Context) -> None:
    """K-83: nothing outside `tools/quarantine/` imports or launches what is in it.

    Both rosters are read off the index rather than transcribed, so each grows and
    shrinks with the tree: a module the quarantine gains is protected the day it is
    staged, and a tool the landing loop gains is inside the window the same day. That is
    what makes this catch the import somebody adds next year rather than the ones that
    are absent today.

    Fail-closed twice over, on K-67's and K-75's ground. A quarantine this rule finds
    empty holds nothing out of anything, and a window it finds empty is the same failure
    from the other end; each is a finding rather than a green line over an empty walk.
    """
    rep = ctx.rep
    findings: list[str] = []

    roster = [path for path in ctx.corpus.tracked
              if path.startswith(QUARANTINE_TREE) and path.endswith(SOURCE_SUFFIX)]
    window = [path for path in ctx.corpus.tracked
              if path.startswith(TOOLS_TREE) and path.endswith(SOURCE_SUFFIX)
              and not path.startswith(QUARANTINE_TREE)]
    if not roster:
        findings.append(f"the index carries no {SOURCE_SUFFIX} file under "
                        f"{QUARANTINE_TREE}, so there is no quarantine for this rule to "
                        "hold anything out of")
    if not window:
        findings.append(f"the index carries no {SOURCE_SUFFIX} file under {TOOLS_TREE} "
                        "outside the quarantine, so this rule reads no site at all")

    # Both guards have to have passed before a site can be read: with either side empty
    # there is nothing for a site to reach into, or nothing to read.
    if roster and window:
        for path in window:
            if not (ctx.root / path).is_file():
                findings.append(f"{path} is in the index and not on disk, so whether it "
                                "reaches into the quarantine is undecided")
                continue
            findings += _reaches(path, _source(ctx, path))

    rep.report("K-83", "site(s) outside the quarantine that reach into it:", findings,
               f"none of the {len(window)} sources under {TOOLS_TREE} outside the "
               f"quarantine imports or launches one of the {len(roster)} it carries")
