# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracle and native C17 ASan/UBSan + mutation controls for witness-validator/."""

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
from vos import toolenv
from vos import witness as w
from vos.proofs import strip_comments

INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]
WV_DIR = ROOT / "witness-validator"
WV_H = WV_DIR / "include" / "vos_witness_validator.h"
WV_C = WV_DIR / "src" / "witness_validator.c"
WV_TEST_C = WV_DIR / "test" / "test_witness_validator.c"
WV_README = WV_DIR / "README.md"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PROOFS_V = ROOT / "proofs" / "WitnessContinuity.v"


@dataclass(frozen=True)
class _WireWitness:
    witness_id: int
    verify_key: bytes


@dataclass(frozen=True)
class _WirePolicy:
    trust_scope: int
    epoch: int
    k: int
    f: int
    witnesses: tuple[_WireWitness, ...]

    @property
    def n(self) -> int:
        return len(self.witnesses)

    def wellformed(self) -> bool:
        n = self.n
        if self.trust_scope <= 0 or not 1 <= self.k <= n or not 0 <= self.f < n:
            return False
        if any(len(wt.verify_key) != 32 or wt.verify_key == bytes(32) for wt in self.witnesses):
            return False
        return (
            len({wt.witness_id for wt in self.witnesses}) == n
            and len({wt.verify_key for wt in self.witnesses}) == n
        )

    def safe(self) -> bool:
        return self.wellformed() and (2 * self.k) > (self.n + self.f)


def _make_hash(tag: int) -> bytes:
    return bytes((tag ^ i) & 0xFF for i in range(32))


def _make_key(witness_id: int) -> bytes:
    return bytes(((witness_id * 17 + i) & 0xFF) or 1 for i in range(32))


def _encode_policy(pol: _WirePolicy) -> bytes:
    out = bytearray(b"VOSWTP01")
    out += pol.trust_scope.to_bytes(8, "little")
    out += pol.epoch.to_bytes(8, "little")
    out += pol.n.to_bytes(4, "little")
    out += pol.k.to_bytes(4, "little")
    out += pol.f.to_bytes(4, "little")
    for wt in pol.witnesses:
        out += wt.witness_id.to_bytes(8, "little")
        out += wt.verify_key
    return bytes(out)


def _encode_checkpoint(entries: tuple[bytes, ...]) -> bytes:
    out = bytearray(b"VOSWTC01")
    out += len(entries).to_bytes(4, "little")
    for entry in entries:
        out += entry
    return bytes(out)


def _transition_digest(old_pol: _WirePolicy, new_pol: _WirePolicy,
                       anchor: tuple[bytes, ...]) -> bytes:
    payload = (
        b"VOSWTT01"
        + hashlib.sha256(_encode_policy(old_pol)).digest()
        + hashlib.sha256(_encode_policy(new_pol)).digest()
        + hashlib.sha256(_encode_checkpoint(anchor)).digest()
    )
    return hashlib.sha256(payload).digest()


def _sign_wire(pol: _WirePolicy, idx: int, stmt_kind: int,
               checkpoint: tuple[bytes, ...], tr_digest: bytes | None = None) -> bytes:
    wt = pol.witnesses[idx]
    pol_dig = hashlib.sha256(_encode_policy(pol)).digest()
    cp_dig = hashlib.sha256(_encode_checkpoint(checkpoint)).digest()
    td = tr_digest if tr_digest is not None else bytes(32)
    msg = (
        b"VOSWIT01"
        + stmt_kind.to_bytes(4, "little")
        + pol.trust_scope.to_bytes(8, "little")
        + pol.epoch.to_bytes(8, "little")
        + pol_dig
        + cp_dig
        + td
        + wt.witness_id.to_bytes(8, "little")
        + wt.verify_key
    )
    mac = hmac.new(wt.verify_key, msg, hashlib.sha256).digest()
    return msg + mac


def _oracle_wire_and_continuity() -> None:
    """Verify canonical wire vectors and WitnessContinuity.v / witness.py oracle invariants."""
    pol = _WirePolicy(
        trust_scope=1,
        epoch=0,
        k=3,
        f=1,
        witnesses=tuple(_WireWitness(wid, _make_key(wid)) for wid in (10, 11, 12, 13)),
    )
    cp = (_make_hash(0x11), _make_hash(0x22))
    pol_dig = hashlib.sha256(_encode_policy(pol)).digest()
    cp_dig = hashlib.sha256(_encode_checkpoint(cp)).digest()
    sig0_wire = _sign_wire(pol, 0, 1, cp)

    ensure(len(sig0_wire) == 196, "VOSWIT01 wire size mismatch")
    ensure(pol_dig.hex() == "cd224280c8a93ff93dd9a05ea57a608ac47635c9d517802506c2fdcef3cfea47",
           "policy digest vector mismatch")
    ensure(cp_dig.hex() == "c890f1eb4a08d755f4a43edb37b0d0ec7362e0486c3155e63d5ed99518a094ca",
           "checkpoint digest vector mismatch")
    ensure(sig0_wire[164:].hex() == "d684919f8df6e61bc6637f37fab4191b2ce1c377522a7c6748e982b7daaea89f",
           "VOSWIT01 HMAC vector mismatch")

    # 1-of-2 split-view safety refusal against WitnessContinuity / witness.py
    p_1of2 = w.flat(2, 1, 0, scope="split-scope")
    ensure(not p_1of2.safe, "1-of-2 must fail 2*K > N+f")
    left_cp = ("base", "left")
    right_cp = ("base", "right")
    s_left = w.Witness(p_1of2, p_1of2.witnesses[0]).sign(left_cp)
    s_right = w.Witness(p_1of2, p_1of2.witnesses[1]).sign(right_cp)
    c_1of2 = w.Client(p_1of2)
    ensure(not c_1of2.admit(left_cp, (s_left,), "base", ("left",), "gen-left"),
           "1-of-2 left split view accepted")
    ensure(not c_1of2.admit(right_cp, (s_right,), "base", ("right",), "gen-right"),
           "1-of-2 right split view accepted")
    ensure(c_1of2.installed == "running-generation" and c_1of2.pinned == (),
           "1-of-2 refusal mutated client state")

    # Continuous terminal transition vs prefix-only refusal + pin immutability
    old_pol = w.flat(4, 3, 1, scope="7", epoch=0, prefix="o")
    new_pol = w.flat(4, 3, 1, scope="7", epoch=1, prefix="n")
    tr = w.Transition(old_pol, new_pol, ("anchor",))
    old_plain = w.signatures(old_pol, ("anchor",))
    old_seals = tuple(w.Witness(old_pol, wt).sign(("anchor",), tr) for wt in old_pol.witnesses[:3])
    new_sigs = w.signatures(new_pol, ("anchor",))
    client = w.Client(old_pol)
    ensure(not client.transition(tr, old_plain, new_sigs),
           "prefix-only transition accepted without terminal seals")
    ensure(client.policy == old_pol and client.pinned == (),
           "refused transition mutated client")
    ensure(client.transition(tr, old_seals, new_sigs),
           "continuous terminal transition refused")
    ensure(client.policy == new_pol and client.continuity_preserved,
           "continuous transition lost policy or continuity")

    # Explicit authenticated rebootstrap fresh scope vs A->B->A reused scope
    rb_pol = w.flat(3, 3, 1, scope="9", epoch=0, prefix="r")
    rb_good = w.Rebootstrap(new_pol, rb_pol, ("anchor", "right"), "fresh operators", True)
    rb_sigs = w.signatures(rb_pol, ("anchor", "right"))
    ensure(not client.rebootstrap(replace(rb_good, authenticated=False), rb_sigs),
           "unauthenticated rebootstrap accepted")
    ensure(client.rebootstrap(rb_good, rb_sigs), "authenticated rebootstrap refused")
    ensure(not client.continuity_preserved and client.policy == rb_pol,
           "rebootstrap did not surrender continuity")
    rb_reused = w.Rebootstrap(rb_pol, old_pol, ("anchor",), "reuse 7", True)
    ensure(not client.rebootstrap(rb_reused, w.signatures(old_pol, ("anchor",))),
           "A-to-B-to-A reused trust scope accepted")


def _surface_and_proof_contract() -> None:
    """Verify SPDX headers, heap-free C17 surface, and WitnessContinuity.v theorems."""
    for path in (WV_H, WV_C, WV_TEST_C, WV_README, PROOFS_V):
        ensure(path.is_file(), f"missing witness-validator artifact: {path}")

    for c_path in (WV_H, WV_C, WV_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        ensure(first_line == "// SPDX-License-Identifier: Apache-2.0",
               f"missing // SPDX header in {c_path}")
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden heap allocator {forbidden} in {c_path}")

    c_src = WV_C.read_text(encoding="utf-8")
    for fn in (
        "vos_wv_policy_is_wellformed",
        "vos_wv_policy_is_safe",
        "vos_wv_parse_policy",
        "vos_wv_parse_checkpoint",
        "vos_wv_parse_signature",
        "vos_wv_parse_certificate",
        "vos_wv_parse_transition",
        "vos_wv_parse_rebootstrap",
        "vos_wv_verify_certificate",
        "vos_wv_admit",
        "vos_wv_transition",
        "vos_wv_rebootstrap",
    ):
        ensure(fn in c_src, f"missing C entry point {fn}")

    v_src = PROOFS_V.read_text(encoding="utf-8")
    for sym in (
        "safe_matches_the_register_spelling",
        "enrolled_keys_identify_witnesses",
        "honest_intersection",
        "certifiedb",
        "transition_okb",
        "rebootstrap_okb",
        "one_of_two_is_refused_and_the_fork_is_real",
        "shared_prefix_transition_is_refused_and_forks",
        "a_reused_trust_scope_is_refused",
    ):
        ensure(sym in v_src, f"missing Rocq specification symbol {sym} in WitnessContinuity.v")
    v_clean = strip_comments(v_src)
    for banned in ("Admitted", "admit", "Axiom", "Parameter", "Conjecture"):
        ensure(
            re.search(rf"\b{banned}\b", v_clean) is None,
            f"forbidden proof keyword {banned} in WitnessContinuity.v",
        )


def _supports_flags(compiler: str, flags: list[str], scratch: Path) -> bool:
    probe_c = scratch / "_probe.c"
    probe_bin = scratch / "_probe"
    probe_c.write_text("int main(void) { return 0; }\n", encoding="utf-8", newline="\n")
    built = subprocess.run(
        [compiler, *flags, str(probe_c), "-o", str(probe_bin)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if built.returncode != 0:
        return False
    ran = subprocess.run([str(probe_bin)], capture_output=True, text=True, timeout=30, check=False)
    return ran.returncode == 0


def _compile_and_run(compiler: str, flags: list[str], src_c: Path,
                     out_bin: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            compiler,
            *flags,
            f"-I{WV_H.parent}",
            f"-I{CRYPTO_INCLUDE}",
            str(src_c),
            str(CRYPTO_SOURCE),
            str(WV_TEST_C),
            "-o",
            str(out_bin),
        ],
        capture_output=True, text=True, timeout=60, check=False,
    )


def _mutants(source: str) -> list[tuple[str, str, str]]:
    def replaced(before: str, after: str, label: str) -> str:
        ensure(source.count(before) == 1, f"mutant anchor missing or non-unique ({label}): {before!r}")
        return source.replace(before, after, 1)

    return [
        (
            "drop-2k-gt-n-plus-f",
            replaced(
                "    return ((uint64_t)2u * (uint64_t)policy->k) >\n"
                "           ((uint64_t)policy->n + (uint64_t)policy->f);",
                "    return 1;",
                "drop-2k-gt-n-plus-f",
            ),
            "1-of-2",
        ),
        (
            "allow-duplicate-signer",
            replaced(
                "        if (seen_signers[enrolled_idx] != 0u) {\n"
                "            return VOS_WV_ERR_DUPLICATE_SIGNER;\n"
                "        }",
                "        if (0 && seen_signers[enrolled_idx] != 0u) {\n"
                "            return VOS_WV_ERR_DUPLICATE_SIGNER;\n"
                "        }",
                "allow-duplicate-signer",
            ),
            "duplicate signer",
        ),
        (
            "skip-key-id-binding",
            replaced(
                "        if (!equal_bytes_ct(sig->signer_key,\n"
                "                            policy->witnesses[enrolled_idx].verify_key,\n"
                "                            VOS_WV_KEY_BYTES)) {\n"
                "            return VOS_WV_ERR_KEY_MISMATCH;\n"
                "        }",
                "        if (0 && !equal_bytes_ct(sig->signer_key,\n"
                "                                 policy->witnesses[enrolled_idx].verify_key,\n"
                "                                 VOS_WV_KEY_BYTES)) {\n"
                "            return VOS_WV_ERR_KEY_MISMATCH;\n"
                "        }",
                "skip-key-id-binding",
            ),
            "wrong signer key",
        ),
        (
            "skip-policy-binding",
            replaced(
                "            !equal_hashes(&sig->policy_digest, &expected_policy_dig) ||",
                "            (0 && !equal_hashes(&sig->policy_digest, &expected_policy_dig)) ||",
                "skip-policy-binding",
            ),
            "different policy parameters",
        ),
        (
            "skip-hmac-check",
            replaced(
                "        if (!equal_bytes_ct(sig->mac, expected_mac, VOS_WV_DIGEST_BYTES)) {\n"
                "            return VOS_WV_ERR_FORGED_MAC;\n"
                "        }",
                "        if (0 && !equal_bytes_ct(sig->mac, expected_mac, VOS_WV_DIGEST_BYTES)) {\n"
                "            return VOS_WV_ERR_FORGED_MAC;\n"
                "        }",
                "skip-hmac-check",
            ),
            "forged HMAC",
        ),
        (
            "accept-padded-bad-sig",
            replaced(
                "        seen_signers[enrolled_idx] = 1u;\n"
                "        valid_count += 1u;",
                "        seen_signers[enrolled_idx] = 1u;\n"
                "        valid_count += 1u;\n"
                "        if (valid_count >= policy->k) {\n"
                "            return VOS_WV_OK;\n"
                "        }",
                "accept-padded-bad-sig",
            ),
            "padded",
        ),
        (
            "skip-pin-prefix-check",
            replaced(
                "    if (!vos_wv_checkpoint_extends(checkpoint, &client->pinned)) {\n"
                "        return VOS_WV_ERR_CHECKPOINT_STALE;\n"
                "    }",
                "    if (0 && !vos_wv_checkpoint_extends(checkpoint, &client->pinned)) {\n"
                "        return VOS_WV_ERR_CHECKPOINT_STALE;\n"
                "    }",
                "skip-pin-prefix-check",
            ),
            "forked checkpoint",
        ),
        (
            "skip-base-inclusion",
            replaced(
                "    if (!vos_wv_checkpoint_contains(checkpoint, base_image_root)) {\n"
                "        return VOS_WV_ERR_MISSING_BASE;\n"
                "    }",
                "    if (0 && !vos_wv_checkpoint_contains(checkpoint, base_image_root)) {\n"
                "        return VOS_WV_ERR_MISSING_BASE;\n"
                "    }",
                "skip-base-inclusion",
            ),
            "missing base_image_root",
        ),
        (
            "skip-package-inclusion",
            replaced(
                "    for (size_t i = 0u; i < package_count; ++i) {\n"
                "        if (!vos_wv_checkpoint_contains(checkpoint, &package_ids[i])) {\n"
                "            return VOS_WV_ERR_MISSING_PACKAGE;\n"
                "        }\n"
                "    }",
                "    (void)package_ids;\n"
                "    (void)package_count;",
                "skip-package-inclusion",
            ),
            "missing package identity",
        ),
        (
            "mutate-pin-before-refusal",
            replaced(
                "    for (size_t i = 0u; i < package_count; ++i) {\n"
                "        if (!vos_wv_checkpoint_contains(checkpoint, &package_ids[i])) {\n"
                "            return VOS_WV_ERR_MISSING_PACKAGE;\n"
                "        }\n"
                "    }\n\n"
                "    client->pinned = *checkpoint;",
                "    client->pinned = *checkpoint;\n"
                "    for (size_t i = 0u; i < package_count; ++i) {\n"
                "        if (!vos_wv_checkpoint_contains(checkpoint, &package_ids[i])) {\n"
                "            return VOS_WV_ERR_MISSING_PACKAGE;\n"
                "        }\n"
                "    }",
                "mutate-pin-before-refusal",
            ),
            "missing package refusal preserved client",
        ),
        (
            "skip-old-terminal-quorum",
            replaced(
                "    st = vos_wv_verify_certificate(&tr->old_policy,\n"
                "                                   VOS_WV_STMT_TERMINAL,\n"
                "                                   &tr->anchor,\n"
                "                                   tr,\n"
                "                                   old_seals,\n"
                "                                   old_seal_count);\n"
                "    if (st != VOS_WV_OK) {\n"
                "        return st;\n"
                "    }",
                "    (void)old_seals;\n"
                "    (void)old_seal_count;",
                "skip-old-terminal-quorum",
            ),
            "prefix-only transition",
        ),
        (
            "allow-nonconsecutive-epoch",
            replaced(
                "    if (tr->old_policy.epoch == UINT64_MAX ||\n"
                "        tr->new_policy.epoch != tr->old_policy.epoch + 1u) {\n"
                "        return 0;\n"
                "    }",
                "    if (tr->new_policy.epoch <= tr->old_policy.epoch) {\n"
                "        return 0;\n"
                "    }",
                "allow-nonconsecutive-epoch",
            ),
            "nonconsecutive epoch",
        ),
        (
            "skip-rebootstrap-auth",
            replaced(
                "    if (!equal_bytes_ct(rb->auth_mac, expected_mac, VOS_WV_DIGEST_BYTES)) {\n"
                "        return VOS_WV_ERR_UNAUTHENTICATED;\n"
                "    }",
                "    if (0 && !equal_bytes_ct(rb->auth_mac, expected_mac, VOS_WV_DIGEST_BYTES)) {\n"
                "        return VOS_WV_ERR_UNAUTHENTICATED;\n"
                "    }",
                "skip-rebootstrap-auth",
            ),
            "unauthenticated rebootstrap",
        ),
        (
            "allow-reused-trust-scope",
            replaced(
                "    if (scope_already_seen(client, rb->new_policy.trust_scope)) {\n"
                "        return VOS_WV_ERR_SCOPE_REUSED;\n"
                "    }",
                "    if (0 && scope_already_seen(client, rb->new_policy.trust_scope)) {\n"
                "        return VOS_WV_ERR_SCOPE_REUSED;\n"
                "    }",
                "allow-reused-trust-scope",
            ),
            "scope",
        ),
        (
            "ignore-trailing-wire-bytes",
            replaced(
                "    if (len > VOS_WV_SIGNATURE_WIRE_BYTES) {\n"
                "        return VOS_WV_ERR_TRAILING_BYTES;\n"
                "    }",
                "    if (0 && len > VOS_WV_SIGNATURE_WIRE_BYTES) {\n"
                "        return VOS_WV_ERR_TRAILING_BYTES;\n"
                "    }",
                "ignore-trailing-wire-bytes",
            ),
            "trailing wire bytes in signature",
        ),
    ]


def _native_c_and_mutation_controls() -> None:
    """Compile and run witness-validator C17 tests under Clang + GCC ASan/UBSan and kill all mutants."""
    if sys.platform == "win32":
        return

    clang = shutil.which("clang")
    gcc = shutil.which("gcc")
    ensure(clang is not None, "clang is required in Linux guest")
    ensure(gcc is not None, "gcc is required in Linux guest")
    if clang is None or gcc is None:
        return

    strict_flags = [
        "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes", "-pedantic",
    ]
    asan_flags = [*strict_flags, "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]

    work = toolenv.environment(ROOT, sys.platform).parent / "witness-validator-c-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wv-", dir=work) as td:
        tmp = Path(td)
        ensure(_supports_flags(gcc, asan_flags, tmp), "gcc ASan/UBSan runtime required")

        # 1. Strict Clang C17 build and run
        clang_bin = tmp / "test_wv_clang"
        clang_built = _compile_and_run(clang, strict_flags, WV_C, clang_bin)
        ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
        clang_ran = subprocess.run(
            [str(clang_bin)], capture_output=True, text=True, timeout=60, check=False,
        )
        ensure(clang_ran.returncode == 0 and "witness_validator_test: ok" in clang_ran.stdout,
               f"clang test run failed: {clang_ran.stderr or clang_ran.stdout}")

        # 2. Strict GCC C17 + ASan/UBSan build and run
        gcc_bin = tmp / "test_wv_gcc_san"
        gcc_built = _compile_and_run(gcc, asan_flags, WV_C, gcc_bin)
        ensure(gcc_built.returncode == 0, f"gcc ASan/UBSan build failed: {gcc_built.stderr}")
        gcc_ran = subprocess.run(
            [str(gcc_bin)], capture_output=True, text=True, timeout=60, check=False,
        )
        ensure(gcc_ran.returncode == 0 and "witness_validator_test: ok" in gcc_ran.stdout,
               f"gcc ASan/UBSan test run failed: {gcc_ran.stderr or gcc_ran.stdout}")

        # 3. Behavioral mutation controls under GCC ASan/UBSan
        source = WV_C.read_text(encoding="utf-8")
        mutants = _mutants(source)
        ensure(len(mutants) >= 10, f"expected >= 10 mutants, got {len(mutants)}")
        for label, mutated_source, expected_diag in mutants:
            mutant_c = tmp / f"mutant_{label}.c"
            mutant_c.write_text(mutated_source, encoding="utf-8", newline="\n")
            mutant_bin = tmp / f"mutant_{label}"
            m_built = _compile_and_run(gcc, asan_flags, mutant_c, mutant_bin)
            ensure(m_built.returncode == 0, f"stillborn mutant {label}: {m_built.stderr}")
            m_ran = subprocess.run(
                [str(mutant_bin)], capture_output=True, text=True, timeout=60, check=False,
            )
            ensure(
                m_ran.returncode != 0 and expected_diag in m_ran.stderr,
                f"mutant survived or missed expected diagnostic ({label}): {m_ran.stderr or m_ran.stdout}",
            )


def cases() -> list[Case]:
    return [
        Case("witness_validator_wire_and_continuity_oracle", _oracle_wire_and_continuity, lane="any"),
        Case("witness_validator_surface_and_proof_contract", _surface_and_proof_contract, lane="any"),
        Case("witness_validator_native_c_and_mutation_controls", _native_c_and_mutation_controls, lane="guest"),
    ]
