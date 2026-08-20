// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// This file implements utilities for access splitting for misaligned accesses.

// Helpers to check address alignment.
//
//   is_aligned_addr - checks for alignment of a physical or virtual address

function is_aligned_paddr(Physaddr(addr) : physaddr, width : nat1) -> bool =
  unsigned(addr) % width == 0

function is_aligned_vaddr(Virtaddr(addr) : virtaddr, width : nat1) -> bool =
  unsigned(addr) % width == 0

overload is_aligned_addr = {is_aligned_paddr, is_aligned_vaddr}

// The misaligned atomicity granule size is restricted by the PMA
// region granule.
type mag_size_exp = range(0, pma_granule_bits)

// This is an external option used for misaligned scalar or vector
// load/store accesses to physical memory regions that do not specify
// a MAG PMA or accesses to which the MAG PMA does not apply, and the
// regions do not raise exceptions for misaligned accesses.
//
// It specifies an integer N, such that when N is greater than zero,
// accesses (as atomic events) are allowed provided the access occurs
// within a naturally aligned 2^N byte region. If the access spans
// more than one of these regions it will be split into multiple
// memory operations.  For the current implementation this region must
// not be more than the page size (i.e. 2^12 = 4096 bytes).

let sys_misaligned_allowed_within_exp : mag_size_exp = config memory.misaligned.default_allowed_within_exp

// This is a external option that controls the order in which the model
// performs misaligned accesses.
let sys_misaligned_order_decreasing : bool = config memory.misaligned.order_decreasing

private val split_access : forall 'n 'width, 13 <= 'n <= 64 & 0 < 'width <= max_mem_access.
  (bits('n), int('width)) -> {'m 'bytes, 'width == 'm * 'bytes & 'bytes > 0. (int('m), int('bytes))}

function split_access(addr, width) = {
  // Use the minimum alignment of the address and the specified width.
  let addr_align  = count_trailing_zeros(addr);
  let width_align = count_trailing_zeros(to_bits(sizeof(pma_granule_bits) + 1, width));
  let bytes_per_access = 2 ^ min(addr_align, width_align);
  let num_accesses = width / bytes_per_access;
  assert(width == num_accesses * bytes_per_access);
  (num_accesses, bytes_per_access)
}

// Though this property seems redundant given the type signature
// above, the test ensures that the assert does not trip.
$[property]
private val prop_split_access : forall 'width, 0 < 'width <= max_mem_access. (bits(16), int('width)) -> bool
function prop_split_access(addr, width) = {
  let (splits, split_width) = split_access(addr, width);
  splits * split_width == width
}

// This is an external option that, when true, causes misaligned load/store accesses
// to be split into single byte operations.  Otherwise, such misaligned accesses
// are split into multiple accesses of smaller widths such that each of the latter
// accesses is aligned.
let sys_misaligned_byte_by_byte : bool = config memory.misaligned.byte_by_byte

enum Splittability = {CanSplit, CannotSplit}

private val split_misaligned : forall 'width, 0 < 'width <= max_mem_access.
  (physaddr, int('width), mag_size_exp, Splittability) -> {'n 'bytes, 'width == 'n * 'bytes & 'bytes > 0. (int('n), int('bytes))}

function split_misaligned(Physaddr(addr), width, allowed_within_exp, splittable) = {
  let do_not_split = splittable == CannotSplit |
     (unsigned(addr) % width == 0) |
     allowed_misaligned(addr[xlen - 1 .. 0], width, allowed_within_exp);

  if do_not_split then (1, width)
  else if sys_misaligned_byte_by_byte then (width, 1)
  else split_access(addr, width)
}

type valid_misaligned_order('n, 'first, 'last, 'step) -> Bool =
    ('first == 0 & 'last == 'n - 1 & 'step == 1)
  | ('first == 'n - 1 & 'last == 0 & 'step == -1)

private val misaligned_order : forall 'n.
  int('n) -> {'first 'last 'step, valid_misaligned_order('n, 'first, 'last, 'step). (int('first), int('last), int('step))}

function misaligned_order(n) = {
  if sys_misaligned_order_decreasing then {
    (n - 1, 0, -1)
  } else {
    (0, n - 1, 1)
  }
}

// The page-boundary split is deleted with address translation: an
// access was split before translation because its two halves could
// land in different pages, and there are no pages (R-15-002).
