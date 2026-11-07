# SPDX-License-Identifier: Apache-2.0
"""Bounded equational reasoning, congruence closure, and proof-block elaboration for Vela."""

from typing import TYPE_CHECKING, cast

from vos.vela.ast import VelaError
from vos.vela.elaborate_types import (
    _BOOL,
    _CHAR,
    _INT_SPECS,
    _NAT,
    _PROP,
    _SORT,
    _UNIT,
    MAX_DEPTH,
    Node,
    _app,
    _apps,
    _Binding,
    _constant,
    _Meta,
    _Term,
    _term,
)

if TYPE_CHECKING:
    from vos.vela.elaborate import _Elaborator


class _ProofsMixin:
    def constant_value(self: _Elaborator, node: Node, environment: dict[str, _Binding]) -> _Binding:
        previous = self.static_forbidden
        # Retain the surrounding bindings while checking the whole initializer.
        # Fresh lambda/function locals are distinct from its runtime inputs.
        self.static_forbidden = (set() if previous is None else previous) | {
            id(binding) for binding in environment.values() if not binding.constant}
        try:
            value_type = self.type(self.node(node["type"]), environment)
            expected = self.whnf(value_type)
            int_spec = self._int_spec(expected)
            if expected not in {_NAT, _BOOL, _UNIT, _CHAR} and int_spec is None:
                raise self.fail("unsupported", "mathematical constants require Nat, bool or Unit", node)
            value = self.check(self.node(node["value"]), value_type, environment)
            self.complete(value)
            available = set().union(*(self.free(binding.term) for binding in environment.values()
                                      if binding.constant))
            dependencies = self.free(value)
            if not dependencies <= available:
                raise self.fail("type", "constant initializer is not a closed static value", node)
            if dependencies:
                return _Binding(_term("static", value_type, value), value_type, constant=True)
            normalized = self.whnf(value)
            if int_spec is not None:
                if normalized.kind != "int":
                    raise self.fail("inference", "constant initializer did not evaluate to an admitted static value", node)
                return _Binding(normalized, value_type, constant=True)
            kind = {_NAT: "nat", _BOOL: "bool", _UNIT: "unit", _CHAR: "char"}[expected]
            if normalized.kind != kind:
                raise self.fail("inference", "constant initializer did not evaluate to an admitted static value", node)
            if kind == "nat" and not 0 <= cast("int", normalized.value) <= self.natural_limit():
                raise self.fail("limit", "constant natural exceeds representation bound", node)
            return _Binding(normalized, value_type, constant=True)
        finally:
            self.static_forbidden = previous

    def _try_unify(self: _Elaborator, left: _Term, right: _Term) -> bool:
        saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        try:
            self.unify(left, right)
        except VelaError as error:
            if error.kind != "type":
                raise
            self.metas = saved
            return False
        else:
            return True

    def convertible(self: _Elaborator, left: _Term, right: _Term) -> bool:
        if left == right:
            return True
        return self._try_unify(left, right)

    def _match_meta_pattern(self: _Elaborator, pattern: _Term, target: _Term) -> bool:
        p = self.resolve(pattern)
        t = self.resolve(target)
        if p == t:
            return True
        if p.kind == "meta" or t.kind == "meta":
            return self._try_unify(p, t)
        if (
            p.kind == t.kind
            and p.value == t.value
            and len(p.args) == len(t.args)
            and p.kind not in {"pi", "lam", "let"}
        ):
            saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            if all(self._match_meta_pattern(pa, ta) for pa, ta in zip(p.args, t.args, strict=True)):
                return True
            self.metas = saved
        return self._try_unify(p, t)

    def _is_prop_type(self: _Elaborator, value_type: _Term) -> bool:
        if value_type in {_PROP, _NAT, _BOOL, _UNIT, _CHAR, _SORT}:
            return False
        if value_type.kind in {"const", "app"}:
            head, _ = self.spine(value_type)
            if head == _constant("Eq"):
                return True
            if (
                head.kind == "const"
                and isinstance(head.value, str)
                and (
                    head.value in _INT_SPECS
                    or head.value in {"Span", "Vec", "Fin", "TextBuilder", "Seq", "Slots"}
                    or head.value in self.records_by_type
                    or head.value in self.unions_by_type
                )
            ):
                return False
        return self.whnf(self.infer(value_type)) == _PROP

    def _extract_equality(self: _Elaborator, prop: _Term) -> tuple[_Term, _Term, _Term] | None:
        head, args = self.spine(self.resolve(prop))
        if head == _constant("Eq") and len(args) == 3:
            return args[0], args[1], args[2]
        head, args = self.spine(self.whnf(prop))
        if head == _constant("Eq") and len(args) == 3:
            return args[0], args[1], args[2]
        return None

    def _replace_subterm(
        self: _Elaborator, term: _Term, eq_type: _Term, u: _Term, z: _Term, depth: int = 0
    ) -> tuple[_Term, bool]:
        if depth > 6:
            return term, False
        term = self.resolve(term)
        if term == u or (
            depth <= 3 and self._try_unify(self.infer(term), eq_type) and self._try_unify(term, u)
        ):
            return z, True
        if term.kind not in {"pi", "lam", "let"} and term.args:
            new_args: list[_Term] = []
            any_rep = False
            for arg in term.args:
                n_arg, rep = self._replace_subterm(arg, eq_type, u, z, depth + 1)
                new_args.append(n_arg)
                any_rep = any_rep or rep
            if any_rep:
                return _Term(term.kind, term.value, tuple(new_args)), True
        if depth <= 2:
            whnf_term = self.whnf(term)
            if whnf_term != term and whnf_term.kind != "if":
                return self._replace_subterm(whnf_term, eq_type, u, z, depth + 1)
        return term, False

    def _try_congruence(
        self: _Elaborator,
        goal_type: _Term,
        lhs: _Term,
        rhs: _Term,
        eq_type: _Term,
        u: _Term,
        v: _Term,
        proof_term: _Term,
    ) -> _Term | None:
        saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        if not (self._try_unify(self.infer(goal_type), _SORT)
                and self._try_unify(self.infer(eq_type), _SORT)):
            self.metas = saved
            return None
        z = self.fresh(eq_type)
        z_id = cast("int", z.value)

        def build_ctx(sub_l: _Term, sub_r: _Term) -> tuple[_Term | None, bool]:
            sub_l = self.resolve(sub_l)
            sub_r = self.resolve(sub_r)
            if sub_l == u and sub_r == v:
                return z, True
            if (sub_l != lhs or sub_r != rhs) and (
                self._try_unify(self.infer(sub_l), eq_type)
                and self._try_unify(sub_l, u)
                and self._try_unify(sub_r, v)
            ):
                return z, True
            if (sub_l.kind == sub_r.kind
                    and sub_l.value == sub_r.value
                    and len(sub_l.args) == len(sub_r.args)
                    and sub_l.kind not in {"pi", "lam", "let"}):
                child_ctxs: list[_Term] = []
                any_replaced = False
                ok = True
                for c_l, c_r in zip(sub_l.args, sub_r.args, strict=True):
                    c_ctx, c_rep = build_ctx(c_l, c_r)
                    if c_ctx is None:
                        ok = False
                        break
                    child_ctxs.append(c_ctx)
                    any_replaced = any_replaced or c_rep
                if ok and any_replaced:
                    return _Term(sub_l.kind, sub_l.value, tuple(child_ctxs)), True
            whnf_l = self.whnf(sub_l)
            whnf_r = self.whnf(sub_r)
            if (whnf_l != sub_l or whnf_r != sub_r) and (
                whnf_l.kind == whnf_r.kind
                and whnf_l.value == whnf_r.value
                and len(whnf_l.args) == len(whnf_r.args)
                and whnf_l.kind not in {"pi", "lam", "let"}
            ):
                child_ctxs = []
                any_replaced = False
                ok = True
                for c_l, c_r in zip(whnf_l.args, whnf_r.args, strict=True):
                    c_ctx, c_rep = build_ctx(c_l, c_r)
                    if c_ctx is None:
                        ok = False
                        break
                    child_ctxs.append(c_ctx)
                    any_replaced = any_replaced or c_rep
                if ok and any_replaced:
                    return _Term(whnf_l.kind, whnf_l.value, tuple(child_ctxs)), True
            if self._try_unify(sub_l, sub_r):
                return sub_l, False
            return None, False

        ctx, replaced = build_ctx(lhs, rhs)
        if replaced and ctx is not None and ctx != z:
            fn = _term("lam", eq_type, ctx, value=z.value)
            return _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, proof_term)
        self.metas = [_Meta(m.type, m.scope, m.solution) for m in saved]
        if not (self._try_unify(self.infer(goal_type), _SORT)
                and self._try_unify(self.infer(eq_type), _SORT)):
            self.metas = saved
            return None
        ctx_l, rep_l = self._replace_subterm(lhs, eq_type, u, z)
        if rep_l and ctx_l != z and self._try_unify(self.substitute(ctx_l, z_id, v), rhs):
            fn = _term("lam", eq_type, ctx_l, value=z.value)
            return _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, proof_term)
        self.metas = [_Meta(m.type, m.scope, m.solution) for m in saved]
        if not (self._try_unify(self.infer(goal_type), _SORT)
                and self._try_unify(self.infer(eq_type), _SORT)):
            self.metas = saved
            return None
        ctx_r, rep_r = self._replace_subterm(rhs, eq_type, v, z)
        if rep_r and ctx_r != z and self._try_unify(self.substitute(ctx_r, z_id, u), lhs):
            fn = _term("lam", eq_type, ctx_r, value=z.value)
            return _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, proof_term)
        self.metas = saved
        return None

    def _try_congruence_trans(
        self: _Elaborator,
        goal_type: _Term,
        lhs: _Term,
        rhs: _Term,
        eq_type: _Term,
        u: _Term,
        v: _Term,
        proof_term: _Term,
        edges: list[tuple[int, _Term, _Term, _Term]],
    ) -> _Term | None:
        if not edges:
            return None
        saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        if not (self._try_unify(self.infer(goal_type), _SORT)
                and self._try_unify(self.infer(eq_type), _SORT)):
            self.metas = saved
            return None
        z = self.fresh(eq_type)
        z_id = cast("int", z.value)
        ctx_l, rep_l = self._replace_subterm(lhs, eq_type, u, z)
        if rep_l and ctx_l != z:
            mid = self.substitute(ctx_l, z_id, v)
            fn = _term("lam", eq_type, ctx_l, value=z.value)
            congr_p = _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, proof_term)
            for _, eu, ev, ep in edges:
                step_saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if self._try_unify(eu, mid) and self._try_unify(ev, rhs):
                    return _apps(_constant("Trans"), goal_type, lhs, mid, rhs, congr_p, ep)
                self.metas = step_saved
                congr2 = self._try_congruence(goal_type, mid, rhs, goal_type, eu, ev, ep)
                if congr2 is not None:
                    return _apps(_constant("Trans"), goal_type, lhs, mid, rhs, congr_p, congr2)
        self.metas = [_Meta(m.type, m.scope, m.solution) for m in saved]
        if not (self._try_unify(self.infer(goal_type), _SORT)
                and self._try_unify(self.infer(eq_type), _SORT)):
            self.metas = saved
            return None
        ctx_r, rep_r = self._replace_subterm(rhs, eq_type, v, z)
        if rep_r and ctx_r != z:
            mid = self.substitute(ctx_r, z_id, u)
            fn = _term("lam", eq_type, ctx_r, value=z.value)
            congr_p = _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, proof_term)
            for _, eu, ev, ep in edges:
                step_saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if self._try_unify(eu, lhs) and self._try_unify(ev, mid):
                    return _apps(_constant("Trans"), goal_type, lhs, mid, rhs, ep, congr_p)
                self.metas = step_saved
                congr1 = self._try_congruence(goal_type, lhs, mid, goal_type, eu, ev, ep)
                if congr1 is not None:
                    return _apps(_constant("Trans"), goal_type, lhs, mid, rhs, congr1, congr_p)
        self.metas = saved
        return None

    def _equality_edges(
        self: _Elaborator, goal_type: _Term, facts: tuple[_Binding, ...]
    ) -> list[tuple[int, _Term, _Term, _Term]]:
        edges: list[tuple[int, _Term, _Term, _Term]] = []
        for idx, fact in enumerate(facts):
            extracted = self._extract_equality(fact.type)
            if extracted is None:
                continue
            eq_type, u, v = extracted
            if not self._try_unify(eq_type, goal_type):
                continue
            edges.append((idx, u, v, fact.term))
            if u != v:
                edges.append((idx, v, u, _apps(_constant("Symm"), goal_type, u, v, fact.term)))
        return edges

    def _chain_sequence(
        self: _Elaborator, goal_type: _Term, lhs: _Term, rhs: _Term, sequence: tuple[_Binding, ...]
    ) -> _Term | None:
        if len(sequence) < 2:
            return None
        saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        steps: list[tuple[_Term, _Term, _Term]] = []
        current = lhs
        for fact in sequence:
            extracted = self._extract_equality(fact.type)
            if extracted is None:
                self.metas = saved
                return None
            eq_type, u, v = extracted
            if not self._try_unify(eq_type, goal_type):
                self.metas = saved
                return None
            if u == current:
                steps.append((u, v, fact.term))
                current = v
            elif v == current:
                steps.append((v, u, _apps(_constant("Symm"), goal_type, u, v, fact.term)))
                current = u
            elif self._try_unify(u, current):
                steps.append((current, v, fact.term))
                current = v
            elif self._try_unify(v, current):
                steps.append((current, u, _apps(_constant("Symm"), goal_type, u, v, fact.term)))
                current = u
            else:
                congr = None
                if self._try_unify(self.infer(eq_type), _SORT) and self._try_unify(self.infer(goal_type), _SORT):
                    z = self.fresh(eq_type)
                    z_id = cast("int", z.value)
                    ctx_u, rep_u = self._replace_subterm(current, eq_type, u, z)
                    if rep_u and ctx_u != z:
                        next_t = self.substitute(ctx_u, z_id, v)
                        fn = _term("lam", eq_type, ctx_u, value=z.value)
                        congr = (
                            current,
                            next_t,
                            _apps(_constant("Congr"), eq_type, goal_type, u, v, fn, fact.term),
                        )
                    elif u != v:
                        ctx_v, rep_v = self._replace_subterm(current, eq_type, v, z)
                        if rep_v and ctx_v != z:
                            next_t = self.substitute(ctx_v, z_id, u)
                            fn = _term("lam", eq_type, ctx_v, value=z.value)
                            sym_p = _apps(_constant("Symm"), eq_type, u, v, fact.term)
                            congr = (
                                current,
                                next_t,
                                _apps(_constant("Congr"), eq_type, goal_type, v, u, fn, sym_p),
                            )
                if congr is not None:
                    steps.append(congr)
                    current = congr[1]
                else:
                    self.metas = saved
                    return None
        if current != rhs and not self._try_unify(current, rhs):
            self.metas = saved
            return None
        acc_u, acc_v, acc_term = steps[0]
        for _, next_v, next_term in steps[1:]:
            acc_term = _apps(_constant("Trans"), goal_type, acc_u, acc_v, next_v, acc_term, next_term)
            acc_v = next_v
        return acc_term

    def _prove_proposition(
        self: _Elaborator,
        goal: _Term,
        environment: dict[str, _Binding],
        facts: tuple[_Binding, ...],
        node: Node,
        *,
        allow_refl: bool = True,
        include_env: bool = True,
    ) -> _Term:
        self.tick()
        self.site = node
        env_facts = (
            tuple(
                binding for binding in environment.values()
                if (self.current_rec_var is None or binding.term != self.current_rec_var)
                and self._is_prop_type(binding.type)
                and not any(binding.term == existing.term for existing in facts)
            )
            if include_env
            else ()
        )
        all_facts = (*facts, *env_facts)
        for fact in reversed(all_facts):
            if fact.type == goal:
                return fact.term
        goal_whnf = self.whnf(goal)
        if goal_whnf.kind == "pi" and cast("int", goal_whnf.value) not in self.nullary_parameters:
            for fact in reversed(all_facts):
                if self._try_unify(fact.type, goal):
                    return fact.term
            var_id = cast("int", goal_whnf.value)
            domain = goal_whnf.args[0]
            var = self.fresh(domain)
            child_env = dict(environment)
            child_facts = list(facts)
            if var_id in self.parameter_names:
                param_name = self.parameter_names[var_id]
                self.parameter_names[cast("int", var.value)] = param_name
                self.bind_local(child_env, param_name, _Binding(var, domain))
            if self._is_prop_type(domain):
                child_facts.append(_Binding(var, domain))
            codomain = self.substitute(goal_whnf.args[1], var_id, var)
            dom_bool_facts = self._fact_bool_terms((_Binding(var, domain),), child_env) if self._is_prop_type(domain) else []
            self.active_facts.extend(dom_bool_facts)
            try:
                body_term = self._prove_proposition(
                    codomain,
                    child_env,
                    tuple(child_facts),
                    node,
                    allow_refl=allow_refl,
                    include_env=include_env,
                )
            finally:
                for _ in dom_bool_facts:
                    self.active_facts.pop()
            return _term("lam", domain, body_term, value=var.value)

        if goal_whnf.kind == "ex":
            for fact in reversed(all_facts):
                if self._try_unify(fact.type, goal):
                    return fact.term
            saved_ex = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            ex_layers: list[tuple[_Term, _Term, _Term]] = []
            curr_ex = goal_whnf
            while curr_ex.kind == "ex":
                ex_dom = curr_ex.args[0]
                ex_lam = curr_ex.args[1]
                w_meta = self.meta(ex_dom, environment)
                ex_layers.append((ex_dom, ex_lam, w_meta))
                curr_ex = self.whnf(self.substitute(ex_lam.args[1], cast("int", ex_lam.value), w_meta))
            for fact in reversed(all_facts):
                attempt_saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if self._match_meta_pattern(curr_ex, fact.type) and all(
                    self.resolve(wm).kind != "meta" for _, _, wm in ex_layers
                ):
                    acc_proof = fact.term
                    for k_ex in range(len(ex_layers) - 1, -1, -1):
                        dom_k, lam_k, wm_k = ex_layers[k_ex]
                        for j_ex in range(k_ex):
                            prev_var_id = cast("int", ex_layers[j_ex][1].value)
                            prev_val = self.resolve(ex_layers[j_ex][2])
                            dom_k = self.substitute(dom_k, prev_var_id, prev_val)
                            lam_k = self.substitute(lam_k, prev_var_id, prev_val)
                        acc_proof = _term("ex_intro", dom_k, lam_k, self.resolve(wm_k), acc_proof)
                    return acc_proof
                self.metas = attempt_saved
            self.metas = saved_ex

        goal_eq = self._extract_equality(goal)
        if goal_eq is not None:
            goal_type, lhs, rhs = goal_eq
            if allow_refl and (
                not all_facts
                or (
                    not facts
                    and all(m.solution is not None for m in self.metas[self.decl_first_meta :])
                )
            ):
                if self._try_unify(lhs, rhs):
                    return _apps(_constant("Refl"), goal_type, lhs)
                if not all_facts:
                    split_proof = self._try_if_split_equality(goal_type, lhs, rhs)
                    if split_proof is not None:
                        return split_proof
            edges = self._equality_edges(goal_type, all_facts)
            for _, u, v, p in reversed(edges):
                if u == lhs and v == rhs:
                    return p
            for i1, u1, v1, p1 in edges:
                if u1 != lhs:
                    continue
                for i2, u2, v2, p2 in edges:
                    if v1 == u2 and v2 == rhs and (i1 != i2 or u1 != v1):
                        return _apps(_constant("Trans"), goal_type, lhs, v1, rhs, p1, p2)
                    if v1 == u2 and i1 != i2:
                        for i3, u3, v3, p3 in edges:
                            if v2 == u3 and v3 == rhs and i3 not in {i1, i2}:
                                step12 = _apps(_constant("Trans"), goal_type, lhs, v1, v2, p1, p2)
                                return _apps(_constant("Trans"), goal_type, lhs, v2, rhs, step12, p3)
            for _, u, v, p in reversed(edges):
                if u != lhs or v != rhs:
                    congr = self._try_congruence(goal_type, lhs, rhs, goal_type, u, v, p)
                    if congr is not None:
                        return congr
            for fact in reversed(all_facts):
                extracted = self._extract_equality(fact.type)
                if extracted is None:
                    continue
                eq_type, u, v = extracted
                if u != lhs or v != rhs:
                    congr = self._try_congruence(goal_type, lhs, rhs, eq_type, u, v, fact.term)
                    if congr is not None:
                        return congr
                    if u != v:
                        sym_p = _apps(_constant("Symm"), eq_type, u, v, fact.term)
                        congr_sym = self._try_congruence(goal_type, lhs, rhs, eq_type, v, u, sym_p)
                        if congr_sym is not None:
                            return congr_sym
            for fact in reversed(all_facts):
                extracted = self._extract_equality(fact.type)
                if extracted is None:
                    continue
                eq_type, u, v = extracted
                ct = self._try_congruence_trans(goal_type, lhs, rhs, eq_type, u, v, fact.term, edges)
                if ct is not None:
                    return ct
                if u != v:
                    sym_p = _apps(_constant("Symm"), eq_type, u, v, fact.term)
                    ct_sym = self._try_congruence_trans(goal_type, lhs, rhs, eq_type, v, u, sym_p, edges)
                    if ct_sym is not None:
                        return ct_sym
            for _, u, v, p in reversed(edges):
                saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if self._try_unify(u, lhs) and self._try_unify(v, rhs):
                    return p
                self.metas = saved
            for i1, u1, v1, p1 in edges:
                saved1 = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if not self._try_unify(u1, lhs):
                    self.metas = saved1
                    continue
                for i2, u2, v2, p2 in edges:
                    if i1 == i2:
                        continue
                    saved2 = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                    if self._try_unify(v1, u2) and self._try_unify(v2, rhs):
                        return _apps(_constant("Trans"), goal_type, lhs, v1, rhs, p1, p2)
                    self.metas = saved2
                self.metas = saved1
            if allow_refl and self._try_unify(lhs, rhs):
                return _apps(_constant("Refl"), goal_type, lhs)
            if allow_refl:
                split_proof = self._try_if_split_equality(goal_type, lhs, rhs)
                if split_proof is not None:
                    return split_proof

        for fact in reversed(all_facts):
            if self._try_unify(fact.type, goal):
                return fact.term

        raise self.fail(
            "type",
            "assertion could not be established; terms or dependent indices are not definitionally equal",
            node,
        )

    def _find_if_condition(self: _Elaborator, term: _Term, depth: int = 0) -> _Term | None:
        if depth > MAX_DEPTH:
            return None
        w = self.whnf(term)
        if w.kind == "if":
            return w.args[1]
        if w.kind in {"sum_match", "pair_match", "unit_match", "sigT_match"} and len(w.args) >= 2:
            for child in w.args[1:]:
                found = self._find_if_condition(child, depth + 1)
                if found is not None:
                    return found
        if w.kind == "lam":
            b_id = cast("int", w.value)
            found = self._find_if_condition(w.args[1], depth + 1)
            if found is not None and b_id not in self.free(found):
                return found
        if w.kind == "app":
            _, args = self.spine(w)
            for child in args:
                found = self._find_if_condition(child, depth + 1)
                if found is not None:
                    return found
        return None

    def _replace_exact(self: _Elaborator, term: _Term, target: _Term, repl: _Term) -> tuple[_Term, bool]:
        term = self.resolve(term)
        if term == target:
            return repl, True
        if term.kind in {"pi", "lam", "let"} or not term.args:
            return term, False
        new_args: list[_Term] = []
        any_rep = False
        for arg in term.args:
            n_arg, rep = self._replace_exact(arg, target, repl)
            new_args.append(n_arg)
            any_rep = any_rep or rep
        if any_rep:
            return _Term(term.kind, term.value, tuple(new_args)), True
        return term, False

    def _expose_and_replace_if(
        self: _Elaborator, term: _Term, cond: _Term, repl: _Term, depth: int = 0
    ) -> tuple[_Term, bool]:
        if depth > MAX_DEPTH:
            return term, False
        term = self.resolve(term)
        if term == cond:
            return repl, True
        w = self.whnf(term)
        if w == cond:
            return repl, True
        if w.kind == "if":
            t_rep, did_t = self._expose_and_replace_if(w.args[2], cond, repl, depth + 1)
            e_rep, did_e = self._expose_and_replace_if(w.args[3], cond, repl, depth + 1)
            if w.args[1] == cond:
                return _term("if", w.args[0], repl, t_rep, e_rep), True
            c_rep, did_c = self._expose_and_replace_if(w.args[1], cond, repl, depth + 1)
            if did_c or did_t or did_e:
                return _term("if", w.args[0], c_rep, t_rep, e_rep), True
            return w, False
        if w.kind in {"sum_match", "pair_match", "unit_match", "sigT_match"} and len(w.args) >= 2:
            s_rep, did_s = self._expose_and_replace_if(w.args[1], cond, repl, depth + 1)
            new_branches: list[_Term] = []
            did_b = False
            for br in w.args[2:]:
                nb, rb = self._expose_and_replace_if(br, cond, repl, depth + 1)
                new_branches.append(nb)
                did_b = did_b or rb
            if did_s or did_b:
                return _Term(w.kind, w.value, (w.args[0], s_rep, *new_branches)), True
            return w, False
        if w.kind == "lam":
            b_id = cast("int", w.value)
            if b_id not in self.free(cond) and b_id not in self.free(repl):
                body_rep, did_body = self._expose_and_replace_if(w.args[1], cond, repl, depth + 1)
                if did_body:
                    return _term("lam", w.args[0], body_rep, value=b_id), True
            return w, False
        if w.kind == "app":
            head, args = self.spine(w)
            new_args: list[_Term] = []
            any_rep = False
            for a in args:
                na, r = self._expose_and_replace_if(a, cond, repl, depth + 1)
                new_args.append(na)
                any_rep = any_rep or r
            if any_rep:
                return _apps(head, *new_args), True
        return term, False

    def _try_if_split_equality(
        self: _Elaborator, goal_type: _Term, lhs: _Term, rhs: _Term, depth: int = 0
    ) -> _Term | None:
        if depth > 8:
            return None
        saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        if self._try_unify(lhs, rhs):
            return _apps(_constant("Refl"), goal_type, self.whnf(rhs))
        self.metas = saved
        cond = self._find_if_condition(lhs)
        if cond is None:
            cond = self._find_if_condition(rhs)
        if cond is None:
            return None
        b_var = self.fresh(_BOOL)
        b_id = cast("int", b_var.value)
        lhs_b, rep_l = self._expose_and_replace_if(lhs, cond, b_var)
        rhs_b, rep_r = self._expose_and_replace_if(rhs, cond, b_var)
        if not rep_l and not rep_r:
            return None
        motive_body = _apps(_constant("Eq"), goal_type, lhs_b, rhs_b)
        motive_lam = _term("lam", _BOOL, motive_body, value=b_id)
        lhs_true = self.substitute(lhs_b, b_id, _term("bool", value=1))
        rhs_true = self.substitute(rhs_b, b_id, _term("bool", value=1))
        yes_proof = self._try_if_split_equality(goal_type, lhs_true, rhs_true, depth + 1)
        if yes_proof is None:
            return None
        lhs_false = self.substitute(lhs_b, b_id, _term("bool", value=0))
        rhs_false = self.substitute(rhs_b, b_id, _term("bool", value=0))
        no_proof = self._try_if_split_equality(goal_type, lhs_false, rhs_false, depth + 1)
        if no_proof is None:
            return None
        return _term("bool_match", motive_lam, cond, yes_proof, no_proof)

    def asserted_proposition(self: _Elaborator, node: Node, environment: dict[str, _Binding]) -> _Term:
        self.site = node
        if node["kind"] == "group":
            return self.asserted_proposition(self.node(node["value"]), environment)
        if node["kind"] == "let_expression":
            return self.asserted_proposition(
                self.node(node["body"]), self.local(self.node(node["binding"]), environment)
            )
        if node["kind"] == "binary":
            operator = self.operator(node["operator"])
            if operator == "==":
                return self.proposition(node, environment)
            if operator == "==>":
                domain = self.asserted_proposition(self.node(node["left"]), environment)
                dom_facts = self._fact_bool_terms((_Binding(_term("unit"), domain),), environment)
                self.active_facts.extend(dom_facts)
                try:
                    codomain = self.asserted_proposition(self.node(node["right"]), environment)
                finally:
                    for _ in dom_facts:
                        self.active_facts.pop()
                return self.pi(domain, codomain)
        if node["kind"] == "quantifier":
            quantifier = node["quantifier"]
            if quantifier not in {"forall", "exists"}:
                raise self.fail("unsupported", f"quantifier '{quantifier}' is not supported", node)
            variables, extended = self.telescope([], self.nodes(node["parameters"]), environment)
            body = self.asserted_proposition(self.node(node["value"]), extended)
            if quantifier == "forall":
                return self.wrap("pi", variables, body)
            result = body
            for variable in reversed(variables):
                domain = self.types[cast("int", variable.value)]
                result = _term("ex", domain, _term("lam", domain, result, value=variable.value))
            return result
        value = self.expression(node, environment)
        value_type = self.whnf(value.type)
        if value_type == _PROP:
            return value.term
        if value_type == _BOOL:
            return _apps(_constant("Eq"), _BOOL, value.term, _term("bool", value=1))
        self.unify(value.type, _PROP)
        return value.term

    def _elaborate_by_expression(
        self: _Elaborator,
        goal: _Term,
        by_node: Node,
        environment: dict[str, _Binding],
        facts: tuple[_Binding, ...],
        assert_node: Node,
    ) -> _Term:
        self.site = by_node
        if by_node["kind"] in {"lambda", "typed_lambda", "match_expression", "if_expression"}:
            return self.check(by_node, goal, environment)
        goal_whnf = self.whnf(goal)
        justification = self.expression(by_node, environment)
        if goal_whnf.kind == "ex" and not self._is_prop_type(justification.type):
            ex_domains: list[tuple[_Term, _Term]] = []
            curr_ex = goal_whnf
            while curr_ex.kind == "ex":
                ex_domains.append((curr_ex.args[0], curr_ex.args[1]))
                curr_ex = self.whnf(curr_ex.args[1].args[1])
            unwrapped_by = self._unwrap_group(by_node)
            if len(ex_domains) > 1 and unwrapped_by["kind"] == "tuple":
                tuple_nodes = self.nodes(unwrapped_by["values"])
                if len(tuple_nodes) == len(ex_domains):
                    witnesses: list[tuple[_Term, _Term, _Term]] = []
                    inst_goal = goal_whnf
                    for t_node in tuple_nodes:
                        inst_ex = self.whnf(inst_goal)
                        dom = inst_ex.args[0]
                        lam = inst_ex.args[1]
                        w_term = self.check(t_node, dom, environment)
                        witnesses.append((dom, lam, w_term))
                        inst_goal = self.substitute(lam.args[1], cast("int", lam.value), w_term)
                    acc_proof = self._prove_proposition(inst_goal, environment, facts, assert_node)
                    for dom, lam, w_term in reversed(witnesses):
                        acc_proof = _term("ex_intro", dom, lam, w_term, acc_proof)
                    return acc_proof
            ex_dom_0 = goal_whnf.args[0]
            ex_lam_0 = goal_whnf.args[1]
            w_term_0 = self.check(by_node, ex_dom_0, environment)
            inst_goal_0 = self.substitute(ex_lam_0.args[1], cast("int", ex_lam_0.value), w_term_0)
            sub_proof = self._prove_proposition(inst_goal_0, environment, facts, assert_node)
            return _term("ex_intro", ex_dom_0, ex_lam_0, w_term_0, sub_proof)
        while self.whnf(justification.type).kind == "pi" and goal_whnf.kind != "pi":
            pi_type = self.whnf(justification.type)
            if cast("int", pi_type.value) in self.nullary_parameters:
                break
            domain = pi_type.args[0]
            if self._is_prop_type(domain):
                arg = self._prove_proposition(domain, environment, facts, by_node)
            else:
                arg = self.meta(domain, environment)
            justification = _Binding(
                _app(justification.term, arg),
                self.substitute(pi_type.args[1], cast("int", pi_type.value), arg),
            )
        if not self._is_prop_type(justification.type):
            raise self.fail("type", "assert 'by' justification must be a proof of a proposition", by_node)
        if goal_whnf.kind == "ex":
            if self._try_unify(justification.type, goal):
                return justification.term
            saved_ex = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            ex_layers: list[tuple[_Term, _Term, _Term]] = []
            curr_ex = goal_whnf
            while curr_ex.kind == "ex":
                ex_dom = curr_ex.args[0]
                ex_lam = curr_ex.args[1]
                w_meta = self.meta(ex_dom, environment)
                ex_layers.append((ex_dom, ex_lam, w_meta))
                curr_ex = self.whnf(self.substitute(ex_lam.args[1], cast("int", ex_lam.value), w_meta))
            if self._match_meta_pattern(curr_ex, justification.type) and all(
                self.resolve(wm).kind != "meta" for _, _, wm in ex_layers
            ):
                acc_proof = justification.term
                for k_ex in range(len(ex_layers) - 1, -1, -1):
                    dom_k, lam_k, wm_k = ex_layers[k_ex]
                    for j_ex in range(k_ex):
                        prev_var_id = cast("int", ex_layers[j_ex][1].value)
                        prev_val = self.resolve(ex_layers[j_ex][2])
                        dom_k = self.substitute(dom_k, prev_var_id, prev_val)
                        lam_k = self.substitute(lam_k, prev_var_id, prev_val)
                    acc_proof = _term("ex_intro", dom_k, lam_k, self.resolve(wm_k), acc_proof)
                return acc_proof
            self.metas = saved_ex
        goal_eq = self._extract_equality(goal)
        just_eq = self._extract_equality(justification.type)
        if goal_eq is not None and just_eq is not None:
            goal_type, lhs, rhs = goal_eq
            eq_type, u, v = just_eq
            if u != lhs or v != rhs:
                congr = self._try_congruence(goal_type, lhs, rhs, eq_type, u, v, justification.term)
                if congr is not None:
                    return congr
                if u != v:
                    sym_p = _apps(_constant("Symm"), eq_type, u, v, justification.term)
                    congr_sym = self._try_congruence(goal_type, lhs, rhs, eq_type, v, u, sym_p)
                    if congr_sym is not None:
                        return congr_sym
        if self._try_unify(justification.type, goal):
            return justification.term
        if goal_eq is not None and just_eq is not None:
            goal_type, lhs, rhs = goal_eq
            eq_type, u, v = just_eq
            saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            if (self._try_unify(eq_type, goal_type)
                    and self._try_unify(v, lhs)
                    and self._try_unify(u, rhs)):
                return _apps(_constant("Symm"), goal_type, u, v, justification.term)
            self.metas = saved
            edges = self._equality_edges(goal_type, facts)
            ct = self._try_congruence_trans(goal_type, lhs, rhs, eq_type, u, v, justification.term, edges)
            if ct is not None:
                return ct
            if u != v:
                sym_p = _apps(_constant("Symm"), eq_type, u, v, justification.term)
                ct_sym = self._try_congruence_trans(goal_type, lhs, rhs, eq_type, v, u, sym_p, edges)
                if ct_sym is not None:
                    return ct_sym
            if self._try_unify(eq_type, goal_type):
                just_orientations = [(u, v, justification.term)]
                if u != v:
                    just_orientations.append((v, u, _apps(_constant("Symm"), goal_type, u, v, justification.term)))
                for ju, jv, jp in just_orientations:
                    if ju == lhs or self._try_unify(ju, lhs):
                        for _, eu, ev, ep in edges:
                            if (jv == eu or self._try_unify(jv, eu)) and (ev == rhs or self._try_unify(ev, rhs)):
                                return _apps(_constant("Trans"), goal_type, lhs, jv, rhs, jp, ep)
                    if jv == rhs or self._try_unify(jv, rhs):
                        for _, eu, ev, ep in edges:
                            if (eu == lhs or self._try_unify(eu, lhs)) and (ev == ju or self._try_unify(ev, ju)):
                                return _apps(_constant("Trans"), goal_type, lhs, ju, rhs, ep, jp)
        raise self.fail("type", "assert justification does not establish the asserted proposition", assert_node)

    def _elaborate_by_block(
        self: _Elaborator,
        goal: _Term,
        by_node: Node,
        environment: dict[str, _Binding],
        facts: tuple[_Binding, ...],
        assert_node: Node,
    ) -> _Term:
        self.node(by_node, "block")
        statements = self.nodes(by_node["statements"])
        if not statements:
            raise self.fail("type", "empty 'by' block cannot justify assertion", by_node)
        child_env = dict(environment)
        active_facts: list[_Binding] = list(facts)
        child_facts: list[_Binding] = []
        peeled_vars: list[_Term] = []
        target_goal = goal
        while self._is_prop_type(target_goal):
            resolved = self.whnf(target_goal)
            if resolved.kind != "pi" or cast("int", resolved.value) in self.nullary_parameters:
                break
            var_id = cast("int", resolved.value)
            if var_id in self.parameter_names:
                param_name = self.parameter_names[var_id]
                if param_name in child_env:
                    break
                var = self.fresh(resolved.args[0])
                self.parameter_names[cast("int", var.value)] = param_name
                self.bind_local(child_env, param_name, _Binding(var, resolved.args[0]))
                if self._is_prop_type(resolved.args[0]):
                    active_facts.append(_Binding(var, resolved.args[0]))
            else:
                var = self.fresh(resolved.args[0])
                active_facts.append(_Binding(var, resolved.args[0]))
            peeled_vars.append(var)
            target_goal = self.substitute(resolved.args[1], var_id, var)

        def finish(term: _Term) -> _Term:
            return self.wrap("lam", peeled_vars, term) if peeled_vars else term

        for index, statement in enumerate(statements):
            self.site = statement
            kind = statement["kind"]
            if kind in {"let", "typed_local", "let_pattern", "constant_local"}:
                previous_keys = set(child_env)
                child_env = self.local(statement, child_env)
                for new_key in set(child_env) - previous_keys:
                    bound = child_env[new_key]
                    if self._is_prop_type(bound.type):
                        child_facts.append(bound)
                continue
            if kind == "assert":
                fact = self._elaborate_assert(statement, child_env, (*active_facts, *child_facts))
                child_facts.append(fact)
                continue
            if kind == "proof":
                sub_facts = self._elaborate_proof_statement(
                    self.node(statement["body"], "block"), child_env, (*active_facts, *child_facts)
                )
                child_facts.extend(sub_facts)
                continue
            if kind == "calc":
                sub_facts = self._elaborate_calc_statement(
                    self.node(statement["body"], "block"), child_env, (*active_facts, *child_facts)
                )
                child_facts.extend(sub_facts)
                continue
            if kind == "let_else":
                if index == len(statements) - 1:
                    raise self.fail("type", "a pure block requires an explicit terminal return after let-else", statement)
                synthetic = {"kind": "block", "span": by_node["span"], "statements": statements[index:]}
                evaluated = self.block(synthetic, child_env, target_goal, facts=(*active_facts, *child_facts))
                return finish(evaluated.term)
            if index == len(statements) - 1 and kind in {"match", "if", "return", "block"}:
                synthetic = {"kind": "block", "span": by_node["span"], "statements": [statement]}
                evaluated = self.block(synthetic, child_env, target_goal, facts=(*active_facts, *child_facts))
                return finish(evaluated.term)
            raise self.fail("unsupported", f"statement '{kind}' is not supported in an assert 'by' block", statement)

        if not child_facts:
            raise self.fail("type", "assert 'by' block contains no proof steps", by_node)
        goal_eq = self._extract_equality(target_goal)
        if goal_eq is not None and len(child_facts) >= 2:
            goal_type, lhs, rhs = goal_eq
            chained = self._chain_sequence(goal_type, lhs, rhs, tuple(child_facts))
            if chained is not None:
                return finish(chained)
        return finish(
            self._prove_proposition(
                target_goal,
                child_env,
                tuple(child_facts),
                assert_node,
                allow_refl=False,
                include_env=False,
            )
        )

    def _try_domain_solver_goal(
        self: _Elaborator,
        node: Node,
        goal: _Term,
        environment: dict[str, _Binding],
        facts: tuple[_Binding, ...],
    ) -> _Binding | None:
        extracted = self._extract_equality(goal)
        if extracted is not None:
            eq_ty, lhs_t, rhs_t = extracted
            eq_ty_w = self.whnf(eq_ty)
            if (
                eq_ty_w == _BOOL
                and self.whnf(rhs_t) == _term("bool", value=1)
                and self._prove_bool_precondition(lhs_t, environment)
            ):
                self.used_domain_solver_in_proof = True
                return _Binding(_apps(_constant("Refl"), _BOOL, _term("bool", value=1)), goal)
            if eq_ty_w == _NAT or self._int_spec(eq_ty_w) is not None:
                spec = self._int_spec(eq_ty_w)
                bool_facts = self._expand_bool_facts(
                    [*self.active_facts, *self._fact_bool_terms(facts, environment)]
                )
                if self._prove_comparison("eq", spec, lhs_t, rhs_t, bool_facts):
                    self.used_domain_solver_in_proof = True
                    return _Binding(_apps(_constant("Refl"), _BOOL, _term("bool", value=1)), goal)
        saved_assert_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        try:
            val_b = self.expression(self.node(node["value"]), environment)
            if self.whnf(val_b.type) == _BOOL and self._prove_bool_precondition(val_b.term, environment):
                self.used_domain_solver_in_proof = True
                return _Binding(_apps(_constant("Refl"), _BOOL, _term("bool", value=1)), goal)
        except VelaError:
            self.metas = saved_assert_m
        return None

    def _elaborate_assert(
        self: _Elaborator, node: Node, environment: dict[str, _Binding], facts: tuple[_Binding, ...]
    ) -> _Binding:
        self.site = node
        self.reset_budget()
        goal = self.asserted_proposition(self.node(node["value"]), environment)
        by_raw = node["by"]
        if by_raw is None:
            if self.in_post_env_theorem:
                solved = self._try_domain_solver_goal(node, goal, environment, facts)
                if solved is not None:
                    return solved
            try:
                term = self._prove_proposition(goal, environment, facts, node)
            except VelaError:
                has_span_env = self.in_post_env_theorem or any(
                    self.spine(self.whnf(b.type))[0] == _constant("Span") for b in environment.values()
                )
                if (
                    self.current_return_type is not None
                    and self._is_prop_type(self.current_return_type)
                    and not has_span_env
                ):
                    raise
                solved = self._try_domain_solver_goal(node, goal, environment, facts)
                if solved is not None:
                    return solved
                raise
        else:
            by_node = self.node(by_raw)
            if by_node["kind"] == "block":
                term = self._elaborate_by_block(goal, by_node, environment, facts, node)
            else:
                term = self._elaborate_by_expression(goal, by_node, environment, facts, node)
        return _Binding(term, goal)

    def _elaborate_proof_statement(
        self: _Elaborator, body_node: Node, environment: dict[str, _Binding], facts: tuple[_Binding, ...]
    ) -> list[_Binding]:
        self.node(body_node, "block")
        statements = self.nodes(body_node["statements"])
        extended = dict(environment)
        new_facts: list[_Binding] = []
        for statement in statements:
            self.site = statement
            kind = statement["kind"]
            if kind in {"let", "typed_local", "let_pattern", "constant_local"}:
                previous_keys = set(extended)
                extended = self.local(statement, extended)
                for new_key in set(extended) - previous_keys:
                    bound = extended[new_key]
                    if self._is_prop_type(bound.type):
                        new_facts.append(bound)
                continue
            if kind == "assert":
                new_facts.append(self._elaborate_assert(statement, extended, (*facts, *new_facts)))
                continue
            if kind == "proof":
                sub = self._elaborate_proof_statement(
                    self.node(statement["body"], "block"), extended, (*facts, *new_facts)
                )
                new_facts.extend(sub)
                continue
            if kind == "calc":
                sub = self._elaborate_calc_statement(
                    self.node(statement["body"], "block"), extended, (*facts, *new_facts)
                )
                new_facts.extend(sub)
                continue
            raise self.fail("unsupported", f"statement '{kind}' requires the full frontend", statement)
        return new_facts

    def _elaborate_calc_statement(
        self: _Elaborator, body_node: Node, environment: dict[str, _Binding], facts: tuple[_Binding, ...]
    ) -> list[_Binding]:
        self.node(body_node, "block")
        statements = self.nodes(body_node["statements"])
        if not statements:
            raise self.fail("type", "calc block requires at least one equality step", body_node)
        extended = dict(environment)
        new_facts: list[_Binding] = []
        chain_type: _Term | None = None
        chain_start: _Term | None = None
        chain_curr: _Term | None = None
        chain_proof: _Term | None = None
        for statement in statements:
            self.site = statement
            kind = statement["kind"]
            if kind in {"let", "typed_local", "let_pattern", "constant_local"}:
                previous_keys = set(extended)
                extended = self.local(statement, extended)
                for new_key in set(extended) - previous_keys:
                    bound = extended[new_key]
                    if self._is_prop_type(bound.type):
                        new_facts.append(bound)
                continue
            if kind != "assert":
                raise self.fail(
                    "type",
                    f"calc block statements must be equality assertions ('assert lhs == rhs'), got '{kind}'",
                    statement,
                )
            step_fact = self._elaborate_assert(statement, extended, (*facts, *new_facts))
            extracted = self._extract_equality(step_fact.type)
            if extracted is None:
                raise self.fail(
                    "type",
                    "calc block steps must be equality assertions ('assert lhs == rhs')",
                    statement,
                )
            eq_type, u, v = extracted
            new_facts.append(step_fact)
            if chain_proof is None:
                chain_type = eq_type
                chain_start = u
                chain_curr = v
                chain_proof = step_fact.term
            else:
                if chain_type is None or chain_start is None or chain_curr is None:
                    raise self.fail("protocol", "internal calc chain state missing", statement)
                if not (self._try_unify(eq_type, chain_type) and self._try_unify(u, chain_curr)):
                    raise self.fail(
                        "type",
                        "calculational proof step left-hand side does not match previous right-hand side",
                        statement,
                    )
                chain_proof = _apps(
                    _constant("Trans"), chain_type, chain_start, chain_curr, v, chain_proof, step_fact.term
                )
                chain_curr = v
                new_facts.append(
                    _Binding(chain_proof, _apps(_constant("Eq"), chain_type, chain_start, chain_curr))
                )
        if chain_proof is None:
            raise self.fail("type", "calc block requires at least one equality step", body_node)
        return new_facts
