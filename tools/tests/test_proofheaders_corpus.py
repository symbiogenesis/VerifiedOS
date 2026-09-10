# SPDX-License-Identifier: Apache-2.0
"""The selftest corpus sweep reports defects and never writes through its template."""

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from tests.test_memplan import _TOY
from tests.test_proofheaders import _SOURCE, _register
from vos import memplan, proofheaders
from vos.checks import Context, headers
from vos.cli import selftest
from vos.register import REGISTER


@contextmanager
def _fixture(crlf: bool = False) -> Iterator[tuple[selftest.Sandbox, dict[str, bytes]]]:
    reg = _register()
    sources = {
        memplan.SOURCE: _SOURCE.replace("Fixture.v", "MemoryPlan.v") + _TOY,
        "proofs/Other.v": _SOURCE.replace("Fixture.v", "Other.v"),
    }
    if crlf:
        sources = {rel: text.replace("\n", "\r\n") for rel, text in sources.items()}
    files = {rel: proofheaders.render(text, reg) for rel, text in sources.items()}
    files[REGISTER] = "# Register\n\n## §1\n\n" + "\n\n".join(reg.body.values()) + "\n"
    files["proofs/RingContract.v"] = "(* separately generated owner *)\nDefinition ring := 1.\n"
    files[memplan.ARTIFACT] = memplan.emit(Path(), source_text=files[memplan.SOURCE])
    with sandbox_tree(files) as pristine, tempfile.TemporaryDirectory(prefix="vos-header-sweep-") as td:
        box = selftest.stand_up(pristine, Path(td) / "lane", fix_ok=True)
        # Simulate the earlier repair's reset, including a linked dependent export.
        box.touched.update(files)
        box.reset()
        yield box, {rel: text.encode("utf-8") for rel, text in files.items()}


def _unchanged(box: selftest.Sandbox, original: dict[str, bytes]) -> None:
    for root in (box.path, box.pristine):
        ensure(all((root / rel).read_bytes() == data for rel, data in original.items()),
               f"the sweep or its cleanup changed source/template bytes under {root}")
    ensure(not box.touched, "the sweep left a mutation pending cleanup")


def _sweep_preserves_bytes_and_generated_owners() -> None:
    for crlf in (False, True):
        with _fixture(crlf) as (box, original):
            problems, out = selftest._proof_header_repair_path(box)
            ensure(not problems, f"the fixture sweep failed: {problems}")
            ensure(any("2 stale manifests detected and repaired" in line for line in out),
                   f"the report did not cover both authored sources: {out}")
            _unchanged(box, original)


def _missing_file_finding_fails_even_with_the_right_count() -> None:
    run = headers.run

    def omit_one(ctx: Context) -> None:
        run(ctx)
        if not ctx.fix:
            ctx.rep.out = [line for line in ctx.rep.out if "proofs/Other.v:" not in line]

    with _fixture() as (box, original), patch.object(headers, "run", side_effect=omit_one):
        problems, out = selftest._proof_header_repair_path(box)
        ensure(any("absent from the findings" in problem for problem in problems),
               f"the sweep accepted a missing proof finding: {out}")
        _unchanged(box, original)


def _premature_export_write_fails_without_changing_the_template() -> None:
    run = headers.run

    def publish_early(ctx: Context) -> None:
        run(ctx)
        if ctx.fix:
            (ctx.root / memplan.ARTIFACT).write_text("premature write", encoding="utf-8")

    with _fixture() as (box, original), patch.object(headers, "run", side_effect=publish_early):
        problems, out = selftest._proof_header_repair_path(box)
        ensure(any("published bytes before the checker flush" in problem for problem in problems),
               f"the sweep accepted an early write: {out}")
        _unchanged(box, original)


def cases() -> list[Case]:
    return [
        Case("corpus sweep preserves LF/CRLF bytes and generated owners",
             _sweep_preserves_bytes_and_generated_owners),
        Case("corpus sweep detects a missing per-file finding",
             _missing_file_finding_fails_even_with_the_right_count),
        Case("corpus sweep contains premature export writes",
             _premature_export_write_fails_without_changing_the_template),
    ]
