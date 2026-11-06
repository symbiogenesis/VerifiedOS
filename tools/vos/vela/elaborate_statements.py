# SPDX-License-Identifier: Apache-2.0
"""Imperative statements, propagation, loops, scopes, and control-flow elaboration for Vela."""

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from vos.vela.ast import VelaError
from vos.vela.elaborate_protocol import _ASSIGN_OPERATORS
from vos.vela.elaborate_types import (
    _BOOL,
    _INT_SPECS,
    _NAT,
    _U8,
    _UNIT,
    _USIZE,
    Node,
    _app,
    _apps,
    _Binding,
    _constant,
    _int_term,
    _IntSpec,
    _Pat,
    _RecordInfo,
    _Term,
    _term,
)

if TYPE_CHECKING:
    from vos.vela.elaborate import _Elaborator


class _StatementsMixin:
    @staticmethod
    def _unwrap_group(node: Node) -> Node:
        while node["kind"] == "group" and isinstance(node.get("value"), dict):
            node = cast("Node", node["value"])
        return node

    def _is_propagatable_union(self: _Elaborator, value_type: _Term) -> bool:
        resolved = self.whnf(value_type)
        head, _ = self.spine(resolved)
        if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.unions_by_type:
            return False
        union_info = self.unions_by_type[head.value]
        if len(union_info.constructors) != 2:
            return False
        names = {c.name for c in union_info.constructors}
        return names in ({"None", "Some"}, {"Err", "Ok"})

    @staticmethod
    def _with_node_field(node: Node, key: str, value: object) -> Node:
        copied = dict(node)
        copied[key] = value
        return copied

    @classmethod
    def _make_list_rebuilder(
        cls, node: Node, key: str, items: list[Node], idx: int, inner_rebuild: Callable[[Node], Node]
    ) -> Callable[[Node], Node]:
        return lambda repl: cls._with_node_field(
            node, key, [*items[:idx], inner_rebuild(repl), *items[idx + 1:]]
        )

    @classmethod
    def _make_nested_list_rebuilder(
        cls,
        node: Node,
        key: str,
        items: list[Node],
        idx: int,
        item_node: Node,
        child_key: str,
        inner_rebuild: Callable[[Node], Node],
    ) -> Callable[[Node], Node]:
        return lambda repl: cls._with_node_field(
            node,
            key,
            [*items[:idx], cls._with_node_field(item_node, child_key, inner_rebuild(repl)), *items[idx + 1:]],
        )

    def _split_first_propagate(self: _Elaborator, node: Node) -> tuple[Node, Callable[[Node], Node]] | None:
        kind = node["kind"]
        if kind == "propagate":
            res_inner = self._split_first_propagate(self.node(node["value"]))
            if res_inner is not None:
                prop, inner_rebuild = res_inner
                return prop, lambda repl: self._with_node_field(node, "value", inner_rebuild(repl))
            return node, lambda repl: repl
        if kind in {"group", "unary", "member", "is", "generic_application", "expression_body"}:
            res = self._split_first_propagate(self.node(node["value"]))
            if res is not None:
                prop, inner_rebuild = res
                return prop, lambda repl: self._with_node_field(node, "value", inner_rebuild(repl))
            return None
        if kind == "binary":
            res_l = self._split_first_propagate(self.node(node["left"]))
            if res_l is not None:
                prop, inner_rebuild = res_l
                return prop, lambda repl: self._with_node_field(node, "left", inner_rebuild(repl))
            res_r = self._split_first_propagate(self.node(node["right"]))
            if res_r is not None:
                prop, inner_rebuild = res_r
                return prop, lambda repl: self._with_node_field(node, "right", inner_rebuild(repl))
            return None
        if kind == "tuple":
            vals = self.nodes(node["values"])
            for i, v in enumerate(vals):
                res = self._split_first_propagate(v)
                if res is not None:
                    prop, inner_rebuild = res
                    return prop, self._make_list_rebuilder(node, "values", vals, i, inner_rebuild)
            return None
        if kind == "call":
            res_c = self._split_first_propagate(self.node(node["callee"]))
            if res_c is not None:
                prop, inner_rebuild = res_c
                return prop, lambda repl: self._with_node_field(node, "callee", inner_rebuild(repl))
            args = self.nodes(node["arguments"])
            for i, a in enumerate(args):
                res_a = self._split_first_propagate(self.node(a["value"]))
                if res_a is not None:
                    prop, inner_rebuild = res_a
                    return prop, self._make_nested_list_rebuilder(node, "arguments", args, i, a, "value", inner_rebuild)
            return None
        if kind == "with_expression":
            res_v = self._split_first_propagate(self.node(node["value"]))
            if res_v is not None:
                prop, inner_rebuild = res_v
                return prop, lambda repl: self._with_node_field(node, "value", inner_rebuild(repl))
            upds = self.nodes(node["updates"])
            for i, u in enumerate(upds):
                res_u = self._split_first_propagate(self.node(u["value"]))
                if res_u is not None:
                    prop, inner_rebuild = res_u
                    return prop, self._make_nested_list_rebuilder(node, "updates", upds, i, u, "value", inner_rebuild)
            return None
        if kind == "if_expression":
            res_cond = self._split_first_propagate(self.node(node["condition"]))
            if res_cond is not None:
                prop, inner_rebuild = res_cond
                return prop, lambda repl: self._with_node_field(node, "condition", inner_rebuild(repl))
            return None
        if kind == "match_expression":
            res_val = self._split_first_propagate(self.node(node["value"]))
            if res_val is not None:
                prop, inner_rebuild = res_val
                return prop, lambda repl: self._with_node_field(node, "value", inner_rebuild(repl))
            return None
        if kind == "let_expression":
            bnode = self.node(node["binding"])
            if bnode.get("value") is not None:
                res_b = self._split_first_propagate(self.node(bnode["value"]))
                if res_b is not None:
                    prop, inner_rebuild = res_b
                    return prop, lambda repl: self._with_node_field(
                        node, "binding", self._with_node_field(bnode, "value", inner_rebuild(repl))
                    )
            return None
        if kind == "index":
            res_v = self._split_first_propagate(self.node(node["value"]))
            if res_v is not None:
                prop, inner_rebuild = res_v
                return prop, lambda repl: self._with_node_field(node, "value", inner_rebuild(repl))
            res_i = self._split_first_propagate(self.node(node["index"]))
            if res_i is not None:
                prop, inner_rebuild = res_i
                return prop, lambda repl: self._with_node_field(node, "index", inner_rebuild(repl))
            return None
        return None

    def _elaborate_propagate(
        self: _Elaborator,
        prop_node: Node,
        environment: dict[str, _Binding],
        target_return_type: _Term,
        continuation: Callable[[str, _Binding, dict[str, _Binding]], _Term],
    ) -> _Term:
        self.site = prop_node
        if self.active_lift_scopes > 0:
            raise self.fail(
                "type",
                "cannot propagate '?' early exit while a record invariant is lifted in an enclosing scope",
                prop_node,
            )
        if self.uninitialized_out_params:
            uninit_name = min(self.uninitialized_out_params)
            raise self.fail(
                "type",
                f"cannot propagate '?' early exit before 'out' parameter '{uninit_name}' is initialized",
                prop_node,
            )
        scrutinee = self.expression(self.node(prop_node["value"]), environment)
        scrut_type = self.whnf(scrutinee.type)
        scrut_head, scrut_type_args = self.spine(scrut_type)
        if (
            scrut_head.kind != "const"
            or not isinstance(scrut_head.value, str)
            or scrut_head.value not in self.unions_by_type
        ):
            raise self.fail(
                "type",
                "'?' operator requires an Option (None/Some) or Result (Err/Ok) union operand",
                prop_node,
            )
        union_info = self.unions_by_type[scrut_head.value]
        if len(union_info.constructors) != 2:
            raise self.fail(
                "type",
                "'?' operator requires a 2-variant Option (None/Some) or Result (Err/Ok) union operand",
                prop_node,
            )
        ok_idx: int | None = None
        err_idx: int | None = None
        for idx, ctor in enumerate(union_info.constructors):
            if ctor.name in {"Some", "Ok"} and len(ctor.fields) == 1:
                ok_idx = idx
            elif (ctor.name == "None" and len(ctor.fields) == 0) or (
                ctor.name == "Err" and len(ctor.fields) == 1
            ):
                err_idx = idx
        if ok_idx is None or err_idx is None:
            raise self.fail(
                "type",
                "'?' operator requires an Option (None/Some) or Result (Err/Ok) union operand",
                prop_node,
            )
        ret_type = self.whnf(target_return_type)
        ret_head, ret_type_args = self.spine(ret_type)
        if (
            ret_head.kind != "const"
            or not isinstance(ret_head.value, str)
            or ret_head.value != scrut_head.value
            or not self._is_propagatable_union(ret_type)
        ):
            raise self.fail(
                "type",
                "'?' propagation requires an enclosing callable or block returning a compatible Option or Result union",
                prop_node,
            )
        inst_payload_types = [
            self._instantiate_generic_type(union_info.generic_vars, scrut_type_args, c.payload_type)
            for c in union_info.constructors
        ]
        err_ctor = union_info.constructors[err_idx]
        err_var = self.fresh(inst_payload_types[err_idx])
        if not err_ctor.fields:
            early_return_term = _apps(_constant(err_ctor.ctor_const), *ret_type_args, _term("unit"))
        else:
            ret_err_type = self._instantiate_generic_type(
                union_info.generic_vars, ret_type_args, err_ctor.payload_type
            )
            self.unify(inst_payload_types[err_idx], ret_err_type)
            early_return_term = _apps(_constant(err_ctor.ctor_const), *ret_type_args, err_var)
        ok_type = inst_payload_types[ok_idx]
        ok_var = self.fresh(ok_type)
        temp_name = f"__vela_prop_{ok_var.value}"
        ok_binding = _Binding(ok_var, ok_type)
        ok_env = dict(environment)
        ok_env[temp_name] = ok_binding
        ok_branch_term = continuation(temp_name, ok_binding, ok_env)
        scrut_var = self.fresh(scrut_type)
        motive_lam = _term("lam", scrut_type, target_return_type, value=scrut_var.value)
        if ok_idx == 0:
            left_lam = _term("lam", ok_type, ok_branch_term, value=ok_var.value)
            right_lam = _term("lam", inst_payload_types[1], early_return_term, value=err_var.value)
        else:
            left_lam = _term("lam", inst_payload_types[0], early_return_term, value=err_var.value)
            right_lam = _term("lam", ok_type, ok_branch_term, value=ok_var.value)
        return _term("sum_match", motive_lam, scrutinee.term, left_lam, right_lam)

    def _check_record_invariants(
        self: _Elaborator,
        record_info: _RecordInfo,
        type_args: list[_Term],
        rec_term: _Term,
        environment: dict[str, _Binding],
        site: Node | None,
        *,
        only_clauses: set[str] | None = None,
        exclude_clauses: set[str] | None = None,
    ) -> None:
        if not record_info.invariants:
            return
        for inv in record_info.invariants:
            if only_clauses is not None and inv.name not in only_clauses:
                continue
            if exclude_clauses is not None and inv.name in exclude_clauses:
                continue
            inst_term = self._instantiate_record_type(record_info, type_args, inv.term)
            inst_term = self.substitute(inst_term, cast("int", inv.self_var.value), rec_term)
            inst_type = self._instantiate_record_type(record_info, type_args, inv.type)
            inst_type = self.substitute(inst_type, cast("int", inv.self_var.value), rec_term)
            clause_label = "" if inv.name.startswith("__anon_") else f" '{inv.name}'"
            if self.whnf(inst_type) == _BOOL:
                if not self._prove_bool_precondition(inst_term, environment):
                    raise self.fail(
                        "type",
                        f"record '{record_info.name}' invariant{clause_label} could not be established",
                        site if site is not None else self.site,
                    )
            else:
                self._prove_proposition(
                    inst_term,
                    environment,
                    (),
                    site if site is not None else cast("Node", self.site),
                )

    def _elaborate_assignment(self: _Elaborator, statement: Node, extended: dict[str, _Binding]) -> dict[str, _Binding]:
        self.site = statement
        target = self._unwrap_group(self.node(statement["target"]))
        raw_op = statement["operator"]
        if (
            not isinstance(raw_op, dict)
            or not isinstance(raw_op.get("text"), str)
            or raw_op["text"] not in _ASSIGN_OPERATORS
        ):
            raise self.fail("protocol", "expected a supported assignment operator", statement)
        op = cast("str", raw_op["text"])
        val_node = self.node(statement["value"])
        updated = dict(extended)
        if target["kind"] == "name":
            tname = self.name(target["name"])
            if tname not in updated:
                raise self.fail("name", f"unknown identifier '{tname}'", target)
            if tname in self.frozen_collections:
                raise self.fail("type", f"cannot mutate collection '{tname}' while iterating over it", statement)
            if tname not in self.mutable_locals:
                raise self.fail(
                    "type",
                    f"cannot assign to immutable binding '{tname}'; declare it with 'var' or 'ref'",
                    target,
                )
            cur_b = updated[tname]
            if self._is_readonly_span(cur_b.term):
                raise self.fail("type", f"cannot mutate a read-only 'in' parameter '{tname}'", target)
            if op == "=":
                prev_assign_target = getattr(self, "_in_lifted_target_assignment", None)
                self._in_lifted_target_assignment = tname
                try:
                    rhs_term = self.check(val_node, cur_b.type, updated)
                finally:
                    self._in_lifted_target_assignment = prev_assign_target
                self._consume_call_updates(updated, statement)
                self.uninitialized_out_params.discard(tname)
            else:
                if tname in self.uninitialized_out_params:
                    raise self.fail(
                        "type",
                        f"cannot apply compound assignment '{op}' to uninitialized 'out' parameter '{tname}'",
                        target,
                    )
                bin_op = op[:-1]
                bin_node: Node = {
                    "kind": "binary",
                    "span": statement["span"],
                    "operator": {"text": bin_op, "span": cast("Node", statement["operator"])["span"]},
                    "left": target,
                    "right": val_node,
                }
                rhs_term = self.check(bin_node, cur_b.type, updated)
                self._consume_call_updates(updated, statement)
            rec_head, rec_targs = self.spine(self.whnf(cur_b.type))
            if (
                rec_head.kind == "const"
                and isinstance(rec_head.value, str)
                and rec_head.value in self.records_by_type
            ):
                rinfo = self.records_by_type[rec_head.value]
                lifted = self.lifted_invariants.get(tname, set())
                self._check_record_invariants(
                    rinfo, rec_targs, rhs_term, updated, statement, exclude_clauses=lifted
                )
            updated[tname] = _Binding(rhs_term, cur_b.type)
            return updated
        if target["kind"] == "member":
            recv_node = self._unwrap_group(self.node(target["value"]))
            fname = self.name(target["name"])
            if recv_node["kind"] != "name":
                raise self.fail("type", "member assignment requires a named record variable target", target)
            rname = self.name(recv_node["name"])
            if rname not in updated:
                raise self.fail("name", f"unknown identifier '{rname}'", recv_node)
            if rname in self.frozen_collections:
                raise self.fail("type", f"cannot mutate collection '{rname}' while iterating over it", statement)
            if rname in self.uninitialized_out_params:
                raise self.fail(
                    "type",
                    f"cannot mutate field '{fname}' of uninitialized 'out' parameter '{rname}'; initialize the whole value first",
                    target,
                )
            if rname not in self.mutable_locals:
                raise self.fail(
                    "type",
                    f"cannot mutate field '{fname}' of immutable record '{rname}'; declare it with 'var' or 'ref'",
                    target,
                )
            cur_b = updated[rname]
            if self._is_readonly_span(cur_b.term):
                raise self.fail("type", f"cannot mutate a read-only 'in' parameter '{rname}'", target)
            rec_type = self.whnf(cur_b.type)
            head, type_args = self.spine(rec_type)
            if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.records_by_type:
                raise self.fail("type", f"member assignment target '{rname}' must be a record", target)
            record_info = self.records_by_type[head.value]
            field_index = next((idx for idx, rf in enumerate(record_info.fields) if rf.name == fname), None)
            if field_index is None:
                raise self.fail("name", f"record '{record_info.name}' has no mutable field '{fname}'", target)
            rhs_expr: Node = (
                val_node
                if op == "="
                else {
                    "kind": "binary",
                    "span": statement["span"],
                    "operator": {"text": op[:-1], "span": cast("Node", statement["operator"])["span"]},
                    "left": target,
                    "right": val_node,
                }
            )
            final_fields: list[_Term] = []
            for idx, rf in enumerate(record_info.fields):
                ftype = self._instantiate_record_type(record_info, type_args, rf.type)
                for j in range(idx):
                    ftype = self.substitute(ftype, cast("int", record_info.fields[j].var.value), final_fields[j])
                if idx == field_index:
                    final_fields.append(self.check(rhs_expr, ftype, updated))
                else:
                    old_ftype = self._instantiate_record_field_type(record_info, type_args, idx, cur_b.term)
                    if not self._try_unify(old_ftype, ftype):
                        raise self.fail(
                            "type",
                            f"field assignment changes an index that field '{rf.name}' depends on; use 'with' to update dependent fields together",
                            statement,
                        )
                    final_fields.append(_apps(_constant(rf.proj_const), *type_args, cur_b.term))
            self._consume_call_updates(updated, statement)
            new_rec_term = _apps(_constant(record_info.ctor_const), *type_args, *final_fields)
            lifted = self.lifted_invariants.get(rname, set())
            self._check_record_invariants(
                record_info, type_args, new_rec_term, updated, statement, exclude_clauses=lifted
            )
            updated[rname] = _Binding(new_rec_term, cur_b.type)
            return updated
        if target["kind"] == "index":
            recv_node = self._unwrap_group(self.node(target["value"]))
            idx_node = self.node(target["index"])
            if recv_node["kind"] != "name":
                raise self.fail("type", "indexed assignment requires a named mutable variable target", target)
            rname = self.name(recv_node["name"])
            if rname not in updated:
                raise self.fail("name", f"unknown identifier '{rname}'", recv_node)
            if rname in self.frozen_collections:
                raise self.fail("type", f"cannot mutate collection '{rname}' while iterating over it", statement)
            if rname in self.uninitialized_out_params:
                raise self.fail(
                    "type",
                    f"cannot mutate indexed element of uninitialized 'out' parameter '{rname}'; initialize the whole value first",
                    target,
                )
            if rname not in self.mutable_locals:
                raise self.fail(
                    "type",
                    f"cannot mutate indexed element of immutable binding '{rname}'; declare it with 'var' or 'ref'",
                    target,
                )
            cur_b = updated[rname]
            if self._is_readonly_span(cur_b.term):
                raise self.fail("type", f"cannot mutate a read-only 'in' parameter '{rname}'", target)
            rhs_expr = (
                val_node
                if op == "="
                else {
                    "kind": "binary",
                    "span": statement["span"],
                    "operator": {"text": op[:-1], "span": cast("Node", statement["operator"])["span"]},
                    "left": target,
                    "right": val_node,
                }
            )
            cur_type = self.whnf(cur_b.type)
            head, type_args = self.spine(cur_type)
            if head == _constant("Span") and len(type_args) == 1 and self.whnf(type_args[0]) == _U8:
                idx_t = self.check(idx_node, _USIZE, updated)
                rhs_t = self.check(rhs_expr, _U8, updated)
                self._check_span_can_write(cur_b.term, updated, statement)
                len_t = _apps(_constant("Span_Length"), _U8, cur_b.term)
                in_bounds = _apps(_constant("int_lt_usize"), idx_t, len_t)
                if not self._prove_bool_precondition(in_bounds, updated):
                    raise self.fail(
                        "type",
                        "cannot prove Span indexed write is in bounds (index < span.Length)",
                        statement,
                    )
                updated[rname] = _Binding(
                    _apps(_constant("Span_Write"), _U8, cur_b.term, idx_t, rhs_t), cur_b.type
                )
                return updated
            if head == _constant("Slots") and len(type_args) == 2:
                elem_t, cap_t = type_args[0], type_args[1]
                idx_t = self._slots_usize_arg(idx_node, updated)
                rhs_t = self.check(rhs_expr, elem_t, updated)
                can_w = _apps(_constant("Slots_CanWrite"), elem_t, cap_t, cur_b.term)
                if not self._prove_bool_precondition(can_w, updated):
                    raise self.fail(
                        "type",
                        "cannot prove Slots has valid tag and write permission (Slots.CanWrite)",
                        statement,
                    )
                live_t = _apps(_constant("Slots_LiveCount"), elem_t, cap_t, cur_b.term)
                lt_live = _apps(_constant("int_lt_usize"), idx_t, live_t)
                eq_live = _apps(_constant("int_eq_usize"), idx_t, live_t)
                cap_u = self._slots_cap_usize_term(cap_t)
                lt_cap = (
                    _apps(_constant("int_lt_usize"), idx_t, cap_u)
                    if self.whnf(cap_u).kind == "int"
                    else _apps(_constant("<"), _app(_constant("int_to_nat_usize"), idx_t), cap_t)
                )
                if not (
                    self._prove_bool_precondition(lt_live, updated)
                    or (
                        self._prove_bool_precondition(eq_live, updated)
                        and self._prove_bool_precondition(lt_cap, updated)
                    )
                ):
                    raise self.fail(
                        "type",
                        "cannot prove Slots indexed write is in bounds (index < LiveCount or (index == LiveCount and index < capacity))",
                        statement,
                    )
                updated[rname] = _Binding(
                    _apps(_constant("Slots_Write"), elem_t, cap_t, cur_b.term, idx_t, rhs_t), cur_b.type
                )
                return updated
            if head == _constant("Seq") and len(type_args) == 1:
                elem_t = type_args[0]
                cnt_t = _apps(_constant("Seq_Count"), elem_t, cur_b.term)
                if self._is_unsuffixed_int_expr(idx_node):
                    idx_nat = self.check(idx_node, _NAT, updated)
                else:
                    idx_b = self.expression(idx_node, updated)
                    idx_w = self.whnf(idx_b.type)
                    if idx_w == _NAT:
                        idx_nat = idx_b.term
                    elif idx_w == _USIZE:
                        idx_nat = _app(_constant("int_to_nat_usize"), idx_b.term)
                    else:
                        raise self.fail("type", "Seq index must have type Nat or usize", idx_node)
                rhs_t = self.check(rhs_expr, elem_t, updated)
                in_bounds = _apps(_constant("<"), idx_nat, cnt_t)
                if not self._prove_bool_precondition(in_bounds, updated):
                    raise self.fail(
                        "type",
                        "cannot prove Seq indexed write is in bounds (index < seq.Count)",
                        statement,
                    )
                updated[rname] = _Binding(
                    _apps(_constant("Seq_Update"), elem_t, cur_b.term, idx_nat, rhs_t), cur_b.type
                )
                return updated
            if head == _constant("Vec") and len(type_args) == 2:
                elem_t, len_t = type_args[0], type_args[1]
                if self._is_unsuffixed_int_expr(idx_node):
                    idx_nat = self.check(idx_node, _NAT, updated)
                else:
                    idx_b = self.expression(idx_node, updated)
                    idx_w = self.whnf(idx_b.type)
                    if idx_w == _NAT:
                        idx_nat = idx_b.term
                    elif idx_w == _USIZE:
                        idx_nat = _app(_constant("int_to_nat_usize"), idx_b.term)
                    else:
                        raise self.fail("type", "Vec index must have type Nat or usize", idx_node)
                rhs_t = self.check(rhs_expr, elem_t, updated)
                in_bounds = _apps(_constant("<"), idx_nat, len_t)
                if not self._prove_bool_precondition(in_bounds, updated):
                    raise self.fail(
                        "type",
                        "cannot prove Vec indexed write is in bounds (index < n)",
                        statement,
                    )
                updated[rname] = _Binding(
                    _apps(_constant("Vec_Update"), elem_t, len_t, idx_nat, rhs_t, cur_b.term), cur_b.type
                )
                return updated
            raise self.fail(
                "type",
                "indexed assignment target must have type Span<byte>, Slots<T, capacity>, Seq<T> or Vec<T, n>",
                target,
            )
        raise self.fail("type", "assignment target must be a mutable local variable or record field", target)

    @staticmethod
    def _extract_ref_or_var_name(arg_node: Node) -> tuple[str | None, bool]:
        val = arg_node.get("value") if arg_node.get("kind") == "argument" else arg_node
        while isinstance(val, dict) and val.get("kind") == "group":
            val = val.get("value")
        if not isinstance(val, dict):
            return None, False
        if (
            val.get("kind") == "unary"
            and isinstance(val.get("operator"), dict)
            and cast("Node", val["operator"]).get("text") == "ref"
        ):
            inner = val.get("value")
            while isinstance(inner, dict) and inner.get("kind") == "group":
                inner = inner.get("value")
            if isinstance(inner, dict) and inner.get("kind") == "name" and isinstance(inner.get("name"), dict):
                return cast("str", cast("Node", inner["name"]).get("text")), True
            return None, True
        if val.get("kind") == "name" and isinstance(val.get("name"), dict):
            return cast("str", cast("Node", val["name"]).get("text")), False
        return None, False

    def _consume_call_updates(
        self: _Elaborator, updated: dict[str, _Binding], site: Node
    ) -> None:
        if not self.last_call_updates:
            return
        pending = list(self.last_call_updates)
        self.last_call_updates.clear()
        for arg_node, new_b in pending:
            self._apply_ref_target_update(arg_node, new_b, updated, site)

    def _apply_ref_target_update(
        self: _Elaborator, arg_node: Node, new_binding: _Binding, updated: dict[str, _Binding], site: Node
    ) -> bool:
        val = arg_node.get("value") if arg_node.get("kind") == "argument" else arg_node
        while isinstance(val, dict) and val.get("kind") == "group":
            val = val.get("value")
        if (
            isinstance(val, dict)
            and val.get("kind") == "unary"
            and isinstance(val.get("operator"), dict)
            and cast("Node", val["operator"]).get("text") in {"ref", "in", "out"}
        ):
            val = val.get("value")
            while isinstance(val, dict) and val.get("kind") == "group":
                val = val.get("value")
        if not isinstance(val, dict):
            return False
        if val.get("kind") == "name" and isinstance(val.get("name"), dict):
            vname = cast("str", cast("Node", val["name"]).get("text"))
            if vname in updated:
                if vname in self.frozen_collections:
                    raise self.fail("type", f"cannot mutate frozen collection '{vname}'", site)
                self.uninitialized_out_params.discard(vname)
                updated[vname] = new_binding
                return True
            return False
        if val.get("kind") == "member" and isinstance(val.get("name"), dict) and isinstance(val.get("value"), dict):
            recv = self._unwrap_group(cast("Node", val["value"]))
            fname = cast("str", cast("Node", val["name"]).get("text"))
            if recv.get("kind") == "name" and isinstance(recv.get("name"), dict):
                rname = cast("str", cast("Node", recv["name"]).get("text"))
                if rname in updated:
                    if rname in self.uninitialized_out_params:
                        raise self.fail(
                            "type",
                            f"cannot partially initialize 'out' parameter '{rname}' before whole-value assignment",
                            site,
                        )
                    if rname in self.frozen_collections:
                        raise self.fail("type", f"cannot mutate frozen collection '{rname}'", site)
                    if rname not in self.mutable_locals:
                        raise self.fail(
                            "type",
                            f"cannot mutate field '{fname}' of immutable record '{rname}'; declare it with 'var' or 'ref'",
                            site,
                        )
                    cur_b = updated[rname]
                    rec_type = self.whnf(cur_b.type)
                    head, type_args = self.spine(rec_type)
                    if (
                        head.kind == "const"
                        and isinstance(head.value, str)
                        and head.value in self.records_by_type
                    ):
                        record_info = self.records_by_type[head.value]
                        field_index = next(
                            (idx for idx, rf in enumerate(record_info.fields) if rf.name == fname), None
                        )
                        if field_index is not None:
                            final_fields: list[_Term] = []
                            for idx, rf in enumerate(record_info.fields):
                                if idx == field_index:
                                    final_fields.append(new_binding.term)
                                else:
                                    final_fields.append(_apps(_constant(rf.proj_const), *type_args, cur_b.term))
                            new_rec_term = _apps(_constant(record_info.ctor_const), *type_args, *final_fields)
                            lifted = self.lifted_invariants.get(rname, set())
                            self._check_record_invariants(
                                record_info, type_args, new_rec_term, updated, site, exclude_clauses=lifted
                            )
                            updated[rname] = _Binding(new_rec_term, cur_b.type)
                            return True
        return False

    def _elaborate_expression_statement(
        self: _Elaborator, statement: Node, extended: dict[str, _Binding]
    ) -> dict[str, _Binding]:
        self.site = statement
        expr_node = self._unwrap_group(self.node(statement["value"]))
        updated = dict(extended)
        if expr_node["kind"] == "call":
            callee = self._unwrap_group(self.node(expr_node["callee"]))
            call_args = self.nodes(expr_node["arguments"])
            path = self._dotted_member_path(callee)
            if path is None and callee["kind"] == "generic_application":
                path = self._dotted_member_path(self.node(callee["value"]))
            if path in {"TransferType", "Slots.TransferType"} and len(call_args) == 3:
                res_b = self.expression(expr_node, updated)
                prod_ty = self.whnf(res_b.type)
                if prod_ty.kind == "prod":
                    src_ty, dst_ty = prod_ty.args
                    src_b = _Binding(
                        self.whnf(_apps(_constant("Fst"), src_ty, dst_ty, res_b.term)), src_ty
                    )
                    dst_b = _Binding(
                        self.whnf(_apps(_constant("Snd"), src_ty, dst_ty, res_b.term)), dst_ty
                    )
                    self._apply_ref_target_update(call_args[0], src_b, updated, statement)
                    self._apply_ref_target_update(call_args[1], dst_b, updated, statement)
                    return updated
            if path in {"CopyRepresentation", "Slots.CopyRepresentation"} and len(call_args) == 3:
                res_b = self.expression(expr_node, updated)
                if self._apply_ref_target_update(call_args[1], res_b, updated, statement):
                    return updated
            if path == "Slots.Write" and len(call_args) == 3:
                res_b = self.expression(expr_node, updated)
                if self._apply_ref_target_update(call_args[0], res_b, updated, statement):
                    return updated
            if path in {"Span.Write", "Span.Fill", "Span.CopyPrefix", "Span.Restore"} and len(call_args) >= 2:
                res_b = self.expression(expr_node, updated)
                if self._apply_ref_target_update(call_args[0], res_b, updated, statement):
                    return updated
            if path == "Format.Write" and len(call_args) == 2:
                b_name, _ = self._extract_ref_or_var_name(call_args[0])
                res_b = self.expression(expr_node, updated)
                if b_name is not None and b_name in updated:
                    updated[b_name] = res_b
                    return updated
        self.expression(expr_node, updated)
        self._consume_call_updates(updated, statement)
        return updated

    def _elaborate_scope_statement(
        self: _Elaborator,
        statement: Node,
        extended: dict[str, _Binding],
        facts: tuple[_Binding, ...],
    ) -> dict[str, _Binding]:
        self.site = statement
        loan_nodes = self.nodes(statement["resources"])
        lift_raw = statement.get("lifts")
        if lift_raw is not None and not isinstance(lift_raw, list):
            raise self.fail("protocol", "expected a syntax list", statement)
        lift_names = [] if lift_raw is None else [self.name(ln) for ln in lift_raw]
        if len(lift_names) != len(set(lift_names)):
            raise self.fail("name", "duplicate record invariant clause in scope lifts list", statement)
        loaned_records: list[tuple[str, _RecordInfo, list[_Term]]] = []
        seen_targets: set[str] = set()
        for loan_node in loan_nodes:
            self.node(loan_node, "unary")
            tname, is_ref = self._extract_ref_or_var_name(loan_node)
            if not is_ref or tname is None:
                raise self.fail("type", "scope header requires 'ref <variable>' loan targets", loan_node)
            if tname in seen_targets:
                raise self.fail("type", f"duplicate 'ref {tname}' loan in scope header", loan_node)
            seen_targets.add(tname)
            if tname not in extended:
                raise self.fail("name", f"unknown identifier '{tname}' in scope header", loan_node)
            if tname in self.uninitialized_out_params:
                raise self.fail(
                    "type",
                    f"cannot take mutable 'ref' loan of uninitialized 'out' parameter '{tname}'",
                    loan_node,
                )
            if tname in self.frozen_collections:
                raise self.fail("type", f"cannot mutably loan frozen collection '{tname}'", loan_node)
            cur_b = extended[tname]
            if self._is_readonly_span(cur_b.term):
                raise self.fail(
                    "type", f"cannot take mutable 'ref' loan of read-only 'in' parameter '{tname}'", loan_node
                )
            rec_type = self.whnf(cur_b.type)
            head, type_args = self.spine(rec_type)
            if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.records_by_type:
                raise self.fail(
                    "type", f"scope invariant lifting requires a record target, got '{tname}'", loan_node
                )
            rinfo = self.records_by_type[head.value]
            loaned_records.append((tname, rinfo, type_args))
        for cname in lift_names:
            matching = [
                tname
                for tname, rinfo, _ in loaned_records
                if any(inv.name == cname and not inv.name.startswith("__anon_") for inv in rinfo.invariants)
            ]
            if not matching:
                raise self.fail(
                    "name",
                    f"none of the loaned records in scope declare named invariant clause '{cname}'",
                    statement,
                )
        saved_mutable = set(self.mutable_locals)
        saved_lifted = {k: set(v) for k, v in self.lifted_invariants.items()}
        saved_active_facts = list(self.active_facts)
        # Remove facts originating from the lifted invariant clauses during the scope body,
        # while retaining pre-scope Slots_LivePrefix / Slots_VacantRange facts on the entry record term.
        lifted_by_target: dict[str, set[str]] = {}
        lifted_fact_terms: set[_Term] = set()
        pre_scope_slot_facts: list[_Term] = []
        for tname, rinfo, type_args in loaned_records:
            self.mutable_locals.add(tname)
            clauses_for_t = {
                inv.name
                for inv in rinfo.invariants
                if inv.name in lift_names
            }
            lifted_by_target[tname] = clauses_for_t
            self.lifted_invariants.setdefault(tname, set()).update(clauses_for_t)
            for inv in rinfo.invariants:
                if inv.name in clauses_for_t:
                    inst_t = self._instantiate_record_type(rinfo, type_args, inv.term)
                    inst_t = self.substitute(inst_t, cast("int", inv.self_var.value), extended[tname].term)
                    w_inst = self.whnf(inst_t)
                    lifted_fact_terms.add(w_inst)
                    w_head, _ = self.spine(w_inst)
                    if w_head in {_constant("Slots_LivePrefix"), _constant("Slots_VacantRange")}:
                        pre_scope_slot_facts.append(inst_t)
        self.active_facts = [
            *(f for f in self.active_facts if self.whnf(f) not in lifted_fact_terms),
            *pre_scope_slot_facts,
        ]
        self.active_lift_scopes += 1
        try:
            body_block = self.node(statement["body"], "block")
            after_env, _ = self._elaborate_non_returning_block(body_block, extended, facts)
        finally:
            self.active_lift_scopes -= 1
            self.mutable_locals = saved_mutable
            self.lifted_invariants = saved_lifted
            self.active_facts = saved_active_facts
        for tname, rinfo, type_args in loaned_records:
            self._check_record_invariants(
                rinfo,
                type_args,
                after_env[tname].term,
                after_env,
                statement,
                only_clauses=lifted_by_target[tname],
            )
            for inv in rinfo.invariants:
                inst_ty = self._instantiate_record_type(rinfo, type_args, inv.type)
                inst_ty = self.substitute(inst_ty, cast("int", inv.self_var.value), after_env[tname].term)
                if self.whnf(inst_ty) == _BOOL:
                    inst_t = self._instantiate_record_type(rinfo, type_args, inv.term)
                    inst_t = self.substitute(inst_t, cast("int", inv.self_var.value), after_env[tname].term)
                    self.active_facts.append(inst_t)
        return after_env

    def _check_loop_invariants(
        self: _Elaborator,
        contracts: list[Node],
        env: dict[str, _Binding],
        site: Node,
        phase: str,
    ) -> list[_Term]:
        proved_bools: list[_Term] = []
        for contract in contracts:
            self.node(contract, "contract")
            if contract["role"] == "decreases":
                continue
            if contract["role"] != "invariant":
                raise self.fail("unsupported", f"loop contract '{contract['role']}' is not supported", contract)
            c_val_node = self.node(contract["value"])
            c_val = self.expression(c_val_node, env)
            c_label = f" '{self.name(contract['name'])}'" if contract.get("name") is not None else ""
            if self.whnf(c_val.type) == _BOOL:
                if not self._prove_bool_precondition(c_val.term, env):
                    raise self.fail(
                        "type",
                        f"loop invariant{c_label} could not be established on loop {phase}",
                        contract,
                    )
                proved_bools.append(c_val.term)
            else:
                prop_t = self.proposition(c_val_node, env)
                self._prove_proposition(prop_t, env, (), contract)
        return proved_bools

    def _assume_loop_invariants(
        self: _Elaborator,
        contracts: list[Node],
        env: dict[str, _Binding],
    ) -> list[_Term]:
        assumed_bools: list[_Term] = []
        for contract in contracts:
            self.node(contract, "contract")
            if contract["role"] == "decreases":
                continue
            if contract["role"] != "invariant":
                raise self.fail("unsupported", f"loop contract '{contract['role']}' is not supported", contract)
            c_val_node = self.node(contract["value"])
            self.active_facts.extend(assumed_bools)
            try:
                c_val = self.expression(c_val_node, env)
            finally:
                for _ in assumed_bools:
                    self.active_facts.pop()
            if self.whnf(c_val.type) == _BOOL:
                assumed_bools.append(c_val.term)
            else:
                prop_t = self.proposition(c_val_node, env)
                extracted = self._extract_equality(prop_t)
                if extracted is not None:
                    eq_ty, u, v = extracted
                    eq_ty_w = self.whnf(eq_ty)
                    if eq_ty_w == _BOOL and self.whnf(v) == _term("bool", value=1):
                        assumed_bools.append(u)
                    elif self._int_spec(eq_ty_w) is not None or eq_ty_w == _NAT:
                        spec = self._int_spec(eq_ty_w)
                        eq_const = f"int_eq_{spec.name}" if spec is not None else "eq_nat"
                        assumed_bools.append(_apps(_constant(eq_const), u, v))
        return assumed_bools

    def _eval_loop_decreases(
        self: _Elaborator,
        contracts: list[Node],
        env: dict[str, _Binding],
    ) -> list[tuple[Node, _Term, _IntSpec | None]]:
        measures: list[tuple[Node, _Term, _IntSpec | None]] = []
        for contract in contracts:
            self.node(contract, "contract")
            if contract["role"] != "decreases":
                continue
            m_b = self.expression(self.node(contract["value"]), env)
            m_w = self.whnf(m_b.type)
            m_spec = self._int_spec(m_w)
            if m_w != _NAT and m_spec is None:
                raise self.fail(
                    "type",
                    "loop 'decreases' termination measure must have type Nat or a fixed-width integer",
                    contract,
                )
            if m_spec is not None and m_spec.signed:
                nonneg = _apps(_constant(f"int_ge_{m_spec.name}"), m_b.term, _int_term(m_spec, 0))
                if not self._prove_bool_precondition(nonneg, env):
                    raise self.fail(
                        "type",
                        "signed loop 'decreases' termination measure could not be proved non-negative",
                        contract,
                    )
            measures.append((contract, m_b.term, m_spec))
        return measures

    def _check_loop_decreases(
        self: _Elaborator,
        before_measures: list[tuple[Node, _Term, _IntSpec | None]],
        after_env: dict[str, _Binding],
        phase: str,
    ) -> None:
        if not before_measures:
            return
        after_measures = self._eval_loop_decreases([c for c, _, _ in before_measures], after_env)
        for j in range(len(before_measures)):
            prefix_eq = True
            for i in range(j):
                _, b_term, b_spec = before_measures[i]
                _, a_term, _ = after_measures[i]
                eq_op = f"int_eq_{b_spec.name}" if b_spec is not None else "eq_nat"
                if not self._prove_bool_precondition(_apps(_constant(eq_op), a_term, b_term), after_env):
                    prefix_eq = False
                    break
            if not prefix_eq:
                continue
            _, bj_term, bj_spec = before_measures[j]
            _, aj_term, _ = after_measures[j]
            lt_op = f"int_lt_{bj_spec.name}" if bj_spec is not None else "<"
            if self._prove_bool_precondition(_apps(_constant(lt_op), aj_term, bj_term), after_env):
                return
        raise self.fail(
            "type",
            f"loop 'decreases' termination measure could not be proved to strictly decrease on {phase}",
            before_measures[0][0],
        )

    def _elaborate_non_returning_block(
        self: _Elaborator,
        block_node: Node,
        environment: dict[str, _Binding],
        facts: tuple[_Binding, ...],
    ) -> tuple[dict[str, _Binding], str | None]:
        self.node(block_node, "block")
        statements = self.nodes(block_node["statements"])
        extended = dict(environment)
        statement_facts: list[_Binding] = []
        saved_active_len = len(self.active_facts)
        try:
            for statement in statements:
                self.site = statement
                kind = cast("str", statement["kind"])
                if kind in {"let", "typed_local", "let_pattern", "constant_local", "var", "var_pattern"}:
                    previous_keys = set(extended)
                    extended = self.local(statement, extended)
                    for new_key in set(extended) - previous_keys:
                        bound = extended[new_key]
                        if self._is_prop_type(bound.type):
                            statement_facts.append(bound)
                            self.active_facts.extend(self._fact_bool_terms((bound,), extended))
                    continue
                if kind in {"let_else", "var_else"}:
                    scrut = self.expression(self.node(statement["value"]), extended)
                    pat = self._parse_pattern(self.node(statement["pattern"]), set())
                    self._typecheck_pattern(pat, scrut.type, extended)
                    else_block = self.node(statement["else"], "block")
                    if self._pattern_matches_concretely(pat, scrut.term):
                        self._bind_concrete_pattern(
                            pat, scrut, extended, is_var=(kind == "var_else")
                        )
                        continue
                    if self._pattern_refuted_concretely(pat, scrut.term):
                        else_env, ctrl = self._elaborate_non_returning_block(
                            else_block, extended, (*facts, *statement_facts)
                        )
                        if ctrl not in {"break", "continue"}:
                            raise self.fail(
                                "type",
                                f"{kind.replace('_', '-')} else block must exit with return, break or continue",
                                statement,
                            )
                        return else_env, ctrl
                    saved_uninit = set(self.uninitialized_out_params)
                    else_env, ctrl = self._elaborate_non_returning_block(
                        else_block, dict(extended), (*facts, *statement_facts)
                    )
                    self.uninitialized_out_params = saved_uninit
                    if ctrl not in {"break", "continue"}:
                        raise self.fail(
                            "type",
                            f"{kind.replace('_', '-')} else block must exit with return, break or continue",
                            statement,
                        )
                    self._bind_symbolic_pattern(pat, scrut, extended, is_var=(kind == "var_else"))
                    continue
                if kind == "assignment":
                    extended = self._elaborate_assignment(statement, extended)
                    continue
                if kind == "expression_statement":
                    extended = self._elaborate_expression_statement(statement, extended)
                    continue
                if kind == "assert":
                    fact = self._elaborate_assert(statement, extended, (*facts, *statement_facts))
                    statement_facts.append(fact)
                    self.active_facts.extend(self._fact_bool_terms((fact,), extended))
                    continue
                if kind == "proof":
                    sub_facts = self._elaborate_proof_statement(
                        self.node(statement["body"], "block"), extended, (*facts, *statement_facts)
                    )
                    statement_facts.extend(sub_facts)
                    self.active_facts.extend(self._fact_bool_terms(sub_facts, extended))
                    continue
                if kind == "calc":
                    sub_facts = self._elaborate_calc_statement(
                        self.node(statement["body"], "block"), extended, (*facts, *statement_facts)
                    )
                    statement_facts.extend(sub_facts)
                    self.active_facts.extend(self._fact_bool_terms(sub_facts, extended))
                    continue
                if kind == "scope":
                    extended = self._elaborate_scope_statement(
                        statement, extended, (*facts, *statement_facts)
                    )
                    continue
                if kind == "foreach":
                    extended = self._elaborate_foreach_statement(
                        statement, extended, (*facts, *statement_facts)
                    )
                    continue
                if kind == "foreach_collection":
                    extended = self._elaborate_foreach_collection_statement(
                        statement, extended, (*facts, *statement_facts)
                    )
                    continue
                if kind == "while":
                    extended = self._elaborate_while_statement(
                        statement, extended, (*facts, *statement_facts)
                    )
                    continue
                if kind in {"break", "continue"}:
                    if self.in_loop_depth <= 0:
                        raise self.fail("type", f"'{kind}' statement is only permitted inside a loop", statement)
                    if self.active_lift_scopes > 0:
                        raise self.fail(
                            "type",
                            f"cannot '{kind}' out of a loop while a record invariant is lifted",
                            statement,
                        )
                    return extended, cast("str", kind)
                if kind == "if":
                    cond_raw = self.node(statement["condition"])
                    condition = self.check(cond_raw, _BOOL, extended)
                    cond_w = self.whnf(condition)
                    then_node = self.node(statement["then"])
                    then_block = (
                        then_node
                        if then_node["kind"] == "block"
                        else {"kind": "block", "span": then_node["span"], "statements": [then_node]}
                    )
                    else_raw = statement["else"]
                    else_block = (
                        None
                        if else_raw is None
                        else (
                            self.node(else_raw)
                            if self.node(else_raw)["kind"] == "block"
                            else {
                                "kind": "block",
                                "span": self.node(else_raw)["span"],
                                "statements": [self.node(else_raw)],
                            }
                        )
                    )
                    if cond_w.kind == "bool":
                        if cond_w.value == 1:
                            extended, ctrl = self._elaborate_non_returning_block(
                                then_block, extended, (*facts, *statement_facts)
                            )
                            if ctrl is not None:
                                return extended, ctrl
                        elif else_block is not None:
                            extended, ctrl = self._elaborate_non_returning_block(
                                else_block, extended, (*facts, *statement_facts)
                            )
                            if ctrl is not None:
                                return extended, ctrl
                        continue
                    saved_uninit = set(self.uninitialized_out_params)
                    self.active_facts.append(condition)
                    try:
                        then_env, then_ctrl = self._elaborate_non_returning_block(
                            then_block, dict(extended), (*facts, *statement_facts)
                        )
                        then_uninit = set(self.uninitialized_out_params)
                    finally:
                        self.active_facts.pop()
                    self.uninitialized_out_params = set(saved_uninit)
                    if else_block is not None:
                        self.active_facts.append(_app(_constant("!"), condition))
                        try:
                            else_env, else_ctrl = self._elaborate_non_returning_block(
                                else_block, dict(extended), (*facts, *statement_facts)
                            )
                            else_uninit = set(self.uninitialized_out_params)
                        finally:
                            self.active_facts.pop()
                    else:
                        else_env, else_ctrl = dict(extended), None
                        else_uninit = set(saved_uninit)
                    if then_ctrl is not None and else_ctrl is None:
                        self.active_facts.append(_app(_constant("!"), condition))
                        self.uninitialized_out_params = else_uninit
                        extended = else_env
                        continue
                    if else_ctrl is not None and then_ctrl is None:
                        self.active_facts.append(condition)
                        self.uninitialized_out_params = then_uninit
                        extended = then_env
                        continue
                    self.uninitialized_out_params = then_uninit | else_uninit
                    for k, orig_b in list(extended.items()):
                        tb = then_env.get(k, orig_b)
                        eb = else_env.get(k, orig_b)
                        if tb.term != eb.term:
                            extended[k] = _Binding(
                                self.whnf(_term("if", orig_b.type, condition, tb.term, eb.term)),
                                orig_b.type,
                            )
                    if then_ctrl is not None and then_ctrl == else_ctrl:
                        return extended, then_ctrl
                    continue
                if kind == "block":
                    extended, ctrl = self._elaborate_non_returning_block(
                        statement, extended, (*facts, *statement_facts)
                    )
                    if ctrl is not None:
                        return extended, ctrl
                    continue
                if kind == "return":
                    if self.active_lift_scopes > 0:
                        raise self.fail(
                            "type",
                            "cannot return from a callable while a record invariant is lifted in an enclosing scope",
                            statement,
                        )
                    raise self.fail("unsupported", "early return inside a loop or scope block is not supported", statement)
                raise self.fail("unsupported", f"statement '{kind}' requires the full frontend", statement)
            return extended, None
        finally:
            del self.active_facts[saved_active_len:]

    def _pattern_matches_concretely(self: _Elaborator, pat: _Pat, term: _Term) -> bool:
        w = self.whnf(term)
        if pat.kind == "wild":
            return True
        if pat.kind == "bool":
            return w.kind == "bool" and bool(w.value) == pat.value
        if pat.kind == "zero":
            return w.kind == "nat" and w.value == 0
        if pat.kind == "succ":
            return w.kind == "nat" and cast("int", w.value) > 0
        if pat.kind == "int_lit":
            return w.kind == "int" and w.value == pat.value
        if pat.kind == "char":
            return w.kind == "char" and w.value == pat.value
        if pat.kind == "union":
            uinfo, uctor = self.union_ctors[cast("str", pat.value)]
            head, args = self.spine(w)
            if head == _constant(uctor.ctor_const):
                payload_args = args[len(uinfo.generic_vars) :]
                if not uctor.fields:
                    return True
                return all(
                    self._pattern_matches_concretely(sp, pa)
                    for sp, pa in zip(pat.args, payload_args, strict=True)
                )
        return False

    def _pattern_refuted_concretely(self: _Elaborator, pat: _Pat, term: _Term) -> bool:
        w = self.whnf(term)
        if pat.kind == "bool" and w.kind == "bool":
            return bool(w.value) != pat.value
        if pat.kind == "zero" and w.kind == "nat":
            return cast("int", w.value) != 0
        if pat.kind == "succ" and w.kind == "nat":
            return cast("int", w.value) == 0
        if pat.kind == "int_lit" and w.kind == "int":
            return w.value != pat.value
        if pat.kind == "char" and w.kind == "char":
            return w.value != pat.value
        if pat.kind == "union":
            uinfo, uctor = self.union_ctors[cast("str", pat.value)]
            head, _ = self.spine(w)
            if head.kind == "const" and any(head == _constant(c.ctor_const) for c in uinfo.constructors):
                return head != _constant(uctor.ctor_const)
        return False

    def _bind_concrete_pattern(
        self: _Elaborator, pat: _Pat, current: _Binding, extended: dict[str, _Binding], *, is_var: bool
    ) -> None:
        for name in pat.names:
            if is_var:
                self.mutable_locals.add(name)
            else:
                self.mutable_locals.discard(name)
            extended[name] = current
        w = self.whnf(current.term)
        if pat.kind == "succ" and w.kind == "nat":
            pred_b = _Binding(_term("nat", value=cast("int", w.value) - 1), _NAT)
            self._bind_concrete_pattern(pat.args[0], pred_b, extended, is_var=is_var)
        elif pat.kind == "union":
            uinfo, uctor = self.union_ctors[cast("str", pat.value)]
            _, type_args = self.spine(self.whnf(current.type))
            _, args = self.spine(w)
            payload_args = args[len(uinfo.generic_vars) :]
            for idx, (sp, pa) in enumerate(zip(pat.args, payload_args, strict=False)):
                fty = self._instantiate_generic_type(uinfo.generic_vars, type_args, uctor.fields[idx].type)
                self._bind_concrete_pattern(sp, _Binding(pa, fty), extended, is_var=is_var)

    def _bind_symbolic_pattern(
        self: _Elaborator, pat: _Pat, current: _Binding, extended: dict[str, _Binding], *, is_var: bool
    ) -> None:
        for name in pat.names:
            if is_var:
                self.mutable_locals.add(name)
            else:
                self.mutable_locals.discard(name)
            extended[name] = current
        if pat.kind == "succ":
            pred_v = self.fresh(_NAT)
            self._bind_symbolic_pattern(pat.args[0], _Binding(pred_v, _NAT), extended, is_var=is_var)
        elif pat.kind == "union":
            uinfo, uctor = self.union_ctors[cast("str", pat.value)]
            _, type_args = self.spine(self.whnf(current.type))
            for idx, sp in enumerate(pat.args):
                fty = self._instantiate_generic_type(uinfo.generic_vars, type_args, uctor.fields[idx].type)
                fv = self.fresh(fty)
                self._bind_symbolic_pattern(sp, _Binding(fv, fty), extended, is_var=is_var)

    def _elaborate_foreach_statement(
        self: _Elaborator,
        statement: Node,
        extended: dict[str, _Binding],
        facts: tuple[_Binding, ...],
    ) -> dict[str, _Binding]:
        self.site = statement
        range_node = self.node(statement["range"], "range")
        start_node = self.node(range_node["start"])
        end_node = self.node(range_node["end"])
        if statement.get("type") is not None:
            elem_type = self.type(self.node(statement["type"]), extended)
            start_term = self.check(start_node, elem_type, extended)
            end_term = self.check(end_node, elem_type, extended)
        elif self._is_unsuffixed_int_expr(start_node) and not self._is_unsuffixed_int_expr(end_node):
            end_b = self.expression(end_node, extended)
            elem_type = end_b.type
            end_term = end_b.term
            start_term = self.check(start_node, elem_type, extended)
        else:
            start_b = self.expression(start_node, extended)
            elem_type = start_b.type
            start_term = start_b.term
            end_term = self.check(end_node, elem_type, extended)
        elem_w = self.whnf(elem_type)
        elem_spec = self._int_spec(elem_w)
        if elem_w != _NAT and elem_spec is None:
            raise self.fail(
                "type", "foreach range loop variable must have type Nat or a fixed-width integer", statement
            )
        var_name = self.name(statement["name"])
        if var_name in self.frozen_collections:
            raise self.fail("type", f"cannot shadow frozen collection '{var_name}'", statement)
        contracts = self.nodes(statement["contracts"])
        body_node = self.node(statement["body"], "block")
        start_w = self.whnf(start_term)
        end_w = self.whnf(end_term)
        saved_mutable = set(self.mutable_locals)
        self.mutable_locals.discard(var_name)
        self.in_loop_depth += 1
        try:
            # Verify loop invariants on entry (var_name = start_term)
            entry_env = dict(extended)
            entry_env[var_name] = _Binding(start_term, elem_type)
            self._check_loop_invariants(contracts, entry_env, statement, "entry")
            self._eval_loop_decreases(contracts, entry_env)
            if (
                start_w.kind in {"nat", "int"}
                and end_w.kind in {"nat", "int"}
                and cast("int", end_w.value) - cast("int", start_w.value) <= 64
            ):
                s_val = cast("int", start_w.value)
                e_val = cast("int", end_w.value)
                cur_env = dict(extended)
                broke = False
                for i_val in range(s_val, e_val):
                    i_term = (
                        _int_term(elem_spec, i_val)
                        if elem_spec is not None
                        else _term("nat", value=i_val)
                    )
                    next_term = (
                        _int_term(elem_spec, i_val + 1)
                        if elem_spec is not None
                        else _term("nat", value=i_val + 1)
                    )
                    iter_env = dict(cur_env)
                    iter_env[var_name] = _Binding(i_term, elem_type)
                    before_m = self._eval_loop_decreases(contracts, iter_env)
                    self.mutable_locals.discard(var_name)
                    after_iter, ctrl = self._elaborate_non_returning_block(body_node, iter_env, facts)
                    for k in list(cur_env):
                        if k != var_name and k in after_iter and k in self.mutable_locals:
                            cur_env[k] = after_iter[k]
                    if ctrl == "break":
                        check_env = dict(cur_env)
                        check_env[var_name] = _Binding(i_term, elem_type)
                        self._check_loop_invariants(contracts, check_env, statement, "break")
                        broke = True
                        break
                    check_env = dict(cur_env)
                    check_env[var_name] = _Binding(next_term, elem_type)
                    self._check_loop_invariants(contracts, check_env, statement, "step")
                    self._check_loop_decreases(before_m, check_env, "step")
                if not broke:
                    end_env = dict(cur_env)
                    end_env[var_name] = _Binding(end_term, elem_type)
                    proved = self._check_loop_invariants(contracts, end_env, statement, "exit")
                    self.active_facts.extend(proved)
                return cur_env

            # Symbolic range induction
            saved_uninit = set(self.uninitialized_out_params)
            sym_env = dict(extended)
            for mname in list(self.mutable_locals):
                if mname in sym_env and mname != var_name:
                    m_ty = sym_env[mname].type
                    sym_env[mname] = _Binding(self.fresh(m_ty), m_ty)
            i_var = self.fresh(elem_type)
            sym_env[var_name] = _Binding(i_var, elem_type)
            ge_op = f"int_ge_{elem_spec.name}" if elem_spec is not None else ">="
            lt_op = f"int_lt_{elem_spec.name}" if elem_spec is not None else "<"
            add_op = f"int_add_{elem_spec.name}" if elem_spec is not None else "+"
            one_term = _int_term(elem_spec, 1) if elem_spec is not None else _term("nat", value=1)
            next_i = _apps(_constant(add_op), i_var, one_term)
            saved_facts_len = len(self.active_facts)
            self.active_facts.append(_apps(_constant(ge_op), i_var, start_term))
            self.active_facts.append(_apps(_constant(lt_op), i_var, end_term))
            assumed = self._assume_loop_invariants(contracts, sym_env)
            self.active_facts.extend(assumed)
            try:
                before_sym_m = self._eval_loop_decreases(contracts, sym_env)
                after_sym, _ = self._elaborate_non_returning_block(body_node, sym_env, facts)
                step_env = dict(sym_env)
                for k in list(sym_env):
                    if k != var_name and k in after_sym and k in self.mutable_locals:
                        step_env[k] = after_sym[k]
                step_env[var_name] = _Binding(next_i, elem_type)
                self._check_loop_invariants(contracts, step_env, statement, "inductive step")
                self._check_loop_decreases(before_sym_m, step_env, "inductive step")
            finally:
                self.uninitialized_out_params = saved_uninit
                del self.active_facts[saved_facts_len:]
            post_env = dict(extended)
            for mname in list(self.mutable_locals):
                if mname in post_env and mname != var_name and sym_env[mname].term != after_sym.get(mname, sym_env[mname]).term:
                    m_ty = post_env[mname].type
                    loop_tag = self.serial
                    self.serial += 1
                    post_env[mname] = _Binding(
                        _apps(_constant("LoopState"), m_ty, post_env[mname].term, _term("nat", value=loop_tag)),
                        m_ty,
                    )
            post_env_with_idx = dict(post_env)
            post_env_with_idx[var_name] = _Binding(end_term, elem_type)
            post_assumed = self._assume_loop_invariants(contracts, post_env_with_idx)
            self.active_facts.extend(post_assumed)
            return post_env
        finally:
            self.in_loop_depth -= 1
            self.mutable_locals = saved_mutable

    def _elaborate_foreach_collection_statement(
        self: _Elaborator,
        statement: Node,
        extended: dict[str, _Binding],
        facts: tuple[_Binding, ...],
    ) -> dict[str, _Binding]:
        self.site = statement
        mode = cast("str", statement["mode"])
        var_name = self.name(statement["name"])
        coll_node = self._unwrap_group(self.node(statement["collection"]))
        if coll_node["kind"] == "range":
            if mode != "value":
                raise self.fail("type", "range iteration only supports 'let' value elements", statement)
            return self._elaborate_foreach_statement(
                {
                    "kind": "foreach",
                    "span": statement["span"],
                    "name": statement["name"],
                    "type": statement["type"],
                    "range": coll_node,
                    "contracts": statement["contracts"],
                    "body": statement["body"],
                },
                extended,
                facts,
            )
        coll_name = self.name(coll_node["name"]) if coll_node["kind"] == "name" else None
        if coll_name is not None and coll_name in self.frozen_collections:
            raise self.fail("type", f"collection '{coll_name}' is already being iterated", coll_node)
        coll_b = self.expression(coll_node, extended)
        if mode == "ref":
            if coll_name is None or coll_name not in self.mutable_locals:
                raise self.fail(
                    "type",
                    "foreach 'ref' element iteration requires a mutable 'var' or 'ref' collection variable",
                    coll_node,
                )
            if self._is_readonly_span(coll_b.term):
                raise self.fail(
                    "type",
                    f"cannot iterate with 'ref' over read-only 'in' parameter '{coll_name}'",
                    coll_node,
                )
        coll_ty = self.whnf(coll_b.type)
        c_head, c_args = self.spine(coll_ty)
        kind_tag = ""
        if c_head == _constant("Span") and len(c_args) == 1 and self.whnf(c_args[0]) == _U8:
            kind_tag = "span"
            elem_type = _U8
            self._check_span_can_read(coll_b.term, extended, coll_node)
            if mode == "ref":
                self._check_span_can_write(coll_b.term, extended, coll_node)
            len_t = self.whnf(_apps(_constant("Span_Length"), _U8, coll_b.term))
            concrete_len = cast("int", len_t.value) if len_t.kind == "int" else None
        elif c_head == _constant("Slots") and len(c_args) == 2:
            kind_tag = "slots"
            elem_type = c_args[0]
            slots_cap = c_args[1]
            can_r = _apps(_constant("Slots_CanRead"), elem_type, slots_cap, coll_b.term)
            if not self._prove_bool_precondition(can_r, extended):
                raise self.fail("type", "cannot prove Slots.CanRead for collection iteration", coll_node)
            if mode == "ref":
                can_w = _apps(_constant("Slots_CanWrite"), elem_type, slots_cap, coll_b.term)
                if not self._prove_bool_precondition(can_w, extended):
                    raise self.fail("type", "cannot prove Slots.CanWrite for 'ref' collection iteration", coll_node)
            live_t = self.whnf(_apps(_constant("Slots_LiveCount"), elem_type, slots_cap, coll_b.term))
            concrete_len = cast("int", live_t.value) if live_t.kind == "int" else None
        elif c_head == _constant("Vec") and len(c_args) == 2:
            kind_tag = "vec"
            elem_type = c_args[0]
            len_t = self.whnf(c_args[1])
            concrete_len = cast("int", len_t.value) if len_t.kind == "nat" else None
        elif c_head == _constant("Seq") and len(c_args) == 1:
            if mode == "ref":
                raise self.fail(
                    "type", "pure sequence 'Seq<T>' does not support mutable 'ref' element iteration", statement
                )
            kind_tag = "seq"
            elem_type = c_args[0]
            cnt_t = self.whnf(_apps(_constant("Seq_Count"), elem_type, coll_b.term))
            concrete_len = cast("int", cnt_t.value) if cnt_t.kind == "nat" else None
        else:
            raise self.fail(
                "type",
                "foreach collection must have type Vec<T, n>, Span<byte>, Slots<T, capacity> or Seq<T>",
                coll_node,
            )
        if statement["type"] is not None:
            ann_type = self.type(self.node(statement["type"]), extended)
            self.unify(elem_type, ann_type)
        contracts = self.nodes(statement["contracts"])
        body_node = self.node(statement["body"], "block")
        saved_mutable = set(self.mutable_locals)
        saved_readonly = set(self.readonly_span_vars)
        if coll_name is not None:
            self.frozen_collections.add(coll_name)
        self.in_loop_depth += 1
        try:
            self._check_loop_invariants(contracts, extended, statement, "entry")
            self._eval_loop_decreases(contracts, extended)
            cur_env = dict(extended)
            if concrete_len is not None and 0 <= concrete_len <= 64:
                cur_coll_term = coll_b.term
                for idx in range(concrete_len):
                    if kind_tag == "span":
                        idx_u = _int_term(_INT_SPECS["usize"], idx)
                        elem_term = self.whnf(_apps(_constant("Span_Read"), _U8, cur_coll_term, idx_u))
                    elif kind_tag == "slots":
                        idx_u = _int_term(_INT_SPECS["usize"], idx)
                        d_val = self._default_term_for_type(elem_type)
                        elem_term = self.whnf(
                            _apps(_constant("Slots_Read"), elem_type, c_args[1], d_val, cur_coll_term, idx_u)
                        )
                    else:
                        seq_m = (
                            self.whnf(_apps(_constant("Vec_Model"), elem_type, c_args[1], cur_coll_term))
                            if kind_tag == "vec"
                            else cur_coll_term
                        )
                        d_val = self._default_term_for_type(elem_type)
                        elem_term = self.whnf(
                            _apps(_constant("Seq_At"), elem_type, d_val, seq_m, _term("nat", value=idx))
                        )
                    iter_env = dict(cur_env)
                    if mode == "ref":
                        self.mutable_locals.add(var_name)
                        iter_env[var_name] = _Binding(elem_term, elem_type)
                    else:
                        self.mutable_locals.discard(var_name)
                        if mode == "in":
                            v_fresh = self.fresh(elem_type)
                            self.readonly_span_vars.add(cast("int", v_fresh.value))
                            iter_env[var_name] = _Binding(elem_term, elem_type)
                        else:
                            iter_env[var_name] = _Binding(elem_term, elem_type)
                    before_m = self._eval_loop_decreases(contracts, iter_env)
                    after_iter, ctrl = self._elaborate_non_returning_block(body_node, iter_env, facts)
                    for k in list(cur_env):
                        if k != var_name and k in after_iter and k in self.mutable_locals:
                            cur_env[k] = after_iter[k]
                    if mode == "ref" and coll_name is not None:
                        new_elem = after_iter[var_name].term
                        if kind_tag == "span":
                            idx_u = _int_term(_INT_SPECS["usize"], idx)
                            cur_coll_term = _apps(_constant("Span_Write"), _U8, cur_coll_term, idx_u, new_elem)
                            cur_env[coll_name] = _Binding(cur_coll_term, coll_b.type)
                        elif kind_tag == "slots":
                            idx_u = _int_term(_INT_SPECS["usize"], idx)
                            cur_coll_term = _apps(
                                _constant("Slots_Write"), elem_type, c_args[1], cur_coll_term, idx_u, new_elem
                            )
                            cur_env[coll_name] = _Binding(cur_coll_term, coll_b.type)
                        elif kind_tag == "vec":
                            cur_coll_term = self._update_vec_at(elem_type, cur_coll_term, idx, new_elem)
                            cur_env[coll_name] = _Binding(cur_coll_term, coll_b.type)
                    if ctrl == "break":
                        self._check_loop_invariants(contracts, cur_env, statement, "break")
                        break
                    self._check_loop_invariants(contracts, cur_env, statement, "step")
                    self._check_loop_decreases(before_m, cur_env, "step")
                return cur_env

            # Symbolic collection iteration
            saved_uninit = set(self.uninitialized_out_params)
            sym_env = dict(extended)
            for mname in list(self.mutable_locals):
                if mname in sym_env and mname != var_name and mname != coll_name:
                    m_ty = sym_env[mname].type
                    sym_env[mname] = _Binding(self.fresh(m_ty), m_ty)
            elem_var = self.fresh(elem_type)
            if mode == "ref":
                self.mutable_locals.add(var_name)
            else:
                self.mutable_locals.discard(var_name)
                if mode == "in":
                    self.readonly_span_vars.add(cast("int", elem_var.value))
            sym_env[var_name] = _Binding(elem_var, elem_type)
            saved_facts_len = len(self.active_facts)
            if kind_tag == "span":
                coll_model = self.whnf(_apps(_constant("Span_Model"), _U8, coll_b.term))
            elif kind_tag == "slots":
                coll_model = self.whnf(_apps(_constant("Slots_Model"), elem_type, c_args[1], coll_b.term))
            elif kind_tag == "vec":
                coll_model = self.whnf(_apps(_constant("Vec_Model"), elem_type, c_args[1], coll_b.term))
            else:
                coll_model = self.whnf(coll_b.term)
            for f_term in self._expand_bool_facts([*self.active_facts, *self._fact_bool_terms(facts, extended)]):
                f_head, f_args = self.spine(f_term)
                if f_head == _constant("Seq_All") and len(f_args) == 3 and self.convertible(f_args[1], coll_model):
                    self.active_facts.append(self.whnf(_app(f_args[2], elem_var)))
            assumed = self._assume_loop_invariants(contracts, sym_env)
            self.active_facts.extend(assumed)
            try:
                before_sym_m = self._eval_loop_decreases(contracts, sym_env)
                after_sym, _ = self._elaborate_non_returning_block(body_node, sym_env, facts)
                step_env = dict(sym_env)
                for k in list(sym_env):
                    if k != var_name and k in after_sym and k in self.mutable_locals:
                        step_env[k] = after_sym[k]
                self._check_loop_invariants(contracts, step_env, statement, "inductive step")
                self._check_loop_decreases(before_sym_m, step_env, "inductive step")
            finally:
                self.uninitialized_out_params = saved_uninit
                del self.active_facts[saved_facts_len:]
            for mname in list(self.mutable_locals):
                if mname in cur_env and mname != var_name and sym_env.get(mname, cur_env[mname]).term != after_sym.get(mname, sym_env.get(mname, cur_env[mname])).term:
                    m_ty = cur_env[mname].type
                    loop_tag = self.serial
                    self.serial += 1
                    cur_env[mname] = _Binding(
                        _apps(_constant("LoopState"), m_ty, cur_env[mname].term, _term("nat", value=loop_tag)),
                        m_ty,
                    )
            post_assumed = self._assume_loop_invariants(contracts, cur_env)
            self.active_facts.extend(post_assumed)
            return cur_env
        finally:
            self.in_loop_depth -= 1
            if coll_name is not None:
                self.frozen_collections.discard(coll_name)
            self.mutable_locals = saved_mutable
            self.readonly_span_vars = saved_readonly

    def _elaborate_while_statement(
        self: _Elaborator,
        statement: Node,
        extended: dict[str, _Binding],
        facts: tuple[_Binding, ...],
    ) -> dict[str, _Binding]:
        self.site = statement
        contracts = self.nodes(statement["contracts"])
        cond_node = self.node(statement["condition"])
        body_node = self.node(statement["body"], "block")
        for contract in contracts:
            self.node(contract, "contract")
            if contract["role"] not in {"invariant", "decreases"}:
                raise self.fail("unsupported", f"loop contract '{contract['role']}' is not supported", contract)
        if not any(c["role"] == "decreases" for c in contracts):
            raise self.fail(
                "type",
                "while loop requires at least one 'decreases' termination contract",
                statement,
            )
        saved_mutable = set(self.mutable_locals)
        self.in_loop_depth += 1
        try:
            self._check_loop_invariants(contracts, extended, statement, "entry")
            self._eval_loop_decreases(contracts, extended)
            cur_env = dict(extended)
            unrolled_concretely = False
            concrete_steps = 0
            for _ in range(64):
                cond_t = self.check(cond_node, _BOOL, cur_env)
                cond_w = self.whnf(cond_t)
                if cond_w.kind != "bool":
                    break
                if cond_w.value == 0:
                    unrolled_concretely = True
                    break
                concrete_steps += 1
                before_m = self._eval_loop_decreases(contracts, cur_env)
                after_iter, ctrl = self._elaborate_non_returning_block(body_node, dict(cur_env), facts)
                next_env = dict(cur_env)
                for k in list(cur_env):
                    if k in after_iter and k in self.mutable_locals:
                        next_env[k] = after_iter[k]
                if ctrl == "break":
                    self._check_loop_invariants(contracts, next_env, statement, "break")
                    return next_env
                self._check_loop_invariants(contracts, next_env, statement, "step")
                self._check_loop_decreases(before_m, next_env, "step")
                cur_env = next_env
            else:
                cond_t = self.check(cond_node, _BOOL, cur_env)
                if self.whnf(cond_t) == _term("bool", value=0):
                    unrolled_concretely = True
            if unrolled_concretely and concrete_steps > 0:
                proved = self._check_loop_invariants(contracts, cur_env, statement, "exit")
                self.active_facts.extend(proved)
                return cur_env

            # Symbolic induction for while loop (also checks 0-trip concrete loops)
            saved_uninit = set(self.uninitialized_out_params)
            sym_env = dict(extended)
            for mname in list(self.mutable_locals):
                if mname in sym_env:
                    m_ty = sym_env[mname].type
                    sym_env[mname] = _Binding(self.fresh(m_ty), m_ty)
            sym_cond = self.check(cond_node, _BOOL, sym_env)
            saved_facts_len = len(self.active_facts)
            self.active_facts.append(sym_cond)
            assumed = self._assume_loop_invariants(contracts, sym_env)
            self.active_facts.extend(assumed)
            try:
                before_sym_m = self._eval_loop_decreases(contracts, sym_env)
                after_sym, sym_ctrl = self._elaborate_non_returning_block(body_node, sym_env, facts)
                step_env = dict(sym_env)
                for k in list(sym_env):
                    if k in after_sym and k in self.mutable_locals:
                        step_env[k] = after_sym[k]
                if sym_ctrl != "break":
                    self._check_loop_invariants(contracts, step_env, statement, "inductive step")
                    self._check_loop_decreases(before_sym_m, step_env, "inductive step")
            finally:
                self.uninitialized_out_params = saved_uninit
                del self.active_facts[saved_facts_len:]
            if unrolled_concretely:
                return cur_env
            post_env = dict(extended)
            for mname in list(self.mutable_locals):
                if mname in post_env and sym_env[mname].term != after_sym.get(mname, sym_env[mname]).term:
                    m_ty = post_env[mname].type
                    loop_tag = self.serial
                    self.serial += 1
                    post_env[mname] = _Binding(
                        _apps(_constant("LoopState"), m_ty, post_env[mname].term, _term("nat", value=loop_tag)),
                        m_ty,
                    )
            post_assumed = self._assume_loop_invariants(contracts, post_env)
            self.active_facts.extend(post_assumed)
            if not self._contains_break_statement(body_node):
                post_cond = self.check(cond_node, _BOOL, post_env)
                self.active_facts.append(self._negate_bool_term(post_cond))
            return post_env
        finally:
            self.in_loop_depth -= 1
            self.mutable_locals = saved_mutable

    def _contains_break_statement(self: _Elaborator, node: Node) -> bool:
        kind = node.get("kind")
        if kind == "break":
            return True
        if kind in {"while", "foreach", "foreach_collection"}:
            return False
        if kind == "block":
            return any(self._contains_break_statement(st) for st in self.nodes(node["statements"]))
        if kind == "if":
            then_b = self._contains_break_statement(self.node(node["then"]))
            else_b = self._contains_break_statement(self.node(node["else"])) if node.get("else") is not None else False
            return then_b or else_b
        if kind in {"let_else", "var_else"}:
            return self._contains_break_statement(self.node(node["else"]))
        if kind == "scope":
            return self._contains_break_statement(self.node(node["body"]))
        return False

    def _update_vec_at(self: _Elaborator, elem_type: _Term, vec_term: _Term, target_idx: int, new_val: _Term) -> _Term:
        v_w = self.whnf(vec_term)
        head, args = self.spine(v_w)
        if head == _constant("VCons") and len(args) == 4:
            if target_idx == 0:
                return _apps(_constant("VCons"), args[0], args[1], new_val, args[3])
            return _apps(
                _constant("VCons"),
                args[0],
                args[1],
                args[2],
                self._update_vec_at(elem_type, args[3], target_idx - 1, new_val),
            )
        return vec_term

    def block(self: _Elaborator, node: Node, environment: dict[str, _Binding], expected: _Term | None = None,
              *, facts: tuple[_Binding, ...] = ()) -> _Binding:
        self.node(node, "block")
        statements = self.nodes(node["statements"])
        extended = dict(environment)
        active_facts: list[_Binding] = list(facts)
        statement_facts: list[_Binding] = []
        peeled_vars: list[_Term] = []
        returns_lambda = False
        final_assert_value: Node | None = None
        if statements:
            last = statements[-1]
            if last["kind"] == "return" and isinstance(last.get("value"), dict):
                unwrapped = self._unwrap_group(cast("Node", last["value"]))
                returns_lambda = unwrapped["kind"] in {"lambda", "typed_lambda"}
            elif last["kind"] == "assert" and isinstance(last.get("value"), dict):
                final_assert_value = self._unwrap_group(cast("Node", last["value"]))
        if not returns_lambda:
            while expected is not None and self._is_prop_type(expected):
                resolved_expected = self.whnf(expected)
                if (resolved_expected.kind != "pi"
                        or cast("int", resolved_expected.value) in self.nullary_parameters):
                    break
                var_id = cast("int", resolved_expected.value)
                if var_id in self.parameter_names:
                    if final_assert_value is not None and final_assert_value["kind"] == "quantifier":
                        break
                    param_name = self.parameter_names[var_id]
                    if param_name in extended:
                        break
                    var = self.fresh(resolved_expected.args[0])
                    self.parameter_names[cast("int", var.value)] = param_name
                    self.bind_local(extended, param_name, _Binding(var, resolved_expected.args[0]))
                    if self._is_prop_type(resolved_expected.args[0]):
                        active_facts.append(_Binding(var, resolved_expected.args[0]))
                else:
                    if (final_assert_value is not None
                            and final_assert_value["kind"] == "binary"
                            and isinstance(final_assert_value.get("operator"), dict)
                            and cast("Node", final_assert_value["operator"]).get("text") == "==>"):
                        break
                    var = self.fresh(resolved_expected.args[0])
                    active_facts.append(_Binding(var, resolved_expected.args[0]))
                peeled_vars.append(var)
                expected = self.substitute(resolved_expected.args[1], var_id, var)

        def finish(result: _Binding) -> _Binding:
            if not peeled_vars:
                return result
            return _Binding(
                self.wrap("lam", peeled_vars, result.term),
                self.wrap("pi", peeled_vars, result.type),
            )

        def lift_stmt_propagate(
            stmt: Node, field_key: str, idx_stmt: int
        ) -> _Binding | None:
            raw_field = stmt.get(field_key)
            if raw_field is None:
                return None
            split_res = self._split_first_propagate(self.node(raw_field))
            if split_res is None:
                return None
            prop_node, rebuild = split_res
            target_ret = expected if expected is not None else self.current_return_type
            if target_ret is None:
                raise self.fail(
                    "type",
                    "'?' propagation requires an enclosing callable or block returning an Option or Result union",
                    prop_node,
                )
            combined_f = (*active_facts, *statement_facts)
            term = self._elaborate_propagate(
                prop_node,
                extended,
                target_ret,
                lambda temp_name, _ok_b, ok_env: self.block(
                    {
                        "kind": "block",
                        "span": node["span"],
                        "statements": [
                            {
                                **stmt,
                                field_key: rebuild(
                                    {
                                        "kind": "name",
                                        "span": prop_node["span"],
                                        "name": {"text": temp_name, "span": prop_node["span"]},
                                    }
                                ),
                            },
                            *statements[idx_stmt + 1:],
                        ],
                    },
                    ok_env,
                    target_ret,
                    facts=combined_f,
                ).term,
            )
            return finish(_Binding(term, target_ret))

        saved_active_len = len(self.active_facts)
        self.active_facts.extend(self._fact_bool_terms(active_facts, extended))
        try:
            for index, statement in enumerate(statements):
                self.site = statement
                kind = cast("str", statement["kind"])
                if kind in {"let", "typed_local", "let_pattern", "constant_local", "var", "var_pattern"}:
                    if kind != "constant_local":
                        lifted = lift_stmt_propagate(statement, "value", index)
                        if lifted is not None:
                            return lifted
                    previous_keys = set(extended)
                    extended = self.local(statement, extended)
                    for new_key in set(extended) - previous_keys:
                        bound = extended[new_key]
                        if self._is_prop_type(bound.type):
                            statement_facts.append(bound)
                            self.active_facts.extend(self._fact_bool_terms((bound,), extended))
                    continue
                if kind == "assignment":
                    lifted = lift_stmt_propagate(statement, "value", index)
                    if lifted is not None:
                        return lifted
                    extended = self._elaborate_assignment(statement, extended)
                    continue
                if kind == "expression_statement":
                    lifted = lift_stmt_propagate(statement, "value", index)
                    if lifted is not None:
                        return lifted
                    extended = self._elaborate_expression_statement(statement, extended)
                    continue
                if kind == "scope":
                    extended = self._elaborate_scope_statement(
                        statement, extended, (*active_facts, *statement_facts)
                    )
                    continue
                if kind == "foreach":
                    extended = self._elaborate_foreach_statement(
                        statement, extended, (*active_facts, *statement_facts)
                    )
                    continue
                if kind == "foreach_collection":
                    extended = self._elaborate_foreach_collection_statement(
                        statement, extended, (*active_facts, *statement_facts)
                    )
                    continue
                if kind == "while":
                    extended = self._elaborate_while_statement(
                        statement, extended, (*active_facts, *statement_facts)
                    )
                    continue
                if kind in {"break", "continue"}:
                    raise self.fail("type", f"'{kind}' statement is only permitted inside a loop", statement)
                if kind == "assert":
                    fact = self._elaborate_assert(statement, extended, (*active_facts, *statement_facts))
                    statement_facts.append(fact)
                    self.active_facts.extend(self._fact_bool_terms((fact,), extended))
                    if index == len(statements) - 1:
                        self.final_ref_bindings = dict(extended)
                        self.final_return_facts = list(self.active_facts[saved_active_len:])
                        self.final_theorem_facts = tuple(statement_facts)
                        if self.in_post_env_theorem and expected is None:
                            return finish(statement_facts[-1])
                        if expected is not None and self._is_prop_type(expected):
                            try:
                                term = self._prove_proposition(
                                    expected,
                                    extended,
                                    tuple(statement_facts),
                                    statement,
                                    allow_refl=False,
                                    include_env=False,
                                )
                                return finish(_Binding(term, expected))
                            except VelaError:
                                if self._entailed_by_theorem_facts(expected, extended):
                                    self.used_domain_solver_in_proof = True
                                    return finish(_Binding(_apps(_constant("Refl"), _BOOL, _term("bool", value=1)), expected))
                                raise
                    continue
                if kind == "proof":
                    sub_facts = self._elaborate_proof_statement(
                        self.node(statement["body"], "block"), extended, (*active_facts, *statement_facts)
                    )
                    statement_facts.extend(sub_facts)
                    self.active_facts.extend(self._fact_bool_terms(sub_facts, extended))
                    if index == len(statements) - 1:
                        self.final_ref_bindings = dict(extended)
                        self.final_return_facts = list(self.active_facts[saved_active_len:])
                        self.final_theorem_facts = tuple(statement_facts)
                        if self.in_post_env_theorem and expected is None:
                            return finish(statement_facts[-1] if statement_facts else _Binding(_constant("Tt"), _UNIT))
                        if expected is not None and self._is_prop_type(expected):
                            try:
                                term = self._prove_proposition(
                                    expected,
                                    extended,
                                    tuple(statement_facts),
                                    statement,
                                    allow_refl=False,
                                    include_env=False,
                                )
                                return finish(_Binding(term, expected))
                            except VelaError:
                                if self._entailed_by_theorem_facts(expected, extended):
                                    self.used_domain_solver_in_proof = True
                                    return finish(_Binding(_apps(_constant("Refl"), _BOOL, _term("bool", value=1)), expected))
                                raise
                    continue
                if kind == "calc":
                    sub_facts = self._elaborate_calc_statement(
                        self.node(statement["body"], "block"), extended, (*active_facts, *statement_facts)
                    )
                    statement_facts.extend(sub_facts)
                    self.active_facts.extend(self._fact_bool_terms(sub_facts, extended))
                    if index == len(statements) - 1:
                        self.final_ref_bindings = dict(extended)
                        self.final_return_facts = list(self.active_facts[saved_active_len:])
                        self.final_theorem_facts = tuple(statement_facts)
                        if self.in_post_env_theorem and expected is None:
                            return finish(statement_facts[-1] if statement_facts else _Binding(_constant("Tt"), _UNIT))
                        if expected is not None and self._is_prop_type(expected):
                            try:
                                term = self._prove_proposition(
                                    expected,
                                    extended,
                                    tuple(statement_facts),
                                    statement,
                                    allow_refl=False,
                                    include_env=False,
                                )
                                return finish(_Binding(term, expected))
                            except VelaError:
                                if self._entailed_by_theorem_facts(expected, extended):
                                    self.used_domain_solver_in_proof = True
                                    return finish(_Binding(_apps(_constant("Refl"), _BOOL, _term("bool", value=1)), expected))
                                raise
                    continue
                if kind in {"let_else", "var_else"}:
                    if index == len(statements) - 1:
                        raise self.fail(
                            "type",
                            f"a pure block requires an explicit terminal return after {kind.replace('_', '-')}",
                            statement,
                        )
                    lifted = lift_stmt_propagate(statement, "value", index)
                    if lifted is not None:
                        return lifted
                    else_block = self.node(statement["else"], "block")
                    else_statements = self.nodes(else_block["statements"])
                    rest_statements = statements[index + 1:]
                    combined_facts = (*active_facts, *statement_facts)
                    visited_arms: set[int] = set()
                    saved_mut = set(self.mutable_locals)
                    if kind == "var_else":
                        pat_preview = self._parse_pattern(self.node(statement["pattern"]), set())
                        pnames: set[str] = set()
                        self._collect_pat_names(pat_preview, pnames)
                        self.mutable_locals.update(pnames)
                    synthetic_match: Node = {
                        "kind": "match",
                        "span": node["span"],
                        "value": statement["value"],
                        "motive": None,
                        "cases": [
                            {
                                "kind": "case",
                                "span": node["span"],
                                "pattern": statement["pattern"],
                                "statements": rest_statements,
                            },
                            {
                                "kind": "case",
                                "span": else_block["span"],
                                "pattern": {"kind": "wildcard_pattern", "span": else_block["span"]},
                                "statements": else_statements,
                            },
                        ],
                    }
                    try:
                        saved_uninit_match = set(self.uninitialized_out_params)
                        result = self.match(
                            synthetic_match,
                            extended,
                            expected,
                            expression_arms=False,
                            facts=combined_facts,
                            refine_scrutinee=True,
                            visited_arms=visited_arms,
                            synthetic=True,
                        )
                        after_match_uninit = set(self.uninitialized_out_params)
                        if 1 not in visited_arms:
                            self.uninitialized_out_params = saved_uninit_match
                            self.block(else_block, extended, result.type, facts=combined_facts)
                            self.uninitialized_out_params = after_match_uninit
                    finally:
                        self.mutable_locals = saved_mut
                    return finish(result)
                if kind == "if" and index < len(statements) - 1:
                    lifted = lift_stmt_propagate(statement, "condition", index)
                    if lifted is not None:
                        return lifted
                    then_node = self.node(statement["then"])
                    then_stmts = (
                        self.nodes(then_node["statements"])
                        if then_node["kind"] == "block"
                        else [then_node]
                    )
                    else_raw = statement["else"]
                    else_stmts = (
                        None
                        if else_raw is None
                        else (
                            self.nodes(self.node(else_raw)["statements"])
                            if self.node(else_raw)["kind"] == "block"
                            else [self.node(else_raw)]
                        )
                    )
                    then_returns = bool(then_stmts and then_stmts[-1]["kind"] == "return")
                    else_returns = bool(else_stmts and else_stmts[-1]["kind"] == "return")
                    if not then_returns and not else_returns:
                        extended, _ = self._elaborate_non_returning_block(
                            {"kind": "block", "span": statement["span"], "statements": [statement]},
                            extended,
                            (*active_facts, *statement_facts),
                        )
                        continue
                    rest_statements = statements[index + 1:]
                    if then_returns and else_stmts is None:
                        cur_stmt: Node = {
                            **statement,
                            "else": {
                                "kind": "block",
                                "span": node["span"],
                                "statements": rest_statements,
                            },
                        }
                    elif then_returns and not else_returns and else_stmts is not None:
                        cur_stmt = {
                            **statement,
                            "else": {
                                "kind": "block",
                                "span": node["span"],
                                "statements": [*else_stmts, *rest_statements],
                            },
                        }
                    elif not then_returns and else_returns:
                        cur_stmt = {
                            **statement,
                            "then": {
                                "kind": "block",
                                "span": node["span"],
                                "statements": [*then_stmts, *rest_statements],
                            },
                        }
                    else:
                        raise self.fail("unsupported", "a returning terminal must be the final statement")
                elif kind == "match" and index < len(statements) - 1:
                    lifted = lift_stmt_propagate(statement, "value", index)
                    if lifted is not None:
                        return lifted
                    rest_statements = statements[index + 1:]
                    new_cases: list[Node] = []
                    for arm in self.nodes(statement["cases"]):
                        arm_stmts = self.nodes(arm["statements"])
                        if arm_stmts and arm_stmts[-1]["kind"] == "return":
                            new_cases.append(arm)
                        else:
                            new_cases.append({**arm, "statements": [*arm_stmts, *rest_statements]})
                    cur_stmt = {**statement, "cases": new_cases}
                elif index != len(statements) - 1:
                    raise self.fail("unsupported", "a returning terminal must be the final statement")
                else:
                    cur_stmt = statement
                if kind == "return":
                    if self.active_lift_scopes > 0:
                        raise self.fail(
                            "type",
                            "cannot return from a callable while a record invariant is lifted in an enclosing scope",
                            cur_stmt,
                        )
                    if cur_stmt["value"] is None:
                        if self.uninitialized_out_params:
                            uninit_list = ", ".join(sorted(self.uninitialized_out_params))
                            raise self.fail(
                                "type",
                                f"cannot return before 'out' parameter '{uninit_list}' is initialized",
                                cur_stmt,
                            )
                        value = _Binding(_term("unit"), _UNIT)
                        if expected is not None:
                            self.unify(value.type, expected)
                        self.final_ref_bindings = dict(extended)
                        self.final_return_facts = list(self.active_facts[saved_active_len:])
                        return finish(value)
                    lifted = lift_stmt_propagate(cur_stmt, "value", index)
                    if lifted is not None:
                        return lifted
                    value_node = self.node(cur_stmt["value"])
                    result = (
                        self.expression(value_node, extended)
                        if expected is None
                        else _Binding(self.check(value_node, expected, extended), expected)
                    )
                    self._consume_call_updates(extended, cur_stmt)
                    if self.uninitialized_out_params:
                        uninit_list = ", ".join(sorted(self.uninitialized_out_params))
                        raise self.fail(
                            "type",
                            f"cannot return before 'out' parameter '{uninit_list}' is initialized",
                            cur_stmt,
                        )
                    self.final_ref_bindings = dict(extended)
                    self.final_return_facts = list(self.active_facts[saved_active_len:])
                    return finish(result)
                if kind == "if":
                    if cur_stmt["else"] is None:
                        raise self.fail("type", "every conditional branch must return")
                    lifted = lift_stmt_propagate(cur_stmt, "condition", index)
                    if lifted is not None:
                        return lifted
                    combined_facts = (*active_facts, *statement_facts)
                    cond_raw = self.node(cur_stmt["condition"])
                    cond_unwrapped = self._unwrap_group(cond_raw)
                    if cond_unwrapped["kind"] == "is":
                        return finish(
                            self._if_is(
                                cond_unwrapped,
                                self.node(cur_stmt["then"]),
                                self.node(cur_stmt["else"]),
                                extended,
                                expected,
                                expression_branches=False,
                                facts=combined_facts,
                                site_node=cur_stmt,
                            )
                        )
                    condition = self.check(cond_raw, _BOOL, extended)
                    saved_uninit = set(self.uninitialized_out_params)
                    self.active_facts.append(condition)
                    try:
                        yes = self.branch(self.node(cur_stmt["then"]), extended, expected, facts=combined_facts)
                        yes_refs = dict(self.final_ref_bindings)
                        yes_uninit = set(self.uninitialized_out_params)
                    finally:
                        self.active_facts.pop()
                    self.uninitialized_out_params = set(saved_uninit)
                    self.active_facts.append(_app(_constant("!"), condition))
                    try:
                        no = self.branch(self.node(cur_stmt["else"]), extended, yes.type, facts=combined_facts)
                        no_refs = dict(self.final_ref_bindings)
                        no_uninit = set(self.uninitialized_out_params)
                    finally:
                        self.active_facts.pop()
                    self.uninitialized_out_params = yes_uninit | no_uninit
                    merged_refs = dict(extended)
                    for rk in set(yes_refs) & set(no_refs):
                        yb = yes_refs[rk]
                        nb = no_refs[rk]
                        if yb.term != nb.term:
                            merged_refs[rk] = _Binding(
                                self.whnf(_term("if", yb.type, condition, yb.term, nb.term)),
                                yb.type,
                            )
                        else:
                            merged_refs[rk] = yb
                    self.final_ref_bindings = merged_refs
                    return finish(_Binding(_term("if", yes.type, condition, yes.term, no.term), yes.type))
                if kind == "match":
                    lifted = lift_stmt_propagate(cur_stmt, "value", index)
                    if lifted is not None:
                        return lifted
                    return finish(
                        self.match(
                            cur_stmt,
                            extended,
                            expected,
                            expression_arms=False,
                            facts=(*active_facts, *statement_facts),
                        )
                    )
                if kind == "block":
                    return finish(
                        self.block(statement, extended, expected, facts=(*active_facts, *statement_facts))
                    )
                raise self.fail("unsupported", f"statement '{kind}' requires the full frontend")
            if (
                statements
                and statements[-1]["kind"]
                in {"assignment", "expression_statement", "scope", "foreach", "foreach_collection", "while"}
                and expected is not None
                and self.whnf(expected) == _UNIT
            ):
                if self.uninitialized_out_params:
                    uninit_list = ", ".join(sorted(self.uninitialized_out_params))
                    raise self.fail(
                        "type",
                        f"cannot return before 'out' parameter '{uninit_list}' is initialized",
                        node,
                    )
                self.final_ref_bindings = dict(extended)
                return finish(_Binding(_term("unit"), _UNIT))
            raise self.fail("type", "a pure block requires an explicit terminal return", node)
        finally:
            del self.active_facts[saved_active_len:]

    def branch(self: _Elaborator, node: Node, environment: dict[str, _Binding], expected: _Term | None,
               *, facts: tuple[_Binding, ...] = ()) -> _Binding:
        if node["kind"] == "block":
            return self.block(node, environment, expected, facts=facts)
        return self.block(
            {"kind": "block", "span": node["span"], "statements": [node]},
            environment,
            expected,
            facts=facts,
        )

    def _if_is(
        self: _Elaborator,
        is_node: Node,
        then_node: Node,
        else_node: Node,
        environment: dict[str, _Binding],
        expected: _Term | None = None,
        *,
        expression_branches: bool = True,
        facts: tuple[_Binding, ...] = (),
        site_node: Node,
    ) -> _Binding:
        visited_arms: set[int] = set()
        if expression_branches:
            synthetic: Node = {
                "kind": "match_expression",
                "span": site_node["span"],
                "value": is_node["value"],
                "motive": None,
                "cases": [
                    {
                        "kind": "expression_case",
                        "span": then_node["span"],
                        "pattern": is_node["pattern"],
                        "value": then_node,
                    },
                    {
                        "kind": "expression_case",
                        "span": else_node["span"],
                        "pattern": {"kind": "wildcard_pattern", "span": else_node["span"]},
                        "value": else_node,
                    },
                ],
            }
            result = self.match(
                synthetic,
                environment,
                expected,
                expression_arms=True,
                facts=facts,
                refine_scrutinee=True,
                visited_arms=visited_arms,
                synthetic=True,
            )
            if 1 not in visited_arms:
                self.check(else_node, result.type, environment)
            return result
        then_stmts = self.nodes(then_node["statements"]) if then_node["kind"] == "block" else [then_node]
        else_stmts = self.nodes(else_node["statements"]) if else_node["kind"] == "block" else [else_node]
        synthetic = {
            "kind": "match",
            "span": site_node["span"],
            "value": is_node["value"],
            "motive": None,
            "cases": [
                {
                    "kind": "case",
                    "span": then_node["span"],
                    "pattern": is_node["pattern"],
                    "statements": then_stmts,
                },
                {
                    "kind": "case",
                    "span": else_node["span"],
                    "pattern": {"kind": "wildcard_pattern", "span": else_node["span"]},
                    "statements": else_stmts,
                },
            ],
        }
        result = self.match(
            synthetic,
            environment,
            expected,
            expression_arms=False,
            facts=facts,
            refine_scrutinee=True,
            visited_arms=visited_arms,
            synthetic=True,
        )
        if 1 not in visited_arms:
            self.branch(else_node, environment, result.type, facts=facts)
        return result

    def if_expression(
        self: _Elaborator, node: Node, environment: dict[str, _Binding], expected: _Term | None = None
    ) -> _Binding:
        self.site = node
        cond_raw = self.node(node["condition"])
        cond_unwrapped = self._unwrap_group(cond_raw)
        then_node = self.node(node["then"])
        else_node = self.node(node["else"])
        if cond_unwrapped["kind"] == "is":
            return self._if_is(
                cond_unwrapped,
                then_node,
                else_node,
                environment,
                expected,
                expression_branches=True,
                site_node=node,
            )
        synthetic: Node = {
            "kind": "match_expression",
            "span": node["span"],
            "value": cond_raw,
            "motive": None,
            "cases": [
                {
                    "kind": "expression_case",
                    "span": then_node["span"],
                    "pattern": {"kind": "bool_pattern", "span": cond_raw["span"], "value": True},
                    "value": then_node,
                },
                {
                    "kind": "expression_case",
                    "span": else_node["span"],
                    "pattern": {"kind": "bool_pattern", "span": cond_raw["span"], "value": False},
                    "value": else_node,
                },
            ],
        }
        return self.match(
            synthetic,
            environment,
            expected,
            expression_arms=True,
            refine_scrutinee=True,
            expected_scrutinee_type=_BOOL,
            synthetic=True,
        )

    def _is_expression(self: _Elaborator, node: Node, environment: dict[str, _Binding]) -> _Binding:
        self.site = node
        pat_node = self.node(node["pattern"])
        synthetic: Node = {
            "kind": "match_expression",
            "span": node["span"],
            "value": node["value"],
            "motive": None,
            "cases": [
                {
                    "kind": "expression_case",
                    "span": pat_node["span"],
                    "pattern": pat_node,
                    "value": {"kind": "bool", "span": pat_node["span"], "value": True},
                },
                {
                    "kind": "expression_case",
                    "span": node["span"],
                    "pattern": {"kind": "wildcard_pattern", "span": pat_node["span"]},
                    "value": {"kind": "bool", "span": node["span"], "value": False},
                },
            ],
        }
        return self.match(synthetic, environment, _BOOL, expression_arms=True, synthetic=True)

    def _project_member(self: _Elaborator, receiver: _Binding, member_name: str, node: Node) -> _Binding:
        self.site = node
        receiver_type = self.whnf(receiver.type)
        head, type_args = self.spine(receiver_type)
        if head == _constant("Span") and len(type_args) == 1 and self.whnf(type_args[0]) == _U8:
            if member_name == "Model":
                self._check_span_can_read(receiver.term, {}, node)
                return _Binding(
                    _apps(_constant("Span_Model"), _U8, receiver.term),
                    _app(_constant("Seq"), _U8),
                )
            span_props: dict[str, tuple[str, _Term]] = {
                "Base": ("Span_Base", _USIZE),
                "Length": ("Span_Length", _USIZE),
                "Tag": ("Span_Tag", _BOOL),
                "PermRead": ("Span_PermRead", _BOOL),
                "PermWrite": ("Span_PermWrite", _BOOL),
                "CanRead": ("Span_CanRead", _BOOL),
                "CanWrite": ("Span_CanWrite", _BOOL),
            }
            if member_name not in span_props:
                raise self.fail("name", f"Span<byte> has no property '{member_name}'", node)
            const_name, prop_ty = span_props[member_name]
            return _Binding(_apps(_constant(const_name), _U8, receiver.term), prop_ty)
        if head == _constant("Vec") and len(type_args) == 2:
            if member_name == "Model":
                return _Binding(
                    _apps(_constant("Vec_Model"), type_args[0], type_args[1], receiver.term),
                    _app(_constant("Seq"), type_args[0]),
                )
            if member_name == "Count":
                return _Binding(type_args[1], _NAT)
            raise self.fail("name", f"Vec has no property '{member_name}'", node)
        if head == _constant("Seq") and len(type_args) == 1:
            if member_name == "Count":
                return _Binding(_apps(_constant("Seq_Count"), type_args[0], receiver.term), _NAT)
            if member_name == "Model":
                return receiver
            raise self.fail("name", f"Seq has no property '{member_name}'", node)
        if head == _constant("Slots") and len(type_args) == 2:
            elem_t, cap_t = type_args[0], type_args[1]
            if member_name == "Capacity":
                cap_w = self.whnf(cap_t)
                if cap_w.kind == "nat":
                    return _Binding(_int_term(_INT_SPECS["usize"], cast("int", cap_w.value)), _USIZE)
                return _Binding(cap_t, _NAT)
            if member_name == "Model":
                return _Binding(
                    _apps(_constant("Slots_Model"), elem_t, cap_t, receiver.term),
                    _app(_constant("Seq"), elem_t),
                )
            slots_props: dict[str, tuple[str, _Term]] = {
                "Base": ("Slots_Base", _USIZE),
                "LiveCount": ("Slots_LiveCount", _USIZE),
                "Tag": ("Slots_Tag", _BOOL),
                "PermRead": ("Slots_PermRead", _BOOL),
                "PermWrite": ("Slots_PermWrite", _BOOL),
                "CanRead": ("Slots_CanRead", _BOOL),
                "CanWrite": ("Slots_CanWrite", _BOOL),
            }
            if member_name not in slots_props:
                raise self.fail("name", f"Slots has no property '{member_name}'", node)
            const_name, prop_ty = slots_props[member_name]
            return _Binding(_apps(_constant(const_name), elem_t, cap_t, receiver.term), prop_ty)
        if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.records_by_type:
            raise self.fail(
                "unsupported",
                "member projection requires a record receiver, a Format.Write call or the full frontend",
                node,
            )
        record_info = self.records_by_type[head.value]
        for idx, rf in enumerate(record_info.fields):
            if rf.name == member_name:
                ftype = self._instantiate_record_field_type(record_info, type_args, idx, receiver.term)
                fterm = _apps(_constant(rf.proj_const), *type_args, receiver.term)
                return _Binding(fterm, ftype)
        if member_name in record_info.properties:
            prop_info = record_info.properties[member_name]
            ptype = self._instantiate_record_type(record_info, type_args, prop_info.type)
            ptype = self.substitute(ptype, cast("int", prop_info.self_var.value), receiver.term)
            pterm = _apps(_constant(prop_info.prop_const), *type_args, receiver.term)
            return _Binding(pterm, ptype)
        raise self.fail("name", f"record '{record_info.name}' has no field or property '{member_name}'", node)

    def with_expression(
        self: _Elaborator, node: Node, environment: dict[str, _Binding], expected: _Term | None = None
    ) -> _Binding:
        self.site = node
        base_node = self.node(node["value"])
        expected_head = self.spine(self.whnf(expected))[0] if expected is not None else None
        if (
            expected is not None
            and expected_head is not None
            and expected_head.kind == "const"
            and expected_head.value in self.records_by_type
        ):
            base_term = self.check(base_node, expected, environment)
            base = _Binding(base_term, expected)
        else:
            base = self.expression(base_node, environment)
        base_type = self.whnf(base.type)
        head, type_args = self.spine(base_type)
        if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.records_by_type:
            raise self.fail("type", "record update 'with { ... }' requires a record value", base_node)
        record_info = self.records_by_type[head.value]
        field_index_by_name = {rf.name: idx for idx, rf in enumerate(record_info.fields)}
        updates = self.nodes(node["updates"])
        update_by_index: dict[int, Node] = {}
        last_index = -1
        last_name = ""
        for update_node in updates:
            self.node(update_node, "field_update")
            fname = self.name(update_node["name"])
            if fname not in field_index_by_name:
                raise self.fail("name", f"record '{record_info.name}' has no field '{fname}'", update_node)
            fidx = field_index_by_name[fname]
            if fidx in update_by_index:
                raise self.fail("name", f"duplicate field '{fname}' in record update", update_node)
            if fidx < last_index:
                raise self.fail(
                    "name",
                    f"record update fields must appear in declaration order; '{fname}' cannot follow '{last_name}'",
                    update_node,
                )
            update_by_index[fidx] = update_node
            last_index = fidx
            last_name = fname
        if not record_info.fields:
            raise self.fail("type", f"record '{record_info.name}' has no fields to update", node)
        final_fields: list[_Term] = []
        for idx, rf in enumerate(record_info.fields):
            ftype = self._instantiate_record_type(record_info, type_args, rf.type)
            for j in range(idx):
                ftype = self.substitute(ftype, cast("int", record_info.fields[j].var.value), final_fields[j])
            if idx in update_by_index:
                u_node = update_by_index[idx]
                final_fields.append(self.check(self.node(u_node["value"]), ftype, environment))
            else:
                old_ftype = self._instantiate_record_field_type(record_info, type_args, idx, base.term)
                if not self._try_unify(old_ftype, ftype):
                    raise self.fail(
                        "type",
                        f"record update changes an index that field '{rf.name}' depends on; update '{rf.name}' as well",
                        node,
                    )
                final_fields.append(_apps(_constant(rf.proj_const), *type_args, base.term))
        result_term = _apps(_constant(record_info.ctor_const), *type_args, *final_fields)
        result_type = _apps(_constant(record_info.type_const), *type_args)
        if expected is not None:
            self.unify(result_type, expected)
        base_unwrapped = self._unwrap_group(base_node)
        base_name = self.name(base_unwrapped["name"]) if base_unwrapped["kind"] == "name" else None
        assign_target = getattr(self, "_in_lifted_target_assignment", None)
        excluded = (
            self.lifted_invariants.get(base_name, set())
            if base_name is not None and base_name == assign_target
            else set()
        )
        self._check_record_invariants(
            record_info, type_args, result_term, environment, node, exclude_clauses=excluded
        )
        return _Binding(result_term, result_type)
