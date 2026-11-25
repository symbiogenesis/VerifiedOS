# Sail unit tests

`unit_tests` runs the generated harness for the Sail tests in
[`model/unit_tests`](../../model/unit_tests/). Separate native harnesses
exercise model integration and individual components:

- `entropy_observer` checks the entropy-root callback boundary.
- `watchdog_join` drives the RoT watchdog's external slow clock from the
  emulator's own platform-layer source
  ([`rot_slow_clock.h`](../../c_emulator/rot_slow_clock.h)) and follows the
  latched bite to the die reset, with a stopped petter, a stopped main clock,
  a detached-clock control and two deliberately inverted expectations.
- `boot_control` runs the RoT boot-control window's Sail properties under
  [`verifiedos-rot.json`](../../config/verifiedos-rot.json) and under a variant
  whose latch, slot and attempt count are not zero, holds the power-on state
  against the variant, checks the validator's four refusals, and carries one
  deliberately inverted expectation.
- `block_payload` generates byte/bit-distinguishing PIO payload and incomplete
  staging cases from the admitted block geometry.
- `block_reset` enumerates command progress and reset boundaries, tear masks,
  volatile-state clearing and stale-response refusals.
- `block_image` binds the device to the emulator's host image adapter
  ([`blkdev_image.h`](../../c_emulator/blkdev_image.h)) and checks the image
  file and a fresh reopen across real process exits: completed and unobserved
  writes, lost incomplete work, reset and error tears, media faults, a host
  write failure, startup refusals and the emulator's image options. Its two
  inverted expectations must fail at the reopened-medium comparison.
- `block_receipt` checks startup, persistence and close failures when a requested
  receipt cannot be written. It checks the host adapter directly, including
  sticky failure and reopening the bytes persisted before a receipt failure.
- `cli_unsigned_parser` checks the emulator's unsigned argument conversion and
  exit status without initializing the Sail model.
- `bf16_nan` checks all BF16 bit patterns against the vendored SoftFloat NaN
  classification macro.

`block_payload` and `block_reset` cover the finite modeled behavior in the
[M5.3 prerequisite predicates](../../../docs/implementation/contracts/block-device-prerequisites.md).
`block_image` adds host-image persistence evidence for the admitted fixture.
Every deliberately wrong expectation must be rejected.

The canonical model build records the CTest verdict with its build receipt.
The [check schedule](../../../tools/README.md#check-scheduling-during-fan-out)
governs focused local feedback and hosted validation.
