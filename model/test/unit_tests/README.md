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

The block campaigns implement the scoped
[M5.3 prerequisite predicates](../../../docs/implementation/contracts/block-device-prerequisites.md).
They establish finite modeled behavior, not host-image persistence or complete
storage acceptance. Their deliberately wrong expectations must be rejected.

From the repository root, run `python tools/run.py model build --background`
and then `python tools/run.py model wait`. The canonical build registers these
harnesses with CTest and includes their verdicts in its result.
