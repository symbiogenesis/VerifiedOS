# SPDX-License-Identifier: Apache-2.0
"""Behavioral tests for the Q25w Span<byte> carrier and vela-first-slice lowering."""

import hashlib
import tempfile
from pathlib import Path
from typing import cast

from tests.harness import TOOLS, Case, ensure
from vos import compiler_diff as cd
from vos.vela import (
    elaborate as vela_elaborate,
)
from vos.vela import (
    first_slice as vela_first_slice,
)
from vos.vela.ast import VelaError

INDEPENDENT_CASES = True

type Node = dict[str, object]


class _Builder:
    """Minimal exact-source schema-2 AST builder for Span<byte> and contract tests."""

    def __init__(self, module: str) -> None:
        self.text = f"module {module};"
        self.module: Node = {"text": module, "span": [len("module "), len("module ") + len(module)]}
        self.declarations: list[Node] = []

    @property
    def offset(self) -> int:
        return len(self.text.encode("utf-8"))

    def write(self, chunk: str) -> None:
        self.text += chunk

    def name(self, text: str) -> Node:
        start = self.offset
        self.write(text)
        return {"text": text, "span": [start, self.offset]}

    def type_simple(self, name: str, *args: str) -> Node:
        start = self.offset
        name_node = self.name(name)
        arg_nodes: list[Node] = []
        if args:
            self.write("<")
            for idx, arg in enumerate(args):
                if idx:
                    self.write(", ")
                a_start = self.offset
                a_name = self.name(arg)
                arg_nodes.append({"kind": "type", "span": [a_start, self.offset], "name": a_name, "arguments": []})
            self.write(">")
        return {"kind": "type", "span": [start, self.offset], "name": name_node, "arguments": arg_nodes}

    def type_modified(self, modifier: str, name: str, *args: str) -> Node:
        start = self.offset
        self.write(modifier + " ")
        inner = self.type_simple(name, *args)
        return {
            "kind": "modified_type",
            "span": [start, self.offset],
            "modifier": modifier,
            "lifetime": None,
            "type": inner,
        }

    def nat_lit(self, digits: str, suffix: str) -> Node:
        start = self.offset
        self.write(digits + suffix)
        return {"kind": "nat", "span": [start, self.offset], "value": digits, "suffix": suffix}

    def bool_lit(self, val: bool) -> Node:
        start = self.offset
        self.write("true" if val else "false")
        return {"kind": "bool", "span": [start, self.offset], "value": val}

    def var(self, name: str) -> Node:
        start = self.offset
        n = self.name(name)
        return {"kind": "name", "span": [start, self.offset], "name": n}

    def member(self, recv_fn: object, field: str) -> Node:
        start = self.offset
        recv = cast("Node", recv_fn(self) if callable(recv_fn) else recv_fn)
        self.write(".")
        fname = self.name(field)
        return {"kind": "member", "span": [start, self.offset], "value": recv, "name": fname}

    def call_span(self, method: str, *arg_fns: object) -> Node:
        start = self.offset
        c_start = self.offset
        span_name = self.name("Span")
        recv: Node = {"kind": "name", "span": [c_start, self.offset], "name": span_name}
        self.write(".")
        m_name = self.name(method)
        callee: Node = {"kind": "member", "span": [c_start, self.offset], "value": recv, "name": m_name}
        self.write("(")
        args: list[Node] = []
        for idx, afn in enumerate(arg_fns):
            if idx:
                self.write(", ")
            a_start = self.offset
            val = cast("Node", afn(self) if callable(afn) else afn)
            args.append({"kind": "argument", "span": [a_start, self.offset], "label": None, "value": val})
        self.write(")")
        return {"kind": "call", "span": [start, self.offset], "callee": callee, "arguments": args}

    def binary(self, op: str, left_fn: object, right_fn: object) -> Node:
        start = self.offset
        left = cast("Node", left_fn(self) if callable(left_fn) else left_fn)
        self.write(" ")
        op_node = self.name(op)
        self.write(" ")
        right = cast("Node", right_fn(self) if callable(right_fn) else right_fn)
        return {"kind": "binary", "span": [start, self.offset], "operator": op_node, "left": left, "right": right}

    def let_expr(self, var_name: str, val_fn: object, body_fn: object) -> Node:
        start = self.offset
        b_start = self.offset
        self.write("let ")
        vname = self.name(var_name)
        self.write(" = ")
        val = cast("Node", val_fn(self) if callable(val_fn) else val_fn)
        binding: Node = {
            "kind": "let",
            "span": [b_start, self.offset],
            "name": vname,
            "type": None,
            "grade": None,
            "value": val,
        }
        self.write(" in ")
        body = cast("Node", body_fn(self) if callable(body_fn) else body_fn)
        return {"kind": "let_expression", "span": [start, self.offset], "binding": binding, "body": body}

    def envelope(self) -> tuple[bytes, Node]:
        raw = self.text.encode("utf-8")
        return raw, {
            "schema": 2,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "ast": {
                "kind": "surface_file",
                "span": [0, len(raw)],
                "name": self.module,
                "declarations": self.declarations,
            },
        }


def _build_cap_gate_ast(cap_lit: str) -> tuple[bytes, Node]:
    b = _Builder("CapGate")
    b.write("\n")
    d_start = b.offset
    b.write("public definition ")
    ret_ty = b.type_simple("Span", "byte")
    b.write(" ")
    fn_name = b.name("PrepareHeader")
    b.write("(")
    p_start = b.offset
    p_ty = b.type_modified("ref", "Span", "byte")
    b.write(" ")
    p_name = b.name("dst")
    param: Node = {"kind": "parameter", "span": [p_start, b.offset], "name": p_name, "type": p_ty, "grade": None}
    b.write(")")

    contracts: list[Node] = []
    for role, expr_fn in (
        ("requires", lambda x: x.member(lambda y: y.var("dst"), "CanRead")),
        ("requires", lambda x: x.member(lambda y: y.var("dst"), "CanWrite")),
        (
            "requires",
            lambda x: x.binary(
                "==",
                lambda y: y.member(lambda z: z.var("dst"), "Length"),
                lambda y: y.nat_lit(cap_lit, "usize"),
            ),
        ),
        ("restores", lambda x: x.var("dst")),
        (
            "ensures",
            lambda x: x.binary(
                "==",
                lambda y: y.member(lambda z: z.var("result"), "Length"),
                lambda y: y.member(lambda z: z.var("dst"), "Length"),
            ),
        ),
    ):
        b.write(" ")
        c_start = b.offset
        b.write(role + " ")
        c_val = expr_fn(b)
        contracts.append({"kind": "contract", "span": [c_start, b.offset], "role": role, "value": c_val})

    b.write(" => ")
    body = b.let_expr(
        "s1",
        lambda x: x.call_span("Write", lambda y: y.var("dst"), lambda y: y.nat_lit("0", "usize"), lambda y: y.nat_lit("0x56", "u8")),
        lambda x: x.let_expr(
            "roView",
            lambda y: y.call_span(
                "ReadOnly",
                lambda z: z.call_span(
                    "Slice",
                    lambda w: w.var("s1"),
                    lambda w: w.nat_lit("0", "usize"),
                    lambda w: w.nat_lit("4", "usize"),
                ),
            ),
            lambda y: y.call_span("Restore", lambda z: z.var("dst"), lambda z: z.var("roView")),
        ),
    )
    b.write(";")
    b.declarations.append({
        "kind": "definition",
        "span": [d_start, b.offset],
        "name": fn_name,
        "result": ret_ty,
        "generics": [],
        "parameters": [param],
        "contracts": contracts,
        "value": body,
        "modifiers": ["public"],
    })
    return b.envelope()


def _capacity_invariance_and_contracts() -> None:
    small_src, small_ast = _build_cap_gate_ast("8")
    large_src, large_ast = _build_cap_gate_ast("1_000_000_000")
    small_elab, small_state = vela_elaborate._checked_elaboration(small_src, small_ast)
    large_elab, large_state = vela_elaborate._checked_elaboration(large_src, large_ast)

    ensure(
        len(small_state.output) == len(large_state.output) == 7,
        f"expected 7 emitted definitions (1 body + 5 restores + 1 ensures), got {len(small_state.output)}",
    )
    ensure(
        small_state.work == large_state.work and small_state.reductions == large_state.reductions,
        "capacity-invariance gate failed: work or reduction steps differed between N=8 and N=1,000,000,000",
    )
    ensure(
        len(small_elab.gallina) == len(large_elab.gallina),
        "capacity-invariance gate failed: emitted Gallina size differed between N=8 and N=1,000,000,000",
    )
    for field_tag in ("Base", "Length", "Tag", "PermRead", "PermWrite"):
        ensure(
            f"vela_d0_PrepareHeader_restores_0_{field_tag}" in small_elab.gallina,
            f"missing restores obligation for {field_tag}",
        )
    ensure("vela_d0_PrepareHeader_ensures_0" in small_elab.gallina, "missing ensures_0 obligation")


def _negative_span_refusals() -> None:
    def single_def(body_fn: object, *, param_mod: str | None = None, restores: bool = False) -> tuple[bytes, Node]:
        b = _Builder("Neg")
        b.write("\n")
        d_start = b.offset
        b.write("public definition ")
        ret_ty = b.type_simple("Span", "byte")
        b.write(" ")
        fn_name = b.name("Bad")
        params: list[Node] = []
        b.write("(")
        if param_mod is not None:
            p_start = b.offset
            p_ty = b.type_modified(param_mod, "Span", "byte")
            b.write(" ")
            p_name = b.name("s")
            params.append({"kind": "parameter", "span": [p_start, b.offset], "name": p_name, "type": p_ty, "grade": None})
        b.write(")")
        contracts: list[Node] = []
        if param_mod is not None:
            for expr_fn in (
                lambda x: x.member(lambda y: y.var("s"), "CanRead"),
                lambda x: x.member(lambda y: y.var("s"), "CanWrite"),
                lambda x: x.binary(">=", lambda y: y.member(lambda z: z.var("s"), "Length"), lambda y: y.nat_lit("8", "usize")),
            ):
                b.write(" ")
                c_start = b.offset
                b.write("requires ")
                c_val = expr_fn(b)
                contracts.append({"kind": "contract", "span": [c_start, b.offset], "role": "requires", "value": c_val})
        if restores:
            b.write(" ")
            c_start = b.offset
            b.write("restores ")
            c_val = b.var("s")
            contracts.append({"kind": "contract", "span": [c_start, b.offset], "role": "restores", "value": c_val})
        b.write(" => ")
        body = cast("Node", body_fn(b) if callable(body_fn) else body_fn)
        b.write(";")
        b.declarations.append({
            "kind": "definition",
            "span": [d_start, b.offset],
            "name": fn_name,
            "result": ret_ty,
            "generics": [],
            "parameters": params,
            "contracts": contracts,
            "value": body,
            "modifiers": ["public"],
        })
        return b.envelope()

    cases = (
        (
            "oob-write",
            single_def(
                lambda b: b.call_span(
                    "Write",
                    lambda x: x.call_span("AllocZeroed", lambda y: y.nat_lit("64", "usize"), lambda y: y.nat_lit("8", "usize")),
                    lambda x: x.nat_lit("8", "usize"),
                    lambda x: x.nat_lit("1", "u8"),
                )
            ),
            "cannot prove Span.Write index is within Span.Length bounds",
        ),
        (
            "mutate-in-borrow",
            single_def(
                lambda b: b.call_span("Write", lambda x: x.var("s"), lambda x: x.nat_lit("0", "usize"), lambda x: x.nat_lit("1", "u8")),
                param_mod="in",
            ),
            "cannot mutate a read-only 'in Span<byte>' borrow",
        ),
        (
            "broken-restores",
            single_def(
                lambda b: b.call_span("Slice", lambda x: x.var("s"), lambda x: x.nat_lit("0", "usize"), lambda x: x.nat_lit("4", "usize")),
                param_mod="ref",
                restores=True,
            ),
            "assertion could not be established",
        ),
    )
    for label, (raw, ast), expected_msg in cases:
        try:
            vela_elaborate.elaborate(raw, ast)
        except VelaError as error:
            ensure(
                error.kind == "type" and expected_msg in error.message,
                f"{label}: expected type error '{expected_msg}', got {error.kind}: {error.message}",
            )
        else:
            raise AssertionError(f"{label} was unexpectedly accepted")


def _clight_lowering_and_purecap_assembly() -> None:
    source = (TOOLS / "vela/examples/first_slice.vela").read_bytes()
    synthetic_ast = {
        "schema": 2,
        "ast": {
            "kind": "surface_file",
            "declarations": [
                {"kind": "union", "name": {"text": "ValidationError"}},
                {"kind": "record", "name": {"text": "ValidationOutcome"}},
                {"kind": "function", "name": {"text": "MakePacket8"}},
                {"kind": "function", "name": {"text": "CopyPacketToDst"}},
                {"kind": "function", "name": {"text": "ComputePacketChecksum"}},
                {"kind": "function", "name": {"text": "PrepareAndValidatePacket"}},
                {"kind": "theorem", "name": {"text": "LawLoopFramePreservesDisjointSuffix"}},
                {"kind": "theorem", "name": {"text": "ValidateEmptyPacketOk"}},
                {"kind": "theorem", "name": {"text": "ValidateFullPacketOk"}},
                {"kind": "theorem", "name": {"text": "ValidatePartialPacketScrubsStaleAndTrailingBytes"}},
                {"kind": "theorem", "name": {"text": "RejectFramingShort"}},
                {"kind": "theorem", "name": {"text": "RejectBadMagic"}},
                {"kind": "theorem", "name": {"text": "RejectLengthOutOfBounds"}},
                {"kind": "theorem", "name": {"text": "RejectChecksumScrubsDestinationAndRestores"}},
            ],
        },
    }
    c_code, checks = vela_first_slice.lower_to_c(source, synthetic_ast)
    ensure(checks == 19, f"expected 19 checks in lowered C, got {checks}")
    ensure("PrepareAndValidatePacket(" in c_code and "CopyPacketToDst(" in c_code, "missing lowered C functions")

    perturbed_code, _ = vela_first_slice.lower_to_c(source, synthetic_ast, perturb_check=7)
    ensure(c_code != perturbed_code, "perturbed C source did not change check 7")

    incomplete_ast = {"schema": 2, "ast": {"kind": "surface_file", "declarations": []}}
    try:
        vela_first_slice.lower_to_c(source, incomplete_ast)
    except ValueError as err:
        ensure("ValidationError" in str(err), f"unexpected error on incomplete AST: {err}")
    else:
        raise AssertionError("incomplete AST was accepted by lower_to_c")

    with tempfile.TemporaryDirectory(prefix="vos-vela-slice-asm-") as tmp:
        workdir = Path(tmp)
        for mode in ("pass", "bounds-trap", "tag-trap", "perm-trap"):
            stream = vela_first_slice._purecap_cheri_asm_stream(mode)
            elf = workdir / f"purecap_{mode}.elf"
            refusals, size = cd.assemble(stream, f"purecap_{mode}", elf)
            ensure(not refusals and size > 0 and elf.is_file(), f"purecap_{mode} failed assembly: {refusals}")


def cases() -> list[Case]:
    return [
        Case("capacity-invariance-and-restores-ensures-obligations", _capacity_invariance_and_contracts),
        Case("semantic-negative-span-refusals", _negative_span_refusals),
        Case("clight-lowering-and-purecap-cheri-assembly", _clight_lowering_and_purecap_assembly),
    ]
