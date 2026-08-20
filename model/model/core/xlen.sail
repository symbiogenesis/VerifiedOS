// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// XLEN is a constant, not a configuration knob. The base is RV64
// (R-15-001), there is exactly one model of one machine (R-15-005), and
// no plain-RV32 target exists anywhere in the platform (R-18-002). The
// capability format forces the same conclusion from below: a register is
// a capability whose address field is the register width (R-15-007i), and
// the 128-bit encoding in cap_format.sail cannot hold a 32-bit one, so an
// RV32 configuration of this model has no capability format to run under.

type xlen : Int = 64
type log2_xlen  : Int = 6
type xlen_bytes : Int = 8

// TODO: Allow configuring a lower number of physical address bits.
// For example it is unlikely that serious RV64 implementations really
// have 64 physical address bits.
type physaddrbits_len : Int = 64

// ASIDs went with address translation (R-15-002, R-15-038): there is no
// `satp`, no walker, and no TLB to tag.

// Variable versions of the above types. Variables and types
// are disjoint in Sail so they are allowed to have the same name.
// This saves typing `sizeof()` everywhere.
let log2_xlen = sizeof(log2_xlen)
let xlen_bytes = sizeof(xlen_bytes)
let xlen = sizeof(xlen)

type xlenbits = bits(xlen)
