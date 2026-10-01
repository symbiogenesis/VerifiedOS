# SPDX-License-Identifier: Apache-2.0
"""Guest diagnostics retain failures and never present an unexecuted proof as fresh."""

import contextlib
import io
import json
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

from ci.report_guest import LANES, READING_FILES, SAIL_MEMO, TOOLCHAINS, main, report
from tests.harness import Case, ensure
from vos import proofaudit, proofreading, receipts
from vos.cli import proof_reading
from vos.cli import proofs as proofs_cli

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "guest-gates.yml"
READING_BASE = "c" * 40


def _bootstrap_failure() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        console = root / "console.log"
        console.write_text("bootstrap failed\n", encoding="utf-8")
        proof = root / "proof.json"
        proof.write_text("old tracked receipt\n", encoding="utf-8")
        for lane in LANES:
            logs = root / lane
            summary = report(lane, logs, console, proof,
                             {"bootstrap": {"outcome": "failure"}}, "abc", toolchains="cold")
            result = json.loads((logs / "results.json").read_text(encoding="utf-8"))
            ensure(result["revision"] == "abc" and result["lane"] == lane,
                   "source revision or lane was lost")
            ensure(result["commands"]["bootstrap"] == "failure", "bootstrap failure was hidden")
            ensure(all(result["commands"][name] == "skipped" for name in LANES[lane][1:]),
                   "unexecuted gates were not skipped")
            ensure(("No evidence record" in summary) == (lane == "model"),
                   "absent evidence was not explained, or explained in a lane without it")
            ensure((logs / "bootstrap-console.log").read_bytes() == console.read_bytes(),
                   "bootstrap console was not retained")
            ensure(not (logs / "proof-evidence.json").exists(), "old proof was published as fresh")


def _pinned_checkout_revision() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        environment = {"GUEST_LANE": "proofs", "GUEST_TOOLCHAINS": "cold",
                       "VOS_LOG_DIR": str(root), "RUNNER_TEMP": str(root),
                       "STEP_RESULTS": "{}", "GITHUB_SHA": "b" * 40,
                       "GITHUB_STEP_SUMMARY": str(root / "summary.md")}
        for pinned in ("", "a" * 40):
            with patch.dict(os.environ, {**environment, "GUEST_REVISION": pinned}):
                main()
            result = json.loads((root / "results.json").read_text(encoding="utf-8"))
            ensure(result["revision"] == (pinned or "b" * 40),
                   "guest diagnostics must identify the pinned checkout, with head SHA fallback")


def _toolchain_state_recorded() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for state in TOOLCHAINS:
            logs = root / state
            summary = report("proofs", logs, root / "absent-console", root / "absent-proof",
                             {"proofs": {"outcome": "success"}}, "abc", toolchains=state)
            result = json.loads((logs / "results.json").read_text(encoding="utf-8"))
            ensure(result["toolchains"] == state, "the toolchain state was not retained")
            ensure(("not cold-installation evidence" in summary) == (state == "restored"),
                   "a restored run was presented as a cold installation")
    with patch.dict(os.environ, {"GUEST_LANE": "proofs", "GUEST_TOOLCHAINS": "warm"}):
        try:
            main()
        except SystemExit as err:
            ensure("unknown toolchain state" in str(err), f"the refusal said {err}")
            return
    ensure(False, "an unknown toolchain state was reported")


def _sail_memo_state_recorded() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for state in SAIL_MEMO:
            logs = root / state
            summary = report("model", logs, root / "absent-console", root / "absent-proof",
                             {"evidence": {"outcome": "success"}}, "abc", toolchains="restored",
                             sail_memo=state)
            result = json.loads((logs / "results.json").read_text(encoding="utf-8"))
            ensure(result["sail_memo"] == state, "the Sail memo state was not retained")
            ensure(("not discharged again" in summary) == (state == "restored"),
                   "a restored memo was presented as re-discharged solver work")
        report("proofs", root / "proofs", root / "absent-console", root / "absent-proof",
               {}, "abc", toolchains="cold")
        result = json.loads((root / "proofs" / "results.json").read_text(encoding="utf-8"))
        ensure("sail_memo" not in result, "a lane without a Sail build stated a memo")
        environment = {"VOS_LOG_DIR": str(root / "main"), "RUNNER_TEMP": str(root),
                       "STEP_RESULTS": "{}", "GITHUB_SHA": "b" * 40, "GUEST_REVISION": "",
                       "GUEST_TOOLCHAINS": "cold",
                       "GITHUB_STEP_SUMMARY": str(root / "summary.md")}
        with patch.dict(os.environ, {**environment, "GUEST_LANE": "model",
                                     "GUEST_SAIL_MEMO": "restored"}):
            main()
        result = json.loads((root / "main" / "results.json").read_text(encoding="utf-8"))
        ensure(result["sail_memo"] == "restored", "the workflow's memo state was not retained")
        for lane, memo in (("model", ""), ("model", "warm"), ("proofs", "cold")):
            with patch.dict(os.environ, {**environment, "GUEST_LANE": lane,
                                         "GUEST_SAIL_MEMO": memo}):
                try:
                    main()
                except SystemExit as err:
                    ensure("memo" in str(err), f"the refusal said {err}")
                    continue
            ensure(False, f"the {lane} lane accepted Sail memo state {memo!r}")


def _proof_outcomes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        proof = root / "proof.json"
        proof.write_text('{"receipt": "fresh"}\n', encoding="utf-8")
        for outcome in ("success", "failure", "skipped", "cancelled"):
            logs = root / outcome
            logs.mkdir()
            (logs / "proof-evidence.json").write_text("stale", encoding="utf-8")
            summary = report("proofs", logs, root / "absent-console", proof,
                             {"bootstrap": {"outcome": "success"},
                              "proofs": {"outcome": outcome}}, "abc", toolchains="cold")
            ensure(f"| proofs | {outcome} |" in summary, "the proof gate outcome was lost")
            retained = logs / "proof-evidence.json"
            ensure(retained.exists() == (outcome == "success"),
                   "proof receipt ignored its producing verdict")
            if outcome == "success":
                ensure(retained.read_bytes() == proof.read_bytes(), "proof receipt bytes changed")


def _model_lane_publishes_no_proof() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        proof = root / "proof.json"
        proof.write_text("tracked receipt\n", encoding="utf-8")
        evidence = {"members": [{"name": "proofs", "exit_code": 0, "seconds": 12.25}]}
        (root / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
        summary = report("model", root, root / "absent-console", proof,
                         {"evidence": {"outcome": "success"},
                          "proofs": {"outcome": "success"}}, "abc", toolchains="cold")
        ensure("| proofs | 0 | 12.2 |" in summary, "evidence member outcome or timing was lost")
        ensure("| proofs | success |" not in summary, "another lane's step entered the table")
        ensure(not (root / "proof-evidence.json").exists(),
               "the model lane published a proof receipt it did not produce")


def _unreadable_evidence() -> None:
    valid = {"name": "proofs", "exit_code": 0, "seconds": 1}
    records: tuple[object, ...] = (
        None, [], {}, {"members": None}, {"members": [None]},
        {"members": [valid, valid]}, {"members": [valid, {"name": "broken"}]},
        *({"members": [valid | override]} for override in (
            {"name": ""}, {"name": 5}, {"exit_code": False}, {"exit_code": "0"},
            {"seconds": -1}, {"seconds": True}, {"seconds": "1"},
            {"seconds": float("nan")}, {"seconds": float("inf")}, {"seconds": 10 ** 400},
        )),
    )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for index, payload in enumerate(("{", *(json.dumps(record) for record in records))):
            logs = root / str(index)
            logs.mkdir()
            (logs / "evidence.json").write_text(payload, encoding="utf-8")
            (logs / "proof-evidence.json").write_text("stale", encoding="utf-8")
            summary = report("model", logs, root / "absent-console", root / "absent-proof",
                             {"evidence": {"outcome": "failure"}}, "abc", toolchains="cold")
            ensure("Evidence report could not be read" in summary, "bad evidence aborted reporting")
            ensure("| Evidence member |" not in summary, "a partial evidence table was published")
            ensure((logs / "results.json").is_file(), "command outcomes were not retained")
            ensure(not (logs / "proof-evidence.json").exists(), "bad evidence published a proof")


def _skipped_evidence_ignores_old_record() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "evidence.json").write_text(json.dumps({"members": [
            {"name": "proofs", "exit_code": 0, "seconds": 1},
        ]}), encoding="utf-8")
        (root / "proof-evidence.json").write_text("old retained receipt", encoding="utf-8")
        proof = root / "proof.json"
        proof.write_text("old tracked receipt", encoding="utf-8")
        summary = report("model", root, root / "absent-console", proof, {}, "abc", toolchains="cold")
        ensure("| proofs |" not in summary, "skipped evidence reused a previous member verdict")
        ensure(not (root / "proof-evidence.json").exists(), "old proof receipt survived reporting")


def _diagnostic_copy_failure_keeps_summary() -> None:
    def fail_copy(source: Path, destination: Path) -> None:
        destination.write_bytes(b"partial")
        raise PermissionError("copy interrupted")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        console = root / "console.log"
        console.write_text("bootstrap output", encoding="utf-8")
        with patch("ci.report_guest.shutil.copyfile", side_effect=fail_copy):
            summary = report("proofs", root, console, root / "proof.json",
                             {"proofs": {"outcome": "success"}}, "abc", toolchains="cold")
        ensure("| proofs | success |" in summary, "copy failure suppressed the gate outcome")
        for filename in ("bootstrap-console.log", "proof-evidence.json"):
            ensure(f"Could not retain {filename}" in summary, "copy failure was not reported")
            ensure(not (root / filename).exists(), "an incomplete diagnostic was published")
        ensure(not list(root.glob(".*.tmp")), "failed copies left temporary artifacts")
        record = json.loads((root / "results.json").read_text(encoding="utf-8"))
        ensure(record["commands"]["proofs"] == "success", "copy failure discarded gate outcomes")


def _member_names_cannot_break_table() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "evidence.json").write_text(json.dumps({"members": [
            {"name": "a|b\n<script>", "exit_code": 1, "seconds": 1},
        ]}), encoding="utf-8")
        summary = report("model", root, root / "absent-console", root / "absent-proof",
                         {"evidence": {"outcome": "failure"}}, "abc", toolchains="cold")
        ensure("| a&#124;b &lt;script&gt; | 1 | 1.0 |" in summary,
               "member name was interpreted as table or HTML syntax")


def _reading_outcome_recorded() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for outcome in ("success", "failure", "skipped", "cancelled"):
            logs = root / outcome
            summary = report("proofs", logs, root / "absent-console", root / "absent-proof",
                             {"proofs": {"outcome": "success"}, "reading": {"outcome": outcome}},
                             "abc", toolchains="cold", reading_base=READING_BASE)
            result = json.loads((logs / "results.json").read_text(encoding="utf-8"))
            ensure(result["commands"]["reading"] == outcome
                   and result["reading_base"] == READING_BASE,
                   "the reading step's outcome and its base were not retained")
            ensure(f"| reading | {outcome} |" in summary, "the reading outcome was lost")
            ensure(("Both readings and the comparison's log are retained" in summary)
                   == (outcome == "success"),
                   "a reading that did not pass was presented as a comparison")
        summary = report("proofs", root / "none", root / "absent-console", root / "absent-proof",
                         {"proofs": {"outcome": "success"}}, "abc", toolchains="cold")
        result = json.loads((root / "none" / "results.json").read_text(encoding="utf-8"))
        ensure(result["commands"]["reading"] == "skipped" and "reading_base" not in result
               and "Proof reading base" not in summary,
               "a run without a reading base stated one")
        environment = {"VOS_LOG_DIR": str(root / "main"), "RUNNER_TEMP": str(root),
                       "STEP_RESULTS": "{}", "GITHUB_SHA": "b" * 40, "GUEST_REVISION": "",
                       "GUEST_TOOLCHAINS": "cold",
                       "GITHUB_STEP_SUMMARY": str(root / "summary.md")}
        with patch.dict(os.environ, {**environment, "GUEST_LANE": "proofs",
                                     "GUEST_SAIL_MEMO": "", "GUEST_READING_BASE": READING_BASE}):
            main()
        result = json.loads((root / "main" / "results.json").read_text(encoding="utf-8"))
        ensure(result["reading_base"] == READING_BASE, "the workflow's reading base was lost")
        # Only the proofs lane states a base, and only one the dispatch check accepts.
        for lane, memo, base in (("model", "cold", READING_BASE),
                                 ("proofs", "", READING_BASE[:7]),
                                 ("proofs", "", READING_BASE.upper())):
            with patch.dict(os.environ, {**environment, "GUEST_LANE": lane,
                                         "GUEST_SAIL_MEMO": memo, "GUEST_READING_BASE": base}):
                try:
                    main()
                except SystemExit as err:
                    ensure("base" in str(err), f"the refusal said {err}")
                    continue
            ensure(False, f"the {lane} lane accepted reading base {base!r}")


def _step(name: str) -> str:
    """One guest-gates step's text, from its name line to the next step."""
    contents = WORKFLOW.read_text(encoding="utf-8")
    return contents.split(f"      - name: {name}\n", 1)[1].split("\n      - ", 1)[0]


def _reading(body: str) -> dict[str, object]:
    """A one-constant reading the schema accepts, its body as given."""
    digest = "0" * 64
    return {"format": proofreading.FORMAT, "schema": proofreading.SCHEMA,
            "reader": {"prover": "The Rocq Prover, version 9.3.0", "prover_sha256": digest,
                       "query_flags": list(proofs_cli.STRICT),
                       "inventory_settings": proofaudit.SETTINGS,
                       "reading_settings": proofreading.SETTINGS},
            "modules": {"M": {"constants": {"M.a": {
                "kind": "Constant", "opacity": "transparent", "universes": "monomorphic",
                "check": "M.a\n     : nat", "about": "M.a : nat\n\nM.a is transparent",
                "print": f"M.a {body}"}}}},
            "provenance": {"sources": {"M.v": digest}, "objects": {"M.vo": digest}}}


def _reading_step() -> None:
    step = _step("Read the proofs against the reading base")
    ensure("        id: reading\n" in step and "reading" in LANES["proofs"],
           "the reporter reads the reading step by its id")
    condition = re.search(r"(?m)^        if: \$\{\{ (.*) \}\}$", step)
    ensure(condition is not None and set(condition[1].split(" && ")) == {
        "matrix.lane == 'proofs'", "!cancelled()", "inputs.reading_base != ''",
        "steps.proofs.outcome == 'success'"},
        "the step runs in the proofs lane, for a named base, over a passing gate's compile")
    ensure("          READING_BASE: ${{ inputs.reading_base }}\n" in step,
           "the base reaches the step through its environment")
    run = step.split("        run: |\n", 1)[1]
    # The proof environment is the gate's own, read from the file the gate reads.
    environment = "mapfile -d '' -t proof_env < \"$RUNNER_TEMP/proof-environment\""
    ensure(environment in _step("Proof gate") and environment in run,
           "the reading reads the gate's explicit environment")
    commands = [line.strip() for line in re.sub(r"\\\n\s*", "", run).split("\n")
                if "tools/run.py" in line]
    ensure(len(commands) == 3 and all(
        'env -i "${proof_env[@]}" python3 tools/run.py proof-reading ' in command
        for command in commands), f"every reading command runs in that environment: {commands}")
    for fragment in ('proof-reading record --out "$candidate"',
                     'proof-reading record --sources "$sources/proofs" --out "$base"',
                     'proof-reading compare "$base" "$candidate" > "$comparison"'):
        ensure(any(fragment in command for command in commands),
               f"the step runs {fragment!r}")
    ensure('git archive --format=tar "$READING_BASE" proofs | tar -x -C "$sources"' in run,
           "the base's sources come from its own commit")
    for name in READING_FILES:
        ensure(f'"$VOS_LOG_DIR/{name}"' in run, f"{name} is written where the artifact keeps it")
    # The step tells a comparison that names differences from a refused one by the line
    # `compare` prints first, which this holds to the command's own output.
    template = "FAIL proof-reading: $count difference(s) between $base and $candidate"
    for line in ('first=$(head -n 1 -- "$comparison")', 'count=${first#"FAIL proof-reading: "}',
                 'count=${count%" difference(s) between $base and $candidate"}',
                 f'"$first" == "{template}"'):
        ensure(line in run, f"the step decides the comparison by {line!r}")
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        base, candidate = folder / READING_FILES[0], folder / READING_FILES[1]
        receipts.write(base, _reading("= 0"))
        receipts.write(candidate, _reading("= 1"))
        for second, code, compared in ((base, 0, False), (candidate, 1, True),
                                       (folder / "absent.json", 1, False)):
            with contextlib.redirect_stdout(io.StringIO()) as said:
                exit_code = proof_reading.main(["compare", str(base), str(second)])
            first = said.getvalue().split("\n", 1)[0]
            count = first.removeprefix("FAIL proof-reading: ").removesuffix(
                f" difference(s) between {base} and {second}")
            matched = count.isdigit() and first == template.replace("$count", count).replace(
                "$base", str(base)).replace("$candidate", str(second))
            ensure(exit_code == code and matched == compared,
                   f"the step must accept exactly a comparison naming differences: {first!r}")


def cases() -> list[Case]:
    return [
        Case("bootstrap failure retains diagnostics without stale proofs", _bootstrap_failure),
        Case("pinned checkout revision survives a newer main head", _pinned_checkout_revision),
        Case("toolchain installation state is recorded and validated", _toolchain_state_recorded),
        Case("Sail memo state is recorded and validated", _sail_memo_state_recorded),
        Case("proof receipt follows its gate verdict", _proof_outcomes),
        Case("model lane publishes no proof receipt", _model_lane_publishes_no_proof),
        Case("unreadable evidence preserves command outcomes", _unreadable_evidence),
        Case("skipped evidence refuses stale records and proof receipts", _skipped_evidence_ignores_old_record),
        Case("diagnostic copy failure preserves the remaining report", _diagnostic_copy_failure_keeps_summary),
        Case("member names are escaped in Markdown tables", _member_names_cannot_break_table),
        Case("reading outcome and base are recorded and validated", _reading_outcome_recorded),
        Case("reading step runs in the gate's environment and reads compare's verdict",
             _reading_step),
    ]
