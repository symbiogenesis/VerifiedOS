# Kernel instance

The GC-free C of one isolated kernel instance, M4.4 in the [implementation checklist](../docs/implementation/implementation-checklist.md). It is authored against the Gallina statements [PartitionContext.v](../proofs/PartitionContext.v), [CyclicExecutive.v](../proofs/CyclicExecutive.v) and [KernelInstance.v](../proofs/KernelInstance.v), under M4.1b's ruling that the kernel C is authored rather than started from CHERI-seL4. Nothing here derives from seL4 or CHERI-seL4. The [service-authoring contract](../docs/implementation/contracts/service-authoring.md#2-single-kernel-instance) and the [scalar ABI](../docs/implementation/contracts/purecap-abi.md) govern its interfaces.

**The target build is unbuilt.** Every file here compiles in a host model and is checked there against generated Gallina vectors. No accepted purecap backend has compiled it, no image containing it has booted on the emulator, and no corpus member exercises it. A green host check is agreement with the Gallina definitions at generated points and nothing more.

## What each file owns

| File | What it implements | Gallina it answers to |
| --- | --- | --- |
| [include/vos_kernel.h](include/vos_kernel.h) | The records: slot, frame, executive cursor, CSR roster, machine, context, completion, extent, partition and initialization descriptors | `Slot`, `Frame`, `Machine`, `Context`, `Completion`, `Extent` |
| [include/vos_platform.h](include/vos_platform.h) | The one difference between the two builds: a saved register is a pointer-typed capability slot on the target and a value/tag pair in the host model | `Word * bool` of PartitionContext.v's merged file |
| [src/executive.c](src/executive.c) | The table-driven cyclic executive: the time-to-slot map, the consumer's structural table checks, and the cursor that releases each table entry at its table instant | `slot_index_at`, `disjoint`, `pairwise_disjoint`, `total_width`, the in-frame conjunct of `slot_fits` |
| [src/context.c](src/context.c) | The image a switch installs and the image a rotation installs; the pending arms; semantic completion; in the host model, the revocation filter and the sanitized-image dispatch check | `canonical_post`, `Switch`, `Rotation`, `pending_written`, `SemanticCompletion`, `filtered`, `ImageIsSanitized` |
| [src/partition.c](src/partition.c) | Partition root handling over the composed initialization descriptor: the consumer refusals the ABI's section 7 names, extent containment, and the readability of the declared extents | `within`, `separated`, `compatible`, `ExtentsAreReadable` |
| [test/host_vectors.c](test/host_vectors.c) | The host-model differential over [KernelVectors.v](../tools/quickchick/KernelVectors.v)'s `kx`, `kc`, `kr` and `kq` families, and fixed consumer refusal controls | n/a |
| [test/target_selfcheck.c](test/target_selfcheck.c) | One translation unit for the contained compiler's program loop | n/a |

`python tools/run.py kernel check` runs the host differential and the trace reader's; `python tools/run.py kernel mutants` runs the authored defects through both. The [tool guide](../tools/README.md) lists the command.

## Choices this code takes that the statements do not

- **The CSR roster is an input.** R-07-015's restore quantifies over every CSR a partition can name, and no artifact enumerates that bank (KernelInstance.v gap b). The switch therefore walks a composition-supplied roster with each row's disposition and names no CSR itself.
- **The static pending arm is a mask.** PartitionContext.v leaves `pending_partition` unconstrained; the host model realizes it as the successor's bits under a composition mask.
- **Two table refusals are the consumer's own.** A zero-width slot, which the time-to-slot map can never select, and a table whose list order is not its time order. The second exists because KernelInstance.v's `SwitchesInTableOrder` reads the table in list order while `admits` admits any order; a time-driven executive over a table listed out of time order would fail the frame clause without making a runtime decision.
- **A stale saved image is refused, not dispatched.** On an image the barrier did not sanitize, the filtered restore stops satisfying R-07-015 and the faithful one installs stale authority; the host model's dispatch check refuses both.

## What is not here, and who supplies it

- **The restore and dispatch sequence.** The `lc` loads of the merged file, the CSR writes, `vmclear`, `fence.t`, the MEPCC install and the dispatching `mret` are instructions no C statement names. R-05-023b admits a verified component's instructions only through backend primitives, and the ABI names no `mret` primitive and no emitted context-restore rule, so the switch text has no admitted source surface yet. `context.c` computes the image that sequence must install and does not claim the sequence.
- **Trap entry, the boundary timer and restart.** The save phase, R-07-040's boundary handler, the crash-only restart and the protected switcher frames the ABI's section 4 assigns to M4.4 are not written.
- **The target reads of the handoff.** The root-set table in `c10`, the boot descriptor in `c11` and the initialization descriptor in `c12` arrive as capabilities under M3.5's handoff. Their byte layout, the producer's authentication and the primitives that read a capability's tag and base on the target are not fixed, so the target build reads none of them and the revocation observation half is host-model only.
- **The M4.4 corpus member.** [vos/kernelrun.py](../tools/vos/kernelrun.py) reads KernelInstance.v's three questions off an emulator trace and is held to the Gallina predicate over generated traces. The member itself, a composed image that boots under the actual initial capability distribution, attempts the declared over-bound derivations, switches through declared restore text and runs the table, waits on M1.2f's accepted backend, M1.7's target path and M3.5's actual handoff.

## Under the contained compiler

[test/target_selfcheck.c](test/target_selfcheck.c) compiles through M1.2f's existing `run.py compiler-diff program` driver with the contained compiler's recorded master build in its typed scalar mode, and runs under the driver's test harness on the recorded Sail executable. That run is evidence about this program under that harness and says nothing about a kernel instance: there is no firmware handoff, no trap entry and no dispatch in it, and the compiler build is not M1.2f's accepted backend. Two refusals of the typed scalar check shape the source as it stands, and both are returned to the compiler's owner rather than worked around silently:

- **A pointer result that is null on one path and an address on another is refused.** A static function with an `if (...) { return 0; } return p;` shape fails at LTL with *use of undefined, overlapping or inconsistent location*, and comparing such a result with a live address fails at Clight with *comparison requires one retained source allocation or null*. `partition.c` therefore returns a partition index rather than an optional extent pointer.
- **A `void *` slot holding a stack object's capability is refused** with *missing or incompatible retained object origin*, although the source-value contract admits an object pointer through `void *` and back. `void *` is the one C type that can hold any saved capability, so the smoke names a typed slot through `VOS_TARGET_SLOT` and the kernel's own slot type stays `void *`.

## Licensing

The C sources are original files under `Apache-2.0` and this document is under `CC-BY-4.0`, by the path map in [COPYRIGHT.md](../COPYRIGHT.md).
