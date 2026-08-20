// =======================================================================================
// Ported from the CHERI-RISC-V Sail model (CTSRD-CHERI/sail-cheri-riscv @ bb07488d,
// src/cheri_sys_regs.sail), which is subject to the BSD two-clause licence in
// model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The capability registers that are not in the merged file.

// The program-counter capability: the authority every fetch is checked
// against, and the register a control transfer installs. `PC` stays beside it
// as the integer program counter, which is PCC's address at every control
// transfer; sequential fetch advances `PC` and checks it against PCC's bounds
// rather than moving PCC.
register PCC     : Capability
register nextPCC : Capability

// The machine trap capabilities, in place of `mtvec`, `mepc`, and the
// trap-scratch CSR (R-15-073, R-07-022, R-07-023). A trap installs `MTCC` as
// the executing PCC, saves the interrupted PCC as `MEPCC`, and leaves the
// handler to bootstrap its authority from `MTDC`. They are reachable only with
// the access-system-registers permission (R-15-003).
register MTCC  : Capability
register MEPCC : Capability
register MTDC  : Capability

// There is no default data capability. It exists to relocate and bound an
// integer-addressed access, which is the hybrid mode this platform does not
// have, so no instruction reads it, no trap installs it, and no partition can
// name it (R-15-001c, R-15-242). Every data access is authorised by the
// capability in the base register it names (core/addr_checks.sail).

// How `cspecialrw` names the bank (extensions/CHERI/cheri_insts.sail). Upstream's
// numbering spans four privilege modes; here there is one, so two ranges of it
// are absent rather than reserved: the user and supervisor banks went with their
// modes (R-15-003), and number 30, upstream's machine scratch capability, went
// with the trap-scratch role that `MTDC` carries here (R-15-073). Number 1,
// upstream's `ddc`, is absent with the register. An absent number is an illegal
// instruction, as an unallocated CSR address is a trap (R-15-014).
type screg = bits(5)

mapping scr_name_map : screg <-> string = {
  0b00000 <-> "pcc",
  0b11100 <-> "mtcc",
  0b11101 <-> "mtdc",
  0b11111 <-> "mepcc",
}

// The smallest instruction a control transfer must have room for inside the
// bounds of the capability it targets. ILEN is fixed at 32 bits and `C` is
// excluded, so this is four bytes rather than the two an implementation that
// might enable compressed instructions has to assume (R-15-036).
let min_instruction_bytes : CapLen = 4
