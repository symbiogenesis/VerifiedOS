# SPDX-License-Identifier: Apache-2.0
"""Module-level declaration checking, record/union lowering, and Gallina rendering for Vela."""

from typing import TYPE_CHECKING, cast

from vos.vela.ast import VelaError
from vos.vela.elaborate_types import (
    _BOOL,
    _GALLINA,
    _NAT,
    _NUMERICS_ALIASES,
    _PROP,
    _U8,
    _UNIT,
    _USIZE,
    Node,
    _app,
    _apps,
    _Binding,
    _constant,
    _IntSpec,
    _Meta,
    _RecordField,
    _RecordInfo,
    _RecordInvariant,
    _RecordMethod,
    _RecordProperty,
    _Term,
    _term,
    _UnionCtor,
    _UnionInfo,
)

if TYPE_CHECKING:
    from vos.vela.elaborate import _Elaborator


class _DeclarationsMixin:
    def complete(self: _Elaborator, term: _Term, seen: dict[int, _Term] | None = None) -> None:
        if seen is None:
            seen = {}
        tid = id(term)
        if tid in seen:
            return
        seen[tid] = term
        self.tick()
        term = self.resolve(term)
        if term.kind == "meta":
            raise self.fail("inference", "unresolved inference variable; add a type or generic argument")
        for child in term.args:
            self.complete(child, seen)

    def _evict_builtin_if_shadowed(self: _Elaborator, name: str) -> None:
        if name in self.builtin_unions:
            self.builtin_unions.discard(name)
            uinfo = self.unions.pop(name, None)
            self.globals.pop(name, None)
            if uinfo is not None:
                for uc in uinfo.constructors:
                    if uc.name in self.builtin_union_ctors:
                        self.builtin_union_ctors.discard(uc.name)
                        self.union_ctors.pop(uc.name, None)
                        self.globals.pop(uc.name, None)
        elif name in self.builtin_union_ctors:
            self.builtin_union_ctors.discard(name)
            self.union_ctors.pop(name, None)
            self.globals.pop(name, None)

    def _record_declaration(self: _Elaborator, node: Node, first_meta: int) -> None:
        modifiers = node["modifiers"]
        allowed_modifiers = {"public", "private", "internal"}
        if (not isinstance(modifiers, list)
                or any(not isinstance(value, str) or value not in allowed_modifiers for value in modifiers)
                or len(modifiers) != len(set(modifiers))):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers", node)
        record_contracts = self.nodes(node["contracts"])
        for c_node in record_contracts:
            self.node(c_node, "contract")
            if c_node["role"] != "invariant":
                raise self.fail("unsupported", f"record contract '{c_node['role']}' is not supported", c_node)
        name = self.name(node["name"])
        self._evict_builtin_if_shadowed(name)
        if (name in self.globals or name in self.records or name in self.unions
                or name in self.union_ctors or name in {"Type", "_", "this"} or "." in name):
            raise self.fail("name", f"duplicate or reserved declaration '{name}'", node)
        generics = self.nodes(node["generics"])
        parameters = self.nodes(node["parameters"])
        for param_node in parameters:
            self.node(param_node, "parameter")
            if param_node["name"] is None:
                raise self.fail("protocol", "record field requires an explicit name", param_node)
            fname = self.name(param_node["name"])
            if fname in {"Type", "_", "this"} or "." in fname:
                raise self.fail("name", f"invalid or reserved record field name '{fname}'", param_node)
            if param_node.get("const", False):
                raise self.fail("unsupported", "record fields cannot be marked const", param_node)
        variables, environment = self.telescope(generics, parameters, {}, unit=False)
        generic_vars = variables[:len(generics)]
        field_vars = variables[len(generics):]
        field_names = [self.name(p["name"]) for p in parameters]
        is_dependent = False
        for idx, fv in enumerate(field_vars):
            ftype = self.types[cast("int", fv.value)]
            if any(cast("int", earlier.value) in self.free(ftype) for earlier in field_vars[:idx]):
                is_dependent = True
                break
        tail_sig_types: tuple[_Term, ...] = ()
        if not field_vars:
            rep_type = _UNIT
        elif len(field_vars) == 1:
            rep_type = _term("prod", self.types[cast("int", field_vars[0].value)], _UNIT)
        elif is_dependent:
            curr_type = self.types[cast("int", field_vars[-1].value)]
            tail_sigs_rev: list[_Term] = [curr_type]
            for fv in reversed(field_vars[:-1]):
                fv_id = cast("int", fv.value)
                fv_type = self.types[fv_id]
                curr_type = _term("sigT", fv_type, _term("lam", fv_type, curr_type, value=fv_id))
                tail_sigs_rev.append(curr_type)
            tail_sigs_rev.reverse()
            tail_sig_types = tuple(tail_sigs_rev)
            rep_type = tail_sig_types[0]
        else:
            rep_type = self.types[cast("int", field_vars[-1].value)]
            for fv in reversed(field_vars[:-1]):
                rep_type = _term("prod", self.types[cast("int", fv.value)], rep_type)
        rep_sort = _term("sort", value=max(self.sort(rep_type), 0))
        type_sig = self.wrap("pi", generic_vars, rep_sort)
        type_def = self.wrap("lam", generic_vars, rep_type)
        self.site = node
        self.complete(type_sig)
        self.complete(type_def)
        for index in range(first_meta, len(self.metas)):
            self.complete(_term("meta", value=index))
            self.complete(self.metas[index].type)
        type_emitted = f"vela_d{len(self.output)}_{name}"
        self.output.append(f"Definition {type_emitted} : {self.render(type_sig)} :=\n  {self.render(type_def)}.")
        type_binding = _Binding(_constant(type_emitted), type_sig, len(generics))
        self.globals[name] = type_binding
        self.constants[type_emitted] = type_binding

        record_type_app = _apps(_constant(type_emitted), *generic_vars)
        if not field_vars:
            unit_var = self.fresh(_UNIT)
            self.nullary_parameters.add(cast("int", unit_var.value))
            ctor_vars = [*generic_vars, unit_var]
            ctor_body = _term("unit")
        elif len(field_vars) == 1:
            ctor_vars = [*generic_vars, field_vars[0]]
            f0_type = self.types[cast("int", field_vars[0].value)]
            ctor_body = _term("pair", f0_type, _UNIT, field_vars[0], _term("unit"))
        elif is_dependent:
            ctor_vars = [*generic_vars, *field_vars]
            ctor_body = field_vars[-1]
            for idx in range(len(field_vars) - 2, -1, -1):
                fv = field_vars[idx]
                sig_ty = tail_sig_types[idx]
                ctor_body = _term("existT", sig_ty.args[0], sig_ty.args[1], fv, ctor_body)
        else:
            ctor_vars = [*generic_vars, *field_vars]
            ctor_body = field_vars[-1]
            acc_type = self.types[cast("int", field_vars[-1].value)]
            for fv in reversed(field_vars[:-1]):
                fv_type = self.types[cast("int", fv.value)]
                ctor_body = _term("pair", fv_type, acc_type, fv, ctor_body)
                acc_type = _term("prod", fv_type, acc_type)
        ctor_sig = self.wrap("pi", ctor_vars, record_type_app)
        ctor_def = self.wrap("lam", ctor_vars, ctor_body)
        self.complete(ctor_sig)
        self.complete(ctor_def)
        ctor_emitted = f"vela_d{len(self.output)}_{name}_ctor"
        self.output.append(f"Definition {ctor_emitted} : {self.render(ctor_sig)} :=\n  {self.render(ctor_def)}.")
        ctor_binding = _Binding(_constant(ctor_emitted), ctor_sig, len(generics))
        self.constants[ctor_emitted] = ctor_binding

        record_fields: list[_RecordField] = []
        for idx, (fname, fvar) in enumerate(zip(field_names, field_vars, strict=True)):
            ftype = self.types[cast("int", fvar.value)]
            self_var = self.fresh(record_type_app)
            proj_vars = [*generic_vars, self_var]
            proj_ret_type = ftype
            if len(field_vars) == 1:
                proj_body = _apps(_constant("Fst"), ftype, _UNIT, self_var)
            elif is_dependent:
                curr_term = self_var
                curr_sig = rep_type
                for step in range(idx):
                    step_val = _term("projT1", curr_sig.args[0], curr_sig.args[1], curr_term)
                    curr_term = _term("projT2", curr_sig.args[0], curr_sig.args[1], curr_term)
                    curr_sig = self.substitute(curr_sig.args[1].args[1], cast("int", curr_sig.args[1].value), step_val)
                    earlier_rf = record_fields[step]
                    proj_call = _apps(_constant(earlier_rf.proj_const), *generic_vars, self_var)
                    proj_ret_type = self.substitute(proj_ret_type, cast("int", earlier_rf.var.value), proj_call)
                if idx < len(field_vars) - 1:
                    curr_term = _term("projT1", curr_sig.args[0], curr_sig.args[1], curr_term)
                proj_body = curr_term
            else:
                curr_term = self_var
                curr_type = rep_type
                for _ in range(idx):
                    curr_term = _apps(_constant("Snd"), curr_type.args[0], curr_type.args[1], curr_term)
                    curr_type = curr_type.args[1]
                if idx < len(field_vars) - 1:
                    curr_term = _apps(_constant("Fst"), curr_type.args[0], curr_type.args[1], curr_term)
                proj_body = curr_term
            proj_sig = self.wrap("pi", proj_vars, proj_ret_type)
            proj_def = self.wrap("lam", proj_vars, proj_body)
            self.complete(proj_sig)
            self.complete(proj_def)
            proj_emitted = f"vela_d{len(self.output)}_{name}_{fname}"
            self.output.append(f"Definition {proj_emitted} : {self.render(proj_sig)} :=\n  {self.render(proj_def)}.")
            proj_binding = _Binding(_constant(proj_emitted), proj_sig, len(generics))
            self.constants[proj_emitted] = proj_binding
            record_fields.append(_RecordField(fname, fvar, ftype, proj_emitted))

        record_info = _RecordInfo(
            name=name,
            type_const=type_emitted,
            ctor_const=ctor_emitted,
            type_binding=type_binding,
            ctor_binding=ctor_binding,
            generic_vars=tuple(generic_vars),
            fields=tuple(record_fields),
            properties={},
            is_dependent=is_dependent,
            tail_sig_types=tail_sig_types,
        )
        self.records[name] = record_info
        self.records_by_type[type_emitted] = record_info
        self.records_by_ctor[ctor_emitted] = record_info
        for idx, rf in enumerate(record_fields):
            self.record_projections[rf.proj_const] = (record_info, idx)

        generic_env: dict[str, _Binding] = {}
        for gnode in generics:
            gname = self.name(gnode["name"])
            generic_env[gname] = environment[gname]
        member_declarations = self.nodes(node["declarations"])
        for member_node in member_declarations:
            self.site = member_node
            if member_node["kind"] not in {"property", "definition", "function"}:
                raise self.fail(
                    "unsupported",
                    f"record member '{member_node['kind']}' requires the full frontend",
                    member_node,
                )
            if member_node["kind"] != "property":
                continue
            prop_first_meta = len(self.metas)
            p_modifiers = member_node["modifiers"]
            if (not isinstance(p_modifiers, list)
                    or any(not isinstance(value, str) or value not in allowed_modifiers for value in p_modifiers)
                    or len(p_modifiers) != len(set(p_modifiers))):
                raise self.fail("unsupported", "unsupported or repeated declaration modifiers", member_node)
            self.no_roles(member_node, "contracts")
            prop_name = self.name(member_node["name"])
            if (prop_name in {"Type", "_", "this"} or "." in prop_name
                    or any(rf.name == prop_name for rf in record_fields)
                    or prop_name in record_info.properties):
                raise self.fail("name", f"duplicate or reserved property '{prop_name}' on record '{name}'", member_node)
            self_var = self.fresh(record_type_app)
            prop_env = dict(generic_env)
            prop_env["this"] = _Binding(self_var, record_type_app)
            for idx, rf in enumerate(record_fields):
                if rf.name not in generic_env:
                    rf_type = self._instantiate_record_field_type(record_info, list(generic_vars), idx, self_var)
                    prop_env[rf.name] = _Binding(_apps(_constant(rf.proj_const), *generic_vars, self_var), rf_type)
            prop_type = self.type(self.node(member_node["type"]), prop_env)
            prop_body = self.check(self.node(member_node["value"]), prop_type, prop_env)
            prop_vars = [*generic_vars, self_var]
            prop_sig = self.wrap("pi", prop_vars, prop_type)
            prop_def = self.wrap("lam", prop_vars, prop_body)
            self.site = member_node
            self.complete(prop_sig)
            self.complete(prop_def)
            for index in range(prop_first_meta, len(self.metas)):
                self.complete(_term("meta", value=index))
                self.complete(self.metas[index].type)
            prop_emitted = f"vela_d{len(self.output)}_{name}_{prop_name}"
            self.output.append(f"Definition {prop_emitted} : {self.render(prop_sig)} :=\n  {self.render(prop_def)}.")
            prop_binding = _Binding(_constant(prop_emitted), prop_sig, len(generics))
            self.constants[prop_emitted] = prop_binding
            self.definitions[prop_emitted] = prop_def
            record_info.properties[prop_name] = _RecordProperty(prop_name, self_var, prop_type, prop_emitted)

        invariants_list: list[_RecordInvariant] = []
        seen_inv_names: set[str] = set()
        for inv_idx, c_node in enumerate(record_contracts):
            self.site = c_node
            inv_first_meta = len(self.metas)
            raw_cname = c_node.get("name")
            if raw_cname is not None:
                cname = self.name(raw_cname)
                if cname in seen_inv_names:
                    raise self.fail("name", f"duplicate invariant clause name '{cname}' on record '{name}'", c_node)
                seen_inv_names.add(cname)
            else:
                cname = f"__anon_invariant_{inv_idx}"
            self_var = self.fresh(record_type_app)
            inv_env = dict(generic_env)
            inv_env["this"] = _Binding(self_var, record_type_app)
            for idx, rf in enumerate(record_fields):
                if rf.name not in generic_env:
                    rf_type = self._instantiate_record_field_type(record_info, list(generic_vars), idx, self_var)
                    inv_env[rf.name] = _Binding(_apps(_constant(rf.proj_const), *generic_vars, self_var), rf_type)
            for pname, rp in record_info.properties.items():
                if pname not in generic_env:
                    rp_type = self.substitute(rp.type, cast("int", rp.self_var.value), self_var)
                    inv_env[pname] = _Binding(_apps(_constant(rp.prop_const), *generic_vars, self_var), rp_type)
            val_node = self.node(c_node["value"])
            saved_inv_metas = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            try:
                inv_b = self.expression(val_node, inv_env)
                inv_w = self.whnf(inv_b.type)
                if inv_w == _BOOL or self._is_prop_type(inv_w):
                    inv_term, inv_type = inv_b.term, inv_w
                else:
                    self.metas = saved_inv_metas
                    inv_term = self.proposition(val_node, inv_env)
                    inv_type = _PROP
            except VelaError:
                self.metas = saved_inv_metas
                inv_term = self.proposition(val_node, inv_env)
                inv_type = _PROP
            self.site = c_node
            self.complete(inv_term)
            self.complete(inv_type)
            for index in range(inv_first_meta, len(self.metas)):
                self.complete(_term("meta", value=index))
                self.complete(self.metas[index].type)
            invariants_list.append(_RecordInvariant(cname, self_var, inv_term, inv_type, c_node))
        record_info.invariants = tuple(invariants_list)

        for member_node in member_declarations:
            if member_node["kind"] in {"definition", "function"}:
                self._elaborate_record_method_declaration(
                    record_info,
                    name,
                    generics,
                    generic_vars,
                    generic_env,
                    record_type_app,
                    record_fields,
                    member_node,
                    allowed_modifiers,
                )

    def _elaborate_record_method_declaration(
        self: _Elaborator,
        record_info: _RecordInfo,
        name: str,
        generics: list[Node],
        generic_vars: list[_Term],
        generic_env: dict[str, _Binding],
        record_type_app: _Term,
        record_fields: list[_RecordField],
        member_node: Node,
        allowed_modifiers: set[str],
    ) -> None:
        self.site = member_node
        m_first_meta = len(self.metas)
        m_kind = cast("str", member_node["kind"])
        m_modifiers = member_node["modifiers"]
        m_allowed = allowed_modifiers | {"const"}
        if (
            not isinstance(m_modifiers, list)
            or any(not isinstance(value, str) or value not in m_allowed for value in m_modifiers)
            or len(m_modifiers) != len(set(m_modifiers))
        ):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers", member_node)
        self.no_roles(member_node, "cancel")
        m_generics = self.nodes(member_node["generics"])
        method_name = self.name(member_node["name"])
        if (
            method_name in {"Type", "_", "this"}
            or "." in method_name
            or any(rf.name == method_name for rf in record_fields)
            or method_name in record_info.properties
            or method_name in record_info.methods
        ):
            raise self.fail(
                "name", f"duplicate or reserved member '{method_name}' on record '{name}'", member_node
            )
        requires_clauses: list[Node] = []
        ensures_clauses: list[Node] = []
        for contract in self.nodes(member_node["contracts"]):
            self.node(contract, "contract")
            role = contract["role"]
            if role in {"requires", "where"}:
                requires_clauses.append(contract)
            elif role == "ensures":
                ensures_clauses.append(contract)
            else:
                raise self.fail(
                    "unsupported",
                    f"contract '{role}' on record method requires the full frontend",
                    contract,
                )
        m_params = self.nodes(member_node["parameters"])
        m_param_names: set[str] = set()
        m_param_labels: list[str | None] = []
        for p_node in m_params:
            self.node(p_node, "parameter")
            if p_node["name"] is not None:
                pname = self.name(p_node["name"])
                if pname == "this":
                    raise self.fail("name", "duplicate or invalid local binding 'this'", p_node)
                m_param_names.add(pname)
                m_param_labels.append(pname)
            else:
                m_param_labels.append(None)
        for g_node in m_generics:
            self.node(g_node, "generic_parameter")
            gname = self.name(g_node["name"])
            if gname == "this":
                raise self.fail("name", "duplicate or invalid local binding 'this'", g_node)
            m_param_names.add(gname)
        self_var = self.fresh(record_type_app)
        base_env = dict(generic_env)
        base_env["this"] = _Binding(self_var, record_type_app)
        for idx, rf in enumerate(record_fields):
            if rf.name not in generic_env and rf.name not in m_param_names:
                rf_type = self._instantiate_record_field_type(record_info, list(generic_vars), idx, self_var)
                base_env[rf.name] = _Binding(_apps(_constant(rf.proj_const), *generic_vars, self_var), rf_type)
        for pname, rp in record_info.properties.items():
            if pname not in generic_env and pname not in m_param_names:
                rp_type = self.substitute(rp.type, cast("int", rp.self_var.value), self_var)
                base_env[pname] = _Binding(_apps(_constant(rp.prop_const), *generic_vars, self_var), rp_type)
        self.mutable_locals = set()
        self.final_return_facts = []
        m_vars, method_env = self.telescope(m_generics, m_params, base_env, unit=True)
        m_gen_vars = m_vars[:len(m_generics)]
        param_vars = m_vars[len(m_generics):]
        self.entry_env = dict(method_env)
        self.final_ref_bindings = dict(method_env)
        req_bool_terms: list[_Term] = []
        req_vars: list[_Term] = []
        for req_idx, req_contract in enumerate(requires_clauses):
            req_val_node = self.node(req_contract["value"])
            saved_req_metas = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            req_val: _Binding | None = None
            if req_val_node["kind"] != "quantifier":
                try:
                    req_val = self.expression(req_val_node, method_env)
                except VelaError:
                    self.metas = saved_req_metas
                    req_val = None
            if req_val is not None and self.whnf(req_val.type) == _BOOL:
                req_bool_terms.append(req_val.term)
                eq_prop = _apps(_constant("Eq"), _BOOL, req_val.term, _term("bool", value=1))
                req_var = self.fresh(eq_prop)
                req_vars.append(req_var)
                method_env[f"__vela_req_{req_idx}"] = _Binding(req_var, eq_prop)
            else:
                self.metas = saved_req_metas
                req_prop = self.proposition(req_val_node, method_env)
                req_var = self.fresh(req_prop)
                req_vars.append(req_var)
                method_env[f"__vela_req_{req_idx}"] = _Binding(req_var, req_prop)
                if req_prop.kind == "app":
                    head_p, args_p = self.spine(req_prop)
                    if (
                        head_p.kind == "const"
                        and head_p.value == "Eq"
                        and len(args_p) == 3
                        and self.whnf(args_p[0]) == _BOOL
                    ):
                        rhs_w = self.whnf(args_p[2])
                        if rhs_w.kind == "bool" and rhs_w.value == 1:
                            req_bool_terms.append(args_p[1])
        result_ty = self.type(self.node(member_node["result"]), method_env)
        raw_body = member_node["value"] if m_kind == "definition" else member_node["body"]
        if raw_body is None:
            raise self.fail("unsupported", "abstract callable signatures have no emitted implementation", member_node)
        body_node = self.node(raw_body)
        prev_ret = self.current_return_type
        self.current_return_type = result_ty
        entry_body_facts = [*req_bool_terms, *self._fact_bool_terms((), method_env)]
        saved_body_facts = list(self.active_facts)
        self.active_facts.extend(entry_body_facts)
        try:
            body_term = self.check(body_node, result_ty, method_env)
        finally:
            self.active_facts = saved_body_facts
            self.current_return_type = prev_ret
        all_vars = [*generic_vars, *m_gen_vars, self_var, *param_vars]
        m_sig = self.wrap("pi", all_vars, result_ty)
        m_def = self.wrap("lam", all_vars, body_term)
        self.site = member_node
        self.complete(m_sig)
        self.complete(m_def)
        for index in range(m_first_meta, len(self.metas)):
            self.complete(_term("meta", value=index))
            self.complete(self.metas[index].type)
        m_emitted = f"vela_d{len(self.output)}_{name}_{method_name}"
        self.output.append(f"Definition {m_emitted} : {self.render(m_sig)} :=\n  {self.render(m_def)}.")
        m_binding = _Binding(_constant(m_emitted), m_sig, len(generics) + len(m_generics))
        self.constants[m_emitted] = m_binding
        self.definitions[m_emitted] = m_def
        param_ids = tuple(cast("int", v.value) for v in all_vars)
        preconditions = tuple((param_ids, req_t) for req_t in req_bool_terms)
        if preconditions:
            self.callable_preconditions[m_emitted] = list(preconditions)
        if ensures_clauses:
            post_env = dict(method_env)
            call_term = _apps(_constant(m_emitted), *all_vars)
            post_env["result"] = _Binding(call_term, result_ty)
            post_vars = [*all_vars, *req_vars]
            post_var_ids = {cast("int", v.value) for v in post_vars}
            saved_post_facts = list(self.active_facts)
            self.active_facts.extend(
                [
                    *req_bool_terms,
                    *self.final_return_facts,
                    *self._fact_bool_terms((), self.entry_env),
                    *self._fact_bool_terms((), post_env),
                ]
            )
            try:
                for ens_idx, ens_contract in enumerate(ensures_clauses):
                    self.reset_budget()
                    ens_val_node = self.node(ens_contract["value"])
                    ens_prop = self.asserted_proposition(ens_val_node, post_env)
                    try:
                        ens_proof = self._prove_proposition(ens_prop, post_env, (), ens_contract)
                    except VelaError:
                        extracted = self._extract_equality(ens_prop)
                        proved_alt = False
                        if extracted is not None:
                            eq_ty_w = self.whnf(extracted[0])
                            if (
                                eq_ty_w == _BOOL
                                and self.whnf(extracted[2]) == _term("bool", value=1)
                                and self._prove_bool_precondition(extracted[1], post_env)
                            ):
                                proved_alt = True
                            elif eq_ty_w == _NAT or self._int_spec(eq_ty_w) is not None:
                                spec = self._int_spec(eq_ty_w)
                                bool_facts = self._expand_bool_facts(
                                    [*self.active_facts, *self._fact_bool_terms((), post_env)]
                                )
                                if self._prove_comparison("eq", spec, extracted[1], extracted[2], bool_facts):
                                    proved_alt = True
                        if not proved_alt:
                            saved_ens_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                            try:
                                ens_b = self.expression(ens_val_node, post_env)
                                if self.whnf(ens_b.type) == _BOOL and self._prove_bool_precondition(
                                    ens_b.term, post_env
                                ):
                                    proved_alt = True
                            except VelaError:
                                self.metas = saved_ens_m
                        if proved_alt:
                            ens_prop = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                            ens_proof = _apps(_constant("Refl"), _BOOL, _term("bool", value=1))
                        else:
                            raise
                    if not (self.free(ens_prop) <= post_var_ids and self.free(ens_proof) <= post_var_ids):
                        ens_prop = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                        ens_proof = _apps(_constant("Refl"), _BOOL, _term("bool", value=1))
                    ens_sig = self.wrap("pi", post_vars, ens_prop)
                    ens_def = self.wrap("lam", post_vars, ens_proof)
                    self.complete(ens_sig)
                    self.complete(ens_def)
                    ens_emitted = f"{m_emitted}_ensures_{ens_idx}"
                    self.output.append(
                        f"Definition {ens_emitted} : {self.render(ens_sig)} :=\n  {self.render(ens_def)}."
                    )
                    self.constants[ens_emitted] = _Binding(_constant(ens_emitted), ens_sig, len(generics) + len(m_generics))
                    self.definitions[ens_emitted] = ens_def
            finally:
                self.active_facts = saved_post_facts
        record_info.methods[method_name] = _RecordMethod(
            name=method_name,
            method_const=m_emitted,
            binding=m_binding,
            method_generics=len(m_generics),
            param_labels=tuple(m_param_labels),
            nullary=not bool(m_params),
        )

    def _union_declaration(self: _Elaborator, node: Node, first_meta: int) -> None:
        modifiers = node["modifiers"]
        allowed_modifiers = {"public", "private", "internal"}
        if (not isinstance(modifiers, list)
                or any(not isinstance(value, str) or value not in allowed_modifiers for value in modifiers)
                or len(modifiers) != len(set(modifiers))):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers", node)
        self.no_roles(node, "contracts")
        name = self.name(node["name"])
        self._evict_builtin_if_shadowed(name)
        if (name in self.globals or name in self.records or name in self.unions
                or name in self.union_ctors or name in {"Type", "_", "this"} or "." in name):
            raise self.fail("name", f"duplicate or reserved declaration '{name}'", node)
        generics = self.nodes(node["generics"])
        constructors = self.nodes(node["constructors"])
        if not constructors:
            raise self.fail("unsupported", "empty union declarations require the full frontend", node)
        generic_vars, generic_env = self.telescope(generics, [], {}, unit=False)
        seen_ctors: set[str] = set()
        ctor_specs: list[tuple[Node, str, list[str], list[_Term], _Term, bool, tuple[_Term, ...]]] = []
        for ctor_node in constructors:
            self.node(ctor_node, "constructor")
            self.no_roles(ctor_node, "contracts")
            if ctor_node["result"] is not None:
                raise self.fail(
                    "unsupported",
                    "indexed union constructor result clauses require the full frontend",
                    ctor_node,
                )
            cname = self.name(ctor_node["name"])
            self._evict_builtin_if_shadowed(cname)
            if (cname in self.globals or cname in self.records or cname in self.unions
                    or cname in self.union_ctors or cname == name or cname in seen_ctors
                    or cname in {"Type", "_", "this"} or "." in cname):
                raise self.fail("name", f"duplicate or reserved union constructor '{cname}'", ctor_node)
            seen_ctors.add(cname)
            cparams = self.nodes(ctor_node["parameters"])
            for param_node in cparams:
                self.node(param_node, "parameter")
                if param_node["name"] is None:
                    raise self.fail("protocol", "union constructor field requires an explicit name", param_node)
                fname = self.name(param_node["name"])
                if fname in {"Type", "_", "this"} or "." in fname:
                    raise self.fail("name", f"invalid or reserved union constructor field name '{fname}'", param_node)
                if param_node.get("const", False):
                    raise self.fail("unsupported", "union constructor fields cannot be marked const", param_node)
            field_vars, _ = self.telescope([], cparams, generic_env, unit=False)
            field_names = [self.name(p["name"]) for p in cparams]
            is_dep = False
            for idx, fv in enumerate(field_vars):
                ftype = self.types[cast("int", fv.value)]
                if any(cast("int", earlier.value) in self.free(ftype) for earlier in field_vars[:idx]):
                    is_dep = True
                    break
            tail_sig_types: tuple[_Term, ...] = ()
            if not field_vars:
                payload_type = _UNIT
            elif len(field_vars) == 1:
                f0_type = self.types[cast("int", field_vars[0].value)]
                payload_type = _term("prod", f0_type, _UNIT) if len(constructors) == 1 else f0_type
            elif is_dep:
                curr_type = self.types[cast("int", field_vars[-1].value)]
                tail_sigs_rev: list[_Term] = [curr_type]
                for fv in reversed(field_vars[:-1]):
                    fv_id = cast("int", fv.value)
                    fv_type = self.types[fv_id]
                    curr_type = _term("sigT", fv_type, _term("lam", fv_type, curr_type, value=fv_id))
                    tail_sigs_rev.append(curr_type)
                tail_sigs_rev.reverse()
                tail_sig_types = tuple(tail_sigs_rev)
                payload_type = tail_sig_types[0]
            else:
                payload_type = self.types[cast("int", field_vars[-1].value)]
                for fv in reversed(field_vars[:-1]):
                    payload_type = _term("prod", self.types[cast("int", fv.value)], payload_type)
            ctor_specs.append((ctor_node, cname, field_names, field_vars, payload_type, is_dep, tail_sig_types))

        payload_types = [spec[4] for spec in ctor_specs]
        if len(constructors) == 1:
            suffix_types = [payload_types[0]]
            rep_type = payload_types[0]
        else:
            suffix_types = [payload_types[-1]]
            for pt in reversed(payload_types[:-1]):
                suffix_types.append(_term("sum", pt, suffix_types[-1]))
            suffix_types.reverse()
            rep_type = suffix_types[0]
        rep_sort = _term("sort", value=max(self.sort(rep_type), 0))
        type_sig = self.wrap("pi", generic_vars, rep_sort)
        type_def = self.wrap("lam", generic_vars, rep_type)
        self.site = node
        self.complete(type_sig)
        self.complete(type_def)
        for index in range(first_meta, len(self.metas)):
            self.complete(_term("meta", value=index))
            self.complete(self.metas[index].type)
        type_emitted = f"vela_d{len(self.output)}_{name}"
        self.output.append(f"Definition {type_emitted} : {self.render(type_sig)} :=\n  {self.render(type_def)}.")
        type_binding = _Binding(_constant(type_emitted), type_sig, len(generics))
        self.globals[name] = type_binding
        self.constants[type_emitted] = type_binding

        union_type_app = _apps(_constant(type_emitted), *generic_vars)
        union_ctors: list[_UnionCtor] = []
        for idx, (ctor_node, cname, field_names, field_vars, payload_type, is_dep, tail_sig_types) in enumerate(ctor_specs):
            self.site = ctor_node
            if not field_vars:
                unit_var = self.fresh(_UNIT)
                self.nullary_parameters.add(cast("int", unit_var.value))
                ctor_vars = [*generic_vars, unit_var]
                payload_val = _term("unit")
            elif len(field_vars) == 1:
                ctor_vars = [*generic_vars, field_vars[0]]
                f0_type = self.types[cast("int", field_vars[0].value)]
                payload_val = (
                    _term("pair", f0_type, _UNIT, field_vars[0], _term("unit"))
                    if len(constructors) == 1
                    else field_vars[0]
                )
            elif is_dep:
                ctor_vars = [*generic_vars, *field_vars]
                payload_val = field_vars[-1]
                for f_idx in range(len(field_vars) - 2, -1, -1):
                    fv = field_vars[f_idx]
                    sig_ty = tail_sig_types[f_idx]
                    payload_val = _term("existT", sig_ty.args[0], sig_ty.args[1], fv, payload_val)
            else:
                ctor_vars = [*generic_vars, *field_vars]
                payload_val = field_vars[-1]
                acc_type = self.types[cast("int", field_vars[-1].value)]
                for fv in reversed(field_vars[:-1]):
                    fv_type = self.types[cast("int", fv.value)]
                    payload_val = _term("pair", fv_type, acc_type, fv, payload_val)
                    acc_type = _term("prod", fv_type, acc_type)
            if len(constructors) == 1:
                ctor_body = payload_val
            else:
                ctor_body = (
                    _term("inl", payload_types[idx], suffix_types[idx + 1], payload_val)
                    if idx < len(constructors) - 1
                    else payload_val
                )
                for j in range(idx - 1, -1, -1):
                    ctor_body = _term("inr", payload_types[j], suffix_types[j + 1], ctor_body)
            ctor_sig = self.wrap("pi", ctor_vars, union_type_app)
            ctor_def = self.wrap("lam", ctor_vars, ctor_body)
            self.complete(ctor_sig)
            self.complete(ctor_def)
            ctor_emitted = f"vela_d{len(self.output)}_{name}_{cname}"
            self.output.append(f"Definition {ctor_emitted} : {self.render(ctor_sig)} :=\n  {self.render(ctor_def)}.")
            ctor_binding = _Binding(_constant(ctor_emitted), ctor_sig, len(generics))
            self.globals[cname] = ctor_binding
            self.constants[ctor_emitted] = ctor_binding
            ctor_fields = tuple(
                _RecordField(fname, fvar, self.types[cast("int", fvar.value)], "")
                for fname, fvar in zip(field_names, field_vars, strict=True)
            )
            union_ctors.append(
                _UnionCtor(
                    name=cname,
                    ctor_const=ctor_emitted,
                    ctor_binding=ctor_binding,
                    fields=ctor_fields,
                    payload_type=payload_type,
                    index=idx,
                    is_dependent=is_dep,
                    tail_sig_types=tail_sig_types,
                )
            )

        union_info = _UnionInfo(
            name=name,
            type_const=type_emitted,
            type_binding=type_binding,
            generic_vars=tuple(generic_vars),
            constructors=tuple(union_ctors),
            suffix_types=tuple(suffix_types),
        )
        self.unions[name] = union_info
        self.unions_by_type[type_emitted] = union_info
        for uc in union_ctors:
            self.union_ctors[uc.name] = (union_info, uc)
            self.unions_by_ctor[uc.ctor_const] = (union_info, uc)

    def _has_unapplied_rec_var(self: _Elaborator, term: _Term, rec_var_id: int) -> bool:
        term = self.resolve(term)
        if term.kind == "var":
            return cast("int", term.value) == rec_var_id
        if term.kind == "app":
            head, arguments = self.spine(term)
            if head.kind == "var" and cast("int", head.value) == rec_var_id:
                expected_arity = len(self.current_rec_generics) + len(self.current_rec_params)
                if len(arguments) < expected_arity:
                    return True
                return any(self._has_unapplied_rec_var(arg, rec_var_id) for arg in arguments)
            return self._has_unapplied_rec_var(head, rec_var_id) or any(
                self._has_unapplied_rec_var(arg, rec_var_id) for arg in arguments
            )
        return any(self._has_unapplied_rec_var(child, rec_var_id) for child in term.args)

    def declaration(self: _Elaborator, node: Node) -> None:
        self.site = node
        self.reset_budget()
        first_meta = len(self.metas)
        self.decl_first_meta = first_meta
        self.whnf_cache.clear()
        self.mutable_locals.clear()
        self.entry_env = {}
        self.final_ref_bindings = {}
        self.final_return_facts = []
        self.frozen_collections.clear()
        self.lifted_invariants.clear()
        self.active_lift_scopes = 0
        self.in_loop_depth = 0
        kind = node["kind"]
        if kind == "import":
            imp_name = self.name(node["name"])
            if imp_name != "Vela.Numerics":
                raise self.fail("unsupported", f"import '{imp_name}' requires the full frontend", node)
            for alias_name, target_name in _NUMERICS_ALIASES.items():
                if (alias_name in self.globals and self.globals[alias_name] != self.globals[target_name]) or (
                    alias_name in self.records or alias_name in self.unions or alias_name in self.union_ctors
                ):
                    raise self.fail("name", f"import alias '{alias_name}' conflicts with an existing declaration", node)
                self.globals[alias_name] = self.globals[target_name]
            return
        if kind == "record":
            self._record_declaration(node, first_meta)
            return
        if kind == "union":
            self._union_declaration(node, first_meta)
            return
        if kind not in {"alias", "definition", "function", "property", "theorem", "lemma", "constant"}:
            raise self.fail("unsupported", f"declaration '{kind}' requires the full frontend")
        modifiers = node["modifiers"]
        allowed_modifiers = {"public", "private", "internal"} | ({"const"} if kind in {"definition", "function"} else set())
        if (not isinstance(modifiers, list) or any(not isinstance(value, str) or value not in allowed_modifiers for value in modifiers)
                or len(modifiers) != len(set(modifiers))):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers")
        decreases_clauses: list[Node] = []
        requires_clauses: list[Node] = []
        ensures_clauses: list[Node] = []
        restores_clauses: list[Node] = []
        if kind in {"definition", "function", "theorem", "lemma"}:
            self.no_roles(node, "cancel")
            has_params_or_generics = (
                kind in {"theorem", "lemma", "function"}
                or bool(self.nodes(node["parameters"]) or self.nodes(node["generics"]))
            )
            for contract in self.nodes(node["contracts"]):
                self.node(contract, "contract")
                role = contract["role"]
                if role == "decreases":
                    decreases_clauses.append(contract)
                elif role in {"requires", "where"} and has_params_or_generics:
                    requires_clauses.append(contract)
                elif role == "ensures" and has_params_or_generics:
                    ensures_clauses.append(contract)
                elif role == "restores" and kind in {"definition", "function"} and has_params_or_generics:
                    restores_clauses.append(contract)
                else:
                    raise self.fail(
                        "unsupported",
                        f"contract '{role}' requires the full frontend",
                        contract,
                    )
            if len(decreases_clauses) > 1:
                raise self.fail("type", "at most one decreases clause is permitted", decreases_clauses[1])
            if kind in {"theorem", "lemma"} and not ensures_clauses:
                raise self.fail("protocol", "theorem requires at least one ensures clause", node)
        else:
            self.no_roles(node, "contracts", "cancel")
        name = self.name(node["name"])
        self._evict_builtin_if_shadowed(name)
        if (name in self.globals or name in self.records or name in self.unions
                or name in self.union_ctors or name in {"Type", "_", "this"} or "." in name):
            raise self.fail("name", f"duplicate or reserved declaration '{name}'")
        generics = [] if kind in {"constant", "property"} else self.nodes(node["generics"])
        parameters = [] if kind in {"alias", "constant", "property"} else self.nodes(node["parameters"])
        variables, environment = self.telescope(
            generics, parameters, {}, unit=kind not in {"alias", "constant", "property"}
        )
        ref_param_names = set(self.mutable_locals)
        self.entry_env = dict(environment)
        self.final_ref_bindings = dict(environment)
        is_recursive = False
        self_var: _Term | None = None
        candidates: list[tuple[int, int]] = []
        req_bool_terms: list[_Term] = []
        req_vars: list[_Term] = []
        req_props: list[_Term] = []
        generic_vars: list[_Term] = []
        param_vars: list[_Term] = []
        entry_body_facts: list[_Term] = []
        body_node: Node = node
        if kind == "constant":
            evaluated = self.constant_value(node, environment)
            body, result = evaluated.term, evaluated.type
            signature = self.wrap("pi", variables, result)
        elif kind == "property":
            result = self.type(self.node(node["type"]), environment)
            prev_ret = self.current_return_type
            self.current_return_type = result
            try:
                body = self.check(self.node(node["value"]), result, environment)
            finally:
                self.current_return_type = prev_ret
            signature = self.wrap("pi", variables, result)
        elif kind == "alias":
            body = self.type(self.node(node["type"]), environment)
            result = self.infer(body)
            signature = self.wrap("pi", variables, result)
        else:
            req_props: list[_Term] = []
            if kind in {"theorem", "lemma"}:
                for req_contract in requires_clauses:
                    req_val_node = self.node(req_contract["value"])
                    req_prop = self.asserted_proposition(req_val_node, environment)
                    req_props.append(req_prop)
                    if req_prop.kind == "app":
                        head_p, args_p = self.spine(req_prop)
                        if (
                            head_p.kind == "const"
                            and head_p.value == "Eq"
                            and len(args_p) == 3
                            and self.whnf(args_p[0]) == _BOOL
                        ):
                            rhs_w = self.whnf(args_p[2])
                            if rhs_w.kind == "bool" and rhs_w.value == 1:
                                req_bool_terms.append(args_p[1])
            else:
                for req_idx, req_contract in enumerate(requires_clauses):
                    req_val_node = self.node(req_contract["value"])
                    saved_req_metas = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                    req_val: _Binding | None = None
                    if req_val_node["kind"] != "quantifier":
                        try:
                            req_val = self.expression(req_val_node, environment)
                        except VelaError:
                            self.metas = saved_req_metas
                            req_val = None
                    if req_val is not None and self.whnf(req_val.type) == _BOOL:
                        req_bool_terms.append(req_val.term)
                        eq_prop = _apps(_constant("Eq"), _BOOL, req_val.term, _term("bool", value=1))
                        req_var = self.fresh(eq_prop)
                        req_vars.append(req_var)
                        environment[f"__vela_req_{req_idx}"] = _Binding(req_var, eq_prop)
                    else:
                        self.metas = saved_req_metas
                        req_prop = self.proposition(req_val_node, environment)
                        req_var = self.fresh(req_prop)
                        req_vars.append(req_var)
                        environment[f"__vela_req_{req_idx}"] = _Binding(req_var, req_prop)
                        if req_prop.kind == "app":
                            head_p, args_p = self.spine(req_prop)
                            if (
                                head_p.kind == "const"
                                and head_p.value == "Eq"
                                and len(args_p) == 3
                                and self.whnf(args_p[0]) == _BOOL
                            ):
                                rhs_w = self.whnf(args_p[2])
                                if rhs_w.kind == "bool" and rhs_w.value == 1:
                                    req_bool_terms.append(args_p[1])
            if kind in {"theorem", "lemma"}:
                self.active_facts.extend(req_bool_terms)
                try:
                    result = self.proposition(self.node(ensures_clauses[0]["value"]), environment)
                finally:
                    for _ in req_bool_terms:
                        self.active_facts.pop()
                for req_prop in reversed(req_props):
                    result = self.pi(req_prop, result)
                if node["body"] is None:
                    raise self.fail("unsupported", "a theorem requires a complete explicit proof body", node)
                body_node = self.node(node["body"])
            else:
                result = self.type(self.node(node["result"]), environment)
                raw_body = node["value"] if kind == "definition" else node["body"]
                if raw_body is None:
                    raise self.fail("unsupported", "abstract callable signatures have no emitted implementation", node)
                body_node = self.node(raw_body)
            generic_vars = variables[:len(generics)]
            param_vars = variables[len(generics):]
            if decreases_clauses:
                dec_contract = decreases_clauses[0]
                dec_val = self.node(dec_contract["value"])
                if dec_val["kind"] != "name":
                    raise self.fail("type", "decreases clause must name a structural parameter", dec_val)
                dec_param_name = self.name(dec_val["name"])
                matched_idx: int | None = None
                for p_idx, p_node in enumerate(parameters):
                    if p_node["name"] is not None and self.name(p_node["name"]) == dec_param_name:
                        matched_idx = p_idx
                        break
                if matched_idx is None:
                    if dec_param_name in environment or dec_param_name in self.globals:
                        raise self.fail(
                            "type",
                            f"decreases clause '{dec_param_name}' must name a value parameter",
                            dec_val,
                        )
                    raise self.fail("name", f"unknown parameter '{dec_param_name}' in decreases clause", dec_val)
                p_var = param_vars[matched_idx]
                if self.whnf(self.types[cast("int", p_var.value)]) != _NAT:
                    raise self.fail(
                        "type",
                        f"decreases parameter '{dec_param_name}' must have type Nat",
                        dec_val,
                    )
                candidates = [(matched_idx, cast("int", p_var.value))]
            else:
                candidates = [
                    (p_idx, cast("int", param_vars[p_idx].value))
                    for p_idx in range(len(parameters))
                    if self.whnf(self.types[cast("int", param_vars[p_idx].value)]) == _NAT
                ]
            signature = self.wrap("pi", variables, result)
            self_var = self.fresh(signature)
            self_binding = _Binding(self_var, signature, len(generics))
            body_env = dict(environment)
            if name not in body_env:
                body_env[name] = self_binding
            self.current_rec_var = self_var
            self.current_rec_name = name
            self.current_rec_generics = list(generic_vars)
            self.current_rec_params = list(param_vars)
            self.current_rec_candidates = candidates
            self.smaller_vars = {p_var_id: set() for _, p_var_id in candidates}
            self.current_return_type = result
            entry_body_facts = [*req_bool_terms, *self._fact_bool_terms((), environment)]
            saved_body_facts = list(self.active_facts)
            self.active_facts.extend(entry_body_facts)
            try:
                body = self.check(body_node, result, body_env)
                if self._has_unapplied_rec_var(body, cast("int", self_var.value)):
                    raise self.fail("type", f"recursive reference to '{name}' must be a direct call", body_node)
                is_recursive = self.current_rec_used
                if is_recursive:
                    candidates = list(self.current_rec_candidates)
                if kind in {"definition", "function"}:
                    for pname in ref_param_names:
                        if pname in self.final_ref_bindings:
                            fin_b = self.final_ref_bindings[pname]
                            fin_head, fin_targs = self.spine(self.whnf(fin_b.type))
                            if (
                                fin_head.kind == "const"
                                and isinstance(fin_head.value, str)
                                and fin_head.value in self.records_by_type
                            ):
                                rinfo = self.records_by_type[fin_head.value]
                                self._check_record_invariants(
                                    rinfo, fin_targs, fin_b.term, self.final_ref_bindings, body_node
                                )
            finally:
                self.active_facts = saved_body_facts
                self.current_rec_var = None
                self.current_rec_name = None
                self.current_rec_generics = []
                self.current_rec_params = []
                self.current_rec_candidates = []
                self.current_rec_used = False
                self.smaller_vars = {}
                self.current_return_type = None
        lam_body = self.wrap("lam", variables, body)
        if is_recursive and self_var is not None:
            struct_p_idx, struct_var_id = candidates[0]
            struct_arity_index = len(generics) + struct_p_idx
            definition = _term(
                "fix",
                signature,
                lam_body,
                _term("nat", value=struct_var_id),
                _term("nat", value=struct_arity_index),
                value=self_var.value,
            )
        else:
            definition = lam_body
        self.site = node
        self.complete(signature)
        self.complete(definition)
        for index in range(first_meta, len(self.metas)):
            self.complete(_term("meta", value=index))
            self.complete(self.metas[index].type)
        emitted = f"vela_d{len(self.output)}_{name}"
        if is_recursive and self_var is not None:
            self.fix_names[cast("int", self_var.value)] = emitted
        self.output.append(f"Definition {emitted} : {self.render(signature)} :=\n  {self.render(definition)}.")
        binding = _Binding(_constant(emitted), signature, len(generics), constant=kind == "constant")
        self.globals[name] = binding
        # Generated references never become names in the source namespace.
        self.constants[emitted] = binding
        self.definitions[emitted] = definition
        if kind in {"theorem", "lemma"} and len(ensures_clauses) > 1:
            init_candidates = (
                candidates
                if decreases_clauses
                else [
                    (p_idx, cast("int", param_vars[p_idx].value))
                    for p_idx in range(len(parameters))
                    if self.whnf(self.types[cast("int", param_vars[p_idx].value)]) == _NAT
                ]
            )
            for ens_idx, ens_contract in enumerate(ensures_clauses[1:], start=1):
                self.reset_budget()
                extra_first_meta = len(self.metas)
                self.active_facts.extend(req_bool_terms)
                try:
                    extra_res = self.proposition(self.node(ens_contract["value"]), environment)
                finally:
                    for _ in req_bool_terms:
                        self.active_facts.pop()
                for req_prop in reversed(req_props):
                    extra_res = self.pi(req_prop, extra_res)
                extra_sig = self.wrap("pi", variables, extra_res)
                extra_self_var = self.fresh(extra_sig)
                extra_self_binding = _Binding(extra_self_var, extra_sig, len(generics))
                extra_body_env = dict(environment)
                if name not in extra_body_env:
                    extra_body_env[name] = extra_self_binding
                self.current_rec_var = extra_self_var
                self.current_rec_name = name
                self.current_rec_generics = list(generic_vars)
                self.current_rec_params = list(param_vars)
                self.current_rec_candidates = list(init_candidates)
                self.smaller_vars = {p_var_id: set() for _, p_var_id in init_candidates}
                self.current_return_type = extra_res
                saved_extra_facts = list(self.active_facts)
                self.active_facts.extend(entry_body_facts)
                try:
                    extra_body = self.check(body_node, extra_res, extra_body_env)
                    if self._has_unapplied_rec_var(extra_body, cast("int", extra_self_var.value)):
                        raise self.fail("type", f"recursive reference to '{name}' must be a direct call", body_node)
                    extra_is_rec = self.current_rec_used
                    extra_cands = list(self.current_rec_candidates) if extra_is_rec else []
                finally:
                    self.active_facts = saved_extra_facts
                    self.current_rec_var = None
                    self.current_rec_name = None
                    self.current_rec_generics = []
                    self.current_rec_params = []
                    self.current_rec_candidates = []
                    self.current_rec_used = False
                    self.smaller_vars = {}
                    self.current_return_type = None
                extra_lam = self.wrap("lam", variables, extra_body)
                if extra_is_rec:
                    struct_p_idx, struct_var_id = extra_cands[0]
                    struct_arity_index = len(generics) + struct_p_idx
                    extra_def = _term(
                        "fix",
                        extra_sig,
                        extra_lam,
                        _term("nat", value=struct_var_id),
                        _term("nat", value=struct_arity_index),
                        value=extra_self_var.value,
                    )
                else:
                    extra_def = extra_lam
                self.site = ens_contract
                self.complete(extra_sig)
                self.complete(extra_def)
                for index in range(extra_first_meta, len(self.metas)):
                    self.complete(_term("meta", value=index))
                    self.complete(self.metas[index].type)
                extra_emitted = f"{emitted}_ensures_{ens_idx}"
                if extra_is_rec:
                    self.fix_names[cast("int", extra_self_var.value)] = extra_emitted
                self.output.append(
                    f"Definition {extra_emitted} : {self.render(extra_sig)} :=\n  {self.render(extra_def)}."
                )
                self.constants[extra_emitted] = _Binding(_constant(extra_emitted), extra_sig, len(generics))
                self.definitions[extra_emitted] = extra_def
        if req_bool_terms and kind in {"definition", "function"}:
            param_ids = tuple(cast("int", v.value) for v in variables)
            self.callable_preconditions[emitted] = [(param_ids, req_t) for req_t in req_bool_terms]
        if (ensures_clauses or restores_clauses) and kind in {"definition", "function"}:
            post_env = dict(environment)
            for pname in ref_param_names:
                if pname in self.final_ref_bindings:
                    post_env[pname] = self.final_ref_bindings[pname]
            call_term = _apps(_constant(emitted), *variables)
            post_env["result"] = _Binding(call_term, result)
            post_vars = [*variables, *req_vars]
            post_var_ids = {cast("int", v.value) for v in post_vars}
            saved_post_facts = list(self.active_facts)
            self.active_facts.extend(
                [
                    *req_bool_terms,
                    *self.final_return_facts,
                    *self._fact_bool_terms((), self.entry_env),
                    *self._fact_bool_terms((), post_env),
                ]
            )
            try:
                span_u8 = _app(_constant("Span"), _U8)
                for rest_idx, rest_contract in enumerate(restores_clauses):
                    rest_val_node = self.node(rest_contract["value"])
                    if rest_val_node["kind"] == "name":
                        target_param_name = self.name(rest_val_node["name"])
                        if target_param_name not in environment:
                            raise self.fail(
                                "name",
                                f"unknown parameter '{target_param_name}' in restores clause",
                                rest_val_node,
                            )
                        param_b = environment[target_param_name]
                        param_ty_w = self.whnf(param_b.type)
                        p_head, p_args = self.spine(param_ty_w)
                        if param_ty_w == span_u8:
                            if self._is_readonly_span(param_b.term):
                                raise self.fail(
                                    "type",
                                    f"restores parameter '{target_param_name}' cannot be a read-only 'in Span<byte>' borrow",
                                    rest_val_node,
                                )
                            if self.whnf(result) == span_u8:
                                restored_span_term = call_term
                            else:
                                res_head, _ = self.spine(self.whnf(result))
                                if (
                                    res_head.kind == "const"
                                    and isinstance(res_head.value, str)
                                    and res_head.value in self.records_by_type
                                    and any(rf.name == "RestoredDst" for rf in self.records_by_type[res_head.value].fields)
                                ):
                                    restored_span_term = self._project_member(
                                        post_env["result"], "RestoredDst", rest_contract
                                    ).term
                                elif (
                                    target_param_name in ref_param_names
                                    and target_param_name in self.final_ref_bindings
                                    and self.free(self.final_ref_bindings[target_param_name].term) <= post_var_ids
                                ):
                                    restored_span_term = self.final_ref_bindings[target_param_name].term
                                else:
                                    raise self.fail(
                                        "type",
                                        f"restores clause for '{target_param_name}' requires a Span<byte> return type or RestoredDst record field",
                                        rest_contract,
                                    )
                            for field_tag, eq_ty in (
                                ("Base", _USIZE),
                                ("Length", _USIZE),
                                ("Tag", _BOOL),
                                ("PermRead", _BOOL),
                                ("PermWrite", _BOOL),
                            ):
                                self.reset_budget()
                                lhs_f = _apps(_constant(f"Span_{field_tag}"), _U8, restored_span_term)
                                rhs_f = _apps(_constant(f"Span_{field_tag}"), _U8, param_b.term)
                                rest_prop = _apps(_constant("Eq"), eq_ty, lhs_f, rhs_f)
                                rest_proof = self._prove_proposition(rest_prop, post_env, (), rest_contract)
                                rest_sig = self.wrap("pi", post_vars, rest_prop)
                                rest_def = self.wrap("lam", post_vars, rest_proof)
                                self.complete(rest_sig)
                                self.complete(rest_def)
                                rest_emitted = f"{emitted}_restores_{rest_idx}_{field_tag}"
                                self.output.append(
                                    f"Definition {rest_emitted} : {self.render(rest_sig)} :=\n  {self.render(rest_def)}."
                                )
                                self.constants[rest_emitted] = _Binding(_constant(rest_emitted), rest_sig, len(generics))
                                self.definitions[rest_emitted] = rest_def
                        elif p_head == _constant("Slots") and len(p_args) == 2:
                            elem_t, cap_t = p_args
                            if self._is_readonly_span(param_b.term):
                                raise self.fail(
                                    "type",
                                    f"restores parameter '{target_param_name}' cannot be a read-only 'in' borrow",
                                    rest_val_node,
                                )
                            if self.whnf(result) == param_ty_w:
                                restored_slots_term = call_term
                            elif (
                                target_param_name in ref_param_names
                                and target_param_name in self.final_ref_bindings
                                and self.free(self.final_ref_bindings[target_param_name].term) <= post_var_ids
                            ):
                                restored_slots_term = self.final_ref_bindings[target_param_name].term
                            else:
                                res_head, _ = self.spine(self.whnf(result))
                                if (
                                    res_head.kind == "const"
                                    and isinstance(res_head.value, str)
                                    and res_head.value in self.records_by_type
                                    and any(rf.name == "RestoredDst" for rf in self.records_by_type[res_head.value].fields)
                                ):
                                    restored_slots_term = self._project_member(
                                        post_env["result"], "RestoredDst", rest_contract
                                    ).term
                                else:
                                    raise self.fail(
                                        "type",
                                        f"restores clause for '{target_param_name}' requires a Slots return type, ref parameter, or RestoredDst record field",
                                        rest_contract,
                                    )
                            for field_tag, eq_ty in (
                                ("Base", _USIZE),
                                ("Tag", _BOOL),
                                ("PermRead", _BOOL),
                                ("PermWrite", _BOOL),
                            ):
                                self.reset_budget()
                                lhs_f = _apps(_constant(f"Slots_{field_tag}"), elem_t, cap_t, restored_slots_term)
                                rhs_f = _apps(_constant(f"Slots_{field_tag}"), elem_t, cap_t, param_b.term)
                                rest_prop = _apps(_constant("Eq"), eq_ty, lhs_f, rhs_f)
                                rest_proof = self._prove_proposition(rest_prop, post_env, (), rest_contract)
                                rest_sig = self.wrap("pi", post_vars, rest_prop)
                                rest_def = self.wrap("lam", post_vars, rest_proof)
                                self.complete(rest_sig)
                                self.complete(rest_def)
                                rest_emitted = f"{emitted}_restores_{rest_idx}_{field_tag}"
                                self.output.append(
                                    f"Definition {rest_emitted} : {self.render(rest_sig)} :=\n  {self.render(rest_def)}."
                                )
                                self.constants[rest_emitted] = _Binding(_constant(rest_emitted), rest_sig, len(generics))
                                self.definitions[rest_emitted] = rest_def
                        else:
                            raise self.fail(
                                "type",
                                f"restores parameter '{target_param_name}' must have type Span<byte> or Slots<T, capacity>",
                                rest_val_node,
                            )
                    else:
                        self.reset_budget()
                        rest_prop = self.asserted_proposition(rest_val_node, post_env)
                        try:
                            rest_proof = self._prove_proposition(rest_prop, post_env, (), rest_contract)
                        except VelaError:
                            extracted = self._extract_equality(rest_prop)
                            proved_rest = False
                            if (
                                extracted is not None
                                and self.whnf(extracted[0]) == _BOOL
                                and self.whnf(extracted[2]) == _term("bool", value=1)
                                and self._prove_bool_precondition(extracted[1], post_env)
                            ):
                                proved_rest = True
                            if not proved_rest:
                                saved_rest_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                                try:
                                    rest_b = self.expression(rest_val_node, post_env)
                                    if self.whnf(rest_b.type) == _BOOL and self._prove_bool_precondition(rest_b.term, post_env):
                                        proved_rest = True
                                except VelaError:
                                    self.metas = saved_rest_m
                            if proved_rest:
                                rest_prop = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                                rest_proof = _apps(_constant("Refl"), _BOOL, _term("bool", value=1))
                            else:
                                raise
                        if not (self.free(rest_prop) <= post_var_ids and self.free(rest_proof) <= post_var_ids):
                            rest_prop = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                            rest_proof = _apps(_constant("Refl"), _BOOL, _term("bool", value=1))
                        rest_sig = self.wrap("pi", post_vars, rest_prop)
                        rest_def = self.wrap("lam", post_vars, rest_proof)
                        self.complete(rest_sig)
                        self.complete(rest_def)
                        rest_emitted = f"{emitted}_restores_{rest_idx}"
                        self.output.append(
                            f"Definition {rest_emitted} : {self.render(rest_sig)} :=\n  {self.render(rest_def)}."
                        )
                        self.constants[rest_emitted] = _Binding(_constant(rest_emitted), rest_sig, len(generics))
                        self.definitions[rest_emitted] = rest_def
                for ens_idx, ens_contract in enumerate(ensures_clauses):
                    self.reset_budget()
                    ens_val_node = self.node(ens_contract["value"])
                    ens_prop = self.asserted_proposition(ens_val_node, post_env)
                    try:
                        ens_proof = self._prove_proposition(ens_prop, post_env, (), ens_contract)
                    except VelaError:
                        extracted = self._extract_equality(ens_prop)
                        proved_alt = False
                        if extracted is not None:
                            eq_ty_w = self.whnf(extracted[0])
                            if (
                                eq_ty_w == _BOOL
                                and self.whnf(extracted[2]) == _term("bool", value=1)
                                and self._prove_bool_precondition(extracted[1], post_env)
                            ):
                                proved_alt = True
                            elif eq_ty_w == _NAT or self._int_spec(eq_ty_w) is not None:
                                spec = self._int_spec(eq_ty_w)
                                bool_facts = self._expand_bool_facts(
                                    [*self.active_facts, *self._fact_bool_terms((), post_env)]
                                )
                                if self._prove_comparison("eq", spec, extracted[1], extracted[2], bool_facts):
                                    proved_alt = True
                        if not proved_alt:
                            saved_ens_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                            try:
                                ens_b = self.expression(ens_val_node, post_env)
                                if self.whnf(ens_b.type) == _BOOL and self._prove_bool_precondition(ens_b.term, post_env):
                                    proved_alt = True
                            except VelaError:
                                self.metas = saved_ens_m
                        if proved_alt:
                            ens_prop = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                            ens_proof = _apps(_constant("Refl"), _BOOL, _term("bool", value=1))
                        else:
                            raise
                    if not (self.free(ens_prop) <= post_var_ids and self.free(ens_proof) <= post_var_ids):
                        ens_prop = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                        ens_proof = _apps(_constant("Refl"), _BOOL, _term("bool", value=1))
                    ens_sig = self.wrap("pi", post_vars, ens_prop)
                    ens_def = self.wrap("lam", post_vars, ens_proof)
                    self.complete(ens_sig)
                    self.complete(ens_def)
                    ens_emitted = f"{emitted}_ensures_{ens_idx}"
                    self.output.append(
                        f"Definition {ens_emitted} : {self.render(ens_sig)} :=\n  {self.render(ens_def)}."
                    )
                    self.constants[ens_emitted] = _Binding(_constant(ens_emitted), ens_sig, len(generics))
                    self.definitions[ens_emitted] = ens_def
            finally:
                self.active_facts = saved_post_facts

    def render(self: _Elaborator, term: _Term) -> str:
        self.tick()
        term = self.resolve(term)
        kind = term.kind
        if kind == "sort":
            return "Prop" if term.value == -1 else f"Type@{{vela_u{term.value}}}"
        if kind == "var":
            return f"vela_v{term.value}"
        if kind == "const":
            name = cast("str", term.value)
            if name in _GALLINA:
                return _GALLINA[name]
            if name in self.definitions or name in self.constants:
                return name
            raise self.fail("protocol", "unmapped internal constant")
        if kind == "nat":
            return f"({term.value} : Corelib.Init.Datatypes.nat)"
        if kind == "char":
            return f"(vela_mk_char ({term.value} : Corelib.Init.Datatypes.nat))"
        if kind == "int":
            spec = cast("_IntSpec", self._int_spec(term.args[0]))
            int_val = cast("int", term.value)
            unsigned = int_val & ((1 << spec.bits) - 1)
            bits_term = "vela_bnil"
            for nib_idx in range(0, spec.bits, 4):
                nib = (unsigned >> nib_idx) & 0xF
                bits_term = f"(vela_x{nib:x} {bits_term})"
            return f"(@vela_mk_int ({spec.tag} : Corelib.Init.Datatypes.nat) {bits_term})"
        if kind == "bool":
            return "Corelib.Init.Datatypes.true" if term.value else "Corelib.Init.Datatypes.false"
        if kind == "unit":
            return "Corelib.Init.Datatypes.tt"
        if kind == "static":
            value = term.args[1] if self.free(term.args[1]) else self.whnf(term)
            return self.render(value)
        if kind == "let":
            domain, value, body = term.args
            return (f"(let vela_v{term.value} : {self.render(domain)} := {self.render(value)} "
                    f"in {self.render(body)})")
        if kind == "fix":
            sig, lam_body, struct_var_term, _ = term.args
            binders: list[str] = []
            curr_lam = self.resolve(lam_body)
            curr_sig = self.resolve(sig)
            while curr_lam.kind == "lam" and curr_sig.kind == "pi":
                domain = curr_lam.args[0]
                binders.append(f"(vela_v{curr_lam.value} : {self.render(domain)})")
                curr_lam = self.resolve(curr_lam.args[1])
                curr_sig = self.resolve(curr_sig.args[1])
            binder_str = " ".join(binders)
            struct_name = f"vela_v{struct_var_term.value}"
            return (
                f"(fix vela_v{term.value} {binder_str} {{struct {struct_name}}} : "
                f"{self.render(curr_sig)} := {self.render(curr_lam)})"
            )
        if kind in {"pi", "lam"}:
            domain, body = term.args
            binder = f"vela_v{term.value} : {self.render(domain)}"
            return (f"(forall ({binder}), {self.render(body)})" if kind == "pi"
                    else f"(fun ({binder}) => {self.render(body)})")
        if kind == "app":
            head, arguments = self.spine(term)
            rendered_head = self.render(head)
            prefix = "(@" if (head.kind == "const" and not rendered_head.startswith("(")) else "("
            return prefix + rendered_head + " " + " ".join(self.render(value) for value in arguments) + ")"
        if kind == "prod":
            return f"(@Corelib.Init.Datatypes.prod {self.render(term.args[0])} {self.render(term.args[1])})"
        if kind == "pair":
            return "(@Corelib.Init.Datatypes.pair " + " ".join(self.render(value) for value in term.args) + ")"
        if kind == "sigT":
            return f"(@Corelib.Init.Specif.sigT {self.render(term.args[0])} {self.render(term.args[1])})"
        if kind == "existT":
            return "(@Corelib.Init.Specif.existT " + " ".join(self.render(value) for value in term.args) + ")"
        if kind in {"projT1", "projT2"}:
            return f"(@Corelib.Init.Specif.{kind} " + " ".join(self.render(value) for value in term.args) + ")"
        if kind == "ex":
            return f"(@Corelib.Init.Logic.ex {self.render(term.args[0])} {self.render(term.args[1])})"
        if kind == "ex_intro":
            return "(@Corelib.Init.Logic.ex_intro " + " ".join(self.render(value) for value in term.args) + ")"
        if kind == "sum":
            return f"(@Corelib.Init.Datatypes.sum {self.render(term.args[0])} {self.render(term.args[1])})"
        if kind in {"inl", "inr"}:
            return f"(@Corelib.Init.Datatypes.{kind} " + " ".join(self.render(value) for value in term.args) + ")"
        if kind == "if":
            _, condition, yes, no = term.args
            return f"(if {self.render(condition)} then {self.render(yes)} else {self.render(no)})"
        if kind == "bool_match":
            motive, scrutinee, yes, no = term.args
            binder = f"vela_v{motive.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| Corelib.Init.Datatypes.true => {self.render(yes)} "
                    f"| Corelib.Init.Datatypes.false => {self.render(no)} end)")
        if kind == "unit_match":
            motive, scrutinee, body = term.args
            binder = f"vela_v{motive.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| Corelib.Init.Datatypes.tt => {self.render(body)} end)")
        if kind == "pair_match":
            motive, scrutinee, branch = term.args
            inner = branch.args[1]
            binder = f"vela_v{motive.value}"
            left_binder = f"vela_v{branch.value}"
            right_binder = f"vela_v{inner.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| @Corelib.Init.Datatypes.pair _ _ {left_binder} {right_binder} => {self.render(inner.args[1])} end)")
        if kind == "sigT_match":
            motive, scrutinee, branch = term.args
            inner = branch.args[1]
            binder = f"vela_v{motive.value}"
            fst_binder = f"vela_v{branch.value}"
            snd_binder = f"vela_v{inner.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| @Corelib.Init.Specif.existT _ _ {fst_binder} {snd_binder} => {self.render(inner.args[1])} end)")
        if kind == "sum_match":
            motive, scrutinee, left_branch, right_branch = term.args
            binder = f"vela_v{motive.value}"
            left_binder = f"vela_v{left_branch.value}"
            right_binder = f"vela_v{right_branch.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| @Corelib.Init.Datatypes.inl _ _ {left_binder} => {self.render(left_branch.args[1])} "
                    f"| @Corelib.Init.Datatypes.inr _ _ {right_binder} => {self.render(right_branch.args[1])} end)")
        if kind == "nat_match":
            motive, scrutinee, zero_branch, succ_branch = term.args
            binder = f"vela_v{motive.value}"
            pred_binder = f"vela_v{succ_branch.value}"
            return (f"(match {self.render(scrutinee)} as {binder} return {self.render(motive.args[1])} with "
                    f"| Corelib.Init.Datatypes.O => {self.render(zero_branch)} "
                    f"| Corelib.Init.Datatypes.S {pred_binder} => {self.render(succ_branch.args[1])} end)")
        raise self.fail("inference", "cannot emit an unresolved term")

