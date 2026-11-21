# SPDX-License-Identifier: Apache-2.0
"""New host-generated rows reject missing, stale and unindexed bytes and queue repair."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import block_authority, commands, composition, corpus
from vos.checks import Context, generated
from vos.register import Artifacts, Register
from vos.report import Reporter

ROOT = TOOLS.parent


def _rows() -> None:
    for path in (block_authority.ARTIFACT, commands.LANE_REFERENCE):
        rows = [row for row in generated.GENERATED if row.path == path]
        ensure(len(rows) == 1 and rows[0].lane == "host" and rows[0].emit is not None,
               f"{path}: no unique host-generated row")
        row = rows[0]
        with tempfile.TemporaryDirectory(prefix="vos-generated-row-") as temporary:
            root = Path(temporary)
            if path == block_authority.ARTIFACT:
                for owner in block_authority.OWNERS:
                    target = root / owner
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((ROOT / owner).read_bytes())
            # The row's emitter is the checked function; no complete checker or repair runs.
            emitter = row.emit
            if emitter is None:
                raise AssertionError("row lost its emitter")
            expected = emitter(root, None)
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            context = Context(root, corpus.Corpus(root, [], {}, [path]), Register(), Artifacts(), Reporter(), fix=True)
            for content in (None, expected + "\n"):
                if content is None:
                    if target.exists():
                        target.unlink()
                else:
                    target.write_text(content, encoding="utf-8", newline="\n")
                context.fixed.clear()
                reading = generated._host_row(context, row, None)
                ensure(bool(reading.findings) and context.fixed.get(path) == expected,
                       f"{path}: missing or stale bytes escaped the integration repair")
            target.write_text(expected, encoding="utf-8", newline="\n")
            ensure(not generated._host_row(context, row, None).findings, "fresh generated row refused")
            context.corpus = corpus.Corpus(root, [], {}, [], indexed=set())
            context.fixed.clear()
            ensure(bool(generated._host_row(context, row, None).findings) and not context.fixed,
                   "unindexed generated artifact acquired passing evidence or repair")


def _projections() -> None:
    paths = [f"{composition.GENERATED}/{name}" for name in composition.OUTPUTS]
    rows = tuple(row for row in generated.GENERATED if row.path in paths)
    ensure([row.path for row in rows] == paths, "K-88 must register the complete ordered projection set")
    with tempfile.TemporaryDirectory(prefix="vos-generated-projections-") as temporary:
        root = Path(temporary)
        (root / composition.GENERATED).mkdir(parents=True)
        owner = root / "source"
        owner.write_bytes(b"first")
        for name, path in zip(composition.OUTPUTS[:-1], paths[:-1], strict=True):
            (root / path).write_bytes(b"first " + name.encode())

        def project(checkout: Path) -> dict[str, bytes]:
            data = (checkout / "source").read_bytes()
            return {name: data + b" " + name.encode() for name in composition.OUTPUTS}

        indexed = set(paths[1:])
        ctx = Context(root, corpus.Corpus(root, [], {}, paths, indexed=indexed),
                      Register(), Artifacts(), Reporter(), fix=True)
        # One unindexed row, one stale member, one missing file, and two current members.
        (root / paths[1]).write_bytes(b"frost")
        with (patch.object(generated, "GENERATED", rows),
              patch.object(composition, "projections", wraps=project) as emit):
            generated.run(ctx)
            ensure(emit.call_count == 1, "regenerated the complete projection set for a sibling row")
            ensure(ctx.rep.findings == 3 and ctx.fixed == {
                paths[1]: "first " + composition.OUTPUTS[1], paths[-1]: "first " + composition.OUTPUTS[-1]},
                   f"mixed projection drift: {ctx.rep.out}")
            findings = [line.strip() for line in ctx.rep.out if line.startswith("       ")]
            ensure(len(findings) == 3 and findings[0].startswith(paths[0])
                   and "index does not carry it" in findings[0]
                   and findings[1].startswith(paths[1]) and "line 1, byte 1 of " in findings[1]
                   and findings[2].startswith(paths[-1]) and "line 1, byte 0 of " in findings[2],
                   f"projection diagnostics changed: {findings}")

            owner.write_bytes("next\n\u03b2".encode())
            ctx.fixed.clear()
            ctx.rep = Reporter()
            generated.run(ctx)
            ensure(emit.call_count == 2 and ctx.fixed == {
                path: "next\n\u03b2 " + name for path, name in zip(paths[1:], composition.OUTPUTS[1:], strict=True)},
                   "another check must derive its repair bytes from the current source")

            owner.unlink()
            ctx.fixed.clear()
            ctx.rep = Reporter()
            generated.run(ctx)
            failures = [line.strip() for line in ctx.rep.out if "generator for " in line]
            ensure(len(failures) == len(indexed) and not ctx.fixed
                   and all(line.startswith(f"the generator for {path} raised: production composition "
                                           "input cannot be read: ")
                           for line, path in zip(failures, paths[1:], strict=True)),
                   f"a generator refusal must reach every indexed row: {failures}")


def cases() -> list[Case]:
    return [Case("block authority and command lanes bind generated bytes", _rows),
            Case("composer projections use one fresh emission per check", _projections)]
