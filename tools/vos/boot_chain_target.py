# SPDX-License-Identifier: Apache-2.0
"""Stage M3.5b's chain campaign where the contained compiler is, and run it where the model builds.

[The boot-handoff contract](../../docs/implementation/contracts/boot-handoff.md)'s
section 9.14 splits the campaign as M7.1f's is split: `stage` compiles the ROM, the
runtime, its two mutants and the M-mode stage through the contained compiler, lays the
payloads out through the composition lanes' composers, signs the images with the
campaign's disposable OpenSSL keys and writes `firmware/chain/target/`; `run` executes
the staged inputs on the golden emulator, one process per run, classifies each ending
strictly by section 9.2, decodes each capture strictly and holds it against
[the oracle](boot_chain.py). Private keys stay in the native output lane.

The composers are the RoT and M-mode lanes' modules, `vos.chain_rot` and
`vos.chain_mmode`. They are imported by name when a command needs them and read
through the protocols below, so this module and its tests load without them.
"""

import hashlib
import importlib
import json
import re
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from vos import boot_chain as bc
from vos import (
    boot_crypto,
    boot_crypto_target,
    boot_release_target,
    boot_signing,
    boot_target,
    image,
    kernel_restore,
    receipts,
)
from vos import boot_handoff as bh
from vos.cli import compiler_diff as cd

# The instruction limit of each run kind but the control, whose limit is section 9.10's
# `chain.control_inst_limit`. Each is far above what its run retires, so a run that
# reaches one supplies no verdict: two SLH-DSA verifications with the ROM's and the
# runtime's placement for a boot run, one ML-DSA verification for the main die.
INST_LIMITS = {"boot": 4_000_000_000, "service": 500_000_000, "main": 2_000_000_000,
               "runtime-only": 2_000_000_000}
# The per-run timeouts' defaults, in seconds. A boot run holds two SLH-DSA verifications
# at up to 5,000 s each with its reads and placement; a main-die run one ML-DSA
# verification at up to 600 s; a service run, a runtime-only run and the control are
# shorter, the control's 50,000,000 instructions included.
TIMEOUTS = {"boot": 12_000, "main": 1_800, "short": 2_400}
CAPTURE_GRANULARITY = 8


class Program(Protocol):
    """What a composer hands back: the composed assembly and the ELF's parts."""

    @property
    def assembly(self) -> str: ...

    @property
    def sections(self) -> Sequence[image.Section]: ...

    @property
    def symbols(self) -> Mapping[str, tuple[str, int]]: ...

    @property
    def entry(self) -> int: ...


class RotComposer(Protocol):
    """`vos.chain_rot`, the RoT lane's composer."""

    ROM_SOURCE: str
    RUNTIME_SOURCE: str
    COMPILE_ARGS: tuple[str, ...]
    RUNTIME_MUTANTS: Mapping[str, tuple[str, str]]

    def RomInputs(self, *, roots: Mapping[int, bytes], runtime_image: bytes,  # noqa: N802
                  slot_images: Mapping[int, bytes], floor: int, entropy_failed: bool) -> object: ...

    def compose_rom(self, root: Path, rom_stream: str, inputs: object) -> Program: ...

    def runtime_payload(self, root: Path, runtime_stream: str) -> bytes: ...

    def compose_runtime_only(self, root: Path, payload: bytes, state: bytes,
                             floor: int) -> Program: ...

    def compose_service(self, root: Path, payload: bytes, state: bytes,
                        request: bytes) -> Program: ...


class MmodeComposer(Protocol):
    """`vos.chain_mmode`, the M-mode lane's composer."""

    MMODE_SOURCE: str
    COMPILE_ARGS: tuple[str, ...]

    def mmode_payload(self, root: Path, mmode_stream: str, kernel_root: bytes,
                      slot_tag: bytes) -> bytes: ...

    def kernel_payload(self, root: Path) -> bytes: ...

    def compose_main(self, root: Path, window: bytes, record: bytes, mailbox: bytes,
                     kernel_store: bytes) -> Program: ...


def rot_composer() -> RotComposer:
    return cast("RotComposer", importlib.import_module("vos.chain_rot"))


def mmode_composer() -> MmodeComposer:
    return cast("MmodeComposer", importlib.import_module("vos.chain_mmode"))


def _json(payload: object) -> bytes:
    """The bytes receipts.write publishes."""
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


# --- staging ----------------------------------------------------------------------------

_MARKER = re.compile(r'^# \d+ "([^"]+)"', re.MULTILINE)


def read_sources(root: Path, unit: cd.Compiled, source: str | None) -> dict[str, str]:
    """This checkout's files the preprocessor read, from the unit's line markers; a unit
    compiled from a checkout source must name it."""
    base = root.resolve()
    text = unit.preprocessed.path.read_text(encoding="utf-8", errors="replace")
    found: dict[str, str] = {}
    for name in dict.fromkeys(_MARKER.findall(text)):
        if name.startswith("<"):
            continue
        path = (Path(unit.preprocessed.cwd) / name).resolve()
        if path.is_relative_to(base):
            found[path.relative_to(base).as_posix()] = receipts.digest(path)
    if source is not None and source not in found:
        raise ValueError(f"the preprocessed unit does not name its own source {source}")
    return found


def lane_arguments(root: Path, arguments: Sequence[str]) -> list[str]:
    """A lane's COMPILE_ARGS with each relative include directory made the checkout's."""
    return [f"-I{root / argument[2:]}" if argument.startswith("-I")
            and not Path(argument[2:]).is_absolute() else argument for argument in arguments]


def portable(argv: Sequence[str], root: Path) -> list[str]:
    """A compile argv without this machine's paths: the compiler by role, its
    configuration files by name and include directories relative to the checkout."""
    base = root.resolve()
    result = ["ccomp"]
    for index, argument in enumerate(argv[1:], start=1):
        directory = Path(argument[2:]) if argument.startswith("-I") else None
        if argv[index - 1] in ("-conf", "-stdlib", "-include"):
            result.append(Path(argument).name)
        elif (directory is not None and directory.is_absolute()
              and directory.resolve().is_relative_to(base)):
            result.append("-I" + directory.resolve().relative_to(base).as_posix())
        else:
            result.append(argument)
    return result


def _named(files: Mapping[str, str]) -> dict[str, str]:
    named = {Path(path).name: digest for path, digest in files.items()}
    if len(named) != len(files):
        raise ValueError("compiler inputs and receipts need distinct file names")
    return dict(sorted(named.items()))


@dataclass(frozen=True)
class Unit:
    """One compiled chain unit."""

    source: str
    arguments: tuple[str, ...]
    mutant: tuple[str, str] | None = None


def compile_unit(root: Path, out: Path, ccomp: Path, compiler_args: Sequence[str], name: str,
                 unit: Unit) -> tuple[cd.Compiled, bytes]:
    """One unit through the contained compiler, its stream held to the accepted dialect.

    A mutant is the runtime source with one exact substitution, written to the output
    lane beside nothing and compiled with the runtime's own directory on the include
    path, so its quoted includes resolve to the files the runtime's do."""
    path = root / unit.source
    extra: list[str] = []
    source = path
    if unit.mutant is not None:
        old, new = unit.mutant
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise ValueError(f"the {name} substitution does not occur exactly once in {unit.source}")
        source = out / "mutants" / name / path.name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
        extra = [f"-I{path.parent}"]
    argv = [str(ccomp), *compiler_args, "-fverifiedos-typed", "-I" + str(root / "firmware/include"),
            *lane_arguments(root, unit.arguments), *extra]
    compiled = cd.compile_c(argv, source, out / name / "compiled")
    if compiled.stream is None or compiled.exit_code:
        raise ValueError(f"{name} target compilation refused: {compiled.said}")
    if cd.refusals(compiled.stream):
        raise ValueError(f"{name} target stream is outside the accepted dialect")
    raw = (out / name / "compiled" / f"{source.stem}.s").read_bytes()
    if hashlib.sha256(raw).hexdigest() != compiled.stream_sha256:
        raise ValueError(f"{name} stream changed after compilation")
    return compiled, raw


def frames(stream: str) -> int | None:
    """The sum of the stream's function frames, where its allocations take a known shape."""
    try:
        return boot_target.stack_ceiling(stream)
    except ValueError:
        return None


class MlDsaSigner:
    """One disposable ML-DSA-87 kernel-stage key, signing with FIPS 204's internal
    interface: OpenSSL's raw message encoding, no context, as `vos_mldsa87_verify_internal`
    verifies. The private key stays in `work`."""

    def __init__(self, work: Path, *, public_bytes: int, signature_bytes: int) -> None:
        self.work = work
        self.signature_bytes = signature_bytes
        work.mkdir(parents=True, exist_ok=True)
        executable = shutil.which("openssl")
        if executable is None:
            raise ValueError("kernel-stage signing needs OpenSSL with ML-DSA-87")
        self.executable = Path(executable)
        self.executable_sha256 = receipts.digest(self.executable)
        self.version = self._run("version", "-a").strip()
        self.key = work / "kernel-key.pem"
        self._run("genpkey", "-algorithm", "ML-DSA-87", "-out", str(self.key))
        self.key.chmod(0o600)
        public = work / "kernel-public.der"
        self._run("pkey", "-in", str(self.key), "-pubout", "-outform", "DER", "-out", str(public))
        encoded = public.read_bytes()
        self.public = encoded[-public_bytes:]
        if encoded != boot_crypto.public_der(boot_crypto.Case(
                "kernel-root", bc.MLDSA, self.public, b"", b"", b"", True)):
            raise ValueError("unexpected ML-DSA-87 public-key encoding")
        self.signed = 0

    def _run(self, *args: str) -> str:
        result = subprocess.run([str(self.executable), *args], cwd=self.work, capture_output=True,
                                text=True, timeout=120, check=False)
        if result.returncode:
            raise ValueError(f"OpenSSL {args[0]} failed ({result.returncode}): {result.stderr[-1000:]}")
        return result.stdout

    def sign(self, message: bytes) -> bytes:
        identity = hashlib.sha256(message).hexdigest()
        prefix, signature = self.work / f"{identity}.message", self.work / f"{identity}.mldsa"
        prefix.write_bytes(message)
        self._run("pkeyutl", "-sign", "-inkey", str(self.key), "-in", str(prefix),
                  "-out", str(signature), "-pkeyopt", "message-encoding:0")
        result = signature.read_bytes()
        if len(result) != self.signature_bytes:
            raise ValueError("unexpected ML-DSA-87 signature size")
        self.signed += 1
        return result

    def identity(self) -> dict[str, object]:
        if receipts.digest(self.executable) != self.executable_sha256:
            raise ValueError("the OpenSSL executable changed during kernel-stage signing")
        return {"scheme": "ML-DSA-87", "interface": "internal message, no context",
                "openssl_version": self.version, "openssl_executable": str(self.executable),
                "openssl_sha256": self.executable_sha256, "root": self.public.hex(),
                "signed_prefixes": self.signed}


def units(rot: RotComposer, mmode: MmodeComposer) -> dict[str, Unit]:
    if set(rot.RUNTIME_MUTANTS) != set(bc.MUTANTS.values()):
        raise ValueError(f"the RoT composer's mutants are {sorted(rot.RUNTIME_MUTANTS)}, not "
                         f"section 9.10's {sorted(bc.MUTANTS.values())}")
    found = {"rom": Unit(rot.ROM_SOURCE, tuple(rot.COMPILE_ARGS)),
             "runtime": Unit(rot.RUNTIME_SOURCE, tuple(rot.COMPILE_ARGS)),
             **{unit: Unit(rot.RUNTIME_SOURCE, tuple(rot.COMPILE_ARGS), rot.RUNTIME_MUTANTS[mutant])
                for unit, mutant in bc.MUTANTS.items()},
             "mmode": Unit(mmode.MMODE_SOURCE, tuple(mmode.COMPILE_ARGS))}
    if tuple(found) != bc.UNITS:
        raise ValueError("the staged units are not the campaign's")
    return found


def signature_verdicts(f: bc.Facts, work: Path, images: Mapping[str, bytes],
                       production: bytes, kernel_root: bytes) -> list[dict[str, object]]:
    """OpenSSL's verdict on each image's signed prefix under its root, and on each flip
    a case makes inside a signature: the oracle's signature decisions, one per triple."""
    records: list[dict[str, object]] = []
    work.mkdir(parents=True, exist_ok=True)
    flipped = {"stage0", "mmode-a", "kernel"}
    for name in bc.IMAGE_NAMES:
        kernel = name == "kernel"
        data = images[name]
        size = f["CHAIN_KSTAGE_HEADER_BYTES"] if kernel else f["BOOT_HEADER_BYTES"]
        scheme, key = (bc.MLDSA, kernel_root) if kernel else (bc.SLH, production)
        prefix, signature = data[:f["BOOT_SIGNED_BYTES"]], data[f["BOOT_HDR_SIGNATURE"]:size]
        variants = [("valid", signature, True)]
        if name in flipped:
            variants.append(("signature-flipped", bc.flip(signature, bc.SIGNATURE_FLIP_AT), False))
        for variant, candidate, wanted in variants:
            accepted = boot_crypto.openssl_verify(work, boot_crypto.Case(
                f"{name}-{variant}", scheme, key, prefix, b"", candidate, wanted))
            if accepted is not wanted:
                raise ValueError(f"OpenSSL {'refused' if wanted else 'accepted'} {name} ({variant})")
            records.append({"image": name, "variant": variant, "accepted": accepted,
                            "key": bc.verdict_key(scheme, key, prefix, candidate)})
    return records


def stage(root: Path, out: Path, ccomp: Path, compiler_args: list[str]) -> dict[str, Any]:
    """Compile every chain unit, lay out and sign the images, and write `bc.STAGED`.

    The staged files are the only compiler output and the only signatures a hosted
    runner receives. Staging binds the compiler's provenance and configuration, the
    exact checkout files each unit's preprocessor read and section 9.13's identities, and
    refuses where the freeze does not hold or `boot-crypto verify` does not pass.
    """
    root, out, ccomp = (path.resolve() for path in (root, out, ccomp))
    out.mkdir(parents=True, exist_ok=True)
    provenance, provenance_files = boot_crypto_target.compiler_provenance(ccomp)
    compiler_files = boot_target.compiler_inputs(compiler_args)
    directory = root / bc.STAGED
    if directory.is_dir() and (unexpected := sorted(
            {path.name for path in directory.iterdir()} - set(bc.STAGED_FILES))):
        raise ValueError(f"{bc.STAGED} holds files staging does not own: {unexpected}")
    rot, mmode = rot_composer(), mmode_composer()
    plan = units(rot, mmode)
    streams: dict[str, str] = {}
    raws: dict[str, bytes] = {}
    sources: dict[str, str] = {}
    directories: set[str] = set()
    entries: dict[str, object] = {}
    native: dict[str, object] = {}
    for name, unit in plan.items():
        compiled, raw = compile_unit(root, out, ccomp, compiler_args, name, unit)
        read = read_sources(root, compiled, None if unit.mutant else unit.source)
        if changed := sorted(key for key, value in read.items() if sources.get(key, value) != value):
            raise ValueError(f"staging inputs changed between units: {changed}")
        sources.update(read)
        directories |= boot_crypto_target.search_directories(root, compiled, read)
        streams[name], raws[name] = raw.decode("utf-8"), raw
        mutant = None
        if unit.mutant is not None:
            mutant = {"name": bc.MUTANTS[name], "source": unit.source,
                      "old_sha256": hashlib.sha256(unit.mutant[0].encode()).hexdigest(),
                      "new_sha256": hashlib.sha256(unit.mutant[1].encode()).hexdigest()}
        entries[name] = {"file": f"{name}.s", "source": unit.source, "mutant": mutant,
                         "assembly_sha256": compiled.stream_sha256,
                         "argv": portable(compiled.argv, root), "lines": compiled.lines,
                         "sum_of_function_frames": frames(streams[name])}
        native[name] = {"argv": list(compiled.argv), "preprocessed_sha256": compiled.preprocessed.sha256}
    f = bc.facts(root)
    state_name = bh.LIFECYCLES[f.lifecycle]
    if state_name not in bh.ROOT_STATES:
        raise ValueError(f"the shipped lifecycle state {state_name} accepts no root to sign under")
    slh = boot_signing.SlhSigner(out / "signing", bh.ROOT_STATES,
                                 public_bytes=f["BOOT_PUBLIC_KEY_BYTES"],
                                 signature_bytes=f["BOOT_SIGNATURE_BYTES"])
    mldsa = MlDsaSigner(out / "signing", public_bytes=f["CHAIN_KSTAGE_PUBLIC_KEY_BYTES"],
                        signature_bytes=f["CHAIN_KSTAGE_SIGNATURE_BYTES"])
    production = slh.roots[state_name]
    runtime = rot.runtime_payload(root, streams["runtime"])
    slots = {name: mmode.mmode_payload(root, streams["mmode"], mldsa.public, tag)
             for name, tag in zip(("mmode-a", "mmode-b", "mmode-recovery"), f.tags, strict=True)}
    kernel = mmode.kernel_payload(root)
    images = {"stage0": bc.build_image(f, runtime, stage=f["BOOT_STAGE_ROT_RUNTIME"],
                                       version=f.floor, signer=production, sign=slh.sign)}
    for name, payload in slots.items():
        images[name] = bc.build_image(f, payload, stage=f["BOOT_STAGE_MMODE_IMAGE"],
                                      version=f.floor, signer=production, sign=slh.sign)
    images["mmode-a-below-floor"] = bc.build_image(
        f, slots["mmode-a"], stage=f["BOOT_STAGE_MMODE_IMAGE"], version=f.floor - 1,
        signer=production, sign=slh.sign)
    images["kernel"] = bc.build_image(f, kernel, stage=f["BOOT_STAGE_CORE_KERNELS"],
                                      version=f.floor, signer=mldsa.public,
                                      sign=lambda _, message: mldsa.sign(message))
    verdicts = signature_verdicts(f, out / "verify", images, production, mldsa.public)
    if (boot_crypto_target.compiler_provenance(ccomp) != (provenance, provenance_files)
            or boot_target.compiler_inputs(compiler_args) != compiler_files
            or any(receipts.digest(root / name) != value for name, value in sources.items())):
        raise ValueError("staging inputs changed during compilation")
    crypto = json.loads((root / boot_crypto_target.MANIFEST).read_text(encoding="utf-8"))
    files: dict[str, bytes] = {f"{name}.s": bc.HEADER.encode("utf-8") + raws[name] for name in bc.UNITS}
    files["images.json"] = _json({"schema": 1, "images": {name: data.hex()
                                                          for name, data in images.items()}})
    headers = {name: {"sha256": hashlib.sha256(data).hexdigest(),
                      **{key: int.from_bytes(data[f[at]:f[at] + 8], "little") for key, at in (
                          ("stage", "BOOT_HDR_STAGE"),
                          ("security_version", "BOOT_HDR_SECURITY_VERSION"),
                          ("payload_length", "BOOT_HDR_PAYLOAD_LENGTH"))}}
               for name, data in images.items()}
    manifest = {
        "schema": 1, "generator": bc.GENERATOR, "contract": bh.CONTRACT, "floor": f.floor,
        "compiler_provenance": provenance,
        "compiler_receipts_sha256": _named(provenance_files),
        "compiler_inputs_sha256": _named(compiler_files),
        "sources_sha256": dict(sorted(sources.items())),
        "search_directories": {name: bc.listing(root, name) for name in sorted(directories)},
        "units": entries, "images": headers,
        "keys": {"rom_roots": {state: key.hex() for state, key in slh.roots.items()},
                 "kernel_root": mldsa.public.hex(), "signed_under": state_name},
        "signature_verdicts": verdicts,
        "freeze": {"manifest": boot_crypto_target.MANIFEST,
                   "sources_sha256": {path: sources.get(path) for path in bc.FROZEN},
                   "compiler": {key: provenance.get(key) for key in ("revision", "compiler_sha256")},
                   "compcert_ini_sha256": _named(compiler_files).get("compcert.ini"),
                   "required_arguments": list(bc.REQUIRED_ARGUMENTS),
                   "crypto_sources_sha256": {path: crypto.get("sources_sha256", {}).get(path)
                                             for path in bc.FROZEN}},
        "files_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
    }
    if problems := bc.freeze_findings(root, manifest):
        raise ValueError("section 9.13's freeze does not hold: " + "; ".join(problems))
    boot_crypto_target.staged(root)
    files["manifest.json"] = _json(manifest)
    for name, data in files.items():
        with receipts.atomic_path(directory / name) as pending:
            pending.write_bytes(data)
    return {"passed": True, "manifest": manifest, "native_units": native,
            "native_compiler_inputs_sha256": compiler_files,
            "native_compiler_receipts_sha256": provenance_files, "compiler_path": str(ccomp),
            "signing": {"slh": slh.identity(), "mldsa": mldsa.identity(),
                        "private_keys": str(out / "signing")}}


def layouts(root: Path, staged: bc.Staged, rot: RotComposer, mmode: MmodeComposer) -> list[str]:
    """Where the composers, run now over the staged streams, lay out other payloads than
    the staged images carry."""
    f = bc.facts(root, staged.manifest["floor"])
    header, kernel_header = f["BOOT_HEADER_BYTES"], f["CHAIN_KSTAGE_HEADER_BYTES"]
    problems: list[str] = []
    if rot.runtime_payload(root, staged.streams["runtime"]) != staged.images["stage0"][header:]:
        problems.append("the RoT composer no longer lays the staged runtime out as stage0")
    for name, tag in zip(("mmode-a", "mmode-b", "mmode-recovery"), f.tags, strict=True):
        if mmode.mmode_payload(root, staged.streams["mmode"], staged.kernel_root,
                               tag) != staged.images[name][header:]:
            problems.append(f"the M-mode composer no longer lays the staged stream out as {name}")
    if mmode.kernel_payload(root) != staged.images["kernel"][kernel_header:]:
        problems.append("the M-mode composer no longer lays the kernel stage out as staged")
    return problems


def verify(root: Path) -> bc.Staged:
    """`chain-verify`: the staged directory, and the composers' layouts of its streams."""
    found = bc.staged(root)
    if problems := layouts(root.resolve(), found, rot_composer(), mmode_composer()):
        raise ValueError("; ".join(problems))
    return found


# --- endings --------------------------------------------------------------------------

_RELEASE = re.compile(r"RELEASE: the RoT released the boot core after (\d+) instructions retired")
_BITE = re.compile(r"FAILURE: the RoT watchdog bit and asserted the die reset after (\d+) "
                   r"external slow-clock ticks with (\d+) instructions retired")
_HTIF = re.compile(r"FAILURE: (\d+) \(0x([0-9a-fA-F]+)\)")
_RETIRED = re.compile(r"^Instructions:\s+(\d+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Ending:
    """How one run ended, by section 9.2: a release, an HTIF success or failure, the
    bite, the instruction limit, or no verdict."""

    kind: str
    code: int | None = None
    ticks: int | None = None
    retired: int | None = None
    reason: str = ""

    def label(self) -> str:
        return f"failure:{self.code}" if self.kind == "failure" else self.kind


def classify(log: str, process_exit: int | None, limit: int) -> Ending:
    """Exactly one recognized verdict line with its exit status, or the instruction limit
    with no verdict line at all; anything else, contradictory lines included, is none."""
    if process_exit is None:
        return Ending("no-verdict", reason="the run reached its timeout")
    markers = [line.strip() for line in log.splitlines()
               if any(word in line for word in ("SUCCESS", "FAILURE", "RELEASE"))]
    if not markers:
        if process_exit == 0 and _RETIRED.findall(log) == [str(limit)]:
            return Ending("limit", retired=limit)
        return Ending("no-verdict", reason=f"exit {process_exit} with no verdict line")
    if len(markers) > 1:
        return Ending("no-verdict", reason=f"contradictory verdict lines: {markers[:3]}")
    line = markers[0]
    if line == "SUCCESS" and process_exit == 0:
        return Ending("success", 0)
    if (match := _RELEASE.fullmatch(line)) and process_exit == 0:
        return Ending("release", retired=int(match[1]))
    if (match := _BITE.fullmatch(line)) and process_exit == 1:
        return Ending("bite", ticks=int(match[1]), retired=int(match[2]))
    if ((match := _HTIF.fullmatch(line)) and int(match[1]) == int(match[2], 16)
            and process_exit == 1):
        return Ending("failure", int(match[1]))
    return Ending("no-verdict", reason=f"unrecognized verdict line or exit {process_exit}: {line!r}")


# --- execution ------------------------------------------------------------------------


def periods(f: bc.Facts) -> dict[str, int]:
    """Section 9.10's external slow-clock period per run kind; 0 runs no external clock."""
    return {"boot": f["CHAIN_SLOW_CLOCK_BOOT_NS"], "service": 0, "main": 0,
            "runtime-only": f["CHAIN_SLOW_CLOCK_WATCHDOG_NS"], "control": 0}


def limits(f: bc.Facts) -> dict[str, int]:
    return {**INST_LIMITS, "control": f["CHAIN_CONTROL_INST_LIMIT"]}


def run_timeouts(boot: int, main: int, short: int) -> dict[str, int]:
    if min(boot, main, short) < 1:
        raise ValueError("every run kind needs a positive timeout")
    return {"boot": boot, "service": short, "main": main, "runtime-only": short, "control": short}


@dataclass(frozen=True)
class ColdBoot:
    """`cold-boot`'s R1 capture and R2 response, as its receipt identifies them."""

    capture: bytes
    response: bytes
    record: dict[str, str]


@dataclass
class Campaign:
    root: Path
    simulator: Path
    facts: bc.Facts
    staged: bc.Staged
    inputs: bc.Inputs
    rows: dict[str, bh.ChainCase]
    rot: RotComposer
    mmode: MmodeComposer
    periods: dict[str, int]
    limits: dict[str, int]
    timeouts: dict[str, int]
    cold: ColdBoot | None = None


def _shipped(root: Path, base: str) -> dict[str, object]:
    digest = receipts.digest(root / base)
    return {"base": base, "base_sha256": digest, "file": None, "sha256": digest, "changes": {}}


def program_findings(f: bc.Facts, program: Program, kind: str) -> list[str]:
    """Where a composed program's capture and HTIF symbols are not section 9.11's."""
    symbols = program.symbols
    found = [] if "tohost" in symbols else ["the program has no tohost"]
    begin, end = symbols.get("begin_signature"), symbols.get("end_signature")
    if kind == "main":
        base, size = f["CHAIN_MAILBOX_BASE"], f["CHAIN_MAIN_SIGNATURE_BYTES"]
        if program.entry != f["CHAIN_MMODE_LOAD_BASE"]:
            found.append(f"the main-die program enters at {program.entry:#x}, not the load base")
        if symbols.get("tohost", ("", -1))[1] != f["CHAIN_TOHOST_BASE"]:
            found.append("the main-die program's tohost is not chain.tohost_base")
    else:
        base, size = f["CHAIN_ROT_CAPTURE_BASE"], f["CHAIN_CAPTURE_BYTES"]
    if begin is None or end is None or begin[1] != base or end[1] - begin[1] != size:
        found.append(f"the program's signature region is not {size:#x} bytes from {base:#x}")
    return found


def emulate(campaign: Campaign, directory: Path, label: str, kind: str, program: Program,
            config: tuple[Path, dict[str, object]]) -> tuple[dict[str, object], Ending, bytes | None]:
    """One emulator process: its row, its ending and its strictly decoded capture."""
    f = campaign.facts
    capture_bytes = f["CHAIN_MAIN_SIGNATURE_BYTES"] if kind == "main" else f["CHAIN_CAPTURE_BYTES"]
    assembly, elf = directory / f"{label}.s", directory / f"{label}.elf"
    signature, log = directory / f"{label}.signature", directory / f"{label}.log"
    assembly.write_text(program.assembly, encoding="utf-8", newline="\n")
    image.write_elf(elf, list(program.sections), dict(program.symbols), program.entry)
    signature.unlink(missing_ok=True)
    period, limit, timeout = campaign.periods[kind], campaign.limits[kind], campaign.timeouts[kind]
    argv = [str(campaign.simulator), "--config", str(config[0]), "--show-times",
            "--inst-limit", str(limit), "--rot-slow-clock-ns", str(period),
            "--test-signature", str(signature),
            "--signature-granularity", str(CAPTURE_GRANULARITY), str(elf)]
    began = time.monotonic()
    process_exit: int | None = None
    try:
        with log.open("w", encoding="utf-8") as output:
            process_exit = subprocess.run(argv, cwd=directory, stdout=output,
                                          stderr=subprocess.STDOUT, timeout=timeout,
                                          check=False).returncode
    except subprocess.TimeoutExpired:
        process_exit = None
    ending = classify(log.read_text(encoding="utf-8", errors="replace"), process_exit, limit)
    problems: list[str] = []
    capture: bytes | None = None
    if signature.is_file():
        try:
            capture = boot_release_target.read_output(signature, capture_bytes)
        except (ValueError, UnicodeDecodeError) as exc:
            problems.append(f"{label} wrote a malformed or short capture: {exc}")
    row: dict[str, object] = {
        "run": label, "kind": kind, "period_ns": period, "inst_limit": limit, "timeout": timeout,
        "config": config[1], "assembly_sha256": receipts.digest(assembly),
        "elf_sha256": receipts.digest(elf), "log_sha256": receipts.digest(log), "argv": argv,
        "entry": hex(program.entry), "process_exit": process_exit, "ending": ending.label(),
        "ending_detail": asdict(ending), "capture_present": signature.is_file(),
        "capture_sha256": hashlib.sha256(capture).hexdigest() if capture is not None else None,
        "seconds": round(time.monotonic() - began, 3), "problems": problems}
    return row, ending, capture


def _decide(row: dict[str, object], ending: Ending, wanted: str, capture: bytes | None,
            policy: str) -> list[str]:
    """A run's ending against the one wanted, and its capture against `policy`: `owed`
    on a release or an HTIF success, `forbidden` on an HTIF failure or a bite, where the
    emulator writes none, and `either` on the control's instruction limit, which
    section 9.10 decides by its lines alone."""
    problems = cast("list[str]", row["problems"])
    if ending.label() != wanted:
        problems.append(f"{row['run']} ended {ending.label()} ({ending.reason or 'as reported'}), "
                        f"not {wanted}")
    if policy == "owed" and capture is None and not problems:
        problems.append(f"{row['run']} wrote no capture")
    if policy == "forbidden" and row["capture_present"]:
        problems.append(f"{row['run']} wrote a capture where its ending allows none")
    return problems


def _mailbox(f: bc.Facts, response: bytes) -> bytes:
    mailbox = bytearray(f["CHAIN_MAILBOX_BYTES"])
    at = f["CHAIN_MAILBOX_RESPONSE_AT"]
    mailbox[at:at + len(response)] = response
    return bytes(mailbox)


def _main_run(campaign: Campaign, directory: Path, case: bc.Plan, window: bytes, record: bytes,
              response: bytes) -> dict[str, object]:
    f = campaign.facts
    if case.kernel_image is None or case.mmode is None:
        raise ValueError(f"{case.spec.name} has no main-die run")
    program = campaign.mmode.compose_main(campaign.root, window, record, _mailbox(f, response),
                                          case.kernel_image)
    if found := program_findings(f, program, "main"):
        return {"run": "r3", "kind": "main", "problems": found, "passed": False}
    row, ending, capture = emulate(campaign, directory, "r3", "main", program,
                                   (campaign.root / bh.MAIN_CONFIG, _shipped(campaign.root, bh.MAIN_CONFIG)))
    wanted = "success" if case.mmode.exit_code == 0 else f"failure:{case.mmode.exit_code}"
    # The emulator writes no capture on FAILURE, so a refusal is decided by its exit code
    # alone; the kernel stage's SUCCESS, written after its eleven checks, is the kernel
    # entry's observation, and only it carries the request and M-mode capture compared.
    row["decided_by"] = "capture and exit code" if wanted == "success" else "exit code"
    problems = _decide(row, ending, wanted, capture,
                       "owed" if wanted == "success" else "forbidden")
    if capture is not None and not problems:
        found, seen = bc.compare("R3", bc.main_capture(f, case), capture)
        problems += found
        row["observed"] = seen
    row["passed"] = not problems
    return row


def _case_row(spec: bc.Spec, case: bc.Plan | None, images: dict[str, str]) -> dict[str, object]:
    expected: dict[str, object] = {"run": spec.run}
    if case is not None:
        expected["verdict"] = case.verdict
        if case.mmode is not None:
            expected["main_die_exit"] = case.mmode.exit_code
    else:
        expected["ending"] = spec.ending()
    return {"case": spec.name, "run": spec.run, "inputs": spec.inputs(), "expected": expected,
            "images_sha256": images, "runs": [], "unexecuted_runs": [], "problems": []}


def _images_used(case: bc.Plan) -> dict[str, str]:
    used = {"stage0": case.stage0, **{f"slot{slot}": data for slot, data in case.stores.items()}}
    if case.kernel_image is not None:
        used["kernel"] = case.kernel_image
    return {name: hashlib.sha256(data).hexdigest() for name, data in used.items()}


def _finish(row: dict[str, object], began: float) -> dict[str, object]:
    runs = cast("list[dict[str, object]]", row["runs"])
    problems = cast("list[str]", row["problems"])
    row["passed"] = (not problems and not row["unexecuted_runs"] and bool(runs)
                     and all(run.get("passed") is True for run in runs))
    row["seconds"] = round(time.monotonic() - began, 3)
    return row


def joined_case(campaign: Campaign, spec: bc.Spec, directory: Path) -> dict[str, object]:
    """A boot case: R1, then on a release R2 and R3, each gated on the one before."""
    began = time.monotonic()
    f, root = campaign.facts, campaign.root
    case = bc.plan(f, spec, campaign.inputs)
    row = _case_row(spec, case, _images_used(case))
    problems = cast("list[str]", row["problems"])
    runs = cast("list[dict[str, object]]", row["runs"])
    owed = ["r1", "r2", "r3"] if case.released else ["r1"]
    problems += bc.table_findings(f, campaign.rows[spec.name], spec, case)
    if problems:
        row["unexecuted_runs"] = owed
        return _finish(row, began)
    variant = bc.configuration_variant(root, bh.ROT_CONFIG, {
        ("platform", "boot_control", "boot_target"): spec.boot_target,
        ("platform", "boot_control", "active_slot"): spec.slot,
        ("platform", "boot_control", "attempts"): case.attempts,
        ("platform", "otp", "lifecycle_state"): bc.LIFECYCLE_STATES[case.lifecycle]},
        directory / "rot-config.json")
    config = (directory / "rot-config.json", variant)
    inputs = campaign.rot.RomInputs(roots=campaign.staged.roots, runtime_image=case.stage0,
                                    slot_images=case.stores, floor=f.floor,
                                    entropy_failed=spec.entropy_failed)
    program = campaign.rot.compose_rom(root, campaign.staged.streams["rom"], inputs)
    if found := program_findings(f, program, "boot"):
        problems += found
        row["unexecuted_runs"] = owed
        return _finish(row, began)
    r1, ending, capture = emulate(campaign, directory, "r1", "boot", program, config)
    runs.append(r1)
    r1_problems = _decide(r1, ending, "release" if case.released else "success", capture, "owed")
    if capture is not None and not r1_problems:
        found, seen = bc.compare("R1", bc.boot_capture(f, case), capture)
        r1_problems += found
        r1["observed"] = seen
    r1["passed"] = not r1_problems
    if spec.name == bc.COLD_BOOT and capture is not None:
        (directory / "r1-capture.bin").write_bytes(capture)
        row["r1_capture"] = f"{spec.name}/r1-capture.bin"
        row["r1_capture_sha256"] = hashlib.sha256(capture).hexdigest()
    if r1_problems or not case.released or case.runtime is None:
        row["unexecuted_runs"] = owed[1:] if r1_problems else []
        return _finish(row, began)
    if case.service_state is None or case.request is None or case.service is None:
        raise ValueError(f"{spec.name} releases without a service plan")
    payload = campaign.staged.images["stage0"][f["BOOT_HEADER_BYTES"]:]
    program = campaign.rot.compose_service(root, payload, case.service_state, case.request)
    if found := program_findings(f, program, "service"):
        problems += found
        row["unexecuted_runs"] = owed[1:]
        return _finish(row, began)
    r2, ending, capture = emulate(campaign, directory, "r2", "service", program, config)
    runs.append(r2)
    r2_problems = _decide(r2, ending, "success", capture, "owed")
    if capture is not None and not r2_problems:
        found, seen = bc.compare("R2", bc.service_capture(f, case), capture)
        r2_problems += found
        r2["observed"] = seen
    r2["passed"] = not r2_problems
    if spec.name == bc.COLD_BOOT and capture is not None:
        at = f["CHAIN_CAPTURE_RESPONSE_AT"]
        response = capture[at:at + f["CHAIN_RESPONSE_BYTES"]]
        (directory / "r2-response.bin").write_bytes(response)
        row["r2_response"] = f"{spec.name}/r2-response.bin"
        row["r2_response_sha256"] = hashlib.sha256(response).hexdigest()
    if r2_problems or case.response is None:
        row["unexecuted_runs"] = owed[2:]
        return _finish(row, began)
    runs.append(_main_run(campaign, directory, case, case.runtime.window, case.runtime.record,
                          case.response))
    return _finish(row, began)


def main_die_case(campaign: Campaign, spec: bc.Spec, directory: Path) -> dict[str, object]:
    """A main-die case: R3 over `cold-boot`'s captured R1 window and record and its R2
    response, each first held to the oracle's."""
    began = time.monotonic()
    f = campaign.facts
    case = bc.plan(f, spec, campaign.inputs)
    row = _case_row(spec, case, _images_used(case))
    problems = cast("list[str]", row["problems"])
    problems += bc.table_findings(f, campaign.rows[spec.name], spec, case)
    cold = campaign.cold
    if cold is None or case.runtime is None or case.service is None:
        raise ValueError(f"{spec.name} needs cold-boot's R1 capture and R2 response")
    window_at, record_at = f["CHAIN_CAPTURE_WINDOW_AT"], f["CHAIN_CAPTURE_RECORD_AT"]
    window = cold.capture[window_at:window_at + f["CHAIN_MMODE_REGION_BYTES"]]
    record = cold.capture[record_at:record_at + f["HANDOFF_BYTES"]]
    if (window != case.runtime.window or record != case.runtime.record
            or cold.response != case.service.response):
        problems.append("cold-boot's R1 capture or R2 response differs from the oracle's")
    if problems:
        row["unexecuted_runs"] = ["r3"]
        return _finish(row, began)
    response = cold.response if spec.response == "bound" else case.response
    if response is None:
        raise ValueError(f"{spec.name} has no response to place")
    cast("list[dict[str, object]]", row["runs"]).append(
        _main_run(campaign, directory, case, window, record, response))
    return _finish(row, began)


def runtime_only_case(campaign: Campaign, spec: bc.Spec, directory: Path) -> dict[str, object]:
    """A watchdog case: a mutant runtime placed unsigned with the state a ROM would leave,
    at the watchdog period or with no external clock."""
    began = time.monotonic()
    f, root = campaign.facts, campaign.root
    unit = next(name for name, mutant in bc.MUTANTS.items() if mutant == spec.mutant)
    payload = campaign.rot.runtime_payload(root, campaign.staged.streams[unit])
    row = _case_row(spec, None, {"payload": hashlib.sha256(payload).hexdigest()})
    problems = cast("list[str]", row["problems"])
    problems += bc.table_findings(f, campaign.rows[spec.name], spec, None)
    kind = "runtime-only" if spec.clock else "control"
    program = campaign.rot.compose_runtime_only(root, payload, bc.runtime_only_state(f, payload),
                                                f.floor)
    problems += program_findings(f, program, kind)
    if problems:
        row["unexecuted_runs"] = ["runtime-only"]
        return _finish(row, began)
    run, ending, capture = emulate(campaign, directory, "runtime-only", kind, program,
                                   (root / bh.ROT_CONFIG, _shipped(root, bh.ROT_CONFIG)))
    cast("list[dict[str, object]]", row["runs"]).append(run)
    wanted = spec.ending()
    run_problems = _decide(run, ending, "limit" if wanted == "limit" else "bite", capture,
                           "either" if wanted == "limit" else "forbidden")
    if wanted == "bite-late" and ending.kind == "bite" and not (ending.ticks or 0) > f.late:
        run_problems.append(f"the bite came after {ending.ticks} ticks, not past the late bound "
                            f"{f.late}")
    if wanted == "bite-early" and ending.kind == "bite" and not (ending.ticks or 0) < f.early:
        run_problems.append(f"the bite came after {ending.ticks} ticks, not before the early "
                            f"bound {f.early}")
    run["passed"] = not run_problems
    return _finish(row, began)


def load_cold_boot(directory: Path, shared: Mapping[str, object]) -> ColdBoot | None:
    """`cold-boot`'s receipt and files from its shard's output, held to the identities this
    shard runs under; None where `cold-boot` did not pass, which leaves its dependants
    unexecuted."""
    path = directory / "report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise TypeError(f"{path} is not a chain report")
    for key, value in shared.items():
        if report.get(key) != value:
            raise ValueError(f"cold-boot's receipt differs from this shard in {key}")
    rows = [row for row in report.get("cases", []) if isinstance(row, dict)
            and row.get("case") == bc.COLD_BOOT]
    if len(rows) != 1 or rows[0].get("passed") is not True:
        return None
    row = rows[0]
    found: dict[str, bytes] = {}
    for name in ("r1_capture", "r2_response"):
        file = (directory / str(row.get(name))).resolve()
        if not file.is_relative_to(directory.resolve()) or not file.is_file():
            raise ValueError(f"cold-boot's {name} is not in {directory}")
        found[name] = file.read_bytes()
        if hashlib.sha256(found[name]).hexdigest() != row.get(f"{name}_sha256"):
            raise ValueError(f"cold-boot's {name} differs from its receipt")
    return ColdBoot(found["r1_capture"], found["r2_response"], {
        "report_sha256": receipts.digest(path),
        "r1_capture_sha256": hashlib.sha256(found["r1_capture"]).hexdigest(),
        "r2_response_sha256": hashlib.sha256(found["r2_response"]).hexdigest()})


def selection_of(case: str | None, group: str | None) -> tuple[str, ...]:
    if (case is None) == (group is None):
        raise ValueError("select exactly one of a case or a group")
    if case is not None:
        if case not in bc.SPECS:
            raise ValueError(f"{case} is not a case of section 9.12")
        return (case,)
    if group not in bc.GROUPS:
        raise ValueError(f"{group} is not one of the groups {sorted(bc.GROUPS)}")
    return bc.GROUPS[group]


def run(root: Path, out: Path, simulator: Path, build_receipt: Path, selection: tuple[str, ...], *,
        timeouts: dict[str, int], jobs: int = 1, cold_boot: Path | None = None) -> dict[str, Any]:
    """Execute the selected cases over the staged inputs and write `progress.json`."""
    started = time.monotonic()
    if not 1 <= jobs <= 6:
        raise ValueError("chain target runs 1 to 6 cases at once")
    root, out, simulator, build_receipt = (path.resolve() for path in (root, out, simulator, build_receipt))
    out.mkdir(parents=True, exist_ok=True)
    sources = receipts.inputs(root, *bc.SOURCE_INPUTS)
    model = receipts.inputs(root, "model")
    identities = {str(path): receipts.digest(path) for path in (simulator, build_receipt)}
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")),
                                  identities[str(simulator)], model)
    rows = {row.name: row for row in bc.require_cases(root)}
    if len(set(selection)) != len(selection) or not set(selection) <= set(rows):
        raise ValueError(f"the selection {list(selection)} is not distinct cases of section 9.12")
    if not bh.boot_control_declared(root):
        raise ValueError(f"{bh.ROT_CONFIG} declares no platform.boot_control, so no case's "
                         "boot-control values can be varied (section 9.4)")
    rot, mmode = rot_composer(), mmode_composer()
    found = bc.staged(root)
    if problems := layouts(root, found, rot, mmode):
        raise ValueError("; ".join(problems))
    manifest_sha256 = receipts.digest(root / bc.MANIFEST)
    identities[str(root / bc.MANIFEST)] = manifest_sha256
    f = bc.facts(root, found.manifest["floor"])
    campaign = Campaign(root, simulator, f, found, found.inputs(), rows, rot, mmode, periods(f),
                        limits(f), timeouts)
    if problems := bc.vacuity_findings(f, campaign.inputs):
        raise ValueError("; ".join(problems))
    shared: dict[str, object] = {
        "source_sha256": sources, "model_source_sha256": model,
        "staged_manifest_sha256": manifest_sha256,
        "compiler_provenance": found.manifest["compiler_provenance"],
        "compiler_inputs_sha256": found.manifest["compiler_inputs_sha256"],
        "freeze": found.manifest["freeze"], "periods_ns": campaign.periods,
        "inst_limits": campaign.limits, "timeouts": timeouts, "floor": f.floor,
        "watchdog_bounds": {"early": f.early, "late": f.late}, "contract": bh.CONTRACT,
        "scope": "section 9's target chain on the golden emulator from staged inputs"}
    blocked: str | None = None
    ordered = [name for name in rows if name in selection]
    if any(bc.SPECS[name].run == "main-die" for name in ordered):
        if cold_boot is None:
            raise ValueError("main-die cases take cold-boot's outputs through --cold-boot")
        campaign.cold = load_cold_boot(cold_boot, shared)
        if campaign.cold is None:
            blocked = "cold-boot did not pass, so its dependants stay unexecuted"
    done: dict[str, dict[str, object]] = {}

    def execute(name: str) -> dict[str, object]:
        spec = bc.SPECS[name]
        directory = out / name
        directory.mkdir(parents=True, exist_ok=True)
        if spec.run == "joined":
            return joined_case(campaign, spec, directory)
        if spec.run == "main-die":
            return main_die_case(campaign, spec, directory)
        return runtime_only_case(campaign, spec, directory)

    runnable = [] if blocked is not None else ordered
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for name, row in zip(runnable, pool.map(execute, runnable), strict=True):
            done[name] = row
            receipts.write(out / "progress.json", {"status": "incomplete", "cases": [
                done[case] for case in ordered if case in done]})
    if sources != receipts.inputs(root, *bc.SOURCE_INPUTS) or model != receipts.inputs(root, "model"):
        raise ValueError("chain campaign sources changed during execution")
    if any(receipts.digest(Path(path)) != value for path, value in identities.items()):
        raise ValueError("the chain campaign's emulator, model receipt or staging changed")
    cases = [done[name] for name in ordered if name in done]
    unexecuted = [name for name in ordered if name not in done]
    return {"passed": not unexecuted and all(row["passed"] is True for row in cases),
            "selection": ordered, "cases": cases, "unexecuted_cases": unexecuted,
            "blocked": blocked, **shared, "inputs_sha256": identities,
            "cold_boot": campaign.cold.record if campaign.cold is not None else None,
            "jobs": jobs, "seconds": round(time.monotonic() - started, 3),
            "milestone_acceptance": "open"}
