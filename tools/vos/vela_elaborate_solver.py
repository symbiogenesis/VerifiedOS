# SPDX-License-Identifier: Apache-2.0
"""Bounded arithmetic, comparison, and Boolean precondition solver for Vela elaboration."""

from typing import TYPE_CHECKING, cast

from vos.vela_elaborate_types import (
    _BOOL,
    _CHAR,
    _INT_SPECS,
    _NAT,
    _U8,
    MAX_NAT_BITS,
    Node,
    _app,
    _apps,
    _Binding,
    _constant,
    _int_term,
    _IntSpec,
    _Term,
    _term,
)

if TYPE_CHECKING:
    from vos.vela_elaborate import _Elaborator


class _SolverMixin:
    def _fact_bool_terms(self: _Elaborator, facts: tuple[_Binding, ...] | list[_Binding], environment: dict[str, _Binding]) -> list[_Term]:
        terms: list[_Term] = []
        all_bindings = [
            *facts,
            *(
                b
                for b in environment.values()
                if (self.current_rec_var is None or b.term != self.current_rec_var)
                and self._is_prop_type(b.type)
            ),
        ]
        for fact in all_bindings:
            extracted = self._extract_equality(fact.type)
            if extracted is not None:
                eq_type, u, v = extracted
                eq_type_w = self.whnf(eq_type)
                if eq_type_w == _BOOL:
                    u_w = self.whnf(u)
                    v_w = self.whnf(v)
                    if v_w == _term("bool", value=1):
                        terms.append(u)
                    elif u_w == _term("bool", value=1):
                        terms.append(v)
                    elif v_w == _term("bool", value=0):
                        terms.append(_app(_constant("!"), u))
                    elif u_w == _term("bool", value=0):
                        terms.append(_app(_constant("!"), v))
                elif eq_type_w == _CHAR:
                    terms.append(_apps(_constant("char_eq"), u, v))
                elif self._int_spec(eq_type_w) is not None or eq_type_w == _NAT:
                    spec = self._int_spec(eq_type_w)
                    eq_const = f"int_eq_{spec.name}" if spec is not None else "eq_nat"
                    terms.append(_apps(_constant(eq_const), u, v))
        for vname, b in environment.items():
            if self.current_rec_var is not None and b.term == self.current_rec_var:
                continue
            r_head, r_targs = self.spine(self.whnf(b.type))
            if (
                r_head.kind == "const"
                and isinstance(r_head.value, str)
                and r_head.value in self.records_by_type
            ):
                rinfo = self.records_by_type[r_head.value]
                lifted = self.lifted_invariants.get(vname, set())
                for inv in rinfo.invariants:
                    if inv.name in lifted:
                        continue
                    inst_ty = self._instantiate_record_type(rinfo, r_targs, inv.type)
                    inst_ty = self.substitute(inst_ty, cast("int", inv.self_var.value), b.term)
                    if self.whnf(inst_ty) == _BOOL:
                        inst_t = self._instantiate_record_type(rinfo, r_targs, inv.term)
                        inst_t = self.substitute(inst_t, cast("int", inv.self_var.value), b.term)
                        terms.append(inst_t)
        return terms

    def _negate_bool_term(self: _Elaborator, term: _Term) -> _Term:
        w = self.whnf(term)
        head, args = self.spine(w)
        if head == _constant("!") and len(args) == 1:
            return args[0]
        if head.kind == "const" and isinstance(head.value, str) and len(args) == 2:
            cname = head.value
            flip_nat = {
                "<": ">=",
                "<=": ">",
                ">": "<=",
                ">=": "<",
                "eq_nat": "ne_nat",
                "ne_nat": "eq_nat",
                "char_lt": "char_ge",
                "char_le": "char_gt",
                "char_gt": "char_le",
                "char_ge": "char_lt",
                "char_eq": "char_ne",
                "char_ne": "char_eq",
                "eq_bool": "ne_bool",
                "ne_bool": "eq_bool",
                "eq_unit": "ne_unit",
                "ne_unit": "eq_unit",
            }
            if cname in flip_nat:
                return _apps(_constant(flip_nat[cname]), args[0], args[1])
            if cname.startswith("int_"):
                prefix, spec_name = cname.rsplit("_", 1)
                if spec_name in _INT_SPECS:
                    op = prefix[4:]
                    flip_int = {"lt": "ge", "le": "gt", "gt": "le", "ge": "lt", "eq": "ne", "ne": "eq"}
                    if op in flip_int:
                        return _apps(_constant(f"int_{flip_int[op]}_{spec_name}"), args[0], args[1])
        return _app(_constant("!"), w)

    def _expand_bool_facts(self: _Elaborator, raw_facts: list[_Term]) -> list[_Term]:
        expanded: list[_Term] = []
        queue = list(raw_facts)
        while queue:
            item = self.whnf(queue.pop(0))
            if item.kind == "if" and len(item.args) == 4:
                cond_t = item.args[1]
                then_w = self.whnf(item.args[2])
                else_w = self.whnf(item.args[3])
                if then_w == _term("bool", value=0):
                    queue.append(self._negate_bool_term(cond_t))
                    queue.append(else_w)
                    continue
                if else_w == _term("bool", value=0):
                    queue.append(cond_t)
                    queue.append(then_w)
                    continue
            head, args = self.spine(item)
            if head == _constant("&&") and len(args) == 2:
                queue.append(args[0])
                queue.append(args[1])
                continue
            if head == _constant("!") and len(args) == 1:
                inner = self.whnf(args[0])
                i_head, i_args = self.spine(inner)
                if i_head == _constant("||") and len(i_args) == 2:
                    queue.append(self._negate_bool_term(i_args[0]))
                    queue.append(self._negate_bool_term(i_args[1]))
                    continue
                neg = self._negate_bool_term(inner)
                if neg != item:
                    queue.append(neg)
                    continue
            if item not in expanded:
                expanded.append(item)
                if head == _constant("Slots_LivePrefix") and len(args) == 4:
                    elem, cap, s, cnt = args
                    queue.append(_apps(_constant("Slots_CanRead"), elem, cap, s))
                    if not self._is_readonly_span(s):
                        queue.append(_apps(_constant("Slots_CanWrite"), elem, cap, s))
                    queue.append(_apps(_constant("int_eq_usize"), _apps(_constant("Slots_LiveCount"), elem, cap, s), cnt))
                    queue.append(_apps(_constant("int_le_usize"), cnt, self._slots_cap_usize_term(cap)))
                elif head == _constant("Slots_VacantRange") and len(args) == 5:
                    elem, cap, s, start, end = args
                    queue.append(_apps(_constant("Slots_CanWrite"), elem, cap, s))
                    queue.append(_apps(_constant("Slots_CanRead"), elem, cap, s))
                    queue.append(_apps(_constant("int_le_usize"), _apps(_constant("Slots_LiveCount"), elem, cap, s), start))
                    queue.append(_apps(_constant("int_le_usize"), start, end))
                    queue.append(_apps(_constant("int_le_usize"), end, self._slots_cap_usize_term(cap)))
                elif head == _constant("Slots_CanWrite") and len(args) == 3:
                    queue.append(_apps(_constant("Slots_CanRead"), args[0], args[1], args[2]))
        changed = True
        while changed:
            changed = False
            for f_item in list(expanded):
                fh, fa = self.spine(f_item)
                if fh == _constant("==>") and len(fa) == 2:
                    ant = self.whnf(fa[0])
                    con = self.whnf(fa[1])
                    if ant in expanded and con not in expanded:
                        expanded.append(con)
                        changed = True
        return expanded

    def _parse_cmp_fact(self: _Elaborator, fact: _Term) -> tuple[str, _IntSpec | None, _Term, _Term] | None:
        w = self.whnf(fact)
        head, args = self.spine(w)
        if head.kind != "const" or not isinstance(head.value, str) or len(args) != 2:
            return None
        cname = head.value
        nat_map = {
            "<": "lt",
            "<=": "le",
            ">": "gt",
            ">=": "ge",
            "eq_nat": "eq",
            "ne_nat": "ne",
            "char_lt": "lt",
            "char_le": "le",
            "char_gt": "gt",
            "char_ge": "ge",
            "char_eq": "eq",
            "char_ne": "ne",
        }
        if cname in nat_map:
            return nat_map[cname], None, args[0], args[1]
        if cname.startswith("int_"):
            prefix, spec_name = cname.rsplit("_", 1)
            spec = _INT_SPECS.get(spec_name)
            op = prefix[4:]
            if spec is not None and op in {"lt", "le", "gt", "ge", "eq", "ne"}:
                return op, spec, args[0], args[1]
        return None

    def _term_bounds(
        self: _Elaborator,
        term: _Term,
        spec: _IntSpec | None,
        facts: list[_Term],
        depth: int = 0,
        visited: frozenset[_Term] = frozenset(),
    ) -> tuple[int, int, set[int]]:
        lo = spec.min_val if spec is not None else 0
        hi = spec.max_val if spec is not None else (1 << MAX_NAT_BITS) - 1
        ne_set: set[int] = set()
        w = self.whnf(term)
        if w.kind in {"int", "nat", "char"}:
            val = cast("int", w.value)
            return val, val, set()
        if w.kind == "var" and cast("int", w.value) in self.types and self.whnf(self.types[cast("int", w.value)]) == _CHAR:
            lo = max(lo, 0)
            hi = min(hi, 0x10FFFF)
        if depth > 2 or w in visited:
            return lo, hi, ne_set
        next_visited = visited | {w}
        head, args = self.spine(w)
        if head.kind == "const" and isinstance(head.value, str):
            cname = head.value
            if cname == "Succ" and len(args) == 1:
                s_lo, s_hi, _ = self._term_bounds(args[0], None, facts, depth + 1, next_visited)
                lo = max(lo, s_lo + 1)
                hi = min(hi, s_hi + 1)
            elif cname in {"char_to_nat", "char_to_u32"} and len(args) == 1:
                s_lo, s_hi, s_ne = self._term_bounds(args[0], None, facts, depth + 1, next_visited)
                lo = max(lo, s_lo, 0)
                hi = min(hi, s_hi, 0x10FFFF)
                ne_set.update(s_ne)
            elif cname == "char_from_u8" and len(args) == 1:
                s_lo, s_hi, s_ne = self._term_bounds(args[0], _INT_SPECS["u8"], facts, depth + 1, next_visited)
                lo = max(lo, s_lo, 0)
                hi = min(hi, s_hi, 255)
                ne_set.update(s_ne)
            elif cname.startswith("int_from_") and len(args) == 1:
                src_spec = _INT_SPECS[cname.split("_")[2]]
                s_lo, s_hi, s_ne = self._term_bounds(args[0], src_spec, facts, depth + 1, next_visited)
                lo = max(lo, s_lo)
                hi = min(hi, s_hi)
                ne_set.update(s_ne)
            elif cname.startswith("int_to_nat_") and len(args) == 1:
                src_spec = _INT_SPECS[cname.split("_")[3]]
                s_lo, s_hi, s_ne = self._term_bounds(args[0], src_spec, facts, depth + 1, next_visited)
                lo = max(lo, s_lo)
                hi = min(hi, s_hi)
                ne_set.update(s_ne)
            elif cname == "nat_to_usize" and len(args) == 1:
                s_lo, s_hi, s_ne = self._term_bounds(args[0], None, facts, depth + 1, next_visited)
                lo = max(lo, s_lo)
                hi = min(hi, s_hi)
                ne_set.update(s_ne)
            elif cname == "Seq_Count" and len(args) == 2:
                lo = max(lo, 0)
            elif spec is not None and len(args) == 2:
                if cname == f"int_and_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], spec, facts, depth + 1, next_visited)
                    if r_lo == r_hi and r_lo >= 0:
                        lo = max(lo, 0)
                        hi = min(hi, r_lo)
                    if l_lo == l_hi and l_lo >= 0:
                        lo = max(lo, 0)
                        hi = min(hi, l_lo)
                elif cname == f"int_rem_{spec.name}" and not spec.signed:
                    _, r_hi, _ = self._term_bounds(args[1], spec, facts, depth + 1, next_visited)
                    if r_hi > 0:
                        lo = max(lo, 0)
                        hi = min(hi, r_hi - 1)
                elif cname == f"int_shr_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], _INT_SPECS["usize"], facts, depth + 1, next_visited)
                    if 0 <= r_lo <= r_hi < spec.bits and (not spec.signed or l_lo >= 0):
                        lo = max(lo, max(0, l_lo) >> r_hi)
                        hi = min(hi, l_hi >> r_lo)
                elif cname == f"int_shl_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], _INT_SPECS["usize"], facts, depth + 1, next_visited)
                    if 0 <= r_lo <= r_hi < spec.bits and l_lo >= 0:
                        lo = max(lo, l_lo << r_lo)
                        hi = min(hi, l_hi << r_hi)
                elif cname == f"int_add_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], spec, facts, depth + 1, next_visited)
                    lo = max(lo, l_lo + r_lo)
                    hi = min(hi, l_hi + r_hi)
                elif cname == f"int_sub_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], spec, facts, depth + 1, next_visited)
                    lo = max(lo, l_lo - r_hi)
                    hi = min(hi, l_hi - r_lo)
                elif cname == f"int_mul_{spec.name}":
                    l_lo, l_hi, _ = self._term_bounds(args[0], spec, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], spec, facts, depth + 1, next_visited)
                    prods = (l_lo * r_lo, l_lo * r_hi, l_hi * r_lo, l_hi * r_hi)
                    lo = max(lo, min(prods))
                    hi = min(hi, max(prods))
            elif spec is None and len(args) == 2:
                if cname == "+":
                    l_lo, l_hi, _ = self._term_bounds(args[0], None, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], None, facts, depth + 1, next_visited)
                    lo = max(lo, l_lo + r_lo)
                    hi = min(hi, l_hi + r_hi)
                elif cname == "-":
                    l_lo, l_hi, _ = self._term_bounds(args[0], None, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], None, facts, depth + 1, next_visited)
                    lo = max(0, l_lo - r_hi)
                    hi = min(hi, max(0, l_hi - r_lo))
                elif cname == "*":
                    l_lo, l_hi, _ = self._term_bounds(args[0], None, facts, depth + 1, next_visited)
                    r_lo, r_hi, _ = self._term_bounds(args[1], None, facts, depth + 1, next_visited)
                    lo = max(lo, l_lo * r_lo)
                    hi = min(hi, l_hi * r_hi)
        uw = self._unwrap_numeric_subject(w)
        for fact in facts:
            parsed = self._parse_cmp_fact(fact)
            if parsed is None:
                continue
            f_op, f_spec, f_l, f_r = parsed
            ufl = self._unwrap_numeric_subject(f_l)
            ufr = self._unwrap_numeric_subject(f_r)
            if ufl == uw:
                r_lo, r_hi, _ = self._term_bounds(f_r, f_spec, facts, depth + 1, next_visited)
                if f_op == "lt":
                    hi = min(hi, r_hi - 1)
                elif f_op == "le":
                    hi = min(hi, r_hi)
                elif f_op == "gt":
                    lo = max(lo, r_lo + 1)
                elif f_op == "ge":
                    lo = max(lo, r_lo)
                elif f_op == "eq":
                    lo = max(lo, r_lo)
                    hi = min(hi, r_hi)
                elif f_op == "ne" and r_lo == r_hi:
                    ne_set.add(r_lo)
            elif ufr == uw:
                l_lo, l_hi, _ = self._term_bounds(f_l, f_spec, facts, depth + 1, next_visited)
                if f_op == "lt":
                    lo = max(lo, l_lo + 1)
                elif f_op == "le":
                    lo = max(lo, l_lo)
                elif f_op == "gt":
                    hi = min(hi, l_hi - 1)
                elif f_op == "ge":
                    hi = min(hi, l_hi)
                elif f_op == "eq":
                    lo = max(lo, l_lo)
                    hi = min(hi, l_hi)
                elif f_op == "ne" and l_lo == l_hi:
                    ne_set.add(l_lo)
        while lo in ne_set and lo <= hi:
            lo += 1
        while hi in ne_set and hi >= lo:
            hi -= 1
        return lo, hi, ne_set

    def _unwrap_numeric_subject(self: _Elaborator, term: _Term, *, normalize_lit: bool = True) -> _Term:
        curr = self.whnf(term)
        while curr.kind == "app":
            head, args = self.spine(curr)
            if (
                head.kind == "const"
                and isinstance(head.value, str)
                and len(args) == 1
                and (
                    head.value.startswith("int_to_nat_")
                    or head.value.startswith("int_from_")
                    or head.value in {"nat_to_usize", "char_to_nat", "char_to_u32", "char_from_u8"}
                )
            ):
                curr = self.whnf(args[0])
            elif (
                head.kind == "const"
                and isinstance(head.value, str)
                and len(args) == 2
                and (head.value == "+" or head.value.startswith("int_add_"))
            ):
                a0 = self._unwrap_numeric_subject(args[0], normalize_lit=False)
                a1 = self._unwrap_numeric_subject(args[1], normalize_lit=False)
                if a0.kind in {"int", "nat"} and a0.value == 0:
                    curr = a1
                elif a1.kind in {"int", "nat"} and a1.value == 0:
                    curr = a0
                else:
                    return _apps(head, a0, a1)
            else:
                break
        if normalize_lit and curr.kind in {"nat", "char"}:
            return _int_term(_INT_SPECS["usize"], cast("int", curr.value))
        return curr

    def _extract_base_and_offset_term(self: _Elaborator, term: _Term) -> tuple[_Term, _Term | None]:
        w = self._unwrap_numeric_subject(term)
        if w.kind == "app":
            head, args = self.spine(w)
            if (
                head.kind == "const"
                and isinstance(head.value, str)
                and len(args) == 2
                and (head.value == "+" or head.value.startswith("int_add_"))
            ):
                base_a, rem_a = self._extract_base_and_offset_term(args[0])
                if rem_a is None:
                    return base_a, args[1]
                return base_a, _apps(head, rem_a, args[1])
        return w, None

    def _same_numeric_subject(self: _Elaborator, a: _Term, b: _Term) -> bool:
        return self._unwrap_numeric_subject(a) == self._unwrap_numeric_subject(b)

    def _prove_comparison(
        self: _Elaborator, op_kind: str, spec: _IntSpec | None, lhs: _Term, rhs: _Term, facts: list[_Term]
    ) -> bool:
        wl = self.whnf(lhs)
        wr = self.whnf(rhs)
        if wl.kind in {"int", "nat", "char"} and wr.kind in {"int", "nat", "char"}:
            lv = cast("int", wl.value)
            rv = cast("int", wr.value)
            return (
                (op_kind == "lt" and lv < rv)
                or (op_kind == "le" and lv <= rv)
                or (op_kind == "gt" and lv > rv)
                or (op_kind == "ge" and lv >= rv)
                or (op_kind == "eq" and lv == rv)
                or (op_kind == "ne" and lv != rv)
            )
        uwl = self._unwrap_numeric_subject(wl)
        uwr = self._unwrap_numeric_subject(wr)
        if uwl == uwr and op_kind in {"le", "ge", "eq"}:
            return True
        for fact in facts:
            parsed = self._parse_cmp_fact(fact)
            if parsed is None:
                continue
            f_op, _, f_l, f_r = parsed
            ufl = self._unwrap_numeric_subject(f_l)
            ufr = self._unwrap_numeric_subject(f_r)
            if ufl == uwl and ufr == uwr:
                if op_kind == f_op:
                    return True
                if op_kind == "le" and f_op in {"lt", "eq"}:
                    return True
                if op_kind == "ge" and f_op in {"gt", "eq"}:
                    return True
                if op_kind == "ne" and f_op in {"lt", "gt"}:
                    return True
            if ufl == uwr and ufr == uwl:
                if op_kind == "lt" and f_op == "gt":
                    return True
                if op_kind == "le" and f_op in {"ge", "eq"}:
                    return True
                if op_kind == "gt" and f_op == "lt":
                    return True
                if op_kind == "ge" and f_op in {"le", "eq"}:
                    return True
                if op_kind == "eq" and f_op == "eq":
                    return True
                if op_kind == "ne" and f_op in {"ne", "lt", "gt"}:
                    return True
        l_lo, l_hi, l_ne = self._term_bounds(wl, spec, facts)
        r_lo, r_hi, r_ne = self._term_bounds(wr, spec, facts)
        if l_lo > l_hi or r_lo > r_hi:
            # Contradictory active facts (unreachable branch)
            return True
        if op_kind == "lt" and l_hi < r_lo:
            return True
        if op_kind == "le" and l_hi <= r_lo:
            return True
        if op_kind == "gt" and l_lo > r_hi:
            return True
        if op_kind == "ge" and l_lo >= r_hi:
            return True
        if op_kind == "eq" and l_lo == l_hi == r_lo == r_hi:
            return True
        if op_kind == "ne":
            if l_hi < r_lo or r_hi < l_lo:
                return True
            if r_lo == r_hi and r_lo in l_ne:
                return True
            if l_lo == l_hi and l_lo in r_ne:
                return True
        base_l, rem_l = self._extract_base_and_offset_term(wl)
        base_r, rem_r = self._extract_base_and_offset_term(wr)
        if self._same_numeric_subject(base_l, base_r) and (rem_l is not None or rem_r is not None):
            zero = _int_term(spec, 0) if spec is not None else _term("nat", value=0)
            off_l = zero if rem_l is None else rem_l
            off_r = zero if rem_r is None else rem_r
            return self._prove_comparison(op_kind, spec, off_l, off_r, facts)
        zero_t = _int_term(spec, 0) if spec is not None else _term("nat", value=0)
        head_l, args_l = self.spine(wl)
        head_r, args_r = self.spine(wr)
        is_sub_l = (
            head_l.kind == "const"
            and isinstance(head_l.value, str)
            and (head_l.value == "-" or head_l.value.startswith("int_sub_"))
            and len(args_l) == 2
        )
        is_sub_r = (
            head_r.kind == "const"
            and isinstance(head_r.value, str)
            and (head_r.value == "-" or head_r.value.startswith("int_sub_"))
            and len(args_r) == 2
        )
        if is_sub_l and self._same_numeric_subject(args_l[0], wr):
            if op_kind == "lt" and self._prove_comparison("gt", spec, args_l[1], zero_t, facts) and self._prove_comparison("gt", spec, args_l[0], zero_t, facts):
                return True
            if op_kind == "le" and self._prove_comparison("ge", spec, args_l[1], zero_t, facts):
                return True
        if is_sub_r and self._same_numeric_subject(wl, args_r[0]):
            if op_kind == "gt" and self._prove_comparison("gt", spec, args_r[1], zero_t, facts) and self._prove_comparison("gt", spec, args_r[0], zero_t, facts):
                return True
            if op_kind == "ge" and self._prove_comparison("ge", spec, args_r[1], zero_t, facts):
                return True
        if is_sub_l and is_sub_r and self._same_numeric_subject(args_l[0], args_r[0]):
            if op_kind == "lt" and self._prove_comparison("gt", spec, args_l[1], args_r[1], facts) and self._prove_comparison("lt", spec, args_r[1], args_l[0], facts):
                return True
            if op_kind == "le" and self._prove_comparison("ge", spec, args_l[1], args_r[1], facts):
                return True
            if op_kind == "gt" and self._prove_comparison("lt", spec, args_l[1], args_r[1], facts) and self._prove_comparison("lt", spec, args_l[1], args_l[0], facts):
                return True
            if op_kind == "ge" and self._prove_comparison("le", spec, args_l[1], args_r[1], facts):
                return True
        is_div_l = (
            head_l.kind == "const"
            and isinstance(head_l.value, str)
            and (head_l.value == "/" or head_l.value.startswith("int_div_"))
            and len(args_l) == 2
        )
        if is_div_l and self._same_numeric_subject(args_l[0], wr):
            two_t = _int_term(spec, 2) if spec is not None else _term("nat", value=2)
            if op_kind == "lt" and self._prove_comparison("ge", spec, args_l[1], two_t, facts) and self._prove_comparison("gt", spec, args_l[0], zero_t, facts):
                return True
            if op_kind == "le" and self._prove_comparison("ge", spec, args_l[1], _int_term(spec, 1) if spec is not None else _term("nat", value=1), facts):
                return True
        # Bounded transitive chaining over active comparison facts
        edges: dict[_Term, list[tuple[_Term, bool]]] = {}
        zero_subj = _int_term(_INT_SPECS["usize"], 0)
        if spec is None or not spec.signed:
            edges.setdefault(zero_subj, []).append((uwl, False))
            edges.setdefault(zero_subj, []).append((uwr, False))
            if is_sub_l:
                ua_l = self._unwrap_numeric_subject(args_l[0])
                b_lo, _, _ = self._term_bounds(args_l[1], spec, facts)
                a_lo, _, _ = self._term_bounds(args_l[0], spec, facts)
                edges.setdefault(uwl, []).append((ua_l, b_lo > 0 and a_lo > 0))
            if is_sub_r:
                ua_r = self._unwrap_numeric_subject(args_r[0])
                b_lo, _, _ = self._term_bounds(args_r[1], spec, facts)
                a_lo, _, _ = self._term_bounds(args_r[0], spec, facts)
                edges.setdefault(uwr, []).append((ua_r, b_lo > 0 and a_lo > 0))
            if is_div_l:
                ua_l = self._unwrap_numeric_subject(args_l[0])
                b_lo, _, _ = self._term_bounds(args_l[1], spec, facts)
                a_lo, _, _ = self._term_bounds(args_l[0], spec, facts)
                if b_lo >= 1:
                    edges.setdefault(uwl, []).append((ua_l, b_lo >= 2 and a_lo > 0))
        for fact in facts:
            parsed = self._parse_cmp_fact(fact)
            if parsed is None:
                continue
            f_op, f_spec, f_l, f_r = parsed
            ufl = self._unwrap_numeric_subject(f_l)
            ufr = self._unwrap_numeric_subject(f_r)
            if f_spec is None or not f_spec.signed:
                edges.setdefault(zero_subj, []).append((ufl, False))
                edges.setdefault(zero_subj, []).append((ufr, False))
            if f_op == "lt":
                edges.setdefault(ufl, []).append((ufr, True))
            elif f_op == "le":
                edges.setdefault(ufl, []).append((ufr, False))
            elif f_op == "gt":
                edges.setdefault(ufr, []).append((ufl, True))
            elif f_op == "ge":
                edges.setdefault(ufr, []).append((ufl, False))
            elif f_op == "eq":
                edges.setdefault(ufl, []).append((ufr, False))
                edges.setdefault(ufr, []).append((ufl, False))

        def can_reach(start_node: _Term, target_node: _Term, need_strict: bool) -> bool:
            frontier: list[tuple[_Term, bool, int]] = [(start_node, False, 0)]
            seen: dict[_Term, bool] = {start_node: False}
            while frontier:
                cur_n, has_strict, steps = frontier.pop(0)
                if cur_n == target_node and (has_strict or not need_strict):
                    return True
                if steps >= 4:
                    continue
                for nxt_n, edge_strict in edges.get(cur_n, ()):
                    nxt_strict = has_strict or edge_strict
                    if nxt_n not in seen or (nxt_strict and not seen[nxt_n]):
                        seen[nxt_n] = nxt_strict
                        frontier.append((nxt_n, nxt_strict, steps + 1))
            return False

        if op_kind == "lt" and can_reach(uwl, uwr, True):
            return True
        if op_kind == "le" and can_reach(uwl, uwr, False):
            return True
        if op_kind == "gt" and can_reach(uwr, uwl, True):
            return True
        if op_kind == "ge" and can_reach(uwr, uwl, False):
            return True
        if op_kind == "eq" and can_reach(uwl, uwr, False) and can_reach(uwr, uwl, False):
            return True
        if op_kind in {"le", "ge"}:
            add_side = uwl if op_kind == "le" else uwr
            bound_side = uwr if op_kind == "le" else uwl
            lh, la = self.spine(add_side)
            if lh == _constant("Succ") and len(la) == 1:
                if self._prove_comparison("lt", spec, la[0], bound_side, facts):
                    return True
            elif (
                lh.kind == "const"
                and isinstance(lh.value, str)
                and (lh.value == "+" or lh.value.startswith("int_add_"))
                and len(la) == 2
            ):
                if (
                    self.whnf(la[1]).kind in {"nat", "int"}
                    and self.whnf(la[1]).value == 1
                    and self._prove_comparison("lt", spec, la[0], bound_side, facts)
                ):
                    return True
                for fact in facts:
                    parsed = self._parse_cmp_fact(fact)
                    if parsed is None or parsed[0] not in {"le", "lt", "eq"}:
                        continue
                    _, _, f_l, f_r = parsed
                    fr_h, fr_a = self.spine(self.whnf(f_r))
                    if (
                        fr_h.kind == "const"
                        and isinstance(fr_h.value, str)
                        and (fr_h.value == "-" or fr_h.value.startswith("int_sub_"))
                        and len(fr_a) == 2
                        and self._same_numeric_subject(fr_a[0], bound_side)
                        and (
                            (self._same_numeric_subject(f_l, la[0]) and self._same_numeric_subject(fr_a[1], la[1]))
                            or (self._same_numeric_subject(f_l, la[1]) and self._same_numeric_subject(fr_a[1], la[0]))
                        )
                    ):
                        return True
        return bool(op_kind == "ne" and (can_reach(uwl, uwr, True) or can_reach(uwr, uwl, True)))

    def _prove_bool_precondition(self: _Elaborator, cond: _Term, environment: dict[str, _Binding]) -> bool:
        w = self.whnf(cond)
        if w == _term("bool", value=1):
            return True
        if w == _term("bool", value=0):
            return False
        facts = self._expand_bool_facts([*self.active_facts, *self._fact_bool_terms((), environment)])
        if w in facts or cond in facts:
            return True
        head, args = self.spine(w)
        if head == _constant("&&") and len(args) == 2:
            return self._prove_bool_precondition(args[0], environment) and self._prove_bool_precondition(
                args[1], environment
            )
        if head == _constant("||") and len(args) == 2:
            return self._prove_bool_precondition(args[0], environment) or self._prove_bool_precondition(
                args[1], environment
            )
        if head == _constant("==>") and len(args) == 2:
            self.active_facts.append(args[0])
            try:
                return self._prove_bool_precondition(args[1], environment)
            finally:
                self.active_facts.pop()
        if head == _constant("!") and len(args) == 1:
            neg = self._negate_bool_term(args[0])
            if neg != w:
                return self._prove_bool_precondition(neg, environment)
        if head == _constant("eq_unit") and len(args) == 2:
            return True
        if head == _constant("eq_bool") and len(args) == 2 and self.convertible(args[0], args[1]):
            return True
        if head == _constant("Seq_Eq") and len(args) == 4 and self.convertible(args[2], args[3]):
            return True
        if head == _constant("Span_Disjoint") and len(args) == 3:
            a_t, b_t = args[1], args[2]
            if _apps(_constant("Span_Disjoint"), _U8, b_t, a_t) in facts:
                return True
            ra, rb = self._root_span(a_t), self._root_span(b_t)
            if (ra, rb) != (a_t, b_t) and (
                _apps(_constant("Span_Disjoint"), _U8, ra, rb) in facts
                or _apps(_constant("Span_Disjoint"), _U8, rb, ra) in facts
            ):
                return True
        if head == _constant("Slots_Disjoint") and len(args) == 5:
            elem, cap_a, cap_b, a_t, b_t = args
            if _apps(_constant("Slots_Disjoint"), elem, cap_b, cap_a, b_t, a_t) in facts:
                return True
            ra, rb = self._root_span(a_t), self._root_span(b_t)
            if (ra, rb) != (a_t, b_t):
                for f_item in facts:
                    fh, fa = self.spine(f_item)
                    if fh == _constant("Slots_Disjoint") and len(fa) == 5:
                        fra, frb = self._root_span(fa[3]), self._root_span(fa[4])
                        if (fra == ra and frb == rb) or (fra == rb and frb == ra):
                            return True
        if head == _constant("Slots_LivePrefix") and len(args) == 4:
            elem, cap, s, cnt = args
            return (
                self._prove_bool_precondition(_apps(_constant("Slots_CanRead"), elem, cap, s), environment)
                and self._prove_bool_precondition(
                    _apps(_constant("int_eq_usize"), _apps(_constant("Slots_LiveCount"), elem, cap, s), cnt),
                    environment,
                )
                and self._prove_bool_precondition(
                    _apps(_constant("int_le_usize"), cnt, self._slots_cap_usize_term(cap)),
                    environment,
                )
            )
        if head == _constant("Slots_VacantRange") and len(args) == 5:
            elem, cap, s, start, end = args
            return (
                self._prove_bool_precondition(_apps(_constant("Slots_CanWrite"), elem, cap, s), environment)
                and self._prove_bool_precondition(
                    _apps(_constant("int_le_usize"), _apps(_constant("Slots_LiveCount"), elem, cap, s), start),
                    environment,
                )
                and self._prove_bool_precondition(_apps(_constant("int_le_usize"), start, end), environment)
                and self._prove_bool_precondition(
                    _apps(_constant("int_le_usize"), end, self._slots_cap_usize_term(cap)),
                    environment,
                )
            )
        if head == _constant("Seq_All") and len(args) == 3:
            elem, seq_t, pred_t = args
            s_head, s_args = self.spine(self.whnf(seq_t))
            if s_head in {_constant("Seq_Take"), _constant("Seq_Skip"), _constant("Seq_Slice")} and len(s_args) >= 2:
                parent_all = self.whnf(_apps(_constant("Seq_All"), elem, s_args[1], pred_t))
                if any(self.convertible(f_item, parent_all) for f_item in facts):
                    return True
            if s_head == _constant("Seq_Take") and len(s_args) == 3:
                parent_seq = s_args[1]
                k_term = self.whnf(s_args[2])
                k_head, k_args = self.spine(k_term)
                prev_k: _Term | None = None
                if (k_head == _constant("Succ") and len(k_args) == 1) or (
                    k_head == _constant("+") and len(k_args) == 2 and self.whnf(k_args[1]) == _term("nat", value=1)
                ):
                    prev_k = k_args[0]
                elif (
                    k_head == _constant("int_to_nat_usize")
                    and len(k_args) == 1
                ):
                    ih, ia = self.spine(self.whnf(k_args[0]))
                    if ih == _constant("int_add_usize") and len(ia) == 2 and self.whnf(ia[1]) == _int_term(_INT_SPECS["usize"], 1):
                        prev_k = _app(_constant("int_to_nat_usize"), ia[0])
                if prev_k is not None:
                    prev_take_all = self.whnf(
                        _apps(_constant("Seq_All"), elem, _apps(_constant("Seq_Take"), elem, parent_seq, prev_k), pred_t)
                    )
                    if any(self.convertible(f_item, prev_take_all) for f_item in facts):
                        d_val = self._default_term_for_type(elem)
                        at_term = _apps(_constant("Seq_At"), elem, d_val, parent_seq, prev_k)
                        step_cond = self.whnf(_app(pred_t, at_term))
                        if self._prove_bool_precondition(step_cond, environment):
                            return True
            for f_item in facts:
                fh, fa = self.spine(f_item)
                if fh == _constant("Seq_All") and len(fa) == 3 and self.convertible(fa[2], pred_t):
                    th, ta = self.spine(self.whnf(fa[1]))
                    if th == _constant("Seq_Take") and len(ta) == 3 and self.convertible(ta[1], seq_t):
                        cnt_seq = _apps(_constant("Seq_Count"), elem, seq_t)
                        if self._prove_comparison("eq", None, ta[2], cnt_seq, facts):
                            return True
        for f_item in facts:
            fh, fa = self.spine(f_item)
            if fh == _constant("Seq_All") and len(fa) == 3:
                all_elem, all_seq, all_pred = fa
                d_val = self._default_term_for_type(all_elem)
                # Check if w is an instance of all_pred(Seq_At(all_elem, d_val, all_seq, idx))
                for sub_t in self._collect_seq_at_terms(w):
                    sh, sa = self.spine(sub_t)
                    if sh == _constant("Seq_At") and len(sa) == 4 and self.convertible(sa[2], all_seq):
                        inst_pred = self.whnf(_app(all_pred, sub_t))
                        if inst_pred == w:
                            cnt_seq = _apps(_constant("Seq_Count"), all_elem, all_seq)
                            if self._prove_comparison("lt", None, sa[3], cnt_seq, facts):
                                return True
                    elif sh == _constant("Span_Read") and len(sa) == 3:
                        span_m = self.whnf(_apps(_constant("Span_Model"), sa[0], sa[1]))
                        if self.convertible(span_m, all_seq):
                            inst_pred = self.whnf(_app(all_pred, sub_t))
                            if inst_pred == w:
                                span_len = _apps(_constant("Span_Length"), sa[0], sa[1])
                                if self._prove_comparison("lt", _INT_SPECS["usize"], sa[2], span_len, facts):
                                    return True
                    elif sh == _constant("Slots_Read") and len(sa) == 5:
                        slots_m = self.whnf(_apps(_constant("Slots_Model"), sa[0], sa[1], sa[3]))
                        if self.convertible(slots_m, all_seq):
                            inst_pred = self.whnf(_app(all_pred, sub_t))
                            if inst_pred == w:
                                slots_live = _apps(_constant("Slots_LiveCount"), sa[0], sa[1], sa[3])
                                if self._prove_comparison("lt", _INT_SPECS["usize"], sa[4], slots_live, facts):
                                    return True
        parsed = self._parse_cmp_fact(w)
        if parsed is not None:
            op_kind, spec, lhs, rhs = parsed
            return self._prove_comparison(op_kind, spec, lhs, rhs, facts)
        return False

    def _collect_seq_at_terms(self: _Elaborator, term: _Term) -> list[_Term]:
        found: list[_Term] = []
        stack = [self.whnf(term)]
        visited: set[int] = set()
        while stack:
            cur = stack.pop()
            if id(cur) in visited:
                continue
            visited.add(id(cur))
            head, args = self.spine(cur)
            if head in {_constant("Seq_At"), _constant("Span_Read"), _constant("Slots_Read")}:
                found.append(cur)
            stack.extend(self.whnf(a) for a in args)
        return found

    def _check_precondition_term(
        self: _Elaborator, req: _Term, environment: dict[str, _Binding], site: Node | None
    ) -> None:
        req_type = self.whnf(self.infer(req))
        if req_type == _BOOL:
            if not self._prove_bool_precondition(req, environment):
                raise self.fail(
                    "type",
                    "call precondition ('requires' clause) could not be established from active facts",
                    site,
                )
            return
        self._prove_proposition(req, environment, (), site if site is not None else cast("Node", self.site))
