// SPDX-License-Identifier: Apache-2.0
// Q35g backend probe: a model with a real-typed register.
default Order dec
$include <prelude.sail>
$include <real.sail>

register Q35G_R : real

function q35g_bump() -> unit = {
  Q35G_R = add_real(Q35G_R, 1.5)
}
