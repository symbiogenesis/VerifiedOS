// SPDX-License-Identifier: Apache-2.0
// Q35g backend probe: reals only inside an expression; no declaration mentions them.
default Order dec
$include <prelude.sail>
$include <real.sail>

function q35g_ceil_div(a : int, b : int) -> int = ceil(div_real(to_real(a), to_real(b)))
