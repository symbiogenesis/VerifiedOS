# SPDX-License-Identifier: Apache-2.0
"""Run the actual SLH boot callback on the RoT profile through the selected backend.

The composition supplies read-only public-key, signed-prefix and signature
capabilities. This is signature target execution, not the RoT release driver.
Compiler products remain in the native output lane and are never published.
"""

import json
import re
import subprocess
import time
from pathlib import Path

from vos import asm, image, kernel_restore, receipts
from vos import boot_handoff as bh
from vos.cli import compiler_diff as cd

SOURCE = "firmware/harness/slh_target.c"


def stack_ceiling(stream: str) -> int:
    """Sum all nonrecursive function frames, refusing unknown allocation shapes."""
    small = re.findall(r"cincoffsetimm c2, c2, -(\d+)", stream)
    large = re.findall(r"li (x\d+), -(\d+)\s+cincoffset c2, c2, \1", stream)
    allocations = re.findall(r"cincoffset(?:imm)? c2, c2,", stream)
    if not allocations or len(allocations) != len(small) + len(large):
        raise ValueError("unrecognized target stack allocation shape")
    return sum(int(n) for n in small) + sum(int(n) for _, n in large)


def compose(stream: str, public: bytes, message: bytes, signature: bytes) -> str:
    """The compiler harness with exact public/message extents and padded signature.

    A power-of-two signature extent avoids unrepresentable bounds. Padding is
    zero and outside the verifier's fixed checked length; it is never signed.
    The ordinary selected ABI supplies a bounded 16 KiB local stack.
    """
    signature_extent = 1 << (len(signature) - 1).bit_length()
    setup = ""
    for reg, label, length in ((10, "vos_public_key", len(public)),
                               (11, "vos_signed_prefix", len(message)),
                               (12, "vos_signature", signature_extent)):
        setup += (f"        li t0, {label}\n"
                  f"        csetaddr c{reg}, c4, t0\n"
                  f"        li t0, {length}\n"
                  f"        csetbounds c{reg}, c{reg}, t0\n"
                  "        li t0, 3\n"
                  f"        candperm c{reg}, c{reg}, t0\n")
    anchor = "        call    main\n"
    if cd.PROLOGUE.count(anchor) != 1:
        raise ValueError("the compiler harness no longer has one main call")
    prologue = cd.PROLOGUE.replace(anchor, setup + anchor, 1)
    result = cd.compose(stream, prologue)
    for label, blob, alignment, capacity in (
        ("vos_public_key", public, 64, len(public)),
        ("vos_signed_prefix", message, 8, len(message)),
        ("vos_signature", signature, signature_extent, signature_extent),
    ):
        result += f"\n        .balign {alignment}\n{label}:\n"
        result += "\n".join("        .byte " + ",".join(str(b) for b in blob[i:i + 32])
                            for i in range(0, len(blob), 32)) + "\n"
        if capacity > len(blob):
            result += f"        .space {capacity - len(blob)}\n"
    return result


def run(root: Path, out: Path, ccomp: Path, ccomp_args: list[str], simulator: Path,
        build_receipt: Path, boot_image: Path, public_key: Path,
        timeout: int = 1200, inst_limit: int = 150_000_000) -> dict[str, object]:
    """Accept a real signed prefix and refuse corrupt signature/wrong-root neighbors."""
    started = time.monotonic()
    root, out, ccomp, simulator, build_receipt, boot_image, public_key = (
        p.resolve() for p in (root, out, ccomp, simulator, build_receipt, boot_image, public_key))
    out.mkdir(parents=True, exist_ok=True)
    sources = receipts.inputs(root, "firmware", "tools/vos")
    model_sources = receipts.inputs(root, "model")
    identities = {str(p): receipts.digest(p) for p in (ccomp, simulator, build_receipt, boot_image, public_key)}
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")),
                                  identities[str(simulator)], model_sources)
    lay = bh.layout(root)
    boot, public = boot_image.read_bytes(), public_key.read_bytes()
    if len(boot) < lay["BOOT_HEADER_BYTES"] or len(public) != lay["BOOT_PUBLIC_KEY_BYTES"]:
        raise ValueError("target signature inputs require a complete header and exact public key")
    message = boot[:lay["BOOT_SIGNED_BYTES"]]
    signature = boot[lay["BOOT_HDR_SIGNATURE"]:lay["BOOT_HEADER_BYTES"]]
    # The real host callback must accept the exact same image before a positive
    # target claim is possible. The input image has the bring-up layout/floor.
    host, _ = bh.compile_rot_stage(root, out)
    host_said = bh.rot_stage(host, boot_image, bh.RotInputs(3, 1, 0, 0), "slh256s", out,
                             roots={"production": public})
    if host_said.get("verdict") != "release":
        raise ValueError(f"the host release rejects the target input: {host_said.get('verdict')}")
    compiled = cd.compile_c([str(ccomp), *ccomp_args, "-fverifiedos-typed",
                             "-I" + str(root / "firmware/include")], root / SOURCE, out / "compiled")
    if compiled.stream is None or compiled.exit_code:
        raise ValueError(f"SLH target compilation refused: {compiled.said}")
    if cd.refusals(compiled.stream):
        raise ValueError("SLH target stream is outside the accepted assembler dialect")
    # Every allocation is a constant negative increment in this finite scalar
    # program. The sum across all frames is a conservative simple-call-path
    # ceiling; the authored verifier is nonrecursive. This is not stack WCET.
    frames = stack_ceiling(compiled.stream)
    if frames > cd.STACK_BYTES:
        raise ValueError("the sum of SLH target frames exceeds the bounded harness stack")
    rows: list[dict[str, object]] = []
    for name, key, sig, expected in (
        ("valid", public, signature, 0),
        ("corrupt-signature", public, bh.flip(signature, 0), 1),
        ("wrong-root", bh.flip(public, 0), signature, 1),
    ):
        composite = compose(compiled.stream, key, message, sig)
        (out / f"{name}.s").write_text(composite, encoding="utf-8", newline="\n")
        assembler = asm.Assembler(composite, name)
        sections, symbols, entry = assembler.assemble()
        text = next(section for section in sections if section.name == ".text")
        if text.addr + len(text.data) > asm.DATA_BASE:
            raise ValueError("the signature target text reaches the data section")
        elf = out / f"{name}.elf"
        image.write_elf(elf, sections, symbols, entry)
        argv = [str(simulator), "--config", str(root / bh.ROT_CONFIG),
                "--inst-limit", str(inst_limit), str(elf)]
        began = time.monotonic()
        log = out / f"{name}.log"
        with log.open("w", encoding="utf-8") as output:
            completed = subprocess.run(argv, cwd=out, stdout=output, stderr=subprocess.STDOUT,
                                       timeout=timeout, check=False)
        verdict, code, said = cd.htif_verdict(log.read_text(encoding="utf-8"), completed.returncode)
        passed = (verdict == ("pass" if expected == 0 else "fail") and code == expected
                  and completed.returncode == expected)
        rows.append({"case": name, "expected_accept": expected == 0, "verdict": verdict,
                     "code": code, "diagnostic": said, "passed": passed,
                     "seconds": round(time.monotonic() - began, 3), "argv": argv,
                     "process_exit": completed.returncode, "elf_sha256": receipts.digest(elf),
                     "log_sha256": receipts.digest(log)})
        receipts.write(out / "progress.json", {"status": "incomplete", "cases": rows})
    if sources != receipts.inputs(root, "firmware", "tools/vos") or model_sources != receipts.inputs(root, "model"):
        raise ValueError("signature target sources changed during the campaign")
    if any(receipts.digest(Path(path)) != value for path, value in identities.items()):
        raise ValueError("signature target tools or inputs changed during the campaign")
    return {"passed": all(row["passed"] for row in rows), "cases": rows,
            "scope": "SLH callback on RoT profile, with host measured-release input",
            "milestone_acceptance": "open", "source_sha256": sources,
            "model_source_sha256": model_sources, "inputs_sha256": identities,
            "preprocessed_sha256": compiled.preprocessed.sha256,
            "assembly_sha256": compiled.stream_sha256, "compile_argv": list(compiled.argv),
            "stack_bytes": cd.STACK_BYTES, "sum_of_function_frames": frames,
            "host_release": host_said, "seconds": round(time.monotonic() - started, 3)}
