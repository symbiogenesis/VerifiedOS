# SPDX-License-Identifier: Apache-2.0
"""M3.5b's target chain campaign: its oracle, endings, staged inputs, join and workflow.

Every case here runs offline: the composers, the contained compiler, OpenSSL and the
emulator are stood in for, so what is decided is this harness's own reading of the
contract's section 9, never the chain firmware's behavior.
"""

import contextlib
import dataclasses
import hashlib
import io
import json
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from tests import test_fanout_ci, test_guest_report
from tests.harness import TOOLS, Case, ensure
from tests.test_boot_crypto import _STREAM
from vos import boot_chain as bc
from vos import boot_chain_target as target
from vos import boot_crypto_target, receipts
from vos import boot_handoff as bh
from vos.checks import generated
from vos.cli import boot_handoff as cli
from vos.cli import compiler_diff as cd

ROOT = TOOLS.parent
WORKFLOW = ROOT / ".github/workflows/boot-chain-target.yml"
CRYPTO_WORKFLOW = ROOT / ".github/workflows/boot-crypto-target.yml"


def _sign(scheme: str, public: bytes, message: bytes, size: int) -> bytes:
    """The fixture's stand-in signature: anyone holding the key computes it."""
    return hashlib.shake_256(scheme.encode() + public + message).digest(size)


def _verify(scheme: str, public: bytes, prefix: bytes, signature: bytes) -> bool:
    return signature == _sign(scheme, public, prefix, len(signature))


def _keys(f: bc.Facts) -> tuple[dict[int, bytes], bytes]:
    roots = {bh.LIFECYCLES.index(state): hashlib.shake_256(state.encode()).digest(
        f["BOOT_PUBLIC_KEY_BYTES"]) for state in bh.ROOT_STATES}
    return roots, hashlib.shake_256(b"kernel-stage root").digest(f["CHAIN_KSTAGE_PUBLIC_KEY_BYTES"])


def _images(f: bc.Facts, roots: dict[int, bytes], kernel_root: bytes) -> dict[str, bytes]:
    production = roots[f.lifecycle]

    def slh(public: bytes, message: bytes) -> bytes:
        return _sign(bc.SLH, public, message, f["BOOT_SIGNATURE_BYTES"])

    def mldsa(public: bytes, message: bytes) -> bytes:
        return _sign(bc.MLDSA, public, message, f["CHAIN_KSTAGE_SIGNATURE_BYTES"])
    images = {"stage0": bc.build_image(f, b"runtime text and data " * 40,
                                       stage=f["BOOT_STAGE_ROT_RUNTIME"], version=f.floor,
                                       signer=production, sign=slh)}
    slots = {name: b"m-mode stage " * 30 + kernel_root + tag
             for name, tag in zip(("mmode-a", "mmode-b", "mmode-recovery"), f.tags, strict=True)}
    for name, payload in slots.items():
        images[name] = bc.build_image(f, payload, stage=f["BOOT_STAGE_MMODE_IMAGE"],
                                      version=f.floor, signer=production, sign=slh)
    images["mmode-a-below-floor"] = bc.build_image(f, slots["mmode-a"],
                                                   stage=f["BOOT_STAGE_MMODE_IMAGE"],
                                                   version=f.floor - 1, signer=production, sign=slh)
    images["kernel"] = bc.build_image(f, b"kernel stage " * 25, stage=f["BOOT_STAGE_CORE_KERNELS"],
                                      version=f.floor, signer=kernel_root, sign=mldsa)
    return images


def _inputs(f: bc.Facts) -> bc.Inputs:
    roots, kernel_root = _keys(f)
    return bc.Inputs(_images(f, roots, kernel_root), roots, kernel_root, _verify)


def _satisfy(owed: bc.Expected, values: dict[str, int]) -> bytes:
    """The owed bytes with the predicate fields given values."""
    data = bytearray(owed.data)
    for name, value in values.items():
        at, width = owed.fields[name]
        data[at:at + width] = value.to_bytes(width, "little")
    return bytes(data)


_RELEASED = {"nonce_at_arm": 7, "pets_accepted": 1, "pets_skipped": 3, "ticks_at_end": 900}


# --- section 5 and the records ------------------------------------------------------


def _encoding_known_answers() -> None:
    f = bc.facts(ROOT)
    width = f["MEASURE_BYTES"]
    # Section 5 spelled out: SHAKE256("VOS-EXT1" || register || code || length || data).
    by_hand = hashlib.shake_256(b"VOS-EXT1" + bytes(width) + bytes([1]) + (1).to_bytes(4, "little")
                                + bytes([3])).digest(width)
    ensure(bc.Measured.reset(f).extend(f, 1, bytes([3])).device == by_hand,
           "item 1's extension is not section 5's encoding")
    digest = hashlib.shake_256(b"image").digest(f["BOOT_DIGEST_BYTES"])
    measured = bc.device_prologue(f, 3, 1, 0).extend(f, f["ITEM_STAGE_MMODE_IMAGE"], digest)
    want = bh.expected_registers(ROOT, bh.layout(ROOT), bh.RotInputs(3, 1, 0, 2), digest)
    ensure((measured.generation.hex(), measured.device.hex(), measured.chain(f).hex()) == want,
           "the chain oracle and the bring-up harness disagree on section 5")
    ensure(measured.chain(f) == hashlib.shake_256(b"VOS-CHN1" + measured.generation
                                                 + measured.device).digest(width),
           "the chain digest is not SHAKE256(VOS-CHN1 || generation || device)")
    stage0 = bc.device_prologue(f, 3, 1, 0).extend(f, f["ITEM_STAGE_ROT_RUNTIME"], digest)
    ensure(stage0.device == bc.device_prologue(f, 3, 1, 0).device and any(stage0.generation),
           "item 4 does not go to the generation register alone")
    ensure(stage0.extend(f, 5, digest).log_bytes(f) == bytes((1, 2, 3, 4, 5)).ljust(
        f["CHAIN_STATE_LOG_BYTES"], b"\0"), "the log is not the item codes, zero beyond")
    ensure(bc.device_prologue(f, 3, 1, 1).device != bc.device_prologue(f, 3, 1, 0).device,
           "the latch's bit is not measured")


_TABLE_ROW = re.compile(r"^\| `([a-z]+\.[a-z_]+)` \| (\d+) \| (\d+) \|", re.MULTILINE)


def _contract_offsets() -> dict[str, tuple[int, int]]:
    """The contract's own field tables, read here as known answers."""
    text = (ROOT / bh.CONTRACT).read_text(encoding="utf-8")
    return {name: (int(at), int(width)) for name, at, width in _TABLE_ROW.findall(text)}


def _records_follow_the_contract() -> None:
    f = bc.facts(ROOT)
    tables = _contract_offsets()

    def field(blob: bytes, name: str) -> bytes:
        at, width = tables[name]
        return blob[at:at + width]

    def word(blob: bytes, name: str) -> int:
        return int.from_bytes(field(blob, name), "little")
    generation, device = bytes(range(32)), bytes(range(32, 64))
    measured = bc.Measured(generation, device, (1, 2, 3, 4))
    state = bc.State(f["CHAIN_RUN_BOOT"], 3, 1, 1, 7, measured)
    record = bc.state_record(f, state)
    ensure(field(record, "state.magic") == b"VOSSTAT1" and word(record, "state.version") == 1
           and word(record, "state.run_kind") == f["CHAIN_RUN_BOOT"]
           and [word(record, f"state.{name}") for name in (
               "lifecycle", "entropy_ok", "boot_target", "floor", "measure_count")] == [3, 1, 1, 7, 4]
           and field(record, "state.log") == bytes((1, 2, 3, 4)).ljust(16, b"\0")
           and field(record, "state.generation") == generation
           and field(record, "state.device") == device, "the state record leaves section 9.5's table")
    end = tables["state.device"][0] + tables["state.device"][1]
    ensure(len(record) == f["CHAIN_STATE_BYTES"] and not any(record[end:]),
           "the state record's tail is not zero")
    ensure(bc.parse_state(f, record) == state, "a state record does not read back")
    ensure(bc.parse_state(f, bc.flip(record, 0)) is None, "a state record with a wrong magic was read")
    digest = bytes(range(64, 96))
    request = bc.item6_request(f, digest)
    ensure(field(request, "request.magic") == b"VOSITM6Q" and word(request, "request.stage") == 2
           and field(request, "request.digest") == digest and len(request) == f["CHAIN_REQUEST_BYTES"]
           and not any(request[48:]), "the request leaves section 9.7's table")
    after = measured.extend(f, f["ITEM_STAGE_CORE_KERNELS"], digest)
    response = bc.item6_response(f, digest, after)
    ensure(field(response, "response.magic") == b"VOSITM6R" and word(response, "response.stage") == 2
           and field(response, "response.digest") == digest
           and field(response, "response.generation") == after.generation
           and field(response, "response.device") == device
           and field(response, "response.chain") == after.chain(f)
           and word(response, "response.measure_count") == 5
           and field(response, "response.log") == bytes((1, 2, 3, 4, 6)).ljust(16, b"\0")
           and not any(response[168:]), "the response leaves section 9.7's table")
    handoff = bc.handoff_record(f, state, 7, 99, digest[:32], measured)
    ensure(field(handoff, "record.magic") == b"VOSHAND1"
           and [word(handoff, f"record.{name}") for name in (
               "version", "lifecycle", "entropy_ok", "boot_target", "security_version", "floor",
               "load_base", "payload_length")] == [1, 3, 1, 1, 7, 7, f["CHAIN_MMODE_LOAD_BASE"], 99]
           and field(handoff, "record.image_digest") == digest[:32]
           and field(handoff, "record.generation") == generation
           and field(handoff, "record.chain") == measured.chain(f) and not any(handoff[200:]),
           "the handoff record leaves section 6's table at section 9.9's values")
    ensure(bc.binds(f, handoff, bc.item6_response(f, digest[:32], measured.extend(
        f, f["ITEM_STAGE_CORE_KERNELS"], digest[:32])), digest[:32]),
           "a response over the record's registers does not bind")
    for name in ("magic", "digest", "generation", "chain"):
        at = tables[f"response.{name}"][0]
        tampered = bc.flip(bc.item6_response(f, digest[:32], measured.extend(
            f, f["ITEM_STAGE_CORE_KERNELS"], digest[:32])), at)
        ensure(not bc.binds(f, handoff, tampered, digest[:32]), f"a response with its {name} off binds")


def _selection_and_counting() -> None:
    f = bc.facts(ROOT)
    a, b, recovery, bound = (f["CHAIN_SLOT_A"], f["CHAIN_SLOT_B"], f["CHAIN_SLOT_RECOVERY"],
                             f["CHAIN_BOOT_ATTEMPT_BOUND"])
    for latch, slot, attempts, want in (
            (1, a, 0, bc.Selection(recovery, a, 0, False, False)),
            (1, b, bound, bc.Selection(recovery, b, bound, False, False)),
            (0, a, 0, bc.Selection(a, a, 1, True, False)),
            (0, a, bound - 1, bc.Selection(a, a, bound, True, False)),
            (0, a, bound, bc.Selection(b, b, 1, True, True)),
            (0, b, bound + 2, bc.Selection(a, a, 1, True, True))):
        ensure(bc.select(f, latch, slot, attempts) == want,
               f"selection of latch {latch}, slot {slot}, {attempts} attempts")


def _oracle_agrees_with_the_case_table() -> None:
    f = bc.facts(ROOT)
    inputs = _inputs(f)
    rows = bc.require_cases(ROOT)
    for row in rows:
        spec = bc.SPECS[row.name]
        case = None if spec.run == "runtime-only" else bc.plan(f, spec, inputs)
        found = bc.table_findings(f, row, spec, case)
        ensure(not found, f"the oracle and section 9.12 disagree on {row.name}: {found}")
    ensure(not bc.vacuity_findings(f, inputs), "the selection control does not hold over the oracle")
    below = next(row for row in rows if row.name == "mmode-below-floor")
    plan = bc.plan(f, bc.SPECS[below.name], inputs)
    for change, phrase in (({"boot_control": "A, 0"}, "boot control"), ({"items": "1,2,3; none"}, "items"),
                           ({"verdict": "refuse-signature"}, "decides"),
                           ({"main_die": "`SUCCESS`"}, "main die")):
        found = bc.table_findings(f, dataclasses.replace(below, **change), bc.SPECS[below.name], plan)
        ensure(any(phrase in finding for finding in found), f"a changed {phrase} cell passed: {found}")
    same = dict(inputs.images, **{"mmode-recovery": inputs.images["mmode-a"]})
    found = bc.vacuity_findings(f, bc.Inputs(same, inputs.roots, inputs.kernel_root, _verify))
    ensure(any("coincide" in finding for finding in found), f"coinciding images passed: {found}")
    try:
        bc.plan(f, bc.SPECS["watchdog-early-pet"], inputs)
    except ValueError:
        pass
    else:
        raise AssertionError("a runtime-only case produced a boot plan")
    unknown = bc.Inputs(inputs.images, inputs.roots, inputs.kernel_root,
                        bc.recorded_verify({"signature_verdicts": []}))
    try:
        bc.plan(f, bc.SPECS["cold-boot"], unknown)
    except ValueError as error:
        ensure("no OpenSSL verdict" in str(error), f"an unrecorded signature refused otherwise: {error}")
    else:
        raise AssertionError("a signature staging never verified was decided")


# --- captures --------------------------------------------------------------------------


def _captures_are_held_exactly() -> None:
    f = bc.facts(ROOT)
    inputs = _inputs(f)
    cold = bc.plan(f, bc.SPECS["cold-boot"], inputs)
    owed = bc.boot_capture(f, cold)
    good = _satisfy(owed, _RELEASED)
    problems, seen = bc.compare("R1", owed, good)
    ensure(not problems and seen["pets_accepted"] == 1, f"the oracle's own capture refused: {problems}")
    gap = owed.fields["mmode_payload_length"][0] + 9
    for label, at in (("record", owed.fields["record"][0] + 3), ("window", owed.fields["window"][0] + 10),
                      ("state", owed.fields["state"][0] + 90), ("generation", owed.fields["generation"][0]),
                      ("head gap", gap), ("slot gap", owed.fields["request"][0] + 100)):
        found, _ = bc.compare("R1", owed, bc.flip(good, at))
        ensure(bool(found), f"a changed {label} byte passed")
    for name, value in (("bitten", 1), ("pets_accepted", 0), ("nonce_at_arm", 0), ("released", 0),
                        ("ticks_at_end", f.late + 1), ("slot_final", 1), ("attempts_final", 2),
                        ("pets_skipped", 4), ("steps_completed", 2), ("verdict", 1)):
        found, _ = bc.compare("R1", owed, _satisfy(owed, {**_RELEASED, name: value}))
        ensure(any(name in finding for finding in found), f"{name} = {value} passed: {found}")
    ensure(bool(bc.compare("R1", owed, good[:-8])[0]), "a short capture passed")
    refused = bc.plan(f, bc.SPECS["runtime-digest-mismatch"], inputs)
    checked = refused.rom.checked
    ensure(checked is not None and checked.digest is not None, "the refused digest was not computed")
    owed = bc.boot_capture(f, refused)
    base = bytes(owed.data)
    at, width = owed.fields["runtime_digest"]
    reached = base[:at] + cast("bytes", checked.digest if checked else b"") + base[at + width:]
    for capture, verdict in ((base, "zero"), (reached, "reached")):
        found, seen = bc.compare("R1", owed, capture)
        ensure(not found and seen["runtime_digest"] == verdict, f"a silent digest ({verdict}) refused: {found}")
    ensure(bool(bc.compare("R1", owed, bc.flip(reached, at))[0]), "a third digest value passed")
    halted = bc.boot_capture(f, bc.plan(f, bc.SPECS["entropy-halt"], inputs))
    ensure(not bc.compare("R1", halted, bytes(halted.data))[0], "a failed health word refused")
    ensure(bool(bc.compare("R1", halted, _satisfy(halted, {"health": f.health}))[0]),
           "the passing health word passed an injected entropy failure")
    runtime_refusal = bc.boot_capture(f, bc.plan(f, bc.SPECS["mmode-below-floor"], inputs))
    for pets in ((0, 3), (1, 3)):
        found, _ = bc.compare("R1", runtime_refusal, _satisfy(runtime_refusal, {
            "nonce_at_arm": 5, "pets_accepted": pets[0], "pets_skipped": pets[1]}))
        ensure(not found, f"a runtime refusal's pets {pets} refused: {found}")
    service = bc.service_capture(f, cold)
    ensure(not bc.compare("R2", service, _satisfy(service, {"lifecycle": 3, "floor": 9}))[0],
           "R2's uncompared head fields were compared")
    for name in ("response", "request", "state", "record"):
        found, _ = bc.compare("R2", service, bc.flip(bytes(service.data), service.fields[name][0] + 20))
        ensure(bool(found), f"a changed R2 {name} passed")
    main = bc.main_capture(f, cold)
    ensure(not bc.compare("R3", main, bytes(main.data))[0], "the oracle's own R3 capture refused")
    for name in ("request", "response", "mcapture.response_bound", "mcapture.kernel_digest"):
        found, _ = bc.compare("R3", main, bc.flip(bytes(main.data), main.fields[name][0]))
        ensure(bool(found), f"a changed R3 {name} passed")
    try:
        bc.main_capture(f, bc.plan(f, bc.SPECS["kernel-signature-corrupt"], inputs))
    except ValueError:
        pass
    else:
        raise AssertionError("a main-die refusal was given a capture to compare")


# --- endings -----------------------------------------------------------------------


_BITE = ("FAILURE: the RoT watchdog bit and asserted the die reset after {} external slow-clock "
         "ticks with 412 instructions retired\n")
_RELEASE_LINE = "RELEASE: the RoT released the boot core after 9001 instructions retired\n"


def _endings_are_section_9_2s() -> None:
    limit = 50
    for log, status, want in (
            (_RELEASE_LINE, 0, "release"), ("HTIF located at 0x80101000\nSUCCESS\n", 0, "success"),
            ("FAILURE: 74 (0x0000004a)\n", 1, "failure:74"), (_BITE.format(70000), 1, "bite"),
            ("kips: 3\nInstructions:     50\n", 0, "limit")):
        ending = target.classify(log, status, limit)
        ensure(ending.label() == want, f"{want} classified as {ending.label()}: {ending.reason}")
    ensure(target.classify(_BITE.format(70000), 1, limit).ticks == 70000, "the bite's ticks were lost")
    for log, status, why in (
            (_RELEASE_LINE, None, "a timeout"), (_RELEASE_LINE + "SUCCESS\n", 0, "a release beside HTIF"),
            ("SUCCESS\nSUCCESS\n", 0, "two verdict lines"), ("SUCCESS\n", 1, "success with exit 1"),
            ("FAILURE: 74 (0x0000004b)\n", 1, "a contradicting hex code"),
            ("FAILURE: 74 (0x0000004a)\n", 0, "failure with exit 0"), (_RELEASE_LINE, 1, "release with exit 1"),
            (_BITE.format(70000), 0, "a bite with exit 0"),
            ("FAILURE: possible trap loop detected with MEPC=0x80000000\n", 1, "a trap loop"),
            ("Instructions:     49\n", 0, "a limit short of the limit"), ("", 0, "no line at all"),
            ("Instructions:     50\n", 1, "the limit with a failing exit"),
            ("Fail-stop: synchronous fault on a live trap path\n", 1, "a fail-stop"),
            ("diagnostic SUCCESS\n", 0, "a prefixed success"),
            (_RELEASE_LINE.replace("9001", "many"), 0, "a malformed release")):
        ending = target.classify(log, status, limit)
        ensure(ending.kind == "no-verdict", f"{why} gave the verdict {ending.label()}")


def _runs_decide_their_captures() -> None:
    f = bc.facts(ROOT)
    for policy, present, capture, wanted, ok in (
            ("owed", True, b"x", "success", True), ("owed", False, None, "success", False),
            ("forbidden", False, None, "bite", True), ("forbidden", True, b"x", "bite", False),
            ("either", True, b"x", "limit", True), ("either", False, None, "limit", True)):
        row: dict[str, object] = {"run": "r", "problems": [], "capture_present": present}
        found = target._decide(row, target.Ending(wanted.split(":")[0]), wanted, capture, policy)
        ensure((not found) is ok, f"policy {policy} with a capture {present}: {found}")
    found = target._decide({"run": "r", "problems": [], "capture_present": False},
                           target.Ending("no-verdict", reason="late"), "success", None, "owed")
    ensure(any("ended no-verdict" in finding for finding in found), f"a wrong ending passed: {found}")

    def program(base: int, size: int, entry: int, tohost: int) -> Any:  # noqa: ANN401
        return SimpleNamespace(symbols={"tohost": (".d", tohost), "begin_signature": (".d", base),
                                        "end_signature": (".d", base + size)}, entry=entry)
    rot = program(f["CHAIN_ROT_CAPTURE_BASE"], f["CHAIN_CAPTURE_BYTES"], 0, 8)
    main = program(f["CHAIN_MAILBOX_BASE"], f["CHAIN_MAIN_SIGNATURE_BYTES"],
                   f["CHAIN_MMODE_LOAD_BASE"], f["CHAIN_TOHOST_BASE"])
    ensure(not target.program_findings(f, rot, "boot") and not target.program_findings(f, main, "main"),
           "well-formed programs refused")
    for kind, bad in (("boot", program(f["CHAIN_ROT_CAPTURE_BASE"], 8, 0, 8)),
                      ("main", program(f["CHAIN_MAILBOX_BASE"], f["CHAIN_MAIN_SIGNATURE_BYTES"], 0,
                                       f["CHAIN_TOHOST_BASE"])),
                      ("main", program(f["CHAIN_MAILBOX_BASE"], f["CHAIN_MAIN_SIGNATURE_BYTES"],
                                       f["CHAIN_MMODE_LOAD_BASE"], 8))):
        ensure(bool(target.program_findings(f, bad, kind)), f"a malformed {kind} program passed")
    ensure(target.selection_of("cold-boot", None) == ("cold-boot",)
           and target.selection_of(None, "watchdog") == bc.GROUPS["watchdog"], "selection")
    for case, group in (("cold-boot", "watchdog"), (None, None), ("invented", None), (None, "boot")):
        try:
            target.selection_of(case, group)
        except ValueError:
            continue
        raise AssertionError(f"selection {case}, {group} accepted")
    for boot, main_, short in ((0, 1, 1), (1, 0, 1), (1, 1, 0)):
        try:
            target.run_timeouts(boot, main_, short)
        except ValueError:
            continue
        raise AssertionError("a zero timeout was accepted")


# --- the runs of a case, with the emulator stood in for ------------------------------


def _program(f: bc.Facts, kind: str) -> Any:  # noqa: ANN401
    if kind == "main":
        base, size, entry, tohost = (f["CHAIN_MAILBOX_BASE"], f["CHAIN_MAIN_SIGNATURE_BYTES"],
                                     f["CHAIN_MMODE_LOAD_BASE"], f["CHAIN_TOHOST_BASE"])
    else:
        base, size, entry, tohost = f["CHAIN_ROT_CAPTURE_BASE"], f["CHAIN_CAPTURE_BYTES"], 0, 8
    return SimpleNamespace(assembly="", sections=[], entry=entry, symbols={
        "tohost": (".d", tohost), "begin_signature": (".d", base), "end_signature": (".d", base + size)})


def _campaign(f: bc.Facts, inputs: bc.Inputs) -> target.Campaign:
    staged = bc.Staged({"floor": f.floor}, dict.fromkeys(bc.UNITS, ""), dict(inputs.images),
                       dict(inputs.roots), inputs.kernel_root)
    rot = SimpleNamespace(RomInputs=lambda **kw: kw,
                          compose_rom=lambda *_: _program(f, "boot"),
                          compose_service=lambda *_: _program(f, "service"),
                          compose_runtime_only=lambda *_: _program(f, "runtime-only"),
                          runtime_payload=lambda _, stream: b"mutant " + stream.encode())
    mmode = SimpleNamespace(compose_main=lambda *_: _program(f, "main"))
    return target.Campaign(ROOT, Path("simulator"), f, staged, inputs,
                           {row.name: row for row in bc.require_cases(ROOT)},
                           cast("Any", rot), cast("Any", mmode), target.periods(f), target.limits(f),
                           target.run_timeouts(1, 1, 1))


type Script = dict[str, tuple[target.Ending, bytes | None]]


def _emulating(script: Script) -> Callable[..., tuple[dict[str, object], target.Ending, bytes | None]]:
    def emulate(campaign: target.Campaign, directory: Path, label: str, kind: str, program: object,
                config: object) -> tuple[dict[str, object], target.Ending, bytes | None]:
        ending, capture = script[label]
        return ({"run": label, "kind": kind, "problems": [], "capture_present": capture is not None,
                 "ending": ending.label()}, ending, capture)
    return emulate


def _boot_cases_gate_their_runs() -> None:
    f = bc.facts(ROOT)
    inputs = _inputs(f)
    campaign = _campaign(f, inputs)
    cold = bc.plan(f, bc.SPECS["cold-boot"], inputs)
    script: Script = {
        "r1": (target.Ending("release", retired=9), _satisfy(bc.boot_capture(f, cold), _RELEASED)),
        "r2": (target.Ending("success", 0), bytes(bc.service_capture(f, cold).data)),
        "r3": (target.Ending("success", 0), bytes(bc.main_capture(f, cold).data))}
    with (tempfile.TemporaryDirectory() as name,
          patch.object(bc, "configuration_variant", return_value={"file": "rot-config.json"})):
        directory = Path(name)
        with patch.object(target, "emulate", _emulating(script)):
            row = target.joined_case(campaign, bc.SPECS["cold-boot"], directory)
        ensure(row["passed"] is True and [run["run"] for run in cast("list[dict[str, object]]", row["runs"])]
               == ["r1", "r2", "r3"], f"cold-boot did not pass over the oracle's bytes: {row}")
        ensure(row["r1_capture_sha256"] == receipts.digest(directory / "r1-capture.bin")
               and row["r2_response_sha256"] == receipts.digest(directory / "r2-response.bin"),
               "cold-boot's R1 capture and R2 response are not identified")
        lying = dict(script, r1=(target.Ending("release", retired=9), _satisfy(
            bc.boot_capture(f, cold), {**_RELEASED, "released": 0})))
        for changed, unrun in ((dict(script, r1=(target.Ending("no-verdict", reason="late"), None)),
                                ["r2", "r3"]), (lying, ["r2", "r3"]),
                               (dict(script, r2=(target.Ending("failure", 3), None)), ["r3"])):
            with patch.object(target, "emulate", _emulating(changed)):
                row = target.joined_case(campaign, bc.SPECS["cold-boot"], directory)
            ensure(row["passed"] is False and row["unexecuted_runs"] == unrun,
                   f"a failed run did not leave {unrun} unexecuted: {row['unexecuted_runs']}")
        halted = bc.plan(f, bc.SPECS["entropy-halt"], inputs)
        refusal: Script = {"r1": (target.Ending("success", 0), bytes(bc.boot_capture(f, halted).data))}
        with patch.object(target, "emulate", _emulating(refusal)):
            row = target.joined_case(campaign, bc.SPECS["entropy-halt"], directory)
        ensure(row["passed"] is True and len(cast("list[object]", row["runs"])) == 1,
               f"a refusal ran past R1 or failed: {row}")
        campaign.rows = {**campaign.rows, "entropy-halt": dataclasses.replace(
            campaign.rows["entropy-halt"], verdict="refuse-no-root")}
        with patch.object(target, "emulate", _emulating(refusal)):
            row = target.joined_case(campaign, bc.SPECS["entropy-halt"], directory)
        ensure(row["passed"] is False and not row["runs"], "a case the table and oracle disagree on ran")


def _main_die_takes_cold_boot() -> None:
    f = bc.facts(ROOT)
    inputs = _inputs(f)
    cold = bc.plan(f, bc.SPECS["cold-boot"], inputs)
    if cold.runtime is None or cold.service is None:
        raise AssertionError("cold-boot does not release")
    capture = bytearray(bc.boot_capture(f, cold).data)
    shared = {"source_sha256": {"a": "b"}, "timeouts": {"boot": 1}}
    with tempfile.TemporaryDirectory() as name:
        directory = Path(name)

        def receipt(passed: bool = True, **changes: object) -> None:
            (directory / "cold-boot").mkdir(exist_ok=True)
            (directory / "cold-boot/r1-capture.bin").write_bytes(bytes(capture))
            (directory / "cold-boot/r2-response.bin").write_bytes(cold.service.response
                                                                  if cold.service else b"")
            row = {"case": "cold-boot", "passed": passed, "r1_capture": "cold-boot/r1-capture.bin",
                   "r2_response": "cold-boot/r2-response.bin",
                   "r1_capture_sha256": receipts.digest(directory / "cold-boot/r1-capture.bin"),
                   "r2_response_sha256": receipts.digest(directory / "cold-boot/r2-response.bin"),
                   **changes}
            (directory / "report.json").write_text(json.dumps({**shared, "cases": [row]}),
                                                    encoding="utf-8")
        receipt()
        loaded = target.load_cold_boot(directory, shared)
        ensure(loaded is not None and loaded.record["report_sha256"] == receipts.digest(
            directory / "report.json"), "cold-boot's outputs were not loaded with their identities")
        receipt(passed=False)
        ensure(target.load_cold_boot(directory, shared) is None, "a failed cold-boot was taken")
        for change, refused in ((lambda: receipt(r1_capture_sha256="0" * 64), "differs from its receipt"),
                                (lambda: receipt(r2_response="../outside.bin"), "is not in"),
                                (lambda: (receipt(), (directory / "report.json").write_text(json.dumps(
                                    {**shared, "timeouts": {"boot": 2}, "cases": []}),
                                    encoding="utf-8")), "differs from this shard in timeouts")):
            change()
            try:
                target.load_cold_boot(directory, shared)
            except ValueError as error:
                ensure(refused in str(error), f"refused for another reason: {error}")
                continue
            raise AssertionError(f"cold-boot loaded although {refused}")
    campaign = _campaign(f, inputs)
    campaign.cold = target.ColdBoot(bytes(capture), cold.service.response, {})
    script: Script = {"r3": (target.Ending("failure", 74), None)}
    with tempfile.TemporaryDirectory() as name, patch.object(target, "emulate", _emulating(script)):
        row = target.main_die_case(campaign, bc.SPECS["kernel-signature-corrupt"], Path(name))
        ensure(row["passed"] is True, f"a main-die refusal on its exit code failed: {row}")
        script["r3"] = (target.Ending("failure", 74), b"capture")
        row = target.main_die_case(campaign, bc.SPECS["kernel-signature-corrupt"], Path(name))
        ensure(row["passed"] is False, "a capture beside FAILURE passed")
        script["r3"] = (target.Ending("failure", 81), None)
        row = target.main_die_case(campaign, bc.SPECS["item6-response-nonbinding"], Path(name))
        ensure(row["passed"] is True, f"the nonbinding response's refusal failed: {row}")
        lied = bytearray(capture)
        lied[f["CHAIN_CAPTURE_WINDOW_AT"] + 5] ^= 1
        campaign.cold = target.ColdBoot(bytes(lied), cold.service.response, {})
        row = target.main_die_case(campaign, bc.SPECS["kernel-digest-mismatch"], Path(name))
        ensure(row["passed"] is False and row["unexecuted_runs"] == ["r3"],
               "a cold-boot capture unlike the oracle's was used")


def _watchdog_cases_read_the_bite() -> None:
    f = bc.facts(ROOT)
    campaign = _campaign(f, _inputs(f))
    for case, ending, capture, ok in (
            ("watchdog-stalled-step", target.Ending("bite", ticks=f.late + 1), None, True),
            ("watchdog-stalled-step", target.Ending("bite", ticks=f.late), None, False),
            ("watchdog-stalled-step", target.Ending("bite", ticks=f.late + 1), b"c", False),
            ("watchdog-early-pet", target.Ending("bite", ticks=f.early - 1), None, True),
            ("watchdog-early-pet", target.Ending("bite", ticks=f.early), None, False),
            ("watchdog-stalled-no-clock", target.Ending("limit", retired=5), b"c", True),
            ("watchdog-stalled-no-clock", target.Ending("bite", ticks=1), None, False),
            ("watchdog-stalled-step", target.Ending("limit", retired=5), None, False)):
        with tempfile.TemporaryDirectory() as name, patch.object(
                target, "emulate", _emulating({"runtime-only": (ending, capture)})):
            row = target.runtime_only_case(campaign, bc.SPECS[case], Path(name))
        ensure(row["passed"] is ok, f"{case} ending {ending} with capture {capture} decided {row}")


# --- staging and the staged directory ----------------------------------------------


_SOURCES = {"firmware/chain/rom.c": b"int rom;\n",
            "firmware/chain/runtime.c": b"int runtime = 1; /* stall here */\n",
            "firmware/chain/mmode.c": b"int mmode;\n"}


def _checkout(root: Path) -> None:
    """A checkout holding the owners `facts` reads, the frozen sources and M7.1f's
    manifest over them, and the chain's sources."""
    for name in (bh.HEADER, bh.CHAIN_HEADER, bh.ROT_STAGE, bh.ROT_CONFIG):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, root / name)
    for name, data in {**{path: f"/* {path} */\n".encode() for path in bc.FROZEN
                          if path != bh.HEADER}, **_SOURCES}.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
    crypto = root / boot_crypto_target.MANIFEST
    crypto.parent.mkdir(parents=True, exist_ok=True)
    crypto.write_text(json.dumps({
        "sources_sha256": {path: receipts.digest(root / path) for path in bc.FROZEN},
        "compiler_provenance": {"revision": "fixture", "compiler_sha256": "c" * 64},
        "compiler_inputs_sha256": {"compcert.ini": "ini"}}), encoding="utf-8")


def _composers() -> tuple[Any, Any]:
    rot = SimpleNamespace(ROM_SOURCE="firmware/chain/rom.c", RUNTIME_SOURCE="firmware/chain/runtime.c",
                          COMPILE_ARGS=("-DVOS_CHAIN=1",),
                          RUNTIME_MUTANTS={"stall": ("= 1;", "= 2;"), "early-pet": ("stall", "pet")},
                          runtime_payload=lambda _, stream: hashlib.shake_256(stream.encode()).digest(300))
    mmode = SimpleNamespace(MMODE_SOURCE="firmware/chain/mmode.c", COMPILE_ARGS=(),
                            mmode_payload=lambda _, stream, key, tag: b"mmode" * 20 + key + tag,
                            kernel_payload=lambda _: b"kernel" * 50)
    return rot, mmode


def _compile_c(root: Path) -> Callable[..., cd.Compiled]:
    """`ccomp -S`'s stand-in: the accepted fixture stream, and a unit whose markers name
    the source and every frozen file."""
    def compile_c(ccomp: list[str], source: Path, fresh: Path, timeout: int = 0) -> cd.Compiled:
        fresh.mkdir(parents=True, exist_ok=True)
        raw = _STREAM.encode("utf-8")
        (fresh / f"{source.stem}.s").write_bytes(raw)
        unit = fresh / f"{source.stem}.i"
        unit.write_text("\n".join([f'# 1 "{source.name}"', *(
            f'# 1 "{(root / path).as_posix()}" 1' for path in (*bc.FROZEN, bh.CHAIN_HEADER))]) + "\n",
            encoding="utf-8")
        prepared = cd.Preprocessed((), str(source.parent), 0, "", unit, "", "unit")
        return cd.Compiled((*ccomp, "-S", unit.name), 0, "", _STREAM,
                           hashlib.sha256(raw).hexdigest(), len(_STREAM.splitlines()), prepared)
    return compile_c


class _Slh:
    def __init__(self, work: Path, states: tuple[str, ...], *, public_bytes: int,
                 signature_bytes: int) -> None:
        self.roots = {state: hashlib.shake_256(b"root " + state.encode()).digest(public_bytes)
                      for state in states}
        self.size = signature_bytes

    def sign(self, public: bytes, message: bytes) -> bytes:
        return _sign(bc.SLH, public, message, self.size)

    def identity(self) -> dict[str, object]:
        return {"scheme": "fixture"}


class _MlDsa:
    def __init__(self, work: Path, *, public_bytes: int, signature_bytes: int) -> None:
        self.public = hashlib.shake_256(b"kernel root").digest(public_bytes)
        self.size = signature_bytes

    def sign(self, message: bytes) -> bytes:
        return _sign(bc.MLDSA, self.public, message, self.size)

    def identity(self) -> dict[str, object]:
        return {"scheme": "fixture"}


def _staging(root: Path, out: Path) -> contextlib.ExitStack:
    rot, mmode = _composers()
    stack = contextlib.ExitStack()
    for owner, attribute, value in (
            (boot_crypto_target, "compiler_provenance", lambda _: (
                {"revision": "fixture", "compiler_sha256": "c" * 64, "kind": "fixture", "source_count": 1},
                {"/native/build-result.json": "r", "/native/build-inputs.json": "i"})),
            (boot_crypto_target, "staged", lambda _: ({}, {})),
            (target.boot_target, "compiler_inputs", lambda _: {"/native/compcert.ini": "ini"}),
            (target, "rot_composer", lambda: rot), (target, "mmode_composer", lambda: mmode),
            (cd, "compile_c", _compile_c(root)), (target.boot_signing, "SlhSigner", _Slh),
            (target, "MlDsaSigner", _MlDsa),
            (target.boot_crypto, "openssl_verify",
             lambda _, case: _verify(case.mode, case.pk, case.message, case.signature))):
        stack.enter_context(patch.object(owner, attribute, value))
    del out
    return stack


def _edit_json(path: Path, change: Callable[[dict[str, Any]], None]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def _staging_writes_what_staged_accepts() -> None:
    with tempfile.TemporaryDirectory() as name:
        template, out = Path(name) / "template", Path(name) / "out"
        _checkout(template)
        with _staging(template, out):
            written = target.stage(template, out, Path("ccomp"), ["-conf", str(out / "compcert.ini")])
            found = bc.staged(template)
            rot, mmode = _composers()
            ensure(not target.layouts(template, found, rot, mmode), "the composers' layouts disagree")
        manifest = found.manifest
        ensure(written["manifest"] == manifest and sorted(found.streams) == sorted(bc.UNITS)
               and set(found.images) == set(bc.IMAGE_NAMES), "staging wrote what staged refuses")
        ensure(all(entry["argv"][:3] == ["ccomp", "-conf", "compcert.ini"]
                   and "-Ifirmware/include" in entry["argv"] for entry in manifest["units"].values()),
               f"a staged argv kept machine paths: {manifest['units']['rom']['argv']}")
        ensure("-Ifirmware/chain" in manifest["units"]["runtime-stall"]["argv"]
               and manifest["units"]["runtime-stall"]["mutant"]["name"] == "stall",
               "a mutant's include path or name was not recorded")
        ensure(manifest["search_directories"]["firmware/chain"] == ["mmode.c", "rom.c", "runtime.c",
                                                                    "vos_chain.h"],
               f"the chain directory's listing kept the staged tree: {manifest['search_directories']}")
        ensure((out / "mutants/runtime-stall/runtime.c").read_bytes() == b"int runtime = 2; /* stall here */\n",
               "the stall substitution was not made exactly once")
        verdicts = {(entry["image"], entry["variant"]): entry["accepted"]
                    for entry in manifest["signature_verdicts"]}
        ensure(len(verdicts) == len(bc.IMAGE_NAMES) + 3
               and verdicts[("stage0", "signature-flipped")] is False, f"verdicts: {verdicts}")
        staged_dir = Path(bc.STAGED)

        def copy(root: Path) -> None:
            shutil.copytree(template, root)
        controls: list[tuple[str, Callable[[Path], object], str]] = [
            ("a changed stream", lambda root: (root / staged_dir / "rom.s").write_bytes(
                (root / staged_dir / "rom.s").read_bytes().replace(b"x11", b"x12")), "differs from its manifest"),
            ("a changed bound source", lambda root: (root / "firmware/chain/rom.c").write_bytes(b"int x;\n"),
             "changed since staging"),
            ("an extra staged file", lambda root: (root / staged_dir / "extra.s").write_bytes(b""),
             "must hold exactly"),
            ("a file shadowing an include", lambda root: (root / "firmware/include/stdint.h").write_bytes(b""),
             "the files in firmware/include changed"),
            ("M7.1f's manifest at another keccak.c", lambda root: _edit_json(
                root / boot_crypto_target.MANIFEST, lambda data: data["sources_sha256"].update(
                    {"firmware/crypto/keccak.c": "0" * 64})), "keccak.c as the chain compiled it"),
            ("M7.1f's manifest at another compiler", lambda root: _edit_json(
                root / boot_crypto_target.MANIFEST, lambda data: data["compiler_provenance"].update(
                    revision="other")), "compiler revision"),
            ("M7.1f's manifest at another compcert.ini", lambda root: _edit_json(
                root / boot_crypto_target.MANIFEST, lambda data: data.update(
                    compiler_inputs_sha256={"compcert.ini": "other"})), "compcert.ini"),
            ("a unit compiled untyped", lambda root: _edit_json(root / bc.MANIFEST, lambda data:
                data["units"]["rom"]["argv"].remove("-fverifiedos-typed")), "without -fverifiedos-typed"),
            ("an unrecorded signature", lambda root: _edit_json(root / bc.MANIFEST, lambda data:
                data.update(signature_verdicts=[])), "no OpenSSL verdict"),
            ("another campaign's manifest", lambda root: _edit_json(root / bc.MANIFEST, lambda data:
                data.update(generator="another")), "does not describe this campaign"),
            ("no staged directory", lambda root: shutil.rmtree(root / staged_dir), "is not staged"),
        ]

        def tampered_image(root: Path) -> None:
            images = root / bc.IMAGES
            data = json.loads(images.read_text(encoding="utf-8"))
            image = bytes.fromhex(data["images"]["mmode-b"])
            data["images"]["mmode-b"] = bc.flip(image, len(image) - 1).hex()
            images.write_text(json.dumps(data), encoding="utf-8")
            _edit_json(root / bc.MANIFEST, lambda manifest: manifest["files_sha256"].update(
                {"images.json": receipts.digest(images)}))
        controls.append(("an image changed beside its manifest", tampered_image, "mmode-b differs"))
        for label, change, reason in controls:
            root = Path(name) / f"control-{len(label)}-{abs(hash(label)) % 10000}"
            copy(root)
            change(root)
            with patch.object(boot_crypto_target, "staged", lambda _: ({}, {})):
                try:
                    bc.staged(root)
                except ValueError as error:
                    ensure(reason in str(error), f"{label} refused for another reason: {error}")
                    continue
            raise AssertionError(f"{label} was accepted as the staged chain")
        root = Path(name) / "relaid"
        copy(root)
        with patch.object(boot_crypto_target, "staged", lambda _: ({}, {})):
            found = bc.staged(root)
        rot, mmode = _composers()
        mmode.kernel_payload = lambda _: b"another kernel"
        ensure(any("kernel stage" in problem for problem in target.layouts(root, found, rot, mmode)),
               "a composer laying the kernel out otherwise passed")


# --- the case set, the join and the CLI ---------------------------------------------


def _case_set_is_the_contract_table() -> None:
    rows = bc.require_cases(ROOT)
    ensure([row.name for row in rows] == [spec.name for spec in bc.CASES],
           "the realized cases are not section 9.12's rows in order")
    ensure(set(bc.GROUPS["main-die"]) | set(bc.GROUPS["watchdog"]) | {
        spec.name for spec in bc.CASES if spec.run == "joined"} == set(bc.SPECS), "groups")
    original = (ROOT / bh.CONTRACT).read_text(encoding="utf-8")
    row = next(line for line in original.splitlines() if line.startswith("| `watchdog-early-pet` |"))
    for edited, why in ((original.replace(row + "\n", ""), "a missing row"),
                        (original.replace(row, row + "\n" + row.replace("early-pet", "extra")), "an added row"),
                        (original.replace(row, row.replace("runtime-only", "joined")), "another run kind")):
        with tempfile.TemporaryDirectory() as name:
            contract = Path(name) / bh.CONTRACT
            contract.parent.mkdir(parents=True)
            contract.write_text(edited, encoding="utf-8")
            try:
                bc.require_cases(Path(name))
            except ValueError:
                continue
        raise AssertionError(f"{why} in the case table was accepted")


def _shard(selection: list[str], **changes: object) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "passed", "passed": True, "selection": selection, "unexecuted_cases": [],
        "cases": [{"case": case, "run": bc.SPECS[case].run, "passed": True, "runs": [], "seconds": 1.0}
                  for case in selection],
        "cold_boot": None, "seconds": 1.0, "jobs": 1, "inputs_sha256": {},
        **{key: f"shared {key}" for key in bc.SHARED}}
    report.update(changes)
    return report


def _campaign_shards(cold_digest: str = "cold-digest") -> dict[str, dict[str, Any]]:
    cold = _shard(["cold-boot"])
    cold["cases"][0].update(r1_capture_sha256="r1", r2_response_sha256="r2")
    return {"cold": cold,
            "boot": _shard([spec.name for spec in bc.CASES
                            if spec.run == "joined" and spec.name != "cold-boot"]),
            "main": _shard(list(bc.GROUPS["main-die"]), cold_boot={
                "report_sha256": cold_digest, "r1_capture_sha256": "r1", "r2_response_sha256": "r2"}),
            "watchdog": _shard(list(bc.GROUPS["watchdog"]))}


def _chain_reports(scratch: Path) -> list[str]:
    """One consistent shard receipt per job, written for `chain-join` to compose."""
    paths = {name: scratch / "chain-shards" / name / "report.json" for name in _campaign_shards()}
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    paths["cold"].write_text(json.dumps(_campaign_shards()["cold"]), encoding="utf-8")
    shards = _campaign_shards(receipts.digest(paths["cold"]))
    for name, path in paths.items():
        if name != "cold":
            path.write_text(json.dumps(shards[name]), encoding="utf-8")
    return [str(path) for path in paths.values()]


def _join_refuses_inconsistent_shards() -> None:
    digests = {name: "cold-digest" if name == "cold" else f"{name}-digest" for name in _campaign_shards()}
    joined = bc.join(ROOT, _campaign_shards(), digests)
    ensure(joined["passed"] and not joined["unexecuted_cases"] and joined["cold_boot_passed"]
           and [row["case"] for row in joined["cases"]] == [spec.name for spec in bc.CASES],
           f"a consistent campaign did not join: {joined['unexecuted_cases']}")
    for key in bc.SHARED:
        shards = _campaign_shards()
        shards["watchdog"][key] = "another"
        try:
            bc.join(ROOT, shards, digests)
        except ValueError as error:
            ensure(f"in {key}" in str(error), f"a differing {key} refused otherwise: {error}")
            continue
        raise AssertionError(f"a shard differing in {key} joined")

    def without(*names: str) -> dict[str, dict[str, Any]]:
        return {name: shard for name, shard in _campaign_shards().items() if name not in names}
    failed_cold = _campaign_shards()
    failed_cold["cold"].update(status="failed", passed=False)
    failed_cold["cold"]["cases"][0]["passed"] = False
    failed_case = _campaign_shards()
    failed_case["boot"].update(status="failed", passed=False)
    failed_case["boot"]["cases"][2]["passed"] = False
    for label, shards, unexecuted in (
            ("a failed cold-boot", failed_cold, []), ("a failed refusal case", failed_case, []),
            ("no main-die shard", without("main"), list(bc.GROUPS["main-die"])),
            ("no cold-boot and no main-die shard", without("cold", "main"),
             ["cold-boot", *bc.GROUPS["main-die"]]),
            ("no watchdog shard", without("watchdog"), list(bc.GROUPS["watchdog"]))):
        joined = bc.join(ROOT, shards, digests)
        ensure(not joined["passed"] and joined["unexecuted_cases"] == unexecuted,
               f"{label} joined as {joined['status']} with {joined['unexecuted_cases']} unexecuted")
    ensure(not bc.join(ROOT, failed_cold, digests)["cold_boot_passed"], "a failed cold-boot passed")

    def change(name: str, **values: object) -> dict[str, dict[str, Any]]:
        shards = _campaign_shards()
        shards[name].update(values)
        return shards
    repeated = _campaign_shards()
    repeated["watchdog"] = _shard([*bc.GROUPS["watchdog"], "cold-boot"])
    contradicted = _campaign_shards()
    contradicted["boot"]["cases"][0]["passed"] = False
    controls: list[tuple[str, dict[str, Any], str]] = [
        ("a main-die shard over a missing cold-boot", without("cold"), "no shard reports"),
        ("another R1 capture", change("main", cold_boot={"report_sha256": "cold-digest",
                                                         "r1_capture_sha256": "x", "r2_response_sha256": "r2"}),
         "not the ones cold-boot's receipt records"),
        ("another cold-boot receipt", change("main", cold_boot={
            "report_sha256": "other", "r1_capture_sha256": "r1", "r2_response_sha256": "r2"}),
         "not the ones cold-boot's receipt records"),
        ("an invented case", change("watchdog", selection=["watchdog-invented"], cases=[]),
         "does not name"),
        ("a case two shards select", repeated, "repeats cold-boot"),
        ("a misstated unexecuted list", change("watchdog", unexecuted_cases=["watchdog-early-pet"]),
         "misstates its unexecuted cases"),
        ("a verdict its cases contradict", contradicted, "verdict its cases do not support"),
        ("a shard that stopped", change("boot", error="no model"), "stopped before its cases"),
        ("an incomplete shard", change("boot", status="incomplete"), "not a completed"),
        ("no shards", {}, "needs shard reports")]
    for label, shards, reason in controls:
        try:
            bc.join(ROOT, shards, digests)
        except ValueError as error:
            ensure(reason in str(error), f"{label} refused for another reason: {error}")
            continue
        raise AssertionError(f"{label} joined")
    with tempfile.TemporaryDirectory() as name:
        reports = _chain_reports(Path(name))
        with contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["chain-join", "--out", str(Path(name) / "campaign"), *reports])
        joined = json.loads((Path(name) / "campaign/report.json").read_text(encoding="utf-8"))
        ensure(code == 0 and joined["passed"] and set(joined["shard_reports_sha256"]) == set(reports),
               f"chain-join refused written shards: {joined.get('error')}")


def _cli_takes_one_selection() -> None:
    seen: list[Any] = []

    def parsed(args: Any) -> int:  # noqa: ANN401
        seen.append(args)
        return 0
    required = ["chain-target", "--staged", "--simulator", "sim", "--build-receipt", "receipt"]
    with (patch.dict(cli.TABLE, {"chain-target": (parsed, "fixture"), "chain-join": (parsed, "fixture"),
                                 "chain-stage": (parsed, "fixture")}),
          contextlib.redirect_stderr(io.StringIO())):
        ensure(cli.main([*required, "--case", "cold-boot"]) == 0, "one case did not parse")
        args = seen[-1]
        ensure(args.case == "cold-boot" and args.group is None and args.jobs == 1
               and args.timeout == target.TIMEOUTS["boot"] and args.cold_boot is None, f"{args}")
        cli.main([*required, "--group", "main-die", "--cold-boot", "dir", "--jobs", "3",
                  "--main-timeout", "60"])
        ensure(seen[-1].group == "main-die" and seen[-1].cold_boot == "dir" and seen[-1].jobs == 3
               and seen[-1].main_timeout == 60, "a group selection did not parse")
        cli.main(["chain-join", "--out", "o", "a.json", "b.json"])
        ensure(seen[-1].reports == ["a.json", "b.json"], "the join's shard receipts did not parse")
        cli.main(["chain-stage", "--ccomp", "ccomp", "--ccomp-arg=-conf", "--ccomp-arg=ini"])
        ensure(seen[-1].ccomp_arg == ["-conf", "ini"], "compiler arguments did not parse")
        for argv in ([*required], [*required, "--case", "cold-boot", "--group", "watchdog"],
                     [*required, "--case", "invented"], [*required, "--group", "boot"],
                     [*required[:1], *required[2:], "--case", "cold-boot"],
                     [*required, "--case", "cold-boot", "--jobs", "7"],
                     ["chain-join", "--out", "o"], ["chain-stage"]):
            try:
                cli.main(argv)
            except SystemExit:
                continue
            raise AssertionError(f"{argv} parsed")


# --- the workflow and the checker ---------------------------------------------------


def _workflow_runs_every_case() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    jobs = test_fanout_ci._workflow_jobs(text)
    ensure(list(jobs) == ["cold-boot", "boot", "main-die", "watchdog", "campaign"], f"jobs: {list(jobs)}")
    matrix = re.search(r"(?m)^        case: \[([^\]]*)\]", jobs["boot"])
    listed = [name.strip() for name in matrix[1].split(",")] if matrix else []
    ensure(listed == [spec.name for spec in bc.CASES if spec.run == "joined" and spec.name != bc.COLD_BOOT],
           f"the boot matrix is not the joined cases beside cold-boot: {listed}")
    ensure("--case cold-boot" in jobs["cold-boot"] and "--group main-die" in jobs["main-die"]
           and "--group watchdog" in jobs["watchdog"] and "    needs: cold-boot\n" in jobs["main-die"]
           and "    needs: [cold-boot, boot, main-die, watchdog]\n" in jobs["campaign"]
           and "--cold-boot \"$RUNNER_TEMP/cold-boot/build/boot-chain-target\"" in jobs["main-die"],
           "the jobs do not run every case group with cold-boot's outputs")
    gates = test_guest_report.WORKFLOW.read_text(encoding="utf-8")
    for job in ("cold-boot", "boot", "main-die", "watchdog", "campaign"):
        found = test_fanout_ci._refused_dispatch_faults(text, job)
        ensure(not found, f"{job} runs checked-out code after a refused dispatch: {found}")
        if job != "campaign":
            found = test_guest_report._campaign_restore_faults(gates, jobs[job])
            ensure(not found, f"{job} misses the model lane's caches: {found}")
            ensure("python3 tools/run.py boot-handoff chain-verify" in jobs[job],
                   f"{job} spends runner time before verifying the staged chain")
    pinned = set(re.findall(r"uses: (\S+@[0-9a-f]{40})", CRYPTO_WORKFLOW.read_text(encoding="utf-8")))
    ensure(set(re.findall(r"uses: (\S+)", text)) <= pinned,
           "the chain workflow runs an action the boot-crypto campaign does not pin")
    cap = re.search(r"CASE_TIMEOUT > (\d+)", text)
    steps = [int(value) for value in re.findall(
        r"- name: Execute the case\n        timeout-minutes: (\d+)", text)]
    budget = (int(cap[1]) if cap else 0) + target.TIMEOUTS["short"] + target.TIMEOUTS["main"]
    ensure(len(steps) == 2 and all(60 * step >= budget for step in steps)
           and all(int(value) <= 360 for value in re.findall(r"(?m)^    timeout-minutes: (\d+)", text)),
           f"a boot case's runs do not fit its step {steps} inside the job cap")
    default = re.search(r"(?m)^        default: (\d+)$", text)
    ensure(default is not None and int(default[1]) >= 2 * 5000 and target.TIMEOUTS["main"] >= 600,
           "the default timeouts cannot hold two SLH-DSA verifications or one ML-DSA one")


def _generated_rows_admit_only_whole_absence() -> None:
    rows = [row for row in generated.GENERATED if row.path in generated.CHAIN_PATHS]
    ensure(len(rows) == len(bc.STAGED_FILES) and set(generated.CHAIN_PATHS) <= generated.paths(),
           "the staged chain is not a set of generated rows")
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)

        def read(indexed: tuple[str, ...] = ()) -> tuple[list[str], object]:
            ctx = cast("Any", SimpleNamespace(root=root, shared={},
                                              corpus=SimpleNamespace(indexed=set(indexed))))
            found = [finding for row in rows for finding in generated._chain_row(ctx, row, None).findings]
            return found, ctx.shared.get("chain_staging")
        with patch.object(bc, "STAGED_REQUIRED", False):
            found, state = read()
        ensure(not found and state == "absent", f"a wholly absent staging was a finding: {found}")
        with patch.object(bc, "STAGED_REQUIRED", True):
            found, _ = read()
        ensure(len(found) == 1 and "required" in found[0], f"required absence passed: {found}")
        found, _ = read((generated.CHAIN_PATHS[0],))
        ensure(bool(found), "a member the index carries and the tree lacks passed")
        (root / bc.STAGED).mkdir(parents=True)
        (root / bc.MANIFEST).write_text("{}", encoding="utf-8")
        found, state = read()
        ensure(bool(found) and state not in (None, "", "absent"),
               f"a partial staging the index lacks passed: {found}")


def cases() -> list[Case]:
    return [Case("section 5's encoding, against its definition and the bring-up", _encoding_known_answers),
            Case("records follow the contract's tables", _records_follow_the_contract),
            Case("selection and counting follow section 9.6", _selection_and_counting),
            Case("the oracle agrees with the case table", _oracle_agrees_with_the_case_table),
            Case("captures are held exactly, silent fields named", _captures_are_held_exactly),
            Case("endings are section 9.2's and nothing else", _endings_are_section_9_2s),
            Case("runs decide their captures and programs", _runs_decide_their_captures),
            Case("boot cases gate their runs", _boot_cases_gate_their_runs),
            Case("main-die cases take cold-boot's outputs", _main_die_takes_cold_boot),
            Case("watchdog cases read the bite's ticks", _watchdog_cases_read_the_bite),
            Case("staging writes what the staged check accepts", _staging_writes_what_staged_accepts),
            Case("the case set is the contract's table", _case_set_is_the_contract_table),
            Case("the join refuses inconsistent shards", _join_refuses_inconsistent_shards),
            Case("the CLI takes exactly one selection", _cli_takes_one_selection),
            Case("the workflow runs every case group", _workflow_runs_every_case),
            Case("generated rows admit only whole absence", _generated_rows_admit_only_whole_absence)]
