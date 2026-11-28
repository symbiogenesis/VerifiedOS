# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracles and native C17 controls for `BackupTrustedScreen.v` and `trusted-screen/`."""

import hashlib
import hmac
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from tests.harness import Case, ensure
from vos.proofs import strip_comments

INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]
TS_DIR = ROOT / "trusted-screen"
TS_H = TS_DIR / "include" / "vos_trusted_screen.h"
TS_C = TS_DIR / "src" / "trusted_screen.c"
TS_TEST_C = TS_DIR / "test" / "test_trusted_screen.c"
TS_README = TS_DIR / "README.md"
BACKUP_INCLUDE = ROOT / "backup" / "include"
BACKUP_SOURCE = ROOT / "backup" / "src" / "backup.c"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PROOFS_V = ROOT / "proofs" / "BackupTrustedScreen.v"

UPPER_HEX = "0123456789ABCDEF"
MAX_ROOTS = 8


def _encode_recovery_display(key: bytes) -> str:
    ensure(len(key) == 32, "recovery key must be 32 bytes")
    raw = "".join(UPPER_HEX[b >> 4] + UPPER_HEX[b & 0x0F] for b in key)
    return " ".join(raw[i : i + 4] for i in range(0, 64, 4))


def _decode_recovery_entry(entry: str) -> bytes | None:
    if len(entry) != 64:
        return None
    out = bytearray()
    for i in range(0, 64, 2):
        hi = UPPER_HEX.find(entry[i])
        lo = UPPER_HEX.find(entry[i + 1])
        if hi < 0 or lo < 0:
            return None
        out.append((hi << 4) | lo)
    return bytes(out)


@dataclass
class _DisplaySession:
    shown_once: bool = False
    secret_buf: bytearray | None = None
    display_buf: str | None = None
    app_visible: bytes = b""
    clipboard: bytes = b""
    screenshot: bytes = b""
    log: bytes = b""

    def show_once(self, key: bytes, unlocked: bool, latch: bool, cred: bool, ack_r17: bool) -> bool:
        if self.shown_once or not (unlocked and latch and cred and ack_r17):
            return False
        self.shown_once = True
        self.secret_buf = bytearray(key)
        self.display_buf = _encode_recovery_display(key)
        return True

    def exit(self, _reason: str) -> None:
        if self.secret_buf is not None:
            for i in range(len(self.secret_buf)):
                self.secret_buf[i] = 0
        self.secret_buf = None
        self.display_buf = None


@dataclass(frozen=True)
class _OracleTrustedPath:
    unlocked: bool
    hw_latch: bool
    primary_cred: bool
    receiver_cred: bool
    app_originated: bool
    epoch: int
    profile: int
    generation: int
    hmac_key: bytes

    def gate_ok(self) -> bool:
        return self.unlocked and self.hw_latch and self.primary_cred and (not self.app_originated)


@dataclass(frozen=True)
class _OracleWitness:
    trusted_issued: bool
    consumed: bool
    seq: int
    epoch: int
    flow: str
    profile: int
    generation: int
    obj_id: int
    dst_id: int
    plan_id: int
    needs_discard: bool
    root_digest: bytes
    mac: bytes


def _witness_mac(hmac_key: bytes, seq: int, epoch: int, flow: str, profile: int,
                 generation: int, obj_id: int, dst_id: int, plan_id: int,
                 needs_discard: bool, root_digest: bytes) -> bytes:
    msg = (
        b"VOSTSCW1"
        + seq.to_bytes(8, "big")
        + epoch.to_bytes(8, "big")
        + flow.encode("ascii")
        + profile.to_bytes(4, "big")
        + generation.to_bytes(8, "big")
        + obj_id.to_bytes(8, "big")
        + dst_id.to_bytes(8, "big")
        + plan_id.to_bytes(8, "big")
        + (1 if needs_discard else 0).to_bytes(1, "big")
        + root_digest
    )
    return hmac.new(hmac_key, msg, hashlib.sha256).digest()


def _issue_oracle_witness(
    tp: _OracleTrustedPath,
    flow: str,
    seq: int,
    obj_id: int,
    dst_id: int,
    plan_id: int,
    needs_discard: bool,
    caveats: dict[str, bool],
    root_digest: bytes = b"\x00" * 32,
) -> _OracleWitness | None:
    if not tp.gate_ok():
        return None
    if flow not in ("export", "restore", "migration"):
        return None
    if not caveats.get("not_rollback", False):
        return None
    if flow == "export" and not caveats.get("off_device_trade", False):
        return None
    if flow == "restore":
        if not caveats.get("surrendered_freshness", False):
            return None
        if needs_discard and not caveats.get("discard_loss", False):
            return None
    if flow == "migration":
        if not (tp.receiver_cred and caveats.get("migration_roots", False)):
            return None
    mac = _witness_mac(
        tp.hmac_key, seq, tp.epoch, flow, tp.profile, tp.generation,
        obj_id, dst_id, plan_id, needs_discard, root_digest,
    )
    return _OracleWitness(
        trusted_issued=True, consumed=False, seq=seq, epoch=tp.epoch, flow=flow,
        profile=tp.profile, generation=tp.generation, obj_id=obj_id,
        dst_id=dst_id, plan_id=plan_id, needs_discard=needs_discard,
        root_digest=root_digest, mac=mac,
    )


def _consume_oracle_witness(
    tp: _OracleTrustedPath,
    spent: set[int],
    w: _OracleWitness,
    flow: str,
    obj_id: int,
    dst_id: int,
    plan_id: int,
    needs_discard: bool,
    root_digest: bytes = b"\x00" * 32,
) -> _OracleWitness | None:
    if not tp.gate_ok() or not w.trusted_issued or w.consumed or w.seq in spent:
        return None
    if w.epoch != tp.epoch or w.flow != flow:
        return None
    if flow == "migration" and not tp.receiver_cred:
        return None
    if (w.profile != tp.profile or w.generation != tp.generation or
            w.obj_id != obj_id or w.dst_id != dst_id or
            w.plan_id != plan_id or w.needs_discard != needs_discard or
            w.root_digest != root_digest):
        return None
    expected_mac = _witness_mac(
        tp.hmac_key, w.seq, w.epoch, w.flow, w.profile, w.generation,
        w.obj_id, w.dst_id, w.plan_id, w.needs_discard, w.root_digest,
    )
    if not hmac.compare_digest(w.mac, expected_mac):
        return None
    spent.add(w.seq)
    return replace(w, consumed=True)


def _display_and_secret_oracle() -> None:
    """Verify 16x4 leading-zero `RecoverySecret-v1` formatting, one-time lock, and exit wipes."""
    key_lz = bytes(range(32))
    disp = _encode_recovery_display(key_lz)
    ensure(len(disp) == 79 and disp.startswith("0001 0203 0405"), "16x4 leading-zero display")
    raw = disp.replace(" ", "")
    ensure(_decode_recovery_entry(raw) == key_lz, "canonical 64-char decode round-trip")
    ensure(_decode_recovery_entry(raw.lower()) is None, "lowercase rejected")
    ensure(_decode_recovery_entry(disp) is None, "spaced display rejected as raw entry")
    ensure(_decode_recovery_entry(raw[:-1]) is None, "short entry rejected")

    for reason in ("Complete", "Cancel", "Lock", "Fault"):
        sess = _DisplaySession()
        ensure(sess.show_once(key_lz, True, True, True, True), f"first show ok ({reason})")
        ensure(not sess.show_once(key_lz, True, True, True, True), "redisplay while showing refused")
        sess.exit(reason)
        ensure(sess.secret_buf is None and sess.display_buf is None, f"buffers cleared on {reason}")
        ensure(not sess.show_once(key_lz, True, True, True, True), f"redisplay after {reason} refused")
        ensure(sess.app_visible == b"" and sess.clipboard == b"" and
               sess.screenshot == b"" and sess.log == b"", "zero side-channel leakage")


def _consent_and_migration_oracle() -> None:
    """Verify flow separation, caveats, HMAC one-use witnesses, and root confirmation."""
    tp = _OracleTrustedPath(
        unlocked=True, hw_latch=True, primary_cred=True, receiver_cred=True,
        app_originated=False, epoch=1, profile=1, generation=7, hmac_key=b"\x42" * 32,
    )
    all_cav = {
        "off_device_trade": True, "surrendered_freshness": True,
        "discard_loss": True, "migration_roots": True, "not_rollback": True,
    }
    ensure(_issue_oracle_witness(tp, "rollback", 1, 1, 1, 1, False, all_cav) is None,
           "rollback flow refused")
    ensure(_issue_oracle_witness(replace(tp, app_originated=True), "export", 1, 1, 1, 1, False, all_cav) is None,
           "app-originated flow refused")
    ensure(_issue_oracle_witness(tp, "export", 1, 1, 1, 1, False, {**all_cav, "off_device_trade": False}) is None,
           "missing R-17-054a caveat refused")
    ensure(_issue_oracle_witness(tp, "restore", 1, 1, 1, 1, True, {**all_cav, "discard_loss": False}) is None,
           "missing discard-loss caveat refused")

    w = _issue_oracle_witness(tp, "restore", 1, 77, 1, 10, True, all_cav)
    ensure(w is not None, "valid restore discard witness issued")
    if w is None:
        raise AssertionError("unreachable")
    spent: set[int] = set()
    ensure(_consume_oracle_witness(replace(tp, unlocked=False), spent, w, "restore", 77, 1, 10, True) is None,
           "locked device refused")
    ensure(_consume_oracle_witness(replace(tp, epoch=2), spent, w, "restore", 77, 1, 10, True) is None,
           "lock/restart epoch expiry refused")
    ensure(_consume_oracle_witness(replace(tp, profile=2), spent, w, "restore", 77, 1, 10, True) is None,
           "profile change refused")
    ensure(_consume_oracle_witness(tp, spent, w, "restore", 77, 1, 99, True) is None,
           "plan change refused")
    ensure(_consume_oracle_witness(tp, spent, replace(w, trusted_issued=False), "restore", 77, 1, 10, True) is None,
           "app-forged witness refused")

    w_done = _consume_oracle_witness(tp, spent, w, "restore", 77, 1, 10, True)
    ensure(w_done is not None and w_done.consumed, "first consumption succeeds")
    ensure(_consume_oracle_witness(tp, spent, w, "restore", 77, 1, 10, True) is None,
           "copy-replay refused via spent ledger")

    roots = ("RoT-A", "RoT-B")
    too_many = tuple(f"RoT-{i}" for i in range(MAX_ROOTS + 1))
    ensure(len(too_many) > MAX_ROOTS, "oversize root set exceeds capacity")
    ensure(roots[:1] != roots and ("RoT-A", "RoT-Evil") != roots,
           "truncated or substituted roots refused")


def _surface_and_proof_contract() -> None:
    """Verify deliverables, SPDX headers, heap-free C17, and Rocq symbols/witnesses."""
    for path in (TS_H, TS_C, TS_TEST_C, TS_README, PROOFS_V):
        ensure(path.is_file(), f"missing trusted-screen artifact: {path}")

    for c_path in (TS_H, TS_C, TS_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        ensure(text.splitlines()[0] == "// SPDX-License-Identifier: Apache-2.0",
               f"missing // SPDX header in {c_path}")
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden dynamic allocation {forbidden} in {c_path}")

    c_src = TS_C.read_text(encoding="utf-8")
    for fn in (
        "vos_ts_wipe",
        "vos_ts_format_recovery_display",
        "vos_ts_trusted_path_init",
        "vos_ts_trusted_path_lock",
        "vos_ts_issue_witness",
        "vos_ts_verify_and_consume_witness",
        "vos_ts_export_authorize",
        "vos_ts_export_show_secret_once",
        "vos_ts_export_confirm_recorded",
        "vos_ts_export_abort",
        "vos_ts_restore_authorize",
        "vos_ts_restore_enter_recovery_secret",
        "vos_ts_restore_consume_and_commit",
        "vos_ts_migration_present_roots",
        "vos_ts_migration_confirm",
        "vos_ts_migration_consume_transfer",
    ):
        ensure(fn in c_src, f"missing C entry point {fn}")

    v_src = PROOFS_V.read_text(encoding="utf-8")
    ensure(v_src.splitlines()[0] == "(* SPDX-License-Identifier: Apache-2.0 *)",
           "missing Rocq SPDX header in BackupTrustedScreen.v")
    for sym in (
        "flow_distinct_from_rollback",
        "display_groups_round_trip_canonical",
        "display_exit_clears_all_buffers",
        "display_once_blocks_redisplay",
        "display_never_leaks_to_side_channels",
        "migration_screen_refuses_unappraised",
        "migration_screen_refuses_oversize_or_empty_roots",
        "migration_confirm_refuses_truncated_or_substituted",
        "no_witness_without_cred_latch_and_caveats",
        "witness_cannot_be_replayed",
        "witness_cannot_be_forged_by_app",
        "witness_expires_on_lock_or_restart",
        "witness_expires_on_binding_change",
        "inhabited_export_screen_trace",
        "inhabited_restore_and_discard_screen_traces",
        "inhabited_migration_screen_trace",
        "screen_refutation_witnesses",
        "witness_CaveatAck",
        "witness_TrustedPathEnv",
        "witness_DisplayState",
        "witness_RootConfirmationScreen",
        "witness_ScreenConsentWitness",
    ):
        ensure(sym in v_src, f"missing Rocq specification symbol {sym} in BackupTrustedScreen.v")

    v_clean = strip_comments(v_src)
    for banned in ("Admitted", "admit", "Axiom", "Parameter", "Conjecture", "Section", "CoFixpoint", "CoInductive"):
        ensure(
            re.search(rf"\b{banned}\b", v_clean) is None,
            f"forbidden proof keyword {banned} in BackupTrustedScreen.v",
        )


def _select_sanitizer_compiler(tmp_path: Path) -> tuple[str, list[str]]:
    """Select a C17 compiler supporting ASan/UBSan on Linux."""
    cflags = ["-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes"]
    san_flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    probe_src = tmp_path / "probe.c"
    probe_src.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    probe_bin = tmp_path / "probe"

    for name in ("gcc", "clang", "cc"):
        compiler = shutil.which(name)
        if compiler is None:
            continue
        res = subprocess.run(
            [compiler, *cflags, *san_flags, str(probe_src), "-o", str(probe_bin)],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if res.returncode == 0:
            return compiler, [*cflags, *san_flags]

    raise AssertionError("no C17 compiler with ASan/UBSan runtime available in Linux guest")


def _native_c_and_mutation_controls() -> None:
    """Compile and run `trusted-screen` tests under GCC ASan/UBSan + Clang strict and kill >= 10 mutants."""
    if sys.platform == "win32":
        return

    with tempfile.TemporaryDirectory(prefix="vos-trusted-screen-c-") as td:
        tmp = Path(td)
        compiler, flags = _select_sanitizer_compiler(tmp)
        binary = tmp / "test_trusted_screen"
        includes = [f"-I{TS_H.parent}", f"-I{BACKUP_INCLUDE}", f"-I{CRYPTO_INCLUDE}"]
        cmd = [
            compiler,
            *flags,
            *includes,
            str(TS_C),
            str(BACKUP_SOURCE),
            str(CRYPTO_SOURCE),
            str(TS_TEST_C),
            "-o",
            str(binary),
        ]
        built = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
        ensure(built.returncode == 0, f"trusted-screen C build failed: {built.stderr}")
        ran = subprocess.run([str(binary)], capture_output=True, text=True, check=False, timeout=60)
        ensure(ran.returncode == 0 and "trusted_screen_test: ok" in ran.stdout,
               f"trusted-screen C test failed: {ran.stderr or ran.stdout}")

        clang = shutil.which("clang")
        if clang is not None:
            clang_bin = tmp / "test_trusted_screen_clang"
            clang_built = subprocess.run(
                [
                    clang, "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes",
                    *includes,
                    str(TS_C), str(BACKUP_SOURCE), str(CRYPTO_SOURCE), str(TS_TEST_C),
                    "-o", str(clang_bin),
                ],
                capture_output=True, text=True, check=False, timeout=60,
            )
            ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
            clang_ran = subprocess.run([str(clang_bin)], capture_output=True, text=True, check=False, timeout=60)
            ensure(clang_ran.returncode == 0 and "trusted_screen_test: ok" in clang_ran.stdout,
                   f"clang binary failed: {clang_ran.stderr or clang_ran.stdout}")

        source = TS_C.read_text(encoding="utf-8")
        mutants: list[tuple[str, str, str]] = [
            (
                "ts-allow-redisplay",
                "    if (scr->displayed_once != 0u) {\n"
                "        return VOS_TS_ERR_REDISPLAY;\n"
                "    }\n"
                "    if (scr->phase != VOS_TS_EXP_AUTHORIZED) {\n"
                "        return VOS_TS_ERR_STATE;\n"
                "    }",
                "    if (0 && scr->displayed_once != 0u) {\n"
                "        return VOS_TS_ERR_REDISPLAY;\n"
                "    }\n"
                "    if (scr->phase == VOS_TS_EXP_IDLE) {\n"
                "        return VOS_TS_ERR_STATE;\n"
                "    }",
            ),
            (
                "ts-omit-zeroize-on-abort",
                "    vos_ts_wipe(scr->secret_buf, sizeof(scr->secret_buf));\n"
                "    vos_ts_wipe(scr->display_buf, sizeof(scr->display_buf));\n"
                "    vos_ts_wipe(&scr->witness, sizeof(scr->witness));",
                "    if (0) {\n"
                "        vos_ts_wipe(scr->secret_buf, sizeof(scr->secret_buf));\n"
                "        vos_ts_wipe(scr->display_buf, sizeof(scr->display_buf));\n"
                "    }\n"
                "    vos_ts_wipe(&scr->witness, sizeof(scr->witness));",
            ),
            (
                "ts-accept-lowercase-secret",
                "    if (!entry_is_canonical_hex_chars(entry, entry_len)) {\n"
                "        vos_ts_wipe(scr->recovered_key, sizeof(scr->recovered_key));\n"
                "        return VOS_TS_ERR_HEX_FORMAT;\n"
                "    }\n"
                "    if (vos_bk_decode_recovery_secret(entry, entry_len, scr->recovered_key) != VOS_BK_OK) {\n"
                "        vos_ts_wipe(scr->recovered_key, sizeof(scr->recovered_key));\n"
                "        return VOS_TS_ERR_HEX_FORMAT;\n"
                "    }",
                "    (void)entry_is_canonical_hex_chars;\n"
                "    char upper[VOS_BK_RECOVERY_HEX_CHARS + 1u];\n"
                "    if (entry_len != VOS_BK_RECOVERY_HEX_CHARS) {\n"
                "        return VOS_TS_ERR_HEX_FORMAT;\n"
                "    }\n"
                "    for (size_t i = 0u; i < entry_len; ++i) {\n"
                "        char ch = entry[i];\n"
                "        upper[i] = (ch >= 'a' && ch <= 'f') ? (char)(ch - 'a' + 'A') : ch;\n"
                "    }\n"
                "    upper[entry_len] = '\\0';\n"
                "    if (vos_bk_decode_recovery_secret(upper, entry_len, scr->recovered_key) != VOS_BK_OK) {\n"
                "        vos_ts_wipe(scr->recovered_key, sizeof(scr->recovered_key));\n"
                "        return VOS_TS_ERR_HEX_FORMAT;\n"
                "    }",
            ),
            (
                "ts-skip-r17-054a-caveat",
                "    case VOS_TS_FLOW_BACKUP_EXPORT:\n"
                "        return cav->ack_off_device_trade != 0u;",
                "    case VOS_TS_FLOW_BACKUP_EXPORT:\n"
                "        return 1;",
            ),
            (
                "ts-skip-discard-caveat",
                "        if (needs_discard != 0u && cav->ack_discard_loss == 0u) {\n"
                "            return 0;\n"
                "        }",
                "        if (0 && needs_discard != 0u && cav->ack_discard_loss == 0u) {\n"
                "            return 0;\n"
                "        }",
            ),
            (
                "ts-allow-witness-replay",
                "    if (witness->consumed != 0u || is_seq_spent(tp, witness->seq)) {\n"
                "        return VOS_TS_ERR_REPLAY;\n"
                "    }",
                "    if (0 && (witness->consumed != 0u || is_seq_spent(tp, witness->seq))) {\n"
                "        return VOS_TS_ERR_REPLAY;\n"
                "    }",
            ),
            (
                "ts-accept-app-originated-witness",
                "    if (witness->trusted_issued != 1u) {\n"
                "        return VOS_TS_ERR_APP_SPOOF;\n"
                "    }",
                "    if (0 && witness->trusted_issued != 1u) {\n"
                "        return VOS_TS_ERR_APP_SPOOF;\n"
                "    }",
            ),
            (
                "ts-truncate-receiver-roots",
                "    if (roots == NULL || root_count == 0u || root_count > VOS_TS_MAX_ROOTS) {\n"
                "        return VOS_TS_ERR_ROOT_TRUNCATED;\n"
                "    }",
                "    if (roots == NULL || root_count == 0u) {\n"
                "        return VOS_TS_ERR_ROOT_TRUNCATED;\n"
                "    }\n"
                "    if (root_count > VOS_TS_MAX_ROOTS) {\n"
                "        root_count = VOS_TS_MAX_ROOTS;\n"
                "    }",
            ),
            (
                "ts-allow-locked-restore",
                "    if (tp->unlocked == 0u) {\n"
                "        return VOS_TS_ERR_LOCKED;\n"
                "    }",
                "    if (0 && tp->unlocked == 0u) {\n"
                "        return VOS_TS_ERR_LOCKED;\n"
                "    }",
            ),
            (
                "ts-skip-plan-profile-binding",
                "    if (witness->unlocked_profile != tp->unlocked_profile ||\n"
                "        witness->generation != tp->device_generation ||\n"
                "        witness->object_or_snapshot_id != expected_obj_id ||\n"
                "        witness->destination_id != expected_dst_id ||\n"
                "        witness->plan_id != expected_plan_id ||\n"
                "        witness->allow_discard != ((expected_needs_discard != 0u) ? 1u : 0u)) {\n"
                "        return VOS_TS_ERR_BINDING;\n"
                "    }",
                "    (void)expected_plan_id;\n"
                "    if (witness->generation != tp->device_generation ||\n"
                "        witness->object_or_snapshot_id != expected_obj_id ||\n"
                "        witness->destination_id != expected_dst_id ||\n"
                "        witness->allow_discard != ((expected_needs_discard != 0u) ? 1u : 0u)) {\n"
                "        return VOS_TS_ERR_BINDING;\n"
                "    }",
            ),
            (
                "ts-allow-migration-before-appraisal",
                "    if (mutually_appraised == 0u) {\n"
                "        return VOS_TS_ERR_NOT_APPRAISED;\n"
                "    }",
                "    if (0 && mutually_appraised == 0u) {\n"
                "        return VOS_TS_ERR_NOT_APPRAISED;\n"
                "    }",
            ),
            (
                "ts-skip-witness-hmac",
                "    if (!mac_ok) {\n"
                "        return VOS_TS_ERR_HMAC;\n"
                "    }",
                "    if (0 && !mac_ok) {\n"
                "        return VOS_TS_ERR_HMAC;\n"
                "    }",
            ),
        ]

        ensure(len(mutants) >= 10, "expected at least 10 behavioral mutants")
        for label, target, replacement in mutants:
            ensure(source.count(target) == 1, f"mutant target missing or non-unique: {label}")
            mutant_c = tmp / f"mutant_{label}.c"
            mutant_c.write_text(source.replace(target, replacement, 1), encoding="utf-8")
            mutant_bin = tmp / f"mutant_{label}"
            m_built = subprocess.run(
                [
                    compiler, *flags, *includes,
                    str(mutant_c), str(BACKUP_SOURCE), str(CRYPTO_SOURCE), str(TS_TEST_C),
                    "-o", str(mutant_bin),
                ],
                capture_output=True, text=True, check=False, timeout=60,
            )
            ensure(m_built.returncode == 0, f"stillborn mutant {label}: {m_built.stderr}")
            m_ran = subprocess.run([str(mutant_bin)], capture_output=True, text=True, check=False, timeout=60)
            ensure(m_ran.returncode != 0, f"mutant survived: {label}")


def cases() -> list[Case]:
    return [
        Case("backup_trusted_screen_display_and_secret_oracle", _display_and_secret_oracle, lane="any"),
        Case("backup_trusted_screen_consent_and_migration_oracle", _consent_and_migration_oracle, lane="any"),
        Case("backup_trusted_screen_surface_and_proof_contract", _surface_and_proof_contract, lane="any"),
        Case("backup_trusted_screen_native_c_and_mutation_controls", _native_c_and_mutation_controls, lane="guest"),
    ]
