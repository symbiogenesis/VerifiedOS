# SPDX-License-Identifier: Apache-2.0
"""The derived header region: the exclusion that holds one out of the citation
reading, and K-108, the rule that stops that exclusion widening.

Every fixture is synthetic, covering both reference manifests and legacy prose
regions. Malformed cases must fail without relying on the shipped proof roster.

What the parse half holds is the shape of the reading rather than the reading's
subject: an artifact with no region is read whole, a well-formed region is skipped,
and each of the three imbalances is a fault the caller is handed rather than a region
silently swallowed. The last is the property the whole design turns on, because a
BEGIN nobody closed would otherwise hold every citation below it out of K-103 and
leave that rule green over nothing.

What the rule half holds is that the region cannot be used to hide a citation, that
a region carrying code or prose is a finding, and that the probe reports when the
exclusion itself moves.
"""

from pathlib import Path

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos import proofcites
from vos.checks import Context, citations
from vos.register import read_artifacts, read_register
from vos.report import Reporter

BEGIN = proofcites.DERIVED_BEGIN
END = proofcites.DERIVED_END

# One entry citing a second, so that a transcription of the first names the second and
# a rule reading only the ids the cited entries transcribe has both directions to
# decide. The third is the id no transcription of the first two reaches.
REGISTER = (
    "# Register\n\n## §1\n\n"
    "**R-01-001** MUST: the first obligation, which R-02-002 also bears.\n"
    "· Accept: it holds.\n"
    "· Trace: t\n"
    "**R-02-002** MUST: the second obligation.\n"
    "· Accept: it holds.\n"
    "· Trace: t\n"
    "**R-03-003** MUST: the third obligation.\n"
    "· Accept: it holds.\n"
    "· Trace: t\n")

REGISTER_DOC = "docs/requirements-register.md"
ARTIFACT = "proofs/Fixture.v"


# =====================================================================================
# the parse: what `derived` reads and what `ids` skips
# =====================================================================================


def _no_region_is_read_whole() -> None:
    text = "(* argues from R-01-001 and R-02-002 *)\nDefinition d := 0.\n"
    region = proofcites.derived(text)
    ensure(region == proofcites.Derived(),
           f"a file carrying no marker carries no region and no fault: {region!r}")
    ensure(proofcites.ids(text) == ["R-01-001", "R-02-002"],
           f"and every citation in it is read: {proofcites.ids(text)!r}")


def _a_well_formed_region_is_skipped() -> None:
    text = (f"(* cites R-01-001\n{BEGIN}\n"
            "   **R-01-001** MUST: the first obligation, which R-02-002 also bears.\n"
            f"{END} *)\nDefinition d := 0.\n")
    region = proofcites.derived(text)
    ensure(len(region.spans) == 1 and not region.faults,
           f"one region and no fault: {region!r}")
    ensure(proofcites.ids(text) == ["R-01-001"],
           f"the citation outside it is read and the transcription is not: "
           f"{proofcites.ids(text)!r}")


def _the_self_feeding_ids_are_not_citations() -> None:
    # The blocker itself: the transcription names an entry the artifact never cites,
    # and reading it as a citation is what makes a region feed the next regeneration.
    text = (f"(* cites R-01-001\n{BEGIN}\n"
            "   **R-01-001** MUST: the first obligation, which R-02-002 also bears.\n"
            f"{END} *)\n")
    ensure("R-02-002" not in proofcites.ids(text),
           "an id a region merely transcribes is no citation of the file it sits in")
    ensure(proofcites.citations([(ARTIFACT, text)]) == {ARTIFACT: {"R-01-001"}},
           "and the index every caller reads inherits that")


def _a_begin_with_no_end_is_a_fault_that_excludes_nothing() -> None:
    text = (f"(* cites R-01-001\n{BEGIN}\n"
            "   **R-02-002** MUST: the second obligation.\n*)\n")
    region = proofcites.derived(text)
    ensure(not region.spans and len(region.faults) == 1,
           f"an unclosed region is a fault and no span: {region!r}")
    ensure("never closes" in region.faults[0], f"and says so: {region.faults!r}")
    ensure(proofcites.ids(text) == ["R-01-001", "R-02-002"],
           "and the file is read whole, which is what keeps a swallowed BEGIN from "
           f"emptying the citation reading: {proofcites.ids(text)!r}")


def _an_end_with_no_begin_is_a_fault() -> None:
    text = f"(* cites R-01-001\n{END} *)\n"
    region = proofcites.derived(text)
    ensure(not region.spans and len(region.faults) == 1,
           f"a stray END is a fault and no span: {region!r}")
    ensure("no line above it opened" in region.faults[0],
           f"and says what it could not read: {region.faults!r}")
    ensure(proofcites.ids(text) == ["R-01-001"],
           f"and nothing is excluded: {proofcites.ids(text)!r}")


def _nested_begins_are_a_fault() -> None:
    text = (f"(* cites R-01-001\n{BEGIN}\n   **R-02-002** MUST: the second.\n"
            f"{BEGIN}\n   **R-03-003** MUST: the third.\n{END} *)\n")
    region = proofcites.derived(text)
    ensure(not region.spans, f"a nested region yields no span at all: {region!r}")
    ensure(any("does not nest" in fault for fault in region.faults),
           f"and the nesting is the fault: {region.faults!r}")
    ensure(proofcites.ids(text) == ["R-01-001", "R-02-002", "R-03-003"],
           f"and every id is read rather than half of them: {proofcites.ids(text)!r}")


def _a_marker_that_is_neither_delimiter_is_a_fault() -> None:
    # a delimiter respelled past the pattern: the region stops being one, which is the
    # one imbalance that would otherwise be silent
    text = (f"(* cites R-01-001\n{proofcites.DERIVED_MARK} BEGIN derived entries |*)\n"
            f"   **R-02-002** MUST: the second obligation.\n{END} *)\n")
    region = proofcites.derived(text)
    ensure(not region.spans and bool(region.faults),
           f"a marker this parse cannot read is a fault: {region!r}")
    ensure(any("neither a BEGIN" in fault for fault in region.faults),
           f"and names itself: {region.faults!r}")


def _two_regions_in_one_file_are_both_skipped() -> None:
    text = (f"(* cites R-01-001\n{BEGIN}\n   **R-02-002** MUST: the second.\n{END}\n"
            f"   and cites R-01-001 again\n{BEGIN}\n"
            f"   **R-03-003** MUST: the third.\n{END} *)\n")
    region = proofcites.derived(text)
    ensure(len(region.spans) == 2 and not region.faults,
           f"two regions and no fault: {region!r}")
    ensure(proofcites.ids(text) == ["R-01-001", "R-01-001"],
           f"and both are held out: {proofcites.ids(text)!r}")


# =====================================================================================
# the rule: K-108 over a fixture corpus
# =====================================================================================


def _context(root: Path) -> Context:
    corpus = corpus_mod.load(root)
    return Context(root=root, corpus=corpus, reg=read_register(corpus),
                   art=read_artifacts(corpus), rep=Reporter())


def _k108(artifact: str) -> list[str]:
    """The findings K-108 reports over a tree carrying one artifact."""
    with sandbox_tree({REGISTER_DOC: REGISTER, ARTIFACT: artifact}) as root:
        ctx = _context(root)
        citations.run(ctx)
    out: list[str] = []
    collecting = False
    for line in ctx.rep.out:
        if line.startswith("FAIL K-108:"):
            collecting = True
        elif collecting and line.startswith("       "):
            out.append(line.strip())
        elif collecting:
            break
    return out


_TRANSCRIPT = ("   **R-01-001** MUST: the first obligation, which R-02-002 also "
               "bears.\n")


def _a_faithful_region_is_no_finding() -> None:
    found = _k108(f"(* cites R-01-001\n{BEGIN}\n{_TRANSCRIPT}{END} *)\n")
    ensure(found == [], f"a region transcribing what the artifact cites passes: {found!r}")


def _a_region_hiding_a_citation_is_the_finding() -> None:
    # R-03-003 is live, so K-103 says nothing about it; what is wrong is that the file
    # names it only inside a region, where the citation reading cannot see it
    found = _k108(f"(* cites R-01-001\n{BEGIN}\n{_TRANSCRIPT}"
                  "   **R-03-003** MUST: the third obligation.\n"
                  f"{END} *)\n")
    ensure(any("names R-03-003" in f for f in found),
           f"an id no cited entry transcribes is the finding: {found!r}")
    ensure(not any("R-02-002" in f for f in found),
           f"and an id the cited entry's own line names is not: {found!r}")


def _a_vernacular_inside_a_region_is_the_finding() -> None:
    found = _k108(f"(* cites R-01-001 *)\n{BEGIN}\n{_TRANSCRIPT}"
                  "Definition d := 0.\n"
                  f"{END}\n")
    ensure(any("opens a vernacular" in f for f in found),
           f"a region that has swallowed code is the finding: {found!r}")


def _prose_inside_a_region_is_the_finding() -> None:
    found = _k108(f"(* cites R-01-001\n{BEGIN}\n{_TRANSCRIPT}"
                  "and a sentence somebody wrote here by hand.\n"
                  f"{END} *)\n")
    ensure(any("names no requirement" in f for f in found),
           f"a line that is no transcription is the finding: {found!r}")


def _a_wrapped_transcription_is_admitted() -> None:
    found = _k108(f"(* cites R-01-001\n{BEGIN}\n{_TRANSCRIPT}"
                  "      also bears, stated at the width this header wraps to.\n"
                  f"{END} *)\n")
    ensure(found == [], f"an indented continuation is part of its entry line: {found!r}")


def _an_unbalanced_region_is_the_finding() -> None:
    found = _k108(f"(* cites R-01-001\n{BEGIN}\n{_TRANSCRIPT}*)\n")
    ensure(any("never closes" in f for f in found),
           f"the imbalance is reported rather than swallowed: {found!r}")


def _the_probe_holds_on_a_tree_with_no_region() -> None:
    # the floor: no artifact here carries a region, and the rule still decides
    found = _k108("(* cites R-01-001 *)\nDefinition d := 0.\n")
    ensure(found == [], f"a tree with no region is clean: {found!r}")
    probes, moved = citations._probe()
    ensure(probes == 4 and moved == [],
           f"and the exclusion answers at every probe: {probes} {moved!r}")


def _compact_manifests_are_strict() -> None:
    body = ("   Owner: docs/requirements-register.md\n"
            "   Requirements: R-01-001\n"
            "   SHA256: " + "a" * 64 + "\n")

    def artifact(value: str) -> str:
        return f"(* cites R-01-001\n{BEGIN}\n{value}{END} *)\n"

    ensure(_k108(artifact(body)) == [], "a compact reference manifest was rejected")
    bad = [body.replace("register.md", "other.md"),
           body.replace("SHA256:", "Digest:"), body.replace("a" * 64, "abc"),
           body + "   Definition hidden := 0.\n",
           body.replace("R-01-001\n", "R-01-001 Definition hidden := 0.\n"),
           body.replace("   Owner: docs/requirements-register.md\n", ""),
           body + "   Owner: docs/requirements-register.md\n"]
    for value in bad:
        ensure(any("malformed reference manifest" in fault for fault in _k108(artifact(value))),
               "an incomplete, extended or corrupted manifest was silently excluded")
    for ident in ("R-02-002", "R-03-003"):
        value = body.replace("Requirements: R-01-001", "Requirements: R-01-001\n      " + ident)
        ensure(any("names " + ident in fault for fault in _k108(artifact(value))),
               "a manifest hid an unauthored citation, including one reached transitively")


def cases() -> list[Case]:
    return [
        Case("no-region-is-read-whole", _no_region_is_read_whole),
        Case("well-formed-region-is-skipped", _a_well_formed_region_is_skipped),
        Case("transcribed-ids-are-no-citation", _the_self_feeding_ids_are_not_citations),
        Case("begin-with-no-end-excludes-nothing",
             _a_begin_with_no_end_is_a_fault_that_excludes_nothing),
        Case("end-with-no-begin-is-a-fault", _an_end_with_no_begin_is_a_fault),
        Case("nested-begins-are-a-fault", _nested_begins_are_a_fault),
        Case("stray-marker-is-a-fault", _a_marker_that_is_neither_delimiter_is_a_fault),
        Case("two-regions-are-both-skipped", _two_regions_in_one_file_are_both_skipped),
        Case("faithful-region-passes", _a_faithful_region_is_no_finding),
        Case("region-hiding-a-citation", _a_region_hiding_a_citation_is_the_finding),
        Case("vernacular-in-a-region", _a_vernacular_inside_a_region_is_the_finding),
        Case("prose-in-a-region", _prose_inside_a_region_is_the_finding),
        Case("wrapped-transcription-admitted", _a_wrapped_transcription_is_admitted),
        Case("unbalanced-region-is-the-finding", _an_unbalanced_region_is_the_finding),
        Case("probe-holds-with-no-region", _the_probe_holds_on_a_tree_with_no_region),
        Case("compact-manifests-are-strict", _compact_manifests_are_strict),
    ]
