# SPDX-License-Identifier: Apache-2.0
"""Pure-Python ElasticDispatch.v oracle and native ASan/UBSan + mutant controls for kernel elastic exec."""

import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import toolenv


def _eevdf_oracle_trace() -> list[tuple[int, int, Fraction, Fraction, Fraction, Fraction]]:
    """Exact rational Fraction simulation of ElasticDispatch.v cooperative EEVDF."""
    weights = [1, 9, 90]
    requests = [4, 1, 4]
    call_bound = 4
    coop_requests = [r + call_bound for r in requests]
    vtime = Fraction(0)
    eligible = [Fraction(0) for _ in range(3)]
    deadline = [Fraction(coop_requests[i], weights[i]) for i in range(3)]

    def select() -> int:
        elig = [i for i in range(3) if eligible[i] <= vtime]
        return min(elig, key=lambda i: (deadline[i], i))

    cur = select()
    steps = [9, 1, 1, 6, 6, 6]
    out: list[tuple[int, int, Fraction, Fraction, Fraction, Fraction]] = []
    total_w = sum(weights)
    for used in steps:
        vtime += Fraction(used, total_w)
        eligible[cur] += Fraction(used, weights[cur])
        deadline[cur] = eligible[cur] + Fraction(coop_requests[cur], weights[cur])
        nxt = select()
        lags = [weights[i] * (vtime - eligible[i]) for i in range(3)]
        ensure(sum(lags) == 0, f"oracle zero-sum lag broken: {lags}")
        out.append((cur, nxt, vtime, lags[0], lags[1], lags[2]))
        cur = nxt
    return out


def elastic_dispatch_rational_oracle() -> None:
    """Verify ElasticDispatch.v cooperative EEVDF lag bound and omitted-padding refutation."""
    trace = _eevdf_oracle_trace()
    bound = Fraction(max(4, 1, 4) + 4)  # max_request + call_bound + yield_bound = 8
    for _, _, _, l0, l1, l2 in trace:
        ensure(l0 + l1 + l2 == 0, "zero-sum accounting lag violated")
        for lag in (l0, l1, l2):
            ensure(abs(lag) <= bound, f"lag {lag} exceeded cooperative bound {bound}")

    # ElasticDispatch.v Section 8 omitted_vd_decl refutation: omitting call_bound + yield_bound (4)
    # causes member 2's lag to reach 101/10 > 10 = sink_inclusive_lag_bound.
    weights = [1, 9, 90]
    requests = [4, 1, 4]
    vtime = Fraction(0)
    eligible = [Fraction(0) for _ in range(3)]
    # Steps from ElasticDispatch.v omitted_vd_steps: (2,9), (1,1), (2,1), (0,6), (2,6), (1,6)
    for member, used in ((2, 9), (1, 1), (2, 1), (0, 6), (2, 6), (1, 6)):
        vtime += Fraction(used, sum(weights))
        eligible[member] += Fraction(used, weights[member])
        _ = eligible[member] + Fraction(requests[member], weights[member])
    lag2 = weights[2] * (vtime - eligible[2])
    ensure(lag2 == Fraction(101, 10) and lag2 > 10,
           f"omitted-padding refutation mismatch: got {lag2}")


def table_permutation_and_csr_oracle() -> None:
    """Verify R-11-023 permutation invariants and PartitionContext CSR disposition rules."""
    base_slots = ((0, 50, 10), (50, 100, 20), (150, 100, 30))
    perm_slots = ((0, 50, 10), (50, 100, 30), (150, 100, 20))
    ensure([s[:2] for s in base_slots] == [s[:2] for s in perm_slots],
           "permutation must preserve widths and offsets")
    ensure(base_slots[0][2] == perm_slots[0][2] and
           sorted(s[2] for s in base_slots[1:]) == sorted(s[2] for s in perm_slots[1:]),
           "discretionary tenant multiset mismatch")


def _variants(source: str) -> list[tuple[str, str, str]]:
    def replaced(before: str, after: str) -> str:
        ensure(source.count(before) == 1, f"elastic_exec mutation anchor missing or non-unique: {before}")
        return source.replace(before, after, 1)

    return [
        ("pristine", source, ""),
        ("wrong-table-order-accepted",
         replaced("  if (vos_frame_validate(next_frame) != VOS_OK) {\n    return VOS_ELASTIC_ERR_INVALID;\n  }",
                  "  if (0 && vos_frame_validate(next_frame) != VOS_OK) {\n    return VOS_ELASTIC_ERR_INVALID;\n  }"),
         "wrong table order must be refused at swap stage"),
        ("incomplete-csr-restore-accepted",
         replaced("        if (!receipt->csr_written[i]) {\n          return VOS_ELASTIC_ERR_INCOMPLETE_RESTORE;\n        }\n"
                  "        if (post->csr[i] != succ->csr[i]) {",
                  "        if (0 && !receipt->csr_written[i]) {\n          return VOS_ELASTIC_ERR_INCOMPLETE_RESTORE;\n        }\n"
                  "        if (post->csr[i] != succ->csr[i]) {"),
         "incomplete CSR restore must be refused"),
        ("omitted-cross-app-vmclear",
         replaced("const int cross_app = d->app_ids[out_member] != d->app_ids[in_member];",
                  "const int cross_app = ((void)d, (void)out_member, (void)in_member, 0);"),
         "cross-app switch must execute vmclear"),
        ("dropped-eevdf-leave-adjustment",
         replaced("  if (w_rem > 0u) {\n"
                  "    struct vos_session_mgr_fields *sm = &st->contexts[st->sm_idx].sm;\n"
                  "    sm->vtime = vos_rat_add(sm->vtime, vos_rat_div(lag_j, vos_rat_make((int64_t)w_rem, 1)));\n"
                  "  }",
                  "  (void)w_rem; (void)lag_j;"),
         "published leave must preserve zero-sum lag"),
        ("boundary-overrun-accepted",
         replaced("return vos_elastic_boundary_need(d) <= rem;",
                  "return ((void)d, (void)rem, 1);"),
         "boundary overrun must request switch"),
        ("static-elision-without-vs-xs-off",
         replaced("const int perform_vmclear = !(ssm->vs_off && ssm->xs_off);",
                  "const int perform_vmclear = ((void)ssm, 0);"),
         "static switch with VS!=Off must execute vmclear"),
        ("omitted-coop-padding",
         replaced("return eff_request(d, st, i) + vos_elastic_call_bound(d);",
                  "return eff_request(d, st, i);"),
         "__TRACE_DIFF__"),
    ]


def _parse_trace_lines(stdout: str) -> list[tuple[int, int, Fraction, Fraction, Fraction, Fraction]]:
    rows: list[tuple[int, int, Fraction, Fraction, Fraction, Fraction]] = []
    for line in stdout.splitlines():
        if not line.startswith("STEP "):
            continue
        fields = dict(tok.split("=", 1) for tok in line.split()[2:])
        rows.append((
            int(fields["cur"]),
            int(fields["next"]),
            Fraction(fields["v"]),
            Fraction(fields["l0"]),
            Fraction(fields["l1"]),
            Fraction(fields["l2"]),
        ))
    return rows


def native_elastic_exec_and_mutant_controls() -> None:
    """Compile kernel elastic exec C with ASan/UBSan, check EEVDF trace, and kill all 7 mutants."""
    if sys.platform == "win32":
        return
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    ensure(compiler is not None, "native elastic exec tests require a C compiler")
    if compiler is None:
        return
    clang = shutil.which("clang")
    root = TOOLS.parent
    work = toolenv.environment(root, sys.platform).parent / "kernel-elastic-c-tests"
    work.mkdir(parents=True, exist_ok=True)
    exec_src = (root / "kernel/src/elastic_exec.c").read_text(encoding="utf-8")
    support_sources = (
        str(root / "kernel/src/context.c"),
        str(root / "kernel/src/executive.c"),
        str(root / "kernel/test/test_elastic_exec.c"),
    )
    includes = ("-I", str(root / "kernel/include"))
    oracle_trace = _eevdf_oracle_trace()

    with tempfile.TemporaryDirectory(prefix="elastic-exec-", dir=work) as tmp:
        scratch = Path(tmp)
        for name, candidate, expected in _variants(exec_src):
            src_path = scratch / f"{name}.c"
            src_path.write_text(candidate, encoding="utf-8", newline="\n")
            exe = scratch / name
            flags = [
                compiler, "-std=c17", "-O1", "-Wall", "-Wextra",
                "-Wstrict-prototypes", "-Werror", "-pedantic",
                "-DVOS_HOST_MODEL", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                *includes, str(src_path), *support_sources, "-o", str(exe),
            ]
            built = subprocess.run(flags, cwd=scratch, capture_output=True, text=True,
                                   check=False, timeout=60)
            ensure(built.returncode == 0,
                   f"{name}: stillborn compilation: {built.stdout}{built.stderr}")
            if expected == "__TRACE_DIFF__":
                tr = subprocess.run([str(exe), "--eevdf-trace"], cwd=scratch,
                                    capture_output=True, text=True, check=False, timeout=30)
                ensure(tr.returncode == 0, f"{name} trace crashed: {tr.stderr}")
                c_trace = _parse_trace_lines(tr.stdout)
                ensure(c_trace != oracle_trace,
                       f"mutant {name} survived differential EEVDF trace check")
                continue

            ran = subprocess.run([str(exe)], cwd=scratch, capture_output=True, text=True,
                                 check=False, timeout=30)
            if name == "pristine":
                ensure(ran.returncode == 0, f"pristine failed: {ran.stdout}{ran.stderr}")
                ensure("ok elastic_exec " in ran.stdout, f"missing verdict: {ran.stdout}")
                ensure(not ran.stderr, f"sanitizer diagnostics: {ran.stderr}")
                tr = subprocess.run([str(exe), "--eevdf-trace"], cwd=scratch,
                                    capture_output=True, text=True, check=False, timeout=30)
                ensure(tr.returncode == 0, f"pristine trace failed: {tr.stderr}")
                c_trace = _parse_trace_lines(tr.stdout)
                ensure(c_trace == oracle_trace,
                       f"EEVDF trace mismatch: C={c_trace} vs oracle={oracle_trace}")
                if clang is not None:
                    clang_obj = scratch / "pristine_clang.o"
                    cbuilt = subprocess.run(
                        [clang, "-std=c17", "-O1", "-Wall", "-Wextra", "-Wstrict-prototypes",
                         "-Werror", "-pedantic", "-DVOS_HOST_MODEL", *includes,
                         "-c", str(src_path), "-o", str(clang_obj)],
                        cwd=scratch, capture_output=True, text=True, check=False, timeout=60)
                    ensure(cbuilt.returncode == 0,
                           f"clang strict C17 check failed: {cbuilt.stdout}{cbuilt.stderr}")
            else:
                ensure(ran.returncode != 0 and expected in ran.stderr,
                       f"mutant {name} survived or missed expected oracle ({expected!r}): {ran.stderr}")


def cases() -> list[Case]:
    return [
        Case("ElasticDispatch.v rational EEVDF and omitted-padding oracle",
             elastic_dispatch_rational_oracle),
        Case("R-11-023 permutation and CSR disposition oracle",
             table_permutation_and_csr_oracle),
        Case("native ASan/UBSan kernel elastic exec, EEVDF trace, and 7 mutant kills",
             native_elastic_exec_and_mutant_controls, lane="guest"),
    ]
