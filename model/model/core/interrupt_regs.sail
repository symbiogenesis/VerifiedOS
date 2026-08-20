// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// State and access functions for mip and mie.
//
// The supervisor views (sip, sie) and the delegation registers
// (medeleg, mideleg) are gone with the mode they delegated to
// (R-15-003), which takes the lowered-view and lifting machinery with
// them: `mip` and `mie` have exactly one reader.

bitfield Minterrupts : xlenbits = {
  MEI  : 11, // Machine external interrupt
  MTI  : 7,  // Timer interrupt
  MSI  : 3,  // Software interrupt
}

private function legalize_mip(o : Minterrupts, _v : xlenbits) -> Minterrupts = {
  // MEIP, MTIP and MSIP are all read-only in `mip`: they are driven by
  // the platform, not by software.
  o
}

private function legalize_mie(o : Minterrupts, v : xlenbits) -> Minterrupts = {
  let v = Mk_Minterrupts(v);
  [o with
    MEI = v[MEI],
    MTI = v[MTI],
    MSI = v[MSI],
  ]
}

// Note that mip's MEIP and SEIP had special handling. MEIP is always
// read-only zero in mip, but there is also an external platform MEIP
// input that is OR'd into mip when it is read, both for dispatching
// interrupts, and when writing rd with CSR instructions but NOT when
// it is used as a value for read-modify-write.

// Called whenever we want mip with the external interrupts ORed in.
// This is the case for a) reading mip, and b) dispatching interrupts.
// But it is NOT the case for reading mip during a CSR read-modify-write
// update, therefore we can't just store them directly in the mip register.
val external_interrupts_pending : unit -> Minterrupts

register mie     : Minterrupts // Enabled
register mip     : Minterrupts // Pending

mapping clause csr_name_map = 0x304  <-> "mie"
mapping clause csr_name_map = 0x344  <-> "mip"

function clause is_CSR_accessible(0x304, _) = true // mie
function clause is_CSR_accessible(0x344, _) = true // mip

enum XipReadType = {
  IncludePlatformInterrupts,
  ExcludePlatformInterrupts,
}

function read_mip(read_type : XipReadType) -> Minterrupts =
  match read_type {
    IncludePlatformInterrupts => Mk_Minterrupts(mip.bits | external_interrupts_pending().bits),
    ExcludePlatformInterrupts => mip,
  }

function write_mip(value : xlenbits) -> unit = {
  mip = legalize_mip(mip, value);
}

function clause read_CSR(0x304) = mie.bits
function clause read_CSR(0x344) = read_mip(ExcludePlatformInterrupts).bits

function clause write_CSR(0x304, value) = { mie = legalize_mie(mie, value); Ok(mie.bits) }
function clause write_CSR(0x344, value) = { write_mip(value); Ok(read_mip(IncludePlatformInterrupts).bits) }
