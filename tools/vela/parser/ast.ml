(* SPDX-License-Identifier: Apache-2.0 *)
(* Located syntax only: no resolution, typing, evaluation or code emission. *)

type json =
  | Null
  | String of string
  | Number of int
  | Boolean of bool
  | Array of json list
  | Object of (string * json) list

type node = { syntax : json; depth : int }

exception Refusal of string * int * string

let max_source_bytes = 65_536
let max_literal_digits = 256
(* Raw syntax includes groups and the file/function/block/return wrappers.
   Semantic expression and block budgets are enforced by the AST consumer. *)
let max_delimiter_depth = 256
let max_syntax_depth = 256
let max_generic_probe_tokens = 200_000

let offsets first last =
  Array [Number first.Lexing.pos_cnum; Number last.Lexing.pos_cnum]

let name first last text =
  Object [("text", String text); ("span", offsets first last)]

let make kind first last fields children =
  let depth = 1 + List.fold_left (fun current child -> max current child.depth) 0 children in
  if depth > max_syntax_depth then
    raise (Refusal ("limit", first.Lexing.pos_cnum,
                    "syntax tree exceeds depth 256"));
  { syntax = Object (("kind", String kind) :: ("span", offsets first last) :: fields);
    depth }

let array nodes = Array (List.map (fun node -> node.syntax) nodes)

let string_json value =
  let out = Buffer.create (String.length value + 2) in
  Buffer.add_char out '"';
  String.iter (function
    | '"' -> Buffer.add_string out "\\\""
    | '\\' -> Buffer.add_string out "\\\\"
    | '\n' -> Buffer.add_string out "\\n"
    | '\r' -> Buffer.add_string out "\\r"
    | '\t' -> Buffer.add_string out "\\t"
    | character when Char.code character < 32 ->
        Buffer.add_string out (Printf.sprintf "\\u%04x" (Char.code character))
    | character -> Buffer.add_char out character) value;
  Buffer.add_char out '"';
  Buffer.contents out

let rec write_json out = function
  | Null -> Buffer.add_string out "null"
  | String value -> Buffer.add_string out (string_json value)
  | Number value -> Buffer.add_string out (string_of_int value)
  | Boolean value -> Buffer.add_string out (if value then "true" else "false")
  | Array values ->
      Buffer.add_char out '[';
      List.iteri (fun index value ->
        if index > 0 then Buffer.add_char out ',';
        write_json out value) values;
      Buffer.add_char out ']'
  | Object fields ->
      Buffer.add_char out '{';
      List.iteri (fun index (key, value) ->
        if index > 0 then Buffer.add_char out ',';
        Buffer.add_string out (string_json key);
        Buffer.add_char out ':';
        write_json out value) fields;
      Buffer.add_char out '}'

let encode value =
  let out = Buffer.create 256 in
  write_json out value;
  Buffer.contents out
