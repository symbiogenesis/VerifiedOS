# Environmental fault sensors and RoT fail-stop boundary

[env_sensors.c](src/env_sensors.c) implements the bounded, GC-free C17
environmental fault sensor validator and single RoT fail-stop boundary
controller specified in [EnvironmentalSensors.v](../proofs/EnvironmentalSensors.v)
and [the environmental sensor contract](../docs/hardware/environmental-fault-sensors.md).
[The public header](include/vos_env_sensors.h) defines the fixed capacities,
status codes, sensor families, topology descriptors, and entry points.

## Components and invariants

- **`vos_es_validate_sensor` (`R-16-008g`)**: Enforces immutable enable constants,
  no `pending` values, named qualification owner and evidence tuple, non-retired
  artifacts, no software-writable thresholds or disables, no dynamic calibration
  or ISA/CSR additions, OPP-table binding, and family-specific band/margin/pitch
  inequalities (including period/pulse/duty consistency and no backside
  optical occlusion).
- **`vos_es_check_dependencies` (`R-15-196`, `R-16-008g`)**: Verifies all
  dependencies reside in the inventory, rejects self-observation and
  guarded-only liveness justifications, refuses RoT slow-clock self-observation,
  and detects any cycle via bounded iterative 3-color DFS.
- **`vos_es_validate_topology` (`R-15-195`, `R-15-196`, `R-16-008g`)**: Refuses
  empty/incomplete topologies and verifies total coverage over `P` (`RoT`, both
  physical `S0`/`S1` lockstep instances, and all `C`/`V`/`M` islands) for every
  `rails(P)` and `clocks(P)` observation site, every datapath, and every
  gap-free logic-tier region at declared pitch.
- **`vos_es_evaluate_step`, `vos_es_acknowledge_transport`, `vos_es_power_loss`,
  `vos_es_recover_reset`, `vos_es_can_release_island`,
  `vos_es_firmware_consume_event` (`R-15-198`, `R-16-005`, `R-16-008g`,
  `R-17-030m`)**: Latches disabling/corrupt/open/stuck/stopped-reference faults,
  trips unexpected deactivations outside reset-isolated table-off states,
  freezes affected islands behind a persistent software-unmaskable RoT latch,
  fires immediate RoT watchdog bite on RoT/shared trips regardless of RoT CPU,
  main clock, or firmware mailbox state, holds reset across power loss until
  boundary health and reset-table recovery complete, and records only closed
  `vos_es_trip_class` events with recurrent counts.

## Validation

Run `python tools/run.py test --only test_env_sensors` on Windows (pure-Python
oracle and static C17/SPDX/proof checks) and
`python3 tools/run.py test --only test_env_sensors` in WSL Linux (also
compiling [env_sensors.c](src/env_sensors.c) and
[test_env_sensors.c](test/test_env_sensors.c) under Clang strict C17 and GCC
C17 ASan/UBSan and running all compiled behavioral mutation controls).
