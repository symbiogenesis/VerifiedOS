/* SPDX-License-Identifier: Apache-2.0 */
%{
open Ast
let optional = function None -> Null | Some value -> value.syntax
let children = function None -> [] | Some value -> [value]
let strings values = Array (List.map (fun value -> String value) values)
let const_fields = function None -> [] | Some _ -> [("const", Boolean true)]
let with_declaration_modifiers first last modifiers value =
  match value.syntax with
  | Object fields ->
      let is_const = List.mem "const" modifiers in
      let occurrences = List.length (List.filter ((=) "const") modifiers) in
      let refuse message = raise (Refusal ("syntax", first.Lexing.pos_cnum, message)) in
      if occurrences > 1 then refuse "repeated const declaration modifier";
      let kind = List.assoc "kind" fields in
      if List.mem "async" modifiers && kind = String "property" then
        refuse "expression properties are total and synchronous";
      let kind, fields, modifiers =
        if is_const && kind = String "field" then begin
          if List.assoc "value" fields = Null || List.assoc "grade" fields <> Null then
            refuse "a constant value requires an initializer and has no use grade";
          if List.hd (List.rev modifiers) <> "const" then
            refuse "a constant value places const immediately before its type";
          String "constant", List.remove_assoc "grade" fields,
          List.filter ((<>) "const") modifiers
        end else begin
          if is_const && not (List.mem kind [String "function"; String "definition"]) then
            refuse "const modifies a function or an initialized value";
          kind, fields, modifiers
        end in
      { value with syntax = Object
          (List.map (fun (key, data) ->
             if key = "span" then key, offsets first last
             else if key = "kind" then key, kind else key, data) fields
           @ [("modifiers", strings modifiers)]) }
  | _ -> value
let binary first last operator left right =
  make "binary" first last [("operator", operator); ("left", left.syntax);
                            ("right", right.syntax)] [left; right]
let name_text = function
  | Object fields -> (match List.assoc_opt "text" fields with Some (String text) -> text | _ -> "")
  | _ -> ""
let last_segment text =
  match List.rev (String.split_on_char '.' text) with
  | head :: _ -> head
  | [] -> text
let is_constructor_spelling text =
  let last = last_segment text in
  String.length last > 0 && last.[0] >= 'A' && last.[0] <= 'Z'
let is_binder_spelling text =
  not (String.contains text '.') && String.length text > 0
  && (text.[0] = '_' || (text.[0] >= 'a' && text.[0] <= 'z'))
let build_pattern first last target values =
  let spelling = name_text target in
  match values with
  | None ->
      if spelling = "_" then make "wildcard_pattern" first last [] []
      else if is_constructor_spelling spelling then
        make "constructor_pattern" first last [("name", target); ("arguments", Array [])] []
      else if is_binder_spelling spelling then
        make "binding_pattern" first last [("name", target)] []
      else
        raise (Refusal ("syntax", first.Lexing.pos_cnum,
                        "pattern binder must be an unqualified lowercase or '_' identifier; constructor patterns require an uppercase constructor name"))
  | Some [] ->
      raise (Refusal ("syntax", first.Lexing.pos_cnum,
                      "nullary constructor pattern '" ^ spelling ^ "()' must be written bare without '()' (write '" ^ spelling ^ "')"))
  | Some args ->
      if not (is_constructor_spelling spelling) then
        raise (Refusal ("syntax", first.Lexing.pos_cnum,
                        "constructor pattern '" ^ spelling ^ "' requires an uppercase constructor name"))
      else
        make "constructor_pattern" first last [("name", target); ("arguments", array args)] args
%}

%token MODULE PUBLIC NAT BOOL LET CONST RETURN IF ELSE TRUE FALSE
%token LPAREN RPAREN LBRACE RBRACE SEMICOLON COMMA EQUAL PLUS STAR EQ LE EOF
%token <string> IDENT DECIMAL
%token PRIVATE INTERNAL ASYNC RECORD STRUCT UNION INTERFACE IMPL IMPORT ALIAS NAMESPACE AS
%token OWNED MOVE IN REF OUT GHOST TRACKED SCOPED REGION CAPTURES GRADE DOMAIN
%token REQUIRES ENSURES RESTORES WHERE EFFECTS INVARIANT DECREASES PROGRESS
%token VIEW GROWS TYPE PREDICATE PROOF
%token EFFECT RESUMES HANDLE SHALLOW WITH RESUME DISPOSE REHANDLE
%token AWAIT SCOPE OPEN LIFTS SPAWN COMMIT ON CANCEL VAR FOREACH WHILE MATCH BREAK CONTINUE
%token DEFINITION THEOREM LEMMA INDUCTIVE COINDUCTIVE UNIVERSE FORALL EXISTS ASSERT BY CALC
%token MACHINE HARDWARE STATE REGISTER TRANSITION RULE WHEN NEXT SCHEDULE CYCLE
%token FN FNMUT FNONCE IS CARRIER ZERO ONE ADD MUL ADMITS INTERPRET LAWS
%token LBRACKET RBRACKET DOT COLON AT QUESTION RANGE ARROW FATARROW IMPLIES IFF
%token MINUS SLASH PERCENT LT GT GE NE AND OR NOT AMP BAR CARET TILDE
%token PLUS_ASSIGN MINUS_ASSIGN STAR_ASSIGN SLASH_ASSIGN MOD_ASSIGN
%token GENERIC_OPEN CALL_GENERIC_OPEN
%token ANNOTATION_OPEN LAMBDA_OPEN
%token <string * string> NUMBER
%token <string> LIFETIME STRING INTERPOLATED_STRING CHARACTER HOLE ANNOTATION_NAME
%start <Ast.node> file
%start <Ast.node> surface_file
%start <unit> generic_call_prefix

%%

/* Internal token-only prefix probe; the public entries still own complete files. */
generic_call_prefix:
  comma_nonempty_list(s_type_argument) GT s_open_paren { () }

file:
  MODULE module_name=name SEMICOLON declarations=nonempty_list(pure_declaration) EOF
    { make "file" $startpos $endpos(declarations)
        [("name", module_name); ("declarations", array declarations)] declarations }

/* Inline the optional modifier to share the prefix with constant declarations. */
pure_declaration:
  PUBLIC constant=ioption(CONST) result=value_type function_name=name LPAREN
  parameters=comma_list(parameter) RPAREN body=function_body
    { make "function" $startpos $endpos
        ([("name", function_name); ("result", result.syntax);
          ("parameters", array parameters); ("body", body.syntax)] @ const_fields constant)
        (result :: body :: parameters) }
| PUBLIC CONST value_type=value_type constant_name=name EQUAL value=expression SEMICOLON
    { make "constant" $startpos $endpos [("name", constant_name); ("type", value_type.syntax);
        ("value", value.syntax)] [value_type; value] }

name:
  spelling=IDENT { name $startpos $endpos spelling }

value_type:
  NAT { make "type" $startpos $endpos [("name", String "Nat")] [] }
| BOOL { make "type" $startpos $endpos [("name", String "bool")] [] }

function_body:
  value=block { value }
| FATARROW value=expression SEMICOLON
    { make "expression_body" $startpos $endpos [("value", value.syntax)] [value] }

parameter:
  constant=option(CONST) parameter_type=value_type parameter_name=name
    { make "parameter" $symbolstartpos $endpos
        ([("name", parameter_name); ("type", parameter_type.syntax)] @ const_fields constant)
        [parameter_type] }

block:
  LBRACE bindings=list(binding) terminal=exit RBRACE
    { if List.length bindings > 64 then
        (let first = $startpos in
         raise (Refusal ("limit", first.Lexing.pos_cnum,
                         "block exceeds 64 bindings")));
      make "block" $startpos $endpos
        [("bindings", array bindings); ("exit", terminal.syntax)] (terminal :: bindings) }

binding:
  LET binding_name=name EQUAL value=expression SEMICOLON
    { make "let" $startpos $endpos
        [("name", binding_name); ("value", value.syntax)] [value] }
| LET annotation=value_type binding_name=name EQUAL value=expression SEMICOLON
    { make "let" $startpos $endpos
        [("name", binding_name); ("type", annotation.syntax); ("value", value.syntax)] [annotation; value] }
| annotation=value_type binding_name=name EQUAL value=expression SEMICOLON
    { let _ = annotation, binding_name, value in
      raise (Refusal ("syntax", $startpos.Lexing.pos_cnum,
                      "local declaration requires 'let' or 'var' before its type (write 'let T x = e;' or 'var T x = e;')")) }
| binding_name=name EQUAL value=expression SEMICOLON
    { make "reassignment" $startpos $endpos
        [("name", binding_name); ("value", value.syntax)] [value] }
| CONST value_type=value_type constant_name=name EQUAL value=expression SEMICOLON
    { make "constant_local" $startpos $endpos [("name", constant_name); ("type", value_type.syntax);
        ("value", value.syntax)] [value_type; value] }

exit:
  RETURN value=expression SEMICOLON
    { make "return" $startpos $endpos [("value", value.syntax)] [value] }
| IF LPAREN condition=expression RPAREN yes=block ELSE no=block
    { make "if" $startpos $endpos
        [("condition", condition.syntax); ("then", yes.syntax); ("else", no.syntax)]
        [condition; yes; no] }

expression:
  value=left_binary(conjunction, s_disjunction_operator) { value }

conjunction:
  value=left_binary(comparison, s_conjunction_operator) { value }

comparison:
  value=sum { value }
| left=sum op=comparison_operator right=sum
    { binary $startpos $endpos op left right }

comparison_operator:
  EQ { name $startpos $endpos "==" } | LE { name $startpos $endpos "<=" }
| NE { name $startpos $endpos "!=" } | LT { name $startpos $endpos "<" }
| GT { name $startpos $endpos ">" } | GE { name $startpos $endpos ">=" }

sum:
  value=left_binary(product, s_sum_operator) { value }
plus_operator:
  PLUS { name $startpos $endpos "+" }

product:
  value=left_binary(unary, s_product_operator) { value }
star_operator:
  STAR { name $startpos $endpos "*" }

unary:
  value=atom { value }
| operator=negation_operator value=unary
    { make "unary" $startpos $endpos
        [("operator", operator); ("value", value.syntax)] [value] }

negation_operator:
  NOT { name $startpos $endpos "!" }

atom:
  value=DECIMAL { make "nat" $startpos $endpos [("value", String value)] [] }
| TRUE { make "bool" $startpos $endpos [("value", Boolean true)] [] }
| FALSE { make "bool" $startpos $endpos [("value", Boolean false)] [] }
| value=name { make "name" $startpos $endpos [("name", value)] [] }
| callee=name LPAREN arguments=comma_list(call_argument(expression, name)) RPAREN
    { make "call" $startpos $endpos
        [("callee", callee); ("arguments", array arguments)] arguments }
| LPAREN value=expression RPAREN
    { make "group" $startpos $endpos [("value", value.syntax)] [value] }

/* Both entries retain argument roles, original spans and the value child. */
call_argument(expression, identifier):
  value=expression
    { make "argument" $startpos $endpos [("label", Null); ("value", value.syntax)] [value] }
| label=identifier COLON value=expression
    { make "argument" $startpos $endpos [("label", label); ("value", value.syntax)] [value] }

/* The wider syntax has a separate AST entry from the pure authoring subset. */
surface_file:
  MODULE module_name=s_path SEMICOLON declarations=list(s_declaration) EOF
    { make "surface_file" $startpos $endpos(declarations)
        [("name", module_name); ("declarations", array declarations)] declarations }

s_identifier:
  value=s_value_identifier { value }
| value=ANNOTATION_NAME { name $startpos $endpos value }
s_value_identifier:
  value=IDENT { name $startpos $endpos value }
| NAT { name $startpos $endpos "Nat" }
| BOOL { name $startpos $endpos "bool" }

s_path:
  value=s_qualified_name(s_identifier) { value }
s_qualified_name(head):
  first=head rest=list(s_path_segment)
    { let text = match first with Object fields ->
          (match List.assoc "text" fields with String value -> value | _ -> "") | _ -> "" in
      name $startpos $endpos (String.concat "." (text :: rest)) }

/* Dictionary projections share ordinary paths; role words remain reserved at
   the start of a name and retain their domain-entry meaning. */
s_member_identifier:
  value=s_identifier { value }
| CARRIER { name $startpos $endpos "carrier" }
| role=s_domain_role { name $startpos $endpos role }

s_modifier:
  PUBLIC { "public" } | PRIVATE { "private" } | INTERNAL { "internal" }
| ASYNC { "async" } | CONST { "const" }

s_declaration:
  modifiers=list(s_modifier) declaration=s_decl
    { with_declaration_modifiers $symbolstartpos $endpos modifiers declaration }

s_decl:
  IMPORT path=s_path SEMICOLON
    { make "import" $startpos $endpos [("name", path)] [] }
| ALIAS alias=s_identifier generics=s_generics contracts=list(s_contract) EQUAL value=s_type SEMICOLON
    { make "alias" $startpos $endpos [("name", alias); ("generics", array generics);
        ("contracts", array contracts); ("type", value.syntax)] (value :: generics @ contracts) }
| NAMESPACE path=s_path LBRACE members=list(s_declaration) RBRACE
    { make "namespace" $startpos $endpos [("name", path); ("declarations", array members)] members }
| kind=s_container_kind container_name=s_identifier generics=s_generics
  contracts=list(s_contract) LBRACE members=list(s_declaration) RBRACE
    { make kind $startpos $endpos [("name", container_name); ("generics", array generics);
        ("contracts", array contracts); ("declarations", array members)] (generics @ contracts @ members) }
| IMPL generics=s_generics target=s_nonfunction_type contracts=list(s_contract) LBRACE members=list(s_declaration) RBRACE
    { make "impl" $startpos $endpos [("type", target.syntax); ("generics", array generics);
        ("contracts", array contracts); ("declarations", array members)]
        (target :: generics @ contracts @ members) }
| RECORD record_name=s_identifier generics=s_generics LPAREN
  parameters=comma_list(s_parameter) RPAREN contracts=list(s_contract) tail=s_record_tail
    { make "record" $startpos $endpos [("name", record_name); ("generics", array generics);
        ("parameters", array parameters); ("contracts", array contracts); ("declarations", array tail)]
        (generics @ parameters @ contracts @ tail) }
| kind=s_sum_kind sum_name=s_identifier generics=s_generics
  contracts=list(s_contract) LBRACE cases=list(s_constructor) RBRACE
    { make kind $startpos $endpos [("name", sum_name); ("generics", array generics);
        ("contracts", array contracts); ("constructors", array cases)] (generics @ contracts @ cases) }
| DOMAIN domain_name=s_identifier generics=s_generics contracts=list(s_contract)
  LBRACE entries=list(s_domain_entry) RBRACE
    { make "domain" $startpos $endpos [("name", domain_name); ("generics", array generics);
        ("contracts", array contracts); ("entries", array entries)] (generics @ contracts @ entries) }
| EFFECT effect_name=s_identifier generics=s_generics contracts=list(s_contract)
  LBRACE operations=list(s_effect_operation) RBRACE
    { make "effect" $startpos $endpos [("name", effect_name); ("generics", array generics);
        ("contracts", array contracts); ("operations", array operations)] (generics @ contracts @ operations) }
| VIEW view_name=s_identifier EQUAL parts=separated_nonempty_list(COMMA, s_view_part) SEMICOLON
    { make "view" $startpos $endpos [("name", view_name); ("parts", array parts)] parts }
| TYPE type_name=s_identifier generics=s_generics kind=option(s_kind_annotation)
  contracts=list(s_contract) definition=option(s_type_definition) SEMICOLON
    { make "associated_type" $startpos $endpos [("name", type_name); ("generics", array generics);
        ("kind_annotation", optional kind); ("contracts", array contracts);
        ("definition", optional definition)] (generics @ children kind @ contracts @ children definition) }
| PREDICATE predicate_name=s_identifier generics=s_generics LPAREN
  parameters=comma_list(s_parameter) RPAREN contracts=list(s_contract)
  definition=option(s_value_definition) SEMICOLON
    { make "predicate" $startpos $endpos [("name", predicate_name); ("generics", array generics);
        ("parameters", array parameters); ("contracts", array contracts); ("definition", optional definition)]
        (generics @ parameters @ contracts @ children definition) }
| UNIVERSE universe=s_identifier SEMICOLON
    { make "universe" $startpos $endpos [("name", universe)] [] }
| DEFINITION header=s_callable_header contracts=list(s_contract) FATARROW value=s_expression SEMICOLON
    { let result, definition_name, generics, parameters = header in
      make "definition" $startpos $endpos [("name", definition_name); ("result", result.syntax);
        ("generics", array generics); ("parameters", array parameters); ("contracts", array contracts);
        ("value", value.syntax)] (result :: value :: generics @ parameters @ contracts) }
| kind=s_theorem_kind theorem_name=s_identifier generics=s_generics LPAREN
  parameters=comma_list(s_parameter) RPAREN pre=list(s_theorem_precontract)
  post=nonempty_list(s_theorem_ensures) body=s_theorem_body
    { let contracts = pre @ post in
      make kind $startpos $endpos [("name", theorem_name); ("generics", array generics);
        ("parameters", array parameters); ("contracts", array contracts); ("body", optional body)]
        (generics @ parameters @ contracts @ children body) }
| kind=s_storage_kind value_type=s_type storage_name=s_identifier EQUAL value=s_expression SEMICOLON
    { make kind $startpos $endpos [("name", storage_name); ("type", value_type.syntax);
        ("value", value.syntax)] [value_type; value] }
| kind=s_rule_kind rule_name=s_identifier LPAREN parameters=comma_list(s_parameter) RPAREN
  guard=option(s_guard) body=s_block
    { make kind $startpos $endpos [("name", rule_name); ("parameters", array parameters);
        ("guard", optional guard); ("body", body.syntax)] (body :: parameters @ children guard) }
| SCHEDULE schedule_name=s_identifier LBRACE rules=list(s_schedule_entry) RBRACE
    { make "schedule" $startpos $endpos [("name", schedule_name); ("rules", array rules)] rules }
| CYCLE value=s_expression SEMICOLON
    { make "cycle" $startpos $endpos [("value", value.syntax)] [value] }
| header=s_callable_header contracts=list(s_contract) body=s_function_body cancel=option(s_cancel)
    { let result, function_name, generics, parameters = header in
      make "function" $startpos $endpos [("name", function_name); ("result", result.syntax);
        ("generics", array generics); ("parameters", array parameters); ("contracts", array contracts);
        ("body", optional body); ("cancel", optional cancel)]
        (result :: generics @ parameters @ contracts @ children body @ children cancel) }
| value_type=s_type property_name=s_identifier contracts=list(s_obligation) FATARROW value=s_expression SEMICOLON
    { make "property" $startpos $endpos [("name", property_name); ("type", value_type.syntax);
        ("contracts", array contracts); ("value", value.syntax)]
        (value_type :: value :: contracts) }
| value_type=s_type field_name=s_identifier grade=option(s_grade) value=option(s_value_definition) SEMICOLON
    { make "field" $startpos $endpos [("name", field_name); ("type", value_type.syntax);
        ("grade", optional grade); ("value", optional value)]
        (value_type :: children grade @ children value) }

/* Declarations share the telescope; each owner retains its contract/body tail. */
%inline s_callable_header:
  result=s_type callable_name=s_identifier generics=s_generics s_parameter_open
  parameters=comma_list(s_parameter) RPAREN
    { result, callable_name, generics, parameters }
%inline s_parameter_open:
  LPAREN { () } | LAMBDA_OPEN { () }

s_container_kind:
  STRUCT { "struct" } | INTERFACE { "interface" }
| MACHINE { "machine" } | HARDWARE { "hardware" }
s_sum_kind:
  UNION { "union" } | INDUCTIVE { "inductive" } | COINDUCTIVE { "coinductive" }
s_theorem_kind:
  THEOREM { "theorem" } | LEMMA { "lemma" }
s_theorem_precontract:
  role=s_theorem_precontract_role value=s_expression
    { make "contract" $startpos $endpos [("role", String role); ("value", value.syntax)] [value] }
s_theorem_precontract_role:
  REQUIRES { "requires" } | WHERE { "where" } | DECREASES { "decreases" }
s_theorem_ensures:
  ENSURES value=s_expression
    { make "contract" $startpos $endpos [("role", String "ensures"); ("value", value.syntax)] [value] }
s_theorem_body:
  SEMICOLON { None } | PROOF body=s_block { Some body }
s_storage_kind:
  STATE { "state" } | REGISTER { "register" }
s_rule_kind:
  TRANSITION { "transition" } | RULE { "rule" }
s_guard:
  WHEN LPAREN value=s_expression RPAREN { value }
s_schedule_entry:
  rule_name=s_path SEMICOLON { make "schedule_entry" $startpos $endpos [("name", rule_name)] [] }
s_record_tail:
  SEMICOLON { [] } | LBRACE members=list(s_declaration) RBRACE { members }
s_type_definition:
  EQUAL value=s_type { value }
s_value_definition:
  EQUAL value=s_expression { value }
s_function_body:
  SEMICOLON { None } | value=s_block { Some value }
| FATARROW value=s_expression SEMICOLON
    { Some (make "expression_body" $startpos $endpos [("value", value.syntax)] [value]) }
s_cancel:
  ON CANCEL body=s_block { body }
s_constructor:
  constructor_name=s_identifier LPAREN parameters=comma_list(s_parameter) RPAREN
  tail=s_constructor_tail SEMICOLON
    { let result, contracts = tail in
      make "constructor" $startpos $endpos [("name", constructor_name); ("parameters", array parameters);
        ("result", optional result); ("contracts", array contracts)] (parameters @ children result @ contracts) }
s_constructor_tail:
  contracts=list(s_contract) { None, contracts }
| COLON result=s_nonfunction_type contracts=list(s_contract) { Some result, contracts }
/* Retain bare callable results: their effects belong to the callable. Group the
   result when a constructor itself needs an effects contract. */
| COLON result=s_qualified_function_type contracts=list(s_obligation) { Some result, contracts }
s_view_part:
  value=s_expression grows=option(GROWS)
    { make "view_part" $startpos $endpos [("value", value.syntax); ("grows", Boolean (grows <> None))] [value] }
s_domain_entry:
  CARRIER value=s_type SEMICOLON
    { make "domain_entry" $startpos $endpos [("role", String "carrier"); ("value", value.syntax)] [value] }
| role=s_domain_role value=s_expression SEMICOLON
    { make "domain_entry" $startpos $endpos [("role", String role); ("value", value.syntax)] [value] }
s_domain_role:
  ZERO { "zero" } | ONE { "one" } | ADD { "add" } | MUL { "mul" }
| ADMITS { "admits" } | INTERPRET { "interpret" } | LAWS { "laws" }
s_effect_operation:
  header=s_callable_header resumes=option(s_resumes) contracts=list(s_contract) SEMICOLON
    { let result, operation_name, generics, parameters = header in
      make "effect_operation" $startpos $endpos [("name", operation_name); ("result", result.syntax);
        ("generics", array generics); ("parameters", array parameters); ("resumes", optional resumes);
        ("contracts", array contracts)] (result :: generics @ parameters @ children resumes @ contracts) }
s_resumes:
  RESUMES LPAREN value=s_expression RPAREN { value }

s_generics:
  { [] } | s_generic_open values=comma_nonempty_list(s_generic_parameter) GT { values }
%inline s_generic_open:
  LT { () } | CALL_GENERIC_OPEN { () }
s_generic_parameter:
  binder=s_generic_binder
    { let mode, generic_name, value_type = binder in
      make "generic_parameter" $startpos $endpos [("mode", String mode); ("name", generic_name);
        ("type", optional value_type)] (children value_type) }
/* Binder modes select syntax roles; one constructor retains their common shape. */
%inline s_generic_binder:
  generic_name=s_identifier kind=option(s_kind_annotation) { "type", generic_name, kind }
| GHOST value_type=s_type generic_name=s_identifier
    { "ghost", generic_name, Some value_type }
| REGION lifetime=LIFETIME
    { "region", name $startpos(lifetime) $endpos(lifetime) lifetime, None }
| EFFECT generic_name=s_identifier { "effect", generic_name, None }
| CAPTURES generic_name=s_identifier { "captures", generic_name, None }
| GRADE generic_name=s_identifier COLON value_type=s_type
    { "grade", generic_name, Some value_type }
s_kind_annotation:
  COLON value=s_nonfunction_type { value }

s_type:
  value=s_nonfunction_type { value }
| value=s_qualified_function_type { value }
s_qualified_function_type:
  value=s_modified_type(s_function_type) { value }
s_nonfunction_type:
  value=s_modified_type(s_type_atom) { value }
/* All type contexts retain the same modifier order, lifetime and child depth. */
s_modified_type(base):
  value=base { value }
| modifier=s_type_modifier lifetime=ioption(s_loan_lifetime) value=s_modified_type(base)
    { make "modified_type" $startpos $endpos [("modifier", String modifier);
        ("lifetime", optional lifetime); ("type", value.syntax)] (value :: children lifetime) }
%inline s_type_modifier:
  OWNED { "owned" } | IN { "in" } | REF { "ref" } | OUT { "out" } | GHOST { "ghost" }
| TRACKED { "tracked" } | SCOPED { "scoped" }
s_loan_lifetime:
  s_generic_open value=LIFETIME GT
    { make "lifetime" $startpos $endpos [("name", name $startpos(value) $endpos(value) value)] [] }
s_type_atom:
  value=s_named_type(s_path) { value }
| value=s_computed_type { value }
| value=s_parenthesized_type(s_open_paren) { value }
%inline s_named_type(path):
  type_name=path arguments=s_type_arguments
    { make "type" $startpos $endpos [("name", type_name); ("arguments", array arguments)] arguments }
/* Only the first token varies for local annotations; the type algebra is shared. */
s_parenthesized_type(opening):
  opening value=s_type RPAREN { make "group_type" $startpos $endpos [("type", value.syntax)] [value] }
| opening first=s_type COMMA rest=separated_nonempty_list(COMMA, s_type) RPAREN
    { make "tuple_type" $startpos $endpos [("types", array (first :: rest))] (first :: rest) }
s_computed_type:
  TYPE LBRACKET value=s_expression RBRACKET
    { make "computed_type" $startpos $endpos [("value", value.syntax)] [value] }
s_open_paren:
  LPAREN { () } | ANNOTATION_OPEN { () } | LAMBDA_OPEN { () }
s_function_type:
  mode=s_function_mode generics=s_generics LPAREN parameters=comma_list(s_parameter) RPAREN ARROW result=s_nonfunction_type
  captures=option(s_capture_type) effects=loption(s_type_effects) contracts=loption(s_callable_contracts)
    { make "function_type" $startpos $endpos [("mode", String mode); ("generics", array generics); ("parameters", array parameters);
        ("result", result.syntax); ("captures", optional captures);
        ("effects", array effects);
        ("contracts", array contracts)]
        (result :: generics @ parameters @ children captures @ contracts @ effects) }
s_callable_contracts:
  WITH LBRACE contracts=list(terminated(s_contract, SEMICOLON)) RBRACE { contracts }
s_function_mode:
  FN { "Fn" } | FNMUT { "FnMut" } | FNONCE { "FnOnce" }
s_capture_type:
  CAPTURES capture=s_path { make "capture" $startpos $endpos [("name", capture)] [] }
s_type_effects:
  EFFECTS s_open_paren effects=comma_list(s_type) RPAREN { effects }
s_type_arguments:
  { [] } | s_generic_open values=comma_nonempty_list(s_type_argument) GT { values }
s_type_argument:
  value=s_generic_type { value }
| value=s_operator_value { value }
| TYPE value=s_type { make "type_argument" $startpos $endpos [("type", value.syntax)] [value] }
| value=s_literal { value }
| value=s_hole { value }
| value=LIFETIME { make "lifetime" $startpos $endpos [("name", name $startpos $endpos value)] [] }
| LPAREN value=s_expression RPAREN { make "group" $startpos $endpos [("value", value.syntax)] [value] }
/* Bare parentheses in generic arguments remain value syntax. Structural types
   have an explicit `type` introducer. */
s_generic_type:
  value=s_modified_type(s_generic_type_atom) { value }
s_generic_type_atom:
  value=s_named_type(s_path) { value }
| value=s_computed_type { value }
| value=s_function_type { value }
s_parameter:
  constant=option(CONST) value_type=s_type parameter_name=option(s_identifier) grade=option(s_grade)
    { make "parameter" $symbolstartpos $endpos
        ([("name", (match parameter_name with None -> Null | Some value -> value));
          ("type", value_type.syntax); ("grade", optional grade)] @ const_fields constant)
        (value_type :: children grade) }
s_grade:
  AT value=s_expression { value }
s_contract:
  value=s_obligation { value }
| EFFECTS values=separated_nonempty_list(COMMA, s_contract_expression)
    { make "effects" $startpos $endpos [("values", array values)] values }
s_obligation:
  role=s_contract_role value=s_contract_expression
    { make "contract" $startpos $endpos [("role", String role); ("value", value.syntax)] [value] }
| INVARIANT value=s_contract_expression
    { make "contract" $startpos $endpos [("role", String "invariant"); ("value", value.syntax)] [value] }
| INVARIANT clause=s_identifier COLON value=s_contract_expression
    { make "contract" $startpos $endpos [("role", String "invariant"); ("name", clause); ("value", value.syntax)] [value] }
s_contract_role:
  REQUIRES { "requires" } | ENSURES { "ensures" } | RESTORES { "restores" }
| WHERE { "where" } | DECREASES { "decreases" } | PROGRESS { "progress" }

s_block:
  LBRACE statements=list(s_statement) RBRACE
    { make "block" $startpos $endpos [("statements", array statements)] statements }

/* Matched and unmatched statements make nearest-else association structural. */
s_statement:
  value=s_statement_with(s_simple_statement) { value }
s_statement_with(simple):
  value=s_closed_statement_with(simple) { value } | value=s_open_statement_with(simple) { value }
s_closed_statement_with(simple):
  value=simple { value }
| IF s_open_paren condition=s_expression RPAREN yes=s_closed_statement_with(simple) ELSE no=s_closed_statement_with(simple)
    { make "if" $startpos $endpos [("condition", condition.syntax); ("then", yes.syntax); ("else", no.syntax)] [condition; yes; no] }
s_open_statement_with(simple):
  IF s_open_paren condition=s_expression RPAREN yes=s_statement_with(simple)
    { make "if" $startpos $endpos [("condition", condition.syntax); ("then", yes.syntax); ("else", Null)] [condition; yes] }
| IF s_open_paren condition=s_expression RPAREN yes=s_closed_statement_with(simple) ELSE no=s_open_statement_with(simple)
    { make "if" $startpos $endpos [("condition", condition.syntax); ("then", yes.syntax); ("else", no.syntax)] [condition; yes; no] }
s_simple_statement:
  value=s_nonempty_simple_statement { value }
| parts=s_empty_match
    { let value, motive = parts in
      make "match" $startpos $endpos [("value", value.syntax); ("motive", optional motive);
        ("cases", Array [])] (value :: children motive) }
s_nonempty_simple_statement:
  value=s_block { value }
| CONST value_type=s_type constant_name=s_identifier EQUAL value=s_expression SEMICOLON
    { make "constant_local" $startpos $endpos [("name", constant_name); ("type", value_type.syntax);
        ("value", value.syntax)] [value_type; value] }
| WHILE LPAREN condition=s_expression RPAREN contracts=list(s_contract) body=s_block
    { make "while" $startpos $endpos [("condition", condition.syntax); ("contracts", array contracts); ("body", body.syntax)]
        (condition :: body :: contracts) }
| FOREACH LPAREN mode=s_iteration_mode binding=s_iteration_binding IN collection=s_expression RPAREN
  contracts=list(s_contract) body=s_block
    { let binding_name, annotation = binding in
      let rec range = function
        | Object fields -> (match List.assoc_opt "kind" fields with
            | Some (String "range") -> true
            | Some (String "group") -> (match List.assoc_opt "value" fields with
                | Some value -> range value | None -> false)
            | _ -> false)
        | _ -> false in
      if mode = "value" && annotation = None && range collection.syntax then
        make "foreach" $startpos $endpos [("name", binding_name); ("range", collection.syntax);
          ("contracts", array contracts); ("body", body.syntax)] (collection :: body :: contracts)
      else make "foreach_collection" $startpos $endpos [("name", binding_name);
        ("type", optional annotation); ("mode", String mode); ("collection", collection.syntax);
        ("contracts", array contracts); ("body", body.syntax)]
        (children annotation @ collection :: body :: contracts) }

| kind=s_local_kind binding=s_local_initializer SEMICOLON
    { let suffix, fields, parts = binding in
      make (kind ^ suffix) $startpos $endpos fields parts }
| kind=s_local_kind pattern=s_local_pattern EQUAL value=s_expression ELSE otherwise=s_block
    { make (kind ^ "_else") $startpos $endpos
        [("pattern", pattern.syntax); ("value", value.syntax); ("else", otherwise.syntax)]
        [pattern; value; otherwise] }
| binding=s_typed_initializer SEMICOLON
    { let _ = binding in
      raise (Refusal ("syntax", $startpos.Lexing.pos_cnum,
                      "local declaration requires 'let' or 'var' before its type (write 'let T x = e;' or 'var T x = e;')")) }
| RETURN value=option(s_expression) SEMICOLON
    { make "return" $startpos $endpos [("value", optional value)] (children value) }
| BREAK SEMICOLON { make "break" $startpos $endpos [] [] }
| CONTINUE SEMICOLON { make "continue" $startpos $endpos [] [] }
| kind=s_proof_block_kind body=s_block { make kind $startpos $endpos [("body", body.syntax)] [body] }
| ASSERT value=s_expression justification=s_assert_tail
    { let by_node, parts = justification in
      make "assert" $startpos $endpos [("value", value.syntax); ("by", by_node)] (value :: parts) }
| SCOPE LPAREN values=comma_list(s_expression) RPAREN body=s_block
    { make "scope" $startpos $endpos [("resources", array values); ("body", body.syntax)] (body :: values) }
| OPEN LPAREN values=comma_list(s_expression) RPAREN clauses=s_lifts body=s_block
    { make "open_invariant" $startpos $endpos [("resources", array values); ("lifts", Array clauses);
        ("body", body.syntax)] (body :: values) }
| MATCH LPAREN value=s_expression RPAREN motive=option(s_match_motive) LBRACE cases=nonempty_list(s_match_case) RBRACE
    { make "match" $startpos $endpos [("value", value.syntax); ("motive", optional motive);
        ("cases", array cases)] (value :: children motive @ cases) }
| NEXT target=s_postfix EQUAL value=s_expression SEMICOLON
    { make "next" $startpos $endpos [("target", target.syntax); ("value", value.syntax)] [target; value] }
| target=s_statement_expression operator=s_assignment value=s_expression SEMICOLON
    { make "assignment" $startpos $endpos [("target", target.syntax); ("operator", operator); ("value", value.syntax)] [target; value] }
| value=s_statement_expression SEMICOLON
    { make "expression_statement" $startpos $endpos [("value", value.syntax)] [value] }
s_annotation_type:
  value=s_modified_type(s_annotation_type_atom) { value }
s_annotation_type_atom:
  value=s_named_type(s_annotation_path) { value }
| value=s_computed_type { value }
| value=s_function_type { value }
| value=s_parenthesized_type(ANNOTATION_OPEN) { value }
s_iteration_mode:
  LET { "value" } | IN { "in" } | REF { "ref" }
s_iteration_binding:
  binding_name=s_identifier { binding_name, None }
| annotation=s_type binding_name=s_identifier { binding_name, Some annotation }
%inline s_proof_block_kind:
  PROOF { "proof" } | CALC { "calc" }
s_assert_tail:
  SEMICOLON { Null, [] }
| BY justification=s_expression SEMICOLON { justification.syntax, [justification] }
| BY body=s_block { body.syntax, [body] }
s_lifts:
  LIFTS clauses=comma_nonempty_list(s_identifier) { clauses }
s_annotation_path:
  first=ANNOTATION_NAME rest=list(s_path_segment)
    { name $startpos $endpos (String.concat "." (first :: rest)) }
s_path_segment:
  DOT value=s_member_identifier
    { match value with Object fields -> (match List.assoc "text" fields with String text -> text | _ -> "") | _ -> "" }
%inline s_local_kind:
  LET { "let" } | VAR { "var" }
/* Statements and expression-local bindings share the complete initializer.
   The owner supplies its keyword, terminator and existing syntax-node span. */
s_local_initializer:
  binding_name=s_identifier grade=option(s_grade) EQUAL value=s_expression
    { "", [("name", binding_name); ("type", Null);
        ("grade", optional grade); ("value", value.syntax)], value :: children grade }
| binding=s_typed_initializer
    { let fields, parts = binding in "", fields, parts }
| pattern=s_local_pattern EQUAL value=s_expression
    { "_pattern", [("pattern", pattern.syntax); ("value", value.syntax)], [pattern; value] }
%inline s_typed_initializer:
  value_type=s_annotation_type binding_name=s_identifier grade=option(s_grade) EQUAL value=s_expression
    { [("name", binding_name); ("type", value_type.syntax);
       ("grade", optional grade); ("value", value.syntax)], value_type :: value :: children grade }
s_assignment:
  EQUAL { name $startpos $endpos "=" } | PLUS_ASSIGN { name $startpos $endpos "+=" }
| MINUS_ASSIGN { name $startpos $endpos "-=" } | STAR_ASSIGN { name $startpos $endpos "*=" }
| SLASH_ASSIGN { name $startpos $endpos "/=" } | MOD_ASSIGN { name $startpos $endpos "%=" }
s_match_case:
  pattern=s_pattern FATARROW statement=s_statement_with(s_nonempty_simple_statement) option(COMMA)
    { make "case" $startpos $endpos(statement)
        [("pattern", pattern.syntax); ("statements", array [statement])] [pattern; statement] }
s_match_motive:
  AS scrutinee=s_identifier COLON value_type=s_type
    { make "match_motive" $startpos $endpos [("name", scrutinee); ("type", value_type.syntax)] [value_type] }
s_match_expression_case:
  pattern=s_pattern FATARROW value=s_expression
    { make "expression_case" $startpos $endpos [("pattern", pattern.syntax); ("value", value.syntax)] [pattern; value] }
/* Sharing the empty prefix avoids competing empty case-list reductions. Keep
   value elimination at the full-expression boundary, like lambdas/type values. */
s_empty_match:
  MATCH LPAREN value=s_expression RPAREN motive=option(s_match_motive) LBRACE RBRACE
    { value, motive }
s_pattern:
  target=s_path values=option(s_pattern_arguments)
    { build_pattern $startpos $endpos target values }
| value=s_product_pattern { value }
| payload=s_literal_payload
    { let kind, fields = payload in make (kind ^ "_pattern") $startpos $endpos fields [] }
s_pattern_arguments:
  s_parameter_open values=comma_list(s_pattern_argument) RPAREN { values }
s_pattern_argument:
  pattern=s_pattern { pattern }
| label=s_identifier COLON pattern=s_pattern
    { make "labeled_pattern" $startpos $endpos [("label", label); ("pattern", pattern.syntax)] [pattern] }
/* A bare local name stays an inferred binder; uppercase constructor patterns,
   qualified constructor patterns, and product patterns use local_pattern. */
s_local_pattern:
  value=s_product_pattern { value }
| first=s_value_identifier values=s_pattern_arguments
    { build_pattern $startpos $endpos first (Some values) }
| first=s_value_identifier rest=nonempty_list(s_path_segment) values=option(s_pattern_arguments)
    { let target = name $startpos $endpos (String.concat "." (name_text first :: rest)) in
      build_pattern $startpos $endpos target values }
s_product_pattern:
  s_parameter_open RPAREN { make "unit_pattern" $startpos $endpos [] [] }
| s_parameter_open value=s_pattern RPAREN
    { make "group_pattern" $startpos $endpos [("pattern", value.syntax)] [value] }
| s_parameter_open first=s_pattern COMMA rest=separated_nonempty_list(COMMA, s_pattern) RPAREN
    { make "tuple_pattern" $startpos $endpos [("patterns", array (first :: rest))] (first :: rest) }

s_expression:
  value=s_statement_expression { value }
| IF s_open_paren condition=s_expression RPAREN yes=s_expression ELSE no=s_expression
    { make "if_expression" $startpos $endpos [("condition", condition.syntax);
        ("then", yes.syntax); ("else", no.syntax)] [condition; yes; no] }
s_statement_expression:
  value=s_implication { value }
| LET initialized=s_local_initializer IN body=s_expression
    { let suffix, fields, parts = initialized in
      let binding = make ("let" ^ suffix) $startpos $endpos(initialized) fields parts in
      make "let_expression" $startpos $endpos
        [("binding", binding.syntax); ("body", body.syntax)] [binding; body] }
| parts=s_empty_match
    { let value, motive = parts in
      make "match_expression" $startpos $endpos [("value", value.syntax); ("motive", optional motive);
        ("cases", Array [])] (value :: children motive) }
| TYPE value=s_nonfunction_type
    { make "type_expression" $startpos $endpos [("type", value.syntax)] [value] }
| signature=s_function_type FATARROW body=s_lambda_body
    { make "typed_lambda" $startpos $endpos [("signature", signature.syntax); ("body", body.syntax)] [signature; body] }
| quantifier=s_quantifier_kind s_parameter_open parameters=comma_nonempty_list(s_parameter) RPAREN FATARROW value=s_expression
    { make "quantifier" $startpos $endpos [("quantifier", String quantifier); ("parameters", array parameters); ("value", value.syntax)] (value :: parameters) }
| LAMBDA_OPEN parameters=comma_list(s_lambda_parameter) RPAREN FATARROW body=s_lambda_body
    { make "lambda" $startpos $endpos [("parameters", array parameters); ("body", body.syntax)] (body :: parameters) }
| parameter_name=s_value_identifier FATARROW body=s_lambda_body
    { let parameter = make "lambda_parameter" $startpos(parameter_name) $endpos(parameter_name)
        [("type", Null); ("name", parameter_name); ("grade", Null)] [] in
      make "lambda" $startpos $endpos [("parameters", array [parameter]); ("body", body.syntax)] [body; parameter] }
%inline s_quantifier_kind:
  FORALL { "forall" } | EXISTS { "exists" }
s_lambda_parameter:
  constant=option(CONST) value_type=s_annotation_type parameter_name=s_identifier grade=option(s_grade)
    { make "lambda_parameter" $symbolstartpos $endpos
        ([("type", value_type.syntax); ("name", parameter_name);
          ("grade", optional grade)] @ const_fields constant) (value_type :: children grade) }
| parameter_name=s_value_identifier grade=option(s_grade)
    { make "lambda_parameter" $startpos $endpos [("type", Null); ("name", parameter_name);
        ("grade", optional grade)] (children grade) }
s_lambda_body:
  value=s_expression { value } | value=s_block { value }
/* Binary operators and their value forms share one spelling and source span.
   Recursive ladders make associativity explicit; comparison/range stay singular. */
left_binary(operand, operator):
  value=operand { value }
| left=left_binary(operand, operator) op=operator right=operand
    { binary $startpos $endpos op left right }
right_binary(operand, operator):
  value=operand { value }
| left=operand op=operator right=right_binary(operand, operator)
    { binary $startpos $endpos op left right }
/* Contracts use the same precedence/postfix rules as expressions, with only
   their outer grouping boundary changed. A full-form contract value (lambda,
   quantifier, let or type expression) is explicitly parenthesized. */
s_implication:
  value=s_implication_with(LPAREN) { value }
s_contract_expression:
  value=s_implication_with(s_parameter_open) { value }
s_postfix:
  value=s_postfix_with(LPAREN) { value }
s_implication_with(opening):
  value=right_binary(s_disjunction_with(opening), s_implication_operator) { value }
s_implication_operator:
  IMPLIES { name $startpos $endpos "==>" } | IFF { name $startpos $endpos "<==>" }
s_disjunction_with(opening):
  value=left_binary(s_conjunction_with(opening), s_disjunction_operator) { value }
s_disjunction_operator:
  OR { name $startpos $endpos "||" }
s_conjunction_with(opening):
  value=left_binary(s_comparison_with(opening), s_conjunction_operator) { value }
s_conjunction_operator:
  AND { name $startpos $endpos "&&" }
s_comparison_with(opening):
  value=s_range_with(opening) { value }
| left=s_range_with(opening) op=s_comparison_operator right=s_range_with(opening) { binary $startpos $endpos op left right }
| value=s_range_with(opening) IS pattern=s_pattern
    { make "is" $startpos $endpos [("value", value.syntax); ("pattern", pattern.syntax)] [value; pattern] }
s_comparison_operator:
  value=comparison_operator { value }
s_range_with(opening):
  value=s_bit_or_with(opening) { value }
| left=s_bit_or_with(opening) RANGE right=s_bit_or_with(opening)
    { make "range" $startpos $endpos [("start", left.syntax); ("end", right.syntax)] [left; right] }
s_bit_or_with(opening):
  value=left_binary(s_bit_xor_with(opening), s_bit_or_operator) { value }
s_bit_or_operator:
  BAR { name $startpos $endpos "|" }
s_bit_xor_with(opening):
  value=left_binary(s_bit_and_with(opening), s_bit_xor_operator) { value }
s_bit_xor_operator:
  CARET { name $startpos $endpos "^" }
s_bit_and_with(opening):
  value=left_binary(s_sum_with(opening), s_bit_and_operator) { value }
s_bit_and_operator:
  AMP { name $startpos $endpos "&" }
s_sum_with(opening):
  value=left_binary(s_product_with(opening), s_sum_operator) { value }
s_sum_operator:
  value=plus_operator { value } | MINUS { name $startpos $endpos "-" }
s_product_with(opening):
  value=left_binary(s_unary_with(opening), s_product_operator) { value }
s_product_operator:
  value=star_operator { value } | SLASH { name $startpos $endpos "/" }
| PERCENT { name $startpos $endpos "%" }
s_unary_with(opening):
  value=s_prefix_with(opening) { value }
| value=s_unary_with(opening) WITH LBRACE updates=comma_nonempty_list(s_field_update) RBRACE
    { make "with_expression" $startpos $endpos
        [("value", value.syntax); ("updates", array updates)] (value :: updates) }
s_prefix_with(opening):
  value=s_postfix_with(opening) { value }
| operator=s_unary_operator value=s_prefix_with(opening)
    { make "unary" $startpos $endpos [("operator", operator); ("value", value.syntax)] [value] }
| DISPOSE value=s_prefix_with(opening)
    { make "dispose" $startpos $endpos [("value", value.syntax)] [value] }
| RESUME continuation=s_identifier s_parameter_open value=s_expression RPAREN
    { make "resume" $startpos $endpos [("continuation", continuation); ("value", value.syntax)] [value] }
s_field_update:
  field_name=s_identifier EQUAL value=s_expression
    { make "field_update" $startpos $endpos [("name", field_name); ("value", value.syntax)] [value] }
%inline s_unary_operator:
  MINUS { name $startpos $endpos "-" } | value=negation_operator { value }
| TILDE { name $startpos $endpos "~" } | MOVE { name $startpos $endpos "move" }
| IN { name $startpos $endpos "in" } | REF { name $startpos $endpos "ref" }
| OUT { name $startpos $endpos "out" }
| STAR { name $startpos $endpos "*" } | AMP { name $startpos $endpos "&" }
| AWAIT { name $startpos $endpos "await" } | SPAWN { name $startpos $endpos "spawn" }
| COMMIT { name $startpos $endpos "commit" }
s_postfix_with(opening):
  value=s_atom_with(opening) { value }
| callee=s_postfix_with(opening) s_parameter_open arguments=comma_list(call_argument(s_expression, s_identifier)) RPAREN
    { make "call" $startpos $endpos [("callee", callee.syntax); ("arguments", array arguments)] (callee :: arguments) }
| value=s_postfix_with(opening) DOT member=s_member_identifier
    { make "member" $startpos $endpos [("value", value.syntax); ("name", member)] [value] }
| value=s_postfix_with(opening) LBRACKET index=s_expression RBRACKET
    { make "index" $startpos $endpos [("value", value.syntax); ("index", index.syntax)] [value; index] }
| value=s_postfix_with(opening) s_expression_generic_open arguments=comma_nonempty_list(s_type_argument) GT
    { make "generic_application" $startpos $endpos [("value", value.syntax); ("arguments", array arguments)] (value :: arguments) }
| value=s_postfix_with(opening) QUESTION
    { make "propagate" $startpos $endpos [("value", value.syntax)] [value] }
%inline s_expression_generic_open:
  GENERIC_OPEN { () } | CALL_GENERIC_OPEN { () }
s_atom_with(opening):
  value=s_literal { value }
| value=INTERPOLATED_STRING
    { make "interpolated_string" $startpos $endpos [("value", String value)] [] }
| value=s_operator_value_with(opening) { value }
| value=s_hole { value }
| value=s_value_identifier { make "name" $startpos $endpos [("name", value)] [] }
| opening RPAREN { make "unit" $startpos $endpos [] [] }
| opening value=s_expression RPAREN { make "group" $startpos $endpos [("value", value.syntax)] [value] }
| opening first=s_expression COMMA rest=separated_nonempty_list(COMMA, s_expression) RPAREN
    { make "tuple" $startpos $endpos [("values", array (first :: rest))] (first :: rest) }
| MATCH LPAREN value=s_expression RPAREN motive=option(s_match_motive)
  LBRACE cases=comma_nonempty_list(s_match_expression_case) RBRACE
    { make "match_expression" $startpos $endpos [("value", value.syntax); ("motive", optional motive);
        ("cases", array cases)] (value :: children motive @ cases) }
| kind=s_handle_kind shallow=option(SHALLOW) LPAREN value=s_expression RPAREN
  capability=option(s_handler_capability) LBRACE clauses=comma_list(s_handler_clause) RBRACE
    { make kind $startpos $endpos [("shallow", Boolean (shallow <> None));
        ("value", value.syntax); ("capability", (match capability with None -> Null | Some value -> value));
        ("clauses", array clauses)] (value :: clauses) }
s_literal:
  payload=s_literal_payload
    { let kind, fields = payload in make kind $startpos $endpos fields [] }
/* Literal spelling/payload is independent of its expression or pattern role. */
%inline s_literal_payload:
  value=DECIMAL { "nat", [("value", String value); ("suffix", String "")] }
| value=NUMBER { let digits, suffix = value in "nat", [("value", String digits); ("suffix", String suffix)] }
| value=STRING { "string", [("value", String value)] }
| value=CHARACTER { "character", [("value", String value)] }
| TRUE { "bool", [("value", Boolean true)] }
| FALSE { "bool", [("value", Boolean false)] }
s_hole:
  value=HOLE { make "hole" $startpos $endpos [("name", name $startpos $endpos value)] [] }
s_handle_kind:
  HANDLE { "handle" } | REHANDLE { "rehandle" }
s_handler_capability:
  AS capability=s_identifier { capability }
s_handler_clause:
  operation_name=s_path LPAREN parameters=comma_list(s_identifier) RPAREN WITH
  continuation=s_identifier FATARROW body=s_lambda_body
    { make "operation_clause" $startpos $endpos [("name", operation_name);
        ("parameters", Array parameters); ("continuation", continuation); ("body", body.syntax)] [body] }
| kind=s_terminal_clause_kind binder=s_identifier FATARROW body=s_lambda_body
    { make kind $startpos $endpos [("name", binder); ("body", body.syntax)] [body] }
%inline s_terminal_clause_kind:
  RETURN { "return_clause" } | DISPOSE { "disposal_clause" }
s_operator_value:
  value=s_operator_value_with(LPAREN) { value }
s_operator_value_with(opening):
  opening op=s_symbolic_operator RPAREN
    { make "operator" $startpos $endpos [("name", op)] [] }
s_symbolic_operator:
  value=s_implication_operator { value }
| value=s_disjunction_operator { value }
| value=s_conjunction_operator { value }
| value=s_comparison_operator { value }
| value=s_bit_or_operator { value }
| value=s_bit_xor_operator { value }
| value=s_bit_and_operator { value }
| value=s_sum_operator { value }
| value=s_product_operator { value }
| NOT { name $startpos $endpos "!" } | TILDE { name $startpos $endpos "~" }

/* Nonempty comma-delimited lists may end in one comma. Product productions
   deliberately keep the non-trailing list combinator and their two-item floor. */
comma_list(item):
  { [] }
| values=comma_nonempty_list(item) { values }
comma_nonempty_list(item):
  first=item rest=comma_tail(item) { first :: rest }
comma_tail(item):
  { [] }
| COMMA { [] }
| COMMA first=item rest=comma_tail(item) { first :: rest }
