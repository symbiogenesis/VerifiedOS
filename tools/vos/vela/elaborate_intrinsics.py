# SPDX-License-Identifier: Apache-2.0
"""Span, Seq, Slots, fixed-width integer intrinsics, and expression elaboration for Vela."""

from typing import TYPE_CHECKING, cast

from vos.vela.elaborate_types import (
    _BOOL,
    _CHAR,
    _INT_INTRINSICS,
    _INT_SPECS,
    _NAT,
    _NUMERICS_ALIASES,
    _PROP,
    _SORT,
    _U8,
    _UNIT,
    _USIZE,
    Node,
    _allows_from_conversion,
    _app,
    _apps,
    _Binding,
    _constant,
    _int_term,
    _InterfaceInfo,
    _InterfaceMethodSpec,
    _IntSpec,
    _Meta,
    _parse_numeric_magnitude,
    _RecordInfo,
    _RecordMethod,
    _Term,
    _term,
)

if TYPE_CHECKING:
    from vos.vela.elaborate import _Elaborator


class _IntrinsicsMixin:
    def _root_span(self: _Elaborator, span_term: _Term) -> _Term:
        curr = self.whnf(span_term)
        while curr.kind == "app":
            head, args = self.spine(curr)
            if head.kind != "const" or not isinstance(head.value, str):
                break
            sname = head.value
            if sname in {
                "Span_ReadOnly",
                "Span_Invalidate",
                "Span_Write",
                "Span_Fill",
                "Span_Slice",
                "Span_CopyPrefix",
                "Span_Restore",
            } and len(args) >= 2:
                curr = self.whnf(args[1])
            elif sname in {"Slots_Write", "Slots_TransferSource", "Slots_TransferDest"} and len(args) >= 3:
                curr = self.whnf(args[2])
            elif sname == "Slots_CopyRepresentation" and len(args) == 6:
                curr = self.whnf(args[4])
            else:
                break
        return curr

    def _is_readonly_span(self: _Elaborator, span_term: _Term) -> bool:
        root = self._root_span(span_term)
        return root.kind == "var" and cast("int", root.value) in self.readonly_span_vars

    def _check_span_can_read(
        self: _Elaborator, span_term: _Term, environment: dict[str, _Binding], site: Node
    ) -> None:
        cond = _apps(_constant("Span_CanRead"), _U8, span_term)
        if not self._prove_bool_precondition(cond, environment):
            raise self.fail(
                "type",
                "cannot prove Span has valid tag and read permission (Span.CanRead)",
                site,
            )

    def _check_span_can_write(
        self: _Elaborator, span_term: _Term, environment: dict[str, _Binding], site: Node
    ) -> None:
        if self._is_readonly_span(span_term):
            raise self.fail("type", "cannot mutate a read-only 'in Span<byte>' borrow", site)
        cond = _apps(_constant("Span_CanWrite"), _U8, span_term)
        if not self._prove_bool_precondition(cond, environment):
            raise self.fail(
                "type",
                "cannot prove Span has valid tag and write permission (Span.CanWrite)",
                site,
            )

    def _check_span_disjoint(
        self: _Elaborator, dst_term: _Term, src_term: _Term, environment: dict[str, _Binding], site: Node
    ) -> None:
        direct_ab = _apps(_constant("Span_Disjoint"), _U8, dst_term, src_term)
        direct_ba = _apps(_constant("Span_Disjoint"), _U8, src_term, dst_term)
        if self._prove_bool_precondition(direct_ab, environment) or self._prove_bool_precondition(
            direct_ba, environment
        ):
            return
        root_dst = self._root_span(dst_term)
        root_src = self._root_span(src_term)
        if root_dst != root_src:
            root_ab = _apps(_constant("Span_Disjoint"), _U8, root_dst, root_src)
            root_ba = _apps(_constant("Span_Disjoint"), _U8, root_src, root_dst)
            if self._prove_bool_precondition(root_ab, environment) or self._prove_bool_precondition(
                root_ba, environment
            ):
                return
        ba = _apps(_constant("Span_Base"), _U8, dst_term)
        la = _apps(_constant("Span_Length"), _U8, dst_term)
        bb = _apps(_constant("Span_Base"), _U8, src_term)
        lb = _apps(_constant("Span_Length"), _U8, src_term)
        cond_ab = _apps(_constant("int_le_usize"), _apps(_constant("int_add_usize"), ba, la), bb)
        cond_ba = _apps(_constant("int_le_usize"), _apps(_constant("int_add_usize"), bb, lb), ba)
        if self._prove_bool_precondition(cond_ab, environment) or self._prove_bool_precondition(
            cond_ba, environment
        ):
            return
        raise self.fail(
            "type",
            "cannot prove Span.CopyPrefix source and destination extents are disjoint",
            site,
        )

    def _elaborate_span_intrinsic(
        self: _Elaborator,
        node: Node,
        member_name: str,
        call_args: list[Node],
        environment: dict[str, _Binding],
    ) -> _Binding:
        self.site = node
        for arg_node in call_args:
            self.node(arg_node, "argument")
            if arg_node["label"] is not None:
                raise self.fail("name", f"Span.{member_name} does not accept labeled arguments", arg_node)
        raw_arg_nodes = [self._unwrap_group(self.node(a["value"])) for a in call_args]
        arg_nodes = [
            self._unwrap_group(self.node(n["value"]))
            if (
                n["kind"] == "unary"
                and isinstance(n.get("operator"), dict)
                and cast("Node", n["operator"]).get("text") in {"ref", "in"}
            )
            else n
            for n in raw_arg_nodes
        ]
        span_u8 = _app(_constant("Span"), _U8)
        if member_name == "AllocZeroed":
            if len(arg_nodes) == 1:
                base_t = _int_term(_INT_SPECS["usize"], 0)
                cap_t = self.check(arg_nodes[0], _USIZE, environment)
            elif len(arg_nodes) == 2:
                base_t = self.check(arg_nodes[0], _USIZE, environment)
                cap_t = self.check(arg_nodes[1], _USIZE, environment)
            else:
                raise self.fail("type", f"Span.AllocZeroed expects 1 or 2 arguments, got {len(arg_nodes)}", node)
            return _Binding(_apps(_constant("Span_AllocZeroed"), _U8, base_t, cap_t), span_u8)
        if member_name in {"ReadOnly", "Invalidate"}:
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Span.{member_name} expects 1 argument, got {len(arg_nodes)}", node)
            s_t = self.check(arg_nodes[0], span_u8, environment)
            return _Binding(_apps(_constant(f"Span_{member_name}"), _U8, s_t), span_u8)
        if member_name == "Disjoint":
            if len(arg_nodes) != 2:
                raise self.fail("type", f"Span.Disjoint expects 2 arguments, got {len(arg_nodes)}", node)
            a_t = self.check(arg_nodes[0], span_u8, environment)
            b_t = self.check(arg_nodes[1], span_u8, environment)
            return _Binding(_apps(_constant("Span_Disjoint"), _U8, a_t, b_t), _BOOL)
        if member_name == "Read":
            if len(arg_nodes) != 2:
                raise self.fail("type", f"Span.Read expects 2 arguments, got {len(arg_nodes)}", node)
            s_t = self.check(arg_nodes[0], span_u8, environment)
            idx_t = self.check(arg_nodes[1], _USIZE, environment)
            self._check_span_can_read(s_t, environment, node)
            len_t = _apps(_constant("Span_Length"), _U8, s_t)
            in_bounds = _apps(_constant("int_lt_usize"), idx_t, len_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", "cannot prove Span.Read index is within Span.Length bounds", node)
            return _Binding(_apps(_constant("Span_Read"), _U8, s_t, idx_t), _U8)
        if member_name == "Write":
            if len(arg_nodes) != 3:
                raise self.fail("type", f"Span.Write expects 3 arguments, got {len(arg_nodes)}", node)
            s_t = self.check(arg_nodes[0], span_u8, environment)
            idx_t = self.check(arg_nodes[1], _USIZE, environment)
            val_t = self.check(arg_nodes[2], _U8, environment)
            self._check_span_can_write(s_t, environment, node)
            len_t = _apps(_constant("Span_Length"), _U8, s_t)
            in_bounds = _apps(_constant("int_lt_usize"), idx_t, len_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", "cannot prove Span.Write index is within Span.Length bounds", node)
            return _Binding(_apps(_constant("Span_Write"), _U8, s_t, idx_t, val_t), span_u8)
        if member_name == "Fill":
            if len(arg_nodes) != 4:
                raise self.fail("type", f"Span.Fill expects 4 arguments, got {len(arg_nodes)}", node)
            s_t = self.check(arg_nodes[0], span_u8, environment)
            off_t = self.check(arg_nodes[1], _USIZE, environment)
            cnt_t = self.check(arg_nodes[2], _USIZE, environment)
            val_t = self.check(arg_nodes[3], _U8, environment)
            self._check_span_can_write(s_t, environment, node)
            len_t = _apps(_constant("Span_Length"), _U8, s_t)
            end_t = _apps(_constant("int_add_usize"), off_t, cnt_t)
            in_bounds = _apps(_constant("int_le_usize"), end_t, len_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail(
                    "type",
                    "cannot prove Span.Fill subrange (offset + count <= Span.Length) is in bounds",
                    node,
                )
            return _Binding(_apps(_constant("Span_Fill"), _U8, s_t, off_t, cnt_t, val_t), span_u8)
        if member_name == "Slice":
            if len(arg_nodes) != 3:
                raise self.fail("type", f"Span.Slice expects 3 arguments, got {len(arg_nodes)}", node)
            s_t = self.check(arg_nodes[0], span_u8, environment)
            off_t = self.check(arg_nodes[1], _USIZE, environment)
            cnt_t = self.check(arg_nodes[2], _USIZE, environment)
            self._check_span_can_read(s_t, environment, node)
            len_t = _apps(_constant("Span_Length"), _U8, s_t)
            end_t = _apps(_constant("int_add_usize"), off_t, cnt_t)
            in_bounds = _apps(_constant("int_le_usize"), end_t, len_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail(
                    "type",
                    "cannot prove Span.Slice subrange (offset + count <= Span.Length) is in bounds",
                    node,
                )
            return _Binding(_apps(_constant("Span_Slice"), _U8, s_t, off_t, cnt_t), span_u8)
        if member_name == "CopyPrefix":
            if len(arg_nodes) != 3:
                raise self.fail("type", f"Span.CopyPrefix expects 3 arguments, got {len(arg_nodes)}", node)
            dst_t = self.check(arg_nodes[0], span_u8, environment)
            src_t = self.check(arg_nodes[1], span_u8, environment)
            cnt_t = self.check(arg_nodes[2], _USIZE, environment)
            self._check_span_can_write(dst_t, environment, node)
            self._check_span_can_read(src_t, environment, node)
            dst_len = _apps(_constant("Span_Length"), _U8, dst_t)
            src_len = _apps(_constant("Span_Length"), _U8, src_t)
            if not self._prove_bool_precondition(_apps(_constant("int_le_usize"), cnt_t, dst_len), environment):
                raise self.fail("type", "cannot prove Span.CopyPrefix count <= dst.Length", node)
            if not self._prove_bool_precondition(_apps(_constant("int_le_usize"), cnt_t, src_len), environment):
                raise self.fail("type", "cannot prove Span.CopyPrefix count <= src.Length", node)
            self._check_span_disjoint(dst_t, src_t, environment, node)
            return _Binding(_apps(_constant("Span_CopyPrefix"), _U8, dst_t, src_t, cnt_t), span_u8)
        if member_name == "Restore":
            if len(arg_nodes) != 2:
                raise self.fail("type", f"Span.Restore expects 2 arguments, got {len(arg_nodes)}", node)
            parent_t = self.check(arg_nodes[0], span_u8, environment)
            view_t = self.check(arg_nodes[1], span_u8, environment)
            self._check_span_can_write(parent_t, environment, node)
            p_base = _apps(_constant("Span_Base"), _U8, parent_t)
            p_len = _apps(_constant("Span_Length"), _U8, parent_t)
            v_base = _apps(_constant("Span_Base"), _U8, view_t)
            v_len = _apps(_constant("Span_Length"), _U8, view_t)
            base_ok = _apps(_constant("int_ge_usize"), v_base, p_base)
            end_ok = _apps(
                _constant("int_le_usize"),
                _apps(_constant("int_add_usize"), v_base, v_len),
                _apps(_constant("int_add_usize"), p_base, p_len),
            )
            if not (
                self._prove_bool_precondition(base_ok, environment)
                and self._prove_bool_precondition(end_ok, environment)
            ):
                raise self.fail(
                    "type",
                    "cannot prove Span.Restore view extent is contained within parent extent",
                    node,
                )
            return _Binding(_apps(_constant("Span_Restore"), _U8, parent_t, view_t), span_u8)
        raise self.fail("name", f"unknown Span intrinsic 'Span.{member_name}'", node)

    def _seq_nat_arg(self: _Elaborator, arg_node: Node, environment: dict[str, _Binding]) -> _Term:
        if self._is_unsuffixed_int_expr(arg_node):
            return self.check(arg_node, _NAT, environment)
        arg_b = self.expression(arg_node, environment)
        ty_w = self.whnf(arg_b.type)
        if ty_w == _NAT:
            return arg_b.term
        spec = self._int_spec(ty_w)
        if spec is not None and not spec.signed:
            val_w = self.whnf(arg_b.term)
            if val_w.kind == "int":
                return _term("nat", value=max(0, cast("int", val_w.value)))
            return _app(_constant(f"int_to_nat_{spec.name}"), arg_b.term)
        raise self.fail("type", "sequence index or count must be Nat or an unsigned integer", arg_node)

    def _elaborate_seq_intrinsic(
        self: _Elaborator,
        node: Node,
        member_name: str,
        gen_args: list[Node],
        call_args: list[Node],
        environment: dict[str, _Binding],
    ) -> _Binding:
        self.site = node
        for arg_node in call_args:
            self.node(arg_node, "argument")
            if arg_node["label"] is not None:
                raise self.fail("name", f"Seq.{member_name} does not accept labeled arguments", arg_node)
        arg_nodes = [self.node(a["value"]) for a in call_args]
        if member_name == "Empty":
            if arg_nodes:
                raise self.fail("type", f"Seq.Empty expects 0 arguments, got {len(arg_nodes)}", node)
            if len(gen_args) > 1:
                raise self.fail("type", "Seq.Empty accepts at most 1 generic type argument", node)
            elem_t = self.type(gen_args[0], environment) if gen_args else self.meta(_SORT, environment)
            return _Binding(_app(_constant("Seq_Empty"), elem_t), _app(_constant("Seq"), elem_t))
        if member_name == "Singleton":
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.Singleton expects 1 argument, got {len(arg_nodes)}", node)
            if len(gen_args) > 1:
                raise self.fail("type", "Seq.Singleton accepts at most 1 generic type argument", node)
            if gen_args:
                elem_t = self.type(gen_args[0], environment)
                val_t = self.check(arg_nodes[0], elem_t, environment)
            else:
                val_b = self.expression(arg_nodes[0], environment)
                elem_t, val_t = val_b.type, val_b.term
            return _Binding(_apps(_constant("Seq_Singleton"), elem_t, val_t), _app(_constant("Seq"), elem_t))
        raise self.fail("name", f"unknown Seq intrinsic 'Seq.{member_name}'", node)

    def _elaborate_seq_method(
        self: _Elaborator,
        node: Node,
        recv_b: _Binding,
        elem_t: _Term,
        member_name: str,
        call_args: list[Node],
        environment: dict[str, _Binding],
    ) -> _Binding:
        self.site = node
        for arg_node in call_args:
            self.node(arg_node, "argument")
            if arg_node["label"] is not None:
                raise self.fail("name", f"Seq.{member_name} does not accept labeled arguments", arg_node)
        arg_nodes = [self.node(a["value"]) for a in call_args]
        seq_ty = _app(_constant("Seq"), elem_t)
        cnt_t = _apps(_constant("Seq_Count"), elem_t, recv_b.term)
        if member_name == "At":
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.At expects 1 argument, got {len(arg_nodes)}", node)
            idx_t = self._seq_nat_arg(arg_nodes[0], environment)
            in_bounds = _apps(_constant("<"), idx_t, cnt_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", "cannot prove Seq.At index is within Seq.Count bounds", node)
            d_val = self._default_term_for_type(elem_t)
            return _Binding(_apps(_constant("Seq_At"), elem_t, d_val, recv_b.term, idx_t), elem_t)
        if member_name == "Update":
            if len(arg_nodes) != 2:
                raise self.fail("type", f"Seq.Update expects 2 arguments, got {len(arg_nodes)}", node)
            idx_t = self._seq_nat_arg(arg_nodes[0], environment)
            val_t = self.check(arg_nodes[1], elem_t, environment)
            in_bounds = _apps(_constant("<"), idx_t, cnt_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", "cannot prove Seq.Update index is within Seq.Count bounds", node)
            return _Binding(_apps(_constant("Seq_Update"), elem_t, recv_b.term, idx_t, val_t), seq_ty)
        if member_name == "Append":
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.Append expects 1 argument, got {len(arg_nodes)}", node)
            other_t = self.check(arg_nodes[0], seq_ty, environment)
            return _Binding(_apps(_constant("Seq_Append"), elem_t, recv_b.term, other_t), seq_ty)
        if member_name in {"Take", "Skip"}:
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.{member_name} expects 1 argument, got {len(arg_nodes)}", node)
            n_t = self._seq_nat_arg(arg_nodes[0], environment)
            in_bounds = _apps(_constant("<="), n_t, cnt_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", f"cannot prove Seq.{member_name} count <= Seq.Count", node)
            return _Binding(_apps(_constant(f"Seq_{member_name}"), elem_t, recv_b.term, n_t), seq_ty)
        if member_name == "Slice":
            if len(arg_nodes) != 2:
                raise self.fail("type", f"Seq.Slice expects 2 arguments, got {len(arg_nodes)}", node)
            off_t = self._seq_nat_arg(arg_nodes[0], environment)
            len_t = self._seq_nat_arg(arg_nodes[1], environment)
            in_bounds = _apps(_constant("<="), _apps(_constant("+"), off_t, len_t), cnt_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail(
                    "type", "cannot prove Seq.Slice subrange (offset + count <= Seq.Count) is in bounds", node
                )
            return _Binding(_apps(_constant("Seq_Slice"), elem_t, recv_b.term, off_t, len_t), seq_ty)
        if member_name == "Contains":
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.Contains expects 1 argument, got {len(arg_nodes)}", node)
            val_t = self.check(arg_nodes[0], elem_t, environment)
            x_var = self.fresh(elem_t)
            eq_body = self._structural_eq_bool(elem_t, x_var, val_t, node)
            pred_lam = _term("lam", elem_t, eq_body, value=x_var.value)
            return _Binding(_apps(_constant("Seq_Any"), elem_t, recv_b.term, pred_lam), _BOOL)
        if member_name in {"All", "Any"}:
            if len(arg_nodes) != 1:
                raise self.fail("type", f"Seq.{member_name} expects 1 predicate argument, got {len(arg_nodes)}", node)
            pred_t = self.check(arg_nodes[0], self.pi(elem_t, _BOOL), environment)
            return _Binding(_apps(_constant(f"Seq_{member_name}"), elem_t, recv_b.term, pred_t), _BOOL)
        raise self.fail("name", f"Seq has no method '{member_name}'", node)

    def _unwrap_ref_expr_node(self: _Elaborator, node: Node) -> Node:
        unwrapped = self._unwrap_group(node)
        if (
            unwrapped["kind"] == "unary"
            and isinstance(unwrapped.get("operator"), dict)
            and cast("Node", unwrapped["operator"]).get("text") in {"ref", "in"}
        ):
            return self._unwrap_group(self.node(unwrapped["value"]))
        return node

    def _slots_usize_arg(self: _Elaborator, arg_node: Node, environment: dict[str, _Binding]) -> _Term:
        if self._is_unsuffixed_int_expr(arg_node):
            return self.check(arg_node, _USIZE, environment)
        arg_b = self.expression(arg_node, environment)
        ty_w = self.whnf(arg_b.type)
        if ty_w == _USIZE:
            return arg_b.term
        spec = self._int_spec(ty_w)
        if spec is not None and not spec.signed and _allows_from_conversion(spec, _INT_SPECS["usize"]):
            return _app(_constant(f"int_from_{spec.name}_usize"), arg_b.term)
        if ty_w == _NAT:
            val_w = self.whnf(arg_b.term)
            if val_w.kind == "nat":
                return _int_term(_INT_SPECS["usize"], cast("int", val_w.value))
            return _app(_constant("nat_to_usize"), arg_b.term)
        raise self.fail("type", "Slots index or count must have type usize", arg_node)

    def _slots_cap_usize_term(self: _Elaborator, cap_t: _Term) -> _Term:
        cap_w = self.whnf(cap_t)
        if cap_w.kind == "nat":
            return _int_term(_INT_SPECS["usize"], cast("int", cap_w.value))
        if cap_w.kind == "int":
            return cap_w
        return _app(_constant("nat_to_usize"), cap_t)

    def _require_slots_binding(self: _Elaborator, arg_node: Node, environment: dict[str, _Binding]) -> tuple[_Binding, _Term, _Term]:
        inner_node = self._unwrap_ref_expr_node(arg_node)
        b = self.expression(inner_node, environment)
        ty_w = self.whnf(b.type)
        head, args = self.spine(ty_w)
        if head != _constant("Slots") or len(args) != 2:
            raise self.fail("type", "expected a Slots<T, capacity> operand", arg_node)
        return b, args[0], args[1]

    def _check_slots_disjoint(
        self: _Elaborator,
        elem_t: _Term,
        cap_a: _Term,
        s_a: _Term,
        cap_b: _Term,
        s_b: _Term,
        environment: dict[str, _Binding],
        site: Node,
    ) -> None:
        cond_ab = _apps(_constant("Slots_Disjoint"), elem_t, cap_a, cap_b, s_a, s_b)
        cond_ba = _apps(_constant("Slots_Disjoint"), elem_t, cap_b, cap_a, s_b, s_a)
        if self._prove_bool_precondition(cond_ab, environment) or self._prove_bool_precondition(
            cond_ba, environment
        ):
            return
        ra = self._root_span(s_a)
        rb = self._root_span(s_b)
        if (ra, rb) != (s_a, s_b):
            r_ab = _apps(_constant("Slots_Disjoint"), elem_t, cap_a, cap_b, ra, rb)
            r_ba = _apps(_constant("Slots_Disjoint"), elem_t, cap_b, cap_a, rb, ra)
            if self._prove_bool_precondition(r_ab, environment) or self._prove_bool_precondition(
                r_ba, environment
            ):
                return
        raise self.fail(
            "type",
            "cannot prove source and destination Slots extents are disjoint (Slots.Disjoint)",
            site,
        )

    def _elaborate_slots_intrinsic(
        self: _Elaborator,
        node: Node,
        member_name: str,
        gen_args: list[Node],
        call_args: list[Node],
        environment: dict[str, _Binding],
        *,
        receiver: _Binding | None = None,
    ) -> _Binding:
        self.site = node
        allowed_labels = {
            "source", "src", "destination", "dst", "count", "slots",
            "index", "value", "start", "end", "base",
        }
        for arg_node in call_args:
            self.node(arg_node, "argument")
            if arg_node["label"] is not None:
                lbl = self.name(arg_node["label"])
                if lbl not in allowed_labels:
                    raise self.fail("name", f"Slots.{member_name} does not accept label '{lbl}'", arg_node)
        arg_nodes = [self.node(a["value"]) for a in call_args]
        if member_name == "AllocVacant":
            if len(arg_nodes) > 1:
                raise self.fail("type", f"Slots.AllocVacant expects at most 1 argument (base), got {len(arg_nodes)}", node)
            if gen_args:
                if len(gen_args) != 2:
                    raise self.fail("type", "Slots.AllocVacant expects <T, capacity> generic arguments", node)
                elem_t = self.type(gen_args[0], environment)
                cap_t = self.argument(gen_args[1], _NAT, environment)
            else:
                elem_t = self.meta(_SORT, environment)
                cap_t = self.meta(_NAT, environment)
            base_t = (
                self._slots_usize_arg(arg_nodes[0], environment)
                if arg_nodes
                else _int_term(_INT_SPECS["usize"], 0)
            )
            return _Binding(
                _apps(_constant("Slots_AllocVacant"), elem_t, cap_t, base_t),
                _apps(_constant("Slots"), elem_t, cap_t),
            )
        if member_name == "LivePrefix":
            if receiver is not None:
                if len(arg_nodes) not in {1, 2}:
                    raise self.fail("type", "Slots.LivePrefix expects (count) or (0, count) arguments on a receiver", node)
                _, elem_t, cap_t = self.spine(self.whnf(receiver.type))[0], *self.spine(self.whnf(receiver.type))[1]
                s_b = receiver
                if len(arg_nodes) == 2:
                    st_w = self.whnf(self._slots_usize_arg(arg_nodes[0], environment))
                    if st_w != _int_term(_INT_SPECS["usize"], 0):
                        raise self.fail("type", "LivePrefix start index must be 0", node)
                cnt_t = self._slots_usize_arg(arg_nodes[-1], environment)
            else:
                if len(arg_nodes) not in {2, 3}:
                    raise self.fail("type", "LivePrefix expects (slots, count) or (slots, 0, count) arguments", node)
                s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                if len(arg_nodes) == 3:
                    st_w = self.whnf(self._slots_usize_arg(arg_nodes[1], environment))
                    if st_w != _int_term(_INT_SPECS["usize"], 0):
                        raise self.fail("type", "LivePrefix start index must be 0", node)
                cnt_t = self._slots_usize_arg(arg_nodes[-1], environment)
            return _Binding(_apps(_constant("Slots_LivePrefix"), elem_t, cap_t, s_b.term, cnt_t), _BOOL)
        if member_name in {"VacantRange", "VacantSuffix"}:
            if receiver is not None:
                _, elem_t, cap_t = self.spine(self.whnf(receiver.type))[0], *self.spine(self.whnf(receiver.type))[1]
                s_b = receiver
                if member_name == "VacantSuffix":
                    if len(arg_nodes) != 1:
                        raise self.fail("type", "Slots.VacantSuffix expects 1 start argument", node)
                    start_t = self._slots_usize_arg(arg_nodes[0], environment)
                    end_t = self._slots_cap_usize_term(cap_t)
                else:
                    if len(arg_nodes) != 2:
                        raise self.fail("type", "Slots.VacantRange expects (start, end) arguments", node)
                    start_t = self._slots_usize_arg(arg_nodes[0], environment)
                    end_t = self._slots_usize_arg(arg_nodes[1], environment)
            else:
                if member_name == "VacantSuffix":
                    if len(arg_nodes) != 2:
                        raise self.fail("type", "VacantSuffix expects (slots, start) arguments", node)
                    s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                    start_t = self._slots_usize_arg(arg_nodes[1], environment)
                    end_t = self._slots_cap_usize_term(cap_t)
                else:
                    if len(arg_nodes) != 3:
                        raise self.fail("type", "VacantRange expects (slots, start, end) arguments", node)
                    s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                    start_t = self._slots_usize_arg(arg_nodes[1], environment)
                    end_t = self._slots_usize_arg(arg_nodes[2], environment)
            return _Binding(
                _apps(_constant("Slots_VacantRange"), elem_t, cap_t, s_b.term, start_t, end_t), _BOOL
            )
        if member_name == "PrefixModel":
            if receiver is not None:
                if len(arg_nodes) != 1:
                    raise self.fail("type", "Slots.PrefixModel expects 1 count argument on a receiver", node)
                _, elem_t, cap_t = self.spine(self.whnf(receiver.type))[0], *self.spine(self.whnf(receiver.type))[1]
                s_b = receiver
                cnt_t = self._slots_usize_arg(arg_nodes[0], environment)
            else:
                if len(arg_nodes) != 2:
                    raise self.fail("type", "PrefixModel expects (slots, count) arguments", node)
                s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                cnt_t = self._slots_usize_arg(arg_nodes[1], environment)
            return _Binding(
                _apps(_constant("PrefixModel"), elem_t, cap_t, s_b.term, cnt_t),
                _app(_constant("Seq"), elem_t),
            )
        if member_name == "Disjoint":
            if len(arg_nodes) != 2:
                raise self.fail("type", "Slots.Disjoint expects 2 Slots arguments", node)
            sa_b, elem_a, cap_a = self._require_slots_binding(arg_nodes[0], environment)
            sb_b, elem_b, cap_b = self._require_slots_binding(arg_nodes[1], environment)
            self.unify(elem_a, elem_b)
            return _Binding(
                _apps(_constant("Slots_Disjoint"), elem_a, cap_a, cap_b, sa_b.term, sb_b.term), _BOOL
            )
        if member_name == "RepEqual":
            if len(arg_nodes) != 3:
                raise self.fail("type", "Slots.RepEqual expects (dst, src, count) arguments", node)
            sa_b, elem_a, cap_a = self._require_slots_binding(arg_nodes[0], environment)
            sb_b, elem_b, cap_b = self._require_slots_binding(arg_nodes[1], environment)
            self.unify(elem_a, elem_b)
            cnt_t = self._slots_usize_arg(arg_nodes[2], environment)
            return _Binding(
                _apps(_constant("Slots_RepEqual"), elem_a, cap_a, cap_b, sa_b.term, sb_b.term, cnt_t), _BOOL
            )
        if member_name == "Read":
            if receiver is not None:
                if len(arg_nodes) != 1:
                    raise self.fail("type", "Slots.Read expects 1 index argument on a receiver", node)
                _, elem_t, cap_t = self.spine(self.whnf(receiver.type))[0], *self.spine(self.whnf(receiver.type))[1]
                s_b = receiver
                idx_t = self._slots_usize_arg(arg_nodes[0], environment)
            else:
                if len(arg_nodes) != 2:
                    raise self.fail("type", "Slots.Read expects (slots, index) arguments", node)
                s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                idx_t = self._slots_usize_arg(arg_nodes[1], environment)
            can_r = _apps(_constant("Slots_CanRead"), elem_t, cap_t, s_b.term)
            if not self._prove_bool_precondition(can_r, environment):
                raise self.fail("type", "cannot prove Slots has valid tag and read permission (Slots.CanRead)", node)
            live_t = _apps(_constant("Slots_LiveCount"), elem_t, cap_t, s_b.term)
            in_live = _apps(_constant("int_lt_usize"), idx_t, live_t)
            if not self._prove_bool_precondition(in_live, environment):
                raise self.fail(
                    "type",
                    "cannot read from a vacant or out-of-bounds slot; prove index < LiveCount (LivePrefix)",
                    node,
                )
            d_val = self._default_term_for_type(elem_t)
            return _Binding(_apps(_constant("Slots_Read"), elem_t, cap_t, d_val, s_b.term, idx_t), elem_t)
        if member_name == "Write":
            if receiver is not None:
                if len(arg_nodes) != 2:
                    raise self.fail("type", "Slots.Write expects (index, value) arguments on a receiver", node)
                _, elem_t, cap_t = self.spine(self.whnf(receiver.type))[0], *self.spine(self.whnf(receiver.type))[1]
                s_b = receiver
                idx_t = self._slots_usize_arg(arg_nodes[0], environment)
                val_t = self.check(arg_nodes[1], elem_t, environment)
            else:
                if len(arg_nodes) != 3:
                    raise self.fail("type", "Slots.Write expects (slots, index, value) arguments", node)
                s_b, elem_t, cap_t = self._require_slots_binding(arg_nodes[0], environment)
                idx_t = self._slots_usize_arg(arg_nodes[1], environment)
                val_t = self.check(arg_nodes[2], elem_t, environment)
            if self._is_readonly_span(s_b.term):
                raise self.fail("type", "cannot write to a read-only 'in Slots' borrow", node)
            can_w = _apps(_constant("Slots_CanWrite"), elem_t, cap_t, s_b.term)
            if not self._prove_bool_precondition(can_w, environment):
                raise self.fail("type", "cannot prove Slots has valid tag and write permission (Slots.CanWrite)", node)
            live_t = _apps(_constant("Slots_LiveCount"), elem_t, cap_t, s_b.term)
            eq_live = _apps(_constant("int_eq_usize"), idx_t, live_t)
            cap_u = self._slots_cap_usize_term(cap_t)
            lt_cap = (
                _apps(_constant("int_lt_usize"), idx_t, cap_u)
                if self.whnf(cap_u).kind == "int"
                else _apps(_constant("<"), _app(_constant("int_to_nat_usize"), idx_t), cap_t)
            )
            if not (
                self._prove_bool_precondition(eq_live, environment)
                and self._prove_bool_precondition(lt_cap, environment)
            ):
                raise self.fail(
                    "type",
                    "cannot write to a non-vacant or out-of-bounds slot; prove VacantRange at index (index == LiveCount and index < capacity)",
                    node,
                )
            return _Binding(
                _apps(_constant("Slots_Write"), elem_t, cap_t, s_b.term, idx_t, val_t), s_b.type
            )
        if member_name == "CopyRepresentation":
            if len(arg_nodes) != 3:
                raise self.fail("type", "CopyRepresentation expects (src, dst, count) arguments", node)
            src_b, elem_src, cap_src = self._require_slots_binding(arg_nodes[0], environment)
            dst_b, elem_dst, cap_dst = self._require_slots_binding(arg_nodes[1], environment)
            self.unify(elem_src, elem_dst)
            cnt_t = self._slots_usize_arg(arg_nodes[2], environment)
            if self._is_readonly_span(dst_b.term):
                raise self.fail("type", "cannot copy representation into a read-only 'in Slots' destination", node)
            src_live = _apps(_constant("Slots_LivePrefix"), elem_src, cap_src, src_b.term, cnt_t)
            if not self._prove_bool_precondition(src_live, environment):
                raise self.fail(
                    "type",
                    "cannot prove CopyRepresentation source has LivePrefix(src, count)",
                    node,
                )
            zero_u = _int_term(_INT_SPECS["usize"], 0)
            dst_vacant = _apps(_constant("Slots_VacantRange"), elem_dst, cap_dst, dst_b.term, zero_u, cnt_t)
            if not self._prove_bool_precondition(dst_vacant, environment):
                raise self.fail(
                    "type",
                    "cannot prove CopyRepresentation destination has VacantRange(dst, 0, count)",
                    node,
                )
            self._check_slots_disjoint(elem_src, cap_src, src_b.term, cap_dst, dst_b.term, environment, node)
            return _Binding(
                _apps(
                    _constant("Slots_CopyRepresentation"),
                    elem_src,
                    cap_src,
                    cap_dst,
                    src_b.term,
                    dst_b.term,
                    cnt_t,
                ),
                dst_b.type,
            )
        if member_name == "TransferType":
            if len(arg_nodes) != 3:
                raise self.fail("type", "TransferType expects (ref src, ref dst, count) arguments", node)
            src_b, elem_src, cap_src = self._require_slots_binding(arg_nodes[0], environment)
            dst_b, elem_dst, cap_dst = self._require_slots_binding(arg_nodes[1], environment)
            self.unify(elem_src, elem_dst)
            if gen_args:
                if len(gen_args) != 1:
                    raise self.fail("type", "TransferType accepts at most 1 generic type argument <T>", node)
                ann_elem = self.type(gen_args[0], environment)
                self.unify(elem_src, ann_elem)
            cnt_t = self._slots_usize_arg(arg_nodes[2], environment)
            if self._is_readonly_span(src_b.term) or self._is_readonly_span(dst_b.term):
                raise self.fail("type", "TransferType requires mutable source and destination Slots", node)
            src_can_w = _apps(_constant("Slots_CanWrite"), elem_src, cap_src, src_b.term)
            if not self._prove_bool_precondition(src_can_w, environment):
                raise self.fail("type", "cannot prove TransferType source has write permission (Slots.CanWrite)", node)
            src_live = _apps(_constant("Slots_LivePrefix"), elem_src, cap_src, src_b.term, cnt_t)
            if not self._prove_bool_precondition(src_live, environment):
                raise self.fail("type", "cannot prove TransferType source has LivePrefix(src, count)", node)
            zero_u = _int_term(_INT_SPECS["usize"], 0)
            dst_vacant = _apps(_constant("Slots_VacantRange"), elem_dst, cap_dst, dst_b.term, zero_u, cnt_t)
            if not self._prove_bool_precondition(dst_vacant, environment):
                raise self.fail(
                    "type", "cannot prove TransferType destination has VacantRange(dst, 0, count)", node
                )
            self._check_slots_disjoint(elem_src, cap_src, src_b.term, cap_dst, dst_b.term, environment, node)
            rep_eq = _apps(_constant("Slots_RepEqual"), elem_src, cap_dst, cap_src, dst_b.term, src_b.term, cnt_t)
            if not self._prove_bool_precondition(rep_eq, environment):
                raise self.fail(
                    "type",
                    "cannot prove TransferType representation equality (Slots.RepEqual); call CopyRepresentation before TransferType",
                    node,
                )
            return _Binding(
                _apps(
                    _constant("Slots_TransferType"),
                    elem_src,
                    cap_src,
                    cap_dst,
                    src_b.term,
                    dst_b.term,
                    cnt_t,
                ),
                _term("prod", src_b.type, dst_b.type),
            )
        raise self.fail("name", f"unknown Slots intrinsic 'Slots.{member_name}'", node)

    @staticmethod
    def _dotted_member_path(node: Node) -> str | None:
        if node["kind"] == "name" and isinstance(node.get("name"), dict):
            text = cast("Node", node["name"]).get("text")
            return text if isinstance(text, str) else None
        if node["kind"] == "member" and isinstance(node.get("name"), dict) and isinstance(node.get("value"), dict):
            prefix = _IntrinsicsMixin._dotted_member_path(cast("Node", node["value"]))
            suffix = cast("Node", node["name"]).get("text")
            if prefix is not None and isinstance(suffix, str):
                return f"{prefix}.{suffix}"
        return None

    def _resolve_int_type_receiver(self: _Elaborator, node: Node, environment: dict[str, _Binding]) -> _IntSpec | None:
        path = self._dotted_member_path(node)
        if path is None:
            return None
        if "." not in path:
            if path in environment:
                return None
            binding = self.globals.get(path)
            if binding is not None and binding.type == _SORT:
                return self._int_spec(binding.term)
            return None
        if path.startswith("Vela.Numerics.") and "Vela" not in environment:
            binding = self.globals.get(path)
            if binding is not None and binding.type == _SORT:
                return self._int_spec(binding.term)
        return None

    def _is_unsuffixed_int_expr(self: _Elaborator, node: Node) -> bool:
        kind = node["kind"]
        if kind == "nat":
            return cast("str", node.get("suffix", "")) == ""
        if kind == "group":
            return self._is_unsuffixed_int_expr(self.node(node["value"]))
        if kind == "unary" and isinstance(node.get("operator"), dict):
            op = cast("Node", node["operator"]).get("text")
            if op in {"-", "~"}:
                return self._is_unsuffixed_int_expr(self.node(node["value"]))
        if kind == "binary" and isinstance(node.get("operator"), dict):
            op = cast("Node", node["operator"]).get("text")
            if op in {"+", "-", "*", "/", "%", "&", "|", "^"}:
                return self._is_unsuffixed_int_expr(self.node(node["left"])) and self._is_unsuffixed_int_expr(
                    self.node(node["right"])
                )
        return False

    def _check_int_arith_precondition(
        self: _Elaborator,
        operator: str,
        spec: _IntSpec,
        left: _Term,
        right: _Term,
        environment: dict[str, _Binding],
        node: Node,
    ) -> None:
        facts = self._expand_bool_facts([*self.active_facts, *self._fact_bool_terms((), environment)])
        l_lo, l_hi, l_ne = self._term_bounds(left, spec, facts)
        r_lo, r_hi, r_ne = self._term_bounds(right, spec, facts)
        if l_lo > l_hi or r_lo > r_hi:
            return
        if operator == "+":
            lo = l_lo + r_lo
            hi = l_hi + r_hi
            for fact in facts:
                parsed = self._parse_cmp_fact(fact)
                if parsed is None:
                    continue
                f_op, f_spec, f_l, f_r = parsed
                fl_head, fl_args = self.spine(self.whnf(f_l))
                fr_head, fr_args = self.spine(self.whnf(f_r))
                # Recognize Nat(a) + Nat(b) <= K or a <= K - b
                if (
                    fl_head.kind == "const"
                    and fl_head.value in {"+", f"int_add_{spec.name}"}
                    and len(fl_args) == 2
                    and (
                        (self._same_numeric_subject(fl_args[0], left) and self._same_numeric_subject(fl_args[1], right))
                        or (self._same_numeric_subject(fl_args[0], right) and self._same_numeric_subject(fl_args[1], left))
                    )
                ):
                    _, k_hi, _ = self._term_bounds(f_r, f_spec, facts)
                    if f_op == "le":
                        hi = min(hi, k_hi)
                    elif f_op == "lt":
                        hi = min(hi, k_hi - 1)
                if (
                    fr_head.kind == "const"
                    and fr_head.value in {"-", f"int_sub_{spec.name}"}
                    and len(fr_args) == 2
                    and (
                        (self._same_numeric_subject(f_l, left) and self._same_numeric_subject(fr_args[1], right))
                        or (self._same_numeric_subject(f_l, right) and self._same_numeric_subject(fr_args[1], left))
                    )
                ):
                    _, k_hi, _ = self._term_bounds(fr_args[0], f_spec, facts)
                    if f_op == "le":
                        hi = min(hi, k_hi)
                    elif f_op == "lt":
                        hi = min(hi, k_hi - 1)
            if not (spec.min_val <= lo and hi <= spec.max_val):
                raise self.fail(
                    "type",
                    f"integer addition on '{spec.name}' may overflow ({lo}..{hi} is not within {spec.min_val}..{spec.max_val}); "
                    "prove the range or use WrappingAdd, SaturatingAdd or CheckedAdd",
                    node,
                )
            return
        if operator == "-":
            lo = l_lo - r_hi
            hi = l_hi - r_lo
            if self._same_numeric_subject(left, right):
                lo, hi = 0, 0
            else:
                if self._prove_comparison("ge", spec, left, right, facts):
                    lo = max(lo, 0)
                if self._prove_comparison("gt", spec, left, right, facts):
                    lo = max(lo, 1)
                if self._prove_comparison("le", spec, left, right, facts):
                    hi = min(hi, 0)
            if not (spec.min_val <= lo and hi <= spec.max_val):
                raise self.fail(
                    "type",
                    f"integer subtraction on '{spec.name}' may overflow ({lo}..{hi} is not within {spec.min_val}..{spec.max_val}); "
                    "prove the range or use WrappingSub, SaturatingSub or CheckedSub",
                    node,
                )
            return
        if operator == "*":
            prods = (l_lo * r_lo, l_lo * r_hi, l_hi * r_lo, l_hi * r_hi)
            lo = min(prods)
            hi = max(prods)
            for fact in facts:
                parsed = self._parse_cmp_fact(fact)
                if parsed is None:
                    continue
                f_op, f_spec, f_l, f_r = parsed
                fl_head, fl_args = self.spine(self.whnf(f_l))
                if (
                    fl_head.kind == "const"
                    and fl_head.value in {"*", f"int_mul_{spec.name}"}
                    and len(fl_args) == 2
                    and (
                        (self._same_numeric_subject(fl_args[0], left) and self._same_numeric_subject(fl_args[1], right))
                        or (self._same_numeric_subject(fl_args[0], right) and self._same_numeric_subject(fl_args[1], left))
                    )
                ):
                    _, k_hi, _ = self._term_bounds(f_r, f_spec, facts)
                    if f_op == "le":
                        hi = min(hi, k_hi)
                    elif f_op == "lt":
                        hi = min(hi, k_hi - 1)
            if not (spec.min_val <= lo and hi <= spec.max_val):
                raise self.fail(
                    "type",
                    f"integer multiplication on '{spec.name}' may overflow ({lo}..{hi} is not within {spec.min_val}..{spec.max_val}); "
                    "prove the range or use WrappingMul, SaturatingMul or CheckedMul",
                    node,
                )
            return
        if operator in {"/", "%"}:
            nonzero = (
                r_lo > 0
                or r_hi < 0
                or 0 in r_ne
                or self._prove_comparison("ne", spec, right, _int_term(spec, 0), facts)
            )
            if not nonzero:
                raise self.fail(
                    "type",
                    f"integer {'division' if operator == '/' else 'remainder'} on '{spec.name}' requires a proved nonzero divisor; "
                    f"prove divisor != 0 or use {'CheckedDiv' if operator == '/' else 'CheckedRem'}",
                    node,
                )
            if operator == "/" and spec.signed:
                can_be_min = (
                    l_lo <= spec.min_val <= l_hi
                    and spec.min_val not in l_ne
                    and not self._prove_comparison("ne", spec, left, _int_term(spec, spec.min_val), facts)
                )
                can_be_neg1 = (
                    r_lo <= -1 <= r_hi
                    and -1 not in r_ne
                    and not self._prove_comparison("ne", spec, right, _int_term(spec, -1), facts)
                )
                if can_be_min and can_be_neg1:
                    raise self.fail(
                        "type",
                        f"signed integer division on '{spec.name}' may overflow at {spec.name}.Min / -1; "
                        f"prove dividend != {spec.name}.Min or divisor != -1, or use CheckedDiv",
                        node,
                    )

    def _elaborate_unary(
        self: _Elaborator, node: Node, environment: dict[str, _Binding], *, expected_int: _Term | None = None
    ) -> _Binding:
        if isinstance(node["operator"], dict) and node["operator"].get("text") == "ref":
            raise self.fail("type", "ref argument is only supported as the target of Format.Write", node)
        operator = self.operator(node["operator"])
        operand_node = self.node(node["value"])
        if operator == "!":
            value = self.check(operand_node, _BOOL, environment)
            return _Binding(_app(_constant("!"), value), _BOOL)
        if operator == "-" and operand_node["kind"] == "nat":
            suffix = cast("str", operand_node["suffix"])
            mag = _parse_numeric_magnitude(cast("str", operand_node["value"]))
            val = -mag
            if suffix:
                canonical = "u8" if suffix == "byte" else _NUMERICS_ALIASES.get(suffix, suffix)
                spec = _INT_SPECS.get(canonical)
            else:
                spec = self._int_spec(expected_int) if expected_int is not None else None
            if spec is None:
                raise self.fail(
                    "type",
                    "negative integer literal requires a signed integer type annotation or suffix",
                    node,
                )
            if not spec.signed:
                raise self.fail("type", f"unsigned integer type '{spec.name}' does not support negation", node)
            if not spec.min_val <= val <= spec.max_val:
                raise self.fail(
                    "type",
                    f"integer literal {val} is out of range for '{spec.name}' ({spec.min_val}..{spec.max_val})",
                    node,
                )
            return _Binding(_int_term(spec, val), spec.const)
        if operator in {"-", "~"}:
            if expected_int is not None and self._int_spec(expected_int) is not None:
                operand = _Binding(self.check(operand_node, expected_int, environment), expected_int)
            else:
                operand = self.expression(operand_node, environment)
            spec = self._int_spec(operand.type)
            if spec is None:
                raise self.fail(
                    "type",
                    f"unary operator '{operator}' requires a fixed-width integer operand",
                    node,
                )
            if operator == "~":
                return _Binding(_app(_constant(f"int_not_{spec.name}"), operand.term), spec.const)
            if not spec.signed:
                raise self.fail(
                    "type",
                    f"unsigned integer type '{spec.name}' does not support unary negation; use WrappingNeg if modular negation is intended",
                    node,
                )
            facts = self._expand_bool_facts([*self.active_facts, *self._fact_bool_terms((), environment)])
            o_lo, o_hi, o_ne = self._term_bounds(operand.term, spec, facts)
            if (
                o_lo <= o_hi
                and o_lo <= spec.min_val <= o_hi
                and spec.min_val not in o_ne
                and not self._prove_comparison("ne", spec, operand.term, _int_term(spec, spec.min_val), facts)
            ):
                raise self.fail(
                    "type",
                    f"signed negation on '{spec.name}' may overflow at {spec.name}.Min; "
                    f"prove operand != {spec.name}.Min or use WrappingNeg, SaturatingNeg or CheckedNeg",
                    node,
                )
            return _Binding(_app(_constant(f"int_neg_{spec.name}"), operand.term), spec.const)
        raise self.fail("unsupported", f"prefix '{operator}' is unsupported")

    def _elaborate_binary(
        self: _Elaborator, node: Node, environment: dict[str, _Binding], *, expected_int: _Term | None = None
    ) -> _Binding:
        operator = self.operator(node["operator"])
        left_node = self.node(node["left"])
        right_node = self.node(node["right"])
        if operator in {"&&", "||", "==>", "<==>"}:
            left_b = _Binding(self.check(left_node, _BOOL, environment), _BOOL)
            if operator in {"&&", "==>"}:
                self.active_facts.append(left_b.term)
                try:
                    right_b = _Binding(self.check(right_node, _BOOL, environment), _BOOL)
                finally:
                    self.active_facts.pop()
            else:
                right_b = _Binding(self.check(right_node, _BOOL, environment), _BOOL)
            return _Binding(_apps(_constant(operator), left_b.term, right_b.term), _BOOL)
        expected_spec = self._int_spec(expected_int) if expected_int is not None else None
        if expected_spec is not None and operator in {"+", "-", "*", "/", "%", "&", "|", "^"}:
            left = _Binding(self.check(left_node, expected_spec.const, environment), expected_spec.const)
            right = _Binding(self.check(right_node, expected_spec.const, environment), expected_spec.const)
        elif self._is_unsuffixed_int_expr(left_node) and not self._is_unsuffixed_int_expr(right_node):
            right = self.expression(right_node, environment)
            if self._int_spec(right.type) is not None:
                left = _Binding(self.check(left_node, right.type, environment), right.type)
            else:
                left = self.expression(left_node, environment)
        elif self._is_unsuffixed_int_expr(right_node) and not self._is_unsuffixed_int_expr(left_node):
            left = self.expression(left_node, environment)
            if self._int_spec(left.type) is not None:
                right = _Binding(self.check(right_node, left.type, environment), left.type)
            else:
                right = self.expression(right_node, environment)
        else:
            left = self.expression(left_node, environment)
            right = self.expression(right_node, environment)
        if operator in {"==", "!="}:
            self.unify(left.type, right.type)
            operand_type = self.whnf(left.type)
            int_spec = self._int_spec(operand_type)
            if int_spec is not None:
                op_name = f"int_{'eq' if operator == '==' else 'ne'}_{int_spec.name}"
                return _Binding(_apps(_constant(op_name), left.term, right.term), _BOOL)
            if operand_type in {_NAT, _BOOL, _CHAR, _UNIT}:
                op_map = {
                    (_NAT, "=="): "eq_nat",
                    (_NAT, "!="): "ne_nat",
                    (_BOOL, "=="): "eq_bool",
                    (_BOOL, "!="): "ne_bool",
                    (_CHAR, "=="): "char_eq",
                    (_CHAR, "!="): "char_ne",
                    (_UNIT, "=="): "eq_unit",
                    (_UNIT, "!="): "ne_unit",
                }
                return _Binding(_apps(_constant(op_map[(operand_type, operator)]), left.term, right.term), _BOOL)
            eq_term = self._structural_eq_bool(operand_type, left.term, right.term, node)
            if operator == "!=":
                return _Binding(_app(_constant("!"), eq_term), _BOOL)
            return _Binding(eq_term, _BOOL)
        if self.whnf(left.type) == _CHAR or self.whnf(right.type) == _CHAR:
            self.unify(left.type, right.type)
            if operator in {"<", "<=", ">", ">="}:
                cmp_map = {"<": "char_lt", "<=": "char_le", ">": "char_gt", ">=": "char_ge"}
                return _Binding(_apps(_constant(cmp_map[operator]), left.term, right.term), _BOOL)
            raise self.fail("type", f"operator '{operator}' is not defined on 'char'", node)
        if self._int_spec(left.type) is not None or self._int_spec(right.type) is not None:
            self.unify(left.type, right.type)
            spec = cast("_IntSpec", self._int_spec(left.type))
            if operator in {"<", "<=", ">", ">="}:
                cmp_map = {"<": "lt", "<=": "le", ">": "gt", ">=": "ge"}
                return _Binding(_apps(_constant(f"int_{cmp_map[operator]}_{spec.name}"), left.term, right.term), _BOOL)
            if operator in {"&", "|", "^"}:
                bit_map = {"&": "and", "|": "or", "^": "xor"}
                return _Binding(
                    _apps(_constant(f"int_{bit_map[operator]}_{spec.name}"), left.term, right.term), spec.const
                )
            if operator in {"+", "-", "*", "/", "%"}:
                self._check_int_arith_precondition(operator, spec, left.term, right.term, environment, node)
                arith_map = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "rem"}
                return _Binding(
                    _apps(_constant(f"int_{arith_map[operator]}_{spec.name}"), left.term, right.term), spec.const
                )
            raise self.fail("type", f"operator '{operator}' is not defined on integer type '{spec.name}'", node)
        if operator in {"&", "|", "^"}:
            raise self.fail(
                "type",
                f"bitwise operator '{operator}' requires a fixed-width integer operand; Nat does not support bitwise operations",
                node,
            )
        binding = self.globals.get(operator)
        if binding is None:
            raise self.fail("unsupported", f"operator '{operator}' is unsupported")
        signature = self.whnf(binding.type)
        self.unify(left.type, signature.args[0])
        signature = self.whnf(signature.args[1])
        self.unify(right.type, signature.args[0])
        return _Binding(_apps(binding.term, left.term, right.term), signature.args[1])

    def _structural_eq_bool(
        self: _Elaborator, operand_type: _Term, left_term: _Term, right_term: _Term, node: Node
    ) -> _Term:
        ty_w = self.whnf(operand_type)
        int_spec = self._int_spec(ty_w)
        if int_spec is not None:
            return _apps(_constant(f"int_eq_{int_spec.name}"), left_term, right_term)
        if ty_w == _NAT:
            return _apps(_constant("eq_nat"), left_term, right_term)
        if ty_w == _BOOL:
            return _apps(_constant("eq_bool"), left_term, right_term)
        if ty_w == _CHAR:
            return _apps(_constant("char_eq"), left_term, right_term)
        if ty_w == _UNIT:
            return _apps(_constant("eq_unit"), left_term, right_term)
        if ty_w.kind == "prod":
            t1, t2 = ty_w.args[0], ty_w.args[1]
            l1 = _apps(_constant("Fst"), t1, t2, left_term)
            r1 = _apps(_constant("Fst"), t1, t2, right_term)
            l2 = _apps(_constant("Snd"), t1, t2, left_term)
            r2 = _apps(_constant("Snd"), t1, t2, right_term)
            return _apps(
                _constant("&&"),
                self._structural_eq_bool(t1, l1, r1, node),
                self._structural_eq_bool(t2, l2, r2, node),
            )
        head, targs = self.spine(ty_w)
        if head == _constant("Vec") and len(targs) == 2:
            elem_t, len_t = targs
            seq_l = _apps(_constant("Vec_Model"), elem_t, len_t, left_term)
            seq_r = _apps(_constant("Vec_Model"), elem_t, len_t, right_term)
            return self._structural_eq_bool(_app(_constant("Seq"), elem_t), seq_l, seq_r, node)
        if head == _constant("Seq") and len(targs) == 1:
            elem_t = targs[0]
            vx = self.fresh(elem_t)
            vy = self.fresh(elem_t)
            eq_body = self._structural_eq_bool(elem_t, vx, vy, node)
            eq_lam = _term("lam", elem_t, _term("lam", elem_t, eq_body, value=vy.value), value=vx.value)
            return _apps(_constant("Seq_Eq"), elem_t, eq_lam, left_term, right_term)
        if head.kind == "const" and isinstance(head.value, str) and head.value in self.records_by_type:
            rinfo = self.records_by_type[head.value]
            if rinfo.is_dependent:
                raise self.fail(
                    "unsupported",
                    f"Boolean equality is not supported on dependent record '{rinfo.name}'",
                    node,
                )
            if not rinfo.fields:
                return _apps(_constant("eq_unit"), _term("unit"), _term("unit"))
            conj: _Term | None = None
            for rf in rinfo.fields:
                f_ty = self._instantiate_record_type(rinfo, targs, rf.type)
                l_f = _apps(_constant(rf.proj_const), *targs, left_term)
                r_f = _apps(_constant(rf.proj_const), *targs, right_term)
                step_eq = self._structural_eq_bool(f_ty, l_f, r_f, node)
                conj = step_eq if conj is None else _apps(_constant("&&"), conj, step_eq)
            return cast("_Term", conj)
        if head.kind == "const" and isinstance(head.value, str) and head.value in self.unions_by_type:
            uinfo = self.unions_by_type[head.value]
            if any(c.is_dependent for c in uinfo.constructors):
                raise self.fail(
                    "unsupported",
                    f"Boolean equality is not supported on dependent union '{uinfo.name}'",
                    node,
                )
            suffix_inst = [
                self._instantiate_generic_type(uinfo.generic_vars, targs, st)
                for st in uinfo.suffix_types
            ]
            payload_inst = [
                self._instantiate_generic_type(uinfo.generic_vars, targs, uc.payload_type)
                for uc in uinfo.constructors
            ]

            def match_union_step(idx: int, l_rem: _Term, r_rem: _Term) -> _Term:
                p_ty = payload_inst[idx]
                s_ty = suffix_inst[idx]
                if idx == len(uinfo.constructors) - 1:
                    if len(uinfo.constructors) == 1 and len(uinfo.constructors[0].fields) == 1:
                        f0_ty = self._instantiate_generic_type(
                            uinfo.generic_vars, targs, uinfo.constructors[0].fields[0].type
                        )
                        l_f0 = _apps(_constant("Fst"), f0_ty, _UNIT, l_rem)
                        r_f0 = _apps(_constant("Fst"), f0_ty, _UNIT, r_rem)
                        return self._structural_eq_bool(f0_ty, l_f0, r_f0, node)
                    return self._structural_eq_bool(p_ty, l_rem, r_rem, node)
                rest_ty = suffix_inst[idx + 1]
                l_motive_v = self.fresh(s_ty)
                l_motive = _term("lam", s_ty, _BOOL, value=l_motive_v.value)
                ll_v = self.fresh(p_ty)
                lr_v = self.fresh(rest_ty)
                r_motive_v1 = self.fresh(s_ty)
                r_motive1 = _term("lam", s_ty, _BOOL, value=r_motive_v1.value)
                rl_v1 = self.fresh(p_ty)
                rr_v1 = self.fresh(rest_ty)
                left_arm_body = _term(
                    "sum_match",
                    r_motive1,
                    r_rem,
                    _term("lam", p_ty, self._structural_eq_bool(p_ty, ll_v, rl_v1, node), value=rl_v1.value),
                    _term("lam", rest_ty, _term("bool", value=0), value=rr_v1.value),
                )
                r_motive_v2 = self.fresh(s_ty)
                r_motive2 = _term("lam", s_ty, _BOOL, value=r_motive_v2.value)
                rl_v2 = self.fresh(p_ty)
                rr_v2 = self.fresh(rest_ty)
                right_arm_body = _term(
                    "sum_match",
                    r_motive2,
                    r_rem,
                    _term("lam", p_ty, _term("bool", value=0), value=rl_v2.value),
                    _term("lam", rest_ty, match_union_step(idx + 1, lr_v, rr_v2), value=rr_v2.value),
                )
                return _term(
                    "sum_match",
                    l_motive,
                    l_rem,
                    _term("lam", p_ty, left_arm_body, value=ll_v.value),
                    _term("lam", rest_ty, right_arm_body, value=lr_v.value),
                )

            return match_union_step(0, left_term, right_term)
        raise self.fail(
            "unsupported",
            "Boolean equality is defined only on Nat, bool, char, Unit, fixed-width integers, tuples, Vec, Seq, and non-dependent records/unions",
            node,
        )

    def _elaborate_index(self: _Elaborator, node: Node, environment: dict[str, _Binding]) -> _Binding:
        self.site = node
        recv_node = self.node(node["value"])
        idx_node = self.node(node["index"])
        recv_b = self.expression(recv_node, environment)
        recv_ty = self.whnf(recv_b.type)
        head, targs = self.spine(recv_ty)
        if head == _constant("Span") and len(targs) == 1 and self.whnf(targs[0]) == _U8:
            idx_t = self.check(idx_node, _USIZE, environment)
            self._check_span_can_read(recv_b.term, environment, node)
            len_t = _apps(_constant("Span_Length"), _U8, recv_b.term)
            in_bounds = _apps(_constant("int_lt_usize"), idx_t, len_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", "cannot prove Span index is within Span.Length bounds", node)
            return _Binding(_apps(_constant("Span_Read"), _U8, recv_b.term, idx_t), _U8)
        if head == _constant("Slots") and len(targs) == 2:
            elem_t, cap_t = targs
            idx_t = self._slots_usize_arg(idx_node, environment)
            can_r = _apps(_constant("Slots_CanRead"), elem_t, cap_t, recv_b.term)
            if not self._prove_bool_precondition(can_r, environment):
                raise self.fail("type", "cannot prove Slots has valid tag and read permission (Slots.CanRead)", node)
            live_t = _apps(_constant("Slots_LiveCount"), elem_t, cap_t, recv_b.term)
            in_live = _apps(_constant("int_lt_usize"), idx_t, live_t)
            if not self._prove_bool_precondition(in_live, environment):
                raise self.fail(
                    "type",
                    "cannot read from a vacant or out-of-bounds slot; prove index < LiveCount (LivePrefix)",
                    node,
                )
            d_val = self._default_term_for_type(elem_t)
            return _Binding(_apps(_constant("Slots_Read"), elem_t, cap_t, d_val, recv_b.term, idx_t), elem_t)
        if head == _constant("Seq") and len(targs) == 1:
            elem_t = targs[0]
            idx_t = self._seq_nat_arg(idx_node, environment)
            cnt_t = _apps(_constant("Seq_Count"), elem_t, recv_b.term)
            in_bounds = _apps(_constant("<"), idx_t, cnt_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", "cannot prove Seq index is within Seq.Count bounds", node)
            d_val = self._default_term_for_type(elem_t)
            return _Binding(_apps(_constant("Seq_At"), elem_t, d_val, recv_b.term, idx_t), elem_t)
        if head == _constant("Vec") and len(targs) == 2:
            elem_t, len_t = targs
            if not self._is_unsuffixed_int_expr(idx_node):
                saved_idx_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                idx_b = self.expression(idx_node, environment)
                idx_head, _ = self.spine(self.whnf(idx_b.type))
                if idx_head == _constant("Fin"):
                    self.unify(idx_b.type, _app(_constant("Fin"), len_t))
                    return _Binding(_apps(_constant("At"), elem_t, len_t, recv_b.term, idx_b.term), elem_t)
                self.metas = saved_idx_m
            idx_t = self._seq_nat_arg(idx_node, environment)
            in_bounds = _apps(_constant("<"), idx_t, len_t)
            if not self._prove_bool_precondition(in_bounds, environment):
                raise self.fail("type", "cannot prove Vec index is within length bounds", node)
            d_val = self._default_term_for_type(elem_t)
            return _Binding(_apps(_constant("Vec_At_Nat"), elem_t, len_t, d_val, idx_t, recv_b.term), elem_t)
        raise self.fail(
            "type",
            "indexing requires a Span<byte>, Slots<T, capacity>, Seq<T> or Vec<T, n> operand",
            node,
        )

    def _elaborate_interface_method_call(
        self: _Elaborator,
        node: Node,
        iface: _InterfaceInfo,
        mspec: _InterfaceMethodSpec,
        iface_gen_args: list[Node],
        pre_evaluated_recv: _Binding | None,
        call_args: list[Node],
        environment: dict[str, _Binding],
    ) -> _Binding:
        self.site = node
        if iface_gen_args and len(iface_gen_args) != len(iface.generic_vars):
            raise self.fail(
                "type",
                f"interface '{iface.name}' expects {len(iface.generic_vars)} generic arguments, got {len(iface_gen_args)}",
                node,
            )
        type_args: list[_Term] = []
        for idx, gv in enumerate(iface.generic_vars):
            dom = self.types[cast("int", gv.value)]
            for prev_gv, prev_t in zip(iface.generic_vars[:idx], type_args, strict=True):
                dom = self.substitute(dom, cast("int", prev_gv.value), prev_t)
            if iface_gen_args:
                type_args.append(self.argument(iface_gen_args[idx], dom, environment))
            else:
                type_args.append(self.meta(dom, environment))
        m_gen_args: list[_Term] = []
        for idx, mgv in enumerate(mspec.generic_vars):
            dom = self._instantiate_generic_type(
                iface.generic_vars, type_args, self.types[cast("int", mgv.value)]
            )
            for prev_mgv, prev_mt in zip(mspec.generic_vars[:idx], m_gen_args, strict=True):
                dom = self.substitute(dom, cast("int", prev_mgv.value), prev_mt)
            m_gen_args.append(self.meta(dom, environment))
        arg_terms: list[_Term] = []
        loan_targets: dict[int, tuple[Node, _Term]] = {}
        seen_loan_names: set[str] = set()
        all_arg_var_names: set[str] = set()
        out_loan_names: set[str] = set()
        if mspec.nullary:
            if pre_evaluated_recv is not None or call_args:
                got_n = (1 if pre_evaluated_recv is not None else 0) + len(call_args)
                raise self.fail(
                    "type",
                    f"interface method '{iface.name}.{mspec.name}' expects 0 arguments, got {got_n}",
                    node,
                )
            arg_terms.append(_term("unit"))
            if self.expected_call_type is not None:
                expected_ret = self._instantiate_generic_type(
                    iface.generic_vars, type_args, mspec.return_type
                )
                for mgv, mgt in zip(mspec.generic_vars, m_gen_args, strict=True):
                    expected_ret = self.substitute(expected_ret, cast("int", mgv.value), mgt)
                self._try_unify(expected_ret, self.expected_call_type)
        else:
            total_given = (1 if pre_evaluated_recv is not None else 0) + len(call_args)
            if total_given != len(mspec.param_vars):
                raise self.fail(
                    "type",
                    f"interface method '{iface.name}.{mspec.name}' expects {len(mspec.param_vars)} arguments, got {total_given}",
                    node,
                )
            labeled_seen = False
            for idx, pvar in enumerate(mspec.param_vars):
                p_dom = self._instantiate_generic_type(
                    iface.generic_vars, type_args, self.types[cast("int", pvar.value)]
                )
                for mgv, mgt in zip(mspec.generic_vars, m_gen_args, strict=True):
                    p_dom = self.substitute(p_dom, cast("int", mgv.value), mgt)
                for j in range(idx):
                    p_dom = self.substitute(p_dom, cast("int", mspec.param_vars[j].value), arg_terms[j])
                if idx == 0 and pre_evaluated_recv is not None:
                    self.unify(pre_evaluated_recv.type, p_dom)
                    arg_terms.append(pre_evaluated_recv.term)
                    continue
                arg_node = call_args[idx - (1 if pre_evaluated_recv is not None else 0)]
                self.node(arg_node, "argument")
                if arg_node["label"] is not None:
                    if pre_evaluated_recv is not None:
                        raise self.fail(
                            "name",
                            "labeled arguments are not supported on receiver-syntax interface calls",
                            arg_node,
                        )
                    labeled_seen = True
                    lbl = self.name(arg_node["label"])
                    if lbl != mspec.param_labels[idx]:
                        raise self.fail(
                            "name",
                            f"expected argument label '{mspec.param_labels[idx]}', got '{lbl}'",
                            arg_node,
                        )
                elif labeled_seen:
                    raise self.fail(
                        "name",
                        "positional arguments cannot follow a labeled argument",
                        arg_node,
                    )
                p_mod = mspec.param_modifiers[idx]
                is_out_param = p_mod == "out"
                is_ref_param = p_mod == "ref"
                arg_val_node = self._unwrap_group(self.node(arg_node["value"]))
                arg_mod = (
                    cast("Node", arg_val_node["operator"]).get("text")
                    if (
                        arg_val_node["kind"] == "unary"
                        and isinstance(arg_val_node.get("operator"), dict)
                        and cast("Node", arg_val_node["operator"]).get("text") in {"ref", "in", "out"}
                    )
                    else None
                )
                if is_out_param and arg_mod != "out":
                    raise self.fail(
                        "type", "an 'out' parameter requires an 'out' call-site argument modifier", arg_node
                    )
                if not is_out_param and arg_mod == "out":
                    raise self.fail(
                        "type", "'out' call-site argument modifier requires an 'out' parameter", arg_node
                    )
                if arg_mod == "out":
                    arg_ident_node = self._unwrap_group(self.node(arg_val_node["value"]))
                    if arg_ident_node["kind"] != "name":
                        raise self.fail(
                            "type", "'out' argument target must be a mutable local or loan variable", arg_node
                        )
                    arg_vname = self.name(arg_ident_node["name"])
                    if arg_vname not in self.mutable_locals:
                        raise self.fail(
                            "type", f"cannot pass immutable binding '{arg_vname}' as an 'out' argument", arg_node
                        )
                    if arg_vname in all_arg_var_names:
                        raise self.fail("type", f"overlapping loan for '{arg_vname}' in call", arg_node)
                    seen_loan_names.add(arg_vname)
                    all_arg_var_names.add(arg_vname)
                    out_loan_names.add(arg_vname)
                    target_b = self.lookup(arg_vname, environment)
                    self.site = arg_node
                    self.unify(target_b.type, p_dom)
                    arg_terms.append(target_b.term)
                    loan_targets[idx] = (arg_ident_node, p_dom)
                else:
                    val_node = (
                        self._unwrap_group(self.node(arg_val_node["value"]))
                        if arg_mod in {"ref", "in"}
                        else self.node(arg_node["value"])
                    )
                    if val_node["kind"] == "name":
                        arg_vname = self.name(val_node["name"])
                        if is_ref_param or arg_mod == "ref":
                            if arg_vname not in self.mutable_locals:
                                raise self.fail(
                                    "type",
                                    f"cannot pass immutable binding '{arg_vname}' as a 'ref' argument",
                                    arg_node,
                                )
                            if arg_vname in all_arg_var_names:
                                raise self.fail("type", f"overlapping loan for '{arg_vname}' in call", arg_node)
                            seen_loan_names.add(arg_vname)
                            loan_targets[idx] = (val_node, p_dom)
                        elif arg_vname in seen_loan_names:
                            raise self.fail("type", f"overlapping loan for '{arg_vname}' in call", arg_node)
                        all_arg_var_names.add(arg_vname)
                    if self.whnf(p_dom).kind == "meta":
                        arg_b = self.expression(val_node, environment)
                        self.unify(p_dom, arg_b.type)
                        arg_terms.append(arg_b.term)
                    else:
                        arg_terms.append(self.check(val_node, p_dom, environment))
            if self.expected_call_type is not None:
                expected_ret = self._instantiate_generic_type(iface.generic_vars, type_args, mspec.return_type)
                for mgv, mgt in zip(mspec.generic_vars, m_gen_args, strict=True):
                    expected_ret = self.substitute(expected_ret, cast("int", mgv.value), mgt)
                for j, pv in enumerate(mspec.param_vars):
                    expected_ret = self.substitute(expected_ret, cast("int", pv.value), arg_terms[j])
                self._try_unify(expected_ret, self.expected_call_type)
        resolved_targs = tuple(self.whnf(t) for t in type_args)
        witness_dict, ensures_dict = self._resolve_single_interface_witness(
            iface.name, resolved_targs, environment, node
        )
        fn_term = witness_dict[mspec.name].term
        all_spec_vars = [*iface.generic_vars, *mspec.generic_vars, *mspec.param_vars]
        all_call_vals = [*resolved_targs, *m_gen_args, *arg_terms]
        for _, req_t in mspec.preconditions:
            inst_req = req_t
            for sv, cv in zip(all_spec_vars, all_call_vals, strict=True):
                inst_req = self.substitute(inst_req, cast("int", sv.value), cv)
            self._check_precondition_term(inst_req, environment, node)
        res_term = _apps(fn_term, *m_gen_args, *arg_terms)
        res_type = mspec.return_type
        for sv, cv in zip(all_spec_vars, all_call_vals, strict=True):
            res_type = self.substitute(res_type, cast("int", sv.value), cv)
        for vname in out_loan_names:
            self.uninitialized_out_params.discard(vname)
        for t_node, t_dom in loan_targets.values():
            upd_term = self.fresh(t_dom)
            self.last_call_updates.append((t_node, _Binding(upd_term, t_dom)))
        if mspec.name in ensures_dict:
            rem_m_ids, ens_props = ensures_dict[mspec.name]
            rem_vals = [*m_gen_args, *arg_terms]
            for ens_t in ens_props:
                inst_ens = ens_t
                for pid, aval in zip(rem_m_ids, rem_vals, strict=True):
                    inst_ens = self.substitute(inst_ens, pid, aval)
                self.active_facts.append(self.whnf(inst_ens))
        return _Binding(res_term, res_type)

    def _elaborate_record_method_call(
        self: _Elaborator,
        node: Node,
        rinfo: _RecordInfo,
        rmethod: _RecordMethod,
        rec_targs: list[_Term],
        recv_b: _Binding,
        gen_args: list[Node],
        call_args: list[Node],
        environment: dict[str, _Binding],
        recv_node: Node | None = None,
    ) -> _Binding:
        self.site = node
        if recv_node is not None:
            unwrapped_recv = self._unwrap_group(recv_node)
            if unwrapped_recv["kind"] == "name":
                r_vname = self.name(unwrapped_recv["name"])
                lifted_set = self.lifted_invariants.get(r_vname)
                if lifted_set is not None and len(lifted_set) > 0:
                    clause_n = min(lifted_set)
                    raise self.fail(
                        "type",
                        f"cannot call method on record '{r_vname}' while invariant '{clause_n}' is lifted",
                        node,
                    )
        term = rmethod.binding.term
        value_type = rmethod.binding.type
        for r_targ in rec_targs:
            value_type = self.whnf(value_type)
            if value_type.kind != "pi":
                raise self.fail("type", "invalid record method generic telescope", node)
            term = _app(term, r_targ)
            value_type = self.substitute(value_type.args[1], cast("int", value_type.value), r_targ)
        if gen_args and len(gen_args) != rmethod.method_generics:
            raise self.fail(
                "type",
                f"expected {rmethod.method_generics} explicit generic arguments on '{rinfo.name}.{rmethod.name}', got {len(gen_args)}",
                node,
            )
        for idx in range(rmethod.method_generics):
            value_type = self.whnf(value_type)
            if value_type.kind != "pi":
                raise self.fail("type", "invalid record method generic telescope", node)
            domain = value_type.args[0]
            g_arg = self.argument(gen_args[idx], domain, environment) if gen_args else self.meta(domain, environment)
            term = _app(term, g_arg)
            value_type = self.substitute(value_type.args[1], cast("int", value_type.value), g_arg)
        value_type = self.whnf(value_type)
        if value_type.kind != "pi":
            raise self.fail("type", "invalid record method receiver parameter", node)
        term = _app(term, recv_b.term)
        value_type = self.substitute(value_type.args[1], cast("int", value_type.value), recv_b.term)
        if not call_args and rmethod.method_const in self.callable_preconditions:
            _, partial_args = self.spine(term)
            full_args = [*partial_args, _term("unit")]
            for param_ids, req_term in self.callable_preconditions[rmethod.method_const]:
                if len(full_args) >= len(param_ids):
                    inst_req = req_term
                    for pid, arg_val in zip(param_ids, full_args, strict=False):
                        inst_req = self.substitute(inst_req, pid, arg_val)
                    self._check_precondition_term(inst_req, environment, node)
        return self.apply(_Binding(term, value_type), call_args, environment)

    def _elaborate_int_intrinsic(
        self: _Elaborator,
        name: str,
        arg_nodes: list[Node],
        environment: dict[str, _Binding],
        node: Node,
        *,
        receiver: _Binding | None = None,
        expected_spec: _IntSpec | None = None,
    ) -> _Binding:
        for arg_n in arg_nodes:
            self.node(arg_n, "argument")
        val_nodes = [self.node(a["value"]) for a in arg_nodes]
        unary_ops = {"WrappingNeg": "wrap_neg", "SaturatingNeg": "sat_neg", "CheckedNeg": "chk_neg"}
        shift_ops = {
            "ShiftLeft": "shl",
            "ShiftRight": "shr",
            "WrappingShiftLeft": "wrap_shl",
            "CheckedShiftLeft": "chk_shl",
            "CheckedShiftRight": "chk_shr",
        }
        binary_ops = {
            "WrappingAdd": "wrap_add",
            "WrappingSub": "wrap_sub",
            "WrappingMul": "wrap_mul",
            "SaturatingAdd": "sat_add",
            "SaturatingSub": "sat_sub",
            "SaturatingMul": "sat_mul",
            "CheckedAdd": "chk_add",
            "CheckedSub": "chk_sub",
            "CheckedMul": "chk_mul",
            "CheckedDiv": "chk_div",
            "CheckedRem": "chk_rem",
        }
        is_checked = name.startswith("Checked")
        ae_const = _constant(self.unions["ArithmeticError"].type_const)
        res_const = _constant(self.unions["Result"].type_const)
        if name in unary_ops:
            if receiver is not None:
                if val_nodes:
                    raise self.fail("type", f"'{name}' expects no additional arguments when called on a receiver", node)
                op_binding = receiver
            else:
                if len(val_nodes) != 1:
                    raise self.fail("type", f"'{name}' expects 1 integer argument, got {len(val_nodes)}", node)
                if expected_spec is not None:
                    op_binding = _Binding(
                        self.check(val_nodes[0], expected_spec.const, environment), expected_spec.const
                    )
                else:
                    op_binding = self.expression(val_nodes[0], environment)
            spec = self._int_spec(op_binding.type)
            if spec is None or (expected_spec is not None and spec.name != expected_spec.name):
                raise self.fail("type", f"'{name}' requires a fixed-width integer operand", node)
            ret_type = _apps(res_const, spec.const, ae_const) if is_checked else spec.const
            return _Binding(_app(_constant(f"int_{unary_ops[name]}_{spec.name}"), op_binding.term), ret_type)
        if name in shift_ops:
            if receiver is not None:
                if len(val_nodes) != 1:
                    raise self.fail("type", f"'{name}' expects 1 shift-count argument when called on a receiver", node)
                lhs_binding = receiver
                count_node = val_nodes[0]
            else:
                if len(val_nodes) != 2:
                    raise self.fail("type", f"'{name}' expects (value, count) arguments, got {len(val_nodes)}", node)
                if expected_spec is not None:
                    lhs_binding = _Binding(
                        self.check(val_nodes[0], expected_spec.const, environment), expected_spec.const
                    )
                else:
                    lhs_binding = self.expression(val_nodes[0], environment)
                count_node = val_nodes[1]
            spec = self._int_spec(lhs_binding.type)
            if spec is None or (expected_spec is not None and spec.name != expected_spec.name):
                raise self.fail("type", f"'{name}' requires a fixed-width integer value operand", node)
            count_term = self.check(count_node, _USIZE, environment)
            if not is_checked:
                facts = self._expand_bool_facts([*self.active_facts, *self._fact_bool_terms((), environment)])
                c_lo, c_hi, _ = self._term_bounds(count_term, _INT_SPECS["usize"], facts)
                if c_lo <= c_hi:
                    count_ok = c_lo >= 0 and (
                        c_hi < spec.bits
                        or self._prove_comparison(
                            "lt",
                            _INT_SPECS["usize"],
                            count_term,
                            _int_term(_INT_SPECS["usize"], spec.bits),
                            facts,
                        )
                    )
                    if not count_ok:
                        raise self.fail(
                            "type",
                            f"'{name}' on '{spec.name}' requires shift count < {spec.bits}; "
                            f"prove count < {spec.bits} or use Checked{name.removeprefix('Wrapping')}",
                            node,
                        )
                    if name == "ShiftLeft":
                        v_lo, v_hi, _ = self._term_bounds(lhs_binding.term, spec, facts)
                        eff_lo = max(0, c_lo)
                        eff_hi = min(c_hi, spec.bits - 1)
                        shifted = (v_lo << eff_lo, v_lo << eff_hi, v_hi << eff_lo, v_hi << eff_hi)
                        s_lo, s_hi = min(shifted), max(shifted)
                        if not (spec.min_val <= s_lo and s_hi <= spec.max_val):
                            raise self.fail(
                                "type",
                                f"ShiftLeft on '{spec.name}' may overflow ({s_lo}..{s_hi} is not within {spec.min_val}..{spec.max_val}); "
                                "prove the range or use WrappingShiftLeft or CheckedShiftLeft",
                                node,
                            )
            ret_type = _apps(res_const, spec.const, ae_const) if is_checked else spec.const
            return _Binding(
                _apps(_constant(f"int_{shift_ops[name]}_{spec.name}"), lhs_binding.term, count_term), ret_type
            )
        # Binary total/checked arithmetic
        if receiver is not None:
            if len(val_nodes) != 1:
                raise self.fail("type", f"'{name}' expects 1 right-hand argument when called on a receiver", node)
            lhs_b = receiver
            rhs_b = _Binding(self.check(val_nodes[0], lhs_b.type, environment), lhs_b.type)
        else:
            if len(val_nodes) != 2:
                raise self.fail("type", f"'{name}' expects 2 integer arguments, got {len(val_nodes)}", node)
            if expected_spec is not None:
                lhs_b = _Binding(self.check(val_nodes[0], expected_spec.const, environment), expected_spec.const)
                rhs_b = _Binding(self.check(val_nodes[1], expected_spec.const, environment), expected_spec.const)
            elif self._is_unsuffixed_int_expr(val_nodes[0]) and not self._is_unsuffixed_int_expr(val_nodes[1]):
                rhs_b = self.expression(val_nodes[1], environment)
                lhs_b = _Binding(self.check(val_nodes[0], rhs_b.type, environment), rhs_b.type)
            elif self._is_unsuffixed_int_expr(val_nodes[1]) and not self._is_unsuffixed_int_expr(val_nodes[0]):
                lhs_b = self.expression(val_nodes[0], environment)
                rhs_b = _Binding(self.check(val_nodes[1], lhs_b.type, environment), lhs_b.type)
            else:
                lhs_b = self.expression(val_nodes[0], environment)
                rhs_b = self.expression(val_nodes[1], environment)
        self.unify(lhs_b.type, rhs_b.type)
        spec = self._int_spec(lhs_b.type)
        if spec is None or (expected_spec is not None and spec.name != expected_spec.name):
            raise self.fail("type", f"'{name}' requires fixed-width integer operands", node)
        ret_type = _apps(res_const, spec.const, ae_const) if is_checked else spec.const
        return _Binding(
            _apps(_constant(f"int_{binary_ops[name]}_{spec.name}"), lhs_b.term, rhs_b.term), ret_type
        )

    def expression(self: _Elaborator, node: Node, environment: dict[str, _Binding]) -> _Binding:
        self.tick()
        self.site = node
        kind = node["kind"]
        if kind == "nat":
            mag = _parse_numeric_magnitude(cast("str", node["value"]))
            suffix = cast("str", node["suffix"])
            if suffix:
                canonical = "u8" if suffix == "byte" else _NUMERICS_ALIASES.get(suffix, suffix)
                spec = _INT_SPECS[canonical]
                if not spec.min_val <= mag <= spec.max_val:
                    raise self.fail(
                        "type",
                        f"integer literal {mag} is out of range for '{spec.name}' ({spec.min_val}..{spec.max_val})",
                        node,
                    )
                return _Binding(_int_term(spec, mag), spec.const)
            return _Binding(_term("nat", value=mag), _NAT)
        if kind == "hole":
            raise self.fail("inference", "unfinished named proof hole; provide an explicit term")
        if kind == "bool":
            return _Binding(_term("bool", value=int(cast("bool", node["value"]))), _BOOL)
        if kind == "character":
            cp = self._decode_char_literal(cast("str", node["value"]), node)
            return _Binding(_term("char", value=cp), _CHAR)
        if kind == "unit":
            return _Binding(_term("unit"), _UNIT)
        if kind == "index":
            return self._elaborate_index(node, environment)
        if kind == "string":
            return self._bytes_binding(self._decode_string_literal(cast("str", node["value"]), node))
        if kind == "interpolated_string":
            raise self.fail(
                "type",
                "interpolated format template requires an explicit Format.Write destination buffer",
                node,
            )
        if kind == "member":
            recv_node = self.node(node["value"])
            member_name = self.name(node["name"])
            type_spec = self._resolve_int_type_receiver(recv_node, environment)
            if type_spec is not None:
                if member_name == "Min":
                    return _Binding(_int_term(type_spec, type_spec.min_val), type_spec.const)
                if member_name == "Max":
                    return _Binding(_int_term(type_spec, type_spec.max_val), type_spec.const)
                if member_name == "Bits":
                    return _Binding(_term("nat", value=type_spec.bits), _NAT)
                raise self.fail(
                    "name", f"integer type '{type_spec.name}' has no associated member '{member_name}'", node
                )
            full_path = self._dotted_member_path(node)
            if full_path is not None and full_path in self.inaccessible_private_symbols:
                mod_origin = self.inaccessible_private_symbols[full_path]
                raise self.fail(
                    "name",
                    f"cannot access private declaration '{full_path}' from module '{mod_origin}'",
                    node,
                )
            if (
                full_path is not None
                and full_path in self.globals
                and full_path.split(".", 1)[0] not in environment
            ):
                return self.lookup(full_path, environment)
            return self._project_member(
                self.expression(recv_node, environment),
                member_name,
                node,
            )
        if kind in {"name", "operator"}:
            name = self.operator(node["name"]) if kind == "operator" else self.name(node["name"])
            if kind == "name" and name in self.uninitialized_out_params:
                raise self.fail("type", f"cannot read uninitialized 'out' parameter '{name}'", node)
            if name == "Type":
                return _Binding(_SORT, _term("sort", value=1))
            if name == "Prop":
                return _Binding(_PROP, _SORT)
            if name == "_":
                value_type = self.meta(_SORT, environment)
                return _Binding(self.meta(value_type, environment), value_type)
            if kind == "name" and name not in environment and name in self.records:
                if self.static_forbidden is not None and id(self.records[name].ctor_binding) in self.static_forbidden:
                    raise self.fail("type", f"constant initializer depends on nonstatic binding '{name}'")
                return self.instantiate(self.records[name].ctor_binding, environment)
            return self.lookup(name, environment)
        if kind == "group":
            return self.expression(self.node(node["value"]), environment)
        if kind == "type_expression":
            value = self.type(self.node(node["type"]), environment)
            return _Binding(value, self.infer(value))
        if kind == "tuple":
            values = [self.expression(value, environment) for value in self.nodes(node["values"])]
            if len(values) < 2:
                raise self.fail("protocol", "a product requires at least two components")
            result = values[-1]
            for value in reversed(values[:-1]):
                result = _Binding(_term("pair", value.type, result.type, value.term, result.term), _term("prod", value.type, result.type))
            return result
        if kind == "generic_application":
            target = self.node(node["value"])
            if target["kind"] != "name":
                raise self.fail("unsupported", "explicit generics require a declared callable name")
            target_name = self.name(target["name"])
            if target_name not in environment and target_name in self.records:
                binding = self.records[target_name].ctor_binding
            else:
                binding = self.lookup(target_name, environment, raw=True)
            return self.instantiate(binding, environment, self.nodes(node["arguments"]))
        if kind == "call":
            callee = self.node(node["callee"])
            call_args = self.nodes(node["arguments"])
            if callee["kind"] == "generic_application":
                base_callee = self.node(callee["value"])
                gen_args = self.nodes(callee["arguments"])
            else:
                base_callee = callee
                gen_args = []
            if base_callee["kind"] == "member":
                receiver = self.node(base_callee["value"])
                member_name = self.name(base_callee["name"])
                if (
                    receiver["kind"] == "name"
                    and self.name(receiver["name"]) in self.interfaces
                    and self.name(receiver["name"]) not in environment
                ):
                    iface = self.interfaces[self.name(receiver["name"])]
                    if member_name not in iface.methods:
                        raise self.fail(
                            "name",
                            f"interface '{iface.name}' has no method '{member_name}'",
                            node,
                        )
                    return self._elaborate_interface_method_call(
                        node, iface, iface.methods[member_name], gen_args, None, call_args, environment
                    )
                if (
                    receiver["kind"] == "generic_application"
                    and self.node(receiver["value"])["kind"] == "name"
                    and self.name(self.node(receiver["value"])["name"]) in self.interfaces
                    and self.name(self.node(receiver["value"])["name"]) not in environment
                ):
                    if gen_args:
                        raise self.fail(
                            "type",
                            "generic arguments cannot be specified on both interface and method in qualified call",
                            node,
                        )
                    iface = self.interfaces[self.name(self.node(receiver["value"])["name"])]
                    if member_name not in iface.methods:
                        raise self.fail(
                            "name",
                            f"interface '{iface.name}' has no method '{member_name}'",
                            node,
                        )
                    return self._elaborate_interface_method_call(
                        node,
                        iface,
                        iface.methods[member_name],
                        self.nodes(receiver["arguments"]),
                        None,
                        call_args,
                        environment,
                    )
                if receiver["kind"] == "name" and self.name(receiver["name"]) == "Seq" and "Seq" not in environment:
                    return self._elaborate_seq_intrinsic(node, member_name, gen_args, call_args, environment)
                if receiver["kind"] == "name" and self.name(receiver["name"]) == "Slots" and "Slots" not in environment:
                    return self._elaborate_slots_intrinsic(node, member_name, gen_args, call_args, environment)
                if not gen_args:
                    if (receiver["kind"] == "name"
                            and self.name(receiver["name"]) == "Format"
                            and member_name == "Write"):
                        return self._format_write(node, call_args, environment)
                    if receiver["kind"] == "name" and self.name(receiver["name"]) == "Span" and "Span" not in environment:
                        return self._elaborate_span_intrinsic(node, member_name, call_args, environment)
                    if receiver["kind"] == "name" and self.name(receiver["name"]) == "char" and "char" not in environment:
                        if member_name in {"From", "TryFrom"}:
                            if len(call_args) != 1:
                                raise self.fail("type", f"'char.{member_name}' expects 1 argument, got {len(call_args)}", node)
                            self.node(call_args[0], "argument")
                            src_b = self.expression(self.node(call_args[0]["value"]), environment)
                            src_w = self.whnf(src_b.type)
                            if member_name == "From":
                                if src_w == _CHAR:
                                    return _Binding(src_b.term, _CHAR)
                                if src_w == _U8:
                                    return _Binding(_app(_constant("char_from_u8"), src_b.term), _CHAR)
                                raise self.fail(
                                    "type",
                                    "'char.From' requires a byte/u8 or char operand; use 'char.TryFrom' for u32 or Nat",
                                    node,
                                )
                            res_const = _constant(self.unions["Result"].type_const)
                            ce_const = _constant(self.unions["ConversionError"].type_const)
                            ret_type = _apps(res_const, _CHAR, ce_const)
                            src_spec = self._int_spec(src_w)
                            if src_spec is not None and src_spec.name == "u32":
                                return _Binding(_app(_constant("char_try_from_u32"), src_b.term), ret_type)
                            if src_w == _NAT:
                                return _Binding(_app(_constant("char_try_from_Nat"), src_b.term), ret_type)
                            raise self.fail("type", "'char.TryFrom' requires a u32 or Nat operand", node)
                        raise self.fail("name", f"unknown char intrinsic 'char.{member_name}'", node)
                    dst_spec = self._resolve_int_type_receiver(receiver, environment)
                    if dst_spec is not None:
                        if member_name in {"From", "TryFrom"}:
                            if len(call_args) != 1:
                                raise self.fail(
                                    "type",
                                    f"'{dst_spec.name}.{member_name}' expects 1 argument, got {len(call_args)}",
                                    node,
                                )
                            self.node(call_args[0], "argument")
                            src_b = self.expression(self.node(call_args[0]["value"]), environment)
                            src_spec = self._int_spec(src_b.type)
                            if member_name == "From":
                                if dst_spec.name == "u32" and self.whnf(src_b.type) == _CHAR:
                                    return _Binding(_app(_constant("char_to_u32"), src_b.term), dst_spec.const)
                                if src_spec is None:
                                    raise self.fail(
                                        "type",
                                        f"'{dst_spec.name}.From' requires a fixed-width integer operand; use '{dst_spec.name}.TryFrom' for Nat",
                                        node,
                                    )
                                if not _allows_from_conversion(src_spec, dst_spec):
                                    raise self.fail(
                                        "type",
                                        f"'{dst_spec.name}.From' does not accept '{src_spec.name}' because the conversion may narrow or change sign; "
                                        f"use '{dst_spec.name}.TryFrom'",
                                        node,
                                    )
                                if src_spec.name == dst_spec.name:
                                    return _Binding(src_b.term, dst_spec.const)
                                return _Binding(
                                    _app(_constant(f"int_from_{src_spec.name}_{dst_spec.name}"), src_b.term),
                                    dst_spec.const,
                                )
                            res_const = _constant(self.unions["Result"].type_const)
                            ce_const = _constant(self.unions["ConversionError"].type_const)
                            ret_type = _apps(res_const, dst_spec.const, ce_const)
                            if src_spec is not None:
                                return _Binding(
                                    _app(_constant(f"int_try_from_{src_spec.name}_{dst_spec.name}"), src_b.term),
                                    ret_type,
                                )
                            if self.whnf(src_b.type) == _NAT:
                                return _Binding(
                                    _app(_constant(f"int_try_from_Nat_{dst_spec.name}"), src_b.term),
                                    ret_type,
                                )
                            raise self.fail(
                                "type",
                                f"'{dst_spec.name}.TryFrom' requires a fixed-width integer or Nat operand",
                                node,
                            )
                        if member_name in _INT_INTRINSICS:
                            return self._elaborate_int_intrinsic(
                                member_name, call_args, environment, node, expected_spec=dst_spec
                            )
                        raise self.fail(
                            "name",
                            f"integer type '{dst_spec.name}' has no associated function '{member_name}'",
                            node,
                        )
                    if self._dotted_member_path(receiver) == "Vela.Numerics" and member_name in _INT_INTRINSICS:
                        return self._elaborate_int_intrinsic(member_name, call_args, environment, node)
                    if (
                        member_name in _INT_INTRINSICS
                        or member_name in {"At", "Update", "Append", "Take", "Skip", "Slice", "Contains", "All", "Any"}
                        or member_name in {"LivePrefix", "VacantRange", "VacantSuffix", "PrefixModel", "Read", "Write"}
                    ):
                        recv_b = self.expression(receiver, environment)
                        if self._int_spec(recv_b.type) is not None and member_name in _INT_INTRINSICS:
                            return self._elaborate_int_intrinsic(
                                member_name, call_args, environment, node, receiver=recv_b
                            )
                        recv_head, recv_targs = self.spine(self.whnf(recv_b.type))
                        if recv_head == _constant("Seq") and len(recv_targs) == 1:
                            return self._elaborate_seq_method(
                                node, recv_b, recv_targs[0], member_name, call_args, environment
                            )
                        if (
                            recv_head == _constant("Slots")
                            and len(recv_targs) == 2
                            and member_name in {"LivePrefix", "VacantRange", "VacantSuffix", "PrefixModel", "Read", "Write"}
                        ):
                            return self._elaborate_slots_intrinsic(
                                node, member_name, gen_args, call_args, environment, receiver=recv_b
                            )
                saved_recv_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                recv_for_method: _Binding | None = None
                try:
                    recv_for_method = self.expression(receiver, environment)
                except Exception:
                    self.metas = saved_recv_m
                if recv_for_method is not None:
                    rm_head, rm_targs = self.spine(self.whnf(recv_for_method.type))
                    if (
                        rm_head.kind == "const"
                        and isinstance(rm_head.value, str)
                        and rm_head.value in self.records_by_type
                        and member_name in self.records_by_type[rm_head.value].methods
                    ):
                        rinfo = self.records_by_type[rm_head.value]
                        rmethod = rinfo.methods[member_name]
                        return self._elaborate_record_method_call(
                            node,
                            rinfo,
                            rmethod,
                            rm_targs,
                            recv_for_method,
                            gen_args,
                            call_args,
                            environment,
                            recv_node=receiver,
                        )
                    candidate_ifaces = [
                        iface
                        for iface in self.interfaces.values()
                        if member_name in iface.methods
                        and not iface.methods[member_name].nullary
                        and len(iface.methods[member_name].param_vars) == 1 + len(call_args)
                    ]
                    if len(candidate_ifaces) == 1:
                        iface = candidate_ifaces[0]
                        return self._elaborate_interface_method_call(
                            node,
                            iface,
                            iface.methods[member_name],
                            gen_args,
                            recv_for_method,
                            call_args,
                            environment,
                        )
                    if len(candidate_ifaces) > 1:
                        for iface in candidate_ifaces:
                            saved_try_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                            saved_try_f = list(self.active_facts)
                            try:
                                return self._elaborate_interface_method_call(
                                    node,
                                    iface,
                                    iface.methods[member_name],
                                    gen_args,
                                    recv_for_method,
                                    call_args,
                                    environment,
                                )
                            except Exception:
                                self.metas = saved_try_m
                                self.active_facts = saved_try_f
                    self.metas = saved_recv_m
            if base_callee["kind"] == "name":
                cname = self.name(base_callee["name"])
                if cname == "old" and "old" not in environment and not gen_args:
                    if len(call_args) != 1:
                        raise self.fail("type", f"'old(...)' expects 1 argument, got {len(call_args)}", node)
                    self.node(call_args[0], "argument")
                    if call_args[0]["label"] is not None:
                        raise self.fail("name", "'old(...)' does not accept labeled arguments", call_args[0])
                    if not self.entry_env:
                        raise self.fail("type", "'old(...)' requires an enclosing callable pre-state", node)
                    old_val_node = self.node(call_args[0]["value"])
                    unwrapped_old = self._unwrap_group(old_val_node)
                    while unwrapped_old["kind"] in {"member", "index"}:
                        unwrapped_old = self._unwrap_group(self.node(unwrapped_old["value"]))
                    if unwrapped_old["kind"] == "name" and self.name(unwrapped_old["name"]) in self.out_param_names:
                        raise self.fail(
                            "type",
                            f"cannot use 'old(...)' on write-only 'out' parameter '{self.name(unwrapped_old['name'])}'",
                            node,
                        )
                    saved_uninit_old = set(self.uninitialized_out_params)
                    self.uninitialized_out_params = set(self.out_param_names)
                    try:
                        return self.expression(old_val_node, self.entry_env)
                    finally:
                        self.uninitialized_out_params = saved_uninit_old
                if (
                    cname not in environment
                    and cname not in self.globals
                    and cname not in self.records
                ):
                    candidate_ifaces = [
                        iface
                        for iface in self.interfaces.values()
                        if cname in iface.methods
                    ]
                    if len(candidate_ifaces) == 1:
                        iface = candidate_ifaces[0]
                        return self._elaborate_interface_method_call(
                            node,
                            iface,
                            iface.methods[cname],
                            gen_args,
                            None,
                            call_args,
                            environment,
                        )
                    if len(candidate_ifaces) > 1:
                        for iface in candidate_ifaces:
                            saved_try_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                            saved_try_f = list(self.active_facts)
                            try:
                                return self._elaborate_interface_method_call(
                                    node,
                                    iface,
                                    iface.methods[cname],
                                    gen_args,
                                    None,
                                    call_args,
                                    environment,
                                )
                            except Exception:
                                self.metas = saved_try_m
                                self.active_facts = saved_try_f
                if (
                    cname in {"LivePrefix", "VacantRange", "VacantSuffix", "PrefixModel", "CopyRepresentation", "TransferType"}
                    and cname not in environment
                    and cname not in self.globals
                ):
                    return self._elaborate_slots_intrinsic(node, cname, gen_args, call_args, environment)
                if not gen_args and cname == "Nat" and "Nat" not in environment:
                    if len(call_args) != 1:
                        raise self.fail("type", f"'Nat(...)' expects 1 argument, got {len(call_args)}", node)
                    self.node(call_args[0], "argument")
                    arg_b = self.expression(self.node(call_args[0]["value"]), environment)
                    src_spec = self._int_spec(arg_b.type)
                    if src_spec is not None:
                        if src_spec.signed:
                            raise self.fail(
                                "type",
                                f"'Nat(...)' total injection requires an unsigned integer operand, got signed '{src_spec.name}'",
                                node,
                            )
                        return _Binding(_app(_constant(f"int_to_nat_{src_spec.name}"), arg_b.term), _NAT)
                    if self.whnf(arg_b.type) == _NAT:
                        return arg_b
                    if self.whnf(arg_b.type) == _CHAR:
                        return _Binding(_app(_constant("char_to_nat"), arg_b.term), _NAT)
                    raise self.fail(
                        "type", "'Nat(...)' conversion requires an unsigned fixed-width integer or char operand", node
                    )
                if not gen_args and cname in _INT_INTRINSICS and cname not in environment and cname not in self.globals:
                    return self._elaborate_int_intrinsic(cname, call_args, environment, node)
            return self.apply(self.expression(callee, environment), call_args, environment)
        if kind in {"lambda", "typed_lambda"}:
            return self.lambda_(node, environment)
        if kind == "let_expression":
            return self.expression(self.node(node["body"]), self.local(self.node(node["binding"]), environment))
        if kind == "if_expression":
            return self.if_expression(node, environment)
        if kind == "with_expression":
            return self.with_expression(node, environment)
        if kind == "is":
            return self._is_expression(node, environment)
        if kind == "match_expression":
            return self.match(node, environment, expression_arms=True)
        if kind == "block":
            return self.block(node, environment)
        if kind == "binary":
            return self._elaborate_binary(node, environment)
        if kind == "unary":
            return self._elaborate_unary(node, environment)
        if kind == "propagate":
            ret_type = self.current_return_type if self.current_return_type is not None else _UNIT
            return _Binding(
                self._elaborate_propagate(node, environment, ret_type, lambda _name, val, _env: val.term),
                ret_type,
            )
        raise self.fail("unsupported", f"expression '{kind}' requires the full frontend")

    def proposition(self: _Elaborator, node: Node, environment: dict[str, _Binding]) -> _Term:
        self.site = node
        if node["kind"] == "group":
            return self.proposition(self.node(node["value"]), environment)
        if node["kind"] == "let_expression":
            return self.proposition(self.node(node["body"]), self.local(self.node(node["binding"]), environment))
        if node["kind"] == "binary":
            operator = self.operator(node["operator"])
            if operator == "==":
                left_node = self.node(node["left"])
                right_node = self.node(node["right"])
                if self._is_unsuffixed_int_expr(left_node) and not self._is_unsuffixed_int_expr(right_node):
                    right_b = self.expression(right_node, environment)
                    left_t = self.check(left_node, right_b.type, environment)
                    self.unify(self.infer(right_b.type), _SORT)
                    return _apps(_constant("Eq"), right_b.type, left_t, right_b.term)
                left = self.expression(left_node, environment)
                right = self.check(right_node, left.type, environment)
                self.unify(self.infer(left.type), _SORT)
                return _apps(_constant("Eq"), left.type, left.term, right)
            if operator == "==>":
                domain = self.proposition(self.node(node["left"]), environment)
                return self.pi(domain, self.proposition(self.node(node["right"]), environment))
        if node["kind"] == "quantifier":
            quant = node["quantifier"]
            if quant not in {"forall", "exists"}:
                raise self.fail("unsupported", "only universal and existential propositions are supported")
            variables, extended = self.telescope([], self.nodes(node["parameters"]), environment)
            body = self.proposition(self.node(node["value"]), extended)
            if quant == "forall":
                return self.wrap("pi", variables, body)
            result = body
            for variable in reversed(variables):
                domain = self.types[cast("int", variable.value)]
                result = _term("ex", domain, _term("lam", domain, result, value=variable.value))
            return result
        value = self.expression(node, environment)
        self.unify(value.type, _PROP)
        return value.term
