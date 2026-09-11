# Compiler assembly comparison

This is the replacement comparison contract for [M1.2b](implementation-checklist.md)
and the remaining assembly debt in [F-318](../assurance/findings-register.md).
It qualifies preservation of the stock RV64 assembly emitted while removing the
scalar float bank. It does not establish the purecap backend's correctness,
source correspondence, target execution or M1.2f's differential verdict.

## Predicate

Compare each FP-free test program's complete assembly byte streams in their
original order. The only permitted difference is the decimal identifier on a
full line matching `[ \t]*# Compartment [0-9]+[ \t]*`, terminated by LF, CRLF or
the end of the file. Replace only that identifier with one fixed marker before
comparison. Preserve the leading and trailing whitespace, comment spelling,
line ending and position in the line sequence. The sequence of annotation and
ordinary lines must agree. The identifier is compiler diagnostic metadata;
compartment identifiers embedded in instructions, symbols or data stay exact.

Every other byte must agree. This includes instruction order, register numbers,
all operands, immediate values, memory widths and offsets, branch and call
targets, labels, symbol binding, relocation spelling, section and alignment
directives, literal data, other comments, whitespace and line endings. No sorting,
register renaming, alias substitution, instruction expansion or relocation
normalization is admitted. The existing [assembler](../../tools/vos/asm.py)
expands `ret` and `la` for the purecap dialect, so it cannot normalize these stock
RV64 inputs without changing their meaning.

An empty, comment-only or data-only input is refused. Each input must contain an
explicit `.text` section and an instruction witness: `ret`, `mv`, `add` or
`addi`, with their ordinary numeric `x0` through `x31` operands and, for `addi`,
a signed decimal immediate in the twelve-bit range. This finite witness grammar
only prevents vacuous equality; it is not validation of the surrounding assembly.
Other unchanged instructions remain opaque bytes. Assembly using a multiline
quoted string, block comment, line continuation, macro, repetition, conditional
assembly, section stack, external include or binary include is unsupported and
refused, even when the two byte streams agree. These exclusions prevent a
comment-shaped line inside another construct from being normalized or a witness
inside an inactive construct from counting as executable code. Non-ASCII input
and control bytes other than tab and line endings are unsupported.

A pair has one of three dispositions: `equal`, meaning exact equality under this
one metadata exception; `different`, naming the first differing normalized byte
and its source line on each side; or `unsupported`, naming the unmet input
condition. Only `equal` succeeds. The report identifies both original byte
streams by SHA256, reports the annotation and witness counts it computed, and
identifies the comparator and this contract. A successful pair is evidence about
those bytes, not about their producer.

## Producer evidence and milestone acceptance

For a milestone claim, retain a nonempty manifest of all required FP-free cases,
their source bytes and hashes, both compiler revisions and executable hashes,
the configuration and preprocessor settings, complete argument vectors and
working directories, successful process exits, and the freshly produced output
bytes and hashes. Remove stale outputs before each invocation. Both arms receive
the same source and relevant settings; working directories keep their outputs
separate. A missing case, missing receipt, failed compiler, stale output or
unsupported comparison leaves acceptance open. A caller cannot establish this
producer evidence by passing two equal arbitrary files to the comparator.

Every manifest member must return `equal`. The scalar-FP refusal remains a
separate successful negative control: the candidate exits unsuccessfully,
names R-15-039, and creates no assembly. M1.2b's clean-build, unchanged-admit,
representation, width and source-boundary clauses are unchanged. The historical
comment-masked agreement reported in the checklist is not a run of this
comparator. Its register-changing pairs still fail this predicate, and F-318
remains open until an accepted run or a separately reviewed stronger contract
discharges every member.

## Register and calling-convention boundary

Every register is fixed by its numeric identity here, including each register
an allocator may treat as temporary. Concrete roles that a proposed extension
must establish from both contained compiler revisions are:

| Register or interface | Required boundary evidence |
| --- | --- |
| `x0` | Architectural zero; never renamed or treated as an ordinary destination. |
| `x1`, `x2`, `x3`, `x4` | Return address, stack, global and thread roles, including any compiler-specific use; fixed at every boundary. |
| `x10` through `x17` | Integer argument/result locations, argument order, multiword values and variadic handling; fixed at call, tail-call, entry and return boundaries. |
| `x8`, `x9`, `x18` through `x27` | Preservation obligations, frame-pointer use and save/restore slots; unchanged preservation of each architectural register. |
| `x5` through `x7`, `x28` through `x31` | Actual caller-clobbered, allocatable and reserved-scratch sets, read from `Machregs`, `Conventions1`, `Asmgen`, `Asmexpand` and allocator definitions; no freedom inferred merely from a temporary-register ABI name. |
| Calls, returns, builtins and compartment transitions | Explicit and implicit reads/writes, clobbers, live values, stack layout, relocation and external-symbol interfaces at both revisions. |

These rows are the obligations of a future extension, not a declaration that the
contained compiler implements a generic ABI unchanged. An extension must bind
the exact role definitions and their hashes before choosing any admissible
mapping. It must preserve ordered instruction operands and dataflow through
control-flow joins and loops, memory addressing and widths, and all live values
at every interface. A whole-function register permutation or an opcode multiset
alone decides none of those conditions. Unsupported instruction semantics or
unresolved liveness must refuse. Compiler source remains in its contained
repository under [M1.1a's decision](../../THIRD-PARTY.md).

## Qualification controls

Positive controls include byte-identical executable input and a changed decimal
identifier on the exact annotation line. Refusal controls change a register,
immediate, load/store width, memory offset, branch or call target, label,
relocation, data byte, section directive, instruction order, annotation position,
or a comment outside the permitted grammar. They also insert/delete a line,
alter line endings, and supply empty, data-only or unsupported lexical forms.
A quoted `# Compartment` string must remain data and differ when its digits
change. File/CLI controls cover unreadable inputs, error exit status and byte
hashes. These tests qualify the comparison mechanism; they do not substitute
synthetic programs for the compiler campaign.
