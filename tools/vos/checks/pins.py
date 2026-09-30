# SPDX-License-Identifier: Apache-2.0
"""pins: every upstream pin this repository states, against the artifact that owns it.

An upstream arrives here as a gitlink: the index carries a path and a commit id and
none of the code, and [THIRD-PARTY.md](../../../THIRD-PARTY.md) carries the licence
record over those pins, one row per submodule, each stating the short id its terms
were read at. The row is hand-copied from the gitlink and the copy had no owner.

**That copy is the one derived fact in this repository whose defect cannot be
repaired downstream.** [AGENTS.md](../../../AGENTS.md) and [the plan's
§12](../../../docs/implementation/implementation-checklist.md#12-build-order-milestones-and-execution-state)
both say it: a licence is a property of the *arrival*, read at the milestone that
would incorporate the upstream, and work built on terms that forbid the composition
is not re-licensed by finding out later. A gitlink advanced without its row moving
leaves the page asserting that somebody read an edition nobody has opened, and every
other rule here stays green over it, because the row is prose that resolves, cites
nothing, and counts nothing.

**Three artifacts state a pin and they are not three opinions.** The index owns it;
the record copies it and is where the terms were read; and the rest of the
repository, the plan's completion notes, the RTL delta's provenance table, the ported
model headers and the tools' own oracle-tree name, restates what the record says. So
the rule is two hops rather than one comparison, and each hop has its own owner.

**Hop one: the record against the index, in both directions, and never repaired.**
A gitlink with no row is an upstream whose terms are not on the page at all; a row
naming no gitlink is a pin for something this repository does not carry; and a row
whose id is not the gitlink's is the defect above. None of the three is rewritten
under `--fix`, and that is the strongest ground in this rule rather than a
convenience. The Pin cell is where the licence was read, and the row's own Licence
cell, its Standing, and the page's reading paragraphs are that reading; advancing the
cell from the index would record a reading nobody took, under a flag run to repair
checklist arithmetic. [marks.py](marks.py) already refuses this repair one artifact
over, on the same ground: what `--fix` rewrites is recomputed from something the
repository already determined, and a provenance claim is not that. The finding *is*
the instruction: somebody moved a gitlink and owes a licence read.

**Hop two: every other site against the record.** What those sites restate is the
record's account, so the record is the artifact that owns the id for them, exactly as
an entry owns a figure the documents restate under K-69. A site is found by the shape
a restatement takes rather than by a list of places to look: an abbreviated object id
on a line that has already named the upstream it belongs to.

**A pin whose row is itself a finding has its sites left alone**, reported by
neither hop. One gitlink advancing moves every site at once, so holding the sites
against a record that is already red would price one act as a dozen findings and
point every one of them at a repair that belongs at the record. One act, one
finding, at the one place a person has to act.

**Nothing here is repaired, and the ground is the same one the whole rule stands
on.** The obvious reading is that a short id in a normalized document is a pure token
substitution and so belongs to `--fix`, and it is wrong about every site this
repository actually has. Each of them states the id *beside what was done at it*:
the record's own row beside the terms read there, the RTL delta's provenance table
beside the date its tree was read on, the plan's completion notes beside a licence
reading taken at a milestone, a ported header beside the file it was transplanted
from, and `vos/env.py`'s `ORACLE_TREE` beside a build tree that stands on disk.
Rewriting the id alone leaves every one of those sentences describing work done at a
commit it no longer names, which is the half-a-sentence hazard that keeps K-70
report-only and, here, is worse than that: it would record a licence reading nobody
took, under a flag run to repair checklist arithmetic. Two further grounds fall in
the same direction and would each be enough on their own, the ported headers being
under [model/](../../../model/)'s `-text` tree where a rewrite risks the line-ending
sweep K-57 names, and `vos/env.py`'s id being a directory's name rather than a
sentence's figure. A pin is never arithmetic to recompute; it is always the record of
something somebody did at a commit, which is the shape K-76 declines to repair one
artifact over.

**Fail-closed at every reading.** An absent record, a pin table this parse cannot
locate by its own heading and column names, a table with no rows, an index carrying
no gitlink at all, and a model window the counts group has not read are each one
finding that stops or narrows the comparison, because each of them would otherwise
leave this rule reporting that every pin of none agrees. The gitlink's id lives in
the index whether or not the submodule is checked out, which is why the index is the
instrument: most checkouts here have `upstream/` unpopulated, and this rule decides
exactly the same thing on one of those.

**The residues are declared and are held in both directions.** A commit id written
beside an upstream's name that is *not* that upstream's pin is exactly what a reader
would misread, so it is named here with what it actually is. The table asks for a
decision the way [marks.py](marks.py)'s kinds do, and an entry that suppresses
nothing goes the way a ruling nothing exercises does. It is keyed by the id and not
by the pin beside it, because what a residue declares is what that commit *is*, which
does not change with whichever name a sentence happens to put in front of it. The
alternative to declaring them is narrowing the shape until they fall out of it, and
that trade runs the wrong way: a token of seven or more hexadecimal digits is what an
abbreviated commit looks like, so any narrowing tight enough to exclude a decimal
figure would one day stop reading a pin whose own id took that shape, silently, where
a residue is loud and asks for a decision.

Historical measurements and a superproject's nested dependencies have narrower
residues, keyed by both file and exact id. Their meaning belongs to the recorded
reading, so the same id in another file remains a restatement to check. Each entry
carries that reading's reason and must still name a scanned site outside the pin
table. The current table is held against the index without either kind of exception.

**What this rule cannot attribute it does not decide.** An id is paired with the last
upstream *named on its own line*, so an id standing on a line that names none is read
by nothing here: the RTL delta's `Read at ...` sentence and its second table's
display-name cell are both such sites today. Attribution by nearness across lines is
the obvious alternative and is worse, that same table putting one upstream's row four
lines above another upstream's cell, so it would pair ids with the wrong pins rather
than leave them unpaired. Membership against the whole pin set was the other
candidate and is worse again: this repository writes many commits of other trees
beside its own, a branch head, an embedded revision, an emulator's own revision, and
holding every id-shaped token against the pins would demand a declaration for each of
them and grow one per completion note. So the residue is stated rather than closed.

**What this cannot decide is whether the terms at the pin were read correctly**, or
read at all. That is the same residue every group here declares: the id is checked
for agreement, and what somebody found when they opened the licence file at it is a
person's to know.

K-97 is this group's other kind of pin, and it is here rather than beside K-81 for one
reason and separated from it for another. **An upstream pins by version as well as by
commit**, and the licence record carries both kinds in one page: a submodule's terms are
read at an object id, and a development tool arrives from a distribution at a version
number, which is the edition its own row's terms were read at exactly as a commit is.
**What owns the two is not the same artifact.** A commit pin is owned by the git index,
which is a fact about the checkout; a version pin is owned by the constant the lane
actually enforces it at, `VERILATOR_PIN` in [vos/cli/rtl.py](../cli/rtl.py), which every
`rtl` loop compares an installed elaborator against and refuses on. So the record is a
restatement here where it is the owner there, and the direction of the reading flips
with it.

K-97 holds the record's development-tools row against that constant. Narrative
references link to this reviewed row or the command instead of repeating its version.
A pin stale in the record is the same defect K-81 exists for one column over: the
row's terms were read at an edition, and a reader installing what the row states runs
a lane the tools refuse. K-81 reads abbreviated object ids rather than version numbers;
K-67 holds the checker dependencies and does not cover this elaborator.

**The sites are enumerated in code and read fail-closed**, on K-67's and K-75's ground,
which is why this rule owes the floors group no member: a site whose pattern no longer
matches is a finding here, on the day it stops matching, rather than a set that has
quietly gone to zero one group later. The window is the enumeration and not a scan, and
what that leaves out is declared rather than discovered. The plan's own completion notes
state the elaborator's version beside an elaboration run at it, which is a measurement
recorded at a gate and not a restatement of the pin, exactly as K-81 leaves a commit
written beside what was done at it to the sentence that did it; the provisioner's Verilator
row and its test's pin loop compose the figure from the constant rather than restating it,
and the two places those same files do spell the version as a literal, `_number`'s
docstring and the case pinning what `_number` parses, are a sample of the elaborator's own
banner rather than a statement of the pin, fixed by the shape a dotted number takes inside
a greeting and still true the day the pin moves, so neither file is a site on either
count; and the *upstream's own* version of the same tool, the one the imported core's own flow
pins through nix, is a fact about that upstream rather than a pin taken here, so no rule
holds it and this one says so rather than reaching for it.

**Reported and never repaired**, on this group's own ground. The record's row states
the version beside the terms read at it, so a token substitution would claim a licence
review at a version that has not been reviewed.

K-115 is the same agreement one step further out, **for the code the hosted workflows
run**. A workflow's `uses:` line names another repository's code and the job token it
runs with, and the record's development-tools table carries one row per action
stating the release and the full commit its terms were read at. A tag moves under that
row without any file here changing, so the rule first holds each line to the one form
that cannot move, `owner/repo[/path]@<40 hex digits> # vX.Y.Z`, and then holds its
commit and release to the action's own row. Membership is total in both directions: a
line naming an action with no row runs code whose terms nobody read, and a row naming
an action no workflow runs is a review of nothing. The two workflow analyzers Host CI
runs are the same kind of pin and are held the same way, each row's release against
the owner the tool is installed from: [pyproject.toml](../../pyproject.toml)'s
`workflows` group for zizmor and [actionlint.sh](../../ci/actionlint.sh)'s version for
actionlint.

**The window is the git index's workflow directory**, every tracked `.yml` or `.yaml`
file under `.github/workflows/`, and each reading fails closed: no workflow, no
`uses:` line at all, a record without its development-tools heading or with no action
row under it, a row stating its reviewed revision other than exactly once, and an owner
this rule cannot read are each a finding rather than an agreement over nothing. That is
why it owes the floors group no member. What it does not decide is whether the commit
is the release the comment names; the row's reviewer read that, and zizmor's online
audits are the instrument that asks GitHub. **Reported and never repaired**, on K-97's
ground: moving a row's commit would claim a licence reading nobody took.

K-116 is the third kind: **a commit a tool consumes rather than a sentence restates.**
The width-transform registry binds the imported core's gitlink it was derived through,
and K-81 does not read that binding, the registry's `"pin"` naming no upstream on its
line. `rtl_width.stage` compares it with the populated imported core only when a guest
elaboration runs, which no hosted gate does, so a gitlink moved without re-deriving the
registry passed every hosted gate. This rule holds the recorded commit, whole, against
the index's gitlink, which every checkout carries populated or not. The device-register
package's recorded Mocha revision is the same kind of binding inside a generated
artifact, so K-88's row for that package holds it, and the row keeps the package out of
K-81's window. **The sites are enumerated in code and read fail-closed**: an artifact
missing from the index, a record its owner's own reader refuses, and a gitlink the
index does not carry are each a finding, so the rule owes the floors group no member.
**Reported and never repaired**: the repair re-derives the registry's source identities
from a checkout at the gitlink and is never a token substitution.
"""

import re
import tomllib
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from vos import corpus as corpus_mod
from vos import pins as pins_mod
from vos import rtl_width
from vos.checks import generated

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== pins: every upstream pin against the artifact that owns it ==="

# The version pin K-97 holds against the reviewed licence row. The constant is read
# out of the source as text rather than imported: a value taken by import would be
# the checker's own module rather than the one under the root it was pointed at.
VERILATOR_SRC = "tools/vos/cli/rtl.py"
_VERILATOR_SRC_RE = re.compile(r'(?m)^VERILATOR_PIN = "([^"\r\n]*)"')

# Each row is a site, the file carrying it, and the pattern that reads the figure out of
# it. Every pattern is anchored on the sentence's own words rather than on the number, so
# a reworded site is a finding and never a site that quietly stopped being read.
_VERILATOR_SITES: list[tuple[str, str, re.Pattern[str]]] = [
    ("development-tools row", pins_mod.RECORD,
     re.compile(r"(?m)^\| Verilator \|[^|]*\|[^|]*pinned at \*\*([^*]+)\*\*")),
]

# K-115's readings. The workflows are the index's own files under this directory; the
# record's rows are the development-tools table's, one per action named `owner/repo`.
WORKFLOWS = ".github/workflows/"
TOOLS_HEADING = "### Development tools, contained by use"
_USES_RE = re.compile(r"(?m)^[ \t]*(?:-[ \t]+)?uses:[ \t]*(.*?)[ \t]*$")
_PINNED_USE_RE = re.compile(
    r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:/[^@\s]+)?@([0-9a-f]{40}) # (v\d+\.\d+\.\d+)")
_ACTION_ROW_RE = re.compile(r"^\| ([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+) \|")
_REVIEWED_ACTION_RE = re.compile(r"reviewed (v\d+\.\d+\.\d+) revision `([0-9a-f]{40})`")

# The workflow analyzers: each row's tool cell, the owner that installs it, and how the
# owner states the release. The row states it as `reviewed **X** release`.
ANALYZER_PROJECT = "tools/pyproject.toml"
ANALYZER_SCRIPT = "tools/ci/actionlint.sh"
_ANALYZER_SCRIPT_RE = re.compile(r"(?m)^actionlint_version=([0-9][0-9A-Za-z.]*)$")
_REVIEWED_RELEASE_RE = re.compile(r"reviewed \*\*([^*\s]+)\*\* release")

# Every id this repository writes beside an upstream's name that is not that
# upstream's pin, with what it actually is. Each one is a reading trap on its face:
# a reader meeting it next to the project's name has every reason to take it for the
# pin, which is why it is named here rather than excluded by a shape.
#
# The first is the deliberate residue this rule declines to own. THIRD-PARTY.md's
# vendored table states the commit `model/` was taken from, and no gitlink owns it,
# because a vendored tree has none: the tree is tracked here whole and its baseline
# is a fact about how it was made rather than a pointer git resolves. That is the
# shape K-71 already declines to hold for the corpus manifest's edition, and the
# precedent is followed rather than a second owner invented for it. What the pin
# table records for `upstream/sail-riscv` is a different figure with a different
# meaning, the comparison reference the curation is read against, whose last
# semantic reconciliation the completion log records, and that one is held.
RESIDUE: dict[str, str] = {
    "8f91355e": "the commit the curated model was vendored from, which no gitlink "
                "owns because a vendored tree has none",
    "b748a82": "the older `sail-riscv` the CHERI oracle's own tree embeds, a fact "
               "about that upstream rather than a pin taken here",
    "11007678": "the numeral of SECOMP's Zenodo DOI, which is not an object id",
}

# The gitlinks of September 2026's native receipts, which record the index they ran
# against rather than restating the current pins.
_CAPTURED_GITLINKS: dict[str, str] = {
    "3243f93905c1de3504e910f76c07f96fef1394d7": "sail-riscv",
    "90cebef1411617fc3eedd359bdf00cb44b1c2439": "llvm-project",
    "5d37f8567667a3c699d2730574c35dfbe772dd67": "rupicola",
    "e8bfad6ab11618d1a0a13cb5f47265cc98605636": "katamaran",
    "b5973217f704923917e7761f73df7dfcb8d0c345": "mocha",
    "36a1dc5cb8c2b17d519bdb9ebf7fa37e591f6e43": "cva6-cheri",
    "24c6e2d8531e6a6d0a9e29bde2a109484099aec9": "axi-cheri-tagcontroller",
    "629146ef7b3b0d74216b5cc94504ded082a85067": "opentitan",
    "405c6d1d8220a18b2f9196141167a5875422dee4": "ibex",
    "930feb298af5bf7d9aa0baeaa21732ff84a2f066": "cheriot-ibex",
    "755c7eaa8f67328cbe1f1ab9080b70afb1772e84": "libjade",
    "78a34ba5cdb853ba601a292bcdd4a780e6ae9c64": "cheri-compressed-cap",
}
_CAPTURING_RECEIPTS: dict[str, str] = {
    "docs/assurance/sail-assistance-evidence/modular.json":
        "the historical modular Sail experiment",
    "docs/implementation/retained-evidence/root/logs/model-build-block-integration-20260919.json":
        "the retained block-integration model build receipt",
}

# These sites retain measured or external editions, or record identifiers that
# resemble object ids. They do not state this repository's current top-level pin.
SITE_RESIDUE: dict[tuple[str, str], str] = {
    **{(file, ident): f"the {name} gitlink captured by {receipt}"
       for file, receipt in _CAPTURING_RECEIPTS.items()
       for ident, name in _CAPTURED_GITLINKS.items()},
    ("THIRD-PARTY.md", "2078da43e25a4623cab2d0d60decddf709aaea28"):
        "the optional libclang 21.1.8 license reading, independent of the compiler-development gitlink",
    ("THIRD-PARTY.md", "8890da780108672e05cf87b6d119bf6a76113fbf"):
        "the current upstream model read for Sail assistance, not the local comparison gitlink",
    ("docs/assurance/sail-assistance.md", "8890da780108672e05cf87b6d119bf6a76113fbf"):
        "the external C++ generation recipe assessed for source versus binary modularity",
    ("THIRD-PARTY.md", "aa8cb46a9284b30b537bcd803cd163d5517f2e2e"):
        "the Modular SAIL paper fork whose license was read, not the upstream model gitlink",
    ("docs/assurance/sail-assistance.md", "aa8cb46a9284b30b537bcd803cd163d5517f2e2e"):
        "the paper's experimental extension-loader fork, assessed and deferred",
    ("docs/implementation/completion-log.md", "b5894db641d36616cdfce49352ec1d9833fcb411"):
        "the Rupicola edition recorded in the completed environment measurement",
    ("docs/implementation/completion-log.md", "beaf4499"):
        "the Sail reconciliation edition recorded at the completed M0 gate",
    ("docs/implementation/completion-log.md", "fd327e8c"):
        "the Katamaran edition recorded by the 2026-09-24 reference refresh",
    ("docs/implementation/completion-log.md", "78a34ba5"):
        "the cheri-compressed-cap edition M2.1 narrowed in the unpublished repository",
    ("docs/hardware/rtl-reparameterization-delta.md", "173646d5"):
        "the tag controller edition selected by the imported core's nested gitlink",
    ("rtl/synthesis-provenance.md", "173646d5"):
        "the tag controller edition selected by the imported core's nested gitlink",
    ("THIRD-PARTY.md", "5691ca0d"):
        "the Fiat-Crypto generator edition whose recorded build and licence reading "
        "the dependency measurements describe",
    ("docs/assurance/proof-reuse/crypto.md", "af03839247c545987c20e99342ab2bbfcd517863"):
        "the Fiat-Crypto dependency selected by the external verified-NTT artifact, "
        "not this repository's Fiat-Crypto gitlink",
    ("docs/assurance/proof-reuse/crypto.md", "0b07a19be15a23cb1c679e70f60d5b6e280caf7a"):
        "the EasyCrypt dependency selected by Formosa ML-KEM's shell.nix, "
        "not the libjade gitlink named earlier in that licence paragraph",
    ("docs/assurance/proof-reuse/languages.md", "14537282"):
        "the numeral of the archived SECOMP artifact's Zenodo record, "
        "not an object id",
}


# K-116's sites: what each binding is, the tracked artifact carrying it, the owner's
# own reader of the commit it records, and the gitlink that commit must be. A binding
# inside a generated artifact is held by that artifact's K-88 row instead.
BINDINGS: list[tuple[str, str, Callable[[str], str], str]] = [
    ("width-transform registry pin", rtl_width.REGISTRY, rtl_width.recorded_pin,
     rtl_width.CORE),
]


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)
    _pins(ctx)
    _version_pin(ctx)
    _workflow_pins(ctx)
    _bindings(ctx)
    rep.line()


def _bindings(ctx: Context) -> None:
    """K-116: every tool-consumed RTL binding names the commit the index carries."""
    findings: list[str] = []
    for label, file, reader, path in BINDINGS:
        if file not in ctx.corpus.indexed:
            findings.append(f"{file} is not in the repository, so its {label} cannot "
                            "be read")
            continue
        try:
            recorded = reader((ctx.root / file).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            findings.append(f"{file}'s {label} cannot be read: {error}")
            continue
        oid = ctx.corpus.gitlinks.get(path)
        if oid is None:
            findings.append(f"{file}'s {label} names {path}, which the index carries no "
                            "gitlink for")
        elif oid != recorded:
            findings.append(
                f"{file}'s {label} is {recorded[:12]} and the index carries {path} at "
                f"{oid[:12]}; regenerate it from a checkout at the gitlink, which "
                "re-derives what was read there and is never a token repair")
    ctx.rep.report("K-116", "tool-consumed RTL binding(s) that disagree with the gitlink "
                   "they were derived through:", findings,
                   f"the {len(BINDINGS)} tool-consumed RTL binding(s) record the commits "
                   "the index carries for their gitlinks")


def _version_pin(ctx: Context) -> None:
    """K-97: every site stating the elaborator's version states the one rtl.py fixes.

    Fail-closed at every reading, on K-67's and K-75's ground. The constant either
    parses in the form it is written in today or there is no owner to hold anything
    against; a document the corpus does not carry is a finding rather than a site
    silently dropped; and a site whose pattern no longer matches, or has come to match
    a sentence that no longer states the pin, is a finding rather than a pass over
    nothing. That is what makes this rule owe the floors group no member of its own.
    """
    rep = ctx.rep
    findings: list[str] = []

    try:
        source = (ctx.root / VERILATOR_SRC).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        source = ""
    stated = _VERILATOR_SRC_RE.search(source)
    if stated is None:
        findings.append(f"{VERILATOR_SRC} no longer states VERILATOR_PIN in a form this "
                        "rule reads, so there is no owner to hold the sites against")

    pin = stated.group(1) if stated else ""
    if stated is not None:
        for label, file, pattern in _VERILATOR_SITES:
            text = ctx.text(file)
            if not text:
                findings.append(f"{file} is not in the repository, so its {label} cannot "
                                "be read")
                continue
            hit = pattern.search(text)
            if hit is None:
                findings.append(f"{file} no longer states the elaborator's pin in its "
                                f"{label}, in a form this rule reads")
            elif hit.group(1) != pin:
                findings.append(
                    f"{file}'s {label} states {hit.group(1)}, {VERILATOR_SRC} pins "
                    f"{pin}; that row's terms were read at the version it states and "
                    "the lane refuses any other, so the edit is a person's")

    rep.report("K-97", "site(s) restating a version pin the lane's own constant does "
               "not fix:", findings,
               f"the reviewed elaborator row states {pin or 'no version'}, which "
               f"{VERILATOR_SRC} fixes and every rtl loop refuses another of")


def _tool_rows(text: str, findings: list[str]) -> dict[str, tuple[int, str]]:
    """The development-tools table's rows, keyed by their tool cell, with line numbers.

    Read from the record's own heading to the next heading, so a row of another
    table is never taken for this one's; a tool stated by two rows is a finding, the
    record then disagreeing with itself about which terms were read.
    """
    found = re.search(rf"(?m)^{re.escape(TOOLS_HEADING)}[^\S\r\n]*$", text)
    if found is None:
        findings.append(f"{pins_mod.RECORD} carries no `{TOOLS_HEADING}` heading, so no "
                        "reviewed row can be read")
        return {}
    base = text.count("\n", 0, found.start()) + 1
    rows: dict[str, tuple[int, str]] = {}
    for offset, raw in enumerate(text[found.start():].split("\n")[1:], start=1):
        line = raw.removesuffix("\r")
        if line.startswith("#"):
            break
        cells = line.split("|")
        if not line.startswith("| ") or len(cells) < 3:
            continue
        tool = cells[1].strip()
        if tool in rows:
            findings.append(f"{pins_mod.RECORD}:{base + offset} is a second row for {tool}, "
                            "and a pin stated twice is one the page can disagree with "
                            "itself about")
            continue
        rows[tool] = (base + offset, line)
    return rows


def _analyzer_releases(ctx: Context, findings: list[str]) -> list[tuple[str, str, str]]:
    """Each workflow analyzer, the owner installing it, and the release it installs."""
    found: list[tuple[str, str, str]] = []
    pins: list[str] = []
    fault = "the workflows group does not pin zizmor exactly once"
    try:
        groups = tomllib.loads((ctx.root / ANALYZER_PROJECT).read_text(encoding="utf-8"))[
            "dependency-groups"]["workflows"]
        pins = [item.partition("==")[2] for item in groups
                if isinstance(item, str) and item.partition("==")[0] == "zizmor"]
    except (OSError, UnicodeDecodeError, ValueError, TypeError, KeyError) as err:
        fault = str(err)
    if len(pins) == 1 and pins[0]:
        found.append(("zizmor", ANALYZER_PROJECT, pins[0]))
    else:
        findings.append(f"{ANALYZER_PROJECT} cannot supply the workflow analyzer's exact "
                        f"zizmor pin: {fault}")
    try:
        script = (ctx.root / ANALYZER_SCRIPT).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        script = ""
    stated = _ANALYZER_SCRIPT_RE.findall(script)
    if len(stated) == 1:
        found.append(("actionlint", ANALYZER_SCRIPT, stated[0]))
    else:
        findings.append(f"{ANALYZER_SCRIPT} does not state actionlint_version exactly once "
                        "in a form this rule reads, so the release Host CI runs is unread")
    return found


def _workflow_pins(ctx: Context) -> None:
    """K-115: every action a workflow runs is the commit and release its row reviewed.

    Fail-closed at every reading, on K-97's ground; see the module's account of K-115
    for what each missing reading would otherwise let pass.
    """
    rep = ctx.rep
    record = pins_mod.RECORD
    findings: list[str] = []
    text = ctx.text(record)
    if not text:
        findings.append(f"{record} is not in the repository, so no reviewed row can be read")
    rows = _tool_rows(text, findings) if text else {}

    # action -> (release, commit, where the row stands); an unreadable row keeps its
    # key with empty values, so the lines naming it are not also reported as rowless
    actions: dict[str, tuple[str, str, str]] = {}
    for tool, (line, row) in rows.items():
        if not _ACTION_ROW_RE.match(row):
            continue
        where = f"{record}:{line}"
        stated = _REVIEWED_ACTION_RE.findall(row)
        if len(stated) != 1:
            findings.append(f"{where} states {tool}'s reviewed release and revision "
                            f"{len(stated)} times; exactly one `reviewed vX.Y.Z revision "
                            "`<full commit>`` is read")
            actions[tool] = ("", "", where)
            continue
        actions[tool] = (stated[0][0], stated[0][1], where)
    if rows and not actions:
        findings.append(f"{record}'s development-tools table carries no action row, so the "
                        "workflows would be held against nothing")

    files = sorted(rel for rel in ctx.corpus.tracked
                   if rel.startswith(WORKFLOWS) and rel.endswith((".yml", ".yaml")))
    if not files:
        findings.append(f"the index carries no workflow under {WORKFLOWS}, so no action "
                        "reference is read")
    used: set[str] = set()
    references = 0
    for rel in files:
        try:
            source = (ctx.root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            findings.append(f"{rel} cannot be read as text, so its action references are "
                            "unread")
            continue
        for m in _USES_RE.finditer(source):
            references += 1
            number = source.count("\n", 0, m.start()) + 1
            where = f"{rel}:{number}"
            pinned = _PINNED_USE_RE.fullmatch(m.group(1))
            if pinned is None:
                findings.append(f"{where} uses `{m.group(1)}`, which is not "
                                "owner/repo[/path]@<full commit> # vX.Y.Z; a tag or branch "
                                "can move under the reviewed row")
                continue
            action, sha, version = pinned.groups()
            used.add(action)
            if action not in actions:
                findings.append(f"{where} runs {action}, which {record}'s development-tools "
                                "table has no row for, so nobody read the terms of the code "
                                "it runs")
                continue
            want_version, want_sha, row = actions[action]
            if want_sha and (sha, version) != (want_sha, want_version):
                findings.append(
                    f"{where} runs {action} at {sha[:12]} ({version}), {row} reviewed "
                    f"{want_sha[:12]} ({want_version}); the row's terms were read at the "
                    "revision it states, so the edit is a person's")
    if files and not references:
        findings.append(f"no workflow under {WORKFLOWS} states an action reference, so the "
                        "rows would be held against nothing")
    if references:
        findings += [f"{where} reviews {action}, which no workflow runs; a row reviewing "
                     "nothing is a licence record for no code"
                     for action, (_, _, where) in actions.items() if action not in used]

    for tool, owner, release in _analyzer_releases(ctx, findings):
        if tool not in rows:
            if rows:
                findings.append(f"{record}'s development-tools table has no {tool} row, and "
                                f"{owner} installs {release}")
            continue
        line, row = rows[tool]
        stated = _REVIEWED_RELEASE_RE.findall(row)
        if stated != [release]:
            findings.append(f"{record}:{line} states {tool}'s reviewed release as "
                            f"{', '.join(stated) or 'nothing'}, {owner} installs {release}; "
                            "the row's terms were read at the release it states")

    rep.report("K-115", "workflow action or analyzer pin(s) the reviewed record does not "
               "state:", findings,
               f"the {references} action references in {len(files)} workflows state the "
               f"commits and releases their {len(actions)} reviewed rows record, and the "
               "workflow analyzers' rows state the releases their owners install")


def _sources(ctx: Context) -> list[tuple[str, str, list[bool]]]:
    """Every file this rule reads, as its lines and which of them a fence displays.

    **The window is the git index**, because a pin is restated wherever somebody
    argues from one and a list of places to look would be a membership nobody
    maintains: the plan's completion notes, the RTL delta's provenance table, a Sail
    header, a build tree's name in `vos/env.py`. So the tool walks what git tracks
    rather than a set some sentence points it at, and the only way for a site to
    escape is for it to leave the repository.

    The tracked files arrive by three routes, and the routes are about *reading* them
    once rather than about which are in scope. A **document** comes from the corpus,
    which already holds its lines and the fence mask over them, so the mask is used
    rather than recomputed here. **`model/`** comes through the citation window the
    counts group already read, handed on rather than opened a second time, which is
    the duplication [vos/](..) exists to refuse. Everything else is read here, and
    carries no mask, a fence being a thing Markdown does and these files are not.

    That leaves two parts of the index unread and both are worth stating. `model/`
    *outside* the citation window is vendored upstream at its own revisions,
    `dependencies/` most of all, and a commit recorded there is somebody else's
    provenance rather than a pin taken here. Holding an upstream's own recorded commits
    against this repository's licence record is not a claim anyone should make, which is
    the ground `corpus.is_model_citation_path` already gives for the same boundary.

    The second is **the generated artifacts**, and the ground is this rule's own subject
    rather than a cost. What it holds is a *restatement*: a person naming an upstream and
    writing a commit beside it, which drifts because a person wrote it. A generated
    artifact restates nothing, its content being a function of its owners and held
    byte-for-byte by K-88, so an object-id-shaped token inside one is not a
    transcription and there is no edit for a finding to ask for. The bundle makes that
    concrete: it is one line of four megabytes carrying every Sail bit literal in the
    model, so `0b00000` reads as seven hex digits on a line that also names an upstream,
    and the rule reported thousands of restatements nobody wrote.

    A file that will not read as text is skipped rather than reported: what every
    tracked file is made of is the glyphs group's question, and pricing one
    unreadable file under both would report one defect twice.
    """
    window: list[tuple[str, str, list[bool]]] = [
        (doc.name, doc.raw, doc.fenced) for doc in ctx.corpus.docs]
    machine = generated.paths()

    # Narrowed here rather than trusted, which is what `Context.shared` being `Any`
    # asks of each reader: the counts group puts `(rel, text)` pairs there and this
    # is the sentence saying so.
    ported = cast("list[tuple[str, str]]", ctx.shared.get("citation_window", []))
    window += [(rel, text, []) for rel, text in ported]

    for rel in ctx.corpus.tracked:
        if rel in ctx.corpus or rel.startswith(corpus_mod.UNREAD_PREFIX):
            continue
        if rel in machine:
            continue
        try:
            text = (ctx.root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        window.append((rel, text, []))
    return window


def _pins(ctx: Context) -> None:
    """K-81: the record's pin table against the index, and every restatement against it."""
    rep, sh = ctx.rep, ctx.shared
    label = "upstream pin(s) that disagree with the gitlink that owns them:"
    record = pins_mod.RECORD

    # Every gitlink and not only the ones under `upstream/`. The record's own section
    # says *these are gitlink entries*, so the set it accounts for is the index's and
    # not a subtree of it, and a submodule added anywhere else would otherwise be an
    # upstream with no terms on the page and nothing to say so.
    gitlinks = ctx.corpus.gitlinks
    read = pins_mod.read_record(ctx.text(record))

    if read.fault is not None or not gitlinks:
        sh["record_pins"] = 0
        sh["pin_restatements"] = 0
        rep.report("K-81", label, [
            read.fault,
            f"the git index carries no gitlink at all, so {record}'s pin table would "
            "be held against nothing" if not gitlinks else None,
        ])
        return

    findings: list[str] = []
    settled: dict[str, tuple[pins_mod.Pin, str]] = {}
    seen: set[str] = set()
    if "citation_window" not in sh:
        findings.append("the counts group has not read the model window, so the "
                        "commits the ported headers state are unread here")
    for pin in read.rows:
        where = f"{record}:{pin.line}"
        if pin.path and pin.path in seen:
            findings.append(f"{where} is a second row for {pin.path}, and a pin stated "
                            "twice is a pin the page can disagree with itself about")
            continue
        seen.add(pin.path)
        if not pin.path:
            findings.append(f"{where} names no submodule in a form this rule reads, "
                            "so the row pins nothing")
        elif pin.path not in gitlinks:
            findings.append(f"{where} pins {pin.path}, which the index carries no "
                            "gitlink for")
        elif not pin.short:
            findings.append(f"{where} pins {pin.path} and states no commit id, so the "
                            "edition its terms were read at is not recorded")
        elif not gitlinks[pin.path].startswith(pin.short):
            findings.append(
                f"{where} pins {pin.path} at {pin.short} and the index carries it at "
                f"{gitlinks[pin.path][:12]}; the terms on that row were read at the "
                "commit the row states, so the repair is a licence read and not a "
                "transcription")
        else:
            settled[pin.path] = (pin, gitlinks[pin.path])

    findings += [f"the index carries a gitlink at {path} and {record}'s pin table has "
                 "no row for it, so an upstream this repository pins has no terms on "
                 "the page" for path in sorted(set(gitlinks) - {p.path for p in read.rows})]

    held, used, site_used = _restatements(ctx, read.rows, settled, findings)

    findings += [f"{ident} is declared here as {why}, and no site states it any more; "
                 "a residue that suppresses nothing is a carve-out nobody audits"
                 for ident, why in RESIDUE.items() if ident not in used]
    for (file, ident), why in SITE_RESIDUE.items():
        if not why.strip():
            findings.append(f"{file} at {ident} has a scoped residue with no reason")
        elif (file, ident) not in site_used:
            findings.append(
                f"{file} at {ident} is declared here as {why}, and no site outside "
                "the pin table states it any more; a scoped residue that suppresses "
                "nothing is a carve-out nobody audits")

    sh["record_pins"] = len(read.rows)
    sh["pin_restatements"] = held
    rep.report("K-81", label, findings,
               f"the {len(read.rows)} upstream pins {record} records are the commits "
               f"the index carries, and the {held} sites restating one state the same "
               "id")


def _restatements(ctx: Context, rows: list[pins_mod.Pin],
                  settled: dict[str, tuple[pins_mod.Pin, str]],
                  findings: list[str]) -> tuple[int, set[str], set[tuple[str, str]]]:
    """Every site that restates a pin, held against the record's row.

    The record's own table rows are skipped, because holding them here would price
    one drifted row as two findings: they are the first hop's subject and this is the
    second's. A row's other statements of its pin in the page's prose are not
    skipped, being restatements like any other.

    A site is held against the whole object id and reported against the record's own
    eight digits, and those are two different lengths on purpose. A site may
    abbreviate the same commit shorter or longer than the record does and be right
    either way, which only the full id can decide; what the finding quotes back is
    the spelling the record uses, because the record is what these sites restate.

    A fenced line is skipped where the file has a fence to speak of, which is the
    corpus's own rule and the corpus's own mask: an id inside one is displayed as
    text and names nothing.
    """
    named = pins_mod.spellings(rows)
    table = {(pins_mod.RECORD, pin.line) for pin in rows}
    used: set[str] = set()
    site_used: set[tuple[str, str]] = set()
    held = 0

    for file, text, fenced in _sources(ctx):
        for site in pins_mod.scan_text(file, text, named):
            if fenced and fenced[site.index]:
                continue
            if site.ident in RESIDUE:
                used.add(site.ident)
                continue
            if (file, site.line) in table:
                continue
            if (file, site.ident) in SITE_RESIDUE:
                site_used.add((file, site.ident))
                continue
            if site.pin.path not in settled:
                continue
            held += 1
            pin, oid = settled[site.pin.path]
            if oid.startswith(site.ident):
                continue
            findings.append(
                f"{site.where()} states the {site.pin.path} pin as {site.ident}, "
                f"{pins_mod.RECORD} records {pin.short}; the sentence around it says "
                "what was done at that commit, so the edit is a person's")
    return held, used, site_used
