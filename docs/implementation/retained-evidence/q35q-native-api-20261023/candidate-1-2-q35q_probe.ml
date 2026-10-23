open Names
open Declarations
open Mod_declarations
let emit s = Feedback.msg_notice (Pp.str s)
let term t = Pp.string_of_ppcmds (Constr.debug_print t)
let rec signature context path = function
| MoreFunctor (id,ty,rest) ->
  let bound = ModPath.MPbound id in
  emit ("FUNCTOR_PARAMETER " ^ path ^ " " ^ ModPath.to_string bound);
  signature (context ^ "/parameter") (ModPath.to_string bound) (mod_type ty);
  signature (context ^ "/result") path rest
| NoFunctor fields ->
  emit ("STRUCTURE " ^ context ^ " " ^ path ^ " fields=" ^ string_of_int (List.length fields));
  List.iter (fun (label,field) ->
    let name = path ^ "." ^ Id.to_string label in
    match field with
    | SFBconst c -> emit ("CONSTANT " ^ context ^ " " ^ name ^ " : " ^ term c.const_type)
    | SFBmind m -> Array.iter (fun i ->
      emit ("INDUCTIVE " ^ context ^ " " ^ path ^ "." ^ Id.to_string i.mind_typename ^ " : " ^ term i.mind_user_arity);
      Array.iteri (fun n t -> emit ("CONSTRUCTOR " ^ context ^ " " ^ path ^ "." ^ Id.to_string i.mind_consnames.(n) ^ " : " ^ term t)) i.mind_user_lc) m.mind_packets
    | SFBmodule m -> signature (context ^ "/module") name (mod_type m)
    | SFBmodtype m -> signature (context ^ "/signature") name (mod_type m)
    | SFBrules _ -> CErrors.user_err (Pp.str ("unsupported native rewrite field " ^ name))) fields
let () =
  let targets = String.split_on_char ',' (Sys.getenv "VOS_CENSUS_TARGETS") in
  List.iter (fun target ->
    let path = Nametab.locate_module (Libnames.qualid_of_string target) in
    emit ("ROOT " ^ ModPath.to_string path);
    signature "root" (ModPath.to_string path) (mod_type (Global.lookup_module path))) targets
