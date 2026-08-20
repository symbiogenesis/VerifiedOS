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

// ILEN is fixed at 32 bits and `C` is excluded, so a 16-bit parcel is an
// illegal instruction whatever mode PCC is in (R-15-036).
function ext_decode_compressed(bv : bits(16)) -> instruction = encdec_compressed(bv)

// One mode, one decode. Upstream reads `auipc`, `jal` and `jalr` through a
// second mapping when PCC is in capability mode; here those encodings have only
// their capability reading, so the mapping and the flag that selected it are
// both absent (R-15-001, extensions/CHERI/cheri_insts.sail).
function ext_decode(bv : bits(32)) -> instruction = encdec(bv)
