# Sensitive-state and key lifetime qualification protocol

This protocol prepares R5a in the [implementation checklist](../implementation/implementation-checklist.md). R-15-200 in the [requirements register](../requirements-register.md) owns its qualification boundary. It shares specimen provenance and laboratory controls with the [R5 macro protocol](macro-qualification-protocol.md), while qualifying first-class macros, registers and dedicated key storage separately. No result or physical guarantee is supplied here.

## 1. Inventory and specimen identity

Before testing, reconcile the implemented dataflow, compiler spill map, register map, netlist and physical storage map into a copy inventory. Each row names a sensitive plaintext, key, expanded-key or derivation-state copy; its storage path and physical location; creation, duplication and overwrite events; retention supply and clock domains; data/tag/check-bit representation; and the reset, OFF or erase event claimed to destroy it. Include temporary datapath latches, buffers, register banks, spilled state and dedicated key-storage copies that implementation analysis finds. A path may be declared absent only with the inspected implementation evidence and its hash.

For each row bind the actual macro or cell construction, die/lot/process, repair configuration, layout and netlist, firmware and erase routine, regulator, discharge path and board revision. The inventory is complete only when every implemented copy source has either a row or a reviewed absence argument. Unresolved hidden state blocks qualification; qualifying one key register cannot qualify a key whose expanded schedule survives elsewhere.

The provider of each specimen, fabrication/preparation scope and laboratory owner are required campaign fields. R5a owns engineering protocol and analysis. If raw evidence is unavailable, it must assign a separately priced measurement child and provider before commissioning; this document is not authorization or pricing for fabrication, laboratory work or new erase hardware.

## 2. Two quantities with separate records

An operational retention record states a **minimum interval of reliable readability**, in seconds, under declared powered/retained conditions, patterns, ageing and uncertainty. Its consumer is reliable operation. It cannot bound how long an adversary can recover a state after power loss.

A confidentiality record states a **maximum supported recoverability window**, in seconds from a precisely recorded loss or erase event, for a declared recovery method and attacker/environment scope. For every inventoried copy it contains the last successful recovery, first failed observation, sampling interval, censoring status, method sensitivity, corner and uncertainty, and any justified upper-bound argument beyond those observations. Failure of a normal memory read does not establish destruction; a finite campaign that ends with a recoverable copy is right-censored and has no established maximum. A method unable to resolve the stored state supplies no confidentiality result.

Report raw data/tag/check-bit recoverability alongside plaintext and key recoverability. State decoding and error-correction capabilities available to the recovery adversary. A cleared capability tag retires authority and cannot hide readable plaintext. For R-17-059a, a relative key-versus-bulk lifetime claim requires the supported bound for **every** usable key, expanded-key and derivation-state copy, joined to the separately characterized bulk and to the adversary named in that entry.

## 3. Campaign design fixed before measurement

Declare the normal operating and thermal-trip corners, cold adversarial corner, retained supplies, power-loss slopes and residual-energy sources, service life and stress history. Cover beginning and end of life and any intermediate state required by the construction's drift model. Characterize cooling before and after removal of power; a room-temperature power-off test does not cover a cooled specimen.

Choose patterns, copy locations, sampling instants, repetitions, specimen populations, stopping rules and coverage/confidence method before the acceptance campaign. Preserve calibration and fixture transfer functions. Record timing resolution, trigger error, temperature gradients, instrument loading, recovery sensitivity, specimen variation and ageing/model uncertainty separately. Sampling beyond tested cells, times or conditions needs a justified bound; absent justification leaves that scope unqualified.

Use independent or sacrificial trials where a recovery read, a probe, cooling or re-powering can disturb the state. Record the intervention and test a control. Avoid counting the measurement's own erase as the device's destruction mechanism.

## 4. Abrupt-loss campaign

Prepare each inventory row with distinguishable known values through its real execution path. Interrupt power without running orderly shutdown, at each declared sensitive lifecycle position and supply configuration. Exercise first-class macros, registers and dedicated storage separately and in the composed power path. Record the external event and the actual rail/clock response at the copy, including residual and back-powered supplies.

At the predeclared time/temperature points attempt recovery with the qualified method, preserving both successful and failed attempts. Include retained-power states, incomplete supply discharge, abrupt loss while erase is in progress and re-powering inside the observed recovery interval. The result is exposure characterization under R-15-200, not sanitization. A missing maximum, unidentified surviving supply or recovery of any usable copy prevents a claimed key-destruction bound.

## 5. Orderly erase and OFF confirmation

Run the actual declared erase transition from every sensitive copy state and retain its timestamps. Check complete coverage of plaintext, key, expanded-key, derivation, tag and check-bit locations. Exercise interruption at each transition boundary, pending writes, repaired locations and retention-domain handoff. Bind the command, completion indication and always-on state to the implementation that consumers will trust.

The decisive rejection case is **completion asserted while a covered state remains recoverable**. Inject supported faults in write/discharge paths, omission of a copy, interrupted power and a stale completion indication; independently inspect the affected storage. For each fault state either the indication must remain unsuccessful or the claimed complete destruction must hold. Missing coverage or an unexplained positive indication rejects the construction. State which faults are physical injections, modeled cases or excluded assumptions; simulation cannot supply the physical implication.

Keep indication timing and indication truth separate. A fixed completion time does not prove erase, and data overwritten without a trustworthy completion signal cannot authorize reuse. OFF is qualified only where the actual supply and storage construction demonstrates the claimed destruction; its name is not evidence. R5's second-class mode-exit discharge result cannot substitute for this campaign's first-class and key copies, or for abrupt loss without that transition.

## 6. Result and acceptance

Each copy row receives separate retention, abrupt-loss exposure and orderly-erase verdicts, with specimen/protocol hashes, raw captures, analysis command, uncertainty and scope. Report unknown or right-censored windows explicitly. A window qualifies only if its claimed upper bound and every required corner/path are supported. An erase construction qualifies only if its completion-to-destruction claim survives the specified faults and all covered copies; measured decay alone supplies no such guarantee (R-15-247c).

Protocol acceptance requires a complete inventory method, separate campaigns and quantities, fixed inputs and uncertainty treatment, a falsifiable completion implication and named evidence providers. It is a Tier A reviewable contract. Evidence providers remain unassigned, so this preparation does not yet satisfy protocol acceptance. Physical R5a completion also requires the resulting evidence, which this repository does not contain. Q7 consumes the joined lifetime record when deciding a deployment threat window. M3.6b may reuse timing capture methods without inheriting a physical verdict; M9a consumes any resulting qualified power-path constraints at the composition-capacity join.
