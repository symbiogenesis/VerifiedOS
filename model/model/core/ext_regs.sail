// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================


// This file contains register handling functions that can be
// overridden by extensions.

/*!
THIS(csrno, access_type) decides whether an access to csrno is allowed. The
privilege argument this carried is gone with the modes (R-15-003), and what
replaced it is the capability: the access-system-registers permission on the
executing PCC *is* the privilege mechanism, so a compartment without it cannot
reach a CSR at all (R-15-003, R-15-073).
*/
function ext_check_CSR(_csrno : csreg, _access_type : CSRAccessType) -> bool =
  PCC.access_system_regs

// The trap this refusal raises is `ext_check_CSR_fail`, defined with the other
// capability traps in the postlude (cap_traps.sail).
