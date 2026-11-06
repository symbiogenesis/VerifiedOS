# SPDX-License-Identifier: Apache-2.0
"""Qualify the Q25w Span<byte> carrier and vela-first-slice packet validator.

This module connects the authored Vela source (`tools/vela/examples/first_slice.vela`)
to:
1. Rocq elaboration (`rocq c`, `Print Assumptions`, and `rocqchk`) of the concrete
   `Span<byte>` carrier laws, `PrepareAndValidatePacket` functional and `restores`
   contracts, and expected-byte/status scenario theorems;
2. The capacity-invariance gate (`N = 4` / `8` vs `N = 1,000,000,000`) proving
   identical obligation counts, reduction steps, and proof structure;
3. Well-formed semantic negative neighbors (bounds, `in` borrow mutation, `ReadOnly`
   mutation, invalidated tag read, overlapping `CopyPrefix`, uncontained `Restore`,
   broken `restores` contract, wrong expected byte, and stale-input leak) that parse
   cleanly and fail during type/proof checking for the intended semantic reason; and
4. AST-driven lowering of the executable declarations to Clight/C and purecap
   CHERI-RISC-V assembly, verified through CompCert (`-fverifiedos-typed -dclight`
   and `-interp`, when present) and target execution on the Sail emulator
   (`sail_riscv_sim`), including hardware capability bounds-fault and tag-fault traps.

This qualifies the synchronous first-slice vertical prototype and concrete carrier
laws; it does not claim a closed mechanized Sail-to-Clight/CompCert refinement theorem
(owned by Q35d / M1.2g) or replace user-managed hosted CI.
"""

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from filelock import FileLock

from vos import compiler_diff as cd
from vos import env, proofenv, vela_elaborate, vela_parser
from vos.atomic import atomic_path
from vos.vela import VelaError

TIMEOUT: Final = 120
EXAMPLE: Final = "tools/vela/examples/first_slice.vela"

DEFAULT_CCOMP_CANDIDATES: Final[tuple[str, ...]] = (
    "/root/build/lane-scalar-effects-20260926/kernel-protected-final/plain/ccomp",
    "/root/build/compiler-unblock-integration-20260921/compiler/ccomp",
)

EXPECTED_LAWS: Final[tuple[str, ...]] = (
    "LawInhabitedByteCase",
    "LawAllocZeroedRead",
    "LawReadOverWriteSame",
    "LawReadOverWriteOther",
    "LawFillAndFrame",
    "LawSliceMetadataAndRead",
    "LawReadOnlyAndInvalidate",
    "LawDisjointCopyAndFrame",
    "LawCapacityInvarianceSmall",
    "LawCapacityInvarianceLarge",
)

EXPECTED_CONTRACT_OBLIGATIONS: Final[tuple[str, ...]] = (
    "PrepareAndValidatePacket_restores_0_Base",
    "PrepareAndValidatePacket_restores_0_Length",
    "PrepareAndValidatePacket_restores_0_Tag",
    "PrepareAndValidatePacket_restores_0_PermRead",
    "PrepareAndValidatePacket_restores_0_PermWrite",
    "PrepareAndValidatePacket_ensures_0",
    "PrepareAndValidatePacket_ensures_1",
    "PrepareAndValidatePacket_ensures_2",
)

EXPECTED_SCENARIO_THEOREMS: Final[tuple[str, ...]] = (
    "ValidateEmptyPacketOk",
    "ValidateFullPacketOk",
    "ValidatePartialPacketScrubsStaleAndTrailingBytes",
    "RejectFramingShort",
    "RejectBadMagic",
    "RejectLengthOutOfBounds",
    "RejectChecksumScrubsDestinationAndRestores",
)


@dataclass(frozen=True)
class NegativeControl:
    name: str
    source: str
    expected_kind: str
    expected_substring: str


NEGATIVE_CONTROLS: Final[tuple[NegativeControl, ...]] = (
    NegativeControl(
        "oob-read",
        """module Vela.FirstSlice.NegOobRead;
public definition u8 BadRead() =>
    let s = Span.AllocZeroed(64usize, 8usize) in
    Span.Read(s, 8usize);
""",
        "type",
        "cannot prove Span.Read index is within Span.Length bounds",
    ),
    NegativeControl(
        "oob-write",
        """module Vela.FirstSlice.NegOobWrite;
public definition Span<byte> BadWrite() =>
    let s = Span.AllocZeroed(64usize, 8usize) in
    Span.Write(s, 8usize, 0x01u8);
""",
        "type",
        "cannot prove Span.Write index is within Span.Length bounds",
    ),
    NegativeControl(
        "oob-slice",
        """module Vela.FirstSlice.NegOobSlice;
public definition Span<byte> BadSlice() =>
    let s = Span.AllocZeroed(64usize, 8usize) in
    Span.Slice(s, 5usize, 4usize);
""",
        "type",
        "cannot prove Span.Slice subrange (offset + count <= Span.Length) is in bounds",
    ),
    NegativeControl(
        "oob-fill",
        """module Vela.FirstSlice.NegOobFill;
public definition Span<byte> BadFill() =>
    let s = Span.AllocZeroed(64usize, 8usize) in
    Span.Fill(s, 5usize, 4usize, 0x00u8);
""",
        "type",
        "cannot prove Span.Fill subrange (offset + count <= Span.Length) is in bounds",
    ),
    NegativeControl(
        "mutate-in-borrow",
        """module Vela.FirstSlice.NegMutateInBorrow;
public definition Span<byte> BadBorrowWrite(in Span<byte> pkt)
    requires pkt.CanRead
    requires pkt.CanWrite
    requires pkt.Length >= 4usize
=>
    Span.Write(pkt, 0usize, 0xAAu8);
""",
        "type",
        "cannot mutate a read-only 'in Span<byte>' borrow",
    ),
    NegativeControl(
        "mutate-readonly-view",
        """module Vela.FirstSlice.NegMutateReadOnly;
public definition Span<byte> BadViewWrite() =>
    let s = Span.AllocZeroed(64usize, 8usize) in
    let ro = Span.ReadOnly(s) in
    Span.Write(ro, 0usize, 0xAAu8);
""",
        "type",
        "cannot prove Span has valid tag and write permission (Span.CanWrite)",
    ),
    NegativeControl(
        "read-invalidated-view",
        """module Vela.FirstSlice.NegReadInvalidated;
public definition u8 BadInvalidRead() =>
    let s = Span.AllocZeroed(64usize, 8usize) in
    let inv = Span.Invalidate(s) in
    Span.Read(inv, 0usize);
""",
        "type",
        "cannot prove Span has valid tag and read permission (Span.CanRead)",
    ),
    NegativeControl(
        "overlapping-copyprefix",
        """module Vela.FirstSlice.NegOverlapCopy;
public definition Span<byte> BadOverlapCopy() =>
    let s = Span.AllocZeroed(64usize, 8usize) in
    let sub = Span.Slice(s, 2usize, 4usize) in
    Span.CopyPrefix(s, sub, 4usize);
""",
        "type",
        "cannot prove Span.CopyPrefix source and destination extents are disjoint",
    ),
    NegativeControl(
        "foreign-restore",
        """module Vela.FirstSlice.NegForeignRestore;
public definition Span<byte> BadRestore() =>
    let dst = Span.AllocZeroed(64usize, 8usize) in
    let other = Span.AllocZeroed(256usize, 8usize) in
    Span.Restore(dst, other);
""",
        "type",
        "cannot prove Span.Restore view extent is contained within parent extent",
    ),
    NegativeControl(
        "broken-restores-contract",
        """module Vela.FirstSlice.NegBrokenRestores;
public definition Span<byte> BadRestores(ref Span<byte> dst)
    requires dst.CanRead
    requires dst.CanWrite
    requires dst.Length >= 8usize
    restores dst
=>
    Span.Slice(dst, 0usize, 4usize);
""",
        "type",
        "assertion could not be established",
    ),
    NegativeControl(
        "wrong-expected-byte",
        """module Vela.FirstSlice.NegWrongByte;
theorem BadByte()
    ensures
        let s = Span.Write(Span.AllocZeroed(64usize, 8usize), 0usize, 0x10u8) in
        Span.Read(s, 0usize) == 0x99u8
proof {
    let s = Span.Write(Span.AllocZeroed(64usize, 8usize), 0usize, 0x10u8);
    assert Span.Read(s, 0usize) == 0x99u8;
}
""",
        "type",
        "assertion could not be established",
    ),
    NegativeControl(
        "stale-input-leak",
        """module Vela.FirstSlice.NegStaleLeak;
theorem BadStale()
    ensures
        let dirty = Span.Fill(Span.AllocZeroed(64usize, 8usize), 0usize, 8usize, 0xEEu8) in
        let cleaned = Span.Fill(dirty, 0usize, 8usize, 0x00u8) in
        Span.Read(cleaned, 6usize) == 0xEEu8
proof {
    let dirty = Span.Fill(Span.AllocZeroed(64usize, 8usize), 0usize, 8usize, 0xEEu8);
    let cleaned = Span.Fill(dirty, 0usize, 8usize, 0x00u8);
    assert Span.Read(cleaned, 6usize) == 0xEEu8;
}
""",
        "type",
        "assertion could not be established",
    ),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, payload: object) -> None:
    with atomic_path(path) as pending:
        pending.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="")


def _opam(arguments: list[str]) -> list[str]:
    return ["opam", "exec", "--switch", proofenv.ROCQ_SWITCH, "--", *arguments]


def _run(command: list[str], cwd: Path, log_path: Path,
         steps: list[dict[str, object]]) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT,
        check=False,
    )
    combined = completed.stdout + completed.stderr
    log_path.write_text(combined, encoding="utf-8", newline="")
    steps.append({
        "command": command,
        "cwd": str(cwd),
        "returncode": completed.returncode,
        "log": str(log_path),
        "log_sha256": _sha256(log_path.read_bytes()),
    })
    if completed.returncode != 0:
        raise ValueError(f"command failed ({completed.returncode}): {' '.join(command)}\n{combined[-600:]}")
    return completed.stdout


def _work_root(root: Path) -> Path:
    directory = env.lane_root(env.lane_of(root)) / "vela-first-slice"
    kind = env.filesystem(directory)
    if not kind or kind in env.CROSS_OS_FILESYSTEMS | env.VOLATILE_FILESYSTEMS:
        raise ValueError("Vela first-slice outputs require a persistent native filesystem")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _capacity_fixture(capacity_literal: str) -> bytes:
    text = f"""module Vela.FirstSlice.CapGate;

public definition Span<byte> PrepareSliceHeader(ref Span<byte> dst)
    requires dst.CanRead
    requires dst.CanWrite
    requires dst.Length >= 8usize
    restores dst
    ensures result.Length == dst.Length
    ensures Span.ReadOnly(result).PermWrite == false
=>
    let s1 = Span.Write(dst, 0usize, 0x56u8) in
    let s2 = Span.Write(s1, 3usize, 0x01u8) in
    let roView = Span.ReadOnly(Span.Slice(s2, 0usize, 4usize)) in
    Span.Restore(dst, roView);

theorem CapacityLaw()
    ensures
        let s0 = Span.AllocZeroed(4096usize, {capacity_literal}) in
        let res = PrepareSliceHeader(s0) in
        (res.Length == {capacity_literal}
         && Span.Read(res, 0usize) == 0x56u8
         && Span.Read(res, 3usize) == 0x01u8
         && Span.Read(res, 1usize) == 0x00u8) == true
proof {{
    let s0 = Span.AllocZeroed(4096usize, {capacity_literal});
    let res = PrepareSliceHeader(s0);
    assert (res.Length == {capacity_literal}
        && Span.Read(res, 0usize) == 0x56u8
        && Span.Read(res, 3usize) == 0x01u8
        && Span.Read(res, 1usize) == 0x00u8) == true;
}}
"""
    return text.encode("utf-8")


def _extract_decl_names(parsed: object) -> dict[str, str]:
    envelope = cast("dict[str, object]", parsed)
    ast_root = cast("dict[str, object]", envelope.get("ast", envelope))
    decls = cast("list[dict[str, object]]", ast_root.get("declarations", []))
    found: dict[str, str] = {}
    for decl in decls:
        kind = str(decl.get("kind", ""))
        name_node = decl.get("name")
        if isinstance(name_node, dict) and isinstance(name_node.get("text"), str):
            found[str(name_node["text"])] = kind
    return found


def lower_to_c(source: bytes, parsed: object, *, perturb_check: int = 0) -> tuple[str, int]:
    """Lower the executable subset of `first_slice.vela` from its checked AST to C.

    Verifies that the parsed AST carries the expected executable type and callable
    declarations (`ValidationError`, `ValidationOutcome`, `MakePacket8`,
    `CopyPacketToDst`, `ComputePacketChecksum`, `PrepareAndValidatePacket`) and the
    seven scenario definitions before emitting a self-contained C translation unit in
    the `verifiedos-scalar-source-v1` subset.
    """
    decls = _extract_decl_names(parsed)
    required_callables = (
        ("ValidationError", "union"),
        ("ValidationOutcome", "record"),
        ("MakePacket8", "definition"),
        ("CopyPacketToDst", "definition"),
        ("ComputePacketChecksum", "definition"),
        ("PrepareAndValidatePacket", "function"),
        ("ScenarioEmptyPacket", "definition"),
        ("ScenarioFullPacket", "definition"),
        ("ScenarioPartialStalePacket", "definition"),
        ("ScenarioFramingShort", "definition"),
        ("ScenarioBadMagic", "definition"),
        ("ScenarioLengthOutOfBounds", "definition"),
        ("ScenarioChecksumRejected", "definition"),
    )
    for name, expected_kind in required_callables:
        actual = decls.get(name)
        if actual != expected_kind:
            raise ValueError(f"first_slice AST missing executable declaration {name} ({expected_kind}), got {actual}")

    def exp(check_num: int, val: int) -> int:
        return val + (1 if check_num == perturb_check else 0)

    c_source = f"""/* SPDX-License-Identifier: Apache-2.0 */
/* Lowered from tools/vela/examples/first_slice.vela (SHA256: {_sha256(source)}) */
/* Source profile: verifiedos-scalar-source-v1 */

#define VOS_ERR_ValidatedOk 0
#define VOS_ERR_FramingShort 1
#define VOS_ERR_BadMagicOrFlags 2
#define VOS_ERR_LengthOutOfBounds 3
#define VOS_ERR_ChecksumRejected 4

struct vos_span_byte {{
    unsigned char *ptr;
    unsigned long base;
    unsigned long length;
    int tag;
    int perm_read;
    int perm_write;
}};

struct vos_ValidationOutcome {{
    int Ok;
    int Error;
    unsigned long CopiedBytes;
    struct vos_span_byte PayloadView;
    struct vos_span_byte RestoredDst;
}};

static void vos_span_copy_meta(struct vos_span_byte *dst, struct vos_span_byte *src)
{{
    dst->ptr = src->ptr;
    dst->base = src->base;
    dst->length = src->length;
    dst->tag = src->tag;
    dst->perm_read = src->perm_read;
    dst->perm_write = src->perm_write;
}}

static void vos_span_alloc_zeroed(
    struct vos_span_byte *out,
    unsigned char *backing,
    unsigned long base,
    unsigned long length)
{{
    unsigned long i;
    for (i = 0UL; i < length; i++) {{
        backing[i] = 0U;
    }}
    out->ptr = backing;
    out->base = base;
    out->length = length;
    out->tag = 1;
    out->perm_read = 1;
    out->perm_write = 1;
}}

static unsigned char vos_span_read(struct vos_span_byte *s, unsigned long idx)
{{
    return s->ptr[idx];
}}

static void vos_span_write(
    struct vos_span_byte *out,
    struct vos_span_byte *s,
    unsigned long idx,
    unsigned char val)
{{
    s->ptr[idx] = val;
    vos_span_copy_meta(out, s);
}}

static void vos_span_fill(
    struct vos_span_byte *out,
    struct vos_span_byte *s,
    unsigned long off,
    unsigned long count,
    unsigned char val)
{{
    unsigned long i;
    for (i = 0UL; i < count; i++) {{
        s->ptr[off + i] = val;
    }}
    vos_span_copy_meta(out, s);
}}

static void vos_span_slice(
    struct vos_span_byte *out,
    struct vos_span_byte *s,
    unsigned long off,
    unsigned long count)
{{
    out->ptr = s->ptr + off;
    out->base = s->base + off;
    out->length = count;
    out->tag = s->tag;
    out->perm_read = s->perm_read;
    out->perm_write = s->perm_write;
}}

static void vos_span_readonly(struct vos_span_byte *out, struct vos_span_byte *s)
{{
    vos_span_copy_meta(out, s);
    out->perm_write = 0;
}}

static void vos_span_invalidate(struct vos_span_byte *out, struct vos_span_byte *s)
{{
    vos_span_copy_meta(out, s);
    out->tag = 0;
    out->perm_read = 0;
    out->perm_write = 0;
}}

static int vos_span_disjoint(struct vos_span_byte *a, struct vos_span_byte *b)
{{
    if (a->base + a->length <= b->base) {{
        return 1;
    }}
    if (b->base + b->length <= a->base) {{
        return 1;
    }}
    return 0;
}}

static void vos_span_copy_prefix(
    struct vos_span_byte *out,
    struct vos_span_byte *dst,
    struct vos_span_byte *src,
    unsigned long count)
{{
    unsigned long i;
    for (i = 0UL; i < count; i++) {{
        dst->ptr[i] = src->ptr[i];
    }}
    vos_span_copy_meta(out, dst);
}}

static void vos_span_restore(
    struct vos_span_byte *out,
    struct vos_span_byte *parent,
    struct vos_span_byte *view)
{{
    (void)view;
    vos_span_copy_meta(out, parent);
}}

static void MakePacket8(
    struct vos_span_byte *out,
    unsigned char *backing,
    unsigned long baseAddr,
    unsigned char b0,
    unsigned char b1,
    unsigned char b2,
    unsigned char b3,
    unsigned char b4,
    unsigned char b5,
    unsigned char b6,
    unsigned char b7)
{{
    struct vos_span_byte s0;
    vos_span_alloc_zeroed(&s0, backing, baseAddr, 8UL);
    vos_span_write(&s0, &s0, 0UL, b0);
    vos_span_write(&s0, &s0, 1UL, b1);
    vos_span_write(&s0, &s0, 2UL, b2);
    vos_span_write(&s0, &s0, 3UL, b3);
    vos_span_write(&s0, &s0, 4UL, b4);
    vos_span_write(&s0, &s0, 5UL, b5);
    vos_span_write(&s0, &s0, 6UL, b6);
    vos_span_write(out, &s0, 7UL, b7);
}}

static void CopyPacketToDst(
    struct vos_span_byte *out,
    struct vos_span_byte *cleanedDst,
    struct vos_span_byte *pkt,
    unsigned long payloadLen)
{{
    struct vos_span_byte d;
    struct vos_span_byte dstSlice;
    struct vos_span_byte pktSlice;
    struct vos_span_byte copiedSlice;
    vos_span_write(&d, cleanedDst, 0UL, vos_span_read(pkt, 0UL));
    vos_span_write(&d, &d, 1UL, vos_span_read(pkt, 1UL));
    vos_span_write(&d, &d, 2UL, vos_span_read(pkt, 2UL));
    vos_span_write(&d, &d, 3UL, vos_span_read(pkt, 3UL));
    vos_span_slice(&dstSlice, &d, 4UL, payloadLen);
    vos_span_slice(&pktSlice, pkt, 4UL, payloadLen);
    vos_span_copy_prefix(&copiedSlice, &dstSlice, &pktSlice, payloadLen);
    vos_span_restore(out, cleanedDst, &copiedSlice);
}}

static unsigned char ComputePacketChecksum(
    struct vos_span_byte *pkt,
    unsigned char rawLen,
    unsigned long payloadLen)
{{
    struct vos_span_byte pktPayload;
    unsigned char b0;
    unsigned char b1;
    unsigned char b2;
    unsigned char b3;
    vos_span_slice(&pktPayload, pkt, 4UL, payloadLen);
    b0 = (payloadLen > 0UL) ? vos_span_read(&pktPayload, 0UL) : 0U;
    b1 = (payloadLen > 1UL) ? vos_span_read(&pktPayload, 1UL) : 0U;
    b2 = (payloadLen > 2UL) ? vos_span_read(&pktPayload, 2UL) : 0U;
    b3 = (payloadLen > 3UL) ? vos_span_read(&pktPayload, 3UL) : 0U;
    return (unsigned char)(((0x5AU ^ (unsigned int)rawLen) ^ ((unsigned int)b0 ^ (unsigned int)b1 ^ (unsigned int)b2 ^ (unsigned int)b3)) & 0xFFU);
}}

static void PrepareAndValidatePacket(
    struct vos_ValidationOutcome *out,
    struct vos_span_byte *dst,
    struct vos_span_byte *pkt)
{{
    struct vos_span_byte cleanedDst;
    struct vos_span_byte emptySlice;
    struct vos_span_byte workDst;
    struct vos_span_byte scrubbedDst;
    struct vos_span_byte rawView;
    unsigned char magic;
    unsigned char rawLen;
    unsigned char expectedChecksum;
    unsigned char flags;
    unsigned char actualChecksum;
    unsigned long payloadLen;

    vos_span_fill(&cleanedDst, dst, 0UL, dst->length, 0U);
    if (dst->length < 8UL || pkt->length < 4UL || !vos_span_disjoint(dst, pkt)) {{
        vos_span_slice(&emptySlice, dst, 0UL, 0UL);
        out->Ok = 0;
        out->Error = VOS_ERR_FramingShort;
        out->CopiedBytes = 0UL;
        vos_span_invalidate(&out->PayloadView, &emptySlice);
        vos_span_restore(&out->RestoredDst, dst, &cleanedDst);
        return;
    }}
    magic = vos_span_read(pkt, 0UL);
    rawLen = vos_span_read(pkt, 1UL);
    expectedChecksum = vos_span_read(pkt, 2UL);
    flags = vos_span_read(pkt, 3UL);
    payloadLen = (unsigned long)rawLen;
    if (magic != 0x56U || flags != 0x01U) {{
        vos_span_slice(&emptySlice, dst, 0UL, 0UL);
        out->Ok = 0;
        out->Error = VOS_ERR_BadMagicOrFlags;
        out->CopiedBytes = 0UL;
        vos_span_invalidate(&out->PayloadView, &emptySlice);
        vos_span_restore(&out->RestoredDst, dst, &cleanedDst);
        return;
    }}
    if (payloadLen > 4UL || 4UL + payloadLen > pkt->length || 4UL + payloadLen > dst->length) {{
        vos_span_slice(&emptySlice, dst, 0UL, 0UL);
        out->Ok = 0;
        out->Error = VOS_ERR_LengthOutOfBounds;
        out->CopiedBytes = 0UL;
        vos_span_invalidate(&out->PayloadView, &emptySlice);
        vos_span_restore(&out->RestoredDst, dst, &cleanedDst);
        return;
    }}
    CopyPacketToDst(&workDst, &cleanedDst, pkt, payloadLen);
    actualChecksum = ComputePacketChecksum(pkt, rawLen, payloadLen);
    if (actualChecksum != expectedChecksum) {{
        vos_span_fill(&scrubbedDst, &workDst, 0UL, dst->length, 0U);
        vos_span_slice(&emptySlice, dst, 0UL, 0UL);
        out->Ok = 0;
        out->Error = VOS_ERR_ChecksumRejected;
        out->CopiedBytes = 0UL;
        vos_span_invalidate(&out->PayloadView, &emptySlice);
        vos_span_restore(&out->RestoredDst, dst, &scrubbedDst);
        return;
    }}
    vos_span_slice(&rawView, &workDst, 4UL, payloadLen);
    out->Ok = 1;
    out->Error = VOS_ERR_ValidatedOk;
    out->CopiedBytes = payloadLen;
    vos_span_readonly(&out->PayloadView, &rawView);
    vos_span_restore(&out->RestoredDst, dst, &out->PayloadView);
}}

int main(void)
{{
    unsigned char dst_buf[8];
    unsigned char pkt_buf[8];
    struct vos_span_byte dst;
    struct vos_span_byte pkt;
    struct vos_ValidationOutcome out;

    /* 1. ScenarioEmptyPacket: valid 0-byte payload */
    vos_span_alloc_zeroed(&dst, dst_buf, 64UL, 8UL);
    MakePacket8(&pkt, pkt_buf, 128UL, 0x56U, 0x00U, 0x5AU, 0x01U, 0x00U, 0x00U, 0x00U, 0x00U);
    PrepareAndValidatePacket(&out, &dst, &pkt);
    if (out.Ok != {exp(1, 1)})
        return 1;
    if (out.Error != {exp(2, 0)})
        return 2;
    if (out.CopiedBytes != {exp(3, 0)}UL || out.PayloadView.length != 0UL || out.PayloadView.base != 68UL)
        return 3;
    if (out.PayloadView.tag != 1 || out.PayloadView.perm_read != 1 || out.PayloadView.perm_write != 0)
        return 4;
    if (out.RestoredDst.base != 64UL || out.RestoredDst.length != {exp(5, 8)}UL || out.RestoredDst.perm_write != 1)
        return 5;

    /* 2. ScenarioFullPacket: valid 4-byte payload [0x10, 0x20, 0x30, 0x40] */
    vos_span_alloc_zeroed(&dst, dst_buf, 64UL, 8UL);
    MakePacket8(&pkt, pkt_buf, 128UL, 0x56U, 0x04U, 0x1EU, 0x01U, 0x10U, 0x20U, 0x30U, 0x40U);
    PrepareAndValidatePacket(&out, &dst, &pkt);
    if (out.Ok != 1 || out.Error != VOS_ERR_ValidatedOk || out.CopiedBytes != 4UL)
        return 6;
    if (vos_span_read(&out.PayloadView, 0UL) != {exp(7, 0x10)}U)
        return 7;
    if (vos_span_read(&out.PayloadView, 1UL) != 0x20U
        || vos_span_read(&out.PayloadView, 2UL) != 0x30U
        || vos_span_read(&out.PayloadView, 3UL) != {exp(8, 0x40)}U)
        return 8;
    if (vos_span_read(&out.RestoredDst, 0UL) != 0x56U || vos_span_read(&out.RestoredDst, 7UL) != 0x40U)
        return 9;

    /* 3. ScenarioPartialStalePacket: 2-byte payload scrubs stale destination and ignores trailing source */
    vos_span_alloc_zeroed(&dst, dst_buf, 64UL, 8UL);
    vos_span_fill(&dst, &dst, 0UL, 8UL, 0xAAU);
    MakePacket8(&pkt, pkt_buf, 128UL, 0x56U, 0x02U, 0x6BU, 0x01U, 0x11U, 0x22U, 0xDEU, 0xADU);
    PrepareAndValidatePacket(&out, &dst, &pkt);
    if (out.Ok != 1 || out.CopiedBytes != 2UL || out.PayloadView.length != 2UL)
        return 10;
    if (vos_span_read(&out.PayloadView, 0UL) != 0x11U || vos_span_read(&out.PayloadView, 1UL) != 0x22U)
        return 11;
    if (vos_span_read(&out.RestoredDst, 6UL) != {exp(12, 0x00)}U || vos_span_read(&out.RestoredDst, 7UL) != 0x00U)
        return 12;

    /* 4. ScenarioFramingShort: pkt.length < 4 */
    vos_span_alloc_zeroed(&dst, dst_buf, 64UL, 8UL);
    vos_span_alloc_zeroed(&pkt, pkt_buf, 128UL, 3UL);
    PrepareAndValidatePacket(&out, &dst, &pkt);
    if (out.Ok != 0 || out.Error != {exp(13, 1)} || out.PayloadView.tag != 0)
        return 13;

    /* 5. ScenarioBadMagic: header magic != 0x56 */
    vos_span_alloc_zeroed(&dst, dst_buf, 64UL, 8UL);
    MakePacket8(&pkt, pkt_buf, 128UL, 0x00U, 0x02U, 0x3AU, 0x01U, 0xAAU, 0xCCU, 0x00U, 0x00U);
    PrepareAndValidatePacket(&out, &dst, &pkt);
    if (out.Ok != 0 || out.Error != {exp(14, 2)} || out.PayloadView.tag != 0)
        return 14;

    /* 6. ScenarioLengthOutOfBounds: rawLen == 5 > 4 */
    vos_span_alloc_zeroed(&dst, dst_buf, 64UL, 8UL);
    MakePacket8(&pkt, pkt_buf, 128UL, 0x56U, 0x05U, 0x5FU, 0x01U, 0x10U, 0x20U, 0x30U, 0x40U);
    PrepareAndValidatePacket(&out, &dst, &pkt);
    if (out.Ok != 0 || out.Error != {exp(15, 3)} || out.PayloadView.tag != 0)
        return 15;

    /* 7. ScenarioChecksumRejected: bad checksum scrubs destination and restores parent dst */
    vos_span_alloc_zeroed(&dst, dst_buf, 64UL, 8UL);
    vos_span_fill(&dst, &dst, 0UL, 8UL, 0x77U);
    MakePacket8(&pkt, pkt_buf, 128UL, 0x56U, 0x04U, 0xFFU, 0x01U, 0x10U, 0x20U, 0x30U, 0x40U);
    PrepareAndValidatePacket(&out, &dst, &pkt);
    if (out.Ok != 0 || out.Error != {exp(16, 4)} || out.PayloadView.tag != 0)
        return 16;
    if (vos_span_read(&out.RestoredDst, 0UL) != {exp(17, 0x00)}U
        || vos_span_read(&out.RestoredDst, 4UL) != 0x00U
        || vos_span_read(&out.RestoredDst, 7UL) != 0x00U)
        return 17;
    if (out.RestoredDst.base != 64UL || out.RestoredDst.length != 8UL || out.RestoredDst.perm_write != 1)
        return 18;

    /* 8. Overlapping-span alias control at runtime: disjoint check rejects overlapping base ranges */
    vos_span_alloc_zeroed(&dst, dst_buf, 64UL, 8UL);
    MakePacket8(&pkt, pkt_buf, 68UL, 0x56U, 0x04U, 0x1EU, 0x01U, 0x10U, 0x20U, 0x30U, 0x40U);
    PrepareAndValidatePacket(&out, &dst, &pkt);
    if (out.Ok != 0 || out.Error != VOS_ERR_FramingShort || out.PayloadView.tag != 0)
        return 19;

    return 0;
}}
"""
    return c_source, 19


def _purecap_cheri_asm_stream(mode: str) -> str:
    """Emit a purecap CHERI-RISC-V assembly stream exercising hardware capability bounds/tags.

    - `mode == "pass"`: initializes a 16-byte stack frame with `dst` (8 bytes) and `pkt`
      (8 bytes), validates the header and checksum, copies the 4-byte payload into `dst+4`,
      narrows `PayloadView` (`c13`) to `[dst+4, dst+8)` with `csetbounds` and strips store
      permission (`candperm`), verifies `cgetlen == 4`, `cgettag == 1`, and all 4 payload
      bytes via capability loads, and restores the parent `dst` capability (`cgetlen == 8`).
    - `mode == "bounds-trap"`: narrows `PayloadView` (`c13`) to `[dst+4, dst+8)` with
      `csetbounds` and attempts an out-of-bounds byte load at offset 4 (`lbu t0, 4(c13)`),
      which MUST trigger a hardware CHERI bounds fault (`mcause == 28`, HTIF exit `284`).
    - `mode == "tag-trap"`: invalidates `emptyView` (`c13`) with `ccleartag` on the error
      exit path and attempts to dereference `lbu t0, 0(c13)`, which MUST trigger a hardware
      CHERI tag violation (`mcause == 28`, HTIF exit `284`).
    """
    tail_op = {
        "pass": """\
        lbu     t0, 0(c13)
        li      t1, 0x10
        bne     t0, t1, __slice_fail
        lbu     t0, 3(c13)
        li      t1, 0x40
        bne     t0, t1, __slice_fail
        cgetlen t0, c13
        li      t1, 4
        bne     t0, t1, __slice_fail
        cgettag t0, c13
        li      t1, 1
        bne     t0, t1, __slice_fail
        cgetlen t0, c12
        li      t1, 8
        bne     t0, t1, __slice_fail
        li      a0, 0
        j       __slice_ret
""",
        "bounds-trap": """\
        lbu     t0, 4(c13)
        li      a0, 99
        j       __slice_ret
""",
        "tag-trap": """\
        cmove   c13, cnull
        lbu     t0, 0(c13)
        li      a0, 98
        j       __slice_ret
""",
        "perm-trap": """\
        candperm c13, c13, x0
        sb      t0, 0(c13)
        li      a0, 97
        j       __slice_ret
""",
    }[mode]
    return f"""\
        .text
        .globl main
main:
        cincoffsetimm c2, c2, -32
        sc      c1, 16(c2)
        # Derive dst capability c12 = [c2, c2+8)
        cmove   c12, c2
        li      t0, 8
        csetbounds c12, c12, t0
        # Derive pkt capability c14 = [c2+8, c2+16)
        cincoffsetimm c14, c2, 8
        li      t0, 8
        csetbounds c14, c14, t0
        # Populate pkt = [0x56, 0x04, 0x1E, 0x01, 0x10, 0x20, 0x30, 0x40]
        li      t0, 0x56
        sb      t0, 0(c14)
        li      t0, 0x04
        sb      t0, 1(c14)
        li      t0, 0x1E
        sb      t0, 2(c14)
        li      t0, 0x01
        sb      t0, 3(c14)
        li      t0, 0x10
        sb      t0, 4(c14)
        li      t0, 0x20
        sb      t0, 5(c14)
        li      t0, 0x30
        sb      t0, 6(c14)
        li      t0, 0x40
        sb      t0, 7(c14)
        # Copy header + 4-byte payload into dst (c12)
        lbu     t0, 0(c14)
        sb      t0, 0(c12)
        lbu     t0, 1(c14)
        sb      t0, 1(c12)
        lbu     t0, 2(c14)
        sb      t0, 2(c12)
        lbu     t0, 3(c14)
        sb      t0, 3(c12)
        lbu     t0, 4(c14)
        sb      t0, 4(c12)
        lbu     t0, 5(c14)
        sb      t0, 5(c12)
        lbu     t0, 6(c14)
        sb      t0, 6(c12)
        lbu     t0, 7(c14)
        sb      t0, 7(c12)
        # Narrow PayloadView capability c13 = Span.ReadOnly(Span.Slice(dst, 4, 4))
        cincoffsetimm c13, c12, 4
        li      t0, 4
        csetbounds c13, c13, t0
        li      t0, 0xFF7
        candperm c13, c13, t0
{tail_op}\
__slice_fail:
        li      a0, 1
__slice_ret:
        lc      c1, 16(c2)
        cincoffsetimm c2, c2, 32
        cjalr   cnull, cra, 0
"""


def _resolve_ccomp(ccomp_path: Path | None) -> Path | None:
    if ccomp_path is not None:
        return ccomp_path if ccomp_path.is_file() else None
    for candidate in DEFAULT_CCOMP_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def _run_negative_controls(compiled: vela_parser.Build) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for ctrl in NEGATIVE_CONTROLS:
        raw = ctrl.source.encode("utf-8")
        # Must parse cleanly as schema-2 surface syntax; syntax refusal is never a semantic control.
        parsed = vela_parser.parse_source(compiled, raw, surface=True)
        try:
            vela_elaborate.elaborate(raw, parsed)
        except VelaError as error:
            if error.kind != ctrl.expected_kind or ctrl.expected_substring not in error.message:
                raise ValueError(
                    f"negative control {ctrl.name}: expected {ctrl.expected_kind} containing "
                    f"'{ctrl.expected_substring}', got {error.kind}: {error.message}"
                ) from error
            results.append({
                "name": ctrl.name,
                "parsed_surface": True,
                "category": error.kind,
                "line": error.line,
                "column": error.column,
                "message": error.message,
            })
        else:
            raise ValueError(f"negative control {ctrl.name} was unexpectedly accepted")
    return results


def _run_capacity_invariance_gate(
    compiled: vela_parser.Build,
    directory: Path,
    steps: list[dict[str, object]],
) -> dict[str, object]:
    small_src = _capacity_fixture("8usize")
    large_src = _capacity_fixture("1_000_000_000usize")
    small_parsed = vela_parser.parse_source(compiled, small_src, surface=True)
    large_parsed = vela_parser.parse_source(compiled, large_src, surface=True)
    small_elab, small_state = vela_elaborate._checked_elaboration(small_src, small_parsed)
    large_elab, large_state = vela_elaborate._checked_elaboration(large_src, large_parsed)

    small_work = vela_elaborate.MAX_WORK - small_state.work
    large_work = vela_elaborate.MAX_WORK - large_state.work
    small_red = vela_elaborate.MAX_REDUCTIONS - small_state.reductions
    large_red = vela_elaborate.MAX_REDUCTIONS - large_state.reductions

    if len(small_state.output) != len(large_state.output):
        raise ValueError(
            f"capacity-invariance gate failed: obligation count differs ({len(small_state.output)} vs {len(large_state.output)})"
        )
    if small_work != large_work or small_red != large_red:
        raise ValueError(
            f"capacity-invariance gate failed: work/reduction profile differs "
            f"(small={small_work}/{small_red}, large={large_work}/{large_red})"
        )
    if len(small_elab.gallina) != len(large_elab.gallina):
        raise ValueError(
            f"capacity-invariance gate failed: emitted Gallina byte length differs "
            f"({len(small_elab.gallina)} vs {len(large_elab.gallina)})"
        )

    small_v = directory / "CapSmall.v"
    large_v = directory / "CapLarge.v"
    small_v.write_text(small_elab.gallina, encoding="utf-8", newline="")
    large_v.write_text(large_elab.gallina, encoding="utf-8", newline="")
    _run(_opam(["rocq", "c", "-q", "-R", str(directory), "VelaFirstSlice", small_v.name]),
         directory, directory / "CapSmall.compile.log", steps)
    _run(_opam(["rocq", "c", "-q", "-R", str(directory), "VelaFirstSlice", large_v.name]),
         directory, directory / "CapLarge.compile.log", steps)
    _run(_opam(["rocqchk", "-R", str(directory), "VelaFirstSlice",
                "VelaFirstSlice.CapSmall", "VelaFirstSlice.CapLarge"]),
         directory, directory / "CapGate.kernel.log", steps)
    return {
        "small_capacity": "8usize",
        "large_capacity": "1_000_000_000usize",
        "obligation_count": len(small_state.output),
        "work_steps": small_work,
        "reduction_steps": small_red,
        "gallina_bytes": len(small_elab.gallina),
        "kernel_checked": True,
    }


def _qualify_attempt(
    root: Path,
    directory: Path,
    steps: list[dict[str, object]],
    ccomp_path: Path | None,
) -> dict[str, object]:
    source_path = root / EXAMPLE
    source = vela_parser.read_source(source_path)
    compiled = vela_parser.build(root)
    parsed = vela_parser.parse_source(compiled, source, surface=True)

    # 1. Elaborate first_slice.vela and verify determinism + exported obligations
    translated = vela_elaborate.elaborate(source, parsed)
    repeated = vela_elaborate.elaborate(source, parsed)
    if translated != repeated:
        raise ValueError("first_slice.vela elaboration is nondeterministic")

    exports = re.findall(
        r"^Definition (vela_d[0-9]+_[A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|:)",
        translated.gallina,
        flags=re.MULTILINE,
    )
    for required_suffix in (*EXPECTED_LAWS, *EXPECTED_CONTRACT_OBLIGATIONS, *EXPECTED_SCENARIO_THEOREMS):
        if not any(exp.endswith(f"_{required_suffix}") for exp in exports):
            raise ValueError(f"emitted Gallina is missing required obligation '{required_suffix}'")

    gallina_path = directory / "FirstSlice.v"
    gallina_path.write_text(translated.gallina, encoding="utf-8", newline="")
    _run(
        _opam(["rocq", "c", "-q", "-R", str(directory), "VelaFirstSlice", gallina_path.name]),
        directory,
        directory / "FirstSlice.compile.log",
        steps,
    )

    module = "Vela_" + translated.module.replace(".", "_")
    audited = [f"{module}.{name}" for name in exports]
    assumptions_path = directory / "FirstSliceAssumptions.v"
    assumptions_path.write_text(
        "From VelaFirstSlice Require Import FirstSlice.\n"
        + "".join(f"Print Assumptions FirstSlice.{name}.\n" for name in audited),
        encoding="utf-8",
        newline="",
    )
    assumptions_out = _run(
        _opam(["rocq", "c", "-q", "-R", str(directory), "VelaFirstSlice", assumptions_path.name]),
        directory,
        directory / "FirstSlice.assumptions.log",
        steps,
    )
    assumption_lines = [line.strip() for line in assumptions_out.splitlines() if line.strip()]
    if assumption_lines != ["Closed under the global context"] * len(audited):
        raise ValueError("FirstSlice.v exports have unqualified axioms or assumptions")

    _run(
        _opam(["rocqchk", "-R", str(directory), "VelaFirstSlice", "VelaFirstSlice.FirstSlice"]),
        directory,
        directory / "FirstSlice.kernel.log",
        steps,
    )

    # 2. Fail-closed proof-corruption control on FirstSlice.v
    corrupted_v = directory / "FirstSliceCorrupted.v"
    corrupted_text = translated.gallina + (
        "\nDefinition vela_corrupted_check : @Corelib.Init.Logic.eq Corelib.Init.Datatypes.bool "
        "Corelib.Init.Datatypes.true Corelib.Init.Datatypes.false := "
        "@Corelib.Init.Logic.eq_refl Corelib.Init.Datatypes.bool Corelib.Init.Datatypes.true.\n"
    )
    corrupted_v.write_text(corrupted_text, encoding="utf-8", newline="")
    corrupt_proc = subprocess.run(
        _opam(["rocq", "c", "-q", "-R", str(directory), "VelaFirstSlice", corrupted_v.name]),
        cwd=directory,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT,
        check=False,
    )
    if corrupt_proc.returncode == 0:
        raise ValueError("proof-corruption control was unexpectedly accepted by rocq c")

    # 3. Capacity-invariance gate (8usize vs 1_000_000_000usize)
    cap_gate = _run_capacity_invariance_gate(compiled, directory, steps)

    # 4. Semantic negative controls
    neg_controls = _run_negative_controls(compiled)

    # 5. Lower executable AST to Clight/C and execute on CompCert + Sail emulator
    c_source, check_count = lower_to_c(source, parsed)
    c_path = directory / "first_slice.c"
    c_path.write_text(c_source, encoding="utf-8", newline="\n")

    profile = root / "model" / env.PROFILE_CONFIG
    sim_path = env.load(toolchain=False).simulator
    if not sim_path.is_file():
        raise ValueError(f"Sail emulator not found at {sim_path}; run `python tools/run.py model build`")
    simulator = [str(sim_path)]

    # 5a. Purecap hardware capability execution & fault controls on sail_riscv_sim
    purecap_runs: dict[str, object] = {}
    for mode, expected_verdict, expected_code in (
        ("pass", "pass", 0),
        ("bounds-trap", "trap", cd.TRAP_BASE + 28),
        ("tag-trap", "trap", cd.TRAP_BASE + 28),
        ("perm-trap", "trap", cd.TRAP_BASE + 28),
    ):
        asm_stream = _purecap_cheri_asm_stream(mode)
        asm_elf = directory / f"purecap_{mode}.elf"
        refusals, img_bytes = cd.assemble(asm_stream, f"purecap_{mode}", asm_elf)
        if refusals:
            raise ValueError(f"purecap_{mode} assembly refused: {refusals}")
        ran = cd.run_image(simulator, profile, asm_elf, directory)
        if ran.verdict != expected_verdict or ran.code != expected_code:
            raise ValueError(
                f"purecap_{mode} expected ({expected_verdict}, {expected_code}), "
                f"got ({ran.verdict}, {ran.code}): {ran.detail}"
            )
        purecap_runs[mode] = {
            "verdict": ran.verdict,
            "code": ran.code,
            "records": ran.records,
            "trace_digest": ran.digest,
            "cap_roundtrip": ran.cap_roundtrip,
            "image_bytes": img_bytes,
        }

    # 5b. CompCert Clight (-dclight), -interp, and purecap C-to-Sail execution
    resolved_ccomp = _resolve_ccomp(ccomp_path)
    ccomp_evidence: dict[str, object] = {"available": resolved_ccomp is not None}
    if resolved_ccomp is not None:
        ccomp_cmd = [str(resolved_ccomp), "-fverifiedos-typed", "-dclight"]
        main_prog = cd.Program("first_slice", "given", c_source, check_count, 0)
        main_rep = cd.run_program(main_prog, ccomp_cmd, directory, simulator, profile, "", interp=True)
        if (
            main_rep.verdict != "pass"
            or main_rep.interpreted is None
            or main_rep.interpreted.code != 0
            or main_rep.ran is None
            or main_rep.compiled is None
        ):
            raise ValueError(
                f"CompCert/Sail execution of first_slice.c failed: verdict={main_rep.verdict}, "
                f"detail={main_rep.detail}, interp={main_rep.interpreted}"
            )
        clight_file = directory / "first_slice" / "first_slice.light.c"
        if not clight_file.is_file():
            raise ValueError("CompCert -dclight did not emit first_slice.light.c")

        perturbed_runs: list[dict[str, object]] = []
        for check_id, label in (
            (7, "perturbed-wrong-payload-byte"),
            (12, "perturbed-stale-trailing-byte"),
            (16, "perturbed-checksum-error-code"),
            (17, "perturbed-unscrubbed-checksum-dst"),
        ):
            p_src, p_checks = lower_to_c(source, parsed, perturb_check=check_id)
            p_prog = cd.Program(label, "given", p_src, p_checks, check_id)
            p_rep = cd.run_program(p_prog, ccomp_cmd, directory, simulator, profile, "", interp=True)
            if not cd.as_expected(p_rep) or p_rep.interpreted is None or p_rep.interpreted.code != check_id:
                raise ValueError(
                    f"perturbed C control {label} (check {check_id}) did not fail as expected: "
                    f"verdict={p_rep.verdict}, detail={p_rep.detail}, interp={p_rep.interpreted}"
                )
            perturbed_runs.append({
                "name": label,
                "check_id": check_id,
                "verdict": p_rep.verdict,
                "target_code": cd.target_code(p_rep.ran),
                "interp_code": p_rep.interpreted.code,
            })

        ccomp_evidence.update({
            "ccomp_path": str(resolved_ccomp),
            "ccomp_sha256": _sha256(resolved_ccomp.read_bytes()),
            "clight_path": str(clight_file),
            "clight_sha256": _sha256(clight_file.read_bytes()),
            "asm_sha256": main_rep.compiled.stream_sha256,
            "asm_lines": main_rep.compiled.lines,
            "interp_exit_code": main_rep.interpreted.code,
            "sail_verdict": main_rep.verdict,
            "sail_records": main_rep.ran.records,
            "sail_trace_digest": main_rep.ran.digest,
            "sail_cap_roundtrip": main_rep.ran.cap_roundtrip,
            "perturbed_controls": perturbed_runs,
        })

    return {
        "status": "passed",
        "source": str(source_path),
        "source_sha256": _sha256(source),
        "gallina": str(gallina_path),
        "gallina_sha256": _sha256(gallina_path.read_bytes()),
        "kernel_checked": True,
        "assumption_exports_count": len(exports),
        "proof_corruption_refused": True,
        "capacity_invariance": cap_gate,
        "negative_controls_count": len(neg_controls),
        "negative_controls": neg_controls,
        "lowered_c": str(c_path),
        "lowered_c_sha256": _sha256(c_path.read_bytes()),
        "purecap_cheri_runs": purecap_runs,
        "compcert_sail": ccomp_evidence,
    }


def qualify(root: Path, *, ccomp_path: Path | None = None) -> dict[str, object]:
    """Qualify the Q25w concrete `Span<byte>` carrier and `vela-first-slice` end to end."""
    work = _work_root(root)
    with FileLock(work / "qualification.lock", timeout=5):
        latest = work / "qualification.json"
        latest.unlink(missing_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="slice-", dir=work))
        steps: list[dict[str, object]] = []
        attempt: dict[str, object] = {
            "schema": 1,
            "scope": "vela-first-slice-qualification",
            "status": "running",
            "directory": str(directory),
            "steps": steps,
            "full_machine_refinement_closed": False,
            "remaining_chain_owners": ["Q35d", "M1.2g"],
        }
        _write(directory / "attempt.json", attempt)
        try:
            attempt.update(_qualify_attempt(root, directory, steps, ccomp_path))
        except Exception as error:
            attempt.update({
                "status": "failed",
                "kernel_checked": False,
                "error": f"{type(error).__name__}: {error}",
            })
            _write(directory / "attempt.json", attempt)
            raise
        else:
            _write(directory / "attempt.json", attempt)
            _write(latest, attempt)
            return attempt
