# SPDX-License-Identifier: Apache-2.0
"""The chain's M-mode stage and kernel stage as bytes, and the main-die run's composition."""

import hashlib
import tempfile
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import boot_handoff as bh
from vos import chain_mmode as cm
from vos import image

ROOT = TOOLS.parent

# A stand-in for the contained compiler's stream: the body's entry symbol and one frame
# in the compiler's allocation shape. The pure tests never run the compiler.
STUB = """\
.text
.globl vos_chain_mmode_entry
vos_chain_mmode_entry:
\tcmove c30, c2
\tcincoffsetimm c2, c2, -32
\tsc c30, 8(c2)
\tli a0, 0
\tlc c2, 8(c2)
\tcjalr cnull, cra, 0
"""


def _refuses(call: Callable[..., object], *args: object) -> bool:
    try:
        call(*args)
    except ValueError:
        return True
    return False


def _word(blob: bytes, at: int) -> int:
    return int.from_bytes(blob[at:at + 8], "little")


def _kernel_layout() -> None:
    lay = bh.chain_layout(ROOT)
    built = cm.kernel_image(ROOT)
    base = lay["CHAIN_KERNEL_LOAD_BASE"]
    payload = cm.kernel_payload(ROOT)
    ensure(payload == built.payload, "the kernel payload is not the assembled image")
    ensure(lay["CHAIN_KERNEL_INIT_AT"] + lay["CHAIN_KERNEL_INIT_BYTES"] == len(payload)
           <= lay["CHAIN_KERNEL_REGION_BYTES"], f"the kernel payload is {len(payload)} bytes")
    text = base + lay["CHAIN_KERNEL_TEXT_AT"]
    for label, want in (("kernel_entry", text + lay["CHAIN_KERNEL_ENTRY_AT"]),
                        ("kernel_trap", text + lay["CHAIN_KERNEL_TRAP_AT"]),
                        ("kernel_text_end", text + lay["CHAIN_KERNEL_TEXT_BYTES"]),
                        ("tohost", lay["CHAIN_TOHOST_BASE"]),
                        ("kstack_base", base + lay["CHAIN_KERNEL_STACK_AT"]),
                        ("root_table", base + lay["CHAIN_KERNEL_ROOT_TABLE_AT"]),
                        ("init_desc", base + lay["CHAIN_KERNEL_INIT_AT"])):
        ensure(built.symbols[label] == want, f"{label} is at {built.symbols[label]:#x}, not {want:#x}")
    trap = lay["CHAIN_KERNEL_TEXT_AT"] + lay["CHAIN_KERNEL_TRAP_AT"]
    ensure(payload[trap:trap + 4] != bytes(4), "the trap entry holds no instruction")
    tohost = lay["CHAIN_TOHOST_BASE"] - base
    ensure(payload[tohost:tohost + 8] == bytes(8), "the image's tohost word is not zero")
    ensure(not any(payload[lay["CHAIN_KERNEL_ROOT_TABLE_AT"]:][:lay["CHAIN_KERNEL_ROOT_TABLE_BYTES"]]),
           "the root table's slot is not empty in the image")


def _kernel_descriptor() -> None:
    lay = bh.chain_layout(ROOT)
    payload = cm.kernel_payload(ROOT)
    base = lay["CHAIN_KERNEL_LOAD_BASE"]
    desc = payload[lay["CHAIN_KERNEL_INIT_AT"]:][:lay["CHAIN_KERNEL_INIT_BYTES"]]
    expected = {
        "INIT_MAGIC_AT": lay["INIT_MAGIC"], "INIT_VERSION_AT": lay["INIT_VERSION"],
        "INIT_COMPOSITION_AT": 1, "INIT_HART_AT": 0,
        "INIT_ROOT_AT": base, "INIT_SWITCH_TEXT_AT": base + lay["CHAIN_KERNEL_TEXT_AT"],
        "INIT_PARTITION_COUNT_AT": 0, "INIT_WINDOW_COUNT_AT": 0, "INIT_SLOT_COUNT_AT": 0,
        "INIT_CSR_COUNT_AT": 0,
    }
    for macro, value in expected.items():
        ensure(_word(desc, lay[macro]) == value, f"the descriptor's {macro} is {_word(desc, lay[macro]):#x}")
    ensure(_word(desc, lay["INIT_ROOT_AT"] + 8) == base + lay["CHAIN_KERNEL_REGION_BYTES"],
           "the descriptor's root extent is not the kernel region")
    ensure(_word(desc, lay["INIT_SWITCH_TEXT_AT"] + 8)
           == base + lay["CHAIN_KERNEL_TEXT_AT"] + lay["CHAIN_KERNEL_TEXT_BYTES"],
           "the descriptor's switch text is not the kernel text")
    ensure(not any(desc[lay["INIT_MAJOR_FRAME_AT"]:]), "the descriptor plans a schedule")


def _checks_unchanged() -> None:
    def checks(path: str) -> str:
        text = (ROOT / path).read_text(encoding="utf-8")
        start, end = text.index("kernel_entry:\n"), text.index("trap_halt:\n")
        return text[start:end].replace("        # The trap entry sits at kernel.trap_at, where the M-mode stage points\n"
                                       "        # MTCC, which derives it from that constant and not from this label.\n"
                                       "        .align  11\n", "")

    ensure(checks(bh.FIXTURE) == checks(cm.KERNEL_STAGE),
           "the kernel stage's checks are not the bring-up fixture's")


def _kernel_drift_refused() -> None:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        for name in (bh.HEADER, bh.CHAIN_HEADER, cm.KERNEL_STAGE):
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes((ROOT / name).read_bytes())
        stage = root / cm.KERNEL_STAGE
        text = stage.read_text(encoding="utf-8")
        anchor = "        .align  11\nkernel_trap:"
        ensure(anchor in text, "the trap alignment anchor is gone")
        stage.write_text(text.replace(anchor, "kernel_trap:"), encoding="utf-8")
        ensure(_refuses(cm.kernel_image, root), "a trap entry off kernel.trap_at was accepted")


def _mmode_payload() -> None:
    lay = bh.chain_layout(ROOT)
    key = hashlib.shake_256(b"chain-mmode test root").digest(lay["CHAIN_KSTAGE_PUBLIC_KEY_BYTES"])
    tags = cm.slot_tag_bytes(ROOT)
    ensure(tags == (b"VOSSLOTA", b"VOSSLOTB", b"VOSRCVRY"), f"unexpected slot tags {tags}")
    payloads = [cm.mmode_payload(ROOT, STUB, key, tag) for tag in tags]
    built = cm.mmode_image(ROOT, STUB, key)
    data_at = lay["CHAIN_MMODE_DATA_AT"]
    for tag, payload in zip(tags, payloads, strict=True):
        ensure(payload == built.payload + tag, "the tag is not appended to the flat image")
        ensure(len(payload) == data_at + len(key) + lay["CHAIN_SLOT_TAG_BYTES"],
               f"the payload is {len(payload)} bytes")
        ensure(payload[data_at:data_at + len(key)] == key, "the root is not the data half's first datum")
    ensure(len({hashlib.shake_256(p).digest(32) for p in payloads}) == 3, "the slots' digests collide")
    base = lay["CHAIN_MMODE_LOAD_BASE"]
    ensure(built.symbols["_start"] == base and built.symbols[cm.ROOT_LABEL] == base + data_at,
           "the entry or the root is misplaced")
    ensure(built.constants["MMODE_STACK_TOP"] == base + lay["CHAIN_MMODE_REGION_BYTES"]
           and built.constants["MMODE_STACK_BASE"] >= base + len(payloads[0]),
           "the body's stack is not the region's top, clear of the payload")
    ensure(built.payload[:4] != bytes(4), "the entry holds no instruction")


def _mmode_refusals() -> None:
    lay = bh.chain_layout(ROOT)
    key = bytes(lay["CHAIN_KSTAGE_PUBLIC_KEY_BYTES"])
    ensure(_refuses(cm.mmode_payload, ROOT, STUB, key, b"VOSSLOTC"), "an unknown tag was accepted")
    ensure(_refuses(cm.mmode_payload, ROOT, STUB, key[:-1], b"VOSSLOTA"), "a short root was accepted")
    ensure(_refuses(cm.mmode_payload, ROOT, STUB.replace("vos_chain_mmode_entry", "other"), key,
                    b"VOSSLOTA"), "a stream without the body's entry was accepted")
    ensure(_refuses(cm.mmode_payload, ROOT, STUB + "\tmul.wide a0, a0, a0\n", key, b"VOSSLOTA"),
           "a stream outside the dialect was accepted")
    deep = STUB.replace("\tcincoffsetimm c2, c2, -32\n", "\tli x5, -40000\n\tcincoffset c2, c2, x5\n")
    ensure(_refuses(cm.mmode_payload, ROOT, deep, key, b"VOSSLOTA"),
           "a frame sum beyond the stage's stack was accepted")


def _permissions_held() -> None:
    key = bytes(bh.chain_layout(ROOT)["CHAIN_KSTAGE_PUBLIC_KEY_BYTES"])
    stage, kernel = cm.mmode_image(ROOT, STUB, key), cm.kernel_image(ROOT)
    joined = bh.Assembled(stage.payload, stage.symbols, {**kernel.constants, **stage.constants})
    findings = bh.entry_table_findings(ROOT, joined)
    ensure(findings == [], f"section 6's permissions and the chain stage disagree: {findings}")


def _main_die_composition() -> None:
    lay = bh.chain_layout(ROOT)
    window = bytes([0x13]) * lay["CHAIN_MMODE_REGION_BYTES"]
    record = bytes([0x5a]) * lay["HANDOFF_BYTES"]
    response = bytes([0xa5]) * lay["CHAIN_RESPONSE_BYTES"]
    mailbox = bytes(lay["CHAIN_MAILBOX_RESPONSE_AT"]) + response
    store = bytes([0x77]) * (lay["CHAIN_KSTAGE_HEADER_BYTES"] + 100)
    program = cm.compose_main(ROOT, window, record, mailbox, store)
    ensure(program.entry == lay["CHAIN_MMODE_LOAD_BASE"] and program.assembly == "",
           "the main-die run does not start at the M-mode load base")
    placed = {section.name: section for section in program.sections}
    for name, address, blob in ((".mmode", lay["CHAIN_MMODE_LOAD_BASE"], window),
                                (".handoff", lay["CHAIN_HANDOFF_BASE"], record),
                                (".kstore", lay["CHAIN_KERNEL_STORE_BASE"], store),
                                (".signature", lay["CHAIN_MAILBOX_BASE"], mailbox)):
        ensure(placed[name].addr == address and bytes(placed[name].data[:len(blob)]) == blob,
               f"{name} is not placed at {address:#x}")
    ensure(len(placed[".kstore"].data) == lay["CHAIN_KERNEL_STORE_BYTES"]
           and not any(placed[".kstore"].data[len(store):]), "the kernel store is not zero-padded")
    ensure(len(placed[".signature"].data) == lay["CHAIN_MAIN_SIGNATURE_BYTES"]
           and not any(placed[".signature"].data[len(mailbox):]), "the signature region is not zero")
    kernel = placed[".kernel"]
    ensure(kernel.addr == lay["CHAIN_KERNEL_LOAD_BASE"]
           and bytes(kernel.data) == bytes(lay["CHAIN_KERNEL_REGION_BYTES"]), "the kernel region is not zero")
    ensure(program.symbols["tohost"] == (".kernel", lay["CHAIN_TOHOST_BASE"]), "tohost is misplaced")
    ensure(program.symbols["begin_signature"] == (".signature", lay["CHAIN_MAILBOX_BASE"])
           and program.symbols["end_signature"]
           == (".signature", lay["CHAIN_MAILBOX_BASE"] + lay["CHAIN_MAIN_SIGNATURE_BYTES"]),
           "the signature region is not the mailbox base's main_signature_bytes")
    spans = sorted((section.addr, section.addr + len(section.data)) for section in program.sections)
    ensure(all(end <= start for (_, end), (start, _) in pairwise(spans)),
           "two main-die sections overlap")
    with tempfile.TemporaryDirectory() as scratch:
        elf = Path(scratch) / "r3.elf"
        image.write_elf(elf, program.sections, program.symbols, program.entry)
        ensure(elf.read_bytes()[:4] == b"\x7fELF", "the main-die image is not an ELF")
    nonzero_request = bytes([1]) + mailbox[1:]
    for args, what in (((window[:-1], record, mailbox, store), "a short window"),
                       ((window, record[:-1], mailbox, store), "a short record"),
                       ((window, record, nonzero_request, store), "a written request slot"),
                       ((window, record, mailbox, store[:10]), "a truncated stage-2 image"),
                       ((window, record, mailbox, bytes(lay["CHAIN_KERNEL_STORE_BYTES"] + 1)),
                        "an oversized stage-2 image")):
        ensure(_refuses(cm.compose_main, ROOT, *args), f"{what} was accepted")


def cases() -> list[Case]:
    return [Case("the kernel stage is laid out by the kernel.* table", _kernel_layout),
            Case("the kernel stage's descriptor names the kernel region and text", _kernel_descriptor),
            Case("the kernel stage keeps the fixture's eleven checks", _checks_unchanged),
            Case("a kernel stage off its table is refused", _kernel_drift_refused),
            Case("the stage-1 payload carries the root and its slot tag", _mmode_payload),
            Case("the stage-1 composer refuses malformed inputs", _mmode_refusals),
            Case("section 6's permissions hold for the chain stage", _permissions_held),
            Case("the main-die run places every window", _main_die_composition)]
