# Kernel instance

The GC-free C of one isolated kernel instance, M4.4 in the [implementation checklist](../docs/implementation/implementation-checklist.md). It is authored against the Gallina statements [PartitionContext.v](../proofs/PartitionContext.v), [CyclicExecutive.v](../proofs/CyclicExecutive.v) and [KernelInstance.v](../proofs/KernelInstance.v), under M4.1b's ruling that the kernel C is authored rather than started from CHERI-seL4. Nothing here derives from seL4 or CHERI-seL4. The [service-authoring contract](../docs/implementation/contracts/service-authoring.md#2-single-kernel-instance) and the [scalar ABI](../docs/implementation/contracts/purecap-abi.md) govern its interfaces.

The accepted contained compiler builds the actual C readers, context image, executive and target adapter into a two-partition C-class composition. [The target runner](../tools/vos/kernel_target.py) authenticates its release with the real SLH verifier, executes the firmware handoff and kernel on Sail, and checks bounds, complete restoration, semantic completion and table order. The RoT C executes on the host in this experiment; the report keeps that executor boundary explicit. [The corpus member](../corpus/kernel-instance.s) replays the exact released memory and handoff record. General restoration, restart and extended executive duties remain open below.

## What each file owns

| File | What it implements | What holds it on the host |
| --- | --- | --- |
| [include/vos_kernel.h](include/vos_kernel.h) | The records: slot, frame, executive cursor, CSR roster, machine, context, completion, extent, partition and initialization records, and their build-time capacities | The Gallina records `Slot`, `Frame`, `Machine`, `Context`, `Completion` and `Extent` it mirrors |
| [include/vos_platform.h](include/vos_platform.h) | The one difference between the two builds: a saved register is a pointer-typed capability slot on the target and a value/tag pair in the host model | `Word * bool` of PartitionContext.v's merged file |
| [src/executive.c](src/executive.c) | The table-driven cyclic executive for one table with one tenant per slot: the time-to-slot map, the consumer's structural table checks, and the cursor that releases each table entry at its table instant | Generated `kx` lines for `slot_index_at`, `disjoint`, `pairwise_disjoint`, `total_width` and the in-frame conjunct of `slot_fits`; the release instants are the harness's own expectation from R-11-014a and R-11-014d, since CyclicExecutive.v defines none |
| [src/context.c](src/context.c) | The image a switch installs and the image a same-label rotation installs; the pending arms; semantic completion; in the host model only, the revocation filter and the sanitized-image dispatch check | Generated `kc`, `kr` and `kq` lines for `canonical_post`, `Switch`, `Rotation`, `pending_written`, `SemanticCompletion`, `filtered` and `ImageIsSanitized` |
| [src/partition.c](src/partition.c) | Partition root handling over the consumer's initialization record: the refusals the ABI's section 7 names, extent containment, one partition per tenant, and the readability of the declared extents | Generated `ke` lines for `within`, `extent_eqb`, `separated`, `compatible` and `ExtentsAreReadable`; the section 7 refusals, containment and the one-partition-per-tenant refusal only by fixed controls |
| [include/vos_handoff.h](include/vos_handoff.h) and [src/handoff.c](src/handoff.c) | Bounded field-by-field readers for the `c11` record and `c12` initialization bytes, using [vos_boot.h](../firmware/include/vos_boot.h)'s layout constants; save-area declarations are retained beside the consumer record | [test/handoff.c](test/handoff.c)'s fixed controls, including the actual assembled firmware fixture's empty schedule refusal |
| [test/host_vectors.c](test/host_vectors.c) | The host-model differential over [KernelVectors.v](../tools/quickchick/KernelVectors.v)'s `kx`, `kc`, `kr`, `kq` and `ke` families, the release expectations, and the fixed consumer refusal controls, each counted apart | n/a |
| [test/target_selfcheck.c](test/target_selfcheck.c) | One translation unit for the contained compiler's program loop | n/a |
| [vos/kernel_restore.py](../tools/vos/kernel_restore.py) | Scalar final restore emission and generated target controls, with distinct setup, restore and dispatch extents | [test_kernel_restore.py](../tools/tests/test_kernel_restore.py) checks assembler acceptance, missing observations, exact write multiplicity and stale build refusal; `kernel restore` checks actual emulator traces and in-program HTIF controls |
| [include/vos_target.h](include/vos_target.h), [src/target.c](src/target.c), [test/target_unit.c](test/target_unit.c) and [vos/kernel_target.py](../tools/vos/kernel_target.py) | The exact scalar composition, actual byte readers and C switch/executive joined to assembly entry and final restore | `kernel target` runs the signed composition and executable defects on Sail |

`python tools/run.py kernel check` runs the host differential and the trace reader's; `python tools/run.py kernel mutants` runs the authored defects through both and credits each kill to the kind of expectation that decided it: a Gallina vector, a fixed consumer control, or the harness's release expectation. The [tool guide](../tools/README.md) lists the command.

On Linux, `python3 tools/run.py test --only kernelhandoff` compiles the separate
handoff controls with warnings as errors, AddressSanitizer and UndefinedBehaviorSanitizer.
Ubuntu Host CI runs that test; its Windows counterpart skips the native C case.
It covers valid minimal and full-capacity descriptors, every truncated prefix,
overlong spans, malformed headers, oversized counts and narrowed integers,
non-Boolean flags, invalid extents, missing save areas and unknown tenants.
Every refusal leaves the destination unchanged. The boot reader preserves all
measurement fields and refuses nonzero reserved bytes; reading a record supplies
no authentication or fresh entropy verdict. Both readers require a stable readable
span whose actual bounds the caller has established. The target entry adapter
supplies these spans after checking the read-only handoff capabilities.

## Choices this code takes that the statements do not

- **The CSR roster is an input.** R-07-015's restore quantifies over every CSR a partition can name, and no artifact enumerates that bank (KernelInstance.v gap b). The switch therefore walks a composition-supplied roster with each row's disposition and names no CSR itself.
- **The static pending arm is a mask.** PartitionContext.v leaves `pending_partition` unconstrained; the host model realizes it as the successor's bits under a composition mask.
- **Two table refusals are the consumer's own.** A zero-width slot, which the time-to-slot map can never select, and a table whose list order is not its time order. The second exists because KernelInstance.v's `SwitchesInTableOrder` reads the table in list order while `admits` admits any order; a time-driven executive over a table listed out of time order would fail the frame clause without making a runtime decision.
- **A tenant is one partition.** Each record declares one partition, with one text extent, per tenant, and a record giving two partitions one tenant is refused rather than validated through its first member. R-07-037b's same-label groups and R-07-037e's elastic domains are therefore refused, not served.
- **The capacities are build constants.** `VOS_MAX_SLOTS`, `VOS_MAX_PARTITIONS`, `VOS_MAX_CSRS` and `VOS_MAX_WINDOWS` size the records, and a build supplies each for its composition; a record needing more is refused. No register entry bounds any of them. The header's defaults serve the host model and the smoke: 64 slots cover R-11-021's reference top rung of 32 tenants with R-11-022a's second focus slot and a reserved band of up to 31 slots, whose size R-11-020 does not state; the roster and window defaults answer to no entry at all (KernelInstance.v gaps b and f).
- **A stale saved image is refused before dispatch.** The host model checks KernelInstance.v gap a's barrier-sanitizes arm. The finite target composition publishes the bitmap bit, clears the resident source and consumes the model's defined filtered load before invoking the real semantic-completion predicate. A failed completion terminates this bounded observation through HTIF; general recovery policy remains open.

## What is not here, and who supplies it

- **The general restore and dispatch sequence.** The scalar emitter below owns register placement, MEPCC installation, `fence.t` and `mret` for the C-class subset with no nameable CSR. General CSR writes, V/M `vmclear` and pending-state installation remain owed. The target adapter checks the compiled C layout before using its merged-register prefix and writes the separate MEPCC transfer slot explicitly.
- **General trap entry and restart.** The finite composition installs and observes actual timer boundaries and dispatches each initial context once. Saving and resuming arbitrary outgoing state, crash-only restart and the protected switcher frames the ABI's section 4 assigns to M4.4 remain open.
- **The executive's other duties.** R-11-023's slot-to-tenant permutation, R-11-024's table swap, R-07-037b's group rotation dispatch and R-07-037g's elastic dispatch are not implemented. `vos_rotation_image` is R-07-037b's step between members of one group and never zeroizes; R-07-037g's cross-application `vmclear`, which PartitionContext.v's `Rotation` does not state either, is not here. The M4.4 member must therefore compose single-partition tenants.
- **The full RoT target executor.** The finite runner consumes the actual firmware-owned handoff and validates tags, sealing, bounds, cursor and permissions before C access. It runs the real signature verifier and release source on the host; executing that RoT source on the modeled RoT remains M3.5's obligation.

## Bounded scalar effects and fault restart

[include/vos_effects.h](include/vos_effects.h) and
[src/effects.c](src/effects.c) bind serialized grant snapshots, acknowledged
runnable-state installation, sticky notification hints, one synchronous copy
invocation, bounded private-frame storage and ownership-closed retirement.
`poll_hint` records the notification protocol only; it never blocks a partition,
changes its runnable status or creates a blocked queue. The caller returns a quiet
poll to its admitted synchronous yield site.

The authenticated composition supplies disjoint private spans, capability slots,
root capabilities and exact revocation masks. `vos_kernel_own` binds the actual
external service storage, including up to the copy service's 524288-byte composed
region, and retirement clears every declared byte and capability slot. These
bounds and ownership declarations require actual target producer validation;
passing a C pointer is not that evidence. Manifest authority edges close the
victim set even when the current grant table happens to be empty. Active copy
work, loans, devices, epoch exhaustion and an open holder set refuse teardown.

Old allocation masks remain set. Completed teardown marks the victim as needing
replacement, and every start refuses until `vos_kernel_replenish` installs a
composition-supplied fresh allocation at the current epoch. Replacement masks
must be disjoint from all retired bits and every still-current allocation. Only
then does the snapshot make those unit IDs grantable again, so a restarted storage
service receives the new crypto authority instead of silently losing its manifest
edge or receiving the retired root. Pool exhaustion refuses. The target producer
must validate actual replacement roots against those fresh masks; this C API does
not mint authority, clear the bitmap or establish an unobserved sweep.

The direct typed C path uses one-use hardware observation tickets. Assembly
preflights retirement, publishes the actual bitmap, reads it back and acknowledges
the same mask and epoch; C consumes the ticket. A missing publication or resident
scrub leaves retirement pending and prevents a new start. Hardware clock samples
carry the current epoch and delay, reject backwards or replayed time, and are
consumed once. The host callback table implements the same boundaries using
volatile accesses; `VOS_EFFECTS_TYPED` omits that host-only table because the
contained scalar backend rejects volatile operations and a global function table.
The direct C functions remain identical in both builds. Every loop has a fixed
composition bound. A successful start means the exact current grant slots and
runnable state are installed; observing the service's actual first entry remains
the composition runner's duty.

[vos/kernel_effects.py](../tools/vos/kernel_effects.py) owns reusable trusted
assembly adapters for actual bitmap publication and bounded clock polling. Its
trap saver exchanges the outgoing `c31` through MTDC, saves all 32 merged values
and tags, recovers that original `c31`, reinstalls MTDC and saves the interrupted
MEPCC. The architectural trap-live guard owns the temporary exchange's nested
fault exclusion. The following scrub retains only the new private trap root.
This is crash-only handling: it destroys the abandoned image and never resumes
an outgoing PCC or partially completed store.

`python tools/run.py kernel effects --simulator PATH --build-receipt FILE`
runs a reset-root C-class experiment with actual capability faults, two dirty
256-byte private frames, actual bitmap publication, complete data/tag cleanup,
and fresh-entry restart. Trace observations decide exact save multiplicity,
values and tags, saved MEPCC, restored MTDC, all-register scrub and the fresh
image. Missing, tagless and corrupted bootstrap saves and a missing scrub retain
HTIF success but fail their trace obligations; stale saved/frame slots fail the
in-program zeroization check. Every campaign binds its sources, model build,
simulator and traces, and begins with an incomplete receipt.

The native [effect controls](test/effects.c) exercise real host storage and the
host callback adapter, including the whole external copy-size span, with the
hardware observations declared as mocked. The contained compiler builds and runs
[test/effects_target_unit.c](test/effects_target_unit.c)'s actual C transition
controls on Sail, with three declared units and local bitmap/clock objects. This
component does not supply authenticated hardware roots. The assembly experiment
does not execute an exported sentry switcher or a full supervisor/copy boot.
`python tools/run.py kernel protected` takes the accepted contained compiler,
its configuration, its `run_timer.py` runner, the simulator and current model-build
receipt. It runs the actual unmodified depth-two compiler producer, its selected
timer cuts and executable refusal/retention controls in native lane directories.
No contained implementation source or generated compiler output is incorporated
into this tree. The public observer independently requires both real private
frames to be running at the innermost cut, observes three tagged return holders,
and checks the old full words disappear from registers, specials and memory when
the actual activation stacks/private storage are cleared before fresh entry.

That campaign uses the producer's fixed `main`/`service`/`leaf` fixture, two
256-byte protected frames and three 128-byte stacks. It checks real comparator
cuts through each selected phase, clear and cleanup population and old/pop-phase
refusals. It is not an arbitrary-roster producer, a proof of all authority ancestry
or physical WCET: the declared release delay uses an explicit one-instruction
clock profile. Joining those actual protected-frame mechanisms to the real
supervisor/copy/storage composition remains M4.4b-i's duty. The finite C frame
reserve/pop helpers alone do not establish that full ABI.

## Finite compiled target

`python tools/run.py kernel target --ccomp PATH --ccomp-arg=ARG --simulator PATH
--build-receipt FILE --out DIR` compiles [test/target_unit.c](test/target_unit.c),
signs its exact composed payload, consumes the actual RoT release bytes and runs
the firmware handoff and kernel on Sail. Compiler configuration and runtime inputs,
source closures, simulator/build receipt, host release compiler/binary, released
payload, record, measurement registers and traces are bound before and after the
campaign. An output lock and incomplete/failed status prevent stale success reuse.

The composition owner in `kernel_target.py` declares two partitions, two slots,
three shared windows and no reachable partition CSR or pending state. Firmware
supplies exact kernel-data, timer, partition-execute and bitmap-word roots. Entry
checks those capabilities, the stack, PCC, MTCC and MTDC, and compares the descriptor
with the exact generated composition before its actual C reader accepts it. A
different valid descriptor is refused, including changed data extents or widths.
Each successor PCC lacks access-system-registers. Its image contains a tagged,
partition-bounded c3, a nonzero untagged c7 marker and no timer or kernel roots.

The declared retired-capability population is one initially tagged saved c4 and its sole
temporary source c20. The exact eight-byte object occupies one capability granule
at a 64-byte aligned location and is seeded once. The model's profile and capability
granule select one exact eight-byte bitmap word. Publication ORs the object's bit
into the existing word, preserving other retired bits. After publication, the source is
cleared, the saved copy is loaded through the actual load filter, and its physical
memory tag is checked. Those observations feed `vos_semantic_completion`; the
epoch alone is insufficient. Borrowed and device/proxy populations are explicitly
empty, and no asynchronous invocation exists. The kernel retains its broader data
root through MTDC, the root table and derived register/protected-frame copies.
The completion witness therefore assumes this fixed trusted kernel never recreates
or regrants retired authority. The trace checks the sole mint occurs before
publication, the original tagged representation is not reintroduced and no later
memory access addresses the retired object. These finite checks do not prove the
premise for arbitrary kernel code or establish TAL admission. This is a qualified
single-hart join, not a general sweep, loan cancellation or proxy protocol.

The reader captures each selected input image before `vos_target_switch`, compares
the C output with that independent input and uses the scalar protocol checker on
each contiguous MEPCC/restore/fence/dispatch transfer. Two real timer interrupts
drive the C table cursor through one frame. The run decides order, not duration.
Fourteen executable controls cover missing/swapped/overbroad/wrong-permission roots,
a sealed execute root, stack/MTDC substitutions, changed descriptors, resident or
saved stale copies, epoch-only completion, a missing fence and a separately compiled
wrong C register copy. The last two retain HTIF success and must fail their specific
trace obligations; compilation failures receive no kill credit.

`--export corpus/kernel-instance.s` writes the frozen corpus member only
after the complete campaign passes. `--check corpus/kernel-instance.s`
repeats the campaign and requires byte-identical generated source. The snapshot
assembler must reproduce every released byte and symbol, including zero padding
and the boot record. Its assembly is independently authored client C output and
authored adapters, with no compiler/runtime library code or private signing keys.
The containing compiler build remains in its native lane. `run.py model corpus`
admits this member under the ordinary terminal HTIF contract; `kernel target`
supplies its additional typed-trace observations and signed-release provenance.

## Scalar final restore

[vos/kernel_restore.py](../tools/vos/kernel_restore.py)'s `emit` owns a final
restore primitive for the C class with an empty partition-nameable CSR roster.
The model's [CSR access check](../model/model/core/ext_regs.sail) denies every
scalar CSR access to a successor PCC without access-system-registers permission.
The emitter refuses V/M classes and nonempty rosters. This subset does not decide
the general CSR roster, implicit vector CSR writes, or out-of-file capability and
pending-state obligations.

On entry, `c31` points at a stable kernel-owned image containing 32 eight-byte
capability slots followed by the successor MEPCC at byte 256. The complete image
occupies 264 bytes. This is a separate transfer layout, not a C struct overlay of
`vos_context`: that record has CSR fields after its merged-register file. The
caller must construct the image and establish readable bounds, a null slot zero,
successor confinement, a PCC without access-system-registers, and the revocation,
timer and trap-state prerequisites before entry. The generated test harness
constructs that image directly with capability stores. It supplies no firmware
handoff or C-to-primitive binding.

Setup reads the saved MEPCC through `c30` and installs it. The declared restore
extent then loads `c1` through `c31` once each, in order, keeping `c31` as the image
base until its own final load, and executes `fence.t`. The separate dispatch
extent contains `mret`; its `mstatus` write is observed there, outside the register
restore extent. The primitive preserves tags through capability loads, has no
ordinary call continuation, and never uses a restored register as scratch.
Architectural `x0` remains the null zero register and supplies no trace write.

`python tools/run.py kernel restore --simulator PATH --build-receipt FILE`
assembles and executes generated controls on the golden emulator. The required
successful model-build receipt binds the simulator's bytes and all current model
source bytes. The report retains that receipt's identity, source and profile
snapshots, each source/ELF/trace identity, declared extents, process return codes,
HTIF results and individual observations. A changed input during the campaign
refuses the aggregate result. The command compares the exported model-source and
simulator join; it does not revalidate the original build tree's other artifacts
or installed build tools.

Each positive control stores a different mixed tagged/untagged image, captures all
restored registers before using scratch, and compares the captured words and tags
with the saved image in-program. The trace reader independently compares the
actual input stores with the actual ordered restore writes, including the final
`c31`, and checks MEPCC installation and `mret`'s effects. Omitted `x17`, lost `c3`
tag, early image-base restoration and omitted `mret` controls must produce their
specific HTIF refusals. A duplicate register load and an omitted fence retain HTIF
success and must fail their trace obligations, so equal final values cannot
conceal those defects. These controls exercise the emitted primitive on the
target; they do not establish a kernel boot, schedule, static duration or semantic
revocation completion. Every report keeps M4.4 acceptance open.

## Under the contained compiler

[test/target_selfcheck.c](test/target_selfcheck.c) and [test/target_handoff_selfcheck.c](test/target_handoff_selfcheck.c) compile through M1.2f's existing `run.py compiler-diff program` driver with the accepted contained compiler in its typed scalar mode. They run under that driver's harness and supply component feedback. The finite target command above compiles the full [test/target_unit.c](test/target_unit.c) and supplies the real handoff, timer and dispatch join. Two earlier typed scalar refusals shape the source and remain compiler-owner issues:

- **A pointer result that is null on one path and an address on another is refused.** A static function with an `if (...) { return 0; } return p;` shape fails at LTL with *use of undefined, overlapping or inconsistent location*, and comparing such a result with a live address fails at Clight with *comparison requires one retained source allocation or null*. `partition.c` therefore returns a partition index rather than an optional extent pointer.
- **A `void *` slot holding a stack object's capability is refused** with *missing or incompatible retained object origin*, although the source-value contract admits an object pointer through `void *` and back. `void *` is the one C type that can hold any saved capability, so the smoke names a typed slot through `VOS_TARGET_SLOT` and the kernel's own slot type stays `void *`.

## Supervisor lifecycle boundary

[lifecycle.c](src/lifecycle.c) consumes the supervisor's generated scalar request
layout under the [context-slot contract](../docs/implementation/contracts/supervisor-context.md).
It decodes bytes without C struct overlays, validates the entire ordered start
batch before effects, consumes definitive malformed requests and preserves the
last watermark for zero, replay, gaps and sequence exhaustion. Initial bring-up
is one-use; later starts require completed retirement and fresh roots.

The entry points are kernel-private. Trusted assembly owns actual bitmap
publication/readback, architectural holder teardown, authentic fresh-root checks
and clock samples. A completion deadline is anchored after clearing and
replenishment. The consumer never spins during backoff. Start serialization stays
held until assembly publishes the acknowledgment fields and sequence, then calls
`published` before dispatch. Empty boundaries refresh the clock and snapshot
without claiming a new effect.

`python tools/run.py test --only test_kernel_lifecycle` exercises the finite
native decision/refusal controls. [The typed unit](test/lifecycle_target_unit.c)
also lowers and runs on the accepted scalar target. Its local hardware
observations are component inputs, not evidence of a composed timer boundary or
ownership closure. The real supervisor/copy, privilege, fixed-release and
fault/restart joins remain M4.4b-i and M7.1a obligations.

## Licensing

The C sources are original files under `Apache-2.0` and this document is under `CC-BY-4.0`, by the path map in [COPYRIGHT.md](../COPYRIGHT.md).
