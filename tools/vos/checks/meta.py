# SPDX-License-Identifier: Apache-2.0
"""meta: the rule registry against the checks this package carries, both directions.

The authored check-registry.json supplies required rule metadata, including its
population's reach class. The driver binds every group to its callback and holds the
verdicts of each clean group against its declarations. This group checks the generated
documentation against that same owner, and reports definition or execution findings
collected by the driver. Correct claims and classifications remain review judgments.

The locked uv bootstrap validates dependency resolution before dispatch. Runtime
checker pins come from the same project manifest and remain exact.

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
both readings: a quarantine carrying no module and a
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

"""

import re
from typing import TYPE_CHECKING

from vos import checkregistry
from vos import commands as command_table
from vos.cli import provision

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== meta: the rule registry against the checks carried ==="

RULES = "tools/check-rules.md"
Q_RULES = "tools/quarantine/check-rules.md"

PROVISION = "tools/vos/cli/provision.py"



PLAN = "PLAN.md"
LOG = "docs/implementation/completion-log.md"

# A holder citation, in the form the landed items write it: the rule id in bold, on the
# sentence saying what that rule holds. Bold is the whole of what separates a claim
# from prose about the checker, which is why the plan's conventions state the form
# rather than leaving the typography to be inferred.
_HOLDER_RE = re.compile(rf"\*\*({checkregistry.ID_PATTERN})\*\*")

# A landing declaration, line-anchored so that a sentence mentioning one is not read as
# making one. The first pattern finds the line at all and the second decides its form,
# which is what makes a mistyped declaration a finding instead of a line nothing reads.
_LANDED_RE = re.compile(r"[^\S\r\n]*(?:\*+ )?Landed:")
_TIER_RE = re.compile(r"[^\S\r\n]*(?:\*+ )?Landed: Tier (?P<tier>[AB])\b(?P<rest>.*)")

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


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)
    if ctx.registry is None:
        try:
            ctx.registry = checkregistry.read(ctx.root)
        except (OSError, ValueError, TypeError) as exc:
            ctx.registry_faults.append(str(exc))
    seen = set(ctx.registry.identifiers) if ctx.registry is not None else set()
    _landings(ctx, seen | _quarantined_rules(ctx))
    _quarantine(ctx)
    _lane(ctx)
    _registry(ctx)
    rep.line()


def _registry(ctx: Context) -> None:
    """K-00: generated views and actual group verdicts share one typed owner."""
    findings = list(ctx.registry_faults)
    if checkregistry.SOURCE not in ctx.corpus.tracked:
        findings.append(f"{checkregistry.SOURCE} is not tracked")
    doc = ctx.corpus.get(RULES)
    if doc is None:
        findings.append(f"{RULES} is not in the repository")
    elif ctx.registry is not None:
        try:
            rendered = checkregistry.render(ctx.registry, doc.raw)
        except ValueError as exc:
            findings.append(str(exc))
        else:
            if rendered != doc.raw:
                if ctx.fix:
                    ctx.fixed[RULES] = rendered
                    ctx.rep.line(f"fixed: {RULES} from its rule metadata")
                else:
                    findings.append(f"{RULES} has stale generated registry or reach views")
    if ctx.registry is not None:
        # This is the final verdict in the final group. It checks all prior group
        # reports plus this group's other rules, before reporting itself.
        rules = [r for r in ctx.registry.rules if r.group == "meta" and r.ident != "K-00"]
        findings += checkregistry.verdict_faults(
            rules, ctx.rep.decisions[ctx.group_start:],
            clean=ctx.rep.findings == ctx.group_findings)
    ctx.rep.report("K-00", "invalid rule definitions, verdicts or generated views:", findings,
                   "typed rule metadata binds the executable groups, every clean group "
                   "decides its declared rules, and generated registry views agree")


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
    return {m.group(1) for m in re.finditer(
        rf"(?m)^\|\s*({checkregistry.ID_PATTERN})\s*\|", doc.raw)}


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
        "| ~~K-", re.compile(rf"^\| ~~({checkregistry.ID_PATTERN})~~ \| retired \|"))}
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

    Fail-closed twice over, on K-75's ground. A quarantine this rule finds
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
