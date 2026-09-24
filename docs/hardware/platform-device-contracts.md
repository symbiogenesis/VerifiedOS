# Platform device wrapper contracts

This contract selects the device-facing R1c-ii simulation boundary before its
implementation. The core-facing SoC top remains dependent on R1b's remaining
port and functional-unit work. No whole-SoC or production-device acceptance is
claimed by standalone wrapper tests.

## Unclaimed IO and the attested device tree

After complete-access PMA validation, a declared aperture routes to its device.
An unclaimed IO access routes to the immutable attested-device-tree image only
when its entire interval lies from the composed `VosDtbAddress` up to the
composed boot-ROM base and it is an ordinary read. Other unclaimed IO accesses
return a decode error. The loader supplies the exact attested blob and zero
padding within that reserved interval before releasing the core; neither writes
nor fetches reach it. No missing device aliases RAM or a zero-returning slave.

This selects the concrete lower-ROM case reported by `vos_soc_decode.sv`.
The existing Sail `pmaCheck` remains the authority for region permissions and
complete-access checks, but its subsequent unclaimed-IO RAM fallback is not
evidence of this selected routing policy. Sail dispatch alignment and a
core-facing integration test remain required before any SoC differential claim.
The route wrapper reports the DTB destination; it does not fabricate blob bytes
or claim that a loader has authenticated them.

## Common simulation slave boundary

Requests carry an aperture-relative 64-bit offset, complete byte width, ordinary
access flag, direction and 64-bit data. Capability/PMA checks precede this
boundary. A valid request receives a combinational response and commits at the
next rising edge; holding valid over several edges makes several requests.
Every malformed width, alignment, kind, direction or reserved offset returns an
error with no slave state effect. Read data is zero on error and every returned
tag is clear. No slave initiates a memory transaction or interrupt.

Reset is synchronous and wins over all requests and progress. The block-device
harness orders bus requests and explicit step events separately; a coincident
request and step is refused while the step proceeds. UART ready/valid handshakes
may occur alongside a bus request, with admission decided from the pre-edge queue
state. Harness backend inputs are not guest-accessible registers.

## UART character wrapper

The register-layout owner is Mocha revision
`2c11b745c4bcdb24a3cad03f3333e4a922985b22`,
`hw/vendor/lowrisc_ip/ip/uart/rtl/uart_reg_pkg.sv`, with status bit meaning from
the adjacent `data/uart.hjson`. Its own SPDX declaration and
`LICENSES/Apache-2.0.txt` were read at that revision. The selected offsets are
`UART_STATUS_OFFSET`, `UART_RDATA_OFFSET`, and `UART_WDATA_OFFSET`; the generator
reads them from that file rather than assigning new locations.

The wrapper supplies a bounded, polled character transport: one byte of RX
buffering and one byte of TX buffering, with external ready/valid byte channels.
It accepts aligned four-byte ordinary accesses. STATUS is read-only; RDATA is
read-only and consumes a buffered byte; WDATA is write-only and stages its low
byte. Empty reads and full writes fault without a queue effect. Other offsets
fault. STATUS uses the owner's TXFULL, RXFULL, TXEMPTY, TXIDLE, RXIDLE and
RXEMPTY positions. At this character boundary TXIDLE means the pending byte
has been accepted by the backend, and RXIDLE means no input byte is offered.
The backend owns actual serialization and line timing. Reset empties both queues.

This is an authored simulation wrapper, not a copy of OpenTitan RTL or complete
OpenTitan UART compatibility. It has no baud, parity, interrupt, FIFO-control or
serial-line implementation; software uses the declared polled subset. Upstream
empty-read behavior is deliberately replaced by an explicit refusal.

## Block-device start-from and backend

Choose an authored wrapper against the reviewed
[block-device contract](../../interfaces/block-device-contract.md) and
[Sail implementation](../../model/model/sys/block_device.sail). Mocha's pinned
IP inventory supplies UART and SPI controller/testbench pieces, not this logical
block slave. Importing another controller would add a second ABI, dependencies
and license incorporation without implementing the reviewed boundary.

`vos_block_device` implements that contract's PIO state machine, validation order,
staging bitmap, declared step counts, completion and reset. Geometry and positive
service steps are explicit parameters validated at elaboration. The external
backend supplies exactly the declared backing image and owns host persistence.
The wrapper does not initialize or recreate the medium on reset.

Backend effects occur only on explicit synchronous boundary outputs. A final
step samples `backend_error_i` and read data, publishes a normal read/write/flush
commit when successful, or publishes a write-tear request on failed WRITE. Reset
of a pending WRITE publishes a tear request and suppresses commit. The backend
applies the contract's supplied mask to its immediately preceding medium and
latched write payload at that boundary. Reset of READ/FLUSH has no medium effect.
There is no asynchronous callback or outstanding backend operation outside these
boundaries, so a canceled operation has no later write or completion to deliver.
An adapter with asynchronous I/O must establish an equivalent fence before use.
Successful backend WRITE/FLUSH means persistence is established before the edge
publishing DONE; a buffered host write is not sufficient.

## Focused acceptance

Generated register constants equal their owners. UART simulation checks status,
empty/full refusals, byte order, queue consumption, backpressure and reset.
Block simulation checks read/write/flush, step counts independent of polling,
last-block placement, overwritten staging, reset/ACK clearing, validation
precedence, malformed accesses and kinds, and reset winning the final-step tie.
An explicit external medium harness checks success persistence, torn-write masks,
read/flush errors, unchanged adjacent blocks and refusal after reset. Route tests
cover DTB read, write/fetch refusal, unrelated unclaimed IO and boundary crossing.
These tests do not discharge capability enforcement before the slave, actual
host-image durability, NAND/ONFI/ECC/FTL, or whole-SoC differential execution.
