# SPDX-License-Identifier: Apache-2.0
"""Generated boundaries and refusal controls for the matrix comparison instrument."""

import copy
import hashlib
import json
import tempfile
from contextlib import redirect_stdout
from fractions import Fraction
from io import StringIO
from pathlib import Path

from tests.harness import Case, ensure
from vos.cli import matrix_margin as cli
from vos.jsonc import Json
from vos.matrix_margin import compare


def _blob(value: object) -> bytes:
    return json.dumps(value).encode()


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _fixture() -> tuple[dict[str, Json], dict[str, Json]]:
    planned: list[Json] = []
    measured: list[Json] = []
    for dtype in ("int8", "bf16"):
        workload, output = _hash(dtype.encode()), _hash((dtype + "-output").encode())
        planned.append({"id": dtype, "dtype": dtype, "workload_sha256": workload,
                        "output_sha256": output})
        arms: dict[str, Json] = {
            name: {"ticks": ticks, "energy_quanta": energy, "output_sha256": output,
                   "receipt_sha256": _hash((dtype + name).encode())}
            for name, ticks, energy in (("rvv", 100, 110), ("matrix", 10, 10))}
        measured.append({"id": dtype, "workload_sha256": workload, **arms})
    plan: dict[str, Json] = {"schema": "matrix-margin-plan-v1",
                             "configuration_sha256": _hash(b"fixture-config"),
                             "protocol_sha256": _hash(b"fixture-protocol"),
                             "rvv_extensions": ["V", "fixture-dot"], "cases": planned}
    report: dict[str, Json] = {"schema": "matrix-margin-report-v1",
                               "configuration_sha256": plan["configuration_sha256"],
                               "plan_sha256": _hash(_blob(plan)),
                               "rvv_extensions": ["V", "fixture-dot"], "cases": measured}
    return plan, report


def _row(document: dict[str, Json], index: int = 0) -> dict[str, Json]:
    rows = document["cases"]
    if not isinstance(rows, list):
        raise TypeError("fixture case shape")
    row = rows[index]
    if not isinstance(row, dict):
        raise TypeError("fixture case shape")
    return row


def _arm(document: dict[str, Json], name: str = "rvv", index: int = 0) -> dict[str, Json]:
    value = _row(document, index)[name]
    if not isinstance(value, dict):
        raise TypeError("fixture arm shape")
    return value


def _refused(plan: bytes, report: bytes) -> None:
    try:
        compare(plan, report)
    except ValueError:
        return
    raise AssertionError("invalid comparison accepted")


def _boundaries() -> None:
    plan, report = _fixture()
    for ticks in range(1, 121):
        for energy in (ticks - 1, ticks, ticks + 1):
            if energy == 0:
                continue
            _arm(report)["ticks"] = ticks
            _arm(report)["energy_quanta"] = energy
            result = compare(_blob(plan), _blob(report))
            expected = "below-band" if ticks < 80 else "review-band" if ticks < 100 else "clears-band"
            ensure(result.band == expected, "one failing case must govern the band")
            ensure(result.cases[0].throughput == str(Fraction(ticks, 10)), "exact throughput")
            ensure(result.cases[0].per_watt == str(Fraction(energy, 10)), "exact per-watt")
            ensure(result.wider_per_watt == (energy > ticks), "strictly wider energy margin")
    # Ratios immediately below either boundary must not round up, even at u64 scale.
    divisor = (2**64 - 1) // 12
    for threshold, expected in ((8, "below-band"), (10, "review-band")):
        _arm(report)["ticks"] = threshold * divisor - 1
        _arm(report, "matrix")["ticks"] = divisor
        ensure(compare(_blob(plan), _blob(report)).band == expected, "no floating-point rounding")
    _arm(report)["ticks"] = 100
    _arm(report, "matrix")["ticks"] = 10
    _arm(report)["energy_quanta"] = 110
    _arm(report, index=1)["ticks"] = 79
    ensure(compare(_blob(plan), _blob(report)).band == "below-band", "bf16 failure is not averaged away")


def _bindings() -> None:
    plan, report = _fixture()
    result = compare(_blob(plan), _blob(report))
    ensure(result.band == "clears-band" and result.wider_per_watt, "positive comparison")
    report["rvv_extensions"] = ["fixture-dot", "V"]
    ensure(compare(_blob(plan), _blob(report)).rvv_extensions == ("V", "fixture-dot"), "set ordering")
    for field in ("plan_sha256", "configuration_sha256"):
        bad = copy.deepcopy(report)
        bad[field] = _hash(b"changed")
        _refused(_blob(plan), _blob(bad))
    for extensions in (["V"], ["V", "fixture-dot", "extra"], ["V", "V"], [], [""]):
        bad = copy.deepcopy(report)
        bad["rvv_extensions"] = list(extensions)
        _refused(_blob(plan), _blob(bad))
    _refused(_blob(plan) + b"\n", _blob(report))
    for index in (0, 1):
        bad = copy.deepcopy(report)
        _row(bad, index)["workload_sha256"] = _hash(b"different-work")
        _refused(_blob(plan), _blob(bad))
        for name in ("rvv", "matrix"):
            bad = copy.deepcopy(report)
            _arm(bad, name, index)["output_sha256"] = _hash(b"wrong-output")
            _refused(_blob(plan), _blob(bad))
        bad = copy.deepcopy(report)
        _arm(bad, "matrix", index)["receipt_sha256"] = _arm(bad, "rvv", index)["receipt_sha256"]
        _refused(_blob(plan), _blob(bad))


def _shapes() -> None:
    plan, report = _fixture()
    for target in ("plan", "report"):
        document = plan if target == "plan" else report
        for index, original in enumerate(_objects(document, target)):
            for field in (*original, "unexpected"):
                changed = copy.deepcopy(document)
                row = _objects(changed, target)[index]
                if field == "unexpected":
                    row[field] = "unknown"
                else:
                    del row[field]
                paired = copy.deepcopy(report)
                if target == "plan":
                    paired["plan_sha256"] = _hash(_blob(changed))
                    _refused(_blob(changed), _blob(paired))
                else:
                    _refused(_blob(plan), _blob(changed))
    for cases_value in ([], [_row(report)], [_row(report), _row(report)],
                        [_row(report), _row(report, 1), {**_row(report), "id": "extra"}]):
        bad = copy.deepcopy(report)
        bad["cases"] = list(cases_value)
        _refused(_blob(plan), _blob(bad))
    for dtype in ("fp32", "int8"):
        bad_plan = copy.deepcopy(plan)
        _row(bad_plan, 1)["dtype"] = dtype
        report["plan_sha256"] = _hash(_blob(bad_plan))
        _refused(_blob(bad_plan), _blob(report))


def _objects(document: dict[str, Json], target: str) -> list[dict[str, Json]]:
    result = [document, _row(document)]
    if target == "report":
        result.extend([_arm(document), _arm(document, "matrix")])
    return result


def _invalid_numbers_and_json() -> None:
    plan, report = _fixture()
    for name in ("rvv", "matrix"):
        for field in ("ticks", "energy_quanta"):
            for value in (0, -1, True, False, 1.0, "100", None, 2**64):
                bad = copy.deepcopy(report)
                _arm(bad, name)[field] = value
                _refused(_blob(plan), _blob(bad))
    for field in ("output_sha256", "receipt_sha256"):
        for value in ("", "A" * 64, "0" * 63, None):
            bad = copy.deepcopy(report)
            _arm(bad)[field] = value
            _refused(_blob(plan), _blob(bad))
    for blob in (b"", b"[]", b"null", b"{", b"\xff", _blob(report)[:-1],
                 _blob(report).replace(b'"ticks": 100', b'"ticks": 100, "ticks": 100'),
                 _blob(report).replace(b'"ticks": 100', b'"ticks": NaN'),
                 _blob(report).replace(b'"ticks": 100', b'"ticks": Infinity')):
        _refused(_blob(plan), blob)
    _refused(_blob(plan).replace(b'"schema":', b'"schema": "duplicate", "schema":'), _blob(report))


def _cli() -> None:
    plan, report = _fixture()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        plan_file, report_file = root / "plan.json", root / "report.json"
        plan_file.write_bytes(_blob(plan))
        outputs: list[str] = []
        for _ in range(2):
            report_file.write_bytes(_blob(report))
            output = StringIO()
            with redirect_stdout(output):
                code = cli.main([str(plan_file), str(report_file), "--json"])
            payload = json.loads(output.getvalue())
            ensure(code == 0 and payload["verdict"] == "compared", "successful comparison")
            ensure(payload["milestone_acceptance"] == "open", "comparison cannot admit ISA")
            ensure(payload["plan_sha256"] == _hash(plan_file.read_bytes()), "original plan identity")
            ensure(payload["report_sha256"] == _hash(report_file.read_bytes()), "original report identity")
            ensure(len(payload["sources_sha256"]) == 3, "tool and contract identity")
            outputs.append(output.getvalue())
        ensure(outputs[0] == outputs[1], "stable evidence")
        _arm(report)["ticks"] = 1
        report_file.write_bytes(_blob(report))
        with redirect_stdout(StringIO()):
            ensure(cli.main([str(plan_file), str(report_file)]) == 0, "valid losing outcome succeeds")
        report_file.write_bytes(b"{}")
        for flags in ([], ["--json"]):
            with redirect_stdout(StringIO()):
                ensure(cli.main([str(plan_file), str(report_file), *flags]) == 1, "invalid report refuses")
                ensure(cli.main([str(plan_file), str(root / "absent"), *flags]) == 1, "missing report refuses")


def cases() -> list[Case]:
    return [Case("generated-ratio-boundaries", _boundaries),
            Case("independent-plan-bindings", _bindings),
            Case("closed-shapes-and-complete-cases", _shapes),
            Case("invalid-numbers-and-json", _invalid_numbers_and_json),
            Case("cli-evidence-and-exits", _cli)]
