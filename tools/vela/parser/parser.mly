/* SPDX-License-Identifier: Apache-2.0 */
%{
open Ast
let optional = function None -> Null | Some value -> value.syntax
let children = function None -> [] | Some value -> [value]
let strings values = Array (List.map (fun value -> String value) values)
let binary first last operator left right =
  make "binary" first last [("operator", operator); ("left", left.syntax);
                            ("right", right.syntax)] [left; right]
%}

%token MODULE PUBLIC NAT BOOL LET RETURN IF ELSE TRUE FALSE
%token LPAREN RPAREN LBRACE RBRACE SEMICOLON COMMA EQUAL PLUS STAR EQ LE EOF
%token <string> IDENT DECIMAL
%token PRIVATE INTERNAL ASYNC RECORD STRUCT UNION INTERFACE TRAIT IMPL IMPORT ALIAS NAMESPACE AS
%token OWNED MOVE IN REF GHOST TRACKED SCOPED REGION CAPTURES GRADE DOMAIN
%token REQUIRES ENSURES RESTORES WHERE EFFECTS INVARIANT DECREASES PROGRESS
%token VIEW GROWS TYPE PREDICATE OPERATION PROOF
%token EFFECT RESUMES HANDLE SHALLOW WITH RESUME DISPOSE REHANDLE
%token AWAIT SCOPE SPAWN COMMIT ON CANCEL VAR FOR WHILE MATCH CASE BREAK CONTINUE
%token DEFINITION THEOREM LEMMA INDUCTIVE COINDUCTIVE UNIVERSE FORALL EXISTS ASSERT CALC
%token MACHINE HARDWARE STATE REGISTER TRANSITION RULE GUARD WHEN NEXT SCHEDULE CYCLE
%token FN FNMUT FNONCE IS CARRIER ZERO ONE ADD MUL ADMITS INTERPRET LAWS
%token LBRACKET RBRACKET DOT COLON AT QUESTION RANGE ARROW FATARROW IMPLIES IFF
%token MINUS SLASH PERCENT LT GT GE NE AND OR NOT AMP BAR CARET TILDE
%token PLUS_ASSIGN MINUS_ASSIGN STAR_ASSIGN SLASH_ASSIGN MOD_ASSIGN
%token GENERIC_OPEN
%token ANNOTATION_OPEN
%token <string * string> NUMBER
%token <string> LIFETIME STRING CHARACTER HOLE ANNOTATION_NAME
%start <Ast.node> file
%start <Ast.node> surface_file

%%

file:
  MODULE module_name=name SEMICOLON functions=nonempty_list(function_decl) EOF
    { make "file" $startpos $endpos(functions)
        [("name", module_name); ("functions", array functions)] functions }

name:
  spelling=IDENT { name $startpos $endpos spelling }

value_type:
  NAT { make "type" $startpos $endpos [("name", String "Nat")] [] }
| BOOL { make "type" $startpos $endpos [("name", String "bool")] [] }

function_decl:
  PUBLIC result=value_type function_name=name LPAREN
  parameters=separated_list(COMMA, parameter) RPAREN body=block
    { make "function" $startpos $endpos
        [("name", function_name); ("result", result.syntax);
         ("parameters", array parameters); ("body", body.syntax)]
        (result :: body :: parameters) }

parameter:
  parameter_type=value_type parameter_name=name
    { make "parameter" $startpos $endpos
        [("name", parameter_name); ("type", parameter_type.syntax)] [parameter_type] }

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

exit:
  RETURN value=expression SEMICOLON
    { make "return" $startpos $endpos [("value", value.syntax)] [value] }
| IF LPAREN condition=expression RPAREN yes=block ELSE no=block
    { make "if" $startpos $endpos
        [("condition", condition.syntax); ("then", yes.syntax); ("else", no.syntax)]
        [condition; yes; no] }

expression:
  value=sum { value }
| left=sum EQ right=sum
    { make "binary" $startpos $endpos
        [("operator", name $startpos($2) $endpos($2) "==");
         ("left", left.syntax); ("right", right.syntax)] [left; right] }
| left=sum LE right=sum
    { make "binary" $startpos $endpos
        [("operator", name $startpos($2) $endpos($2) "<=");
         ("left", left.syntax); ("right", right.syntax)] [left; right] }

sum:
  value=product { value }
| left=sum PLUS right=product
    { make "binary" $startpos $endpos
        [("operator", name $startpos($2) $endpos($2) "+");
         ("left", left.syntax); ("right", right.syntax)] [left; right] }

product:
  value=atom { value }
| left=product STAR right=atom
    { make "binary" $startpos $endpos
        [("operator", name $startpos($2) $endpos($2) "*");
         ("left", left.syntax); ("right", right.syntax)] [left; right] }

atom:
  value=DECIMAL { make "nat" $startpos $endpos [("value", String value)] [] }
| TRUE { make "bool" $startpos $endpos [("value", Boolean true)] [] }
| FALSE { make "bool" $startpos $endpos [("value", Boolean false)] [] }
| value=name { make "name" $startpos $endpos [("name", value)] [] }
| callee=name LPAREN arguments=separated_list(COMMA, expression) RPAREN
    { make "call" $startpos $endpos
        [("callee", callee); ("arguments", array arguments)] arguments }
| LPAREN value=expression RPAREN
    { make "group" $startpos $endpos [("value", value.syntax)] [value] }

/* The wider syntax is deliberately separate from the frozen pure AST entry. */
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

s_modifiers:
  values=list(s_modifier) { values }

s_modifier:
  PUBLIC { "public" } | PRIVATE { "private" } | INTERNAL { "internal" }
| ASYNC { "async" }

s_declaration:
  modifiers=s_modifiers declaration=s_decl
    { { declaration with syntax = (match declaration.syntax with
        Object fields -> Object (List.map (fun (key, value) -> if key = "span" then (key, offsets $symbolstartpos $endpos) else (key, value)) fields @ [("modifiers", strings modifiers)]) | value -> value) } }

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
  parameters=separated_list(COMMA, s_parameter) RPAREN contracts=list(s_contract) tail=s_record_tail
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
  parameters=separated_list(COMMA, s_parameter) RPAREN contracts=list(s_contract)
  definition=option(s_value_definition) SEMICOLON
    { make "predicate" $startpos $endpos [("name", predicate_name); ("generics", array generics);
        ("parameters", array parameters); ("contracts", array contracts); ("definition", optional definition)]
        (generics @ parameters @ contracts @ children definition) }
| OPERATION result=s_type operation_name=s_identifier generics=s_generics LPAREN
  parameters=separated_list(COMMA, s_parameter) RPAREN contracts=list(s_contract) SEMICOLON
    { make "operation" $startpos $endpos [("name", operation_name); ("result", result.syntax);
        ("generics", array generics); ("parameters", array parameters); ("contracts", array contracts)]
        (result :: generics @ parameters @ contracts) }
| PROOF proof_name=s_identifier SEMICOLON
    { make "proof_signature" $startpos $endpos [("name", proof_name)] [] }
| UNIVERSE universe=s_identifier SEMICOLON
    { make "universe" $startpos $endpos [("name", universe)] [] }
| DEFINITION result=s_type definition_name=s_identifier generics=s_generics LPAREN
  parameters=separated_list(COMMA, s_parameter) RPAREN contracts=list(s_contract) EQUAL value=s_expression SEMICOLON
    { make "definition" $startpos $endpos [("name", definition_name); ("result", result.syntax);
        ("generics", array generics); ("parameters", array parameters); ("contracts", array contracts);
        ("value", value.syntax)] (result :: value :: generics @ parameters @ contracts) }
| kind=s_theorem_kind theorem_name=s_identifier generics=s_generics LPAREN
  parameters=separated_list(COMMA, s_parameter) RPAREN COLON proposition=s_expression body=s_theorem_body
    { make kind $startpos $endpos [("name", theorem_name); ("generics", array generics);
        ("parameters", array parameters); ("proposition", proposition.syntax); ("body", optional body)]
        (proposition :: generics @ parameters @ children body) }
| kind=s_storage_kind value_type=s_type storage_name=s_identifier EQUAL value=s_expression SEMICOLON
    { make kind $startpos $endpos [("name", storage_name); ("type", value_type.syntax);
        ("value", value.syntax)] [value_type; value] }
| kind=s_rule_kind rule_name=s_identifier LPAREN parameters=separated_list(COMMA, s_parameter) RPAREN
  guard=option(s_guard) body=s_block
    { make kind $startpos $endpos [("name", rule_name); ("parameters", array parameters);
        ("guard", optional guard); ("body", body.syntax)] (body :: parameters @ children guard) }
| SCHEDULE schedule_name=s_identifier LBRACE rules=list(s_schedule_entry) RBRACE
    { make "schedule" $startpos $endpos [("name", schedule_name); ("rules", array rules)] rules }
| CYCLE value=s_expression SEMICOLON
    { make "cycle" $startpos $endpos [("value", value.syntax)] [value] }
| result=s_type function_name=s_identifier generics=s_generics LPAREN
  parameters=separated_list(COMMA, s_parameter) RPAREN contracts=list(s_contract)
  body=s_function_body cancel=option(s_cancel)
    { make "function" $startpos $endpos [("name", function_name); ("result", result.syntax);
        ("generics", array generics); ("parameters", array parameters); ("contracts", array contracts);
        ("body", optional body); ("cancel", optional cancel)]
        (result :: generics @ parameters @ contracts @ children body @ children cancel) }
| value_type=s_type field_name=s_identifier grade=option(s_grade) value=option(s_value_definition) SEMICOLON
    { make "field" $startpos $endpos [("name", field_name); ("type", value_type.syntax);
        ("grade", optional grade); ("value", optional value)]
        (value_type :: children grade @ children value) }

s_container_kind:
  STRUCT { "struct" } | INTERFACE { "interface" } | TRAIT { "trait" }
| MACHINE { "machine" } | HARDWARE { "hardware" }
s_sum_kind:
  UNION { "union" } | INDUCTIVE { "inductive" } | COINDUCTIVE { "coinductive" }
s_theorem_kind:
  THEOREM { "theorem" } | LEMMA { "lemma" }
s_theorem_body:
  SEMICOLON { None } | PROOF body=s_block { Some body }
s_storage_kind:
  STATE { "state" } | REGISTER { "register" }
s_rule_kind:
  TRANSITION { "transition" } | RULE { "rule" }
s_guard:
  WHEN LPAREN value=s_expression RPAREN { value }
| GUARD value=s_expression { value }
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
s_cancel:
  ON CANCEL body=s_block { body }
s_constructor:
  constructor_name=s_identifier LPAREN parameters=separated_list(COMMA, s_parameter) RPAREN
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
  result=s_type operation_name=s_identifier generics=s_generics LPAREN parameters=separated_list(COMMA, s_parameter) RPAREN
  resumes=option(s_resumes) contracts=list(s_contract) SEMICOLON
    { make "effect_operation" $startpos $endpos [("name", operation_name); ("result", result.syntax);
        ("generics", array generics); ("parameters", array parameters); ("resumes", optional resumes);
        ("contracts", array contracts)] (result :: generics @ parameters @ children resumes @ contracts) }
s_resumes:
  RESUMES LPAREN value=s_expression RPAREN { value }

s_generics:
  { [] } | LT values=separated_nonempty_list(COMMA, s_generic_parameter) GT { values }
s_generic_parameter:
  generic_name=s_identifier kind=option(s_kind_annotation)
    { make "generic_parameter" $startpos $endpos [("mode", String "type"); ("name", generic_name);
        ("type", optional kind)] (children kind) }
| GHOST value_type=s_type generic_name=s_identifier
    { make "generic_parameter" $startpos $endpos [("mode", String "ghost"); ("name", generic_name);
        ("type", value_type.syntax)] [value_type] }
| REGION lifetime=LIFETIME
    { make "generic_parameter" $startpos $endpos [("mode", String "region");
        ("name", name $startpos(lifetime) $endpos(lifetime) lifetime); ("type", Null)] [] }
| EFFECT generic_name=s_identifier
    { make "generic_parameter" $startpos $endpos [("mode", String "effect"); ("name", generic_name); ("type", Null)] [] }
| CAPTURES generic_name=s_identifier
    { make "generic_parameter" $startpos $endpos [("mode", String "captures"); ("name", generic_name); ("type", Null)] [] }
| GRADE generic_name=s_identifier COLON value_type=s_type
    { make "generic_parameter" $startpos $endpos [("mode", String "grade"); ("name", generic_name);
        ("type", value_type.syntax)] [value_type] }
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
  OWNED { "owned" } | IN { "in" } | REF { "ref" } | GHOST { "ghost" }
| TRACKED { "tracked" } | SCOPED { "scoped" }
s_loan_lifetime:
  LT value=LIFETIME GT
    { make "lifetime" $startpos $endpos [("name", name $startpos(value) $endpos(value) value)] [] }
s_type_atom:
  type_name=s_path arguments=s_type_arguments
    { make "type" $startpos $endpos [("name", type_name); ("arguments", array arguments)] arguments }
| value=s_computed_type { value }
| s_open_paren RPAREN { make "unit_type" $startpos $endpos [] [] }
| s_open_paren value=s_type RPAREN { make "group_type" $startpos $endpos [("type", value.syntax)] [value] }
| s_open_paren first=s_type COMMA rest=separated_nonempty_list(COMMA, s_type) RPAREN
    { make "tuple_type" $startpos $endpos [("types", array (first :: rest))] (first :: rest) }
s_computed_type:
  TYPE LBRACKET value=s_expression RBRACKET
    { make "computed_type" $startpos $endpos [("value", value.syntax)] [value] }
s_open_paren:
  LPAREN { () } | ANNOTATION_OPEN { () }
s_function_type:
  mode=s_function_mode generics=s_generics LPAREN parameters=separated_list(COMMA, s_parameter) RPAREN ARROW result=s_nonfunction_type
  captures=option(s_capture_type) effects=option(s_type_effects) contracts=option(s_callable_contracts)
    { let contracts = match contracts with None -> [] | Some values -> values in
      make "function_type" $startpos $endpos [("mode", String mode); ("generics", array generics); ("parameters", array parameters);
        ("result", result.syntax); ("captures", optional captures);
        ("effects", (match effects with None -> Array [] | Some values -> array values));
        ("contracts", array contracts)]
        (result :: generics @ parameters @ children captures @ contracts @ (match effects with None -> [] | Some values -> values)) }
s_callable_contracts:
  WITH LBRACE contracts=list(terminated(s_contract, SEMICOLON)) RBRACE { contracts }
s_function_mode:
  FN { "Fn" } | FNMUT { "FnMut" } | FNONCE { "FnOnce" }
s_capture_type:
  CAPTURES capture=s_path { make "capture" $startpos $endpos [("name", capture)] [] }
s_type_effects:
  EFFECTS LPAREN effects=separated_list(COMMA, s_type) RPAREN { effects }
s_type_arguments:
  { [] } | LT values=separated_nonempty_list(COMMA, s_type_argument) GT { values }
s_type_argument:
  value=s_generic_type { value }
| value=s_operator_value { value }
| TYPE value=s_type { make "type_argument" $startpos $endpos [("type", value.syntax)] [value] }
| value=s_literal { value }
| value=s_hole { value }
| value=LIFETIME { make "lifetime" $startpos $endpos [("name", name $startpos $endpos value)] [] }
| LPAREN value=s_expression RPAREN { make "group" $startpos $endpos [("value", value.syntax)] [value] }
/* Bare parentheses in generic arguments remain value syntax. Structural types
   have an explicit `type` introducer; legacy parenthesized callables are distinct. */
s_generic_type:
  value=s_modified_type(s_generic_type_atom) { value }
s_generic_type_atom:
  type_name=s_path arguments=s_type_arguments
    { make "type" $startpos $endpos [("name", type_name); ("arguments", array arguments)] arguments }
| value=s_computed_type { value }
| value=s_function_type { value }
| LPAREN value=s_function_type RPAREN { make "group_type" $startpos $endpos [("type", value.syntax)] [value] }
s_parameter:
  value_type=s_type parameter_name=option(s_parameter_name) grade=option(s_grade)
    { make "parameter" $startpos $endpos [("name", (match parameter_name with None -> Null | Some value -> value));
        ("type", value_type.syntax); ("grade", optional grade)] (value_type :: children grade) }
s_parameter_name:
  value=s_identifier { value } | HANDLE { name $startpos $endpos "handle" }
s_grade:
  AT value=s_expression { value }
s_contract:
  value=s_obligation { value }
| EFFECTS values=separated_nonempty_list(COMMA, s_expression)
    { make "effects" $startpos $endpos [("values", array values)] values }
s_obligation:
  role=s_contract_role value=s_expression
    { make "contract" $startpos $endpos [("role", String role); ("value", value.syntax)] [value] }
s_contract_role:
  REQUIRES { "requires" } | ENSURES { "ensures" } | RESTORES { "restores" }
| WHERE { "where" } | INVARIANT { "invariant" } | DECREASES { "decreases" } | PROGRESS { "progress" }

s_block:
  LBRACE statements=list(s_statement) RBRACE
    { make "block" $startpos $endpos [("statements", array statements)] statements }

/* Matched and unmatched statements make nearest-else association structural. */
s_statement:
  value=s_closed_statement { value } | value=s_open_statement { value }
s_closed_statement:
  value=s_simple_statement { value }
| IF s_open_paren condition=s_expression RPAREN yes=s_closed_statement ELSE no=s_closed_statement
    { make "if" $startpos $endpos [("condition", condition.syntax); ("then", yes.syntax); ("else", no.syntax)] [condition; yes; no] }
s_open_statement:
  IF s_open_paren condition=s_expression RPAREN yes=s_statement
    { make "if" $startpos $endpos [("condition", condition.syntax); ("then", yes.syntax); ("else", Null)] [condition; yes] }
| IF s_open_paren condition=s_expression RPAREN yes=s_closed_statement ELSE no=s_open_statement
    { make "if" $startpos $endpos [("condition", condition.syntax); ("then", yes.syntax); ("else", no.syntax)] [condition; yes; no] }
s_simple_statement:
  value=s_block { value }
| WHILE LPAREN condition=s_expression RPAREN contracts=list(s_contract) body=s_block
    { make "while" $startpos $endpos [("condition", condition.syntax); ("contracts", array contracts); ("body", body.syntax)]
        (condition :: body :: contracts) }
| FOR LPAREN LET binding_name=s_identifier IN range=s_expression RPAREN contracts=list(s_contract) body=s_block
    { make "for" $startpos $endpos [("name", binding_name); ("range", range.syntax);
        ("contracts", array contracts); ("body", body.syntax)] (range :: body :: contracts) }

| kind=s_local_kind binding_name=s_identifier grade=option(s_grade) EQUAL value=s_expression SEMICOLON
    { make kind $startpos $endpos [("name", binding_name); ("type", Null);
        ("grade", optional grade); ("value", value.syntax)] (value :: children grade) }
| kind=s_local_kind value_type=s_annotation_type binding_name=s_identifier grade=option(s_grade) EQUAL value=s_expression SEMICOLON
    { make kind $startpos $endpos [("name", binding_name); ("type", value_type.syntax);
        ("grade", optional grade); ("value", value.syntax)] (value_type :: value :: children grade) }
| kind=s_local_kind pattern=s_local_pattern EQUAL value=s_expression SEMICOLON
    { make (kind ^ "_pattern") $startpos $endpos [("pattern", pattern.syntax); ("value", value.syntax)] [pattern; value] }
| value_type=s_annotation_type binding_name=s_identifier grade=option(s_grade) EQUAL value=s_expression SEMICOLON
    { make "typed_local" $startpos $endpos [("name", binding_name);
        ("type", value_type.syntax); ("grade", optional grade); ("value", value.syntax)]
        (value_type :: value :: children grade) }
| RETURN value=option(s_expression) SEMICOLON
    { make "return" $startpos $endpos [("value", optional value)] (children value) }
| BREAK SEMICOLON { make "break" $startpos $endpos [] [] }
| CONTINUE SEMICOLON { make "continue" $startpos $endpos [] [] }
| PROOF body=s_block { make "proof" $startpos $endpos [("body", body.syntax)] [body] }
| ASSERT value=s_expression SEMICOLON { make "assert" $startpos $endpos [("value", value.syntax)] [value] }
| CALC body=s_block { make "calc" $startpos $endpos [("body", body.syntax)] [body] }
| SCOPE LPAREN values=separated_list(COMMA, s_expression) RPAREN body=s_block
    { make "scope" $startpos $endpos [("resources", array values); ("body", body.syntax)] (body :: values) }
| MATCH LPAREN value=s_expression RPAREN motive=option(s_match_motive) LBRACE cases=nonempty_list(s_match_case) RBRACE
    { make "match" $startpos $endpos [("value", value.syntax); ("motive", optional motive);
        ("cases", array cases)] (value :: children motive @ cases) }
| parts=s_empty_match
    { let value, motive = parts in
      make "match" $startpos $endpos [("value", value.syntax); ("motive", optional motive);
        ("cases", Array [])] (value :: children motive) }
| NEXT target=s_postfix EQUAL value=s_expression SEMICOLON
    { make "next" $startpos $endpos [("target", target.syntax); ("value", value.syntax)] [target; value] }
| target=s_expression operator=s_assignment value=s_expression SEMICOLON
    { make "assignment" $startpos $endpos [("target", target.syntax); ("operator", operator); ("value", value.syntax)] [target; value] }
| value=s_expression SEMICOLON
    { make "expression_statement" $startpos $endpos [("value", value.syntax)] [value] }
s_annotation_type:
  value=s_modified_type(s_annotation_type_atom) { value }
s_annotation_type_atom:
  type_name=s_annotation_path arguments=s_type_arguments
    { make "type" $startpos $endpos [("name", type_name); ("arguments", array arguments)] arguments }
| value=s_computed_type { value }
| value=s_function_type { value }
| ANNOTATION_OPEN RPAREN { make "unit_type" $startpos $endpos [] [] }
| ANNOTATION_OPEN value=s_type RPAREN { make "group_type" $startpos $endpos [("type", value.syntax)] [value] }
| ANNOTATION_OPEN first=s_type COMMA rest=separated_nonempty_list(COMMA, s_type) RPAREN
    { make "tuple_type" $startpos $endpos [("types", array (first :: rest))] (first :: rest) }
s_annotation_path:
  first=ANNOTATION_NAME rest=list(s_path_segment)
    { name $startpos $endpos (String.concat "." (first :: rest)) }
s_path_segment:
  DOT value=s_member_identifier
    { match value with Object fields -> (match List.assoc "text" fields with String text -> text | _ -> "") | _ -> "" }
s_local_kind:
  LET { "let" } | VAR { "var" }
s_assignment:
  EQUAL { name $startpos $endpos "=" } | PLUS_ASSIGN { name $startpos $endpos "+=" }
| MINUS_ASSIGN { name $startpos $endpos "-=" } | STAR_ASSIGN { name $startpos $endpos "*=" }
| SLASH_ASSIGN { name $startpos $endpos "/=" } | MOD_ASSIGN { name $startpos $endpos "%=" }
s_match_case:
  CASE pattern=s_pattern COLON statements=list(s_statement)
    { make "case" $startpos $endpos [("pattern", pattern.syntax); ("statements", array statements)] (pattern :: statements) }
s_match_motive:
  AS scrutinee=s_identifier COLON value_type=s_type
    { make "match_motive" $startpos $endpos [("name", scrutinee); ("type", value_type.syntax)] [value_type] }
s_match_expression_case:
  CASE pattern=s_pattern FATARROW value=s_expression SEMICOLON
    { make "expression_case" $startpos $endpos [("pattern", pattern.syntax); ("value", value.syntax)] [pattern; value] }
/* Sharing the empty prefix avoids competing empty case-list reductions. Keep
   value elimination at the full-expression boundary, like lambdas/type values. */
s_empty_match:
  MATCH LPAREN value=s_expression RPAREN motive=option(s_match_motive) LBRACE RBRACE
    { value, motive }
s_pattern:
  LET binding_name=s_identifier { make "binding_pattern" $startpos $endpos [("name", binding_name)] [] }
| constructor_name=s_path arguments=option(s_pattern_arguments)
    { let values = match arguments with None -> [] | Some values -> values in
      let wildcard = match constructor_name, arguments with
        | Object fields, None -> List.assoc "text" fields = String "_" | _ -> false in
      if wildcard then make "wildcard_pattern" $startpos $endpos [] []
      else make "constructor_pattern" $startpos $endpos [("name", constructor_name); ("arguments", array values)] values }
| value=s_product_pattern { value }
| TRUE { make "bool_pattern" $startpos $endpos [("value", Boolean true)] [] }
| FALSE { make "bool_pattern" $startpos $endpos [("value", Boolean false)] [] }
| value=DECIMAL { make "nat_pattern" $startpos $endpos [("value", String value); ("suffix", String "")] [] }
| value=NUMBER { let digits, suffix = value in make "nat_pattern" $startpos $endpos [("value", String digits); ("suffix", String suffix)] [] }
| value=STRING { make "string_pattern" $startpos $endpos [("value", String value)] [] }
| value=CHARACTER { make "character_pattern" $startpos $endpos [("value", String value)] [] }
s_pattern_arguments:
  LPAREN values=separated_list(COMMA, s_pattern) RPAREN { values }
/* A bare local name stays an inferred binder. Constructor elimination has an
   explicit argument list, while nested patterns reuse the general grammar. */
s_local_pattern:
  value=s_product_pattern { value }
| constructor_name=s_qualified_name(s_value_identifier) values=s_pattern_arguments
    { make "constructor_pattern" $startpos $endpos
        [("name", constructor_name); ("arguments", array values)] values }
s_product_pattern:
  LPAREN RPAREN { make "unit_pattern" $startpos $endpos [] [] }
| LPAREN value=s_pattern RPAREN
    { make "group_pattern" $startpos $endpos [("pattern", value.syntax)] [value] }
| LPAREN first=s_pattern COMMA rest=separated_nonempty_list(COMMA, s_pattern) RPAREN
    { make "tuple_pattern" $startpos $endpos [("patterns", array (first :: rest))] (first :: rest) }

s_expression:
  value=s_implication { value }
| parts=s_empty_match
    { let value, motive = parts in
      make "match_expression" $startpos $endpos [("value", value.syntax); ("motive", optional motive);
        ("cases", Array [])] (value :: children motive) }
| TYPE value=s_nonfunction_type
    { make "type_expression" $startpos $endpos [("type", value.syntax)] [value] }
| signature=s_function_type FATARROW body=s_lambda_body
    { make "typed_lambda" $startpos $endpos [("signature", signature.syntax); ("body", body.syntax)] [signature; body] }
| FORALL LPAREN parameters=separated_nonempty_list(COMMA, s_parameter) RPAREN FATARROW value=s_expression
    { make "quantifier" $startpos $endpos [("quantifier", String "forall"); ("parameters", array parameters); ("value", value.syntax)] (value :: parameters) }
| EXISTS LPAREN parameters=separated_nonempty_list(COMMA, s_parameter) RPAREN FATARROW value=s_expression
    { make "quantifier" $startpos $endpos [("quantifier", String "exists"); ("parameters", array parameters); ("value", value.syntax)] (value :: parameters) }
| LPAREN parameters=s_lambda_parameters RPAREN FATARROW body=s_lambda_body
    { make "lambda" $startpos $endpos [("parameters", array parameters); ("body", body.syntax)] (body :: parameters) }
| LPAREN RPAREN FATARROW body=s_lambda_body
    { make "lambda" $startpos $endpos [("parameters", Array []); ("body", body.syntax)] [body] }
s_lambda_parameters:
  parameters=separated_nonempty_list(COMMA, s_lambda_parameter) { parameters }
s_lambda_parameter:
  value_type=s_annotation_type parameter_name=s_identifier grade=option(s_grade)
    { make "lambda_parameter" $startpos $endpos [("type", value_type.syntax); ("name", parameter_name);
        ("grade", optional grade)] (value_type :: children grade) }
s_lambda_body:
  value=s_expression { value } | value=s_block { value }
/* Binary operators and their value forms share one spelling and source span.
   Recursive ladders make associativity explicit; comparison/range stay singular. */
s_left_binary(operand, operator):
  value=operand { value }
| left=s_left_binary(operand, operator) op=operator right=operand
    { binary $startpos $endpos op left right }
s_right_binary(operand, operator):
  value=operand { value }
| left=operand op=operator right=s_right_binary(operand, operator)
    { binary $startpos $endpos op left right }
s_implication:
  value=s_right_binary(s_disjunction, s_implication_operator) { value }
s_implication_operator:
  IMPLIES { name $startpos $endpos "==>" } | IFF { name $startpos $endpos "<==>" }
s_disjunction:
  value=s_left_binary(s_conjunction, s_disjunction_operator) { value }
s_disjunction_operator:
  OR { name $startpos $endpos "||" }
s_conjunction:
  value=s_left_binary(s_comparison, s_conjunction_operator) { value }
s_conjunction_operator:
  AND { name $startpos $endpos "&&" }
s_comparison:
  value=s_range { value }
| left=s_range op=s_comparison_operator right=s_range { binary $startpos $endpos op left right }
| value=s_range IS pattern=s_pattern
    { make "is" $startpos $endpos [("value", value.syntax); ("pattern", pattern.syntax)] [value; pattern] }
s_comparison_operator:
  EQ { name $startpos $endpos "==" } | NE { name $startpos $endpos "!=" }
| LT { name $startpos $endpos "<" } | GT { name $startpos $endpos ">" }
| LE { name $startpos $endpos "<=" } | GE { name $startpos $endpos ">=" }
s_range:
  value=s_bit_or { value }
| left=s_bit_or RANGE right=s_bit_or
    { make "range" $startpos $endpos [("start", left.syntax); ("end", right.syntax)] [left; right] }
s_bit_or:
  value=s_left_binary(s_bit_xor, s_bit_or_operator) { value }
s_bit_or_operator:
  BAR { name $startpos $endpos "|" }
s_bit_xor:
  value=s_left_binary(s_bit_and, s_bit_xor_operator) { value }
s_bit_xor_operator:
  CARET { name $startpos $endpos "^" }
s_bit_and:
  value=s_left_binary(s_sum, s_bit_and_operator) { value }
s_bit_and_operator:
  AMP { name $startpos $endpos "&" }
s_sum:
  value=s_left_binary(s_product, s_sum_operator) { value }
s_sum_operator:
  PLUS { name $startpos $endpos "+" } | MINUS { name $startpos $endpos "-" }
s_product:
  value=s_left_binary(s_unary, s_product_operator) { value }
s_product_operator:
  STAR { name $startpos $endpos "*" } | SLASH { name $startpos $endpos "/" }
| PERCENT { name $startpos $endpos "%" }
s_unary:
  value=s_postfix { value }
| operator=s_unary_operator value=s_unary
    { make "unary" $startpos $endpos [("operator", operator); ("value", value.syntax)] [value] }
| DISPOSE value=s_unary
    { make "dispose" $startpos $endpos [("value", value.syntax)] [value] }
| RESUME continuation=s_identifier LPAREN value=s_expression RPAREN
    { make "resume" $startpos $endpos [("continuation", continuation); ("value", value.syntax)] [value] }
%inline s_unary_operator:
  MINUS { name $startpos $endpos "-" } | NOT { name $startpos $endpos "!" }
| TILDE { name $startpos $endpos "~" } | MOVE { name $startpos $endpos "move" }
| IN { name $startpos $endpos "in" } | REF { name $startpos $endpos "ref" }
| AWAIT { name $startpos $endpos "await" } | SPAWN { name $startpos $endpos "spawn" }
| COMMIT { name $startpos $endpos "commit" }
s_postfix:
  value=s_atom { value }
| callee=s_postfix LPAREN arguments=separated_list(COMMA, s_expression) RPAREN
    { make "call" $startpos $endpos [("callee", callee.syntax); ("arguments", array arguments)] (callee :: arguments) }
| value=s_postfix DOT member=s_member_identifier
    { make "member" $startpos $endpos [("value", value.syntax); ("name", member)] [value] }
| value=s_postfix LBRACKET index=s_expression RBRACKET
    { make "index" $startpos $endpos [("value", value.syntax); ("index", index.syntax)] [value; index] }
| value=s_postfix GENERIC_OPEN arguments=separated_nonempty_list(COMMA, s_type_argument) GT
    { make "generic_application" $startpos $endpos [("value", value.syntax); ("arguments", array arguments)] (value :: arguments) }
| value=s_postfix QUESTION
    { make "propagate" $startpos $endpos [("value", value.syntax)] [value] }
s_atom:
  value=s_literal { value }
| value=s_operator_value { value }
| value=s_hole { value }
| value=s_value_identifier { make "name" $startpos $endpos [("name", value)] [] }
| LPAREN RPAREN { make "unit" $startpos $endpos [] [] }
| LPAREN value=s_expression RPAREN { make "group" $startpos $endpos [("value", value.syntax)] [value] }
| LPAREN first=s_expression COMMA rest=separated_nonempty_list(COMMA, s_expression) RPAREN
    { make "tuple" $startpos $endpos [("values", array (first :: rest))] (first :: rest) }
| MATCH LPAREN value=s_expression RPAREN motive=option(s_match_motive)
  LBRACE cases=nonempty_list(s_match_expression_case) RBRACE
    { make "match_expression" $startpos $endpos [("value", value.syntax); ("motive", optional motive);
        ("cases", array cases)] (value :: children motive @ cases) }
| kind=s_handle_kind shallow=option(SHALLOW) LPAREN value=s_expression RPAREN
  capability=option(s_handler_capability) LBRACE clauses=s_handler_clauses RBRACE
    { make kind $startpos $endpos [("shallow", Boolean (shallow <> None));
        ("value", value.syntax); ("capability", (match capability with None -> Null | Some value -> value));
        ("clauses", array clauses)] (value :: clauses) }
s_literal:
  value=DECIMAL { make "nat" $startpos $endpos [("value", String value); ("suffix", String "")] [] }
| value=NUMBER { let digits, suffix = value in make "nat" $startpos $endpos [("value", String digits); ("suffix", String suffix)] [] }
| value=STRING { make "string" $startpos $endpos [("value", String value)] [] }
| value=CHARACTER { make "character" $startpos $endpos [("value", String value)] [] }
| TRUE { make "bool" $startpos $endpos [("value", Boolean true)] [] }
| FALSE { make "bool" $startpos $endpos [("value", Boolean false)] [] }
s_hole:
  value=HOLE { make "hole" $startpos $endpos [("name", name $startpos $endpos value)] [] }
s_handle_kind:
  HANDLE { "handle" } | REHANDLE { "rehandle" }
s_handler_capability:
  AS capability=s_identifier { capability }
s_handler_clauses:
  { [] }
| clause=s_handler_clause { [clause] }
| clause=s_handler_clause COMMA rest=s_handler_clauses { clause :: rest }
s_handler_clause:
  operation_name=s_path LPAREN parameters=separated_list(COMMA, s_identifier) RPAREN WITH
  continuation=s_identifier FATARROW body=s_lambda_body
    { make "operation_clause" $startpos $endpos [("name", operation_name);
        ("parameters", Array parameters); ("continuation", continuation); ("body", body.syntax)] [body] }
| RETURN result=s_identifier FATARROW body=s_lambda_body
    { make "return_clause" $startpos $endpos [("name", result); ("body", body.syntax)] [body] }
| DISPOSE reason=s_identifier FATARROW body=s_lambda_body
    { make "disposal_clause" $startpos $endpos [("name", reason); ("body", body.syntax)] [body] }
s_operator_value:
  LPAREN op=s_symbolic_operator RPAREN
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
