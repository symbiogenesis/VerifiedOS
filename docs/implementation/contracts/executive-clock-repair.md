# Executive clock arithmetic repair

This bounded correction belongs to the single-kernel executive and target
adapter governed by the [service contract](service-authoring.md#2-single-kernel-instance)
and [kernel ABI](purecap-abi.md#7-the-kernel-entry-interface). It changes the
finite C clock representation, not the Gallina schedule or admission policy.
Implementation begins after this contract is committed.

## Clock boundary

A release is the mathematical sum of the composition phase, major-frame index
times major-frame length, and selected slot offset. An accepted C operation
returns that sum only when it fits in `uint64_t`. Zero and `UINT64_MAX` remain
ordinary representable instants; neither is an error sentinel. A separate success
result carries refusal, and a refused operation leaves output storage unchanged.

Frame validation refuses an initial release outside that range. Cursor
advancement refuses a frame-index wrap or an unrepresentable next release and
leaves the cursor unchanged. Reaching the finite clock horizon is an explicit
refusal requiring the caller to stop dispatch; it never schedules a wrapped time.

The target adapter checks the additional sampled timer epoch and slot duration
before publishing a deadline. Its assembly consumer checks success before
writing the timer comparator or restoring and dispatching the successor.

## Acceptance

- Actual C controls preserve ordinary table order, frame advancement and exact
  releases, including a legitimate release at zero and at `UINT64_MAX`.
- The reported phase-plus-offset overflow, major-frame multiplication overflow,
  final addition overflow and frame-index exhaustion each refuse without changing
  output or cursor. Invalid empty/zero-frame and out-of-range cursor inputs refuse.
- Target deadline controls cover epoch and duration overflow and prove a refused
  call leaves its comparator-output storage unchanged. Generated assembly checks
  the status before loading that output and writing the timer comparator.
- Native focused controls compile the authored sources with strict C17 warnings
  and ASan/UBSan on the guest. Focused host controls check the emitted adapter and
  existing call sites. The contained compiler and Sail campaign remain required
  hosted acceptance for changed target inputs; a native pass supplies no target
  or proof verdict.

The [validation handoff](../../../AGENTS.md#tool-execution-and-validation) owns
integration and user-managed hosted checks. This repair adds no dependency,
clock reset policy, wrapped-clock interpretation or new ISA operation.
