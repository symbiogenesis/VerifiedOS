// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Extensions may wish to interpose and transform decoded instructions,
// based on other machine state. This is supported via decode instruction
// hooks, the default implementation of which is provided below.

// One length, one decode. ILEN is fixed at 32 bits and `C` is excluded, so the
// fetch never produces a 16-bit parcel for a second decode hook to interpose on
// (R-15-036, R-15-014, postlude/fetch.sail).

// One mode, one decode. Upstream reads `auipc`, `jal` and `jalr` through a
// second mapping when PCC is in capability mode; here those encodings have only
// their capability reading, so the mapping and the flag that selected it are
// both absent (R-15-001, extensions/CHERI/cheri_insts.sail).
function ext_decode(bv : bits(32)) -> instruction = encdec(bv)
