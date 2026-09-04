// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Current fetch hooks for RISC-V extensions call extensions
// to check PC validity *before* standard fetch processing checks.

// **There is one instruction length, so the fetch decodes none.** `C` is
// excluded and ILEN is fixed at 32 (R-15-036, R-15-014), which is why the two
// checks below ask PCC for four bytes and refuse a PC that is not four-byte
// aligned; reading the low two bits of the first granule to choose a *shorter*
// instruction would be the instruction-length encoding of the extension this
// profile does not have, and it would contradict both of those checks in the
// same function. So a word whose low two bits are not `11` is an unallocated
// 32-bit encoding rather than a parcel: it reaches the illegal-instruction path
// through `ILLEGAL`, the wildcard `encdec` clause every unallocated point
// reaches (postlude/insts_end.sail), and `mtval` carries the whole word.

// This instruction byte fetcher is used for partial fetches, and
// hence doesn't return the FetchResult type that a full fetcher does.
// All the bytes fetched go through memory protection and PMA checks;
// this just barely works for Ziccif with ILEN=32 (bits) since there
// are no discarded bytes that lie outside protection boundaries.
// This will have to be generalized when ILEN is increased above 32
// (e.g. to 48): there could be discarded bytes that straddle
// protection boundaries in that case, and memory protection and PMA
// checks do not apply to discarded bytes.

private union FetchBytes_Result('width : Int), 'width >= 0 = {
  FetchBytes_Ext_Error : ext_fetch_addr_error,
  FetchBytes_Exception : ExceptionType,
  FetchBytes_Success   : bits('width * 8),
}

private function fetch_bytes forall 'n, 'n in {2, 4} . (fetch_start : xlenbits, granule_start : xlenbits, width : int('n)) -> FetchBytes_Result('n) = {
  match ext_fetch_check_pc(fetch_start, granule_start, width) {
    Some(e) => return FetchBytes_Ext_Error(e),
    None()  => (),
  };

  let paddr = physical_address(Virtaddr(granule_start));

  match mem_read(InstructionFetch(), paddr, width, false, false) {
    Err(exc_addr, e) => {
      // Instruction fetches are not currently split at the physical memory layer.
      assert(exc_addr == paddr);
      FetchBytes_Exception(e)
    },
    Ok(bytes) => FetchBytes_Success(bytes),
  }
}

private function fetch() -> FetchResult = {
  // TODO: Add a parameter to try_step() to allow forcing the fetch result and use that instead.

  if get_config_rvfi()
  then return rvfi_fetch();

  // Doing this check here assumes the external fetch checks are higher priority
  // than the following alignment check. It covers a whole instruction, which is
  // what the fetch sequence about to run reads.
  match ext_fetch_check_pc(PC, PC, min_instruction_bytes) {
    Some(e) => return F_Ext_Error(e),
    None()  => (),
  };

  // Instructions are 32 bits wide and 4-byte aligned: there are no
  // compressed instructions to relax this to 2-byte alignment.
  if   PC[1 .. 0] != 0b00
  then return F_Error(E_Fetch_Addr_Align(), PC);

  // The PC is four-byte aligned by the refusal above, so `Ziccif` alone decides
  // between the two sequences below and the alignment conjunct upstream carries
  // beside it is a condition no run can fail.
  //
  // NOTE: The atomicity requirements for the fetch can be implemented
  // in the memory model in two ways: (i) A single memory transaction
  // in Sail, i.e. the approach followed below, or (ii) multiple smaller
  // (e.g. 2-byte) fetches, along with rules in the memory model specifying
  // that nothing can intervene between these smaller
  // intra-instruction fetches.  The former approach is currently simpler
  // since it does not require any additional rules in the memory model.
  // However, if/when ILEN is increased to 48 and higher, it may be that
  // the complexities around memory protection could be addressed using
  // smaller fetches and augmenting the memory model with these additional
  // rules for intra-instruction split fetches.
  if currentlyEnabled(Ext_Ziccif) then {
    match fetch_bytes(PC, PC, 4) {
      FetchBytes_Ext_Error(e)   => F_Ext_Error(e),
      FetchBytes_Exception(e)   => F_Error(e, PC),
      FetchBytes_Success(bytes) => F_Base(bytes),
    }
  } else {
    // Split the fetch into 16-bit granules to generate precise fault
    // addresses in any fetch exception, which is the whole of what the split
    // is for once there is no second instruction length to discover: both
    // granules are read on every fetch, and the second one's fault names the
    // address it was raised at (core/addr_checks.sail).
    match fetch_bytes(PC, PC, 2) {
      FetchBytes_Ext_Error(e) => F_Ext_Error(e),
      FetchBytes_Exception(e) => F_Error(e, PC),
      FetchBytes_Success(ilo) =>
        match fetch_bytes(PC, PC + 2, 2) {
          FetchBytes_Ext_Error(e) => F_Ext_Error(e),
          FetchBytes_Exception(e) => F_Error(e, PC + 2),
          FetchBytes_Success(ihi) => F_Base(append(ihi, ilo)),
        },
    }
  }
}
