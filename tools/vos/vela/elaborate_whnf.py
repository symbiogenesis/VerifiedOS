# SPDX-License-Identifier: Apache-2.0
"""Weak-head normal form reduction and carrier evaluation for Vela elaboration."""

from typing import TYPE_CHECKING, cast

from vos.vela.elaborate_protocol import _OPERATORS
from vos.vela.elaborate_types import (
    _BOOL,
    _CHAR,
    _INT_SPECS,
    _NAT,
    _UNIT,
    _app,
    _apps,
    _clamp_int,
    _constant,
    _int_term,
    _RecordInfo,
    _Term,
    _term,
    _trunc_div,
    _trunc_rem,
    _wrap_int,
)

if TYPE_CHECKING:
    from vos.vela.elaborate import _Elaborator


class _WhnfMixin:
    def _is_whnf_constructor(self: _Elaborator, term: _Term) -> bool:
        if term.kind in {"nat", "int", "bool", "char", "unit", "pair", "inl", "inr", "existT"}:
            return True
        if term.kind == "app" and term.args[0] == _constant("Succ"):
            return True
        head, _ = self.spine(term)
        return (
            head.kind == "const"
            and isinstance(head.value, str)
            and (head.value in self.records_by_ctor or head.value in self.unions_by_ctor)
        )

    def _lam_arity(self: _Elaborator, term: _Term) -> int:
        count = 0
        curr = self.resolve(term)
        while curr.kind == "lam":
            count += 1
            curr = self.resolve(curr.args[1])
        return count

    def _build_dependent_record_tail(
        self: _Elaborator, record_info: _RecordInfo, type_args: list[_Term], field_vals: list[_Term]
    ) -> _Term:
        right_val = field_vals[-1]
        for k in range(len(field_vals) - 2, 0, -1):
            fv = field_vals[k]
            fvar_id = cast("int", record_info.fields[k].var.value)
            ftype = self._instantiate_record_type(record_info, type_args, record_info.fields[k].type)
            tail_type = self._instantiate_record_type(record_info, type_args, record_info.tail_sig_types[k + 1])
            for j in range(k):
                earlier_id = cast("int", record_info.fields[j].var.value)
                ftype = self.substitute(ftype, earlier_id, field_vals[j])
                tail_type = self.substitute(tail_type, earlier_id, field_vals[j])
            fam_lam = _term("lam", ftype, tail_type, value=fvar_id)
            right_val = _term("existT", ftype, fam_lam, fv, right_val)
        return right_val

    def occurs(self: _Elaborator, index: int, term: _Term) -> bool:
        term = self.resolve(term)
        return ((term.kind == "meta" and term.value == index)
                or any(self.occurs(index, child) for child in term.args))

    def whnf(self: _Elaborator, term: _Term) -> _Term:
        self.tick()
        term = self.resolve(term)
        if self.static_forbidden is None and all(
            m.solution is not None for m in self.metas[self.decl_first_meta :]
        ):
            self.decl_first_meta = len(self.metas)
            tid = id(term)
            cached = self.whnf_cache.get(tid)
            if cached is not None:
                return cached[1]
            res = self._whnf_core(term)
            self.whnf_cache[tid] = (term, res)
            self.whnf_cache[id(res)] = (res, res)
            return res
        return self._whnf_core(term)

    def _whnf_core(self: _Elaborator, term: _Term) -> _Term:
        if term.kind == "let":
            self.tick(True)
            return self.whnf(self.substitute(term.args[2], cast("int", term.value), term.args[1]))
        if term.kind == "static":
            if self.free(term.args[1]):
                return self.whnf(term.args[1])
            previous = self.static_forbidden
            self.static_forbidden = set() if previous is None else previous
            try:
                normalized = self.whnf(term.args[1])
                expected_whnf = self.whnf(term.args[0])
                kind = (
                    "int"
                    if self._int_spec(expected_whnf) is not None
                    else {_NAT: "nat", _BOOL: "bool", _CHAR: "char", _UNIT: "unit"}[expected_whnf]
                )
                if normalized.kind != kind:
                    raise self.fail("inference", "constant initializer did not evaluate to an admitted static value")
                return normalized
            finally:
                self.static_forbidden = previous
        if term.kind == "nat" and not 0 <= cast("int", term.value) <= self.natural_limit():
            raise self.fail("limit", "computed natural exceeds representation bound")
        if term.kind in {"if", "bool_match"}:
            condition = self.whnf(term.args[1])
            if condition.kind == "bool":
                self.tick(True)
                return self.whnf(term.args[2] if condition.value else term.args[3])
            return term
        if term.kind == "unit_match":
            scrutinee = self._expand_union_ctor(self.whnf(term.args[1]))
            if scrutinee.kind == "unit":
                self.tick(True)
                return self.whnf(term.args[2])
            rec_head, rec_args = self.spine(scrutinee)
            if rec_head.kind == "const" and isinstance(rec_head.value, str) and rec_head.value in self.records_by_ctor:
                record_info = self.records_by_ctor[rec_head.value]
                if not record_info.fields and len(rec_args) == len(record_info.generic_vars) + 1:
                    self.tick(True)
                    return self.whnf(term.args[2])
            return term
        if term.kind == "pair_match":
            scrutinee = self._expand_union_ctor(self.whnf(term.args[1]))
            if scrutinee.kind == "pair":
                self.tick(True)
                branch = term.args[2]
                inner = self.substitute(branch.args[1], cast("int", branch.value), scrutinee.args[2])
                return self.whnf(self.substitute(inner.args[1], cast("int", inner.value), scrutinee.args[3]))
            rec_head, rec_args = self.spine(scrutinee)
            if rec_head.kind == "const" and isinstance(rec_head.value, str) and rec_head.value in self.records_by_ctor:
                record_info = self.records_by_ctor[rec_head.value]
                if (
                    not record_info.is_dependent
                    and record_info.fields
                    and len(rec_args) == len(record_info.generic_vars) + len(record_info.fields)
                ):
                    self.tick(True)
                    type_args = rec_args[:len(record_info.generic_vars)]
                    field_vals = rec_args[len(record_info.generic_vars):]
                    field_types = [
                        self._instantiate_record_type(record_info, type_args, rf.type)
                        for rf in record_info.fields
                    ]
                    left_val = field_vals[0]
                    if len(field_vals) == 1:
                        right_val = _term("unit")
                    else:
                        right_val = field_vals[-1]
                        right_type = field_types[-1]
                        for fv, ft in reversed(list(zip(field_vals[1:-1], field_types[1:-1], strict=True))):
                            right_val = _term("pair", ft, right_type, fv, right_val)
                            right_type = _term("prod", ft, right_type)
                    branch = term.args[2]
                    inner = self.substitute(branch.args[1], cast("int", branch.value), left_val)
                    return self.whnf(self.substitute(inner.args[1], cast("int", inner.value), right_val))
            return term
        if term.kind == "sigT_match":
            scrutinee = self._expand_union_ctor(self.whnf(term.args[1]))
            if scrutinee.kind == "existT":
                self.tick(True)
                branch = term.args[2]
                inner = self.substitute(branch.args[1], cast("int", branch.value), scrutinee.args[2])
                return self.whnf(self.substitute(inner.args[1], cast("int", inner.value), scrutinee.args[3]))
            rec_head, rec_args = self.spine(scrutinee)
            if rec_head.kind == "const" and isinstance(rec_head.value, str) and rec_head.value in self.records_by_ctor:
                record_info = self.records_by_ctor[rec_head.value]
                if (
                    record_info.is_dependent
                    and len(rec_args) == len(record_info.generic_vars) + len(record_info.fields)
                ):
                    self.tick(True)
                    type_args = rec_args[:len(record_info.generic_vars)]
                    field_vals = rec_args[len(record_info.generic_vars):]
                    left_val = field_vals[0]
                    right_val = self._build_dependent_record_tail(record_info, type_args, field_vals)
                    branch = term.args[2]
                    inner = self.substitute(branch.args[1], cast("int", branch.value), left_val)
                    return self.whnf(self.substitute(inner.args[1], cast("int", inner.value), right_val))
            return term
        if term.kind in {"projT1", "projT2"}:
            pair_val = self._expand_union_ctor(self.whnf(term.args[2]))
            if pair_val.kind == "existT":
                self.tick(True)
                return self.whnf(pair_val.args[2] if term.kind == "projT1" else pair_val.args[3])
            rec_head, rec_args = self.spine(pair_val)
            if rec_head.kind == "const" and isinstance(rec_head.value, str) and rec_head.value in self.records_by_ctor:
                record_info = self.records_by_ctor[rec_head.value]
                if (
                    record_info.is_dependent
                    and len(rec_args) == len(record_info.generic_vars) + len(record_info.fields)
                ):
                    self.tick(True)
                    type_args = rec_args[:len(record_info.generic_vars)]
                    field_vals = rec_args[len(record_info.generic_vars):]
                    if term.kind == "projT1":
                        return self.whnf(field_vals[0])
                    return self.whnf(self._build_dependent_record_tail(record_info, type_args, field_vals))
            return term
        if term.kind == "sum_match":
            scrutinee = self._expand_union_ctor(self.whnf(term.args[1]))
            if scrutinee.kind == "inl":
                self.tick(True)
                left_branch = term.args[2]
                return self.whnf(self.substitute(left_branch.args[1], cast("int", left_branch.value), scrutinee.args[2]))
            if scrutinee.kind == "inr":
                self.tick(True)
                right_branch = term.args[3]
                return self.whnf(self.substitute(right_branch.args[1], cast("int", right_branch.value), scrutinee.args[2]))
            return term
        if term.kind == "nat_match":
            scrutinee = self.whnf(term.args[1])
            if scrutinee.kind == "nat":
                self.tick(True)
                amount = cast("int", scrutinee.value)
                if amount == 0:
                    return self.whnf(term.args[2])
                succ_branch = term.args[3]
                pred = _term("nat", value=amount - 1)
                return self.whnf(self.substitute(succ_branch.args[1], cast("int", succ_branch.value), pred))
            if scrutinee.kind == "app" and scrutinee.args[0] == _constant("Succ"):
                self.tick(True)
                succ_branch = term.args[3]
                return self.whnf(self.substitute(succ_branch.args[1], cast("int", succ_branch.value), scrutinee.args[1]))
            return term
        if term.kind == "const" and term.value in self.definitions:
            if self.definitions[term.value].kind == "fix":
                return term
            self.tick(True)
            return self.whnf(self.definitions[term.value])
        if term.kind != "app":
            return term
        head, arguments = self.spine(term)
        if head.kind == "const" and head.value not in self.definitions:
            pass
        else:
            new_head = self.whnf(head)
            if new_head.kind == "lam":
                self.tick(True)
                substituted = self.substitute(new_head.args[1], cast("int", new_head.value), arguments[0])
                return self.whnf(_apps(substituted, *arguments[1:]))
            if new_head != head:
                term = _apps(new_head, *arguments)
                head, arguments = self.spine(term)
        if head.kind == "fix":
            struct_idx = cast("int", head.args[3].value)
            total_arity = self._lam_arity(head.args[1])
            if len(arguments) >= total_arity and self._is_whnf_constructor(self.whnf(arguments[struct_idx])):
                self.tick(True)
                fix_id = cast("int", head.value)
                self_rep = _constant(self.fix_names[fix_id]) if fix_id in self.fix_names else head
                unfolded = self.substitute(head.args[1], fix_id, self_rep)
                return self.whnf(_apps(unfolded, *arguments))
            return term
        if head.kind != "const":
            return term
        name = head.value
        if isinstance(name, str) and name in self.definitions and self.definitions[name].kind == "fix":
            fix_term = self.definitions[name]
            struct_idx = cast("int", fix_term.args[3].value)
            total_arity = self._lam_arity(fix_term.args[1])
            if len(arguments) >= total_arity and self._is_whnf_constructor(self.whnf(arguments[struct_idx])):
                self.tick(True)
                unfolded = self.substitute(fix_term.args[1], cast("int", fix_term.value), _constant(name))
                return self.whnf(_apps(unfolded, *arguments))
        if isinstance(name, str) and name in self.record_projections:
            record_info, field_index = self.record_projections[name]
            proj_arity = len(record_info.generic_vars) + 1
            if len(arguments) >= proj_arity:
                rec_val = self.whnf(arguments[proj_arity - 1])
                rec_head, rec_args = self.spine(rec_val)
                if (rec_head == _constant(record_info.ctor_const)
                        and len(rec_args) == len(record_info.generic_vars) + len(record_info.fields)):
                    self.tick(True)
                    projected = rec_args[len(record_info.generic_vars) + field_index]
                    return self.whnf(_apps(projected, *arguments[proj_arity:]))
        if name in {"Fst", "Snd"} and len(arguments) >= 3:
            pair = self.whnf(arguments[2])
            if pair.kind == "pair":
                self.tick(True)
                projected = pair.args[2] if name == "Fst" else pair.args[3]
                return self.whnf(_apps(projected, *arguments[3:]))
        if name == "At" and len(arguments) >= 4:
            vector, values = self.spine(self.whnf(arguments[2]))
            index, indices = self.spine(self.whnf(arguments[3]))
            if vector == _constant("VCons") and len(values) == 4:
                if index == _constant("FZero") and len(indices) == 2:
                    self.tick(True)
                    return self.whnf(_apps(values[2], *arguments[4:]))
                if index == _constant("FSucc") and len(indices) == 2:
                    self.tick(True)
                    at_step = _apps(_constant("At"), arguments[0], values[1], values[3], indices[1])
                    return self.whnf(_apps(at_step, *arguments[4:]))
        if name == "Vec_At_Nat" and len(arguments) >= 5:
            elem_t, len_t, default_val, idx_t, vec_t = arguments[:5]
            idx_w = self.whnf(idx_t)
            vec_w = self.whnf(vec_t)
            v_head, v_args = self.spine(vec_w)
            if v_head == _constant("VNil") or vec_w.kind == "unit":
                self.tick(True)
                return self.whnf(_apps(default_val, *arguments[5:]))
            head_elem: _Term | None = None
            tail_vec: _Term | None = None
            tail_len: _Term | None = None
            if v_head == _constant("VCons") and len(v_args) == 4:
                tail_len, head_elem, tail_vec = v_args[1], v_args[2], v_args[3]
            elif vec_w.kind == "pair" and len(vec_w.args) == 4:
                head_elem, tail_vec = vec_w.args[2], vec_w.args[3]
                len_w = self.whnf(len_t)
                _, pred_len = self._peel_nat(len_w)
                tail_len = pred_len if pred_len is not None else _term("nat", value=0)
            if head_elem is not None and tail_vec is not None and tail_len is not None:
                idx_kind, idx_pred = self._peel_nat(idx_w)
                if idx_kind == "zero":
                    self.tick(True)
                    return self.whnf(_apps(head_elem, *arguments[5:]))
                if idx_kind == "succ" and idx_pred is not None:
                    self.tick(True)
                    step = _apps(_constant("Vec_At_Nat"), elem_t, tail_len, default_val, idx_pred, tail_vec)
                    return self.whnf(_apps(step, *arguments[5:]))
        if name == "Vec_Update" and len(arguments) == 5:
            elem_t, _len_t, idx_t, val_t, vec_t = arguments
            idx_w = self.whnf(idx_t)
            vec_w = self.whnf(vec_t)
            v_head, v_args = self.spine(vec_w)
            if v_head == _constant("VCons") and len(v_args) == 4:
                tail_len, head_elem, tail_vec = v_args[1], v_args[2], v_args[3]
                idx_kind, idx_pred = self._peel_nat(idx_w)
                if idx_kind == "zero":
                    self.tick(True)
                    return _apps(_constant("VCons"), elem_t, tail_len, val_t, tail_vec)
                if idx_kind == "succ" and idx_pred is not None:
                    self.tick(True)
                    new_tail = self.whnf(_apps(_constant("Vec_Update"), elem_t, tail_len, idx_pred, val_t, tail_vec))
                    return _apps(_constant("VCons"), elem_t, tail_len, head_elem, new_tail)
        if name == "ByteLength" and len(arguments) == 2:
            self.tick(True)
            return self.whnf(arguments[0])
        if name == "EmptyBuilder" and len(arguments) == 2 and self.whnf(arguments[1]).kind == "unit":
            self.tick(True)
            return _apps(
                _constant("TextBuilderVal"),
                self.whnf(arguments[0]),
                _term("bool", value=1),
                _term("nat", value=0),
            )
        if name in {"Fits", "Written"} and len(arguments) == 2:
            builder_head, builder_args = self.spine(self.whnf(arguments[1]))
            if builder_head == _constant("TextBuilderVal") and len(builder_args) == 3:
                self.tick(True)
                return self.whnf(builder_args[1] if name == "Fits" else builder_args[2])
        if name == "FormatStep" and len(arguments) == 3:
            cap = self.whnf(arguments[0])
            builder_head, builder_args = self.spine(self.whnf(arguments[1]))
            chunk = self.whnf(arguments[2])
            if (cap.kind == "nat" and chunk.kind == "nat"
                    and builder_head == _constant("TextBuilderVal") and len(builder_args) == 3):
                ok = self.whnf(builder_args[1])
                used = self.whnf(builder_args[2])
                if ok.kind == "bool" and used.kind == "nat":
                    self.tick(True)
                    total = cast("int", used.value) + cast("int", chunk.value)
                    if total > self.natural_limit():
                        raise self.fail("limit", "computed natural exceeds representation bound")
                    fits = int(bool(cast("int", ok.value)) and total <= cast("int", cap.value))
                    return _apps(
                        _constant("TextBuilderVal"),
                        cap,
                        _term("bool", value=fits),
                        _term("nat", value=total),
                    )
        if name == "Succ" and len(arguments) == 1:
            value = self.whnf(arguments[0])
            if value.kind == "nat":
                self.tick(True)
                if cast("int", value.value) >= self.natural_limit():
                    raise self.fail("limit", "computed natural exceeds representation bound")
                return _term("nat", value=cast("int", value.value) + 1)
        if name == "!" and len(arguments) == 1:
            value = self.whnf(arguments[0])
            if value.kind == "bool":
                self.tick(True)
                return _term("bool", value=1 - cast("int", value.value))
        if len(arguments) == 2 and name in _OPERATORS | {"eq_nat", "eq_bool", "ne_nat", "ne_bool"}:
            left, right = (self.whnf(value) for value in arguments)
            if left.kind == right.kind and left.kind in {"nat", "bool"}:
                a, b = cast("int", left.value), cast("int", right.value)
                operations = {"+": lambda: a + b, "*": lambda: a * b,
                              "-": lambda: max(0, a - b), "/": lambda: 0 if b == 0 else a // b,
                              "%": lambda: a if b == 0 else a % b,
                              "<=": lambda: int(a <= b), "<": lambda: int(a < b),
                              ">=": lambda: int(a >= b), ">": lambda: int(a > b),
                              "eq_nat": lambda: int(a == b), "eq_bool": lambda: int(a == b),
                              "ne_nat": lambda: int(a != b), "ne_bool": lambda: int(a != b),
                              "&&": lambda: int(bool(a and b)), "||": lambda: int(bool(a or b)),
                              "==>": lambda: int(not a or b), "<==>": lambda: int(a == b)}
                operation = operations.get(name)
                if operation is not None:
                    self.tick(True)
                    limit = self.natural_limit()
                    if ((name == "+" and a > limit - b)
                            or (name == "*" and a != 0 and b > limit // a)):
                        raise self.fail("limit", "computed natural exceeds representation bound")
                    value = operation()
                    if value > limit:
                        raise self.fail("limit", "computed natural exceeds representation bound")
                    kind = "nat" if name in {"+", "*", "-", "/", "%"} else "bool"
                    return _term(kind, value=value)
            if name == "+" and left.kind == "nat":
                self.tick(True)
                amount = cast("int", left.value)
                if amount == 0:
                    return right
                return _app(_constant("Succ"), _apps(_constant("+"), _term("nat", value=amount - 1), right))
            if name == "+" and left.kind == "app" and left.args[0] == _constant("Succ"):
                self.tick(True)
                return _app(_constant("Succ"), self.whnf(_apps(_constant("+"), left.args[1], right)))
            if left.kind == "bool" and name in {"&&", "||", "==>"}:
                self.tick(True)
                if name == "&&":
                    return right if left.value else _term("bool", value=0)
                if name == "||":
                    return _term("bool", value=1) if left.value else right
                return right if left.value else _term("bool", value=1)
            l_kind, l_pred = self._peel_nat(left)
            r_kind, r_pred = self._peel_nat(right)
            if name == "-":
                if l_kind == "zero":
                    self.tick(True)
                    return _term("nat", value=0)
                if r_kind == "zero":
                    self.tick(True)
                    return left
                if l_kind == "succ" and r_kind == "succ" and l_pred is not None and r_pred is not None:
                    self.tick(True)
                    return self.whnf(_apps(_constant("-"), l_pred, r_pred))
            if name == "<=":
                if l_kind == "zero":
                    self.tick(True)
                    return _term("bool", value=1)
                if l_kind == "succ" and r_kind == "zero":
                    self.tick(True)
                    return _term("bool", value=0)
                if l_kind == "succ" and r_kind == "succ" and l_pred is not None and r_pred is not None:
                    self.tick(True)
                    return self.whnf(_apps(_constant("<="), l_pred, r_pred))
            if name == "<" and r_kind in {"zero", "succ"}:
                self.tick(True)
                return self.whnf(_apps(_constant("<="), _app(_constant("Succ"), left), right))
            if name == ">=" and (l_kind in {"zero", "succ"} or r_kind in {"zero", "succ"}):
                self.tick(True)
                return self.whnf(_apps(_constant("<="), right, left))
            if name == ">" and l_kind in {"zero", "succ"}:
                self.tick(True)
                return self.whnf(_apps(_constant("<="), _app(_constant("Succ"), right), left))
            if name in {"eq_nat", "ne_nat"}:
                if (l_kind == "zero" and r_kind == "succ") or (l_kind == "succ" and r_kind == "zero"):
                    self.tick(True)
                    return _term("bool", value=0 if name == "eq_nat" else 1)
                if l_kind == "succ" and r_kind == "succ" and l_pred is not None and r_pred is not None:
                    self.tick(True)
                    return self.whnf(_apps(_constant(name), l_pred, r_pred))
        if name == "nat_to_usize" and len(arguments) == 1:
            n_w = self.whnf(arguments[0])
            if n_w.kind == "nat":
                self.tick(True)
                return _int_term(_INT_SPECS["usize"], _wrap_int(_INT_SPECS["usize"], cast("int", n_w.value)))
        if name in {"eq_unit", "ne_unit"} and len(arguments) == 2:
            self.tick(True)
            return _term("bool", value=1 if name == "eq_unit" else 0)
        if name in {"char_eq", "char_ne", "char_lt", "char_le", "char_gt", "char_ge"} and len(arguments) == 2:
            left = self.whnf(arguments[0])
            right = self.whnf(arguments[1])
            if left.kind == "char" and right.kind == "char":
                self.tick(True)
                a = cast("int", left.value)
                b = cast("int", right.value)
                res_bool = {
                    "char_eq": a == b,
                    "char_ne": a != b,
                    "char_lt": a < b,
                    "char_le": a <= b,
                    "char_gt": a > b,
                    "char_ge": a >= b,
                }[cast("str", name)]
                return _term("bool", value=int(res_bool))
        if name == "char_to_nat" and len(arguments) == 1:
            c_w = self.whnf(arguments[0])
            if c_w.kind == "char":
                self.tick(True)
                return _term("nat", value=cast("int", c_w.value))
        if name == "char_to_u32" and len(arguments) == 1:
            c_w = self.whnf(arguments[0])
            if c_w.kind == "char":
                self.tick(True)
                return _int_term(_INT_SPECS["u32"], cast("int", c_w.value))
        if name == "char_from_u8" and len(arguments) == 1:
            b_w = self.whnf(arguments[0])
            if b_w.kind == "int":
                self.tick(True)
                return _term("char", value=cast("int", b_w.value))
        if name in {"char_try_from_u32", "char_try_from_Nat"} and len(arguments) == 1:
            v_w = self.whnf(arguments[0])
            if v_w.kind in {"int", "nat"}:
                self.tick(True)
                cp = cast("int", v_w.value)
                ce_const = _constant(self.unions["ConversionError"].type_const)
                if 0 <= cp <= 0x10FFFF and not (0xD800 <= cp <= 0xDFFF):
                    return self._make_result_ok(_CHAR, ce_const, _term("char", value=cp))
                return self._make_result_err(_CHAR, ce_const, self._make_conv_err())
        if isinstance(name, str) and name.startswith("int_"):
            reduced_int = self._whnf_int_op(name, arguments)
            if reduced_int is not None:
                return reduced_int
        if isinstance(name, str) and name.startswith("Span_"):
            reduced_span = self._whnf_span_op(name, arguments)
            if reduced_span is not None:
                return reduced_span
        if isinstance(name, str) and (name.startswith("Seq_") or name in {"Vec_Model", "Span_Model"}):
            reduced_seq = self._whnf_seq_op(name, arguments)
            if reduced_seq is not None:
                return reduced_seq
        if isinstance(name, str) and (name.startswith("Slots_") or name == "PrefixModel"):
            reduced_slots = self._whnf_slots_op(name, arguments)
            if reduced_slots is not None:
                return reduced_slots
        if head.value == "if" and len(arguments) >= 4:
            condition = self.whnf(arguments[1])
            if condition.kind == "bool":
                self.tick(True)
                chosen = arguments[2] if condition.value else arguments[3]
                return self.whnf(_apps(chosen, *arguments[4:]))
        return term

    def _make_result_ok(self: _Elaborator, val_type: _Term, err_type: _Term, val_term: _Term) -> _Term:
        res_union = self.unions["Result"]
        ok_ctor = next(c for c in res_union.constructors if c.name == "Ok")
        return _apps(_constant(ok_ctor.ctor_const), val_type, err_type, val_term)

    def _make_result_err(self: _Elaborator, val_type: _Term, err_type: _Term, err_term: _Term) -> _Term:
        res_union = self.unions["Result"]
        err_ctor = next(c for c in res_union.constructors if c.name == "Err")
        return _apps(_constant(err_ctor.ctor_const), val_type, err_type, err_term)

    def _make_arith_err(self: _Elaborator, ctor_name: str) -> _Term:
        ae_union = self.unions["ArithmeticError"]
        ctor = next(c for c in ae_union.constructors if c.name == ctor_name)
        return _app(_constant(ctor.ctor_const), _term("unit"))

    def _make_conv_err(self: _Elaborator) -> _Term:
        ce_union = self.unions["ConversionError"]
        ctor = ce_union.constructors[0]
        return _app(_constant(ctor.ctor_const), _term("unit"))

    def _whnf_int_op(self: _Elaborator, name: str, arguments: list[_Term]) -> _Term | None:
        ae_const = _constant(self.unions["ArithmeticError"].type_const)
        ce_const = _constant(self.unions["ConversionError"].type_const)
        if name.startswith("int_to_nat_") and len(arguments) == 1:
            arg = self.whnf(arguments[0])
            if arg.kind == "int":
                self.tick(True)
                return _term("nat", value=max(0, cast("int", arg.value)))
            return None
        if name.startswith("int_from_") and len(arguments) == 1:
            parts = name.split("_")
            dst_spec = _INT_SPECS[parts[3]]
            arg = self.whnf(arguments[0])
            if arg.kind == "int":
                self.tick(True)
                # Admitted From conversions widen exactly; any other pair keeps the
                # kernel image's low destination bits.
                return _int_term(dst_spec, _wrap_int(dst_spec, cast("int", arg.value)))
            return None
        if name.startswith("int_try_from_") and len(arguments) == 1:
            parts = name.split("_")
            dst_spec = _INT_SPECS[parts[4]]
            arg = self.whnf(arguments[0])
            if arg.kind in {"int", "nat"}:
                self.tick(True)
                val = cast("int", arg.value)
                if dst_spec.min_val <= val <= dst_spec.max_val:
                    return self._make_result_ok(dst_spec.const, ce_const, _int_term(dst_spec, val))
                return self._make_result_err(dst_spec.const, ce_const, self._make_conv_err())
            return None
        prefix, spec_name = name.rsplit("_", 1)
        spec = _INT_SPECS.get(spec_name)
        if spec is None:
            return None
        op = prefix[4:]  # strip "int_"
        if len(arguments) == 1 and op in {"neg", "not", "wrap_neg", "sat_neg", "chk_neg"}:
            arg = self.whnf(arguments[0])
            if arg.kind != "int":
                return None
            self.tick(True)
            a = cast("int", arg.value)
            if op in {"neg", "wrap_neg"}:
                return _int_term(spec, _wrap_int(spec, -a))
            if op == "not":
                return _int_term(spec, _wrap_int(spec, ~a))
            if op == "sat_neg":
                return _int_term(spec, _clamp_int(spec, -a))
            if spec.min_val <= -a <= spec.max_val:
                return self._make_result_ok(spec.const, ae_const, _int_term(spec, -a))
            return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
        if len(arguments) == 2:
            left = self.whnf(arguments[0])
            right = self.whnf(arguments[1])
            if left.kind != "int" or right.kind != "int":
                return None
            self.tick(True)
            a = cast("int", left.value)
            b = cast("int", right.value)
            if op in {"add", "wrap_add"}:
                return _int_term(spec, _wrap_int(spec, a + b))
            if op in {"sub", "wrap_sub"}:
                return _int_term(spec, _wrap_int(spec, a - b))
            if op in {"mul", "wrap_mul"}:
                return _int_term(spec, _wrap_int(spec, a * b))
            if op == "div":
                if b == 0:
                    return _int_term(spec, 0)
                return _int_term(spec, _wrap_int(spec, _trunc_div(a, b)))
            if op == "rem":
                if b == 0:
                    return _int_term(spec, a)
                if spec.signed and a == spec.min_val and b == -1:
                    return _int_term(spec, 0)
                return _int_term(spec, _wrap_int(spec, _trunc_rem(a, b)))
            if op == "and":
                return _int_term(spec, _wrap_int(spec, a & b))
            if op == "or":
                return _int_term(spec, _wrap_int(spec, a | b))
            if op == "xor":
                return _int_term(spec, _wrap_int(spec, a ^ b))
            if op == "sat_add":
                return _int_term(spec, _clamp_int(spec, a + b))
            if op == "sat_sub":
                return _int_term(spec, _clamp_int(spec, a - b))
            if op == "sat_mul":
                return _int_term(spec, _clamp_int(spec, a * b))
            if op == "eq":
                return _term("bool", value=int(a == b))
            if op == "ne":
                return _term("bool", value=int(a != b))
            if op == "lt":
                return _term("bool", value=int(a < b))
            if op == "le":
                return _term("bool", value=int(a <= b))
            if op == "gt":
                return _term("bool", value=int(a > b))
            if op == "ge":
                return _term("bool", value=int(a >= b))
            if op in {"shl", "wrap_shl"}:
                if not 0 <= b < spec.bits:
                    return _int_term(spec, 0)
                return _int_term(spec, _wrap_int(spec, a << b))
            if op == "shr":
                if not 0 <= b < spec.bits:
                    return _int_term(spec, -1 if (spec.signed and a < 0) else 0)
                if spec.signed:
                    return _int_term(spec, a >> b)
                return _int_term(spec, (a & ((1 << spec.bits) - 1)) >> b)
            if op == "chk_add":
                if spec.min_val <= a + b <= spec.max_val:
                    return self._make_result_ok(spec.const, ae_const, _int_term(spec, a + b))
                return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
            if op == "chk_sub":
                if spec.min_val <= a - b <= spec.max_val:
                    return self._make_result_ok(spec.const, ae_const, _int_term(spec, a - b))
                return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
            if op == "chk_mul":
                if spec.min_val <= a * b <= spec.max_val:
                    return self._make_result_ok(spec.const, ae_const, _int_term(spec, a * b))
                return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
            if op == "chk_div":
                if b == 0:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("ZeroDivisor"))
                if spec.signed and a == spec.min_val and b == -1:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
                return self._make_result_ok(spec.const, ae_const, _int_term(spec, _trunc_div(a, b)))
            if op == "chk_rem":
                if b == 0:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("ZeroDivisor"))
                # CheckedRem(MIN, -1) is Ok(0): the remainder is representable even
                # though the matching quotient is not.
                return self._make_result_ok(spec.const, ae_const, _int_term(spec, _trunc_rem(a, b)))
            if op == "chk_shl":
                if not 0 <= b < spec.bits:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("InvalidShift"))
                if not spec.min_val <= (a << b) <= spec.max_val:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("Overflow"))
                return self._make_result_ok(spec.const, ae_const, _int_term(spec, a << b))
            if op == "chk_shr":
                if not 0 <= b < spec.bits:
                    return self._make_result_err(spec.const, ae_const, self._make_arith_err("InvalidShift"))
                shifted = (a >> b) if spec.signed else ((a & ((1 << spec.bits) - 1)) >> b)
                return self._make_result_ok(spec.const, ae_const, _int_term(spec, shifted))
        return None

    def _span_root_and_const_offset(self: _Elaborator, elem: _Term, span_term: _Term) -> tuple[_Term, int] | None:
        self.tick()
        s = self.whnf(span_term)
        if s.kind == "if":
            return None
        s_head, s_args = self.spine(s)
        if s_head.kind == "const" and isinstance(s_head.value, str):
            sname = s_head.value
            if sname == "Span_AllocZeroed" and len(s_args) == 3:
                base_w = self.whnf(s_args[1])
                if base_w.kind == "int":
                    return (_constant("__concrete_addr__"), cast("int", base_w.value))
                return (s, 0)
            if (
                sname
                in {
                    "Span_ReadOnly",
                    "Span_Invalidate",
                    "Span_Write",
                    "Span_Fill",
                    "Span_CopyPrefix",
                    "Span_Restore",
                    "LoopState",
                }
                and len(s_args) >= 2
            ):
                return self._span_root_and_const_offset(elem, s_args[1])
            if sname == "Span_Slice" and len(s_args) == 4:
                off_w = self.whnf(s_args[2])
                if off_w.kind != "int":
                    return None
                inner_ro = self._span_root_and_const_offset(elem, s_args[1])
                if inner_ro is None:
                    return None
                return (
                    inner_ro[0],
                    _wrap_int(_INT_SPECS["usize"], inner_ro[1] + cast("int", off_w.value)),
                )
        return (s, 0)

    def _lookup_span_at_root_offset(
        self: _Elaborator,
        elem: _Term,
        span_term: _Term,
        target_root: _Term,
        target_off: int,
        orig_span: _Term,
    ) -> _Term | None:
        self.tick()
        s = self.whnf(span_term)
        ro = self._span_root_and_const_offset(elem, s)
        if ro is None or ro[0] != target_root:
            return None
        cur_off = ro[1]
        s_head, s_args = self.spine(s)
        if s_head.kind == "const" and isinstance(s_head.value, str):
            sname = s_head.value
            if sname == "Span_AllocZeroed" and len(s_args) == 3:
                return _int_term(_INT_SPECS["u8"], 0)
            if sname in {"Span_ReadOnly", "Span_Invalidate"} and len(s_args) == 2:
                return self._lookup_span_at_root_offset(elem, s_args[1], target_root, target_off, orig_span)
            if sname == "Span_Slice" and len(s_args) == 4:
                return self._lookup_span_at_root_offset(elem, s_args[1], target_root, target_off, orig_span)
            if sname == "Span_Restore" and len(s_args) == 3:
                return self._lookup_span_at_root_offset(elem, s_args[2], target_root, target_off, orig_span)
            if sname == "Span_Write" and len(s_args) == 4:
                inner, w_idx, val = s_args[1], s_args[2], s_args[3]
                w_idx_w = self.whnf(w_idx)
                if w_idx_w.kind == "int":
                    w_off = _wrap_int(_INT_SPECS["usize"], cur_off + cast("int", w_idx_w.value))
                    if target_off == w_off:
                        return self.whnf(val)
                    return self._lookup_span_at_root_offset(elem, inner, target_root, target_off, orig_span)
                return None
            if sname == "Span_Fill" and len(s_args) == 5:
                inner, off, count, val = s_args[1], s_args[2], s_args[3], s_args[4]
                off_w = self.whnf(off)
                cnt_w = self.whnf(count)
                if off_w.kind == "int" and cnt_w.kind == "int":
                    lo = _wrap_int(_INT_SPECS["usize"], cur_off + cast("int", off_w.value))
                    hi = lo + cast("int", cnt_w.value)
                    if lo <= target_off < hi:
                        return self.whnf(val)
                    return self._lookup_span_at_root_offset(elem, inner, target_root, target_off, orig_span)
                return None
            if sname == "Span_CopyPrefix" and len(s_args) == 4:
                dst_s, src_s, count = s_args[1], s_args[2], s_args[3]
                cnt_w = self.whnf(count)
                if cnt_w.kind == "int":
                    lo = cur_off
                    hi = lo + cast("int", cnt_w.value)
                    if lo <= target_off < hi:
                        src_ro = self._span_root_and_const_offset(elem, src_s)
                        if src_ro is not None:
                            src_target = _wrap_int(_INT_SPECS["usize"], src_ro[1] + (target_off - lo))
                            return self._lookup_span_at_root_offset(elem, src_s, src_ro[0], src_target, src_s)
                        return None
                    return self._lookup_span_at_root_offset(elem, dst_s, target_root, target_off, orig_span)
                return None
        if s != orig_span and target_root != _constant("__concrete_addr__") and cur_off == 0:
            return _apps(_constant("Span_Read"), elem, s, _int_term(_INT_SPECS["usize"], target_off))
        return None

    def _whnf_span_op(self: _Elaborator, name: str, arguments: list[_Term]) -> _Term | None:
        if name in {"Span_CanRead", "Span_CanWrite"} and len(arguments) == 2:
            elem, s = arguments
            perm_const = "Span_PermRead" if name == "Span_CanRead" else "Span_PermWrite"
            self.tick(True)
            return self.whnf(
                _apps(
                    _constant("&&"),
                    _apps(_constant("Span_Tag"), elem, s),
                    _apps(_constant(perm_const), elem, s),
                )
            )
        if name in {"Span_Base", "Span_Length", "Span_Tag", "Span_PermRead", "Span_PermWrite"} and len(arguments) == 2:
            elem = arguments[0]
            s = self.whnf(arguments[1])
            s_head, s_args = self.spine(s)
            if s_head.kind != "const" or not isinstance(s_head.value, str):
                return None
            sname = s_head.value
            if sname == "Span_AllocZeroed" and len(s_args) == 3:
                self.tick(True)
                if name == "Span_Base":
                    return self.whnf(s_args[1])
                if name == "Span_Length":
                    return self.whnf(s_args[2])
                return _term("bool", value=1)
            if sname == "Span_ReadOnly" and len(s_args) == 2:
                self.tick(True)
                if name == "Span_PermWrite":
                    return _term("bool", value=0)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_Invalidate" and len(s_args) == 2:
                self.tick(True)
                if name in {"Span_Tag", "Span_PermRead", "Span_PermWrite"}:
                    return _term("bool", value=0)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_Write" and len(s_args) == 4:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_Fill" and len(s_args) == 5:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_Slice" and len(s_args) == 4:
                self.tick(True)
                if name == "Span_Base":
                    return self.whnf(
                        _apps(_constant("int_add_usize"), _apps(_constant("Span_Base"), elem, s_args[1]), s_args[2])
                    )
                if name == "Span_Length":
                    return self.whnf(s_args[3])
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_CopyPrefix" and len(s_args) == 4:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "Span_Restore" and len(s_args) == 3:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            if sname == "LoopState" and len(s_args) == 3:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, s_args[1]))
            return None
        if name == "Span_Disjoint" and len(arguments) == 3:
            elem, a, b = arguments
            ba = self.whnf(_apps(_constant("Span_Base"), elem, a))
            if ba.kind != "int":
                return None
            la = self.whnf(_apps(_constant("Span_Length"), elem, a))
            bb = self.whnf(_apps(_constant("Span_Base"), elem, b))
            lb = self.whnf(_apps(_constant("Span_Length"), elem, b))
            if la.kind != "int" or bb.kind != "int" or lb.kind != "int":
                return None
            self.tick(True)
            ba_v = cast("int", ba.value)
            la_v = cast("int", la.value)
            bb_v = cast("int", bb.value)
            lb_v = cast("int", lb.value)
            return _term("bool", value=int(ba_v + la_v <= bb_v or bb_v + lb_v <= ba_v))
        if name == "Span_Read" and len(arguments) == 3:
            elem, s, idx = arguments
            s_w = self.whnf(s)
            idx_w = self.whnf(idx)
            if s_w.kind != "app":
                if s_w != s or idx_w != idx:
                    self.tick(True)
                    return _apps(_constant("Span_Read"), elem, s_w, idx_w)
                return None
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Span_AllocZeroed") and len(s_args) == 3:
                self.tick(True)
                return _int_term(_INT_SPECS["u8"], 0)
            if idx_w.kind != "int":
                return None
            ro = self._span_root_and_const_offset(elem, s_w)
            if ro is None:
                return None
            target_off = _wrap_int(_INT_SPECS["usize"], ro[1] + cast("int", idx_w.value))
            found = self._lookup_span_at_root_offset(elem, s_w, ro[0], target_off, s_w)
            if found is not None:
                self.tick(True)
                return found
            return None
        return None

    def _extract_seq_elements(self: _Elaborator, seq_term: _Term) -> list[_Term] | None:
        cur = self.whnf(seq_term)
        elems: list[_Term] = []
        while True:
            head, args = self.spine(cur)
            if head == _constant("Seq_Empty") and len(args) == 1:
                return elems
            if head == _constant("Seq_Cons") and len(args) == 3:
                elems.append(args[1])
                cur = self.whnf(args[2])
                continue
            if head == _constant("Seq_Singleton") and len(args) == 2:
                elems.append(args[1])
                return elems
            return None

    def _build_seq_term(self: _Elaborator, elem_type: _Term, elems: list[_Term]) -> _Term:
        acc = _app(_constant("Seq_Empty"), elem_type)
        for item in reversed(elems):
            acc = _apps(_constant("Seq_Cons"), elem_type, item, acc)
        return acc

    def _default_term_for_type(self: _Elaborator, type_term: _Term) -> _Term:
        t_w = self.whnf(type_term)
        if t_w == _constant("Nat"):
            return _term("nat", value=0)
        if t_w == _constant("bool"):
            return _term("bool", value=0)
        if t_w == _CHAR:
            return _term("char", value=0)
        if t_w == _constant("Unit"):
            return _term("unit")
        if t_w.kind == "const" and isinstance(t_w.value, str) and t_w.value in _INT_SPECS:
            return _int_term(_INT_SPECS[t_w.value], 0)
        if t_w.kind == "prod":
            return _term(
                "pair",
                t_w.args[0],
                t_w.args[1],
                self._default_term_for_type(t_w.args[0]),
                self._default_term_for_type(t_w.args[1]),
            )
        head, args = self.spine(t_w)
        if head == _constant("Vec") and len(args) == 2:
            len_w = self.whnf(args[1])
            if len_w.kind == "nat" and 0 <= cast("int", len_w.value) <= 64:
                n_val = cast("int", len_w.value)
                elem_def = self._default_term_for_type(args[0])
                acc = _apps(_constant("VNil"), args[0], _term("unit"))
                for k in range(n_val):
                    acc = _apps(_constant("VCons"), args[0], _term("nat", value=k), elem_def, acc)
                return acc
        if head == _constant("Seq") and len(args) == 1:
            return _app(_constant("Seq_Empty"), args[0])
        if head == _constant("Span") and len(args) == 1:
            z = _int_term(_INT_SPECS["usize"], 0)
            return _apps(_constant("Span_AllocZeroed"), args[0], z, z)
        if head == _constant("Slots") and len(args) == 2:
            z = _int_term(_INT_SPECS["usize"], 0)
            return _apps(_constant("Slots_AllocVacant"), args[0], args[1], z)
        if head.kind == "const" and isinstance(head.value, str) and head.value in self.records_by_type:
            rinfo = self.records_by_type[head.value]
            if not rinfo.fields:
                return _apps(_constant(rinfo.ctor_const), *args, _term("unit"))
            f_vals: list[_Term] = []
            for idx, rf in enumerate(rinfo.fields):
                fty = self._instantiate_record_type(rinfo, args, rf.type)
                for j in range(idx):
                    fty = self.substitute(fty, cast("int", rinfo.fields[j].var.value), f_vals[j])
                f_vals.append(self._default_term_for_type(fty))
            return _apps(_constant(rinfo.ctor_const), *args, *f_vals)
        if head.kind == "const" and isinstance(head.value, str) and head.value in self.unions_by_type:
            uinfo = self.unions_by_type[head.value]
            ctor = uinfo.constructors[0]
            if not ctor.fields:
                return _apps(_constant(ctor.ctor_const), *args, _term("unit"))
            f_vals = []
            for rf in ctor.fields:
                fty = self._instantiate_generic_type(uinfo.generic_vars, args, rf.type)
                f_vals.append(self._default_term_for_type(fty))
            return _apps(_constant(ctor.ctor_const), *args, *f_vals)
        return _term("nat", value=0)

    def _whnf_seq_op(self: _Elaborator, name: str, arguments: list[_Term]) -> _Term | None:
        if name == "Seq_Singleton" and len(arguments) == 2:
            elem, val = arguments
            self.tick(True)
            return _apps(_constant("Seq_Cons"), elem, val, _app(_constant("Seq_Empty"), elem))
        if name == "Vec_Model" and len(arguments) == 3:
            elem, _len, vec_term = arguments
            v_w = self.whnf(vec_term)
            v_head, v_args = self.spine(v_w)
            if v_head == _constant("VNil") and len(v_args) in {1, 2}:
                self.tick(True)
                return _app(_constant("Seq_Empty"), elem)
            if v_head == _constant("VCons") and len(v_args) == 4:
                self.tick(True)
                tail_seq = self.whnf(_apps(_constant("Vec_Model"), elem, v_args[1], v_args[3]))
                return _apps(_constant("Seq_Cons"), elem, v_args[2], tail_seq)
            return None
        if name == "Span_Model" and len(arguments) == 2:
            elem, span_term = arguments
            s_w = self.whnf(span_term)
            len_w = self.whnf(_apps(_constant("Span_Length"), elem, s_w))
            if len_w.kind == "int":
                n = cast("int", len_w.value)
                if 0 <= n <= 64:
                    elems: list[_Term] = []
                    for i in range(n):
                        idx_term = _int_term(_INT_SPECS["usize"], i)
                        val_w = self.whnf(_apps(_constant("Span_Read"), elem, s_w, idx_term))
                        elems.append(val_w)
                    self.tick(True)
                    return self._build_seq_term(elem, elems)
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Span_Write") and len(s_args) == 4:
                self.tick(True)
                inner_model = self.whnf(_apps(_constant("Span_Model"), elem, s_args[1]))
                idx_nat = self.whnf(_app(_constant("int_to_nat_usize"), s_args[2]))
                return self.whnf(_apps(_constant("Seq_Update"), elem, inner_model, idx_nat, s_args[3]))
            return None
        if name == "Seq_Count" and len(arguments) == 2:
            _elem, seq_term = arguments
            s_w = self.whnf(seq_term)
            elems = self._extract_seq_elements(s_w)
            if elems is not None:
                self.tick(True)
                return _term("nat", value=len(elems))
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Seq_Cons") and len(s_args) == 3:
                self.tick(True)
                return self.whnf(_app(_constant("Succ"), _apps(_constant("Seq_Count"), s_args[0], s_args[2])))
            if s_head == _constant("Seq_Update") and len(s_args) == 4:
                self.tick(True)
                return self.whnf(_apps(_constant("Seq_Count"), s_args[0], s_args[1]))
            if s_head == _constant("Seq_Append") and len(s_args) == 3:
                self.tick(True)
                c1 = _apps(_constant("Seq_Count"), s_args[0], s_args[1])
                c2 = _apps(_constant("Seq_Count"), s_args[0], s_args[2])
                return self.whnf(_apps(_constant("+"), c1, c2))
            if s_head == _constant("Vec_Model") and len(s_args) == 3:
                self.tick(True)
                return self.whnf(s_args[1])
            if s_head == _constant("Span_Model") and len(s_args) == 2:
                len_w = self.whnf(_apps(_constant("Span_Length"), s_args[0], s_args[1]))
                if len_w.kind == "int":
                    self.tick(True)
                    return _term("nat", value=max(0, cast("int", len_w.value)))
                self.tick(True)
                return self.whnf(_app(_constant("int_to_nat_usize"), len_w))
            if s_head == _constant("Slots_Model") and len(s_args) == 3:
                live_w = self.whnf(_apps(_constant("Slots_LiveCount"), s_args[0], s_args[1], s_args[2]))
                if live_w.kind == "int":
                    self.tick(True)
                    return _term("nat", value=max(0, cast("int", live_w.value)))
                self.tick(True)
                return self.whnf(_app(_constant("int_to_nat_usize"), live_w))
            if s_head == _constant("PrefixModel") and len(s_args) == 4:
                cnt_w = self.whnf(s_args[3])
                if cnt_w.kind == "int":
                    self.tick(True)
                    return _term("nat", value=max(0, cast("int", cnt_w.value)))
                self.tick(True)
                return self.whnf(_app(_constant("int_to_nat_usize"), cnt_w))
            return None
        if name == "Seq_At" and len(arguments) == 4:
            elem, default_val, seq_term, idx_term = arguments
            s_w = self.whnf(seq_term)
            i_w = self.whnf(idx_term)
            elems = self._extract_seq_elements(s_w)
            if elems is not None and i_w.kind == "nat":
                idx_val = cast("int", i_w.value)
                self.tick(True)
                if 0 <= idx_val < len(elems):
                    return self.whnf(elems[idx_val])
                return self.whnf(default_val)
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Seq_Update") and len(s_args) == 4:
                upd_idx = self.whnf(s_args[2])
                if self.convertible(upd_idx, i_w):
                    self.tick(True)
                    return self.whnf(s_args[3])
                if upd_idx.kind == "nat" and i_w.kind == "nat" and upd_idx.value != i_w.value:
                    self.tick(True)
                    return self.whnf(_apps(_constant("Seq_At"), elem, default_val, s_args[1], i_w))
            if s_head == _constant("Seq_Append") and len(s_args) == 3:
                r_elems = self._extract_seq_elements(s_args[2])
                if r_elems is not None and len(r_elems) == 1:
                    c_left = self.whnf(_apps(_constant("Seq_Count"), elem, s_args[1]))
                    if self.convertible(i_w, c_left):
                        self.tick(True)
                        return self.whnf(r_elems[0])
            i_head, i_args = self.spine(i_w)
            if s_head == _constant("Span_Model") and len(s_args) == 2:
                if i_w.kind == "nat":
                    idx_u = _int_term(_INT_SPECS["usize"], cast("int", i_w.value))
                    self.tick(True)
                    return self.whnf(_apps(_constant("Span_Read"), s_args[0], s_args[1], idx_u))
                if i_head == _constant("int_to_nat_usize") and len(i_args) == 1:
                    self.tick(True)
                    return self.whnf(_apps(_constant("Span_Read"), s_args[0], s_args[1], i_args[0]))
            if s_head == _constant("Slots_Model") and len(s_args) == 3:
                if i_w.kind == "nat":
                    idx_u = _int_term(_INT_SPECS["usize"], cast("int", i_w.value))
                    self.tick(True)
                    return self.whnf(
                        _apps(_constant("Slots_Read"), s_args[0], s_args[1], default_val, s_args[2], idx_u)
                    )
                if i_head == _constant("int_to_nat_usize") and len(i_args) == 1:
                    self.tick(True)
                    return self.whnf(
                        _apps(_constant("Slots_Read"), s_args[0], s_args[1], default_val, s_args[2], i_args[0])
                    )
            return None
        if name == "Seq_Update" and len(arguments) == 4:
            elem, seq_term, idx_term, val_term = arguments
            s_w = self.whnf(seq_term)
            i_w = self.whnf(idx_term)
            elems = self._extract_seq_elements(s_w)
            if elems is not None and i_w.kind == "nat":
                idx_val = cast("int", i_w.value)
                self.tick(True)
                updated = list(elems)
                if 0 <= idx_val < len(updated):
                    updated[idx_val] = val_term
                return self._build_seq_term(elem, updated)
            return None
        if name == "Seq_Append" and len(arguments) == 3:
            elem, left_seq, right_seq = arguments
            l_w = self.whnf(left_seq)
            r_w = self.whnf(right_seq)
            l_elems = self._extract_seq_elements(l_w)
            r_elems = self._extract_seq_elements(r_w)
            if l_elems is not None and r_elems is not None:
                self.tick(True)
                return self._build_seq_term(elem, [*l_elems, *r_elems])
            if l_elems is not None and len(l_elems) == 0:
                self.tick(True)
                return r_w
            if r_elems is not None and len(r_elems) == 0:
                self.tick(True)
                return l_w
            return None
        if name == "Seq_Take" and len(arguments) == 3:
            elem, seq_term, count_term = arguments
            s_w = self.whnf(seq_term)
            c_w = self.whnf(count_term)
            if c_w.kind == "nat" and cast("int", c_w.value) == 0:
                self.tick(True)
                return _app(_constant("Seq_Empty"), elem)
            elems = self._extract_seq_elements(s_w)
            if elems is not None and c_w.kind == "nat":
                cnt = cast("int", c_w.value)
                self.tick(True)
                return self._build_seq_term(elem, elems[: max(0, cnt)])
            cnt_seq = self.whnf(_apps(_constant("Seq_Count"), elem, s_w))
            if self.convertible(cnt_seq, c_w):
                self.tick(True)
                return s_w
            return None
        if name == "Seq_Skip" and len(arguments) == 3:
            elem, seq_term, count_term = arguments
            s_w = self.whnf(seq_term)
            c_w = self.whnf(count_term)
            if c_w.kind == "nat" and cast("int", c_w.value) == 0:
                self.tick(True)
                return s_w
            elems = self._extract_seq_elements(s_w)
            if elems is not None and c_w.kind == "nat":
                cnt = cast("int", c_w.value)
                self.tick(True)
                return self._build_seq_term(elem, elems[max(0, cnt) :])
            return None
        if name == "Seq_Slice" and len(arguments) == 4:
            elem, seq_term, off_term, cnt_term = arguments
            self.tick(True)
            skipped = _apps(_constant("Seq_Skip"), elem, seq_term, off_term)
            return self.whnf(_apps(_constant("Seq_Take"), elem, skipped, cnt_term))
        if name == "Seq_Contains" and len(arguments) == 3:
            _elem, seq_term, val_term = arguments
            s_w = self.whnf(seq_term)
            elems = self._extract_seq_elements(s_w)
            if elems is not None:
                if len(elems) == 0:
                    self.tick(True)
                    return _term("bool", value=0)
                all_decided = True
                for item in elems:
                    if self.convertible(item, val_term):
                        self.tick(True)
                        return _term("bool", value=1)
                    item_w = self.whnf(item)
                    val_w = self.whnf(val_term)
                    if item_w.kind != val_w.kind or item_w.kind not in {"nat", "int", "bool", "char"}:
                        all_decided = False
                if all_decided:
                    self.tick(True)
                    return _term("bool", value=0)
            return None
        if name in {"Seq_All", "Seq_Any"} and len(arguments) == 3:
            _elem, seq_term, pred_term = arguments
            s_w = self.whnf(seq_term)
            elems = self._extract_seq_elements(s_w)
            if elems is not None:
                is_all = name == "Seq_All"
                if len(elems) == 0:
                    self.tick(True)
                    return _term("bool", value=1 if is_all else 0)
                all_decided = True
                for item in elems:
                    res = self.whnf(_app(pred_term, item))
                    if res.kind == "bool":
                        if is_all and res.value == 0:
                            self.tick(True)
                            return _term("bool", value=0)
                        if not is_all and res.value == 1:
                            self.tick(True)
                            return _term("bool", value=1)
                    else:
                        all_decided = False
                if all_decided:
                    self.tick(True)
                    return _term("bool", value=1 if is_all else 0)
            return None
        if name == "Seq_Eq" and len(arguments) == 4:
            _elem, eq_fn, left_seq, right_seq = arguments
            l_w = self.whnf(left_seq)
            r_w = self.whnf(right_seq)
            if self.convertible(l_w, r_w):
                self.tick(True)
                return _term("bool", value=1)
            l_elems = self._extract_seq_elements(l_w)
            r_elems = self._extract_seq_elements(r_w)
            if l_elems is not None and r_elems is not None:
                if len(l_elems) != len(r_elems):
                    self.tick(True)
                    return _term("bool", value=0)
                for lx, rx in zip(l_elems, r_elems, strict=True):
                    step = self.whnf(_apps(eq_fn, lx, rx))
                    if step.kind == "bool":
                        if step.value == 0:
                            self.tick(True)
                            return _term("bool", value=0)
                    elif not self.convertible(lx, rx):
                        return None
                self.tick(True)
                return _term("bool", value=1)
            return None
        return None

    def _whnf_slots_op(self: _Elaborator, name: str, arguments: list[_Term]) -> _Term | None:
        if name in {"Slots_CanRead", "Slots_CanWrite"} and len(arguments) == 3:
            elem, cap, s = arguments
            s_w = self.whnf(s)
            head, args = self.spine(s_w)
            if head in {_constant("Slots_Write"), _constant("Slots_TransferSource"), _constant("Slots_TransferDest")} and len(args) >= 3:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, cap, args[2]))
            if head == _constant("Slots_CopyRepresentation") and len(args) == 6:
                self.tick(True)
                return self.whnf(_apps(_constant(name), elem, args[2], args[4]))
            tag_t = self.whnf(_apps(_constant("Slots_Tag"), elem, cap, s_w))
            perm_const = "Slots_PermRead" if name == "Slots_CanRead" else "Slots_PermWrite"
            perm_t = self.whnf(_apps(_constant(perm_const), elem, cap, s_w))
            if tag_t.kind == "bool" and perm_t.kind == "bool":
                self.tick(True)
                return _term("bool", value=1 if (tag_t.value == 1 and perm_t.value == 1) else 0)
            return None
        if name in {
            "Slots_Base",
            "Slots_LiveCount",
            "Slots_Tag",
            "Slots_PermRead",
            "Slots_PermWrite",
            "Slots_RepModel",
            "Slots_Model",
        } and len(arguments) == 3:
            elem, cap, s = arguments
            s_w = self.whnf(s)
            head, args = self.spine(s_w)
            if head == _constant("Slots_Mk") and len(args) == 9:
                field_map = {
                    "Slots_Base": 2,
                    "Slots_LiveCount": 3,
                    "Slots_Tag": 4,
                    "Slots_PermRead": 5,
                    "Slots_PermWrite": 6,
                    "Slots_RepModel": 7,
                    "Slots_Model": 8,
                }
                self.tick(True)
                return self.whnf(args[field_map[name]])
            if head == _constant("Slots_AllocVacant") and len(args) == 3:
                self.tick(True)
                if name == "Slots_Base":
                    return self.whnf(args[2])
                if name == "Slots_LiveCount":
                    return _int_term(_INT_SPECS["usize"], 0)
                if name in {"Slots_Tag", "Slots_PermRead", "Slots_PermWrite"}:
                    return _term("bool", value=1)
                if name in {"Slots_RepModel", "Slots_Model"}:
                    return _app(_constant("Seq_Empty"), elem)
            if head == _constant("Slots_Write") and len(args) == 5:
                inner_s = args[2]
                idx_t = self.whnf(args[3])
                val_t = args[4]
                if name in {"Slots_Base", "Slots_Tag", "Slots_PermRead", "Slots_PermWrite"}:
                    self.tick(True)
                    return self.whnf(_apps(_constant(name), elem, cap, inner_s))
                inner_live = self.whnf(_apps(_constant("Slots_LiveCount"), elem, cap, inner_s))
                if name == "Slots_LiveCount":
                    if idx_t.kind == "int" and inner_live.kind == "int":
                        i_val = cast("int", idx_t.value)
                        l_val = cast("int", inner_live.value)
                        self.tick(True)
                        return _int_term(_INT_SPECS["usize"], max(l_val, i_val + 1))
                    self.tick(True)
                    return self.whnf(
                        _apps(_constant("int_add_usize"), idx_t, _int_term(_INT_SPECS["usize"], 1))
                    )
                if name in {"Slots_RepModel", "Slots_Model"}:
                    inner_model = self.whnf(_apps(_constant(name), elem, cap, inner_s))
                    elems = self._extract_seq_elements(inner_model)
                    if idx_t.kind == "int" and inner_live.kind == "int":
                        i_val = cast("int", idx_t.value)
                        l_val = cast("int", inner_live.value)
                        if elems is not None:
                            if i_val == l_val and i_val == len(elems):
                                self.tick(True)
                                return self._build_seq_term(elem, [*elems, val_t])
                            if 0 <= i_val < len(elems):
                                updated = list(elems)
                                updated[i_val] = val_t
                                self.tick(True)
                                return self._build_seq_term(elem, updated)
                    self.tick(True)
                    return self.whnf(
                        _apps(
                            _constant("Seq_Append"),
                            elem,
                            inner_model,
                            _apps(_constant("Seq_Singleton"), elem, val_t),
                        )
                    )
            if head == _constant("Slots_CopyRepresentation") and len(args) == 6:
                src_cap, _dst_cap, src_s, dst_s, _cnt = args[1], args[2], args[3], args[4], args[5]
                if name in {"Slots_Base", "Slots_Tag", "Slots_PermRead", "Slots_PermWrite"}:
                    self.tick(True)
                    return self.whnf(_apps(_constant(name), elem, cap, dst_s))
                if name == "Slots_LiveCount":
                    self.tick(True)
                    return _int_term(_INT_SPECS["usize"], 0)
                if name == "Slots_RepModel":
                    self.tick(True)
                    return self.whnf(_apps(_constant("PrefixModel"), elem, src_cap, src_s, _cnt))
                self.tick(True)
                return _app(_constant("Seq_Empty"), elem)
            if head == _constant("Slots_TransferSource") and len(args) == 4:
                inner_s = args[2]
                if name in {"Slots_Base", "Slots_Tag", "Slots_PermRead", "Slots_PermWrite"}:
                    self.tick(True)
                    return self.whnf(_apps(_constant(name), elem, cap, inner_s))
                if name == "Slots_LiveCount":
                    self.tick(True)
                    return _int_term(_INT_SPECS["usize"], 0)
                if name in {"Slots_RepModel", "Slots_Model"}:
                    self.tick(True)
                    return _app(_constant("Seq_Empty"), elem)
            if head == _constant("Slots_TransferDest") and len(args) == 4:
                inner_s = args[2]
                cnt_t = args[3]
                if name in {"Slots_Base", "Slots_Tag", "Slots_PermRead", "Slots_PermWrite"}:
                    self.tick(True)
                    return self.whnf(_apps(_constant(name), elem, cap, inner_s))
                if name == "Slots_LiveCount":
                    self.tick(True)
                    return self.whnf(cnt_t)
                if name in {"Slots_RepModel", "Slots_Model"}:
                    self.tick(True)
                    return self.whnf(_apps(_constant("Slots_RepModel"), elem, cap, inner_s))
            return None
        if name == "PrefixModel" and len(arguments) == 4:
            elem, cap, s, cnt = arguments
            s_w = self.whnf(s)
            cnt_w = self.whnf(cnt)
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Slots_TransferDest") and len(s_args) == 4 and self.convertible(s_args[3], cnt_w):
                self.tick(True)
                return self.whnf(_apps(_constant("Slots_Model"), elem, cap, s_w))
            live_w = self.whnf(_apps(_constant("Slots_LiveCount"), elem, cap, s_w))
            model_w = self.whnf(_apps(_constant("Slots_Model"), elem, cap, s_w))
            elems = self._extract_seq_elements(model_w)
            if self.convertible(live_w, cnt_w) and elems is not None:
                self.tick(True)
                return model_w
            if elems is not None and cnt_w.kind == "int":
                k = max(0, cast("int", cnt_w.value))
                self.tick(True)
                return self._build_seq_term(elem, elems[:k])
            return None
        if name == "Slots_Read" and len(arguments) == 5:
            elem, cap, default_val, s, idx = arguments
            s_w = self.whnf(s)
            idx_w = self.whnf(idx)
            head, args = self.spine(s_w)
            if head == _constant("Slots_Write") and len(args) == 5:
                w_idx = self.whnf(args[3])
                if self.convertible(w_idx, idx_w):
                    self.tick(True)
                    return self.whnf(args[4])
                if w_idx.kind == "int" and idx_w.kind == "int" and w_idx.value != idx_w.value:
                    self.tick(True)
                    return self.whnf(_apps(_constant("Slots_Read"), elem, cap, default_val, args[2], idx_w))
            if head == _constant("Slots_TransferDest") and len(args) == 4:
                inner_w = self.whnf(args[2])
                i_head, i_args = self.spine(inner_w)
                if i_head == _constant("Slots_CopyRepresentation") and len(i_args) == 6:
                    self.tick(True)
                    return self.whnf(_apps(_constant("Slots_Read"), elem, i_args[1], default_val, i_args[3], idx_w))
            model_w = self.whnf(_apps(_constant("Slots_Model"), elem, cap, s_w))
            elems = self._extract_seq_elements(model_w)
            if elems is not None and idx_w.kind == "int":
                i_val = cast("int", idx_w.value)
                if 0 <= i_val < len(elems):
                    self.tick(True)
                    return self.whnf(elems[i_val])
            return None
        if name == "Slots_LivePrefix" and len(arguments) == 4:
            elem, cap, s, cnt = arguments
            s_w = self.whnf(s)
            cnt_w = self.whnf(cnt)
            cap_w = self.whnf(cap)
            s_head, s_args = self.spine(s_w)
            if s_head == _constant("Slots_TransferDest") and len(s_args) == 4 and self.convertible(s_args[3], cnt_w):
                self.tick(True)
                return _term("bool", value=1)
            if (
                s_head in {_constant("Slots_TransferSource"), _constant("Slots_AllocVacant")}
                and cnt_w.kind == "int"
                and cast("int", cnt_w.value) == 0
            ):
                self.tick(True)
                return _term("bool", value=1)
            live_w = self.whnf(_apps(_constant("Slots_LiveCount"), elem, cap_w, s_w))
            can_read = self.whnf(_apps(_constant("Slots_CanRead"), elem, cap_w, s_w))
            if can_read.kind == "bool" and can_read.value == 0:
                self.tick(True)
                return _term("bool", value=0)
            if self.convertible(live_w, cnt_w):
                if cnt_w.kind == "int" and cap_w.kind in {"int", "nat"}:
                    c_val = cast("int", cnt_w.value)
                    cap_val = cast("int", cap_w.value)
                    if can_read.kind == "bool" and can_read.value == 1:
                        self.tick(True)
                        return _term("bool", value=1 if 0 <= c_val <= cap_val else 0)
            elif live_w.kind == "int" and cnt_w.kind == "int" and live_w.value != cnt_w.value:
                self.tick(True)
                return _term("bool", value=0)
            return None
        if name == "Slots_VacantRange" and len(arguments) == 5:
            elem, cap, s, start, end = arguments
            s_w = self.whnf(s)
            start_w = self.whnf(start)
            end_w = self.whnf(end)
            cap_w = self.whnf(cap)
            cap_u_w = self.whnf(self._slots_cap_usize_term(cap_w))
            s_head, s_args = self.spine(s_w)
            if (
                s_head == _constant("Slots_AllocVacant")
                and len(s_args) == 3
                and start_w.kind == "int"
                and cast("int", start_w.value) == 0
                and (self.convertible(end_w, cap_u_w) or (end_w.kind == "int" and cast("int", end_w.value) == 0))
            ):
                self.tick(True)
                return _term("bool", value=1)
            if (
                s_head == _constant("Slots_TransferSource")
                and len(s_args) == 4
                and start_w.kind == "int"
                and cast("int", start_w.value) == 0
                and (
                    self.convertible(end_w, s_args[3])
                    or self.convertible(end_w, cap_u_w)
                    or (end_w.kind == "int" and cast("int", end_w.value) == 0)
                )
            ):
                self.tick(True)
                return _term("bool", value=1)
            if (
                s_head == _constant("Slots_TransferDest")
                and len(s_args) == 4
                and self.convertible(start_w, s_args[3])
                and (self.convertible(end_w, cap_u_w) or self.convertible(end_w, s_args[3]))
            ):
                self.tick(True)
                return _term("bool", value=1)
            live_w = self.whnf(_apps(_constant("Slots_LiveCount"), elem, cap_w, s_w))
            can_write = self.whnf(_apps(_constant("Slots_CanWrite"), elem, cap_w, s_w))
            if can_write.kind == "bool" and can_write.value == 0:
                self.tick(True)
                return _term("bool", value=0)
            if (
                live_w.kind == "int"
                and start_w.kind == "int"
                and end_w.kind == "int"
                and cap_w.kind in {"int", "nat"}
                and can_write.kind == "bool"
                and can_write.value == 1
            ):
                l_val = cast("int", live_w.value)
                st_val = cast("int", start_w.value)
                en_val = cast("int", end_w.value)
                cp_val = cast("int", cap_w.value)
                self.tick(True)
                return _term("bool", value=1 if (l_val <= st_val <= en_val <= cp_val) else 0)
            return None
        if name == "Slots_Disjoint" and len(arguments) == 5:
            elem, cap_a, cap_b, s_a, s_b = arguments
            sa_w = self.whnf(s_a)
            sb_w = self.whnf(s_b)
            ca_w = self.whnf(cap_a)
            cb_w = self.whnf(cap_b)
            ba_w = self.whnf(_apps(_constant("Slots_Base"), elem, ca_w, sa_w))
            bb_w = self.whnf(_apps(_constant("Slots_Base"), elem, cb_w, sb_w))
            if (
                ca_w.kind in {"int", "nat"}
                and cb_w.kind in {"int", "nat"}
                and ba_w.kind == "int"
                and bb_w.kind == "int"
            ):
                ba_val = cast("int", ba_w.value)
                bb_val = cast("int", bb_w.value)
                ca_val = cast("int", ca_w.value)
                cb_val = cast("int", cb_w.value)
                disjoint = (ba_val + ca_val <= bb_val) or (bb_val + cb_val <= ba_val)
                self.tick(True)
                return _term("bool", value=1 if disjoint else 0)
            return None
        if name == "Slots_RepEqual" and len(arguments) == 6:
            elem, cap_a, cap_b, s_a, s_b, cnt = arguments
            sa_w = self.whnf(s_a)
            sb_w = self.whnf(s_b)
            cnt_w = self.whnf(cnt)
            head_a, args_a = self.spine(sa_w)
            if (
                head_a == _constant("Slots_CopyRepresentation")
                and len(args_a) == 6
                and self.convertible(args_a[1], cap_b)
                and self.convertible(args_a[3], sb_w)
                and self.convertible(args_a[5], cnt_w)
            ):
                self.tick(True)
                return _term("bool", value=1)
            rep_a = self.whnf(_apps(_constant("Slots_RepModel"), elem, cap_a, sa_w))
            mod_b = self.whnf(_apps(_constant("Slots_Model"), elem, cap_b, sb_w))
            if self.convertible(rep_a, mod_b):
                self.tick(True)
                return _term("bool", value=1)
            return None
        if name == "Slots_TransferType" and len(arguments) == 6:
            elem, src_cap, dst_cap, src_s, dst_s, cnt = arguments
            self.tick(True)
            src_next = _apps(_constant("Slots_TransferSource"), elem, src_cap, src_s, cnt)
            dst_next = _apps(_constant("Slots_TransferDest"), elem, dst_cap, dst_s, cnt)
            return _term(
                "pair",
                _apps(_constant("Slots"), elem, src_cap),
                _apps(_constant("Slots"), elem, dst_cap),
                src_next,
                dst_next,
            )
        return None

    @staticmethod
    def _peel_nat(term: _Term) -> tuple[str, _Term | None]:
        if term.kind == "nat":
            amount = cast("int", term.value)
            return ("zero", None) if amount == 0 else ("succ", _term("nat", value=amount - 1))
        if term.kind == "app" and term.args[0] == _constant("Succ"):
            return "succ", term.args[1]
        return "other", None

    @staticmethod
    def spine(term: _Term) -> tuple[_Term, list[_Term]]:
        arguments: list[_Term] = []
        while term.kind == "app":
            arguments.append(term.args[1])
            term = term.args[0]
        return term, list(reversed(arguments))
