# SPDX-License-Identifier: Apache-2.0
"""Execute the bounded C resident adapter and its compiled defect controls."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv
from vos.corpus import find_root

SOURCE = "storage/src/resident_reads.c"
FIXTURE = "storage/test/resident_reads.c"
TRAFFIC_MARK = "    /* BEGIN_TRAFFIC: all persistent read stores are holder-private or output. */"


def _variants(source: str) -> list[tuple[str, str, str]]:
    def changed(before: str, after: str) -> str:
        ensure(source.count(before) == 1, "resident mutation anchor must be unique")
        return source.replace(before, after, 1)

    return [
        ("pristine", source, ""),
        ("common-counter", changed(TRAFFIC_MARK, TRAFFIC_MARK + "\n"
            "    PUT(o, VOS_RESIDENT_COMMON, o->common.next_token, o->common.next_token + 1);\n"
            "    PUT(o, VOS_RESIDENT_COMMON, o->common.next_token, o->common.next_token - 1);"),
            "classified traffic"),
        ("replacement-touch", changed(TRAFFIC_MARK, TRAFFIC_MARK + "\n"
            "    PUT(o, VOS_RESIDENT_COMMON, o->common.last_version, o->common.last_version + 1);"),
            "common state frame"),
        ("hidden-reacquire", changed(TRAFFIC_MARK, TRAFFIC_MARK + "\n"
            "    PUT(o, VOS_RESIDENT_COMMON, o->common.reservation[holder].live, 1U);"),
            "classified traffic"),
        ("wrong-domain", changed("domain != c->identity.domain || h->boot != c->boot ||",
            "((void)domain, h->boot != c->boot) ||"), "wrong domain"),
        ("no-auth", changed("if (!verify(verification, &id, snapshot, resident_length)) return 0;",
            "(void)verify(verification, &id, snapshot, resident_length);"),
            "actual-byte authentication"),
        ("completion-rebind", changed("!r.active || r.sequence != sequence || r.token != h->token ||",
            "!r.active || ((void)sequence, 0) || r.token != h->token ||"), "stale completion"),
        ("counter-overrun", changed("o->pending[holder].active || o->sequence[holder] >= o->common.limit",
            "o->pending[holder].active"), "counter exhaustion"),
        ("premature-zero", changed("PUT(o, VOS_RESIDENT_COMMON, o->common.accepting, 0U);\n    for (uint32_t holder",
            "PUT(o, VOS_RESIDENT_COMMON, o->common.bytes[0], 0U);\n"
            "    PUT(o, VOS_RESIDENT_COMMON, o->common.accepting, 0U);\n    for (uint32_t holder"),
            "quarantined unchanged backing"),
        ("renew-without-authority", changed(
            "if (o == 0 || !authority(o, h, domain, now)) return 0;",
            "if (o == 0 || h == 0 || h->holder >= VOS_RESIDENT_HOLDERS) return 0;\n"
            "    (void)domain; (void)now;"), "renewal refusal preserves both transfers"),
        ("renew-without-budget", changed(
            "r->renewed >= VOS_RESIDENT_RENEWALS || expires <= r->expires ||",
            "expires <= r->expires ||"), "renewal budget"),
        ("renew-pending-rebind", changed(
            "PUT(o, VOS_RESIDENT_COMMON, r->renewed, r->renewed + 1U);",
            "PUT(o, VOS_RESIDENT_COMMON, r->renewed, r->renewed + 1U);\n"
            "    PUT(o, VOS_RESIDENT_PRIVATE, o->pending[h->holder].token, h->token + 1);"),
            "renewal preserves exact handles and pending transfers"),
        ("close-without-cancellation", changed(
            "PUT(o, VOS_RESIDENT_PRIVATE, o->pending[holder].active, 0U);\n"
            "    PUT(o, VOS_RESIDENT_COMMON, r->live, 0U);",
            "PUT(o, VOS_RESIDENT_COMMON, r->live, 0U);"), "close cancels selected transfer"),
        ("close-peer-transfer", changed(
            "PUT(o, VOS_RESIDENT_COMMON, r->live, 0U);",
            "PUT(o, VOS_RESIDENT_COMMON, r->live, 0U);\n"
            "    PUT(o, VOS_RESIDENT_PRIVATE, o->pending[1U - holder].active, 0U);"),
            "close preserves peer"),
        ("stale-close", changed(
            "if (!r->live || domain != r->handle.identity.domain ||\n"
            "        !handle_equal(h, &r->handle)) return 0;",
            "if (!r->live || domain != r->handle.identity.domain ||\n"
            "        !identity_equal(&h->identity, &r->handle.identity)) return 0;"),
            "stale lifecycle cannot rebind successor"),
        ("close-releases-backing", changed(
            "PUT(o, VOS_RESIDENT_COMMON, r->live, 0U);",
            "PUT(o, VOS_RESIDENT_COMMON, r->live, 0U);\n"
            "    PUT(o, VOS_RESIDENT_COMMON, o->common.occupied, 0U);"),
            "close retains quarantined backing"),
        ("readmit-keeps-renewal-count", changed(
            "    PUT(o, VOS_RESIDENT_COMMON, c->reservation[holder].renewed, 0U);\n",
            ""), "readmission resets renewal bound"),
    ]


def resident_c_controls() -> None:
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    ensure(compiler is not None, "compiled resident controls require a native C compiler")
    if compiler is None:
        raise RuntimeError("no native C compiler")
    root = find_root()
    work = toolenv.environment(root, sys.platform).parent / "resident-c-tests"
    work.mkdir(parents=True, exist_ok=True)
    source = (root / SOURCE).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="resident-", dir=work) as directory:
        scratch = Path(directory)
        for name, candidate, expected in _variants(source):
            path = scratch / f"{name}.c"
            path.write_text(candidate, encoding="utf-8", newline="\n")
            executable = scratch / name
            compiled = subprocess.run([compiler, "-std=c17", "-O1", "-Wall", "-Wextra",
                "-Wstrict-prototypes",
                "-Werror", "-pedantic", "-I" + str(root / "storage/include"),
                str(path), str(root / "storage/src/node_image.c"), str(root / FIXTURE),
                "-o", str(executable)],
                capture_output=True, text=True, timeout=30, check=False)
            ensure(compiled.returncode == 0,
                   f"{name}: stillborn compilation is not an executed rejection: {compiled.stderr}")
            if compiled.returncode != 0:
                raise RuntimeError(f"{name} did not compile")
            result = subprocess.run([str(executable)], capture_output=True, text=True,
                                    timeout=30, check=False)
            if name == "pristine":
                ensure(result.returncode == 0, result.stderr)
                ensure("ok resident C payload, lifetime and stored-write controls" in result.stderr,
                       "pristine resident controls did not reach their success verdict")
            else:
                ensure(result.returncode != 0 and expected in result.stderr,
                       f"{name}: compiled control survived or missed its intended oracle: {result.stderr}")


def cases() -> list[Case]:
    return [Case("resident C payload, retention and executed defect controls",
                 resident_c_controls, lane="guest")]
