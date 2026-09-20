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
capability mode whatever the imported field comment says. **The deletion is not
whole in the staged core**, because these rows name the issue stage, the commit
stage and the top level: the decoder's own mode output and `id_stage.sv`'s reset
to the integer mode are the mode pipeline the
[delta](rtl-reparameterization-delta.md) books at §2.2, and a staged core out of
reset decodes in the integer mode until its first redirect.

`cjalr` admits a forward-edge sentry as its target and writes its return address
already sealed as a backward-edge one (R-15-068, R-15-071), so the branch unit's
two single-sentry reads take the forward-edge and backward-edge constants
respectively. The signed comparison the imported test made over a one-bit object
type goes with the widened field.

**Three site classes stay unresolved and each is recorded rather than aliased.**
The CHERI unit's seal-entry arm seals to the edge the instruction names, and no
register entry names an edge for a single seal-entry opcode, so which edge that
opcode seals is an instruction-encoding decision this seam does not take. The
same unit's get-mode and set-mode arms are instructions the one-mode reading
deletes rather than re-values, and whether an opcode exists is the decoder's.
The ariane package's single root feeds nine reset sites of two kinds, the `PCC`
and capability trap registers on the execute side and the default data
capability on the data side; R-15-007l and R-15-007p make one almighty root
inexpressible and fix that the split exists, and which of the two roots each
surviving site takes follows the CSR seam's own decision about which of those
registers this profile keeps. No root alias is introduced over either root.

**The member layer behind those names is not reached, and its residue is
enumerated rather than claimed absent.** The elaborator stops at an unresolved
type or constant name before it reads a member, so no member access in the
staged sources has been compiled. Searching them for an access whose name the
frozen records do not declare finds twelve lines of code and one comment. Nine
are on the capability record, four in `cheri_unit.sv` and five in
`load_store_unit.sv`, naming `uperms`, `hperms`, `res_lo`, `res_hi` and `addr`;
one is the representable-alignment `mask` on the bounds-return record in
`cheri_unit.sv`; and two read the imported scoreboard entry's `int_mode` in
`csr_regfile.sv`. Each sits on a row the
[delta](rtl-reparameterization-delta.md) books as a **deletion** rather than a
repointing: the capability-reconstruction and subset-test pair (R-15-002,
R-15-006, R-15-007m) with the reserved-field test beside it, `CRAM` and its mask
(R-15-007k, R-08-011), the levels signals whose three permission bits the frozen
lattice replaces with the local/global discipline (R-08-005, R-15-074), and the
mode pipeline. Deleting an excluded instruction's arm, or the readers of a
deleted pipeline, is decoder and functional-unit curation, so this seam repoints
what the frozen format has a name for and leaves each of those to the row that
owns it.

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

## Acceptance evidence

Both sets below are the lines beginning `%Error` in the curated arm's output of
`python tools/run.py rtl elaborate`, under Verilator 5.052 in the lane derived
from this checkout, with `upstream/cva6-cheri` at the registry's pin and
`upstream/opentitan` at its gitlink populated under a cone sparse checkout of
`hw/ip/prim` and `hw/ip/prim_generic`. The elaborator's own
`Exiting due to N error(s)` summary line is not one of them. Both are
name-resolution diagnostics: the elaborator stops at that stage, so neither set
says anything about the member reads behind it.

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
`REG_ROOT_CAP` 1 at `include/ariane_pkg.sv`. Every one is a site the section
above records as unresolved, and no other imported identifier is left. The
registry stages ten sources at 75 replacements, each source guarded by its exact
input and output identity.

Neither run elaborates the core and neither is asked to. **What the second set
decides is a fact about names and not about members**: no imported cause
constant, trap-value type, permission-report helper or mode reader is left
unresolved outside the three classes the section above records. What it does not
decide is any member read, any instruction's semantics, or any absence. The
member residue that section enumerates lies behind this stage, and no run has
reached it; the registry's own edits are held against the frozen field list by
the staging tests instead.
