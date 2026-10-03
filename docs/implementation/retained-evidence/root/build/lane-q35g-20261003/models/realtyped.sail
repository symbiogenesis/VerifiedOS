// SPDX-License-Identifier: Apache-2.0
// Q35g backend probe: a model whose declarations mention reals, with an
// undefined real and a real literal.
default Order dec
$include <prelude.sail>
$include <real.sail>

function q35g_half(n : int) -> real = div_real(to_real(n), to_real(2))

function q35g_step() -> real = {
  let r : real = undefined;
  add_real(r, 1.5)
}
