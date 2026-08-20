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
// An integer *is* the register's 64 data bits, and the low 36 of them are the
// address field a capability reading takes: the address space is narrower than
// a register, so an address is an integer but not every integer is an address
// (R-15-002a, core/cap_format.sail). Reading a register as an integer and
// writing that integer back is therefore the identity on every value, which is
// what keeps XLEN-wide integer arithmetic intact on a machine whose registers
// hold authority.
//
// An integer write yields an *untagged* capability: writing an integer over a
// register destroys the authority it held rather than reinterpreting it, which
// is the merged file's whole discipline and the reason no capability is ever
// reconstructed from a bit pattern (R-05-136, R-15-002). The null-capability
// transform the memory interface applies is applied here too, so the zero
// register reads as integer zero and a register stored with `sd` and reloaded
// with `lc` is the capability it was (core/cap_common.sail).

function regval_from_reg(r : regtype) -> xlenbits = capToMemBits(r)

function regval_into_reg(v : xlenbits) -> regtype = int_to_cap(v)
