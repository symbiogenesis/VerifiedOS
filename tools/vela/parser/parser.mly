/* SPDX-License-Identifier: Apache-2.0 */
%{
open Ast
%}

%token MODULE PUBLIC NAT BOOL LET RETURN IF ELSE TRUE FALSE
%token LPAREN RPAREN LBRACE RBRACE SEMICOLON COMMA EQUAL PLUS STAR EQ LE EOF
%token <string> IDENT DECIMAL
%start <Ast.node> file

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
