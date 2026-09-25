# Sail unit tests

`unit_tests` runs the generated harness for the Sail tests in
[`model/unit_tests`](../../model/unit_tests/). Native C++ harnesses in this
directory also call the actual generated Sail model:

- `entropy_observer` checks the entropy-root callback boundary.
- `watchdog_join` drives the RoT watchdog's external slow clock from the
  emulator's own platform-layer source
  ([`rot_slow_clock.h`](../../c_emulator/rot_slow_clock.h)) and follows the
  latched bite to the die reset, with a stopped petter, a stopped main clock,
  a detached-clock control and two deliberately inverted expectations.
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

`block_payload` and `block_reset` implement the scoped
[M5.3 prerequisite predicates](../../../docs/implementation/contracts/block-device-prerequisites.md).
They establish finite modeled behavior, not host-image persistence or complete
storage acceptance. `block_image` covers host-image persistence for the admitted
fixture only; it supplies no architectural HTIF case or storage acceptance.
Every deliberately wrong expectation must be rejected.

From the repository root, run `python tools/run.py model build --background`
and then `python tools/run.py model wait`. The canonical build registers these
harnesses with CTest and includes their verdicts in its result.
