# SPDX-License-Identifier: Apache-2.0
"""M3.5's boot-handoff harness: the RoT's measured release of the boot core, end to end.

[The boot-handoff contract](../../docs/implementation/contracts/boot-handoff.md) states
the predicate this module decides and the layout it builds. The pieces, in the order a
run meets them:

1. The RoT stage is [boot_verify.c](../../firmware/rot/boot_verify.c) compiled for the
   host with [the harness driver](../../firmware/harness/rot_stage_main.c), standing in
   for the RoT hart until the purecap backend and M1.7's target path can build it for
   the RoT composition. Every report says so.
2. Its device inputs come from the golden emulator running
   [the probe](../../firmware/harness/rot_inputs.s) under the RoT composition, so the
   lifecycle state, the entropy verdict and the floor are the model's answers.
3. The M-mode image is [the handoff stage](../../firmware/mmode/handoff.s) assembled
   with [the kernel-entry fixture](../../firmware/harness/kernel_entry_fixture.s) by the
   in-tree assembler, then wrapped in the fixed-layout header with a **fixture
   signature**, which is not a signature scheme (see `fixture_signature`).
4. A release is the golden emulator started on the main-die composition from exactly
   the bytes the RoT stage placed and the record it wrote; a refusal starts no run.

The layout constants are read from [vos_boot.h](../../firmware/include/vos_boot.h),
which owns them, so this module restates none of them.
"""

import ast
import hashlib
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import asm, image, trace

HEADER = "firmware/include/vos_boot.h"
SOURCES = ("firmware/include/vos_keccak.h", "firmware/include/vos_boot.h",
           "firmware/crypto/keccak.c", "firmware/rot/boot_verify.c",
           "firmware/harness/rot_stage_main.c")
C_UNITS = ("firmware/crypto/keccak.c", "firmware/rot/boot_verify.c",
           "firmware/harness/rot_stage_main.c")
MMODE = "firmware/mmode/handoff.s"
FIXTURE = "firmware/harness/kernel_entry_fixture.s"
PROBE = "firmware/harness/rot_inputs.s"
ROT_CONFIG = "model/config/verifiedos-rot.json"
MAIN_CONFIG = "model/config/verifiedos.json"
CONTRACT = "docs/implementation/contracts/boot-handoff.md"
INPUTS = (*SOURCES, MMODE, FIXTURE, PROBE, ROT_CONFIG, MAIN_CONFIG, CONTRACT)

CFLAGS = ("-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
          "-fsanitize=address,undefined", "-fno-sanitize-recover=all")

# Not a signature scheme: anyone holding the public key computes it. It lets the
# harness exercise the accept and reject arms a real verifier would take, and it is
# spelled identically in the C driver, which checks it with its own SHAKE256.
FIXTURE_DOMAIN = b"VOS-FIXTURE-SIG1"

LIFECYCLES = ("raw", "test", "development", "production", "rma")

# The harness's root public keys, one per lifecycle state that accepts one: a
# deterministic stand-in for the composition's provisioned roots.
ROOT_STATES = ("test", "development", "production", "rma")

_DEFINE = re.compile(r"^#define\s+(VOS_\w+)\s+(.+?)\s*(?://.*)?$")
_SUFFIX = re.compile(r"\b(0[xX][0-9A-Fa-f]+|\d+)[uU]\b")


def _evaluate(node: ast.expr) -> int:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        return left * right
    raise ValueError(f"{HEADER}: unsupported expression {ast.dump(node)}")


def header_constants(root: Path) -> dict[str, int]:
    """Every integer macro of vos_boot.h, evaluated over the ones before it.

    String macros are skipped; an expression naming a macro not yet defined, or using
    an operator other than +, - and *, is refused rather than guessed.
    """
    values: dict[str, int] = {}
    for line in (root / HEADER).read_text(encoding="utf-8").splitlines():
        match = _DEFINE.match(line.strip())
        if not match or match.group(2).startswith('"'):
            continue
        text = _SUFFIX.sub(r"\1", match.group(2))
        for name in sorted(re.findall(r"\bVOS_\w+\b", text), key=len, reverse=True):
            if name not in values:
                raise ValueError(f"{HEADER}: {match.group(1)} names {name} before it is defined")
            text = re.sub(rf"\b{name}\b", str(values[name]), text)
        values[match.group(1)] = _evaluate(ast.parse(text, mode="eval").body)
    return values


def string_constants(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (root / HEADER).read_text(encoding="utf-8").splitlines():
        match = _DEFINE.match(line.strip())
        if match and match.group(2).startswith('"') and match.group(2).endswith('"'):
            values[match.group(1)] = match.group(2)[1:-1]
    return values


@dataclass(frozen=True)
class Layout:
    """The header, record and composition constants a run uses, from vos_boot.h."""

    c: dict[str, int]

    def __getitem__(self, name: str) -> int:
        return self.c[f"VOS_{name}"]


def layout(root: Path) -> Layout:
    return Layout(header_constants(root))


def expected_registers(root: Path, lay: Layout, inputs: RotInputs,
                       image_digest: bytes | None) -> tuple[str, str, str]:
    """The generation register, device register and chain digest, recomputed here.

    The encoding is section 5's, over hashlib's SHAKE256, so the C extension is held
    against a second implementation of the same stated encoding rather than against
    its own report. `image_digest` is None for a refusal, which extends item 5 never.
    """
    domains = string_constants(root)
    extend_domain = domains["VOS_MEASURE_EXTEND_DOMAIN"].encode()
    chain_domain = domains["VOS_MEASURE_CHAIN_DOMAIN"].encode()
    width = lay["MEASURE_BYTES"]

    def extend(register: bytes, code: int, data: bytes) -> bytes:
        return hashlib.shake_256(extend_domain + register + bytes([code])
                                 + len(data).to_bytes(4, "little") + data).digest(width)

    device = bytes(width)
    for code, value in ((lay["ITEM_LIFECYCLE"], inputs.lifecycle),
                        (lay["ITEM_ENTROPY_VERDICT"], 1 if inputs.entropy_ok else 0),
                        (lay["ITEM_BOOT_TARGET"], inputs.boot_target & 1)):
        device = extend(device, code, bytes([value]))
    generation = bytes(width)
    if image_digest is not None:
        generation = extend(generation, lay["ITEM_STAGE_MMODE_IMAGE"], image_digest)
    chain = hashlib.shake_256(chain_domain + generation + device).digest(width)
    return generation.hex(), device.hex(), chain.hex()


def fixture_signature(lay: Layout, public_key: bytes, message: bytes) -> bytes:
    return hashlib.shake_256(FIXTURE_DOMAIN + public_key + message).digest(
        lay["BOOT_SIGNATURE_BYTES"])


def root_key(state: str) -> bytes:
    return hashlib.shake_256(f"VOS-HARNESS-ROOT {state}".encode()).digest(64)


@dataclass
class Assembled:
    """The M-mode stage and fixture as one flat payload from the load base."""

    payload: bytes
    symbols: dict[str, int]
    constants: dict[str, int]


def assemble_mmode(root: Path, stage_text: str | None = None) -> Assembled:
    """Assemble the handoff stage followed by the fixture, and flatten the image.

    `stage_text` replaces the stage's source, which is how the handoff mutants are
    built. The flat payload runs from the text base to the end of `.data`, the gap
    between the two sections zero-filled, which is the extent the RoT measures.
    """
    stage = stage_text if stage_text is not None else (root / MMODE).read_text(encoding="utf-8")
    source = stage + "\n" + (root / FIXTURE).read_text(encoding="utf-8")
    assembler = asm.Assembler(source, "mmode-image")
    sections, _, _ = assembler.assemble()
    text = next(s for s in sections if s.name == ".text")
    data = next(s for s in sections if s.name == ".data")
    if text.addr >= data.addr or text.addr + len(text.data) > data.addr:
        raise ValueError("the image's text overruns its data base")
    flat = bytearray(data.addr + len(data.data) - text.addr)
    flat[0:len(text.data)] = text.data
    flat[data.addr - text.addr:] = data.data
    constants = {name: value for name, (value, _) in assembler.constants.items()}
    return Assembled(bytes(flat), dict(assembler.symbols), constants)


def composition_findings(lay: Layout, built: Assembled) -> list[str]:
    """Where the assembled image and vos_boot.h disagree about the composition."""
    findings = []
    if lay["BRINGUP_MMODE_LOAD_BASE"] != asm.TEXT_BASE:
        findings.append(f"the assembler's text base {asm.TEXT_BASE:#x} is not the load base "
                        f"{lay['BRINGUP_MMODE_LOAD_BASE']:#x}")
    for constant, macro, owner in (("BOOT_DESCRIPTOR", "BRINGUP_HANDOFF_BASE", MMODE),
                                   ("BOOT_DESCRIPTOR_BYTES", "HANDOFF_BYTES", MMODE),
                                   ("FIXTURE_HANDOFF_MAGIC", "HANDOFF_MAGIC", FIXTURE),
                                   ("FIXTURE_INIT_MAGIC", "INIT_MAGIC", FIXTURE),
                                   ("FIXTURE_INIT_VERSION", "INIT_VERSION", FIXTURE),
                                   ("FIXTURE_LOAD_BASE", "BRINGUP_MMODE_LOAD_BASE", FIXTURE),
                                   ("FIXTURE_REGION_BYTES", "BRINGUP_MMODE_REGION_BYTES",
                                    FIXTURE)):
        if built.constants.get(constant) != lay[macro]:
            findings.append(f"{owner}'s {constant} is not VOS_{macro}")
    if len(built.payload) > lay["BRINGUP_MMODE_REGION_BYTES"]:
        findings.append(f"the payload's {len(built.payload)} bytes exceed the region")
    if lay["BRINGUP_HANDOFF_BASE"] < lay["BRINGUP_MMODE_LOAD_BASE"] + lay[
            "BRINGUP_MMODE_REGION_BYTES"]:
        findings.append("the handoff record overlaps the M-mode image region")
    return findings + descriptor_findings(lay, built)


def descriptor_findings(lay: Layout, built: Assembled) -> list[str]:
    """The fixture's initialization descriptor against section 6's layout.

    Its magic and version are the macros', and its extent is exactly the header plus
    the arrays its four counts declare, so a descriptor that is too short for its
    counts or carries trailing bytes is reported.
    """
    base = built.symbols.get("init_desc")
    end = built.symbols.get("init_desc_end")
    if base is None or end is None:
        return [f"{FIXTURE} has no init_desc or init_desc_end label"]
    at = base - lay["BRINGUP_MMODE_LOAD_BASE"]
    blob = built.payload[at:at + (end - base)]

    def word(macro: str) -> int:
        offset = lay[macro]
        return int.from_bytes(blob[offset:offset + 8], "little")

    if len(blob) < lay["INIT_HEADER_BYTES"]:
        return [f"the initialization descriptor's {len(blob)} bytes are shorter than "
                f"its {lay['INIT_HEADER_BYTES']}-byte header"]
    findings = []
    if word("INIT_MAGIC_AT") != lay["INIT_MAGIC"]:
        findings.append("the initialization descriptor's magic is not VOS_INIT_MAGIC")
    if word("INIT_VERSION_AT") != lay["INIT_VERSION"]:
        findings.append("the initialization descriptor's version is not VOS_INIT_VERSION")
    implied = (lay["INIT_HEADER_BYTES"]
               + word("INIT_PARTITION_COUNT_AT") * lay["INIT_PARTITION_BYTES"]
               + word("INIT_WINDOW_COUNT_AT") * lay["INIT_WINDOW_BYTES"]
               + word("INIT_SLOT_COUNT_AT") * lay["INIT_SLOT_BYTES"]
               + word("INIT_CSR_COUNT_AT") * lay["INIT_CSR_BYTES"])
    if implied != len(blob):
        findings.append(f"the initialization descriptor is {len(blob)} bytes; its counts "
                        f"imply {implied}")
    return findings


def build_image(lay: Layout, payload: bytes, *, security_version: int, signer: bytes,
                magic: int | None = None, stage: int | None = None,
                offset: int | None = None, length: int | None = None,
                digest: bytes | None = None) -> bytes:
    """The header and payload, every field defaulting to its well-formed value."""
    header = bytearray(lay["BOOT_HEADER_BYTES"])

    def put(at: int, value: int) -> None:
        header[at:at + 8] = value.to_bytes(8, "little")

    put(lay["BOOT_HDR_MAGIC"], lay["BOOT_MAGIC"] if magic is None else magic)
    put(lay["BOOT_HDR_STAGE"], lay["BOOT_STAGE_MMODE_IMAGE"] if stage is None else stage)
    put(lay["BOOT_HDR_SECURITY_VERSION"], security_version)
    put(lay["BOOT_HDR_PAYLOAD_OFFSET"], lay["BOOT_HEADER_BYTES"] if offset is None else offset)
    put(lay["BOOT_HDR_PAYLOAD_LENGTH"], len(payload) if length is None else length)
    at = lay["BOOT_HDR_PAYLOAD_DIGEST"]
    header[at:at + lay["BOOT_DIGEST_BYTES"]] = (
        hashlib.shake_256(payload).digest(lay["BOOT_DIGEST_BYTES"]) if digest is None else digest)
    signed = bytes(header[:lay["BOOT_SIGNED_BYTES"]])
    at = lay["BOOT_HDR_SIGNATURE"]
    header[at:at + lay["BOOT_SIGNATURE_BYTES"]] = fixture_signature(lay, signer, signed)
    return bytes(header) + payload


def flip(data: bytes, at: int) -> bytes:
    out = bytearray(data)
    out[at] ^= 0x01
    return bytes(out)


def put_word(data: bytes, at: int, value: int) -> bytes:
    """`data` with one little-endian doubleword replaced, as a change after signing."""
    out = bytearray(data)
    out[at:at + 8] = value.to_bytes(8, "little")
    return bytes(out)


# --- running the pieces ---------------------------------------------------------


@dataclass
class Emulation:
    """One golden-emulator run: its HTIF verdict and its commit trace's summary."""

    verdict: str                 # success | failure | no-verdict
    code: int | None
    retired: int
    first_pc: int | None
    reached: dict[str, bool] = field(default_factory=dict)
    signature: list[int] = field(default_factory=list)


def emulate(simulator: Path, config: Path, elf: Path, timeout: int,
            watch: dict[str, int] | None = None, signature: Path | None = None) -> Emulation:
    argv = [str(simulator), "--config", str(config), "--trace-commit",
            "--inst-limit", "200000"]
    if signature is not None:
        argv += ["--test-signature", str(signature), "--signature-granularity", "8"]
    try:
        done = subprocess.run([*argv, str(elf)], capture_output=True, text=True,
                              errors="replace", timeout=timeout, check=False)
        output = done.stdout + done.stderr
    except subprocess.TimeoutExpired:
        return Emulation("no-verdict", None, 0, None)
    records = trace.normalize_commit(output.splitlines())
    pcs = [int(r.split()[1], 16) for r in records if r.startswith("I ")]
    failure = re.search(r"^FAILURE: (\d+)", output, re.MULTILINE)
    if re.search(r"^SUCCESS$", output, re.MULTILINE):
        verdict, code = "success", 0
    elif failure:
        verdict, code = "failure", int(failure.group(1))
    else:
        verdict, code = "no-verdict", done.returncode
    run = Emulation(verdict, code, len(pcs), pcs[0] if pcs else None)
    run.reached = {name: pc in set(pcs) for name, pc in (watch or {}).items()}
    if signature is not None and signature.is_file():
        run.signature = [int(line, 16) for line in
                         signature.read_text(encoding="utf-8").split()]
    return run


def compile_rot_stage(root: Path, out: Path) -> tuple[Path, str]:
    compiler = shutil.which("cc")
    if compiler is None:
        raise RuntimeError("no C compiler named cc on PATH")
    binary = out / "rot-stage"
    subprocess.run([compiler, *CFLAGS, "-I", str(root / "firmware/include"),
                    *(str(root / unit) for unit in C_UNITS), "-o", str(binary)],
                   check=True, capture_output=True, text=True)
    version = subprocess.run([compiler, "--version"], capture_output=True, text=True,
                             check=True).stdout.splitlines()[0]
    return binary, version


def shake_differential(binary: Path) -> dict[str, object]:
    """The C SHAKE256 against Python's hashlib over the rate's boundaries."""
    lengths = sorted({*range(4), *range(133, 140), 271, 272, 273, 1000, 4096, 40000})
    outputs = (1, 32, 135, 136, 137, 300)
    pairs = [(n, m) for n in lengths for m in outputs]
    inputs = {n: hashlib.shake_128(f"input {n}".encode()).digest(n) for n in lengths}
    batch = "".join(f"{m} {inputs[n].hex()}\n" for n, m in pairs)
    said = subprocess.run([str(binary), "shake256-lines"], input=batch, capture_output=True,
                          text=True, check=True).stdout.split()
    disagreements = [f"in={n} out={m}" for index, (n, m) in enumerate(pairs)
                     if index >= len(said) or said[index] != hashlib.shake_256(
                         inputs[n]).hexdigest(m)]
    if len(said) != len(pairs):
        disagreements.append(f"{len(said)} answers for {len(pairs)} pairs")
    return {"compared": len(pairs), "input_lengths": lengths, "output_lengths": list(outputs),
            "disagreements": disagreements}


@dataclass(frozen=True)
class RotInputs:
    lifecycle: int
    entropy_ok: int
    boot_target: int
    floor: int


def rot_stage(binary: Path, image_path: Path, inputs: RotInputs, verifier: str,
              out: Path, extra: tuple[str, ...] = ()) -> dict[str, str]:
    roots = [f"root.{state}={root_key(state).hex()}" for state in ROOT_STATES]
    done = subprocess.run(
        [str(binary), "boot", f"image={image_path}", f"lifecycle={inputs.lifecycle}",
         f"entropy={inputs.entropy_ok}", f"target={inputs.boot_target}",
         f"floor={inputs.floor}", f"verifier={verifier}", f"sram={out / 'sram.bin'}",
         f"handoff={out / 'handoff.bin'}", *extra, *roots],
        capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise RuntimeError(f"rot-stage exited {done.returncode}: {done.stderr.strip()}")
    return dict(line.split("=", 1) for line in done.stdout.splitlines() if "=" in line)


def placed_elf(lay: Layout, window: bytes, record: bytes, tohost: int, path: Path) -> None:
    """The main die's memory at release: the placed window and the RoT's record."""
    sections = [image.Section(".image", lay["BRINGUP_MMODE_LOAD_BASE"], bytearray(window),
                              writable=True, executable=True),
                image.Section(".handoff", lay["BRINGUP_HANDOFF_BASE"], bytearray(record),
                              writable=True)]
    image.write_elf(path, sections, {"tohost": (".image", tohost)},
                    lay["BRINGUP_MMODE_LOAD_BASE"])


# --- the case table -------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    """One boot attempt and what the contract says must happen to it."""

    name: str
    decides: str
    image: Callable[[Scenario], bytes]
    expect: str                                   # a vos_boot_verdict_name
    emulator: str | None = None                   # "success" or "failure:N" after release
    inputs: Callable[[RotInputs], RotInputs] = lambda given: given
    verifier: str = "fixture"
    stage_text: Callable[[str], str] | None = None
    force_run: str | None = None                  # expected verdict of a run bypassing the RoT
    driver: Callable[[Scenario], tuple[str, ...]] = lambda scenario: ()  # extra driver args


@dataclass
class Scenario:
    lay: Layout
    built: Assembled
    floor: int

    def valid(self, *, security_version: int | None = None, magic: int | None = None,
              stage: int | None = None, offset: int | None = None,
              length: int | None = None, digest: bytes | None = None) -> bytes:
        return build_image(self.lay, self.built.payload,
                           security_version=self.floor if security_version is None
                           else security_version,
                           signer=root_key("production"), magic=magic, stage=stage,
                           offset=offset, length=length, digest=digest)


def _same(text: str, old: str, new: str) -> str:
    if old not in text:
        raise ValueError(f"handoff mutant anchor {old!r} is absent from {MMODE}")
    return text.replace(old, new, 1)


def cases() -> list[Case]:
    padding = 0x4000   # inside the zero gap between the image's text and data
    return [
        Case("valid", "a valid measurement releases the die and the kernel entry holds",
             lambda s: s.valid(), "release", emulator="success"),
        Case("payload-padding-byte-flipped",
             "a one-byte change the kernel never reads is refused on the measurement; "
             "forced past the RoT, the same bytes run to success",
             lambda s: flip(s.valid(), s.lay["BOOT_HEADER_BYTES"] + padding),
             "refuse-digest", force_run="success"),
        Case("payload-kernel-byte-flipped", "a changed kernel instruction is refused",
             lambda s: flip(s.valid(), s.lay["BOOT_HEADER_BYTES"] + 0x800),
             "refuse-digest"),
        Case("digest-field-resigned", "a signed header whose digest is not the payload's",
             lambda s: s.valid(digest=bytes(32)), "refuse-digest"),
        Case("digest-last-byte-resigned", "a signed digest differing in its last byte only",
             lambda s: s.valid(digest=flip(hashlib.shake_256(s.built.payload).digest(
                 s.lay["BOOT_DIGEST_BYTES"]), s.lay["BOOT_DIGEST_BYTES"] - 1)),
             "refuse-digest"),
        Case("digest-field-unsigned", "a header byte changed after signing",
             lambda s: flip(s.valid(), s.lay["BOOT_HDR_PAYLOAD_DIGEST"]),
             "refuse-signature"),
        Case("signature-byte-flipped", "a changed signature byte",
             lambda s: flip(s.valid(), s.lay["BOOT_HDR_SIGNATURE"] + 100),
             "refuse-signature"),
        Case("development-root-on-production", "R-09-036: another state's root verifies "
             "nothing in production",
             lambda s: build_image(s.lay, s.built.payload, security_version=s.floor,
                                   signer=root_key("development")), "refuse-signature"),
        Case("below-floor", "a security version under the anti-rollback floor",
             lambda s: s.valid(security_version=s.floor - 1), "refuse-floor"),
        Case("header-rewritten-during-verify",
             "a header signed at F - 1 and shown as F: the input is rewritten to the signed "
             "F - 1 while the release runs, and the floor and the signature decide one copy",
             lambda s: put_word(s.valid(security_version=s.floor - 1),
                                s.lay["BOOT_HDR_SECURITY_VERSION"], s.floor),
             "refuse-signature", verifier="fixture-racing",
             driver=lambda s: (f"race_version={s.floor - 1}",)),
        Case("length-beyond-region", "a declared length beyond the image region",
             lambda s: s.valid(length=s.lay["BRINGUP_MMODE_REGION_BYTES"] + 1),
             "refuse-length"),
        Case("length-zero", "a declared length of zero", lambda s: s.valid(length=0),
             "refuse-length"),
        Case("length-at-region", "a payload filling the region exactly is admitted",
             lambda s: build_image(s.lay, s.built.payload + bytes(
                 s.lay["BRINGUP_MMODE_REGION_BYTES"] - len(s.built.payload)),
                 security_version=s.floor, signer=root_key("production")),
             "release", emulator="success"),
        Case("image-window-short", "an image window one byte short of the payload refuses "
             "before anything is placed", lambda s: s.valid(), "refuse-placement",
             driver=lambda s: (f"window={len(s.built.payload) - 1}",)),
        Case("truncated-payload", "an input shorter than its declared payload",
             lambda s: s.valid()[:-1], "refuse-truncated"),
        Case("truncated-header", "an input shorter than the header",
             lambda s: s.valid()[:s.lay["BOOT_HEADER_BYTES"] - 1], "refuse-truncated"),
        Case("offset-not-fixed", "an offset field other than the header size, signed",
             lambda s: s.valid(offset=s.lay["BOOT_HEADER_BYTES"] + 8), "refuse-offset"),
        Case("magic-wrong", "a format identifier other than VOSBOOT1, signed",
             lambda s: s.valid(magic=0), "refuse-magic"),
        Case("stage-wrong", "the RoT runtime's stage identifier on the M-mode path",
             lambda s: s.valid(stage=s.lay["BOOT_STAGE_ROT_RUNTIME"]), "refuse-stage"),
        Case("verifier-absent", "no bound signature verifier refuses rather than skips",
             lambda s: s.valid(), "refuse-no-verifier", verifier="absent"),
        Case("entropy-failed", "R-09-006a: a failed start-up verdict (injected) refuses",
             lambda s: s.valid(), "refuse-entropy",
             inputs=lambda given: RotInputs(given.lifecycle, 0, given.boot_target, given.floor)),
        Case("lifecycle-raw", "a state that accepts no root (injected raw) refuses",
             lambda s: s.valid(), "refuse-no-root",
             inputs=lambda given: RotInputs(0, given.entropy_ok, given.boot_target, given.floor)),
        Case("development-part", "a development part (injected) admits its own root: "
             "same generation register, different device register",
             lambda s: build_image(s.lay, s.built.payload, security_version=s.floor,
                                   signer=root_key("development")), "release",
             emulator="success",
             inputs=lambda given: RotInputs(2, given.entropy_ok, given.boot_target, given.floor)),
        Case("mutant-mepcc-kept", "a released handoff that leaves MEPCC is caught at "
             "kernel entry", lambda s: s.valid(), "release", emulator="failure:10",
             stage_text=lambda t: _same(t, "cspecialrw cnull, mepcc, c31",
                                        "cspecialrw cnull, mepcc, cnull")),
        Case("mutant-unseal-root-kept", "a released handoff that keeps c3's object-type "
             "root is caught at kernel entry", lambda s: s.valid(), "release",
             emulator="failure:1",
             stage_text=lambda t: _same(t, "cclear  0, 0xe3db", "cclear  0, 0xe3d3")),
        Case("mutant-global-stack", "a released handoff with a global stack is caught",
             lambda s: s.valid(), "release", emulator="failure:4",
             stage_text=lambda t: _same(t, ".equ    PERMS_STACK_LOCAL, 0xfe",
                                        ".equ    PERMS_STACK_LOCAL, 0xff")),
        Case("mutant-linked-entry", "a released handoff that enters with a link leaves a "
             "firmware return sentry in cra", lambda s: s.valid(), "release",
             emulator="failure:1",
             stage_text=lambda t: _same(t, "cjr     c5", "cjalr   cra, c5, 0")),
        Case("mutant-timer-armed", "a released handoff that arms the boundary timer is "
             "caught when the event arrives at the kernel's trap entry", lambda s: s.valid(),
             "release", emulator="failure:32",
             stage_text=lambda t: _same(t, _SENTRY_ANCHOR, _ARM_TIMER + _SENTRY_ANCHOR)),
    ]


# The timer mutant arms an immediate boundary event just before the entry sentry is
# minted, after MTCC and MTDC are installed and through scratch that the final clear
# scrubs. mtimecmp is the main composition's CLINT (model/config/verifiedos.json) plus
# the model's MTIMECMP_BASE (model/model/sys/platform.sail).
_SENTRY_ANCHOR = "        # The transient entry sentry, minted last"
_ARM_TIMER = ("        li      a3, 0x2004000\n"
              "        csetaddr c13, c8, a3\n"
              "        sd      zero, 0(c13)\n")


def digests(root: Path, names: tuple[str, ...]) -> dict[str, str]:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


# --- the contract's tables against the owner ----------------------------------------

# Each qualified field the contract's tables name, and the macro pair (offset, width)
# or the value macro it must agree with. A width of an int is literal: every integer
# field is one little-endian doubleword.
_FIELDS: dict[str, tuple[str, str | int]] = {
    "header.magic": ("BOOT_HDR_MAGIC", 8),
    "header.stage": ("BOOT_HDR_STAGE", 8),
    "header.security_version": ("BOOT_HDR_SECURITY_VERSION", 8),
    "header.payload_offset": ("BOOT_HDR_PAYLOAD_OFFSET", 8),
    "header.payload_length": ("BOOT_HDR_PAYLOAD_LENGTH", 8),
    "header.payload_digest": ("BOOT_HDR_PAYLOAD_DIGEST", "BOOT_DIGEST_BYTES"),
    "header.signature": ("BOOT_HDR_SIGNATURE", "BOOT_SIGNATURE_BYTES"),
    "record.magic": ("HANDOFF_MAGIC_AT", 8),
    "record.version": ("HANDOFF_VERSION_AT", 8),
    "record.lifecycle": ("HANDOFF_LIFECYCLE_AT", 8),
    "record.entropy_ok": ("HANDOFF_ENTROPY_AT", 8),
    "record.boot_target": ("HANDOFF_BOOT_TARGET_AT", 8),
    "record.security_version": ("HANDOFF_SECURITY_VERSION_AT", 8),
    "record.floor": ("HANDOFF_FLOOR_AT", 8),
    "record.load_base": ("HANDOFF_LOAD_BASE_AT", 8),
    "record.payload_length": ("HANDOFF_PAYLOAD_LENGTH_AT", 8),
    "record.image_digest": ("HANDOFF_IMAGE_DIGEST_AT", "BOOT_DIGEST_BYTES"),
    "record.generation": ("HANDOFF_GENERATION_AT", "MEASURE_BYTES"),
    "record.device": ("HANDOFF_DEVICE_AT", "MEASURE_BYTES"),
    "record.chain": ("HANDOFF_CHAIN_AT", "MEASURE_BYTES"),
    "init.magic": ("INIT_MAGIC_AT", 8),
    "init.version": ("INIT_VERSION_AT", 8),
    "init.composition": ("INIT_COMPOSITION_AT", 8),
    "init.hart": ("INIT_HART_AT", 8),
    "init.root": ("INIT_ROOT_AT", "INIT_EXTENT_BYTES"),
    "init.switch_text": ("INIT_SWITCH_TEXT_AT", "INIT_EXTENT_BYTES"),
    "init.partition_count": ("INIT_PARTITION_COUNT_AT", 8),
    "init.window_count": ("INIT_WINDOW_COUNT_AT", 8),
    "init.slot_count": ("INIT_SLOT_COUNT_AT", 8),
    "init.csr_count": ("INIT_CSR_COUNT_AT", 8),
    "init.major_frame": ("INIT_MAJOR_FRAME_AT", 8),
    "init.phase_offset": ("INIT_PHASE_OFFSET_AT", 8),
    "init.reserved_count": ("INIT_RESERVED_COUNT_AT", 8),
    "init.pending_arm": ("INIT_PENDING_ARM_AT", 8),
    "init.rotation_swaps": ("INIT_ROTATION_SWAPS_AT", 8),
    "init.pending_static_mask": ("INIT_PENDING_STATIC_MASK_AT", 8),
}
_VALUES: dict[str, str] = {
    "header.bytes": "BOOT_HEADER_BYTES",
    "header.signed_bytes": "BOOT_SIGNED_BYTES",
    "record.bytes": "HANDOFF_BYTES",
    "composition.load_base": "BRINGUP_MMODE_LOAD_BASE",
    "composition.region_bytes": "BRINGUP_MMODE_REGION_BYTES",
    "composition.handoff_base": "BRINGUP_HANDOFF_BASE",
    "init.header_bytes": "INIT_HEADER_BYTES",
    "init.partition_bytes": "INIT_PARTITION_BYTES",
    "init.window_bytes": "INIT_WINDOW_BYTES",
    "init.slot_bytes": "INIT_SLOT_BYTES",
    "init.csr_bytes": "INIT_CSR_BYTES",
}
_ROW = re.compile(r"^\|\s*`([a-z_]+\.[a-z_]+)`\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")


def _number(text: str) -> int | None:
    text = text.replace(",", "").strip()
    try:
        return int(text, 0)
    except ValueError:
        return None


def contract_findings(root: Path) -> list[str]:
    """Where the contract's layout tables and vos_boot.h disagree, or a row is missing."""
    lay = layout(root)
    seen: set[str] = set()
    findings: list[str] = []
    for line in (root / CONTRACT).read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if not match:
            continue
        name, first, second = match.groups()
        if name in _FIELDS:
            seen.add(name)
            offset_macro, width = _FIELDS[name]
            want_width = width if isinstance(width, int) else lay[width]
            if _number(first) != lay[offset_macro] or _number(second) != want_width:
                findings.append(f"{CONTRACT}: {name} is at {first} for {second} bytes; "
                                f"{HEADER} has {lay[offset_macro]} for {want_width}")
        elif name in _VALUES:
            seen.add(name)
            if _number(first) != lay[_VALUES[name]]:
                findings.append(f"{CONTRACT}: {name} is {first}; {HEADER} has "
                                f"{lay[_VALUES[name]]:#x}")
    missing = sorted((set(_FIELDS) | set(_VALUES)) - seen)
    findings += [f"{CONTRACT} has no row for {name}" for name in missing]
    return findings + case_table_findings(root)


# Section 6's kernel-entry rows whose expanded permissions an assembled constant
# states: the stage's `.equ` for what it narrows, and the fixture's for the execute
# root, which the stage bounds without changing its permissions.
_PERMISSIONS: dict[str, str] = {
    "PCC": "PERMS_CODE_ROOT_ASR_GLOBAL",
    "`csp` / `c2`": "PERMS_STACK_LOCAL",
    "`c10`": "PERMS_R_CAP_LM_LG_GLOBAL",
    "`c11`": "PERMS_R_GLOBAL",
    "`c12`": "PERMS_R_CAP_LM_LG_GLOBAL",
    "MTCC": "PERMS_CODE_ROOT_ASR_GLOBAL",
    "MTDC": "PERMS_DATA_ROOT_GLOBAL",
}
_PERMISSION_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|[^|]*\|\s*`(0x[0-9a-fA-F]+)`")


def entry_table_findings(root: Path, built: Assembled) -> list[str]:
    """Where section 6's permission column and the assembled constants disagree.

    Only the rows `_PERMISSIONS` names are held; the remaining cells of that table,
    and the operations table of section 5, are prose no command reads.
    """
    seen: set[str] = set()
    findings: list[str] = []
    for line in (root / CONTRACT).read_text(encoding="utf-8").splitlines():
        match = _PERMISSION_ROW.match(line)
        if not match or match.group(1) not in _PERMISSIONS:
            continue
        location, stated = match.group(1), int(match.group(2), 16)
        seen.add(location)
        constant = _PERMISSIONS[location]
        if built.constants.get(constant) != stated:
            findings.append(f"{CONTRACT}: {location} carries {stated:#x}; the image's "
                            f"{constant} is {built.constants.get(constant)}")
    findings += [f"{CONTRACT}'s kernel-entry table has no permission row for {location}"
                 for location in sorted(set(_PERMISSIONS) - seen)]
    return findings


_CASE_ROW = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|[^|]*\|\s*`([a-z-]+)`\s*\|\s*([^|]+?)\s*\|\s*$")
_RUN_CELL = re.compile(r"`(SUCCESS|FAILURE: \d+)`")


def _run_cell(text: str) -> tuple[str | None, str | None]:
    """A table cell's main-die run and forced run, in `Case`'s spelling."""
    def spell(match: re.Match[str] | None) -> str | None:
        if match is None:
            return None
        word = str(match.group(1))
        return "success" if word == "SUCCESS" else "failure:" + word.split(": ")[1]

    main, _, forced = text.partition("forced:")
    return spell(_RUN_CELL.search(main)), spell(_RUN_CELL.search(forced))


def case_table_findings(root: Path) -> list[str]:
    """Where section 2's case table and `cases()` disagree, in either direction."""
    table: dict[str, tuple[str, str | None, str | None]] = {}
    for line in (root / CONTRACT).read_text(encoding="utf-8").splitlines():
        match = _CASE_ROW.match(line)
        if match and match.group(2).startswith(("release", "refuse")):
            table[match.group(1)] = (match.group(2), *_run_cell(match.group(3)))
    findings = []
    declared = {case.name: (case.expect, case.emulator, case.force_run) for case in cases()}
    for name in sorted(set(table) | set(declared)):
        if name not in table:
            findings.append(f"{CONTRACT}'s case table has no row for {name}")
        elif name not in declared:
            findings.append(f"{CONTRACT}'s case table names {name}, which the harness lacks")
        elif table[name] != declared[name]:
            findings.append(f"{CONTRACT} says {name} is {table[name]}; the harness "
                            f"expects {declared[name]}")
    return findings


# --- one harness run ------------------------------------------------------------------


def _record_findings(lay: Layout, record: bytes, said: dict[str, str], payload: bytes,
                     inputs: RotInputs) -> list[str]:
    """Hold the handoff record the RoT wrote against what it reported and measured."""
    def word(macro: str) -> int:
        at = lay[macro]
        return int.from_bytes(record[at:at + 8], "little")

    def blob(macro: str) -> str:
        at = lay[macro]
        return record[at:at + 32].hex()

    expected = {
        "HANDOFF_MAGIC_AT": lay["HANDOFF_MAGIC"], "HANDOFF_VERSION_AT": lay["HANDOFF_VERSION"],
        "HANDOFF_LIFECYCLE_AT": inputs.lifecycle,
        "HANDOFF_ENTROPY_AT": 1 if inputs.entropy_ok else 0,
        "HANDOFF_BOOT_TARGET_AT": inputs.boot_target & 1, "HANDOFF_FLOOR_AT": inputs.floor,
        "HANDOFF_SECURITY_VERSION_AT": int(said["security_version"]),
        "HANDOFF_LOAD_BASE_AT": lay["BRINGUP_MMODE_LOAD_BASE"],
        "HANDOFF_PAYLOAD_LENGTH_AT": len(payload),
    }
    findings = [f"record {macro} holds {word(macro)}, expected {value}"
                for macro, value in expected.items() if word(macro) != value]
    digest = hashlib.shake_256(payload).hexdigest(32)
    for macro, value in (("HANDOFF_IMAGE_DIGEST_AT", digest),
                         ("HANDOFF_GENERATION_AT", said["generation"]),
                         ("HANDOFF_DEVICE_AT", said["device"]),
                         ("HANDOFF_CHAIN_AT", said["chain"])):
        if blob(macro) != value:
            findings.append(f"record {macro} disagrees with the stage's report")
    if any(record[lay["HANDOFF_USED_BYTES"]:]):
        findings.append("record bytes past the used extent are not zero")
    return findings


def _observed(run: Emulation) -> str:
    return f"failure:{run.code}" if run.verdict == "failure" else run.verdict


@dataclass
class Line:
    """One case's summary as the command prints it."""

    case: str
    rot_verdict: str
    emulator: str
    forced: str | None
    problems: list[str]


@dataclass
class HarnessResult:
    """The JSON report, one line per case, and the run-level findings."""

    report: dict[str, object]
    lines: list[Line]
    findings: list[str]

    @property
    def ok(self) -> bool:
        return not self.findings and bool(self.lines) and all(
            not line.problems for line in self.lines)


def run_harness(root: Path, simulator: Path, out: Path, timeout: int) -> HarnessResult:
    """Every case of `cases()`, the probe, the SHAKE comparison and the controls.

    The result is ok only when every case matched the contract and no run-level
    finding stands.
    """
    lay = layout(root)
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "contract": CONTRACT,
        "inputs_sha256": digests(root, INPUTS),
        "simulator": str(simulator),
        "simulator_sha256": hashlib.sha256(simulator.read_bytes()).hexdigest(),
        "rot_executor": "firmware/rot/boot_verify.c compiled for the host; the RoT hart "
                        "does not execute it until the purecap backend and M1.7 join",
        "signature_verifier": "fixture (not a signature scheme); SLH-DSA-SHAKE-256s owed",
        "milestone_acceptance": "open",
    }
    findings: list[str] = contract_findings(root)
    binary, compiler = compile_rot_stage(root, out)
    report["compiler"] = compiler
    report["cflags"] = list(CFLAGS)
    shake = shake_differential(binary)
    report["shake256_differential"] = shake
    if shake["disagreements"]:
        findings.append(f"SHAKE256 disagrees with hashlib at {shake['disagreements']}")

    probe_elf = out / "rot_inputs.elf"
    asm.assemble_file(root / PROBE, probe_elf)
    probe_sig = out / "rot_inputs.sig"
    probe_sig.unlink(missing_ok=True)
    probe = emulate(simulator, root / ROT_CONFIG, probe_elf, timeout, signature=probe_sig)
    report["probe"] = {"config": ROT_CONFIG, "verdict": _observed(probe),
                       "retired": probe.retired, "signature": [hex(v) for v in probe.signature]}
    if probe.verdict != "success" or len(probe.signature) != 3:
        findings.append(f"the RoT probe did not report: {_observed(probe)}")
        report["findings"] = findings
        report["ok"] = False
        return HarnessResult(report, [], findings)
    lifecycle, health, floor = probe.signature
    entropy_ok = 1 if (health >> 32) & 1 and not (health >> 33) & 1 else 0
    given = RotInputs(lifecycle, entropy_ok, 0, floor)
    report["rot_inputs"] = {"lifecycle": LIFECYCLES[lifecycle] if lifecycle < 5 else lifecycle,
                            "entropy_ok": entropy_ok, "health_word": hex(health),
                            "boot_target": "0 (no model door; harness-supplied)",
                            "floor": floor, "floor_origin": "probe-established by "
                            "advancing counter 0 in the same power-on"}

    stage_source = (root / MMODE).read_text(encoding="utf-8")
    built = assemble_mmode(root)
    findings += composition_findings(lay, built) + entry_table_findings(root, built)
    report["payload"] = {"bytes": len(built.payload),
                         "shake256": hashlib.shake_256(built.payload).hexdigest(32),
                         "kernel_entry": hex(built.symbols["kernel_entry"])}
    load_base = lay["BRINGUP_MMODE_LOAD_BASE"]
    rows: list[dict[str, object]] = []
    lines: list[Line] = []
    valid_said: dict[str, str] = {}
    valid_record = b""
    for case in cases():
        case_built = built if case.stage_text is None else assemble_mmode(
            root, case.stage_text(stage_source))
        scenario = Scenario(lay, case_built, floor)
        directory = out / case.name
        directory.mkdir(parents=True, exist_ok=True)
        for stale in ("sram.bin", "handoff.bin", "placed.elf", "forced.elf"):
            (directory / stale).unlink(missing_ok=True)
        data = case.image(scenario)
        (directory / "image.bin").write_bytes(data)
        inputs = case.inputs(given)
        problems: list[str] = []
        said: dict[str, str] = {}
        try:
            said = rot_stage(binary, directory / "image.bin", inputs, case.verifier, directory,
                             case.driver(scenario))
        except RuntimeError as exc:
            problems.append(f"the RoT stage failed: {str(exc)[:300]}")
        row: dict[str, object] = {
            "case": case.name, "decides": case.decides, "expected": case.expect,
            "inputs": {"lifecycle": inputs.lifecycle, "entropy_ok": inputs.entropy_ok,
                       "boot_target": inputs.boot_target, "floor": inputs.floor,
                       "verifier": case.verifier, "driver": list(case.driver(scenario))},
            "rot_verdict": said.get("verdict"), "released": said.get("released"),
            "measured_items": said.get("log"), "generation": said.get("generation"),
            "device": said.get("device"), "chain": said.get("chain"),
        }
        emulator_text = "not started: no release"
        forced_text: str | None = None
        if said.get("verdict") != case.expect:
            problems.append(f"verdict {said.get('verdict')}, expected {case.expect}")
        if case.expect == "release" and not (directory / "sram.bin").is_file():
            problems.append("no placed window was written, so no main-die run starts")
            row["emulator"] = emulator_text
        elif case.expect == "release":
            if said.get("released") != "1" or said.get("log") != "1,2,3,5":
                problems.append(f"released={said.get('released')} log={said.get('log')}")
            window = (directory / "sram.bin").read_bytes()
            record = (directory / "handoff.bin").read_bytes()
            header = lay["BOOT_HEADER_BYTES"]
            payload = data[header:header + int(said.get("payload_length", "0"))]
            if not payload or window[:len(payload)] != payload or any(window[len(payload):]):
                problems.append("the placed window is not exactly the payload")
            problems += _record_findings(lay, record, said, payload, inputs)
            want = expected_registers(root, lay, inputs,
                                      hashlib.shake_256(payload).digest(lay["BOOT_DIGEST_BYTES"]))
            if (said.get("generation"), said.get("device"), said.get("chain")) != want:
                problems.append("the measurement registers differ from section 5's encoding")
            elf = directory / "placed.elf"
            placed_elf(lay, window, record, case_built.symbols["tohost"], elf)
            run = emulate(simulator, root / MAIN_CONFIG, elf, timeout,
                          watch={"kernel_entry": case_built.symbols["kernel_entry"]})
            row["emulator"] = {"config": MAIN_CONFIG, "verdict": _observed(run),
                               "retired": run.retired,
                               "first_pc": hex(run.first_pc) if run.first_pc is not None else None,
                               "reached_kernel_entry": run.reached.get("kernel_entry")}
            emulator_text = f"{_observed(run)} after {run.retired} retired"
            if _observed(run) != case.emulator or run.first_pc != load_base:
                problems.append(f"emulator {_observed(run)} from {run.first_pc}, "
                                f"expected {case.emulator} from {load_base:#x}")
            if case.emulator == "success" and not run.reached.get("kernel_entry"):
                problems.append("the run never retired the kernel entry")
            if case.name == "valid":
                valid_said, valid_record = said, record
        else:
            if (said.get("released") != "0" or said.get("image_window_zero") != "1"
                    or said.get("handoff_window_untouched") != "1"
                    or (directory / "sram.bin").exists()):
                problems.append("a refusal released, left bytes in the image window, "
                                "touched the record or wrote a placed window")
            if said.get("log") != "1,2,3":
                problems.append(f"a refusal measured {said.get('log')}, expected 1,2,3")
            want = expected_registers(root, lay, inputs, None)
            if (said.get("generation"), said.get("device"), said.get("chain")) != want:
                problems.append("the measurement registers differ from section 5's encoding")
            row["emulator"] = emulator_text
        if case.force_run is not None:
            header = lay["BOOT_HEADER_BYTES"]
            tampered = data[header:header + len(case_built.payload)]
            window = tampered + bytes(lay["BRINGUP_MMODE_REGION_BYTES"] - len(tampered))
            elf = directory / "forced.elf"
            placed_elf(lay, window, valid_record, case_built.symbols["tohost"], elf)
            run = emulate(simulator, root / MAIN_CONFIG, elf, timeout)
            row["forced_past_rot"] = {"verdict": _observed(run), "retired": run.retired}
            forced_text = _observed(run)
            if _observed(run) != case.force_run:
                problems.append(f"forced run {_observed(run)}, expected {case.force_run}")
        if case.name == "development-part" and valid_said:
            same = said.get("generation") == valid_said.get("generation")
            differs = said.get("device") != valid_said.get("device")
            row["generation_equals_valid"] = same
            row["device_differs_from_valid"] = differs
            if not (same and differs):
                problems.append("R-09-025a split not observed between the two parts")
        row["problems"] = problems
        rows.append(row)
        lines.append(Line(case.name, said.get("verdict", "none"), emulator_text,
                          forced_text, problems))

    # The record is the RoT's and not the image's: the valid payload with no record.
    control: dict[str, object] = {"control": "valid payload placed with a zero record"}
    if valid_record:
        elf = out / "control-no-record.elf"
        window = built.payload + bytes(lay["BRINGUP_MMODE_REGION_BYTES"] - len(built.payload))
        placed_elf(lay, window, bytes(lay["HANDOFF_BYTES"]), built.symbols["tohost"], elf)
        run = emulate(simulator, root / MAIN_CONFIG, elf, timeout)
        control["verdict"] = _observed(run)
        control["expected"] = "failure:6"
        if _observed(run) != "failure:6":
            findings.append(f"the no-record control ended {_observed(run)}, expected failure:6")
    else:
        findings.append("the valid case produced no record for the controls")
    report["controls"] = [control]
    report["cases"] = rows
    report["findings"] = findings
    result = HarnessResult(report, lines, findings)
    report["ok"] = result.ok
    return result
