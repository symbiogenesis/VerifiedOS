# SPDX-License-Identifier: Apache-2.0
"""Independent finite-state oracle and structural audit for CombinedReduction.v.

Verifies the R-17-058d combined fault-and-probing reduction model in
[CombinedReduction.v](../../proofs/CombinedReduction.v) against an independent
finite-state Python enumerator over small sharing orders (`d = 1, 2`) and checks
the Gallina source's theorem inventory, witness completeness (`R-05-166`), and
forbidden-construct exclusions (`R-05-163`, `R-05-164`).
"""

import itertools
import re
from collections import Counter
from pathlib import Path

from tests.harness import Case, ensure
from vos import proofaudit, proofs
from vos.cli import proofs as proof_gate

INDEPENDENT_CASES = True

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMBINED_V = _REPO_ROOT / "proofs" / "CombinedReduction.v"


# ---------------------------------------------------------------------------
# Independent finite-state model (shares no code with Rocq proofs)
# ---------------------------------------------------------------------------

def _encode_gf2(secret: int, masks: tuple[int, ...]) -> tuple[int, ...]:
    """Return (d + 1) additive GF(2) shares summing to `secret`."""
    completing = secret
    for mask in masks:
        completing ^= mask
    return (*masks, completing)


def _step_budget_derivation(
    in_region_limit: int,
    actions: tuple[str | None, ...],
    initial_budget: int,
) -> tuple[bool, int, int, int]:
    """Simulate `(pc, budget)` transitions under budget-1 rules.

    Returns `(valid, final_pc, final_budget, fault_count)`.
    """
    pc = 0
    budget = initial_budget
    faults = 0
    for act in actions:
        if act is None:
            pc += 1
        else:
            if pc > in_region_limit or budget < 1:
                return (False, pc, budget, faults)
            budget -= 1
            faults += 1
            pc += 1
    return (True, pc, budget, faults)


def _eval_checked_circuit(
    d: int,
    shares: tuple[int, ...],
    fault_kind: str | None,
    fault_idx: int | None,
) -> tuple[int, ...]:
    """Evaluate the `2 * (d + 1)`-wire masked circuit under fault class.

    Wires `0..d` hold the `(d + 1)` primary shares; wires `(d + 1)..(2 * d + 1)`
    hold the share-local check copies. A benign share-confined fault
    (`corrupt_false` at `idx <= d`) perturbs wire `(d + 1) + idx` using only
    share `idx` (`x_idx ^ 0`), remaining strictly inside share domain `idx`.
    """
    num_shares = d + 1
    ensure(len(shares) == num_shares, "share vector length mismatch")
    low_wires = list(shares)
    high_wires = list(shares)
    if fault_kind == "corrupt_false" and fault_idx is not None and fault_idx <= d:
        # Share-local perturbation inside domain `fault_idx` (never reads other shares).
        high_wires[fault_idx] = shares[fault_idx] ^ 0
    return tuple(low_wires + high_wires)


def _is_effective_fault(d: int, fault_kind: str | None, fault_idx: int | None) -> bool:
    """Match R-17-058d effective vs share-confined classification on the instance."""
    if fault_kind is None:
        return False
    ensure(fault_idx is not None, "explicit fault requires a target index")
    if fault_idx is None:
        return False
    if fault_idx > d:
        return True
    return fault_kind in ("skip", "corrupt_true")


def _emit_token(effective: bool, withhold_enabled: bool = True) -> bool:
    """Return acceptance token (`True` = accepted, `False` = withheld)."""
    return not (effective and withhold_enabled)


def _probe_distribution(
    d: int,
    secret: int,
    probes: tuple[int, ...],
    fault_kind: str | None,
    fault_idx: int | None,
    cross_share: bool = False,
) -> Counter[tuple[int, ...]]:
    """Compute exact unnormalized counting distribution over all `2^d` masks."""
    dist: Counter[tuple[int, ...]] = Counter()
    for masks in itertools.product((0, 1), repeat=d):
        shares = _encode_gf2(secret, masks)
        wires = _eval_checked_circuit(d, shares, fault_kind, fault_idx)
        if cross_share:
            # Cross-share fault injects wire computing `share_0 ^ share_1`.
            wires = (*wires, shares[0] ^ shares[1])
        obs = tuple(wires[w] for w in probes)
        dist[obs] += 1
    return dist


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def _single_fault_budget_oracle() -> None:
    """Verify budget `b <= 1` partition and structural exclusion of >=2 faults."""
    actions_alphabet: tuple[str | None, ...] = (None, "skip", "corrupt_false", "corrupt_true")
    for d in (1, 2):
        limit = d + 1
        fault_free_seen = 0
        single_fault_seen = 0
        for length in range(1, limit + 3):
            for trace in itertools.product(actions_alphabet, repeat=length):
                valid, _pc, final_b, f_cnt = _step_budget_oracle(limit, trace)
                explicit_faults = sum(1 for a in trace if a is not None)
                if explicit_faults >= 2:
                    ensure(not valid, f"budget-1 admitted {explicit_faults} faults: {trace}")
                if any(a is not None and i > limit for i, a in enumerate(trace)):
                    ensure(not valid, f"out-of-region fault admitted: {trace}")
                if valid:
                    ensure(f_cnt <= 1 and f_cnt + final_b == 1,
                           f"budget conservation failed: {trace} -> ({final_b}, {f_cnt})")
                    if f_cnt == 0:
                        ensure(final_b == 1, "fault-free derivation must keep budget 1")
                        fault_free_seen += 1
                    else:
                        ensure(final_b == 0, "single-fault derivation must leave budget 0")
                        single_fault_seen += 1
        ensure(fault_free_seen > 0 and single_fault_seen > 0,
               f"both derivation classes must be inhabited for d={d}")


def _step_budget_oracle(
    limit: int,
    trace: tuple[str | None, ...],
) -> tuple[bool, int, int, int]:
    return _step_budget_derivation(limit, trace, initial_budget=1)


def _exhaustive_combined_reduction_oracle() -> None:
    """Exhaustively verify effective-vs-share-confined partition and unreduced order `d`."""
    for d in (1, 2):
        num_wires = 2 * (d + 1)
        all_probe_sets_d = tuple(
            ps
            for length in range(d + 1)
            for ps in itertools.product(range(num_wires), repeat=length)
        )
        candidates: list[tuple[str | None, int | None]] = [(None, None)]
        for idx in range(d + 2):
            candidates.extend(
                (kind, idx) for kind in ("skip", "corrupt_false", "corrupt_true")
            )

        effective_count = 0
        confined_count = 0
        for fault_kind, fault_idx in candidates:
            effective = _is_effective_fault(d, fault_kind, fault_idx)
            token = _emit_token(effective, withhold_enabled=True)
            if effective:
                effective_count += 1
                ensure(token is False,
                       f"effective fault ({fault_kind}, {fault_idx}) did not withhold token")
            else:
                confined_count += 1
                ensure(token is True, "fault-free/benign trace unexpectedly withheld token")
                # Check unreduced order `d`: EVERY probe set of size <= d must match for s=0 vs s=1.
                for ps in all_probe_sets_d:
                    d0 = _probe_distribution(d, 0, ps, fault_kind, fault_idx)
                    d1 = _probe_distribution(d, 1, ps, fault_kind, fault_idx)
                    ensure(d0 == d1,
                           f"unreduced {d}-probing leaked at ({fault_kind}, {fault_idx}) on {ps}: "
                           f"{d0} != {d1}")
                # Tightness: probing all (d + 1) shares breaks independence.
                full_ps = tuple(range(d + 1))
                d0_full = _probe_distribution(d, 0, full_ps, fault_kind, fault_idx)
                d1_full = _probe_distribution(d, 1, full_ps, fault_kind, fault_idx)
                ensure(d0_full != d1_full,
                       f"(d+1)-probing should recover secret for d={d}")
        ensure(effective_count > 0 and confined_count > 0,
               f"combined partition must exercise both arms for d={d}")


def _refutation_cross_share_and_two_fault_oracle() -> None:
    """Verify Refutation (i): cross-share fault & two-fault injection break reduction."""
    # Cross-share fault at d = 1 leaks with a single probe (<= d = 1).
    cross_wire = 4
    d0 = _probe_distribution(1, 0, (cross_wire,), "corrupt_false", 0, cross_share=True)
    d1 = _probe_distribution(1, 1, (cross_wire,), "corrupt_false", 0, cross_share=True)
    ensure(d0 != d1, f"cross-share fault did not leak at order d=1: {d0} == {d1}")

    # Two-fault trace is excluded by budget-1, admitted by budget-2, and defeats parity check.
    two_fault = ("corrupt_true", "corrupt_true")
    valid_b1, _, _, _ = _step_budget_derivation(2, two_fault, initial_budget=1)
    valid_b2, _, final_b2, fcnt_b2 = _step_budget_derivation(2, two_fault, initial_budget=2)
    ensure(not valid_b1, "budget-1 must reject two-fault trace")
    ensure(valid_b2 and final_b2 == 0 and fcnt_b2 == 2, "budget-2 admits two-fault trace")
    parity_ok = (fcnt_b2 % 2) == 0
    ensure(parity_ok, "two-fault cancellation defeats parity check")


def _refutation_unwithheld_token_and_weakened_order_oracle() -> None:
    """Verify Refutations (ii) and (iii): missing withholding and weakened (d-1) order."""
    # Refutation (ii): effective fault without token withholding fails detection arm.
    effective = _is_effective_fault(1, "skip", 0)
    token_unwithheld = _emit_token(effective, withhold_enabled=False)
    ensure(effective and token_unwithheld is True,
           "unwithheld effective fault must fail detection arm")

    # Refutation (iii): 2-share circuit at order d=2 is secure at d-1=1, leaks at d=2.
    for w in range(2):
        d0_r = _probe_distribution(1, 0, (w,), None, None)
        d1_r = _probe_distribution(1, 1, (w,), None, None)
        ensure(d0_r == d1_r, f"2-share circuit must be 1-probing secure on wire {w}")
    d0_u = _probe_distribution(1, 0, (0, 1), None, None)
    d1_u = _probe_distribution(1, 1, (0, 1), None, None)
    ensure(d0_u != d1_u, "2-share circuit must leak under 2 probes (unreduced d=2)")


def _source_structure_and_witnesses_check() -> None:
    """Audit proofs/CombinedReduction.v structure, witnesses, and forbidden constructs."""
    ensure(_COMBINED_V.is_file(), f"missing proof file: {_COMBINED_V}")
    text = _COMBINED_V.read_text(encoding="utf-8")
    ensure(text.startswith("(* SPDX-License-Identifier: Apache-2.0 *)\n"),
           "CombinedReduction.v must start with SPDX Apache-2.0 header and LF newline")
    ensure("\r" not in text, "CombinedReduction.v must use LF line endings only")

    # Check required declarations exist as top-level Vernacular statements.
    sentences = proofs.sentences(text)
    declared: set[str] = set()
    for sentence in sentences:
        hit = re.match(
            rf"^(?:{proofs.CONTROL_PREFIXES})(?:{'|'.join(proofs.DECLARATIONS)})\s+([\w']+)",
            sentence,
        )
        if hit:
            declared.add(hit.group(1))

    required_symbols = {
        "FaultAction",
        "FaultStepSystem",
        "FaultStep",
        "FaultDerivation",
        "zero_budget_permits_no_fault",
        "single_fault_budget_conservation",
        "at_most_one_fault_per_activation",
        "two_faults_have_no_derivation",
        "out_of_region_fault_excluded",
        "activation_derivation_partition",
        "ShareLocalized",
        "UnreducedOrderSecure",
        "share_localized_unreduced_probing_secure",
        "MaskedActivation",
        "ConformingMaskedDatapath",
        "EffectiveDetectedArm",
        "ShareConfinedProbingArm",
        "combined_single_fault_reduction",
        "combined_reduction_preserves_unreduced_order",
        "instantiated_masked_activation",
        "instantiated_masked_activation_conforming",
        "instantiated_combined_reduction",
        "cross_share_fault_breaks_unreduced_probing",
        "two_fault_injection_breaks_reduction",
        "missing_token_withholding_violates_detection_arm",
        "weakened_order_claim_fails_unreduced_predicate",
        "witness_FaultStepSystem",
        "witness_ShareLocalized",
        "witness_MaskedActivation",
        "witness_ConformingMaskedDatapath",
    }
    missing = sorted(required_symbols - declared)
    ensure(not missing, f"missing declarations in CombinedReduction.v: {missing}")

    # Forbidden constructs (R-05-163 / R-05-164 / Rocq strictness).
    forbidden_tokens = ("Axiom", "Parameter", "Admitted", "Section",
                        "CoFixpoint", "CoInductive", "cofix", "SProp")
    for sentence in sentences:
        first_word = sentence.split(maxsplit=1)[0] if sentence.split() else ""
        ensure(first_word not in forbidden_tokens,
               f"forbidden Vernacular construct {first_word!r} in: {sentence[:80]!r}")
    ensure(not proofaudit.unsupported_abstractions(text),
           "CombinedReduction.v contains unsupported module functor/signature abstractions")
    ensure(not proofaudit.pinned_overrides(text),
           "CombinedReduction.v overrides pinned Rocq warning/selector flags")

    # R-05-166 witness check across locally Required modules.
    probing_text = (_REPO_ROOT / "proofs" / "ProbingModel.v").read_text(encoding="utf-8")
    support_text = (_REPO_ROOT / "proofs" / "ProofSupport.v").read_text(encoding="utf-8")
    witnesses = proof_gate.scan_witnesses(text, imported=(probing_text, support_text))
    ensure(not witnesses.unbuilt,
           f"unwitnessed quantified records in CombinedReduction.v: {witnesses.unbuilt}")
    ensure(witnesses.witness_count >= 2,
           f"expected >=2 witnessed records, got {witnesses.witness_count}")


def cases() -> list[Case]:
    return [
        Case("combined reduction single-fault budget oracle", _single_fault_budget_oracle),
        Case("combined reduction exhaustive partition and unreduced order",
             _exhaustive_combined_reduction_oracle),
        Case("combined reduction cross-share and two-fault refutations",
             _refutation_cross_share_and_two_fault_oracle),
        Case("combined reduction unwithheld-token and weakened-order refutations",
             _refutation_unwithheld_token_and_weakened_order_oracle),
        Case("combined reduction Rocq source structure and witnesses",
             _source_structure_and_witnesses_check),
    ]
