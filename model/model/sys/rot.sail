// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The Root of Trust's four peripherals: the OTP fuse bank that holds the
// lifecycle state (R-09-003, R-09-032), the entropy root (R-15-241), the
// monotonic counter file (R-10-013), and the windowed watchdog (R-15-240).
//
// **No instruction, no access type, no CSR, and nothing on the decode surface.**
// Every one of these is reached by an ordinary load or store through a
// capability, exactly as the CLINT, the interrupt file, the revocation sidecar
// and the refresh sequencer are (sys/platform.sail). `Zkr`'s entropy-source CSR
// is excluded outright (R-15-037), so there is no architectural draw
// instruction and no `seed` register; the lifecycle state is read through a
// window rather than through a CSR because R-09-032 makes it a hardware input
// to the reset path and not a software-writable register; and the counters and
// the watchdog are register slaves because R-15-194 makes them the management
// processor's duties rather than any core's instruction set. That is the same
// claim A-17 is an auditor's search of the decode surface for
// (docs/absence-contract.md).
//
// **These windows are the die's and the RoT's answer to them is the composed
// hart's.** The peripherals sit in the address map of every composition,
// exactly as the refresh sequencer's window does, because the die has one RoT
// whichever of its cores an emulator composes (R-15-194, R-15-113). What varies
// is who may open the door: there is exactly one management processor, so a
// requester on any other class reaching any of these four windows is the same
// fail-stop event a non-ON decode already is (R-15-189h), and the model refuses
// it in both directions at every width. Refusing here rather than leaving the
// window unclaimed is what makes the refusal real: an IO address no device
// claims falls through to the RAM path and reads as zero (sys/mem.sail), which
// is silence and not a refusal, and that contrast is what corpus/platform-rot.s
// runs into from the C class.
//
// **What is here is state and ordering, which is the whole of what a model of
// architectural state can carry of these four.** R-15-078 says it in the one
// place the register names Sail directly for the RoT: *the Sail model carries
// the gate rather than a model of the debugger*. So the lifecycle enumeration
// and its acyclic relation are here (R-09-032 says they exist in RTL **or
// Sail**, which is the strongest-anchored obligation on this file), the
// counter's advance-before-anything ordering is here (R-12-017), the
// health-test-before-first-draw ordering is here (R-09-006a), and the OTP's
// one-way write is here. The conditioner's *function*, the debugger, the
// signature schemes, the sealing hierarchy and the attestation quote are not:
// they are M3.2's firmware and M3.4's primitives, and a model of them here
// would be a model of the harness rather than of the machine, which is where
// cbo.scrub stops at the syndrome and the FEC pass stops at the hard decision
// (extensions/platform/cbo_scrub.sail, extensions/fec/fec_insts.sail).

// *****************************************************************
// The lifecycle (R-09-032, R-09-033).

// Exactly the five states R-09-032 enumerates and no sixth. *No state outside
// the enumeration and no edge outside the relation exists in RTL or Sail* is
// that entry's own criterion, so the enumeration is closed here and the
// relation below is a total function over it rather than a table a composition
// may extend.
enum LifecycleState = {
  Lifecycle_Raw,
  Lifecycle_Test,
  Lifecycle_Development,
  Lifecycle_Production,
  Lifecycle_RMA,
}

mapping lifecycle_state_str : LifecycleState <-> string = {
  Lifecycle_Raw         <-> "raw",
  Lifecycle_Test        <-> "test",
  Lifecycle_Development <-> "development",
  Lifecycle_Production  <-> "production",
  Lifecycle_RMA         <-> "rma",
}
overload to_str = {lifecycle_state_str}

type lifecycle_state_count : Int = 5
let  lifecycle_state_count = sizeof(lifecycle_state_count)
type lifecycle_index = range(0, lifecycle_state_count - 1)

function lifecycle_to_index(s : LifecycleState) -> lifecycle_index =
  match s {
    Lifecycle_Raw         => 0,
    Lifecycle_Test        => 1,
    Lifecycle_Development => 2,
    Lifecycle_Production  => 3,
    Lifecycle_RMA         => 4,
  }

function lifecycle_of_index(i : lifecycle_index) -> LifecycleState =
  match i {
    0 => Lifecycle_Raw,
    1 => Lifecycle_Test,
    2 => Lifecycle_Development,
    3 => Lifecycle_Production,
    _ => Lifecycle_RMA,
  }

// The relation, as a total function refusing every edge it does not carry:
// raw to test, test to development or to production, development and production
// to RMA, and RMA terminal (R-09-032). Development and production are siblings
// with no edge between them, which is that entry's own reading of its own
// relation and the one a reader is most likely to get wrong.
//
// **It is a function of the pair and of nothing else**, which is what makes
// R-09-033's *no sequence of transitions re-enters a state the device has left*
// a property somebody can state over it: the relation is acyclic because the
// index strictly increases across every edge it carries, and a state's
// successors are therefore all above it. Nothing here reads a fuse, an
// authorization, a credential, or a signature, because none of those decides
// which edges exist; they decide whether a burn is attempted, which is the
// firmware's question (R-09-035, R-15-079, M3.2).
function lifecycle_admits(from_state : LifecycleState, to_state : LifecycleState) -> bool =
  match (from_state, to_state) {
    (Lifecycle_Raw,         Lifecycle_Test)        => true,
    (Lifecycle_Test,        Lifecycle_Development) => true,
    (Lifecycle_Test,        Lifecycle_Production)  => true,
    (Lifecycle_Development, Lifecycle_RMA)         => true,
    (Lifecycle_Production,  Lifecycle_RMA)         => true,
    (_, _)                                         => false,
  }

// The relation's arity, counted over the relation rather than declared beside
// it. The attested devicetree carries it (postlude/device_tree.sail) and a
// number written there by hand would be R-09-032's relation stated twice, which
// is what the core-class nodes leave the roster's own count out for.
function lifecycle_edge_count() -> nat = {
  var edges : nat = 0;
  foreach (i from 0 to (lifecycle_state_count - 1)) {
    foreach (j from 0 to (lifecycle_state_count - 1)) {
      if lifecycle_admits(lifecycle_of_index(i), lifecycle_of_index(j)) then edges = edges + 1
    }
  };
  edges
}

// The state a composition resets into. It is a composition constant rather than
// a value the model chooses: a part on a bench is in *development* and a part in
// the field is in *production*, and both are compositions of this one machine.
// The validator asserts nothing about which, because all five are states a real
// part is in, and a refusal here would be the model deciding what a part's
// history was.
let plat_rot_lifecycle_reset : LifecycleState = config platform.otp.lifecycle_state

// The live state. R-09-032 makes it *readable* and not software-writable, so
// nothing below assigns it except the burn, which advances along the relation.
register otp_lifecycle : LifecycleState = plat_rot_lifecycle_reset

// **The one difference between this and the fuse it models is stated rather than
// elided.** R-09-032 makes the state a hardware input to the *reset path*, so on
// a real part a burn takes effect at the next reset and the state read during a
// run never changes under the software reading it. This model has no reset path
// to re-enter, its whole run being one power-on, so the burn takes effect where
// it is issued. What the model gets right is the relation, the monotonicity and
// the one-way fuse write; what a machine adds is where the latch is, and that
// is an RTL obligation (R-09-033's own criterion states it as one) rather than
// something a model of architectural state can exhibit.
function lifecycle_burn(to_state : LifecycleState) -> bool =
  if not(lifecycle_admits(otp_lifecycle, to_state)) then false
  else { otp_lifecycle = to_state; true }

// R-15-078's gate, and the whole of what this model carries about the Debug
// Module. *No DM transaction reaches the fabric in the production state* is a
// stated RTL refinement obligation against Sail, so what Sail owes is the
// predicate that obligation quantifies over and not a debugger: in production
// the RoT's OTP fuse holds the DM's clock and reset gated off and its fabric
// port electrically quiesced, and this is where a refinement proof reads which
// state that is. The trigger module is not gated here and is not here at all:
// R-15-079a deletes it in every lifecycle state, so it is absent rather than
// fused (core/extensions.sail carries no trigger row and no CSR bank carries a
// `tselect`).
function debug_module_fabric_gated() -> bool = otp_lifecycle == Lifecycle_Production

// The fuse bank the lifecycle is one entry of, and the provisioning state the
// rest of it is. **The width is the model's bound and not the architecture's**,
// the way the revocation plane's is (core/revocation.sail): a Sail register is a
// fixed width, so the model fixes one and the validator refuses a window too
// narrow to address it rather than letting the top words fall silently outside
// the map.
//
// **No key material is here, and that absence is the point.** R-09-003 puts
// keys, the lifecycle state and the anti-rollback counters in on-die OTP, and of
// the three only the second and third have architectural content: a readable key
// door in the address map is exactly the structure R-12-014 and R-10-032 refuse
// when they keep every key inside the crypto core and hand a compartment sealed
// blobs and capability handles. So the fuse bank carries provisioning state, the
// key region is absent from this window entirely, and a search of this file for
// a key finds this paragraph.
type otp_fuse_words : Int = 16
let  otp_fuse_words = sizeof(otp_fuse_words)
type otp_fuse_bits_len : Int = otp_fuse_words * 64
let  otp_fuse_bits_len = sizeof(otp_fuse_bits_len)

register otp_fuses : bits(otp_fuse_bits_len) = zeros()

function otp_read_fuse(w : range(0, otp_fuse_words - 1)) -> bits(64) = {
  var out : bits(64) = zeros();
  foreach (b from 0 to 63) {
    out = [out with b = otp_fuses[w * 64 + b]]
  };
  out
}

// **A fuse burns and never unburns, which is the whole architectural content of
// one-time programmability.** A burn sets bits and clears none, so a write whose
// value would clear a bit already set is refused rather than silently masked:
// masking would make an attempt to unburn indistinguishable from a burn that
// changed nothing, and R-09-033's monotonicity is stated over the fuse state.
function otp_burn_fuse(w : range(0, otp_fuse_words - 1), v : bits(64)) -> bool = {
  let held = otp_read_fuse(w);
  if (held & ~(v)) != zeros() then false
  else {
    foreach (b from 0 to 63) {
      otp_fuses = [otp_fuses with (w * 64 + b) = (held[b] | v[b])]
    };
    true
  }
}

// *****************************************************************
// The entropy root (R-15-241, R-15-241a through R-15-241e, R-15-037).

// **Two noise sources into one conditioner, each separately health-tested, and
// no sample reaching the conditioner unattributed** (R-15-241e). The count is a
// composition constant with a floor rather than a value: the requirement says
// *multiple independent noise sources spanning at least two physical
// mechanisms*, which is a floor, and the model refuses a declaration below it
// and carries no opinion above it. Which two mechanisms they are is a silicon
// fact with no architectural content, exactly as the memory classes' media are
// (core/memory_class.sail): what reaches this model is that there are at least
// two of them, that each is tested on its own, and that every sample carries
// which one it came from.
type rot_max_noise_sources : Int = 4
let  rot_max_noise_sources = sizeof(rot_max_noise_sources)

let plat_rot_noise_sources : range(0, rot_max_noise_sources) = config platform.trng.noise_sources

// **The emulated source is a configuration-seeded generator, and this is where
// the deterministic-replay obligation is stated rather than met.** §2 of the
// implementation plan calls for the TRNG *as a seeded PRNG in emulation*, and
// that is what this is. R-15-241 requires every draw to be accounted for in the
// deterministic-replay nondeterminism record, R-16-015 puts every draw from the
// single entropy root in that record's secret class, and R-16-017 requires a
// secret draw be recorded as a sealed commitment and **never as a value**.
//
// A seed in a configuration file does not discharge that obligation, it evades
// it: it replaces the nondeterminism with determinism instead of recording it,
// and the artifact it puts the draw in is a tracked file rather than a sealed
// commitment. So three things are true of this seed and all three are stated
// here rather than left to be inferred. It is an **emulation fact and not an
// architectural one**, so it is not emitted into the attested devicetree
// (postlude/device_tree.sail) and no property asserts a drawn value. Nothing in
// this model is a nondeterminism record: a search of model/model for one returns
// this paragraph and nothing else. And what would discharge the obligation is
// the sealing primitive M3.4 supplies and the record M3.2's firmware writes,
// neither of which exists, so the obligation is live and owed elsewhere rather
// than met here.
let plat_rot_trng_seed : bits(64) = to_bits_truncate(64, config platform.trng.seed : int)

// The start-up sample budget R-15-241b fixes and does not state. Its owner is
// the source's stochastic model, an artifact this repository does not hold and
// no milestone yet authors, so the model carries the shape and refuses a
// budget of zero, a health test over no samples being a test that cannot fail.
let plat_rot_startup_samples : range(0, 65535) = config platform.trng.startup_samples

// One generator per source, advanced by a single multiplicative step. The
// constant is Knuth's MMIX multiplier, chosen because it is a published constant
// with a full period rather than because anything here depends on its
// distribution: **nothing in this model is a claim about entropy**. R-15-241c's
// conditioner is a vetted non-keyed cryptographic function whose output is
// full-entropy at a claimed rate, and this is a stand-in for it in exactly the
// sense the FEC pass's hard decision is a stand-in for belief propagation: what
// the model carries is which values reach which consumer, and replacing the
// arithmetic changes the value the door returns and nothing else about the
// machine.
register rot_source_state : vector(rot_max_noise_sources, bits(64)) = vector_init(zeros())

// Every sample carries the index of the source it came from, which is
// R-15-241e's *no source reaching the conditioner unattributed* made a type
// rather than a convention: the conditioner below takes this and cannot be
// handed a bare word.
struct NoiseSample = {
  source : range(0, rot_max_noise_sources - 1),
  bits64 : bits(64),
}

// Per-source health state. **Each source is separately health-tested**
// (R-15-241e), so the verdict is per source; the *failure action* is not, which
// is R-15-241b's single latched fail-stop with no degraded path. A source that
// fails does not leave the other one running at a reduced rate, because a
// reduced rate is exactly the degraded path R-17-030o refuses.
register rot_source_started : bits(rot_max_noise_sources) = zeros()
register rot_source_last : vector(rot_max_noise_sources, bits(64)) = vector_init(zeros())

// The one latch. R-15-241b makes fail-stop the sole failure action and
// R-17-030o collects it, so this is architectural state rather than a
// diagnostic: what it records is that the root stopped, and every operation
// needing fresh randomness stops with it.
register rot_entropy_fail_stop : bool = false

// Whether the start-up tests have completed for every declared source. R-09-006a
// requires them to complete *before the first draw any measured stage can make*,
// so this is the precondition the draw below reads, and the ordering is
// architectural rather than a convention of the firmware.
function rot_startup_complete() -> bool = {
  var done : bool = plat_rot_noise_sources > 0;
  foreach (i from 0 to (rot_max_noise_sources - 1)) {
    if i < plat_rot_noise_sources & rot_source_started[i] != bitone then done = false
  };
  done
}

// The mixing step, four xor-shift rounds. Every round is a bijection on 64 bits
// and so is their composition, which is the one property anything here relies
// on: two different inputs give two different outputs, so a source that is
// stepping produces samples that differ and the continuous test below is a test
// of the source rather than of the arithmetic.
private function rot_mix(v : bits(64)) -> bits(64) = {
  var x = v;
  x = x ^ (x >> 33);
  x = x ^ (x << 21);
  x = x ^ (x >> 17);
  x = x ^ (x << 31);
  x
}

// A source's own salt. **Which physical mechanism a source is has no
// architectural content**, exactly as which medium a latency class is has none
// (core/memory_class.sail): what reaches this model is that the sources are
// separate, that each carries its own verdict, and that every sample says which
// one it came from. So the sources are told apart here by a salt and not by a
// second stand-in arithmetic pretending to be a second mechanism, which would be
// a claim about a distribution this file makes nowhere.
private function rot_source_salt(i : range(0, rot_max_noise_sources - 1)) -> bits(64) =
  plat_rot_trng_seed + to_bits_truncate(64, i + 1)

private function rot_source_step(i : range(0, rot_max_noise_sources - 1)) -> bits(64) = {
  let next = rot_source_state[i] + 0x0000000000000001;
  rot_source_state[i] = next;
  rot_mix(next ^ rot_source_salt(i))
}

// The continuous on-line test R-15-241b requires beside the start-up one. It is
// a stuck-source test and nothing more: two consecutive samples equal is the one
// failure a model with no stochastic content can detect at all, and it is the
// failure R-15-241e names first (*death, sticking, or narrowed distribution*).
// The third of those three is invisible from here and is booked where it
// belongs, in R-17-049a's subversion residual, rather than claimed here.
private function rot_source_sample(i : range(0, rot_max_noise_sources - 1)) -> NoiseSample = {
  let v = rot_source_step(i);
  if v == rot_source_last[i] then rot_entropy_fail_stop = true;
  rot_source_last[i] = v;
  struct { source = i, bits64 = v }
}

// The start-up health tests, over the fixed sample budget, per source
// (R-15-241b, R-15-241e). They are a door rather than a reset action because
// R-09-006a makes their completion an event the measured chain orders against:
// *the verdict is measured into the chain*, so the RoT firmware runs them and
// the chain records that it did (M3.2). What the model owes is that a draw
// before them is refused, which is the clause in `rot_draw` below.
function rot_run_startup_tests() -> bool = {
  if rot_entropy_fail_stop then return false;
  if plat_rot_noise_sources == 0 then return false;

  foreach (i from 0 to (rot_max_noise_sources - 1)) {
    if i < plat_rot_noise_sources then {
      // The counter starts at zero and the first sample is taken at one, so the
      // continuous test's *previous* sample is the one this source would have
      // produced at zero. That is a real sample of this source rather than a
      // sentinel value chosen to differ, which is what keeps the first
      // comparison a comparison.
      rot_source_state[i] = zeros();
      rot_source_last[i] = rot_mix(rot_source_salt(i));
      foreach (_s from 1 to plat_rot_startup_samples) {
        let _ = rot_source_sample(i)
      };
      if not(rot_entropy_fail_stop) then rot_source_started = [rot_source_started with i = bitone]
    }
  };
  not(rot_entropy_fail_stop)
}

// The one conditioner (R-15-241c, R-15-241e). Every declared source is sampled
// once and every sample is absorbed under its own attribution; a sample whose
// index is not one of the declared sources is not absorbed at all, which is what
// makes *no source reaching the conditioner unattributed* a mechanism rather
// than a promise.
private function rot_condition(acc : bits(64), s : NoiseSample) -> bits(64) =
  if s.source >= plat_rot_noise_sources then acc
  else rot_mix(acc ^ s.bits64 ^ to_bits_truncate(64, s.source + 1))

// A draw. **The output is the conditioner's and never a source's**, which is
// R-15-241c's *raw source output reaches no consumer*: there is no offset in the
// window that returns a sample, no accessor here that returns one, and
// `rot_source_sample` is private to this file. What a consumer holds on a real
// part is the DRBG in the crypto core, which this die's model does not carry
// (R-15-241, R-15-241d), so what this door hands out is conditioned root output
// at the one place R-15-241d says the DRBG is instantiated from.
//
// Three refusals, and each is a requirement rather than a convenience: a draw
// before the start-up tests complete (R-09-006a), a draw after the fail-stop has
// latched (R-15-241b), and a draw on a composition declaring no source at all.
// None of the three has a degraded answer: the draw does not happen.
function rot_draw() -> option(bits(64)) = {
  if rot_entropy_fail_stop then return None();
  if not(rot_startup_complete()) then return None();

  var acc : bits(64) = 0x6a09e667f3bcc908;
  foreach (i from 0 to (rot_max_noise_sources - 1)) {
    if i < plat_rot_noise_sources then acc = rot_condition(acc, rot_source_sample(i))
  };
  if rot_entropy_fail_stop then None() else Some(acc)
}

// *****************************************************************
// The monotonic counters (R-10-013, R-09-013, R-09-028, R-12-017).

// **Exactly the four states R-10-013's closed enumeration names and no fifth.**
// The enumeration is closed by conferral rather than by amendment (R-10-013a):
// four requirements confer membership, R-10-013 collects them, and a fifth
// member is not admitted until that sentence is reopened. So this is a five-way
// match with four arms and no default, and a state that later needs freshness
// arrives here as an amendment rather than as a row somebody adds.
enum MonotonicCounter = {
  Counter_ImageSecurityVersion,  // the base-image security-version floor (R-09-028)
  Counter_SealingRootVersion,    // the key-wrapping and sealing-root version (R-09-023)
  Counter_CredentialAttempt,     // the credential attempt-counter version (R-12-017)
  Counter_FreshnessEpoch,        // the durable-state freshness-epoch root (R-10-013c)
}

mapping monotonic_counter_str : MonotonicCounter <-> string = {
  Counter_ImageSecurityVersion <-> "image-security-version",
  Counter_SealingRootVersion   <-> "sealing-root-version",
  Counter_CredentialAttempt    <-> "credential-attempt",
  Counter_FreshnessEpoch       <-> "freshness-epoch",
}
overload to_str = {monotonic_counter_str}

type monotonic_counter_count : Int = 4
let  monotonic_counter_count = sizeof(monotonic_counter_count)
type monotonic_counter_index = range(0, monotonic_counter_count - 1)

function monotonic_counter_to_index(c : MonotonicCounter) -> monotonic_counter_index =
  match c {
    Counter_ImageSecurityVersion => 0,
    Counter_SealingRootVersion   => 1,
    Counter_CredentialAttempt    => 2,
    Counter_FreshnessEpoch       => 3,
  }

function monotonic_counter_of_index(i : monotonic_counter_index) -> MonotonicCounter =
  match i {
    0 => Counter_ImageSecurityVersion,
    1 => Counter_SealingRootVersion,
    2 => Counter_CredentialAttempt,
    _ => Counter_FreshnessEpoch,
  }

// **Counters and not clocks** (R-09-013). Nothing here reads `mtime`, a tick, a
// wall-clock value, or an elapsed interval, which is a property a reader checks
// by looking at what these functions take, the way the refresh sequencer's
// independence of every runtime measure is checked by looking at what its
// functions take (sys/memory_sequencer.sail, R-15-247r). A cold boot with
// unknown wall-clock time is therefore safe by construction here rather than by
// a rule about here.
register monotonic_counters : vector(monotonic_counter_count, bits(64)) = vector_init(zeros())

// The one write. It advances by exactly one and there is no door that sets a
// value, decrements, resets, or reloads: *nothing rolls it back* is R-12-017's
// own sentence and it is a property of the mechanism rather than of the
// firmware's discipline. Saturation is the model's honest end state: a counter
// that wrapped would present a spent value as fresh, which is the one thing the
// enumeration exists to prevent, and a real part's rated endurance is exhausted
// long before 2^64 (R-10-013d).
function monotonic_advance(c : MonotonicCounter) -> bool = {
  let i = monotonic_counter_to_index(c);
  let held = monotonic_counters[i];
  if held == ones() then false
  else { monotonic_counters[i] = held + 1; true }
}

function monotonic_read(c : MonotonicCounter) -> bits(64) =
  monotonic_counters[monotonic_counter_to_index(c)]

// *****************************************************************
// The windowed watchdog (R-15-240, R-15-194, R-16-005).

// **It is non-deletable, and in a model of architectural state that is an
// absence rather than a mechanism.** There is no disable door at any offset of
// the window, no enable bit, no mask, no configuration key that turns it off
// once a composition declares it, and no path anywhere in this file that clears
// the latch below. A reader looking for the structure that would delete it finds
// this paragraph, which is what A-17 is for the decode surface read over an
// address map.
//
// **The counter is in the watchdog's own slow-clock ticks and this model carries
// no ratio to the spine.** A `slow_clock_divisor` beside the bounds is the
// natural wrong move: R-15-196 makes the RoT's independent slow clock one of
// exactly three genuinely asynchronous boundaries, *none modeled as
// fixed-latency*, with every theorem touching the RoT path using one-sided
// bounds only, so a declared ratio between the spine and this counter would be
// exactly the fixed-latency model that entry refuses. The bounds are therefore
// stated in this counter's ticks, and crossing them into a schedule is §11's
// (R-11-007, R-11-017).
//
// **The bounds are the composition's and this model asserts no value**, for the
// reason the sequencer's cadence is the composition's: R-11-017 emits the
// operating-point assignment, the TDM NoC schedule and the watchdog windows as
// one artifact and that artifact is itself a crown-jewel specification, so a
// value written here ahead of it would be a placeholder becoming an
// architectural input. What the validator holds is that a window is a window.
let plat_rot_watchdog_early : range(0, 4294967295) = config platform.watchdog.early_ticks
let plat_rot_watchdog_late  : range(0, 4294967295) = config platform.watchdog.late_ticks

// Ticks since the last accepted pet, the outstanding challenge, and the bite.
register watchdog_ticks : bits(64) = zeros()
register watchdog_nonce : bits(64) = zeros()
register watchdog_bitten : bool = false

// The advance, and **nothing in this model calls it**, which is the position
// `memory_sequencer_discharge_phase` already holds: the slow clock is a failure
// domain disjoint from the cores, the main clock tree and the scheduler
// (R-15-240), so advancing it from this model's own instruction tick would make
// the timeout a function of instruction retirement, which is precisely the
// coupling an independent clock exists to remove. What walks it is the RoT
// firmware's own schedule (M3.2), exactly as the RoT's sequence table walks the
// sequencer's phases (R-15-198).
function watchdog_advance(ticks : int) -> unit =
  if ticks <= 0 | watchdog_bitten then ()
  else watchdog_ticks = watchdog_ticks + to_bits_truncate(64, ticks)

// The bite. R-16-005 makes it the last resort and equal to a reset, and R-15-198
// makes it the only signal that asserts the die, so it is a latch and not a
// report: a bitten watchdog is not petted back to life from inside the machine.
private function watchdog_bite() -> unit = {
  watchdog_bitten = true;
  watchdog_nonce = zeros();
}

// The challenge. **A pet is a challenge-response over a nonce the device
// issued** (R-15-240), so the nonce comes from the entropy root and not from a
// counter: a predictable challenge is a pet a wedged core can compute ahead of
// time, which is the one thing a challenge-response buys over a magic write.
//
// That makes the two fail-closed seams compose, and the composition is stated
// rather than discovered: if the root has latched, no nonce is issued, the
// outstanding challenge is zero, and a pet of zero is refused below, so an
// entropy failure ends in a bite. That is R-17-030o's *every operation needing
// fresh randomness* reaching the one operation whose failure is a reset, and it
// is a consequence of the two entries rather than a third rule.
private function watchdog_issue_nonce() -> unit =
  match rot_draw() {
    None()    => watchdog_nonce = zeros(),
    Some(n)   => watchdog_nonce = if n == zeros() then ones() else n,
  }

// The pet, classified against the window. **Early pets fault as well as late**
// (R-15-240), which is the whole of what *windowed* means and the half a
// one-sided watchdog gets wrong: a core stuck in a loop that pets as fast as it
// can is exactly as dead as one that has stopped, and only the early bound
// catches it.
enum WatchdogPetOutcome = {
  Pet_Accepted,   // inside the window, with the outstanding nonce
  Pet_Early,      // before the early bound: the bite latches
  Pet_Late,       // after the late bound: the bite latches
  Pet_Unmatched,  // not the challenge this device issued: the bite latches
  Pet_Bitten,     // already latched; a bite is not petted back
}

mapping watchdog_pet_outcome_str : WatchdogPetOutcome <-> string = {
  Pet_Accepted  <-> "accepted",
  Pet_Early     <-> "early",
  Pet_Late      <-> "late",
  Pet_Unmatched <-> "unmatched",
  Pet_Bitten    <-> "bitten",
}
overload to_str = {watchdog_pet_outcome_str}

function watchdog_pet(response : bits(64)) -> WatchdogPetOutcome = {
  if watchdog_bitten then return Pet_Bitten;

  // The response is checked before the window, so a wrong answer inside the
  // window is a bite rather than an accepted pet with a note. There is exactly
  // one capability holder (R-15-240), so a response that does not match is not
  // a second petter racing the first; it is the petter having lost the plot.
  if response == zeros() | response != watchdog_nonce then {
    watchdog_bite();
    return Pet_Unmatched;
  };

  let ticks = unsigned(watchdog_ticks);
  if ticks < plat_rot_watchdog_early then { watchdog_bite(); Pet_Early }
  else if ticks > plat_rot_watchdog_late then { watchdog_bite(); Pet_Late }
  else {
    watchdog_ticks = zeros();
    watchdog_issue_nonce();
    Pet_Accepted
  }
}

// The device's own arming, which is the RoT firmware's first act on it and not
// something a requester reaches: the window opens with a challenge outstanding
// and the counter at zero.
function watchdog_arm() -> unit =
  if watchdog_bitten then ()
  else { watchdog_ticks = zeros(); watchdog_issue_nonce() }

// *****************************************************************
// The four windows' layout.

// The doors, at doubleword offsets, and the extent each set of doors needs. They
// are here beside the semantics rather than in the decode that reads them
// (sys/platform.sail), because the validator refuses a declared window too
// narrow to address them (postlude/validate_config.sail) and a layout stated in
// one file and sized in another is one fact written twice.
//
// **Every door is a doubleword.** A narrower access would name a sub-word of a
// counter, a nonce, or a fuse, which is the reason the revocation slave takes
// doublewords only: the unit of each of these structures is the word, and half
// a monotonic counter is not a value.
let ROT_OTP_STATE       : int = 0    // read: the lifecycle state's index
let ROT_OTP_BURN        : int = 8    // write: the target state's index
let ROT_OTP_DM_GATE     : int = 16   // read: 1 where no DM transaction reaches the fabric
let ROT_OTP_FUSE_COUNT  : int = 24   // read: the fuse bank's width in words
let ROT_OTP_FUSE_BASE   : int = 256  // read/write: the fuse bank, one word per door
let ROT_OTP_BYTES       : int = ROT_OTP_FUSE_BASE + 8 * otp_fuse_words

let ROT_TRNG_DRAW       : int = 0    // read: one conditioned word
let ROT_TRNG_HEALTH     : int = 8    // read: the per-source verdicts and the latch
let ROT_TRNG_SOURCES    : int = 16   // read: the declared noise source count
let ROT_TRNG_BUDGET     : int = 24   // read: the start-up sample budget
let ROT_TRNG_STARTUP    : int = 32   // write: run the start-up health tests
let ROT_TRNG_BYTES      : int = 40

let ROT_CTR_BASE        : int = 0    // read: the four counters, one word per door
let ROT_CTR_ADVANCE     : int = 32   // write: advance the counter this index names
let ROT_CTR_COUNT       : int = 40   // read: the enumeration's size
let ROT_CTR_BYTES       : int = 48

let ROT_WDT_NONCE       : int = 0    // read: the outstanding challenge
let ROT_WDT_TICKS       : int = 8    // read: slow-clock ticks since the last pet
let ROT_WDT_PET         : int = 16   // write: the response
let ROT_WDT_BITTEN      : int = 24   // read: the latch
let ROT_WDT_EARLY       : int = 32   // read: the early bound
let ROT_WDT_LATE        : int = 40   // read: the late bound
let ROT_WDT_ARM         : int = 48   // write: open the window with a fresh challenge
let ROT_WDT_BYTES       : int = 56

// **There is no offset in any of the four that disables anything.** The watchdog
// has no door that stops it (R-15-240's non-deletable), the entropy root has no
// door that clears its latch or reduces its rate (R-15-241b's no degraded path),
// the counters have no door that writes a value or decrements (R-12-017's
// nothing rolls it back), and the OTP has no door that unburns a fuse or reverses
// a lifecycle edge (R-09-033). Each of those is an absence rather than a
// mechanism, so a reader auditing this device set reads this list and then reads
// the decode in sys/platform.sail, which claims exactly these offsets and faults
// on every other one.

// *****************************************************************
// Who the four windows answer.

// **There is exactly one management processor** (R-15-194), so these four
// windows answer the RoT and refuse every other class. It is derived from the
// composed hart's roster entry rather than declared as a fifth configuration
// key, because the roster already says which core this run is and a second
// declaration of the same fact is the defect this repository is built to catch
// (R-15-052b, core/core_class.sail).
function rot_is_composed_hart() -> bool =
  match this_core_class() {
    Some(CoreClass_RoT) => true,
    _                   => false,
  }
