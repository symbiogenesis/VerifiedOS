(* SPDX-License-Identifier: Apache-2.0 *)
{
open Parser

type state = {
  mutable delimiters : int;
  surface : bool;
  probe_tokens : int ref;
  generic_probes : (int, bool) Hashtbl.t;
  probe_depth : int;
}
let create ?(surface=false) () = {
  delimiters = 0; surface; probe_tokens = ref 0;
  generic_probes = Hashtbl.create 32; probe_depth = 0;
}
let refuse kind lexbuf message =
  raise (Ast.Refusal (kind, Lexing.lexeme_start lexbuf, message))
let opening state lexbuf token =
  state.delimiters <- state.delimiters + 1;
  if state.delimiters > Ast.max_delimiter_depth then
    refuse "limit" lexbuf (Printf.sprintf "delimiter nesting exceeds %d" Ast.max_delimiter_depth);
  token
let closing state token = state.delimiters <- max 0 (state.delimiters - 1); token
(* Prefix classification reuses the authored generic-argument grammar. Clones
   share only immutable source bytes, memoized decisions and the work budget. *)
let generic_call next state lexbuf =
  let offset = Lexing.lexeme_start lexbuf in
  match Hashtbl.find_opt state.generic_probes offset with
  | Some decision -> decision
  | None ->
      if state.probe_depth >= Ast.max_delimiter_depth then
        refuse "limit" lexbuf "generic-call probe nesting exceeds 256";
      let probe_state = { state with probe_depth = state.probe_depth + 1 } in
      let probe = { lexbuf with Lexing.lex_mem = Array.copy lexbuf.Lexing.lex_mem } in
      let inspect input =
        incr state.probe_tokens;
        if !(state.probe_tokens) > Ast.max_generic_probe_tokens then
          raise (Ast.Refusal ("limit", offset, "generic-call probes exceed 200000 inspected tokens"));
        next probe_state input
      in
      let decision =
        try Parser.generic_call_prefix inspect probe; true with
        | Parser.Error -> false
        | Ast.Refusal ("syntax", _, _) -> false
      in
      Hashtbl.add state.generic_probes offset decision;
      decision
let pure_reserved = function
  | "fn" | "Bool" | "async" | "await" | "effect" | "effects" | "handler"
  | "handle" | "resume" | "dispose" | "mut" | "var" | "unsafe" | "borrow"
  | "requires" | "ensures" | "restores" | "ghost" | "tracked" | "grade"
  | "proof" | "owned" | "move" | "ref" | "in" | "out" | "captures" | "scope"
  | "spawn" | "commit" | "on" | "cancel" | "region" | "view" | "union" | "foreach" -> true
  | _ -> false
let pure_unsupported word =
  let mode = match word with
    | "in" -> Some "a shared read loan" | "ref" -> Some "an initialized exclusive loan"
    | "out" -> Some "an exclusive initialization loan" | "owned" -> Some "consuming ownership"
    | "move" -> Some "an explicit ownership transfer" | _ -> None
  in
  match word, mode with
  | "var", _ -> "'var' declares a mutable binding; let and unmarked type-first bindings are immutable. Local reassignment requires the wider Vela surface; the pure prototype does not support mutation"
  | _, Some requested -> "'" ^ word ^ "' requests " ^ requested ^ "; the pure Nat/bool prototype cannot check ownership, borrowing or resource lifetimes"
  | _ -> "'" ^ word ^ "' is outside the pure prototype"
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
  let rec skip_raw quotes index =
    if index >= length then length
    else if at index = '"' then
      let rec run cursor = if cursor < length && at cursor = '"' then 1 + run (cursor + 1) else 0 in
      let count = run index in
      if count >= quotes then index + count else skip_raw quotes (index + count)
    else skip_raw quotes (index + 1)
  in
  let rec quoted index =
    if index >= length then length
    else match at index with
      | '\\' -> quoted (min length (index + 2))
      | '"' -> index + 1
      | '\r' | '\n' -> length
      | _ -> quoted (index + 1)
  in
  let skip_double_quoted start_quote =
    let rec run cursor = if cursor < length && at cursor = '"' then 1 + run (cursor + 1) else 0 in
    let quotes = run start_quote in
    if quotes >= 3 then skip_raw quotes (start_quote + quotes)
    else if quotes = 2 then start_quote + 2
    else quoted (start_quote + 1)
  in
  (* A grade or a generic value may contain a callback block. Skip its balanced
     delimiters without interpreting statements or changing lexer positions. *)
  let rec block closing depth index =
    if depth > Ast.max_delimiter_depth then refuse "limit" lexbuf "annotation block nesting exceeds 256"
    else if index >= length then length
    else let index = trivia index in
      if index >= length then length
      else match at index with
        | '"' -> block closing depth (skip_double_quoted index)
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
        | '"' -> angles depth parens brackets (skip_double_quoted index)
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
        | '"' -> parenthesized_type depth (skip_double_quoted index)
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
        | '"' -> binder_tail parens brackets graded (skip_double_quoted index)
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
(* Classify a parenthesized lambda telescope from its closing arrow. This probe
   reads bounded bytes only: comments, quoted literals and nested delimiters do
   not move positions or grant an identifier a type. Declaration/pattern
   telescopes followed by the same arrow accept the same opening token. *)
let lambda_open lexbuf =
  let source = lexbuf.Lexing.lex_buffer in
  let length = lexbuf.Lexing.lex_buffer_len in
  let at index = Bytes.get source index in
  let rec comment depth index =
    if depth > Ast.max_delimiter_depth then refuse "limit" lexbuf "lambda comment nesting exceeds 256"
    else if index + 1 >= length then length
    else if at index = '/' && at (index + 1) = '*' then comment (depth + 1) (index + 2)
    else if at index = '*' && at (index + 1) = '/' then
      if depth = 1 then index + 2 else comment (depth - 1) (index + 2)
    else comment depth (index + 1)
  in
  let rec trivia index =
    if index >= length then length else match at index with
      | ' ' | '\t' | '\r' | '\n' -> trivia (index + 1)
      | '/' when index + 1 < length && at (index + 1) = '*' -> trivia (comment 1 (index + 2))
      | '/' when index + 1 < length && at (index + 1) = '/' ->
          let rec line current = if current < length && at current <> '\r' && at current <> '\n' then line (current + 1) else current in
          trivia (line (index + 2))
      | _ -> index
  in
  let rec skip_raw quotes index =
    if index >= length then length
    else if at index = '"' then
      let rec run cursor = if cursor < length && at cursor = '"' then 1 + run (cursor + 1) else 0 in
      let count = run index in
      if count >= quotes then index + count else skip_raw quotes (index + count)
    else skip_raw quotes (index + 1)
  in
  let rec quoted quote index =
    if index >= length then length else match at index with
      | '\\' -> quoted quote (min length (index + 2))
      | value when value = quote -> index + 1
      | '\r' | '\n' -> length
      | _ -> quoted quote (index + 1)
  in
  let skip_double_quoted start_quote =
    let rec run cursor = if cursor < length && at cursor = '"' then 1 + run (cursor + 1) else 0 in
    let quotes = run start_quote in
    if quotes >= 3 then skip_raw quotes (start_quote + quotes)
    else if quotes = 2 then start_quote + 2
    else quoted '"' (start_quote + 1)
  in
  let rec balanced stack depth index =
    if depth > Ast.max_delimiter_depth then refuse "limit" lexbuf "lambda delimiter nesting exceeds 256"
    else let index = trivia index in
      if index >= length then false else match at index with
        | '"' -> balanced stack depth (skip_double_quoted index)
        | '\'' when index + 2 < length && at (index + 2) = '\'' ->
            balanced stack depth (index + 3)
        | '\'' when index + 3 < length && at (index + 1) = '\\' && at (index + 3) = '\'' ->
            balanced stack depth (index + 4)
        | '(' -> balanced (')' :: stack) (depth + 1) (index + 1)
        | '[' -> balanced (']' :: stack) (depth + 1) (index + 1)
        | '{' -> balanced ('}' :: stack) (depth + 1) (index + 1)
        | (')' | ']' | '}') as closing ->
            (match stack with
             | expected :: rest when expected = closing ->
                 if rest = [] then
                   let after = trivia (index + 1) in
                   after + 1 < length && at after = '=' && at (after + 1) = '>'
                 else balanced rest (depth - 1) (index + 1)
             | _ -> false)
        | _ -> balanced stack depth (index + 1)
  in
  balanced [')'] 1 lexbuf.Lexing.lex_curr_pos

let annotation_name lexbuf = annotation lexbuf false
let identifier state lexbuf =
  let word = Lexing.lexeme lexbuf in
  if not state.surface && pure_reserved word then
    refuse "unsupported" lexbuf (pure_unsupported word);
  match word with
  | "module" -> MODULE | "public" -> PUBLIC
  | "Nat" -> if state.surface && annotation_name lexbuf then ANNOTATION_NAME word else NAT
  | "bool" -> if state.surface && annotation_name lexbuf then ANNOTATION_NAME word else BOOL
  | "let" -> LET | "const" -> CONST | "return" -> RETURN | "if" -> IF | "else" -> ELSE
  | "true" -> TRUE | "false" -> FALSE
  | _ when not state.surface -> IDENT word
  | "private" -> PRIVATE | "internal" -> INTERNAL | "async" -> ASYNC
  | "record" -> RECORD | "struct" -> STRUCT | "union" -> UNION
  | "interface" -> INTERFACE | "impl" -> IMPL
  | "trait" -> refuse "syntax" lexbuf "traits use 'interface' declarations"
  | "import" -> IMPORT | "alias" -> ALIAS | "namespace" -> NAMESPACE | "as" -> AS
  | "owned" -> OWNED | "move" -> MOVE | "in" -> IN | "ref" -> REF | "out" -> OUT
  | "null" -> refuse "syntax" lexbuf "absence requires an explicit Option case"
  | "ghost" -> GHOST | "tracked" -> TRACKED | "scoped" -> SCOPED
  | "region" -> REGION | "captures" -> CAPTURES | "grade" -> GRADE | "domain" -> DOMAIN
  | "requires" -> REQUIRES | "ensures" -> ENSURES | "restores" -> RESTORES
  | "where" -> WHERE | "effects" -> EFFECTS | "invariant" -> INVARIANT
  | "decreases" -> DECREASES | "progress" -> PROGRESS
  | "view" -> VIEW | "grows" -> GROWS | "type" -> TYPE | "predicate" -> PREDICATE
  | "operation" -> refuse "syntax" lexbuf "abstract callable declarations omit 'operation'"
  | "proof" -> PROOF | "effect" -> EFFECT | "resumes" -> RESUMES
  | "handle" -> HANDLE | "shallow" -> SHALLOW | "with" -> WITH | "resume" -> RESUME
  | "dispose" -> DISPOSE | "rehandle" -> REHANDLE | "await" -> AWAIT
  | "scope" -> SCOPE | "open" -> OPEN | "lifts" -> LIFTS | "spawn" -> SPAWN | "commit" -> COMMIT | "on" -> ON | "cancel" -> CANCEL
  | "var" -> VAR | "foreach" -> FOREACH | "while" -> WHILE | "match" -> MATCH
  | "case" -> refuse "syntax" lexbuf "match arms use 'Pattern => body' without 'case'"
  | "break" -> BREAK | "continue" -> CONTINUE | "definition" -> DEFINITION
  | "theorem" -> THEOREM | "lemma" -> LEMMA | "inductive" -> INDUCTIVE
  | "coinductive" -> COINDUCTIVE | "universe" -> UNIVERSE | "forall" -> FORALL
  | "exists" -> EXISTS | "assert" -> ASSERT | "by" -> BY | "calc" -> CALC
  | "machine" -> MACHINE | "hardware" -> HARDWARE | "state" -> STATE | "register" -> REGISTER
  | "transition" -> TRANSITION | "rule" -> RULE | "when" -> WHEN
  | "next" -> NEXT | "schedule" -> SCHEDULE | "cycle" -> CYCLE
  | "Fn" -> FN | "FnMut" -> FNMUT | "FnOnce" -> FNONCE | "is" -> IS
  | "carrier" -> CARRIER | "zero" -> ZERO | "one" -> ONE | "add" -> ADD | "mul" -> MUL
  | "admits" -> ADMITS | "interpret" -> INTERPRET | "laws" -> LAWS
  | _ -> if annotation_name lexbuf then ANNOTATION_NAME word else IDENT word
let digit_run lexbuf spelling prefix valid =
  let length = String.length spelling in
  let index = ref prefix in
  let count = ref 0 in
  while !index < length && (valid spelling.[!index] || spelling.[!index] = '_') do
    if spelling.[!index] = '_' then begin
      if !index = prefix || !index + 1 >= length ||
         not (valid spelling.[!index - 1]) || not (valid spelling.[!index + 1]) then
        refuse "syntax" lexbuf "numeric separator must be between digits of the same base"
    end else incr count;
    incr index
  done;
  if !count = 0 then refuse "syntax" lexbuf "numeric base prefix requires digits";
  if !count > Ast.max_literal_digits then refuse "limit" lexbuf "literal exceeds 256 digits";
  !index
let pure_decimal lexbuf =
  let spelling = Lexing.lexeme lexbuf in
  let count = digit_run lexbuf spelling 0 (function '0'..'9' -> true | _ -> false) in
  (* Return the decimal token alone; its suffix must receive the original pure
     keyword classification and position on the next lexer invocation. *)
  lexbuf.Lexing.lex_curr_pos <- lexbuf.Lexing.lex_start_pos + count;
  lexbuf.Lexing.lex_curr_p <- { lexbuf.Lexing.lex_curr_p with
    Lexing.pos_cnum = lexbuf.Lexing.lex_start_p.Lexing.pos_cnum + count };
  DECIMAL (String.sub spelling 0 count)
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
  let index = digit_run lexbuf spelling prefix valid in
  let digits = String.sub spelling 0 index in
  let suffix = String.sub spelling index (length - index) in
  if suffix <> "" && not state.surface then refuse "syntax" lexbuf "unexpected literal suffix";
  if suffix <> "" && (suffix.[0] >= '0' && suffix.[0] <= '9') then
    refuse "syntax" lexbuf "invalid digit for numeric base";
  if suffix = "" && prefix = 0 then DECIMAL digits else NUMBER (digits, suffix)
let is_space = function ' ' | '\t' -> true | _ -> false
let is_newline = function '\r' | '\n' -> true | _ -> false
let is_hex = function '0'..'9' | 'a'..'f' | 'A'..'F' -> true | _ -> false
let line_break_end source length index =
  if index < length && Bytes.get source index = '\r'
     && index + 1 < length && Bytes.get source (index + 1) = '\n'
  then index + 2 else index + 1
let valid_escape source length index =
  if index >= length then None
  else match Bytes.get source index with
    | '"' | '\'' | '\\' | 'n' | 'r' | 't' | '0' -> Some (index + 1)
    | 'u' when index + 2 < length && Bytes.get source (index + 1) = '{' ->
        let rec digits count value cursor =
          if cursor < length && is_hex (Bytes.get source cursor) then
            let digit = match Bytes.get source cursor with
              | '0'..'9' as ch -> Char.code ch - Char.code '0'
              | 'a'..'f' as ch -> 10 + Char.code ch - Char.code 'a'
              | 'A'..'F' as ch -> 10 + Char.code ch - Char.code 'A'
              | _ -> 0
            in
            if count >= 6 then None else digits (count + 1) (value * 16 + digit) (cursor + 1)
          else if count >= 1 && cursor < length && Bytes.get source cursor = '}'
                  && value <= 0x10ffff && (value < 0xd800 || value > 0xdfff) then
            Some (cursor + 1)
          else None
        in
        digits 0 0 (index + 2)
    | _ -> None
let raw_string state lexbuf =
  let start = Lexing.lexeme_start lexbuf in
  if not state.surface then
    refuse "syntax" lexbuf "raw string literals require the wider Vela surface";
  let after_open = Lexing.lexeme_end lexbuf in
  let quotes = after_open - start in
  let source = lexbuf.Lexing.lex_buffer in
  let length = lexbuf.Lexing.lex_buffer_len in
  let at index = Bytes.get source index in
  let rec count_quotes index =
    if index < length && at index = '"' then 1 + count_quotes (index + 1) else 0
  in
  let rec find_close index =
    if index >= length then
      raise (Ast.Refusal ("syntax", start, "unterminated raw string literal"))
    else if at index = '"' then
      let run = count_quotes index in
      if run < quotes then find_close (index + run)
      else if run > quotes then
        raise (Ast.Refusal ("syntax", start, "raw string closing delimiter has excess quotes"))
      else index
    else find_close (index + 1)
  in
  let close_start = find_close after_open in
  let close_end = close_start + quotes in
  let rec first_newline index =
    if index >= close_start then None
    else if is_newline (at index) then Some index
    else first_newline (index + 1)
  in
  (match first_newline after_open with
   | None -> ()
   | Some open_nl ->
       for index = after_open to open_nl - 1 do
         if not (is_space (at index)) then
           raise (Ast.Refusal ("syntax", start, "multi-line raw string opening line must end with a newline"))
       done;
       let rec last_line_start index current =
         if index >= close_start then current
         else if is_newline (at index) then
           let next = line_break_end source close_start index in
           last_line_start next next
         else last_line_start (index + 1) current
       in
       let body_start = line_break_end source close_start open_nl in
       let close_line = last_line_start body_start body_start in
       for index = close_line to close_start - 1 do
         if not (is_space (at index)) then
           raise (Ast.Refusal ("syntax", start, "multi-line raw string closing delimiter must be on its own line"))
       done;
       let indent_len = close_start - close_line in
       let rec check_lines line_start =
         if line_start < close_line then begin
           let rec line_end index has_non_space =
             if index >= close_line || is_newline (at index) then index, has_non_space
             else line_end (index + 1) (has_non_space || not (is_space (at index)))
           in
           let nl_pos, has_non_space = line_end line_start false in
           if has_non_space then begin
             if nl_pos - line_start < indent_len then
               raise (Ast.Refusal ("syntax", start, "raw string content line has less indentation than the closing delimiter"));
             for k = 0 to indent_len - 1 do
               if at (line_start + k) <> at (close_line + k) then
                 raise (Ast.Refusal ("syntax", start, "raw string content line has less indentation than the closing delimiter"))
             done
           end;
           check_lines (line_break_end source close_line nl_pos)
         end
       in
       check_lines body_start);
  lexbuf.Lexing.lex_curr_pos <- close_end;
  lexbuf.Lexing.lex_curr_p <- { lexbuf.Lexing.lex_curr_p with Lexing.pos_cnum = close_end };
  STRING (Bytes.sub_string source start (close_end - start))
let interpolated_string state lexbuf =
  let start = Lexing.lexeme_start lexbuf in
  if not state.surface then
    refuse "syntax" lexbuf "unexpected character";
  let after_open = Lexing.lexeme_end lexbuf in
  let source = lexbuf.Lexing.lex_buffer in
  let length = lexbuf.Lexing.lex_buffer_len in
  let at index = Bytes.get source index in
  let rec skip_inner_quoted quote index =
    if index >= length || is_newline (at index) then
      raise (Ast.Refusal ("syntax", start, "unterminated literal in interpolation hole"))
    else if at index = '\\' then
      match valid_escape source length (index + 1) with
      | Some next -> skip_inner_quoted quote next
      | None -> raise (Ast.Refusal ("syntax", start, "invalid escape in interpolation hole"))
    else if at index = quote then index + 1
    else skip_inner_quoted quote (index + 1)
  in
  let rec scan_hole stack depth has_expr in_spec has_spec index =
    if depth > Ast.max_delimiter_depth then
      raise (Ast.Refusal ("limit", start, "delimiter nesting exceeds 256"));
    if index >= length || is_newline (at index) then
      raise (Ast.Refusal ("syntax", start, "unterminated interpolation hole"));
    match at index with
    | ' ' | '\t' ->
        if in_spec then
          raise (Ast.Refusal ("syntax", start, "whitespace is not permitted in an interpolation format specifier"));
        scan_hole stack depth has_expr in_spec has_spec (index + 1)
    | '"' ->
        if in_spec then
          raise (Ast.Refusal ("syntax", start, "quotes are not permitted in an interpolation format specifier"));
        scan_hole stack depth true in_spec has_spec (skip_inner_quoted '"' (index + 1))
    | '\'' ->
        if in_spec then
          raise (Ast.Refusal ("syntax", start, "quotes are not permitted in an interpolation format specifier"));
        if index + 1 < length && (at (index + 1) = '\\' || (index + 2 < length && at (index + 2) = '\'')) then
          scan_hole stack depth true in_spec has_spec (skip_inner_quoted '\'' (index + 1))
        else
          scan_hole stack depth true in_spec has_spec (index + 1)
    | '(' when not in_spec -> scan_hole (')' :: stack) (depth + 1) true in_spec has_spec (index + 1)
    | '[' when not in_spec -> scan_hole (']' :: stack) (depth + 1) true in_spec has_spec (index + 1)
    | '{' when not in_spec -> scan_hole ('}' :: stack) (depth + 1) true in_spec has_spec (index + 1)
    | (')' | ']') as closing when not in_spec ->
        (match stack with
         | expected :: rest when expected = closing ->
             scan_hole rest (depth - 1) has_expr in_spec has_spec (index + 1)
         | _ -> raise (Ast.Refusal ("syntax", start, "mismatched delimiter in interpolation hole")))
    | '}' ->
        (match stack with
         | '}' :: rest -> scan_hole rest (depth - 1) has_expr in_spec has_spec (index + 1)
         | _ :: _ -> raise (Ast.Refusal ("syntax", start, "mismatched delimiter in interpolation hole"))
         | [] ->
             if not has_expr then
               raise (Ast.Refusal ("syntax", start, "empty interpolation hole"));
             if in_spec && not has_spec then
               raise (Ast.Refusal ("syntax", start, "empty interpolation format specifier"));
             index + 1)
    | ':' when stack = [] && not in_spec ->
        if index + 1 < length && at (index + 1) = ':' then
          scan_hole stack depth has_expr false false (index + 2)
        else if not has_expr then
          raise (Ast.Refusal ("syntax", start, "empty interpolation hole"))
        else
          scan_hole stack depth has_expr true false (index + 1)
    | ':' when in_spec ->
        raise (Ast.Refusal ("syntax", start, "multiple colons in interpolation format specifier"))
    | ('(' | ')' | '[' | ']' | '{') when in_spec ->
        raise (Ast.Refusal ("syntax", start, "delimiters are not permitted in an interpolation format specifier"))
    | _ ->
        if in_spec then scan_hole stack depth has_expr true true (index + 1)
        else scan_hole stack depth true false false (index + 1)
  in
  let rec scan index =
    if index >= length || is_newline (at index) then
      raise (Ast.Refusal ("syntax", start, "unterminated interpolated format string"));
    match at index with
    | '"' -> index + 1
    | '\\' ->
        (match valid_escape source length (index + 1) with
         | Some next -> scan next
         | None -> raise (Ast.Refusal ("syntax", start, "invalid escape in interpolated format string")))
    | '{' ->
        if index + 1 < length && at (index + 1) = '{' then scan (index + 2)
        else scan (scan_hole [] (state.delimiters + 1) false false false (index + 1))
    | '}' ->
        if index + 1 < length && at (index + 1) = '}' then scan (index + 2)
        else raise (Ast.Refusal ("syntax", start, "unescaped closing brace in interpolated format string"))
    | _ -> scan (index + 1)
  in
  let close_end = scan after_open in
  lexbuf.Lexing.lex_curr_pos <- close_end;
  lexbuf.Lexing.lex_curr_p <- { lexbuf.Lexing.lex_curr_p with Lexing.pos_cnum = close_end };
  INTERPOLATED_STRING (Bytes.sub_string source start (close_end - start))
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
  | '"' '"' '"' '"'* { raw_string state lexbuf }
  | "$\"" { interpolated_string state lexbuf }
  | '"' ([^ '"' '\\' '\r' '\n'] | escape)* '"' { STRING (Lexing.lexeme lexbuf) }
  | '\'' ([^ '\'' '\\' '\r' '\n'] | escape) '\'' { CHARACTER (Lexing.lexeme lexbuf) }
  | '\'' identifier ('.' identifier)* { LIFETIME (Lexing.lexeme lexbuf) }
  | '?' identifier { HOLE (Lexing.lexeme lexbuf) }
  | '(' { opening state lexbuf (if state.surface && lambda_open lexbuf then LAMBDA_OPEN
      else if state.surface && annotation lexbuf true then ANNOTATION_OPEN else LPAREN) } | ')' { closing state RPAREN }
  | '{' { opening state lexbuf LBRACE } | '}' { closing state RBRACE }
  | '[' { opening state lexbuf LBRACKET } | ']' { closing state RBRACKET }
  | ';' { SEMICOLON } | ',' { COMMA } | '.' { DOT } | ':' { COLON }
  | "??" {
      if state.surface then refuse "syntax" lexbuf "implicit optional operators are not supported";
      (* Preserve the pure entry's original one-character tokenization. *)
      lexbuf.Lexing.lex_curr_pos <- lexbuf.Lexing.lex_start_pos + 1;
      lexbuf.Lexing.lex_curr_p <- { lexbuf.Lexing.lex_curr_p with
        Lexing.pos_cnum = lexbuf.Lexing.lex_start_p.Lexing.pos_cnum + 1 };
      QUESTION }
  | "?." {
      if state.surface then
        refuse "syntax" lexbuf
          "'?' is early-return propagation, not C# null-conditional '?.'; write '(expr?).Member' to propagate or 'match' to handle locally";
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
  | '/' { SLASH } | '%' { PERCENT }
  | '<' { if state.surface && generic_call token state lexbuf then CALL_GENERIC_OPEN else LT }
  | '>' { GT }
  | eof { EOF }
  | _ { refuse "syntax" lexbuf "unexpected character" }
and comment state depth start = parse
  | "/*" { if depth >= Ast.max_delimiter_depth then refuse "limit" lexbuf "comment nesting exceeds 256";
             comment state (depth + 1) start lexbuf }
  | "*/" { if depth > 1 then comment state (depth - 1) start lexbuf }
  | newline { Lexing.new_line lexbuf; comment state depth start lexbuf }
  | eof { raise (Ast.Refusal ("syntax", start, "unterminated block comment")) }
  | _ { comment state depth start lexbuf }
