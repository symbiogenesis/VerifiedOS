# SPDX-License-Identifier: Apache-2.0
"""Python reference oracle, proof-surface audit, and C17 ASan/UBSan + mutation controls for `checkpoint/`."""

import hashlib
import hmac
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv
from vos.proofs import strip_comments

INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]
CP_DIR = ROOT / "checkpoint"
CP_H = CP_DIR / "include" / "vos_checkpoint.h"
CP_C = CP_DIR / "src" / "checkpoint.c"
CP_TEST_C = CP_DIR / "test" / "test_checkpoint.c"
CP_README = CP_DIR / "README.md"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PROOFS_V = ROOT / "proofs" / "SemanticCheckpoint.v"

MAGIC = b"VOSSEM01"
WIRE_VERSION = 1
SCHEMA_VERSION = 1
APP_EDITOR = 1
APP_PAINTER = 2
PAYLOAD_SEMANTIC = 1
PAYLOAD_RAW_HEAP = 2
PAYLOAD_EXECUTABLE = 3
PAYLOAD_SESSION_KEY = 4

MAX_TEXT_BYTES = 256
MAX_UNDO = 16
MAX_TILES = 16
MAX_IMAGE_HISTORY = 16
MAX_WIRE_BYTES = 56 + 1056 + 32

REQUIRED_CITED_REQS = frozenset(
    {
        "R-05-163",
        "R-05-164",
        "R-05-165",
        "R-05-166",
        "R-08-006",
        "R-08-007a",
        "R-08-015a",
        "R-11-018",
        "R-11-018a",
        "R-14-011a",
        "R-14-011b",
    }
)


@dataclass(frozen=True)
class _UndoEntry:
    op_kind: int
    offset: int
    prev_cursor: int
    old_byte: int
    new_byte: int


@dataclass(frozen=True)
class _EditorDoc:
    text: bytes
    cursor: int
    undo: tuple[_UndoEntry, ...]
    dirty: bool


@dataclass(frozen=True)
class _WireMeta:
    app_id: int
    payload_kind: int
    schema_version: int
    generation: int
    confidentiality_label: int
    security_critical: int
    fresh_epoch: int
    forbidden_flags: int


def _encode_editor_wire(meta: _WireMeta, doc: _EditorDoc, auth_key: bytes) -> bytes:
    ensure(meta.app_id == APP_EDITOR, "editor app id required")
    ensure(meta.payload_kind == PAYLOAD_SEMANTIC, "non-semantic payload rejected")
    ensure(meta.forbidden_flags == 0, "forbidden authority flags rejected")
    ensure(meta.schema_version == SCHEMA_VERSION and meta.generation > 0, "invalid schema/gen")
    ensure(len(doc.text) <= MAX_TEXT_BYTES and doc.cursor <= len(doc.text), "invalid editor bounds")
    ensure(len(doc.undo) <= MAX_UNDO, "invalid undo count")

    payload = bytearray(
        struct.pack("<IIII", len(doc.text), doc.cursor, len(doc.undo), 1 if doc.dirty else 0)
    )
    payload.extend(doc.text)
    for entry in doc.undo:
        payload.extend(
            struct.pack(
                "<IIIBBBB",
                entry.op_kind,
                entry.offset,
                entry.prev_cursor,
                entry.old_byte,
                entry.new_byte,
                0,
                0,
            )
        )
    header = struct.pack(
        "<8sIIIIQIIQII",
        MAGIC,
        WIRE_VERSION,
        meta.app_id,
        meta.payload_kind,
        meta.schema_version,
        meta.generation,
        meta.confidentiality_label,
        meta.security_critical,
        meta.fresh_epoch,
        meta.forbidden_flags,
        len(payload),
    )
    body = header + bytes(payload)
    mac = hmac.new(auth_key, body, hashlib.sha256).digest()
    return body + mac


def _decode_editor_wire(
    wire: bytes, auth_key: bytes, expected_label: int
) -> tuple[str, tuple[_WireMeta, _EditorDoc] | None]:
    if len(wire) < 56 + 32 or len(wire) > MAX_WIRE_BYTES:
        return "bad_format", None
    (
        magic,
        version,
        app_id,
        payload_kind,
        schema_version,
        generation,
        label,
        sec_crit,
        fresh_epoch,
        forbidden_flags,
        payload_len,
    ) = struct.unpack("<8sIIIIQIIQII", wire[:56])
    if (
        magic != MAGIC
        or version != WIRE_VERSION
        or app_id != APP_EDITOR
        or schema_version != SCHEMA_VERSION
        or generation == 0
        or label != expected_label
    ):
        return "bad_format", None
    if payload_kind != PAYLOAD_SEMANTIC:
        return "non_semantic", None
    if forbidden_flags != 0:
        return "forbidden_authority", None
    if sec_crit != 0 and fresh_epoch == 0:
        return "fresh_failed", None
    if len(wire) != 56 + payload_len + 32:
        return "trailing_bytes", None

    expected_mac = hmac.new(auth_key, wire[: 56 + payload_len], hashlib.sha256).digest()
    if not hmac.compare_digest(expected_mac, wire[56 + payload_len :]):
        return "auth_failed", None
    if payload_len < 16:
        return "bad_format", None

    text_len, cursor, undo_count, dirty = struct.unpack("<IIII", wire[56:72])
    if (
        text_len > MAX_TEXT_BYTES
        or cursor > text_len
        or undo_count > MAX_UNDO
        or payload_len != 16 + text_len + 16 * undo_count
    ):
        return "bad_format", None
    text = wire[72 : 72 + text_len]
    undo: list[_UndoEntry] = []
    at = 72 + text_len
    for _ in range(undo_count):
        op_kind, offset, prev_cursor, old_b, new_b, _r0, _r1 = struct.unpack(
            "<IIIBBBB", wire[at : at + 16]
        )
        undo.append(_UndoEntry(op_kind, offset, prev_cursor, old_b, new_b))
        at += 16
    meta = _WireMeta(
        app_id=app_id,
        payload_kind=payload_kind,
        schema_version=schema_version,
        generation=generation,
        confidentiality_label=label,
        security_critical=sec_crit,
        fresh_epoch=fresh_epoch,
        forbidden_flags=forbidden_flags,
    )
    return "ok", (meta, _EditorDoc(text=text, cursor=cursor, undo=tuple(undo), dirty=bool(dirty)))


@dataclass
class _OracleStore:
    slots: list[bytes | None]
    active_slot: int
    endurance_used: int
    endurance_limit: int
    space_reserved: int


@dataclass
class _OraclePilot:
    store: _OracleStore
    slate_owner: str | None
    grant_active: bool
    session_authority: bool
    doc: _EditorDoc
    recovery_outcome: str


def _oracle_stage_and_commit(
    pilot: _OraclePilot, new_doc: _EditorDoc, auth_key: bytes, *, crash_pre_commit: bool
) -> str:
    if pilot.store.endurance_used >= pilot.store.endurance_limit:
        return "endurance_exhausted"
    gen = pilot.store.endurance_used + 2
    meta = _WireMeta(APP_EDITOR, PAYLOAD_SEMANTIC, SCHEMA_VERSION, gen, 0x11, 0, 0, 0)
    wire = _encode_editor_wire(meta, new_doc, auth_key)
    if len(wire) > pilot.store.space_reserved:
        return "out_of_space"
    inactive = 1 - pilot.store.active_slot
    pilot.store.slots[inactive] = wire
    pilot.store.endurance_used += 1
    if crash_pre_commit:
        pilot.store.slots[inactive] = None
        return "crashed_pre_commit"
    pilot.store.active_slot = inactive
    return "committed"


def _oracle_unlock(
    pilot: _OraclePilot, grant_state: str, auth_key: bytes
) -> tuple[str, _OraclePilot]:
    if pilot.slate_owner == "painter":
        return "dual_ownership", pilot
    active_wire = pilot.store.slots[pilot.store.active_slot]
    if active_wire is None:
        return "incomplete", replace(
            pilot, grant_active=False, session_authority=False, recovery_outcome="incomplete"
        )
    verdict, decoded = _decode_editor_wire(active_wire, auth_key, 0x11)
    if verdict != "ok" or decoded is None:
        return "incomplete", replace(
            pilot, grant_active=False, session_authority=False, recovery_outcome="incomplete"
        )
    if grant_state != "valid":
        return "grant_refused", replace(
            pilot, grant_active=False, session_authority=False, recovery_outcome="grant_refused"
        )
    return "ok", replace(
        pilot,
        slate_owner="editor",
        grant_active=True,
        session_authority=False,
        doc=decoded[1],
        recovery_outcome="ok",
    )


def _check_python_oracle_and_proof_surface() -> None:
    """Run the pure-Python semantic-checkpoint oracle and validate `SemanticCheckpoint.v` surface."""
    for path in (CP_H, CP_C, CP_TEST_C, CP_README, PROOFS_V, CRYPTO_SOURCE):
        ensure(path.is_file(), f"missing required checkpoint artifact: {path}")

    auth_key = bytes(range(0x30, 0x50))
    doc0 = _EditorDoc(text=b"", cursor=0, undo=(), dirty=False)
    doc1 = _EditorDoc(
        text=b"Hi",
        cursor=2,
        undo=(_UndoEntry(1, 0, 0, 0, ord("H")), _UndoEntry(1, 1, 1, 0, ord("i"))),
        dirty=True,
    )
    meta1 = _WireMeta(APP_EDITOR, PAYLOAD_SEMANTIC, SCHEMA_VERSION, 2, 0x11, 0, 0, 0)
    wire1 = _encode_editor_wire(meta1, doc1, auth_key)
    v_ok, dec = _decode_editor_wire(wire1, auth_key, 0x11)
    ensure(v_ok == "ok" and dec is not None and dec[1] == doc1, "valid editor roundtrip")

    v_trail, _ = _decode_editor_wire(wire1 + b"\xaa", auth_key, 0x11)
    ensure(v_trail == "trailing_bytes", f"trailing bytes must fail, got {v_trail}")

    tampered = bytearray(wire1)
    tampered[-1] ^= 0x01
    v_mac, _ = _decode_editor_wire(bytes(tampered), auth_key, 0x11)
    ensure(v_mac == "auth_failed", f"tampered MAC must fail, got {v_mac}")

    raw_wire = bytearray(wire1)
    struct.pack_into("<I", raw_wire, 16, PAYLOAD_RAW_HEAP)
    raw_wire[-32:] = hmac.new(auth_key, bytes(raw_wire[:-32]), hashlib.sha256).digest()
    v_raw, _ = _decode_editor_wire(bytes(raw_wire), auth_key, 0x11)
    ensure(v_raw == "non_semantic", f"raw heap wire must fail, got {v_raw}")

    tagged_wire = bytearray(wire1)
    struct.pack_into("<I", tagged_wire, 48, 1)
    tagged_wire[-32:] = hmac.new(auth_key, bytes(tagged_wire[:-32]), hashlib.sha256).digest()
    v_tag, _ = _decode_editor_wire(bytes(tagged_wire), auth_key, 0x11)
    ensure(v_tag == "forbidden_authority", f"tagged cap wire must fail, got {v_tag}")

    # A/B slot pre-commit vs post-commit crash-cut oracle
    init_wire = _encode_editor_wire(
        _WireMeta(APP_EDITOR, PAYLOAD_SEMANTIC, SCHEMA_VERSION, 1, 0x11, 0, 0, 0),
        doc0,
        auth_key,
    )
    pilot_pre = _OraclePilot(
        store=_OracleStore([init_wire, None], 0, 0, 4, MAX_WIRE_BYTES),
        slate_owner=None,
        grant_active=False,
        session_authority=False,
        doc=doc0,
        recovery_outcome="none",
    )
    ensure(
        _oracle_stage_and_commit(pilot_pre, doc1, auth_key, crash_pre_commit=True)
        == "crashed_pre_commit",
        "pre-commit crash succeeds in test harness",
    )
    res_pre, out_pre = _oracle_unlock(pilot_pre, "valid", auth_key)
    ensure(
        res_pre == "ok" and out_pre.doc == doc0 and not out_pre.session_authority,
        "pre-commit crash preserves prior checkpoint and zero session authority",
    )

    pilot_post = _OraclePilot(
        store=_OracleStore([init_wire, None], 0, 0, 4, MAX_WIRE_BYTES),
        slate_owner=None,
        grant_active=False,
        session_authority=False,
        doc=doc0,
        recovery_outcome="none",
    )
    ensure(
        _oracle_stage_and_commit(pilot_post, doc1, auth_key, crash_pre_commit=False)
        == "committed",
        "commit succeeds",
    )
    res_rev, out_rev = _oracle_unlock(pilot_post, "revoked", auth_key)
    ensure(
        res_rev == "grant_refused" and not out_rev.grant_active and not out_rev.session_authority,
        "revoked grant refuses unlock",
    )
    res_post, out_post = _oracle_unlock(pilot_post, "valid", auth_key)
    ensure(
        res_post == "ok" and out_post.doc == doc1 and not out_post.session_authority,
        "post-commit unlock restores doc1 with zero session authority",
    )

    # Check header constants match
    h_text = CP_H.read_text(encoding="utf-8")
    for tok in (
        "VOS_CP_MAX_TEXT_BYTES = 256u",
        "VOS_CP_MAX_UNDO = 16u",
        "VOS_CP_MAX_TILES = 16u",
        "VOS_CP_MAX_IMAGE_HISTORY = 16u",
        "VOS_CP_WIRE_HEADER_BYTES = 56u",
    ):
        ensure(tok in h_text, f"missing expected header constant: {tok}")

    # Proof-surface checks on SemanticCheckpoint.v
    v_raw_text = PROOFS_V.read_text(encoding="utf-8")
    v_code = strip_comments(v_raw_text)
    ensure(
        "Require ProofSupport WorkflowProfiles." in v_code,
        "SemanticCheckpoint.v must Require ProofSupport WorkflowProfiles",
    )
    for forbidden in ("Admitted", "Axiom", "Parameter", "Conjecture"):
        ensure(
            re.search(rf"\b{forbidden}\b", v_code) is None,
            f"forbidden vernacular {forbidden} in SemanticCheckpoint.v",
        )

    m_derived = re.search(
        r"\(\*\|\s*BEGIN derived: cited entries\s*\|\*\)(.*?)\(\*\|\s*END derived\s*\|\*\)",
        v_raw_text,
        re.DOTALL,
    )
    if m_derived is None:
        raise AssertionError("SemanticCheckpoint.v missing derived header region")
    derived_reqs = set(re.findall(r"R-\d{2}-\d{3}[a-z]?", m_derived.group(1)))
    ensure(
        derived_reqs >= REQUIRED_CITED_REQS,
        f"missing derived cited requirements: {sorted(REQUIRED_CITED_REQS - derived_reqs)}",
    )

    records = re.findall(r"^\s*Record\s+([A-Za-z0-9_']+)\s*:=", v_code, re.MULTILINE)
    ensure(len(records) >= 5, f"expected >= 5 Records in SemanticCheckpoint.v, got {records}")
    for rec in records:
        ensure(
            re.search(rf"^\s*Definition\s+witness_{re.escape(rec)}\s*:\s*{re.escape(rec)}\b", v_code, re.MULTILINE)
            is not None,
            f"missing witness_{rec} definition for Record {rec}",
        )

    for sym in (
        "concrete_cp_ok_refines_abstract",
        "concrete_cp_excludes_nonsemantic_and_authority",
        "pre_commit_crash_preserves_prior_checkpoint",
        "post_commit_crash_preserves_new_checkpoint",
        "reusable_excludes_all_hazards",
        "crash_cut_never_dual_owners",
        "unlock_restores_acknowledged_document",
        "unlock_refuses_revoked_or_expired_grant",
        "unlock_never_reinstates_tags_or_session",
        "incomplete_checkpoint_preserves_recovery_outcome",
        "positive_editor_to_painter_swap_and_restore",
        "positive_editor_lock_unlock_recovery",
        "refute_stale_register",
        "refute_saved_context",
        "refute_active_loan",
        "refute_late_dma_reply",
        "refute_out_of_space_checkpoint",
        "refute_endurance_exhaustion",
        "refute_revoked_grant_on_unlock",
        "refute_expired_grant_on_unlock",
        "refute_tagged_capability_restoration",
        "refute_incomplete_checkpoint",
        "refute_dual_slate_ownership",
    ):
        ensure(
            re.search(rf"\b{re.escape(sym)}\b", v_code) is not None,
            f"missing required Gallina theorem/example: {sym}",
        )


def _compile_checkpoint_binary(
    compiler: str, flags: list[str], cp_source: Path, out_bin: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            compiler,
            *flags,
            f"-I{CP_H.parent}",
            f"-I{CRYPTO_INCLUDE}",
            str(cp_source),
            str(CRYPTO_SOURCE),
            str(CP_TEST_C),
            "-o",
            str(out_bin),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _supports_flags(compiler: str, flags: list[str], tmp: Path) -> bool:
    probe_c = tmp / "probe.c"
    probe_bin = tmp / "probe"
    probe_c.write_text("int main(void) { return 0; }\n", encoding="utf-8", newline="\n")
    done = subprocess.run(
        [compiler, *flags, str(probe_c), "-o", str(probe_bin)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return done.returncode == 0


def _build_mutants(source: str) -> list[tuple[str, str, str]]:
    specs: list[tuple[str, str, str, str]] = [
        (
            "accept_raw_heap_payload",
            "if (payload_kind != VOS_CP_PAYLOAD_SEMANTIC) {",
            "if (0 && payload_kind != VOS_CP_PAYLOAD_SEMANTIC) {",
            "decoder rejects raw heap payload",
        ),
        (
            "accept_tagged_cap_payload",
            "if (forbidden_flags != 0u) {",
            "if (0 && forbidden_flags != 0u) {",
            "decoder rejects tagged capability flags",
        ),
        (
            "skip_hmac_tag_verify",
            "if (!mac_match) {",
            "if (0 && !mac_match) {",
            "tampered HMAC rejected",
        ),
        (
            "accept_trailing_bytes",
            "if (wire_len != expected_total) {",
            "if (0 && wire_len != expected_total) {",
            "trailing bytes rejected",
        ),
        (
            "permit_stale_register_reuse",
            "if (!roots->live_registers_clear) {",
            "if (0 && !roots->live_registers_clear) {",
            "stale register refuses release",
        ),
        (
            "permit_saved_context_reuse",
            "if (!roots->raw_saved_clear) {",
            "if (0 && !roots->raw_saved_clear) {",
            "saved context refuses release",
        ),
        (
            "permit_active_loan_reuse",
            "if (!roots->loans_closed) {",
            "if (0 && !roots->loans_closed) {",
            "active loan refuses release",
        ),
        (
            "permit_late_dma_reuse",
            "if (!roots->devices_completed) {",
            "if (0 && !roots->devices_completed) {",
            "late DMA refuses release",
        ),
        (
            "ignore_checkpoint_space_limit",
            "if (candidate_len > (size_t)eng->space_reserved) {",
            "if (0 && candidate_len > (size_t)eng->space_reserved) {",
            "checkpoint space limit refused",
        ),
        (
            "ignore_endurance_exhaustion",
            "    if (eng->target_app != VOS_CP_APP_NONE || target_app == eng->selected_app) {\n"
            "        return VOS_CP_ERR_BAD_STATE;\n"
            "    }\n"
            "    if (eng->endurance_used >= eng->endurance_limit) {",
            "    if (eng->target_app != VOS_CP_APP_NONE || target_app == eng->selected_app) {\n"
            "        return VOS_CP_ERR_BAD_STATE;\n"
            "    }\n"
            "    if (0 && eng->endurance_used >= eng->endurance_limit) {",
            "endurance exhaustion refused",
        ),
        (
            "reinstate_revoked_or_expired_grant",
            "    if (grant_state != VOS_CP_GRANT_VALID) {\n"
            "        ed->document_grant = 0u;\n"
            "        ed->session_authority = 0u;\n"
            "        ed->tagged_state_restored = 0u;\n"
            "        eng->recovery_outcome = VOS_CP_RECOVERY_GRANT_REFUSED;\n"
            "        *out_outcome = VOS_CP_RECOVERY_GRANT_REFUSED;",
            "    if (0 && grant_state != VOS_CP_GRANT_VALID) {\n"
            "        ed->document_grant = 0u;\n"
            "        ed->session_authority = 0u;\n"
            "        ed->tagged_state_restored = 0u;\n"
            "        eng->recovery_outcome = VOS_CP_RECOVERY_GRANT_REFUSED;\n"
            "        *out_outcome = VOS_CP_RECOVERY_GRANT_REFUSED;",
            "revoked grant refused",
        ),
        (
            "restore_session_authority_on_unlock",
            "ed->session_authority = 0u; /* unlock never restores prior session */",
            "ed->session_authority = 1u; /* mutated: restores prior session */",
            "unlock restored document without reviving session or tagged state",
        ),
        (
            "overwrite_active_ab_slot_pre_commit",
            "/* Stage strictly into the INACTIVE slot so active_slot remains intact pre-commit. */\n"
            "    const uint32_t stage_idx = 1u - st->active_slot;",
            "/* Stage strictly into the INACTIVE slot so active_slot remains intact pre-commit. */\n"
            "    const uint32_t stage_idx = st->active_slot;",
            "active checkpoint always valid after crash",
        ),
        (
            "permit_dual_slate_ownership",
            "if (dst->owns_slate != 0u || other->owns_slate != 0u) {",
            "if (0 && (dst->owns_slate != 0u || other->owns_slate != 0u)) {",
            "dual slate ownership refused",
        ),
    ]
    mutants: list[tuple[str, str, str]] = []
    for label, target, replacement, expected_diag in specs:
        count = source.count(target)
        ensure(count == 1, f"mutant target for {label} matched {count} times (expected 1)")
        mutants.append((label, source.replace(target, replacement, 1), expected_diag))
    return mutants


def _native_c17_and_mutants() -> None:
    """Compile and run `checkpoint` under Clang C17 + GCC ASan/UBSan and kill >= 10 mutants."""
    if sys.platform == "win32":
        return

    clang = shutil.which("clang")
    gcc = shutil.which("gcc")
    ensure(clang is not None, "clang compiler is required in Linux guest")
    ensure(gcc is not None, "gcc compiler is required in Linux guest")
    if clang is None or gcc is None:
        return

    strict_flags = [
        "-std=c17",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wstrict-prototypes",
        "-pedantic",
    ]
    asan_flags = [*strict_flags, "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]

    work = toolenv.environment(ROOT, sys.platform).parent / "semantic-checkpoint-c-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="scp-", dir=work) as td:
        tmp = Path(td)
        ensure(_supports_flags(gcc, asan_flags, tmp), "gcc ASan/UBSan runtime is required")

        clang_bin = tmp / "checkpoint_test_clang"
        clang_built = _compile_checkpoint_binary(clang, strict_flags, CP_C, clang_bin)
        ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
        clang_ran = subprocess.run(
            [str(clang_bin)], capture_output=True, text=True, timeout=60, check=False
        )
        ensure(
            clang_ran.returncode == 0 and "checkpoint_test: ok" in clang_ran.stdout,
            f"clang test run failed: {clang_ran.stderr or clang_ran.stdout}",
        )

        gcc_bin = tmp / "checkpoint_test_gcc_asan"
        gcc_built = _compile_checkpoint_binary(gcc, asan_flags, CP_C, gcc_bin)
        ensure(gcc_built.returncode == 0, f"gcc ASan/UBSan build failed: {gcc_built.stderr}")
        gcc_ran = subprocess.run(
            [str(gcc_bin)], capture_output=True, text=True, timeout=60, check=False
        )
        ensure(
            gcc_ran.returncode == 0 and "checkpoint_test: ok" in gcc_ran.stdout,
            f"gcc ASan/UBSan test run failed: {gcc_ran.stderr or gcc_ran.stdout}",
        )

        source = CP_C.read_text(encoding="utf-8")
        mutants = _build_mutants(source)
        ensure(len(mutants) >= 10, f"expected >= 10 mutants, got {len(mutants)}")
        for label, mutated_source, expected_diag in mutants:
            mut_c = tmp / f"mutant_{label}.c"
            mut_c.write_text(mutated_source, encoding="utf-8", newline="\n")
            mut_bin = tmp / f"mutant_{label}"
            m_built = _compile_checkpoint_binary(gcc, asan_flags, mut_c, mut_bin)
            ensure(m_built.returncode == 0, f"stillborn mutant {label}: {m_built.stderr}")
            m_ran = subprocess.run(
                [str(mut_bin)], capture_output=True, text=True, timeout=60, check=False
            )
            ensure(
                m_ran.returncode != 0 and expected_diag in m_ran.stderr,
                f"mutant survived or missed expected diagnostic ({label}): "
                f"{m_ran.stderr or m_ran.stdout}",
            )


def cases() -> list[Case]:
    return [
        Case("semantic_checkpoint_python_oracle", _check_python_oracle_and_proof_surface, lane="any"),
        Case("semantic_checkpoint_c17_and_mutants", _native_c17_and_mutants, lane="guest"),
    ]
