# Bounded C17 attested TLS session-custody vault

[session_custody.c](src/session_custody.c) implements the bounded, GC-free C17
protected TLS 1.3 session-context and key-custody vault (`vos_sc_vault` and
`vos_sc_session`) bridging [crypto_core.c](../storage/src/crypto_core.c) and
[attested_tls.c](../attested-tls/src/attested_tls.c), modeled in
[AttestedCustodyBridge.v](../proofs/AttestedCustodyBridge.v),
[AttestedSession.v](../proofs/AttestedSession.v),
[CredentialHandles.v](../proofs/CredentialHandles.v), and
[attested-tls-protocol.md](../docs/implementation/attested-tls-protocol.md).
[The public header](include/vos_session_custody.h) declares the opaque handle
structures, status codes, and vault/session entry points, linking against
[vos_attested_tls.h](../attested-tls/include/vos_attested_tls.h) and
[vos_crypto_core.h](../storage/include/vos_crypto_core.h).

## Custody and protocol boundaries

- **Protected TLS context registration (`vos_sc_register_tls_context`)**: Admits
  only completed, server-authenticated, non-resumed, non-early-data TLS 1.3
  contexts whose configuration digest matches `expected_config_digest` and whose
  traffic-key custody is non-zero. Internally derives the 32-byte
  `EXPORTER-Channel-Binding` (empty context) via `vos_hmac_sha256` from the
  protected traffic key and seals an opaque MAC-authenticated
  `vos_sc_context_handle`.
- **Authenticated credential binding (`vos_sc_quote_session`)**: Accepts no
  caller-supplied exporter argument. Authenticates both the opaque context handle
  and the delegated or root `vos_sc_cred_handle`, enforces unit ownership and
  seven-part account ceilings, and drives `vos_atls_issue_local`.
- **Monotonic teardown and spent-context enforcement (`vos_sc_teardown_context`,
  `vos_sc_advance_lifecycle`, `vos_sc_retire_unit_generation`,
  `vos_sc_session_reconnect`)**: Wipes traffic keys and derived exporters on
  teardown, retires active handles on generation or lifecycle changes, rejects
  cross-unit alias collisions, and retains spent context identities across
  reconnects so A-to-B-to-A reuse fails even with a fresh nonce.
- **Authenticated session flow (`vos_sc_session_open`, `vos_sc_session_begin`,
  `vos_sc_session_decide`, `vos_sc_session_fetch_one`, `vos_sc_session_close`)**:
  Binds the relying-party session to the expected configuration digest, active
  vault epoch, and protected `attested-tls` state machine with no unauthenticated
  object-fetch fallback.

## Validation

Run `python tools/run.py test --only test_attested_custody_bridge` on Windows
(pure-Python reference oracle and proof-surface checks) and
`python3 tools/run.py test --only test_attested_custody_bridge` in WSL Linux
(compiling `src/session_custody.c`, `../attested-tls/src/attested_tls.c`,
`../storage/src/crypto_core.c`, and `test/test_session_custody.c` with Clang
C17 strict and GCC ASan/UBSan and killing compiled behavioral mutants), as
orchestrated by [test_attested_custody_bridge.py](../tools/tests/test_attested_custody_bridge.py).
