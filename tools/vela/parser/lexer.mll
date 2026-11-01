(* SPDX-License-Identifier: Apache-2.0 *)
{
open Parser

type state = { mutable delimiters : int }

let create () = { delimiters = 0 }

let refuse kind lexbuf message =
  raise (Ast.Refusal (kind, Lexing.lexeme_start lexbuf, message))

let opening state lexbuf token =
  state.delimiters <- state.delimiters + 1;
  if state.delimiters > Ast.max_delimiter_depth then
    refuse "limit" lexbuf "delimiter nesting exceeds 64";
  token

let closing state token =
  state.delimiters <- max 0 (state.delimiters - 1);
  token

let identifier lexbuf =
  match Lexing.lexeme lexbuf with
  | "module" -> MODULE | "public" -> PUBLIC | "Nat" -> NAT | "bool" -> BOOL
  | "let" -> LET | "return" -> RETURN | "if" -> IF | "else" -> ELSE
  | "true" -> TRUE | "false" -> FALSE
  | ("fn" | "Bool" | "async" | "await" | "effect" | "effects" | "handler"
    | "handle" | "resume" | "dispose" | "mut" | "var" | "unsafe" | "borrow"
    | "requires" | "ensures" | "restores" | "ghost" | "tracked" | "grade"
    | "proof" | "owned" | "move" | "ref" | "in" | "captures" | "scope"
    | "spawn" | "commit" | "on" | "cancel" | "region" | "view" | "union") as word ->
      refuse "unsupported" lexbuf ("'" ^ word ^ "' is outside the pure prototype")
  | word -> IDENT word
}

let identifier = ['A'-'Z' 'a'-'z' '_'] ['A'-'Z' 'a'-'z' '0'-'9' '_']*
let decimal = ['0'-'9']+
let newline = "\r\n" | '\r' | '\n'

rule token state = parse
  | [' ' '\t']+ { token state lexbuf }
  | newline { Lexing.new_line lexbuf; token state lexbuf }
  | "//" [^ '\r' '\n']* { token state lexbuf }
  | identifier { identifier lexbuf }
  | decimal {
      let spelling = Lexing.lexeme lexbuf in
      if String.length spelling > Ast.max_literal_digits then
        refuse "limit" lexbuf "literal exceeds 256 decimal digits";
      DECIMAL spelling }
  | '(' { opening state lexbuf LPAREN }
  | ')' { closing state RPAREN }
  | '{' { opening state lexbuf LBRACE }
  | '}' { closing state RBRACE }
  | ';' { SEMICOLON }
  | ',' { COMMA }
  | "==" { EQ }
  | "<=" { LE }
  | '=' { EQUAL }
  | '+' { PLUS }
  | '*' { STAR }
  | eof { EOF }
  | _ { refuse "syntax" lexbuf "unexpected character" }
