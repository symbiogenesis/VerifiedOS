// SPDX-License-Identifier: Apache-2.0
/* These wrappers retain the SMT input alongside the actual curated result. */
register vos_pc : bits(64)

val vos_expand_local : bits(4) -> bits(17)
function vos_expand_local(shape) = {
  let code = 0b0 @ shape;
  code @ perms_expand(code)
}

val vos_expand_global : bits(4) -> bits(17)
function vos_expand_global(shape) = {
  let code = 0b1 @ shape;
  code @ perms_expand(code)
}
