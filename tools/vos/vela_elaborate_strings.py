# SPDX-License-Identifier: Apache-2.0
"""String literal decoding, interpolated template holes, and Format.Write elaboration for Vela."""

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from vos.vela_ast import (
    DECIMAL,
    trivia_end,
)
from vos.vela_authoring import assist_loan_argument
from vos.vela_elaborate_protocol import (
    _BIN_LITERAL,
    _HEX_LITERAL,
)
from vos.vela_elaborate_types import (
    _BOOL,
    _CHAR,
    _NAT,
    MAX_STRING_BYTES,
    Node,
    _app,
    _apps,
    _Binding,
    _constant,
    _Term,
    _term,
)

if TYPE_CHECKING:
    from vos.vela_elaborate import _Elaborator


class _StringsMixin:
    def _decode_escaped_segment(self: _Elaborator, segment: str, node: Node) -> bytes:
        escapes = {"\\": "\\", '"': '"', "'": "'", "n": "\n", "r": "\r", "t": "\t", "0": "\0"}
        chars: list[str] = []
        index = 0
        while index < len(segment):
            ch = segment[index]
            if ch != "\\":
                chars.append(ch)
                index += 1
                continue
            if index + 1 >= len(segment):
                raise self.fail("syntax", "unterminated escape sequence in string literal", node)
            nxt = segment[index + 1]
            if nxt in escapes:
                chars.append(escapes[nxt])
                index += 2
                continue
            if nxt == "u" and index + 2 < len(segment) and segment[index + 2] == "{":
                end = segment.find("}", index + 3)
                if end == -1:
                    raise self.fail("syntax", "unterminated \\u{...} escape sequence", node)
                hex_digits = segment[index + 3:end]
                if not (1 <= len(hex_digits) <= 6 and all(c in "0123456789abcdefABCDEF" for c in hex_digits)):
                    raise self.fail("syntax", "invalid \\u{...} hex digits", node)
                codepoint = int(hex_digits, 16)
                if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                    raise self.fail("syntax", "Unicode scalar escape is out of range or a surrogate", node)
                chars.append(chr(codepoint))
                index = end + 1
                continue
            raise self.fail("syntax", f"unsupported string escape '\\{nxt}'", node)
        return "".join(chars).encode("utf-8")

    def _decode_char_literal(self: _Elaborator, spelling: str, node: Node) -> int:
        if len(spelling) < 3 or not spelling.startswith("'") or not spelling.endswith("'"):
            raise self.fail("protocol", "character literal lacks single-quote delimiters", node)
        body = spelling[1:-1]
        if "\n" in body or "\r" in body:
            raise self.fail("syntax", "character literal cannot contain a raw newline", node)
        if not body.startswith("\\") and "'" in body:
            raise self.fail("syntax", "unescaped single quote in character literal", node)
        raw_bytes = self._decode_escaped_segment(body, node)
        decoded = raw_bytes.decode("utf-8")
        if len(decoded) != 1:
            raise self.fail("syntax", "character literal must encode exactly one Unicode scalar value", node)
        return ord(decoded[0])

    def _decode_string_literal(self: _Elaborator, spelling: str, node: Node) -> bytes:
        if spelling.startswith('"""'):
            quotes = len(spelling) - len(spelling.lstrip('"'))
            body = spelling[quotes:-quotes]
            if "\n" in body or "\r" in body:
                normalized = body.replace("\r\n", "\n").replace("\r", "\n")
                lines = normalized.split("\n")
                closing_indent = lines[-1]
                dedented: list[str] = []
                for content_line in lines[1:-1]:
                    if content_line == "":
                        dedented.append("")
                    else:
                        if not content_line.startswith(closing_indent):
                            raise self.fail(
                                "syntax",
                                "raw string content line has less indentation than closing delimiter",
                                node,
                            )
                        dedented.append(content_line[len(closing_indent):])
                raw_bytes = "\n".join(dedented).encode("utf-8")
            else:
                raw_bytes = body.encode("utf-8")
        else:
            raw_bytes = self._decode_escaped_segment(spelling[1:-1], node)
        if len(raw_bytes) > MAX_STRING_BYTES:
            raise self.fail("limit", f"string literal exceeds {MAX_STRING_BYTES} UTF-8 bytes", node)
        return raw_bytes

    def _bytes_binding(self: _Elaborator, raw_bytes: bytes) -> _Binding:
        term = _apps(_constant("VNil"), _NAT, _term("unit"))
        for length, byte_val in enumerate(reversed(raw_bytes)):
            term = _apps(
                _constant("VCons"),
                _NAT,
                _term("nat", value=length),
                _term("nat", value=byte_val),
                term,
            )
        return _Binding(term, _apps(_constant("Vec"), _NAT, _term("nat", value=len(raw_bytes))))

    def _parse_hole_ast(self: _Elaborator, start_byte: int, end_byte: int, container: Node) -> Node:
        src = self.protocol.source
        raw_expr = src[start_byte:end_byte].decode("utf-8", errors="replace").strip()
        tokens: list[tuple[str, str, int, int]] = []
        cursor = trivia_end(src, start_byte, block_comments=True)
        multi_ops = (b"<==>", b"==>", b"::<", b"==", b"!=", b"<=", b">=", b"&&", b"||")
        single_ops = set(b"(){}[].,:=+-*/%<>!&|^~?")
        while cursor < end_byte:
            matched_multi = False
            for op in multi_ops:
                if src[cursor:cursor + len(op)] == op and cursor + len(op) <= end_byte:
                    tokens.append(("punct", op.decode("ascii"), cursor, cursor + len(op)))
                    cursor = trivia_end(src, cursor + len(op), block_comments=True)
                    matched_multi = True
                    break
            if matched_multi:
                continue
            byte0 = src[cursor]
            if byte0 in single_ops and not (
                byte0 == ord("?")
                and cursor + 1 < end_byte
                and (
                    ord("A") <= src[cursor + 1] <= ord("Z")
                    or ord("a") <= src[cursor + 1] <= ord("z")
                    or src[cursor + 1] == ord("_")
                )
            ):
                tokens.append(("punct", chr(byte0), cursor, cursor + 1))
                cursor = trivia_end(src, cursor + 1, block_comments=True)
                continue
            if byte0 == ord('"'):
                end = cursor + 1
                while end < end_byte and src[end] != ord('"'):
                    if src[end] == ord("\\"):
                        end += 2
                    else:
                        end += 1
                if end >= end_byte or src[end] != ord('"'):
                    raise self.fail("syntax", "unterminated string literal in interpolation hole", container)
                end += 1
                tokens.append(("string", src[cursor:end].decode("utf-8"), cursor, end))
                cursor = trivia_end(src, end, block_comments=True)
                continue
            if byte0 == ord("'"):
                end = cursor + 1
                while end < end_byte and src[end] != ord("'"):
                    if src[end] == ord("\\"):
                        end += 2
                    else:
                        end += 1
                if end >= end_byte or src[end] != ord("'"):
                    raise self.fail("syntax", "unterminated character literal in interpolation hole", container)
                end += 1
                tokens.append(("char", src[cursor:end].decode("utf-8"), cursor, end))
                cursor = trivia_end(src, end, block_comments=True)
                continue
            if ord("0") <= byte0 <= ord("9"):
                end = cursor + 1
                while end < end_byte and (
                    ord("0") <= src[end] <= ord("9")
                    or ord("A") <= src[end] <= ord("Z")
                    or ord("a") <= src[end] <= ord("z")
                    or src[end] == ord("_")
                ):
                    end += 1
                token_str = src[cursor:end].decode("ascii")
                split_at = len(token_str)
                for sfx in ("usize", "byte", "u16", "u32", "u64", "i16", "i32", "i64", "u8", "i8"):
                    if token_str.endswith(sfx) and len(token_str) > len(sfx):
                        candidate_mag = token_str[:-len(sfx)]
                        if (
                            DECIMAL.fullmatch(candidate_mag)
                            or _HEX_LITERAL.fullmatch(candidate_mag)
                            or _BIN_LITERAL.fullmatch(candidate_mag)
                        ):
                            split_at = len(candidate_mag)
                            break
                else:
                    if not (
                        _HEX_LITERAL.fullmatch(token_str)
                        or _BIN_LITERAL.fullmatch(token_str)
                    ):
                        for idx_ch, ch in enumerate(token_str):
                            if not (ch.isdigit() or ch == "_"):
                                split_at = idx_ch
                                break
                tokens.append(("nat", f"{token_str[:split_at]}:{token_str[split_at:]}", cursor, end))
                cursor = trivia_end(src, end, block_comments=True)
                continue
            if (
                ord("A") <= byte0 <= ord("Z")
                or ord("a") <= byte0 <= ord("z")
                or byte0 in {ord("_"), ord("?")}
            ):
                end = cursor + 1
                if byte0 == ord("?") and (
                    end >= end_byte
                    or not (
                        ord("A") <= src[end] <= ord("Z")
                        or ord("a") <= src[end] <= ord("z")
                        or src[end] == ord("_")
                    )
                ):
                    raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)
                while end < end_byte and (
                    ord("0") <= src[end] <= ord("9")
                    or ord("A") <= src[end] <= ord("Z")
                    or ord("a") <= src[end] <= ord("z")
                    or src[end] == ord("_")
                ):
                    end += 1
                tokens.append(("ident", src[cursor:end].decode("ascii"), cursor, end))
                cursor = trivia_end(src, end, block_comments=True)
                continue
            raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)

        if not tokens:
            raise self.fail("syntax", "empty interpolation hole in format template", container)

        pos = 0

        def peek() -> tuple[str, str, int, int] | None:
            return tokens[pos] if pos < len(tokens) else None

        def consume(expected_kind: str | None = None, expected_text: str | None = None) -> tuple[str, str, int, int]:
            nonlocal pos
            tok = peek()
            if tok is None or (expected_kind is not None and tok[0] != expected_kind) or (
                expected_text is not None and tok[1] != expected_text
            ):
                raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)
            pos += 1
            return tok

        def has_generic_call_ahead(start_idx: int) -> bool:
            depth = 0
            idx = start_idx
            while idx < len(tokens):
                tk, tv, _, _ = tokens[idx]
                if tk == "punct" and tv in {"<", ":: <", "::<"}:
                    depth += 1
                elif tk == "punct" and tv == ">":
                    depth -= 1
                    if depth == 0:
                        return idx + 1 < len(tokens) and tokens[idx + 1][0] == "punct" and tokens[idx + 1][1] == "("
                elif tk == "punct" and tv in {";", "{", "}"}:
                    return False
                idx += 1
            return False

        def is_tok(kind: str, val: str | None = None) -> bool:
            t = peek()
            return t is not None and t[0] == kind and (val is None or t[1] == val)

        def parse_type_node() -> Node:
            t_tok = consume("ident")
            name_node: Node = {"text": t_tok[1], "span": [t_tok[2], t_tok[3]]}
            args: list[Node] = []
            end_b = t_tok[3]
            if is_tok("punct", "<"):
                consume("punct", "<")
                while True:
                    if is_tok("nat"):
                        ntok = consume("nat")
                        v_str, s_str = ntok[1].split(":", 1)
                        args.append({"kind": "nat", "span": [ntok[2], ntok[3]], "value": v_str, "suffix": s_str})
                    else:
                        args.append(parse_type_node())
                    if is_tok("punct", ","):
                        consume("punct", ",")
                        if is_tok("punct", ">"):
                            break
                    else:
                        break
                gt_tok = consume("punct", ">")
                end_b = gt_tok[3]
            return {"kind": "type", "span": [t_tok[2], end_b], "name": name_node, "arguments": args}

        def parse_pattern_node() -> Node:
            ptok = peek()
            if ptok is None:
                raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)
            if ptok[0] == "ident" and ptok[1] == "_":
                consume("ident", "_")
                return {"kind": "wildcard_pattern", "span": [ptok[2], ptok[3]]}
            if ptok[0] == "ident" and ptok[1] in {"true", "false"}:
                consume("ident")
                return {"kind": "bool_pattern", "span": [ptok[2], ptok[3]], "value": ptok[1] == "true"}
            if ptok[0] == "nat":
                consume("nat")
                v_str, s_str = ptok[1].split(":", 1)
                return {"kind": "nat_pattern", "span": [ptok[2], ptok[3]], "value": v_str, "suffix": s_str}
            if ptok[0] == "char":
                consume("char")
                return {"kind": "character_pattern", "span": [ptok[2], ptok[3]], "value": ptok[1]}
            if ptok[0] == "string":
                consume("string")
                return {"kind": "string_pattern", "span": [ptok[2], ptok[3]], "value": ptok[1]}
            if ptok[0] == "ident":
                consume("ident")
                ident_node: Node = {"text": ptok[1], "span": [ptok[2], ptok[3]]}
                if is_tok("punct", "("):
                    consume("punct", "(")
                    pargs: list[Node] = []
                    if peek() is not None and not is_tok("punct", ")"):
                        while True:
                            if (
                                pos + 1 < len(tokens)
                                and tokens[pos][0] == "ident"
                                and tokens[pos + 1][0] == "punct"
                                and tokens[pos + 1][1] == ":"
                            ):
                                ltok = consume("ident")
                                consume("punct", ":")
                                inner_p = parse_pattern_node()
                                inner_end = cast("list[int]", inner_p["span"])[1]
                                pargs.append(
                                    {
                                        "kind": "labeled_pattern",
                                        "span": [ltok[2], inner_end],
                                        "label": {"text": ltok[1], "span": [ltok[2], ltok[3]]},
                                        "pattern": inner_p,
                                    }
                                )
                            else:
                                pargs.append(parse_pattern_node())
                            if is_tok("punct", ","):
                                consume("punct", ",")
                                if is_tok("punct", ")"):
                                    break
                            else:
                                break
                    rp = consume("punct", ")")
                    return {
                        "kind": "constructor_pattern",
                        "span": [ptok[2], rp[3]],
                        "name": ident_node,
                        "arguments": pargs,
                    }
                return {"kind": "binding_pattern", "span": [ptok[2], ptok[3]], "name": ident_node}
            raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)

        def parse_primary() -> Node:
            tok = peek()
            if tok is None:
                raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)
            tk, tv, ts, te = tok
            if tk == "ident" and tv == "if":
                consume("ident", "if")
                consume("punct", "(")
                cond = parse_expr()
                consume("punct", ")")
                yes = parse_expr()
                consume("ident", "else")
                no = parse_expr()
                no_end = cast("list[int]", no["span"])[1]
                return {
                    "kind": "if_expression",
                    "span": [ts, no_end],
                    "condition": cond,
                    "then": yes,
                    "else": no,
                }
            if tk == "ident" and tv in {"true", "false"}:
                consume("ident")
                return {"kind": "bool", "span": [ts, te], "value": tv == "true"}
            if tk == "nat":
                consume("nat")
                v_str, s_str = tv.split(":", 1)
                return {"kind": "nat", "span": [ts, te], "value": v_str, "suffix": s_str}
            if tk == "string":
                consume("string")
                return {"kind": "string", "span": [ts, te], "value": tv}
            if tk == "char":
                consume("char")
                return {"kind": "character", "span": [ts, te], "value": tv}
            if tk == "punct" and tv == "(":
                consume("punct", "(")
                if is_tok("punct", ")"):
                    rp = consume("punct", ")")
                    return {"kind": "unit", "span": [ts, rp[3]]}
                first = parse_expr()
                if is_tok("punct", ","):
                    items = [first]
                    while is_tok("punct", ","):
                        consume("punct", ",")
                        items.append(parse_expr())
                    rp = consume("punct", ")")
                    return {"kind": "tuple", "span": [ts, rp[3]], "values": items}
                rp = consume("punct", ")")
                return {"kind": "group", "span": [ts, rp[3]], "value": first}
            if tk == "ident":
                consume("ident")
                kind_name = "hole" if tv.startswith("?") else "name"
                return {"kind": kind_name, "span": [ts, te], "name": {"text": tv, "span": [ts, te]}}
            raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)

        def parse_postfix() -> Node:
            node: Node = parse_primary()
            while True:
                nxt = peek()
                if nxt is None:
                    break
                nk, nv, _, _ = nxt
                node_start = cast("list[int]", node["span"])[0]
                if nk == "punct" and nv == ".":
                    consume("punct", ".")
                    mtok = consume("ident")
                    node = {
                        "kind": "member",
                        "span": [node_start, mtok[3]],
                        "value": node,
                        "name": {"text": mtok[1], "span": [mtok[2], mtok[3]]},
                    }
                    continue
                if nk == "punct" and (
                    nv == "::<" or (nv == "<" and node["kind"] == "name" and has_generic_call_ahead(pos))
                ):
                    consume("punct")
                    gargs: list[Node] = []
                    while True:
                        if is_tok("nat"):
                            ntok = consume("nat")
                            v_str, s_str = ntok[1].split(":", 1)
                            gargs.append(
                                {"kind": "nat", "span": [ntok[2], ntok[3]], "value": v_str, "suffix": s_str}
                            )
                        else:
                            gargs.append(parse_type_node())
                        if is_tok("punct", ","):
                            consume("punct", ",")
                            if is_tok("punct", ">"):
                                break
                        else:
                            break
                    gt_tok = consume("punct", ">")
                    node = {
                        "kind": "generic_application",
                        "span": [node_start, gt_tok[3]],
                        "value": node,
                        "arguments": gargs,
                    }
                    continue
                if nk == "punct" and nv == "(":
                    consume("punct", "(")
                    cargs: list[Node] = []
                    if peek() is not None and not is_tok("punct", ")"):
                        while True:
                            if (
                                pos + 1 < len(tokens)
                                and tokens[pos][0] == "ident"
                                and tokens[pos + 1][0] == "punct"
                                and tokens[pos + 1][1] == ":"
                            ):
                                ltok = consume("ident")
                                consume("punct", ":")
                                val_node = parse_expr()
                                val_end = cast("list[int]", val_node["span"])[1]
                                cargs.append(
                                    {
                                        "kind": "argument",
                                        "span": [ltok[2], val_end],
                                        "label": {"text": ltok[1], "span": [ltok[2], ltok[3]]},
                                        "value": val_node,
                                    }
                                )
                            else:
                                val_node = parse_expr()
                                val_span = cast("list[int]", val_node["span"])
                                cargs.append(
                                    {
                                        "kind": "argument",
                                        "span": [val_span[0], val_span[1]],
                                        "label": None,
                                        "value": val_node,
                                    }
                                )
                            if is_tok("punct", ","):
                                consume("punct", ",")
                                if is_tok("punct", ")"):
                                    break
                            else:
                                break
                    rp = consume("punct", ")")
                    node = {"kind": "call", "span": [node_start, rp[3]], "callee": node, "arguments": cargs}
                    continue
                if nk == "ident" and nv == "with":
                    consume("ident", "with")
                    consume("punct", "{")
                    updates: list[Node] = []
                    while peek() is not None and not is_tok("punct", "}"):
                        ftok = consume("ident")
                        consume("punct", "=")
                        fval = parse_expr()
                        fval_end = cast("list[int]", fval["span"])[1]
                        updates.append(
                            {
                                "kind": "field_update",
                                "span": [ftok[2], fval_end],
                                "name": {"text": ftok[1], "span": [ftok[2], ftok[3]]},
                                "value": fval,
                            }
                        )
                        if is_tok("punct", ","):
                            consume("punct", ",")
                        else:
                            break
                    rb = consume("punct", "}")
                    node = {
                        "kind": "with_expression",
                        "span": [node_start, rb[3]],
                        "value": node,
                        "updates": updates,
                    }
                    continue
                if nk == "ident" and nv == "is":
                    consume("ident", "is")
                    pat_node = parse_pattern_node()
                    pat_end = cast("list[int]", pat_node["span"])[1]
                    node = {"kind": "is", "span": [node_start, pat_end], "value": node, "pattern": pat_node}
                    continue
                if nk == "punct" and nv == "?":
                    qtok = consume("punct", "?")
                    node = {"kind": "try", "span": [node_start, qtok[3]], "value": node}
                    continue
                if nk == "punct" and nv == "[":
                    consume("punct", "[")
                    idx_node = parse_expr()
                    rb = consume("punct", "]")
                    node = {"kind": "index", "span": [node_start, rb[3]], "value": node, "index": idx_node}
                    continue
                break
            return node

        def parse_unary() -> Node:
            tok = peek()
            if tok is not None and (
                (tok[0] == "punct" and tok[1] in {"!", "-", "~"})
                or (tok[0] == "ident" and tok[1] == "ref")
            ):
                consume()
                operand = parse_unary()
                op_end = cast("list[int]", operand["span"])[1]
                return {
                    "kind": "unary",
                    "span": [tok[2], op_end],
                    "operator": {"text": tok[1], "span": [tok[2], tok[3]]},
                    "value": operand,
                }
            return parse_postfix()

        def parse_bin(next_fn: Callable[[], Node], ops: set[str], *, right_assoc: bool = False) -> Node:
            left: Node = next_fn()
            while True:
                cur_op = peek()
                if cur_op is None or cur_op[0] != "punct" or cur_op[1] not in ops:
                    break
                op_tok = consume("punct")
                right = parse_bin(next_fn, ops, right_assoc=True) if right_assoc else next_fn()
                left_start = cast("list[int]", left["span"])[0]
                right_end = cast("list[int]", right["span"])[1]
                left = {
                    "kind": "binary",
                    "span": [left_start, right_end],
                    "operator": {"text": op_tok[1], "span": [op_tok[2], op_tok[3]]},
                    "left": left,
                    "right": right,
                }
            return left

        def parse_mul() -> Node:
            return parse_bin(parse_unary, {"*", "/", "%"})

        def parse_add() -> Node:
            return parse_bin(parse_mul, {"+", "-"})

        def parse_cmp() -> Node:
            return parse_bin(parse_add, {"<", "<=", ">", ">="})

        def parse_eq() -> Node:
            return parse_bin(parse_cmp, {"==", "!="})

        def parse_bitand() -> Node:
            return parse_bin(parse_eq, {"&"})

        def parse_bitxor() -> Node:
            return parse_bin(parse_bitand, {"^"})

        def parse_bitor() -> Node:
            return parse_bin(parse_bitxor, {"|"})

        def parse_and() -> Node:
            return parse_bin(parse_bitor, {"&&"})

        def parse_or() -> Node:
            return parse_bin(parse_and, {"||"})

        def parse_expr() -> Node:
            return parse_bin(parse_or, {"==>", "<==>"}, right_assoc=True)

        ast_node = parse_expr()
        if pos != len(tokens):
            raise self.fail("unsupported", f"unsupported interpolation hole expression '{raw_expr}'", container)
        self.protocol.visit(ast_node, (start_byte, end_byte))
        return ast_node

    def _check_hole_target_alias(self: _Elaborator, node: Node, target_name: str) -> None:
        kind = node["kind"]
        if kind == "name":
            if self.name(node["name"]) == target_name:
                raise self.fail(
                    "type",
                    f"Format.Write hole cannot alias or read target buffer '{target_name}'",
                    node,
                )
            return
        if kind in {"group", "unary", "member", "is", "generic_application"}:
            self._check_hole_target_alias(self.node(node["value"]), target_name)
            return
        if kind == "index":
            self._check_hole_target_alias(self.node(node["value"]), target_name)
            self._check_hole_target_alias(self.node(node["index"]), target_name)
            return
        if kind == "binary":
            self._check_hole_target_alias(self.node(node["left"]), target_name)
            self._check_hole_target_alias(self.node(node["right"]), target_name)
            return
        if kind == "if_expression":
            self._check_hole_target_alias(self.node(node["condition"]), target_name)
            self._check_hole_target_alias(self.node(node["then"]), target_name)
            self._check_hole_target_alias(self.node(node["else"]), target_name)
            return
        if kind == "tuple":
            for item in self.nodes(node["values"]):
                self._check_hole_target_alias(item, target_name)
            return
        if kind == "call":
            self._check_hole_target_alias(self.node(node["callee"]), target_name)
            for arg_node in self.nodes(node["arguments"]):
                self._check_hole_target_alias(self.node(arg_node["value"]), target_name)
            return
        if kind == "with_expression":
            self._check_hole_target_alias(self.node(node["value"]), target_name)
            for upd_node in self.nodes(node["updates"]):
                self._check_hole_target_alias(self.node(upd_node["value"]), target_name)
            return

    def _format_write(
        self: _Elaborator, node: Node, arguments: list[Node], environment: dict[str, _Binding]
    ) -> _Binding:
        if len(arguments) != 2:
            raise self.fail("type", "Format.Write requires (ref builder, $\"...\") arguments", node)
        labeled = False
        for idx, arg_node in enumerate(arguments):
            self.node(arg_node, "argument")
            label = arg_node["label"]
            if label is None and labeled:
                raise self.fail("name", "positional arguments cannot follow a named argument", arg_node)
            labeled = labeled or label is not None
            if label is not None:
                spelling = self.name(label)
                expected_label = "target" if idx == 0 else "template"
                if spelling != expected_label:
                    raise self.fail(
                        "name", f"expected argument label '{expected_label}', got '{spelling}'", arg_node
                    )
        target_arg = self.node(arguments[0]["value"])
        if (target_arg["kind"] != "unary"
                or not isinstance(target_arg["operator"], dict)
                or target_arg["operator"].get("text") != "ref"):
            hint = ""
            if target_arg["kind"] == "name":
                tname = self.name(target_arg["name"])
                t_err = self.protocol.error("type", "", target_arg)
                assist_loan_argument(self.protocol.source, t_err.line, t_err.column, "ref")
                hint = f"; write 'ref {tname}'"
            raise self.fail(
                "type",
                f"Format.Write requires an explicit ref TextBuilder<capacity> target{hint}",
                arguments[0],
            )
        target_inner = self.node(target_arg["value"])
        target_name = self.name(target_inner["name"]) if target_inner["kind"] == "name" else None
        builder = self.expression(target_inner, environment)
        capacity = self.meta(_NAT, environment)
        self.unify(builder.type, _app(_constant("TextBuilder"), capacity))
        capacity = self.whnf(capacity)
        template_arg = self.node(arguments[1]["value"])
        if template_arg["kind"] != "interpolated_string":
            raise self.fail(
                "type",
                "Format.Write requires an interpolated $\"...\" format template",
                arguments[1],
            )
        spelling = cast("str", template_arg["value"])
        body = spelling[2:-1]
        body_start_byte = cast("list[int]", template_arg["span"])[0] + 2
        literal_chars: list[str] = []
        chunk_terms: list[_Term] = []
        concrete_bytes = 0
        index = 0
        while index < len(body):
            ch = body[index]
            if ch == "{":
                if index + 1 < len(body) and body[index + 1] == "{":
                    literal_chars.append("{")
                    index += 2
                    continue
                if literal_chars:
                    concrete_bytes += len(
                        self._decode_escaped_segment("".join(literal_chars), template_arg)
                    )
                    literal_chars.clear()
                scan = index + 1
                brace_depth = 1
                paren_depth = 0
                bracket_depth = 0
                in_quote = False
                in_single_quote = False
                colon_index: int | None = None
                while scan < len(body) and brace_depth > 0:
                    c_scan = body[scan]
                    if in_quote:
                        if c_scan == "\\":
                            scan += 2
                            continue
                        if c_scan == '"':
                            in_quote = False
                        scan += 1
                        continue
                    if in_single_quote:
                        if c_scan == "\\":
                            scan += 2
                            continue
                        if c_scan == "'":
                            in_single_quote = False
                        scan += 1
                        continue
                    if c_scan == '"':
                        in_quote = True
                    elif c_scan == "'":
                        in_single_quote = True
                    elif c_scan == "{":
                        brace_depth += 1
                    elif c_scan == "}":
                        brace_depth -= 1
                        if brace_depth == 0:
                            break
                    elif c_scan == "(":
                        paren_depth += 1
                    elif c_scan == ")":
                        paren_depth = max(0, paren_depth - 1)
                    elif c_scan == "[":
                        bracket_depth += 1
                    elif c_scan == "]":
                        bracket_depth = max(0, bracket_depth - 1)
                    elif (
                        c_scan == ":"
                        and brace_depth == 1
                        and paren_depth == 0
                        and bracket_depth == 0
                        and not (scan + 1 < len(body) and body[scan + 1] == ":")
                        and not (scan > index + 1 and body[scan - 1] == ":")
                    ):
                        colon_index = scan
                    scan += 1
                if brace_depth != 0:
                    raise self.fail("syntax", "unterminated interpolation hole in format template", template_arg)
                end = scan
                raw_start = index + 1
                raw_end = colon_index if colon_index is not None else end
                spec = body[colon_index + 1:end].strip() if colon_index is not None else ""
                expr_byte_start = body_start_byte + len(body[:raw_start].encode("utf-8"))
                expr_byte_end = body_start_byte + len(body[:raw_end].encode("utf-8"))
                hole_ast = self._parse_hole_ast(expr_byte_start, expr_byte_end, template_arg)
                if target_name is not None:
                    self._check_hole_target_alias(hole_ast, target_name)
                hole_binding = self.expression(hole_ast, environment)
                if builder.term.kind == "var" and cast("int", builder.term.value) in self.free(hole_binding.term):
                    raise self.fail(
                        "type",
                        f"Format.Write hole cannot alias or read target buffer '{target_name or 'target'}'",
                        hole_ast,
                    )
                hole_type = self.whnf(hole_binding.type)
                head, type_args = self.spine(hole_type)
                hole_int_spec = self._int_spec(hole_type)
                if hole_type == _NAT or hole_int_spec is not None:
                    if spec not in {"", "d", "x", "x2", "x4", "x8", "X", "X2", "X4", "X8", "b"}:
                        raise self.fail(
                            "type", f"unsupported format specifier '{spec}' for Nat hole", template_arg
                        )
                    val = self.whnf(hole_binding.term)
                    if val.kind in {"nat", "int"}:
                        n_val = cast("int", val.value)
                        if spec in {"", "d"}:
                            concrete_bytes += len(str(n_val))
                        elif n_val < 0:
                            raise self.fail(
                                "type",
                                f"format specifier '{spec}' requires a non-negative integer value",
                                template_arg,
                            )
                        elif spec in {"x", "X"}:
                            concrete_bytes += len(format(n_val, "x"))
                        elif spec in {"x2", "X2"}:
                            concrete_bytes += max(2, len(format(n_val, "x")))
                        elif spec in {"x4", "X4"}:
                            concrete_bytes += max(4, len(format(n_val, "x")))
                        elif spec in {"x8", "X8"}:
                            concrete_bytes += max(8, len(format(n_val, "x")))
                        else:
                            concrete_bytes += len(format(n_val, "b"))
                    elif spec in {"x2", "X2", "x4", "X4", "x8", "X8"} and (
                        hole_int_spec is None or not hole_int_spec.signed
                    ):
                        concrete_bytes += int(spec[1:])
                    else:
                        raise self.fail(
                            "type",
                            "symbolic Nat hole requires a fixed-width hex specifier (x2, x4, x8) or concrete value",
                            template_arg,
                        )
                elif hole_type == _BOOL:
                    if spec != "":
                        raise self.fail(
                            "type", f"unsupported format specifier '{spec}' for bool hole", template_arg
                        )
                    val = self.whnf(hole_binding.term)
                    if val.kind == "bool":
                        concrete_bytes += 4 if val.value else 5
                    else:
                        chunk_terms.append(
                            _term("if", _NAT, hole_binding.term, _term("nat", value=4), _term("nat", value=5))
                        )
                elif hole_type == _CHAR:
                    if spec != "":
                        raise self.fail(
                            "type", f"unsupported format specifier '{spec}' for char hole", template_arg
                        )
                    val = self.whnf(hole_binding.term)
                    if val.kind == "char":
                        cp = cast("int", val.value)
                        concrete_bytes += len(chr(cp).encode("utf-8"))
                    elif self._prove_bool_precondition(
                        _apps(_constant("char_le"), hole_binding.term, _term("char", value=0x7F)), environment
                    ):
                        concrete_bytes += 1
                    else:
                        raise self.fail(
                            "type",
                            "symbolic char hole requires a concrete character value or proved ASCII bound (<= '\\u{7F}')",
                            template_arg,
                        )
                elif head == _constant("Vec") and len(type_args) == 2 and self.whnf(type_args[0]) == _NAT:
                    if spec != "":
                        raise self.fail(
                            "type", f"unsupported format specifier '{spec}' for byte-vector hole", template_arg
                        )
                    len_term = self.whnf(type_args[1])
                    if len_term.kind == "nat":
                        concrete_bytes += cast("int", len_term.value)
                    else:
                        chunk_terms.append(len_term)
                else:
                    raise self.fail(
                        "type",
                        "interpolated hole type does not implement static Format<T>",
                        template_arg,
                    )
                index = end + 1
                continue
            if ch == "}":
                if index + 1 < len(body) and body[index + 1] == "}":
                    literal_chars.append("}")
                    index += 2
                    continue
                raise self.fail("syntax", "unescaped closing '}' in interpolated format template", template_arg)
            literal_chars.append(ch)
            index += 1
        if literal_chars:
            concrete_bytes += len(self._decode_escaped_segment("".join(literal_chars), template_arg))
        if concrete_bytes > MAX_STRING_BYTES:
            raise self.fail(
                "limit", f"formatted template exceeds {MAX_STRING_BYTES} UTF-8 bytes", template_arg
            )
        total_chunk = _term("nat", value=concrete_bytes)
        for extra in chunk_terms:
            total_chunk = (
                extra if total_chunk == _term("nat", value=0) else _apps(_constant("+"), total_chunk, extra)
            )
        return _Binding(
            _apps(_constant("FormatStep"), capacity, builder.term, total_chunk),
            _app(_constant("TextBuilder"), capacity),
        )
