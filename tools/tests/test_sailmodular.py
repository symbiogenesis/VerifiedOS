# SPDX-License-Identifier: Apache-2.0
"""Fail-closed compiler-range partitioning and dependency identity checks."""

import hashlib
import json

from jsonschema import Draft202012Validator

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import sailmodular as subject


def _fixture() -> tuple[bytes, list[subject.Declaration]]:
    pieces = [(8, "helper", b"static int helper(int x) { return x + 1; }"),
              (9, "state", b"int state"),
              (21, "a", b'int Model::a() { const char *s = "}"; return helper(++state); }'),
              (21, "b", b"int Model::b() { return helper(state); }"),
              (24, "Model", b"Model::Model() { state = 3; }"),
              (25, "~Model", b"Model::~Model() {}")]
    raw = b'#include "sail_riscv_model.h"\nnamespace hart {\n'
    declarations = []
    for kind, name, code in pieces:
        begin = len(raw)
        declarations.append(subject.Declaration(kind, name, begin, begin + len(code),
                            begin + code.index(b"{") if kind != 9 else None, kind == 8))
        raw += code + (b";" if kind == 9 else b"") + b"\n"
    raw += b"}\n"
    return raw, declarations


def _refuses(raw: bytes, declarations: list[subject.Declaration], count: int = 2) -> None:
    try:
        subject.partition(raw, declarations, count)
    except ValueError:
        return
    raise AssertionError("unsupported partition was accepted")


def _single_owners() -> None:
    raw, declarations = _fixture()
    files, rows = subject.partition(raw, declarations, 2)
    ensure(len(rows) == 4, "method inventory changed")
    ensure(b"static int helper" not in files["owner.cpp"], "shared helper stayed internal")
    ensure(b"int helper(int x) { return x + 1; }" in files["owner.cpp"], "helper body changed")
    ensure(b"int state;" in files["owner.cpp"] and b"extern int state;" in files["shared.hpp"],
           "state does not have one definition and shared declaration")
    for declaration in declarations:
        if declaration.kind in subject.METHOD_KINDS:
            method = raw[declaration.begin:declaration.end]
            ensure(sum(value.count(method) for value in files.values()) == 1,
                   "a method was duplicated or its original bytes changed")
            row = next(item for item in rows if item["begin"] == declaration.begin)
            ensure(row["sha256"] == hashlib.sha256(method).hexdigest(), "method identity drift")
    ensure(all(b"int state;" not in files[name] for name in ("part0.cpp", "part1.cpp")),
           "state was duplicated into method libraries")


def _ranges() -> None:
    raw, declarations = _fixture()
    first = declarations[0]
    _refuses(raw, [first, first, *declarations[1:]])
    _refuses(raw, [subject.Declaration(8, "helper", -1, first.end, first.body), *declarations[1:]])
    _refuses(raw, [*declarations, subject.Declaration(9, "past", len(raw), len(raw) + 3)])
    _refuses(raw, [subject.Declaration(8, "helper", first.begin, first.end, first.end),
                   *declarations[1:]])


def _unsupported() -> None:
    raw, declarations = _fixture()
    state = declarations[1]
    for bad in (subject.Declaration(9, "state", state.begin, state.end, initialized=True),
                subject.Declaration(9, "state", state.begin, state.end, internal=True),
                subject.Declaration(2, "state", state.begin, state.end)):
        _refuses(raw, [declarations[0], bad, *declarations[2:]])
    _refuses(raw + b"#if FOO\n#endif\n", declarations)
    _refuses(raw.replace(b"static ", b"inline ", 1), declarations)
    _refuses(raw, declarations, 1)
    _refuses(raw, declarations, 17)
    _refuses(raw, declarations, 5)


def _deterministic() -> None:
    raw, declarations = _fixture()
    ensure(subject.partition(raw, declarations, 3) == subject.partition(raw, declarations[::-1], 3),
           "compiler callback order changes partition results")


def _freshness() -> None:
    with sandbox_tree({"dependency.h": "old\n"}) as root:
        source = root / "dependency.h"
        manifest = {str(source): hashlib.sha256(source.read_bytes()).hexdigest()}
        subject.verify_manifest(manifest)
        before = source.stat()
        source.write_bytes(b"new\n")
        import os  # noqa: PLC0415 (test-specific preserved-mtime mutation)
        os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
        try:
            subject.verify_manifest(manifest)
        except ValueError:
            pass
        else:
            raise AssertionError("changed dependency with preserved mtime was reused")
        source.unlink()
        try:
            subject.verify_manifest(manifest)
        except OSError:
            pass
        else:
            raise AssertionError("missing dependency was reused")


def _compile_database() -> None:
    with sandbox_tree({"compile_commands.json": "[]"}) as root:
        row = {"directory": str(root), "file": str(root / "sail_riscv_model.cpp"),
               "arguments": ["clang++", "-Ispace name", "-O2", "-o", "model.o", "-c",
                             str(root / "sail_riscv_model.cpp")]}
        database = root / "compile_commands.json"
        database.write_text(json.dumps([row]), encoding="utf-8")
        source, args, compiler = subject.compile_arguments(root)
        ensure(source.name == "sail_riscv_model.cpp" and args == ["-Ispace name", "-O2"]
               and compiler == "clang++", "compile database argument boundaries changed")
        database.write_text(json.dumps([row, row]), encoding="utf-8")
        try:
            subject.compile_arguments(root)
        except ValueError:
            pass
        else:
            raise AssertionError("duplicate compile database entry accepted")


def _schema() -> None:
    schema = json.loads((TOOLS / "sail-modular/report.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    digest = "0" * 64
    stage = {"name": "build", "command": ["cmake", "--build"], "exit_code": 0,
             "wall_seconds": 1.0, "log": "/native/build.log", "log_sha256": digest,
             "user_seconds": 1.0, "system_seconds": 0.1, "peak_rss_kib": 100}
    report = {"schema": 1, "verdict": "pass", "run": "/native/run", "limitations": "empirical",
              "partitions": 4, "methods": 4, "declarations": 6, "identity": {}, "manifest": {"input": digest},
              "build_jobs": 4, "compiler_cache": "disabled for both measured builds",
              "baseline_receipt": {}, "suite_cases": 1, "corpus": [{"name": "one", "records": 1,
              "trace_digest": digest, "elf_sha256": digest, "output_sha256": digest}],
              "stages": [stage] * 7, "artifacts": {"simulator": digest}}
    ensure(not list(validator.iter_errors(report)), "valid report rejected")
    report["partitions"] = 1
    ensure(bool(list(validator.iter_errors(report))), "invalid partition count accepted")


def _suite_membership() -> None:
    with sandbox_tree({"report.xml": '<testsuite><testcase name="one" status="run">'
                       '<system-out>result 42</system-out></testcase></testsuite>'}) as root:
        path = root / "report.xml"
        ensure(subject._suite(path, root) == {"one": ("run", "result 42")},
               "CTest output or status was discarded")
        for bad in ('<testsuite><testcase name="one"/><testcase name="one"/></testsuite>',
                    '<testsuite/>', '<!DOCTYPE testsuite><testsuite/>',
                    '<testsuite><testcase name="one"><system-out>[This part of the test output was removed '
                    'since it exceeds the threshold of 1024 bytes.]</system-out></testcase></testsuite>'):
            path.write_text(bad, encoding="utf-8")
            try:
                subject._suite(path, root)
            except ValueError:
                pass
            else:
                raise AssertionError("unsupported or empty CTest membership accepted")


def cases() -> list[Case]:
    return [Case("sailmodular: methods and shared state have single owners", _single_owners),
            Case("sailmodular: reject invalid compiler ranges", _ranges),
            Case("sailmodular: reject unsupported generated shapes", _unsupported),
            Case("sailmodular: deterministic balanced partitions", _deterministic),
            Case("sailmodular: byte-based dependency freshness", _freshness),
            Case("sailmodular: compile database boundaries", _compile_database),
            Case("sailmodular: exact CTest membership and output", _suite_membership),
            Case("sailmodular: qualification JSON schema", _schema)]
