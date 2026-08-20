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

// A PCC in capability mode reads `auipc`, `jal` and `jalr` as their capability
// forms; every other encoding takes the ordinary decode, which is what
// `NOT_CAPMODE` says (postlude/insts_end.sail). The branch goes with hybrid mode
// in M0.6f, leaving one decode.
function ext_decode(bv : bits(32)) -> instruction =
  if PCC.flag_cap_mode then {
    match encdec_capmode(bv) {
      NOT_CAPMODE(_) => encdec(bv),
      capmode_instruction => capmode_instruction,
    }
  } else encdec(bv)
