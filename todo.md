### Static code overlays

The one memory-capacity lever left open, and deliberately last.

For applications too large to remain resident even after §13's dead and duplication elimination (R-13-010a, R-13-010b, R-13-010c) and the §15 dictionary encoding (R-15-036a), composition can generate fixed code overlays:

1. The schedule identifies the code required in each phase.
2. A dedicated loader fills an instruction bank before that phase.
3. Hardware verifies its hash and its canonical encoded representation.
4. Software never receives store authority to the executable bank.
5. The bank is invalidated before reuse.

This is a statically scheduled instruction store rather than a demand-filled cache, so it preserves deterministic timing. It nonetheless adds considerably more proof machinery than anything above it: a loader with bank-fill authority, a per-phase residency plan the §11 schedule must carry, a hash-check stage on the fill path, and an invalidation obligation that joins the `fence.t` argument.

**It is not pursued unless the levers above prove insufficient against a measured roster.** They have not yet been measured, so the condition is untested rather than met.
