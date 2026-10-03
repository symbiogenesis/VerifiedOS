// SPDX-License-Identifier: Apache-2.0
// Q35g backend probe: a model without reals.
default Order dec
$include <prelude.sail>

register Q35G_A : bits(8)

function q35g_pick(x : bits(8)) -> bits(8) = {
  let c : bool = undefined;
  Q35G_A = x;
  if c then x else Q35G_A
}
