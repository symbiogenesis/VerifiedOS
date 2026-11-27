# Elastic Pool Service and Member Heap Library

Original Apache-2.0 GC-free C17 implementation of the elastic pool service and
default member heap library (`Q34c-ii-a`), authored against
[ElasticPool.v](../proofs/ElasticPool.v) and
[elastic_pool.py](../tools/vos/elastic_pool.py). Incorporates no CheriBSD or
other upstream allocator code.

## Files

| Artifact | Purpose |
| --- | --- |
| [include/vos_elastic_pool.h](include/vos_elastic_pool.h) | Composition-fixed size-class table (`16`–`65536` bytes), plan/slot/holder/domain structures, and public status codes |
| [src/elastic_pool.c](src/elastic_pool.c) | 5-phase two-generation quarantine, eager zeroing, exact granule narrowing without runtime `CRRL`/`CRAM`, per-island 8-byte revocation-granule separation, `LinkedMetaState` holder barrier wired to [vos_effects.h](../kernel/include/vos_effects.h), nested heap lifetime invalidation, and exhausted-class refusal |
| [test/test_elastic_pool.c](test/test_elastic_pool.c) | Native ASan/UBSan self-checks and `--trace` differential harness |

## Profile and Verification

Authored under [c-language-profile.md](../docs/implementation/c-language-profile.md):
caller-owned backing buffers, zero dynamic allocation, bounded loops, and no
pointer-to-integer casts. Run `python3 tools/run.py test --only test_elastic_pool_c`
on Linux for the native ASan/UBSan suite, differential comparison against
`vos.elastic_pool`, and compiled behavioral mutation controls.
