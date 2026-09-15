# Object-store and transactor authoring contract

This fixes the authorable M5.4 contract before its recovered Gallina artifact is completed. The [checklist](implementation-checklist.md) retains the whole implementation item. R-06-005, R-10-001, R-10-001a, R-10-009, R-10-032, R-11-001, R-11-002, R-11-005 and R-13-023b in the [register](../requirements-register.md) own the obligations; this contract adds no architectural requirement.

The source artifact is `proofs/ObjectTransactor.v`. It uses [JournalIndex.v](../../proofs/JournalIndex.v) for journal records, stores, filters and replay. [KeyspaceDomains.v](../../proofs/KeyspaceDomains.v) retains the keyspace, domains and freshness-epoch semantics. The transactor changes signed image roots and never redefines that mutable-store algebra. [RotFirmware.v](../../proofs/RotFirmware.v) and [RomVerifier.v](../../proofs/RomVerifier.v) retain the counter and boot verifier. The transactor reads the floor; advancing or resealing a counter is not one of its effects.

## Source-level acceptance

The artifact must compile and pass the repository's native constant inventory, exact empty assumption-set check, theorem-type binding, record-witness check and kernel recheck. General properties need jointly satisfiable premises and a positive constructed machine. A checksum, signature, proof-checker or health boolean is an explicit abstract interface, not a proof that its real implementation is trustworthy.

The following independent failures must be exhibited and refused by the relevant obligation:

- Returning bytes whose content address differs from the requested name, and returning an object outside the boot-attested root's authenticated closure. Every traversed object must be authenticated before its links can authorize descendants. Exhausting the declared walk depth with children still pending refuses the image rather than treating its truncated prefix as complete.
- Selecting an unverified root copy, selecting a lower verifying version over a higher one, or following an untrusted stored slot pointer.
- Modifying the running slot during staging, retaining a stale admission verdict after replacing a candidate, or flipping after verification refused the candidate.
- Booting a candidate below the floor, lowering the floor, or having the transactor itself advance/reseal that floor.
- Remaining on an unhealthy candidate when a permitted predecessor is available, or falling back through the floor. The retained predecessor is the exact previous live root recorded by a flip; restaging invalidates it. Fallback rechecks retention, signature/root bytes, complete image, admission and both floor guards. A staged or unauthenticated root cannot become a predecessor merely because its version is high enough. The absence of a permitted predecessor is an explicit unresolved recovery handoff, not permission to boot the refused predecessor.
- Treating journal commit membership alone as evidence that the staged image is complete, or pinning an inconsistent checkpoint. The exact base and admitted package identities require the qualified witness-evidence decision; selective delivery of separately valid logged variants remains possible.

Generated crash prefixes and every declared tear location in the staging journal must run through both existing recovery arms, without choosing one. A completely staged candidate is admitted when all independent guards hold; each required guard has a refusing witness. Generated checks and focused mutation probes report their actual domain, and any survivors remain findings rather than being hidden by changing that domain. The authorable source slice has no blanket requirement to mutate every fixture literal; its theorem and refusal obligations above are the fixed acceptance criteria.

## Execution predicate and open producers

The target predicate runs `python tools/run.py model corpus` over the produced storage image. It stages a candidate through M5.3's device/storage path, refuses corrupted or misbound bytes before returning an object, verifies and publishes the candidate, and observes M3.5's next boot attest that root. A second run induces health failure and observes an allowed predecessor at the next boot. Both record the actual counter and witness pin, and failures publish no unverified generation.

The selected [storage recovery policy](storage-recovery-policy.md), persistent image adapter, byte decoder/authentication bridge, executable storage package, health/escalation policy, root-publication interface and M3.5 boot/counter path are needed for that predicate. M6.2b owns proof checking; M6.2c owns the actual witness-evidence reader and its refinement. Until those joins exist, completing the reference artifact is partial M5.4 progress and cannot close the implementation item.
