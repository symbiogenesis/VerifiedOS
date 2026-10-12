# Pending contained-compiler audits

This bundle preserves Q39's current standard-mode and VM-mode pairs while their
original whole-environment kernel checks continue. Each pair keeps its own source
revision, producer, compilation receipt, pre-query seal and checker arguments.
The standard pair is `ec5b8250bb9b895a3162375e8ac80cda2ccdcbee`; the VM pair is
`6409d0ed65fd07de4fb37aa9c8f7a9d5c317cc9d`. Neither pair is selected as accepted.

[The generated summary](summary.json) records the successful export, configure,
clean, dependency, proof-compilation, extraction and compiler stages. Original
receipts remain `passed: false`, with no completed kernel receipt. Full kernel
qualification, exact whole-environment axiom classification and final input
stability remain pending. This bundle closes no checklist item or firmware
provenance blocker and supplies no hosted acceptance.

[The manifest](manifest.json) binds both stored and decompressed payload bytes.
[The capture record](capture.json) retains original paths, capture intervals,
before/after file observations, process identities and exact checker argv.
Captures are independent observations, not a globally atomic four-run snapshot.
The [supplement](capture-supplement.json) distinguishes later inode/device
observations from metadata recorded during capture. Source input inventories,
original stage-progress records, Make root/include output and completed query
declaration metadata retain paths, digests, commands, names and locations;
query source, object and statement-body bytes remain private. The generated Make
query recipes also remain private and are represented by their hashes.
The original compilation receipts and metadata-only seals are retained verbatim;
the seals and diagnostic kernel traces use lossless gzip. Contained source, proof
objects, executables and installed libraries remain private at their bound paths.

[The stage catalog](stage-capture.json) records original successful-stage log
hashes and byte counts. The original stage logs remain private: proof logs print
assumption types, and compiler logs echo generated source. The catalog's
declaration-start scan is an advisory heuristic with false negatives; its zero
counts provide no disclosure assurance. The offline verifier checks catalog
consistency with the original receipts, without rehashing the omitted stage logs.

Library traversal is derived from each exact diagnostic prefix. Rocq 9.3 emits a
checking header before importing that library, then visits its ordered library
list sequentially. See the locked release's
[import operation](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/checkLibrary.ml#L107-L124)
and [ordered traversal](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/checkLibrary.ml#L417-L422).
The verifier requires emitted checking headers to match the ordered prefix and
excludes the current entered library from the advanced-past lower bound. A
partial final line is retained byte for byte and excluded from interpretation.
The library-count fraction gives neither a workload percentage nor an ETA.
Constant-entry messages do not establish completed constant checks. A log prefix
provides no resumable checker certificate or complete audit reuse basis.

To reproduce the summary from the public bundle without WSL, a compiler, a prover,
network access or any live native-tree reads, run from the repository root:

```powershell
python docs/implementation/retained-evidence/q39/pending-audits-20261012/verify.py
```

`--write-summary` regenerates only this bundle's `summary.json`. This historical
artifact verifier checks captured bytes and derived facts; it does not validate
the omitted current object, source, tool or library populations, or substitute
for the original qualification driver. [Focused consistency and refusal
controls](verification.json) record the verifier's checks; their success supplies
no passing kernel verdict. To revalidate compilation reuse, use the
private validator through the [reuse contract](../../../contracts/contained-compiler-reuse.md).
The [earlier candidate catalog](../compilation-candidates-20261012.json) contains
separate VM compilation reuse observations and older interrupted records. Those
older records are not the current standard pair.

Native evidence and every original sealed dependency remain at their bound
locations. Public metadata retention is separate from preserving the private
build products. No original audit was stopped, restarted, attached to or changed
to make this export.
