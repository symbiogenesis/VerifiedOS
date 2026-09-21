// The `mstatus` SXL/UXL reset test this file used to hold went with the
// fields: those are the effective XLEN of supervisor and user mode, and
// there is one mode (R-15-003). What replaces it is the property that
// deletion establishes and a later edit could silently regress.

// `misa` must advertise neither supervisor nor user mode after reset.
$[test]
function test_misa_has_no_privileged_modes() -> unit = {
  reset_misa();
  assert(misa[S] == 0b0);
  assert(misa[U] == 0b0);
}

// A trap leaves the hart with interrupts disabled and the previous
// enable saved, and that is now the whole of the privilege transition.
$[test]
function test_trap_saves_only_the_interrupt_enable() -> unit = {
  reset_trap_protocol();
  reset_tvec();
  mstatus[MIE] = 0b1;
  mstatus[MPIE] = 0b0;
  let _ = trap_handler(Exception(E_M_EnvCall()), zeros(), None(), None());
  assert(mstatus[MIE] == 0b0);
  assert(mstatus[MPIE] == 0b1);
  assert(trap_path_live);
  reset_trap_protocol();
}

// Every retained enable-bit combination delivers the boundary timer. The
// pending bit is read-only to software and is not an ordinary maskable IRQ.
$[test]
function test_boundary_timer_ignores_enable_bits() -> unit = {
  reset_trap_protocol();
  foreach (global_bit from 0 to 1) {
    foreach (local_bit from 0 to 1) {
      mstatus[MIE] = to_bits(1, global_bit);
      let mask : xlenbits = if local_bit == 0 then zeros() else ones();
      let _ = write_CSR(0x304, mask);
      assert(read_CSR(0x304) == 0x0000000000000080);
      mip[MTI] = 0b1;
      assert(shouldWakeForInterrupt());
      match dispatchInterrupt() {
        Some(I_M_Timer) => (),
        _ => assert(false, "a writable enable masked the boundary"),
      };
    };
  };
  reset_trap_protocol();
  assert(dispatchInterrupt() == None());
}

// A comparison latches one event. Servicing it cannot immediately create a
// second event from the same expired comparison; mtimecmp must be reprogrammed.
$[test]
function test_boundary_timer_is_latched_and_not_level_retriggered() -> unit = {
  reset_trap_protocol();
  PCC = default_cap;
  MTCC = default_cap;
  reset_tvec();
  mtimecmp = 0x0000000000000064;
  mtime = 0x0000000000000063;
  boundary_timer_armed = true;
  clint_dispatch();
  assert(mip[MTI] == 0b0);
  mtime = 0x0000000000000064;
  clint_dispatch();
  assert(mip[MTI] == 0b1 & not(boundary_timer_armed));
  let _ = trap_handler(Interrupt(I_M_Timer), zeros(), None(), None());
  assert(trap_path_live & mip[MTI] == 0b0);
  mtime = 0x0000000000000065;
  clint_dispatch();
  assert(mip[MTI] == 0b0);
  reset_trap_protocol();
}

// A pending timer survives the full synchronous path, including an mtimecmp
// update. MRET releases it before the next predecessor instruction can issue.
$[test]
function test_pending_timer_waits_for_mret_without_nesting() -> unit = {
  reset_trap_protocol();
  PCC = default_cap;
  MTCC = default_cap;
  reset_tvec();
  let _ = trap_handler(Exception(E_M_EnvCall()), 0x0000000000001000, None(), None());
  let saved = MEPCC;
  let cause = mcause;
  let value = mtval;
  mip[MTI] = 0b1;
  mtime = 0x000000000000000a;
  mtimecmp = 0x0000000000000014;
  boundary_timer_armed = true;
  clint_dispatch();
  assert(mip[MTI] == 0b1 & dispatchInterrupt() == None());
  let held = trap_handler(Interrupt(I_M_Timer), 0x0000000000002000, None(), None());
  assert(held == 0x0000000000002000 & not(trap_fail_stop));
  assert(MEPCC == saved & mcause == cause & mtval == value);
  match execute(MRET()) {
    Retire_Success() => (),
    _ => assert(false, "admitted mret must retire"),
  };
  assert(not(trap_path_live) & not(trap_fail_stop));
  assert(dispatchInterrupt() == Some(I_M_Timer));
  assert(MEPCC == saved);
  reset_trap_protocol();
}

// A second synchronous trap is a fail-stop, without a second saved-PC bank
// or replacement of the first cause/value/vector. The failure stays latched.
$[test]
function test_second_trap_preserves_the_first_context_and_stops() -> unit = {
  reset_trap_protocol();
  PCC = default_cap;
  MTCC = default_cap;
  reset_tvec();
  let _ = trap_handler(Exception(E_M_EnvCall()), 0x0000000000001000, Some(0x0000000000001111), None());
  let saved = MEPCC;
  let cause = mcause;
  let value = mtval;
  let vector = nextPCC;
  let status = mstatus;
  let refused = trap_handler(Exception(E_Illegal_Instr()), 0x0000000000002000, Some(0x0000000000002222), None());
  assert(refused == 0x0000000000002000 & trap_path_live & trap_fail_stop);
  assert(MEPCC == saved & mcause == cause & mtval == value);
  assert(nextPCC == vector & mstatus == status);
  let _ = trap_handler(Exception(E_Breakpoint()), 0x0000000000003000, Some(0x0000000000003333), None());
  assert(trap_fail_stop & MEPCC == saved & mcause == cause & mtval == value);
  mip[MTI] = 0b1;
  assert(dispatchInterrupt() == None() & not(shouldWakeForInterrupt()));
  let stopped_pc = PC;
  let stopped_next = nextPC;
  let stopped_pcc = PCC;
  let register_value = x15;
  let old_bite = watchdog_bitten;
  let old_nonce = watchdog_nonce;
  watchdog_bitten = false;
  watchdog_nonce = 0x1234567812345678;
  foreach (attempt from 0 to 2) {
    assert(try_step(attempt, true));
    assert(PC == stopped_pc & nextPC == stopped_next & PCC == stopped_pcc);
    assert(nextPCC == vector & MEPCC == saved & mcause == cause & mtval == value);
    assert(x15 == register_value);
    assert(watchdog_bitten & watchdog_nonce == zeros());
  };
  reset_trap_protocol();
  assert(not(trap_path_live) & not(trap_fail_stop) & watchdog_bitten);
  // The test harness restores its enclosing RoT fixture, not a software path.
  watchdog_bitten = old_bite;
  watchdog_nonce = old_nonce;
}
