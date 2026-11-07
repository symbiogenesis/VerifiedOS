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
    _ImplInstance,
    _InterfaceInfo,
    _InterfaceLawSpec,
    _InterfaceMethodSpec,
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

    def _solver_statement(
        self: _Elaborator,
        binders: list[_Term],
        goal: _Term,
        fact_bools: list[_Term],
    ) -> tuple[_Term, bool]:
        """Close a solver-discharged goal into the statement the solver established.

        The goal is quantified over its declaration binders. When it also mentions
        elaboration-local variables, such as symbolic loop states, every fact the
        solver could see becomes an explicit premise over those variables, so the
        statement records the discharged verification condition rather than a
        stronger claim. Returns the statement and whether generalization occurred.
        """
        bound = {cast("int", v.value) for v in binders}
        extra_ids = set(self.free(goal)) - bound
        premises: list[_Term] = []
        if extra_ids:
            seen: set[_Term] = set()
            for fact in fact_bools:
                if fact in seen:
                    continue
                seen.add(fact)
                premises.append(_apps(_constant("Eq"), _BOOL, fact, _term("bool", value=1)))
                extra_ids |= set(self.free(fact)) - bound
            pending = list(extra_ids)
            while pending:
                index = pending.pop()
                for dependency in set(self.free(self.types[index])) - bound - extra_ids:
                    extra_ids.add(dependency)
                    pending.append(dependency)
        statement = goal
        for premise in reversed(premises):
            statement = self.pi(premise, statement)
        extra_vars = [_term("var", value=index) for index in sorted(extra_ids)]
        statement = self.wrap("pi", [*binders, *extra_vars], statement)
        return statement, bool(extra_ids)

    def _emit_solver_trusted(
        self: _Elaborator,
        emitted: str,
        statement: _Term,
        node: Node,
        reason: str,
        generic_count: int,
    ) -> _Term:
        """Emit an explicit, counted assumption for an obligation without a kernel proof.

        The kernel sees the real statement; `Print Assumptions` names the axiom, and
        the preceding marker records its source location and reason for the ledger.
        """
        self.complete(statement)
        axiom = f"vela_solver_{emitted}"
        location = self.protocol.error("trust", reason, node)
        self.output.append(
            f"(* vela-solver-trust: {emitted} at {location.line}:{location.column}; {reason} *)\n"
            f"Axiom {axiom} : {self.render(statement)}."
        )
        self.constants[axiom] = _Binding(_constant(axiom), statement, generic_count)
        return _constant(axiom)

    def _replace_images(self: _Elaborator, term: _Term, images: list[tuple[_Term, _Term]]) -> _Term:
        """Replace symbolic post-states by the named kernel images of the same effect."""
        if not images:
            return term
        memo: dict[int, _Term] = {}

        def walk(current: _Term) -> _Term:
            key = id(current)
            if key in memo:
                return memo[key]
            resolved = self.resolve(current)
            replaced: _Term | None = None
            for old, new in images:
                if resolved == old:
                    replaced = new
                    break
            if replaced is None:
                children = tuple(walk(child) for child in resolved.args)
                replaced = resolved if children == resolved.args else _Term(resolved.kind, resolved.value, children)
            memo[key] = replaced
            return replaced

        return walk(term)

    def _emit_obligation(
        self: _Elaborator,
        emitted: str,
        binders: list[_Term],
        prop: _Term,
        proof: _Term | None,
        node: Node,
        reason: str,
        generic_count: int,
        fact_bools: list[_Term],
        images: list[tuple[_Term, _Term]] | None = None,
    ) -> None:
        """Emit a contract obligation with a kernel proof or as a solver-trusted assumption."""
        bound = {cast("int", v.value) for v in binders}
        stated = self._replace_images(prop, images or [])
        if proof is not None and self.free(prop) <= bound and self.free(proof) <= bound:
            signature = self.wrap("pi", binders, stated)
            definition = self.wrap("lam", binders, self._replace_images(proof, images or []))
            self.complete(signature)
            self.complete(definition)
            self.output.append(f"Definition {emitted} : {self.render(signature)} :=\n  {self.render(definition)}.")
        else:
            facts = [self._replace_images(fact, images or []) for fact in fact_bools]
            signature, generalized = self._solver_statement(binders, stated, facts)
            if generalized:
                reason = f"{reason}; generalized over elaboration-local state with its facts"
            definition = self._emit_solver_trusted(emitted, signature, node, reason, generic_count)
            # The axiom carries the statement; the export's type is inferred from it.
            self.output.append(f"Definition {emitted} :=\n  {self.render(definition)}.")
        self.constants[emitted] = _Binding(_constant(emitted), signature, generic_count)
        self.definitions[emitted] = definition

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

    def _record_visibility(self: _Elaborator, name: str, modifiers: list[object], node: Node) -> bool:
        vis = [m for m in modifiers if m in {"public", "private", "internal"}]
        if len(vis) > 1:
            raise self.fail("unsupported", "conflicting visibility modifiers", node)
        is_pub = "public" in vis
        if is_pub:
            self.public_symbols.add(name)
        else:
            self.private_symbols.add(name)
        return is_pub

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
                or name in self.union_ctors or name in self.interfaces
                or name in {"Type", "_", "this"} or "." in name):
            raise self.fail("name", f"duplicate or reserved declaration '{name}'", node)
        self._record_visibility(name, modifiers, node)
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
            pt = self.node(param_node["type"])
            if pt["kind"] == "modified_type":
                raise self.fail("unsupported", f"record fields cannot have loan modifier '{pt.get('modifier')}'", param_node)
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
                    ens_proof: _Term | None
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
                        if not proved_alt:
                            raise
                        ens_proof = None
                    self._emit_obligation(
                        f"{m_emitted}_ensures_{ens_idx}",
                        post_vars,
                        ens_prop,
                        ens_proof,
                        ens_contract,
                        "method postcondition discharged by the untrusted solver",
                        len(generics) + len(m_generics),
                        [*self.active_facts, *self._fact_bool_terms((), post_env)],
                    )
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
                or name in self.union_ctors or name in self.interfaces
                or name in {"Type", "_", "this"} or "." in name):
            raise self.fail("name", f"duplicate or reserved declaration '{name}'", node)
        is_pub = self._record_visibility(name, modifiers, node)
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
                    or cname in self.union_ctors or cname in self.interfaces
                    or cname == name or cname in seen_ctors
                    or cname in {"Type", "_", "this"} or "." in cname):
                raise self.fail("name", f"duplicate or reserved union constructor '{cname}'", ctor_node)
            seen_ctors.add(cname)
            if is_pub:
                self.public_symbols.add(cname)
            else:
                self.private_symbols.add(cname)
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
                pt = self.node(param_node["type"])
                if pt["kind"] == "modified_type":
                    raise self.fail("unsupported", f"union constructor fields cannot have loan modifier '{pt.get('modifier')}'", param_node)
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
                expected_arity = (
                    len(self.current_rec_generics)
                    + len(self.current_rec_params)
                    + len(self.current_rec_witnesses)
                )
                if len(arguments) < expected_arity:
                    return True
                return any(self._has_unapplied_rec_var(arg, rec_var_id) for arg in arguments)
            return self._has_unapplied_rec_var(head, rec_var_id) or any(
                self._has_unapplied_rec_var(arg, rec_var_id) for arg in arguments
            )
        return any(self._has_unapplied_rec_var(child, rec_var_id) for child in term.args)

    def _import_declaration(self: _Elaborator, node: Node) -> None:
        modifiers = node.get("modifiers", [])
        if modifiers:
            raise self.fail("unsupported", "import declarations do not accept modifiers", node)
        imp_name = self.name(node["name"])
        if imp_name == "Vela.Numerics":
            for alias_name, target_name in _NUMERICS_ALIASES.items():
                if (alias_name in self.globals and self.globals[alias_name] != self.globals[target_name]) or (
                    alias_name in self.records
                    or alias_name in self.unions
                    or alias_name in self.union_ctors
                    or alias_name in self.interfaces
                ):
                    raise self.fail("name", f"import alias '{alias_name}' conflicts with an existing declaration", node)
                self.globals[alias_name] = self.globals[target_name]
            return
        if imp_name == self.module_name:
            raise self.fail("name", f"module '{imp_name}' cannot import itself", node)
        if imp_name in self.imported_modules:
            raise self.fail("name", f"duplicate import of module '{imp_name}'", node)
        if imp_name not in self.available_modules:
            raise self.fail("unsupported", f"import '{imp_name}' requires the full frontend", node)
        self.imported_modules.add(imp_name)
        mod = self.available_modules[imp_name]
        self.serial = max(self.serial, mod.serial)
        self.types.update(mod.types)
        self.parameter_names.update(mod.parameter_names)
        self.nullary_parameters.update(mod.nullary_parameters)
        self.constant_parameters.update(mod.constant_parameters)
        self.readonly_span_vars.update(mod.readonly_span_vars)
        self.ref_parameters.update(mod.ref_parameters)
        self.out_parameters.update(mod.out_parameters)
        self.constants.update(mod.constants)
        self.definitions.update(mod.definitions)
        self.records_by_type.update(mod.records_by_type)
        self.records_by_ctor.update(mod.records_by_ctor)
        self.record_projections.update(mod.record_projections)
        self.unions_by_type.update(mod.unions_by_type)
        self.unions_by_ctor.update(mod.unions_by_ctor)
        self.callable_preconditions.update(mod.callable_preconditions)
        self.callable_ensures.update(mod.callable_ensures)
        self.callable_ref_updates.update(mod.callable_ref_updates)
        self.callable_where_constraints.update(mod.callable_where_constraints)
        self.fix_names.update(mod.fix_names)
        existing_out = set(self.output)
        for line in mod.output:
            if line not in existing_out:
                self.output.append(line)
                existing_out.add(line)
        for priv_sym in mod.private_symbols:
            self.inaccessible_private_symbols[f"{imp_name}.{priv_sym}"] = imp_name
            if priv_sym not in self.globals:
                self.inaccessible_private_symbols[priv_sym] = imp_name
        for pub_sym in mod.public_symbols:
            if (
                pub_sym in self.globals
                or pub_sym in self.records
                or pub_sym in self.unions
                or pub_sym in self.union_ctors
                or pub_sym in self.interfaces
            ):
                raise self.fail(
                    "name",
                    f"imported declaration '{pub_sym}' from '{imp_name}' conflicts with an existing binding",
                    node,
                )
            self.inaccessible_private_symbols.pop(pub_sym, None)
            qual_name = f"{imp_name}.{pub_sym}"
            if pub_sym in mod.globals:
                self.globals[pub_sym] = mod.globals[pub_sym]
                self.globals[qual_name] = mod.globals[pub_sym]
            if pub_sym in mod.records:
                self.records[pub_sym] = mod.records[pub_sym]
                self.records[qual_name] = mod.records[pub_sym]
            if pub_sym in mod.unions:
                self.unions[pub_sym] = mod.unions[pub_sym]
                self.unions[qual_name] = mod.unions[pub_sym]
            if pub_sym in mod.union_ctors:
                self.union_ctors[pub_sym] = mod.union_ctors[pub_sym]
                self.union_ctors[qual_name] = mod.union_ctors[pub_sym]
            if pub_sym in mod.interfaces:
                self.interfaces[pub_sym] = mod.interfaces[pub_sym]
                self.interfaces[qual_name] = mod.interfaces[pub_sym]
        for iface_name, mod_inst_list in mod.impls.items():
            target_list = self.impls.setdefault(iface_name, [])
            for inst in mod_inst_list:
                if inst not in target_list:
                    for existing_inst in target_list:
                        if self._impl_instances_overlap(existing_inst, inst):
                            raise self.fail(
                                "type",
                                f"imported impl for interface '{iface_name}' from '{imp_name}' overlaps an existing impl",
                                node,
                            )
                    target_list.append(inst)

    def _split_where_clause(
        self: _Elaborator, contract_node: Node, environment: dict[str, _Binding]
    ) -> tuple[list[tuple[_InterfaceInfo, tuple[_Term, ...], Node]], list[Node]]:
        def flatten_and(expr: Node) -> list[Node]:
            unwrapped = self._unwrap_group(expr)
            if unwrapped["kind"] == "binary" and self.operator(unwrapped["operator"]) == "&&":
                return [
                    *flatten_and(self.node(unwrapped["left"])),
                    *flatten_and(self.node(unwrapped["right"])),
                ]
            return [unwrapped]

        iface_constraints: list[tuple[_InterfaceInfo, tuple[_Term, ...], Node]] = []
        prop_contracts: list[Node] = []
        for conj in flatten_and(self.node(contract_node["value"])):
            if conj["kind"] == "call":
                callee = self._unwrap_group(self.node(conj["callee"]))
                if callee["kind"] == "generic_application":
                    base_c = self._unwrap_group(self.node(callee["value"]))
                    if base_c["kind"] == "name" and self.name(base_c["name"]) in self.interfaces:
                        cname = self.name(base_c["name"])
                        raise self.fail(
                            "type",
                            f"interface constraint '{cname}' takes arguments in parentheses, not '<...>'",
                            conj,
                        )
                if callee["kind"] == "name":
                    cname = self.name(callee["name"])
                    if cname in self.interfaces:
                        iface = self.interfaces[cname]
                        arg_nodes = self.nodes(conj["arguments"])
                        if len(arg_nodes) != len(iface.generic_vars):
                            raise self.fail(
                                "type",
                                f"interface constraint '{cname}' expects {len(iface.generic_vars)} arguments, got {len(arg_nodes)}",
                                conj,
                            )
                        t_args: list[_Term] = []
                        for idx, anode in enumerate(arg_nodes):
                            self.node(anode, "argument")
                            if anode["label"] is not None:
                                raise self.fail("type", "interface constraint arguments do not accept labels", anode)
                            aval = self._unwrap_group(self.node(anode["value"]))
                            g_dom = self.types[cast("int", iface.generic_vars[idx].value)]
                            for prev_gv, prev_t in zip(iface.generic_vars[:idx], t_args, strict=True):
                                g_dom = self.substitute(g_dom, cast("int", prev_gv.value), prev_t)
                            if aval["kind"] == "name":
                                aname = self.name(aval["name"])
                                b = self.lookup(aname, environment, raw=True)
                                t_term = b.term
                                self.site = anode
                                self.unify(self.infer(t_term), g_dom)
                            elif aval["kind"] == "type_expression":
                                t_term = self.type(self.node(aval["type"]), environment)
                                self.site = anode
                                self.unify(self.infer(t_term), g_dom)
                            else:
                                t_term = self.argument(aval, g_dom, environment)
                            t_args.append(self.whnf(t_term))
                        iface_constraints.append((iface, tuple(t_args), conj))
                        continue
            prop_contracts.append(
                {
                    "kind": "contract",
                    "role": "where",
                    "value": conj,
                    "span": conj["span"],
                }
            )
        return iface_constraints, prop_contracts

    def _bind_where_constraints(
        self: _Elaborator,
        where_iface_constraints: list[tuple[_InterfaceInfo, tuple[_Term, ...], Node]],
    ) -> tuple[list[_Term], list[tuple[str, tuple[_Term, ...]]]]:
        witness_vars: list[_Term] = []
        active_keys: list[tuple[str, tuple[_Term, ...]]] = []
        for iface, t_args, c_node in where_iface_constraints:
            key = (iface.name, t_args)
            if key in self.active_interface_witnesses:
                raise self.fail("type", f"duplicate interface constraint '{iface.name}' in where clause", c_node)
            active_keys.append(key)
            w_dict: dict[str, _Binding] = {}
            e_dict: dict[str, tuple[tuple[int, ...], tuple[_Term, ...]]] = {}
            if iface.methods:
                for mname, mspec in iface.methods.items():
                    inst_sig = mspec.signature
                    for gv, tv in zip(iface.generic_vars, t_args, strict=True):
                        inst_sig = self.substitute(inst_sig, cast("int", gv.value), tv)
                    w_var = self.fresh(inst_sig)
                    witness_vars.append(w_var)
                    w_dict[mname] = _Binding(w_var, inst_sig, mspec.method_generics)
                    if mspec.preconditions:
                        inst_preconds: list[tuple[tuple[int, ...], _Term]] = []
                        for p_ids, req_t in mspec.preconditions:
                            sub_req = req_t
                            for gv, tv in zip(iface.generic_vars, t_args, strict=True):
                                sub_req = self.substitute(sub_req, cast("int", gv.value), tv)
                            rem_ids = tuple(
                                pid for pid in p_ids if all(pid != cast("int", gv.value) for gv in iface.generic_vars)
                            )
                            inst_preconds.append((rem_ids, sub_req))
                        self.var_preconditions[cast("int", w_var.value)] = inst_preconds
                    if mspec.ensures_props:
                        inst_ens: list[_Term] = []
                        for ep in mspec.ensures_props:
                            sub_ep = ep
                            for gv, tv in zip(iface.generic_vars, t_args, strict=True):
                                sub_ep = self.substitute(sub_ep, cast("int", gv.value), tv)
                            sub_ep = self.substitute(sub_ep, cast("int", mspec.self_var.value), w_var)
                            inst_ens.append(sub_ep)
                        rem_m_ids = tuple(
                            cast("int", v.value) for v in [*mspec.generic_vars, *mspec.param_vars]
                        )
                        e_dict[mname] = (rem_m_ids, tuple(inst_ens))
            else:
                w_var = self.fresh(_UNIT)
                witness_vars.append(w_var)
            self.active_interface_witnesses[key] = w_dict
            if e_dict:
                self.active_interface_ensures[key] = e_dict
        return witness_vars, active_keys

    def _interface_declaration(self: _Elaborator, node: Node, first_meta: int) -> None:
        modifiers = node["modifiers"]
        allowed_modifiers = {"public", "private", "internal"}
        if (
            not isinstance(modifiers, list)
            or any(not isinstance(value, str) or value not in allowed_modifiers for value in modifiers)
            or len(modifiers) != len(set(modifiers))
        ):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers", node)
        if node["contracts"]:
            raise self.fail("unsupported", "interface-level contracts require the full frontend", node)
        name = self.name(node["name"])
        self._evict_builtin_if_shadowed(name)
        if (
            name in self.globals
            or name in self.records
            or name in self.unions
            or name in self.union_ctors
            or name in self.interfaces
            or name in {"Type", "_", "this"}
            or "." in name
        ):
            raise self.fail("name", f"duplicate or reserved declaration '{name}'", node)
        self._record_visibility(name, modifiers, node)
        generics = self.nodes(node["generics"])
        if not generics:
            raise self.fail("type", f"interface '{name}' requires at least one generic parameter", node)
        member_nodes = self.nodes(node["declarations"])
        if not member_nodes:
            raise self.fail("type", f"interface '{name}' requires at least one member or law declaration", node)
        generic_vars, generic_env = self.telescope(generics, [], {}, unit=False)
        methods: dict[str, _InterfaceMethodSpec] = {}
        laws: dict[str, _InterfaceLawSpec] = {}
        active_key = (name, tuple(generic_vars))
        self.active_interface_witnesses[active_key] = {}
        self.active_interface_ensures[active_key] = {}
        self.interfaces[name] = _InterfaceInfo(
            name=name,
            generic_vars=tuple(generic_vars),
            methods={},
            laws={},
        )
        try:
            for mnode in member_nodes:
                self.site = mnode
                self.mutable_locals.clear()
                self.out_param_names.clear()
                self.uninitialized_out_params.clear()
                mkind = mnode["kind"]
                if mkind not in {"function", "definition", "lemma", "theorem"}:
                    raise self.fail("unsupported", f"interface member '{mkind}' is not supported", mnode)
                m_modifiers = mnode["modifiers"]
                m_allowed = {"public", "private", "internal"} | (
                    {"const"} if mkind in {"function", "definition"} else set()
                )
                if (
                    not isinstance(m_modifiers, list)
                    or any(not isinstance(v, str) or v not in m_allowed for v in m_modifiers)
                    or len(m_modifiers) != len(set(m_modifiers))
                ):
                    raise self.fail("unsupported", "unsupported or repeated declaration modifiers", mnode)
                mname = self.name(mnode["name"])
                if (
                    mname in methods
                    or mname in laws
                    or mname == name
                    or mname in {"Type", "_", "this"}
                    or "." in mname
                ):
                    raise self.fail("name", f"duplicate or reserved interface member '{mname}'", mnode)
                m_generics = self.nodes(mnode["generics"])
                m_params = self.nodes(mnode["parameters"])
                if mkind in {"function", "definition"}:
                    raw_body = mnode["value"] if mkind == "definition" else mnode["body"]
                    if raw_body is not None:
                        raise self.fail(
                            "type",
                            f"interface member '{mname}' must be an abstract signature without a body",
                            mnode,
                        )
                    self.no_roles(mnode, "cancel")
                    m_reqs: list[Node] = []
                    m_enss: list[Node] = []
                    for cnode in self.nodes(mnode["contracts"]):
                        self.node(cnode, "contract")
                        crole = cnode["role"]
                        if crole in {"requires", "where"}:
                            m_reqs.append(cnode)
                        elif crole == "ensures":
                            m_enss.append(cnode)
                        else:
                            raise self.fail(
                                "unsupported",
                                f"interface member contract '{crole}' is not supported",
                                cnode,
                            )
                    m_vars, m_env = self.telescope(m_generics, m_params, generic_env, unit=True)
                    m_gen_vars = m_vars[: len(m_generics)]
                    m_param_vars = m_vars[len(m_generics) :]
                    m_param_labels = [
                        self.name(p["name"]) if p["name"] is not None else None for p in m_params
                    ]
                    m_param_mods: list[str | None] = []
                    for p in m_params:
                        pt = self.node(p["type"])
                        m_param_mods.append(
                            cast("str | None", pt.get("modifier"))
                            if pt["kind"] == "modified_type"
                            else None
                        )
                    m_res_type = self.type(self.node(mnode["result"]), m_env)
                    m_sig = self.wrap("pi", m_vars, m_res_type)
                    m_self_var = self.fresh(m_sig)
                    all_m_param_ids = tuple(cast("int", v.value) for v in [*generic_vars, *m_vars])
                    m_preconds: list[tuple[tuple[int, ...], _Term]] = []
                    m_req_bools: list[_Term] = []
                    for rc in m_reqs:
                        rv_node = self.node(rc["value"])
                        rb = self.expression(rv_node, m_env)
                        if self.whnf(rb.type) != _BOOL:
                            raise self.fail(
                                "type", "interface method requires clause must be a boolean expression", rc
                            )
                        m_preconds.append((all_m_param_ids, rb.term))
                        m_req_bools.append(rb.term)
                    if m_preconds:
                        rem_ids = tuple(cast("int", v.value) for v in m_vars)
                        self.var_preconditions[cast("int", m_self_var.value)] = [
                            (rem_ids, rt) for _, rt in m_preconds
                        ]
                    m_ens_terms: list[_Term] = []
                    if m_enss:
                        post_m_env = dict(m_env)
                        for out_pname in self.out_param_names:
                            self.uninitialized_out_params.discard(out_pname)
                        call_m_term = _apps(m_self_var, *m_vars)
                        post_m_env["result"] = _Binding(call_m_term, m_res_type)
                        saved_f = list(self.active_facts)
                        self.active_facts.extend(m_req_bools)
                        try:
                            for ec in m_enss:
                                ev_node = self.node(ec["value"])
                                eb = self.expression(ev_node, post_m_env)
                                if self.whnf(eb.type) != _BOOL:
                                    raise self.fail(
                                        "type",
                                        "interface method ensures clause must be a boolean expression",
                                        ec,
                                    )
                                m_ens_terms.append(eb.term)
                        finally:
                            self.active_facts = saved_f
                    mspec = _InterfaceMethodSpec(
                        name=mname,
                        method_generics=len(m_generics),
                        generic_vars=tuple(m_gen_vars),
                        param_vars=tuple(m_param_vars),
                        param_labels=tuple(m_param_labels),
                        param_modifiers=tuple(m_param_mods),
                        return_type=m_res_type,
                        signature=m_sig,
                        self_var=m_self_var,
                        nullary=not bool(m_params),
                        preconditions=tuple(m_preconds),
                        ensures_clauses=tuple(m_enss),
                        ensures_props=tuple(m_ens_terms),
                    )
                    methods[mname] = mspec
                    self.active_interface_witnesses[active_key][mname] = _Binding(
                        m_self_var, m_sig, len(m_generics)
                    )
                    if m_ens_terms:
                        rem_ids = tuple(cast("int", v.value) for v in m_vars)
                        self.active_interface_ensures[active_key][mname] = (rem_ids, tuple(m_ens_terms))
                else:
                    if mnode["body"] is not None:
                        raise self.fail(
                            "type",
                            f"interface law '{mname}' must be an abstract signature without a proof body",
                            mnode,
                        )
                    if m_generics:
                        raise self.fail(
                            "unsupported", "generic interface laws require the full frontend", mnode
                        )
                    l_reqs: list[Node] = []
                    l_enss: list[Node] = []
                    for cnode in self.nodes(mnode["contracts"]):
                        self.node(cnode, "contract")
                        crole = cnode["role"]
                        if crole in {"requires", "where"}:
                            l_reqs.append(cnode)
                        elif crole == "ensures":
                            l_enss.append(cnode)
                        else:
                            raise self.fail(
                                "unsupported",
                                f"interface law contract '{crole}' is not supported",
                                cnode,
                            )
                    if not l_enss:
                        raise self.fail("protocol", "interface law requires at least one ensures clause", mnode)
                    l_vars, l_env = self.telescope([], m_params, generic_env, unit=True)
                    if self.out_param_names:
                        raise self.fail(
                            "type", "interface law parameters cannot use 'out' modifier", mnode
                        )
                    l_req_props: list[_Term] = []
                    l_req_bools: list[_Term] = []
                    for rc in l_reqs:
                        rp = self.asserted_proposition(self.node(rc["value"]), l_env)
                        l_req_props.append(rp)
                        ext = self._extract_equality(rp)
                        if (
                            ext is not None
                            and self.whnf(ext[0]) == _BOOL
                            and self.whnf(ext[2]) == _term("bool", value=1)
                        ):
                            l_req_bools.append(ext[1])
                    l_ens_props: list[_Term] = []
                    saved_f = list(self.active_facts)
                    self.active_facts.extend(l_req_bools)
                    try:
                        for ec in l_enss:
                            ep = self.proposition(self.node(ec["value"]), l_env)
                            l_ens_props.append(ep)
                    finally:
                        self.active_facts = saved_f
                    laws[mname] = _InterfaceLawSpec(
                        name=mname,
                        kind=cast("str", mkind),
                        param_vars=tuple(l_vars),
                        requires_clauses=tuple(l_reqs),
                        ensures_clauses=tuple(l_enss),
                        req_props=tuple(l_req_props),
                        ensures_props=tuple(l_ens_props),
                    )
                self.interfaces[name] = _InterfaceInfo(
                    name=name,
                    generic_vars=tuple(generic_vars),
                    methods=dict(methods),
                    laws=dict(laws),
                )
        finally:
            self.active_interface_witnesses.pop(active_key, None)
            self.active_interface_ensures.pop(active_key, None)
            self.mutable_locals.clear()
            self.out_param_names.clear()
            self.uninitialized_out_params.clear()
        for index in range(first_meta, len(self.metas)):
            self.complete(_term("meta", value=index))
            self.complete(self.metas[index].type)

    def _check_no_computed_impl_type(self: _Elaborator, node: Node) -> None:
        kind = node["kind"]
        if kind in {"computed_type", "function_type", "modified_type"}:
            raise self.fail(
                "type",
                f"impl target type head cannot contain '{kind}'",
                node,
            )
        if kind in {"group_type", "type_argument"}:
            self._check_no_computed_impl_type(self.node(node["type"]))
        elif kind == "tuple_type":
            for child in self.nodes(node["types"]):
                self._check_no_computed_impl_type(child)
        elif kind == "type":
            for arg in self.nodes(node["arguments"]):
                if arg["kind"] in {"type_argument", "type", "group_type", "tuple_type", "computed_type", "function_type", "modified_type"}:
                    self._check_no_computed_impl_type(arg)

    def _impl_instances_overlap(
        self: _Elaborator, first: _ImplInstance, second: _ImplInstance
    ) -> bool:
        if len(first.target_types) != len(second.target_types):
            return False
        saved_metas = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
        try:
            first_metas: list[_Term] = []
            for gv in first.generic_vars:
                dom = self.types[cast("int", gv.value)]
                for prev_gv, prev_m in zip(first.generic_vars[: len(first_metas)], first_metas, strict=True):
                    dom = self.substitute(dom, cast("int", prev_gv.value), prev_m)
                first_metas.append(self.meta(dom, {}))
            second_metas: list[_Term] = []
            for gv in second.generic_vars:
                dom = self.types[cast("int", gv.value)]
                for prev_gv, prev_m in zip(second.generic_vars[: len(second_metas)], second_metas, strict=True):
                    dom = self.substitute(dom, cast("int", prev_gv.value), prev_m)
                second_metas.append(self.meta(dom, {}))
            inst_first: list[_Term] = []
            for t in first.target_types:
                sub_t = t
                for gv, gm in zip(first.generic_vars, first_metas, strict=True):
                    sub_t = self.substitute(sub_t, cast("int", gv.value), gm)
                inst_first.append(sub_t)
            inst_second: list[_Term] = []
            for t in second.target_types:
                sub_t = t
                for gv, gm in zip(second.generic_vars, second_metas, strict=True):
                    sub_t = self.substitute(sub_t, cast("int", gv.value), gm)
                inst_second.append(sub_t)
            return all(
                self._try_unify(t1, t2) for t1, t2 in zip(inst_first, inst_second, strict=True)
            )
        finally:
            self.metas = saved_metas

    def _impl_declaration(self: _Elaborator, node: Node, first_meta: int) -> None:
        modifiers = node["modifiers"]
        allowed_modifiers = {"public", "private", "internal"}
        if (
            not isinstance(modifiers, list)
            or any(not isinstance(value, str) or value not in allowed_modifiers for value in modifiers)
            or len(modifiers) != len(set(modifiers))
        ):
            raise self.fail("unsupported", "unsupported or repeated declaration modifiers", node)
        generics = self.nodes(node["generics"])
        impl_generic_vars, impl_env = self.telescope(generics, [], {}, unit=False)
        impl_type_node = self.node(node["type"])
        if impl_type_node["kind"] != "type":
            raise self.fail("type", "impl target must name an interface application", impl_type_node)
        iface_name = self.name(impl_type_node["name"])
        if iface_name not in self.interfaces:
            raise self.fail("name", f"unknown interface '{iface_name}' in impl declaration", impl_type_node)
        iface = self.interfaces[iface_name]
        type_arg_nodes = self.nodes(impl_type_node["arguments"])
        if len(type_arg_nodes) != len(iface.generic_vars):
            raise self.fail(
                "type",
                f"interface '{iface_name}' expects {len(iface.generic_vars)} type arguments, got {len(type_arg_nodes)}",
                impl_type_node,
            )
        target_types: list[_Term] = []
        for idx, arg_node in enumerate(type_arg_nodes):
            if arg_node["kind"] in {"type_argument", "type", "group_type", "tuple_type", "computed_type", "function_type", "modified_type"}:
                self._check_no_computed_impl_type(arg_node)
            expected_g_dom = self.types[cast("int", iface.generic_vars[idx].value)]
            for prev_gv, prev_t in zip(iface.generic_vars[:idx], target_types, strict=True):
                expected_g_dom = self.substitute(expected_g_dom, cast("int", prev_gv.value), prev_t)
            t_val = self.argument(arg_node, expected_g_dom, impl_env)
            target_types.append(self.whnf(t_val))
        if all(self.resolve(t) in impl_generic_vars for t in target_types):
            raise self.fail(
                "type",
                f"blanket impl for '{iface_name}' over bare type parameters is not permitted",
                impl_type_node,
            )
        used_gen_ids = set().union(*(self.free(t) for t in target_types))
        for gv in impl_generic_vars:
            if cast("int", gv.value) not in used_gen_ids:
                raise self.fail(
                    "type",
                    "impl generic parameter must be determined by the implemented interface arguments",
                    node,
                )
        where_iface_constraints: list[tuple[_InterfaceInfo, tuple[_Term, ...], Node]] = []
        for cnode in self.nodes(node["contracts"]):
            self.node(cnode, "contract")
            if cnode["role"] != "where":
                raise self.fail("unsupported", f"impl contract '{cnode['role']}' is not supported", cnode)
            ifaces_c, props_c = self._split_where_clause(cnode, impl_env)
            if props_c:
                raise self.fail(
                    "type",
                    "impl where clause only supports interface constraints",
                    props_c[0],
                )
            where_iface_constraints.extend(ifaces_c)
        candidate_inst = _ImplInstance(
            interface_name=iface_name,
            generic_vars=tuple(impl_generic_vars),
            target_types=tuple(target_types),
            where_constraints=tuple((wi.name, wt) for wi, wt, _ in where_iface_constraints),
            methods={},
        )
        for existing_inst in self.impls.get(iface_name, []):
            if self._impl_instances_overlap(existing_inst, candidate_inst):
                raise self.fail(
                    "type",
                    f"overlapping or duplicate impl for interface '{iface_name}'",
                    node,
                )
        member_nodes = self.nodes(node["declarations"])
        impl_methods_by_name: dict[str, Node] = {}
        impl_laws_by_name: dict[str, Node] = {}
        for mnode in member_nodes:
            self.site = mnode
            mkind = mnode["kind"]
            if mkind not in {"function", "definition", "lemma", "theorem"}:
                raise self.fail("unsupported", f"impl member '{mkind}' is not supported", mnode)
            mname = self.name(mnode["name"])
            if mname in impl_methods_by_name or mname in impl_laws_by_name:
                raise self.fail("name", f"duplicate member '{mname}' in impl of '{iface_name}'", mnode)
            if mkind in {"function", "definition"}:
                if mname not in iface.methods:
                    raise self.fail(
                        "name",
                        f"method '{mname}' is not declared by interface '{iface_name}'",
                        mnode,
                    )
                impl_methods_by_name[mname] = mnode
            else:
                if mname not in iface.laws:
                    raise self.fail(
                        "name",
                        f"law '{mname}' is not declared by interface '{iface_name}'",
                        mnode,
                    )
                impl_laws_by_name[mname] = mnode
        for req_mname in iface.methods:
            if req_mname not in impl_methods_by_name:
                raise self.fail(
                    "type",
                    f"impl of '{iface_name}' is missing required method '{req_mname}'",
                    node,
                )
        for req_lname in iface.laws:
            if req_lname not in impl_laws_by_name:
                raise self.fail(
                    "type",
                    f"impl of '{iface_name}' is missing required law '{req_lname}'",
                    node,
                )
        impl_witness_vars, active_where_keys = self._bind_where_constraints(where_iface_constraints)
        self_active_key = (iface.name, tuple(target_types))
        self.active_interface_witnesses[self_active_key] = {}
        self.active_interface_ensures[self_active_key] = {}
        emitted_methods: dict[str, _Binding] = {}
        applied_self_methods: dict[str, _Term] = {}
        try:
            for mname, mspec in iface.methods.items():
                mnode = impl_methods_by_name[mname]
                self.site = mnode
                self.reset_budget()
                m_first_meta = len(self.metas)
                self.mutable_locals.clear()
                self.out_param_names.clear()
                self.uninitialized_out_params.clear()
                self.entry_env = {}
                self.final_ref_bindings = {}
                self.final_return_facts = []
                self.frozen_collections.clear()
                self.lifted_invariants.clear()
                self.active_lift_scopes = 0
                self.in_loop_depth = 0
                mkind = mnode["kind"]
                raw_body = mnode["value"] if mkind == "definition" else mnode["body"]
                if raw_body is None:
                    raise self.fail(
                        "type",
                        f"impl method '{mname}' requires a concrete body",
                        mnode,
                    )
                m_generics = self.nodes(mnode["generics"])
                if len(m_generics) != mspec.method_generics:
                    raise self.fail(
                        "type",
                        f"impl method '{mname}' generic arity does not match interface '{iface_name}'",
                        mnode,
                    )
                m_params = self.nodes(mnode["parameters"])
                expected_p_count = 0 if mspec.nullary else len(mspec.param_vars)
                if len(m_params) != expected_p_count:
                    raise self.fail(
                        "type",
                        f"impl method '{mname}' parameter count does not match interface '{iface_name}'",
                        mnode,
                    )
                for p_idx, p_node in enumerate(m_params):
                    pt = self.node(p_node["type"])
                    p_mod = (
                        cast("str | None", pt.get("modifier"))
                        if pt["kind"] == "modified_type"
                        else None
                    )
                    if p_mod != mspec.param_modifiers[p_idx]:
                        raise self.fail(
                            "type",
                            f"parameter modifier of '{mname}' in impl does not match interface '{iface_name}'",
                            p_node,
                        )
                    p_const = bool(p_node.get("const", False))
                    expected_const = (
                        cast("int", mspec.param_vars[p_idx].value) in self.constant_parameters
                    )
                    if p_const != expected_const:
                        raise self.fail(
                            "type",
                            f"constant-parameter requirement of '{mname}' in impl does not match interface '{iface_name}'",
                            p_node,
                        )
                m_vars, m_env = self.telescope(m_generics, m_params, impl_env, unit=True)
                ref_param_names = set(self.mutable_locals)
                self.entry_env = dict(m_env)
                self.final_ref_bindings = dict(m_env)
                spec_m_vars = [*mspec.generic_vars, *mspec.param_vars]
                for idx_v, (mv, spec_mv) in enumerate(zip(m_vars, spec_m_vars, strict=True)):
                    expected_dom = self.types[cast("int", spec_mv.value)]
                    for gv, tv in zip(iface.generic_vars, target_types, strict=True):
                        expected_dom = self.substitute(expected_dom, cast("int", gv.value), tv)
                    for prev_smv, prev_mv in zip(spec_m_vars[:idx_v], m_vars[:idx_v], strict=True):
                        expected_dom = self.substitute(expected_dom, cast("int", prev_smv.value), prev_mv)
                    self.site = mnode
                    self.unify(self.types[cast("int", mv.value)], expected_dom)
                expected_ret = mspec.return_type
                for gv, tv in zip(iface.generic_vars, target_types, strict=True):
                    expected_ret = self.substitute(expected_ret, cast("int", gv.value), tv)
                for spec_mv, mv in zip(spec_m_vars, m_vars, strict=True):
                    expected_ret = self.substitute(expected_ret, cast("int", spec_mv.value), mv)
                m_res_type = self.type(self.node(mnode["result"]), m_env)
                self.site = self.node(mnode["result"])
                self.unify(m_res_type, expected_ret)

                inst_req_bools: list[_Term] = []
                for _, req_t in mspec.preconditions:
                    sub_req = req_t
                    for gv, tv in zip(iface.generic_vars, target_types, strict=True):
                        sub_req = self.substitute(sub_req, cast("int", gv.value), tv)
                    for spec_mv, mv in zip(spec_m_vars, m_vars, strict=True):
                        sub_req = self.substitute(sub_req, cast("int", spec_mv.value), mv)
                    inst_req_bools.append(sub_req)

                m_ens_clauses: list[Node] = []
                for cnode in self.nodes(mnode["contracts"]):
                    self.node(cnode, "contract")
                    crole = cnode["role"]
                    if crole in {"requires", "where"}:
                        rv_b = self.expression(self.node(cnode["value"]), m_env)
                        if self.whnf(rv_b.type) != _BOOL:
                            raise self.fail(
                                "type",
                                "impl method requires clause must be a boolean expression",
                                cnode,
                            )
                        saved_rf = list(self.active_facts)
                        self.active_facts.extend(inst_req_bools)
                        try:
                            if not self._prove_bool_precondition(rv_b.term, m_env):
                                raise self.fail(
                                    "type",
                                    f"impl method '{mname}' cannot strengthen preconditions beyond interface '{iface_name}'",
                                    cnode,
                                )
                        finally:
                            self.active_facts = saved_rf
                    elif crole == "ensures":
                        m_ens_clauses.append(cnode)
                    else:
                        raise self.fail(
                            "unsupported",
                            f"impl method contract '{crole}' is not supported",
                            cnode,
                        )

                body_node = self.node(raw_body)
                prev_ret = self.current_return_type
                self.current_return_type = m_res_type
                saved_body_f = list(self.active_facts)
                self.active_facts.extend([*inst_req_bools, *self._fact_bool_terms((), m_env)])
                try:
                    m_body = self.check(body_node, m_res_type, m_env)
                    if self.uninitialized_out_params:
                        uninit_name = min(self.uninitialized_out_params)
                        raise self.fail(
                            "type",
                            f"out parameter '{uninit_name}' is not initialized on all exit paths",
                            body_node,
                        )
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
                    self.active_facts = saved_body_f
                    self.current_return_type = prev_ret

                full_m_vars = [*impl_generic_vars, *impl_witness_vars, *m_vars]
                m_sig = self.wrap("pi", full_m_vars, m_res_type)
                m_def = self.wrap("lam", full_m_vars, m_body)
                self.site = mnode
                self.complete(m_sig)
                self.complete(m_def)
                for index in range(m_first_meta, len(self.metas)):
                    self.complete(_term("meta", value=index))
                    self.complete(self.metas[index].type)
                m_emitted = f"vela_d{len(self.output)}_impl_{iface_name}_{mname}"
                self.output.append(
                    f"Definition {m_emitted} : {self.render(m_sig)} :=\n  {self.render(m_def)}."
                )
                m_binding = _Binding(
                    _constant(m_emitted), m_sig, len(impl_generic_vars) + len(m_generics)
                )
                self.constants[m_emitted] = m_binding
                self.definitions[m_emitted] = m_def
                emitted_methods[mname] = m_binding

                if ref_param_names:
                    all_m_ids = tuple(cast("int", v.value) for v in full_m_vars)
                    idx_to_t: dict[int, _Term] = {}
                    for p_idx, p_node in enumerate(m_params):
                        if p_node["name"] is not None:
                            pname = self.name(p_node["name"])
                            if pname in ref_param_names and pname in self.final_ref_bindings:
                                ft = self.final_ref_bindings[pname].term
                                if self.free(ft) <= set(all_m_ids):
                                    idx_to_t[p_idx] = ft
                    if idx_to_t:
                        self.callable_ref_updates[m_emitted] = (all_m_ids, idx_to_t)

                applied_m_term = _apps(_constant(m_emitted), *impl_generic_vars, *impl_witness_vars)
                applied_m_sig = self.wrap("pi", m_vars, m_res_type)
                applied_self_methods[mname] = applied_m_term
                self.active_interface_witnesses[self_active_key][mname] = _Binding(
                    applied_m_term, applied_m_sig, len(m_generics)
                )
                if mspec.ensures_props:
                    inst_self_ens: list[_Term] = []
                    for ep in mspec.ensures_props:
                        sub_ep = ep
                        for gv, tv in zip(iface.generic_vars, target_types, strict=True):
                            sub_ep = self.substitute(sub_ep, cast("int", gv.value), tv)
                        sub_ep = self.substitute(
                            sub_ep, cast("int", mspec.self_var.value), applied_m_term
                        )
                        inst_self_ens.append(sub_ep)
                    rem_self_ids = tuple(
                        cast("int", v.value) for v in [*mspec.generic_vars, *mspec.param_vars]
                    )
                    self.active_interface_ensures[self_active_key][mname] = (
                        rem_self_ids,
                        tuple(inst_self_ens),
                    )

                if mspec.ensures_props or m_ens_clauses:
                    post_env = dict(m_env)
                    for pname in ref_param_names:
                        if pname in self.final_ref_bindings:
                            post_env[pname] = self.final_ref_bindings[pname]
                    call_term = _apps(_constant(m_emitted), *full_m_vars)
                    post_env["result"] = _Binding(call_term, m_res_type)
                    saved_pf = list(self.active_facts)
                    self.active_facts.extend(
                        [
                            *inst_req_bools,
                            *self.final_return_facts,
                            *self._fact_bool_terms((), self.entry_env),
                            *self._fact_bool_terms((), post_env),
                        ]
                    )
                    try:
                        for spec_ep in mspec.ensures_props:
                            sub_ep = spec_ep
                            for gv, tv in zip(iface.generic_vars, target_types, strict=True):
                                sub_ep = self.substitute(sub_ep, cast("int", gv.value), tv)
                            for spec_mv, mv in zip(spec_m_vars, m_vars, strict=True):
                                sub_ep = self.substitute(sub_ep, cast("int", spec_mv.value), mv)
                            sub_ep = self.substitute(
                                sub_ep, cast("int", mspec.self_var.value), applied_m_term
                            )
                            if not self._prove_bool_precondition(sub_ep, post_env):
                                raise self.fail(
                                    "type",
                                    f"impl method '{mname}' does not satisfy ensures clause of interface '{iface_name}'",
                                    mnode,
                                )
                        for ec in m_ens_clauses:
                            ev_b = self.expression(self.node(ec["value"]), post_env)
                            if self.whnf(ev_b.type) != _BOOL or not self._prove_bool_precondition(
                                ev_b.term, post_env
                            ):
                                raise self.fail(
                                    "type",
                                    f"impl method '{mname}' does not satisfy its ensures clause",
                                    ec,
                                )
                    finally:
                        self.active_facts = saved_pf

            for lname, lspec in iface.laws.items():
                lnode = impl_laws_by_name[lname]
                self.site = lnode
                self.reset_budget()
                l_first_meta = len(self.metas)
                self.mutable_locals.clear()
                self.out_param_names.clear()
                self.uninitialized_out_params.clear()
                if lnode["body"] is None:
                    raise self.fail(
                        "type",
                        f"impl law '{lname}' requires an explicit proof body",
                        lnode,
                    )
                if self.nodes(lnode["generics"]):
                    raise self.fail(
                        "unsupported",
                        "generic impl laws require the full frontend",
                        lnode,
                    )
                l_params = self.nodes(lnode["parameters"])
                expected_l_pcount = (
                    0
                    if (
                        len(lspec.param_vars) == 1
                        and cast("int", lspec.param_vars[0].value) in self.nullary_parameters
                    )
                    else len(lspec.param_vars)
                )
                if len(l_params) != expected_l_pcount:
                    raise self.fail(
                        "type",
                        f"impl law '{lname}' parameter count does not match interface '{iface_name}'",
                        lnode,
                    )
                l_vars, l_env = self.telescope([], l_params, impl_env, unit=True)
                for idx_v, (lv, spec_lv) in enumerate(zip(l_vars, lspec.param_vars, strict=True)):
                    expected_dom = self.types[cast("int", spec_lv.value)]
                    for gv, tv in zip(iface.generic_vars, target_types, strict=True):
                        expected_dom = self.substitute(expected_dom, cast("int", gv.value), tv)
                    for prev_slv, prev_lv in zip(lspec.param_vars[:idx_v], l_vars[:idx_v], strict=True):
                        expected_dom = self.substitute(expected_dom, cast("int", prev_slv.value), prev_lv)
                    self.site = lnode
                    self.unify(self.types[cast("int", lv.value)], expected_dom)

                inst_l_reqs: list[_Term] = []
                inst_l_req_bools: list[_Term] = []
                for rp in lspec.req_props:
                    sub_rp = rp
                    for gv, tv in zip(iface.generic_vars, target_types, strict=True):
                        sub_rp = self.substitute(sub_rp, cast("int", gv.value), tv)
                    for spec_lv, lv in zip(lspec.param_vars, l_vars, strict=True):
                        sub_rp = self.substitute(sub_rp, cast("int", spec_lv.value), lv)
                    for mname, mspec in iface.methods.items():
                        sub_rp = self.substitute(
                            sub_rp,
                            cast("int", mspec.self_var.value),
                            applied_self_methods[mname],
                        )
                    inst_l_reqs.append(sub_rp)
                    ext = self._extract_equality(sub_rp)
                    if (
                        ext is not None
                        and self.whnf(ext[0]) == _BOOL
                        and self.whnf(ext[2]) == _term("bool", value=1)
                    ):
                        inst_l_req_bools.append(ext[1])

                l_ens_nodes = [
                    c for c in self.nodes(lnode["contracts"]) if c["role"] == "ensures"
                ]
                if len(l_ens_nodes) != len(lspec.ensures_props):
                    raise self.fail(
                        "type",
                        f"impl law '{lname}' ensures clause count does not match interface '{iface_name}'",
                        lnode,
                    )
                for ens_idx, (spec_ep, impl_ec) in enumerate(
                    zip(lspec.ensures_props, l_ens_nodes, strict=True)
                ):
                    expected_ep = spec_ep
                    for gv, tv in zip(iface.generic_vars, target_types, strict=True):
                        expected_ep = self.substitute(expected_ep, cast("int", gv.value), tv)
                    for spec_lv, lv in zip(lspec.param_vars, l_vars, strict=True):
                        expected_ep = self.substitute(expected_ep, cast("int", spec_lv.value), lv)
                    for mname, mspec in iface.methods.items():
                        expected_ep = self.substitute(
                            expected_ep,
                            cast("int", mspec.self_var.value),
                            applied_self_methods[mname],
                        )
                    saved_lf = list(self.active_facts)
                    self.active_facts.extend(inst_l_req_bools)
                    try:
                        impl_ep = self.proposition(self.node(impl_ec["value"]), l_env)
                    finally:
                        self.active_facts = saved_lf
                    self.site = impl_ec
                    self.unify(impl_ep, expected_ep)
                    law_goal = expected_ep
                    for rp in reversed(inst_l_reqs):
                        law_goal = self.pi(rp, law_goal)
                    full_l_vars = [*impl_generic_vars, *impl_witness_vars, *l_vars]
                    law_sig = self.wrap("pi", full_l_vars, law_goal)
                    prev_ret = self.current_return_type
                    self.current_return_type = law_goal
                    saved_lbody_f = list(self.active_facts)
                    self.active_facts.extend([*inst_l_req_bools, *self._fact_bool_terms((), l_env)])
                    try:
                        law_proof = self.check(self.node(lnode["body"]), law_goal, l_env)
                    finally:
                        self.active_facts = saved_lbody_f
                        self.current_return_type = prev_ret
                    law_def = self.wrap("lam", full_l_vars, law_proof)
                    self.site = lnode
                    self.complete(law_sig)
                    self.complete(law_def)
                    for index in range(l_first_meta, len(self.metas)):
                        self.complete(_term("meta", value=index))
                        self.complete(self.metas[index].type)
                    suffix = "" if ens_idx == 0 else f"_ensures_{ens_idx}"
                    l_emitted = f"vela_d{len(self.output)}_impl_{iface_name}_{lname}{suffix}"
                    self.output.append(
                        f"Definition {l_emitted} : {self.render(law_sig)} :=\n  {self.render(law_def)}."
                    )
                    l_binding = _Binding(_constant(l_emitted), law_sig, len(impl_generic_vars))
                    self.constants[l_emitted] = l_binding
                    self.definitions[l_emitted] = law_def
        finally:
            self.active_interface_witnesses.pop(self_active_key, None)
            self.active_interface_ensures.pop(self_active_key, None)
            for wk in active_where_keys:
                self.active_interface_witnesses.pop(wk, None)
                self.active_interface_ensures.pop(wk, None)
            self.mutable_locals.clear()
            self.out_param_names.clear()
            self.uninitialized_out_params.clear()

        final_inst = _ImplInstance(
            interface_name=iface_name,
            generic_vars=tuple(impl_generic_vars),
            target_types=tuple(target_types),
            where_constraints=tuple((wi.name, wt) for wi, wt, _ in where_iface_constraints),
            methods=emitted_methods,
        )
        self.impls.setdefault(iface_name, []).append(final_inst)

    def _resolve_single_interface_witness(
        self: _Elaborator,
        iface_name: str,
        inst_t_args: tuple[_Term, ...],
        environment: dict[str, _Binding],
        call_site: Node | None,
    ) -> tuple[dict[str, _Binding], dict[str, tuple[tuple[int, ...], tuple[_Term, ...]]]]:
        for (act_iface, act_t_args), w_dict in self.active_interface_witnesses.items():
            if act_iface == iface_name and len(act_t_args) == len(inst_t_args):
                saved_metas = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if all(self._try_unify(a, b) for a, b in zip(act_t_args, inst_t_args, strict=True)):
                    return w_dict, self.active_interface_ensures.get((act_iface, act_t_args), {})
                self.metas = saved_metas

        iface = self.interfaces[iface_name]
        for impl_inst in self.impls.get(iface_name, []):
            saved_metas = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            g_metas: list[_Term] = []
            for gv in impl_inst.generic_vars:
                dom = self.types[cast("int", gv.value)]
                for prev_gv, prev_m in zip(impl_inst.generic_vars[: len(g_metas)], g_metas, strict=True):
                    dom = self.substitute(dom, cast("int", prev_gv.value), prev_m)
                g_metas.append(self.meta(dom, environment))
            inst_targets: list[_Term] = []
            for t in impl_inst.target_types:
                sub_t = t
                for gv, gm in zip(impl_inst.generic_vars, g_metas, strict=True):
                    sub_t = self.substitute(sub_t, cast("int", gv.value), gm)
                inst_targets.append(sub_t)
            if all(
                self._try_unify(pat_t, arg_t)
                for pat_t, arg_t in zip(inst_targets, inst_t_args, strict=True)
            ):
                g_sols = [self.whnf(self.resolve(gm)) for gm in g_metas]
                impl_witness_args: list[_Term] = []
                for w_iface_name, w_raw_t_args in impl_inst.where_constraints:
                    w_inst_t_args: list[_Term] = []
                    for wt in w_raw_t_args:
                        wt_sub = wt
                        for gv, gsol in zip(impl_inst.generic_vars, g_sols, strict=True):
                            wt_sub = self.substitute(wt_sub, cast("int", gv.value), gsol)
                        w_inst_t_args.append(self.whnf(wt_sub))
                    sub_w_dict, _ = self._resolve_single_interface_witness(
                        w_iface_name, tuple(w_inst_t_args), environment, call_site
                    )
                    sub_iface = self.interfaces[w_iface_name]
                    if sub_iface.methods:
                        impl_witness_args.extend(
                            sub_w_dict[sub_mname].term for sub_mname in sub_iface.methods
                        )
                    else:
                        impl_witness_args.append(_term("unit"))
                res_methods: dict[str, _Binding] = {}
                res_ensures: dict[str, tuple[tuple[int, ...], tuple[_Term, ...]]] = {}
                for mname, mspec in iface.methods.items():
                    m_b = impl_inst.methods[mname]
                    m_term, m_type = m_b.term, m_b.type
                    for arg_term in [*g_sols, *impl_witness_args]:
                        m_type = self.whnf(m_type)
                        m_term = _app(m_term, arg_term)
                        m_type = self.substitute(m_type.args[1], cast("int", m_type.value), arg_term)
                    res_methods[mname] = _Binding(m_term, m_type, mspec.method_generics)
                    if mspec.ensures_props:
                        inst_ens: list[_Term] = []
                        for ep in mspec.ensures_props:
                            sub_ep = ep
                            for gv, tv in zip(iface.generic_vars, inst_t_args, strict=True):
                                sub_ep = self.substitute(sub_ep, cast("int", gv.value), tv)
                            sub_ep = self.substitute(
                                sub_ep, cast("int", mspec.self_var.value), m_term
                            )
                            inst_ens.append(sub_ep)
                        rem_m_ids = tuple(
                            cast("int", v.value) for v in [*mspec.generic_vars, *mspec.param_vars]
                        )
                        res_ensures[mname] = (rem_m_ids, tuple(inst_ens))
                return res_methods, res_ensures
            self.metas = saved_metas

        raise self.fail(
            "type",
            f"no implementation of interface '{iface_name}' for the given type arguments",
            call_site,
        )

    def _resolve_interface_witnesses(
        self: _Elaborator,
        callee_emitted: str,
        full_args: list[_Term],
        environment: dict[str, _Binding],
        call_site: Node | None,
    ) -> list[_Term]:
        param_ids, specs = self.callable_where_constraints[callee_emitted]
        witness_terms: list[_Term] = []
        for iface_name, raw_t_args in specs:
            inst_t_args: list[_Term] = []
            for rt in raw_t_args:
                sub_t = rt
                for pid, aval in zip(param_ids, full_args, strict=False):
                    sub_t = self.substitute(sub_t, pid, aval)
                inst_t_args.append(self.whnf(sub_t))
            w_dict, _ = self._resolve_single_interface_witness(
                iface_name, tuple(inst_t_args), environment, call_site
            )
            iface = self.interfaces[iface_name]
            if iface.methods:
                witness_terms.extend(w_dict[mname].term for mname in iface.methods)
            else:
                witness_terms.append(_term("unit"))
        return witness_terms

    def declaration(self: _Elaborator, node: Node) -> None:
        self.site = node
        self.reset_budget()
        first_meta = len(self.metas)
        self.decl_first_meta = first_meta
        self.whnf_cache.clear()
        self.mutable_locals.clear()
        self.out_param_names.clear()
        self.uninitialized_out_params.clear()
        self.last_call_updates.clear()
        self.entry_env = {}
        self.final_ref_bindings = {}
        self.final_return_facts = []
        self.frozen_collections.clear()
        self.lifted_invariants.clear()
        self.active_lift_scopes = 0
        self.in_loop_depth = 0
        kind = node["kind"]
        if kind == "import":
            self._import_declaration(node)
            return
        if kind == "record":
            self._record_declaration(node, first_meta)
            return
        if kind == "union":
            self._union_declaration(node, first_meta)
            return
        if kind == "interface":
            self._interface_declaration(node, first_meta)
            return
        if kind == "impl":
            self._impl_declaration(node, first_meta)
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
                or name in self.union_ctors or name in self.interfaces
                or name in {"Type", "_", "this"} or "." in name):
            raise self.fail("name", f"duplicate or reserved declaration '{name}'")
        self._record_visibility(name, modifiers, node)
        generics = [] if kind in {"constant", "property"} else self.nodes(node["generics"])
        parameters = [] if kind in {"alias", "constant", "property"} else self.nodes(node["parameters"])
        variables, environment = self.telescope(
            generics, parameters, {}, unit=kind not in {"alias", "constant", "property"}
        )
        if kind in {"theorem", "lemma"} and self.out_param_names:
            raise self.fail("type", "proof declarations do not accept 'out' initialization parameters", node)
        ref_param_names = set(self.mutable_locals)
        self.entry_env = dict(environment)
        self.final_ref_bindings = dict(environment)
        where_iface_constraints: list[tuple[_InterfaceInfo, tuple[_Term, ...], Node]] = []
        if requires_clauses:
            filtered_reqs: list[Node] = []
            for rc in requires_clauses:
                if rc["role"] == "where":
                    ifaces_c, props_c = self._split_where_clause(rc, environment)
                    where_iface_constraints.extend(ifaces_c)
                    filtered_reqs.extend(props_c)
                else:
                    filtered_reqs.append(rc)
            requires_clauses = filtered_reqs
        witness_vars, active_where_keys = self._bind_where_constraints(where_iface_constraints)
        try:
            is_recursive = False
            is_post_env_theorem = False
            post_env_obligations: list[tuple[_Term, Node]] = []
            post_env_binders: list[_Term] = []
            post_env_facts: list[_Term] = []
            post_state_images: list[tuple[_Term, _Term]] = []
            self_var: _Term | None = None
            candidates: list[tuple[int, int]] = []
            req_bool_terms: list[_Term] = []
            req_vars: list[_Term] = []
            req_props: list[_Term] = []
            generic_vars = variables[:len(generics)]
            param_vars = variables[len(generics):]
            variables = [*generic_vars, *param_vars, *witness_vars]
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
                req_props = []
                if kind in {"theorem", "lemma"}:
                    saved_req_active = list(self.active_facts)
                    try:
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
                                ):
                                    ty_w = self.whnf(args_p[0])
                                    if ty_w == _BOOL:
                                        rhs_w = self.whnf(args_p[2])
                                        if rhs_w.kind == "bool" and rhs_w.value == 1:
                                            req_bool_terms.append(args_p[1])
                                            self.active_facts.append(args_p[1])
                                    else:
                                        spec_p = self._int_spec(ty_w)
                                        if spec_p is not None:
                                            eq_b = _apps(_constant(f"int_eq_{spec_p.name}"), args_p[1], args_p[2])
                                            req_bool_terms.append(eq_b)
                                            self.active_facts.append(eq_b)
                                        elif ty_w == _NAT:
                                            eq_b = _apps(_constant("eq_nat"), args_p[1], args_p[2])
                                            req_bool_terms.append(eq_b)
                                            self.active_facts.append(eq_b)
                    finally:
                        self.active_facts = saved_req_active
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
                    if node["body"] is None:
                        raise self.fail("unsupported", "a theorem requires a complete explicit proof body", node)
                    body_node = self.node(node["body"])
                    if ref_param_names:
                        is_post_env_theorem = True
                        result = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                    else:
                        saved_ens_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                        self.active_facts.extend(req_bool_terms)
                        try:
                            result = self.proposition(self.node(ensures_clauses[0]["value"]), environment)
                        except VelaError as err:
                            self.metas = saved_ens_m
                            if err.kind == "name":
                                is_post_env_theorem = True
                                result = _apps(_constant("Eq"), _BOOL, _term("bool", value=1), _term("bool", value=1))
                            else:
                                raise
                        finally:
                            for _ in req_bool_terms:
                                self.active_facts.pop()
                    for req_prop in reversed(req_props):
                        result = self.pi(req_prop, result)
                else:
                    result = self.type(self.node(node["result"]), environment)
                    raw_body = node["value"] if kind == "definition" else node["body"]
                    if raw_body is None:
                        raise self.fail("unsupported", "abstract callable signatures have no emitted implementation", node)
                    body_node = self.node(raw_body)
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
                self.current_rec_witnesses = list(witness_vars)
                self.current_rec_candidates = candidates
                self.smaller_vars = {p_var_id: set() for _, p_var_id in candidates}
                self.current_return_type = result
                entry_body_facts = [*req_bool_terms, *self._fact_bool_terms((), environment)]
                saved_body_facts = list(self.active_facts)
                self.active_facts.extend(entry_body_facts)
                self.used_domain_solver_in_proof = False
                self.final_theorem_facts = ()
                try:
                    if is_post_env_theorem:
                        self.in_post_env_theorem = True
                        try:
                            req_fact_bindings = tuple(_Binding(self.fresh(rp), rp) for rp in req_props)
                            self.block(body_node, body_env, None, facts=req_fact_bindings)
                        finally:
                            self.in_post_env_theorem = False
                        post_env = dict(self.final_ref_bindings)
                        post_env_binders = [*variables, *(binding.term for binding in req_fact_bindings)]
                        post_env_facts = [
                            *self.active_facts,
                            *self.final_return_facts,
                            *self._fact_bool_terms(self.final_theorem_facts, post_env),
                        ]
                        for ens_contract in ensures_clauses:
                            self.reset_budget()
                            ens_prop = self.proposition(self.node(ens_contract["value"]), post_env)
                            post_env_obligations.append((ens_prop, ens_contract))
                            try:
                                self._prove_proposition(
                                    ens_prop,
                                    post_env,
                                    self.final_theorem_facts,
                                    ens_contract,
                                    allow_refl=False,
                                    include_env=False,
                                )
                            except VelaError:
                                if not self._entailed_by_theorem_facts(ens_prop, post_env):
                                    raise self.fail(
                                        "type", "could not discharge theorem postcondition", ens_contract
                                    ) from None
                        body = _apps(_constant("Refl"), _BOOL, _term("bool", value=1))
                    else:
                        body = self.check(body_node, result, body_env)
                    if self._has_unapplied_rec_var(body, cast("int", self_var.value)):
                        raise self.fail("type", f"recursive reference to '{name}' must be a direct call", body_node)
                    is_recursive = self.current_rec_used
                    if is_recursive:
                        candidates = list(self.current_rec_candidates)
                    if kind in {"definition", "function"}:
                        if self.uninitialized_out_params:
                            uninit_name = min(self.uninitialized_out_params)
                            raise self.fail(
                                "type",
                                f"out parameter '{uninit_name}' is not initialized on all exit paths",
                                body_node,
                            )
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
                    self.current_rec_witnesses = []
                    self.current_rec_candidates = []
                    self.current_rec_used = False
                    self.smaller_vars = {}
                    self.current_return_type = None
            emitted = f"vela_d{len(self.output)}_{name}"
            if kind in {"theorem", "lemma"} and is_post_env_theorem:
                if not post_env_obligations:
                    raise self.fail("type", "a theorem over mutated parameters requires an ensures clause", node)
                first_prop, first_contract = post_env_obligations[0]
                signature, generalized = self._solver_statement(post_env_binders, first_prop, post_env_facts)
                reason = "theorem over mutated parameters discharged by the untrusted solver"
                if generalized:
                    reason = f"{reason}; generalized over elaboration-local state with its facts"
                definition = self._emit_solver_trusted(emitted, signature, first_contract, reason, len(generics))
                result = signature
            elif kind in {"theorem", "lemma"} and self.used_domain_solver_in_proof:
                definition = self._emit_solver_trusted(
                    emitted, signature, node, "theorem proof step discharged by the untrusted solver", len(generics)
                )
            else:
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
            if is_recursive and self_var is not None:
                self.fix_names[cast("int", self_var.value)] = emitted
            if definition.kind == "const" and str(definition.value).startswith("vela_solver_"):
                # The axiom carries the statement; the export's type is inferred from it.
                self.output.append(f"Definition {emitted} :=\n  {self.render(definition)}.")
            else:
                self.output.append(f"Definition {emitted} : {self.render(signature)} :=\n  {self.render(definition)}.")
            binding = _Binding(_constant(emitted), signature, len(generics), constant=kind == "constant")
            self.globals[name] = binding
            # Generated references never become names in the source namespace.
            self.constants[emitted] = binding
            self.definitions[emitted] = definition
            for post_idx, (post_prop, post_contract) in enumerate(post_env_obligations[1:], start=1):
                self._emit_obligation(
                    f"{emitted}_ensures_{post_idx}",
                    post_env_binders,
                    post_prop,
                    None,
                    post_contract,
                    "theorem over mutated parameters discharged by the untrusted solver",
                    len(generics),
                    post_env_facts,
                )
            if where_iface_constraints:
                base_param_ids = tuple(cast("int", v.value) for v in [*generic_vars, *param_vars])
                self.callable_where_constraints[emitted] = (
                    base_param_ids,
                    tuple((wi.name, wt) for wi, wt, _ in where_iface_constraints),
                )
            if ref_param_names and kind in {"definition", "function"}:
                base_param_ids = tuple(cast("int", v.value) for v in [*generic_vars, *param_vars])
                all_var_ids = {cast("int", v.value) for v in [*generic_vars, *param_vars]}
                idx_to_term: dict[int, _Term] = {}
                for p_idx, p_node in enumerate(parameters):
                    if p_node["name"] is not None:
                        pname = self.name(p_node["name"])
                        if pname in ref_param_names and pname in self.final_ref_bindings:
                            fin_t = self.final_ref_bindings[pname].term
                            if self.free(fin_t) <= all_var_ids:
                                idx_to_term[p_idx] = fin_t
                if idx_to_term:
                    self.callable_ref_updates[emitted] = (base_param_ids, idx_to_term)
                for p_idx, fin_t in idx_to_term.items():
                    pname = self.name(parameters[p_idx]["name"])
                    post_name = f"{emitted}_post_{pname}"
                    post_type = self.final_ref_bindings[pname].type
                    post_sig = self.wrap("pi", variables, post_type)
                    post_def = self.wrap("lam", variables, fin_t)
                    self.complete(post_sig)
                    self.complete(post_def)
                    # The kernel image of the callable's effect on this exclusive loan.
                    self.output.append(f"Definition {post_name} : {self.render(post_sig)} :=\n  {self.render(post_def)}.")
                    self.constants[post_name] = _Binding(_constant(post_name), post_sig, len(generics))
                    self.definitions[post_name] = post_def
                    post_state_images.append((fin_t, _apps(_constant(post_name), *variables)))
            if kind in {"theorem", "lemma"} and len(ensures_clauses) > 1 and not is_post_env_theorem:
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
                    self.current_rec_witnesses = list(witness_vars)
                    self.current_rec_candidates = list(init_candidates)
                    self.smaller_vars = {p_var_id: set() for _, p_var_id in init_candidates}
                    self.current_return_type = extra_res
                    saved_extra_facts = list(self.active_facts)
                    self.active_facts.extend(entry_body_facts)
                    self.used_domain_solver_in_proof = cast("bool", False)
                    self.final_theorem_facts = ()
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
                        self.current_rec_witnesses = []
                        self.current_rec_candidates = []
                        self.current_rec_used = False
                        self.smaller_vars = {}
                        self.current_return_type = None
                    if self.used_domain_solver_in_proof:
                        extra_def = self._emit_solver_trusted(
                            f"{emitted}_ensures_{ens_idx}",
                            extra_sig,
                            ens_contract,
                            "theorem proof step discharged by the untrusted solver",
                            len(generics),
                        )
                    else:
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
                base_param_ids = tuple(cast("int", v.value) for v in [*generic_vars, *param_vars])
                self.callable_preconditions[emitted] = [(base_param_ids, req_t) for req_t in req_bool_terms]
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
                                if (
                                    target_param_name in ref_param_names
                                    and target_param_name in self.final_ref_bindings
                                    and self.final_ref_bindings[target_param_name].term != param_b.term
                                    and self.free(self.final_ref_bindings[target_param_name].term) <= post_var_ids
                                ):
                                    restored_span_term = self.final_ref_bindings[target_param_name].term
                                elif self.whnf(result) == span_u8:
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
                                    self._emit_obligation(
                                        f"{emitted}_restores_{rest_idx}_{field_tag}",
                                        post_vars,
                                        rest_prop,
                                        rest_proof,
                                        rest_contract,
                                        "descriptor preservation discharged by the untrusted solver",
                                        len(generics),
                                        list(self.active_facts),
                                        post_state_images,
                                    )
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
                                    self._emit_obligation(
                                        f"{emitted}_restores_{rest_idx}_{field_tag}",
                                        post_vars,
                                        rest_prop,
                                        rest_proof,
                                        rest_contract,
                                        "descriptor preservation discharged by the untrusted solver",
                                        len(generics),
                                        list(self.active_facts),
                                        post_state_images,
                                    )
                            else:
                                raise self.fail(
                                    "type",
                                    f"restores parameter '{target_param_name}' must have type Span<byte> or Slots<T, capacity>",
                                    rest_val_node,
                                )
                        else:
                            self.reset_budget()
                            rest_prop = self.asserted_proposition(rest_val_node, post_env)
                            rest_proof: _Term | None
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
                                if not proved_rest:
                                    raise
                                rest_proof = None
                            self._emit_obligation(
                                f"{emitted}_restores_{rest_idx}",
                                post_vars,
                                rest_prop,
                                rest_proof,
                                rest_contract,
                                "restoration predicate discharged by the untrusted solver",
                                len(generics),
                                list(self.active_facts),
                                post_state_images,
                            )
                    sym_post_env = dict(environment)
                    sym_res_var = self.fresh(result)
                    sym_post_env["result"] = _Binding(sym_res_var, result)
                    sym_loan_pairs: list[tuple[int, int]] = []
                    for p_idx, p_node in enumerate(parameters):
                        if p_node["name"] is not None:
                            pname = self.name(p_node["name"])
                            if pname in ref_param_names:
                                p_dom = self.types[cast("int", param_vars[p_idx].value)]
                                sym_lvar = self.fresh(p_dom)
                                sym_post_env[pname] = _Binding(sym_lvar, p_dom)
                                sym_loan_pairs.append((p_idx, cast("int", sym_lvar.value)))
                    base_param_ids = tuple(cast("int", v.value) for v in [*generic_vars, *param_vars])
                    for ens_idx, ens_contract in enumerate(ensures_clauses):
                        self.reset_budget()
                        ens_val_node = self.node(ens_contract["value"])
                        ens_prop = self.asserted_proposition(ens_val_node, post_env)
                        ens_proof: _Term | None
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
                            if not proved_alt:
                                raise
                            ens_proof = None
                        self._emit_obligation(
                            f"{emitted}_ensures_{ens_idx}",
                            post_vars,
                            ens_prop,
                            ens_proof,
                            ens_contract,
                            "postcondition discharged by the untrusted solver",
                            len(generics),
                            [*self.active_facts, *self._fact_bool_terms((), post_env)],
                            post_state_images,
                        )
                        saved_sym_m = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                        try:
                            sym_eb = self.expression(ens_val_node, sym_post_env)
                            if self.whnf(sym_eb.type) == _BOOL:
                                self.callable_ensures.setdefault(emitted, []).append(
                                    (
                                        base_param_ids,
                                        tuple(sym_loan_pairs),
                                        cast("int", sym_res_var.value),
                                        sym_eb.term,
                                    )
                                )
                        except VelaError:
                            self.metas = saved_sym_m
                finally:
                    self.active_facts = saved_post_facts
        finally:
            for wk in active_where_keys:
                self.active_interface_witnesses.pop(wk, None)
                self.active_interface_ensures.pop(wk, None)
            self.out_param_names.clear()
            self.uninitialized_out_params.clear()
            self.last_call_updates.clear()

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

    def _split_and_conjuncts(self: _Elaborator, term: _Term) -> list[_Term]:
        w = self.whnf(term)
        head, args = self.spine(w)
        if head == _constant("&&") and len(args) == 2:
            return [*self._split_and_conjuncts(args[0]), *self._split_and_conjuncts(args[1])]
        return [term]

    def _entailed_by_theorem_facts(
        self: _Elaborator, ens_prop: _Term, post_env: dict[str, _Binding]
    ) -> bool:
        if not self.final_theorem_facts:
            return False
        prop_eqs: list[tuple[_Term, _Term, _Term]] = []
        bool_conjuncts: list[_Term] = []
        for fact in self.final_theorem_facts:
            saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
            if self._try_unify(fact.type, ens_prop):
                return True
            self.metas = saved
            f_ext = self._extract_equality(fact.type)
            if f_ext is not None:
                f_ty, f_u, f_v = f_ext
                if self.whnf(f_ty) == _BOOL and self.whnf(f_v) == _term("bool", value=1):
                    for c in self._split_and_conjuncts(f_u):
                        bool_conjuncts.append(c)
                        c_w = self.whnf(c)
                        c_h, c_args = self.spine(c_w)
                        if (
                            c_h.kind == "const"
                            and isinstance(c_h.value, str)
                            and (
                                c_h.value in {"eq_nat", "char_eq", "bool_eq"}
                                or c_h.value.startswith(("int_eq_", "union_eq_", "record_eq_"))
                            )
                            and len(c_args) == 2
                        ):
                            prop_eqs.append((_UNIT, c_args[0], c_args[1]))
                else:
                    prop_eqs.append((f_ty, f_u, f_v))

        def match_eq(lhs: _Term, rhs: _Term) -> bool:
            lhs_s = self._simplify_span_read_with_facts(lhs, self.active_facts)
            rhs_s = self._simplify_span_read_with_facts(rhs, self.active_facts)
            for _, u, v in prop_eqs:
                u_s = self._simplify_span_read_with_facts(u, self.active_facts)
                v_s = self._simplify_span_read_with_facts(v, self.active_facts)
                for a1, a2 in ((lhs, rhs), (lhs_s, rhs_s)):
                    for b1, b2 in ((u, v), (u_s, v_s)):
                        saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                        if (self._try_unify(a1, b1) and self._try_unify(a2, b2)) or (
                            self._try_unify(a1, b2) and self._try_unify(a2, b1)
                        ):
                            return True
                        self.metas = saved
            return False

        def match_bool_conjunct(conj: _Term) -> bool:
            for bc in bool_conjuncts:
                saved = [_Meta(m.type, m.scope, m.solution) for m in self.metas]
                if self._try_unify(conj, bc):
                    return True
                self.metas = saved
            c_w = self.whnf(conj)
            c_h, c_args = self.spine(c_w)
            return (
                c_h.kind == "const"
                and isinstance(c_h.value, str)
                and (
                    c_h.value in {"eq_nat", "char_eq", "bool_eq"}
                    or c_h.value.startswith(("int_eq_", "union_eq_", "record_eq_"))
                )
                and len(c_args) == 2
                and match_eq(c_args[0], c_args[1])
            )

        e_ext = self._extract_equality(ens_prop)
        if e_ext is not None:
            e_ty, e_u, e_v = e_ext
            if self.whnf(e_ty) == _BOOL and self.whnf(e_v) == _term("bool", value=1):
                conjs = self._split_and_conjuncts(e_u)
                if conjs and all(match_bool_conjunct(c) for c in conjs):
                    return True
            if match_eq(e_u, e_v):
                return True
        return False


