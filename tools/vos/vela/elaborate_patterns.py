# SPDX-License-Identifier: Apache-2.0
"""Pattern parsing, dependent pattern typing, and exhaustive match compilation for Vela elaboration."""

from typing import TYPE_CHECKING, cast

from vos.vela.elaborate_types import (
    _BOOL,
    _CHAR,
    _NAT,
    _NUMERICS_ALIASES,
    _SORT,
    _UNIT,
    MAX_PATTERN_NAT,
    Node,
    _app,
    _apps,
    _Binding,
    _constant,
    _int_term,
    _parse_numeric_magnitude,
    _Pat,
    _RecordInfo,
    _Row,
    _Term,
    _term,
)

if TYPE_CHECKING:
    from vos.vela.elaborate import _Elaborator


class _PatternsMixin:
    def _parse_pattern(self: _Elaborator, node: Node, seen: set[str]) -> _Pat:
        self.tick()
        self.site = node
        kind = node["kind"]
        if kind == "wildcard_pattern":
            return _Pat("wild", node)
        if kind == "binding_pattern":
            name = self.name(node["name"])
            if "." in name or name == "_" or name in seen:
                raise self.fail("name", f"duplicate or invalid pattern binding '{name}'", node)
            seen.add(name)
            return _Pat("wild", node, names=(name,))
        if kind == "group_pattern":
            return self._parse_pattern(self.node(node["pattern"]), seen)
        if kind == "unit_pattern":
            return _Pat("unit", node)
        if kind == "bool_pattern":
            return _Pat("bool", node, value=cast("bool", node["value"]))
        if kind == "character_pattern":
            cp = self._decode_char_literal(cast("str", node["value"]), node)
            return _Pat("char", node, value=cp)
        if kind == "string_pattern":
            raw_bytes = self._decode_string_literal(cast("str", node["value"]), node)
            return _Pat("string", node, value=raw_bytes.decode("latin1"))
        if kind == "tuple_pattern":
            items = [self._parse_pattern(item, seen) for item in self.nodes(node["patterns"])]
            if len(items) < 2:
                raise self.fail("protocol", "a tuple pattern requires at least two components", node)
            result = items[-1]
            for item in reversed(items[:-1]):
                result = _Pat("pair", node, args=(item, result))
            return result
        if kind == "nat_pattern":
            amount = _parse_numeric_magnitude(cast("str", node["value"]))
            suffix = cast("str", node["suffix"])
            if suffix or amount > MAX_PATTERN_NAT:
                return _Pat("int_lit", node, value=f"{amount}:{suffix}")
            result = _Pat("zero", node, value=f"{amount}:")
            for _ in range(amount):
                result = _Pat("succ", node, value=f"{amount}:", args=(result,))
            return result
        if kind == "constructor_pattern":
            cname = self.name(node["name"])
            arguments = self.nodes(node["arguments"])
            if cname == "Succ":
                if len(arguments) != 1:
                    raise self.fail("type", "constructor 'Succ' expects 1 pattern argument", node)
                if arguments[0]["kind"] == "labeled_pattern":
                    raise self.fail("name", "constructor 'Succ' does not accept labeled pattern arguments", arguments[0])
                return _Pat("succ", node, args=(self._parse_pattern(arguments[0], seen),))
            if cname in self.records:
                record_info = self.records[cname]
                if len(arguments) != len(record_info.fields):
                    raise self.fail(
                        "type",
                        f"constructor '{cname}' expects {len(record_info.fields)} pattern arguments, got {len(arguments)}",
                        node,
                    )
                labeled = False
                sub_patterns: list[_Pat] = []
                for idx, arg_node in enumerate(arguments):
                    expected_field = record_info.fields[idx]
                    if arg_node["kind"] == "labeled_pattern":
                        labeled = True
                        spelling = self.name(arg_node["label"])
                        if spelling != expected_field.name:
                            raise self.fail(
                                "name",
                                f"expected pattern field label '{expected_field.name}', got '{spelling}'",
                                arg_node,
                            )
                        sub_patterns.append(self._parse_pattern(self.node(arg_node["pattern"]), seen))
                    else:
                        if labeled:
                            raise self.fail(
                                "name",
                                "positional pattern arguments cannot follow a labeled pattern argument",
                                arg_node,
                            )
                        sub_patterns.append(self._parse_pattern(arg_node, seen))
                return _Pat("record", node, value=cname, args=tuple(sub_patterns))
            if cname in self.union_ctors:
                _, ctor_info = self.union_ctors[cname]
                if len(arguments) != len(ctor_info.fields):
                    raise self.fail(
                        "type",
                        f"constructor '{cname}' expects {len(ctor_info.fields)} pattern arguments, got {len(arguments)}",
                        node,
                    )
                labeled = False
                sub_patterns = []
                for idx, arg_node in enumerate(arguments):
                    expected_field = ctor_info.fields[idx]
                    if arg_node["kind"] == "labeled_pattern":
                        labeled = True
                        spelling = self.name(arg_node["label"])
                        if spelling != expected_field.name:
                            raise self.fail(
                                "name",
                                f"expected pattern field label '{expected_field.name}', got '{spelling}'",
                                arg_node,
                            )
                        sub_patterns.append(self._parse_pattern(self.node(arg_node["pattern"]), seen))
                    else:
                        if labeled:
                            raise self.fail(
                                "name",
                                "positional pattern arguments cannot follow a labeled pattern argument",
                                arg_node,
                            )
                        sub_patterns.append(self._parse_pattern(arg_node, seen))
                return _Pat("union", node, value=cname, args=tuple(sub_patterns))
            if cname not in self.globals:
                raise self.fail("name", f"unknown constructor '{cname}'", node)
            if cname in {"VNil", "VCons", "FZero", "FSucc"}:
                raise self.fail("unsupported", f"indexed elimination over '{cname}' requires the full frontend", node)
            raise self.fail("type", f"'{cname}' is not a pattern constructor", node)
        raise self.fail("protocol", f"unexpected pattern node '{kind}'", node)

    def _instantiate_generic_type(
        self: _Elaborator, generic_vars: tuple[_Term, ...], type_args: list[_Term], target_type: _Term
    ) -> _Term:
        result = target_type
        for gv, arg in zip(generic_vars, type_args, strict=True):
            result = self.substitute(result, cast("int", gv.value), arg)
        return result

    def _instantiate_record_type(
        self: _Elaborator, record_info: _RecordInfo, type_args: list[_Term], target_type: _Term
    ) -> _Term:
        return self._instantiate_generic_type(record_info.generic_vars, type_args, target_type)

    def _instantiate_record_field_type(
        self: _Elaborator, record_info: _RecordInfo, type_args: list[_Term], field_idx: int, receiver_term: _Term
    ) -> _Term:
        ftype = self._instantiate_record_type(record_info, type_args, record_info.fields[field_idx].type)
        for j in range(field_idx):
            earlier_rf = record_info.fields[j]
            proj_term = _apps(_constant(earlier_rf.proj_const), *type_args, receiver_term)
            ftype = self.substitute(ftype, cast("int", earlier_rf.var.value), proj_term)
        return ftype

    def _expand_union_ctor(self: _Elaborator, term: _Term) -> _Term:
        head, args = self.spine(term)
        if head.kind != "const" or not isinstance(head.value, str) or head.value not in self.unions_by_ctor:
            return term
        union_info, ctor_info = self.unions_by_ctor[head.value]
        expected_val_arity = len(ctor_info.fields) if ctor_info.fields else 1
        if len(args) != len(union_info.generic_vars) + expected_val_arity:
            return term
        type_args = args[:len(union_info.generic_vars)]
        field_vals = args[len(union_info.generic_vars):]
        field_types = [
            self._instantiate_generic_type(union_info.generic_vars, type_args, rf.type)
            for rf in ctor_info.fields
        ]
        if not ctor_info.fields:
            payload_val = _term("unit")
        elif len(ctor_info.fields) == 1:
            if len(union_info.constructors) == 1:
                payload_val = _term("pair", field_types[0], _UNIT, field_vals[0], _term("unit"))
            else:
                payload_val = field_vals[0]
        elif ctor_info.is_dependent:
            payload_val = field_vals[-1]
            for k in range(len(field_vals) - 2, -1, -1):
                fv = field_vals[k]
                fvar_id = cast("int", ctor_info.fields[k].var.value)
                ftype = field_types[k]
                tail_type = self._instantiate_generic_type(
                    union_info.generic_vars, type_args, ctor_info.tail_sig_types[k + 1]
                )
                for j in range(k):
                    earlier_id = cast("int", ctor_info.fields[j].var.value)
                    ftype = self.substitute(ftype, earlier_id, field_vals[j])
                    tail_type = self.substitute(tail_type, earlier_id, field_vals[j])
                fam_lam = _term("lam", ftype, tail_type, value=fvar_id)
                payload_val = _term("existT", ftype, fam_lam, fv, payload_val)
        else:
            payload_val = field_vals[-1]
            acc_type = field_types[-1]
            for fv, ft in reversed(list(zip(field_vals[:-1], field_types[:-1], strict=True))):
                payload_val = _term("pair", ft, acc_type, fv, payload_val)
                acc_type = _term("prod", ft, acc_type)
        if len(union_info.constructors) == 1:
            return payload_val
        inst_payload_types = [
            self._instantiate_generic_type(union_info.generic_vars, type_args, c.payload_type)
            for c in union_info.constructors
        ]
        inst_suffix_types = [
            self._instantiate_generic_type(union_info.generic_vars, type_args, st)
            for st in union_info.suffix_types
        ]
        idx = ctor_info.index
        if idx < len(union_info.constructors) - 1:
            result = _term("inl", inst_payload_types[idx], inst_suffix_types[idx + 1], payload_val)
        else:
            result = payload_val
        for j in range(idx - 1, -1, -1):
            result = _term("inr", inst_payload_types[j], inst_suffix_types[j + 1], result)
        return result

    def _typecheck_pattern(
        self: _Elaborator,
        pat: _Pat,
        expected_type: _Term,
        environment: dict[str, _Binding],
        pattern_bindings: dict[str, _Binding] | None = None,
        *,
        smaller_roots: frozenset[int] = frozenset(),
        destruct_roots: frozenset[int] = frozenset(),
    ) -> _Term:
        self.tick()
        self.site = pat.node
        bound_var: _Term | None = None
        if pattern_bindings is not None:
            for name in pat.names:
                fresh_v = self.fresh(expected_type)
                for r_id in smaller_roots:
                    if r_id in self.smaller_vars:
                        self.smaller_vars[r_id].add(cast("int", fresh_v.value))
                pattern_bindings[name] = _Binding(fresh_v, expected_type)
                if bound_var is None:
                    bound_var = fresh_v
        if pat.kind == "wild":
            if bound_var is not None:
                return bound_var
            fresh_w = self.fresh(expected_type)
            for r_id in smaller_roots:
                if r_id in self.smaller_vars:
                    self.smaller_vars[r_id].add(cast("int", fresh_w.value))
            return fresh_w
        if pat.kind == "unit":
            self.unify(expected_type, _UNIT)
            return _term("unit")
        if pat.kind == "bool":
            self.unify(expected_type, _BOOL)
            return _term("bool", value=1 if pat.value else 0)
        if pat.kind == "char":
            self.unify(expected_type, _CHAR)
            return _term("char", value=cast("int", pat.value))
        if pat.kind == "string":
            raw_bytes = cast("str", pat.value).encode("latin1")
            str_term = _app(_constant("VNil"), _NAT)
            for index_b, b_val in enumerate(reversed(raw_bytes)):
                str_term = _apps(
                    _constant("VCons"),
                    _NAT,
                    _term("nat", value=index_b),
                    _term("nat", value=b_val),
                    str_term,
                )
            str_type = _apps(_constant("Vec"), _NAT, _term("nat", value=len(raw_bytes)))
            self.unify(expected_type, str_type)
            return str_term
        spec = self._int_spec(expected_type)
        if spec is not None and pat.kind in {"zero", "succ", "int_lit"}:
            if pat.node["kind"] != "nat_pattern":
                raise self.fail("type", "constructor 'Succ' requires a Nat scrutinee", pat.node)
            amount = _parse_numeric_magnitude(cast("str", pat.node["value"]))
            suffix = cast("str", pat.node["suffix"])
            if suffix:
                canonical = "u8" if suffix == "byte" else _NUMERICS_ALIASES.get(suffix, suffix)
                if canonical != spec.name:
                    raise self.fail(
                        "type",
                        f"integer pattern suffix '{suffix}' does not match scrutinee type '{spec.name}'",
                        pat.node,
                    )
            if not spec.min_val <= amount <= spec.max_val:
                raise self.fail(
                    "type",
                    f"integer pattern {amount} is out of range for '{spec.name}' ({spec.min_val}..{spec.max_val})",
                    pat.node,
                )
            return _int_term(spec, amount)
        if pat.kind == "int_lit":
            self.unify(expected_type, _NAT)
            _, suffix = cast("str", pat.value).split(":", 1)
            if suffix:
                raise self.fail(
                    "type",
                    f"integer pattern with suffix '{suffix}' requires type '{suffix}', not Nat",
                    pat.node,
                )
            raise self.fail(
                "limit",
                f"natural pattern literal exceeds structural bound ({MAX_PATTERN_NAT})",
                pat.node,
            )
        if pat.kind in {"zero", "succ"}:
            self.unify(expected_type, _NAT)
            if pat.kind == "zero":
                return _term("nat", value=0)
            pred_term = self._typecheck_pattern(
                pat.args[0],
                _NAT,
                environment,
                pattern_bindings,
                smaller_roots=smaller_roots | destruct_roots,
                destruct_roots=destruct_roots,
            )
            return _app(_constant("Succ"), pred_term)
        if pat.kind == "record":
            record_info = self.records[cast("str", pat.value)]
            type_args = [self.meta(self.types[cast("int", gv.value)], environment) for gv in record_info.generic_vars]
            expected_rec_type = _apps(_constant(record_info.type_const), *type_args)
            self.unify(expected_type, expected_rec_type)
            sub_terms: list[_Term] = []
            for idx, (sub_pat, rf) in enumerate(zip(pat.args, record_info.fields, strict=True)):
                ftype = self._instantiate_record_type(record_info, type_args, rf.type)
                for j in range(idx):
                    ftype = self.substitute(ftype, cast("int", record_info.fields[j].var.value), sub_terms[j])
                sub_terms.append(
                    self._typecheck_pattern(sub_pat, ftype, environment, pattern_bindings)
                )
            if not sub_terms:
                return _apps(_constant(record_info.ctor_const), *type_args, _term("unit"))
            return _apps(_constant(record_info.ctor_const), *type_args, *sub_terms)
        if pat.kind == "union":
            union_info, ctor_info = self.union_ctors[cast("str", pat.value)]
            type_args = [self.meta(self.types[cast("int", gv.value)], environment) for gv in union_info.generic_vars]
            expected_union_type = _apps(_constant(union_info.type_const), *type_args)
            self.unify(expected_type, expected_union_type)
            sub_terms = []
            for idx, (sub_pat, rf) in enumerate(zip(pat.args, ctor_info.fields, strict=True)):
                ftype = self._instantiate_generic_type(union_info.generic_vars, type_args, rf.type)
                for j in range(idx):
                    ftype = self.substitute(ftype, cast("int", ctor_info.fields[j].var.value), sub_terms[j])
                sub_terms.append(
                    self._typecheck_pattern(sub_pat, ftype, environment, pattern_bindings)
                )
            if not sub_terms:
                return _apps(_constant(ctor_info.ctor_const), *type_args, _term("unit"))
            return _apps(_constant(ctor_info.ctor_const), *type_args, *sub_terms)
        if pat.kind == "pair":
            resolved = self.whnf(expected_type)
            if resolved.kind == "meta":
                left_type = self.meta(_SORT, environment)
                right_type = self.meta(_SORT, environment)
                self.unify(resolved, _term("prod", left_type, right_type))
                resolved = self.whnf(expected_type)
            if resolved.kind != "prod":
                raise self.fail("type", "tuple pattern requires a product scrutinee", pat.node)
            left_t = self._typecheck_pattern(pat.args[0], resolved.args[0], environment, pattern_bindings)
            right_t = self._typecheck_pattern(pat.args[1], resolved.args[1], environment, pattern_bindings)
            return _term("pair", resolved.args[0], resolved.args[1], left_t, right_t)
        raise self.fail("protocol", f"unexpected internal pattern '{pat.kind}'", pat.node)

    def _require_irrefutable(self: _Elaborator, pat: _Pat) -> None:
        if pat.kind in {"bool", "zero", "succ", "int_lit", "char", "string", "union"}:
            raise self.fail("type", "local pattern binding requires an irrefutable pattern; use match", pat.node)
        for child in pat.args:
            self._require_irrefutable(child)

    def _bind_irrefutable(self: _Elaborator, pat: _Pat, current: _Binding, extended: dict[str, _Binding]) -> None:
        self.site = pat.node
        for name in pat.names:
            self.bind_local(extended, name, current)
        if pat.kind == "record":
            rec_type = self.whnf(current.type)
            _, type_args = self.spine(rec_type)
            record_info = self.records[cast("str", pat.value)]
            for idx, (sub_pat, rf) in enumerate(zip(pat.args, record_info.fields, strict=True)):
                ftype = self._instantiate_record_field_type(record_info, type_args, idx, current.term)
                fterm = _apps(_constant(rf.proj_const), *type_args, current.term)
                self._bind_irrefutable(sub_pat, _Binding(fterm, ftype), extended)
        elif pat.kind == "pair":
            prod_type = self.whnf(current.type)
            left_type, right_type = prod_type.args
            left_term = _apps(_constant("Fst"), left_type, right_type, current.term)
            right_term = _apps(_constant("Snd"), left_type, right_type, current.term)
            self._bind_irrefutable(pat.args[0], _Binding(left_term, left_type), extended)
            self._bind_irrefutable(pat.args[1], _Binding(right_term, right_type), extended)

    def _collect_pat_names(self: _Elaborator, pat: _Pat, out: set[str]) -> None:
        for name in pat.names:
            out.add(name)
        for child in pat.args:
            self._collect_pat_names(child, out)

    def local(self: _Elaborator, node: Node, environment: dict[str, _Binding]) -> dict[str, _Binding]:
        self.site = node
        if node["kind"] in {"let_pattern", "var_pattern"}:
            binding = self.expression(self.node(node["value"]), environment)
            pat = self._parse_pattern(self.node(node["pattern"]), set())
            self._require_irrefutable(pat)
            self._typecheck_pattern(pat, binding.type, environment)
            extended = dict(environment)
            self._bind_irrefutable(pat, binding, extended)
            bound_names: set[str] = set()
            self._collect_pat_names(pat, bound_names)
            for bname in bound_names:
                if bname in self.frozen_collections:
                    raise self.fail("type", f"cannot rebind collection '{bname}' while iterating over it", node)
                if node["kind"] == "var_pattern":
                    self.mutable_locals.add(bname)
                else:
                    self.mutable_locals.discard(bname)
            return extended
        if node["kind"] == "constant_local":
            binding = self.constant_value(node, environment)
        elif node["kind"] not in {"let", "typed_local", "var"}:
            raise self.fail("unsupported", "only local let/var name bindings are supported")
        else:
            self.no_roles(node, "grade")
            if node["type"] is None:
                binding = self.expression(self.node(node["value"]), environment)
            else:
                value_type = self.type(self.node(node["type"]), environment)
                binding = _Binding(self.check(self.node(node["value"]), value_type, environment), value_type)
        extended = dict(environment)
        bname = self.name(node["name"])
        if bname in self.frozen_collections:
            raise self.fail("type", f"cannot rebind collection '{bname}' while iterating over it", node)
        if node["kind"] == "var":
            self.mutable_locals.add(bname)
        else:
            self.mutable_locals.discard(bname)
        self.bind_local(extended, bname, binding)
        return extended

    def match(self: _Elaborator, node: Node, environment: dict[str, _Binding], expected: _Term | None = None,
              *, expression_arms: bool = True, facts: tuple[_Binding, ...] = (),
              refine_scrutinee: bool = False, expected_scrutinee_type: _Term | None = None,
              visited_arms: set[int] | None = None, synthetic: bool = False) -> _Binding:
        self.site = node
        value_node = self.node(node["value"])
        if expected_scrutinee_type is not None:
            scrutinee = _Binding(self.check(value_node, expected_scrutinee_type, environment), expected_scrutinee_type)
        else:
            scrutinee = self.expression(value_node, environment)
        root_var = self.fresh(scrutinee.type)
        root_var_id = cast("int", root_var.value)
        motive_node = node["motive"]
        motive_body: _Term | None = None
        if motive_node is not None:
            motive = self.node(motive_node, "match_motive")
            motive_env = dict(environment)
            self.bind_local(motive_env, self.name(motive["name"]), _Binding(root_var, scrutinee.type))
            motive_body = self.type(self.node(motive["type"]), motive_env)
            match_type = self.substitute(motive_body, root_var_id, scrutinee.term)
            if expected is not None:
                self.unify(match_type, expected)
        elif (expected is not None and scrutinee.term.kind == "var"
              and cast("int", scrutinee.term.value) in self.free(expected)):
            motive_body = self.substitute(expected, cast("int", scrutinee.term.value), root_var)
        if expected is not None and self._is_prop_type(expected):
            refine_scrutinee = True
        scrut_smaller_roots: frozenset[int] = frozenset[int]()
        scrut_destruct_roots: frozenset[int] = frozenset[int]()
        if scrutinee.term.kind == "var":
            scrut_var_id_0 = cast("int", scrutinee.term.value)
            scrut_smaller_roots = frozenset(
                [r_id for r_id, s_set in self.smaller_vars.items() if scrut_var_id_0 in s_set]
            )
            scrut_destruct_roots = frozenset(
                [
                    r_id
                    for r_id, s_set in self.smaller_vars.items()
                    if scrut_var_id_0 == r_id or scrut_var_id_0 in s_set
                ]
            )
        cases = self.nodes(node["cases"])
        rows: list[_Row] = []
        arm_pattern_bindings: list[dict[str, _Binding]] = []
        for arm_index, arm in enumerate(cases):
            self.node(arm, "expression_case" if expression_arms else "case")
            pat = self._parse_pattern(self.node(arm["pattern"]), set())
            bindings_for_arm: dict[str, _Binding] = {}
            self._typecheck_pattern(
                pat,
                scrutinee.type,
                environment,
                bindings_for_arm,
                smaller_roots=scrut_smaller_roots,
                destruct_roots=scrut_destruct_roots,
            )
            arm_pattern_bindings.append(bindings_for_arm)
            rows.append(_Row((pat,), (), arm, arm_index))
        scrutinee_type = self.whnf(scrutinee.type)
        scrutinee_head, scrutinee_targs = self.spine(scrutinee_type)
        if (scrutinee_type not in {_UNIT, _BOOL, _NAT, _CHAR}
                and self._int_spec(scrutinee_type) is None
                and scrutinee_type.kind != "prod"
                and not (
                    scrutinee_head == _constant("Vec")
                    and len(scrutinee_targs) == 2
                    and self.whnf(scrutinee_targs[0]) == _NAT
                )
                and not (
                    scrutinee_head.kind == "const"
                    and (scrutinee_head.value in self.records_by_type or scrutinee_head.value in self.unions_by_type)
                )):
            raise self.fail(
                "type",
                "match scrutinee must have type Nat, bool, char, Unit, a fixed-width integer, a product, a record or a union",
                value_node,
            )
        inferred_result: list[_Term | None] = [expected]
        local_visited: set[int] = set()

        def subst_cols(
            cols: list[tuple[_Term, _Term, _Term]], var_id: int, replacement: _Term
        ) -> list[tuple[_Term, _Term, _Term]]:
            return [(cv, cs, self.substitute(ct, var_id, replacement)) for cv, cs, ct in cols]

        def specialize_rows(active_rows: list[_Row], index: int, ctor_kind: str, ctor_term: _Term,
                            col_var_id: int, col_type: _Term, sub_count: int, *,
                            bool_value: bool = False, ctor_name: str = "") -> list[_Row]:
            specialized: list[_Row] = []
            for row in active_rows:
                pat = row.patterns[index]
                updated_bindings = tuple(
                    (
                        bname,
                        _Binding(
                            self.substitute(bval.term, col_var_id, ctor_term),
                            self.substitute(bval.type, col_var_id, ctor_term),
                        ),
                    )
                    for bname, bval in row.bindings
                )
                if pat.kind == "wild":
                    extra = tuple((name, _Binding(ctor_term, col_type)) for name in pat.names)
                    wilds = tuple(_Pat("wild", pat.node) for _ in range(sub_count))
                    specialized.append(_Row(
                        row.patterns[:index] + wilds + row.patterns[index + 1:],
                        updated_bindings + extra,
                        row.arm,
                        row.arm_index,
                    ))
                elif (
                    pat.kind == ctor_kind
                    and (ctor_kind != "bool" or pat.value == bool_value)
                    and (ctor_kind != "union" or pat.value == ctor_name)
                ):
                    specialized.append(_Row(
                        row.patterns[:index] + pat.args + row.patterns[index + 1:],
                        updated_bindings,
                        row.arm,
                        row.arm_index,
                    ))
            return specialized

        def compile_matrix(columns: list[tuple[_Term, _Term, _Term]], active_rows: list[_Row],
                           pattern_term: _Term) -> _Term:
            self.tick()
            if not active_rows:
                raise self.fail("type", "non-exhaustive match: missing pattern case", node)
            first = active_rows[0]
            if all(pat.kind == "wild" for pat in first.patterns):
                local_visited.add(first.arm_index)
                if visited_arms is not None:
                    visited_arms.add(first.arm_index)
                arm_env = dict(environment)
                leaf_pattern = pattern_term
                for col_var, col_scrutinee, _ in columns:
                    if col_var != col_scrutinee:
                        leaf_pattern = self.substitute(leaf_pattern, cast("int", col_var.value), col_scrutinee)
                arm_facts = facts
                if refine_scrutinee:
                    for env_name, env_binding in list(arm_env.items()):
                        if env_binding.term == scrutinee.term:
                            arm_env[env_name] = _Binding(
                                leaf_pattern,
                                scrutinee.type,
                                env_binding.generics,
                                env_binding.constant,
                            )
                        elif scrutinee.term.kind == "var" and cast("int", scrutinee.term.value) in self.free(env_binding.type):
                            arm_env[env_name] = _Binding(
                                env_binding.term,
                                self.substitute(env_binding.type, cast("int", scrutinee.term.value), leaf_pattern),
                                env_binding.generics,
                                env_binding.constant,
                            )
                    if scrutinee.term.kind == "var":
                        scrut_id = cast("int", scrutinee.term.value)
                        arm_facts = tuple(
                            _Binding(
                                f.term,
                                self.substitute(f.type, scrut_id, leaf_pattern),
                                f.generics,
                                f.constant,
                            )
                            for f in facts
                        )
                for name, bound in first.bindings:
                    bound_term = bound.term
                    bound_type = bound.type
                    for col_var, col_scrutinee, _ in columns:
                        if col_var != col_scrutinee:
                            bound_term = self.substitute(bound_term, cast("int", col_var.value), col_scrutinee)
                            bound_type = self.substitute(bound_type, cast("int", col_var.value), col_scrutinee)
                    self.bind_local(arm_env, name, _Binding(bound_term, bound_type))
                for pat, (_, col_scrutinee, col_type) in zip(first.patterns, columns, strict=True):
                    for name in pat.names:
                        self.bind_local(arm_env, name, _Binding(col_scrutinee, col_type))
                arm = first.arm
                self.site = arm
                leaf_expected = (self.substitute(motive_body, root_var_id, leaf_pattern)
                                 if motive_body is not None else inferred_result[0])
                if expression_arms:
                    value_node = self.node(arm["value"])
                    if leaf_expected is None:
                        evaluated = self.expression(value_node, arm_env)
                        inferred_result[0] = evaluated.type
                        return evaluated.term
                    return self.check(value_node, leaf_expected, arm_env)
                block_node = {"kind": "block", "span": arm["span"], "statements": arm["statements"]}
                evaluated = self.block(block_node, arm_env, leaf_expected, facts=arm_facts)
                if motive_body is None and inferred_result[0] is None:
                    inferred_result[0] = evaluated.type
                return evaluated.term

            index = next(i for i, pat in enumerate(first.patterns) if pat.kind != "wild")
            col_var, col_scrutinee, col_type = columns[index]
            col_var_id = cast("int", col_var.value)
            col_type = self.whnf(col_type)
            without_index = columns[:index] + columns[index + 1:]

            if first.patterns[index].kind == "string":
                target_pat = first.patterns[index]
                target_str = cast("str", target_pat.value)
                raw_bytes = target_str.encode("latin1")
                lit_term = _app(_constant("VNil"), _NAT)
                for index_b, b_val in enumerate(reversed(raw_bytes)):
                    lit_term = _apps(
                        _constant("VCons"),
                        _NAT,
                        _term("nat", value=index_b),
                        _term("nat", value=b_val),
                        lit_term,
                    )
                str_vec_type = _apps(_constant("Vec"), _NAT, _term("nat", value=len(raw_bytes)))
                yes_rows_s: list[_Row] = []
                no_rows_s: list[_Row] = []
                for row in active_rows:
                    pat = row.patterns[index]
                    updated_bindings = tuple(
                        (
                            bname,
                            _Binding(
                                self.substitute(bval.term, col_var_id, lit_term),
                                self.substitute(bval.type, col_var_id, lit_term),
                            ),
                        )
                        for bname, bval in row.bindings
                    )
                    if pat.kind == "wild":
                        extra = tuple((name, _Binding(lit_term, col_type)) for name in pat.names)
                        yes_rows_s.append(
                            _Row(
                                row.patterns[:index] + row.patterns[index + 1:],
                                updated_bindings + extra,
                                row.arm,
                                row.arm_index,
                            )
                        )
                        no_rows_s.append(row)
                    elif pat.kind == "string" and pat.value == target_str:
                        yes_rows_s.append(
                            _Row(
                                row.patterns[:index] + row.patterns[index + 1:],
                                updated_bindings,
                                row.arm,
                                row.arm_index,
                            )
                        )
                    else:
                        no_rows_s.append(row)
                eq_cond = self._structural_eq_bool(str_vec_type, col_scrutinee, lit_term, node)
                ne_cond = _app(_constant("!"), eq_cond)
                self.active_facts.append(eq_cond)
                try:
                    yes_branch = compile_matrix(
                        subst_cols(without_index, col_var_id, lit_term),
                        yes_rows_s,
                        self.substitute(pattern_term, col_var_id, lit_term),
                    )
                finally:
                    self.active_facts.pop()
                self.active_facts.append(ne_cond)
                try:
                    no_branch = compile_matrix(columns, no_rows_s, pattern_term)
                finally:
                    self.active_facts.pop()
                ret_ty = (
                    self.substitute(motive_body, root_var_id, pattern_term)
                    if motive_body is not None
                    else cast("_Term", inferred_result[0])
                )
                return _term("if", ret_ty, eq_cond, yes_branch, no_branch)

            if col_type == _CHAR:
                target_pat = first.patterns[index]
                target_cp = cast("int", target_pat.value)
                lit_term = _term("char", value=target_cp)
                yes_rows_c: list[_Row] = []
                no_rows_c: list[_Row] = []
                for row in active_rows:
                    pat = row.patterns[index]
                    updated_bindings = tuple(
                        (
                            bname,
                            _Binding(
                                self.substitute(bval.term, col_var_id, lit_term),
                                self.substitute(bval.type, col_var_id, lit_term),
                            ),
                        )
                        for bname, bval in row.bindings
                    )
                    if pat.kind == "wild":
                        extra = tuple((name, _Binding(lit_term, col_type)) for name in pat.names)
                        yes_rows_c.append(
                            _Row(
                                row.patterns[:index] + row.patterns[index + 1:],
                                updated_bindings + extra,
                                row.arm,
                                row.arm_index,
                            )
                        )
                        no_rows_c.append(row)
                    elif pat.kind == "char" and pat.value == target_cp:
                        yes_rows_c.append(
                            _Row(
                                row.patterns[:index] + row.patterns[index + 1:],
                                updated_bindings,
                                row.arm,
                                row.arm_index,
                            )
                        )
                    else:
                        no_rows_c.append(row)
                eq_cond = _apps(_constant("char_eq"), col_scrutinee, lit_term)
                ne_cond = _apps(_constant("char_ne"), col_scrutinee, lit_term)
                self.active_facts.append(eq_cond)
                try:
                    yes_branch = compile_matrix(
                        subst_cols(without_index, col_var_id, lit_term),
                        yes_rows_c,
                        self.substitute(pattern_term, col_var_id, lit_term),
                    )
                finally:
                    self.active_facts.pop()
                self.active_facts.append(ne_cond)
                try:
                    no_branch = compile_matrix(columns, no_rows_c, pattern_term)
                finally:
                    self.active_facts.pop()
                ret_ty = (
                    self.substitute(motive_body, root_var_id, pattern_term)
                    if motive_body is not None
                    else cast("_Term", inferred_result[0])
                )
                return _term("if", ret_ty, eq_cond, yes_branch, no_branch)

            if col_type == _UNIT:
                unit_term = _term("unit")
                body = compile_matrix(
                    subst_cols(without_index, col_var_id, unit_term),
                    specialize_rows(active_rows, index, "unit", unit_term, col_var_id, _UNIT, 0),
                    self.substitute(pattern_term, col_var_id, unit_term),
                )
                if motive_body is None:
                    return body
                motive_lam = _term("lam", _UNIT, self.substitute(motive_body, root_var_id, pattern_term), value=col_var_id)
                return _term("unit_match", motive_lam, col_scrutinee, body)

            if col_type == _BOOL:
                true_term = _term("bool", value=1)
                false_term = _term("bool", value=0)
                self.active_facts.append(col_scrutinee)
                try:
                    yes = compile_matrix(
                        subst_cols(without_index, col_var_id, true_term),
                        specialize_rows(active_rows, index, "bool", true_term, col_var_id, _BOOL, 0, bool_value=True),
                        self.substitute(pattern_term, col_var_id, true_term),
                    )
                finally:
                    self.active_facts.pop()
                self.active_facts.append(_app(_constant("!"), col_scrutinee))
                try:
                    no = compile_matrix(
                        subst_cols(without_index, col_var_id, false_term),
                        specialize_rows(active_rows, index, "bool", false_term, col_var_id, _BOOL, 0, bool_value=False),
                        self.substitute(pattern_term, col_var_id, false_term),
                    )
                finally:
                    self.active_facts.pop()
                if motive_body is None:
                    return _term("if", cast("_Term", inferred_result[0]), col_scrutinee, yes, no)
                motive_lam = _term("lam", _BOOL, self.substitute(motive_body, root_var_id, pattern_term), value=col_var_id)
                return _term("bool_match", motive_lam, col_scrutinee, yes, no)

            col_int_spec = self._int_spec(col_type)
            if col_int_spec is not None:
                target_pat = first.patterns[index]
                target_val = _parse_numeric_magnitude(cast("str", target_pat.node["value"]))
                lit_term = _int_term(col_int_spec, target_val)
                yes_rows: list[_Row] = []
                no_rows: list[_Row] = []
                for row in active_rows:
                    pat = row.patterns[index]
                    updated_bindings = tuple(
                        (
                            bname,
                            _Binding(
                                self.substitute(bval.term, col_var_id, lit_term),
                                self.substitute(bval.type, col_var_id, lit_term),
                            ),
                        )
                        for bname, bval in row.bindings
                    )
                    if pat.kind == "wild":
                        extra = tuple((name, _Binding(lit_term, col_type)) for name in pat.names)
                        yes_rows.append(
                            _Row(
                                row.patterns[:index] + row.patterns[index + 1:],
                                updated_bindings + extra,
                                row.arm,
                                row.arm_index,
                            )
                        )
                        no_rows.append(row)
                    else:
                        row_val = _parse_numeric_magnitude(cast("str", pat.node["value"]))
                        if row_val == target_val:
                            yes_rows.append(
                                _Row(
                                    row.patterns[:index] + row.patterns[index + 1:],
                                    updated_bindings,
                                    row.arm,
                                    row.arm_index,
                                )
                            )
                        else:
                            no_rows.append(row)
                eq_cond = _apps(_constant(f"int_eq_{col_int_spec.name}"), col_scrutinee, lit_term)
                ne_cond = _apps(_constant(f"int_ne_{col_int_spec.name}"), col_scrutinee, lit_term)
                self.active_facts.append(eq_cond)
                try:
                    yes_branch = compile_matrix(
                        subst_cols(without_index, col_var_id, lit_term),
                        yes_rows,
                        self.substitute(pattern_term, col_var_id, lit_term),
                    )
                finally:
                    self.active_facts.pop()
                self.active_facts.append(ne_cond)
                try:
                    no_branch = compile_matrix(columns, no_rows, pattern_term)
                finally:
                    self.active_facts.pop()
                ret_ty = (
                    self.substitute(motive_body, root_var_id, pattern_term)
                    if motive_body is not None
                    else cast("_Term", inferred_result[0])
                )
                return _term("if", ret_ty, eq_cond, yes_branch, no_branch)

            if col_type.kind == "prod":
                left_type, right_type = col_type.args
                left_var = self.fresh(left_type)
                right_var = self.fresh(right_type)
                pair_term = _term("pair", left_type, right_type, left_var, right_var)
                sub_columns = [(left_var, left_var, left_type), (right_var, right_var, right_type)]
                body = compile_matrix(
                    subst_cols(columns[:index], col_var_id, pair_term)
                    + sub_columns
                    + subst_cols(columns[index + 1:], col_var_id, pair_term),
                    specialize_rows(active_rows, index, "pair", pair_term, col_var_id, col_type, 2),
                    self.substitute(pattern_term, col_var_id, pair_term),
                )
                motive_return = (self.substitute(motive_body, root_var_id, pattern_term)
                                 if motive_body is not None else cast("_Term", inferred_result[0]))
                motive_lam = _term("lam", col_type, motive_return, value=col_var_id)
                branch_lam = _term("lam", left_type, _term("lam", right_type, body, value=right_var.value), value=left_var.value)
                return _term("pair_match", motive_lam, col_scrutinee, branch_lam)

            col_head, col_type_args = self.spine(col_type)
            if col_head.kind == "const" and isinstance(col_head.value, str) and col_head.value in self.records_by_type:
                record_info = self.records_by_type[col_head.value]
                if not record_info.fields:
                    ctor_term = _apps(_constant(record_info.ctor_const), *col_type_args, _term("unit"))
                    body = compile_matrix(
                        subst_cols(without_index, col_var_id, ctor_term),
                        specialize_rows(active_rows, index, "record", ctor_term, col_var_id, col_type, 0),
                        self.substitute(pattern_term, col_var_id, ctor_term),
                    )
                    if motive_body is None:
                        return body
                    motive_lam = _term(
                        "lam", col_type, self.substitute(motive_body, root_var_id, pattern_term), value=col_var_id
                    )
                    return _term("unit_match", motive_lam, col_scrutinee, body)
                if len(record_info.fields) == 1:
                    ft_0 = self._instantiate_record_type(record_info, col_type_args, record_info.fields[0].type)
                    fvar_0 = self.fresh(ft_0)
                    dummy_unit_var = self.fresh(_UNIT)
                    ctor_term = _apps(_constant(record_info.ctor_const), *col_type_args, fvar_0)
                    sub_columns = [(fvar_0, fvar_0, ft_0)]
                    body = compile_matrix(
                        subst_cols(columns[:index], col_var_id, ctor_term)
                        + sub_columns
                        + subst_cols(columns[index + 1:], col_var_id, ctor_term),
                        specialize_rows(active_rows, index, "record", ctor_term, col_var_id, col_type, 1),
                        self.substitute(pattern_term, col_var_id, ctor_term),
                    )
                    motive_return = (
                        self.substitute(motive_body, root_var_id, pattern_term)
                        if motive_body is not None
                        else cast("_Term", inferred_result[0])
                    )
                    motive_lam = _term("lam", col_type, motive_return, value=col_var_id)
                    branch_lam = _term(
                        "lam",
                        ft_0,
                        _term("lam", _UNIT, body, value=dummy_unit_var.value),
                        value=fvar_0.value,
                    )
                    return _term("pair_match", motive_lam, col_scrutinee, branch_lam)
                field_types: list[_Term] = []
                field_vars: list[_Term] = []
                for idx_f, rf in enumerate(record_info.fields):
                    ft = self._instantiate_record_type(record_info, col_type_args, rf.type)
                    for j in range(idx_f):
                        ft = self.substitute(ft, cast("int", record_info.fields[j].var.value), field_vars[j])
                    fv = self.fresh(ft)
                    field_types.append(ft)
                    field_vars.append(fv)
                ctor_term = _apps(_constant(record_info.ctor_const), *col_type_args, *field_vars)
                sub_columns = [(fv, fv, ft) for fv, ft in zip(field_vars, field_types, strict=True)]
                body = compile_matrix(
                    subst_cols(columns[:index], col_var_id, ctor_term)
                    + sub_columns
                    + subst_cols(columns[index + 1:], col_var_id, ctor_term),
                    specialize_rows(active_rows, index, "record", ctor_term, col_var_id, col_type, len(field_vars)),
                    self.substitute(pattern_term, col_var_id, ctor_term),
                )
                if record_info.is_dependent:
                    tail_types: list[_Term] = []
                    for k in range(len(field_types) - 1):
                        tt = self._instantiate_record_type(
                            record_info, col_type_args, record_info.tail_sig_types[k + 1]
                        )
                        for j in range(k + 1):
                            tt = self.substitute(tt, cast("int", record_info.fields[j].var.value), field_vars[j])
                        tail_types.append(tt)
                else:
                    tail_types = [field_types[-1]]
                    for ft in reversed(field_types[1:-1]):
                        tail_types.append(_term("prod", ft, tail_types[-1]))
                    tail_types.reverse()
                tail_vars: list[_Term] = [
                    self.fresh(tail_types[k]) for k in range(len(field_types) - 2)
                ] + [field_vars[-1]]
                curr_body = body
                for k in range(len(field_types) - 2, -1, -1):
                    left_var = field_vars[k]
                    left_type = field_types[k]
                    right_var = tail_vars[k]
                    right_type = tail_types[k]
                    if k == 0:
                        scrut = col_scrutinee
                        scrut_var_id = col_var_id
                        scrut_type = col_type
                        motive_return = (
                            self.substitute(motive_body, root_var_id, pattern_term)
                            if motive_body is not None
                            else cast("_Term", inferred_result[0])
                        )
                    else:
                        scrut = tail_vars[k - 1]
                        scrut_var_id = cast("int", scrut.value)
                        scrut_type = tail_types[k - 1]
                        motive_return = cast("_Term", inferred_result[0])
                    if record_info.is_dependent and cast("int", left_var.value) in self.free(motive_return):
                        fam_lam = _term("lam", left_type, right_type, value=left_var.value)
                        proj1_var = _term("projT1", left_type, fam_lam, _term("var", value=scrut_var_id))
                        motive_return = self.substitute(motive_return, cast("int", left_var.value), proj1_var)
                        if motive_body is None and inferred_result[0] is not None:
                            inferred_result[0] = self.substitute(motive_return, scrut_var_id, scrut)
                    motive_lam = _term("lam", scrut_type, motive_return, value=scrut_var_id)
                    branch_lam = _term(
                        "lam",
                        left_type,
                        _term("lam", right_type, curr_body, value=right_var.value),
                        value=left_var.value,
                    )
                    match_kind = "sigT_match" if record_info.is_dependent else "pair_match"
                    curr_body = _term(match_kind, motive_lam, scrut, branch_lam)
                return curr_body

            if col_head.kind == "const" and isinstance(col_head.value, str) and col_head.value in self.unions_by_type:
                union_info = self.unions_by_type[col_head.value]
                if len(union_info.constructors) == 1:
                    ctor_info = union_info.constructors[0]
                    if not ctor_info.fields:
                        ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, _term("unit"))
                        body = compile_matrix(
                            subst_cols(without_index, col_var_id, ctor_term),
                            specialize_rows(
                                active_rows, index, "union", ctor_term, col_var_id, col_type, 0, ctor_name=ctor_info.name
                            ),
                            self.substitute(pattern_term, col_var_id, ctor_term),
                        )
                        if motive_body is None:
                            return body
                        motive_lam = _term(
                            "lam", col_type, self.substitute(motive_body, root_var_id, pattern_term), value=col_var_id
                        )
                        return _term("unit_match", motive_lam, col_scrutinee, body)
                    if len(ctor_info.fields) == 1:
                        ft_0 = self._instantiate_generic_type(
                            union_info.generic_vars, col_type_args, ctor_info.fields[0].type
                        )
                        fvar_0 = self.fresh(ft_0)
                        dummy_unit_var = self.fresh(_UNIT)
                        ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, fvar_0)
                        sub_columns = [(fvar_0, fvar_0, ft_0)]
                        body = compile_matrix(
                            subst_cols(columns[:index], col_var_id, ctor_term)
                            + sub_columns
                            + subst_cols(columns[index + 1:], col_var_id, ctor_term),
                            specialize_rows(
                                active_rows, index, "union", ctor_term, col_var_id, col_type, 1, ctor_name=ctor_info.name
                            ),
                            self.substitute(pattern_term, col_var_id, ctor_term),
                        )
                        if motive_body is not None:
                            unit_motive_ret = self.substitute(
                                motive_body,
                                root_var_id,
                                self.substitute(
                                    pattern_term,
                                    col_var_id,
                                    _term("pair", ft_0, _UNIT, fvar_0, dummy_unit_var),
                                ),
                            )
                            body = _term(
                                "unit_match",
                                _term("lam", _UNIT, unit_motive_ret, value=dummy_unit_var.value),
                                dummy_unit_var,
                                body,
                            )
                        motive_return = (
                            self.substitute(motive_body, root_var_id, pattern_term)
                            if motive_body is not None
                            else cast("_Term", inferred_result[0])
                        )
                        motive_lam = _term("lam", col_type, motive_return, value=col_var_id)
                        branch_lam = _term(
                            "lam",
                            ft_0,
                            _term("lam", _UNIT, body, value=dummy_unit_var.value),
                            value=fvar_0.value,
                        )
                        return _term("pair_match", motive_lam, col_scrutinee, branch_lam)
                    field_types = []
                    field_vars = []
                    for idx_f, rf in enumerate(ctor_info.fields):
                        ft = self._instantiate_generic_type(union_info.generic_vars, col_type_args, rf.type)
                        for j in range(idx_f):
                            ft = self.substitute(ft, cast("int", ctor_info.fields[j].var.value), field_vars[j])
                        fv = self.fresh(ft)
                        field_types.append(ft)
                        field_vars.append(fv)
                    ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, *field_vars)
                    sub_columns = [(fv, fv, ft) for fv, ft in zip(field_vars, field_types, strict=True)]
                    body = compile_matrix(
                        subst_cols(columns[:index], col_var_id, ctor_term)
                        + sub_columns
                        + subst_cols(columns[index + 1:], col_var_id, ctor_term),
                        specialize_rows(
                            active_rows,
                            index,
                            "union",
                            ctor_term,
                            col_var_id,
                            col_type,
                            len(field_vars),
                            ctor_name=ctor_info.name,
                        ),
                        self.substitute(pattern_term, col_var_id, ctor_term),
                    )
                    if ctor_info.is_dependent:
                        tail_types = []
                        for k in range(len(field_types) - 1):
                            tt = self._instantiate_generic_type(
                                union_info.generic_vars, col_type_args, ctor_info.tail_sig_types[k + 1]
                            )
                            for j in range(k + 1):
                                tt = self.substitute(tt, cast("int", ctor_info.fields[j].var.value), field_vars[j])
                            tail_types.append(tt)
                    else:
                        tail_types = [field_types[-1]]
                        for ft in reversed(field_types[1:-1]):
                            tail_types.append(_term("prod", ft, tail_types[-1]))
                        tail_types.reverse()
                    tail_vars = [
                        self.fresh(tail_types[k]) for k in range(len(field_types) - 2)
                    ] + [field_vars[-1]]
                    curr_body = body
                    for k in range(len(field_types) - 2, -1, -1):
                        left_var = field_vars[k]
                        left_type = field_types[k]
                        right_var = tail_vars[k]
                        right_type = tail_types[k]
                        if k == 0:
                            scrut = col_scrutinee
                            scrut_var_id = col_var_id
                            scrut_type = col_type
                            motive_return = (
                                self.substitute(motive_body, root_var_id, pattern_term)
                                if motive_body is not None
                                else cast("_Term", inferred_result[0])
                            )
                        else:
                            scrut = tail_vars[k - 1]
                            scrut_var_id = cast("int", scrut.value)
                            scrut_type = tail_types[k - 1]
                            if motive_body is not None and not ctor_info.is_dependent:
                                partial = scrut
                                p_type = scrut_type
                                for j in range(k - 1, -1, -1):
                                    partial = _term("pair", field_types[j], p_type, field_vars[j], partial)
                                    p_type = _term("prod", field_types[j], p_type)
                                motive_return = self.substitute(
                                    motive_body,
                                    root_var_id,
                                    self.substitute(pattern_term, col_var_id, partial),
                                )
                            else:
                                motive_return = cast("_Term", inferred_result[0])
                        if ctor_info.is_dependent and cast("int", left_var.value) in self.free(motive_return):
                            fam_lam = _term("lam", left_type, right_type, value=left_var.value)
                            proj1_var = _term("projT1", left_type, fam_lam, _term("var", value=scrut_var_id))
                            motive_return = self.substitute(motive_return, cast("int", left_var.value), proj1_var)
                            if motive_body is None and inferred_result[0] is not None:
                                inferred_result[0] = self.substitute(motive_return, scrut_var_id, scrut)
                        motive_lam = _term("lam", scrut_type, motive_return, value=scrut_var_id)
                        branch_lam = _term(
                            "lam",
                            left_type,
                            _term("lam", right_type, curr_body, value=right_var.value),
                            value=left_var.value,
                        )
                        match_kind = "sigT_match" if ctor_info.is_dependent else "pair_match"
                        curr_body = _term(match_kind, motive_lam, scrut, branch_lam)
                    return curr_body

                inst_payload_types = [
                    self._instantiate_generic_type(union_info.generic_vars, col_type_args, c.payload_type)
                    for c in union_info.constructors
                ]
                inst_suffix_types = [
                    self._instantiate_generic_type(union_info.generic_vars, col_type_args, st)
                    for st in union_info.suffix_types
                ]
                num_ctors = len(union_info.constructors)

                def suffix_inj(from_idx: int, inner_term: _Term) -> _Term:
                    acc = inner_term
                    for j in range(from_idx - 1, -1, -1):
                        acc = _term("inr", inst_payload_types[j], inst_suffix_types[j + 1], acc)
                    return acc

                def ctor_inj(ctor_idx: int, payload_term: _Term) -> _Term:
                    base = (
                        _term("inl", inst_payload_types[ctor_idx], inst_suffix_types[ctor_idx + 1], payload_term)
                        if ctor_idx < num_ctors - 1
                        else payload_term
                    )
                    return suffix_inj(ctor_idx, base)

                payload_vars: list[_Term] = []
                payload_branches: list[_Term] = []
                for ctor_idx, ctor_info in enumerate(union_info.constructors):
                    if not ctor_info.fields:
                        pvar = self.fresh(_UNIT)
                        ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, _term("unit"))
                        leaf_body = compile_matrix(
                            subst_cols(without_index, col_var_id, ctor_term),
                            specialize_rows(
                                active_rows, index, "union", ctor_term, col_var_id, col_type, 0, ctor_name=ctor_info.name
                            ),
                            self.substitute(pattern_term, col_var_id, ctor_term),
                        )
                        if motive_body is None:
                            pbranch = leaf_body
                        else:
                            motive_ret = self.substitute(
                                motive_body,
                                root_var_id,
                                self.substitute(pattern_term, col_var_id, ctor_inj(ctor_idx, pvar)),
                            )
                            pbranch = _term(
                                "unit_match",
                                _term("lam", _UNIT, motive_ret, value=pvar.value),
                                pvar,
                                leaf_body,
                            )
                        payload_vars.append(pvar)
                        payload_branches.append(pbranch)
                    elif len(ctor_info.fields) == 1:
                        ft_0 = self._instantiate_generic_type(
                            union_info.generic_vars, col_type_args, ctor_info.fields[0].type
                        )
                        pvar = self.fresh(ft_0)
                        ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, pvar)
                        sub_columns = [(pvar, pvar, ft_0)]
                        pbranch = compile_matrix(
                            subst_cols(columns[:index], col_var_id, ctor_term)
                            + sub_columns
                            + subst_cols(columns[index + 1:], col_var_id, ctor_term),
                            specialize_rows(
                                active_rows, index, "union", ctor_term, col_var_id, col_type, 1, ctor_name=ctor_info.name
                            ),
                            self.substitute(pattern_term, col_var_id, ctor_term),
                        )
                        payload_vars.append(pvar)
                        payload_branches.append(pbranch)
                    else:
                        pvar = self.fresh(inst_payload_types[ctor_idx])
                        field_types = []
                        field_vars = []
                        for idx_f, rf in enumerate(ctor_info.fields):
                            ft = self._instantiate_generic_type(union_info.generic_vars, col_type_args, rf.type)
                            for j in range(idx_f):
                                ft = self.substitute(ft, cast("int", ctor_info.fields[j].var.value), field_vars[j])
                            fv = self.fresh(ft)
                            field_types.append(ft)
                            field_vars.append(fv)
                        ctor_term = _apps(_constant(ctor_info.ctor_const), *col_type_args, *field_vars)
                        sub_columns = [(fv, fv, ft) for fv, ft in zip(field_vars, field_types, strict=True)]
                        leaf_body = compile_matrix(
                            subst_cols(columns[:index], col_var_id, ctor_term)
                            + sub_columns
                            + subst_cols(columns[index + 1:], col_var_id, ctor_term),
                            specialize_rows(
                                active_rows,
                                index,
                                "union",
                                ctor_term,
                                col_var_id,
                                col_type,
                                len(field_vars),
                                ctor_name=ctor_info.name,
                            ),
                            self.substitute(pattern_term, col_var_id, ctor_term),
                        )
                        if ctor_info.is_dependent:
                            tail_types = []
                            for k in range(len(field_types) - 1):
                                tt = self._instantiate_generic_type(
                                    union_info.generic_vars, col_type_args, ctor_info.tail_sig_types[k + 1]
                                )
                                for j in range(k + 1):
                                    tt = self.substitute(tt, cast("int", ctor_info.fields[j].var.value), field_vars[j])
                                tail_types.append(tt)
                        else:
                            tail_types = [field_types[-1]]
                            for ft in reversed(field_types[1:-1]):
                                tail_types.append(_term("prod", ft, tail_types[-1]))
                            tail_types.reverse()
                        tail_vars = [
                            self.fresh(tail_types[k]) for k in range(len(field_types) - 2)
                        ] + [field_vars[-1]]
                        curr_body = leaf_body
                        for k in range(len(field_types) - 2, -1, -1):
                            left_var = field_vars[k]
                            left_type = field_types[k]
                            right_var = tail_vars[k]
                            right_type = tail_types[k]
                            if k == 0:
                                scrut = pvar
                                scrut_var_id = cast("int", pvar.value)
                                scrut_type = inst_payload_types[ctor_idx]
                            else:
                                scrut = tail_vars[k - 1]
                                scrut_var_id = cast("int", scrut.value)
                                scrut_type = tail_types[k - 1]
                            if motive_body is not None and not ctor_info.is_dependent:
                                partial = scrut
                                p_type = scrut_type
                                for j in range(k - 1, -1, -1):
                                    partial = _term("pair", field_types[j], p_type, field_vars[j], partial)
                                    p_type = _term("prod", field_types[j], p_type)
                                motive_return = self.substitute(
                                    motive_body,
                                    root_var_id,
                                    self.substitute(pattern_term, col_var_id, ctor_inj(ctor_idx, partial)),
                                )
                            else:
                                motive_return = cast("_Term", inferred_result[0])
                            if ctor_info.is_dependent and cast("int", left_var.value) in self.free(motive_return):
                                fam_lam = _term("lam", left_type, right_type, value=left_var.value)
                                proj1_var = _term("projT1", left_type, fam_lam, _term("var", value=scrut_var_id))
                                motive_return = self.substitute(motive_return, cast("int", left_var.value), proj1_var)
                                if motive_body is None and inferred_result[0] is not None:
                                    inferred_result[0] = self.substitute(motive_return, scrut_var_id, scrut)
                            motive_lam = _term("lam", scrut_type, motive_return, value=scrut_var_id)
                            branch_lam = _term(
                                "lam",
                                left_type,
                                _term("lam", right_type, curr_body, value=right_var.value),
                                value=left_var.value,
                            )
                            match_kind = "sigT_match" if ctor_info.is_dependent else "pair_match"
                            curr_body = _term(match_kind, motive_lam, scrut, branch_lam)
                        payload_vars.append(pvar)
                        payload_branches.append(curr_body)

                sum_vars = [self.fresh(inst_suffix_types[i]) for i in range(1, num_ctors - 1)]
                acc_body = payload_branches[-1]
                acc_var = payload_vars[-1]
                for i in range(num_ctors - 2, -1, -1):
                    left_lam = _term("lam", inst_payload_types[i], payload_branches[i], value=payload_vars[i].value)
                    right_lam = _term("lam", inst_suffix_types[i + 1], acc_body, value=acc_var.value)
                    if i == 0:
                        scrut = col_scrutinee
                        scrut_var_id = col_var_id
                        scrut_type = col_type
                        motive_return = (
                            self.substitute(motive_body, root_var_id, pattern_term)
                            if motive_body is not None
                            else cast("_Term", inferred_result[0])
                        )
                    else:
                        scrut = sum_vars[i - 1]
                        scrut_var_id = cast("int", scrut.value)
                        scrut_type = inst_suffix_types[i]
                        motive_return = (
                            self.substitute(
                                motive_body,
                                root_var_id,
                                self.substitute(pattern_term, col_var_id, suffix_inj(i, scrut)),
                            )
                            if motive_body is not None
                            else cast("_Term", inferred_result[0])
                        )
                    motive_lam = _term("lam", scrut_type, motive_return, value=scrut_var_id)
                    acc_body = _term("sum_match", motive_lam, scrut, left_lam, right_lam)
                    if i > 0:
                        acc_var = sum_vars[i - 1]
                return acc_body

            if col_type == _NAT:
                zero_term = _term("nat", value=0)
                zero_body = compile_matrix(
                    subst_cols(without_index, col_var_id, zero_term),
                    specialize_rows(active_rows, index, "zero", zero_term, col_var_id, _NAT, 0),
                    self.substitute(pattern_term, col_var_id, zero_term),
                )
                pred_var = self.fresh(_NAT)
                pred_var_id = cast("int", pred_var.value)
                for r_id, s_set in self.smaller_vars.items():
                    if (
                        col_var_id == r_id
                        or col_var_id in s_set
                        or (
                            col_scrutinee.kind == "var"
                            and (
                                cast("int", col_scrutinee.value) == r_id
                                or cast("int", col_scrutinee.value) in s_set
                            )
                        )
                    ):
                        s_set.add(pred_var_id)
                succ_term = _app(_constant("Succ"), pred_var)
                sub_columns = [(pred_var, pred_var, _NAT)]
                succ_body = compile_matrix(
                    subst_cols(columns[:index], col_var_id, succ_term)
                    + sub_columns
                    + subst_cols(columns[index + 1:], col_var_id, succ_term),
                    specialize_rows(active_rows, index, "succ", succ_term, col_var_id, _NAT, 1),
                    self.substitute(pattern_term, col_var_id, succ_term),
                )
                motive_return = (self.substitute(motive_body, root_var_id, pattern_term)
                                 if motive_body is not None else cast("_Term", inferred_result[0]))
                motive_lam = _term("lam", _NAT, motive_return, value=col_var_id)
                succ_lam = _term("lam", _NAT, succ_body, value=pred_var.value)
                return _term("nat_match", motive_lam, col_scrutinee, zero_body, succ_lam)

            raise self.fail("type", "match column must have type Nat, bool, Unit, a product or a record", node)

        term = compile_matrix([(root_var, scrutinee.term, scrutinee_type)], rows, root_var)
        result_type = (self.substitute(motive_body, root_var_id, scrutinee.term)
                       if motive_body is not None else cast("_Term", inferred_result[0]))
        if not synthetic:
            for arm_index, arm in enumerate(cases):
                if arm_index in local_visited:
                    continue
                arm_env = dict(environment)
                for bname, bval in arm_pattern_bindings[arm_index].items():
                    self.bind_local(arm_env, bname, bval)
                self.site = arm
                if expression_arms:
                    self.check(self.node(arm["value"]), result_type, arm_env)
                else:
                    block_node = {"kind": "block", "span": arm["span"], "statements": arm["statements"]}
                    self.block(block_node, arm_env, result_type, facts=facts)
        return _Binding(term, result_type)
