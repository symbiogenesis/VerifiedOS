# Compatibility workflow job service

[compat_workflow.c](src/compat_workflow.c) implements the bounded, GC-free C17
editor-driven native successor-generation workflow service specified in
[CompatibilityWorkflow.v](../proofs/CompatibilityWorkflow.v) and
[the compatibility contract](../docs/implementation/contracts/compatibility.md).
[The public header](include/vos_compat_workflow.h) defines the fixed capacities,
status codes, and 9 explicit-authority operations, linking against
[crypto_core.c](../storage/src/crypto_core.c) via
[vos_crypto_core.h](../storage/include/vos_crypto_core.h) for SHA-256
content-addressed staging and complete proof-cache identity digests.

## Components and invariants

- **9 explicit-authority operations (`R-13-027`, `R-13-027a`, `R-18-004e`)**:
  `vos_compat_read_source_slice`, `vos_compat_stage_edited_source`,
  `vos_compat_submit_build`, `vos_compat_advance_build`,
  `vos_compat_read_diagnostics`, `vos_compat_cancel_build`,
  `vos_compat_submit_successor_admission`,
  `vos_compat_request_generation_consent`, and
  `vos_compat_read_successor_test_result`. Editor and builder hold zero
  execute, signing, mint, sealing, capability-wiring, or boot-selection
  authority.
- **Same-generation native execution refusal (`R-02-008`, `R-13-001a`,
  `R-14-013e`)**: `vos_compat_attempt_forbidden_op` refuses executing staged
  native bytes, rewriting the running roster, installing runtime native
  plugins, loading external helpers by path, bypassing checking, or escaping
  from Wasm into native execution.
- **8 bounded pools & 6-state lifecycle (`R-08-046`)**: validates all 8 pool
  manifest entries (`SourceIndex`, `EditedStaging`, `BuildJobs`, `PassArenas`,
  `DiagnosticsBuffer`, `ProofCache`, `CandidateClosure`, `ConsentTransfer`)
  and enforces `Free -> Bound -> Quiescing -> Revoked -> Sweeping -> Reusable`,
  preventing early reuse on interruption, retiring exhausted epochs without
  wrap, and emitting `VOS_COMPAT_DIAG_TRUNCATED_MARKER` on diagnostics
  overflow.
- **Complete proof-cache keying & `R-12-020` authenticator decline**: keys
  proof cache entries by SHA-256 over source, dependency closure, imported
  lemmas, semantics, configuration, assumption set, and profile ID, never
  bypassing admission, and unconditionally declines external roaming hardware
  authenticators.

## Validation

Run `python tools/run.py test --only test_compat_workflow` on Windows
(pure-Python oracle and C17/SPDX/proof checks) and
`python3 tools/run.py test --only test_compat_workflow` in WSL Linux (also
compiling [compat_workflow.c](src/compat_workflow.c),
[crypto_core.c](../storage/src/crypto_core.c), and
[test_compat_workflow.c](test/test_compat_workflow.c) under Clang strict C17
and GCC C17 ASan/UBSan and running all compiled behavioral mutation controls).
