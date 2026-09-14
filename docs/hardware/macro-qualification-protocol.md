# Second-class macro qualification protocol

This is the protocol-authoring part of R5 in the [implementation checklist](../implementation/implementation-checklist.md). It measures the architecture and measurands owned by [R4](second-class-macro-architecture.md#5-the-measurands) against R-15-247m in the [requirements register](../requirements-register.md). It contains no measured value and grants no qualification. A missing specimen or result leaves R5 open.

## 1. Inputs fixed before a campaign

The campaign record identifies the die, fabrication process and lot, deck and macro revision, mask and layout hashes, extracted netlist, controller and sequencer revisions, package, board and power-delivery network. The specimen is a repaired megabit-class macro with payload, tags, both ECC fields, refresh and discharge paths, spares and routing present. A cell coupon, unrepaired array or simulation cannot substitute for it. A repair map names each faulty and replacement row or column, the screening procedure, coverage and remaining usable addresses. Freeze that map before measuring; repeat the affected measurements if it changes.

Declare the operational voltage and junction-temperature range, the thermal-trip corner, cold attack corner, service life and composed bias/refresh stress profile. State the ageing model and its validation; accelerated stress without a justified relation to service life supplies only evidence at the applied stress. Bind calibration certificates, fixture transfer functions, clock reference, trigger definition and raw captures to the specimen record.

Before observing the data, fix the tested population and patterns, address and repair classes, repetitions, stopping rules, uncertainty method and one-sided coverage/confidence claim. State what is exhaustively exercised and what is sampled. Sampling never warrants an all-cell claim by itself: the unsampled population needs a stated physical bound and a validation method, or the claim remains unqualified. Record negative results and censored observations. No tolerance, dwell or corner may be selected after observing a failure to turn that failure into a pass.

Every result carries its symbol, unit, specimen and protocol revision, raw-data hashes, processing command, estimate or interval, uncertainty budget, tested scope, acceptance comparison and verdict. Instrument resolution, calibration, trigger skew, fixture loading, spatial variation, ageing uncertainty, interpolation and sampling uncertainty appear separately where applicable; an omitted contribution needs a ground. Missing mandatory evidence is `unqualified`, not zero.

## 2. Density, geometry and repair

### `rho_usable`

Use layout-area metrology reconciled with fabricated macro boundaries and an electrical address census. Count usable payload bits after repair and divide by the complete macro footprint, including tag and check columns, spares, sense amplifiers, drivers, maintenance and routing overhead. Keep stacked footprint area and summed deck area distinct. Reject a cell-density substitution, inaccessible payload counted as usable, or an unexplained layout/electrical discrepancy. The uncertainty budget includes boundary resolution and unusable-address classification. R5 owns the result; R-18-004b's composition supplies the capacity threshold it must meet.

### `w_row`

Reconcile decoded row addresses, extracted column connectivity and electrical walking-pattern tests, including tag/check columns and repair substitutions. Report cells per row with its deck and subarray identity. Reject a row definition that omits overhead or combines separately accessed rows. Record metrology and mapping uncertainty; the block-geometry constraint consumes the result only after qualification.

### `w_page`

Capture the codewords presented by one read access and relate them to the same row map. Report codewords per access, without treating a page as an open-page timing state. Reject a value requiring a second access or excluding repaired paths. Account for capture resolution and mapping coverage.

### `w_sense`

At the hot corner, exercise all declared sense and repaired-address classes in one access, including data, tags and check bits. Report the single-access width in bits and its uncertainty. Reject a width requiring time multiplexing beyond the declared access. R-15-181a owns the choice between its codeword and fallback; the protocol supplies evidence and does not choose another codeword.

### `n_rows_bank`

Reconcile the bank decoder, repair map and electrical census. Report usable rows per bank, excluding spares counted only as substitutes. Reject unexplained holes or a bank that crosses the deck boundary R4 declares. Record identification uncertainty; the bank-count search consumes this geometry rather than a guessed row count.

### `n_spare`, `f_repair`

Record physical spare rows and columns by subarray, defects found before repair, substitution map and post-repair coverage under the same pattern suite. Exercise substituted and unaffected addresses through normal and maintenance paths. Reject latent aliasing, duplicated usable capacity or timing depending on substitution. State screening coverage and its uncertainty; an unobserved defect rate is not zero.

## 3. Fixed access constants

For each constant below, use a calibrated timing source and logic/analogue capture at the declared macro interface. Exercise declared address, pattern, prior-access and repair classes across operational corners and end-of-life stress. Report elapsed time and the conversion to the composition clock with uncertainty. Acceptance requires a common externally visible bound and completion schedule for every admitted class, with no data-, history-, address- or repair-dependent interface timing. A mean or percentile cannot supply the constant. Missing coverage leaves the affected constant unqualified.

### `t_read`

Measure from address presentation to a valid whole codeword, including tag and check columns. Refuse a result that excludes their arrival or relies on an open row. Separate controller ECC latency from the macro measurement and bind both when publishing the class constant.

### `t_write`

Measure from whole-codeword presentation to committed data, tags and check bits. Verify readback using independently prepared sacrificial samples so measurement reads do not change the event being timed. Refuse torn planes or a declared completion preceding any required commit.

### `t_refresh`

Measure the complete row read-and-rewrite through both ports, including both planes and check fields. Exercise ON and RETAINED operation. Refuse a result for reading alone or a rewrite that misses any admitted address class. Refresh retention and ECC correction remain separate postconditions.

## 4. Retention and service-life evidence

### `T_ret_floor`

At the hot thermal-trip corner after declared lifetime stress, write the predeclared patterns, withhold refresh for independently selected intervals and measure the first failure boundary across the repaired population. Bound the interval over which all tested payload, tag and check bits remain readable, including the uncertainty and unsampled-population argument. Read disturb is controlled with independent specimens or separate sacrificial trials. The qualified lower bound, reduced by uncertainty and required margin, must exceed the composed refresh sweep and its worst phase gap. This operational floor cannot justify sanitization or confidentiality (R-15-247c).

### `T_ret_ceiling`

At the declared cold attack corner and power states, determine the longest observed recovery interval and a separately justified upper bound, if one can be established. Preserve a right-censored result where any cell remains recoverable at the last observation. Report seconds, recovery method, state discrimination criterion and confidence scope; absence of recovery by one reader is not proof of destruction. This result characterizes R-17-058f's exposure window and supplies no erase guarantee. R5a separately qualifies first-class and key copies.

### `N_endure`

Apply the composed write and refresh stress at the hot corner, with periodic independent retention tests. Report cycles to loss of the required floor, counting refresh rewrites and disclosing acceleration assumptions. Right-censor survivors. Qualification requires the complete declared service-life workload to fit within the supported endurance bound; averaging surviving and failed banks is inadmissible.

### `dV_th`

Use calibrated transistor characterization tied to the same process and macro specimens before and after the composed bias stress. Report read- and write-device threshold drift in volts, spatial and lifetime variation, and uncertainty. Correlate drift to retention and timing margin at the required corner. A device-only result cannot replace the macro's retention/timing campaign.

### `V_rail_retained`

Sweep the independently controlled retained rail at the hot and lifetime corners while performing complete refresh writes. Establish the lowest supported rail with uncertainty and declared margin; test entry, residence and exit. Refuse a rail qualified only for holding a readable bit when refresh cannot commit there. Runtime rail choice stays composition-fixed under R-15-247r.

## 5. Discharge and the indication

### `t_discharge`

Preload payload, tags and check bits with the pattern and prior-state population. Assert each allowed phase's complete bank set, including the largest simultaneous set, through the production discharge path. Characterize every required corner, repair class, ageing state, supply path and short power interruption. Choose the dwell before the qualification run from the characterization bound plus declared uncertainty and margin. At that one fixed instant, perform one phase indication read; no polling or retry enters a successful run. Publish time and composition cycles together.

### `Q_witness`

Freeze witness locations and cardinality by bank/subarray before qualification. Compare the one phase indication with independent post-dwell examination of every data, tag and check region covered by its claim. Exercise held-charge, disconnected wordline, weak-driver and failed-subarray cases supported by the declared fault model. A positive indication with any covered region not at the landing state is a false success and rejects the witness construction. Explain coverage of faults and locations that cannot be injected; do not infer soundness from witness agreement alone.

There are two separate dwell-invariance questions. The indication must entail the complete phase's landing state at the fixed dwell, and both positive and negative externally observable outcomes must occur at the same declared read instant independent of discharge speed or prior contents. Sweep controlled delay and supply/temperature conditions on independent runs, including deliberately incomplete discharge, and compare transition timestamps with the predeclared resolution and uncertainty. Refuse an early-success path, speed-dependent timeout, second indication read, retry or positive indication lost when the discharged domain's rail collapses. Verify the surviving latch in the always-on RoT domain. This is the timing evidence M3.6b consumes; an FPGA rehearsal validates its capture harness and does not qualify the macro.

## 6. Activation, coupling and power

### `I_bank_peak`

Use calibrated current and voltage capture with sufficient bandwidth and de-embedded fixture impedance. Measure whole-bank assertion and row refresh separately, at the required corner and pattern/repair population. Report amperes, waveform and uncertainty, including peaks lost to bandwidth limits. No average-energy figure substitutes for instantaneous current.

### `I_pdn_max`

Characterize the actual provisioned delivery network with the admitted phase waveforms and simultaneous loads. Record the rail floor and allowed droop limits supplied by R-15-189i's provisioning. Report the supported simultaneous current envelope in amperes with fixture and model uncertainty. Reject any phase outside the supported voltage, thermal or power-signature limits; do not exchange a droop violation for lower average energy.

### `C_bl_per_row`

Measure bitline capacitance with calibrated impedance/charge techniques on the realized geometry, reconciled with extracted connectivity and repair configuration. Report farads per row and uncertainty, then bind the energy calculation to the measured voltage and access pattern. A literature cell value cannot price a macro bitline.

### `theta_couple`

Capture calibrated junction temperatures in activated banks and neighbours, including cross-deck locations, under each declared simultaneous phase and sustained refresh load. Report temperature rise per declared activation condition, response times and spatial/calibration uncertainty. A phase qualifies only against the composition's thermal limits after including coupling; independent single-bank measurements cannot supply that join.

### `sigma_disturb`

Prepare known victim patterns and exercise neighbouring reads, writes and whole-bank assertions, across decks and repaired paths, over the declared stress population. Report stored-level changes with the probe's unit and resolution, plus functional error observations and coverage. Refuse any disturb-immunity inference from an ECC-corrected endpoint alone. Compare against the declared data/tag correction and scrub obligations, with failures retained.

### `P_refresh`

Measure refresh energy on the repaired macro at the hot-corner cadence derived from the qualified floor, including controller and delivery losses declared inside the boundary. Scale to the actual capacity and schedule, stating the scaling assumptions and uncertainty. Report watts by composition mode and compare with R-18-004c's power budget. A low-utilization or room-temperature measurement cannot qualify capacity refresh power.

## 7. Acceptance and consumers

The protocol is reviewable when each R4 measurand has a preparation, instrument, corner, uncertainty treatment and decidable refusal above; the campaign inputs, repair identity and data schema are fixed; and timing invariance is distinguished from indication soundness and retention from recovery. Missing detail fails protocol acceptance. This is a Tier A contract review, not measured completion of R5.

Qualification requires every mandatory result against one consistent macro/process/repair identity, all stated comparisons passing and all uncertainty covered by declared margins. No density enters the devicetree until the complete R-15-247m package qualifies. A failed macro remains unqualified; the failure neither reopens the architecture nor establishes a different part's capacity. R5 owns measurement and evidence analysis. Specimen procurement, fabrication and lab availability remain external dependencies, with R-17-063b supplying no foundry offering or delivery date.

M3.6b consumes discharge timing and indication captures. M9a joins the measured activation envelope, qualified geometry and frozen bank granularity to composition-capacity droop/thermal admission. Q6 consumes usable resources and supply evidence, Q7 the exposure characterization, and R5a independently covers first-class and key lifetime. None can promote an emulator constant, an FPGA timing result or an unfilled protocol into physical qualification.
