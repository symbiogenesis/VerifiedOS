# Bounded C17 attested TLS application protocol

[attested_tls.c](src/attested_tls.c) implements the bounded, GC-free C17
canonical wire codecs, protected local broker issuance (`vos_atls_issue_local`),
and single-attempt appraiser state machine (`FRESH -> WAITING -> OPEN -> CLOSED`)
modeled in [AttestedSession.v](../proofs/AttestedSession.v),
[CredentialHandles.v](../proofs/CredentialHandles.v), and
[attested-tls-protocol.md](../docs/implementation/attested-tls-protocol.md).
[The public header](include/vos_attested_tls.h) declares the fixed capacities,
status codes, and entry points, linking against
[crypto_core.c](../storage/src/crypto_core.c) (`vos_sha256` and
`vos_hmac_sha256`) declared in [vos_crypto_core.h](../storage/include/vos_crypto_core.h).

## Protocol surfaces

- **Canonical wire codecs**: `Challenge` (`VOSATLC1`, domain
  `VerifiedOS/Q22c/TLS-attestation/v1`), `Evidence` (`VOSATLE1` with
  SHA-256/HMAC-SHA-256 seal), `ObjectFetchRequest` (`VOSATLR1`), and
  `ObjectFetchReply` (`VOSATLP1`). Positive composition bounds are checked
  before parsing, and trailing bytes or non-canonical lengths are refused.
- **Protected local broker issuance (`vos_atls_issue_local`)**: Accepts no
  caller-supplied exporter argument. Reads measured generation, principal,
  origin, exporter, and optional origin-scoped unit alias strictly from the
  protected context and broker state after checking sealed credential custody
  and seven-part authorization, consuming one credential use on success.
- **Single-attempt appraiser (`vos_atls_begin_appraisal`, `vos_atls_decide`,
  `vos_atls_fetch_one`, `vos_atls_reconnect`)**: Enforces complete server-authenticated
  non-early-data non-resumed TLS contexts, spent context-ID and nonce history
  (refusing A-to-B-to-A cycles even with a fresh nonce), strict monotonic
  deadlines (`now < deadline`), software-only vs. origin-scoped unit-alias
  policies, and one bounded fetch before closing with no unauthenticated fallback.

## Validation

Run `python tools/run.py test --only test_attested_tls_c` on Windows (pure-Python
oracle and structural checks) and `python3 tools/run.py test --only test_attested_tls_c`
in WSL Linux (also compiling `src/attested_tls.c`, `../storage/src/crypto_core.c`,
and `test/test_attested_tls.c` with Clang C17 strict and GCC ASan/UBSan and
killing all compiled behavioral mutants), as orchestrated by
[test_attested_tls_c.py](../tools/tests/test_attested_tls_c.py).
