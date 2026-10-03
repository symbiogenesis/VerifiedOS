// SPDX-License-Identifier: Apache-2.0
// Q35g backend probe: a concurrency-interface model without reals.
default Order dec
$include <prelude.sail>
$include <concurrency_interface/read_write.sail>

function q35g_pa_bits(x : bits(64)) -> bits(64) = x

instantiation sail_mem_read with
  'pa = bits(64),
  'translation_summary = unit,
  'arch_ak = unit,
  'abort = unit,
  pa_bits = q35g_pa_bits

register Q35G_X : bits(64)

function q35g_touch() -> unit = {
  let c : bool = undefined;
  if c then Q35G_X = 0x0000000000000001
}
