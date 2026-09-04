// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Instruction declarations.
//
// This includes scattered declarations for decoding, execution, and assembly parsing and printing.
// This file also defines the execution result, i.e. the return value from the `execute()` function.

scattered union instruction

union ExecutionResult = {
  // Successfully retired.
  Retire_Success                 : unit,

  // The instruction is a compressed instruction, and should be
  // executed as an uncompressed instruction. This can be used
  // for non-compressed instructions too but we only support
  // one level of indirection. This avoids making the execute()
  // function recursive, which is helpful for some backends,
  // and allows Sail to generate faster C/C++ code by avoiding
  // reallocation.
  ExecuteAs                      : instruction,

  // An instruction such as WFI, WRS.{STO,NTO}
  // entered a wait state, which may or may not
  // retire depending on the configuration.
  Enter_Wait                     : WaitReason,

  // Did not retire for a standard reason.
  Illegal_Instruction            : unit,
  Trap                           : (sync_exception, xlenbits),

  // Did not retire for custom reason.
  Ext_CSR_Check_Failure          : unit,
  Ext_ControlAddr_Check_Failure  : ext_control_addr_error,
  Ext_DataAddr_Check_Failure     : ext_data_addr_error,
  Ext_XRET_Priv_Failure          : unit,
}

// To ease the introduction of `ExecutionResult`, this global
// definition is temporarily used instead of the previous
// RETIRE_SUCCESS enum value so that we don't have to immediately
// update all the places RETIRE_SUCCESS was used.

let RETIRE_SUCCESS : ExecutionResult = Retire_Success()

// Trap helpers

function trap(exc : sync_exception) -> ExecutionResult =
  Trap(exc, PC)

function memory_exception(vaddr : virtaddr, exc : ExceptionType) -> ExecutionResult =
  trap(make_sync_exception(exc, bits_of(vaddr)))

// returns whether an instruction was retired
val execute : instruction -> ExecutionResult
scattered function execute

val assembly : instruction <-> string
scattered mapping assembly

val encdec : instruction <-> bits(32)
scattered mapping encdec

// There is no second, *shorter* decode either. `C` is excluded and ILEN is
// fixed at 32 (R-15-036, R-15-014), so the fetch reads one 32-bit word and
// never a parcel (postlude/fetch.sail), and the 16-bit mapping the compressed
// extension decoded through has nothing left to decode.

// There is no second, capability-mode decode. Upstream needs one because
// `auipc`, `jal` and `jalr` read differently under a capability-mode PCC; here
// those encodings have only their capability reading, so the one mapping below
// carries them (extensions/CHERI/cheri_insts.sail, R-15-001).

// We declare the ILLEGAL instruction clause here instead of in
// insts_end, so that model extensions can make use of it.
// However, the encdec mapping must come last to ensure that all
// unmatched encodings decode to an illegal instruction.
union clause instruction = ILLEGAL : word
