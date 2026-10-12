# Preventing recurring CI failures

This contract owns the maintenance work prompted by the October 2026 CI review.
The [validation handoff](../../AGENTS.md#tool-execution-and-validation) and
[Guest CI contract](README.md) retain their acceptance requirements. These tools
prepare complete inputs and improve diagnostics; they grant no model, proof,
compiler or target acceptance of their own.

## Generated behavioral checks

The vector bit-count generator selects independent expected answers by an explicit
operation match, without depending on Sail vector literal order. Generated failures
name the operation, width, input, aliasing and expected and observed answers.
A small hosted Sail adapter check exercises the actual generated selector with
distinguishable answers before the full model evidence sweep. The integer oracle,
decoded corpus, instruction semantics and full Guest lanes remain intact.
Acceptance reproduces the original descending-index mismatch as a negative control
and checks every supported width and operation with the corrected selector.

Every host-reproducible corpus artifact belongs to the existing generated-artifact
registry, including block authority. The normal integration repair regenerates it
from its owners; focused controls reject missing or stale bytes. Behavioral emulator
acceptance remains separate.

Corpus image baselines bind each reviewed member's name, source bytes and encoded
image bytes. Migration first reproduces the existing aggregate baseline. An explicit
extension operation refuses changed or removed old members before recording new
members; an encoder or source change requires a separately reviewed baseline update.
Normal checks never rewrite baselines. Controls cover additions, removals, changed
sources and changed encoded images.

## Retained evidence

A retention producer copies explicitly selected files into a new contained bundle,
writes their hashes and byte counts, and emits a manifest citation with its hash.
It refuses existing destinations, escaping or ambiguous member names and symlinks;
interruption never publishes a partial bundle. Identity and gzip records bind both
stored and decoded bytes. The citation may have a readable descriptive label:
the resolved indexed target and independently recorded hash establish identity.
External roots, traversal checks, indexed membership and nested-manifest refusal
remain mandatory. Acceptance includes the existing retention controls and producer
controls for successful publication, collisions, escaping paths, changed bytes and
interrupted publication. Producing a bundle does not stage it or edit an owning note.

## Command and workflow preparation

Help-only lane declarations generate their documentation and test enumeration from
command metadata. Operational commands retain independent handler fixtures; lane
portability checks do not depend on the checkout's historical staged boot receipts.
Strict current target verification remains in its dedicated acceptance checks.
Acceptance rejects undeclared or untested operational handlers and checks every
declared help spelling on both host platforms.

Instrument dispatch has an explicit convenience route that resolves a local Git
revision to a full lowercase commit SHA. Raw dispatch remains available for refusal
qualification, and the hosted plan still checks commit existence, main ancestry,
recipes and all inputs. Acceptance covers canonical resolution, invalid refs,
literal raw inputs and unchanged interrupted-dispatch behavior.

The boot-chain workflow checks revision, timeout and staged readiness once before
allocating campaign runners. No refused plan executes campaign code. Acceptance
covers absent, stale and incomplete staging, valid readiness and dependency wiring;
no readiness result substitutes for campaign execution.

Actionlint caches only the pinned source archive under its SHA-256 identity and
verifies cached bytes before extraction. Corruption cannot authorize an executable;
verified downloads publish atomically, with bounded network retries. Both workflow
analyzers remain mandatory. Acceptance exercises reuse without a network request,
corruption refusal or verified replacement, and interrupted download cleanup.

Formatting uses locked editions on explicitly selected changed files. Preparation
must not install shared Git hooks, weaken analyzers, silently accept rewritten
baselines or run full local gates. Focused tests and Python analysis supply local
feedback; Host CI and every Guest lane supply the final hosted handoff.
