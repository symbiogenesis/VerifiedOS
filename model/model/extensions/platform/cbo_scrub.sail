// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// `cbo.scrub`, the synchronous block verify-and-correct (R-15-177a).
//
// Every codeword in one naturally aligned CBO block is read through the
// error-detecting check, a correctably erroneous codeword is rewritten
// corrected, data plane and tag plane alike, and a detected-but-uncorrectable
// error in either plane is a fail-stop, at one fixed per-block latency whether
// anything was corrected or not (R-15-179).
//
// **It is an instruction and not an engine, and that is the whole reason it
// exists.** R-15-177 mandates background scrubbing, which on any other machine
// is an autonomous walker; a walker would fail the fifth admission test
// outright (R-15-010) and would put a memory agent outside the §11 schedule.
// So address progression stays in software: the scrubber is a kernel task in
// its own admitted background slot at a composition-time cadence, and this
// instruction is what it issues, one block at a time. The same instruction is
// what the R-15-189k exit-path sweep and the R-15-247h second-class refresh
// ride, priced in their own transition budgets rather than modeled as a second
// mechanism.
//
// **The pass is exactly value- and tag-preserving, and that is the property
// worth having.** A scrub that rewrote a block through the ordinary store path
// would clear the validity tag of every granule it covered, tag clearing being
// a property of the write path and not an instruction (R-15-007r,
// core/mem_metadata.sail), which would make maintenance of a capability-
// bearing array destroy the authority in it. So the block is read and written
// back a granule at a time with its metadata carried across, and the tag plane
// survives a scrub where it does not survive an `sd` of the same bits.
//
// **What is not here is the fault, because the fault is not architectural
// state.** This model has no error model: no codeword carries a syndrome, so
// nothing is ever correctable and nothing is ever uncorrectable, and the two
// halves R-15-177a states beyond the pass land where their state does rather
// than being invented here as a fault-injection register the machine does not
// have.
//
//   - The **correction telemetry** goes to the sentinel, which is a core class
//     and a device rather than a structure this hart can read (§15, M0.8): a
//     corrected codeword is not observable to the scrubbing hart at all, which
//     is what makes correction invisible in the timing as well (R-15-179).
//   - The **fail-stop** on an uncorrectable error needs no new channel when it
//     arrives, and that is worth stating rather than deferring: the read below
//     already returns `MemoryOpResult`, so a detection joins the same error
//     path a PMA refusal takes, and the clause changes by a case rather than by
//     a mechanism. What differs is only which agent it stops, and that is the
//     sentinel's to decide.
//
// The encoding is MISC-MEM `funct3` 010 at immediate 5, with a zero destination
// as every cache-block operation has: `cbo.zero` is 4, `lc` shares the `funct3`
// and is separated from both by a *non-zero* destination
// (extensions/CHERI/cheri_insts.sail, R-15-060). Five rather than one of the
// three points `Zicbom` vacated (R-15-061), because reusing a named standard
// encoding for a different operation makes a stock disassembler print the wrong
// instruction where an unallocated one makes it print none, and this profile's
// rule is that an unallocated encoding traps rather than that it lies
// (R-15-014).

union clause instruction = CBO_SCRUB : (regidx)

mapping clause encdec = CBO_SCRUB(rs1)
  <-> 0b000000000101 @ encdec_reg(rs1) @ 0b010 @ 0b00000 @ 0b0001111

mapping clause assembly = CBO_SCRUB(rs1)
  <-> "cbo.scrub" ^ spc() ^ "(" ^ opt_spc() ^ reg_name(rs1) ^ opt_spc() ^ ")"

// The block is addressed the way `cbo.zero` addresses it: the base register
// names an address anywhere in the block and the block is the naturally aligned
// one containing it, so the offset below is zero or negative
// (extensions/Zicboz/zicboz_insts.sail). The authority is checked once for the
// whole block and needs load and store permission both
// (core/addr_checks.sail).
//
// The granule is the capability's rather than the block's, because the metadata
// this preserves is keyed per granule and a single wide access would carry the
// conjunction of the block's tags instead of each of them (R-15-203,
// sys/mem.sail). That is the same reason `cloadtags` walks the block granule by
// granule (extensions/CHERI/cheri_insts.sail).
function clause execute CBO_SCRUB(rs1) = {
  let rs1_val = X(rs1);
  let block_size = caps_per_block * cap_size;
  let access : MemoryAccessType(mem_payload) = CacheAccess(CB_scrub());
  assert(plat_cache_block_size_exp == sizeof(log2_cap_block_size),
         "cbo.scrub covers the CBO block, so the two must be configured alike");

  let negative_offset = (rs1_val & ~(zero_extend(ones(plat_cache_block_size_exp)))) - rs1_val;

  match get_transformed_data_addr(rs1, negative_offset, access, block_size) {
    Ext_DataAddr_Error(e) => Ext_DataAddr_Check_Failure(e),
    Ext_DataAddr_OK(vaddr) => {
      let base = physical_address(vaddr);
      var failure : option(ExceptionType) = None();

      foreach (i from 0 to (caps_per_block - 1)) {
        match failure {
          Some(_) => (),
          None()  => {
            let granule = Physaddr(bits_of(base) + (i * cap_size));
            match mem_read_meta(access, granule, cap_size, false, false, true) {
              Err(_, e) => failure = Some(e),
              // The write-back is the read's own bits and the read's own tag.
              // On this model that is always what the array already holds, the
              // correction being empty; on a machine with a syndrome it is the
              // corrected codeword, and nothing here changes but the value the
              // read returns.
              Ok(v, tag) =>
                match mem_write_value_meta(granule, cap_size, v, access, tag, false, false) {
                  Err(_, e) => failure = Some(e),
                  Ok(true)  => (),
                  Ok(false) => internal_error(__FILE__, __LINE__, "cbo.scrub got false from mem_write_value_meta"),
                },
            }
          },
        }
      };

      match failure {
        // Errors report the address the instruction encoded rather than the
        // aligned base, which is `cbo.zero`'s convention and here is always
        // `rs1` (extensions/Zicboz/zicboz_insts.sail).
        Some(e) => memory_exception(vaddr - negative_offset, e),
        None()  => RETIRE_SUCCESS,
      }
    },
  }
}
