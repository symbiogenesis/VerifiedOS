# The RTL Re-Parameterization Delta

*The per-site account of what the frozen 64+1-bit capability format requires of the imported CHERI-CVA6 datapath, which implements the ISAv8/v9 128-bit lineage. The [plan's §11](implementation-checklist.md#11-building-an-fpga-from-it-all) says the format is **re-parameterized, not configured**, and books that under R1; this document is the enumeration that makes the R1 estimate a measurement rather than a guess.*

> **Precedence.** [The Sail model](../model/model/core/cap_format.sail) is the definition and this document is a reading of it against one importable implementation. Where the two disagree the model wins and this document is defective. [The frozen profile's §4.1](isa-profile.md#41-the-capability-format) is the prose the model implements, and R-15-007a is the obligation the narrowing owes.

## 1. What is read, and at which revision

Every site below is read from the tree at a pin, not from a description of it.

| Side | Artifact | Revision | Read |
| --- | --- | --- | --- |
| Definition | `model/model/core/cap_format.sail`, `cap_common.sail`, `cap_causes.sail` | this repository's curated model | 2026-08-23 |
| Implementation | `upstream/cva6-cheri`, `core/` | `36a1dc5c` | 2026-08-23 |
| Interconnect | `upstream/axi-cheri-tagcontroller` | `173646d5` | 2026-08-23 |
| Integration | `upstream/mocha`, `hw/top_chip/` | `ef1370c1`, tagged `v0.1.1` | 2026-08-31 |

The two capability formats, stated as their own sources state them:

| | Frozen dialect | CHERI-CVA6 at `36a1dc5c` |
| --- | --- | --- |
| Width, excluding the tag | 64 | 128 (`CLEN = 2 * XLEN`) |
| Address field | 36, stored uncompressed | 64, the whole `XLEN` |
| Permissions | one 5-bit code naming one of 32 enumerated sets, expanded to a 12-bit architectural bitmap | 9 independent architectural bits, 4 software-defined bits, 22 reserved bits |
| Object type | 4 bits, sixteen classes, unsealed `0b1111` | 1 bit, unsealed `0`, sentry `1` |
| Exponent | 5-bit field, normalized case carried IEEE-754 fashion in the field itself | 6 bits, split into two 3-bit halves stolen from the mantissa low bits, selected by a separate `EF` format bit |
| Base mantissa | 8 | 14 |
| Top mantissa | 6 stored, high two derived | 12 stored, high two derived |
| Maximum effective exponent | 30 | 52 |
| Reserved fields | none; the table spends 64 bits exactly | 22 bits across `res_hi` and `res_lo` |
| Capability-mode flag | none; the machine is purecap-only | one `int_mode` bit, and a hybrid decode path behind it |
| Tag-plane granule | one tag per 64-bit granule | one tag per 128-bit region |

Two consequences of that table govern everything below. The first is that **`CLEN` collapses onto `XLEN`**: a capability and an integer occupy one register and one memory word, so every place the imported datapath distinguishes a capability-width quantity from an integer-width one loses its distinction. The second is that **the bounds encoding is not a narrowing of the imported one**: the frozen format has no internal-exponent flag and steals no mantissa bits, so the functions that pack and unpack bounds are replaced rather than re-parameterized.

## 2. The site register

Sites are grouped by what a curator does to each, because that is what prices them. A **width** site follows a changed parameter and needs reading, not authoring. A **literal** site carries a constant that a parameter change does not reach. A **structure** site is a declaration whose shape changes. A **rewrite** site is a function whose algorithm the frozen format states differently. A **deletion** site has no counterpart at all. A **new** site is behaviour the frozen format requires that the imported tree does not have.

### 2.1 The format package

All of `core/include/cva6_cheri_pkg.sv`, which is where the format is fixed.

| Line | Site | Kind | What the frozen format requires |
| --- | --- | --- | --- |
| 25 | `CLEN = 2 * XLEN` | width | `CLEN = XLEN`. This one identity propagates to every row of §2.2 |
| 26 | `CTLEN = 2 * XLEN + 1` | width | `XLEN + 1`, the merged file's 65-bit register (R-15-007i) |
| 27 | `CAP_ADDR_WIDTH = XLEN` | width | 36 (R-15-002a). The address field is narrower than the effective address, which is what makes `addrInRange` in §2.5 a new check rather than a widened one |
| 28, 29 | `CAP_UPERMS_WIDTH = 4`, `CAP_UPERMS_SHIFT = 6` | deletion | no software-defined permission bits; the software classification rides the 4-bit object type, enforced (R-15-007n) |
| 30, 31 | `CAP_RSERV_HI_WIDTH = 7`, `CAP_RSERV_LO_WIDTH = 15` | deletion | no reserved field. The reserved-field legality half of upstream capability integrity is vacuous here (R-15-007a) |
| 32 | `CAP_M_WIDTH = 14` | width | 8. The stored top mantissa is `CAP_M_WIDTH - 2`, so 6 follows (R-15-007c) |
| 33 | `CAP_E_WIDTH = 6` | width | 5 |
| 34 | `CAP_E_HALF_WIDTH = CAP_E_WIDTH / 2` | deletion | no half. The frozen exponent is a field of its own and is not stolen from the mantissas; at width 5 the halving has no integral reading, so this is not a parameter that can be re-valued |
| 35 | `CAP_OTYPE_WIDTH = 1` | width | 4, sixteen classes, thirteen composition-allocatable (R-15-007) |
| 36 | `CAP_RESET_EXP = 0` | literal | the reset exponent is `cap_max_E`, 30, not zero. Every comparison against `CAP_RESET_EXP` inverts sense with it |
| 37 | `CAP_MAX_EXP = 52` | literal | 30, which is `cap_len_width - cap_mantissa_width + 1` |
| 38 | `CAP_RESET_TOP` | width | follows `CAP_M_WIDTH`; `{2'b01, 6'b0}` |
| 43 | `CAP_GUEST_EXCEPTION = 31` | deletion | no hypervisor extension, so no guest cause |
| 47 to 55 | three fault types and five violation codes | structure | eleven ISAv9 cause codes in a 5-bit field, with the reporting register above them (`cap_causes.sail`, R-15-073a) |
| 59, 60 | `UNSEALED_CAP = 0`, `SENTRY_CAP = 1` | structure | `0b1111` unsealed, `0b1110` forward-edge sentry, `0b1101` backward-edge sentry, and thirteen allocatable classes below them. The polarity inverts, so every `!= UNSEALED_CAP` test in §2.3 changes constant, and the single sentry becomes a pair the branch unit must distinguish by edge (R-15-071) |
| 69, 70 | `addrmw_t`, `addrmwm2_t` | width | follow |
| 71, 72, 74 | `resw_lo_t`, `resw_hi_t`, `upermsw_t` | deletion | with their fields |
| 78 | `cmw_t = [CAP_M_WIDTH-3:0]` | width | `[5:0]`, the profile's 6-bit stored top mantissa |
| 79, 80, 82 | `hmw_t`, `hcmw_t`, `hew_t` | deletion | with the embedded-exponent format |
| 87 to 92 | `cap_tval2_t`, a 4-bit fault type over 12 `wpri` bits over a 4-bit cause over 2 ignored bits | structure | violation type in the low five bits of `mtval`, the reporting register above it, `PCC` reported as `0b100000` outside the file's index space |
| 97 to 126 | `cap_hperms_t`, nine independent bits | rewrite | a 5-bit code and a total 32-entry expansion. Three of the nine have no counterpart at all: `cap_level`, `permit_store_level` and `permit_elevate_level` are the levels mechanism, which the frozen dialect replaces with an address-keyed revocation sidecar carrying no capability field (R-08-004a, R-08-005a). Two the frozen lattice adds that the struct does not carry: `Permit_Seal` and `Permit_Unseal`, admitted in no common set (R-15-007o), and the global bit crossing every shape (R-15-074) |
| 130 to 143 | `cap_report_perms_t` | structure | the 12-bit expanded bitmap, order `ASR US SE X LM LG SL SC LC W R` above the global bit |
| 146 to 155 | `cap_flags_t`, the `int_mode` bit | deletion | one mode. This is the largest single deletion in the datapath by site count, because the flag is threaded through decode, issue, execute, commit, the CSR file and the top level (§2.2 and §2.3, which is where those sites are enumerated; §2.4 is the tag plane and carries none of them) |
| 158 to 162 | `cap_bounds_t` | structure | `{E: 5, B: 8, T: 8}` with a `normalized` case flag in place of the format bit |
| 165 to 168 | `cap_fmt_t`, the `EMBEDDED_EXP` / `IMPLIED_EXP` pair | deletion | the case rides the exponent field: a zero field is the denormal case at effective exponent zero, and a field of *k*+1 is the normalized case at effective exponent *k* |
| 171 to 174 | `cap_implied_exp_fmt_t` | deletion | no second packing |
| 177 to 182 | `cap_embedded_exp_fmt_t` | deletion | no exponent stealing |
| 186 to 193 | `cap_cbounds_t`, the union over the two packings | deletion | the packed bounds are three adjacent fields at fixed positions |
| 196 to 203 | `cap_meta_data_t`, comparisons over the full 14-bit mantissa against `r` | rewrite | the frozen model derives the representable limit from the top three mantissa bits and compares in three bits. The correspondence between the two formulations is itself part of what R-15-007a's representation-correctness proof owes |
| 241 to 285 | `DEFAULT_BOUNDS_CAP`, `REG_ROOT_CAP`, `REG_NULL_CAP`, `MEM_NULL_CAP` | structure | one root capability becomes **two**: no admitted permission set holds both store and execute, so composition hands each core an execute-side and a store-side authority and a single almighty root is inexpressible (R-15-007l, R-15-007p) |
| 311 to 319 | `legalize_arch_perms` | deletion | the enumeration is total, so no encoding is illegal and there is nothing to legalize. Its two consumers in `cheri_unit.sv` become constant-false (§2.3) |
| 332 to 336 | `set_cap_mem_addr_inc`, 12-bit immediate sign-extended over `CAP_ADDR_WIDTH` | width | over 36 |
| 391 | `exp > CAP_MAX_EXP ? CAP_MAX_EXP` | literal | 30 |
| 394, 395 | `{2'b00, cap.addr}` at 66 bits, sliced `[XLEN+1-exp -: CAP_M_WIDTH]` | literal | 38 bits, sliced at the frozen widths |
| 396 | `r = base_bits - 14'b01000000000000` | literal | a 14-bit literal with no re-parameterized reading; the frozen limit is `B3 - 0b001` over the top three bits |
| 421, 423, 432, 433 | four `66'b0` concatenation literals | literal | `cap_addr_width + 2`, so 38 |
| 424, 432, 491 | three `52'b0` shift literals | literal | the frozen shift distance, which is not `CAP_MAX_EXP` on this side either |
| 427 to 430 | the malformed-bounds predicate, cased on `exp == 0` and `exp == 1` | rewrite | which triples derive a top below their base is a property of the algorithm at 8 and 6 bits, and R-15-007a states decode as a total function over the 19-bit bounds encoding and characterizes that set at these widths rather than inheriting it |
| 436 | the top-wrap correction, guarded `exp > 1` | rewrite | the frozen guard is `E < cap_max_E - 1`, which is a different predicate and not a re-valued constant |
| 447 | `are_cap_reg_bounds_root`, `exp == CAP_RESET_EXP` | literal | the frozen reset exponent is the maximal one, so the test inverts |
| 450 to 460 | `get_cap_reg_flags`, `set_cap_reg_flags` | deletion | with `int_mode` |
| 493 | `getLength` saturating at `CAP_RESET_EXP`, carrying an upstream comment reading *short of being correct* | rewrite | the frozen `getCapLength` is a wrapping quantity with a stated assertion that a tagged capability has `top >= base`. This is a named upstream defect and the re-parameterization must not carry it across |
| 506 to 525 | `set_cap_reg_address`, `T_W = CAP_ADDR_WIDTH - CAP_M_WIDTH` | width and new | widths follow, but the frozen `setCapAddr` additionally clears the tag when the address lies above 2^36, a condition with no upstream counterpart because upstream's field is the whole address space |
| 546 to 556 | `is_offset_in_range` | deletion | dead on arrival upstream: it assigns its result and then unconditionally overwrites it with zero. The live path is `fastRepCheck`, which the frozen model states over `cap_max_E - 2` |
| 559 to 564 | `bot3z`, `add_b1000` | deletion | both exist to zero and round the three mantissa bits the embedded exponent occupies. Nothing occupies them here |
| 575 to 677 | `set_cap_reg_bounds`, 103 lines | rewrite | the frozen `setCapBounds` is 42 lines with a different shape: one exponent choice from a leading-zero count, one `norm` decision, one conditional exponent increment, and none of the `int_exp`, `lmask_lo`, `lmask_lo_ovflw`, `len_carry_in`, `len_max` or `len_max_less_1` family. **This is the single largest item in the delta** |
| 577, 674 | the returned representable-alignment `mask` | deletion | `CRAM`, `CRRL` and `CSetBoundsExact` are excluded: their consumer is a runtime allocator and allocation here is composition-time, so every emitted narrowing is exactly representable by construction (R-15-007k, R-08-011) |
| 663 | `final_exp == 6'd0` | literal | a 6-bit width literal inside a comparison against zero |
| 697 to 736 | `cap_reg_to_cap_mem`, `cap_mem_to_cap_reg` | rewrite and new | the frozen boundary is `capToMemBits` and `memBitsToCapability`, which pack three adjacent bounds fields, derive the top mantissa's high two bits from the base's, and **exclusive-or the whole word with the null capability's bits in both directions**, so that an all-zeroes granule reads back as canonical `NULL`. The imported tree has that transform on the store path only (§2.2), so the load path gains it |
| 744 to 782 | `hperms_and_uperms_to_report_perms`, `report_perms_to_hperms` | rewrite | `perms_expand` and `perms_narrow`. `perms_narrow` searches all 32 codepoints for the largest admitted set contained in the mask, which is how a bitwise mask reaches a non-orthogonal field and is the one place in the format path where the frozen dialect is **more** logic than the imported one |
| 804 to 811 | `count_zeros_msb`, returning `ew_t` | width | returns 5 bits and counts over the frozen slice |
| 820 to 823 | `extract_addr_mid`, a left shift by the exponent | rewrite | the frozen model takes a right shift; the two formulations are not the same expression at the same widths |
| 831 to 857 | `decode_bounds` | rewrite | with the two-format union gone, decode is the top-two-bit derivation alone. The three hard-coded slices `[11:0]`, `[13:12]` and the two `3'b000` steals are the M=14 positions and become `[5:0]` and `[7:6]` with no steal |
| 865 to 889 | `encode_bounds` | rewrite | the frozen packing is field-adjacent, and the exponent-half extraction has no counterpart |

Read at `36a1dc5c` on 2026-08-23, 94 lines of that one file mention a format parameter by name, and every function above the halfway mark of the file is on the list. The package is not a place where a curator changes seven numbers.

### 2.2 The width identity, outside the package

`CLEN = 2 * XLEN` is declared twice and consumed across the datapath. Every row here is a site the identity's collapse reaches.

| File | Lines | Kind | What the frozen format requires |
| --- | --- | --- | --- |
| `core/include/ariane_pkg.sv` | 34 | width | `CLEN = CheriPresent ? 2 * XLEN : XLEN` becomes `XLEN` on both arms |
| `core/include/build_config_pkg.sv` | 37, 41, 45 | width | `cfg.CLEN`, `cfg.PCLEN = $bits(cap_reg_t)`, and `cfg.CLEN_ALIGN_BYTES = $clog2(CLEN/8)`, which falls from 4 to 3 |
| `core/store_unit.sv` | 97 to 133 | deletion | `data_align` rotates a store's data into the upper half `[CLEN-1:XLEN]` through a 16-way case. At `CLEN == XLEN` there is no upper half, and the whole table has no referent |
| `core/store_unit.sv` | 314, 317, 318 | rewrite | the store path's capability encode and its null exclusive-or, at the collapsed width |
| `core/load_unit.sv` | 108, 229, 539, 540, 565, 566, 578, 620 | width and new | the load path's alignment, sign bits and decode. Line 620 decodes without the null exclusive-or its store-side partner performs, which the frozen definition puts on both sides |
| `core/load_unit.sv` | 627 to 635 | deletion | the three levels clears (`clr_elevate`, `clr_cap_level`, `clr_load_mutable`) act on format bits that do not exist here; the frozen load's tag clear is the revocation-sidecar check instead (R-08-005) |
| `core/load_store_unit.sv` | 194, 952, 1003, 1007, 1011, 1064, 1073 to 1083, 1106 | width and deletion | the access-size constants follow the collapse; the levels signals go with their bits |
| `core/store_buffer.sv` | 45, 47, 60, 62 | width | the buffer holds `CLEN` data and `CLEN/8` byte enables |
| `core/amo_buffer.sv` | 28, 44 | deletion | the buffer goes with `A` (A-13) |
| `core/commit_stage.sv` | 62, 64, 132, 173, 174 | width and deletion | `PCLEN` ports follow; the `int_mode` write to `PCC` goes |
| `core/branch_unit.sv` | 35, 59, 60, 123, 129, 131, 208, 226, 230 to 232 | width and structure | `PCLEN` ports follow; the single `SENTRY_CAP` becomes an edge pair, and `cjalr` must admit a forward-edge sentry as a target and write its return address already sealed as a backward-edge one (R-15-068, R-15-071) |
| `core/issue_read_operands.sv` | 72, 74, 250, 252, 367, 491, 493, 522, 528, 534 | width and deletion | `PCLEN` ports and the `PCC` registers follow; the `int_mode` set and get go |
| `core/cva6.sv` | 148, 176, 223, 227, 239, 342, 399, 459, 566, 121, 184, 662, 806, 807, 915 | width and deletion | the top-level data and `PCLEN` ports follow; the `int_mode` and `clr_cap_level` wires go |
| `core/ex_stage.sv`, `core/csr_regfile.sv`, `core/scoreboard.sv`, `core/id_stage.sv`, `core/issue_stage.sv` | 55; 46, 68; n/a; 103 to 106, 164 to 172, 184, 340, 368, 474 to 496; 59, 300 | width and deletion | `PCLEN` ports follow; the `int_mode` pipeline, which `id_stage.sv` carries as a per-issue-port shift register with its own reset value, goes whole |
| `core/cva6_rvfi.sv` | 106, 107, 257, 258, 259, 296, 373, 380 | width | the commit trace's read and write masks are `CLEN/8` wide. This is the port [the differential corpus](differential-corpus.md) reads, so its width change is visible to the co-simulation gate rather than internal |
| `core/cache_subsystem/wt_dcache*.sv`, `wt_axi_adapter.sv`, `wt_cache_subsystem.sv` | 109 lines across the seven write-through files | width | the cache's banks, byte enables, write buffer, miss unit and AXI adapter are all stated in `CLEN`. **A-09 and A-10 delete these blocks outright**, so the work here is deletion rather than re-parameterization, and the lines are counted so that a curator who keeps a cache through bring-up knows what the keeping costs |
| `core/cache_subsystem/wt_dcache_missunit.sv` | 362 | deletion | a 128-bit atomic's second half, selected as `data[CLEN +: CLEN]`. No such access exists at the collapsed width, and `A` is excluded anyway |
| `core/cva6_mmu/cva6_ptw.sv` | 661, 663 | deletion | with the MMU (A-14) |

### 2.3 Permissions, object type and mode, in the functional units

| File | Lines | Kind | What the frozen format requires |
| --- | --- | --- | --- |
| `core/cheri_unit.sv` | 102 to 113 | rewrite | `ACPERM` masks the reported permission bitmap and re-legalizes. The frozen `candperm` intersects and then takes `perms_narrow` of the result, so the operation is a 32-way largest-subset search and not a bitwise and |
| `core/cheri_unit.sv` | 115 to 155 | deletion | `CBLD` and `SCSS`, the capability-reconstruction and subset-test pair, are both excluded, the first at the root and the second on both of its consumers (R-15-002, R-15-006, R-15-007m) |
| `core/cheri_unit.sv` | 148 | deletion | the reserved-field test, with the fields |
| `core/cheri_unit.sv` | 161 to 163, 244 to 248 | deletion | `GCMODE` and `SCMODE`, with `int_mode` |
| `core/cheri_unit.sv` | 169 to 172, 249 to 255 | width | `GCHI` and `SCHI` read and write the capability's upper `XLEN` bits. At the collapsed width the upper half is the metadata itself, so these keep their meaning and change their slice |
| `core/cheri_unit.sv` | 174 to 183 | structure | `GCPERM` answers in the 12-bit expanded bitmap |
| `core/cheri_unit.sv` | 189 to 191 | width | `GCTYPE` returns four bits, and the architectural reading of a reserved type is a sign-extension rather than a zero-extension |
| `core/cheri_unit.sv` | 204 to 208 | structure | `SENTRY` must seal to the edge the instruction names |
| `core/cheri_unit.sv` | 217 to 233 | deletion | `CRAM` goes; `SCBNDSR` and `SCBNDS` keep their obligation and take the rewritten `setCapBounds` |
| `core/cheri_unit.sv` | 275, 276, 285, 286 | deletion | `operand_*_hperms_malformed` is constant false: the permission enumeration is total, so no operand carries a malformed permission encoding |
| `core/decoder.sv` | 92, 100, 101, 204, 206, 371, 498, 1101, 1109, 1383, 1412, 1447, 1482, 1724, 1839, 1853, 1867 | deletion | the hybrid decode. Every `use_ddc` assignment goes with the default data capability the frozen model does not carry, and the mode-selected `JALR`/`CJALR` and `JAL`/`CJAL` pairs collapse to their capability arms |
| `core/compressed_decoder.sv` | 28, 59, 93, 279, 452, 826, 913, 942 | deletion | the whole file goes with `C` |
| `core/csr_regfile.sv` | 1091, 2645, 2648, 2819, 2970 | structure and deletion | the sealed-capability test changes constant; the mode-selected capability CSR read and write go; the access-system-registers check stays and reads the expanded bitmap |

### 2.4 The tag plane and the bus user bits

The imported tag path carries one tag per 128-bit region on the AXI user bits, with the tags in a memory block of their own. This platform's granule is 64 bits (R-15-203), so the shape transfers and the parameterization does not.

| File | Lines | Kind | What the frozen format requires |
| --- | --- | --- | --- |
| `mocha/hw/top_chip/rtl/top_pkg.sv` | 114, 115 | literal | `CapSizeBits = 128` becomes 64, and the tag store's length, `DRAMPhysicalLength >> $clog2(CapSizeBits)`, doubles with it |
| `mocha/hw/top_chip/rtl/axi_sram.sv` | 21, 88 | literal | the tag-bit address width, stated as `AddrWidth - $clog2(CapSizeBits/8)`, gains a bit |
| `axi-cheri-tagcontroller/src/axi_tagctrl_top.sv`, `axi_tagctrl_reg_wrap.sv` | 16, 128 | width | `CapSize` is a real parameter with a 128 default, so the granule change is a parameter here and not a rewrite |
| `axi-cheri-tagcontroller/src/axi_tagctrl_w.sv`, `axi_tagctrl_r.sv` | 119, 202; 79, 122 | width | the tag-bit index, `a_x_addr[$clog2(CapSize/8) +: $clog2(AxiDataWidth)]`, shifts down one bit, and the number of tags a beat carries doubles |
| `axi-cheri-tagcontroller/src/axi_tagctrl_ax.sv` | 92, 97, 105 | width | the block-size arithmetic follows |
| `cva6-cheri/core/cache_subsystem/wt_dcache_mem.sv` | 156, 295 | width | the user-bit indexing carries a `(CLEN/XLEN)` factor, which is exactly the two-beats-per-tag mapping. At the collapsed width the factor is one, and one AXI beat carries exactly one tag. This is the site where the frozen granule makes the bus **simpler** than the reference |
| `cva6-cheri/core/include/cv64a6_imafdczcheri_sv39_config_pkg.sv` | 33, 42 | n/a | `CheriCapTagWidth = 1` and `DataUserWidth = CheriCapTagWidth` are already right, and stay |

The tag controller also holds a **tag cache**, which A-11 excludes: CHERI tags ride the SRAM word here and no separate tag hierarchy exists. What transfers from the reference is the separate tag block and the user-bit carriage, not the caching in front of them.

**The two `mocha` rows are sites in a file this plan does not take, and that is why they are literal rows rather than work.** Both sit in the bring-up SoC's own top-level glue, and taking that top whole is the arm the plan refuses: it would import an address map from a design that fields an MMU this profile deletes. The top this design carries is authored over [the frozen profile's composition](../model/config/verifiedos.json) instead, and it is owed rather than written: R1c-ii has authored the map-facing half alone, so no file here states the frozen granule yet and what these two rows record is a reference literal with no destination on this side rather than one an authored top has already restated. What does transfer from this section is the fabric's own `CapSize`, which is a parameter on the tag controller rather than a rewrite, and the collapsed-width fact that one AXI beat carries exactly one tag.

### 2.5 Behaviour the frozen format requires and the imported tree does not have

Five sites are additions rather than changes, and each is named because a delta read as narrowing alone would miss them.

1. **The null exclusive-or on the load path.** `capToMemBits` and `memBitsToCapability` apply it in both directions; `store_unit.sv:317` applies it on the store side only, so `load_unit.sv:620` gains it. An all-zeroes granule must read back as untagged `NULL`, which is what eager zeroize and `cbo.zero` rely on being able to do (R-15-182, R-15-060).
2. **The out-of-range address clear.** `setCapAddr` clears the tag when the address exceeds the 36-bit field. Upstream has no such case, its field being the whole space (R-15-002a).
3. **`perms_narrow`.** A 32-entry largest-admitted-subset search, so that `candperm` can only ever remove authority over a non-orthogonal field (R-15-007b).
4. **The forward and backward sentry edges.** `cjalr` unseals a forward-edge sentry into `PCC` and writes the return address already sealed as a backward-edge sentry, and admits neither in the other's role (R-15-068, R-15-071).
5. **The revocation load filter.** Every tagged capability load checks a sidecar bitmap at the granule containing the loaded capability's base and clears the loaded tag before architectural writeback. It replaces the levels bits the imported format carries, at one fixed latency (R-08-005, R-08-005a).

## 3. What the delta prices

The register above separates into three kinds of work, and only the first is what the word *re-parameterization* ordinarily suggests.

- **Following a parameter.** Most of §2.2 and §2.4. A curator changes the declaration and reads the consumers to confirm they follow. Cheap per site and large in count.
- **Replacing a constant a parameter does not reach.** The literal rows of §2.1. Each is a small edit and a large hazard, because a wrong one is silent: the design elaborates, the bounds decode, and a capability at one exponent is wrong.
- **Authoring against the model.** `setCapBounds`, `decode_bounds`, `encode_bounds`, the meta-data comparison, the malformed predicate, the permission expansion and narrowing, and the five additions of §2.5. These are written from `cap_common.sail` and checked against it, not edited from the imported source.

The third kind is where the estimate lives, and it is also where R-15-007a's representation-correctness proof and this work meet: the proof states encode and decode as a round trip over the 19-bit bounds encoding at these widths, and the RTL that implements them is the third implementation of the same definition, after the model and the emulator fork.

**The third kind's format half is authored, and the instrument that decides it is the model's own output.** [`rtl/vos_cheri_pkg.sv`](../rtl/vos_cheri_pkg.sv) carries the bounds decode, the bounds construction, the representable-limit comparison and the fast representability check, the address and offset setters, the length, the malformed predicate, and the permission expansion and narrowing, each authored against `cap_common.sail` rather than edited from the imported source. What decides agreement is not a reading of the two files side by side: [`tools/run.py rtl crosscheck`](../tools/vos/cli/rtl.py) compiles the model with a generator that calls those functions and prints what they return, and requires the SystemVerilog to reproduce every line, the vectors crossing as text so no adapter sits between the two implementations. That is M2.1's method pointed at the third implementation rather than the second. The declared parameters are held separately and earlier, on the host, by rule K-79, which reads the format out of the three Sail files that fix it and holds every restatement it can read as digits, this document's own §1 table included, against them; the count-word restatements, "sixteen classes" and "thirteen composition-allocatable" among them, are outside that reader and the rule says so rather than counting them. What none of that reaches is the datapath: every row of §2.2, §2.3 and §2.4 is still a site a curator visits, and the format package is what a visit to one of them now calls into rather than re-derives.
