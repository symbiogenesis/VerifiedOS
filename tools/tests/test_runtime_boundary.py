# SPDX-License-Identifier: Apache-2.0
"""Behavioral, source-inventory, seeded-defect, and proof-structure tests for Q47."""

import re
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import corpus as corpus_mod
from vos import proofaudit, proofcites
from vos import proofs as proofs_mod
from vos import runtime_boundary as rb
from vos.register import read_register

INDEPENDENT_CASES = True

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _live_source_inventory() -> None:
    inv = rb.scan_boundary_inventory(_REPO_ROOT)
    ensure(inv["exact_native_acceptance"] is False,
           "host-source boundary scan must never claim exact_native_acceptance")
    ensure(inv["production_admission"] is False,
           "host-source boundary scan must never claim production_admission")
    ensure(inv["components_scanned"] == list(rb.ACTIVE_TARGET_COMPONENTS),
           f"unexpected scanned component list: {inv['components_scanned']!r}")
    ensure(inv["forbidden_symbol_findings"] == [],
           f"unexpected forbidden unwind/runtime symbols in active target C: "
           f"{inv['forbidden_symbol_findings']!r}")
    ensure(len(inv["exported_declarations"]) > 50,
           f"expected rich exported boundary census, got {len(inv['exported_declarations'])}")
    ensure(len(inv["callback_boundaries"]) >= 5,
           f"expected real callback boundaries (router/storage/supervisor), got "
           f"{len(inv['callback_boundaries'])}")
    ensure(len(inv["mutable_state_boundaries"]) >= 30,
           f"expected mutable state boundaries, got {len(inv['mutable_state_boundaries'])}")

    # Verify harness exclusions are actually discovered and excluded from target scan.
    excluded = [
        path
        for comp in inv["components"]
        for path in comp["excluded_harness_files"]
    ]
    ensure(any("/test/" in p or "/host/" in p for p in excluded),
           "expected test/ and host/ harnesses to be recorded as excluded")
    target_srcs = [
        path
        for comp in inv["components"]
        for path in comp["target_sources"]
    ]
    ensure(not any("/test/" in p or "/host/" in p for p in target_srcs),
           "test/ or host/ harness leaked into target source list")


def _optional_component_graceful() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-q47-opt-") as td:
        root = Path(td)
        for comp in rb.ACTIVE_TARGET_COMPONENTS:
            (root / comp / "include").mkdir(parents=True, exist_ok=True)
            (root / comp / "src").mkdir(parents=True, exist_ok=True)
            (root / comp / "include" / "stub.h").write_text(
                "int stub_op(int *out);\n", encoding="utf-8", newline=""
            )
            (root / comp / "src" / "stub.c").write_text(
                "int stub_op(int *out) { *out = 1; return 0; }\n",
                encoding="utf-8",
                newline="",
            )
        inv_without = rb.scan_boundary_inventory(root)
        ensure(inv_without["components_absent_optional"] == list(rb.OPTIONAL_TARGET_COMPONENTS),
               f"absent optional components not recorded: {inv_without['components_absent_optional']!r}")

        # Now add an optional component (`attested-tls`) and ensure it is scanned dynamically.
        (root / "attested-tls" / "include").mkdir(parents=True, exist_ok=True)
        (root / "attested-tls" / "src").mkdir(parents=True, exist_ok=True)
        (root / "attested-tls" / "include" / "tls.h").write_text(
            "int vos_tls_handshake(void (*cb)(void *), void *ctx);\n",
            encoding="utf-8",
            newline="",
        )
        (root / "attested-tls" / "src" / "tls.c").write_text(
            "int vos_tls_handshake(void (*cb)(void *), void *ctx) { if (cb) cb(ctx); return 0; }\n",
            encoding="utf-8",
            newline="",
        )
        inv_with = rb.scan_boundary_inventory(root)
        ensure("attested-tls" in inv_with["components_scanned"],
               "present optional component `attested-tls` was not scanned")
        ensure("attested-tls" not in inv_with["components_absent_optional"],
               "present optional component still listed as absent")
        ensure(any(d["name"] == "vos_tls_handshake" for d in inv_with["callback_boundaries"]),
               "callback boundary in optional component was not extracted")


def _adversarial_controls_pass() -> None:
    verdicts = rb.run_adversarial_controls()
    ensure(len(verdicts) >= 12, f"expected >= 12 adversarial controls, got {len(verdicts)}")
    failed = [v for v in verdicts if not v.passed]
    ensure(not failed, f"adversarial Q47 control(s) failed: {failed!r}")


def _seeded_defects_killed() -> None:
    report = rb.run_seeded_defect_matrix()
    ensure(report["total_mutants"] == 23,
           f"expected 23 seeded mutants (6 callback + 4 teardown + 13 symbols), "
           f"got {report['total_mutants']}")
    ensure(report["stillborn_mutants"] == 0,
           f"unexpected stillborn mutants: {report['stillborn_mutants']}")
    ensure(report["survivors"] == [],
           f"seeded defect survivor(s): {report['survivors']!r}")
    ensure(report["executed_kills"] == report["total_mutants"],
           f"not all seeded defects were killed: {report!r}")


def _scalar_signal_var_not_false_positive() -> None:
    # Target C files use local/parameter `uint32_t *signal` / `uint32_t signal = 0;`;
    # the scanner must accept scalar variables while catching `signal(...)` calls and `<signal.h>`.
    clean = (
        "void helper(uint32_t *signal) {\n"
        "    uint32_t local = 0;\n"
        "    *signal = local;\n"
        "}\n"
    )
    ensure(rb.scan_c_for_forbidden_symbols("copy-service", "copy-service/src/ok.c", clean) == [],
           "scalar parameter named `signal` triggered a false positive")

    injected_call = "void bad(void (*h)(int)) { signal(2, h); }\n"
    findings = rb.scan_c_for_forbidden_symbols("copy-service", "copy-service/src/bad.c", injected_call)
    ensure(any(f["symbol"] == "signal" for f in findings),
           "injected `signal(...)` call was not detected")

    injected_malloc = "void *bad(unsigned n) { return malloc(n); }\n"
    m_findings = rb.scan_c_for_forbidden_symbols("pool", "pool/src/bad.c", injected_malloc)
    ensure(any(f["symbol"] == "malloc" for f in m_findings),
           "injected `malloc(...)` call was not detected")


def _proof_structural_audit() -> None:
    proof_path = _REPO_ROOT / "proofs" / "RuntimeBoundary.v"
    text = proof_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    ensure(bool(lines) and lines[0] == "(* SPDX-License-Identifier: Apache-2.0 *)",
           "RuntimeBoundary.v must open with SPDX Apache-2.0 on line 1")
    ensure(bool(re.search(r"\(\* ={3,}\r?\n", text)),
           "RuntimeBoundary.v must open with a ruled header comment")

    # No forbidden Rocq constructs
    ensure(proofaudit.coinductive_forms(text) == [],
           "RuntimeBoundary.v must contain no coinductive/cofix forms")
    ensure(proofaudit.pinned_overrides(text) == [],
           "RuntimeBoundary.v must contain no pinned setting overrides or Timeout/AllocLimit")
    ensure(proofaudit.dynamic_sources(text) == [],
           "RuntimeBoundary.v must contain no dynamic source loading")
    for forbidden in ("Section", "Axiom", "Parameter", "Admitted", "SProp"):
        ensure(re.search(rf"\b{forbidden}\b", text) is None,
               f"RuntimeBoundary.v contains forbidden keyword `{forbidden}`")

    # Every Record/Structure must have a closed `Definition witness_<R> : <R> :=`
    records = re.findall(r"(?m)^(?:Record|Structure)\s+([A-Za-z_][A-Za-z0-9_']*)\b", text)
    ensure(len(records) >= 6, f"expected >= 6 declared Records, got {records!r}")
    for rec in records:
        ensure(re.search(rf"(?m)^Definition\s+witness_{re.escape(rec)}\s*:\s*{re.escape(rec)}\s*:=", text) is not None,
               f"missing `Definition witness_{rec} : {rec} := ...` (R-05-166)")

    # Every Proof. must close with Qed. or Defined.
    stmts = proofs_mod.sentences(text)
    proof_starts = sum(1 for s in stmts if s == "Proof")
    proof_ends = sum(1 for s in stmts if s in {"Qed", "Defined"})
    ensure(proof_starts > 0 and proof_starts == proof_ends,
           f"Proof/Qed mismatch: {proof_starts} Proof. vs {proof_ends} Qed./Defined.")

    # Every requirement cited outside derived blocks must be live in the register.
    reg = read_register(corpus_mod.load(_REPO_ROOT))
    cited = set(proofcites.ids(text))
    ensure(bool(cited), "RuntimeBoundary.v cites no requirement IDs")
    unknown = sorted(cited - reg.id_set)
    ensure(not unknown, f"RuntimeBoundary.v cites unknown requirement IDs: {unknown!r}")


def cases() -> list[Case]:
    return [
        Case("live_source_inventory", _live_source_inventory),
        Case("optional_component_graceful", _optional_component_graceful),
        Case("adversarial_controls_pass", _adversarial_controls_pass),
        Case("seeded_defects_killed", _seeded_defects_killed),
        Case("scalar_signal_var_not_false_positive", _scalar_signal_var_not_false_positive),
        Case("proof_structural_audit", _proof_structural_audit),
    ]
