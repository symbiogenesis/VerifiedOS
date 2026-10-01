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

K-67 holds the resolved lockfile against tools/pyproject.toml's checker pins.
The runtime reads the same manifest. Missing, malformed and duplicate declarations
are findings, so an unreadable side cannot silently remove the comparison.

K-75 is that rule one figure over, on the version the tools are *written* to rather
than the versions they run. The interpreter floor decides what the two checkers admit
and what this directory's Python may say, and it is written as a setting in ty's
dialect and in ruff's, shown in the manual install command, and restated as a literal
the provisioner probes the running interpreter against and as the version the CI workflows install;
ty.toml's is the source because it is the environment an editor's language server and
this gate both resolve against, and the only site that writes the figure bare. The
sites are enumerated rather than counted here, because the count is `_FLOOR_SITES`' to
state. The two dialects are why the rule is worth having rather than obvious: `3.14`
and `py314` are one figure in two spellings, so a bump applied to one of them does not
read as a disagreement with the other. Narrative prose links to the supported version
instead of copying it. The provisioner explicitly restates the floor, while
tools/pyproject.toml constrains the interpreter used for dependency resolution.
Both are held against ty's target.

The window is the enumerated sites rather than a directory, as K-67's is: the host
and guest workflows' `python-version` settings sit outside `tools/` and select the
interpreters their gates run on. Historical measurements retain the interpreter
versions used for those runs and are outside this current setup check.

K-84 is the third direction on the same registry and the one that faces outward. K-00
holds the registry against the checks and the selftest holds it against the mutants,
and nothing held a rule id *cited* outside the registry to naming a rule at all. K-11
does that for every other id family the repository declares, R-, CJ-, A-, B- and P-,
and the K- family is the one it does not reach. What makes the gap worth a rule is the
two-tier landing rule the plan's checklist conventions state: a Tier-B landing is a
spot read of an item's findings, admitted on four conditions, and the fourth is that
some rule holds whatever fact the landing created. Three of the four are gates that
run. The fourth is a claim about the item, so the item states it and this rule holds
the statement, which is what turns a promise into a condition something can fail.

The form is the one the landed items already write, a rule id in bold where the
landing says what that rule holds, and it is bold rather than plain because both forms
occur and only one is a claim. A rule *discussed* is written plain: a hole in the
numbering nothing records, a rule that retires when the generator replacing it lands,
a rule named as the price of an instrument. Holding every citation instead would
report the hole in the numbering as a finding against the document that reports it,
which is the one live case in the tree, and it belongs to the register act that owns
the hole rather than to a rule about landings.

Two things this one deliberately does not decide. Whether the named rule holds *that*
fact is a reading, and it is the residue every conferral here declares. And a
declaration is read where it is made and never demanded where it is absent: a tier is
a property of the reading a landing was given, so a landing taken before the tiers
existed has none to state and none a later hand can assign it. The floor is inside the
rule rather than in the floors group, on the precedent the two rules above set: a
corpus naming no holder at all is a finding here rather than a green line over nothing.

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
names the quarantine's directory in order to find it, and the selftest has to spell
the coupling in order to seed the mutant that proves this rule bites. The alternative was
to write both so the rule's own pattern would miss them, which is a rule written around
its own text. The *import* half takes no carve-out at all, so the two files the path half
excuses are still held against the coupling that matters, and it is the same reasoning
that keeps the selftest outside K-00's scan: a rule that read its own prover would decide
less rather than more.

What K-83 does not decide is whether the quarantine should still be one. That is the
condition `tools/quarantine/README.md` states per instrument and a person's to read at
the milestone that meets it.

K-100 is the fifth and its subject is the lane this repository builds in, written down.
`run.py provision` is that lane as a table: one row per switch, pin, checker,
distribution package and layout invariant, each naming the loop that wants the fact and
the artifact that owns it. **No artifact declared that set before the table did**, so the
provisioner became its owner, and what stands in for the entry nobody wrote is the
discipline the rows are written under: every row names a consumer already in this tree,
`find_package(GMP)` for libgmp-dev, `_compiler_args` for clang, `_ccache_args` for
ccache, cmake's `git describe` for git, and a row that cannot name one is not written.
That discipline was a sentence in a completion note, which is prose no rule reads.

**This is that discipline as a gate, and it decides two things.** Every path a row names
is one the git index carries, and every symbol a row names as that artifact's own is a
token that artifact still spells; and every `run.py` command a row names is one the entry
point's table carries. Neither is hypothetical: the tools here are refactored by whole
directories, seventeen entry points having become one package in a single item, so a row
naming a module by a path it has left, or a function by a name a shard renamed, is a lane
description that has stopped describing anything with every gate green.

**Read by import on one side and off the tree on the other**, which is what makes it a
comparison rather than a restatement. The table is `provision.FACTS` itself, so nothing
here transcribes a row and a row added tomorrow is inside the rule the day it is written;
what each row is held against is the index and the file, read at the root this run was
pointed at.

**What it does not decide is the half F-197c is actually about.** Whether the package set
is *complete* is a question no artifact in this repository can answer, because none
declares one; this holds that every row points at something real and says nothing about
the rows that are missing. That gap stays open and belongs to a register act.

**Two carve-outs, both declared.** A symbol is looked for only in a file this checker may
open, so `model/CMakeLists.txt`'s `find_package(GMP)` is held at the path alone: `model/`
is outside the document corpus by name and stood up as empty files in the mutation
sandbox, so reading it would need a declaration in `corpus.py`'s value window for one
token. And `run.py` is read as a command and never as a path, that name standing in an
owner cell only where the sentence names the loop that configures a tree; excluding it by
shape instead would mean refusing a file name with no directory in it, which is what
`THIRD-PARTY.md` is.

**Fail-closed on all three readings, and the three are not closed the same way**, which
is the part worth writing down. The path reading is refused per row: an empty fact table,
a row naming no artifact at all, and a path the index does not carry are each a finding
rather than a pass over nothing. The symbol and command readings cannot be, a row being
under no obligation to name either, so what closes them is a floor across the populated
table: an owner column that has stopped taking the `path's SYMBOL` form and a `needs`
column that has stopped naming `run.py` each report here, because a reading that has
narrowed to nothing while the paths still resolve is exactly the vacuous pass the floors
group exists for and is the one this rule could otherwise take silently. Both floors are
inside the rule for the reason K-84's is, the meta group reporting after the floors group
and so having no count to hand it. What none of the three reaches is the reading that
narrows *without* emptying, a single owner cell reworded off the `path's SYMBOL` form
dropping its symbol with the gate green, which is the residue `tools/check-rules.md`
declares of every pattern here.

K-119 holds the registry against the section of `tools/check-rules.md` that prices it.
That section sorts the rules into four reach classes, found by name, a computed value,
found by pattern and total, and states that every rule the registry carries is named
under exactly one of them. A class list is prose, so a rule registered without being
added to one leaves the section describing less than the table while every other gate
stays green, and a rule named under two leaves a reader unable to say which reach it has.

**The rules it decides about are the registry's own rows**, the set K-00 reads, so a row
is inside it the day it is written; the classes are read off the page, each at the
`Where the set is` opening it, matched in any letter case, and named by the first `**`
bold phrase after it, past a plain space and whatever words or italics then stand short
of a full stop or the line's end, any `.` counting as a full stop; that phrase must be
in `**` bold with no third `*` beside either pair and spell one of the four names
exactly, and the class's rules are read from one membership sentence standing anywhere
from that lead to the next class's lead, or to the section's end after the last class:
`which is what` or `that is what`, with only the first letter of the first word in
either case, single-spaced with plain spaces on one line apart from any underscore, a
plain list of ids, then `are`. The four class names are fixed here rather than read,
so a class retitled away and a fifth class opened that way are each a finding rather
than a class this rule stops or never starts reading, and so is a `Where the set is`
anywhere in the section, one wrapped across a line, spaced apart or set in underscore
italics included, that opens no class in that form. So is any
`which is what` or `that is what` the reading does not take in the section, in any
letter case or spacing and followed by a rule id past no letter, digit or `.`, so that
whitespace, punctuation and Markdown's emphasis, code, strikethrough, parenthesis and
link marks are crossed and one in underscore italics, wrapped across a line, spaced
apart, in capitals, or listing its ids in a code span, emphasis, strikethrough,
parentheses or a link is found; a membership sentence in other words,
`which is exactly what`, or one with a word, an HTML tag or an entity before its first
id, is read as prose, which is the residue. What that reading does not reach is a class
introduced in some other sentence form: it is read as part of the class before it, or
as part of no class ahead of the first, and is caught only where it carries a
membership sentence of its own, that sentence then being a class's second, one standing
ahead of every class, or one in a form the reading does not take. A list is decided
whole by a grammar of ids, `K-a through K-b` ranges, commas and `and`, and a range
expands over the active rows whose numbers it spans, so a struck row inside one is
skipped rather than placed.

**Fail-closed at every reading.** A missing section, a `Where the set is` that opens no
class, a membership sentence in a form the reading does not take or ahead of the first
class, a class with no membership sentence or with two, a list carrying a word the
grammar does not know, a range that runs backwards or ends on an id the registry does
not carry as an active rule, an id a class names that is struck, quarantined or never
registered, and a class naming no registered rule are each findings, so the floor is
inside the rule for the reason K-84's is. What it does not decide is whether a rule
sits in the class its row and code fit, which is a reading.
"""

import re
import tomllib
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING

from vos import commands as command_table
from vos import figures, toolenv
from vos.cli import provision

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== meta: the rule registry against the checks carried ==="

RULES = "tools/check-rules.md"
Q_RULES = "tools/quarantine/check-rules.md"
RULE_ID_RE = re.compile(r"\bK-\d{2,3}\b")
REGISTRY_ROW_RE = re.compile(r"^\| (K-\d{2,3}) \|")

README = "tools/README.md"
PROJECT = toolenv.PROJECT
LOCK = toolenv.LOCK
PROVISION = "tools/vos/cli/provision.py"

_HOST_WORKFLOW = ".github/workflows/host-gates.yml"
_GUEST_WORKFLOW = ".github/workflows/guest-gates.yml"
_CAMPAIGN_WORKFLOW = ".github/workflows/boot-crypto-target.yml"

TY_CONF = "tools/ty.toml"
RUFF_CONF = "tools/ruff.toml"

PLAN = "docs/implementation/implementation-checklist.md"
LOG = "docs/implementation/completion-log.md"

# A holder citation, in the form the landed items write it: the rule id in bold, on the
# sentence saying what that rule holds. Bold is the whole of what separates a claim
# from prose about the checker, which is why the plan's conventions state the form
# rather than leaving the typography to be inferred.
_HOLDER_RE = re.compile(r"\*\*(K-\d{2,3})\*\*")

# A landing declaration, line-anchored so that a sentence mentioning one is not read as
# making one. The first pattern finds the line at all and the second decides its form,
# which is what makes a mistyped declaration a finding instead of a line nothing reads.
_LANDED_RE = re.compile(r"[^\S\r\n]*(?:\*+ )?Landed:")
_TIER_RE = re.compile(r"[^\S\r\n]*(?:\*+ )?Landed: Tier (?P<tier>[AB])\b(?P<rest>.*)")

# K-119's reading of the reach section. A class opens with `Where the set is`, in any
# letter case so that a lead written mid-sentence is read too, and is named by the first
# `**` bold phrase after it, past a plain space and whatever words or italics then stand,
# short of a full stop or the line's end: any `.` ends the lead's reach, one inside a
# code span or a link included. The phrase is in `**` bold with no third `*` beside
# either pair, so a name in bold italics or trailed by a stray `*` opens nothing, and
# every `Where the set is` in the section has to open a class. The lookahead past the
# closing pair holds that side; the phrase's own characters and the crossing before it
# already refuse a `*` against the other three. The four class names are fixed here
# rather than read off the page and the bold phrase is compared with them exactly, the
# lead alone being matched in any letter case, so a class retitled away, a fifth class
# opened that way, and a `Where the set is` naming no class are each a finding rather
# than a class this rule silently stops or never starts reading. The opener takes the
# lead's four words single-spaced with plain spaces, no word character before them and a
# plain space after them; the lead-finder is wider, any whitespace between the words, a
# line break included, and only a letter or digit beside them refused, so a lead wrapped
# across a line, spaced apart, set in underscore italics or followed by markup or
# punctuation is found and, opening nothing, is a finding rather than text read as part
# of the class before it.
REACH_HEADING = "## What a passing run does not decide"
REACH_CLASSES = ("name", "computed value", "pattern", "total")
_CLASS_LEAD_RE = re.compile(
    r"(?<![^\W_])Where\s+the\s+set\s+is(?![^\W_])", re.IGNORECASE)
_CLASS_OPEN_RE = re.compile(
    r"\bWhere the set is (?:[^*.\r\n]|\*(?!\*))*?\*\*([^*\r\n]+)\*\*(?!\*)", re.IGNORECASE)

# A class's membership sentence: `which is what` or `that is what`, with only the first
# letter of the first word in either case, so that one opening a sentence and one
# written mid-sentence are both read, the list, then `are`. The capture admits only the
# characters a list is spelled in, so a sentence that merely discusses a rule is not
# read as a list; what it captures is then decided whole by the grammar below, so a word
# the grammar does not know is a finding rather than a list cut short at it. Ids admit
# the letter suffix, so a suffixed id is named and resolved rather than making the
# sentence unreadable. The finder is wider, the three words in any letter case with any
# whitespace between them, a line break included, then an id past no letter, digit or
# `.`, and only a letter or digit before them refused, so a membership sentence set in
# underscore italics, wrapped, spaced apart, in capitals or listing its ids in a code
# span, emphasis, strikethrough, parentheses or a link is found and, read by no class,
# is a finding rather than a list the section names and nothing reads. Prose such as
# `which is what separates` reaches a word before any id and is not found, and neither
# is an id past a `.`; a membership sentence in other words, `which is exactly what`,
# or one with a word, an HTML tag or an entity before its first id, is read as prose,
# which is the residue.
_MEMBERS_RE = re.compile(r"\b(?:[Ww]hich|[Tt]hat) is what (K-[\w ,-]*?) are\b")
_MEMBERS_FIND_RE = re.compile(
    r"(?<![^\W_])(?:which|that)\s+is\s+what(?:[^\w.]|_)*K-\d", re.IGNORECASE)
_CLASS_ID = r"K-\d{2,3}[a-z]?"
_CLASS_ITEM = rf"{_CLASS_ID}(?: through {_CLASS_ID})?"
_CLASS_ITEM_RE = re.compile(rf"({_CLASS_ID})(?: through ({_CLASS_ID}))?")
_CLASS_LIST_RE = re.compile(rf"{_CLASS_ITEM}(?:(?:, and |, | and ){_CLASS_ITEM})*")

# A struck registry row, retired or never allocated: an id the registry carries and no
# run reports, so a class naming one is placing a rule that decides nothing.
_STRUCK_ROW_RE = re.compile(rf"^\| ~~({_CLASS_ID})~~ \|")

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
_Q_PATH_EXEMPT = ("tools/vos/checks/meta.py", "tools/vos/cli/selftest.py")

# The interpreter floor, as the type checker's own environment fixes it.
_FLOOR_SRC_RE = re.compile(r'(?m)^python-version = "([^"\r\n]*)"')

# A repository path an owner cell names, and the same path with the symbol that cell
# calls that artifact's own. The symbol run admits an `and` chain because a row names two
# constants of one module that way, and the continuation has to look like a symbol,
# upper-cased or underscored, so that `VERILATOR_PIN, which is ... and arrives by` stops
# at the constant instead of reading the sentence after it.
_OWNER_PATH_RE = re.compile(r"((?:[\w.-]+/)*[\w.-]+\.(?:py|toml|md|txt))")
_OWNER_SYM_RE = re.compile(
    r"((?:[\w.-]+/)*[\w.-]+\.(?:py|toml|md|txt))'s "
    r"([A-Za-z_]\w*(?:\(\w*\))?(?: and [A-Za-z_]*[A-Z_]\w*)*)")

# The entry point, named in an owner cell as the command that drives a stage rather than
# as a path. It is excluded by name because the alternative is a shape that refuses a
# file name carrying no directory, which is what THIRD-PARTY.md is.
_ENTRY_POINT = "run.py"
_OWNER_CMD_RE = re.compile(r"run\.py ([a-z][\w-]*)")

# Where a symbol may be looked for: this directory, and any document the corpus already
# carries. `model/` is neither, being outside the corpus by name and stood up as empty
# files in the mutation sandbox, so a token read there would pass on the host and fail
# every baseline; those rows are held at the path alone.
_SYMBOL_TREE = "tools/"


def _plain(floor: str) -> str:
    """The floor as ty.toml and the installer spell it."""
    return floor


def _packed(floor: str) -> str:
    """ruff's own spelling, the same figure with its separator dropped."""
    return "py" + floor.replace(".", "")


# The floor's sites, each with the file it is in, the pattern that reads it, and how
# that site spells the figure. Every match of a pattern and every group it captures is
# held, because a workflow with several jobs installs the interpreter once per job.
_FLOOR_SITES: list[tuple[str, str, re.Pattern[str], Callable[[str], str]]] = [
    ("target version", RUFF_CONF,
     re.compile(r'(?m)^target-version = "([^"\r\n]*)"'), _packed),
    ("manual interpreter install", README,
     re.compile(r"`uv python install --no-config ([^`\s]+)`"), _plain),
    ("provisioned floor", PROVISION,
     re.compile(r'(?m)^INTERPRETER_FLOOR = "([^"\r\n]*)"'), _plain),
    ("workflow interpreter", _HOST_WORKFLOW,
     re.compile(r'(?m)^\s*python-version: "([^"\r\n]*)"'), _plain),
    ("workflow interpreter", _GUEST_WORKFLOW,
     re.compile(r'(?m)^\s*python-version: "([^"\r\n]*)"'), _plain),
    ("workflow interpreter", _CAMPAIGN_WORKFLOW,
     re.compile(r'(?m)^\s*python-version: "([^"\r\n]*)"'), _plain),
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
    # every rule the registry carries, hoisted out of the K-00 block below because K-84
    # holds citations against the same set: an absent registry leaves it empty, which is
    # the fail-closed reading both rules want rather than a comparison against nothing
    seen: set[str] = set()
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

    _classes(ctx, seen)
    _pins(ctx)
    _floor(ctx)
    # A holder citation resolves against either registry, because a quarantined rule
    # still holds what the landing created; what quarantine moved is which loop runs it
    # and never whether it holds. Reading the landing loop's registry alone would report
    # every landing held by a quarantined rule as naming nothing, which is a finding
    # against the landing for an act taken two items away from it.
    _landings(ctx, seen | _quarantined_rules(ctx))
    _quarantine(ctx)
    _lane(ctx)
    rep.line()


def _lane(ctx: Context) -> None:
    """K-100: every row of the lane's fact table names something this tree carries.

    The table is imported and each row is held against the index and the tree, so this
    adds no second copy of the lane and a row written tomorrow is inside the rule that
    day. What a row must name is an artifact the index carries; where it goes further
    and names that artifact's own constant or function, the token has to still be there.

    Fail-closed at each of the three readings, and the last two need a floor of their
    own rather than a per-row refusal. An empty table, a row naming no artifact at all,
    and a path the index does not carry each stop that row's comparison rather than
    passing over it. A row is not obliged to name a symbol or a command, so neither of
    those can be refused per row; what is refused is the reading going to zero across a
    populated table, an owner column that has stopped taking the `path's SYMBOL` form or
    a `needs` column that has stopped naming `run.py` being a reading that has moved and
    not a table with nothing left to check. Those two floors are inside the rule for the
    reason K-84's is, the meta group reporting after the floors group and so having no
    count to hand it.
    """
    rep = ctx.rep
    findings: list[str] = []
    facts = provision.FACTS
    if not facts:
        findings.append(f"{PROVISION} declares no fact at all, so this lane is described "
                        "by nothing and there is no row to hold")

    commands = {command.name for command in command_table.COMMANDS}
    paths = symbols = named = 0
    for fact in facts:
        found = [path for path in _OWNER_PATH_RE.findall(fact.owner)
                 if path != _ENTRY_POINT]
        if not found:
            findings.append(f"the row for `{fact.name}` names no artifact this rule can "
                            f"read as a path, so what owns that fact is unresolvable")
        carried = set()
        for path in found:
            paths += 1
            if path in ctx.corpus.tracked:
                carried.add(path)
            else:
                findings.append(f"the row for `{fact.name}` names {path} as what owns it, "
                                "and the git index carries no such path")

        for path, group in _OWNER_SYM_RE.findall(fact.owner):
            if path not in carried:
                continue
            if not (path.startswith(_SYMBOL_TREE) or path in ctx.corpus):
                continue
            text = _source(ctx, path) if path.startswith(_SYMBOL_TREE) else ctx.text(path)
            for symbol in group.split(" and "):
                symbols += 1
                if symbol not in text:
                    findings.append(
                        f"the row for `{fact.name}` names `{symbol}` as {path}'s, and that "
                        "file no longer spells it, so the fact names a consumer this "
                        "tree does not have")

        for command in _OWNER_CMD_RE.findall(f"{fact.needs} {fact.owner}"):
            named += 1
            if command not in commands:
                findings.append(f"the row for `{fact.name}` names `run.py {command}` as what "
                                "wants it, and the entry point carries no such command")

    if facts and not symbols:
        findings.append("no row of the lane's fact table names a symbol as an artifact's "
                        "own, so the reading that holds a consumer's name against the "
                        "file spelling it decides nothing")
    if facts and not named:
        findings.append("no row of the lane's fact table names a `run.py` command, so "
                        "the reading that holds a row's consumer against the entry "
                        "point's table decides nothing")

    rep.report("K-100", "row(s) of the lane's fact table naming what this tree does not "
               "carry:", findings,
               f"the {paths} artifacts {PROVISION}'s {len(facts)} rows name are paths the "
               f"index carries, the {symbols} symbols they name are ones those files "
               f"still spell, and the {named} run.py commands they name are the entry "
               "point's")


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
    """K-67: the lockfile agrees with the runtime's manifest reader."""
    rep = ctx.rep
    findings: list[str] = []
    pins: dict[str, str] = {}
    try:
        pins = toolenv.checker_pins(ctx.root)
    except (OSError, ValueError, TypeError, KeyError) as err:
        findings.append(f"{PROJECT} cannot supply exact ty and ruff pins: {err}")
    if pins:
        try:
            packages = tomllib.loads(_source(ctx, LOCK))["package"]
            if not isinstance(packages, list) or not all(
                    isinstance(package, dict) for package in packages):
                findings.append(f"{LOCK}'s package must be an array of tables")
            else:
                for name, want in pins.items():
                    versions = [package.get("version") for package in packages
                                if package.get("name") == name]
                    if versions != [want]:
                        findings.append(f"{LOCK}'s {name} versions are {versions!r}, "
                                        f"{PROJECT} pins {want}")
        except (ValueError, TypeError, KeyError) as err:
            findings.append(f"{LOCK} cannot supply resolved checker pins: {err}")

    rep.report("K-67", f"pin site(s) disagreeing with the versions {PROJECT} "
               "fixes:", findings,
               f"the lockfile states ty {pins.get('ty')} and "
               f"ruff {pins.get('ruff')}, the versions {PROJECT} fixes")


def _floor(ctx: Context) -> None:
    """K-75: every site stating the interpreter floor states the one ty.toml fixes.

    Fail-closed in the same two places K-67 is. The source either parses in the form it
    is written in today or is a finding, so a reworded setting cannot take the
    comparison down and leave the rule green; and a site whose pattern no longer matches
    is a finding rather than a site quietly dropped from the enumeration.

    The comparison uses each site's spelling: ruff packs the version into one token
    of its own dialect instead of writing it the way ty.toml does.
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
    # source there is nothing to compare a site to, and without the README every site
    # that document carries is missing for a reason that is not its own.
    floor = stated.group(1) if stated else ""
    if not findings and doc is not None:
        try:
            required = tomllib.loads(_source(ctx, PROJECT))["project"]["requires-python"]
            major, minor = floor.split(".")
            want = f">={floor},<{major}.{int(minor) + 1}"
            if required != want:
                findings.append(f"{PROJECT}'s requires-python states {required!r}, "
                                f"{TY_CONF} requires {want}")
        except (ValueError, TypeError, KeyError) as err:
            findings.append(f"{PROJECT} cannot supply requires-python: {err}")
        # one read per file the table names, the README's coming from the corpus the
        # run already holds rather than from a second trip to disk
        text: dict[str, str] = {README: doc.raw}
        for _, file, _, _ in _FLOOR_SITES:
            if file not in text:
                text[file] = _source(ctx, file)

        for label, file, pattern, spell in _FLOOR_SITES:
            want = spell(floor)
            hits = list(pattern.finditer(text[file]))
            if not hits:
                findings.append(f"{file} no longer states the floor in its {label}, in a "
                                "form this rule reads")
                continue
            findings += [f"{file}'s {label} states {found}, {TY_CONF} fixes {want}"
                         for hit in hits for found in hit.groups() if found != want]

    rep.report("K-75", "interpreter floor site(s) disagreeing with the version ty.toml "
               "fixes:", findings,
               f"the {figures.words(len(_FLOOR_SITES))} sites that restate "
               f"the interpreter floor spell ty.toml's {floor}")


def _quarantined_rules(ctx: Context) -> set[str]:
    """Every rule id the quarantine's own registry carries.

    Read for K-84 alone and deliberately not for K-00, which holds the landing loop's
    registry against the checks reporting *under it*: a quarantined rule reports under
    the quarantine's gate, so admitting it here would make K-00 green over a rule this
    loop no longer runs. An unreadable quarantine registry yields the empty set, which
    leaves K-84 exactly as fail-closed as it was before the quarantine existed.
    """
    doc = ctx.corpus.get(Q_RULES)
    if doc is None:
        return set()
    return {m.group(1) for m in re.finditer(r"(?m)^\|\s*(K-\d+)\s*\|", doc.raw)}


def _landings(ctx: Context, registered: set[str]) -> None:
    """K-84: a holder citation names a registered rule, and a Tier-B landing names one.

    Two readings of the plan's two-tier landing rule, held as one rule because they are
    one claim seen from its two ends. A landing that created a fact says which rule
    holds it, and the rule it names is one the registry carries. Struck registry
    rows in the `retired` group preserve former rule identities for historical
    completion-log evidence only; never-allocated IDs remain invalid citations.

    Fail-closed in three places. An unreadable registry leaves `registered` empty, so
    every citation is a finding rather than a pass over nothing; a corpus stating no
    holder at all is a finding, which is this rule's own floor; and a `Landed:` line
    whose form this rule cannot read is a finding rather than a declaration silently
    skipped.

    The citation half reads the whole document corpus and the declaration half reads
    the plan and the completion log, and the asymmetry is deliberate: naming a holder
    is the same claim wherever it is written, where a landing is an act the plan
    records, in the log for a landed item and in the plan for an open one.
    """
    rep = ctx.rep
    findings: list[str] = []
    registry = ctx.corpus.get(RULES)
    retired = ({m.group(1) for _, m in registry.unfenced(
        "| ~~K-", re.compile(r"^\| ~~(K-\d{2,3})~~ \| retired \|"))}
        if registry is not None else set())

    if not registered:
        findings.append(f"neither {RULES} nor {Q_RULES} yields a rule this run can "
                        "read, so a holder citation would be held against nothing")

    cited = 0
    for doc in ctx.corpus.docs:
        for m in _HOLDER_RE.finditer(doc.raw):
            if doc.is_fenced(m.start()):
                continue
            cited += 1
            if m.group(1) not in registered and not (
                    doc.name == LOG and m.group(1) in retired):
                findings.append(f"{doc.name}:{doc.at(m.start())} names {m.group(1)} as "
                                f"the rule holding what it created, and {RULES} carries "
                                "no active rule for that claim (retired rules apply "
                                "only to completion-log evidence)")
    if not cited and registered:
        findings.append("no document names a rule holding what a landing created, so "
                        "this rule reads nothing; the form is the rule id in bold, which "
                        f"{PLAN}'s checklist conventions fix")

    # a landed item's note, and so its declaration, lives in the completion log from
    # S10b; the plan is still read because an open item's note stays there
    declared = 0
    for name in (PLAN, LOG):
        doc = ctx.corpus.get(name)
        if doc is None:
            findings.append(f"{name} is not in the repository, so no landing can be "
                            "read there")
            continue
        for i, _ in doc.unfenced("Landed:", _LANDED_RE):
            declared += 1
            tier = _TIER_RE.match(doc.lines[i])
            if tier is None:
                findings.append(f"{name}:{i + 1} declares a landing in a form this rule "
                                "does not read; a declaration is 'Landed: Tier A' or "
                                "'Landed: Tier B under' the rules holding what it created")
            elif tier.group("tier") == "B" and not _HOLDER_RE.search(tier.group("rest")):
                findings.append(f"{name}:{i + 1} lands at Tier B and names no rule "
                                "holding what it created, which is the fourth of the "
                                "four conditions Tier B is admitted on")

    rep.report("K-84", "holder citation(s) and landing declaration(s) no registry "
               "answers:", findings,
               f"the corpus's {cited} holder citations name active, quarantined or "
               f"historical retired rules, and each of the {declared} landing declarations "
               "in the plan and the completion log states a tier and, at Tier B, the "
               "rule holding what it created")


def _rule_key(rule: str) -> tuple[int, str]:
    """A rule id's place in the numbering, a letter suffix ordering it after its number.

    Every id reaching here matched `_CLASS_ID` or `REGISTRY_ROW_RE`, both of which fix
    the digits and at most one lower-case letter after them, so the split cannot fail.
    """
    digits = rule[2:].rstrip("abcdefghijklmnopqrstuvwxyz")
    return int(digits), rule[2 + len(digits):]


def _class_members(listed: str, registered: set[str], struck: set[str],
                   quarantined: set[str]) -> tuple[list[str], list[str]]:
    """One class's list, expanded: the registered rules it names, and what it names wrongly.

    The list has already matched the whole grammar, so every item is an id or a range.
    A range expands over the registered rules whose numbers it spans, which is what lets
    a struck row sit inside one without being placed; its two ends have to be registered
    themselves, so a range cannot quietly reach past the rules it was written over.
    """
    members: list[str] = []
    wrong: list[str] = []

    def unplaceable(rule: str, role: str) -> str | None:
        if rule in registered:
            return None
        if rule in struck:
            why = "which the registry carries struck, so no run reports it"
        elif rule in quarantined:
            why = "which the quarantine's registry carries and its own gate runs"
        else:
            why = "which the registry does not carry"
        return f"{role} {rule}, {why}"

    for m in _CLASS_ITEM_RE.finditer(listed):
        first, last = m.group(1), m.group(2)
        if last is None:
            problem = unplaceable(first, "names")
            if problem:
                wrong.append(problem)
            else:
                members.append(first)
            continue
        ends = [p for p in (unplaceable(first, "opens a range at"),
                            unplaceable(last, "closes a range at")) if p]
        if ends:
            wrong += ends
            continue
        lo, hi = _rule_key(first), _rule_key(last)
        if lo >= hi:
            wrong.append(f"names the range {first} through {last}, which runs backwards "
                         "or spans one rule")
            continue
        members += sorted((r for r in registered if lo <= _rule_key(r) <= hi),
                          key=_rule_key)
    return members, wrong


def _classes(ctx: Context, registered: set[str]) -> None:
    """K-119: every registered rule is named under exactly one reach class.

    The rules decided about are the registry's own rows, so nothing narrows them; the
    classes are read off the reach section, and every way that reading can fail is a
    finding rather than a class read as empty. A class that could not be read is not
    followed by a finding for every rule it would have placed, because the unreadable
    class is already the finding and the rest would restate it once per member.
    """
    rep = ctx.rep
    findings: list[str] = []
    doc = ctx.corpus.get(RULES)
    placed: dict[str, list[str]] = {rule: [] for rule in registered}
    sizes: dict[str, int] = {}
    unread = False

    if doc is None:
        findings.append(f"{RULES} is not in the repository, so there is no reach class "
                        "to read")
    elif not registered:
        findings.append(f"{RULES} registers no rule this run can read, so no class "
                        "membership is held against anything")
    else:
        struck = {m.group(1) for _, m in doc.unfenced("| ~~K-", _STRUCK_ROW_RE)}
        quarantined = _quarantined_rules(ctx)
        top = next((i for i, line in enumerate(doc.lines)
                    if line == REACH_HEADING and not doc.fenced[i]), None)
        if top is None:
            findings.append(f"{RULES} carries no '{REACH_HEADING}' section, so no rule "
                            "can be placed in a reach class")
            unread = True
        else:
            bottom = next((i for i in range(top + 1, len(doc.lines))
                           if doc.lines[i].startswith("## ") and not doc.fenced[i]),
                          len(doc.lines))
            lo = doc.starts[top]
            hi = doc.starts[bottom] if bottom < len(doc.lines) else len(doc.raw)
            opens = [m for m in _CLASS_OPEN_RE.finditer(doc.raw, lo, hi)
                     if not doc.is_fenced(m.start())]
            # A lead that opens no class leaves what it introduces read as part of the
            # class before it, so it is reported rather than passed over.
            starts = {m.start() for m in opens}
            findings += [f"{RULES}:{doc.at(m.start())} states 'Where the set is' in a form "
                         "that opens no reach class this rule reads: the four words "
                         "single-spaced with plain spaces on one line, with no underscore "
                         "before the first and a plain space after the last, then the "
                         "class in `**` bold with no third `*` beside either pair before "
                         "a full stop or the line's end"
                         for m in _CLASS_LEAD_RE.finditer(doc.raw, lo, hi)
                         if m.start() not in starts and not doc.is_fenced(m.start())]
            # The membership sentences each region reads: the stretch ahead of the first
            # class, then each class from its lead to the next one's or the section's end.
            cuts = [lo, *(m.start() for m in opens), hi]
            regions = [[c for c in _MEMBERS_RE.finditer(doc.raw, a, b)
                        if not doc.is_fenced(c.start())] for a, b in pairwise(cuts)]
            # A membership sentence in a form no region reads leaves the rules it names
            # unread while its class reads as complete, so it is reported. One lying
            # inside a sentence a region read is a word of that list, which the grammar
            # below already decides, so it is not reported a second time. Prose naming a
            # rule past `is what` is found the same way and cannot be told from one, so
            # the finding states what it found and both ways out of it.
            spans = [c.span() for clauses in regions for c in clauses]
            missed = [c for c in _MEMBERS_FIND_RE.finditer(doc.raw, lo, hi)
                      if not doc.is_fenced(c.start())
                      and not any(a <= c.start() < b for a, b in spans)]
            findings += [f"{RULES}:{doc.at(c.start())} states 'which is what' or 'that is "
                         "what' before a rule id, which this rule reads as a membership "
                         "sentence and cannot take: either rewrite it as one ('which is "
                         "what' or 'that is what', with only the first letter of the first "
                         "word in either case, single-spaced with plain spaces on one line "
                         "apart from any underscore, a plain list of ids, then 'are') or "
                         "reword the prose so no id follows 'is what'"
                         for c in missed]
            if missed:
                unread = True
            # No class's region reaches back past the first opener, so a membership
            # sentence ahead of it belongs to a class no reading sees.
            ahead = regions[0]
            findings += [f"{RULES}:{doc.at(c.start())} states a membership sentence ahead "
                         "of the first reach class, so no class reads it" for c in ahead]
            if ahead:
                unread = True
            seen_classes: set[str] = set()
            for k, m in enumerate(opens):
                name = m.group(1)
                where = f"{RULES}:{doc.at(m.start())}"
                if name not in REACH_CLASSES:
                    findings.append(f"{where} opens a reach class '**{name}**' that is not "
                                    f"one of the {figures.words(len(REACH_CLASSES))} this "
                                    "rule reads, so the rules it names are placed nowhere")
                    unread = True
                    continue
                if name in seen_classes:
                    findings.append(f"{where} opens the '{name}' class a second time")
                    unread = True
                    continue
                seen_classes.add(name)
                # The region runs from this lead to the next, or to the section's end
                # after the last, so a membership sentence standing between the lead and
                # the bold name is this class's own and counted with the rest rather than
                # falling between two regions.
                clauses = regions[k + 1]
                if len(clauses) != 1:
                    findings.append(
                        f"{where}: the '{name}' class states "
                        f"{'no' if not clauses else figures.words(len(clauses))} "
                        "membership sentence(s) this rule reads, where it needs exactly "
                        "one: 'which is what' or 'that is what', with only the first "
                        "letter of the first word in either case, its rules, then 'are'")
                    unread = True
                    continue
                listed = clauses[0].group(1)
                if not _CLASS_LIST_RE.fullmatch(listed):
                    findings.append(f"{RULES}:{doc.at(clauses[0].start())}: the '{name}' "
                                    f"class lists '{listed}', which is not a list of rule "
                                    "ids and ranges this rule reads")
                    unread = True
                    continue
                members, wrong = _class_members(listed, registered, struck, quarantined)
                findings += [f"the '{name}' class {problem}" for problem in wrong]
                if not members:
                    findings.append(f"the '{name}' class names no rule the registry "
                                    "carries")
                for rule in sorted(set(members), key=_rule_key):
                    if members.count(rule) > 1:
                        findings.append(f"the '{name}' class names {rule} more than once")
                    placed[rule].append(name)
                sizes[name] = len(set(members))
            for name in REACH_CLASSES:
                if name not in seen_classes:
                    findings.append(f"{RULES} opens no '{name}' class in a form this rule "
                                    "reads: 'Where the set is', then the class in `**` "
                                    "bold with no third `*` beside either pair")
                    unread = True

    for rule in sorted(placed, key=_rule_key):
        classes = placed[rule]
        if len(classes) > 1:
            findings.append(f"{rule} is named under {figures.words(len(classes))} reach "
                            f"classes, {' and '.join(classes)}, where the page says one")
        elif not classes and not unread and doc is not None:
            findings.append(f"{rule} is registered and named under no reach class")

    rep.report("K-119", "finding(s) in how the reach classes place the registry's rules:",
               findings,
               f"each of the registry's {len(registered)} rules is named under exactly one "
               f"of the {figures.words(len(REACH_CLASSES))} reach classes ("
               + ", ".join(f"{name} {sizes.get(name, 0)}" for name in REACH_CLASSES) + ")")


def _at(text: str, offset: int) -> int:
    """The 1-based line an offset falls on, for a finding somebody has to go and read."""
    return text.count("\n", 0, offset) + 1


def _reaches(path: str, text: str) -> list[str]:
    """Every way one source outside the quarantine reaches into it."""
    # Both patterns require this literal. Reject ordinary sources in one substring
    # scan before attempting regex matches at every character and line boundary.
    if "quarantine" not in text:
        return []
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
