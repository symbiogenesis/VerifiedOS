// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// The tag-plane functions below follow the CHERI-RISC-V Sail model
// (CTSRD-CHERI/sail-cheri-riscv @ bb07488d, src/cheri_mem_metadata.sail), which is
// subject to the BSD two-clause licence in model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The metadata every physical memory access carries is the CHERI validity
// tag: one bit per capability-sized granule, held in a plane of its own
// (R-15-203). It is not addressable as data, so it is metadata on the access
// rather than a second memory the model reads.

type mem_meta = bool

let default_meta : mem_meta = false

// The tag plane is indexed by granule, not by byte: the granule holding an
// address is what a tag belongs to, so the index is the address with its
// in-granule bits dropped. Every capability access is granule-aligned, and a
// data access clears the tag of every granule it overwrites, which is what
// makes tag clearing a property of the write path rather than an instruction
// (R-15-007r, R-15-115a, R-15-183).
type tagaddrbits = bits(physaddrbits_len - log2_cap_size)

function addr_to_tag_addr(addr : physaddrbits) -> tagaddrbits =
  truncateLSB(addr, physaddrbits_len - log2_cap_size)

function tag_addr_to_addr(tag_addr : tagaddrbits) -> physaddrbits =
  tag_addr @ zeros(log2_cap_size)

// The tag plane's backing store. These are the Sail runtime's own tag
// primitives, which the emulator already links; the concurrency interface
// reaches them through internal names the model may not use, and its request
// tag is keyed by the access address rather than by the granule, so the model
// keys the plane itself and the interface's tag field stays unused.
val __write_tag = impure "write_tag_bool" : (bits(64), bool) -> unit
val __read_tag = impure "read_tag_bool" : bits(64) -> bool

function __WriteRAM_Meta(addr : physaddrbits, width : mem_access_width, meta : mem_meta) -> unit = {
  // An access may span more than one granule: a capability store is aligned
  // and spans exactly one, while a wide data store covers as many as its
  // width reaches and clears every one of them.
  let first = unsigned(addr_to_tag_addr(addr));
  let last = unsigned(addr_to_tag_addr(addr + (width - 1)));
  foreach (i from first to last) {
    __write_tag(to_bits_truncate(64, i), meta);
  }
}

function __ReadRAM_Meta(addr : physaddrbits, _width : mem_access_width) -> mem_meta =
  __read_tag(zero_extend(addr_to_tag_addr(addr)))
