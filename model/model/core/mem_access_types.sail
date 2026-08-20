// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// What a memory access carries. Two payload classes remain: the
// page-table-entry class went with the walker (R-15-002, R-15-038) and
// the shadow-stack class with `Zicfiss` (R-15-044).

enum mem_payload = { Data, Vector }

mapping mem_payload_name : mem_payload <-> string = {
  Data           <-> "Data",
  Vector         <-> "Vector",
}

function accessType_to_str(access : MemoryAccessType(mem_payload)) -> string =
  match access {
    Load(_)                   => "R",
    Store(_)                  => "W",
    Atomic(_)                 => "RW",
    InstructionFetch()        => "X",
    CacheAccess(_)            => "C",
  }

overload to_str = {accessType_to_str}

function is_amo_access(access : MemoryAccessType(mem_payload)) -> bool =
  match access {
    Atomic(_) => true,
    _         => false,
  }

function is_vector_access(access : MemoryAccessType(mem_payload)) -> bool =
  match access {
    Load(Vector)  => true,
    Store(Vector) => true,
    _             => false,
  }
