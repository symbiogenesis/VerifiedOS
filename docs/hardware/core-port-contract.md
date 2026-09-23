# Scalar core port contract

This contract fixes the interfaces the curated scalar core presents to the SoC
top R1c-ii authors: the shared widths, the exception record, the top-level core
ports and the memory-request boundary the flat-SRAM replacement stands at. It is
a review of the imported CHERI-CVA6 top at `36a1dc5c` under the curated
configuration and the [scalar staging contract](scalar-width-transform-contract.md),
and it binds the parts of that boundary this repository has decided. It claims
no functional correctness of the core behind the ports: the staging contract's
next layer lists the register-width readings still owed, several of them at
these ports.

## Widths

Every width below is derived, not restated: the configuration package
[`vos_c_class_config_pkg.sv`](../../rtl/vos_c_class_config_pkg.sv), the imported
`build_config_pkg.sv` as staged, and the format packages
[`vos_cheri_pkg.sv`](../../rtl/vos_cheri_pkg.sv) and
[`vos_cva6_cheri_pkg.sv`](../../rtl/vos_cva6_cheri_pkg.sv) own them, and the
width check measures the register, PCC and memory widths.

| Name | Bits | Owner and meaning |
| --- | --- | --- |
| `XLEN`, `VLEN` | 64 | Configuration record; integer and virtual-address width |
| `CLEN` | 64 | `cva6_cheri_pkg::CLEN`; the memory word, one capability granule |
| `CTLEN` | 65 | `cva6_cheri_pkg::CTLEN`; the memory form `{tag, bits}` |
| `REGLEN`, `PCLEN` | 68 | `$bits(cap_reg_t)`; the decoded capability record, register and PCC |
| `CLEN_ALIGN_BYTES` | 3 | `$clog2(CLEN/8)`; the byte-offset bits within a granule |
| `PLEN` | 56 | Imported build rule for a 64-bit core |
| `GPLEN` | 41 | Imported build rule; carried by `tval2`, which no cause here writes |
| Capability address | 36 | `CapAddrWidth`; an address above 2^36 is never inside a capability's bounds |
| AXI address, data, ID, user | 64, 64, 4, 1 | Configuration record |

A register holds the decoded record. Its integer reading is the memory form
`reg_to_int` and its address reading is `cap_addr_bits`; neither is a slice of
the record's low bits, whose upper 28 are decoded metadata. Any port declared
`PCLEN` or `REGLEN` wide therefore carries a decoded capability, and a consumer
takes its address or integer through those functions.

## Exception record

The imported `exception_t` is `{cause, tval, tval2, tinst, gva, valid}` at
`XLEN`, `XLEN`, `GPLEN`, 32, 1 and 1 bits. A capability violation writes
`cause = CAP_EXCEPTION = 28`, `tval = capex_tval(code, regnum)` and `tval2 = 0`:
the eleven-bit payload is the five-bit cause code of `cap_causes.sail` below the
six-bit register index, zero-extended, with `PCC_IDX = 0b100000` naming the
program counter. The generated region of the adapter owns the codes, the index
width and the packing (K-104). `gva` is zero, the hypervisor extension being
off. Every other cause is the base ISA's, reported by the imported pipeline.

## Top-level ports

| Port | Width | Direction | What the top drives or reads |
| --- | --- | --- | --- |
| `clk_i`, `rst_ni` | 1 | in | Core clock and active-low asynchronous reset |
| `boot_addr_i` | `PCLEN` | in | The code root with its address set to the reset vector, `set_cap_addr_checked(RootCodeCap, reset_vector)` |
| `hart_id_i` | `XLEN` | in | The hart's index in the composition |
| `irq_i` | 2 | in | Tied low |
| `ipi_i` | 1 | in | Tied low |
| `time_irq_i` | 1 | in | The slot-boundary timer's pending line, `MTIP` |
| `debug_req_i` | 1 | in | Tied low |
| `rvfi_probes_o` | probe record | out | Read by the trace adapter, never by the SoC's function |
| `cvxif_req_o`, `cvxif_resp_i` | record | out, in | Response tied to zero; `CvxifEn` is off |
| `noc_req_o`, `noc_resp_i` | AXI4 with atomic operations | out, in | The memory side below |

**The reset vector is an integer and the reset authority is not the top's.** The
model resets `PC` to `pc_reset_address` and `PCC` to the code root whatever that
address is (`model/model/sys/sys_control.sail`, `model/model/postlude/step_ext.sail`),
and the staged core resets `pcc_q` to `REG_ROOT_CODE` and its register file to
the model's grants without reading this port. The port keeps the imported
`PCLEN` shape because the imported CSR file derives the reset `mtvec` capability
from it; the top drives the code root there so that the reload's authority is
the one the model resets `MTCC` to. Which address the reset vector is follows the
composition and the measured-boot handoff that places the M-mode image
(R-09-006), not this contract. The core's two readers of the port's address, the
frontend's boot PC at `cva6.sv:723` and the `mtvec` reload at
`csr_regfile.sv:1264` in the staged numbering, still read the record's low bits
and are in the staging contract's next layer.

**One asynchronous input is live.** The slot-boundary timer is the core's only
asynchronous trap (R-15-066a, R-17-018), so the external and software interrupt
inputs are tied low and the top offers no platform interrupt controller to the
core. `SoftwareInterruptEn` is off in the configuration record. The debug module
is not imported and `DebugEn` is off, so the debug request is tied low.

## Memory side

At the core's boundary the memory side is AXI4 with the atomic-operation
extension (`NOC_TYPE_AXI4_ATOP`): 64-bit address and data, four-bit IDs and one
user bit. The AW and AR user fields are driven zero; the W and R user bit of each
64-bit beat is the capability tag of that beat's granule. At the collapsed
granule one beat carries exactly one capability and one tag (delta §2.4). The
tag controller or the top's memory holds the tag beside the word; nothing on this
port carries a tag for a partial word.

## Memory-request boundary inside the core

The load/store unit and the frontend reach memory through the cache subsystem's
ports, and those ports are the boundary the flat-SRAM replacement stands at
through a `SUBSTITUTIONS` row in the imported manifest's place, keeping them, so
the TSO store buffer and the load path develop against it before the replacement
exists. The imported `wt_cache_subsystem` ports are:

| Port | What it carries at the curated configuration |
| --- | --- |
| `icache_areq_i`, `icache_areq_o` | Fetch address translation; the MMU is absent, so the physical address is the virtual one |
| `icache_dreq_i`, `icache_dreq_o` | Fetch data requests and responses with their fetch exceptions |
| `icache_en_i`, `icache_flush_i` | Cache enable and flush, which a cacheless replacement accepts and completes |
| `dcache_req_ports_i/o[4]` | Four data request ports: 0 the page-table walker, tied off; 1 the load unit; 2 the accelerator, inactive; 3 the store buffer, which wins it from the accelerator |
| `dcache_amo_req_i`, `dcache_amo_resp_o` | Atomic requests from the commit stage; no instruction issues one while `RVA` is off |
| `dcache_enable_i`, `dcache_flush_i`, `dcache_flush_ack_o` | Enable, flush and its single-cycle acknowledge |
| `wbuffer_empty_o`, `wbuffer_not_ni_o` | Write buffer drained, which the top level's no-store-pending signal ANDs in for the commit side; and no non-idempotent write pending, which the load unit waits on before a non-idempotent load |
| `noc_req_o`, `noc_resp_i` | The AXI side above |
| `inval_addr_i`, `inval_valid_i`, `inval_ready_o` | Coherence invalidations, unused here |

A data request port carries `dcache_req_i_t` in and `dcache_req_o_t` out. At
this width `data_wdata` and `data_rdata` are one 64-bit granule and `data_be` its
eight byte enables. `address_index` is sent first and `address_tag` follows with
`tag_valid` once the address is known; that tag is the address's upper part and
not a capability tag. The capability tag rides `data_wuser` on a store and
`data_ruser` on a load response: a capability store carries the stored value's
tag, every other store carries zero, and a store whose enables do not cover the
whole granule writes the tag clear, so no data write leaves a capability
standing. A load may carry `strip_tag`, which the response echoes as
`data_strip_tag`, and the load unit then delivers the value untagged. `kill_req`
cancels a load between its two phases, and `data_gnt`, `data_rvalid` and
`data_rid` sequence the transaction.

## What stays owed at the boundary

The contract fixes the interfaces the top binds; it does not implement them.
The core's own readings of `boot_addr_i`, of the commit, exception-return and
trap-vector PCs at the frontend, and of the load/store address are register-width
readings in the staging contract's next layer. The flat-SRAM replacement, the
TSO store buffer and the revocation load filter are not written, and the tag
plane behind the AXI side is R1c-ii's and the fabric's. Whole-SoC elaboration
waits for those; the map-facing and device packages proceed against this
contract.
