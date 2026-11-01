(* SPDX-License-Identifier: Apache-2.0 *)
{
open Parser

type state = { mutable delimiters : int; surface : bool }
let create ?(surface=false) () = { delimiters = 0; surface }
let refuse kind lexbuf message =
  raise (Ast.Refusal (kind, Lexing.lexeme_start lexbuf, message))
let opening state lexbuf token =
  state.delimiters <- state.delimiters + 1;
  if state.delimiters > Ast.max_delimiter_depth then
    refuse "limit" lexbuf (Printf.sprintf "delimiter nesting exceeds %d" Ast.max_delimiter_depth);
  token
let closing state token = state.delimiters <- max 0 (state.delimiters - 1); token
let pure_reserved = function
  | "fn" | "Bool" | "async" | "await" | "effect" | "effects" | "handler"
  | "handle" | "resume" | "dispose" | "mut" | "var" | "unsafe" | "borrow"
  | "requires" | "ensures" | "restores" | "ghost" | "tracked" | "grade"
  | "proof" | "owned" | "move" | "ref" | "in" | "captures" | "scope"
  | "spawn" | "commit" | "on" | "cancel" | "region" | "view" | "union" -> true
  | _ -> false
let identifier state lexbuf =
  let word = Lexing.lexeme lexbuf in
  if not state.surface && pure_reserved word then
    refuse "unsupported" lexbuf ("'" ^ word ^ "' is outside the pure prototype");
  match word with
  | "module" -> MODULE | "public" -> PUBLIC | "Nat" -> NAT | "bool" -> BOOL
  | "let" -> LET | "return" -> RETURN | "if" -> IF | "else" -> ELSE
  | "true" -> TRUE | "false" -> FALSE
  | _ when not state.surface -> IDENT word
  | "private" -> PRIVATE | "internal" -> INTERNAL | "async" -> ASYNC
  | "record" -> RECORD | "struct" -> STRUCT | "union" -> UNION
  | "interface" -> INTERFACE | "trait" -> TRAIT | "impl" -> IMPL
  | "import" -> IMPORT | "alias" -> ALIAS | "namespace" -> NAMESPACE
  | "owned" -> OWNED | "move" -> MOVE | "in" -> IN | "ref" -> REF
  | "ghost" -> GHOST | "tracked" -> TRACKED | "scoped" -> SCOPED
  | "region" -> REGION | "captures" -> CAPTURES | "grade" -> GRADE | "domain" -> DOMAIN
  | "requires" -> REQUIRES | "ensures" -> ENSURES | "restores" -> RESTORES
  | "where" -> WHERE | "effects" -> EFFECTS | "invariant" -> INVARIANT
  | "decreases" -> DECREASES | "progress" -> PROGRESS
  | "view" -> VIEW | "grows" -> GROWS | "type" -> TYPE | "predicate" -> PREDICATE
  | "operation" -> OPERATION | "proof" -> PROOF | "effect" -> EFFECT | "resumes" -> RESUMES
  | "handle" -> HANDLE | "shallow" -> SHALLOW | "with" -> WITH | "resume" -> RESUME
  | "dispose" -> DISPOSE | "rehandle" -> REHANDLE | "await" -> AWAIT
  | "scope" -> SCOPE | "spawn" -> SPAWN | "commit" -> COMMIT | "on" -> ON | "cancel" -> CANCEL
  | "var" -> VAR | "for" -> FOR | "while" -> WHILE | "match" -> MATCH | "case" -> CASE
  | "break" -> BREAK | "continue" -> CONTINUE | "definition" -> DEFINITION
  | "theorem" -> THEOREM | "lemma" -> LEMMA | "inductive" -> INDUCTIVE
  | "coinductive" -> COINDUCTIVE | "universe" -> UNIVERSE | "forall" -> FORALL
  | "exists" -> EXISTS | "assert" -> ASSERT | "calc" -> CALC
  | "machine" -> MACHINE | "hardware" -> HARDWARE | "state" -> STATE | "register" -> REGISTER
  | "transition" -> TRANSITION | "rule" -> RULE | "guard" -> GUARD | "when" -> WHEN
  | "next" -> NEXT | "schedule" -> SCHEDULE | "cycle" -> CYCLE
  | "Fn" -> FN | "FnMut" -> FNMUT | "FnOnce" -> FNONCE | "is" -> IS
  | "carrier" -> CARRIER | "zero" -> ZERO | "one" -> ONE | "add" -> ADD | "mul" -> MUL
  | "admits" -> ADMITS | "interpret" -> INTERPRET | "laws" -> LAWS
  | _ -> IDENT word
let numeric state lexbuf =
  let spelling = Lexing.lexeme lexbuf in
  let length = String.length spelling in
  let prefix, valid =
    if state.surface && length >= 2 && spelling.[0] = '0' then
      match spelling.[1] with
      | 'x' | 'X' -> 2, (function '0'..'9' | 'a'..'f' | 'A'..'F' -> true | _ -> false)
      | 'b' | 'B' when spelling <> "0byte" -> 2, (function '0' | '1' -> true | _ -> false)
      | _ -> 0, (function '0'..'9' -> true | _ -> false)
    else 0, (function '0'..'9' -> true | _ -> false)
  in
  let index = ref prefix in
  while !index < length && valid spelling.[!index] do incr index done;
  if !index = prefix then refuse "syntax" lexbuf "numeric base prefix requires digits";
  if !index - prefix > Ast.max_literal_digits then refuse "limit" lexbuf "literal exceeds 256 digits";
  let digits = String.sub spelling 0 !index in
  let suffix = String.sub spelling !index (length - !index) in
  if suffix <> "" && not state.surface then refuse "syntax" lexbuf "unexpected literal suffix";
  if suffix <> "" && (suffix.[0] >= '0' && suffix.[0] <= '9') then
    refuse "syntax" lexbuf "invalid digit for numeric base";
  if suffix = "" && prefix = 0 then DECIMAL digits else NUMBER (digits, suffix)
}
let identifier = ['A'-'Z' 'a'-'z' '_'] ['A'-'Z' 'a'-'z' '0'-'9' '_']*
let decimal = ['0'-'9']+
let newline = "\r\n" | '\r' | '\n'
let escape = '\\' ['"' '\'' '\\' 'n' 'r' 't' '0']
rule token state = parse
  | [' ' '\t']+ { token state lexbuf }
  | newline { Lexing.new_line lexbuf; token state lexbuf }
  | "//" [^ '\r' '\n']* { token state lexbuf }
  | "/*" { if not state.surface then refuse "syntax" lexbuf "unexpected character";
             comment state 1 (Lexing.lexeme_start lexbuf) lexbuf; token state lexbuf }
  | identifier { identifier state lexbuf }
  | decimal identifier? { numeric state lexbuf }
  | '"' ([^ '"' '\\' '\r' '\n'] | escape)* '"' { STRING (Lexing.lexeme lexbuf) }
  | '\'' ([^ '\'' '\\' '\r' '\n'] | escape) '\'' { CHARACTER (Lexing.lexeme lexbuf) }
  | '\'' identifier ('.' identifier)* { LIFETIME (Lexing.lexeme lexbuf) }
  | '?' identifier { HOLE (Lexing.lexeme lexbuf) }
  | '(' { opening state lexbuf LPAREN } | ')' { closing state RPAREN }
  | '{' { opening state lexbuf LBRACE } | '}' { closing state RBRACE }
  | '[' { opening state lexbuf LBRACKET } | ']' { closing state RBRACKET }
  | ';' { SEMICOLON } | ',' { COMMA } | '.' { DOT } | ':' { COLON }
  | '@' { AT } | '?' { QUESTION } | ".." { RANGE } | "::<" { GENERIC_OPEN }
  | "==>" { IMPLIES } | "<==>" { IFF } | "=>" { FATARROW } | "->" { ARROW }
  | "==" { EQ } | "<=" { LE } | ">=" { GE } | "!=" { NE }
  | "&&" { AND } | "||" { OR } | "!" { NOT }
  | "&" { AMP } | "|" { BAR } | "^" { CARET } | "~" { TILDE }
  | "+=" { PLUS_ASSIGN } | "-=" { MINUS_ASSIGN } | "*=" { STAR_ASSIGN }
  | "/=" { SLASH_ASSIGN } | "%=" { MOD_ASSIGN }
  | '=' { EQUAL } | '+' { PLUS } | '*' { STAR } | '-' { MINUS }
  | '/' { SLASH } | '%' { PERCENT } | '<' { LT } | '>' { GT }
  | eof { EOF }
  | _ { refuse "syntax" lexbuf "unexpected character" }
and comment state depth start = parse
  | "/*" { if depth >= Ast.max_delimiter_depth then refuse "limit" lexbuf "comment nesting exceeds 256";
             comment state (depth + 1) start lexbuf }
  | "*/" { if depth > 1 then comment state (depth - 1) start lexbuf }
  | newline { Lexing.new_line lexbuf; comment state depth start lexbuf }
  | eof { raise (Ast.Refusal ("syntax", start, "unterminated block comment")) }
  | _ { comment state depth start lexbuf }
