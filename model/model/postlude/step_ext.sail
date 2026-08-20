// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The default implementation of hooks for the step() and main() functions.

function ext_fetch_hook(f : FetchResult) -> FetchResult = f

function ext_pre_step_hook()  -> unit = ()
function ext_post_step_hook() -> unit = ()

// On a machine whose registers hold authority, reset is not free to leave the
// register file undefined the way the base ISA leaves the integer file: an
// undefined capability would be authority nothing granted. Every register
// resets to the null capability, which is also the all-zeroes granule
// (R-15-007i, cap_common.sail).
function ext_reset() -> unit = {
  // The machine comes out of reset holding the root authority, and the root is
  // a **pair** rather than one capability: no admitted permission set holds
  // both store and execute, so a single almighty root is inexpressible and the
  // execute side and the store side are separate authorities (R-15-007l,
  // R-15-007p). The execute side spans the address space so that the first
  // fetch is inside its bounds, and the trap capabilities start from it. The
  // composition-fixed initial distribution that replaces this is M-mode
  // firmware's to install (§3, R-15-076a), and it can only narrow what it is
  // given.
  PCC     = default_cap;
  nextPCC = default_cap;
  MTCC    = default_cap;
  MEPCC   = default_cap;
  // The handler's data capability is granted rather than assumed.
  MTDC    = null_cap;

  // The store side lands in `c1`, which is where firmware finds it. It carries
  // `store-local` because `candperm` can only remove: a stack capability is
  // derivable only from a root that already holds the permission.
  x1  = root_data_cap;
  x2  = null_cap;
  x3  = null_cap;
  x4  = null_cap;
  x5  = null_cap;
  x6  = null_cap;
  x7  = null_cap;
  x8  = null_cap;
  x9  = null_cap;
  x10 = null_cap;
  x11 = null_cap;
  x12 = null_cap;
  x13 = null_cap;
  x14 = null_cap;
  x15 = null_cap;
  x16 = null_cap;
  x17 = null_cap;
  x18 = null_cap;
  x19 = null_cap;
  x20 = null_cap;
  x21 = null_cap;
  x22 = null_cap;
  x23 = null_cap;
  x24 = null_cap;
  x25 = null_cap;
  x26 = null_cap;
  x27 = null_cap;
  x28 = null_cap;
  x29 = null_cap;
  x30 = null_cap;
  x31 = null_cap;
}
