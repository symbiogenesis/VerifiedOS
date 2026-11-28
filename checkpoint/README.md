# Semantic checkpoint and slate-slot reuse pilot (Q32b-i)

`checkpoint/` implements the bounded, GC-free C17 semantic-checkpoint,
two-slot A/B transactional commit, `Roots` reuse-barrier, and lock/unlock
recovery engine for Q32b's two-workload pilot (editor document + competing
image workspace).

## Specifications and formal companion

- [Workflow profiles and hibernation design](../docs/implementation/workflow-profiles.md)
- [Finite workflow lifecycle and admission contract](../docs/implementation/contracts/workflow-formal.md)
- [Authored C language profile](../docs/implementation/c-language-profile.md)
- [Abstract lifecycle model](../proofs/WorkflowProfiles.v)
- [Concrete semantic-checkpoint and lock/unlock proofs](../proofs/SemanticCheckpoint.v)

## Module layout

| Artifact | Purpose |
| --- | --- |
| [vos_checkpoint.h](include/vos_checkpoint.h) | Bounded editor/painter models, canonical `"VOSSEM01"` wire bounds, A/B store, `Roots`, and `vos_cp_*` API |
| [checkpoint.c](src/checkpoint.c) | Canonical serializer/decoder with HMAC-SHA256 authentication, A/B commit, crash-cut injection, barrier checks, and lock/unlock recovery |
| [test_checkpoint.c](test/test_checkpoint.c) | Standalone host test driver exercising editor <-> painter swaps, all crash cuts, lock/unlock recovery, and refusal cases |
| [vos_crypto_core.h](../storage/include/vos_crypto_core.h) | Shared SHA-256, HMAC-SHA256, and RoT `Fresh` epoch sealing interface |
| [crypto_core.c](../storage/src/crypto_core.c) | Self-contained C17 cryptographic primitives linked by `checkpoint.c` |
| [test_semantic_checkpoint.py](../tools/tests/test_semantic_checkpoint.py) | Pure-Python reference oracle, proof-surface checks, Clang/GCC ASan+UBSan builds, and compiled behavioral mutants |

## Validation

Run the behavioral suite (Python oracle + proof-surface checks on both platforms,
plus Clang strict C17, GCC C17 ASan/UBSan, and compiled behavioral mutants in WSL):

```sh
python tools/run.py test --only test_semantic_checkpoint
```
