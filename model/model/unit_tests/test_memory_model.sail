// Properties of the memory model the profile adopts and of the prediction
// discipline it refuses: Ztso in place of RVWMO (core/extensions.sail,
// core/phys_mem_interface.sail) and the collapse of `fence` to `drain | nop`
// (extensions/I/base_insts.sail).
//
// What is asserted here is bounded by what an architectural model can hold, and
// the bound is worth stating before the properties rather than after. Ztso is a
// property of the store buffer and of the fabric beneath it, so the ordering
// itself is an RTL-against-Sail obligation and not something this model exhibits
// (R-15-016): one hart over single-copy memory has no execution that separates
// TSO from sequential consistency, and `sail_barrier` is a no-op in the C
// backend besides. Static-only prediction is the same shape one step further
// out, discharged structurally by rows A-04 through A-06 of the
// microarchitectural absence contract rather than by refinement, because Sail
// carries architectural state and no model can state *there is no branch
// predictor* (R-15-021, R-15-098).
//
// So three of the four properties below are about the decode surface and the
// total function beneath it, which is the whole of what R-15-017 puts inside an
// architectural model, and the fourth is the visibility a machine with no buffer
// already has. The one architecturally observable change this batch makes is the
// reserved-`fm` trap.

// *****************************************************************
// `fence` collapses to `drain | nop`.

// R-15-017 states the surviving semantics as two conditions over named bits: a
// `fence` drains iff its predecessor set contains a write (`PW` or `PO`) and its
// successor set contains a read (`PR` or `PI`). The sets are IORW, so the
// property is stated below over those four bit positions and the implementation
// is one mask per side; a lattice arm per legal pair, which is what upstream
// carries, is the thing being deleted rather than a second way of saying this.
//
// The quantification is over all 256 pairs because the claim is total: there is
// no reserved predecessor or successor combination left to except, every one of
// them being either a drain or a no-op and none of them illegal.
$[test]
function test_fence_collapses_to_drain_or_nop() -> unit = {
  foreach (p from 0 to 15) {
    foreach (s from 0 to 15) {
      let pred : bits(4) = to_bits(4, p);
      let succ : bits(4) = to_bits(4, s);

      // IORW: the write half of a predecessor is O and W, the read half of a
      // successor is I and R.
      let pred_has_write = pred[0] == bitone | pred[2] == bitone;
      let succ_has_read  = succ[1] == bitone | succ[3] == bitone;
      assert(fence_drains(pred, succ) == (pred_has_write & succ_has_read));

      // Every legal pair retires, drain or not. A fence that could fail would
      // be a fence a partition could observe failing.
      match execute(FENCE(pred, succ, zreg, zreg)) {
        Retire_Success() => (),
        _                => assert(false, "every legal fence must retire"),
      };
    }
  };

  // The four corners, read off the requirement rather than off the loop, so a
  // change to the masks that preserved the loop's own restatement would still
  // be caught: rw,rw drains; w,r drains and is the minimal one that does; r,w
  // does not, having a read predecessor and a write successor; and an empty set
  // on either side is a no-op whatever stands on the other.
  assert(fence_drains(0b0011, 0b0011));
  assert(fence_drains(0b0001, 0b0010));
  assert(not_bool(fence_drains(0b0010, 0b0001)));
  assert(not_bool(fence_drains(0b0000, 0b0011)));
  assert(not_bool(fence_drains(0b0011, 0b0000)));

  // The I and O bits are read, which is what retires `is_fiom_active`: upstream
  // ignored them here and made the implication a bit of `menvcfg` (R-15-017).
  assert(fence_drains(0b0100, 0b1000));
}

// *****************************************************************
// A reserved `fm` traps.

// The base ISA's forward-compatibility rule is that an implementation treats a
// reserved `fm` as `fm`=0000 and executes it. This profile refuses that rule:
// all reserved, custom, and unused encodings trap rather than silently
// executing (R-15-014), and R-15-017 says so for this instruction by name. This
// is the one architecturally observable change the memory-model batch makes.
$[test]
function test_a_reserved_fence_fm_is_illegal() -> unit = {
  // The two allocated `fm` values decode.
  match ext_decode(0x0000000f) {
    FENCE(_, _, _, _) => (),
    _                 => assert(false, "fm=0000 must decode as fence"),
  };
  match ext_decode(0x0330000f) {
    FENCE(_, _, _, _) => (),
    _                 => assert(false, "fence rw,rw must decode as fence"),
  };
  match ext_decode(0x8330000f) {
    FENCE_TSO() => (),
    _           => assert(false, "fm=1000 at rw,rw must decode as fence.tso"),
  };

  // Every other `fm` is reserved and reaches no clause.
  foreach (fm from 1 to 15) {
    let word : bits(32) = to_bits(4, fm) @ 0b0011 @ 0b0011 @ 0b00000 @ 0b000 @ 0b00000 @ 0b0001111;
    if fm != 8 then {
      match ext_decode(word) {
        ILLEGAL(_) => (),
        _          => assert(false, "a reserved fence fm must be illegal"),
      }
    }
  };

  // `fm`=1000 is `fence.tso`'s allocation and not a fourth fence: it is
  // reserved at every predecessor and successor pair but rw,rw.
  match ext_decode(0x8000000f) {
    ILLEGAL(_) => (),
    _          => assert(false, "fm=1000 away from rw,rw must be illegal"),
  };

  // `rs1` and `rd` stay legal-and-ignored, which is the residual class the base
  // ISA reserves for a *future* extension rather than for none. It is the
  // contrast `fence.t` is written against, whose own reserved fields trap.
  match ext_decode(0x0338000f) {
    FENCE(_, _, _, _) => (),
    _                 => assert(false, "a fence with a non-zero rs1 stays legal"),
  };
  match ext_decode(0x0330018f) {
    FENCE(_, _, _, _) => (),
    _                 => assert(false, "a fence with a non-zero rd stays legal"),
  };
}

// *****************************************************************
// Neither fence disturbs architectural state.

// A fence's whole architectural content is the barrier, so what is left to
// assert is that nothing else moved, the validity tag of a held capability
// included: a fence that cleared a tag would be a fence that destroyed
// authority, and the tag is the one piece of register state no integer
// comparison would notice going (R-15-007i, R-15-007r).
$[test]
function test_neither_fence_disturbs_architectural_state() -> unit = {
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  C(encdec_reg(0b00010)) = setCapAddrChecked(region, 0x0000000080000000);
  X(encdec_reg(0b00011)) = 0x0123456789abcdef;

  // The draining arm, the two no-op arms, and `fence.tso`.
  match execute(FENCE(0b0011, 0b0011, zreg, zreg)) {
    Retire_Success() => (),
    _                => assert(false, "a draining fence must retire"),
  };
  match execute(FENCE(0b0010, 0b0001, zreg, zreg)) {
    Retire_Success() => (),
    _                => assert(false, "a non-draining fence must retire"),
  };
  match execute(FENCE(0b0000, 0b0000, zreg, zreg)) {
    Retire_Success() => (),
    _                => assert(false, "an empty fence must retire"),
  };
  match execute(FENCE_TSO()) {
    Retire_Success() => (),
    _                => assert(false, "fence.tso must retire"),
  };

  assert(C(encdec_reg(0b00010)).tag);
  assert(C(encdec_reg(0b00010)) == setCapAddrChecked(region, 0x0000000080000000));
  assert(X(encdec_reg(0b00011)) == 0x0123456789abcdef);
}

// *****************************************************************
// A store is visible to the next load without a fence.

// Sequential consistency by absence, read at one hart. The drain is available
// for userspace store to later-load synchronization and this model has no buffer
// for a load to pass, so the fence is architecturally empty here and the value
// is already there (R-15-015, R-15-213). That is not a demonstration that the
// machine is TSO; it is the statement that the *model* cannot distinguish TSO
// from sequential consistency, which is why R-15-016 puts the guarantee on the
// RTL side and why the store buffer's deletion is a design-space question the
// exploration answers rather than something this file could settle.
$[test]
function test_a_store_is_visible_to_the_next_load_without_a_fence() -> unit = {
  let cell = Physaddr(0x0000000080000200);

  let _ = mem_write_value(cell, 8, 0x0f1e2d3c4b5a6978, Store(Data), false, false);
  match mem_read(Load(Data), cell, 8, false, false) {
    Ok(v)     => assert(v == 0x0f1e2d3c4b5a6978),
    Err(_, _) => assert(false, "a first-class cell must be readable"),
  };

  // Interposing the drain changes nothing, in either direction.
  match execute(FENCE(0b0011, 0b0011, zreg, zreg)) {
    Retire_Success() => (),
    _                => assert(false, "a draining fence must retire"),
  };
  match mem_read(Load(Data), cell, 8, false, false) {
    Ok(v)     => assert(v == 0x0f1e2d3c4b5a6978),
    Err(_, _) => assert(false, "a first-class cell must be readable"),
  };

  let _ = mem_write_value(cell, 8, zeros(), Store(Data), false, false);
}
