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
# The boot signature target campaign, which restores the model lane's installed
# toolchains and Sail memo.
CAMPAIGN = WORKFLOW.parent / "boot-crypto-target.yml"
READING_BASE = "c" * 40
# The minutes guest-gates.yml's job leaves under its limit, past every lane's step limits.
LIMIT_MARGIN = 30


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
        # The model lane's build and the rtl lane's bundle each run Sail over a memo.
        for lane, memo in (("model", "restored"), ("rtl", "cold")):
            with patch.dict(os.environ, {**environment, "GUEST_LANE": lane,
                                         "GUEST_SAIL_MEMO": memo}):
                main()
            result = json.loads((root / "main" / "results.json").read_text(encoding="utf-8"))
            ensure(result["lane"] == lane and result["sail_memo"] == memo,
                   f"the {lane} lane's memo state was not retained")
        for lane, memo in (("model", ""), ("model", "warm"), ("rtl", ""), ("proofs", "cold")):
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


def _workflow_step(contents: str, name: str) -> str:
    """One step's text in a workflow, from its name line to the next step; empty where no
    step bears the name."""
    parts = contents.split(f"      - name: {name}\n", 1)
    return parts[1].split("\n      - ", 1)[0] if len(parts) == 2 else ""


def _step(name: str) -> str:
    """One guest-gates step's text, from its name line to the next step."""
    return _workflow_step(WORKFLOW.read_text(encoding="utf-8"), name)


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
        "matrix.lane == 'proofs'", "!cancelled()", "steps.dispatch.outcome != 'failure'",
        "inputs.reading_base != ''", "steps.proofs.outcome == 'success'"},
        "the step runs in the proofs lane of an accepted dispatch, for a named base, over "
        "a passing gate's compile")
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
    # Once the comparison is decided, both readings' digests reach the log and summary.
    digests = ('for reading in "$base" "$candidate"; do', 'digest=$(sha256sum -- "$reading")',
               '| tee -a "$GITHUB_STEP_SUMMARY"')
    ensure(all(line in run and run.index(line) > run.rindex("\n          fi\n")
               for line in digests), "both readings' digests follow the comparison's verdict")
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


def _runs_in(lane: str, step: str) -> bool:
    """Whether a guest-gates step can run in `lane`: a condition naming lanes runs only in
    those, one excluding a lane never in it, and a step without either in every lane."""
    guard = re.search(r"(?m)^        if: (.*)$", step)
    condition = guard[1] if guard is not None else ""
    named = set(re.findall(r"matrix\.lane == '(\w+)'", condition))
    return (not named or lane in named) and f"matrix.lane != '{lane}'" not in condition


def _guest_steps() -> list[str]:
    """The guest-gates job's steps, each from its name line to the next step."""
    job = WORKFLOW.read_text(encoding="utf-8").split("\n  guest-gates:\n", 1)[1]
    return job.split("\n      - ")[1:]


def _lane_step_limits() -> None:
    # A job that reaches its own limit is cancelled, so its report and upload never run:
    # the limits of the steps each lane can run stay the margin the job states under its
    # limit, which the steps without a limit of their own share.
    job = WORKFLOW.read_text(encoding="utf-8").split("\n  guest-gates:\n", 1)[1]
    job_limit = re.search(r"(?m)^    timeout-minutes: (\d+)$", job)
    named = {"model": ("Bootstrap guest toolchains", "Model evidence"),
             "rtl": ("Bootstrap guest toolchains", "Check generated model bundle",
                     "Lint standalone RTL", "Check frozen RTL widths and store lanes",
                     "Crosscheck RTL against fresh model vectors"),
             "proofs": ("Bootstrap guest toolchains", "Proof gate",
                        "Read the proofs against the reading base")}
    ensure(set(named) == set(LANES), f"every lane's limits are read: {sorted(LANES)}")
    for lane, steps in named.items():
        limits: dict[str, int] = {}
        for lane_step in _guest_steps():
            limit = re.search(r"(?m)^        timeout-minutes: (\d+)$", lane_step)
            if limit is not None and _runs_in(lane, lane_step):
                limits[lane_step.split("\n", 1)[0].removeprefix("name: ")] = int(limit[1])
        ensure(set(steps) <= set(limits) and job_limit is not None
               and sum(limits.values()) + LIMIT_MARGIN <= int(job_limit[1]),
               f"the {lane} lane's step limits {limits} must stay {LIMIT_MARGIN} minutes "
               "under the job's")


def _matrix(contents: str) -> list[dict[str, str]]:
    """The matrix entries of guest-gates.yml's text, each as its fields."""
    parts = contents.split("        include:\n", 1)
    block = parts[1] if len(parts) == 2 else ""
    entries: list[dict[str, str]] = []
    for line in block.split("\n    env:\n", 1)[0].splitlines():
        first = re.fullmatch(r" {10}- (\w+): (.*)", line)
        later = re.fullmatch(r" {12}(\w+): (.*)", line)
        if first is not None:
            entries.append({first[1]: first[2]})
        elif later is not None and entries:
            entries[-1][later[1]] = later[2]
    return entries


def _lanes_match_the_workflow() -> None:
    """The reporter's lanes are the workflow's: each lane's commands run in it alone, a
    lane restoring another's caches selects that lane's toolchains and saves none of
    them, and a weekly skip needs every lane's artifact."""
    entries = _matrix(WORKFLOW.read_text(encoding="utf-8"))
    lanes = {entry["lane"]: entry for entry in entries}
    ensure(set(lanes) == set(LANES) and len(lanes) == len(entries),
           f"the matrix's lanes are the reporter's, once each: {entries}")
    for lane, entry in lanes.items():
        owner = lanes.get(entry["cache_lane"], {})
        ensure(owner.get("cache_lane") == owner.get("lane")
               and owner.get("toolchains") == entry["toolchains"],
               f"the {lane} lane restores caches its own toolchain selection fills: {entry}")
    steps = _guest_steps()
    for lane, ids in LANES.items():
        for step_id in ids:
            step = next((text for text in steps if f"\n        id: {step_id}\n" in text), "")
            others = [other for other in LANES if other != lane and _runs_in(other, step)]
            ensure(_runs_in(lane, step) and (step_id == "bootstrap" or not others),
                   f"step {step_id} runs in the {lane} lane alone, also running in {others}")
    for name in ("Save installed toolchains", "Cache guest source downloads"):
        step = next((text for text in steps if text.startswith(f"name: {name}\n")), "")
        ensure("matrix.cache_lane == matrix.lane" in step,
               f"{name!r} saves only from the lane whose cache it is")
    changes = WORKFLOW.read_text(encoding="utf-8").split("\n  changes:\n", 1)[1].split(
        "\n  guest-gates:\n", 1)[0]
    for lane in LANES:
        ensure(f'grep -q "^guest-{lane}-$GITHUB_SHA-"' in changes,
               f"a weekly skip needs the {lane} lane's artifact")


def _with(step: str, key: str) -> list[str]:
    """Every one-line value a step's `with:` states for `key`."""
    return [str(value) for value in re.findall(rf"(?m)^          {re.escape(key)}: (.*)$", step)]


def _block(text: str, header: str) -> list[str]:
    """The stripped lines of the block scalar the line `header` opens, which end at the
    first line indented no deeper than it; empty where no line is `header`."""
    lines = text.split("\n")
    start = next((n for n, line in enumerate(lines) if line == header), None)
    depth = len(header) - len(header.lstrip())
    block: list[str] = []
    for line in lines[start + 1:] if start is not None else []:
        if len(line) - len(line.lstrip()) <= depth:
            break
        block.append(line.strip())
    return block


def _campaign_restore_faults(gates: str, campaign: str) -> list[str]:
    """Why the boot signature campaign's restores could miss the caches guest-gates.yml's
    model lane saves. Each restore's key, fallback and paths must be the model lane's,
    read with its cache lane and its image component, the runner image's version, which
    the campaign names directly. Both workflows must compute that version, the Sail
    solver identity and the recipe identity alike, the last for the model lane's
    selection, in steps bearing the ids the keys read."""
    faults: list[str] = []
    model = next((entry for entry in _matrix(gates) if entry.get("lane") == "model"), {})
    images = (_workflow_step(gates, "Identify the runner image"),
              _workflow_step(campaign, "Identify the runner image"))
    version = "${ImageOS:-unknown}-${ImageVersion:-unknown}"
    if not (version in images[0] and version in images[1]
            and '[[ "$GUEST_CACHE_LANE" == proofs ]]' in images[0]
            and 'echo "toolchain=$version"' in images[0]):
        faults.append("the model lane's image component is not the image version the "
                      "campaign computes")
    for name, ident in (("Identify the runner image", "image"),
                        ("Identify the toolchain recipe", "recipe"),
                        ("Identify the Sail solver", "solver")):
        if not re.search(rf"(?m)^        id: {ident}$", _workflow_step(campaign, name)):
            faults.append(f"the campaign's {name!r} is not identified as {ident}")
    recipe = " ".join(_workflow_step(campaign, "Identify the toolchain recipe")
                      .replace("\\\n", " ").split())
    if not model.get("toolchains") or (
            f"$(python3 tools/ci/bootstrap_guest.py --print-recipe-identity "
            f"{model['toolchains']})") not in recipe:
        faults.append("the campaign's recipe identity is not the model lane's selection's")
    restore = (_workflow_step(gates, "Restore installed toolchains"),
               _workflow_step(campaign, "Restore installed toolchains"))
    keys = _with(restore[0], "key")
    key = keys[0] if len(keys) == 1 else ""
    for lane_value, model_value in (("${{ matrix.cache_lane }}", model.get("cache_lane", "")),
                                    ("${{ steps.image.outputs.toolchain }}",
                                     "${{ steps.image.outputs.version }}")):
        key = key.replace(lane_value, model_value)
    if not key or _with(restore[1], "key") != [key]:
        faults.append(f"the campaign's toolchain key {_with(restore[1], 'key')} is not the "
                      f"model lane's {key!r}")
    if _with(restore[1], "restore-keys") != _with(restore[0], "restore-keys"):
        faults.append("the campaign's toolchain fallback is not the model lane's")
    paths = _block(gates, "      GUEST_TOOLCHAIN_PATHS: |")
    if (_with(restore[0], "path") != ["${{ env.GUEST_TOOLCHAIN_PATHS }}"] or not paths
            or _block(restore[1], "          path: |") != paths):
        faults.append("the campaign's toolchain paths are not GUEST_TOOLCHAIN_PATHS")
    memo = (_workflow_step(gates, "Restore the Sail memo"),
            _workflow_step(campaign, "Restore the Sail memo"))
    for field in ("path", "key", "restore-keys"):
        stated = _with(memo[0], field)
        if len(stated) != 1 or _with(memo[1], field) != stated:
            faults.append(f"the campaign's Sail memo {field} is not the model lane's {stated}")
    solver = [[line.strip() for line in _workflow_step(text, "Identify the Sail solver")
               .split("\n") if "identity=" in line] for text in (gates, campaign)]
    if len(solver[0]) != 1 or solver[1] != solver[0]:
        faults.append(f"the campaign's Sail solver identity {solver[1]} is not the model "
                      f"lane's {solver[0]}")
    return faults


def _campaign_restores_the_model_lane() -> None:
    """The boot signature campaign restores the model lane's installed toolchains and Sail
    memo under the keys and paths that lane saves them by, and a drift on either side is
    named."""
    original = {"gates": WORKFLOW.read_text(encoding="utf-8"),
                "campaign": CAMPAIGN.read_text(encoding="utf-8")}
    found = _campaign_restore_faults(original["gates"], original["campaign"])
    ensure(not found, f"the campaign's restores miss the model lane's caches: {found}")
    identity = "-${{ steps.recipe.outputs.identity }}\n"
    for side, old, new in (
            ("campaign", "key: guest-toolchains-v1-model-", "key: guest-toolchains-v2-model-"),
            ("gates", identity, identity.replace("\n", "-x\n")),
            ("campaign", "            !~/verifiedos-guest/opam/log\n", ""),
            ("gates", "        !~/verifiedos-guest/opam/log\n", ""),
            ("campaign", "restore-keys: guest-sail-memo-v1-", "restore-keys: guest-sail-memo-v2-"),
            ("campaign", "--toolchain sail --toolchain rtl)", "--toolchain sail)"),
            ("gates", 'echo "toolchain=$version"', 'echo "toolchain=${ImageOS:-unknown}"'),
            ("campaign", "['snapshots']['sail'][:16]", "['snapshots']['sail'][:12]"),
            ("campaign", "        id: recipe\n", "        id: identity\n")):
        mutant = dict(original, **{side: original[side].replace(old, new, 1)})
        ensure(mutant[side] != original[side]
               and bool(_campaign_restore_faults(mutant["gates"], mutant["campaign"])),
               f"the campaign's restores must be refused with {old!r} made {new!r} in {side}")


# The compiler cache's steps, in workflow order, and its lineage: the runner, its image
# and the model lane's toolchain recipe, which the model's hash follows in the key.
CCACHE_STEPS = ("Restore the compiler cache", "Count this run's compiler cache use",
                "Model evidence", "Trim the compiler cache", "Save the compiler cache")
CCACHE_LINEAGE = ("guest-ccache-v1-${{ runner.os }}-${{ runner.arch }}-"
                  "${{ steps.image.outputs.version }}-${{ steps.recipe.outputs.identity }}-")


def _conjuncts(step: str) -> set[str]:
    """The `&&` operands of a step's one-line condition; empty where it states none."""
    condition = re.search(r"(?m)^        if: \$\{\{ (.*) \}\}$", step)
    return set(str(condition[1]).split(" && ")) if condition is not None else set()


def _compiler_cache_faults(contents: str) -> list[str]:
    """Why guest-gates.yml's compiler cache could serve or keep what it must not: only
    the model lane restores it, a cold run looks its key up without restoring it, the
    key is the lineage and the model's hash, and only main saves the restored key's
    entry, past a passing sweep and the trim that leaves this build's objects alone. The
    count and the trim run beside the sweep and never fail the job."""
    faults: list[str] = []
    restore, start, _, trim, save = (_workflow_step(contents, name) for name in CCACHE_STEPS)
    places = [contents.find(f"      - name: {name}\n") for name in CCACHE_STEPS]
    if -1 in places or places != sorted(places):
        faults.append(f"the compiler cache's steps do not stand in the order {CCACHE_STEPS}")
    model = "matrix.lane == 'model'"
    if "        id: ccache\n" not in restore or _conjuncts(restore) != {
            model, "!cancelled()", "steps.bootstrap.outcome == 'success'"}:
        faults.append("the compiler cache is restored other than by the model lane alone")
    if (_with(restore, "key") != [CCACHE_LINEAGE + "${{ hashFiles('model/**') }}"]
            or _with(restore, "restore-keys") != [CCACHE_LINEAGE]):
        faults.append("the compiler cache's key or fallback leaves its lineage")
    if _with(restore, "lookup-only") != ["${{ env.GUEST_COLD == 'true' }}"]:
        faults.append("a cold run restores the compiler cache")
    paths = _block(restore, "          path: |")
    if (paths[:1] != ["${{ env.CCACHE_DIR }}"]
            or _block(save, "          path: |") != paths):
        faults.append("the compiler cache's restore and save name other paths")
    for step, ident, after in ((start, "ccache-start", "steps.bootstrap.outcome == 'success'"),
                               (trim, "ccache-trim", "steps.ccache-start.outcome == 'success'")):
        if (f"        id: {ident}\n" not in step or "        continue-on-error: true\n" not in step
                or _conjuncts(step) != {model, "!cancelled()",
                                        "steps.dispatch.outcome != 'failure'", after}):
            faults.append(f"the step {ident} runs other than beside the model lane's sweep, "
                          "or can fail the job")
    if "ccache --evict-older-than" not in trim:
        faults.append("the trim leaves entries this build did not use")
    if _with(save, "key") != ["${{ steps.ccache.outputs.cache-primary-key }}"] or _conjuncts(
            save) != {"github.ref == 'refs/heads/main'", model, "!cancelled()",
                      "steps.evidence.outcome == 'success'", "steps.ccache.outcome == 'success'",
                      "steps.ccache.outputs.cache-hit != 'true'",
                      "steps.ccache-trim.outcome == 'success'"}:
        faults.append("the compiler cache is saved other than by main's model lane, under "
                      "the missed key, after a passing sweep and its trim")
    return faults


def _compiler_cache_steps() -> None:
    contents = WORKFLOW.read_text(encoding="utf-8")
    found = _compiler_cache_faults(contents)
    ensure(not found, f"the compiler cache's steps are refused: {found}")
    for name, old, new in (
            ("Restore the compiler cache", "matrix.lane == 'model'",
             "(matrix.lane == 'model' || matrix.lane == 'rtl')"),
            ("Restore the compiler cache",
             "          lookup-only: ${{ env.GUEST_COLD == 'true' }}\n", ""),
            ("Restore the compiler cache", "restore-keys: guest-ccache-v1-${{ runner.os }}-"
             "${{ runner.arch }}-${{ steps.image.outputs.version }}-",
             "restore-keys: guest-ccache-v1-${{ runner.os }}-${{ runner.arch }}-"),
            ("Save the compiler cache", "            !${{ env.CCACHE_DIR }}/tmp\n", ""),
            ("Save the compiler cache", "github.ref == 'refs/heads/main' && ", ""),
            ("Save the compiler cache", " && steps.ccache-trim.outcome == 'success'", ""),
            ("Trim the compiler cache", "        continue-on-error: true\n", ""),
            ("Trim the compiler cache", "ccache --evict-older-than", "ccache --cleanup #")):
        step = _workflow_step(contents, name)
        mutant = contents.replace(step, step.replace(old, new, 1), 1)
        ensure(mutant != contents and bool(_compiler_cache_faults(mutant)),
               f"the compiler cache's steps must be refused with {old!r} made {new!r} in {name!r}")


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
        Case("each lane's step limits stay a margin under the job's", _lane_step_limits),
        Case("the reporter's lanes and their caches match the workflow's",
             _lanes_match_the_workflow),
        Case("the boot signature campaign restores the model lane's caches by their keys",
             _campaign_restores_the_model_lane),
        Case("the model lane alone restores and saves the compiler cache, never cold",
             _compiler_cache_steps),
    ]
