// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

function clause currentlyEnabled(Ext_Zbc) = hartSupports(Ext_Zbc)
function clause currentlyEnabled(Ext_Zbkc) = hartSupports(Ext_Zbkc)

// *****************************************************************
union clause instruction = CLMUL : (regidx, regidx, regidx)

$[wavedrom "MINMAX/CLMUL _ _ CLMUL _ OP"]
mapping clause encdec = CLMUL(rs2, rs1, rd)
  <-> 0b0000101 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b001 @ encdec_reg(rd) @ 0b0110011
  when currentlyEnabled(Ext_Zbc) | currentlyEnabled(Ext_Zbkc)

mapping clause assembly = CLMUL(rs2, rs1, rd)
  <-> "clmul" ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1) ^ sep() ^ reg_name(rs2)

function clause execute CLMUL(rs2, rs1, rd) = {
  let prod = carryless_mul(X(rs1), X(rs2));
  X(rd) = prod[xlen - 1 .. 0];
  RETIRE_SUCCESS
}

// *****************************************************************
union clause instruction = CLMULH : (regidx, regidx, regidx)

$[wavedrom "MINMAX/CLMUL _ _ CLMULH _ OP"]
mapping clause encdec = CLMULH(rs2, rs1, rd)
  <-> 0b0000101 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b011 @ encdec_reg(rd) @ 0b0110011
  when currentlyEnabled(Ext_Zbc) | currentlyEnabled(Ext_Zbkc)

mapping clause assembly = CLMULH(rs2, rs1, rd)
  <-> "clmulh" ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1) ^ sep() ^ reg_name(rs2)

function clause execute CLMULH(rs2, rs1, rd) = {
  let prod = carryless_mul(X(rs1), X(rs2));
  X(rd) = prod[2 * xlen - 1 .. xlen];
  RETIRE_SUCCESS
}

// *****************************************************************
// `Zbc` is excluded by name (R-15-048a), and `clmulr` below is gated on it
// alone: no shipped configuration enables the key, so the clause decodes for
// nothing and its encoding point reaches the illegal-instruction path by the
// route every unallocated point does (R-15-014).
//
// The clause stays, and that is a curation call rather than an oversight.
// Where an excluded extension owns its whole file, the file goes and the next
// re-pin has nothing to reconcile. This file is not that one: `clmul` and
// `clmulh` above are reached through the adopted `Zbkc` (R-15-042), so the only
// deletion on offer is a surgical edit inside a vendored file, a divergence
// carried into every re-pin from here on, and it would buy nothing the key does
// not already buy. So this exclusion is a supported-flag reading false, where
// `Zacas`'s is a property of the model (R-15-026): what separates them is which
// deletion the file admits, and not how firmly either is excluded.
union clause instruction = CLMULR : (regidx, regidx, regidx)

$[wavedrom "MINMAX/CLMUL _ _ CLMULR _ OP"]
mapping clause encdec = CLMULR(rs2, rs1, rd)
  <-> 0b0000101 @ encdec_reg(rs2) @ encdec_reg(rs1) @ 0b010 @ encdec_reg(rd) @ 0b0110011
  when currentlyEnabled(Ext_Zbc)

mapping clause assembly = CLMULR(rs2, rs1, rd)
  <-> "clmulr" ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1) ^ sep() ^ reg_name(rs2)

function clause execute CLMULR(rs2, rs1, rd) = {
  X(rd) = carryless_mulr(X(rs1), X(rs2));
  RETIRE_SUCCESS
}
