// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// The capability register type below follows the CHERI-RISC-V Sail model
// (CTSRD-CHERI/sail-cheri-riscv @ bb07488d, src/cheri_reg_type.sail), which is
// subject to the BSD two-clause licence in model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The register file is **merged**: one file of 32 registers, each holding a
// capability with its validity tag, an integer operand being that register's
// address field read as an integer (R-15-007i). There is no separate
// capability bank and therefore no instruction that moves a value between
// banks, and the partition switch's restore quantifies over one file
// (R-07-015, R-15-214).
type regtype = Capability

// The zero register reads as the null capability, which is the all-zeroes
// granule (cap_common.sail).
let zero_reg : regtype = null_cap

function RegStr(r : regtype) -> string = capToString(r)

// conversions
//
// An integer read is the address field. An integer write yields an *untagged*
// capability at that address: writing an integer over a register destroys the
// authority it held rather than reinterpreting it, which is the merged file's
// whole discipline and the reason no capability is ever reconstructed from a
// bit pattern (R-05-136, R-15-002).

function regval_from_reg(r : regtype) -> xlenbits = r.address

function regval_into_reg(v : xlenbits) -> regtype = int_to_cap(v)
