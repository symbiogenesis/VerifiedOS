// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Platform-specific definitions, and basic MMIO devices.

// Current constraints on this implementation are:
// - it cannot access memory directly, but instead provides definitions for the physical memory model
// - it can access system register state, needed to manipulate interrupt bits
// - it relies on externs to get platform address information and doesn't hardcode them

// Location of HTIF (Host Target InterFace) tohost port. None if not enabled.
// This is used for console output and signalling the end of tests.
register htif_tohost_base : option(physaddrbits) = None()
let htif_tohost_size = 8
// This is called externally. bits(64) is used because it's easier to deal with from C.
function enable_htif(tohost_addr : bits(64)) -> unit = htif_tohost_base = Some(trunc(tohost_addr))

private function within_clint forall 'n, 0 < 'n <= max_mem_access . (Physaddr(addr) : physaddr, width : int('n)) -> bool = {
  if not(plat_have_clint) then return false;

  // To avoid overflow issues when physical memory extends to the end
  // of the addressable range, we need to perform address bound checks
  // on unsigned unbounded integers.
  let addr_int       = unsigned(addr);
  let clint_base_int = unsigned(plat_clint_base);
  let clint_size_int = unsigned(plat_clint_size);
    clint_base_int <= addr_int
  & (addr_int + sizeof('n)) <= (clint_base_int + clint_size_int)
}

private function within_htif_writable forall 'n, 0 < 'n <= max_mem_access . (Physaddr(addr) : physaddr, width : int('n)) -> bool =
  match htif_tohost_base {
    None() => false,
    Some(base) => (addr <_u base + htif_tohost_size) & (addr + width >_u base)
  }

private function within_htif_readable forall 'n, 0 < 'n <= max_mem_access . (addr : physaddr, width : int('n)) -> bool =
  within_htif_writable(addr, width)

// CLINT (Core Local Interruptor), based on Spike.

// Each hart has a memory-mapped mtimecmp register. Typically these are
// exposed as an array in CLINT. The CLINT implementation here is currently
// hard-coded to use the mtimecmp for hart 0.
register mtimecmp : bits(64)

// CLINT memory-mapped IO
//
// The `msip` door is gone with `mip.MSI` (R-15-066a): it was the
// memory-mapped write that set the software-interrupt bit, and that
// bit is hardwired zero. What is left of the CLINT is the machine
// timer, which the kernel programs directly (R-15-063).

// relative address map:
//
// 4000 mtimecmp hart 0 lo  -- memory-mapped timer thresholds
// 4004 mtimecmp hart 0 hi
// 4008 mtimecmp hart 1 lo
// 400c mtimecmp hart 1 hi
// bff8 mtime lo            -- memory-mapped clocktimer value
// bffc mtime hi

let MTIMECMP_BASE    : physaddrbits = zero_extend(0x04000)
let MTIMECMP_BASE_HI : physaddrbits = zero_extend(0x04004)
let MTIME_BASE       : physaddrbits = zero_extend(0x0bff8)
let MTIME_BASE_HI    : physaddrbits = zero_extend(0x0bffc)

private val clint_load : forall 'n, 'n > 0. (MemoryAccessType(mem_payload), physaddr, int('n)) -> MemoryOpResult(bits(8 * 'n))
function clint_load(access, paddr, width) = {
  let Physaddr(addr) = paddr;
  let addr = addr - plat_clint_base;
  // FIXME: For now, only allow exact aligned access.
  if addr == MTIMECMP_BASE & ('n == 4)
  then {
    if   get_config_print_clint()
    then print_log("clint<4>[" ^ bits_str(addr) ^ "] -> " ^ bits_str(mtimecmp[31..0]));
    // FIXME: Redundant zero_extend currently required by Lem backend
    Ok(zero_extend(32, mtimecmp[31..0]))
  }
  else if addr == MTIMECMP_BASE & ('n == 8)
  then {
    if   get_config_print_clint()
    then print_log("clint<8>[" ^ bits_str(addr) ^ "] -> " ^ bits_str(mtimecmp));
    // FIXME: Redundant zero_extend currently required by Lem backend
    Ok(zero_extend(64, mtimecmp))
  }
  else if addr == MTIMECMP_BASE_HI & ('n == 4)
  then {
    if   get_config_print_clint()
    then print_log("clint-hi<4>[" ^ bits_str(addr) ^ "] -> " ^ bits_str(mtimecmp[63..32]));
    // FIXME: Redundant zero_extend currently required by Lem backend
    Ok(zero_extend(32, mtimecmp[63..32]))
  }
  else if addr == MTIME_BASE & ('n == 4)
  then {
    if   get_config_print_clint()
    then print_log("clint[" ^ bits_str(addr) ^ "] -> " ^ bits_str(mtime));
    Ok(zero_extend(32, mtime[31..0]))
  }
  else if addr == MTIME_BASE & ('n == 8)
  then {
    if   get_config_print_clint()
    then print_log("clint[" ^ bits_str(addr) ^ "] -> " ^ bits_str(mtime));
    Ok(zero_extend(64, mtime))
  }
  else if addr == MTIME_BASE_HI & ('n == 4)
  then {
    if   get_config_print_clint()
    then print_log("clint[" ^ bits_str(addr) ^ "] -> " ^ bits_str(mtime));
    Ok(zero_extend(32, mtime[63..32]))
  }
  else {
    if   get_config_print_clint()
    then print_log("clint[" ^ bits_str(addr) ^ "] -> <not-mapped>");
    Err(paddr, accessFaultFromAccessType(access))
  }
}

// The `mip_was_written` parameter went with the `msip` door, its only
// `true` caller: the timer comparator is now the register's only
// writer, so a callback is owed exactly when the bit changes.
function clint_dispatch() -> unit = {
  let old_mip = mip.bits;
  mip[MTI] = bool_to_bit(mtimecmp <=_u mtime);
  if get_config_print_clint()
  then print_log("clint mtime " ^ bits_str(mtime));
  if old_mip != mip.bits then {
    csr_write_callback("mip", mip.bits);
  };
}

private val clint_store: forall 'n, 'n > 0. (physaddr, int('n), bits(8 * 'n)) -> MemoryOpResult(bool)
function clint_store(paddr, width, data) = {
  let Physaddr(addr) = paddr;
  let addr = addr - plat_clint_base;
  if addr == MTIMECMP_BASE & 'n == 8 then {
    if   get_config_print_clint()
    then print_log("clint<8>[" ^ bits_str(addr) ^ "] <- " ^ bits_str(data) ^ " (mtimecmp)");
    mtimecmp = zero_extend(64, data); // FIXME: Redundant zero_extend currently required by Lem backend
    clint_dispatch();
    Ok(true)
  } else if addr == MTIMECMP_BASE & 'n == 4 then {
    if   get_config_print_clint()
    then print_log("clint<4>[" ^ bits_str(addr) ^ "] <- " ^ bits_str(data) ^ " (mtimecmp)");
    mtimecmp = vector_update_subrange(mtimecmp, 31, 0, zero_extend(32, data));  // FIXME: Redundant zero_extend currently required by Lem backend
    clint_dispatch();
    Ok(true)
  } else if addr == MTIMECMP_BASE_HI & 'n == 4 then {
    if   get_config_print_clint()
    then print_log("clint<4>[" ^ bits_str(addr) ^ "] <- " ^ bits_str(data) ^ " (mtimecmp)");
    mtimecmp = vector_update_subrange(mtimecmp, 63, 32, zero_extend(32, data)); // FIXME: Redundant zero_extend currently required by Lem backend
    clint_dispatch();
    Ok(true)
  } else if addr == MTIME_BASE & 'n == 8 then {
    if   get_config_print_clint()
    then print_log("clint<8>[" ^ bits_str(addr) ^ "] <- " ^ bits_str(data) ^ " (mtime)");
    mtime = data;
    clint_dispatch();
    Ok(true)
  } else if addr == MTIME_BASE & 'n == 4 then {
    if   get_config_print_clint()
    then print_log("clint<4>[" ^ bits_str(addr) ^ "] <- " ^ bits_str(data) ^ " (mtime)");
    mtime[31 .. 0] = data;
    clint_dispatch();
    Ok(true)
  } else if addr == MTIME_BASE_HI & 'n == 4 then {
    if   get_config_print_clint()
    then print_log("clint<4>[" ^ bits_str(addr) ^ "] <- " ^ bits_str(data) ^ " (mtime)");
    mtime[63 .. 32] = data;
    clint_dispatch();
    Ok(true)
  } else {
    if   get_config_print_clint()
    then print_log("clint[" ^ bits_str(addr) ^ "] <- " ^ bits_str(data) ^ " (<unmapped>)");
    Err(paddr, E_SAMO_Access_Fault())
  }
}

// The timer. The performance counters are deleted (R-15-077), so
// `mtime` is the only thing a tick advances and there is nothing left
// to inhibit it.

function tick_clock() -> unit = {
  mtime  = mtime  + 1;
  clint_dispatch()
}

// The machine-level interrupt file (R-15-064, R-15-065).
//
// AIA is adopted capability-read with static routing: an MSI *is* a store to an
// interrupt file, so interrupt-send authority is a write capability in the
// composed topology rather than an entry in a side table. Only the machine
// level exists, and of that only the **pending array**: the supervisor and
// guest/VS files, the delivery-enable, threshold, and top-pending-selection
// machinery, and the whole `miselect`/`mireg`/`mtopei` indirect interface are
// dead Sail surface here and are excluded (isa-profile.md §5.2).
//
// **Deleting the indirect interface is what puts the array in the address map.**
// Upstream an interrupt file exposes `seteipnum` to senders and leaves the
// pending bits to be read through indirect CSRs; with those CSRs gone the array
// has to be somewhere software can reach, and *software reads pending bits with
// ordinary loads* is R-15-065's own sentence. So the file has two doors: the
// sender's write-only doorbell, and the array itself, read and written by the
// receiver through the capability the composed distribution gives it.
//
// Nothing here raises a trap. `mip`'s external-interrupt field is hardwired
// zero and the only asynchronous trap on the core is the slot-boundary timer
// (R-15-066a), so an MSI is *latched pending state* that software polls at a
// point of its own choosing, never a control transfer.
//
// The identity count is 64 here, one doubleword. It is a composition parameter
// rather than an architectural constant, and identity 0 is reserved by AIA and
// so sets nothing.
register imsic_eip : bits(64) = zeros()

let IMSIC_SETEIPNUM : physaddrbits = zero_extend(0x000)
let IMSIC_EIP       : physaddrbits = zero_extend(0x008)

private function within_imsic forall 'n, 0 < 'n <= max_mem_access . (Physaddr(addr) : physaddr, width : int('n)) -> bool = {
  if not(plat_have_imsic) then return false;
  let addr_int = unsigned(addr);
  let base_int = unsigned(plat_imsic_base);
  let size_int = unsigned(plat_imsic_size);
    base_int <= addr_int
  & (addr_int + sizeof('n)) <= (base_int + size_int)
}

private val imsic_load : forall 'n, 'n > 0. (MemoryAccessType(mem_payload), physaddr, int('n)) -> MemoryOpResult(bits(8 * 'n))
function imsic_load(access, paddr, width) = {
  let Physaddr(addr) = paddr;
  let addr = addr - plat_imsic_base;
  // `seteipnum` is write-only, as it is upstream: a sender has no reason to
  // read the doorbell it rang, and answering with the array through it would
  // give the pending state a second name.
  if addr == IMSIC_SETEIPNUM & ('n == 8) then Ok(zeros())
  else if addr == IMSIC_EIP & ('n == 8) then Ok(zero_extend(64, imsic_eip))
  else Err(paddr, accessFaultFromAccessType(access))
}

private val imsic_store : forall 'n, 'n > 0. (physaddr, int('n), bits(8 * 'n)) -> MemoryOpResult(bool)
function imsic_store(paddr, width, data) = {
  let Physaddr(addr) = paddr;
  let addr = addr - plat_imsic_base;
  if addr == IMSIC_SETEIPNUM & ('n == 8) then {
    // Sending an MSI: the value written is the interrupt identity, and an
    // identity outside the file's range sets nothing rather than faulting,
    // which is the standard's own disposition and keeps a sender's authority a
    // property of the capability it stored through rather than of the number it
    // chose.
    let eiid = unsigned(zero_extend(64, data)[5 .. 0]);
    let in_range = unsigned(zero_extend(64, data)) < 64;
    if in_range & eiid != 0 then imsic_eip = [imsic_eip with eiid = bitone];
    Ok(true)
  } else if addr == IMSIC_EIP & ('n == 8) then {
    // The receiver's door: pending bits are cleared by writing them back, since
    // the indirect interface that would otherwise carry the write is deleted.
    // Identity 0 is reserved and stays clear whatever is written.
    imsic_eip = zero_extend(64, data) & ~(zero_extend(64, 0b1));
    Ok(true)
  } else Err(paddr, E_SAMO_Access_Fault())
}

// The revocation sidecar's register slave (R-08-005a).
//
// The bitmap is not addressable as data and is not part of any compartment's
// memory: it is a window of its own, so *ordinary compartments cannot address
// the bitmap, and only the kernel revocation path may update it* is a fact
// about the composed capability distribution rather than about a mode
// (R-15-003). The filter that reads the plane on every capability load does not
// come through here: it reads the plane directly (core/revocation.sail), which
// is the model's statement of the bank-side lookup that *adds no fabric request
// or main-memory access* (R-08-005, isa-profile.md §7).
//
// Doublewords only. The sweep and the kernel's retire path both work a word at
// a time, and a narrower access would name a sub-word of a structure whose
// index is a granule.
private function within_revocation forall 'n, 0 < 'n <= max_mem_access . (Physaddr(addr) : physaddr, width : int('n)) -> bool = {
  if not(plat_have_revocation) then return false;
  let addr_int = unsigned(addr);
  let base_int = unsigned(plat_revocation_base);
    base_int <= addr_int
  & (addr_int + sizeof('n)) <= (base_int + revocation_bitmap_bytes)
}

private function revocation_word_index(Physaddr(addr) : physaddr) -> option(range(0, revocation_words - 1)) = {
  let offset = unsigned(addr - plat_revocation_base);
  if offset % 8 != 0 then None()
  else {
    let word = offset / 8;
    if 0 <= word & word < revocation_words then Some(word) else None()
  }
}

private val revocation_load : forall 'n, 'n > 0. (MemoryAccessType(mem_payload), physaddr, int('n)) -> MemoryOpResult(bits(8 * 'n))
function revocation_load(access, paddr, width) =
  if 'n == 8 then match revocation_word_index(paddr) {
    None()     => Err(paddr, accessFaultFromAccessType(access)),
    Some(word) => Ok(zero_extend(64, revocation_read_word(word))),
  } else Err(paddr, accessFaultFromAccessType(access))

private val revocation_store : forall 'n, 'n > 0. (physaddr, int('n), bits(8 * 'n)) -> MemoryOpResult(bool)
function revocation_store(paddr, width, data) =
  if 'n == 8 then match revocation_word_index(paddr) {
    None()     => Err(paddr, E_SAMO_Access_Fault()),
    Some(word) => { revocation_write_word(word, zero_extend(64, data)); Ok(true) },
  } else Err(paddr, E_SAMO_Access_Fault())

// The refresh and discharge sequencer's register slave (R-15-247h).
//
// **It answers no requester, at any width, in either direction, and that is the
// whole of its behaviour on this side of the fabric.** The mechanism is §12
// matter, sequenced by the RoT while every application core, DMA engine, and
// capability-bearing fabric initiator is held in reset, and every access this
// model can issue is a hart's. A hart executing an instruction is by
// construction not in reset, so an access that reaches this window is the same
// fail-stop sentinel event a non-ON decode already is (R-15-189h, R-15-247k)
// rather than a door software may knock on. The schedule the slave runs is
// sys/memory_sequencer.sail.
//
// The window is *in* the address map rather than absent from it because the
// composition declares the slave and an auditor checks it is unreachable, which
// is a different fact from its not existing: A-17 is the search of the decode
// surface for a maintenance instruction, and this is the search of the address
// map for a door (docs/absence-contract.md). Refusing here rather than leaving
// the window unclaimed is also what makes the refusal real: an IO address no
// device claims falls through to the RAM path and reads as zero (sys/mem.sail),
// which is silence and not a refusal.
private function within_memory_sequencer forall 'n, 0 < 'n <= max_mem_access . (Physaddr(addr) : physaddr, width : int('n)) -> bool = {
  if not(plat_have_memory_sequencer) then return false;
  let addr_int = unsigned(addr);
  let base_int = unsigned(plat_memory_sequencer_base);
  let size_int = unsigned(plat_memory_sequencer_size);
    base_int <= addr_int
  & (addr_int + sizeof('n)) <= (base_int + size_int)
}

private val memory_sequencer_load : forall 'n, 'n > 0. (MemoryAccessType(mem_payload), physaddr, int('n)) -> MemoryOpResult(bits(8 * 'n))
function memory_sequencer_load(access, paddr, _width) = Err(paddr, accessFaultFromAccessType(access))

private val memory_sequencer_store : forall 'n, 'n > 0. (physaddr, int('n), bits(8 * 'n)) -> MemoryOpResult(bool)
function memory_sequencer_store(paddr, _width, _data) = Err(paddr, E_SAMO_Access_Fault())

// The Root of Trust's four register slaves (R-09-001, sys/rot.sail): the OTP
// fuse bank holding the lifecycle state, the entropy root, the monotonic counter
// file, and the windowed watchdog.
//
// **All four are in the address map of every composition and all four answer the
// RoT alone.** The die has one management processor (R-15-194) and one RoT class
// in the roster (R-15-113), so these windows are the die's exactly as the
// refresh sequencer's is, and what decides whether a door opens is the composed
// hart's class rather than a configuration key: a requester on any other class
// is refused in both directions at every width, which is the same fail-stop
// event reaching the sequencer's window already is. That refusal is a *claimed*
// window and not an absent one, because an IO address no device claims falls
// through to the RAM path and reads as zero (sys/mem.sail), which is silence and
// not a refusal; corpus/platform-rot.s runs into both answers one page apart.
//
// **Doublewords only, and every unclaimed offset faults.** The unit of a fuse, a
// counter, a nonce and a conditioned word is the word, so a narrower or wider
// access names a sub-word of a structure whose index is the word, which is the
// revocation slave's own reason for the same restriction. And the decode below
// claims exactly the doors sys/rot.sail enumerates: there is no offset that
// disables the watchdog, clears the entropy latch, writes a counter, or unburns
// a fuse, and an access to one that is not a door faults rather than reading as
// zero.

private function within_rot_window forall 'n, 0 < 'n <= max_mem_access .
    (declared : bool, base : physaddrbits, size : physaddrbits,
     Physaddr(addr) : physaddr, width : int('n)) -> bool = {
  if not(declared) then return false;
  let addr_int = unsigned(addr);
  let base_int = unsigned(base);
  let size_int = unsigned(size);
    base_int <= addr_int
  & (addr_int + sizeof('n)) <= (base_int + size_int)
}

private function within_otp forall 'n, 0 < 'n <= max_mem_access . (addr : physaddr, width : int('n)) -> bool =
  within_rot_window(plat_have_otp, plat_otp_base, plat_otp_size, addr, width)

private function within_trng forall 'n, 0 < 'n <= max_mem_access . (addr : physaddr, width : int('n)) -> bool =
  within_rot_window(plat_have_trng, plat_trng_base, plat_trng_size, addr, width)

private function within_monotonic forall 'n, 0 < 'n <= max_mem_access . (addr : physaddr, width : int('n)) -> bool =
  within_rot_window(plat_have_monotonic, plat_monotonic_base, plat_monotonic_size, addr, width)

private function within_watchdog forall 'n, 0 < 'n <= max_mem_access . (addr : physaddr, width : int('n)) -> bool =
  within_rot_window(plat_have_watchdog, plat_watchdog_base, plat_watchdog_size, addr, width)

// The fuse bank's word index, or `None` where the offset is not one of its
// doors. Written as a bounds check rather than as a mask because the bank's
// width is the model's own and a mask would silently wrap a word past the end of
// it onto one inside it (sys/rot.sail, core/revocation.sail).
private function otp_fuse_index(offset : int) -> option(range(0, otp_fuse_words - 1)) = {
  if offset < ROT_OTP_FUSE_BASE then None()
  else {
    let byte = offset - ROT_OTP_FUSE_BASE;
    if byte % 8 != 0 then None()
    else {
      let word = byte / 8;
      if 0 <= word & word < otp_fuse_words then Some(word) else None()
    }
  }
}

private val otp_load : forall 'n, 'n > 0. (MemoryAccessType(mem_payload), physaddr, int('n)) -> MemoryOpResult(bits(8 * 'n))
function otp_load(access, paddr, width) = {
  let Physaddr(addr) = paddr;
  let offset = unsigned(addr - plat_otp_base);
  let rot = rot_is_composed_hart();
  if rot & ('n == 8) & offset == ROT_OTP_STATE then
    Ok(zero_extend(64, to_bits_truncate(64, lifecycle_to_index(otp_lifecycle))))
  else if rot & ('n == 8) & offset == ROT_OTP_DM_GATE then
    Ok(zero_extend(64, if debug_module_fabric_gated() then 0x0000000000000001 else zeros()))
  else if rot & ('n == 8) & offset == ROT_OTP_FUSE_COUNT then
    Ok(zero_extend(64, to_bits_truncate(64, otp_fuse_words)))
  else if rot & ('n == 8) then match otp_fuse_index(offset) {
    Some(word) => Ok(zero_extend(64, otp_read_fuse(word))),
    None()     => Err(paddr, accessFaultFromAccessType(access)),
  }
  else Err(paddr, accessFaultFromAccessType(access))
}

private val otp_store : forall 'n, 'n > 0. (physaddr, int('n), bits(8 * 'n)) -> MemoryOpResult(bool)
function otp_store(paddr, width, data) = {
  let Physaddr(addr) = paddr;
  let offset = unsigned(addr - plat_otp_base);
  let rot = rot_is_composed_hart();
  if rot & ('n == 8) & offset == ROT_OTP_BURN then {
    // The one door that moves the lifecycle, and it moves it only along
    // R-09-032's relation: a target outside the enumeration and an edge the
    // relation does not carry are both refused here, so *no edge outside the
    // relation exists* is the decode and not a check somebody may skip.
    let target = unsigned(zero_extend(64, data));
    if target >= lifecycle_state_count then Err(paddr, E_SAMO_Access_Fault())
    else if lifecycle_burn(lifecycle_of_index(target)) then Ok(true)
    else Err(paddr, E_SAMO_Access_Fault())
  }
  else if rot & ('n == 8) then match otp_fuse_index(offset) {
    // A burn sets bits and clears none. A write that would clear a bit already
    // set is refused rather than masked, so an attempt to unburn is a fault a
    // program can see instead of a store that quietly did nothing (R-09-033).
    Some(word) => if otp_burn_fuse(word, zero_extend(64, data)) then Ok(true)
                  else Err(paddr, E_SAMO_Access_Fault()),
    None()     => Err(paddr, E_SAMO_Access_Fault()),
  }
  else Err(paddr, E_SAMO_Access_Fault())
}

private val trng_load : forall 'n, 'n > 0. (MemoryAccessType(mem_payload), physaddr, int('n)) -> MemoryOpResult(bits(8 * 'n))
function trng_load(access, paddr, width) = {
  let Physaddr(addr) = paddr;
  let offset = unsigned(addr - plat_trng_base);
  let rot = rot_is_composed_hart();
  if rot & ('n == 8) & offset == ROT_TRNG_DRAW then
    // **The conditioner's output and never a source's** (R-15-241c). There is no
    // second offset here that answers with a raw sample, and the sampler that
    // produces one is private to sys/rot.sail, so *raw source output reaches no
    // consumer* is an absence in this decode rather than a rule about it. A draw
    // before the start-up health tests complete (R-09-006a) and a draw after the
    // fail-stop has latched (R-15-241b) are refused rather than answered at a
    // reduced rate, which is what *no degraded path* means at the one place a
    // consumer could ask for one.
    match rot_draw() {
      Some(word) => Ok(zero_extend(64, word)),
      None()     => Err(paddr, accessFaultFromAccessType(access)),
    }
  else if rot & ('n == 8) & offset == ROT_TRNG_HEALTH then {
    let started : bits(64) = zero_extend(64, rot_source_started);
    let complete : bits(64) = if rot_startup_complete() then 0x0000000100000000 else zeros();
    let stopped : bits(64) = if rot_entropy_fail_stop then 0x0000000200000000 else zeros();
    Ok(zero_extend(64, started | complete | stopped))
  }
  else if rot & ('n == 8) & offset == ROT_TRNG_SOURCES then
    Ok(zero_extend(64, to_bits_truncate(64, plat_rot_noise_sources)))
  else if rot & ('n == 8) & offset == ROT_TRNG_BUDGET then
    Ok(zero_extend(64, to_bits_truncate(64, plat_rot_startup_samples)))
  else Err(paddr, accessFaultFromAccessType(access))
}

private val trng_store : forall 'n, 'n > 0. (physaddr, int('n), bits(8 * 'n)) -> MemoryOpResult(bool)
function trng_store(paddr, width, _data) = {
  let Physaddr(addr) = paddr;
  let offset = unsigned(addr - plat_trng_base);
  if rot_is_composed_hart() & ('n == 8) & offset == ROT_TRNG_STARTUP then
    // The start-up tests are run, not requested: the door takes no argument
    // whose value could select a shorter budget, a subset of the sources, or a
    // weaker test, which is the whole of what the *fixed* in R-15-241b's fixed
    // sample budget can mean on this side of the fabric.
    if rot_run_startup_tests() then Ok(true) else Err(paddr, E_SAMO_Access_Fault())
  else Err(paddr, E_SAMO_Access_Fault())
}

private function monotonic_door_index(offset : int) -> option(monotonic_counter_index) = {
  if offset < ROT_CTR_BASE then None()
  else {
    let byte = offset - ROT_CTR_BASE;
    if byte % 8 != 0 then None()
    else {
      let i = byte / 8;
      if 0 <= i & i < monotonic_counter_count then Some(i) else None()
    }
  }
}

private val monotonic_load : forall 'n, 'n > 0. (MemoryAccessType(mem_payload), physaddr, int('n)) -> MemoryOpResult(bits(8 * 'n))
function monotonic_load(access, paddr, width) = {
  let Physaddr(addr) = paddr;
  let offset = unsigned(addr - plat_monotonic_base);
  let rot = rot_is_composed_hart();
  if rot & ('n == 8) & offset == ROT_CTR_COUNT then
    Ok(zero_extend(64, to_bits_truncate(64, monotonic_counter_count)))
  else if rot & ('n == 8) then match monotonic_door_index(offset) {
    Some(i) => Ok(zero_extend(64, monotonic_read(monotonic_counter_of_index(i)))),
    None()  => Err(paddr, accessFaultFromAccessType(access)),
  }
  else Err(paddr, accessFaultFromAccessType(access))
}

private val monotonic_store : forall 'n, 'n > 0. (physaddr, int('n), bits(8 * 'n)) -> MemoryOpResult(bool)
function monotonic_store(paddr, width, data) = {
  let Physaddr(addr) = paddr;
  let offset = unsigned(addr - plat_monotonic_base);
  if rot_is_composed_hart() & ('n == 8) & offset == ROT_CTR_ADVANCE then {
    // The one write, and it names a counter rather than carrying a value: there
    // is no door that sets, reloads, or decrements one, so *nothing rolls it
    // back* is a property of the address map (R-12-017, R-10-013).
    let i = unsigned(zero_extend(64, data));
    if i >= monotonic_counter_count then Err(paddr, E_SAMO_Access_Fault())
    else if monotonic_advance(monotonic_counter_of_index(i)) then Ok(true)
    else Err(paddr, E_SAMO_Access_Fault())
  }
  else Err(paddr, E_SAMO_Access_Fault())
}

private val watchdog_load : forall 'n, 'n > 0. (MemoryAccessType(mem_payload), physaddr, int('n)) -> MemoryOpResult(bits(8 * 'n))
function watchdog_load(access, paddr, width) = {
  let Physaddr(addr) = paddr;
  let offset = unsigned(addr - plat_watchdog_base);
  let rot = rot_is_composed_hart();
  if rot & ('n == 8) & offset == ROT_WDT_NONCE then Ok(zero_extend(64, watchdog_nonce))
  else if rot & ('n == 8) & offset == ROT_WDT_TICKS then Ok(zero_extend(64, watchdog_ticks))
  else if rot & ('n == 8) & offset == ROT_WDT_BITTEN then
    Ok(zero_extend(64, if watchdog_bitten then 0x0000000000000001 else zeros()))
  else if rot & ('n == 8) & offset == ROT_WDT_EARLY then
    Ok(zero_extend(64, to_bits_truncate(64, plat_rot_watchdog_early)))
  else if rot & ('n == 8) & offset == ROT_WDT_LATE then
    Ok(zero_extend(64, to_bits_truncate(64, plat_rot_watchdog_late)))
  else Err(paddr, accessFaultFromAccessType(access))
}

private val watchdog_store : forall 'n, 'n > 0. (physaddr, int('n), bits(8 * 'n)) -> MemoryOpResult(bool)
function watchdog_store(paddr, width, data) = {
  let Physaddr(addr) = paddr;
  let offset = unsigned(addr - plat_watchdog_base);
  let rot = rot_is_composed_hart();
  if rot & ('n == 8) & offset == ROT_WDT_PET then
    // A pet outside the window and a pet that is not the outstanding challenge
    // both latch the bite, so the store *retires* and the machine is what
    // changed: a bite is a reset line rather than a fault a program handles
    // (R-15-198, R-16-005), and reporting it as an access fault here would make
    // the last resort trappable by the thing it exists to catch.
    { let _ = watchdog_pet(zero_extend(64, data)); Ok(true) }
  else if rot & ('n == 8) & offset == ROT_WDT_ARM then { watchdog_arm(); Ok(true) }
  else Err(paddr, E_SAMO_Access_Fault())
}

// Basic terminal character I/O.

val plat_term_write = impure {cpp: "plat_term_write", lem: "plat_term_write"} : bits(8) -> unit
val plat_term_read  = impure {cpp: "plat_term_read", lem: "plat_term_read"}  : unit -> bits(8)

// Spike's HTIF device interface, which multiplexes the above MMIO devices.

bitfield htif_cmd : bits(64) = {
  device  : 63 .. 56,
  cmd     : 55 .. 48,
  payload : 47 .. 0
}

// Current value of the HTIF tohost register.
register htif_tohost : bits(64) = zeros()
register htif_done : bool = false
register htif_exit_code : bits(64) = zeros()

// Applications sometimes write the lower 32-bit payload bytes without
// writing the control bytes; this is seen in the riscv-tests suite.
// However, processing the payload bytes too early could miss a
// subsequent write to the control bytes.  As a workaround, if the
// payload is written a few times with the same value, without an
// intervening write to the control bytes, we process the whole htif
// command anyway.

register htif_cmd_write : bits(1) = zeros()
register htif_payload_writes : bits(4) = zeros()

// Once a htif command has been processed, the port is reset.
private function reset_htif () -> unit = {
  htif_cmd_write = 0b0;
  htif_payload_writes = 0x0;
  htif_tohost = zeros();
}

// Since the htif tohost port is only available at a single address,
// we'll assume here that physical memory model has correctly
// dispatched the address.

private val htif_load : forall 'n, 0 < 'n <= max_mem_access . (MemoryAccessType(mem_payload), physaddr, int('n)) -> MemoryOpResult(bits(8 * 'n))
function htif_load(access, addr, width) = {
  let Physaddr(paddr) = addr;
  if   get_config_print_htif()
  then print_log("htif[" ^ hex_bits_str(paddr) ^ "] -> " ^ bits_str(htif_tohost));

  let base : physaddrbits = match htif_tohost_base {
    Some(base) => base,
    None() => internal_error(__FILE__, __LINE__, "HTIF load while HTIF isn't enabled"),
  };

  // Only aligned 4-byte and 8-byte accesses are supported.
  if      width == 8 & paddr == base
  then    Ok(zero_extend(64, htif_tohost))         // FIXME: Redundant zero_extend currently required by Lem backend
  else if width == 4 & paddr == base
  then    Ok(zero_extend(32, htif_tohost[31..0]))  // FIXME: Redundant zero_extend currently required by Lem backend
  else if width == 4 & paddr == base + 4
  then    Ok(zero_extend(32, htif_tohost[63..32])) // FIXME: Redundant zero_extend currently required by Lem backend
  else    Err(addr, accessFaultFromAccessType(access))
}

private val htif_store : forall 'n, 0 < 'n <= max_mem_access . (physaddr, int('n), bits(8 * 'n)) -> MemoryOpResult(bool)
function htif_store(addr, width, data) = {
  let Physaddr(paddr) = addr;
  if   get_config_print_htif()
  then print_log("htif[" ^ hex_bits_str(paddr) ^ "] <- " ^ bits_str(data));

  let base : physaddrbits = match htif_tohost_base {
    Some(base) => base,
    None() => internal_error(__FILE__, __LINE__, "HTIF store while HTIF isn't enabled"),
  };

  // Store the written value so that we can ack it later.
  // Only aligned 4-byte and 8-byte accesses are supported.
  if      width == 8 & paddr == base
  then    { htif_cmd_write = 0b1;
            htif_payload_writes = htif_payload_writes + 1;
            htif_tohost = zero_extend(data) }
  else if width == 4 & paddr == base
  then    { if   data == htif_tohost[31 .. 0]
            then htif_payload_writes = htif_payload_writes + 1
            else htif_payload_writes = 0x1;
            htif_tohost = vector_update_subrange(htif_tohost, 31, 0, data) }
  else if width == 4 & paddr == base + 4
  then    { if   data[15 .. 0] == htif_tohost[47 .. 32]
            then htif_payload_writes = htif_payload_writes + 1
            else htif_payload_writes = 0x1;
            htif_cmd_write = 0b1;
            htif_tohost = vector_update_subrange(htif_tohost, 63, 32, data) }
  else return Err(addr, E_SAMO_Access_Fault());

  // Execute if there were repeated writes of the same payload without
  // a cmd (e.g. in riscv-tests), or we have a complete htif command.
  if   (((htif_cmd_write == 0b1) & (unsigned(htif_payload_writes) > 0))
        | (unsigned(htif_payload_writes) > 2))
  then {
    let cmd = Mk_htif_cmd(htif_tohost);
    match cmd[device] {
      0x00 => { // syscall-proxy
        if   get_config_print_htif()
        then print_log("htif-syscall-proxy cmd: " ^ bits_str(cmd[payload]));
        if   cmd[payload][0] == 0b1
        then {
             htif_done = true;
             htif_exit_code = (zero_extend(64, cmd[payload]) >> 1)
        }
        else ()
      },
      0x01 => { // terminal
        if   get_config_print_htif()
        then print_log("htif-term cmd: " ^ bits_str(cmd[payload]));
        match cmd[cmd] {
          0x00 => /* TODO: terminal input handling */ (),
          0x01 => plat_term_write(cmd[payload][7..0]),
          c    => print("Unknown term cmd: " ^ bits_str(c))
        };
        // reset to ack
        reset_htif()
      },
      _ => print("htif-???? cmd: " ^ bits_str(data))
    }
  };
  Ok(true)
}

// Top-level MMIO dispatch
function within_mmio_readable forall 'n, 0 < 'n <= max_mem_access . (addr : physaddr, width : int('n)) -> bool =
  if get_config_rvfi()
  then false
  else within_clint(addr, width) | within_imsic(addr, width) | within_revocation(addr, width)
       | within_memory_sequencer(addr, width)
       | within_otp(addr, width) | within_trng(addr, width)
       | within_monotonic(addr, width) | within_watchdog(addr, width)
       | (within_htif_readable(addr, width) & 1 <= 'n)

function within_mmio_writable forall 'n, 0 < 'n <= max_mem_access . (addr : physaddr, width : int('n)) -> bool =
  if get_config_rvfi()
  then false
  else within_clint(addr, width) | within_imsic(addr, width) | within_revocation(addr, width)
       | within_memory_sequencer(addr, width)
       | within_otp(addr, width) | within_trng(addr, width)
       | within_monotonic(addr, width) | within_watchdog(addr, width)
       | (within_htif_writable(addr, width) & 'n <= 8)

function mmio_read forall 'n, 0 < 'n <= max_mem_access . (access : MemoryAccessType(mem_payload), paddr : physaddr, width : int('n)) -> MemoryOpResult(bits(8 * 'n)) =
  if   within_clint(paddr, width)
  then clint_load(access, paddr, width)
  else if within_imsic(paddr, width)
  then imsic_load(access, paddr, width)
  else if within_revocation(paddr, width)
  then revocation_load(access, paddr, width)
  else if within_memory_sequencer(paddr, width)
  then memory_sequencer_load(access, paddr, width)
  else if within_otp(paddr, width)
  then otp_load(access, paddr, width)
  else if within_trng(paddr, width)
  then trng_load(access, paddr, width)
  else if within_monotonic(paddr, width)
  then monotonic_load(access, paddr, width)
  else if within_watchdog(paddr, width)
  then watchdog_load(access, paddr, width)
  else if within_htif_readable(paddr, width)
  then htif_load(access, paddr, width)
  else Err(paddr, accessFaultFromAccessType(access))

function mmio_write forall 'n, 0 < 'n <= max_mem_access . (paddr : physaddr, width : int('n), data: bits(8 * 'n)) -> MemoryOpResult(bool) =
  if   within_clint(paddr, width)
  then clint_store(paddr, width, data)
  else if within_imsic(paddr, width)
  then imsic_store(paddr, width, data)
  else if within_revocation(paddr, width)
  then revocation_store(paddr, width, data)
  else if within_memory_sequencer(paddr, width)
  then memory_sequencer_store(paddr, width, data)
  else if within_otp(paddr, width)
  then otp_store(paddr, width, data)
  else if within_trng(paddr, width)
  then trng_store(paddr, width, data)
  else if within_monotonic(paddr, width)
  then monotonic_store(paddr, width, data)
  else if within_watchdog(paddr, width)
  then watchdog_store(paddr, width, data)
  else if within_htif_writable(paddr, width)
  then htif_store(paddr, width, data)
  else Err(paddr, E_SAMO_Access_Fault())
