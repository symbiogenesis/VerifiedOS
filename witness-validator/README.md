# Local Witness-Evidence Validator

`witness-validator/` implements the bounded, GC-free C17 local witness-evidence
parser and validator for M6.2c, aligned with
[WitnessContinuity.v](../proofs/WitnessContinuity.v),
[witness-policy-qualification.md](../docs/assurance/witness-policy-qualification.md),
and [witness.py](../tools/vos/witness.py).
[The public header](include/vos_witness_validator.h) defines fixed-capacity
records, error codes, and validation entry points;
[witness_validator.c](src/witness_validator.c) links against
[crypto_core.c](../storage/src/crypto_core.c) via
[vos_crypto_core.h](../storage/include/vos_crypto_core.h) for SHA-256 and
HMAC-SHA-256.

## Canonical wire formats and invariants

- **`VOSWTP01` (`vos_wv_parse_policy`, `vos_wv_policy_is_safe`)**: Enforces
  non-zero `trust_scope`, `1 <= K <= N <= VOS_WV_MAX_WITNESSES`, `0 <= f < N`,
  pairwise distinct `witness_id`s, non-zero pairwise distinct 32-byte
  `verify_key`s, exact byte consumption (`VOS_WV_ERR_TRAILING_BYTES`), and
  flat-policy intersection safety `2 * K > N + f` (refusing `1-of-2` even when
  all signatures authenticate).
- **`VOSWTC01` (`vos_wv_parse_checkpoint`)**: Parses bounded ordered log entry
  digests (`<= VOS_WV_MAX_CHECKPOINT_ENTRIES`) and rejects truncated or trailing
  bytes.
- **`VOSWIT01` / `VOSWTS01` (`vos_wv_parse_signature`, `vos_wv_parse_certificate`, `vos_wv_verify_certificate`)**:
  Binds `stmt_kind` (`VOS_WV_STMT_PLAIN` or `VOS_WV_STMT_TERMINAL`),
  `trust_scope`, `epoch`, canonical policy digest, checkpoint digest, transition
  digest, enrolled `signer_id`, enrolled 32-byte `signer_key`, and canonical
  HMAC-SHA-256 MAC. Refuses duplicate, foreign, wrong-key, misbound, forged,
  and padded extra signatures even after `K` valid signers have appeared.
- **`vos_wv_admit`**: Verifies certificate quorum, prefix consistency against
  `client->pinned`, and inclusion of both `base_image_root` and every required
  `package_ids[i]`. Refusal leaves `client` (including `pinned` and
  `running_generation`) byte-identical.
- **`VOSWTT01` (`vos_wv_parse_transition`, `vos_wv_transition`)**: Enforces
  matching `old_policy`, continuous same-scope consecutive-epoch transition
  (`epoch + 1`, both policies safe), anchor extension from `client->pinned`,
  old-policy `VOS_WV_STMT_TERMINAL` seal quorum bound to the exact transition,
  and new-policy anchor quorum before updating policy and pin together.
- **`VOSWTR01` (`vos_wv_parse_rebootstrap`, `vos_wv_rebootstrap`)**: Verifies
  bootstrap-authority HMAC-SHA-256 over the full replacement decision, non-empty
  non-whitespace assumptions, safe replacement policy, fresh unused
  `trust_scope` (refusing `A -> B -> A` scope reuse), and new-policy anchor
  quorum while recording `continuity_preserved = 0`.

## Validation

Run `python tools/run.py test --only test_witness_validator_c` on Windows
(pure-Python oracle and C17/SPDX source checks) and
`python3 tools/run.py test --only test_witness_validator_c` in WSL Linux (also
compiling with strict Clang C17, GCC C17 ASan/UBSan, and running all compiled
behavioral mutation controls).
