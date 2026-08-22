// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// These enums are arranged according to the level of PMA support they require:
// AMOSwap < AMOLogical < AMOArithmetic
//
// The compare-and-swap operand `AMOCAS` is gone with `Zacas` (R-15-026,
// R-15-027), which the profile excludes as an absence of the model rather
// than a configuration key: `Zaamo` refcounts are single-instruction, the
// rings are SPSC under Ztso, and no capability is in shared mutable memory,
// so nothing on this machine issues a CAS. The levels above `AMOArithmetic`
// went with it, that grading being the CAS operand widths and nothing else.
enum amoop = { AMOSWAP, AMOAND, AMOOR, AMOXOR, AMOADD, AMOMIN, AMOMAX, AMOMINU, AMOMAXU }

mapping amo_mnemonic : amoop <-> string = {
  AMOSWAP <-> "amoswap",
  AMOAND  <-> "amoand",
  AMOOR   <-> "amoor",
  AMOXOR  <-> "amoxor",
  AMOADD  <-> "amoadd",
  AMOMIN  <-> "amomin",
  AMOMAX  <-> "amomax",
  AMOMINU <-> "amominu",
  AMOMAXU <-> "amomaxu",
}

mapping maybe_aqrl : (bool, bool) <-> string = {
  (true, true)   <-> ".aqrl",
  (true, false)  <-> ".aq",
  (false, true)  <-> ".rl",
  (false, false) <-> "",
}
