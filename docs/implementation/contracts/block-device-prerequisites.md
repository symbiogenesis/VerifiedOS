# Block-device execution prerequisites

M5.3a, M5.3b and M5.3c split finite device evidence from M5.3's remaining
storage integration. The [reviewed device contract](../../../interfaces/block-device-contract.md)
owns all behavior. These campaigns add no device semantics or normative claims.
Their acceptance predicates are committed before implementation starts.

## Payload family

M5.3a executes the actual generated Sail model, with enabled device dispatch and
a valid fixture containing at least two blocks. Generate patterns from the
fixture geometry which collectively distinguish every byte location and every
bit, including all-zero, all-one and nonuniform patterns. Exercise full-block
write and read at each selected block, shuffled staging and replacement of an
already written word. Compare every returned byte, cleared load tags, the whole
medium including unselected blocks, and unchanged medium before completion.
Rewriting BLOCK invalidates staging; omitting each staging word in turn refuses
WRITE without medium mutation. A wrong expected byte must fail a comparison.
Bound enumeration by the admitted model geometry and report the actual cases.
This is modeled PIO behavior, not host-image persistence or storage authentication.

## Reset boundaries

M5.3b runs READ, WRITE and FLUSH on the actual generated Sail model. Enumerate
reset before submission, immediately after submission, after every nonfinal
progress event, simultaneous with the final event, and after completion before
status observation or ACK. Include IDLE, validation-error and terminal states.
For pending writes use zero, full and non-prefix masks with distinguishable old
and new bytes; compare the entire medium with `(old & ~mask) | (new & mask)`.
The old bytes are those at the event, including an earlier injected corruption.
READ and FLUSH resets preserve the medium. Every reset clears all volatile state,
advances the association epoch and defeats a canceled response delivered during
and after a new command. Exercise final success and IO error outcomes and verify
reset wins a simultaneous final progress event. Generate boundary counts from
the fixture service bounds. A wrong expected byte or residual volatile field
must fail the campaign's comparison. No process-exit durability is claimed.

## Architectural authority

M5.3c generates purecap assembly from the existing composition, assembler and
profile owners. The real golden emulator runs it through the existing HTIF
corpus path with a nonempty commit trace. Include a valid-authority positive
control and untagged, insufficient-bounds, missing-load and missing-store
capability cases at otherwise valid device accesses. Confirm the observed trap
cause, and verify through a valid capability that refused operations did not
alter control, staging or medium state, using completion/readback when a field
is not directly readable. Distinguishable payloads expose an unintended write.
A case reaching its continuation without the expected refusal must fail HTIF.
Reproduce the generated assembly and reject drift from its inputs; retain the
measured trace manifest and document the corpus member. Architectural refusal
may precede device dispatch, as the device contract permits. This campaign
establishes neither kernel authority distribution nor the two storage instances.

## Integration and evidence

Each worker owns its campaign and runs focused acceptance checks in a dedicated
worktree. Canonical model builds use the existing RelWithDebInfo profile;
`python tools/run.py model build --background` followed by `model wait` supplies
the build verdict. The integrator combines test registration and corpus metadata,
repairs derived artifacts and runs the required stable host wave. Source edits,
case membership, commands, results, elapsed intervals and remaining obligations
are recorded at landing. A failed campaign or unavailable executor keeps its
item open. M5.3d owns the unchanged full storage acceptance boundary.
