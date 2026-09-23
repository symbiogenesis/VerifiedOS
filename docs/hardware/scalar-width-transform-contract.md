# Scalar width staging contract

R1b seam 2 binds the imported scalar datapath to the frozen capability widths
through explicit semantic transforms of its pinned sources. The integrator
authorizes this staging route: imported bodies remain behind the existing
`upstream/cva6-cheri` gitlink, and only the transformations are authored here.
This contract precedes their implementation. It supplements the
[reparameterization delta](rtl-reparameterization-delta.md) and does not select
instruction semantics for later seams.

## Transform boundary

The transform registry names each source, its SHA-256 identity, an ordered set
of exact replacements with match counts, and the resulting SHA-256 identity.
The runner rejects a missing source, an identity mismatch, a changed match
count, or an unexpected resulting identity. Source decoding uses UTF-8 and
normalizes source line endings to LF before these identities and replacements;
this makes the identity independent of Git's host text checkout conversion.
The selected source pin remains recorded separately.

Only the curated elaboration arm applies these transforms. The stock arm
continues to measure the stock source. Staged files retain all original notices
and add a modification notice naming this contract. The build lane contains
the input/output identities, exact replacements and source-to-staged diffs.
No imported body is copied into tracked `rtl/`. This is source provenance,
not formal equivalence or a synthesized absence result.

## Seam 2 decisions

`CLEN` is the frozen capability memory width, equal to `XLEN`, in both
`ariane_pkg` and `build_config_pkg`. Register and PCC transport widths continue
to derive from `$bits(cva6_cheri_pkg::cap_reg_t)`, the typedef of the Sail-owned
decoded record. No padded legacy register shape is introduced. The store
alignment function rotates bytes within one frozen word and has no upper
capability half; only the low address bits within that word select rotation.
Full-width accesses still require alignment at their architectural boundary.

The imported bounds metadata temporaries disappear. Their declarations,
assignments, and metadata-only helper arguments are removed together; the
frozen helpers derive bounds directly from the capability record. No replacement
`cap_meta_data_t` or ignored compatibility argument is introduced. The
permission-report, exception-type and mode consumers are seam 3's below. This
seam must not invent aliases for those unresolved architectural choices.

## Seam 3 decisions

A capability violation reports one `mcause` code and its detail in `mtval`: the
violation's own code in the low five bits and the register that raised it above
them. The imported 22-bit trap-value layout, its four-bit check-type field and
its reserved and ignored bits have no counterpart, and the payload moves from
`tval2` to `tval`. Each imported violation constant takes the model's own cause.
A bounds failure is a length violation, and the one imported permission
violation resolves per site into the execute, load, store or
access-system-registers cause according to the check that raised it. The three
check-type constants report nothing the model's payload carries, so they are
removed rather than re-encoded.

**The reported register follows the authority the model's own clause names.**
An instruction fetch checks `PCC` and reports `PCC_IDX`, and so does a jump
naming no register (`ext_fetch_check_pc` and `ext_control_check_pc` in
`model/model/core/addr_checks.sail`, and `CJAL` in
`model/model/extensions/CHERI/cheri_insts.sail`). `cjalr` checks its source
register and reports `capreg_idx_of_regidx(cs1)` for each of its causes, tag,
seal, execute and length alike. A data access reports its base register's index,
`cap_mode_auth` naming exactly one authority because there is one mode. So the
branch unit's bounds check reports `PCC_IDX` where its jump base is the program
counter and the operand's own index on `cjalr`, whose jump base is that operand,
and the load/store unit reports the base register the control record carries as
a five-bit `rs1`. **The imported `use_ddc` arm is unreachable rather than
accounted for**: the model has one arm and reaches no default data capability
here, and the flag that would select the imported one is the mode flag the
one-mode reading below deletes, so the reported index names the base register in
every case the staged core reaches.

**One imported conflation survives and is recorded rather than repaired.** The
imported bounds condition folds `!target_pcc.tag` into the length test, so an
untagged jump target reports a length violation where the model has a distinct
tag violation. On `cjalr` the imported block's own last-write-wins order already
reports the tag violation, which is the model's priority; on the remaining paths
the model checks `PCC`'s bounds directly rather than a moved capability, so the
untagged case has no model counterpart there to disagree with. Splitting the
condition is branch-unit curation and this seam does not take it.

`candperm` intersects the capability's own expanded permission bitmap with the
operand mask and narrows the result to the largest admitted set inside it, so
the nine independent architectural bits, the software-defined bits and the pair
of report/architectural conversions become calls on the format package's
expansion and narrowing. `cgetperm` answers in the expanded bitmap and reads its
width from the format package. The permission enumeration is total, so the two
malformed-permission tests are constant false and nothing legalizes an encoding.

There is one instruction-encoding mode and it is the capability one (R-15-001c,
R-15-242), so the mode flag has no field. A write of it is vacuous and is
removed. The two readers that still have a consumer, the issue stage's mode
output and the top level's resolved-branch mode input, answer a constant `1'b0`,
and the jump-into-integer-mode mispredict cannot fire and goes with them. No
mode member is invented. **The constant is a reading of the imported polarity
and is stated rather than assumed**, because a reader is not an identity the way
the removed writes are: every imported consumer treats 1 as the integer mode,
`decoder.sv` selecting `JALR` over `CJALR` and asserting `use_ddc` on it,
`compressed_decoder.sv` gating its capability forms on its negation and
`csr_regfile.sv` gating capability CSR access on the same, so 0 is the
capability mode whatever the imported field comment says. The decoder's own
mode path is seam 4's below.

`cjalr` admits a forward-edge sentry as its target and writes its return address
already sealed as a backward-edge one (R-15-068, R-15-071), so the branch unit's
two single-sentry reads take the forward-edge and backward-edge constants
respectively. The signed comparison the imported test made over a one-bit object
type goes with the widened field.

## Seam 4 decisions

Seam 4 resolves the three name classes seam 3 left, the decoder's mode path and
the member layer behind them. Each decision reads the model's own clause.

**`csealentry` seals to the forward edge.** The model's `CSealEntry` mints the
forward-edge sentry from a capability whose tag it clears where the input was
sealed, and the backward edge is minted only by a call's link
(`model/model/extensions/CHERI/cheri_insts.sail`, R-15-071). The CHERI unit's
seal-entry arm takes `SENTRY_FWD_CAP`, so a return capability cannot be
fabricated by an instruction, and its operand check already clears the result's
tag where the input was sealed, which is the model's `clearTagIfSealed`.

**The mode instructions are not instructions.** The model's instruction surface
has no mode read, mode write or mode switch, one mode leaving nothing for them to
select (`cheri_insts.sail`, R-15-001c, R-15-242). The CHERI unit's get-mode and
set-mode arms go, and the decoder's rows for them and for the mode-switch pair go
with them, so all four encodings reach the default arm and decode as illegal.
`id_stage.sv` ties the decoders' mode input to `1'b0` at its single source and
resets its mode register to the same value, and with the mode-switch rows gone
no decoder output differs from its input, so the mode is constant from reset.
Every `use_ddc` assignment and every mode-selected `JALR`/`CJALR` and `JAL`/`CJAL`
choice therefore reads the capability arm. The fields stay in the imported
scoreboard entry, and the two `csr_regfile.sv` readers of its `int_mode` read the
constant.

**Reset hands out the model's split root set, and nothing else.** The model's
`ext_reset` puts the execute-side root in `PCC`, `MTCC` and `MEPCC`, the
store-side root in `c1`, the seal and unseal bootstrap authorities in `c2` and
`c3`, and the null capability in `MTDC` and every other register
(`model/model/postlude/step_ext.sail`, R-15-007l, R-15-007p). The ariane
package's single root becomes `REG_ROOT_CODE`, which every code-side site takes:
the reset values of `PCC`, `mtvec` and `mepc`, and eight sites behind the
supervisor, hypervisor, debug and test-injection parameters the curated
configuration turns off, the reset values of `sepc`, `stvec`, `vsepc`, `vstvec`
and `dpc`, the test-injection `mtvec` reload, the debug `dpc` write and the debug
trap vector. `DDC` resets to null, being absent (R-15-001c); the register itself
goes with the CSR seam. The register file takes a per-register
reset file, `REG_RESET_FILE`, which grants `REG_ROOT_DATA_CAP`,
`REG_ROOT_SEAL_CAP` and `REG_ROOT_UNSEAL_CAP` to `c1`, `c2` and `c3` and null
elsewhere, through an `INIT_FILE` parameter on the imported register file whose
default keeps the single `INIT_VAL` everywhere. The format package carries the
two object-type roots beside the two memory roots, bounded to the nonreserved
types with the cursor at zero as `cap_common.sail` states them. The
test-injection arm's all-root register file has no split reading and takes the
same grants.

**The excluded instructions' arms go whole with their decode rows.** Capability
reconstruction and the subset test (R-15-002, R-15-006, R-15-007m) carry the
reserved-field test beside them, and the representable-alignment mask carries
the bounds-return record's `mask` (R-15-007k, R-08-011). The CHERI unit loses
the reconstruction and subset-test arm and the mask's branch of the bounds arm,
and the decoder loses the three rows, so the three encodings decode as illegal.

**The levels signals become the load's transitivity.** The imported load/store
unit derived three clears from the levels bits and the load-mutable bit. The
model's `cap_load` clears the tag where the authority lacks load-capability, and
its `load_transitivity` makes a tagged result local where the authority lacks
load-global and strips its three store permissions where it lacks load-mutable
(`model/model/extensions/CHERI/cheri_mem.sail`, R-15-074). The control record
carries `clr_load_global` and `clr_load_mutable` in the place of the levels pair,
each read through the format package's permission accessors, and the load unit
narrows a tagged result's expanded permissions through `set_cap_perms`, over the
tag it keeps and never over data. The revocation filter the same clause applies
first is behaviour the datapath does not have (delta §2.5, item 5).

**Storing authority is checked by traps and never by a tag clear.** The model's
`cap_access_checks` faults a store of a tagged capability without
store-capability, and of a local one without store-local, and otherwise stores
the value with its tag. The imported store path cleared the stored tag where the
authority lacked store or capability permission or failed the levels test. The
stored tag is now the value's own, and the data check
raises `CapEx_PermitStoreCapViolation` and `CapEx_PermitStoreLocalCapViolation`
on the capability store, below the permission, seal and tag checks and above the
length check in the model's priority.

**Every bounds test the width collapse made modular is the format package's.**
The collapsed top is 37 bits, so the imported load/store test summed the 64-bit
address and size in 64 bits and wrapped, and exempted any capability at the root
exponent, whose bounds now cover 2^36 bytes and not the whole space. The issue
stage's fetch test cast the 64-bit PC to the 36-bit address type. Both call
`in_cap_bounds`, which states `inCapBounds` over the effective address at 65 bits
and is held by the crosscheck. An eight-byte data access at `2^64 - 8` passed the
imported bounds test through any capability, its end wrapping to zero, and a
fetch at `2^36 + 0x100` passed it under a code capability with bounds
`[0, 0x1000)`, its PC aliasing to `0x100`. Each is a length violation in the
model, and `in_cap_bounds` refuses both by its own arithmetic; no simulation of
the staged core has exercised either case.

**The merged file's integer view is the memory form.** The model's register
holds the decoded capability, and its integer reading and writing are
`regval_from_reg = capToMemBits` and `regval_into_reg = int_to_cap`
(`model/model/core/reg_type.sail`). The imported `reg_to_x` read the register's
low 64 bits and `x_to_reg` set a null capability's address, which the imported
layout made equal to the integer. At the frozen record the address is 36 bits
and the upper 28 bits of the record are decoded fields, so both helpers now call
`reg_to_int` and `int_to_reg`. Reading back an integer write returns the
integer, by the packed form's decode and encode being inverse on its bits and
the null transform cancelling; the width check exercises that over 65,732
integers, every single-bit, single-cleared-bit and low-mask pattern among them.

## The next layer

With seam 4 in place the curated arm elaborates, so what stands is no longer a
name or member the elaborator refuses. Two classes are measured and open.

**Raw readings of a register-width value.** The imported datapath reads a
register's integer value and a capability's address by one slice of its low
XLEN or VLEN bits, or by an implicit truncation, and writes an integer into a
register by zero extension. The imported layout made all three the identity. At
the frozen record the integer reading is `reg_to_int`, the address reading is
`cap_addr_bits`, and neither is a slice; the integer write is `int_to_reg`. The
elaborator enumerates a floor of the sites by three predicates, given with their
counts under the evidence below, and each site needs a reading of which it is
before it is repointed. The two helpers are integer readings by their new bodies,
and the 57 calls of them in `core/` at the pin, the two definitions included,
are sites of the same class where a call is an address reading, which no
elaborator predicate sees: the load/store unit's virtual address is
`reg_to_x` of its base capability plus the offset, where the model takes
`capAddrBits` (`cap_mode_auth`). The fetch-side PC inputs at the top level, the
branch unit's jump base, link and redirect, the load/store address, and the
integer CSR views of capability CSRs are among the sites, so the staged core does
not yet compute a correct PC, jump target, data address or integer CSR value.

**The decoder decodes the standard line's encodings, not the model's.** The
imported decoder places the capability instructions on the `OP` opcode with the
RISC-V CHERI standard line's function codes, and the model places them on opcode
`0b1011011` with ISAv9's. The delta's decoder row books only the hybrid decode,
so the re-encoding is on no row.

## Acceptance predicate

The exact-source and exact-output guards pass at the selected pin, and tests
refuse changed bytes, missing matches, extra matches and altered expected output.
Curated file-list staging applies every registry row exactly once; the stock
list remains unchanged. Standalone frozen packages lint, a width probe measures
the memory/register/PCC widths, and a store-rotation test covers every lane and
bit. The existing Sail-to-RTL capability vector crosscheck remains green.
Curated elaboration records its actual remaining errors, with the removed
metadata sites absent. A smaller/different diagnostic set is seam progress;
the remaining core need not elaborate, and this acceptance gives no instruction
refinement, functional-unit completion or SoC integration credit.

Seam 4 is accepted when the curated arm elaborates with no line beginning
`%Error`, the elaboration diff reports no unexplained or inert structure, the
staging tests refuse a registry that keeps any excluded operation's decode row
or drops the reset grants, the width check holds the integer view's round trip
and the four reset roots, and the crosscheck stays green. An elaboration without
errors is a statement about names, members and widths the elaborator resolves;
it decides no instruction's semantics and no absence, and the next layer above
is open.

## Acceptance evidence

Every set below is the lines beginning `%Error` in the curated arm's output of
`python tools/run.py rtl elaborate`, under Verilator 5.052 in the lane derived
from this checkout, with `upstream/cva6-cheri` at the registry's pin and
`upstream/opentitan` at its gitlink populated under a cone sparse checkout of
`hw/ip/prim` and `hw/ip/prim_generic`. The elaborator's own
`Exiting due to N error(s)` summary line is not one of them. The first two sets
are name-resolution diagnostics, the elaborator stopping at that stage before
any member read, and the third is the member layer behind them.

**Before seam 3**, at the seam-2 registry: **44 diagnostics** over eight files,
`branch_unit.sv` 11, `cheri_unit.sv` 11, `issue_read_operands.sv` 9,
`load_store_unit.sv` 7, `csr_regfile.sv` 3, `include/ariane_pkg.sv` 1,
`commit_stage.sv` 1 and `cva6.sv` 1, naming sixteen unresolved identifiers:
`CAP_PERM_VIOLATION` 6, `set_cap_reg_flags` 5, `cap_tval2_t` 4,
`get_cap_reg_flags` 4, `CAP_BOUNDS_VIOLATION` 3, `CAP_SEAL_VIOLATION` 3,
`CAP_TAG_VIOLATION` 3, `legalize_arch_perms` 3, `SENTRY_CAP` 3,
`CAP_INSTR_FETCH_FAULT` 2, `cap_report_perms_t` 2,
`hperms_and_uperms_to_report_perms` 2, `CAP_DATA_ACCESS_FAULT` 1,
`CAP_JUMP_BRANCH_FAULT` 1, `REG_ROOT_CAP` 1 and `report_perms_to_hperms` 1.

**After seam 3**: **4 diagnostics** over two files, `cheri_unit.sv` 3 and
`include/ariane_pkg.sv` 1, naming three identifiers, `SENTRY_CAP` 1,
`get_cap_reg_flags` 1 and `set_cap_reg_flags` 1 at `cheri_unit.sv` and
`REG_ROOT_CAP` 1 at `include/ariane_pkg.sv`, the three classes the seam 4
decisions resolve, and no other imported identifier. The registry staged ten
sources at 75 replacements, each source guarded by its exact input and output
identity.

Neither of those runs elaborates the core and neither is asked to: both sets are
facts about names and not about members.

**The member layer, with the three classes resolved**, at a registry of ten
sources and 86 replacements: **42 diagnostics** over three files and thirteen
source lines, every one a member the frozen record does not declare. `load_store_unit.sv` 23 at five lines, the levels, load-mutable,
load-capability and store-level reads of `hperms`; `cheri_unit.sv` 11 at four
lines, `uperms` and `hperms` in the subset test, `res_lo` and `res_hi` in the
reserved-field test, and the representable-alignment `mask`; and `load_unit.sv`
8 at four lines, the three levels clears. The last file was not a staged source,
so a search of the staged sources alone did not reach it. Every site is on a
delta deletion row and is resolved by the seam 4 decisions; the load/store
unit's store-level read is the one whose model reading is a trap rather than a
deletion.

**After seam 4**: **0 diagnostics**. The registry stages fourteen sources at 111
replacements. `rtl elaborate` completes both arms and reports the curated arm at
52 module kinds, 275 cells and 4,584 declared variables against the baseline's
63, 416 and 5,325, eleven structures the disabling parameters remove
(`amo_buffer`, `bht`, `btb`, `compressed_decoder`, `cva6_mmu`, `cva6_ptw`,
`cva6_shared_tlb`, `cva6_tlb`, `perf_counters`, `pmp_entry`, `ras`), none
displaced, introduced, unexplained or inert. These counts are the tool's JSON
inventory under 5.052 and are not comparable with the XML figures R1 took under
5.032.

The curated arm is not warning-free. Re-running the tool's own curated
invocation over its own composed file list and staged sources keeps the output
the tool discards on success: **279 lines beginning `%Warning`**, `WIDTHEXPAND`
110, `SELRANGE` 81, `WIDTHTRUNC` 78, `UNSIGNED` 7, `CMPCONST` 2 and `ASCRANGE` 1.
Of the `SELRANGE` lines, 77 select index 1 of a one-entry dimension in the issue,
commit and realignment paths at one issue port, 2 read 64 bits of the
instruction cache's 4-bit user field, and 2 are the CHERI unit's upper-half
reads, `GCHI` and `SCHI` selecting `[127:64]` of the 65-bit memory form. The next
layer's integer-view class has three elaborator predicates, each a floor of
candidates: **21** selects of bits `[63:0]` or `[63:2]` of a 68-bit variable,
at `branch_unit.sv` 8, `csr_regfile.sv` 5, `cva6.sv` 4, `ex_stage.sv` 2,
`cheri_unit.sv` 1 and `issue_read_operands.sv` 1; **25**
`WIDTHTRUNC` lines whose right side is 68 bits, and **33** `WIDTHEXPAND` lines
whose target is 68 bits. The elaborator folds a select of a 68-bit member of a
wider packed structure into a select of the structure, so reads such as the
branch unit's `fu_data_i.operand_a[VLEN-1:0]` and the store unit's
`lsu_ctrl_i.data[XLEN-1:0]` are found by reading and not by the first predicate.
