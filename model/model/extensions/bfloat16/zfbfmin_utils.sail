// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

function fsplit_BF16 (v : bits(16)) -> (bits(1), bits(8), bits(7)) = (v[15..15], v[14..7], v[6..0])

function fmake_BF16 (sign : bits(1), exp : bits(8), mant : bits(7)) -> (bits(16)) = (sign @ exp @ mant)

function bf16_to_f32 (v : bits(16)) -> (bits_fflags, bits(32)) = {
  let (sign, exp, mant) = fsplit_BF16(v);
  let is_nan = exp == ones() & mant != zeros();
  let is_inf = exp == ones() & mant == zeros();

  let fflags = if is_nan & signed(mant) >= 0 then nvFlag() else zeros();
  // `canonical_NaN_S` and `fmake_S` were scalar-F/D helpers (R-15-039); the
  // single-precision assembly is written out here instead.
  let value : bits(32) =
    if is_nan then canonical_NaN(32)
    else if is_inf then sign @ ones(8) @ zeros(23)
    else sign @ exp @ mant @ zeros(16);

  (fflags, value)
}

function bf16_to_f32_set_flags(nval : bits(16)) -> bits(32) = {
  let (_, wval) = bf16_to_f32(nval);
  wval
}
