// SPDX-License-Identifier: Apache-2.0
// Q35g backend probe: a concurrency-interface model with an undefined real.
default Order dec
$include <prelude.sail>
$include <real.sail>
$include <concurrency_interface/read_write.sail>

function q35g_pa_bits(x : bits(64)) -> bits(64) = x

instantiation sail_mem_read with
  'pa = bits(64),
  'translation_summary = unit,
  'arch_ak = unit,
  'abort = unit,
  pa_bits = q35g_pa_bits

register Q35G_X : bits(64)

function q35g_real() -> real = {
  let r : real = undefined;
  if lt_real(r, to_real(0)) then to_real(0) else r
}
