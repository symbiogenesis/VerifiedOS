# Purecap ABI and primitive contract

This is the ABI and primitive contract [M1.2d](implementation-checklist.md)
implements and M3.5 and M4.4 author against, the first row of
[the plan's sequencing table](implementation-checklist.md#sequencing). It states
the register roles over the merged file, the frame and the spill discipline over
the plan laid out at composition, the sentry call and return sequences and the
cross-compartment sequence, the float-typed value's route, each primitive
R-05-023b requires with its operand form and emission shape read from the
model's own clause, and the kernel entry interface M3.5 hands M4.4 with what
M4.4's switch restores. Its scalar bring-up convention selects implementation
choices within those obligations so firmware and kernel authors can share one
interface. Those choices are identified below; they do not freeze the production
ABI or close the backend's emission and proof work. Unresolved choices remain in
[the last section](#8-what-the-register-leaves-open).

**Precedence.** The [register](../requirements-register.md) governs; the
[profile](../hardware/isa-profile.md) is its derived view of the ISA; the
meaning of every instruction is its Sail clause and nothing else (R-05-019b,
R-05-023b); the statement artifacts under [proofs/](../../proofs/) fix what the
switch restores and what the handoff supplies; this document is read after all
four and is defective wherever it disagrees with any of them. The start-from is
read last: SECOMP's `riscV/` backend at the pinned gitlink
`5c20b839e556b78c0ee7f1ce5b28fb00d0e69d78`, which is the tree M1.1b names.
M1.2b's partial backend modifies this start-from in the contained repository.
Where the register does not fix a role, this document distinguishes the selected
scalar convention from the start-from and records the remaining production join.

**Sources.** The repository clauses below are the model and register named at
each use; the start-from references are `riscV/Conventions1.v`, `Machregs.v`,
`Asm.v`, `Asmgen.v` and `Stacklayout.v` at the pin above.
M1.2b's partial backend deletes the float bank; its
note in [the checklist](implementation-checklist.md) carries what moved,
and this document cites that note rather than the contained revision where the
two differ.

## 1. The register file and its roles

**One file, 32 registers of 64+1 bits** (R-15-007i,
[reg_type.sail](../../model/model/core/reg_type.sail)). A register's integer
reading is its 64 data bits, its capability reading is the same bits with the
validity tag, and an integer write clears the tag, so reading a register as an
integer and writing it back is the identity on the value and destroys the
authority. There is no capability bank and no instruction moves a value between
banks. The consequence for an ABI is F-000q's: a role assigned to a register is
also an authority discipline, an ABI integer name being an authority destroyer,
so the roles below name which registers may hold authority at a boundary rather
than which bank a value sits in. The dialect provides integer and capability aliases,
`x5`, `t0`, `c5` and `ct0` naming one register
([dialect.py](../../tools/vos/dialect.py)), and the zero register's capability
reading is `cnull`, the null capability the all-zeroes granule decodes as
(R-15-182). The vector file `v0` to `v31` is a second file of `VLEN` bits and
holds no capability.

The architectural roles and start-from that the scalar convention selects from:

| Register | Role | Fixed by |
| --- | --- | --- |
| `x0` / `cnull` | Architectural zero; reads as the null capability | the model (`zero_reg` in [reg_type.sail](../../model/model/core/reg_type.sail)) |
| `x1` / `cra` | The link register: `cjal` and `cjalr` with a non-zero destination write the next instruction's PCC sealed as a backward-edge sentry into it (R-15-068). At reset it holds the store-side root (below), which every corpus member moves out with `cmove c8, c1` before its first call | the model's `link_capability` ([cheri_insts.sail](../../model/model/extensions/CHERI/cheri_insts.sail)) and the dialect's `call` and `ret` expansions ([asm.py](../../tools/vos/asm.py)) |
| `x2` / `csp` | The stack capability. Its permission shape is `perms_stack`, codepoint `0b01001`, the one admitted shape carrying store-local (R-15-074, [cap_common.sail](../../model/model/core/cap_common.sail) line 119), so it is derivable only from the store-side root `root_data_cap`, `candperm` being able only to remove | the permission by R-15-074; the register number by the start-from (`SP := X2`, `Asm.v` line 102) and the psABI, which no entry fixes (gap a) |
| `x3` / `gp`, `x4` / `tp` | Reserved and unused by the start-from (`Machregs.v` lines 30 to 32). No entry names a global-pointer or a thread-pointer role: a global is reached by PCC-relative materialization, `auipcc` then `cincoffset` (R-15-031b), or by the composition-time absolute form R-15-036l decides at the freeze, and no entry names a thread pointer | nothing; the absence is the start-from's and the roles are gap a |
| `x5` to `x7`, `x28` to `x31` / `t0` to `t6` | Caller-clobbered temporaries. `x31` is the assembly generator's reserved scratch, never allocatable (`Machregs.v` lines 33 to 34; `Asmgen.v` materializes immediates, comparisons and global addresses through `X31`). `x5` is destroyed by a jump table (`Machregs.v` line 202). `x30` is the parent-frame temporary, destroyed at function entry, through which a parent's argument is loaded (`Machregs.v` lines 234 to 236, `Asmgen.v` `Mgetparam`) | the start-from; no entry fixes a scratch set, and the second scratch the M1.2 cell's axis 7 asks for is gap b |
| `x8` to `x9`, `x18` to `x27` / `s0` to `s11` | The psABI's callee-saved set, and **at the pin the start-from preserves none of it**: `is_callee_save r` is `false` for every `r`, `int_callee_save_regs` is `nil` and the standard split is commented out (`Conventions1.v` lines 35 to 49 and 67 to 68), so `destroyed_at_call` is every allocatable register. `x8` also spells `fp` and `cfp`, and the start-from keeps no frame pointer, loading the back link through `x30` | the start-from; which convention the purecap backend keeps is gap c |
| `x10` to `x17` / `a0` to `a7` | Arguments in order (`int_param_regs`, `Conventions1.v` line 230) and the result in `x10` (`loc_result`, line 143); a ninth and later argument in an 8-byte outgoing stack slot (`int_arg`, lines 244 to 253); a variadic call's arguments in integer registers then on the stack (lines 211 to 217); an indirect call destroys the eight (`Machregs.v` lines 238 to 239) | the start-from; the float-typed case is [section 5](#5-the-float-typed-values-route) and the roles are gap a |
| `v0` to `v31` | Not in the merged file. The start-from's convention names no vector register, no entry states a preservation rule across a call, and the partition switch zeroizes the file rather than saving it (R-07-014a, R-07-014c) | nothing; gap d |

**Selected scalar convention.** M1.2d's scalar authoring interface retains the
start-from's argument and result locations and its empty callee-saved set.
`x5` through `x30` are caller-clobbered, including every `s` alias; `x31` is
reserved for emission and caller-clobbered; `x3` and `x4` are unavailable to
allocation and carry no ambient global or thread authority. `csp` is restored
with its value and tag on every ordinary return. `cra` is the call's return
sentry, saved with `sc` before any nested call and restored with `lc` before
`ret`. There is no persistent frame-pointer register. A scalar capability or
word result occupies `a0`; the first eight scalar arguments occupy `a0` through
`a7` in signature order, and later arguments occupy successive 8-byte slots in
the caller's outgoing area. Each signature states the value kind, including the
tag requirement; same-width integer and capability values are not interchangeable.
The reviewed scalar subset has no aggregate-return, variadic, vector or
floating-point computation convention; an author needing one rejoins its
backend owner before emission. Section 5 states the required float route.

An ordinary caller spills every value it needs after the call. This deliberately
includes a kernel-entry input in `a0` through `a2`: its boot role does not make
it callee-saved. `x30` remains the transient parent-frame register at entry and
parameter loads. The selected frame sequence below needs only `x31` for a
large size or offset; it adds no second reserved scratch to the allocatable
set. A later emission rule needing simultaneous temporaries owes a fresh
liveness review before changing that set.

The allocatable set at the pin is the 26 integer registers `R5` to `R30` of
`Machregs.v` (the predicate: constructors of `mreg` naming an `X` register), and
M1.2b's partial backend keeps that set with the float constructors deleted. The
reset distribution the roles sit over is the model's: PCC, `nextPCC`, MTCC and
MEPCC start at `default_cap`, the execute-side root carrying access-system-
registers over the whole space, MTDC at the null capability, and `x1` at
`root_data_cap`, the store-side root, with every other register null
([step_ext.sail](../../model/model/postlude/step_ext.sail) lines 31 to 71);
the split is R-15-007l's and R-15-007p's, no admitted permission set holding
both store and execute. Firmware narrows what it is given and installs the
composed distribution (R-07-019, R-07-028); the roles above are what code runs
under after that.

**What the merged file does to the argument registers.** An argument register
carries a capability and an integer alike, and the callee reads which from the
signature rather than from a bank; the route contract's `call` rule fixes the
required and provided ABI and authority at every call
([compiler-route-contract.md](../languages/compiler-route-contract.md)). A
capability argument is a capability in `a0` to `a7` with its tag, and an integer
argument is an untagged register; nothing in the file distinguishes the two but
the tag, which is why a spill of either follows [section 3](#3-the-spill-discipline-and-the-validity-tag)
and not the register's name.

## 2. The frame, laid out at composition

**What the plan lays out and what it does not.** The heap is compiled and no
runtime allocator exists (R-08-010); the whole-program slot plan fixes every
object's slot and live range (R-08-011); stacks and register-save areas are
first-class regions of that plan (R-15-247s, the `Stacks` and
`RegisterSaveAreas` kinds of [MemoryPlan.v](../../proofs/MemoryPlan.v)). A
region carries a base, a length, its base and length in granules and a live
range, and the plan lays **no per-function frame**: the stack a partition or a
compartment runs on is a plan region, and every frame inside it is the backend's
layout, which is what M1.2d owns and the plan does not.

**The start-from's frame.** `make_env` (`Stacklayout.v` lines 43 to 57) lays,
from the lowest offset, the outgoing argument area, the back link, the return
address, the callee-save area (empty at the pin, the set being empty), the
locals and the Cminor stack data, with the frame size aligned to 16 bytes. The
prologue is `Pallocframe sz link_ofs` followed by a store of `RA` at the
return-address offset (`Asmgen.v` lines 940 to 944) and the epilogue reloads
`RA` and issues `Pfreeframe` (lines 838 to 840). `Pallocframe`'s semantics is a
`Mem.alloc` at runtime (`Asm.v` lines 973 to 974), which is the run-time frame
block the M1.2 cell's axis 8 rules a re-homing: in the authored backend the frame
is a span of the stack region the plan laid out, and the pair becomes an address
move on `csp` by a composition-time size, with or without a narrowing.

**What a frame-derived narrowing owes R-15-007k.** Every bounds narrowing the
backend emits is exactly representable, and the obligation falls on the plan
(R-15-007k); `CRAM`, `CRRL` and `CSetBoundsExact` are absent, so exactness is
decided before emission and never reported at runtime. In the plan's own terms
a narrowing is a `Narrowing` record, a region, an offset in granules, a stride
in granules, a dynamic index and a length in granules, and it is `Exact` when
its base is a whole number of that region's granules
([MemoryPlan.v](../../proofs/MemoryPlan.v) lines 2336 to 2363); a quantized
region base narrows exactly at every index (`a_quantized_slot_base_narrows_exactly`,
lines 2370 to 2382) and the plan's own check admits only exact narrowings
(`spec_narrow_ok`, lines 2396 to 2408). A frame carved from `csp` is such a
record over the `Stacks` region: the frame's offset is `offset_granules`, its
size is `length_granules`, and its index is zero. So a frame narrowing is exact
under the plan's rule when the frame's offset and size are whole granules of the
stack region, where the region's granule is `representable_granule` of its
length: one byte below 128 bytes, and at or above that threshold the coarsest power of two whose
sixty-fourfold still fits inside the length (lines 2011 to 2012, R-15-007c). The
figure a reader should not have to derive: a stack region of 65,536 bytes has a
granule of 1,024 bytes, so under the plan's rule every frame carved from it sits
at a multiple of 1,024 bytes and is a multiple of 1,024 bytes long. That is the
plan's reading 8, which aligns to the coarsest granule the encoding may use for
the **region's** length; the algebra admits a frame of length *L* at the
granule of *L* alone, which is finer, and which of the two a per-frame narrowing
is held to is gap e.

**Whether a frame is narrowed at all is not fixed, and the register places the
narrow elsewhere.** R-15-031b names the address-then-narrow pair "at allocation
and compartment entry" and names no per-function narrow, so a backend that
narrows `csp` once, in the switcher at compartment entry, and runs every frame
as an offset within that one stack capability emits no frame narrowing and owes
R-15-007k nothing for the frame itself; a backend that narrows per frame owes the paragraph
above at every prologue and gives every callee a capability that reaches no
caller frame. Each is admissible under the entries as they stand; the scalar
convention below selects the first. Under either, a capability slot is 8 bytes at 8-byte alignment,
M1.2b's partial backend pinning the capability to one `Mint64`/`Q64` slot, one
tag per 64-bit granule (R-15-203), and a capability access straddling a granule
faulting as a misaligned access
([cap-trap.s](../../corpus/cap-trap.s) lines 81 to 90); the start-from's 8-byte
slots and 16-byte frame alignment therefore stand, and no entry asks for a wider
one.

**Selected scalar frame.** A stack grows downward within its composition-laid
`Stacks` region. At entry its cursor is the top of the available span, aligned
to 16 bytes. Each nonempty frame has a composition-known size `F`, a positive
multiple of 16; its outgoing area, tagged back link, tagged return sentry,
typed spills, locals and stack data follow the start-from's layout order.
Each capability slot is 8-byte aligned and disjoint from every live integer
slot. No red zone is addressed below the current cursor. Before admitting a
call path, the slot plan and TAL frame rule establish that every cursor move
is representable and every accessed slot lies within the assigned stack,
including the maximum simultaneous frames. Unbounded recursion, dynamic stack
allocation and a path exceeding that span are refused by this scalar subset.

The prologue saves the incoming `csp` in `c30`, moves `csp` down by `F` using
`cincoffsetimm` or `cincoffset`, and stores the saved parent and `cra` with `sc`
at the layout's back-link and return-address offsets. The epilogue reloads
`cra` and then `csp` with `lc` and returns. A parent argument is loaded through
the tagged back link, with its signature choosing `lc` or an integer load.
An immediate outside an instruction's signed range is materialized through
`x31`; an integer add or move must never update `csp` or copy the back link.
An empty leaf frame may omit these operations when its rule proves no saved
value, stack access or nested call needs them.

Ordinary function entry emits no `csetbounds`: `csp` retains the bounds of the
compartment's stack across the entire call. The callee consequently retains
authority to reach caller frames; the TAL resource/frame proof supplies the
intra-compartment ownership obligation. This convention claims no hardware
isolation between ordinary function frames. The switcher still derives an
exactly bounded callee stack at every compartment entry, and a narrowed pointer
to a stack subobject still owes R-15-007k independently. Choosing the no-narrow
frame arm leaves MemoryPlan's conservative region-granule rule unchanged.

## 3. The spill discipline and the validity tag

A spill is a store of a register's value into a frame slot and a reload is the
load back, and on the merged file the tag decides the instruction and not the
register's name.

- **A capability-typed value is spilled with the capability store and reloaded
  with the capability load**, at an 8-byte-aligned slot, tag-preserving. A spill
  through the integer store clears the granule's tag on the write path, tag
  clearing being a property of that path and not an instruction (R-15-007r), and
  the reload then yields an untagged value whose later dereference raises a
  tag-violation fault. Clearing the stored tag does not itself raise a fault;
  R-15-007h's absence of a cause code or control-flow term describes the failed
  derivation, not the later dereference. The route contract
  refuses integer spill and reload of a capability outright and requires
  tag-preserving spills under the `frame` rule
  ([compiler-route-contract.md](../languages/compiler-route-contract.md)).
- **A local capability may be spilled only to the stack.** A local capability is
  storable only through a capability bearing store-local, which by construction
  only the stack carries (R-15-074), so a delegated buffer bounded to a call
  (R-04-004) and every other local capability spills into the frame through
  `csp` and into no plan region reached through a data capability. The root holds
  store-local because `candperm` can only remove; the composition hands it to no
  data capability but the stack's.
- **Every live value crosses a call in the caller's frame at the pin**, there
  being no callee-saved register (section 1), and an indirect call destroys the
  argument registers besides. A convention with a callee-saved set moves that
  cost into the callee's prologue and epilogue and hands the cross-compartment
  scrub (R-15-069a) a set it must clear on return. The scalar convention keeps
  the empty set; changing that is a production ABI decision, gap c.
- **The return sentry spills like any capability.** `cra` holds a backward-edge
  sentry the jump minted and no software can mint (R-15-071); spilled with the
  capability store and reloaded with the capability load it is the sentry it
  was, and `ret` enters it. A slot overwritten with anything else reaches `ret`
  as whatever it is: a sealed value of another type or a sentry entered in the
  wrong role is a seal violation, an untagged value a tag violation, and an
  unsealed executable capability is an ordinary jump, which is the residual
  R-15-072 leaves to the typed callee set rather than to the ISA.
- **A float-typed value spills as an untagged integer slot** and a vector value
  as a vector store; a computation that spans slots sinks its own vector state
  under the compiler's sink-before-yield transformation (R-07-014b), the kernel
  carrying nothing across a switch on its behalf.

## 4. Calls and returns

**The two sentry otypes** are the reserved codepoints `0b1110`, the forward
edge, and `0b1101`, the backward edge ([cap_common.sail](../../model/model/core/cap_common.sail)
lines 63 to 65), reported by `cgettype` as the architectural values -2 and -3.
A forward-edge sentry is a call target and a backward-edge sentry is a return
address, and `cjalr` admits each only in its own role (R-15-008, R-15-071); the
profile carries no other sentry (R-15-070).

**The admission table of `cjalr cd, cs1, imm`**, read from its clause
([cheri_insts.sail](../../model/model/extensions/CHERI/cheri_insts.sail) lines
122 to 163): the source must be tagged; if it is sealed, then with a non-zero
`cd` it must be a forward-edge sentry and with `cd` equal to `x0` it may be
either edge, and in both cases `imm` must be zero, any other sealed type, any
sentry entered in the wrong role and any displacement onto a sentry being a seal
violation; it must carry execute permission; the target must be
four-byte aligned and inside the source's bounds by at least one instruction
(`min_instruction_bytes` is 4, R-15-036). On success `cd` receives the next
PCC sealed as a backward edge and the source, unsealed, becomes the executing
PCC, so entering a sentry installs its bounds ([cap-control.s](../../corpus/cap-control.s)
check 4). `cjal cd, imm` writes the same link and jumps within PCC.

The sequences, in the dialect's spelling and in the start-from's constructor:

| Sequence | Emission | Start-from constructor |
| --- | --- | --- |
| Direct call | `call sym`, which is `cjal cra, off` ([asm.py](../../tools/vos/asm.py) `_p_call`); the link is the return sentry | `Pjal_s symb sig true` (`Asmgen.v` line 878) |
| Indirect call | `cjalr cra, cs, 0` on a forward-edge sentry or on an unsealed executable capability | `Pjal_r r sig true` (line 876) |
| Return | `ret`, which is `cjalr cnull, cra, 0` (`_p_ret`): a jump writing no link, the one role a backward edge is reachable in | `Pj_r RA sig true` after the epilogue (line 896) |
| Tail call or computed jump | `cjr cs`, which is `cjalr cnull, cs, 0` (`_p_cjr`): enters either edge or unsealed code and keeps `cra` | `Pj_r r sig false` and `Pj_s symb sig` after the epilogue (lines 881 to 883) |
| Minting a call target | `csealentry cd, cs1` ([section 6](#6-the-primitive-surface)) | none; the start-from mints no sentry |

Three things the table settles. A call through an unsealed executable capability
is admitted by the clause, so an intra-compartment function pointer need not be
a sentry, and R-15-068's sentence that a compartment is reached only by jumping
through the sentry its manifest was handed is a statement about entry points
handed across a boundary; whether the backend seals every function pointer or
only those is an ABI choice. The scalar convention allows unsealed code for
ordinary same-compartment pointers, with the typed callee-set obligation
unchanged; every exported compartment entry remains a sentry reached through
the switcher. A return address is never software's to forge, the
backward edge being minted by the jump alone (`link_capability`, lines 67 to 72;
`csealentry` mints the forward edge only, lines 271 to 277). And a call that
enters a return sentry traps, which
[cap-trap.s](../../corpus/cap-trap.s) check 5 exhibits as a seal violation with
the raising register in `mtval`.

**The cross-compartment sequence.** The only path between two compartments is a
sealed entry point through the switcher, which saves and restores the caller and
bounds a delegated buffer to the call through the local/global discipline
(R-04-004); the switcher is a specialization of `cjalr`, its entry point being
itself a sentry entered by that instruction (R-15-069); the switch and seal
authority is the kernel's (R-07-020); and the scrub on each direction is
`cclear`, two of which clear the merged file, so that the callee sees no
register the caller did not pass and the caller no register the callee did not
return (R-15-069a). The start-from's compartment layer is the layer this
realizes, and the correspondence is stated so a reader of `Asm.v` can find each
piece: a call and a return are `Pjal_*` and `Pj_r` with their flag set and a
signature attached (`sig_call`, `is_return`, lines 1324 to 1336); a cross-
compartment call pushes a shadow frame holding the caller's stack pointer and
return address and hands the callee dummy blocks for both (`update_stack_call`,
lines 1253 to 1293); every register that is not an argument of the signature is
invalidated on the call and every register that is not the result on the return
(`invalidate_call`, `invalidate_return`); no pointer crosses in either direction
(`NO_CROSS_PTR`, lines 1525 to 1527 and 1566 to 1567); a stack argument is read
across the boundary from the caller's frame by `Pld_arg`
(`exec_step_load_arg_cross`, lines 1455 to 1481); and the return restores the
caller's program counter and stack pointer from the shadow frame
(`invalidate_cross_return`, lines 1400 to 1405). On this machine:

1. The caller places its arguments in `a0` to `a7`, every capability among them
   a local capability bounded to the call (R-15-074) or a sealed grant handle
   (R-08-004a), the edge's extent and rights being the IDL message type and the
   manifest's import and export tables fixed at composition (R-05-117,
   R-05-124), so no containment test runs on the path (R-15-007m); it enters the
   switcher's forward-edge sentry with `cjalr cra, cswitch, 0`.
2. The switcher saves the caller's `csp` and return sentry where R-07-027a lets
   the kernel hold state no principal names, narrows the stack for the callee
   by the address-then-narrow pair at compartment entry (R-15-031b), exact
   under R-15-007k against the stack region's granule, clears every register
   the callee is not passed with `cclear` (R-15-069a), and enters the callee's
   forward-edge sentry with `cjalr cra, ctarget, 0`.
3. The callee returns with `ret` into the switcher's backward-edge sentry.
4. The switcher clears every register but the result with `cclear`, restores the
   caller's `csp` and return sentry, and returns with `ret`.

What that shape leaves unfixed is gap g: the register that carries the edge's
identity into the switcher, the two `cclear` masks per direction, where and how
deep the saved caller state is kept, and whether the switcher's text runs under a
PCC carrying access-system-registers or holds the seal and unseal authorities
without it. The start-from's `NO_CROSS_PTR` is replaced and not inherited: a
capability crosses here exactly as the manifest's edge admits it.

## 5. The float-typed value's route

Scalar floating point is excluded entirely, the `f` register file with it
(R-15-039), and all floating point is VL=1 RVV on the one FPU. The fork books a
soft-float-register calling convention as its accepted ABI cost (R-15-040), and
the profile fixes what that means at the instruction: a scalar operand of a
vector-FP instruction is the low `SEW` bits of an integer register, and
`vfmv.f.s` writes its element zero-extended into an integer register rather than
NaN-boxed ([the profile's exclusion notes](../hardware/isa-profile.md#6-exclusions),
R-15-040). So a float-typed value lives in an integer register, is passed and
returned in the integer argument and result registers, and spills as an untagged
integer slot. M1.2b's partial backend exhibits the passing half: `double id(double x)`
and a forwarding call compile with no `f` register named and the call's `x10`
untouched, and a `double` passed to a variadic callee moves with `mv x11, x10`
where the pin moved through `f1`; the same backend refuses a float load, store
or spill by name, which its note books as the open work behind F-319.

The lowering is R-18-014i's: a dependent scalar-float chain keeps its
intermediates resident in vector registers and takes its integer-register moves
at the chain's boundaries rather than per operation, `vmv.s.x` in and `vfmv.f.s`
out, and independent scalar-float work is batched to VL greater than one under
the SLP duty R-18-014a already owes. Two consequences an author should read here
rather than derive: a partition that computes any float needs its vector state
gated on at partition setup (`mstatus.VS`, R-07-012), the kernel itself being
scalar-only; and code cannot rely on vector intermediates surviving a call or
compartment crossing until the preservation convention is fixed (gap d).
`Zfinx` is not the route and is excluded on its own ground (R-15-039d), so the
soft-float convention is the only scalar-float ABI on the machine, and every
later vector-FP extension defining a scalar-operand form pays the same re-homing
(R-15-040b).

## 6. The primitive surface

R-05-023b fixes the shape: a verified component reaches an instruction the
profile carries and no lowering duty reaches through exactly one surface, a
backend primitive **named by the instruction's own profile mnemonic and operand
form**, whose meaning in the source language is the instruction's Sail clause and
never a second statement of it. Membership is the profile's instruction rows and
nothing else, a primitive naming no row is a defect of the compiler, and a
component naming an instruction no primitive covers does not build. The
backend's test set carries one positive case per primitive emitting the encoding
the row states and one negative case rejecting a name no row carries
(R-18-014a). Each primitive emits its named instruction with the operand form
below. Operand preparation, result placement and any temporary registers remain
backend work: their emitted sequence must preserve the Sail meaning and satisfy
R-05-023a's record. The register does not require every source invocation to be
one instruction in total. A barrier primitive must preserve the ordering its
Sail clause states.

The four the M1.2 cell names, each from its own clause:

| Primitive | Sail constructor and file | Assembly form | Encoding | Operands | Consumer |
| --- | --- | --- | --- | --- | --- |
| `vmclear` | `VMClear : unit`, [vmclear.sail](../../model/model/extensions/platform/vmclear.sail) | `vmclear` | custom-0, `funct3` 001, every other field zero, decoded only where `hartSupports(Ext_Zve32x)` | none | the partition switch, M4.4 |
| `fence.t` | `FENCE_T : unit`, [fence_t.sail](../../model/model/extensions/platform/fence_t.sail) | `fence.t` | MISC-MEM, `funct3` 100, every other field zero | none | the partition switch, M4.4 |
| `cspecialrw` | `CSpecialRW : (regidx, screg, regidx)`, [cheri_insts.sail](../../model/model/extensions/CHERI/cheri_insts.sail) lines 560 to 618 | `cspecialrw cd, scr, cs1` | `0b0000001 @ scr @ cs1 @ 000 @ cd @ 0b1011011` | a destination capability register, a special register name, a source capability register | M3.5's firmware and M4.4's kernel for the three trap registers; any code for reading `pcc` |
| `csealentry` | `CSealEntry : (regidx, regidx)`, the same file, lines 264 to 283 | `csealentry cd, cs1` | `0b1111111 @ 0b10001 @ cs1 @ 000 @ cd @ 0b1011011` | a destination and a source capability register | the composer and firmware minting entry points; the backend minting a call target it hands across a boundary |

**`vmclear`** takes no operand and names no destination because the class's
unit-state inventory names them all (R-15-069d): it re-initializes `v0` to `v31`
through the reset path's `init_vregs`, clears the class's software-managed
scratchpad in whole chunks by a physical write that carries no capability and
clears every granule's tag for free, and writes `vl`, `vtype` and `vcsr` to the
values reset gives them, `vtype.vill` set so that no configuration is what a
successor reads (lines 165 to 186). It is admitted on the switch bound, replacing
a `cbo.zero` and `cclear` loop whose trip count the kernel proof would carry
(R-15-069e, R-07-014c), and it is one fixed per-class entry in the timing-
annotated model. Its decode guard is the static class predicate and not
`mstatus.VS`, so an outgoing partition cannot make the zeroize conditional by
writing `VS` back to `Off`; on a vectorless class the encoding traps as every
unallocated encoding does (R-15-014). It is the second of R-15-220's three
switch terms, and the rotation of R-07-037b omits it.

**`fence.t`** takes no operand and drains the store buffer unconditionally,
`sail_barrier(Barrier_RISCV_drain)`, the same barrier a draining `fence` emits
under a different condition (R-15-213); the register files are deliberately not
in its flush set, the total restore standing in their place (R-15-214,
R-07-016), and its cost is a padded per-class constant the fence completes at
and never before (R-15-218). It is adopted as a fork-and-frozen platform-custom
instruction with full Sail semantics (R-15-062) and is the first of R-15-220's
three terms. In the source language it is a barrier: the backend moves no memory
operation across it, which is what the clause says of it and what a compiler
test must show.

**`cspecialrw cd, scr, cs1`** names one of four special registers and no other,
the bank being closed by R-15-001b and R-15-073 rather than by upstream's
numbering: `pcc` at `0b00000`, `mtcc` at `0b11100`, `mtdc` at `0b11101` and
`mepcc` at `0b11111` ([cap_regs.sail](../../model/model/core/cap_regs.sail)
lines 41 to 48), an absent number being an illegal instruction (R-15-014). `cd`
receives the register's old value, `pcc` read at the architectural PC and
`mepcc` legalized on the way out; when `cs1` is not `cnull` the register is
written, MTCC with its address legalized as the `mtvec` view legalizes it, and a
write to `pcc` is illegal. Reading `pcc` needs no permission; MTCC, MTDC and
MEPCC need access-system-registers on the executing PCC, and their absence is a
capability fault whose `mtval` names the special register above the merged
file's indices (lines 565 to 615, R-15-003, R-15-073a). Its emission shapes are
the corpus's: `cspecialrw cnull, mtcc, c9` installs a handler,
`cspecialrw c19, pcc, cnull` reads the executing capability, and
`cspecialrw c10, mtdc, c8` writes MTDC and reads what it held
([cap-inspect.s](../../corpus/cap-inspect.s), [zicond-csr.s](../../corpus/zicond-csr.s)).
Its consumers are the kernel and the firmware, a compartment's PCC lacking the
permission (R-07-023); a compartment reaches it only to read `pcc`.

**`csealentry cd, cs1`** seals `cs1` with the forward-edge otype and clears the
tag first if `cs1` was already sealed (line 275), so it mints a call target and
never a return address; it needs no permission, a sentry holding neither
`Permit_Seal` nor `Permit_Unseal` and the sealing being instruction semantics
(R-15-007o, R-15-068). Its source is an unsealed capability carrying execute
permission with its address at the entry and its bounds at the entry's extent,
which is what installs those bounds as the callee's PCC; the corpus mints one
from `pcc` ([cap-derive.s](../../corpus/cap-derive.s) check 10), from a
materialized code capability ([cap-control.s](../../corpus/cap-control.s)
checks 2 and 3) and from one narrowed to the callee's eight bytes (check 4).
The scalar choice for ordinary function pointers is stated in section 4.

Beside the four, **`cclear h, mask`** (`CClear : (bits(1), bits(16))`,
[cheri_custom.sail](../../model/model/extensions/CHERI/cheri_custom.sail) lines
68 to 85) is the switcher's instruction and not a backend primitive a component
names: it clears the sixteen registers `mask` selects in the half `h` selects to
untagged NULL, reusing the S-type field layout with no destination named, and
R-18-014a puts its one selection rule in the switcher's emitter (R-15-069a,
R-15-069b). And `cjalr` and `cjal` are not primitives at all, being the
control-transfer instructions every call lowers to.

**Source identity.** The [profile's CHERI table](../hardware/isa-profile.md#4-cheri-feature-set)
names `cspecialrw cd, scr, cs1` and `csealentry cd, cs1` explicitly beside the
custom-instruction rows for `fence.t` and `vmclear`. A primitive's registered key
is that exact mnemonic with its operand form; a source language that cannot use
the mnemonic as an identifier carries it as a string key. Thus `"fence.t"`
with no operands names `FENCE_T`, while `"fence_t"` names no profile row and
is refused. A legal C or Gallina binding such as `vos_fence_t` is a binding to
the `"fence.t"` key, never another admitted primitive or an unchecked external
function. Its source declaration, elaborated primitive term and lowering record
must preserve that identity. The compiler owner implements this binding and the
barrier effect before a consumer may compile it; this spelling decision adds no
frontend syntax or working builtin by itself.

## 7. The kernel entry interface

**The chain and what each stage supplies.** The chain is RoT, then verified
M-mode firmware, then per-core kernels, then the static image, every stage
measured before it runs (R-09-002); the ROM's one sequence places the verified
M-mode image in main SRAM and releases the boot core into the measured chain
(R-09-006); the firmware runs first, installs exactly the composed capability
graph as running kernel state (R-07-028), derives each core's partition-bounded
root and goes quiescent with nothing resident (R-07-019, R-07-024). The core the
RoT releases starts from the model's reset state of section 1, and the sequence
table the RoT executes is the devicetree's (R-15-198).
[MModeFirmware.v](../../proofs/MModeFirmware.v) fixes the handoff as a relation:
the installed distribution equals the plan edge for edge, every root the
firmware hands a core lies inside that core's partition (R-07-006's criterion,
"the root capability's bounds are the partition's"), every core has a root, and
the resident inventory is the kernel alone (`Handoff`, lines 800 to 805);
[its landed note](completion-log.md#m33-implement-m-mode-firmware-in-gallina)
records that no artifact distinguishes a region's text from its data, so the
permission split R-15-007p makes of the root is stated there only as some root
per core.

What M4.4's kernel holds at its first instruction, each item with what fixes it:

1. **The root pair, bounded to the partition.** An execute-side authority over
   the image's read-only text extents and a store-side authority over its data
   (R-15-007p), each bounded to the core's physical partition plus the declared
   shared windows (R-07-006), the composition-time disjointness being a build
   artifact (R-07-005). The execute side is the kernel's PCC; which register the
   store side arrives in is selected below as a capability table, preserving a
   separate authority for every composed extent.
2. **Entry as a sentry.** A compartment is reached only through the sentry its
   manifest was handed (R-15-068), and a partition or a kernel task is
   dispatched by `mret` with a sentry in MEPCC unsealing on `mret` as it does
   when jumped to (R-07-020, R-15-007j). Whether the firmware enters the kernel
   by `mret` with the kernel's forward-edge sentry in MEPCC, by `cjr` into that
   sentry with `cra` null so that nothing can return to a stage that has gone
   quiescent, or by a plain jump into unsealed text is fixed by no entry. The
   scalar convention selects the no-link sentry jump below.
3. **The trap registers.** MTCC holds the kernel's trap entry with
   access-system-registers, a trap installing it as the executing PCC, saving
   the interrupted PCC as MEPCC and bootstrapping the handler's authority from
   MTDC (R-07-022, R-15-073), and a trap taken while the trap path is live
   stops the die rather than re-entering (R-15-073c). Firmware installs the
   trap capabilities before the selected handoff below.
4. **The stack capability.** `csp` bears `perms_stack` and is derivable only
   from the store-side root, the only root holding store-local; its bounds are
   the kernel's stack region of the plan, a first-class region (R-15-247s). Who
   derives it is selected below as the firmware.
5. **The devicetree.** A static devicetree declares core classes, islands, the
   NoC schedule, OPP tables and the calibration limits (R-09-007), the reset
   and power sequence table (R-15-198), the mode vectors (R-15-189f) and the
   bank-to-island map (R-15-228); it is the sole origin of device authority, the
   verified HAL reaching a device register only from a root device capability
   handed in at construction (R-05-138); and the address map it declares is
   dense inside the 36-bit space (R-15-002b). How the kernel receives it, as a
   capability in a named register or as a composition-time address inside its
   data root is selected below; its producer and attestation join remain gap j.
6. **The hart's identity.** `mhartid` is read-only and the one implementation
   identifier with a consumer: the kernel selects its per-hart state, the core's
   class and the island binding from it at boot
   ([the profile's CSR bank](../hardware/isa-profile.md#51-present), R-07-012).
7. **The partition contexts and the schedule table.** Whether "running kernel
   state" in R-07-028 includes the contexts R-07-015 restores and the table
   R-11-024 swaps is unstated, which MModeFirmware.v reports as its gap b and
   the staging responsibility below selects an implementation split without
   strengthening that proof artifact's `Handoff` relation.

**Selected scalar handoff.** Firmware and kernel author against these inputs at
the first C body instruction, with no return to firmware:

| Location | Supplied value and authority | Producer and consumer responsibility |
| --- | --- | --- |
| PCC | The kernel entry text capability, unsealed by the no-link jump, with execute and access-system-registers, without store | Firmware derives the exact text extent and mints its forward sentry; the kernel never inherits firmware's text authority |
| `csp` / `c2` | Local `perms_stack` capability bounded to the kernel's `Stacks` region, cursor at its representable, 16-byte-aligned initial top | Firmware derives it before discarding its reset authority; the frame rule consumes it |
| `c10` / `a0` | Global read-only capability to the kernel root-set table, with load-capability, load-global and load-mutable so reading a member preserves its authority | Firmware installs exactly the composed, permission-split roots, one tagged member per declared extent; the table grants no permission its members lack |
| `c11` / `a1` | Global read-only capability to the measured boot descriptor/devicetree, bounded to its declared byte extent | Firmware supplies the authenticated producer handoff; kernel consumers use the composition's declared layout, with no content-based device discovery |
| `c12` / `a2` | Global read-only capability to the composed kernel initialization descriptor; capability-bearing fields use transitive capability loads | It names the planned context/save areas and initial schedule inputs; the kernel initializes and validates its running contexts and table before its first dispatch |
| MTCC, MTDC | Kernel trap-text authority and the composed authority its handler needs to bootstrap its data access | Firmware installs them before handoff; the trap prologue reads MTDC explicitly, since taking a trap does not copy MTDC to a general register |
| MEPCC | Null | Firmware clears the reset/firmware continuation before handoff; the first real trap or dispatch installs the required successor value |
| `cra`, `x3`, `x4`, all other merged registers | Null, except for the transient entry target described next | Firmware scrubs every noninput; kernel entry discards the last temporary before calling C |

The tables have exactly representable bounds and naturally aligned tagged
entries. Read-only describes access to the table itself: its
`perms_r_cap_lm_lg` shape retains the load transitivity required to retrieve a
global writable member unchanged. A plain `perms_r` capability cannot replace
it. Ordinary tables contain global members only; a borrowed local capability
requires storage through stack authority and cannot be installed in a data
table merely because that table is read-only to its consumer.

The final jump uses a transient forward-edge kernel sentry in `c5`, installed
by firmware while its PCC still has system-register permission. After installing
MTCC and MTDC, firmware puts null in a nonzero scratch register and writes
MEPCC from it: `cspecialrw` with source `cnull` only reads and does not clear a
special register. It clears noninputs, keeps `c2`, `c5`, `c10`, `c11` and `c12`,
and issues `cjr c5`, which is `cjalr cnull, c5, 0`. The entry stub immediately
clears `c5`. The masks and instructions are executable assembly in the
[scalar witness](../../interfaces/examples/scalar-abi.s); they describe this
one-time handoff only and decide no cross-compartment switcher mask. Firmware
leaves ordinary interrupt delivery disabled until the kernel has installed its
initial dispatch state. Entry code is nonreturning; null `cra` is no return
sentry, and the kernel's first partition dispatch remains `mret` as required.

The table's bounds and read-only permission do not authenticate its bytes. The
producer join still owes the exact descriptor layout, source and image binding,
measured-chain evidence, root-set membership and the consumer's acceptance of
that evidence. No parser, attestation verifier or graph-to-context refinement is
supplied here. M3.5 owns that real producer and installation evidence; M4.4 owns
initial context/table construction and its `PartitionContext` relation. A kernel
consumer must reject a missing descriptor, a wrong-hart or wrong-composition
descriptor, or an initialization lacking a planned successor before dispatch.
Those are producer/consumer checks, not Sail capability faults. This authoring
split answers who writes initial state without claiming that
`MModeFirmware.Handoff` already proves its context and schedule components.

**What M4.4's switch restores**, from [PartitionContext.v](../../proofs/PartitionContext.v):
every one of the 32 registers, value and validity tag together, is written
from the successor's context before its first instruction (`RestoresRegisters`,
R-07-015, R-15-007i), so the save area is tag-carrying memory written and read
with the capability store and load, a restore that drops the tags being refuted
by name (`tag_dropping_switch_refutes_register_totality`); every CSR a partition
can name is written, restored where the profile's CSR bank restores it and
written to zero where the bank zeroizes it, the vector CSRs being the zeroized
class (`RestoresNameableCsrs`, R-15-001b); the interrupt-file pending bits are
the successor's under either of R-07-044's arms; and two post-states reached
from one successor context agree on all three, whatever the predecessors held
(`NoResidue`). The vector and matrix state is zeroized by `vmclear` and never
saved (R-07-014a, R-07-014c); the switch pays R-15-220's three terms, `fence.t`,
`vmclear` and the OPP relock, and R-07-037b's intra-slot rotation performs the
register swap and the restorable-CSR restore and omits all three
(`rotation_restore_is_total`, `rotation_omits_the_three_constants`). The
register save area for one context is 32 slots of 8 bytes plus the nameable CSR
bank, laid out by the plan as a first-class `RegisterSaveAreas` region
(R-15-247s), and which CSRs a partition can name is the bank's reachability
under the access-system-registers gate (R-15-003), carried by PartitionContext.v
as a field rather than a copy.

**Positive scalar case and refusal review.** The
[assembly witness](../../interfaces/examples/scalar-abi.s) begins at the final
firmware transfer with its capability inputs stated as preconditions. It clears
MEPCC through a nonzero null-valued source, scrubs noninputs, and enters the
forward sentry without minting a firmware return. The kernel stub clears its
target temporary. With stack bounds `[S,S+128)` and initial cursor `S+128`, its
32-byte frame moves the cursor to `S+96`; the nested helper's 32-byte frame
moves it to `S+64`. Their slots do not overlap. The helper spills a writable
data capability before a leaf overwrites `a0` with integer 42, reloads the
capability through the stack and writes 42 through it. Both epilogues recover
the tagged back links and the matching return values of `cra`; the outer body
ends with its original `csp`, root-table input and boot descriptor restored,
and null `cra`. It remains nonreturning.

The review reads `CJALR`, `CIncOffsetImmediate`, `CSpecialRW`, `LoadCapImm` and `StoreCapImm`
from [the CHERI instructions](../../model/model/extensions/CHERI/cheri_insts.sail)
and [the capability memory path](../../model/model/extensions/CHERI/cheri_mem.sail),
the permission accessors from [cap_common.sail](../../model/model/core/cap_common.sail),
and `CClear` from [cheri_custom.sail](../../model/model/extensions/CHERI/cheri_custom.sail).
Its refusal cases distinguish an admission defect from an architectural trap:

| Changed input or sequence | Decisive consequence |
| --- | --- |
| Spill `D` or `cra` using `sd` | The write path clears that slot's tag; a subsequent dereference or `ret` faults for an untagged capability. The compiler's typed spill rule refuses the sequence before emission. |
| Update `sp` with integer `addi` | The merged-register integer write clears `csp`'s tag; the next frame access faults. The frame rule requires capability cursor operations. |
| Remove store-local from stack authority while spilling the local back link | The capability store fails its store-local check; storing the local back link in an ordinary table is refused for the same reason. |
| Read the root table through plain read-only authority without load-capability | `lc` delivers an untagged member; read-only bytes alone cannot implement the root-set handoff. Dropping load-mutable instead strips the member's store authority. |
| Use `cjalr cra, c5, 0` for final firmware entry | Sail permits the forward call but mints a live firmware return capability, violating this handoff's no-continuation predicate. |
| Use a backward sentry as a linked call target, or displace any sealed sentry | `CJALR` reports a seal violation; the matching `ret` is a zero-displacement, no-link entry. |
| Clear MEPCC with source register `cnull` | `CSpecialRW` performs a read and leaves MEPCC unchanged; the scrub predicate refuses the stale continuation even though the instruction succeeds. |
| Exceed the assigned stack or use a nonrepresentable frame cursor | The composition/frame acceptance fails before emission; Sail bounds or tag faults are not an accepted stack-overflow path. |
| Omit descriptor provenance or a planned initial successor | The M3.5/M4.4 producer join remains unsatisfied, even if every capability access succeeds. |

Assembler acceptance checks operand spellings and encodings in this fixture.
The state transitions above are a review against the Sail clauses, not a
measured target run, compiler-emission test, source-correspondence theorem or
firmware boot. Those remain the M1.2d, M1.2f, M3.5 and M4.4 joins.

## 8. What the register leaves open

The letters retain the decisions consumers cite. A selected scalar arm is an
authoring agreement under the register, not a claim that the register fixes the
entire production ABI. Its backend implementation, final-image checks and
consumer evidence remain M1.2d's join.

- **(a) Integer register roles: selected for scalar bring-up.** Section 1 fixes
  arguments, scalar result, unavailable registers and scratch roles. Production
  aggregate, variadic and vector signatures are outside this selection.
- **(b) Second scratch: unnecessary for the selected frame sequence.** `x31`
  handles a large frame size or slot offset; `x30` carries the tagged parent
  frame when needed. M1.2d reviews liveness at every additional emission rule.
- **(c) Callee preservation: selected as empty.** Every live allocatable value
  crosses an ordinary call in the caller's frame, and `csp` is restored on
  return. A changed production set reopens allocation, prologues, outlining
  costs and the cross-compartment return scrub together.
- **(d) Vector registers across a call: open.** No entry or start-from
  definition fixes preservation for `v0` through `v31`; the partition switch
  zeroizes the file. R-15-040 and R-18-014a remain its owners.
- **(e) Frame narrowing: selected as absent at ordinary function entry.** The
  stack keeps its compartment bounds; section 2 states the ownership and
  stack-budget consequences. The region-granule versus frame-granule choice
  matters only if a later convention narrows frames. MemoryPlan's reading 8 and
  R-15-007k remain unchanged, including for narrowed stack subobjects.
- **(f) Ordinary function pointers: unsealed code is permitted.** The typed
  callee-set check remains required by R-15-072. R-15-068's exported entries
  remain sentries reached through the switcher; this choice closes no
  cross-compartment sequence.
- **(g) Switcher protocol: open.** The edge-identity register, scrub masks,
  bounded saved-caller-state layout and nesting limit, and the switcher's
  authority need a reviewed producer/consumer protocol under R-15-069 and
  R-04-004. The one-time firmware scrub in section 7 is not that protocol.
- **(h) Primitive profile membership: present.** The explicit operand-form
  rows for `cspecialrw` and `csealentry` are in the profile's CHERI table.
  R-05-023b now has a profile row to name for each required primitive; emission
  and its positive/negative compiler tests remain owed.
- **(i) Kernel entry transport: selected.** Section 7 assigns roots and
  descriptors, stack derivation, trap-state installation and the no-link sentry
  jump. M3.5 still owes the actual split-root producer and installed-state
  refinement; the abstract `MModeFirmware.Handoff` root relation alone does
  not establish this concrete state.
- **(j) Boot descriptor transport: selected; provenance join: open.** `c11`
  carries the bounded read-only descriptor. The real layout and authenticated
  producer/consumer evidence under R-09-007 remain owed; read-only authority
  cannot replace them.
- **(k) Initial contexts and schedule: assigned to kernel initialization.**
  Firmware supplies the composed inputs through `c12`; the kernel constructs
  and checks running contexts and its schedule table before dispatch. Relating
  those inputs to R-07-028 and proving the context/table initialization remain
  separate joins; the existing firmware statement artifact is unchanged.
- **(l) Primitive spelling: selected as exact registered identity.** A
  nonidentifier mnemonic is a string key; a legal source binding resolves to
  that key and never extends membership. The compiler implements the binding,
  operand typing and Sail effects before source compilation is accepted.
