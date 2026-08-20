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
//
// Both registers are narrowed to the machine-timer bits (R-15-066a).
// What that deletes is fields, not registers: `MTIE` and `MTIP` arm
// and report the slot-boundary timer, the core's only asynchronous
// trap, and the external- and software-interrupt fields are hardwired
// zero and unwritable, an MSI being latched pending state read with an
// ordinary load and no wired level interrupt existing on the die
// (R-15-065, R-15-066). The unnamed bits of the underlying `xlenbits`
// are that hardwiring: nothing constructs them non-zero and no
// legalization can set them.

bitfield Minterrupts : xlenbits = {
  MTI  : 7,  // Timer interrupt
}

private function legalize_mie(o : Minterrupts, v : xlenbits) -> Minterrupts = {
  let v = Mk_Minterrupts(v);
  [o with MTI = v[MTI]]
}

register mie     : Minterrupts // Enabled
register mip     : Minterrupts // Pending

mapping clause csr_name_map = 0x304  <-> "mie"
mapping clause csr_name_map = 0x344  <-> "mip"

function clause is_CSR_accessible(0x304, _) = true // mie
function clause is_CSR_accessible(0x344, _) = true // mip

// `mip` is read-only: `MTIP` is driven by the timer comparator and
// every other bit is hardwired zero, so a write is ignored rather than
// legalized. The platform-interrupt OR that upstream applied on the
// read path went with the external-interrupt field it carried, and
// with it the read-modify-write asymmetry that made `mip` the one CSR
// whose written-back value differed from its read value.
function clause read_CSR(0x304) = mie.bits
function clause read_CSR(0x344) = mip.bits

function clause write_CSR(0x304, value) = { mie = legalize_mie(mie, value); Ok(mie.bits) }
function clause write_CSR(0x344, _) = Ok(mip.bits)
