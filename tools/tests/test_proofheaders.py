# SPDX-License-Identifier: Apache-2.0
"""Generated proof headers preserve code and authored citations and converge."""

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from tests.test_memplan import _TOY
from vos import corpus as corpus_mod
from vos import memplan, proofcites, proofheaders, proofs
from vos.checks import Context, generated, headers
from vos.register import REGISTER, Register, read_artifacts, read_register
from vos.report import Reporter

_SOURCE = (
    "(* SPDX-License-Identifier: Apache-2.0 *)\n"
    "(* =========================================================================\n"
    "   Fixture.v\n\n"
    "   The author's reading of R-01-001 stays here, including its gaps.\n"
    "   ========================================================================= *)\n"
    "Definition result : nat := 1.\n")

# Root selection is confined to this child: test modules run concurrently, so a
# process-wide find_root patch or stdout redirect in the runner would affect peers.
_SHOW_CLI = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from vos import corpus
import run
root = Path(sys.argv[2])
corpus.find_root = lambda start=None: root
raise SystemExit(run.main(["proofs", "headers", *sys.argv[3:]]))
"""


def _register() -> Register:
    ids = ["R-01-001", "R-02-001", "R-03-001"]
    return Register(ids=ids, id_set=set(ids), body={
        "R-01-001": "**R-01-001** MUST: follow R-02-001 for the (*P*+1)-th member.",
        "R-02-001": "**R-02-001** MUST: follow R-03-001 for the second obligation.",
        "R-03-001": "**R-03-001** MUST: satisfy the third obligation.",
    }, accept_text={"R-01-001": "· Accept: a criterion never transcribed."})


def _generation_preserves_citations_and_code() -> None:
    reg = _register()
    result = proofheaders.render(_SOURCE, reg)
    ensure(proofcites.ids(result) == proofcites.ids(_SOURCE),
           "quoting the first obligation widened the artifact's citations")
    ensure("Owner: docs/requirements-register.md" in result
           and "Requirements: R-01-001\n" in result,
           "the manifest must name its owner and authored citation set")
    ensure("R-02-001" not in result and "R-03-001" not in result,
           "a referenced entry was promoted into an authored citation")
    ensure("MUST:" not in result and "· Accept:" not in result,
           "owner prose was duplicated in the generated region")
    payload = "vos-proof-requirements-v1\0R-01-001\0" + reg.body["R-01-001"] + "\0"
    ensure(hashlib.sha256(payload.encode("utf-8")).hexdigest() in result,
           "the fingerprint does not cover the selected exact normative body")
    ensure(proofs.sentences(result) == proofs.sentences(_SOURCE),
           "the manifest changed the Gallina sentences outside the comment")
    start = result.index("   " + proofcites.DERIVED_BEGIN)
    stop = result.index(proofcites.DERIVED_END) + len(proofcites.DERIVED_END) + 1
    ensure(result[:start] + result[stop:] == _SOURCE,
           "generation changed authored bytes outside its new region")
    ensure(proofheaders.render(result, reg) == result,
           "the second regeneration did not reach a byte-for-byte fixpoint")


def _a_changed_entry_rewrites_only_its_region() -> None:
    reg = _register()
    first = proofheaders.render(_SOURCE, reg)
    reg.body["R-01-001"] = "**R-01-001** MUST: use the updated obligation."
    second = proofheaders.render(first, reg)
    ensure(second != first and "updated obligation" not in second,
           "a changed normative body must update its fingerprint without copying prose")
    old_span = proofcites.derived(first).spans[0]
    new_span = proofcites.derived(second).spans[0]
    ensure(first[:old_span[0]] == second[:new_span[0]]
           and first[old_span[1]:] == second[new_span[1]:],
           "updating a derived entry changed authored bytes")


def _canonical_selection_and_fingerprint_scope() -> None:
    reg = _register()
    source = _SOURCE.replace("R-01-001", "R-03-001, R-01-001 and R-03-001")
    first = proofheaders.manifest(source, reg)
    ensure("Requirements: R-01-001 R-03-001\n" in first,
           "the manifest must deduplicate citations in register order")
    reg.body["R-02-001"] = "**R-02-001** MUST: a changed uncited obligation."
    reg.accept_text["R-01-001"] = "· Accept: a changed criterion."
    ensure(proofheaders.manifest(source, reg) == first,
           "uncited entries or criteria entered the normative-body fingerprint")
    reg.ids.reverse()
    ensure(proofheaders.manifest(source, reg) != first,
           "the fingerprint must bind canonical requirement order")


def _show_reads_owner_prose_without_writes() -> None:
    reg = _register()
    source = proofheaders.render(_SOURCE, reg)
    reg.body["R-01-001"] = "**R-01-001** MUST: the current owner prose."
    files = {REGISTER: "# Register\n\n## §1\n\n" + "\n\n".join(reg.body.values()) + "\n",
             "proofs/Fixture.v": source}
    with sandbox_tree(files) as root:
        def cli(path: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, "-c", _SHOW_CLI, str(TOOLS), str(root), "--show", path],
                cwd=root, capture_output=True, text=True, encoding="utf-8",
                check=False, timeout=60)

        done = cli("proofs/Fixture.v")
        ensure(done.returncode == 0 and reg.body["R-01-001"] in done.stdout,
               "--show must read current normative prose even when the manifest is stale: "
               f"exit {done.returncode}, stdout={done.stdout!r}, stderr={done.stderr!r}")
        ensure(reg.body["R-02-001"] not in done.stdout,
               "--show widened the selection to transitive citations")
        ensure(all((root / rel).read_text(encoding="utf-8") == text
                   for rel, text in files.items()), "--show wrote into its owners")
        rejected = cli("../outside.v")
        ensure(rejected.returncode == 1 and "select a non-generated proof" in rejected.stdout,
               "--show accepted a path outside the proof source set")


def _line_endings_are_preserved() -> None:
    original = _SOURCE.replace("\n", "\r\n")
    result = proofheaders.render(original, _register())
    ensure("\n" not in result.replace("\r\n", ""),
           "generation mixed LF into a CRLF artifact")
    ensure(proofheaders.render(result, _register()) == result,
           "a CRLF artifact did not converge")


def _unsafe_regions_are_refused() -> None:
    marker = proofcites.DERIVED_BEGIN + "\n" + proofcites.DERIVED_END + "\n"
    inputs = [
        _SOURCE.replace("R-01-001", "R-99-999"),
        _SOURCE.replace("R-01-001", "no obligation"),
        _SOURCE + proofcites.DERIVED_BEGIN,
        _SOURCE + marker,
        _SOURCE + marker + marker,
        "(* R-01-001 *)\nDefinition x := 0.\n",
    ]
    for source in inputs:
        try:
            proofheaders.render(source, _register())
        except proofheaders.HeaderError:
            continue
        raise AssertionError("an unsafe or unidentified header was silently rewritten")


def _the_plan_excludes_the_ring_and_reports_every_fault() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-headers-") as td:
        root = Path(td)
        (root / "proofs").mkdir()
        fixture = root / "proofs/Fixture.v"
        fixture.write_text(_SOURCE, encoding="utf-8", newline="")
        ring = root / "proofs/RingContract.v"
        ring.write_text("owned by the ring compiler", encoding="utf-8")
        changed, faults = proofheaders.plan(root, _register())
        ensure(set(changed) == {"proofs/Fixture.v"} and not faults,
               f"the plan's scope is wrong: {changed.keys()}, {faults}")
        ensure(fixture.read_text(encoding="utf-8") == _SOURCE,
               "planning must not write its result")
        changed, faults = proofheaders.plan(root, _register(), [
            "proofs/Missing.v", "proofs/Fixture.v", "proofs/RingContract.v"])
        ensure(len(faults) == 1 and "Missing.v" in faults[0]
               and set(changed) == {"proofs/Fixture.v"},
               "an unreadable artifact stopped planning the remaining artifacts")


def _memory_plan_header_repair_updates_its_export_once() -> None:
    reg = _register()
    source = _SOURCE.replace("Fixture.v", "MemoryPlan.v") + _TOY
    current = proofheaders.render(source, reg)
    digest = current.split("SHA256: ", 1)[1][:64]
    stale = current.replace(digest, "0" * 64, 1)
    ensure(stale != current, "the fixture did not seed a stale generated header")
    files = {
        REGISTER: "# Register\n\n## §1\n\n" + "\n\n".join(reg.body.values()) + "\n",
        memplan.SOURCE: stale,
        memplan.ARTIFACT: memplan.emit(Path(), source_text=stale),
    }
    row = next(row for row in generated.GENERATED if row.path == memplan.ARTIFACT)

    def context(root: Path, fix: bool = False) -> Context:
        corpus = corpus_mod.load(root)
        return Context(root=root, corpus=corpus, reg=read_register(corpus),
                       art=read_artifacts(corpus), rep=Reporter(), fix=fix)

    with sandbox_tree(files) as root:
        before = context(root)
        ensure(not generated._host_row(before, row, None).findings,
               "K-88 must initially agree with the stale source's own export")
        headers.run(before)
        ensure(any(line.startswith("FAIL K-109:") for line in before.rep.out),
               "the seeded header was not a K-109 finding")

        repair = context(root, fix=True)
        generated._host_row(repair, row, None)
        headers.run(repair)
        ensure(set(repair.fixed) == {memplan.SOURCE, memplan.ARTIFACT},
               f"one repair must queue source and dependent export: {repair.fixed.keys()}")
        ensure(repair.fixed[memplan.SOURCE] == current,
               "the proof header did not return to its normative owner")
        ensure(all((root / name).read_bytes() == text.encode("utf-8")
                   for name, text in files.items()),
               "planning published a repair before the checker flush")
        for name, text in repair.fixed.items():
            (root / name).write_text(text, encoding="utf-8", newline="")

        for fix in (False, True):
            after = context(root, fix=fix)
            reading = generated._host_row(after, row, None)
            headers.run(after)
            ensure(not reading.findings and after.rep.findings == 0,
                   f"K-88 and K-109 must be clean after one repair: "
                   f"{reading.findings}, {after.rep.out}")
            ensure(after.fixed == {}, "the second repair must queue no bytes")


def cases() -> list[Case]:
    return [
        Case("generation preserves citations and code", _generation_preserves_citations_and_code),
        Case("a changed entry rewrites only its region", _a_changed_entry_rewrites_only_its_region),
        Case("canonical selection and fingerprint scope", _canonical_selection_and_fingerprint_scope),
        Case("show reads owner prose without writes", _show_reads_owner_prose_without_writes),
        Case("line endings are preserved", _line_endings_are_preserved),
        Case("unsafe regions are refused", _unsafe_regions_are_refused),
        Case("the plan excludes the ring and accumulates faults",
             _the_plan_excludes_the_ring_and_reports_every_fault),
        Case("memory-plan header repair updates its export once",
             _memory_plan_header_repair_updates_its_export_once),
    ]
