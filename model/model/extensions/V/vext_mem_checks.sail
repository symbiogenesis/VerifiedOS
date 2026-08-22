// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The capability semantics of the vector memory surface: what every element of
// a vector load or store owes its authorising capability, and which elements
// may raise (R-08-003, R-15-115, R-15-115a, R-15-115b).
//
// **The check itself is not here and is not a second copy of one.** A vector
// memory operation is scalar-issued: it names a base register, and that
// register holds the capability the access is authorised by, exactly as an
// ordinary load or store does (R-15-115, R-15-001c). Every element of every
// clause in vext_mem_insts.sail reaches memory through `data_read` or
// `data_write`, which compose `ext_data_get_addr` over `cap_data_checks`
// (core/addr_checks.sail), so the check lands per element, at the element's own
// address and its own width, with no vector-specific check beside it. That is
// what makes accelerator-class compute inherit the whole spatial-safety story
// rather than a device-side approximation (R-08-003), and it is why an indexed
// or gather-scatter element, whose address is a runtime value, is checked like
// any other (R-15-085a).
//
// **The tag clear is not here either, for the same kind of reason.** A vector
// store clears the validity tag of every granule it overwrites, partial-granule
// writes included (R-15-115a), and that is a property of the write path rather
// than of any instruction: `mem_write_value` carries `default_meta` and
// `__WriteRAM_Meta` clears every granule the access spans (core/mem_metadata.sail,
// R-15-007r, R-15-183). A vector store therefore lands the tag write a scalar
// store already performs, once per element, and adds no architectural state and
// no admission-test case (R-15-012).
//
// **What is here is the one thing neither of those supplies: the mask.** The
// two contracts over a masked vector memory operation compose as *check every
// element, fault only on the active ones* (R-15-115b), which is the only
// realization satisfying both R-15-085's mask-independent timing and
// R-15-115's element-wise check rather than a compromise between them.

// The body elements a vector memory operation turns off, as distinct from the
// elements it never had.
//
// `init_masked_result` and `init_masked_source` return one mask, and it folds
// three different reasons an element is inactive: it lies past `vl`, it lies
// past a fractional LMUL's real element count, or `v0` turns it off. Only the
// third is a *mask*, and only the third carries R-15-115b's obligation: `vl`
// and `vtype` are architectural registers a partition reads back, so an
// operation shorter than VLMAX leaks nothing by being shorter, where the mask
// is a value the discipline may hold secret-labeled data beside and whose
// observability through timing or memory traffic is what R-15-085 forbids.
//
// The predicate is derived from the existing one rather than restated:
// `init_masked_source` with an all-ones vector mask is exactly *in the body*,
// so the body-inactive elements are that set minus the ones `v0` admits. A
// second copy of the tail arithmetic is how the two would come to disagree.
val vector_body_inactive : forall 'n 'p, 'n > 0. (int('n), int('p), bits('n)) -> bits('n)
function vector_body_inactive(num_elem, LMUL_pow, vm_val) = {
  let in_body : bits('n) = init_masked_source(num_elem, LMUL_pow, ones());
  in_body & ~(vm_val)
}

// One masked-off element's capability check, performed and discarded.
//
// The arguments are the ones the active element's access takes, so the check is
// the same check at the same cost: the authority is the same base register, the
// address is the same element address, and the width is the same element width.
// What differs is only what happens to the answer, which is nothing
// (R-15-115b): a masked-off element raises no capability exception, because
// raising it would leak the mask through the trap and would depart from the
// element-wise semantics the check is defined against, while skipping the check
// would hand back the cycles the timing contract holds and leak the mask the
// other way (R-15-085, R-15-085a).
//
// **No address reaches the memory interface, whether the check passed or
// failed, and that is stronger than the requirement rather than short of it.**
// R-15-115b pads the *failing* masked-off access, so that an address the domain
// holds no authority for never reaches the fabric while the bank cycle is still
// spent. This model executes no cycles (core/timing.sail is where a latency
// lives), so an access issued here would contribute no timing and would instead
// contribute exactly what a masked-off element must not have: a store would
// write memory, and a load of a device endpoint would be a read with a side
// effect. So every masked-off access is padded here, the failing one and the
// passing one alike, and the bank cycle both of them spend is R-15-085a's
// `Timing_VectorMemUnit` and `Timing_VectorMemIndexed` rows rather than a
// transaction this file could emit.
val vector_masked_element_check :
  (regidx, xlenbits, mem_access_width, MemoryAccessType(mem_payload)) -> unit

function vector_masked_element_check(base, offset, width, access) = {
  // The result is discarded and the discarding is the semantics. It is written
  // as a binding rather than as a bare call so that a reader sees a value being
  // dropped, which is what R-15-115b says happens to it.
  let _discarded : Ext_DataAddr_Check(ext_data_addr_error) =
    ext_data_get_addr(base, offset, access, width);
  ()
}
