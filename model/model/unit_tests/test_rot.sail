// Properties of the Root of Trust's four peripherals (sys/rot.sail): the OTP
// fuse bank holding the lifecycle state (R-09-003, R-09-032), the entropy root
// (R-15-241), the monotonic counter file (R-10-013), and the windowed watchdog
// (R-15-240).
//
// Each of these is net-new here and no upstream model carries one, so there is
// no oracle to differentially test it against and a property asserted about it
// and a program that runs it are different evidence. The program half is
// corpus/platform-rot.s, and it reaches exactly one side of these devices: the
// golden emulator is the C class (M0.10), the windows answer the RoT alone
// (R-15-194), and so every check a corpus member can make is a refusal. The
// mechanism behind the doors is therefore asserted here, which is the same
// division test_keccak.sail makes between the permutation and the instruction
// and M0.8c's scratchpad makes between a property and a member.
//
// **Two properties install a roster of their own and put back what they found**,
// for the reason M0.8c's scratchpad properties install a region: the harness runs
// under the generated *max* configuration, which composes hart 0 on the C class,
// so a property about what the RoT sees is a property about a structure no
// configuration this harness runs has. They drop the head they prepended rather
// than assigning a binding saved beforehand, which is the one of the two shapes
// that is correct whatever the list representation is: both restore here, and
// the other one does so because the emitted list is reference-counted
// (M0.20, unit_tests/test_matrix_scratchpad.sail).

// *****************************************************************
// The lifecycle.

// **The enumeration is closed and the relation is exactly R-09-032's**, which is
// the strongest-anchored obligation on this file: *no state outside the
// enumeration and no edge outside the relation exists in RTL or Sail* is that
// entry's own criterion, and it names Sail. What is asserted is the whole 5x5
// square rather than the five edges, because an edge the relation should not
// carry is invisible to a check that only walks the ones it should.
$[test]
function test_the_lifecycle_relation_is_exactly_the_five_edges() -> unit = {
  assert(lifecycle_state_count == 5);

  // The index and its inverse agree, which is what the attested devicetree's
  // state name and the OTP window's state index are two renderings of.
  foreach (i from 0 to (lifecycle_state_count - 1)) {
    assert(lifecycle_to_index(lifecycle_of_index(i)) == i);
  };

  // Every admitted pair, against the five R-09-032 names. Raw to test, test to
  // development or to production, development and production to RMA, and RMA
  // terminal.
  foreach (i from 0 to (lifecycle_state_count - 1)) {
    foreach (j from 0 to (lifecycle_state_count - 1)) {
      let from_state = lifecycle_of_index(i);
      let to_state   = lifecycle_of_index(j);
      let named = (i == 0 & j == 1) | (i == 1 & j == 2) | (i == 1 & j == 3)
                | (i == 2 & j == 4) | (i == 3 & j == 4);
      assert(lifecycle_admits(from_state, to_state) == named,
             "the lifecycle relation carries exactly the five edges R-09-032 names");
      // **Acyclic, and by the one argument that needs no traversal**: every
      // edge strictly increases the index, so no sequence of transitions
      // re-enters a state the device has left (R-09-033), which is that entry's
      // stated refinement obligation read as a property of the relation.
      if lifecycle_admits(from_state, to_state) then assert(j > i);
    }
  };
  assert(lifecycle_edge_count() == 5);

  // Development and production are siblings with no edge between them, which is
  // R-09-032's own reading of its own relation and the one a reader is most
  // likely to get wrong.
  assert(not(lifecycle_admits(Lifecycle_Development, Lifecycle_Production)));
  assert(not(lifecycle_admits(Lifecycle_Production, Lifecycle_Development)));

  // RMA is terminal, and it is the only edge out of production (R-09-035).
  foreach (j from 0 to (lifecycle_state_count - 1)) {
    assert(not(lifecycle_admits(Lifecycle_RMA, lifecycle_of_index(j))));
  };
  assert(lifecycle_admits(Lifecycle_Production, Lifecycle_RMA));
}

// **A burn advances along the relation and refuses every other edge**, and there
// is no reverse, reset, vendor-unlock, re-provisioning, or refurbishment path in
// any state (R-09-033). What is asserted beside the walk is that exactly one
// state is readable at any time, which is R-09-032's other half.
$[test]
function test_a_lifecycle_burn_advances_and_never_reverses() -> unit = {
  otp_lifecycle = Lifecycle_Raw;

  // An edge the relation does not carry is refused and leaves the state where
  // it was, so a refused burn is a burn that did not happen rather than one that
  // half happened.
  assert(not(lifecycle_burn(Lifecycle_Development)));
  assert(otp_lifecycle == Lifecycle_Raw);
  assert(not(lifecycle_burn(Lifecycle_Raw)));
  assert(otp_lifecycle == Lifecycle_Raw);

  assert(lifecycle_burn(Lifecycle_Test));
  assert(otp_lifecycle == Lifecycle_Test);

  // Test is the one state with two successors, and taking one closes the other:
  // development and production are siblings, so a part that went to production
  // has no path to development.
  assert(lifecycle_burn(Lifecycle_Production));
  assert(otp_lifecycle == Lifecycle_Production);
  assert(not(lifecycle_burn(Lifecycle_Development)));
  assert(not(lifecycle_burn(Lifecycle_Test)));
  assert(otp_lifecycle == Lifecycle_Production);

  // RMA is forward and terminal, and nothing leaves it.
  assert(lifecycle_burn(Lifecycle_RMA));
  assert(otp_lifecycle == Lifecycle_RMA);
  foreach (j from 0 to (lifecycle_state_count - 1)) {
    assert(not(lifecycle_burn(lifecycle_of_index(j))));
  };
  assert(otp_lifecycle == Lifecycle_RMA);
}

// **R-15-078's gate, and the whole of what this model carries about the Debug
// Module.** *No DM transaction reaches the fabric in the production state* is a
// stated RTL refinement obligation against Sail, so what Sail owes is the
// predicate that obligation quantifies over: the state the fuse holds, read
// where a refinement proof can name it. Nothing here models a debugger, and the
// trigger module is absent rather than gated (R-15-079a).
$[test]
function test_the_debug_module_gate_is_the_production_state() -> unit = {
  foreach (i from 0 to (lifecycle_state_count - 1)) {
    otp_lifecycle = lifecycle_of_index(i);
    assert(debug_module_fabric_gated() == (otp_lifecycle == Lifecycle_Production));
  };
}

// **A fuse burns and never unburns.** A write that sets bits is a burn, a write
// that would clear one is refused rather than masked, and burning a value a word
// already holds changes nothing: that is the whole architectural content of
// one-time programmability, and it is what R-09-033's monotonicity is stated
// over.
$[test]
function test_an_otp_fuse_sets_bits_and_clears_none() -> unit = {
  assert(otp_fuse_words > 0);
  assert(otp_read_fuse(0) == zeros());

  assert(otp_burn_fuse(0, 0x000000000000000f));
  assert(otp_read_fuse(0) == 0x000000000000000f);

  // A superset burns: the bits already set stay set and the new ones join them.
  assert(otp_burn_fuse(0, 0x00000000000000ff));
  assert(otp_read_fuse(0) == 0x00000000000000ff);

  // A subset does not, because it would clear. The refusal is what makes an
  // attempt to unburn visible rather than a store that quietly did nothing.
  assert(not(otp_burn_fuse(0, 0x000000000000000f)));
  assert(not(otp_burn_fuse(0, zeros())));
  assert(otp_read_fuse(0) == 0x00000000000000ff);

  // Idempotent at the value it holds, and every other word is untouched: a burn
  // is a word's and not the bank's.
  assert(otp_burn_fuse(0, 0x00000000000000ff));
  assert(otp_read_fuse(0) == 0x00000000000000ff);
  assert(otp_read_fuse(otp_fuse_words - 1) == zeros());
}

// *****************************************************************
// The entropy root.

// **At least two attributed sources into one conditioner, each separately
// health-tested** (R-15-241e), and **the start-up tests complete before the
// first draw any measured stage can make** (R-09-006a). The second is an
// ordering the model carries rather than a discipline the firmware keeps: a draw
// before the tests is refused, and refused is the only other answer there is.
$[test]
function test_the_root_tests_every_source_before_the_first_draw() -> unit = {
  assert(plat_rot_noise_sources >= 2);
  assert(plat_rot_noise_sources <= rot_max_noise_sources);
  assert(plat_rot_startup_samples > 0);

  // Before the tests: no verdict, and no draw. There is no reduced-rate answer
  // and no last-known-good one, which is what *no degraded path* means at the
  // one place a consumer could ask for one (R-15-241b, R-17-030o).
  assert(not(rot_startup_complete()));
  assert(rot_draw() == None());

  assert(rot_run_startup_tests());
  assert(rot_startup_complete());

  // Every declared source carries its own verdict, and a source the composition
  // did not declare carries none: the tests are per source and the count is the
  // composition's.
  foreach (i from 0 to (rot_max_noise_sources - 1)) {
    assert((rot_source_started[i] == bitone) == (i < plat_rot_noise_sources));
  };

  // And now a draw answers, twice differently: the conditioner advances with
  // every draw rather than latching one word. What it hands out is the
  // conditioner's output and never a source's (R-15-241c) -- there is no
  // accessor here that returns a sample, `rot_source_sample` being private to
  // sys/rot.sail and no window offset answering with one, so that half is an
  // absence in the address map rather than an assertion here.
  match (rot_draw(), rot_draw()) {
    (Some(a), Some(b)) => assert(a != b, "the conditioner advances with each draw"),
    (_, _)             => assert(false, "a healthy root draws"),
  };
}

// **One latched fail-stop and no path out of it** (R-15-241b, R-17-030o). The
// sole failure action is fail-stop: nothing here reduces a rate, falls back to
// the surviving source, or replays a last known good word, and there is no
// function in the model that clears the latch. A failed health test therefore
// stops every operation needing fresh randomness, which is what the seam
// collects.
$[test]
function test_an_entropy_failure_latches_and_has_no_degraded_path() -> unit = {
  assert(rot_run_startup_tests());
  assert(rot_draw() != None());

  rot_entropy_fail_stop = true;

  assert(rot_draw() == None());
  // Re-running the start-up tests is not a way back: a stopped root is not
  // restarted by testing it again, which is the difference between a latch and
  // a status bit.
  assert(not(rot_run_startup_tests()));
  assert(rot_entropy_fail_stop);
  assert(rot_draw() == None());
}

// *****************************************************************
// The monotonic counters.

// **Exactly the four states R-10-013 enumerates, advancing by one and never
// decreasing** (R-12-017), and **counters rather than clocks** (R-09-013): the
// advance takes the counter it names and takes no time, no tick, and no interval,
// so a cold boot with unknown wall-clock time is safe by construction here rather
// than by a rule about here.
$[test]
function test_the_counter_file_is_four_counters_that_only_advance() -> unit = {
  assert(monotonic_counter_count == 4);
  foreach (i from 0 to (monotonic_counter_count - 1)) {
    assert(monotonic_counter_to_index(monotonic_counter_of_index(i)) == i);
    assert(monotonic_read(monotonic_counter_of_index(i)) == zeros());
  };

  // One counter advances by one and the others do not move with it: they are
  // four counters and not one counter read four ways, which is what makes the
  // enumeration's closure a budget over a wearing part (R-10-013d).
  assert(monotonic_advance(Counter_CredentialAttempt));
  assert(monotonic_read(Counter_CredentialAttempt) == 0x0000000000000001);
  assert(monotonic_read(Counter_ImageSecurityVersion) == zeros());
  assert(monotonic_read(Counter_SealingRootVersion) == zeros());
  assert(monotonic_read(Counter_FreshnessEpoch) == zeros());

  assert(monotonic_advance(Counter_CredentialAttempt));
  assert(monotonic_read(Counter_CredentialAttempt) == 0x0000000000000002);

  // Saturation is the end state and not a wrap: a counter that wrapped would
  // present a spent value as fresh, which is the one thing the enumeration
  // exists to prevent.
  monotonic_counters[monotonic_counter_to_index(Counter_FreshnessEpoch)] = ones();
  assert(not(monotonic_advance(Counter_FreshnessEpoch)));
  assert(monotonic_read(Counter_FreshnessEpoch) == ones());
}

// *****************************************************************
// The windowed watchdog.

// **Early pets fault as well as late** (R-15-240), which is the whole of what
// *windowed* means and the half a one-sided watchdog gets wrong: a core stuck in
// a loop petting as fast as it can is exactly as dead as one that has stopped.
// What is asserted is the classification across the whole window, and that a
// bite latches.
$[test]
function test_a_pet_outside_the_window_bites_at_either_end() -> unit = {
  assert(plat_rot_watchdog_early > 0);
  assert(plat_rot_watchdog_late > plat_rot_watchdog_early);
  assert(rot_run_startup_tests());

  // Early: the counter has not reached the near bound.
  watchdog_arm();
  let challenge = watchdog_nonce;
  assert(challenge != zeros());
  watchdog_advance(plat_rot_watchdog_early - 1);
  assert(watchdog_pet(challenge) == Pet_Early);
  assert(watchdog_bitten);

  // A bite is not petted back. R-16-005 makes it the last resort and R-15-198
  // makes it the only signal that asserts the die, so it is a latch and not a
  // report, and nothing in this model clears it.
  assert(watchdog_pet(challenge) == Pet_Bitten);

  // Late: past the far bound. The latch is cleared here by the property rather
  // than by the machine, there being no mechanism that does it, exactly as the
  // sequencer's fail-stop is exercised.
  watchdog_bitten = false;
  watchdog_arm();
  let challenge2 = watchdog_nonce;
  watchdog_advance(plat_rot_watchdog_late + 1);
  assert(watchdog_pet(challenge2) == Pet_Late);
  assert(watchdog_bitten);
}

// **A pet is a challenge-response over a nonce the device issued** (R-15-240),
// so a value that is not the outstanding challenge is a bite and not a refusal:
// there is exactly one capability holder, so a wrong answer is the petter having
// lost the plot rather than a second petter racing the first. An accepted pet
// resets the counter and issues a fresh challenge, which is what stops a
// recorded response from being replayed.
$[test]
function test_a_pet_is_a_challenge_response_and_the_challenge_moves() -> unit = {
  assert(rot_run_startup_tests());
  watchdog_arm();

  let challenge = watchdog_nonce;
  assert(challenge != zeros());
  watchdog_advance(plat_rot_watchdog_early + 1);
  assert(watchdog_pet(challenge) == Pet_Accepted);
  assert(not(watchdog_bitten));
  assert(watchdog_ticks == zeros());

  // The challenge moved, so the response just given is not the response now
  // wanted: replaying it bites.
  let next = watchdog_nonce;
  assert(next != zeros() & next != challenge);
  watchdog_advance(plat_rot_watchdog_early + 1);
  assert(watchdog_pet(challenge) == Pet_Unmatched);
  assert(watchdog_bitten);
}

// **The two fail-closed seams compose, and the composition is a consequence
// rather than a third rule.** The challenge comes from the entropy root
// (R-15-240), so a latched health-test failure leaves no challenge to answer and
// the watchdog bites: R-17-030o's *every operation needing fresh randomness*
// reaching the one operation whose failure is a reset (R-17-030c). It is
// asserted here rather than left to be discovered because the alternative
// reading, that a stopped root leaves the watchdog quietly disarmed, is
// available and is exactly the degraded path R-15-241b refuses.
$[test]
function test_a_stopped_entropy_root_leaves_the_watchdog_no_challenge() -> unit = {
  assert(rot_run_startup_tests());
  watchdog_arm();
  assert(watchdog_nonce != zeros());

  rot_entropy_fail_stop = true;
  watchdog_advance(plat_rot_watchdog_early + 1);
  let challenge = watchdog_nonce;
  assert(watchdog_pet(challenge) == Pet_Accepted);

  // No draw, so no challenge, and the next pet has nothing to answer with.
  assert(watchdog_nonce == zeros());
  watchdog_advance(plat_rot_watchdog_early + 1);
  assert(watchdog_pet(zeros()) == Pet_Unmatched);
  assert(watchdog_bitten);
}

// *****************************************************************
// The four windows.

// **The windows are in the address map of every composition and answer the RoT
// alone** (R-15-194). This is the C-class side, which is the side the harness's
// own configuration composes and the only side a corpus program reaches: the
// window is claimed, so every access to it faults in both directions at every
// width, where an IO address no device claims falls through to the RAM path and
// reads as zero. Claiming the window is what makes the refusal a thing a program
// can run into rather than a silence (sys/mem.sail, M0.16).
// The walk is a recursion rather than a loop body because Sail's `foreach` runs
// over an integer range and the four bases are a list; it is here rather than in
// sys/platform.sail because it is a property's helper and not the machine's.
function each_rot_door_refuses(doors : list(physaddrbits)) -> unit =
  match doors {
    [||]          => (),
    base :: rest  => {
      let addr = Physaddr(base);
      assert(within_mmio_readable(addr, 8), "the window is claimed rather than absent");
      assert(within_mmio_writable(addr, 8));
      match mmio_read(Load(Data), addr, 8) {
        Err(_, _) => (),
        Ok(_)     => assert(false, "an RoT window answers no requester off the RoT class"),
      };
      match mmio_write(addr, 8, zeros()) {
        Err(_, _) => (),
        Ok(_)     => assert(false, "an RoT window answers no requester off the RoT class"),
      };
      // A narrower access is not a way in either: the refusal is the window's
      // rather than one register's, so it does not turn on the width a requester
      // happens to name.
      match mmio_read(Load(Data), addr, 4) {
        Err(_, _) => (),
        Ok(_)     => assert(false, "the refusal does not turn on the access width"),
      };
      each_rot_door_refuses(rest)
    },
  }

$[test]
function test_the_rot_windows_refuse_every_other_class() -> unit = {
  assert(plat_have_otp & plat_have_trng & plat_have_monotonic & plat_have_watchdog);
  assert(not(rot_is_composed_hart()));

  each_rot_door_refuses([|
    plat_otp_base, plat_trng_base, plat_monotonic_base, plat_watchdog_base
  |])
}

// **And the RoT's own side, which needs a roster of its own.** The harness runs
// under the generated max configuration, which composes hart 0 on the C class,
// so a property about what the RoT sees must supply the composition it is about:
// the roster entry for the composed identity is prepended, the doors are read,
// and the head is dropped again. That is M0.8c's *a property about a structure no
// shipped configuration has is a property that must supply it*, and the restore
// drops the head it prepended rather than assigning a binding saved beforehand,
// which is the shape that reads what it is restoring from the register itself
// (M0.20, unit_tests/test_matrix_scratchpad.sail).
$[test]
function test_the_rot_windows_answer_the_rot() -> unit = {
  core_roster = struct {
    hartid = plat_hartid, class = CoreClass_RoT, island = 5,
    pinned = false, fec_units = false
  } :: core_roster;
  assert(rot_is_composed_hart());

  // The lifecycle state is readable, and it is the state and not a fuse word:
  // exactly one state is readable at any time (R-09-032).
  match mmio_read(Load(Data), Physaddr(plat_otp_base + to_bits_truncate(64, ROT_OTP_STATE)), 8) {
    Ok(v) => assert(unsigned(v) == lifecycle_to_index(otp_lifecycle)),
    Err(_, _) => assert(false, "the OTP answers the RoT"),
  };

  // The counter file answers, and the advance door moves exactly the counter it
  // names by exactly one.
  match mmio_write(Physaddr(plat_monotonic_base + to_bits_truncate(64, ROT_CTR_ADVANCE)), 8,
                   to_bits_truncate(64, monotonic_counter_to_index(Counter_ImageSecurityVersion))) {
    Ok(_)     => (),
    Err(_, _) => assert(false, "the advance door answers the RoT"),
  };
  match mmio_read(Load(Data), Physaddr(plat_monotonic_base + to_bits_truncate(64, ROT_CTR_BASE)), 8) {
    Ok(v)     => assert(unsigned(v) == 1),
    Err(_, _) => assert(false, "the counter file answers the RoT"),
  };

  // An offset inside the window that is not a door faults rather than reading as
  // zero, which is what keeps *there is no door that disables this device* a
  // statement about the address map rather than about the decode below it.
  match mmio_read(Load(Data), Physaddr(plat_watchdog_base + to_bits_truncate(64, ROT_WDT_BYTES)), 8) {
    Err(_, _) => (),
    Ok(_)     => assert(false, "an offset that is not a door faults"),
  };

  // A draw before the start-up health tests is refused through the window
  // exactly as it is refused through the function (R-09-006a).
  match mmio_read(Load(Data), Physaddr(plat_trng_base + to_bits_truncate(64, ROT_TRNG_DRAW)), 8) {
    Err(_, _) => (),
    Ok(_)     => assert(false, "a draw before the start-up tests is refused"),
  };

  match core_roster {
    _ :: rest => core_roster = rest,
    [||]      => assert(false, "the installed roster entry must still be there"),
  }
}
