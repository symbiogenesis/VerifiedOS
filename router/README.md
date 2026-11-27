# Contained Object Router and Credential Handles

GC-free ISO C17 implementation of the host-authorable object-router and
protocol-credential boundaries specified in
[ObjectRouter.v](../proofs/ObjectRouter.v),
[CredentialHandles.v](../proofs/CredentialHandles.v), and
[service-authoring.md](../docs/implementation/contracts/service-authoring.md#1-object-router-and-credential-handles).

## Files

- [vos_router.h](include/vos_router.h): public types and entry points using
  explicit caller-owned bounded storage with no heap allocation or recursion.
- [router.c](src/router.c): private namespace index write validation,
  session-scoped capability routing, bounded live-query delta publication,
  reboot erasure/rescan recovery, and sealed seven-binding credential handle
  authorization and monotone delegation.
- [test_router.c](test/test_router.c): host C17 positive and negative control
  suite executed under ASan/UBSan and compiled mutation controls via
  `python3 tools/run.py test --only test_router_c`.

## Scope and boundaries

- **Private namespaces (`R-10-005b`, `R-12-024a`, `R-12-024e`)**: rejects
  tagged words inside declared index extents, rejects cross-domain index
  extents and cross-domain writes, enforces session revocation-epoch matching,
  and guarantees returned object capabilities are derivable from the caller's
  presented namespace capability.
- **Bounded live-query delta streams (`R-10-005c`, `R-08-046`)**: validates
  composition-fixed queue and result bounds, publishes only after commit without
  backpressuring commit on full rings or overflowing subscriptions, collapses
  overflow to a single `VOS_DELTA_RESCAN` marker with no subsequent deltas, and
  erases all subscriptions on reboot so recovery re-establishes with rescan.
- **Sealed seven-binding credential handles (`R-12-015a`, `R-12-015b`)**:
  binds protocol role, principal, peer/origin scope bitset, permitted operations
  bitset, transcript/domain separator, use-count ceiling, and expiry over a
  shared server-owned account counter; refuses raw handle export and widened
  delegation; enforces server-side trusted-path consent. Logical handle values
  in C do not establish hardware CHERI sealing or cryptographic key custody.
