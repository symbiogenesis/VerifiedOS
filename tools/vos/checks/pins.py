# SPDX-License-Identifier: Apache-2.0
"""Check upstream gitlink pins, tool-consumed RTL bindings, and development-tool reviews (`K-81`, `K-116`, `K-118`).

- `K-81` checks upstream pins in two hops (via [vos/pins.py](../pins.py)):
  1. The pin table in [THIRD-PARTY.md](../../../THIRD-PARTY.md) must match the Git
     index's `160000` gitlinks in both directions.
  2. Every commit-ID restatement on a line naming an upstream across tracked files
     (excluding `model/` outside the citation window and generated artifacts) must match
     that upstream's pin in [THIRD-PARTY.md](../../../THIRD-PARTY.md) or be declared in
     `RESIDUE` or `SITE_RESIDUE` (which are also checked for liveness).
  Neither hop is auto-repaired by `--fix` because advancing a pin requires a license
  review at the new commit.
- `K-116` checks that tool-consumed RTL source bindings (`BINDINGS`, such as
  [tools/rtl-width-transforms.json](../../rtl-width-transforms.json)) record the exact commit
  that the Git index carries for their imported core gitlink.
- `K-118` checks development-tool license reviews and their generated view in
  [THIRD-PARTY.md](../../../THIRD-PARTY.md) against [tools/development-tools.json](../../development-tools.json)
  and the repository's lockfiles and workflows (via [vos/devtools.py](../devtools.py)),
  regenerating the view under `--fix` when the reviewed identities already match.
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

if TYPE_CHECKING:
    from . import Context

HEADING = "=== pins: every upstream pin against the artifact that owns it ==="

# Commit IDs appearing alongside an upstream's name that are not that upstream's gitlink pin.
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
    **{(f"docs/implementation/retained-evidence/submodules-{date}/hardware.json", ident):
       f"the {name} edition retained by the dated 2026-10-31 source reading or "
       "used as the preceding side of the 2026-11-03 comparison, not the current gitlink"
       for date in ("20261031", "20261103")
       for ident, name in {
           "6c85882513bb12711cdcbea69a1a7eb065a37f1a": "Mocha",
           "41049e9deb40e0602cd5272c40398be380ae2637": "OpenTitan",
           "cafaeae02c014456a99247b68788d31b7516a252": "CHERIoT-Ibex",
       }.items()},
    **{(f"docs/implementation/retained-evidence/submodules-{date}/model.json",
        "80985afd8164c31902181d41885e06e2df6dfe6d"):
       "the Katamaran edition retained by the dated 2026-10-31 source reading or "
       "used as the preceding side of the 2026-11-03 comparison, not the current gitlink"
       for date in ("20261031", "20261103")},
    ("docs/implementation/retained-evidence/submodules-20261103/llvm-project.json",
     "8b066788f709ce1815a2b1ffe01639e98487bb65"):
        "the preceding LLVM edition in the exact 2026-11-03 comparison URL, "
        "not the selected reference gitlink",
    ("docs/implementation/retained-evidence/submodules-20261103/s2n-bignum.json",
     "573ea98f6a2eea3172f6146f83b86b9e526ce2dd"):
        "the preceding s2n-bignum edition in the exact 2026-11-03 comparison URL, "
        "not the selected reference gitlink",
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
    """Yield `(rel_path, text, fence_mask)` for every tracked file in `K-81`'s scan window.

    Reads Markdown documents from `ctx.corpus`, curated `model/` files from
    `ctx.shared["citation_window"]`, and remaining tracked text/gzip-evidence files
    from disk (excluding `model/` outside the citation window and generated artifacts).
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
                except OSError, EOFError, ValueError, zlib.error:
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
        except OSError, UnicodeDecodeError, EOFError, ValueError, zlib.error:
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
