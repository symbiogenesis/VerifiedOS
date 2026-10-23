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
let rec path = function
| ModPath.MPfile d -> node "MPfile" ["directory_reversed",dir d]
| ModPath.MPbound x -> node "MPbound" ["identifier",mbid x]
| ModPath.MPdot (p,i) -> node "MPdot" ["parent",path p; "label",id i]
let kernel_name x = let p,i = KerName.repr x in O ["path",path p;"label",id i]
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
let inspect () =
  let targets = String.split_on_char ',' (Sys.getenv "VOS_CENSUS_TARGETS") in
  let roots = List.map (fun target ->
    let p = Nametab.locate_module (Libnames.qualid_of_string target) in
    O ["requested",S target;"native_path",path p;"module",module_body "concrete-unqualified" p (Global.lookup_module p)]) targets in
  let output = O ["schema",S "verifiedos-rocq-native-metadata/1";"producer",S "rocq-9.3.0-constructor-api";"acceptance",S "metadata-only";"roots",A roots] in
  Feedback.msg_notice (Pp.str (encode output))
let () = Mltop.declare_cache_obj_full (Mltop.interp_only_obj inspect) "vos_rocq_census"
