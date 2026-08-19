// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

function accessFaultFromAccessType(access : MemoryAccessType(mem_payload)) -> ExceptionType =
  match access {
    InstructionFetch()                  => E_Fetch_Access_Fault(),
    Load(Data)                          => E_Load_Access_Fault(),
    Load(Vector)                        => E_Load_Access_Fault(),
    Load(PageTableEntry)                => E_Load_Access_Fault(),
    LoadReserved(_, _, Data)            => E_Load_Access_Fault(),
    Store(Data)                         => E_SAMO_Access_Fault(),
    Store(Vector)                       => E_SAMO_Access_Fault(),
    Store(PageTableEntry)               => E_SAMO_Access_Fault(),
    StoreConditional(_, _, Data)        => E_SAMO_Access_Fault(),
    Atomic(_, _, _, Data, Data)         => E_SAMO_Access_Fault(),

    // "For shadow stack instructions, the reported instruction type
    // is always as though it were a store or AMO, even for instructions
    // SSPOPCHK and C.SSPOPCHK that only read from memory and do not
    // write to it."
    Load(ShadowStack)                   => E_SAMO_Access_Fault(),
    Store(ShadowStack)                  => E_SAMO_Access_Fault(),

    Atomic(_, _, _, ShadowStack, ShadowStack) => E_SAMO_Access_Fault(),

    LoadReserved(_, _, p)               => internal_error(__FILE__, __LINE__, "Invalid payload (" ^ mem_payload_name(p) ^ ") for LoadReserved."),
    StoreConditional(_, _, p)           => internal_error(__FILE__, __LINE__, "Invalid payload (" ^ mem_payload_name(p) ^ ") for StoreConditional."),
    Atomic(_, _, _, rp, wp)             => internal_error(__FILE__, __LINE__, "Invalid payloads (" ^ mem_payload_name(rp) ^ ", " ^ mem_payload_str(wp) ^ ") for Atomic."),

    // Cache-block zero (CB_zero) instructions raise store faults.
    CacheAccess(CB_zero())              => E_SAMO_Access_Fault(),
  }

function alignmentFaultFromAccessType(access : MemoryAccessType(mem_payload)) -> ExceptionType =
  match access {
    InstructionFetch()                  => E_Fetch_Addr_Align(),
    Load(Data)                          => E_Load_Addr_Align(),
    Load(Vector)                        => E_Load_Addr_Align(),
    Load(PageTableEntry)                => E_Load_Addr_Align(),
    LoadReserved(_, _, Data)            => E_Load_Addr_Align(),
    Store(Data)                         => E_SAMO_Addr_Align(),
    Store(Vector)                       => E_SAMO_Addr_Align(),
    Store(PageTableEntry)               => E_SAMO_Addr_Align(),
    StoreConditional(_, _, Data)        => E_SAMO_Addr_Align(),
    Atomic(_, _, _, Data, Data)         => E_SAMO_Addr_Align(),

    // "For shadow stack instructions, the reported instruction type
    // is always as though it were a store or AMO, even for instructions
    // SSPOPCHK and C.SSPOPCHK that only read from memory and do not
    // write to it."
    Load(ShadowStack)                   => E_SAMO_Addr_Align(),
    Store(ShadowStack)                  => E_SAMO_Addr_Align(),

    Atomic(_, _, _, ShadowStack, ShadowStack) => E_SAMO_Addr_Align(),

    LoadReserved(_, _, p)               => internal_error(__FILE__, __LINE__, "Invalid payload (" ^ mem_payload_name(p) ^ ") for LoadReserved."),
    StoreConditional(_, _, p)           => internal_error(__FILE__, __LINE__, "Invalid payload (" ^ mem_payload_name(p) ^ ") for StoreConditional."),
    Atomic(_, _, _, rp, wp)             => internal_error(__FILE__, __LINE__, "Invalid payloads (" ^ mem_payload_name(rp) ^ ", " ^ mem_payload_str(wp) ^ ") for Atomic."),

    // Cache-block zero (CB_zero) instructions raise store faults.
    CacheAccess(CB_zero())              => E_SAMO_Addr_Align(),
  }
