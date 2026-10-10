# Environmental fault sensors and characterization contract

This is Q41's specification and characterization plan for
[R-16-008g](../spec.md#r-16-008g). It defines the sensor inventory,
immutable qualification fields, trip boundary and evidence owed at integration.
It supplies no analog design, RTL, measured threshold, spatial coverage result or
detection probability. The highest fault-coverage mode it permits is **detected**.
The [requirements register](../requirements-register.md) owns the obligations;
this document gives their hardware and characterization owners acceptance cases.

The power/reset sequence table and the clock-spine topology remain their owners'
outputs under [R-15-198](../spec.md#r-15-198) and
[R-15-195](../spec.md#r-15-195). The RoT's independent slow clock is included under
[R-15-196](../spec.md#r-15-196). A core roster or an island number is insufficient
to identify a physical rail, clock leaf or detector site. This contract therefore
maps every member of the emitted topology, without transcribing a roster or
inventing physical domain names. Missing concrete inputs refuse integration;
they are not an empty inventory that passes.

## 1. Selected families and the upstream reading

The following are family selections for process-specific implementation, not
selections of commercial parts or permission to incorporate their circuits.
Published results identify mechanisms; their electrical values, geometry,
coverage and rates do not become VerifiedOS values.

| Guard | Selected family | Primary source and limit of the reading |
| --- | --- | --- |
| Supply level | Local under/over-voltage window detector, with independent reference and loss-of-power response | [TI's TPS3700 datasheet, revision G](https://www.ti.com/lit/ds/symlink/tps3700.pdf), sections 7.3 and 7.4, describes window comparison, hysteresis, pulse sensitivity and behavior as the detector loses supply. It is a reference for the family and its blind spots, not an on-die implementation or a glitch-bandwidth claim. |
| Clock period and duty | Edge and pulse-width window monitor, with a qualified independent missing-edge observation | [He, Su and Yang, *Design-Agnostic Distributed Timing Fault Injection Monitor*, 2025](https://arxiv.org/html/2501.09665v1), sections II and III, describes a DLL/clock-replica family and pulse addition, skipping, duty changes and phase shifts. Qualification must cover both polarities, absolute period and stopped clocks; following a disturbed clock with an adaptive reference is an explicit refutation case. |
| Datapath timing margin | Locally placed critical-path replica/canary driven by fixed public excitation, comparing its physical delay with a fixed margin | [Alnajjar et al., *PVT-induced timing error detection through replica circuits and time redundancy*, 2013](https://www.jstage.jst.go.jp/article/elex/10/5/10_10.20130081/_pdf), studies replica-path monitoring and mismatch with functional paths. This selection uses a monitor-only replica, not execution recovery, replay, or an architectural operand comparison. Replica correspondence and local coverage must be qualified. |
| Logic-tier illumination | Distributed direct CMOS photodiode/photocurrent detector with threshold output | [The authors' institutional record of *Silicon Proven … Sub-Vt Optical Sensor for Hardware Security Applications*, 2023](https://cris.biu.ac.il/en/publications/silicon-proven-129-%CE%BCm-18-%CE%BCm-65nm-sub-vt-optical-sensor-for-hardwa/) identifies direct optical sensing inside the digital logic fabric; the publication is [IEEE Access, DOI 10.1109/ACCESS.2023.3338001](https://doi.org/10.1109/ACCESS.2023.3338001). Device/process transfer, spectral response and placement are qualification work. No reported sensitivity or false-positive rate is imported. |

OpenTitan is read at this repository's gitlink revision
`ae79548c0fb30c708ec3f870d4b462611ed87b4f`, under its
[root Apache-2.0 LICENSE](https://github.com/lowRISC/opentitan/blob/ae79548c0fb30c708ec3f870d4b462611ed87b4f/LICENSE)
and the inspected RTL's Apache-2.0 headers. This document incorporates no source.
Its existing [third-party row](../../THIRD-PARTY.md#pinned-as-submodules) remains the
licensing/provenance owner; an implementation that copies or adapts code owes its
own incorporation reading and distribution record.

The exact structural references are:

| Pinned artifact | Structure read | Boundary that VerifiedOS must supply |
| --- | --- | --- |
| [Earl Grey `sensor_ctrl.sv`](https://github.com/lowRISC/opentitan/blob/ae79548c0fb30c708ec3f870d4b462611ed87b4f/hw/top_earlgrey/ip/sensor_ctrl/rtl/sensor_ctrl.sv) and its [operation document](https://github.com/lowRISC/opentitan/blob/ae79548c0fb30c708ec3f870d4b462611ed87b4f/hw/top_earlgrey/ip/sensor_ctrl/doc/theory_of_operation.md) | Independent synchronization of active-high/active-low sensor indications; assertion of either active polarity forms an event; fatal events persist without acknowledging the sensor. | It also has writable alert enables, fatal/recoverable selection, trigger/test fields and a filtered wake path. Those policies are not this contract's immutable, unconditional fail-stop path. |
| [Earl Grey `alert_handler.sv`](https://github.com/lowRISC/opentitan/blob/ae79548c0fb30c708ec3f870d4b462611ed87b4f/hw/top_earlgrey/ip_autogen/alert_handler/rtl/alert_handler.sv) and its [operation document](https://github.com/lowRISC/opentitan/blob/ae79548c0fb30c708ec3f870d4b462611ed87b4f/hw/top_earlgrey/ip_autogen/alert_handler/doc/theory_of_operation.md) | Alert receivers, channel pinging, signal-integrity failures, escalation senders and hardened controller state. | Configurable classes, accumulation, interrupts and escalation waits do not establish an immediate RoT latch, an independent RoT bite or physical sensor health. Channel pinging alone cannot discover a detached transducer that still returns a healthy channel response. |
| [Earl Grey `ast.sv`](https://github.com/lowRISC/opentitan/blob/ae79548c0fb30c708ec3f870d4b462611ed87b4f/hw/top_earlgrey/ip/ast/rtl/ast.sv), [AST specification](https://github.com/lowRISC/opentitan/blob/ae79548c0fb30c708ec3f870d4b462611ed87b4f/hw/top_earlgrey/ip/ast/README.md) and [`ast_part_secondary.sv`](https://github.com/lowRISC/opentitan/blob/ae79548c0fb30c708ec3f870d4b462611ed87b4f/hw/top_earlgrey/ip/ast/rtl/ast_part_secondary.sv) | Supply/clock interfaces, primary/secondary partitions and paired alert interfaces. | The secondary partition's **Alerts Open-Source Selection** ties the shield, clock-glitch, glitch-detector, temperature and other physical source pairs inactive; other-0 comes from TLUL integrity. These are placeholders, not active analog detectors. The upstream programmable/deep-sleep and boot-response choices do not qualify this die. Foundry-specific cells and their evidence are external prerequisites. |

## 2. Inventory generated from the composed topology

The sensor implementation owner consumes the same emitted topology and identity
as the reset table, clock spine, OPP assignment and physical layout. Let `P` be
the RoT, both physical S-class lockstep instances and every composed core island,
including their constituent cores. The lockstep partner is a physical instance
even where the roster represents the pair by one architectural hart. Let
`rails(P)` and `clocks(P)` include every supply and clock actually consumed by
those blocks and their shared dependencies. Trace supply parents and clock
parents to their sources: a monitor only at a PLL output does not replace a
monitor at a locally faultable clock leaf, nor does a regulator-input monitor
replace a monitor at the powered region.

The following mapping is quantified over those sets. Its rows define how an
implementation emits the inventory, not a hand-maintained count of its members.

| Topology member | Sensor and immutable fields from section 3 | Destination and ownership |
| --- | --- | --- |
| Each RoT supply, including the watchdog/reset path's supply dependencies | Supply window; per-state voltage bands, reference identity, response envelope and health bound | RoT latch plus direct RoT-self-fault bite. Analog qualification owner sets the band and loss-of-power behavior. |
| Each supply used by either S-class instance or any core island, including shared rails used by fabric, memories or device blocks serving it | Supply window at each qualified observation site; per-state bands and site-to-consumer relation | RoT latch, targeting every affected island. A rail shared with the RoT additionally takes the RoT bite. Analog qualification owner sets each band. |
| Every clock used by the RoT, including its independent slow clock and the clocks the watchdog/reset path needs | Period/duty and missing-edge monitor; per-state edge bands and qualified independent observer | RoT latch plus direct bite. Clock qualification owner sets bands and observer bounds; observing the slow clock with itself is refused. |
| The spine/PLL hierarchy and every derived clock consumed by the S-class pair or a core island, including its shared fabric/memory/device clocks and local leaves | Period/duty and missing-edge monitor; per-OPP divider state, gate state, phase/edge bands and site relation | RoT latch for all dependent islands; RoT sharing takes bite. Clock qualification owner sets every band, including reset/transition cases. |
| The RoT datapath and every core's datapath, covering both physical S-class instances and all composed C/V/M/S/RoT classes | Distributed replica/canary timing-margin sites; path-class binding, declared minimum slack and correspondence envelope | RoT latch; a RoT region takes bite. Timing qualification owner closes local placement and representative-path correspondence, independently of whether software activates a functional critical path. |
| Every region of the logic tier, including cores, the RoT, sentinel/comparator, sensor controllers, trip routing and reset logic | Direct photocurrent sites; threshold, spectral/temporal envelope, coordinates and declared pitch | RoT latch for affected islands; any RoT/bite-control region takes bite. Optical qualification owner sets threshold and pitch against the actual stack and floorplan. |

An externally recovered interface clock that terminates in its bounded FIFO is
not an island clock merely because the island drives the FIFO's fabric side.
Its fabric-side clock is included above. An external clock actually used by a
protected block, or powering/timing the detector boundary, must be included;
the clock-spine owner must identify it rather than call it mesochronous by fiat.
No extra fixed-latency architectural crossing is introduced by detector-local
references; the RoT crossings retain one-sided bounds.

The integration checker must generate its concrete inventory and compare the
following relations with the elaborated RTL and physical design:

1. Every member of `rails(P)` and `clocks(P)` has a monitor at every declared
   observation site, and each actual physical consumer is associated with its
   affected island set. Shared upstream nodes and local leaves are both checked.
2. Every actual core datapath, the RoT and both S-class instances have their
   timing sites; every logic-tier region has an optical-site assignment at the
   declared pitch. Gaps, floorplan obstructions and regions outside a qualified
   site's footprint are reported explicitly and refuse qualification.
3. Every monitor's supply, reference, enable, reset, trip and health-check
   dependencies are themselves inside the inventory and the section 4 boundary.
   The dependency graph cannot justify a monitor's liveness solely by that same
   monitor or solely by the clock/rail it is meant to guard.
4. Every state, OPP, table suffix and transition that releases a consumer has
   qualified constant fields. A missing topology, path, site, value, evidence
   identity or owner refuses, as does a field naming a retired physical artifact.

The emitted inventory is a generated/checkable deliverable of sensor
implementation. This document creates no second topology file or duplicated
roster. At present the [composition](../../model/config/verifiedos.json) carries
core roles and island bindings; it is not a qualified physical rail/leaf/site
inventory. Its numeric clock and watchdog placeholders are not sensor settings.

## 3. Devicetree field contract and qualification owners

`environmental-sensors` is a proposed attested-devicetree record, emitted with
the real topology under R-09-007; it is not an added model configuration or MMIO
window here. Each row has a stable `sensor-id` and records the following typed
fields. Quantities use explicit units and canonical integer/rational encodings;
the consuming descriptor's encoding/canonicity is owned by the devicetree
implementation. A textual `pending` is permitted in planning evidence but never
in an accepted part's record.

| Fields | Meaning and qualification owner |
| --- | --- |
| `kind`, `guarded-resource-refs`, `consumer-refs`, `site-ref`, `affected-island-refs`, `rot-self-fault` | Family, physical observation point and full dependency relation. Sensor implementation owner generates these from the reset/clock/layout owners' artifacts and checks RTL identity. |
| `qualification-owner`, `part-profile-ref`, `cell-revision-ref`, `layout-ref`, `operating-envelope-ref`, `qualification-evidence-ref` | Named accountable owner and immutable part/process, cell, layout and evidence identities. Part qualification owner signs the tuple; changed identities invalidate its acceptance. |
| `state-ref`, `opp-ref`, `voltage-min-uv`, `voltage-max-uv`, `hysteresis-uv`, `pulse-response-envelope-ref` | Supply bounds at the observation point, hysteresis and amplitude/duration response envelope. **Analog qualification owner** sets every voltage/hysteresis value and pulse-envelope entry. |
| `period-min-ps`, `period-max-ps`, `high-min-ps`, `high-max-ps`, `low-min-ps`, `low-max-ps`, `duty-min-ratio`, `duty-max-ratio`, `missing-edge-max-ps`, `clock-reference-ref`, `reference-error-bound-ref` | Period, both pulse widths, duty and cessation bounds per composed clock state. **Clock qualification owner** sets every edge/period/duty bound and qualifies the independent observer. Period and pulse/duty fields must agree, with measurement uncertainty accounted for. |
| `path-class-refs`, `excitation-ref`, `slack-min-ps`, `replica-correspondence-ref`, `timing-site-ref` | Fixed public excitation, timing margin and local mapping to functional path classes. **Timing qualification owner** sets each margin and records mismatch over corners/aging. Unrepresented paths remain explicit residuals. |
| `photocurrent-trip-na`, `dark-current-envelope-ref`, `spectral-envelope-ref`, `optical-pulse-envelope-ref`, `optical-site-layout-ref`, `max-site-pitch-um` | Direct illumination threshold, dark-current/background envelope, wavelength/pulse response, placement and pitch. **Optical qualification owner** sets every threshold, optical response bound and pitch on the selected logic-tier stack. A two-dimensional pitch alone supplies no coverage result. |
| `expected-state-ref`, `enable-constant`, `configuration-integrity-ref`, `health-method-ref`, `health-max-ps`, `trip-path-ref`, `trip-latch-ref`, `trip-response-bound-ref`, `reset-hold-ref` | Table-authorized on/off/transition expectation, immutable enable, health supervision, latch/bite destination and response bounds. **Sensor boundary implementation owner** binds paths; the **part qualification owner**, with analog/clock/timing/optical owners, sets each physical health/response bound. |

Every scalar threshold, band, margin, pitch, pulse envelope and response bound
must carry its named owner's qualification evidence, including the inequality
convention at an endpoint and uncertainty. Outside a supply/clock band, below
the declared timing margin, or above the light threshold is a trip. Endpoint and
hysteresis tests are specified in the evidence rather than left to rounding.
The record binds the threshold constants to the actual cell/fuse/hardwired
settings read at qualification. It cannot ask software to choose or tune them.

OPP/state selection follows only the attested reset/mode table and composed OPP
assignment. Each selection is among qualified constants; no software-writable
threshold, monitor disable, data-dependent adaptation or dynamic calibration
path is admitted. Manufacturing trim is fixed before part acceptance, included
in the identity and integrity check, and inaccessible to production software.
The devicetree reports the settings; changing an attested description cannot
silently reprogram analog silicon.

## 4. One fail-stop boundary, including RoT self-fault

The transducer, its reference and excitation, constant storage/selection,
expected-state and enable checking, trip capture, routing, health checking,
RoT latch and final reset/bite control form one fail-stop boundary. A fault that
disables a sensor or corrupts its settings/path must latch failure rather than
create a successful disarm. Paired indications, fail-active encodings, protected
constants and bounded liveness checks are candidate means; implementation must
exercise open/stuck lines, valid-looking wrong settings, broken transducers and
stopped references. Neither an encoding nor a ping demonstrates analog health
by itself. Any blind disabling fault becomes a finding and prevents qualification
of the claimed boundary, even if the event transport's digital test passes.

For an island-only trip, hardware captures the event persistently and carries it
to the **RoT's** existing fail-stop-class latch, the class of uncorrectable ECC.
It does not wait for the struck island to execute, poll, acknowledge or send an
MSI; software masking cannot stop it. The RoT invokes the existing reset/isolation
and containment policy for every dependent island. Detection freezes further
release of the affected domains. Response bounds include trip capture, crossings,
latch, issue cutoff and reset/isolation; they are qualification/implementation
evidence, never assumed to prevent every corrupted result preceding capture.
Acknowledgement used for transport cannot erase the latch or authorize restart.

A trip on any RoT supply, consumed clock, timing region or optical region, or on
a shared resource reaching the RoT, **asserts the RoT watchdog bite** under
[R-16-005](../spec.md#r-16-005). This path must not depend on the faulted RoT
CPU, its main/spine clock, or successful delivery through its firmware mailbox.
The boundary owner supplies a qualified physical reset assertion/hold mechanism
and independent observation for the slow-clock-fault case. An extra
detector-internal reference is physical monitor circuitry, not another
architecturally modeled clock domain or a second management processor.

Where power loss prevents active logic from reporting, the device must be held
in reset and fail release on restoration until the boundary is healthy and the
reset table's recovery checks finish. No claim is made that an unpowered latch
retains its event, that a stopped watchdog can time itself, or that attestation
can reconstruct a cause whose record was lost. The qualification record must
show the reset-safe behavior across total supply loss and recovery; an absent
independent assertion/hold path refuses the RoT-self-fault implementation.

Intentional rail-off or clock-gated intervals are table states, not discretionary
sensor masks. An always-on boundary observes expected rail/gate state and keeps
trip latches/health supervision live. A local datapath detector may be physically
inactive only while its consumer is confirmed reset/isolated under the composed
off state. Before release its constants, enable and health are checked. A gate,
rail or detector becoming inactive while its consumer is authorized active trips;
a transition that overruns its declared bound trips. OPP divider/rail changes
use separately qualified transition bands and fixed table dwells, without
retuning a PLL at a partition boundary or following workload-induced excursions.
No quiet interval hides a trip just before entry, during isolation or at release.

M3's RoT firmware consumes the persistent latch only after the hardware stop is
asserted, records the closed environmental-trip class through the existing
attested event mechanism and counts recurrent containment under
[R-17-030m](../spec.md#r-17-030m). Public cause detail is limited
to the permitted event class; raw analog values/site maps are qualification data,
not ambient telemetry. The record distinguishes a known trip from an unknown
reset/power-loss cause and states any lost accounting interval. Rate evidence
does not weaken fail-stop. Repeated reset takes the existing recovery path;
the stopped device loses only work the existing transactional policy leaves
uncommitted, subject to its own acceptance.

## 5. Architectural and physical-only boundary

The detectors hold monitor state and sticky failure evidence, not architectural
register, capability, memory, PC or execution-result state. Their outputs can
request the already existing fail-stop/bite and cannot supply a computed value,
repair/replay an instruction, vote on a result or change a successful committed
result. They add no instruction, CSR, access type, writable threshold, interrupt
model member or software-controlled clock/rail policy. R-16-008e's exclusions and
the S-class-only replication decision stand. The [frozen ISA profile](isa-profile.md),
Sail sources/configuration and [R-18-010](../spec.md#r-18-010)'s
RTL-to-Sail obligation are unchanged; a circuit implementing this boundary still
owes that obligation on the same terms as
[R-15-157](../spec.md#r-15-157)'s physical hardening.

The selected timing monitor's excitation and expected value are fixed public
monitor signals. It samples no architectural operand, signature or functional
result and performs no secret-dependent comparison. Supply, clock and optical
detectors likewise inspect physical quantities. Qualification must refute a
candidate that makes the event depend on a software-computed value at matched
physical stimuli, or exposes additional value/timing telemetry. This does not
prove the absence of all physical workload coupling: missed coupling is a
qualification/model-faithfulness residual, never a digital theorem about physics.

Light sites reside in the logic tier and must preserve the backside optical
inspection access under [R-15-160](../spec.md#r-15-160). Layout
review rejects opaque added backside structures or a protection mesh used as an
optical barrier. The sensor trips on illumination, not breach of a barrier;
[R-17-059a](../spec.md#r-17-059a)'s mesh disposition is unchanged.

## 6. Characterization campaigns and refutations

Part qualification freezes the operating envelope before campaigns: process and
lot identities, voltage/OPP states, temperature and aging corners, packaging/stack,
authorized clock tolerance/jitter, optical background/dark current and legal
reset/standby/wake transitions. The campaign owner records calibrated instruments,
measurement sites and uncertainty, DUT/cell/layout/configuration identity,
injection coordinates and time, measured local waveform, detector event, RoT
latch/bite and final containment, alongside independently observed functional
effects. Generator or pulser settings alone are not the stimulus at the die.
Instrumented validation builds can expose internal observations; production
software gains no detector tuning or raw sensor surface.

Each campaign uses the sensor-specific observation band in section 3 and the
qualification envelope. A negative control includes a real nonzero excursion
**inside** the declared band with no path margin or optical threshold violated,
for which the plan expects no trip. A blank/sham control supplements it and
cannot replace it. Excursions on/near either side of every threshold test the
declared endpoint and hysteresis conventions. An in-band stimulus that still
faults functional logic refutes an extrapolated coverage claim; it never licenses
widening the fault model or suppressing the resulting evidence.

| Campaign | Sweep and observations | Negative controls | Refutation cases returned to owners |
| --- | --- | --- | --- |
| Supply glitch | Under/over-voltage amplitude, duration, slew, repetition and phase at each rail/site; active/off/transition states; shared rails, detector reference and RoT supply loss/recovery. Observe timing margin, functional effects, trip and stop separately. | Measured voltage excursion wholly inside the qualified state/transition band, with margin remaining above its minimum; sham pulser. | Out-of-band waveform in the declared response envelope without latch/bite; in-band functional corruption; local droop absent at the chosen monitor site; detector power loss/disarm, reference-following or latch clear that permits release. |
| Clock | Period/duty change, both-polarity shortened/extended pulses, inserted/skipped edges, phase shifts and stopped clock, at spine parents and local leaves; divider/OPP, gate and reset-table transitions; slow-clock fault separately. | Measured nonzero period/duty/phase perturbation inside all declared bounds with no margin violation; legal composed divider transition; sham injector. | Out-of-band or missing edge without latch/bite; same average frequency hiding a bad pulse; adaptive/reference common-mode tracking; downstream leaf-only glitch; stopped watched/reference clock preventing reporting; legitimate transition producing an unexplained trip. |
| Electromagnetic | Position, orientation, pulse shape, timing and repetition over rail, clock, datapath, detector/control and RoT regions. Observe local rails/edges/margin proxies and effects, including localized strikes with no measured global excursion. | Nonzero coupling whose measured local rail/edge/margin quantities remain in their qualified bands, expected not to trip; matched probe placement without pulse. | Functional datapath/fetch/comparison corruption without trip; local event missed by replica placement; corrupted enable/constants/routing or direct bite; trip at matched in-band physical quantities differing only with a software value; failure to contain a shared-domain event. |
| Laser/illumination | Coordinates over the whole logic tier, between sites and at edges/obstructions; wavelength, focus, duration, energy and phase on actual front/backside stack; RoT and trip-controller sites, dark current/background and aging. Observe local photocurrent, functional effect and latch/bite. | Nonzero illumination yielding photocurrent below the declared threshold and no other detector-band violation, expected not to trip; blocked/sham beam. | Qualified over-threshold photocurrent without stop; a fault between/under sites without trip; wavelength/stack/aging blind spot; detached or blinded optical cell; backside inspection occlusion; corrupted event routing; value-dependent current-detector response. |

The timing qualification owner also sweeps the declared monitored-path slack
above/below every margin at each datapath site, exercising the public monitor
pattern over all its transition classes. Replica/functional-path mismatch,
setup/hold distinctions, process gradients and localized perturbations are
reported even when the nominal replica test passes. A detector may not borrow
another detector's observation to claim its own margin was measured.

Boundary tests inject failures of transducers, references, trim/constants,
selectors, enables, active/inactive event lines, health response, trip latches,
crossings and bite/reset hold. Test during entry/exit from every relevant table
suffix, simultaneous island trips and RoT/island trips, and before firmware runs.
An event transported correctly while a disabling fault remains silent is a
boundary failure. These fault tests are evidence and not a complete multi-fault
theorem. FPGA/digital rehearsal can qualify the harness and modeled transport;
only actual part measurements address analog thresholds, pitch and physical
response. FPGA timing/optical readings never qualify a different process.

False-trip measurement runs **without adversarial injection** across the frozen
operating envelope and its legal transitions, including fixed-tier/elastic
workloads with different public and secret operand patterns. Report observation
time and exposed devices/sites/state dwell, event counts, instrument uncertainty,
interrupted intervals, environment excursions and unresolved causes. A false trip
means a trip while independently measured physical quantities satisfy the
declared envelope, not merely a device that seemed to compute correctly.
Characterize event counts per declared exposure to report an observed false-trip
rate; this is not a detection probability or a lifetime/general-population bound.
No trips observed is recorded as zero observed events over the named exposure,
never as zero possible false trips. The independent review decides whether the
measured nuisance/availability cost permits that part; changing settings requires
new identity-bound qualification, not a runtime workaround.

## 7. Residual attribution and protected-sequence boundary

[R-16-008b](../spec.md#r-16-008b) retains its effect-based owners.
Supply/clock/timing/optical sensors can narrow a case only where its physical
cause excites the qualified local detector. They are cited as characterization
evidence, never as a substitute mechanism or a proof that the case is closed.

| Case | What this sensor family can narrow | What remains and where it belongs |
| --- | --- | --- |
| Stored-state corruption | Rail/clock excursions during accesses, timing loss near cells/control, and illumination near the logic tier | ECC remains the correcting/fail-stop owner. Direct or localized upsets, stacked-memory effects outside optical reach and in-band/missed faults remain physical residuals. |
| Capability corruption | Physical excursions in tag/data/check paths near qualified sites | Tag integrity and bounds checks remain the attributed owner. A corrupted check or wrong result not detected there gains no sensor guarantee. |
| Live kernel fault | Qualified physical causes of faults in a kernel's core/island | Multikernel confinement and crash-only restart remain the owner. A cause inside bands or outside a site's reach stays unclosed. |
| Wedged/runaway core | Stopped/bad clocks, supply departures and local timing/illumination events | Layered watchdogs remain the owner. A logical wedge within physical bands is not a sensor event. |
| Skipped/corrupted critical instruction, including decision/token epilogue | Qualified excursions while the protected sequence executes | Instrumentation and the protected-sequence model retain their distinct scope and unresolved findings. A sensor does not prove token withholding, repair a wrong reduction or exclude an ineffective fault. |
| Fault in the detector/sentinel itself | Qualified excursions near its supply/clock/timing/light sites; boundary health tests | The S-class lockstep detector remains the attributed owner where applicable. Common-mode, coordinated and silent physical boundary corruption can escape; RoT continuous operation has no new comparator. |
| Transient arithmetic, fetch-check or other combinational datapath strike | Local timing/illumination or rail/clock departure observed by a qualified site | A wrong result inside the bands or missing every site remains unclaimed at consumer grade under R-17-058b. No attribution of this remainder to sensors is made. |

The [protected-sequence fault model](protected-sequence-fault-model.md) perturbs
a canonical fetched instruction or skips its execution within its activation
budget. It does not model analog sensor behavior. Its reported reduction/token,
ineffective-fault, encoded-fetch and boundary findings are unchanged here.
Campaigns retain faults in the compare/fail-stop epilogue, direct datapath strikes,
multi-instruction effects of one physical encoded-fetch fault, simultaneous and
coordinated strikes as separate observed outcomes. A sensor trip cannot turn an
out-of-model physical strike into an in-model instruction fault, or characterize
R-16-008f's axiom by implication. Its separate bring-up/model-faithfulness work
remains with that model's owner.

[R-17-058b](../spec.md#r-17-058b)'s limits remain: multi-fault and
signature coincidences; epilogue faults; the unreplicated C/V/M classes and RoT's
continuous operation; unclaimed consumer-grade transient datapath corruption;
and the observable trip/no-trip safe-error outcome. Sensors close none of them.
They also supply no combined probe-and-fault theorem under R-17-058c/R-17-058d.
An adversary can provoke a correct sensor and stop a correctly behaving device
without software access, the availability seam
[R-17-030n](../spec.md#r-17-030n). False-trip characterization
does not remove that deliberate-trip denial or its one-bit observation.

## 8. Owners, joins and acceptance

The implementation owners are **Q41a · Implement environmental sensor cells and
the RoT fail-stop boundary** and **Q41b · Qualify environmental sensor bands,
placement and fault campaigns** in the
[implementation checklist](../implementation/implementation-checklist.md).
Existing owner tracks are consumers, not evidence that these new packages are
already implemented.

| Accountable owner/package | Deliverable and acceptance predicate | Existing join |
| --- | --- | --- |
| **Q41a environmental sensor implementation owner**, with foundry/analog cell designer | Licensed process-specific supply, clock, replica and optical cells; generated topology inventory/field emitter and refusal checker; fixed constants and healthy-enable checks; one fail-stop/latch/bite/reset-hold boundary. Acceptance requires the section 2 total mapping and section 4 disabling/self-fault cases on the actual bound RTL/cell interfaces. | RTL track's RoT/island integration; R1c-ii is the SoC/device integration consumer, not acceptance of physical sensors. |
| **Q41b analog, clock, timing and optical qualification owners**, accountable to the **Q41b environmental sensor part qualification owner** | Each respective section 3 threshold/band/margin/pitch and reference/response bound, with process/layout/part identities and campaign refutations. No unnamed supplier value qualifies a setting. | The reset/clock-spine/devicetree owners and M9/M9a power/droop evidence supply compatible operating states; R5/R5a qualify memory/lifetimes separately, not sensor coverage. |
| **Q41a RoT trip firmware owner** | Existing-latch consumption after hardware stop, guarded recovery/release and attested event class/rate accounting. Reject a mailbox-only trip, clear-before-stop, stale/unknown cause reported as measured, or recurrent trips omitted from the event account. | M3's RoT specification/executable firmware; completed boot-chain work receives this additional integration obligation rather than being claimed to implement it. |
| **Q41b environmental sensor characterization owner** | Instrumented glitch/clock/EM/laser campaigns, timing/health/boundary cases and operating-envelope false-trip exposure records. Every campaign includes the specified in-band and sham controls; missing observations or unexplained counterexamples refuse the affected qualification claim. | Bring-up specimens, floorplan/stack and independent R-05-150 review; harness rehearsal precedes physical measurements without substituting for them. |
| **Independent specification/qualification reviewer** | Read register/contract pairs, full topology join, immutable/no-ISA/physical-only argument, nuisance cost and every refutation/residual. Approve the contract's scope separately from any later part qualification; record the actual evidence revision. | R-05-150 release gate and the implementation checklist's Tier A landing. |

The contract landing predicate is a full reading of the Q41/R-16-008g clauses
against sections 1–7, including the RoT self-fault route and all four negative
controls. It accepts a specification and plan only. The topology-emission,
analog/RTL, firmware and qualification packages remain open until their named
deliverables and joins exist. No `n/a` is permitted for a required sensor because
the physical design is unfinished; `n/a` is limited to a field inapplicable to
the selected sensor kind. A required unresolved value is a refusal.

At integration, accept only when the actual attested tree and elaborated RTL
agree with the generated physical mapping; every qualification owner/evidence
tuple is present; settings/enable/latch paths satisfy the single boundary;
no frozen profile, Sail or ISA surface has changed; and all required physical
and operating-envelope records have independent review. A missing domain or
clock is a finding even if every already listed sensor passes its test. No
sampled campaign, successful source build or transport proof upgrades the
environmental coverage claim beyond **detected**.
