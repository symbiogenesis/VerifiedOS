# SPDX-License-Identifier: Apache-2.0
"""Hand-counted observation boundaries and refusal controls for churn accounting."""

import json
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from hashlib import sha256
from io import BytesIO, StringIO, TextIOWrapper
from itertools import combinations, product
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tests.harness import Case, ensure
from vos.allocation_churn import SCOPE, ExpectedIdentity, analyze, expected_identity
from vos.cli import allocation_churn as cli
from vos.jsonc import Json


def _capture() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "identity": {"roster_revision": "a" * 40, "image_sha256": "b" * 64,
                     "composition_sha256": "c" * 64},
        "complete": True,
        "window": {"start_tick": 0, "end_tick": 30, "tick_hz": 100},
        "domains": [{"id": "kernel-0", "period_ticks": 10,
                     "background_ticks_per_period": 4, "quarantine_capacity_bytes": 10}],
        "teardowns": [
            {"id": "a", "domain": "kernel-0", "retire_tick": 2, "reuse_tick": 8,
             "swept_capability_bytes": 16, "quarantined_bytes": 6},
            {"id": "b", "domain": "kernel-0", "retire_tick": 5, "reuse_tick": 10,
             "swept_capability_bytes": 8, "quarantined_bytes": 4},
            {"id": "c", "domain": "kernel-0", "retire_tick": 10, "reuse_tick": 20,
             "swept_capability_bytes": 0, "quarantined_bytes": 10},
        ],
        "sweep_quanta": [
            {"domain": "kernel-0", "start_tick": 2, "end_tick": 4},
            {"domain": "kernel-0", "start_tick": 8, "end_tick": 10},
            {"domain": "kernel-0", "start_tick": 12, "end_tick": 16},
            {"domain": "kernel-0", "start_tick": 22, "end_tick": 25},
        ],
    }


def _expected(raw: bytes) -> ExpectedIdentity:
    return ExpectedIdentity("a" * 40, "b" * 64, "c" * 64, sha256(raw).hexdigest())


def _report(capture: dict[str, Any]) -> dict[str, Json]:
    raw = json.dumps(capture).encode("utf-8")
    return analyze(raw, _expected(raw))


def _object(value: Json) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise TypeError("expected a report object")
    return value


def _domain(report: dict[str, Json], index: int = 0) -> dict[str, Json]:
    rows = report["domains"]
    if not isinstance(rows, list):
        raise TypeError("expected domain report rows")
    return _object(rows[index])


def _refused(raw: bytes, expected: ExpectedIdentity | None = None) -> None:
    try:
        analyze(raw, _expected(raw) if expected is None else expected)
    except (TypeError, ValueError) as err:
        ensure(bool(str(err)), "a refused capture needs a diagnostic")
    else:
        raise AssertionError("malformed or mismatched capture was accepted")


def _hand_counted_boundaries() -> None:
    report = _report(_capture())
    totals, domain = _object(report["totals"]), _domain(report)
    ensure(report["within_declared_limits"] is True, "equality at both budgets must pass")
    ensure(totals["teardown_count"] == 3, "three kernel teardown records")
    ensure(totals["teardowns_per_second"] == {"numerator": 10, "denominator": 1},
           "three teardowns in 0.3 seconds")
    ensure(totals["swept_capability_bytes_total"] == 24
           and totals["swept_capability_bytes_mean"] == {"numerator": 8, "denominator": 1}
           and totals["swept_capability_bytes_max"] == 16, "attributed bytes are 16, 8, 0")
    ensure(domain["quarantine_peak_bytes"] == 10 and domain["quarantine_margin_bytes"] == 0,
           "overlap is 6+4; the ten-byte retirement at tick 10 follows release")
    ensure(domain["sweep_ticks_total"] == 11 and domain["sweep_ticks_peak_per_period"] == 4
           and domain["background_margin_ticks"] == 0, "period service is 4, 4, 3 ticks")
    ensure(report["scope"] == SCOPE and report["milestone_acceptance"] == "open",
           "within-budget observations must not close target acceptance")


def _zero_activity_and_fractional_rates() -> None:
    capture = _capture()
    capture["teardowns"] = []
    capture["sweep_quanta"] = []
    report = _report(capture)
    ensure(report["within_declared_limits"] is True, "declared zero activity is valid")
    totals = _object(report["totals"])
    ensure(totals["teardown_count"] == 0 and totals["quarantine_peak_bytes"] == 0
           and totals["swept_capability_bytes_mean"] is None, "no teardown has no mean footprint")
    capture = _capture()
    capture["teardowns"] = capture["teardowns"][:1]
    ensure(_object(_report(capture)["totals"])["teardowns_per_second"]
           == {"numerator": 10, "denominator": 3}, "rates retain the exact third")


def _period_spanning_quanta() -> None:
    capture = _capture()
    capture["teardowns"] = []
    capture["domains"][0]["background_ticks_per_period"] = 2
    capture["sweep_quanta"] = [{"domain": "kernel-0", "start_tick": 8, "end_tick": 12}]
    report = _report(capture)
    ensure(report["within_declared_limits"] is True
           and _domain(report)["sweep_ticks_total"] == 4
           and _domain(report)["sweep_ticks_peak_per_period"] == 2,
           "the boundary splits four ticks into two and two")
    capture["domains"][0]["background_ticks_per_period"] = 10
    capture["sweep_quanta"] = [{"domain": "kernel-0", "start_tick": 8, "end_tick": 22}]
    domain = _domain(_report(capture))
    ensure(domain["sweep_ticks_total"] == 14 and domain["sweep_ticks_peak_per_period"] == 10,
           "two partial periods surround one full ten-tick period")
    capture["window"] = {"start_tick": 10**30, "end_tick": 2 * 10**30, "tick_hz": 1}
    capture["sweep_quanta"] = [{"domain": "kernel-0", "start_tick": 10**30,
                                 "end_tick": 2 * 10**30}]
    ensure(_domain(_report(capture))["sweep_ticks_peak_per_period"] == 10,
           "large coordinates require no expansion of the elapsed window")


def _budget_excess() -> None:
    capture = _capture()
    capture["domains"][0]["quarantine_capacity_bytes"] = 9
    report = _report(capture)
    ensure(report["within_declared_limits"] is False
           and _domain(report)["quarantine_margin_bytes"] == -1,
           "a one-byte excess is a capacity finding")
    capture = _capture()
    capture["sweep_quanta"] = [{"domain": "kernel-0", "start_tick": 2, "end_tick": 7}]
    report = _report(capture)
    ensure(report["within_declared_limits"] is False
           and _domain(report)["sweep_ticks_total"] == 5
           and _domain(report)["background_margin_ticks"] == -1,
           "five ticks exceed one period's four despite twelve ticks in the whole window")


def _independent_domain_pools() -> None:
    capture = _capture()
    capture["domains"].append({"id": "kernel-1", "period_ticks": 15,
                               "background_ticks_per_period": 1, "quarantine_capacity_bytes": 2})
    capture["teardowns"].append({"id": "d", "domain": "kernel-1", "retire_tick": 21,
                                 "reuse_tick": 30, "swept_capability_bytes": 0,
                                 "quarantined_bytes": 2})
    report = _report(capture)
    ensure(report["within_declared_limits"] is True
           and _domain(report, 1)["quarantine_peak_bytes"] == 2
           and _object(report["totals"])["quarantine_peak_bytes"] == 10,
           "different-time pool peaks are not added into an invented simultaneous peak")


def _six_tick_capture() -> dict[str, Any]:
    capture = _capture()
    capture["window"]["end_tick"] = 6
    capture["domains"] = [
        {"id": "kernel-0", "period_ticks": 2,
         "background_ticks_per_period": 1, "quarantine_capacity_bytes": 2},
        {"id": "kernel-1", "period_ticks": 3,
         "background_ticks_per_period": 1, "quarantine_capacity_bytes": 3},
    ]
    capture["teardowns"] = []
    capture["sweep_quanta"] = []
    return capture


def _generated_quarantine_accounting() -> None:
    # A finite tick oracle is independent of the analyzer's endpoint-delta scan.
    # Enumerate every pair of positive intervals, including unordered retirements,
    # simultaneous release/retire boundaries and overlapping independent pools.
    intervals = tuple(combinations(range(7), 2))
    for left, right in product(intervals, repeat=2):
        capture = _six_tick_capture()
        rows: list[dict[str, Any]] = [
            {"id": name, "domain": domain, "retire_tick": interval[0],
             "reuse_tick": interval[1], "swept_capability_bytes": 0,
             "quarantined_bytes": amount}
            for name, domain, interval, amount in (
                ("a", "kernel-0", left, 1), ("b", "kernel-0", right, 2),
                ("c", "kernel-1", (1, 5), 3))
        ]
        capture["teardowns"] = list(reversed(rows))
        report = _report(capture)
        peaks = {
            domain: max(sum(row["quarantined_bytes"] for row in rows
                            if (domain is None or row["domain"] == domain)
                            and row["retire_tick"] <= tick < row["reuse_tick"])
                        for tick in range(6))
            for domain in (None, "kernel-0", "kernel-1")
        }
        ensure(_object(report["totals"])["quarantine_peak_bytes"] == peaks[None],
               f"{left}, {right}: simultaneous total agrees with the tick oracle")
        for index, domain in enumerate(capture["domains"]):
            observed = _domain(report, index)
            peak = peaks[domain["id"]]
            ensure(observed["quarantine_peak_bytes"] == peak
                   and observed["quarantine_margin_bytes"]
                   == domain["quarantine_capacity_bytes"] - peak,
                   f"{left}, {right}: each pool keeps its own peak and margin")
        ensure(report["within_declared_limits"] == (peaks["kernel-0"] <= 2),
               f"{left}, {right}: only a domain's own capacity decides its limit")


def _generated_period_accounting() -> None:
    # Every six-tick pattern meets identical, alternating and complementary
    # activity in the other domain, without a redundant full Cartesian sweep.
    # One domain coalesces busy ticks into quanta; the other leaves them adjacent.
    # Direct tick counting checks both against their different period boundaries.
    for left, flip in product(range(1 << 6), (0, 0b010101, 0b111111)):
        right = left ^ flip
        capture = _six_tick_capture()
        expected_peaks: list[int] = []
        expected_totals: list[int] = []
        for index, (mask, period) in enumerate(((left, 2), (right, 3))):
            busy = [bool(mask & (1 << tick)) for tick in range(6)]
            expected_peaks.append(max(sum(busy[start:start + period])
                                      for start in range(0, 6, period)))
            expected_totals.append(sum(busy))
            for tick, active in enumerate(busy):
                if not active:
                    continue
                quanta = capture["sweep_quanta"]
                if index == 0 and tick and busy[tick - 1]:
                    quanta[-1]["end_tick"] = tick + 1
                else:
                    quanta.append({"domain": f"kernel-{index}",
                                   "start_tick": tick, "end_tick": tick + 1})
        capture["sweep_quanta"].reverse()
        report = _report(capture)
        for index, peak in enumerate(expected_peaks):
            domain = _domain(report, index)
            ensure(domain["sweep_ticks_total"] == expected_totals[index]
                   and domain["sweep_ticks_peak_per_period"] == peak
                   and domain["background_margin_ticks"] == 1 - peak,
                   f"{left}, {right}, domain {index}: service agrees with the tick oracle")
        ensure(report["within_declared_limits"] == (max(expected_peaks) <= 1),
               f"{left}, {right}: every period's reservation decides the verdict")


def _malformed_records() -> None:
    changes: list[tuple[str, str, object]] = [
        ("capture", "complete", False), ("capture", "schema_version", True),
        ("capture", "accepted", True), ("capture", "domains", []),
        ("capture", "teardowns", None),
        ("capture", "sweep_quanta", []), ("window", "tick_hz", 0),
        ("window", "start_tick", 1), ("window", "end_tick", 0),
        ("domain", "id", ""), ("domain", "period_ticks", -1),
        ("domain", "background_ticks_per_period", 0),
        ("domain", "background_ticks_per_period", 11),
        ("domain", "quarantine_capacity_bytes", 0),
        ("teardown", "reuse_tick", None), ("teardown", "reuse_tick", 31),
        ("teardown", "reuse_tick", 2), ("teardown", "retire_tick", 30),
        ("teardown", "domain", "missing"), ("teardown", "quarantined_bytes", True),
        ("teardown", "swept_capability_bytes", 1.0),
        ("quantum", "domain", "missing"), ("quantum", "end_tick", 2),
        ("quantum", "end_tick", 31),
    ]
    for section, field, value in changes:
        capture = _capture()
        rows = {"capture": capture, "window": capture["window"],
                "domain": capture["domains"][0], "teardown": capture["teardowns"][0],
                "quantum": capture["sweep_quanta"][0]}
        rows[section][field] = value
        _refused(json.dumps(capture).encode("utf-8"))
    for group in ("domains", "teardowns", "sweep_quanta"):
        capture = _capture()
        capture[group].append(capture[group][0])
        _refused(json.dumps(capture).encode("utf-8"))
    capture = _capture()
    del capture["teardowns"][0]["reuse_tick"]
    _refused(json.dumps(capture).encode("utf-8"))
    raw = json.dumps(_capture()).encode("utf-8")
    _refused(raw.replace(b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1'))
    for raw in (b'{"number":NaN}', b'\xff', b'{', b'[' * 2000 + b'0' + b']' * 2000):
        _refused(raw)


def _independent_identity_and_raw_bytes() -> None:
    raw = json.dumps(_capture()).encode("utf-8")
    expected = _expected(raw)
    for field, value in (("roster_revision", "d" * 40), ("image_sha256", "d" * 64),
                         ("composition_sha256", "d" * 64), ("capture_sha256", "d" * 64)):
        _refused(raw, replace(expected, **{field: value}))
    _refused(raw + b"\n", expected)
    ensure(expected_identity(json.dumps(asdict(expected)).encode("utf-8")) == expected,
           "the independent descriptor preserves all four identities")


def _cli_verdicts() -> None:
    with TemporaryDirectory(prefix="vos-churn-") as directory:
        root = Path(directory).resolve()
        capture_path, expected_path = root / "capture.json", root / "expected.json"
        for budget, code in ((4, 0), (3, 1)):
            capture = _capture()
            capture["domains"][0]["background_ticks_per_period"] = budget
            raw = json.dumps(capture).encode("utf-8")
            capture_path.write_bytes(raw)
            expected_path.write_text(json.dumps(asdict(_expected(raw))), encoding="utf-8", newline="")
            output = StringIO()
            with redirect_stdout(output):
                actual = cli.main([str(capture_path), "--expected-identity", str(expected_path), "--json"])
            report = json.loads(output.getvalue())
            ensure(actual == code and report["milestone_acceptance"] == "open",
                   "CLI distinguishes observations within and beyond budgets")
            ensure(len(report["sources_sha256"]) == 3
                   and report["identity"]["capture_sha256"] == sha256(raw).hexdigest(),
                   "report binds capture and implementation inputs")
        capture_path.write_bytes(raw + b"\n")
        for flags in ([], ["--json"]):
            output = StringIO()
            with redirect_stdout(output):
                actual = cli.main([str(capture_path), "--expected-identity", str(expected_path), *flags])
            ensure(actual == 2 and "capture" in output.getvalue(),
                   "both renderings diagnose mismatched input without crashing")


def _cli_escaped_diagnostics() -> None:
    # JSON can carry escaped lone surrogates; valid identifiers retain their
    # semantics, while refusal diagnostics must survive strict UTF-8 output.
    with TemporaryDirectory(prefix="vos-churn-unicode-") as directory:
        root = Path(directory).resolve()
        capture_path, expected_path = root / "capture.json", root / "expected.json"
        for defect in ("none", "duplicate-key", "duplicate-domain", "unaligned-window",
                       "duplicate-teardown", "invalid-teardown", "overlap", "absent-service"):
            capture = _capture()
            capture["domains"][0]["id"] = "kernel-\ud800"
            for row in [*capture["teardowns"], *capture["sweep_quanta"]]:
                row["domain"] = "kernel-\ud800"
            capture["teardowns"][0]["id"] = "teardown-\ud800"
            if defect == "duplicate-domain":
                capture["domains"].append(capture["domains"][0])
            elif defect == "unaligned-window":
                capture["window"]["start_tick"] = 1
            elif defect == "duplicate-teardown":
                capture["teardowns"].append(capture["teardowns"][0])
            elif defect == "invalid-teardown":
                capture["teardowns"][0]["reuse_tick"] = 0
            elif defect == "overlap":
                capture["sweep_quanta"].append(capture["sweep_quanta"][0])
            elif defect == "absent-service":
                capture["sweep_quanta"] = []
            raw = json.dumps(capture).encode("utf-8")
            if defect == "duplicate-key":
                raw = b'{"\\ud800": 0, "\\ud800": 0, ' + raw[1:]
            capture_path.write_bytes(raw)
            expected_path.write_text(json.dumps(asdict(_expected(raw))), encoding="utf-8", newline="")
            for flags in ([], ["--json"]):
                buffer = BytesIO()
                with TextIOWrapper(buffer, encoding="utf-8", errors="strict") as output:
                    with redirect_stdout(output):
                        actual = cli.main([str(capture_path), "--expected-identity",
                                           str(expected_path), *flags])
                    output.flush()
                    rendered = buffer.getvalue().decode("utf-8")
                ensure(actual == (0 if defect == "none" else 2),
                       f"{defect}: UTF-8 diagnostics preserve the capture verdict")
                ensure("\\ud800" in rendered, f"{defect}: output escapes the lone surrogate")
                if flags:
                    report = json.loads(rendered)
                    ensure(report["milestone_acceptance"] == "open"
                           and (defect == "none" or isinstance(report["error"], str)),
                           f"{defect}: JSON retains a structured verdict")


def cases() -> list[Case]:
    return [Case("hand-counted-boundaries", _hand_counted_boundaries),
            Case("zero-and-exact-rates", _zero_activity_and_fractional_rates),
            Case("period-spanning-quanta", _period_spanning_quanta),
            Case("budget-excess", _budget_excess),
            Case("independent-domain-pools", _independent_domain_pools),
            Case("generated-quarantine-accounting", _generated_quarantine_accounting),
            Case("generated-period-accounting", _generated_period_accounting),
            Case("malformed-records", _malformed_records),
            Case("identity-and-raw-bytes", _independent_identity_and_raw_bytes),
            Case("cli-verdicts", _cli_verdicts),
            Case("cli-escaped-diagnostics", _cli_escaped_diagnostics)]
