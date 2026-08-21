// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The revocation plane: the load filter's state and the predicate over it.
//
// R-08-005 puts *freed ⇒ unreachable* at **access** time rather than at sweep
// completion, and R-08-005b puts the clear inside the load's own definition: a
// capability-width load whose result is revoked writes the value back with its
// validity tag cleared, and that is a defined result of the load rather than an
// effect a filter layers onto it. What is here is only the state that decides
// it; the clear is in `cap_load` (extensions/CHERI/cheri_mem.sail).
//
// The structure is CHERIoT's non-MMU realization and not a one-bit imitation of
// RVY `Svyrg`: a dedicated bitmap over a composition-fixed union of 64-byte
// aligned revocable intervals, **one bit per 8-byte capability granule**, `0`
// live and `1` revoked. It carries the load-time predicate and nothing else,
// the epoch, the sweep, and the quarantine staying kernel protocol state rather
// than being collapsed into this bit (R-08-005a, R-08-006, R-08-007a). No
// colour is stamped at derivation and the format carries no colour field, so
// this address-keyed bit is what both cases rest on, the object case and the
// grant-slot case alike (R-08-004a, R-08-004b).
//
// **The map is one interval here, and that is a fact about the composition
// rather than a narrowing of the requirement.** The covered set is whatever
// `revocation_covered` answers over, so a second interval is a clause in that
// one function: the index, the load's clear, and the register slave below all
// quantify over the predicate rather than over the interval. One composed image
// has one revocable region, so one is what the configuration declares.
//
// **The width is the model's bound and not the architecture's.** The payload is
// exactly Σ|I|/64 bytes and the static memory plan charges it, its ECC bits, and
// macro periphery against the SRAM capacity budget (R-08-005a); a Sail register
// is a fixed width, so the model fixes a width and the configuration is
// validated to fit inside it (postlude/validate_config.sail) rather than the
// other way round.

// 4096 granules, so 32 KiB of covered interval and a 512-byte payload. The
// granule is the capability's own, because the bit that decides a loaded
// capability is indexed by that capability's base: the two have to be keyed
// alike or the index would not name the capability it decides (R-15-203).
type log2_revocation_granules : Int = 12
let  log2_revocation_granules = sizeof(log2_revocation_granules)
type revocation_granules : Int = 2 ^ log2_revocation_granules
let  revocation_granules = sizeof(revocation_granules)

// The payload, in bytes and in doublewords: Σ|I|/64 exactly, which is what the
// register slave below exposes to the kernel revocation path.
type revocation_bitmap_bytes : Int = 2 ^ (log2_revocation_granules - 3)
let  revocation_bitmap_bytes = sizeof(revocation_bitmap_bytes)
type revocation_words : Int = 2 ^ (log2_revocation_granules - 6)
let  revocation_words = sizeof(revocation_words)

// The widest interval a bitmap of that width covers.
let revocation_max_interval : int = revocation_granules * cap_size

register revocation_bits : bits(revocation_granules) = zeros()

// Whether a physical address falls in the covered union. An address outside it
// is *live* rather than absent: an uncovered interval takes the same pipeline
// path with a constant live result, which is what keeps one fixed latency on
// every capability load whether or not its base is covered (R-08-005, R-17-023).
function revocation_covered(addr : physaddrbits) -> bool = {
  if not(plat_have_revocation) then false
  else {
    let addr_int = unsigned(addr);
    let base_int = unsigned(plat_revocation_interval_base);
    let size_int = unsigned(plat_revocation_interval_size);
    base_int <= addr_int & addr_int < (base_int + size_int)
  }
}

// The granule index a covered address selects. The arithmetic is in bits rather
// than in integers so the result is in range by construction: the low
// `log2_revocation_granules` bits of the granule-shifted offset are exactly the
// bitmap's index space, and the caller has already established that the address
// is covered.
function revocation_index(addr : physaddrbits) -> range(0, revocation_granules - 1) = {
  let offset = addr - plat_revocation_interval_base;
  unsigned((offset >> log2_cap_size)[log2_revocation_granules - 1 .. 0])
}

// The predicate the load filter reads: is the granule containing this address
// revoked? Indexed by the **loaded capability's base**, which is the one field
// that names the object rather than the access, so a stale capability into the
// middle of a freed object is caught as surely as one to its start (R-08-005a).
function revocation_revoked(addr : physaddrbits) -> bool =
  if not(revocation_covered(addr)) then false
  else revocation_bits[revocation_index(addr)] == bitone

// The kernel revocation path's view of the plane, a doubleword at a time.
//
// The bitmap is not addressable as data: it is a register slave of its own
// (sys/platform.sail), so an ordinary compartment reaches it only if the
// composed distribution hands it a capability to that window, which is what
// *only the kernel revocation path may update it* becomes on a machine whose
// privilege is a permission rather than a ring (R-08-005a, R-15-003).
//
// The two accessors are written as bit loops rather than as a slice because the
// index is dynamic and a bit-at-a-time update is the one form the model already
// uses for a dynamically indexed bitvector (`cloadtags`).
function revocation_read_word(w : range(0, revocation_words - 1)) -> bits(64) = {
  var out : bits(64) = zeros();
  foreach (b from 0 to 63) {
    out = [out with b = revocation_bits[w * 64 + b]]
  };
  out
}

function revocation_write_word(w : range(0, revocation_words - 1), v : bits(64)) -> unit = {
  foreach (b from 0 to 63) {
    revocation_bits = [revocation_bits with (w * 64 + b) = v[b]]
  }
}
