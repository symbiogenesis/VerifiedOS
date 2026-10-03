# SPDX-License-Identifier: Apache-2.0
"""M3.5b's RoT programs: the composers' addresses, symbol spans, payload layout and mutants."""

from itertools import pairwise
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import asm, chain_rot, image
from vos import boot_handoff as bh

ROOT = TOOLS.parent

# A stand-in for a compiled stream: every C entry the assembly calls, and the one frame
# allocation the stack-ceiling reader requires. Composition never runs it.
STUB = ("vos_chain_rom:\n        cincoffsetimm c2, c2, -32\n        li a0, 0\n        ret\n"
        "vos_chain_runtime_admit:\n        ret\nvos_chain_runtime_verify:\n        ret\n"
        "vos_chain_select:\n        ret\nvos_chain_pet_due:\n        ret\n"
        "vos_chain_step_ready:\n        ret\nvos_chain_service_item6:\n        ret\n")


def _lay() -> bh.Layout:
    return chain_rot.layout(ROOT)


def _inputs(**changes: object) -> chain_rot.RomInputs:
    lay = _lay()
    fields: dict[str, object] = {
        "roots": {lay["LIFECYCLE_PRODUCTION"]: bh.root_key("production"),
                  lay["LIFECYCLE_DEVELOPMENT"]: bh.root_key("development")},
        "runtime_image": b"\x11" * 300,
        "slot_images": {lay["CHAIN_SLOT_A"]: b"\x22" * 40, lay["CHAIN_SLOT_RECOVERY"]: b"\x33" * 50},
        "floor": 2, "entropy_failed": False}
    fields.update(changes)
    return chain_rot.RomInputs(**fields)  # type: ignore[arg-type]


def _section(program: chain_rot.Program, name: str) -> image.Section:
    found = [s for s in program.sections if s.name == name]
    ensure(len(found) == 1, f"{name} appears {len(found)} times")
    return found[0]


def _captures(program: chain_rot.Program) -> None:
    lay = _lay()
    base = lay["CHAIN_ROT_CAPTURE_BASE"]
    ensure(program.symbols["begin_signature"][1] == base, "the capture does not start at its base")
    ensure(program.symbols["end_signature"][1] - base == lay["CHAIN_CAPTURE_BYTES"],
           "the signature span is not exactly capture.bytes")
    ensure(base % lay["CHAIN_ROT_CAPTURE_WINDOW_BYTES"] == 0, "the capture window's bound is not exact")
    ensure(program.symbols["tohost"][1] == chain_rot.tohost(lay), "tohost is not the word after the capture")
    capture = _section(program, ".capture")
    ensure(capture.addr == base and len(capture.data) == lay["CHAIN_CAPTURE_BYTES"]
           and not any(capture.data), "the capture is not loaded zero over its extent")
    names = {s.name for s in program.sections}
    ensure(all(section in names for section, _ in program.symbols.values()),
           "a symbol names a section the program does not load")
    spans = sorted((s.addr, s.addr + len(s.data), s.name) for s in program.sections if s.data)
    for (_, end, name), (start, _, following) in pairwise(spans):
        ensure(end <= start, f"{name} overlaps {following}")


def _rom_layout() -> None:
    lay = _lay()
    program = chain_rot.compose_rom(ROOT, STUB, _inputs())
    ensure(program.entry == chain_rot.ROM_TEXT_BASE == program.symbols["_start"][1],
           "the ROM does not start at its reset entry")
    _captures(program)
    for name, base, data in ((".store-runtime", lay["CHAIN_STORE_RUNTIME_BASE"], b"\x11" * 300),
                             (".store-a", lay["CHAIN_STORE_A_BASE"], b"\x22" * 40),
                             (".store-recovery", lay["CHAIN_STORE_RECOVERY_BASE"], b"\x33" * 50)):
        section = _section(program, name)
        ensure(section.addr == base and bytes(section.data) == data, f"{name} is misplaced")
    ensure(".store-b" not in {s.name for s in program.sections}, "an absent slot image was placed")
    state = _section(program, ".state")
    ensure(state.addr == lay["CHAIN_ROT_STATE_BASE"] and not any(state.data), "the state window is not zero")
    table = bytes(_section(program, ".roots").data)
    present = int.from_bytes(table[:8], "little")
    ensure(present == (1 << lay["LIFECYCLE_PRODUCTION"]) | (1 << lay["LIFECYCLE_DEVELOPMENT"]),
           "the root table's presence word is wrong")
    at = chain_rot.ROOT_TABLE_KEYS_AT + lay["LIFECYCLE_PRODUCTION"] * lay["BOOT_PUBLIC_KEY_BYTES"]
    ensure(table[at:at + 64] == bh.root_key("production"), "the production root is misplaced")
    raw = chain_rot.ROOT_TABLE_KEYS_AT + lay["LIFECYCLE_RAW"] * lay["BOOT_PUBLIC_KEY_BYTES"]
    ensure(not any(table[raw:raw + 64]), "the raw state holds a root")
    ensure((chain_rot.ROOT_TABLE_BASE + chain_rot.ROOT_TABLE_KEYS_AT) % lay["BOOT_PUBLIC_KEY_BYTES"] == 0,
           "a root's capability bound is not exact")
    text = _section(program, ".text")
    ensure(text.addr + len(text.data) <= chain_rot.ROM_DATA_BASE, "the ROM's text overruns its data")
    ensure("ROM_FLOOR_ADVANCES, 0x2\n" in program.assembly
           and "ROM_ENTROPY_FAILED, 0x0\n" in program.assembly, "the run parameters are not composed")
    failed = chain_rot.compose_rom(ROOT, STUB, _inputs(entropy_failed=True, floor=3))
    ensure("ROM_ENTROPY_FAILED, 0x1\n" in failed.assembly and "ROM_FLOOR_ADVANCES, 0x3\n" in failed.assembly,
           "the entropy injection or the floor did not reach the assembly")


def _rom_refuses_bad_inputs() -> None:
    lay = _lay()
    for changes in ({"floor": 0}, {"floor": 17},
                    {"roots": {lay["LIFECYCLE_COUNT"]: bh.root_key("production")}},
                    {"roots": {3: b"\x00" * 63}},
                    {"slot_images": {3: b"\x00"}},
                    {"runtime_image": bytes(lay["CHAIN_STORE_RUNTIME_BYTES"] + 1)}):
        try:
            chain_rot.compose_rom(ROOT, STUB, _inputs(**changes))
        except ValueError:
            continue
        raise AssertionError(f"compose_rom accepted {sorted(changes)}")


def _payload_is_flat() -> None:
    lay = _lay()
    base = lay["CHAIN_ROT_RUNTIME_BASE"]
    data_at = lay["CHAIN_ROT_RUNTIME_DATA_AT"]
    source = chain_rot.runtime_assembly(ROOT, STUB)
    sections, symbols, entry = asm.Assembler(source, "runtime-test", text_base=base,
                                             data_base=base + data_at).assemble()
    text = next(s for s in sections if s.name == ".text")
    data = next(s for s in sections if s.name == ".data")
    payload = chain_rot.runtime_payload(ROOT, STUB)
    ensure(entry == base == symbols["_start"][1], "the runtime's entry is not its base")
    ensure(len(payload) == data_at + len(data.data), "the payload does not end at the data's end")
    ensure(payload[:len(text.data)] == bytes(text.data), "the text is not at the payload's start")
    ensure(not any(payload[len(text.data):data_at]), "the gap between text and data is not zero")
    ensure(payload[data_at:] == bytes(data.data), "the data half is not at chain.rot_runtime_data_at")
    ensure(len(payload) <= lay["CHAIN_ROT_RUNTIME_REGION_BYTES"], "the payload overruns its region")
    ensure(symbols["__rt_stack"][1] % chain_rot.STACK_BYTES == 0, "the runtime's stack bound is not exact")


def _mutants_occur_once() -> None:
    text = (ROOT / chain_rot.RUNTIME_SOURCE).read_text(encoding="utf-8")
    ensure(set(chain_rot.RUNTIME_MUTANTS) == {"stall", "early-pet"}, "section 9.10's mutants are not the two")
    for name, (old, new) in chain_rot.RUNTIME_MUTANTS.items():
        ensure(text.count(old) == 1, f"the {name} mutant's text occurs {text.count(old)} times")
        ensure(new not in text, f"the {name} mutant's replacement is already in the runtime")
        mutated = chain_rot.mutated_source(ROOT, name)
        ensure(new in mutated and old not in mutated and len(mutated) == len(text) - len(old) + len(new),
               f"the {name} mutant was not applied exactly once")
    stall_old, stall_new = chain_rot.RUNTIME_MUTANTS["stall"]
    ensure(">> 32)" in stall_old and ">> 32)" not in stall_new,
           "the stall mutant does not move step.entropy's completion bit")
    early_old, early_new = chain_rot.RUNTIME_MUTANTS["early-pet"]
    ensure("ticks >=" in early_old and "ticks >=" not in early_new and "return 1u" in early_new,
           "the early-pet mutant still consults the tick count")
    entry = (ROOT / chain_rot.RUNTIME_ASSEMBLY).read_text(encoding="utf-8")
    ensure(entry.count("call    vos_chain_step_ready") == 3 and entry.count("call    vos_chain_pet_due") == 4,
           "the assembly does not ask the C decisions at three steps and four pet points")
    try:
        chain_rot.mutated_source(ROOT, "absent")
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown mutant was accepted")


def _runtime_only_and_service() -> None:
    lay = _lay()
    payload = chain_rot.runtime_payload(ROOT, STUB)
    state = bytes(range(256))
    only = chain_rot.compose_runtime_only(ROOT, payload, state, 4)
    _captures(only)
    ensure(only.entry == chain_rot.ROM_TEXT_BASE, "the preamble is not the runtime-only entry")
    ensure("PREAMBLE_FLOOR_ADVANCES, 0x4\n" in only.assembly, "the preamble's floor is not composed")
    runtime = _section(only, ".runtime")
    ensure(runtime.addr == lay["CHAIN_ROT_RUNTIME_BASE"] and bytes(runtime.data) == payload,
           "the payload is not placed at the runtime base")
    ensure(bytes(_section(only, ".state").data) == state, "the state record is not placed")
    request = bytes(range(64))
    service = chain_rot.compose_service(ROOT, payload, state, request)
    _captures(service)
    ensure(service.entry == lay["CHAIN_ROT_RUNTIME_BASE"], "the service run does not enter the runtime base")
    window = bytes(_section(service, ".state").data)
    at = lay["CHAIN_STATE_REQUEST_AT"]
    ensure(window[:256] == state and window[at:at + 64] == request,
           "the request is not at state.request_at")
    for call in (lambda: chain_rot.compose_runtime_only(ROOT, payload, state[:-1], 2),
                 lambda: chain_rot.compose_runtime_only(ROOT, b"", state, 2),
                 lambda: chain_rot.compose_service(ROOT, payload, state, request[:-1])):
        try:
            call()
        except ValueError:
            continue
        raise AssertionError("a malformed runtime-only or service input was accepted")


def _equates_follow_owners() -> None:
    lay = _lay()
    values = chain_rot.equates(ROOT)
    ensure(values["CHAIN_INPUT_BYTES"] == 48 and values["CHAIN_INPUT_HEALTH_WORD_AT"] == 8
           and values["CHAIN_INPUT_ATTEMPTS_AT"] == 40, "the inputs record's layout is not vos_chain.h's")
    ensure(values["CHAIN_SELECTION_CHARGED_AT"] == 24 and values["CHAIN_SELECTION_BYTES"] == 32,
           "the selection record's layout is not vos_chain.h's")
    ensure(values["CHAIN_POLICY_BYTES"] == lay["LIFECYCLE_COUNT"] * chain_rot.POINTER_BYTES,
           "the policy is not one capability per lifecycle state")
    ensure(values["ROT_TRNG_HEALTH"] == 8 and values["ROT_WDT_ARM"] == 48,
           "rot.sail's door offsets were not read")
    ensure(all(values[name] == lay.c[name] for name in lay.c), "a header macro was restated")
    ensure((chain_rot.FAILED_HEALTH >> 32) & 3 == 2, "the injected health word does not fail")
    args = chain_rot.compile_args(Path("/x"))
    ensure(args[:2] == ["-fverifiedos-typed", f"-I{Path('/x') / 'firmware/include'}"],
           "section 9.13's compile arguments are not first")


def cases() -> list[Case]:
    return [Case("the ROM program places every window at its address", _rom_layout),
            Case("the ROM composer refuses malformed inputs", _rom_refuses_bad_inputs),
            Case("the stage-0 payload is flat with its data at its offset", _payload_is_flat),
            Case("each runtime mutant names one line of runtime.c's decisions", _mutants_occur_once),
            Case("runtime-only and service runs place payload, state and request", _runtime_only_and_service),
            Case("the assembly's constants come from their owners", _equates_follow_owners)]
