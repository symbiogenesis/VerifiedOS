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
(* Contextual annotation names resolve the lexical ambiguity between a type-first
   binder and comparison. This bounded token-shape probe never resolves names.
   The driver uses Lexing.from_string, so the complete bounded input is buffered. *)
let annotation lexbuf parenthesized =
  let source = lexbuf.Lexing.lex_buffer in
  let length = lexbuf.Lexing.lex_buffer_len in
  let at index = Bytes.get source index in
  let initial = function 'A'..'Z' | 'a'..'z' | '_' -> true | _ -> false in
  let subsequent value = initial value || (value >= '0' && value <= '9') in
  let rec word index = if index < length && subsequent (at index) then word (index + 1) else index in
  let rec comment depth index =
    if depth > Ast.max_delimiter_depth then refuse "limit" lexbuf "annotation comment nesting exceeds 256"
    else if index + 1 >= length then length
    else if at index = '/' && at (index + 1) = '*' then comment (depth + 1) (index + 2)
    else if at index = '*' && at (index + 1) = '/' then
      if depth = 1 then index + 2 else comment (depth - 1) (index + 2)
    else comment depth (index + 1)
  in
  let rec trivia index =
    if index >= length then length
    else match at index with
      | ' ' | '\t' | '\r' | '\n' -> trivia (index + 1)
      | '/' when index + 1 < length && at (index + 1) = '*' -> trivia (comment 1 (index + 2))
      | '/' when index + 1 < length && at (index + 1) = '/' ->
          let rec line current = if current < length && at current <> '\r' && at current <> '\n' then line (current + 1) else current in
          trivia (line (index + 2))
      | _ -> index
  in
  let rec quoted index =
    if index >= length then length
    else match at index with
      | '\\' -> quoted (min length (index + 2))
      | '"' -> index + 1
      | '\r' | '\n' -> length
      | _ -> quoted (index + 1)
  in
  (* A grade or a generic value may contain a callback block. Skip its balanced
     delimiters without interpreting statements or changing lexer positions. *)
  let rec block closing depth index =
    if depth > Ast.max_delimiter_depth then refuse "limit" lexbuf "annotation block nesting exceeds 256"
    else if index >= length then length
    else let index = trivia index in
      if index >= length then length
      else match at index with
        | '"' -> block closing depth (quoted (index + 1))
        | '\'' when index + 2 < length && at (index + 2) = '\'' -> block closing depth (index + 3)
        | '\'' when index + 3 < length && at (index + 1) = '\\' && at (index + 3) = '\'' -> block closing depth (index + 4)
        | '{' -> block ('}' :: closing) (depth + 1) (index + 1)
        | '(' -> block (')' :: closing) (depth + 1) (index + 1)
        | '[' -> block (']' :: closing) (depth + 1) (index + 1)
        | ('}' | ')' | ']') as delimiter ->
            (match closing with
             | expected :: rest when delimiter = expected ->
                 if rest = [] then index + 1 else block rest (depth - 1) (index + 1)
             | _ -> length)
        | _ -> block closing depth (index + 1)
  in
  let rec angles depth parens brackets index =
    if depth > Ast.max_delimiter_depth || parens > Ast.max_delimiter_depth
       || brackets > Ast.max_delimiter_depth then refuse "limit" lexbuf "annotation nesting exceeds 256"
    else if index >= length then length
    else let index = trivia index in
      if index >= length then length
      else match at index with
        | '"' -> angles depth parens brackets (quoted (index + 1))
        | '\'' when index + 2 < length && at (index + 2) = '\'' -> angles depth parens brackets (index + 3)
        | '\'' when index + 3 < length && at (index + 1) = '\\' && at (index + 3) = '\'' -> angles depth parens brackets (index + 4)
        | '(' -> angles depth (parens + 1) brackets (index + 1)
        | ')' when parens > 0 -> angles depth (parens - 1) brackets (index + 1)
        | '[' -> angles depth parens (brackets + 1) (index + 1)
        | ']' when brackets > 0 -> angles depth parens (brackets - 1) (index + 1)
        | '-' when index + 1 < length && at (index + 1) = '>' ->
            angles depth parens brackets (index + 2)
        | '=' when index + 1 < length && at (index + 1) = '>' ->
            angles depth parens brackets (index + 2)
        | '<' when parens = 0 && brackets = 0 -> angles (depth + 1) parens brackets (index + 1)
        | '>' when parens = 0 && brackets = 0 ->
            if depth = 1 then index + 1 else angles (depth - 1) parens brackets (index + 1)
        | '{' -> angles depth parens brackets (block ['}'] 1 (index + 1))
        | ';' | '}' -> length
        | _ -> angles depth parens brackets (index + 1)
  in
  let rec path index =
    let index = trivia index in
    if index < length && at index = '.' then
      let next = trivia (index + 1) in
      if next < length && initial (at next) then path (word next) else length
    else index
  in
  let rec parenthesized_type depth index =
    if depth > Ast.max_delimiter_depth then refuse "limit" lexbuf "annotation nesting exceeds 256"
    else if index >= length then length
    else let index = trivia index in
      if index >= length then length
      else match at index with
        | '"' -> parenthesized_type depth (quoted (index + 1))
        | '\'' when index + 2 < length && at (index + 2) = '\'' -> parenthesized_type depth (index + 3)
        | '\'' when index + 3 < length && at (index + 1) = '\\' && at (index + 3) = '\'' -> parenthesized_type depth (index + 4)
        | '(' -> parenthesized_type (depth + 1) (index + 1)
        | ')' -> if depth = 1 then trivia (index + 1) else parenthesized_type (depth - 1) (index + 1)
        | '{' -> parenthesized_type depth (block ['}'] 1 (index + 1))
        | ';' | '}' -> length
        | _ -> parenthesized_type depth (index + 1)
  in
  let after_type = if parenthesized then parenthesized_type 1 lexbuf.Lexing.lex_curr_pos
    else let after_path = path lexbuf.Lexing.lex_curr_pos in
      (* `<=` and `<==>` are complete operators, never generic openers. *)
      if after_path + 1 < length && at after_path = '<' && at (after_path + 1) <> '='
      then trivia (angles 1 0 0 (after_path + 1)) else after_path in
  let arrow index =
    let index = trivia index in
    index + 1 < length && at index = '=' && at (index + 1) = '>'
  in
  let rec binder_tail parens brackets graded index =
    if parens > Ast.max_delimiter_depth || brackets > Ast.max_delimiter_depth then
      refuse "limit" lexbuf "binder annotation nesting exceeds 256"
    else if index >= length then false
    else let index = trivia index in
      if index >= length then false
      else match at index with
        | '"' -> binder_tail parens brackets graded (quoted (index + 1))
        | '\'' when index + 2 < length && at (index + 2) = '\'' -> binder_tail parens brackets graded (index + 3)
        | '\'' when index + 3 < length && at (index + 1) = '\\' && at (index + 3) = '\'' -> binder_tail parens brackets graded (index + 4)
        | '(' -> binder_tail (parens + 1) brackets graded (index + 1)
        | ')' -> if parens = 0 then arrow (index + 1) else binder_tail (parens - 1) brackets graded (index + 1)
        | '[' -> binder_tail parens (brackets + 1) graded (index + 1)
        | ']' when brackets > 0 -> binder_tail parens (brackets - 1) graded (index + 1)
        | '@' when parens = 0 && brackets = 0 -> binder_tail parens brackets true (index + 1)
        (* A comma may belong to a generic grade argument or a later binder.
           Once inside a grade, keep allowing balanced callback/type blocks. *)
        | ',' when parens = 0 && brackets = 0 -> binder_tail parens brackets graded (index + 1)
        | ('<' | '>' | '!') when index + 1 < length && at (index + 1) = '=' ->
            binder_tail parens brackets graded (index + 2)
        | '=' when index + 1 < length && (at (index + 1) = '=' || at (index + 1) = '>') ->
            binder_tail parens brackets graded (index + 2)
        | '=' when graded && parens = 0 && brackets = 0 -> true
        | '{' when graded || parens > 0 || brackets > 0 ->
            binder_tail parens brackets graded (block ['}'] 1 (index + 1))
        | ';' | '{' | '}' -> false
        | _ -> binder_tail parens brackets graded (index + 1)
  in
  if after_type >= length || not (initial (at after_type)) then false
  else let after_binder = trivia (word after_type) in
    after_binder < length && (match at after_binder with
      | '=' -> after_binder + 1 >= length || (at (after_binder + 1) <> '=' && at (after_binder + 1) <> '>')
      | ')' -> arrow (after_binder + 1)
      | ',' -> binder_tail 0 0 false (after_binder + 1)
      | '@' -> binder_tail 0 0 true (after_binder + 1)
      | _ -> false)
let annotation_name lexbuf = annotation lexbuf false
let identifier state lexbuf =
  let word = Lexing.lexeme lexbuf in
  if not state.surface && pure_reserved word then
    refuse "unsupported" lexbuf ("'" ^ word ^ "' is outside the pure prototype");
  match word with
  | "module" -> MODULE | "public" -> PUBLIC
  | "Nat" -> if state.surface && annotation_name lexbuf then ANNOTATION_NAME word else NAT
  | "bool" -> if state.surface && annotation_name lexbuf then ANNOTATION_NAME word else BOOL
  | "let" -> LET | "return" -> RETURN | "if" -> IF | "else" -> ELSE
  | "true" -> TRUE | "false" -> FALSE
  | _ when not state.surface -> IDENT word
  | "private" -> PRIVATE | "internal" -> INTERNAL | "async" -> ASYNC
  | "record" -> RECORD | "struct" -> STRUCT | "union" -> UNION
  | "interface" -> INTERFACE | "trait" -> TRAIT | "impl" -> IMPL
  | "import" -> IMPORT | "alias" -> ALIAS | "namespace" -> NAMESPACE | "as" -> AS
  | "owned" -> OWNED | "move" -> MOVE | "in" -> IN | "ref" -> REF | "out" -> OUT
  | "null" -> refuse "syntax" lexbuf "absence requires an explicit Option case"
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
  | _ -> if annotation_name lexbuf then ANNOTATION_NAME word else IDENT word
let pure_decimal lexbuf =
  let spelling = Lexing.lexeme lexbuf in
  let count = ref 0 in
  while !count < String.length spelling && spelling.[!count] >= '0' && spelling.[!count] <= '9' do incr count done;
  if !count > Ast.max_literal_digits then refuse "limit" lexbuf "literal exceeds 256 decimal digits";
  (* Return the decimal token alone; its suffix must receive the original pure
     keyword classification and position on the next lexer invocation. *)
  lexbuf.Lexing.lex_curr_pos <- lexbuf.Lexing.lex_start_pos + !count;
  lexbuf.Lexing.lex_curr_p <- { lexbuf.Lexing.lex_curr_p with
    Lexing.pos_cnum = lexbuf.Lexing.lex_start_p.Lexing.pos_cnum + !count };
  DECIMAL (String.sub spelling 0 !count)
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
  | decimal identifier? { if state.surface then numeric state lexbuf else pure_decimal lexbuf }
  | '"' ([^ '"' '\\' '\r' '\n'] | escape)* '"' { STRING (Lexing.lexeme lexbuf) }
  | '\'' ([^ '\'' '\\' '\r' '\n'] | escape) '\'' { CHARACTER (Lexing.lexeme lexbuf) }
  | '\'' identifier ('.' identifier)* { LIFETIME (Lexing.lexeme lexbuf) }
  | '?' identifier { HOLE (Lexing.lexeme lexbuf) }
  | '(' { opening state lexbuf (if state.surface && annotation lexbuf true then ANNOTATION_OPEN else LPAREN) } | ')' { closing state RPAREN }
  | '{' { opening state lexbuf LBRACE } | '}' { closing state RBRACE }
  | '[' { opening state lexbuf LBRACKET } | ']' { closing state RBRACKET }
  | ';' { SEMICOLON } | ',' { COMMA } | '.' { DOT } | ':' { COLON }
  | "??" | "?." {
      if state.surface then refuse "syntax" lexbuf "implicit optional operators are not supported";
      (* Preserve the pure entry's original one-character tokenization. *)
      lexbuf.Lexing.lex_curr_pos <- lexbuf.Lexing.lex_start_pos + 1;
      lexbuf.Lexing.lex_curr_p <- { lexbuf.Lexing.lex_curr_p with
        Lexing.pos_cnum = lexbuf.Lexing.lex_start_p.Lexing.pos_cnum + 1 };
      QUESTION }
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
