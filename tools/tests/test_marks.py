# SPDX-License-Identifier: Apache-2.0
"""SPDX checks bind the policy declaration and retain opening-window diagnostics."""

import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import corpus
from vos.checks import Context, marks
from vos.register import Artifacts, Register
from vos.report import Reporter

INDEPENDENT_CASES = True

LICENSE = "Apache-2.0"
MARK = f"# SPDX-License-Identifier: {LICENSE}"
FENCE = chr(96) * 3
DECLARATION = f"{FENCE}text\n{MARK}\n{FENCE}\n"


def _license_declaration() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-marks-policy-") as temp:
        root = Path(temp)
        rel = "source.py"
        (root / rel).write_text(MARK + "\n", encoding="utf-8")
        for raw, clean in (
            (f"An example mentions SPDX-License-Identifier: MIT.\n\n{DECLARATION}", True),
            (DECLARATION.replace("\n", "\r\n"), True),
            (DECLARATION.replace(LICENSE, f"{LICENSE} OR MIT"), False),
            (f"{DECLARATION}\n{DECLARATION}", False),
            (f"{MARK}\n", False),
        ):
            doc = corpus.from_text(raw, marks.LICENSE_MAP)
            source = corpus.Corpus(root, [doc], {}, [marks.LICENSE_MAP, rel])
            ctx = Context(root, source, Register(), Artifacts(), Reporter())
            marks.run(ctx)
            verdict = "ok" if clean else "FAIL"
            ensure(any(line.startswith(f"{verdict} K-52:") for line in ctx.rep.out),
                   f"licensing declaration gave an unexpected verdict for {raw!r}")


def _opening_window() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-marks-source-") as temp:
        root = Path(temp)
        rel = "source.py"
        path = root / rel
        header = MARK.encode()
        fixtures = (
            (b"\r\n" * (marks.DEPTH - 1) + header, None),
            ("\u2028".encode() * (marks.DEPTH - 1) + header, None),
            (b"\n" * marks.DEPTH + header, f"marked at line {marks.DEPTH + 1}"),
            (b"//" + header[1:], "wrong syntax"),
            (header.replace(LICENSE.encode(), b"MIT"), "marked `MIT`"),
            (b"unmarked\n", "carries no license mark"),
            (header + b"\n" + b"x" * 16384 + b"\xff", "unreadable"),
        )
        for payload, diagnostic in fixtures:
            path.write_bytes(payload)
            finding = marks._fault(root, rel, LICENSE)
            if diagnostic is None:
                ensure(finding is None, f"opening mark had a finding: {finding}")
            else:
                ensure(finding is not None and diagnostic in finding,
                       f"missing {diagnostic!r} finding: {finding}")


def cases() -> list[Case]:
    return [Case("canonical-license-declaration", _license_declaration),
            Case("bounded-opening-mark-window", _opening_window)]
