// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Upper immediate ops. `auipc` is not among them: it forms a PC-relative
// address, and on a purecap machine that address is a capability derived from
// PCC, so the encoding is `auipcc` and its clause is the capability surface's
// (extensions/CHERI/cheri_insts.sail, R-15-001).
enum uop = {LUI}
enum bop = {BEQ, BNE, BLT, BGE, BLTU, BGEU}      // branch ops
enum iop = {ADDI, SLTI, SLTIU, XORI, ORI, ANDI}  // immediate ops
enum sop = {SLLI, SRLI, SRAI}                    // shift ops
enum rop = {ADD, SUB, SLL, SLT, SLTU, XOR,
            SRL, SRA, OR, AND}                   // reg-reg ops

enum ropw  = {ADDW, SUBW, SLLW, SRLW, SRAW}      // reg-reg 32-bit ops
enum sopw  = {SLLIW, SRLIW, SRAIW}               // RV64-only shift ops
