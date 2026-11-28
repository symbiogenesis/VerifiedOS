# Same-session Wasm application host

[wasm_host.c](src/wasm_host.c) implements the bounded, GC-free C17 same-session
Wasm application host lifecycle and security-boundary engine specified in
[WasmAppHost.v](../proofs/WasmAppHost.v) and
[the application-host contract](../docs/implementation/contracts/application-host.md).
[The public header](include/vos_wasm_host.h) defines the fixed capacities,
lifecycle phases, status codes, and entry points, linking against
[crypto_core.c](../storage/src/crypto_core.c) via
[vos_crypto_core.h](../storage/include/vos_crypto_core.h) for SHA-256 bundle
and closure digests and HMAC-SHA-256 semantic checkpoint authentication.

## Components and invariants

- **`vos_whost_prepare` (`R-14-013e`, `R-14-013g`, `R-14-013h`)**: Validates the
  canonical closure SHA-256 digest, descriptor SHA-256 digest, Core 3.0 and ABI
  compatibility, and bounded memory/table/stack reservations without executing
  any guest start function or spending new grants; refuses filesystem-path
  authority and leaves any live host running untouched on failure.
- **`vos_whost_launch` (`R-14-013e`, `R-14-013f`, `R-08-047b`)**: Activates a
  prepared bundle into a distinct clear-group host instance (`group_id`) with a
  fresh `act_id` and strictly monotone `epoch`, binds trusted consent to the
  exact `bundle_digest` rather than the guest UI label, and retires the handle
  namespace on epoch exhaustion without wrapping.
- **`vos_whost_invoke_import` (`R-14-013f`, `R-08-047c`)**: Requires an active
  non-cancelling host, binding-scoped handle matching `(act_id, epoch,
  group_id)`, explicit active grant, exact requesting-epoch reply, and tag-free
  transport without elastic-pool capability export.
- **`vos_whost_replace` (`R-14-013f`)**: Enforces two-phase transactional
  replacement: pre-commit refusal leaves the old binding live and usable, while
  post-commit failure closes and sanitizes the host with the candidate's
  acknowledged durable work without mixing bundle A's grants with bundle B's
  execution or durable state.
- **`vos_whost_cancel_begin`, `vos_whost_drain_imports`,
  `vos_whost_enter_sweeping`, `vos_whost_sweep_and_zeroize`,
  `vos_whost_complete_reuse` (`R-08-046`, `R-08-047b`)**: Enforces the
  `Free -> Prepared -> Active -> Cancelling -> Sweeping -> Sanitized -> Reusable`
  barrier, stopping execution and ingress, draining outstanding imports, and
  sweeping and zeroizing host buffers before reuse.
- **`vos_whost_restore` (`R-14-013f`)**: Verifies the checkpoint HMAC-SHA-256,
  bundle digest, ABI, profile, schema, and generation, restoring only with
  current grants and a fresh session key without resurrecting old grants, tagged
  memory, or embedded session keys.

## Validation

Run `python tools/run.py test --only test_wasm_host` on Windows (pure-Python
independent oracle and C17/SPDX/proof/link checks) and
`python3 tools/run.py test --only test_wasm_host` in WSL Linux (also compiling
[wasm_host.c](src/wasm_host.c), [crypto_core.c](../storage/src/crypto_core.c),
and [test_wasm_host.c](test/test_wasm_host.c) under Clang strict C17 and GCC
C17 ASan/UBSan and running all compiled behavioral mutation controls).
