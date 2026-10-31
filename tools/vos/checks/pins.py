# SPDX-License-Identifier: Apache-2.0
"""pins: every upstream pin this repository states, against the artifact that owns it.

An upstream arrives here as a gitlink: the index carries a path and a commit id and
none of the code, and [THIRD-PARTY.md](../../../THIRD-PARTY.md) carries the licence
record over those pins, one row per submodule, each stating the short id its terms
were read at. The row is hand-copied from the gitlink and the copy had no owner.

**That copy is the one derived fact in this repository whose defect cannot be
repaired downstream.** [AGENTS.md](../../../AGENTS.md) and [the plan's
§12](../../../PLAN.md#12-build-order-milestones-and-execution-state)
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

K-116 holds **a commit a tool consumes rather than a sentence restates.**
The width-transform registry binds the imported core's gitlink it was derived through,
and K-81 does not read that binding, the registry's `"pin"` naming no upstream on its
line. `rtl_width.stage` compares it with the populated imported core only when a guest
elaboration runs, which no hosted gate does, so without this rule a gitlink moved
without re-deriving the registry passes every hosted gate. This rule holds the recorded
commit, whole, against the index's gitlink, which every checkout carries populated or
not. The device-register package's recorded Mocha revision is the same kind of binding
inside a generated artifact, so K-88's row for that package holds it, and the row keeps
the package out of K-81's window.
**The sites are enumerated in code and read fail-closed**: an artifact missing from the
index, a record its owner's own reader refuses, and a gitlink the index does not carry
are each a finding, so the rule owes the floors group no member.
**Reported and never repaired**: the repair re-derives the registry's source identities
from a checkout at the gitlink and is never a token substitution.

K-118 binds structured authored licence-review identities to the dependency artifacts
that own installed releases. The development-tools section is generated from those
identities and its authored Markdown template. A changed dependency refuses before
repair; regeneration can reproduce an existing reading but never advance it. The
shared library also retains the hook-repository and pip-constraint censuses, so new
code installed by those routes still requires a review record. Structured action
reviews generate pinned licence URLs and are held against every parsed workflow
reference in both directions. Licence evidence and all prose outside the generated
section retain their own owners.

"""

import zlib
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, cast

from vos import corpus as corpus_mod
from vos import devtools, literalsearch, retained, rtl_width
from vos import pins as pins_mod
from vos.checks import generated
from vos.checks.interims import archive_needles
from vos.report import apart

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== pins: every upstream pin against the artifact that owns it ==="

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
}

# The gitlinks of retained native receipts, which record the index they ran
# against rather than restating the current pins.
_CAPTURED_GITLINKS: dict[str, str] = {
    "5c20b839e556b78c0ee7f1ce5b28fb00d0e69d78": "SECOMP",
    "bb07488dac8322fc4a653a01d049e16fa05c9065": "sail-cheri-riscv",
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
    "504c2987452f87fe44bce9b9f12e19d6e051761f": "hacl-star",
    "e6946985c9165b3270eae457c0fae887cd7b7b76": "fiat-crypto",
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
    **{("docs/assurance/proof-reuse/systems.md", ident): reason
       for ident, reason in {
           "3fe5d0a957a95c27cff204e729a5e96a3e3217ad":
               "the general Rocq Perennial framework edition read by SYS-PERENNIAL, "
               "not the selected PoWER correspondence source gitlink",
           "f97c83addc2f66f8d58004321f0b1f055c046c30":
               "the surveyed default Lean lineage lacking crash logic, "
               "not the selected Rocq PoWER source gitlink",
           "3e3e0a484d61d0a15b578f5d5887ead84f145d71":
               "the surveyed later Rocq master edition, "
               "not the selected PoWER correspondence source gitlink",
       }.items()},
    ("docs/assurance/proof-reuse/parsers.md", "aef82ed"):
        "the commit suffix of vasn's selected Verus toolchain release, "
        "not the vasn source gitlink",
    **{("docs/implementation/upstream-merged-review.md", ident): reason
       for ident, reason in {
           "cd3f185e3a40cd402632d78a2bc213d62ae6f753":
               "the original vector-length change reviewed for adoption, "
               "not the later sail-riscv reference gitlink",
           "94139d1b7413cdbe517a80dcdb8b365b2189af0e":
               "the upstream segment-store correction compared with the curated model, "
               "not the current sail-riscv reference gitlink",
           "35d5ebc383ac20ad0b918a5fd30db11047ca2805":
               "the Mocha AXI observation change, not the later selected Mocha gitlink",
           "7a654caed0e1121e9ad405038ea40f9a0840a49d":
               "the Mocha AXI ordering correction, not the later selected Mocha gitlink",
           "4f8ce828fcacd6f392cb4f9be9046d46ce4bec07":
               "the concurrency-interface v2 candidate reviewed for a future port, "
               "not the current sail-riscv reference gitlink",
           "3229c62ba0c424a0f6346d622907238c94885bb2":
               "the Katamaran universal-contract method change, "
               "not the later selected reference gitlink",
           "56fede178c18d18ea3cda56c33217f8c718157d0":
               "the Rust pointer-simplification correction proposed for comparison, "
               "not the later selected compiler-reference gitlink",
       }.items()},
    **{(file, "8b953fe8f17bb4553792c63665d368dc7f6bbd26"):
       "the merged Katamaran PR 73 edition used for its notation comparison, "
       "not the later selected reference gitlink"
       for file in (
           "PLAN.md",
           "docs/implementation/upstream-prs.md",
           "docs/implementation/upstream-prs/snapshot.json",
       )},
    **{("docs/implementation/retained-evidence/submodules-20261031/hardware.json", ident):
       f"the previous {name} edition in its exact upstream comparison URL, "
       "not the newly selected reference gitlink"
       for ident, name in {
           "f9bacf5d6a9d91b1dc00cfd2228c88fc17eae93c": "Mocha",
           "c974f0c64e73c97e6b61bae1ea67a25a62ed1e5f": "tag-controller",
           "10738f384903ad7f7405a452ad41d6b8da23d2bb": "OpenTitan",
           "1b29dae8866e6c0f0a3cd9dead53a77b4f45e357": "Ibex",
           "531ca2ec439fe3fa89bd6f60ae8f256bc0b9b241": "CHERIoT-Ibex",
       }.items()},
    ("docs/implementation/retained-evidence/submodules-20261031/model.json",
     "c3b7ecff27c1a6e8ed058d5aca362df1e2f63311"):
        "the rejected Perennial branch tip lacking the selected PoWER interface, "
        "not the retained source gitlink",
    **{(file, ident):
       f"the Katamaran PR's GitHub Actions {kind} identifier, not a commit"
       for file in (
           "docs/implementation/upstream-prs.md",
           "docs/implementation/upstream-prs/snapshot.json",
       ) for ident, kind in {
           "39373527048": "workflow run",
           "119294205432": "matrix.rocq job",
       }.items()},
    **{(file, ident):
       f"the Fiat-Crypto PR's GitHub Actions {kind} identifier, not a commit"
       for file in (
           "docs/implementation/upstream-prs.md",
           "docs/implementation/upstream-prs/snapshot.json",
       ) for kind, identifiers in (
           ("workflow run", (
               "33583775967", "33583775999", "33583776028", "33583776030", "33583776031",
               "33583776070", "33583780869", "33583780870", "33583780876", "33583780877",
               "33583780879", "33583780885", "33583780890", "33583780901", "33583780916",
               "33583780920", "33583780921", "33583780934", "33583780940", "33583781018",
           )),
           ("job", (
               "100103482330", "100103482482", "100103482501", "100103482593",
               "100103482622", "100103482640", "100103482723", "100103496234",
               "100103496329", "100103496336", "100103496471", "100103496480",
               "100103496536", "100103496537", "100103496552", "100103496623",
               "100103496690", "100103496691", "100103496705", "100103496804",
               "100103496833", "100103496939", "100103496999", "100103497391",
               "100354425061", "100365136950", "100365136962", "100365136998",
               "100377669460", "100377669549", "100377669986", "100377670093",
               "100377670098", "100377670138", "100377670146", "100377670180",
               "100405711986", "100405712013", "100414085100", "100414085202",
               "100424424408", "100424424433", "100425040773", "100522360413",
               "100522360432", "100522360832", "100522360946", "100598621919",
               "100604260784", "100606509673", "100623585699", "100626643696",
               "100672625359",
           )),
       ) for ident in identifiers},
    **{(file, ident):
       "the nested machine_utils edition inspected for first-party terms, "
       "not a parent proof development's top-level gitlink"
       for file in (
           "docs/implementation/upstream-prs.md",
           "docs/implementation/upstream-prs/snapshot.json",
       ) for ident in (
           "68081522", "6808152216bcee011c6e6cdcf3500ff8547104f1",
           "56d2f2b6d9373f1349f8689455715f168dd86ece",
           "3040e1bc4158020a69e96a9a2dcf1b6b30503acd",
       )},
    **{("docs/hardware/cheri-version-matrix.md", ident): reason
       for oid, reason in {
           "48e02787212371dc1bf28af3ee713d555de9866a":
               "the Alliance fork's main comparison, not the riscv/sail-riscv gitlink",
           "7726ab7586de0ef4a4a23e2d37fd4310fd43bedd":
               "the Alliance fork's codasip comparison branch",
           "937b306b8b1288d0dd16e04be85ffa29ceb0c6d3":
               "the Alliance QEMU main comparison, not the CTSRD-CHERI oracle gitlink",
           "d847ab5e94692d7edd2402bb0523f4a592396fc9":
               "the Cambridge 0.9.9-upgrade comparison, not the selected master oracle",
           "157a45a70f9d3ceea4b25e07d0777240ade56f38":
               "the Cambridge 0.9.8.2-upgrade comparison branch",
           "e66c89496aaf422c5caa62fba79122a359e642bf":
               "the Cambridge pdr32 comparison branch",
           "5b12002f14900341fe79fa3fbb00a4b45505d187":
               "the TestRIG RVY-support comparison, not its selected master gitlink",
       }.items() for ident in (oid[:8], oid)},
    ("docs/hardware/cheri-version-matrix.md", "96c96126f48fd7e73bb3aedffd35a70547dfaf49"):
        "the archived Alliance standalone model, not the Cambridge oracle gitlink",
    **{(file, "47bc545117348495f71aad9e20d5c9bb9ed3a757"):
       "the historical Katamaran source measured by the recorded Q35 dependency trial"
       for file in (
           "docs/assurance/machine-logic-breakdown.md",
           "docs/assurance/machine-logic-dependency-trial.md",
           "tools/machine-logic-trial/trial.py",
       )},
    ("docs/implementation/completion-log.md", "5c20b839"):
        "the historical SECOMP source and licence reading recorded at M1.1",
    ("docs/implementation/completion-log.md", "ae79548c0fb30c708ec3f870d4b462611ed87b4f"):
        "the OpenTitan source reading recorded at the completed Q41 contract landing",
    ("docs/implementation/retained-evidence/q39/shelving-triage-20261012/release-triage.json",
     "5c20b839e556b78c0ee7f1ce5b28fb00d0e69d78"):
        "the immutable SECOMP comparison base used in the historical Q39 triage",
    **{(file, "bb07488d"):
       "the unchanged historical CHERI transplant header in Q35p's model-owner reproducer, "
       "not a statement of the current comparison gitlink"
       for file in (
           "docs/implementation/retained-evidence/close3-q35p-20261013/bindings.sail.txt",
           "docs/implementation/retained-evidence/q35p-tag-outcomes-20261023/bindings.sail.txt",
       )},
    **{(file, "bb07488d"): "the historical CHERI source transplanted into the curated model"
       for file in (
           "model/model/core/addr_checks.sail",
           "model/model/core/cap_common.sail",
           "model/model/core/cap_causes.sail",
           "model/model/core/cap_regs.sail",
           "model/model/core/cap_format.sail",
           "model/model/core/mem_metadata.sail",
           "model/model/core/reg_type.sail",
           "model/model/extensions/CHERI/cheri_mem.sail",
           "model/model/extensions/CHERI/cheri_insts.sail",
           "model/model/postlude/cap_traps.sail",
       )},
    ("docs/implementation/completion-log.md", "bb07488d"):
        "the CHERI oracle edition recorded at the completed M0 reconciliation",
    **{(file, ident): f"the {name} gitlink captured by {receipt}"
       for file, receipt in _CAPTURING_RECEIPTS.items()
       for ident, name in _CAPTURED_GITLINKS.items()},
    ("THIRD-PARTY.md", "2078da43e25a4623cab2d0d60decddf709aaea28"):
        "the optional libclang 21.1.8 license reading, independent of the compiler-development gitlink",
    ("THIRD-PARTY.md", "8890da780108672e05cf87b6d119bf6a76113fbf"):
        "the historical upstream model reading for Sail assistance, not the local comparison gitlink",
    ("docs/assurance/sail-assistance.md", "8890da780108672e05cf87b6d119bf6a76113fbf"):
        "the external C++ generation recipe assessed for source versus binary modularity",
    ("THIRD-PARTY.md", "aa8cb46a9284b30b537bcd803cd163d5517f2e2e"):
        "the Modular SAIL paper fork whose license was read, not the upstream model gitlink",
    ("docs/assurance/sail-assistance.md", "aa8cb46a9284b30b537bcd803cd163d5517f2e2e"):
        "the paper's experimental extension-loader fork, assessed and deferred",
    ("docs/implementation/completion-log.md", "beaf4499"):
        "the Sail reconciliation edition recorded at the completed M0 gate",
    ("docs/hardware/rtl-reparameterization-delta.md", "173646d5"):
        "the tag controller edition selected by the imported core's nested gitlink",
    ("rtl/synthesis-provenance.md", "173646d5"):
        "the tag controller edition selected by the imported core's nested gitlink",
    ("docs/assurance/proof-reuse/crypto.md", "e6946985"):
        "the Fiat-Crypto source and licence edition read by the dated reuse survey",
    ("docs/assurance/proof-reuse/crypto.md", "af03839247c545987c20e99342ab2bbfcd517863"):
        "the Fiat-Crypto dependency selected by the external verified-NTT artifact, "
        "not this repository's Fiat-Crypto gitlink",
    ("docs/assurance/proof-reuse/crypto.md", "0b07a19be15a23cb1c679e70f60d5b6e280caf7a"):
        "the EasyCrypt dependency selected by Formosa ML-KEM's shell.nix, "
        "not the libjade gitlink named earlier in that licence paragraph",
    ("docs/assurance/proof-reuse/languages.md", "14537282"):
        "the numeral of the archived SECOMP artifact's Zenodo record, "
        "not an object id",
    ("THIRD-PARTY.md", "675963fc"):
        "the LLVM dependency selected by CHERIoT Rust's own gitlink, "
        "not the independent upstream LLVM tooling pin",
    ("docs/assurance/proof-reuse/languages.md", "675963fce3ae380774038a7e001ad33f63c8dcdd"):
        "the LLVM dependency selected by the source-qualified CHERIoT Rust fork, "
        "not the independent upstream LLVM tooling pin",
    ("THIRD-PARTY.md", "36676697"):
        "the historical Fiat-Crypto edition selected by the GarageDoor artifact, "
        "not the current field-emission gitlink",
    ("THIRD-PARTY.md", "36676697ca59b0b3d8bcc477dac1eacda89e921c"):
        "the historical Fiat-Crypto edition whose GarageDoor source and terms were read",
    ("docs/assurance/proof-reuse/systems.md", "36676697ca59b0b3d8bcc477dac1eacda89e921c"):
        "the GarageDoor artifact's historical Fiat-Crypto source and theorem edition",
    ("docs/background/architectural-alternatives.md", "36676697"):
        "the GarageDoor artifact's historical Fiat-Crypto edition used as a recipe reference",
    ("docs/assurance/proof-reuse/crypto.md", "f854fc6a2d7f88559df37796f6c498c5f96b66d9"):
        "the inspected AUCurves superproject edition in its Libjade bridge URL, "
        "not the separately maintained libjade gitlink",
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
    _dev_tools(ctx)
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
            stated, carried = apart(recorded, oid)
            findings.append(
                f"{file}'s {label} is {stated} and the index carries {path} at "
                f"{carried}; regenerate it from a checkout at the gitlink, which "
                "re-derives what was read there and is never a token repair")
    ctx.rep.report("K-116", "tool-consumed RTL binding(s) that disagree with the gitlink "
                   "they were derived through:", findings,
                   f"the {len(BINDINGS)} tool-consumed RTL binding(s) record the commits "
                   "the index carries for their gitlinks")


def _dev_tools(ctx: Context) -> None:
    """K-118: installed editions match authored reviews and their generated view."""
    text = ctx.text(devtools.RECORD)
    expected, findings = devtools.inspect(ctx.root, ctx.corpus.indexed, text)
    if expected is not None and expected != text:
        if ctx.fix and not findings:
            ctx.fixed[devtools.RECORD] = expected
            ctx.rep.line(f"fixed: {devtools.RECORD} generated development-tool view")
        else:
            findings.append(f"{devtools.RECORD}'s development-tool view is stale; "
                            f"regenerate from {devtools.DATA} without changing reviewed identities")
    ctx.rep.report("K-118", "unreadable or stale development-tool review(s):", findings,
                   "dependency owners agree with authored licence reviews and their generated view")


def _sources(ctx: Context, named: list[tuple[str, str, pins_mod.Pin]]) -> Iterator[tuple[str, str, list[bool]]]:
    """Indexed source and exact pin-candidate lines, with their fence masks.

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
    for doc in ctx.corpus.docs:
        yield doc.name, doc.raw, doc.fenced
    machine = generated.paths()

    # Narrowed here rather than trusted, which is what `Context.shared` being `Any`
    # asks of each reader: the counts group puts `(rel, text)` pairs there and this
    # is the sentence saying so.
    ported = cast("list[tuple[str, str]]", ctx.shared.get("citation_window", []))
    for rel, text in ported:
        yield rel, text, []

    for rel in ctx.corpus.tracked:
        if rel in ctx.corpus or rel.startswith(corpus_mod.UNREAD_PREFIX):
            continue
        if rel in machine:
            continue
        try:
            if rel.startswith(corpus_mod.COMPRESSED_EVIDENCE) and rel.endswith(".gz"):
                # Static parser inputs, not a decision from the later rule group.
                # Sharing them keeps the archive's candidate facts in one pass.
                blob = (ctx.root / rel).read_bytes()
                cache = cast(retained.Cache, ctx.shared.setdefault("retained_scan", retained.Cache()))
                try:
                    sensitive, folded = archive_needles()
                    facts = cache.scan(rel, blob, tuple(needle for needle, _, _ in named),
                                       sensitive, folded)
                except (OSError, EOFError, ValueError, zlib.error):
                    # The legacy reader owns exact malformed-gzip and text behavior.
                    # Failed or unsupported prescans are never cached as absences.
                    pass
                else:
                    if not facts.pin_name:
                        continue
                    if facts.pin_text is not None:
                        yield rel, facts.pin_text, []
                        continue
                text = corpus_mod.gzip_contents(blob).decode("utf-8")
            else:
                text = corpus_mod.scan_bytes(ctx.root, rel).decode("utf-8")
            # Preserve read_text's universal-newline behavior for these files,
            # including retained text now stored as lossless gzip evidence.
            text = text.replace("\r\n", "\n").replace("\r", "\n")
        except (OSError, UnicodeDecodeError, EOFError, ValueError, zlib.error):
            continue
        lowered = text.lower()
        candidate = any(needle in lowered for needle, _, _ in named)
        del lowered
        if not candidate:
            continue
        yield rel, text, []


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
            # The row is quoted whole, as the record spells it, and the gitlink at
            # twelve digits or as far as the two must run to differ.
            _, carried = apart(pin.short, gitlinks[pin.path])
            findings.append(
                f"{where} pins {pin.path} at {pin.short} and the index carries it at "
                f"{carried}; the terms on that row were read at the "
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
    try:
        matcher = literalsearch.compile_names(tuple(needle for needle, _, _ in named))
    except literalsearch.LegacyRequiredError:
        matcher = None
    table = {(pins_mod.RECORD, pin.line) for pin in rows}
    used: set[str] = set()
    site_used: set[tuple[str, str]] = set()
    held = 0

    for file, text, fenced in _sources(ctx, named):
        # scan_text proposes name-bearing line regions before applying the exact
        # attribution grammar; no whole-file id scan is needed for absent names.
        for site in pins_mod.scan_text(file, text, named, matcher=matcher):
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
