(* SPDX-License-Identifier: Apache-2.0 *)
(* The native boundary reads one bounded UTF-8 file and emits syntax or a refusal. *)

let read_source () =
  let bytes = Bytes.create (Ast.max_source_bytes + 1) in
  let rec read count =
    if count = Bytes.length bytes then count
    else
      let got = input stdin bytes count (Bytes.length bytes - count) in
      if got = 0 then count else read (count + got)
  in
  let count = read 0 in
  if count > Ast.max_source_bytes then
    raise (Ast.Refusal ("limit", 0, "source exceeds 65536 bytes"));
  Bytes.sub_string bytes 0 count

let validate_utf8 source =
  let length = String.length source in
  let byte index = Char.code source.[index] in
  let continuation index = index < length && byte index >= 0x80 && byte index <= 0xbf in
  let invalid index = raise (Ast.Refusal ("encoding", index, "source is not valid UTF-8")) in
  let rec walk index =
    if index < length then begin
      let lead = byte index in
      let width =
        if lead <= 0x7f then 1
        else if lead >= 0xc2 && lead <= 0xdf then 2
        else if lead >= 0xe0 && lead <= 0xef then 3
        else if lead >= 0xf0 && lead <= 0xf4 then 4
        else invalid index
      in
      if index + width > length then invalid index;
      for offset = 1 to width - 1 do
        if not (continuation (index + offset)) then invalid index
      done;
      if width >= 3 then begin
        let second = byte (index + 1) in
        if (lead = 0xe0 && second < 0xa0) || (lead = 0xed && second >= 0xa0)
           || (lead = 0xf0 && second < 0x90) || (lead = 0xf4 && second >= 0x90)
        then invalid index
      end;
      walk (index + width)
    end
  in
  walk 0

let position source target =
  let limit = min target (String.length source) in
  let rec scan index line column =
    if index >= limit then (line, column)
    else match source.[index] with
      | '\r' ->
          let width = if index + 1 < limit && source.[index + 1] = '\n' then 2 else 1 in
          scan (index + width) (line + 1) 1
      | '\n' -> scan (index + 1) (line + 1) 1
      | character when Char.code character land 0xc0 = 0x80 ->
          scan (index + 1) line column
      | _ -> scan (index + 1) line (column + 1)
  in
  scan 0 1 1

let diagnostic source kind offset message =
  let line, column = position source offset in
  Ast.Object [("kind", Ast.String kind); ("line", Ast.Number line);
              ("column", Ast.Number column); ("message", Ast.String message)]

let () =
  set_binary_mode_in stdin true;
  set_binary_mode_out stdout true;
  let source = ref "" in
  let current = ref 0 in
  let publish_failure kind offset message =
    print_endline (Ast.encode (diagnostic !source kind offset message));
    exit 1
  in
  try
    let surface = match Array.to_list Sys.argv with
      | [_] -> false
      | [_; "--surface"] -> true
      | _ -> raise (Ast.Refusal ("syntax", 0, "expected no arguments or --surface"))
    in
    source := read_source ();
    validate_utf8 !source;
    let lexbuf = Lexing.from_string !source in
    let state = Lexer.create ~surface () in
    let next lexbuf =
      let token = Lexer.token state lexbuf in
      current := Lexing.lexeme_start lexbuf;
      token
    in
    let syntax = (if surface then Parser.surface_file else Parser.file) next lexbuf in
    print_endline (Ast.encode (Ast.Object [("schema", Ast.Number (if surface then 2 else 1));
                                          ("ast", syntax.syntax)]))
  with
  | Ast.Refusal (kind, offset, message) -> publish_failure kind offset message
  | Parser.Error -> publish_failure "syntax" !current "unexpected token or incomplete input"
  | Stack_overflow -> publish_failure "limit" !current "native parser stack limit exceeded"
  | Sys_error message -> publish_failure "io" !current message
