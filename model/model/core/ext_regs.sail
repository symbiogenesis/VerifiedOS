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
THIS(csrno, access_type) allows an extension to block an access to csrno.
It should return true if the access is allowed. The privilege argument
this carried is gone with the modes (R-15-003): every access is a
machine-mode access.
*/
function ext_check_CSR(_csrno : csreg, _access_type : CSRAccessType) -> bool = true

/*!
THIS is called if ext_check_CSR returns false. It should
cause an appropriate RISCV exception.
 */
function ext_check_CSR_fail() -> unit = ()
