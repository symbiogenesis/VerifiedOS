# SPDX-License-Identifier: Apache-2.0
"""K-114 over fixture trees: the consumer lists' two forms and every way they can part.

The live tree exercises the rule's clean path on every `check.py` run, and the selftest
seeds the one defect it exists for, a premise nothing accounts for. What only a fixture
can pin is the rest of the closure: the non-empty list form read and resolved, a
declaration that classifies nothing, a listed consumer citing nothing of its interim,
the governing entry missing or unreadable, and where a lineage name starts and stops,
escaped and unescaped `F*` included.

The fixtures name the real lineages because the lineage names are the rule's subject.
This directory is one of the rule's declared exclusions, so none of them is a citation
the live run reads.
"""

from pathlib import Path

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos.checks import Context, interims
from vos.register import REGISTER, read_artifacts, read_register
from vos.report import Reporter

FSTAR, EASYCRYPT = interims.FSTAR, interims.EASYCRYPT
GOVERNED = (REGISTER, interims.GOVERNING)

_BOOKS = ("· Accept: the two entries (F\\*/Z3 for libcrux/HACL\\*, EasyCrypt's Why3/SMT) "
          "each carry a destination and a consumer list, held here. ")
_EMPTY = _BOOKS + "Both consumer lists are empty."
_LISTED = (_BOOKS + "F\\*/Z3's consumers are M3.4x and `kernel/src/mlkem.c`; EasyCrypt's "
           "consumer list is empty.")

_PLAN = ("# Plan\n\n### M3 · Boot chain\n\n"
         "* [ ] **M3.4x · Import a post-quantum primitive** · 2 h, range 1–3 · I\n"
         "  * The implementation is authored against the standard.\n")
_PLAN_RIDING = _PLAN.replace("authored against the standard",
                             "imported, and its correctness rests on HACL\\*'s proof")
_LOG = "# Log\n\n## M3 · Boot chain\n\n### M3.4a · The licence reads\n\n  * Read.\n"
_RECORD = "# Third-Party Components\n\n## Pinned as submodules\n\nNone.\n"
_MLKEM = "/* Hacl_ ML-KEM arithmetic, whose correctness rides F* and Z3. */\nint x;\n"

_HELD_HERE = "each carry a destination and a consumer list, held here"
_DECLARED = {GOVERNED: interims.NonPremise((FSTAR, EASYCRYPT), "the governing rule",
                                           (_HELD_HERE,))}

_MLDSA = "proofs/campaigns/mldsa-reference.md"
_CORE = "4. Verified crypto core (Coq)"
_PREMISE = ("Its decapsulation rests on HACL\\*'s verified ML-KEM, whose F\\* proof it "
            "takes as its premise.")


def _register(accept: str | None) -> str:
    head = "# Register\n\n## §5\n\n"
    if accept is None:
        return head + "**R-05-021** IS: A verified compiler is transport.\n· Trace: CJ-T\n"
    return (head + "**R-05-022** MUST: Every interim non-Coq anchor carries a destination.\n"
            + (accept + "\n" if accept else "") + "· Trace: CJ-T\n")


def _decide(files: dict[str, str], accept: str | None = _EMPTY,
            declared: dict[tuple[str, str], interims.NonPremise] | None = None,
            excluded: dict[str, str] | None = None,
            snapshots: bool = False) -> tuple[list[str], str]:
    tree = {REGISTER: _register(accept), interims.PLAN: _PLAN, interims.LOG: _LOG,
            interims.RECORD: _RECORD, **files}
    with sandbox_tree(tree) as root:
        ctx = _context(root)
        return interims.decide(ctx, excluded or {},
                               _DECLARED if declared is None else declared, snapshots)


def _context(root: Path) -> Context:
    corpus = corpus_mod.load(root)
    return Context(root=root, corpus=corpus, reg=read_register(corpus),
                   art=read_artifacts(corpus), rep=Reporter())


def _names(blob: bytes) -> list[str]:
    return [blob[at:at + len(tok.needle)].decode() for at, tok in interims.hits(blob)]


def _empty_form_holds() -> None:
    found, ok = _decide({})
    ensure(not found, f"a declared tree under the empty lists must hold: {found!r}")
    ensure("(0 listed)" in ok, f"the empty form lists no consumer: {ok!r}")
    read = interims.read_lists(_EMPTY)
    ensure(read.consumers == {FSTAR: [], EASYCRYPT: []} and not read.faults,
           f"the empty sentence is both lists empty: {read!r}")


def _non_empty_form_is_read_and_resolved() -> None:
    read = interims.read_lists(_LISTED)
    ensure(not read.faults, f"the per-interim form must read: {read.faults!r}")
    ensure(read.consumers == {FSTAR: ["M3.4x", "`kernel/src/mlkem.c`"], EASYCRYPT: []},
           f"the entries are the label head and the path: {read.consumers!r}")
    found, ok = _decide({interims.PLAN: _PLAN_RIDING, "kernel/src/mlkem.c": _MLKEM},
                        accept=_LISTED)
    ensure(not found, f"both listed consumers cite F*/Z3 where they are anchored: {found!r}")
    ensure("(2 listed)" in ok, f"the clean line counts the entries: {ok!r}")
    item = (interims.PLAN, "M3.4x · Import a post-quantum primitive")
    both, _ = _decide({interims.PLAN: _PLAN_RIDING, "kernel/src/mlkem.c": _MLKEM},
                      accept=_LISTED, declared={**_DECLARED, item: interims.NonPremise(
                          (FSTAR,), "a comparator", ("its correctness rests on",))})
    ensure(len(both) == 1 and "is both a consumer R-05-022 lists for F*/Z3 and a "
           "non-premise" in both[0],
           f"an anchor both listed and declared is a finding: {both!r}")
    single = interims.read_lists(_BOOKS + "F\\*/Z3's consumer is R-05-061. EasyCrypt's "
                                          "consumers are M3.4b, `proofs/X.v`, and Q2a.")
    ensure(single.consumers == {FSTAR: ["R-05-061"],
                                EASYCRYPT: ["M3.4b", "`proofs/X.v`", "Q2a"]},
           f"a singular statement and a serial comma both read: {single.consumers!r}")


def _unlisted_consumer_is_a_finding() -> None:
    found, _ = _decide({"kernel/src/mlkem.c": _MLKEM, interims.PLAN: _PLAN_RIDING})
    ensure(any(f.startswith("kernel/src/mlkem.c:1 cites Hacl, F*") for f in found),
           f"a source resting on HACL* is named by path, line and token: {found!r}")
    ensure(any("(M3.4x · Import a post-quantum primitive) cites HACL of F*/Z3" in f
               for f in found),
           f"a plan item's citation is named with the item it sits under: {found!r}")
    ensure(len(found) == 2, f"one finding per unaccounted line: {found!r}")


def _live(path: str) -> str:
    return (TOOLS.parent / path).read_text(encoding="utf-8")


def _premise_in_declared_anchor_is_a_finding() -> None:
    # The live files under the live declarations, so the fragments these cases hold are
    # the ones the rule ships with rather than a fixture's copy of them.
    for path, anchor, text, after in (
            (_MLDSA, "", _live(_MLDSA),
             "carries no authorization for deterministic production signing."),
            (interims.PLAN, _CORE, _live(interims.PLAN),
             "This module is a dependency of the RoT (§2), the object system (§6), "
             "and the filesystem (§7).")):
        declared = {**_DECLARED, **{site: np for site, np in interims.NON_PREMISE.items()
                                    if site[0] == path}}
        found, _ = _decide({path: text}, declared=declared)
        ensure(not found, f"{path} under its live declarations must hold: {found!r}")
        ensure(text.count(after) == 1, f"the seed point must be unique in {path}")
        seeded = text.replace(after, f"{after} {_PREMISE}")
        found, _ = _decide({path: seeded}, declared=declared)
        line = seeded[:seeded.index(_PREMISE)].count("\n") + 1
        where = f"{path}:{line} ({anchor})" if anchor else f"{path}:{line}"
        ensure(any(f.startswith(f"{where} cites HACL, F\\* of F*/Z3") and
                   "none of the fragments" in f for f in found),
               f"a premise written into a declared anchor is unresolved: {found!r}")
        ensure(len(found) == 1, f"only the seeded line is a finding: {found!r}")


def _fragments_are_exact() -> None:
    notes = "docs/notes.md"
    text = ("HACL\\* is a comparator here.\n\nHACL\\* is a comparator there.\n\n"
            "libcrux is read for its answers.\n")
    declared = {**_DECLARED, (notes, ""): interims.NonPremise(
        (FSTAR,), "comparator notes", ("is a comparator", "is read", "for its answers"))}
    found, _ = _decide({notes: text}, declared=declared)
    ensure(any("fragment 'is a comparator', which lines 1, 3" in f for f in found),
           f"a fragment two citing lines carry names neither: {found!r}")
    ensure(sum(" on a line none of the fragments" in f for f in found) == 2,
           f"so both lines it would have named stay unresolved: {found!r}")
    ensure(any(f.startswith(f"{notes}:5 is named by 2 declared fragments") for f in found),
           f"a line two fragments name is a finding: {found!r}")
    for fragments, want in (((), "names no fragment"), (("  ",), "a blank fragment")):
        declared = {**_DECLARED, (notes, ""): interims.NonPremise(
            (FSTAR,), "comparator notes", fragments)}
        found, _ = _decide({notes: "libcrux is read for its answers.\n"}, declared=declared)
        ensure(any(want in f for f in found), f"'{want}' must be a finding: {found!r}")
        ensure(any(" on a line none of the fragments" in f for f in found),
               f"and the line it would have named stays unresolved: {found!r}")


def _stale_declaration_is_a_finding() -> None:
    declared = {**_DECLARED,
                ("docs/notes.md", ""): interims.NonPremise((FSTAR,), "a comparator note",
                                                           ("comparator",)),
                GOVERNED: interims.NonPremise((FSTAR, EASYCRYPT, "Lean"), "the rule",
                                              (_HELD_HERE,))}
    found, _ = _decide({"docs/notes.md": "No lineage is named here.\n"}, declared=declared)
    ensure(any(f.startswith("docs/notes.md is declared no premise of F*/Z3")
               and "classifies nothing" in f for f in found),
           f"a declaration no citation answers is a finding: {found!r}")
    ensure(any(f.startswith("docs/notes.md declares the fragment 'comparator', and no "
                            "line") for f in found),
           f"a fragment naming no citing line is a finding: {found!r}")
    ensure(any("declared no premise of Lean" in f for f in found),
           f"each interim a declaration names must be cited there: {found!r}")
    unmatched, _ = _decide({}, excluded={"docs/gone/": "nothing lives here"})
    ensure(any("exclusion of docs/gone/" in f for f in unmatched),
           f"an exclusion matching no tracked file is a finding: {unmatched!r}")


def _exclusions_are_exact() -> None:
    files = {"docs/reuse.md": "HACL\\* is surveyed.\n",
             "docs/reuse-bearing.md": "HACL\\* bears on nothing.\n",
             "docs/reuse/crypto.md": "libcrux is surveyed.\n"}
    found, _ = _decide(files, excluded={"docs/reuse": "a prefix with no slash",
                                        "docs/reuse/": "the subject records"})
    ensure(any(f.startswith("the exclusion of docs/reuse (") for f in found),
           f"a row without a slash is one exact path, and none is tracked: {found!r}")
    ensure(any(f.startswith("docs/reuse.md:1 cites") for f in found) and
           any(f.startswith("docs/reuse-bearing.md:1 cites") for f in found),
           f"so neither sibling file is excluded by it: {found!r}")
    ensure(not any(f.startswith("docs/reuse/crypto.md") for f in found),
           f"a row ending in a slash excludes the directory: {found!r}")

    evidence = "docs/implementation/retained-evidence/run.json"
    pin = '    "upstream/hacl-star": "gitlink:' + "0" * 40 + '",\n'
    twice = "{\n" + pin + pin + "}\n"
    found, ok = _decide({evidence: twice}, snapshots=True)
    ensure(not found and "2 snapshot pin entries passed over" in ok,
           f"a snapshot's pin entries are passed over, twins included: {found!r} {ok!r}")
    found, _ = _decide({evidence: twice.replace("}", '"note": "rests on HACL*"\n}')},
                       snapshots=True)
    ensure(len(found) == 1 and found[0].startswith(f"{evidence}:4 cites HACL"),
           f"any other line of retained evidence is read: {found!r}")
    found, _ = _decide({"docs/run.json": twice}, snapshots=True)
    ensure(any(f.startswith("docs/run.json:2 cites hacl") for f in found),
           f"a pin entry outside the evidence directories is read: {found!r}")
    ensure(any("passes over no line citing a lineage" in f for f in found),
           f"and the pin exclusion passing over nothing is a finding: {found!r}")


def _every_tracked_file_is_read_or_reported() -> None:
    tree = {REGISTER: _register(_EMPTY), interims.PLAN: _PLAN, interims.LOG: _LOG,
            interims.RECORD: _RECORD, "kernel/gone.c": "int x;\n",
            "kernel/latin.c": "int x;\n"}
    with sandbox_tree(tree) as root:
        (root / "kernel/gone.c").unlink()
        (root / "kernel/latin.c").write_bytes(b"/* caf\xe9 */\n/* Hacl_ caf\xe9 */\n")
        found, _ = interims.decide(_context(root), {}, _DECLARED)
    ensure(any(f.startswith("kernel/gone.c is in the index and not on disk") and
               "undecided" in f for f in found),
           f"a tracked file absent from disk is undecided, not skipped: {found!r}")
    ensure(any(f.startswith("kernel/latin.c:2 cites Hacl of F*/Z3") for f in found),
           f"a file that is not UTF-8 is still read: {found!r}")
    ensure(len(found) == 2, f"and nothing else is reported: {found!r}")


def _listed_consumer_citing_nothing_is_a_finding() -> None:
    accept = (_BOOKS + "F\\*/Z3's consumers are M9.9 and `kernel/src/mlkem.c`; "
              "EasyCrypt's consumers are R-05-022 and `proofs/Absent.v`.")
    found, _ = _decide({"kernel/src/mlkem.c": "int x;\n"}, accept=accept,
                       declared={})
    ensure(any("lists `kernel/src/mlkem.c` as a consumer of F*/Z3, and nothing at "
               "kernel/src/mlkem.c cites" in f for f in found),
           f"a listed path citing nothing of its interim is a finding: {found!r}")
    ensure(any("lists M9.9 as a consumer of F*/Z3, and no checklist item" in f
               for f in found), f"a label naming no item is a finding: {found!r}")
    ensure(any("`proofs/Absent.v` as a consumer of EasyCrypt, and the index carries no "
               "such path" in f for f in found),
           f"a path the index does not carry is a finding: {found!r}")
    ensure(not any("R-05-022 as a consumer" in f for f in found),
           f"a listed entry citing its interim resolves: {found!r}")


def _missing_governing_entry_fails_closed() -> None:
    for accept, want in ((None, "declares no R-05-022"),
                         ("", "carries no criterion"),
                         (_BOOKS + "The lists are kept elsewhere.",
                          "states no consumer list for F*/Z3"),
                         (_EMPTY + " EasyCrypt's consumer list is empty.",
                          "beside a list of its own"),
                         (_BOOKS + "EasyCrypt's consumer list is empty. F\\*/Z3's "
                                   "consumer list is empty. EasyCrypt's consumers are "
                                   "M3.4x.", "EasyCrypt's consumer list twice"),
                         (_BOOKS + "F\\*/Z3's consumers are M3.4x and M3.4x; EasyCrypt's "
                                   "consumer list is empty.", "enters M3.4x in")):
        found, _ = _decide({}, accept=accept)
        ensure(any(want in f for f in found),
               f"an unreadable list must fail closed with '{want}': {found!r}")


def _escaped_and_unescaped_fstar() -> None:
    ensure(_names(b"F*/Z3 and F\\*/Z3, `F*`, (F*) and **F\\***") ==
           ["F*", "F\\*", "F*", "F*", "F\\*"],
           f"both spellings of the prover are read: {_names(b'F*/Z3 and F\\*/Z3')!r}")
    ensure(_names(b"**F** PDF* *F* F*x F**, *Low* and Lower*") == [],
           "bold and italic letters, a longer word and a following word are not the "
           f"prover: {_names(b'**F** PDF* *F* F*x F**, *Low* and Lower*')!r}")
    ensure(_names(b"Low\\* and **F*/Z3**") == ["Low\\*", "F*"],
           f"the low-level fragment and a bold span are read: {_names(b'Low\\* **F*/Z3**')!r}")
    ensure(_names(b"Hacl_Hash, hacl-star, SHACL, hax_lib, haxe, Jasmine, formosa-crypto")
           == ["Hacl", "hacl", "hax", "formosa"],
           "a word start in any case, with no longer word read as a lineage")


_STAR = "⋆"

# One spelling per lineage name the table must keep reading. The loop over TOKENS
# holds each token to its own canonical spelling; this list is what fails when a token
# is dropped, so it is the floor against the table narrowing.
_READ = ("F*", "F\\*", f"F{_STAR}", "Low*", "Low\\*", f"Low{_STAR}", "FStar", "fstar.exe",
         "FStarLang", "mitls-fstar", "F-star", "LowStar", "KaRaMeL", "krml", "HACL",
         "hacl-star", "Hacl_Hash", "EverCrypt", "libcrux", "Cryspen", "hax", "EasyCrypt",
         "Jasmin", "jasminc", "jasmin2ec", "jasmin-lang", "libjade", "formosa-crypto")
_NOT_READ = ("jasmine", "Jasmine", "**F**", "*F*", "*Low*", "Vale", "Z3", "Why3",
             "SHACL", "haxe")


def _token_table_reads_every_name() -> None:
    for tok in interims.TOKENS:
        got = [t for _, t in interims.hits(tok.name.encode())]
        ensure(got == [tok], f"token {tok.name!r} must read its own canonical spelling "
                             f"and nothing else: {[t.name for t in got]!r}")
    for spelling in _READ:
        ensure(len(interims.hits(spelling.encode())) == 1,
               f"{spelling!r} is a lineage name the table must read")
    for spelling in _NOT_READ:
        ensure(not interims.hits(spelling.encode()),
               f"{spelling!r} is not a lineage name: {_names(spelling.encode())!r}")


def cases() -> list[Case]:
    return [
        Case("empty-form-holds", _empty_form_holds),
        Case("non-empty-form-is-read-and-resolved", _non_empty_form_is_read_and_resolved),
        Case("unlisted-consumer-is-a-finding", _unlisted_consumer_is_a_finding),
        Case("premise-in-declared-anchor-is-a-finding",
             _premise_in_declared_anchor_is_a_finding),
        Case("fragments-are-exact", _fragments_are_exact),
        Case("stale-declaration-is-a-finding", _stale_declaration_is_a_finding),
        Case("exclusions-are-exact", _exclusions_are_exact),
        Case("every-tracked-file-is-read-or-reported",
             _every_tracked_file_is_read_or_reported),
        Case("listed-consumer-citing-nothing-is-a-finding",
             _listed_consumer_citing_nothing_is_a_finding),
        Case("missing-governing-entry-fails-closed", _missing_governing_entry_fails_closed),
        Case("escaped-and-unescaped-fstar", _escaped_and_unescaped_fstar),
        Case("token-table-reads-every-name", _token_table_reads_every_name),
    ]
