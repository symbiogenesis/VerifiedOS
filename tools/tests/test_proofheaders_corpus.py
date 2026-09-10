# SPDX-License-Identifier: Apache-2.0
"""Every indexed proof survives a stale-manifest repair in a private corpus copy."""

import hashlib
import json
from pathlib import Path

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos import memplan, proofcites, proofheaders, proofs
from vos.checks import Context, generated, headers
from vos.register import REGISTER, read_artifacts, read_register
from vos.report import Reporter


def _context(root: Path, *, fix: bool = False) -> Context:
    corpus = corpus_mod.load(root)
    return Context(root=root, corpus=corpus, reg=read_register(corpus),
                   art=read_artifacts(corpus), rep=Reporter(), fix=fix)


def _stale_manifest(text: str, rel: str) -> str:
    region = proofcites.derived(text)
    ensure(not region.faults and len(region.spans) == 1,
           f"{rel}: the corpus proof does not have one safe manifest: {region.faults}")
    start, stop = region.spans[0]
    prefix, marker, digest = text[start:stop].partition("SHA256: ")
    ensure(bool(marker) and bool(digest) and digest[0] in "0123456789abcdef",
           f"{rel}: cannot seed a stale manifest without its fingerprint")
    first = "1" if digest[0] == "0" else "0"
    return text[:start] + prefix + marker + first + digest[1:] + text[stop:]


def _indexed_proof_corpus_repairs_without_changing_authored_content() -> None:
    # The index decides membership; fixture size and proof names follow the corpus.
    # Private copies include the generated ring, which repair must leave untouched.
    checkout = TOOLS.parent
    source_corpus = corpus_mod.load(checkout)
    rels = sorted(rel for rel in source_corpus.tracked if proofcites.is_source(rel))
    authored = set(rels) - proofheaders.EXCLUDED
    ensure(bool(authored), "an empty proof corpus cannot witness header preservation")
    original = {rel: (checkout / rel).read_bytes()
                for rel in [REGISTER, *rels, memplan.ARTIFACT]}
    files = {rel: data.decode("utf-8") for rel, data in original.items()}
    identities = {rel: (set(proofcites.ids(files[rel])), proofs.sentences(files[rel]))
                  for rel in rels}
    row = next(row for row in generated.GENERATED if row.path == memplan.ARTIFACT)

    with sandbox_tree(files) as root:
        baseline = _context(root)
        changed, faults = proofheaders.plan(root, baseline.reg, rels)
        ensure(not changed and not faults,
               f"the indexed proof corpus needs repair before mutation: "
               f"{sorted(changed)}, {faults}")
        ensure(not generated._host_row(baseline, row, None).findings,
               "the original memory-plan export disagrees with its proof")
        for rel in sorted(authored):
            seeded = _stale_manifest(files[rel], rel)
            ensure(seeded != files[rel], f"{rel}: no stale fingerprint was seeded")
            ensure((set(proofcites.ids(seeded)), proofs.sentences(seeded)) == identities[rel],
                   f"{rel}: the seed changed authored citations or Gallina sentences")
            (root / rel).write_text(seeded, encoding="utf-8", newline="")

        before = _context(root)
        headers.run(before)
        ensure(before.rep.findings == len(authored),
               f"each stale proof needs its own finding: {before.rep.out}")
        ensure(all(any(f"{rel}: generated requirement header is stale" in line
                       for line in before.rep.out) for rel in authored),
               f"a stale proof was absent from the findings: {before.rep.out}")

        seeded_bytes = {rel: (root / rel).read_bytes() for rel in original}
        repair = _context(root, fix=True)
        generated._host_row(repair, row, None)
        headers.run(repair)
        ensure(repair.rep.findings == 0,
               f"the corpus repair refused a stale proof: {repair.rep.out}")
        ensure(set(repair.fixed) == authored | {memplan.ARTIFACT},
               f"the repair omitted a proof or crossed ownership: {sorted(repair.fixed)}")
        ensure(all((root / rel).read_bytes() == data for rel, data in seeded_bytes.items()),
               "repair planning published bytes before the checker flush")
        for rel, text in repair.fixed.items():
            if rel in authored:
                ensure((set(proofcites.ids(text)), proofs.sentences(text)) == identities[rel],
                       f"{rel}: repair changed authored citations or Gallina sentences")
            (root / rel).write_text(text, encoding="utf-8", newline="")

        ensure(all((root / rel).read_bytes() == data for rel, data in original.items()),
               "repair failed to restore exact corpus bytes or changed an excluded owner")
        exported = json.loads((root / memplan.ARTIFACT).read_text(encoding="utf-8"))
        source_md5 = hashlib.md5((root / memplan.SOURCE).read_bytes(),
                                usedforsecurity=False).hexdigest()
        ensure(exported["header"]["source_md5"] == source_md5,
               "the dependent export does not bind the repaired source bytes")
        for fix in (False, True):
            after = _context(root, fix=fix)
            reading = generated._host_row(after, row, None)
            headers.run(after)
            ensure(not reading.findings and after.rep.findings == 0,
                   f"the corpus did not converge after one repair: "
                   f"{reading.findings}, {after.rep.out}")
            ensure(not after.fixed,
                   f"the converged corpus queued another repair: {sorted(after.fixed)}")


def cases() -> list[Case]:
    return [Case("indexed proof corpus repairs without changing authored content",
                 _indexed_proof_corpus_repairs_without_changing_authored_content)]
