// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// These two definitions refer to the architectural physical address.
type physaddrbits = bits(physaddrbits_len)
let physaddrbits_len = sizeof(physaddrbits_len)

// There is no address translation: `satp` is Bare and the sole
// autonomous hardware walker is deleted with the MMU (R-15-002,
// R-15-038). `virtaddr` is therefore the *effective* address an
// instruction computes, which is XLEN wide, and `physaddr` is the
// address presented to the physical memory map. The two types stay
// distinct because the widths do: an effective address that does not
// fit the implemented physical address faults at the PMA check rather
// than wrapping.
newtype physaddr = Physaddr : physaddrbits
newtype virtaddr = Virtaddr : xlenbits

function bits_of_physaddr(Physaddr(paddr) : physaddr) -> physaddrbits = paddr

function bits_of_virtaddr(Virtaddr(vaddr) : virtaddr) -> xlenbits = vaddr

// The effective address *is* the physical address.
function physical_address(Virtaddr(vaddr) : virtaddr) -> physaddr = Physaddr(zero_extend(vaddr))

function sub_virtaddr_xlenbits(Virtaddr(addr) : virtaddr, offset : xlenbits) -> virtaddr = Virtaddr(addr - offset)

overload operator - = { sub_virtaddr_xlenbits }

overload bits_of = { bits_of_physaddr, bits_of_virtaddr }

// This refers to the size of an _implemented_ physical address, which
// may be smaller than the architectural physical address.
type physaddr_bits : Int = config memory.physaddr_bits
// The lower bound of 13 is required to prevent empty bitvectors during address translation.
constraint 13 <= physaddr_bits & physaddr_bits <= 64
let physaddr_bits = sizeof(physaddr_bits)
