// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The exceptions the ISA's own list does not carry.
//
// The page-table-walk accumulator and its error types went with the walker
// (R-15-002, R-15-038): there is no translation to fail, so no accumulator is
// threaded and no walk error is turned into an exception annotation.
//
// What remains is the capability exception. A capability violation raises one
// cause code, ISAv9's 0x1c, and reports which violation and which register in
// `mtval` (cap_causes.sail, R-15-073a). The two ISAv9 codes beside it,
// load-cap-page-fault and store-cap-page-fault, name a page fault and go with
// the MMU.

enum ext_exc_type = { EXC_CHERI }

mapping ext_exc_type_bits : ext_exc_type <-> exc_code = {
  EXC_CHERI <-> 0b011100, // 28
}

function ext_exc_type_to_str(_e : ext_exc_type) -> string = "cheri"
