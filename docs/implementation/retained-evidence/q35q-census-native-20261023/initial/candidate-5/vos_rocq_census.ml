(* SPDX-License-Identifier: Apache-2.0 *)
(* Original VerifiedOS serializer against the locked Rocq 9.3.0 public API.
   This is metadata evidence, never a census or proof-acceptance decision. *)
open Names
open Constr
open Declarations
open Mod_declarations

type json = S of string | N of int | B of bool | A of json list | O of (string * json) list | Null
let rec encode = function
| S s -> let b = Buffer.create (String.length s + 2) in
  Buffer.add_char b '"'; String.iter (fun c -> match c with
  | '"' -> Buffer.add_string b "\\\"" | '\\' -> Buffer.add_string b "\\\\"
  | c when Char.code c < 32 -> Buffer.add_string b (Printf.sprintf "\\u%04x" (Char.code c))
  | c -> Buffer.add_char b c) s; Buffer.add_char b '"'; Buffer.contents b
| N n -> string_of_int n | B b -> string_of_bool b | Null -> "null"
| A a -> "[" ^ String.concat "," (List.map encode a) ^ "]"
| O a -> "{" ^ String.concat "," (List.map (fun (k,v) -> encode (S k) ^ ":" ^ encode v) a) ^ "}"
let node tag xs = O (("tag", S tag)::xs)
let arr f a = A (Array.to_list (Array.map f a))
let lst f a = A (List.map f a)
let opt f = function None -> Null | Some x -> f x
let id i = S (Id.to_string i)
let name = function Name.Anonymous -> node "Anonymous" [] | Name.Name i -> node "Name" ["id",id i]
let dir d = lst id (DirPath.repr d)
let mbid x = let n,i,d = MBId.repr x in O ["stamp",N n; "id",id i; "directory_reversed",dir d]
let module_domain = ref ModPath.Set.empty
let kernel_domain = ref KerName.Set.empty
let rec path p =
  module_domain := ModPath.Set.add p !module_domain;
  match p with
| ModPath.MPfile d -> node "MPfile" ["directory_reversed",dir d]
| ModPath.MPbound x -> node "MPbound" ["identifier",mbid x]
| ModPath.MPdot (p,i) -> node "MPdot" ["parent",path p; "label",id i]
let kernel_name x = kernel_domain := KerName.Set.add x !kernel_domain; let p,i = KerName.repr x in O ["path",path p;"label",id i]
let constant c = O ["user",kernel_name (Constant.user c);"canonical",kernel_name (Constant.canonical c)]
let mind m = O ["user",kernel_name (MutInd.user m);"canonical",kernel_name (MutInd.canonical m)]
let ind (m,i) = O ["block",mind m;"index_zero_based",N i]
let construct (i,k) = O ["inductive",ind i;"index_one_based",N k]
let qvar q = match Sorts.QVar.repr q with
| Sorts.QVar.Var n -> node "Var" ["index",N n]
| Sorts.QVar.Secvar n -> node "Secvar" ["index",N n]
| Sorts.QVar.Unif (s,n) -> node "Unif" ["name",S s;"index",N n]
let qglobal g = let d,n = Sorts.QGlobal.repr g in O ["directory_reversed",dir d;"index",N n]
let quality = function
| Sorts.Quality.QVar q -> node "QVar" ["variable",qvar q]
| Sorts.Quality.QGlobal q -> node "QGlobal" ["global",qglobal q]
| Sorts.Quality.QConstant q -> node (match q with QProp -> "QProp" | QSProp -> "QSProp" | QType -> "QType") []
let level l = if Univ.Level.is_set l then node "Set" [] else
  match Univ.Level.var_index l, Univ.Level.name l with
  | Some n,None -> node "Var" ["index",N n]
  | None,Some g -> let d,s,n = Univ.UGlobal.repr g in node "Global" ["directory_reversed",dir d;"name",S s;"index",N n]
  | _ -> CErrors.user_err (Pp.str "VOS census unsupported universe-level representation")
let universe u = lst (fun (l,n) -> O ["level",level l;"offset",N n]) (Univ.Universe.repr u)
let instance u = let q,l = UVars.Instance.to_array u in O ["qualities",arr quality q;"levels",arr level l]
let sort = function
| Sorts.SProp -> node "SProp" [] | Sorts.Prop -> node "Prop" [] | Sorts.Set -> node "Set" []
| Sorts.Type u -> node "Type" ["universe",universe u]
| Sorts.GSort (q,u) -> node "GSort" ["quality",qglobal q;"universe",universe u]
| Sorts.VSort (q,u) -> node "VSort" ["quality",qvar q;"universe",universe u]
let relevance = function
| Sorts.Relevant -> node "Relevant" [] | Sorts.Irrelevant -> node "Irrelevant" []
| Sorts.RelevanceVar q -> node "RelevanceVar" ["variable",qvar q]
let binder a = O ["name",name (Context.binder_name a);"relevance",relevance (Context.binder_relevance a)]
let cast = function VMcast -> "VMcast" | NATIVEcast -> "NATIVEcast" | DEFAULTcast -> "DEFAULTcast"
let style = function LetStyle -> "LetStyle" | IfStyle -> "IfStyle" | LetPatternStyle -> "LetPatternStyle" | MatchStyle -> "MatchStyle"
let case_info c = O ["inductive",ind c.ci_ind;"parameters",N c.ci_npar;"constructor_declarations",arr (fun n->N n) c.ci_cstr_ndecls;"constructor_arguments",arr (fun n->N n) c.ci_cstr_nargs;"printing_style",S (style c.ci_pp_info.style)]
let projection p = O ["inductive",ind (Projection.inductive p);"parameters",N (Projection.npars p);"argument",N (Projection.arg p);"unfolded",B (Projection.unfolded p)]
let rec term t = match Constr.kind t with
| Rel n -> node "Rel" ["index_one_based",N n]
| Var i -> node "Var" ["id",id i]
| Meta n -> CErrors.user_err (Pp.str ("VOS census unsupported Meta " ^ string_of_int n))
| Evar _ -> CErrors.user_err (Pp.str "VOS census unsupported Evar")
| Sort s -> node "Sort" ["sort",sort s]
| Cast (v,k,t) -> node "Cast" ["value",term v;"kind",S (cast k);"type",term t]
| Prod (a,t,b) -> node "Prod" ["binder",binder a;"type",term t;"body",term b]
| Lambda (a,t,b) -> node "Lambda" ["binder",binder a;"type",term t;"body",term b]
| LetIn (a,v,t,b) -> node "LetIn" ["binder",binder a;"value",term v;"type",term t;"body",term b]
| App (f,a) -> node "App" ["function",term f;"arguments",arr term a]
| Const (c,u) -> node "Const" ["name",constant c;"instance",instance u]
| Ind (i,u) -> node "Ind" ["name",ind i;"instance",instance u]
| Construct (i,u) -> node "Construct" ["name",construct i;"instance",instance u]
| Case (c,u,ps,((ns,p),r),inv,v,bs) -> node "Case" ["info",case_info c;"instance",instance u;"parameters",arr term ps;"return",O ["binders",arr binder ns;"type",term p;"relevance",relevance r];"inversion",(match inv with NoInvert -> node "NoInvert" [] | CaseInvert {indices} -> node "CaseInvert" ["indices",arr term indices]);"scrutinee",term v;"branches",arr (fun (ns,b) -> O ["binders",arr binder ns;"body",term b]) bs]
| Fix ((rs,n),d) -> node "Fix" ["recursive_arguments",arr (fun n->N n) rs;"selected",N n;"declarations",recursive d]
| CoFix (n,d) -> node "CoFix" ["selected",N n;"declarations",recursive d]
| Proj (p,r,v) -> node "Proj" ["projection",projection p;"relevance",relevance r;"value",term v]
| Int n -> node "Int" ["unsigned_decimal",S (Uint63.to_string n)]
| Float f -> node "Float" ["exact_hex_or_nan",S (Float64.to_hex_string f)]
| String s -> node "String" ["bytes_hex",S (String.concat "" (List.init (String.length (Pstring.to_string s)) (fun i -> Printf.sprintf "%02x" (Char.code (Pstring.to_string s).[i]))))]
| Array (u,a,d,t) -> node "Array" ["instance",instance u;"values",arr term a;"default",term d;"type",term t]
and recursive (ns,ts,bs) = O ["binders",arr binder ns;"types",arr term ts;"bodies",arr term bs]
let constraints c = let qs,us = PConstraints.elements c in O [
  "qualities",lst (fun (a,Sorts.ElimConstraint.ElimTo,b) -> O ["left",quality a;"kind",S "ElimTo";"right",quality b]) qs;
  "universes",lst (fun (a,k,b) -> O ["left",level a;"kind",S (match k with Univ.UnivConstraint.Lt->"Lt"|Le->"Le"|Eq->"Eq");"right",level b]) us]
let abstract_context c = let names = UVars.AbstractContext.names c in O ["quality_names",arr name names.quals;"universe_names",arr name names.univs;"instance",instance (UVars.make_abstract_instance c);"constraints",constraints (UVars.AbstractContext.constraints c)]
let universes = function Monomorphic -> node "Monomorphic" [] | Polymorphic c -> node "Polymorphic" ["context",abstract_context c]
let named_decl d = let a,v,t = Context.Named.Declaration.to_tuple d in O ["id",id (Context.binder_name a);"relevance",relevance (Context.binder_relevance a);"value",opt term v;"type",term t]
let rel_decl d = let a,v,t = Context.Rel.Declaration.to_tuple d in O ["binder",binder a;"value",opt term v;"type",term t]
let body_kind = function Undef _ -> "Undef" | Def _ -> "Def" | OpaqueDef _ -> "OpaqueDef" | Primitive _ -> "Primitive" | Symbol _ -> "Symbol"
let constant_type c = O ["type",term c.const_type;"relevance",relevance c.const_relevance;"universes",universes c.const_universes;"section_universes",instance c.const_univ_hyps;"section_context_innermost_first",lst named_decl c.const_hyps;"body_kind",S (body_kind c.const_body)]
let inductive_type i = O ["name",id i.mind_typename;"type",term i.mind_user_arity;"arity_context_innermost_first",lst rel_decl i.mind_arity_ctxt;"sort",sort i.mind_sort;"relevance",relevance i.mind_relevance;"constructors",arr (fun (n,t) -> O ["name",id n;"type",term t]) (Array.mapi (fun n t -> i.mind_consnames.(n),t) i.mind_user_lc)]
let rec signature context p = function
| MoreFunctor (x,ty,rest) -> node "MoreFunctor" ["context",S context;"parameter_identifier",mbid x;"parameter",signature "interface-functor-parameter" (ModPath.MPbound x) (mod_type ty);"result",signature "interface-functor-result" p rest]
| NoFunctor fields -> node "NoFunctor" ["context",S context;"path",path p;"field_count",N (List.length fields);"fields",lst (fun (label,f) -> let p' = ModPath.MPdot (p,label) in O ["label",id label;"path",path p';"field",field context p p' f]) fields]
and field context parent p = function
| SFBconst c -> node "SFBconst" ["metadata",constant_type c]
| SFBmind m -> node "SFBmind" ["universes",universes m.mind_universes;"section_universes",instance m.mind_univ_hyps;"section_context_innermost_first",lst named_decl m.mind_hyps;"parameter_context_innermost_first",lst rel_decl m.mind_params_ctxt;"packets",arr inductive_type m.mind_packets]
| SFBmodule m -> module_body context p m
| SFBmodtype m -> node "SFBmodtype" ["signature",signature "interface-module-type" p (mod_type m)]
| SFBrules _ -> CErrors.user_err (Pp.str ("VOS census unsupported native rewrite field " ^ ModPath.to_string p))
and module_body context p m =
  let kind = match mod_expr m with Abstract->"Abstract" | Algebraic _->"Algebraic" | Struct _->"Struct" | FullStruct->"FullStruct" in
  node "SFBmodule" ["implementation_kind",S kind;"implementation_connection",S "unqualified";"signature",signature context p (mod_type m)]
let metadata_inspect () =
  let targets = String.split_on_char ',' (Sys.getenv "VOS_CENSUS_TARGETS") in
  let roots = List.map (fun target ->
    let p = Nametab.locate_module (Libnames.qualid_of_string target) in
    O ["requested",S target;"native_path",path p;"module",module_body "concrete-unqualified" p (Global.lookup_module p)]) targets in
  let output = O ["schema",S "verifiedos-rocq-native-metadata/1";"producer",S "rocq-9.3.0-constructor-api";"acceptance",S "metadata-only";"roots",A roots] in
  Feedback.msg_notice (Pp.str (encode output))


(* Census v1 is deliberately separate from the preserved metadata-only entry. *)
let refuse s = CErrors.user_err (Pp.str ("VOS census refused: " ^ s))
let stable kind xs = kind ^ ":" ^ Digest.to_hex (Digest.string (encode (A xs)))
let get k = function O xs -> (try List.assoc k xs with Not_found -> refuse ("missing " ^ k)) | _ -> refuse "expected object"
let string = function S s -> s | _ -> refuse "expected string"
let as_list = function A xs -> xs | _ -> refuse "expected array"
let fields_rev = ref [] and modules_rev = ref [] and declarations_rev = ref [] and contexts_rev = ref []
let abbreviations_rev = ref []
let resolver_values = ref []
let register_resolver owner role root resolver =
  let key = stable "resolver" [S owner;S role;path root] in
  if not (List.exists (fun (k,_,_,_,_) -> k=key) !resolver_values) then
    resolver_values := (key,owner,role,root,resolver)::!resolver_values;
  key
let projection_repr p = projection (Projection.make p false)
let typing_flags f =
  let strategies = Conv_oracle.fold_strategy (fun r strategy acc ->
    let kind,v,c,p = match r with
    | Conv_oracle.EvalVarRef x -> "variable",id x,Null,Null
    | Conv_oracle.EvalConstRef c -> "constant",Null,constant c,Null
    | Conv_oracle.EvalProjectionRef p -> "projection",Null,Null,projection_repr p in
    let strategy = match strategy with Conv_oracle.Expand->node "Expand" [] | Level n->node "Level" ["level",N n] | Opaque->node "Opaque" [] in
    O ["kind",S kind;"variable",v;"constant",c;"projection",p;"strategy",strategy]::acc) f.conv_oracle [] in
  O ["check_guarded",B f.check_guarded;"check_positive",B f.check_positive;
     "check_universes",B f.check_universes;"check_eliminations",B f.check_eliminations;
     "share_reduction",B f.share_reduction;"unfold_dep_heuristic",B f.unfold_dep_heuristic;
     "enable_VM",B f.enable_VM;"enable_native_compiler",B f.enable_native_compiler;
     "indices_matter",B f.indices_matter;"impredicative_set",B f.impredicative_set;
     "sprop_allowed",B f.sprop_allowed;"allow_uip",B f.allow_uip;
     "conversion_oracle",A (List.sort (fun a b->String.compare (encode a) (encode b)) strategies)]
let body_identity t =
  let previous_paths= !module_domain and previous_names= !kernel_domain in
  module_domain:=ModPath.Set.empty;kernel_domain:=KerName.Set.empty;
  let restore () =
    module_domain:=ModPath.Set.union previous_paths !module_domain;
    kernel_domain:=KerName.Set.union previous_names !kernel_domain in
  try
    let encoded=encode(term t) in
    let paths=ModPath.Set.elements !module_domain and names=KerName.Set.elements !kernel_domain in
    restore();
    O["encoding",S "verifiedos-rocq-native-term-json/1";"algorithm",S "blake2b-256";
      "digest",S(Digest.BLAKE256.to_hex(Digest.BLAKE256.string encoded));
      "module_paths",lst path paths;"kernel_names",lst kernel_name names]
  with error->restore();raise error
let full_constant c =
  let body,inline,primitive = match c.const_body with
  | Undef n -> Null,opt (fun n->N n) n,Null
  | Def t -> body_identity t,Null,Null
  | OpaqueDef _ -> Null,Null,Null
  | Primitive p -> Null,Null,S (CPrimitives.to_string p)
  | Symbol _ -> refuse "unsupported native symbol" in
  let original = match constant_type c with O xs -> xs | _ -> refuse "internal constant metadata shape" in
  O (("kind",S "constant")::("transparent_body",Null)::("transparent_body_identity",body)::("inline_level",inline)::
     ("primitive",primitive)::("inline_code",B c.const_inline_code)::
     ("typing_flags",typing_flags c.const_typing_flags)::original)
let record_info = function
| NotRecord -> node "NotRecord" [] | FakeRecord -> node "FakeRecord" []
| PrimRecord r -> node "PrimRecord" ["id",id r.id;"projections",arr id r.projections;
  "relevances",arr relevance r.relevances;"types",arr term r.tys;
  "has_eta",S (match r.has_eta with AlwaysEta->"AlwaysEta"|MaybeEta->"MaybeEta"|NoEta->"NoEta")]
let full_packet p = O ["name",id p.mind_typename;"type",term p.mind_user_arity;
  "arity_context_innermost_first",lst rel_decl p.mind_arity_ctxt;"sort",sort p.mind_sort;
  "relevance",relevance p.mind_relevance;"record",record_info p.mind_record;
  "squashed",opt (function AlwaysSquashed->node "AlwaysSquashed" [] | SometimesSquashed qs->node "SometimesSquashed" ["qualities",lst quality (Sorts.Quality.Set.elements qs)]) p.mind_squashed;
  "relies_on_indices_not_mattering",B p.mind_relies_on_indices_not_mattering;
  "constructor_count",N (Array.length p.mind_consnames);
  "constructors",arr (fun (n,t,(ctx,conclusion),na,nd)->O ["name",id n;"type",term t;
    "normal_form_context_innermost_first",lst rel_decl ctx;"normal_form_conclusion",term conclusion;
    "real_arguments",N na;"real_declarations",N nd])
    (Array.mapi (fun i n -> n,p.mind_user_lc.(i),p.mind_nf_lc.(i),p.mind_consnrealargs.(i),p.mind_consnrealdecls.(i)) p.mind_consnames)]
let full_inductive m =
  let variance = opt (arr (function UVars.Variance.Irrelevant->S "Irrelevant"|Covariant->S "Covariant"|Invariant->S "Invariant")) in
  O ["kind",S "mutual-inductive";"universes",universes m.mind_universes;
     "section_universes",instance m.mind_univ_hyps;"section_context_innermost_first",lst named_decl m.mind_hyps;
     "parameter_context_innermost_first",lst rel_decl m.mind_params_ctxt;
     "parameter_count",N m.mind_nparams;"uniform_parameter_count",N m.mind_nparams_rec;
     "recursivity",S (match m.mind_finite with Finite->"Finite"|CoFinite->"CoFinite"|BiFinite->"BiFinite");
     "template",opt (fun t->O ["parameter_arguments",lst (opt sort) t.template_param_arguments;
       "conclusion",sort t.template_concl;"context",abstract_context t.template_context;"defaults",instance t.template_defaults]) m.mind_template;
     "variance",variance m.mind_variance;"section_variance",variance m.mind_sec_variance;
     "private",opt (fun b->B b) m.mind_private;"typing_flags",typing_flags m.mind_typing_flags;
     "packet_count",N (Array.length m.mind_packets);"packets",arr full_packet m.mind_packets]
let metadata = function SFBconst c->full_constant c | SFBmind m->full_inductive m | _->refuse "non-object implementation field"
let field_kind = function SFBconst _->"constant"|SFBmind _->"mutual-inductive"|SFBmodule _->"module"|SFBmodtype _->"module-type"|SFBrules _->refuse "unsupported native rewrite field"
let field_namespace = function SFBmodule _|SFBmodtype _->"module"|_->"object"
let rec expression = function
| MENoFunctor e -> node "MENoFunctor" ["body",algebraic e]
| MEMoreFunctor e -> node "MEMoreFunctor" ["body",expression e]
and algebraic = function
| MEident p -> node "MEident" ["path",path p]
| MEapply (f,a) -> node "MEapply" ["function",algebraic f;"argument",path a]
| MEwith (e,WithMod (ls,p)) -> node "MEwithModule" ["base",algebraic e;"labels",lst id ls;"module",path p]
| MEwith (e,WithDef (ls,(t,c))) -> node "MEwithDefinition" ["base",algebraic e;"labels",lst id ls;"term",term t;"context",opt abstract_context c]
let rec implementation owner p m =
  let delta = register_resolver owner "signature" p (mod_delta m) in
  let kind,expr,structure = match mod_expr m with
  | Abstract -> "Abstract",Null,Null | FullStruct -> "FullStruct",Null,Null
  | Algebraic e -> "Algebraic",expression e,Null
  | Struct (r,fs) -> ignore (register_resolver owner "implementation" p r); "Struct",Null,raw_structure owner p fs in
  O ["kind",S kind;"expression",expr;"algebraic_type",opt expression (mod_type_alg m);"structure",structure;"resolver_id",S delta]
and raw_structure owner p fs = O ["path",path p;"field_count",N (List.length fs);"fields",
  lst (fun (label,f)-> O ["label",id label;"namespace",S (field_namespace f);"kind",S (field_kind f);
    "metadata",(match f with SFBconst _|SFBmind _->metadata f|_->Null);
    "module",(let child=ModPath.MPdot(p,label) in match f with
      | SFBmodule m->raw_module owner child m | SFBmodtype m->raw_modtype owner child m | _->Null)]) fs]
and raw_signature owner p = function
| MoreFunctor(x,ty,rest)->node "MoreFunctor" ["parameter_identifier",mbid x;
  "parameter",raw_modtype owner (ModPath.MPbound x) ty;"result",raw_signature owner p rest]
| NoFunctor fs->node "NoFunctor" ["structure",raw_structure owner p fs]
and raw_module owner p m = O ["path",path p;"kind",S "module";
  "signature",raw_signature owner p (mod_type m);"implementation",implementation owner p m]
and raw_modtype owner p m = O ["path",path p;"kind",S "module-type";
  "signature",raw_signature owner p (mod_type m);"implementation",type_implementation owner p m]
and type_implementation owner p m = O ["kind",S "NotApplicable";"expression",Null;
  "algebraic_type",opt expression (mod_type_alg m);"structure",Null;
  "resolver_id",S (register_resolver owner "signature" p (mod_delta m))]

(* Original implementation evaluation. Expressions are evaluated against actual
   native module bodies; native substitutions, not rendered terms, do the work. *)
type expansion = { origin:ModPath.t; original:structure_body; instantiated:structure_body;
                   trace:json list; substitution:Mod_subst.substitution }
let expansion_cache = ref []
let lookup_field namespace label fs =
  match List.filter (fun (l,f)->Id.equal l label && field_namespace f=namespace) fs with
  | [(_,f)]->f | []->refuse ("missing implementation field " ^ Id.to_string label)
  | _->refuse ("ambiguous implementation field " ^ Id.to_string label)
let locator p label packet ctor = O ["module_path",path p;"namespace",S "object";
  "label",id label;"packet_index",opt (fun n->N n) packet;"constructor_index",opt (fun n->N n) ctor]
let rec implementation_module owner visiting p = match p with
| ModPath.MPfile _|ModPath.MPbound _ -> Global.lookup_module p
| ModPath.MPdot (parent,label) ->
  let e = expand owner visiting parent in
  (match lookup_field "module" label e.instantiated with SFBmodule m->m|_->refuse "implementation is a module type")
and expand owner visiting p =
  let key=owner ^ ":" ^ ModPath.to_string p in
  match List.assoc_opt key !expansion_cache with
  | Some e -> e
  | None ->
    if ModPath.Set.mem p visiting then refuse ("cyclic implementation " ^ ModPath.to_string p);
    let visiting=ModPath.Set.add p visiting in
    let target=implementation_module owner visiting p in
    let source,raw,subs,trace = evaluate owner visiting p p target [] Mod_subst.empty_subst [] in
    let target_delta=mod_delta target in
    let subs,trace = if ModPath.equal source p then subs,trace else
      let rid=register_resolver owner "substitution" p target_delta in
      let rebase=Mod_subst.map_mp source p target_delta in
      Mod_subst.join subs rebase,
      trace @ [node "substitution" ["source",locator source (Id.of_string "__module_root") None None;
        "target",locator p (Id.of_string "__module_root") None None;"resolver_id",S rid]] in
    let instantiated=Modops.subst_structure subs p raw in
    let e={origin=source;original=raw;instantiated;trace;substitution=subs} in
    expansion_cache:=(key,e)::!expansion_cache;e
and evaluate owner visiting destination source m arguments subs trace =
  let bind action signature arguments subs trace =
    let rec loop prefix signature arguments subs trace = match signature,arguments with
    | MoreFunctor(x,_,rest),argument::tail ->
      let argument=Mod_subst.subst_mp subs argument in
      let argmod=implementation_module owner visiting argument in
      let delta=mod_delta argmod in
      let rid=register_resolver owner "application-argument" argument delta in
      let subs=Mod_subst.join (Mod_subst.map_mbid x argument delta) subs in
      let prefix=node "MEapply" ["function",prefix;"argument",path argument] in
      let step=node "functor-application" ["parameter_identifier",mbid x;"argument",path argument;
        "expression",prefix;"resolver_id",S rid] in
      loop prefix rest tail subs (trace@[step])
    | MoreFunctor _,[] -> refuse "unapplied functor used as concrete implementation"
    | NoFunctor body,[] -> action body subs trace
    | NoFunctor _,_::_ -> refuse "excess implementation functor arguments" in
    loop (node "MEident" ["path",path source]) signature arguments subs trace in
  match mod_expr m with
  | Abstract -> refuse "concrete module has Abstract implementation"
  | FullStruct -> bind (fun fs subs trace ->
      let rid=register_resolver owner "implementation" source (mod_delta m) in
      source,fs,subs,trace@[node "structure-field" ["field",locator source (Id.of_string "__module_root") None None;"implementation_kind",S "FullStruct";"resolver_id",S rid]])
      (mod_type m) arguments subs trace
  | Struct(delta,body) -> bind (fun fs subs trace ->
      let rid=register_resolver owner "implementation" source delta in
      source,fs,subs,trace@[node "structure-field" ["field",locator source (Id.of_string "__module_root") None None;"implementation_kind",S "Struct";"resolver_id",S rid]])
      (Modops.annotate_struct_body body (mod_type m)) arguments subs trace
  | Algebraic expr -> bind (fun alg subs trace ->
      let rec follow args = function
      | MEapply(fn,arg)->follow (Mod_subst.subst_mp subs arg::args) fn
      | MEident referenced ->
        let referenced=Mod_subst.subst_mp subs referenced in
        if ModPath.Set.mem referenced visiting || ModPath.equal referenced source then refuse "cyclic algebraic implementation";
        let visiting=ModPath.Set.add referenced visiting in
        let rid=register_resolver owner "implementation" source (mod_delta m) in
        let trace=trace@[node "module-alias" ["source",path source;"target",path referenced;
          "expression",algebraic alg;"resolver_id",S rid]] in
        let referenced_module=implementation_module owner visiting referenced in
        evaluate owner visiting destination referenced referenced_module args subs trace
      | MEwith _ -> refuse "module implementation contains unsupported with refinement" in
      follow [] alg) (Modops.annotate_module_expression expr (mod_type m)) arguments subs trace

let native_reference = function
| GlobRef.VarRef _ -> refuse "section variable is not a closed declaration"
| GlobRef.ConstRef c -> O ["kind",S "constant";"exported_name",S (Constant.to_string c);
  "canonical_name",S (KerName.to_string (Constant.canonical c));"user",kernel_name (Constant.user c);
  "canonical",kernel_name (Constant.canonical c);"packet_index",Null;"constructor_index",Null]
| GlobRef.IndRef (m,i) -> O ["kind",S "inductive";"exported_name",S (KerName.to_string (MutInd.user m));
  "canonical_name",S (KerName.to_string (MutInd.canonical m));
  "user",kernel_name (MutInd.user m);"canonical",kernel_name (MutInd.canonical m);
  "packet_index",N i;"constructor_index",Null]
| GlobRef.ConstructRef ((m,i),k) -> O ["kind",S "constructor";"exported_name",S (KerName.to_string (MutInd.user m));
  "canonical_name",S (KerName.to_string (MutInd.canonical m));
  "user",kernel_name (MutInd.user m);"canonical",kernel_name (MutInd.canonical m);
  "packet_index",N i;"constructor_index",N k]
let reference_at delta p label packet ctor =
  let kn=KerName.make p label in
  match packet,ctor with
  | None,None->GlobRef.ConstRef (Mod_subst.constant_of_delta_kn delta kn)
  | Some i,None->GlobRef.IndRef (Mod_subst.mind_of_delta_kn delta kn,i)
  | Some i,Some k->GlobRef.ConstructRef ((Mod_subst.mind_of_delta_kn delta kn,i),k)
  | None,Some _->refuse "constructor without inductive packet"
let actual_reference p label packet ctor =
  let kn=KerName.make p label in
  let env=Global.env() in
  match packet,ctor with
  | None,None ->
    let proposed=Constant.make1 kn in
    if not (Environ.mem_constant proposed env) then refuse ("missing concrete global " ^ KerName.to_string kn);
    GlobRef.ConstRef (Constant.make kn (Environ.lookup_constant_canonical proposed env))
  | Some i,k ->
    let proposed=MutInd.make1 kn in
    if not (Environ.mem_mind proposed env) then refuse ("missing concrete inductive " ^ KerName.to_string kn);
    let m=MutInd.make kn (Environ.lookup_mind_canonical proposed env) in
    (match k with None->GlobRef.IndRef(m,i)|Some k->GlobRef.ConstructRef((m,i),k))
  | None,Some _->refuse "constructor without inductive packet"

let json_parse source =
  let n=String.length source and pos=ref 0 in
  let rec spaces () = while !pos<n && List.mem source.[!pos] [' ';'\t';'\r';'\n'] do incr pos done
  and expect c = spaces(); if !pos>=n || source.[!pos]<>c then refuse "invalid resolution-request JSON";incr pos
  and quoted () =
    expect '"';let b=Buffer.create 32 in
    let hex () = if !pos+4>n then refuse "short JSON unicode escape";
      let h=String.sub source !pos 4 in pos:= !pos+4;
      try int_of_string ("0x"^h) with Failure _->refuse "invalid JSON unicode escape" in
    let rec loop () = if !pos>=n then refuse "unterminated JSON string";
      let c=source.[!pos] in incr pos; match c with
      | '"' -> Buffer.contents b
      | '\\' -> if !pos>=n then refuse "short JSON escape";
        let c=source.[!pos] in incr pos;
        (match c with
         | '"'|'\\'|'/'->Buffer.add_char b c | 'b'->Buffer.add_char b '\b'
         | 'f'->Buffer.add_char b '\012' | 'n'->Buffer.add_char b '\n'
         | 'r'->Buffer.add_char b '\r' | 't'->Buffer.add_char b '\t'
         | 'u'->let first=hex() in
           let value=if first>=0xd800 && first<=0xdbff then (
             if !pos+2>n || String.sub source !pos 2<>"\\u" then refuse "missing JSON low surrogate";
             pos:= !pos+2;let second=hex() in
             if second<0xdc00 || second>0xdfff then refuse "invalid JSON low surrogate";
             0x10000+((first-0xd800) lsl 10)+(second-0xdc00)) else first in
           if not (Uchar.is_valid value) then refuse "invalid JSON scalar";
           Buffer.add_utf_8_uchar b (Uchar.of_int value)
         | _->refuse "invalid JSON escape");loop()
      | c when Char.code c<32->refuse "control byte in JSON string"
      | c->Buffer.add_char b c;loop() in loop()
  and value () = spaces();if !pos>=n then refuse "missing JSON value";
    match source.[!pos] with
    | '"'->S(quoted())
    | '['->incr pos;spaces();if !pos<n && source.[!pos]=']' then (incr pos;A []) else
      let rec loop acc = let v=value() in spaces();if !pos>=n then refuse "unterminated JSON array";
        let c=source.[!pos] in incr pos;if c=']' then A(List.rev(v::acc)) else if c=',' then loop(v::acc) else refuse "invalid JSON array" in loop []
    | '{'->incr pos;spaces();if !pos<n && source.[!pos]='}' then (incr pos;O []) else
      let rec loop acc = let k=quoted() in if List.mem_assoc k acc then refuse "duplicate JSON key";
        expect ':';let v=value() in spaces();if !pos>=n then refuse "unterminated JSON object";
        let c=source.[!pos] in incr pos;if c='}' then O(List.rev((k,v)::acc)) else if c=',' then loop((k,v)::acc) else refuse "invalid JSON object" in loop []
    | '0'..'9'->let start= !pos in while !pos<n && source.[!pos]>='0' && source.[!pos]<='9' do incr pos done;
      let t=String.sub source start (!pos-start) in if String.length t>1 && t.[0]='0' then refuse "JSON leading zero";
      (try N(int_of_string t) with Failure _->refuse "JSON integer overflow")
    | _->refuse "unsupported resolution-request JSON value" in
  let v=value() in spaces();if !pos<>n then refuse "trailing JSON input";v

let native_global_name reference =
  try Libnames.string_of_path (Nametab.path_of_global reference)
  with Not_found -> Pp.string_of_ppcmds (Printer.pr_global reference)
let native_reference_raw = native_reference
let native_reference reference =
  let canonical=match reference with
  | GlobRef.ConstRef c->GlobRef.ConstRef(Constant.make1(Constant.canonical c))
  | GlobRef.IndRef(m,i)->GlobRef.IndRef(MutInd.make1(MutInd.canonical m),i)
  | GlobRef.ConstructRef((m,i),k)->GlobRef.ConstructRef((MutInd.make1(MutInd.canonical m),i),k)
  | GlobRef.VarRef _->refuse "section variable reference" in
  let original=match native_reference_raw reference with O xs->xs|_->assert false in
  O(List.map (fun (k,v)->if k="exported_name" then k,S(native_global_name reference)
      else if k="canonical_name" then k,S(native_global_name canonical) else k,v) original)
let context parent kind p parameter signature =
  let identifier=stable "context" [opt (fun s->S s) parent;S kind;path p;opt mbid parameter] in
  if not (List.exists(fun c->get "id" c=S identifier) !contexts_rev) then
    contexts_rev:=O["id",S identifier;"parent_id",opt(fun s->S s)parent;"kind",S kind;
      "owner_path",path p;"parameter_identifier",opt mbid parameter;
      "parameter_signature_module_id",opt(fun s->S s)signature]::!contexts_rev;
  identifier
let is_alias reference = match reference with
| GlobRef.ConstRef c->not(KerName.equal (Constant.user c)(Constant.canonical c))
| GlobRef.IndRef(m,_)|GlobRef.ConstructRef((m,_),_)->not(KerName.equal(MutInd.user m)(MutInd.canonical m))
| GlobRef.VarRef _->false
let complete_trace source destination label packet ctor steps =
  List.map(function
  | O (("tag",S "structure-field")::xs)->O(("tag",S "structure-field")::List.map(fun(k,v)->if k="field" then k,locator source label packet ctor else k,v)xs)
  | O (("tag",S "substitution")::xs)->O(("tag",S "substitution")::List.map(fun(k,v)->if k="source" then k,locator source label packet ctor else if k="target" then k,locator destination label packet ctor else k,v)xs)
  | step->step) steps
let module_query root target kind = O["owner_root_id",S root;"kind",S kind;"target",S target;
  "target_module_id",S root;"coverage_path",A []]
let extend_query query step =
  match query with O xs->O(List.map(fun(k,v)->if k="coverage_path" then k,A(as_list v@[step]) else k,v)xs)|_->assert false
let declare_object owner ctx abstract p label f =
  let fid=stable "field"[S owner;S "object";id label] in
  let expansion=if abstract then None else Some(expand owner ModPath.Set.empty p) in
  let declarations=match f with
  | SFBconst c->["constant",label,None,None,c.const_type]
  | SFBmind m->Array.to_list(Array.mapi(fun i packet->
      ("inductive",packet.mind_typename,Some i,None,packet.mind_user_arity)::
      Array.to_list(Array.mapi(fun k name->"constructor",name,Some i,Some(k+1),packet.mind_user_lc.(k))packet.mind_consnames))m.mind_packets)|>List.flatten
  | _->refuse "object population contains non-object" in
  let classification=ref None in
  let ids=List.map(fun(kind,name,packet,ctor,ty)->
    let did=stable "declaration"[S fid;S kind;opt(fun n->N n)packet;opt(fun n->N n)ctor] in
    let reference=if abstract then None else Some(actual_reference p label packet ctor) in
    let cls=match reference with None->"interface"|Some r when is_alias r->"alias"|Some _->"owned" in
    (match !classification with None->classification:=Some cls|Some x when x=cls->()|_->refuse "inconsistent mutual-inductive ownership");
    let refjson=opt native_reference reference in
    let exported=match reference with Some r->native_global_name r|None->ModPath.to_string p^"."^Id.to_string name in
    let connection,alias=match reference,expansion with
    | Some r,Some e->
      let original=lookup_field "object" label e.original and instantiated=lookup_field "object" label e.instantiated in
      let source_delta=mod_delta(implementation_module owner ModPath.Set.empty e.origin) in
      let source_ref=reference_at source_delta e.origin label packet ctor in
      let instantiated_ref=Globnames.subst_global_reference e.substitution source_ref in
      let rid=register_resolver owner "signature" p (mod_delta(implementation_module owner ModPath.Set.empty p)) in
      let direct=node "direct-lookup"["reference",native_reference r;"lookup_succeeded",B true] in
      let connection=O["lookup_succeeded",B true;"exported_reference",native_reference r;
        "source_field",locator e.origin label packet ctor;"instantiated_field",locator p label packet ctor;
        "source_reference",native_reference source_ref;"implementation_reference",native_reference instantiated_ref;
        "source_metadata",metadata original;"instantiated_metadata",metadata instantiated;
        "steps",A(complete_trace e.origin p label packet ctor e.trace@[direct]);
        "audit_query_name",get "canonical_name"(native_reference r)] in
      let alias=if cls="alias" then O["kind",S "declaration-alias";"exported_reference",native_reference r;
        "target_reference",native_reference instantiated_ref;"resolver_id",S rid] else Null in connection,alias
    | None,None->Null,Null | _->assert false in
    declarations_rev:=O["id",S did;"field_id",S fid;"namespace",S "object";"kind",S kind;"label",id name;
      "packet_index",opt(fun n->N n)packet;"constructor_index",opt(fun n->N n)ctor;
      "classification",S cls;"context_id",S ctx;"exported_name",S exported;
      "native_reference",refjson;"type",term ty;"implementation_connection",connection;"alias",alias]::!declarations_rev;
    did)declarations in
  let cls=match !classification with Some x->x|None->refuse "empty mutual inductive" in
  fields_rev:=O["id",S fid;"parent_module_id",S owner;"namespace",S "object";"label",id label;
    "kind",S(field_kind f);"context_id",S ctx;"classification",S cls;"metadata",metadata f;
    "child_module_id",Null;"declaration_ids",lst(fun s->S s)ids]::!fields_rev;
  fid

let rec visit_module root query parent kind ctx abstract p signature impl_builder =
  let mid=stable "module"[path p;S ctx;S kind] in
  let query=match parent with
  | None when kind<>"functor-parameter-signature" -> O["owner_root_id",S root;"kind",S(if kind="module-type" then "module-type" else "module");
      "target",S(ModPath.to_string p);"target_module_id",S mid;"coverage_path",A []]
  | _->query in
  let rec parameters previous query params = function
  | MoreFunctor(x,ty,rest)->
    let bound=ModPath.MPbound x in
    let pc=context(Some previous)"functor-parameter" bound (Some x) None in
    let pq=extend_query query (node "functor-parameter"["identifier",mbid x]) in
    let sid=visit_module root pq None "functor-parameter-signature" pc true bound (mod_type ty)
      (fun owner->type_implementation owner bound ty) in
    contexts_rev:=List.map(function O xs as record->if get "id" record=S pc then
      O(List.map(fun(k,v)->if k="parameter_signature_module_id" then k,S sid else k,v)xs) else record|_->assert false)!contexts_rev;
    let query=extend_query query(node "functor-result"["identifier",mbid x]) in
    parameters pc query (params@[O["identifier",mbid x;"context_id",S pc;"signature_module_id",S sid]]) rest
  | NoFunctor fs->
    let result=if params=[] then ctx else context(Some previous)"functor-result" p None None in
    params,result,query,fs in
  let params,result_ctx,body_query,fs=parameters ctx query [] signature in
  let abstract=abstract || params<>[] in
  let seen=Hashtbl.create 32 in
  let fids=List.map(fun(label,f)->
    let ns=field_namespace f in
    let duplicate=ns^":"^Id.to_string label in
    if Hashtbl.mem seen duplicate then refuse("duplicate native field "^duplicate);
    Hashtbl.add seen duplicate();
    match f with
    | SFBconst _|SFBmind _->declare_object mid result_ctx abstract p label f
    | SFBrules _->refuse "unsupported native rewrite field"
    | SFBmodule m->
      let fid=stable "field"[S mid;S ns;id label] and child=ModPath.MPdot(p,label) in
      let cc=context(Some result_ctx)"concrete-module" child None None in
      let cq=if abstract then extend_query body_query(node "field"["namespace",S ns;"label",id label])
        else O["owner_root_id",S root;"kind",S "module";"target",S(ModPath.to_string child);
          "target_module_id",S(stable "module"[path child;S cc;S "module"]);"coverage_path",A []] in
      let childid=visit_module root cq (Some fid) "module" cc abstract child (mod_type m)(fun owner->implementation owner child m) in
      fields_rev:=O["id",S fid;"parent_module_id",S mid;"namespace",S ns;"label",id label;"kind",S "module";
        "context_id",S result_ctx;"classification",S(if abstract then "interface" else "owned");"metadata",Null;
        "child_module_id",S childid;"declaration_ids",A []]::!fields_rev;fid
    | SFBmodtype m->
      let fid=stable "field"[S mid;S ns;id label] and child=ModPath.MPdot(p,label) in
      let cc=context(Some result_ctx)"module-type" child None None in
      let cq=if abstract then extend_query body_query(node "field"["namespace",S ns;"label",id label])
        else O["owner_root_id",S root;"kind",S "module-type";"target",S(ModPath.to_string child);
          "target_module_id",S(stable "module"[path child;S cc;S "module-type"]);"coverage_path",A []] in
      let childid=visit_module root cq (Some fid) "module-type" cc true child (mod_type m)(fun owner->type_implementation owner child m) in
      fields_rev:=O["id",S fid;"parent_module_id",S mid;"namespace",S ns;"label",id label;"kind",S "module-type";
        "context_id",S result_ctx;"classification",S "interface";"metadata",Null;
        "child_module_id",S childid;"declaration_ids",A []]::!fields_rev;fid)fs in
  let impl=impl_builder mid in
  if not abstract && get "kind" impl=S "Abstract" then refuse "concrete module has Abstract implementation";
  modules_rev:=O["id",S mid;"parent_field_id",opt(fun x->S x)parent;"kind",S kind;
    "native_path",path p;"context_id",S ctx;"query",query;
    "signature",O["parameters",A params;"result_context_id",S result_ctx;"field_count",N(List.length fs);"field_ids",lst(fun s->S s)fids];
    "implementation",impl;"abbreviation_ids",A [];"empty_evidence",S(if fs=[] then "native-empty" else "nonempty")]::!modules_rev;
  mid

let enumerate_abbreviations () =
  let entries=Abbreviation.fold(fun key data acc->(key,data)::acc)[] in
  let entries=List.sort(fun(_,a)(_,b)->Libnames.compare_full_path(Abbreviation.full_path a)(Abbreviation.full_path b))entries in
  List.iter(fun(key,data)->
    let full=Abbreviation.full_path data in
    let native_owner=KerName.modpath key in
    let owners=List.filter(fun m->get "native_path" m=path native_owner)!modules_rev in
    match owners with
    | []->()
    | [owner]->
      let mid=string(get "id" owner) in
      let variables,notation=Abbreviation.interp data in
      let target=match variables,notation with
      | [],Notation_term.NRef(reference,None)->reference
      | _->refuse("unsupported owned abbreviation "^Libnames.string_of_path full) in
      let aid=stable "abbreviation"[S mid;S(Libnames.string_of_path full);kernel_name key] in
      abbreviations_rev:=O["id",S aid;"module_id",S mid;"exported_name",S(Libnames.string_of_path full);
        "native_abbreviation_path",S(KerName.to_string key);"enabled",B(Abbreviation.enabled data);
        "only_parsing",B(Abbreviation.only_parsing data);"interpretation",O["kind",S "direct-reference";
          "bound_variables",A [];"target_reference",native_reference target]]::!abbreviations_rev;
      modules_rev:=List.map(function O xs as m->if get "id" m=S mid then O(List.map(fun(k,v)->
        if k="abbreviation_ids" then k,A(as_list v@[S aid])
        else if k="empty_evidence" && get "field_count"(get "signature" m)=N 0 then k,S "native-alias-only" else k,v)xs)else m|_->assert false)!modules_rev
    | _->refuse "ambiguous abbreviation owner")entries

let environment () =
  let env=Global.env() in
  let graph=Environ.universes env in
  let universe_nodes=Univ.Level.Map.bindings(UGraph.repr graph)|>List.map(fun(l,n)->
    O["level",level l;"node",(match n with UGraph.Alias target->node "Alias"["target",level target]
      | Node successors->node "Node"["successors",lst(fun(l,strict)->O["level",level l;"strict",B strict])(Univ.Level.Map.bindings successors)])]) in
  let qualities=Environ.qualities env in
  let domain=QGraph.domain qualities in
  O["universe_graph",O["type_in_type",B(UGraph.type_in_type graph);"nodes",A universe_nodes];
    "quality_graph",O["ignore_constraints",B(QGraph.ignore_constraints qualities);"domain",lst quality(Sorts.Quality.Set.elements domain);
      "constraints",constraints(PConstraints.of_qualities(QGraph.constraints_for ~kept:domain qualities))];
    "typing_flags",typing_flags(Environ.typing_flags env)]
let export_resolvers () =
  List.iter(fun(_,_,_,_,r)->List.iter(fun(_,kn)->ignore(kernel_name kn))(Mod_subst.inline_of_delta None r))!resolver_values;
  let paths=ModPath.Set.elements !module_domain and names=KerName.Set.elements !kernel_domain in
  List.rev !resolver_values|>List.map(fun(key,owner,role,root,r)->O["id",S key;"owner_module_id",S owner;
    "role",S role;"coverage",S "finite-enumerated-domain";"root",path root;
    "module_effects",lst(fun p->O["input",path p;"output",path(Mod_subst.mp_of_delta r p);"is_alias",B(Mod_subst.mp_is_alias r p)])paths;
    "kernel_effects",lst(fun kn->O["input",kernel_name kn;"output",kernel_name(Mod_subst.kn_of_delta r kn)])names;
    "inline_keys",lst(fun(level,kn)->O["level",N level;"key",kernel_name kn])(Mod_subst.inline_of_delta None r)])
let resolve_requests roots requests =
  let seen=Hashtbl.create 32 in
  List.map(fun request->
    let rid=string(get "id" request) and requested=string(get "requested_root" request) and spelling=string(get "spelling" request) in
    let row=match get "row_index" request with N n when n>=0->n|_->refuse "invalid request row index" in
    if rid<>requested^":"^string_of_int row || Hashtbl.mem seen rid then refuse "invalid or duplicate resolution request id";
    Hashtbl.add seen rid();
    let root=match List.filter(fun root->get "requested" root=S requested)roots with [root]->root|_->refuse "foreign requested resolution root" in
    let q=Libnames.qualid_of_string spelling in
    let resolved=Nametab.locate_extended_all q in
    let candidate=match resolved with
    | [Globnames.TrueGlobal reference]->
      let refjson=native_reference reference in
      let matches=List.filter(fun d->get "native_reference" d=refjson)!declarations_rev in
      (match matches with
      | [d]->O["declaration_id",get "id" d;"abbreviation_id",Null;"reference",refjson;
        "mode",S "global";"field_id",get "field_id" d]
      | []->refuse("foreign or unclassified native row "^spelling)
      | _->refuse("ambiguous native declaration row "^spelling))
    | [Globnames.Abbrev key]->
      let name=KerName.to_string key in
      (match List.filter(fun a->get "native_abbreviation_path" a=S name)!abbreviations_rev with
      | [a]->O["declaration_id",Null;"abbreviation_id",get "id" a;
        "reference",get "target_reference"(get "interpretation" a);"mode",S "abbreviation";"field_id",Null]
      | _->refuse("unclassified native abbreviation "^spelling))
    | []->refuse("missing native resolution "^spelling)
    | _->refuse("ambiguous native resolution "^spelling) in
    O["request_id",S rid;"root_module_id",get "module_id" root;"candidates",A[candidate]])requests
let census_inspect () =
  let targets=String.split_on_char ','(Sys.getenv "VOS_CENSUS_TARGETS") in
  if targets=[] || List.exists((=)"")targets || List.length(List.sort_uniq String.compare targets)<>List.length targets then refuse "empty or duplicate target population";
  let requests=as_list(json_parse(try Sys.getenv "VOS_CENSUS_RESOLVE" with Not_found->"[]")) in
  let roots=List.map(fun target->
    let p=Nametab.locate_module(Libnames.qualid_of_string target) in
    let ctx=context None "concrete-root" p None None in
    let mid=stable "module"[path p;S ctx;S "module"] in
    let query=module_query mid target "module" in
    let actual=visit_module mid query None "module" ctx false p (mod_type(Global.lookup_module p))
      (fun owner->implementation owner p(Global.lookup_module p)) in
    O["requested",S target;"native_path",path p;"module_id",S actual])targets in
  enumerate_abbreviations();
  let resolutions=resolve_requests roots requests in
  let environment=environment() in
  let resolvers=export_resolvers() in
  let output=O["schema",S "verifiedos-sail-support-census/1";"producer",S "rocq-9.3.0-constructor-api";
    "requested_roots",lst(fun s->S s)targets;"roots",A roots;"contexts",A(List.rev !contexts_rev);
    "modules",A(List.rev !modules_rev);"fields",A(List.rev !fields_rev);"declarations",A(List.rev !declarations_rev);
    "abbreviations",A(List.rev !abbreviations_rev);"resolvers",A resolvers;"resolution_requests",A requests;
    "resolutions",A resolutions;"environment",environment] in
  Feedback.msg_notice(Pp.str(encode output))
let inspect () = match Sys.getenv_opt "VOS_CENSUS_MODE" with
| None|Some "metadata"->metadata_inspect()
| Some "census"->census_inspect()
| Some _->refuse "unsupported census mode"
let () = Mltop.declare_cache_obj_full (Mltop.interp_only_obj inspect) "vos_rocq_census"
