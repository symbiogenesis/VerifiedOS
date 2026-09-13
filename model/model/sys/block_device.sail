// SPDX-License-Identifier: BSD-2-Clause
// M5.3's bounded PIO model, specified by interfaces/block-device-contract.md.
// The persistent register is the modeled medium. A host image adapter must
// persist and reopen these bytes explicitly; this module does not open files.

let blkdev_max_bytes : int(8192) = 8192
let blkdev_max_block_bytes : int(4096) = 4096
type blkdev_buffer = vector(4096, bits(8))
type blkdev_image = vector(8192, bits(8))

type blkdev_u64_int = range(0, 18446744073709551615)

let plat_blkdev_block_bytes : blkdev_u64_int = config platform.blkdev.block_bytes
let plat_blkdev_block_count : blkdev_u64_int = config platform.blkdev.block_count
let plat_blkdev_read_steps : blkdev_u64_int = config platform.blkdev.read_steps
let plat_blkdev_write_steps : blkdev_u64_int = config platform.blkdev.write_steps
let plat_blkdev_flush_steps : blkdev_u64_int = config platform.blkdev.flush_steps
let plat_blkdev_backing : list(range(0, 255)) = config platform.blkdev.backing

register blkdev_medium : blkdev_image = vector_init(zeros())
register blkdev_staging : blkdev_buffer = vector_init(zeros())
register blkdev_payload : blkdev_buffer = vector_init(zeros())
register blkdev_written : bits(512) = zeros()
register blkdev_status : range(0, 3) = 0
register blkdev_result : range(0, 4) = 0
register blkdev_block : bits(64) = zeros()
register blkdev_pending_block : bits(64) = zeros()
register blkdev_command : range(0, 3) = 0
register blkdev_remaining : nat = 0
// An unbounded association number is a model input token, never an MMIO field.
// Reset invalidates old events, including their medium effects.
register blkdev_epoch : nat = 0

function blkdev_backing_length(bytes : list(range(0, 255))) -> nat =
  match bytes { [||] => 0, _byte :: rest => 1 + blkdev_backing_length(rest) }

function blkdev_geometry_valid(base : int, size : int, b : int, n : int,
                              r : int, w : int, f : int, backing_bytes : int) -> bool = {
  if base < 0 | size < 0 then return false;
  if base % 8 != 0 then return false;
  if base + size > 2 ^ physaddr_bits then return false;
  if b <= 0 then return false;
  if b % 8 != 0 | b > size - 256 then return false;
  if b > blkdev_max_block_bytes | n <= 0 then return false;
  if b >= 2 ^ 64 | n >= 2 ^ 64 | n * b >= 2 ^ 64 then return false;
  if n * b > blkdev_max_bytes | backing_bytes != n * b then return false;
  if r <= 0 | w <= 0 | f <= 0 then return false;
  r < 2 ^ 64 & w < 2 ^ 64 & f < 2 ^ 64
}

function blkdev_clear_volatile() -> unit = {
  blkdev_staging = vector_init(zeros());
  blkdev_payload = vector_init(zeros());
  blkdev_written = zeros();
  blkdev_status = 0;
  blkdev_result = 0;
  blkdev_block = zeros();
  blkdev_pending_block = zeros();
  blkdev_command = 0;
  blkdev_remaining = 0;
}

// Startup consumes an exact explicit byte array once. Reset never reloads it.
function blkdev_initialize() -> unit = {
  if not(plat_have_blkdev) then return ();
  assert(blkdev_geometry_valid(unsigned(plat_blkdev_base), unsigned(plat_blkdev_size),
    plat_blkdev_block_bytes, plat_blkdev_block_count, plat_blkdev_read_steps,
    plat_blkdev_write_steps, plat_blkdev_flush_steps, blkdev_backing_length(plat_blkdev_backing)));
  blkdev_medium = vector_init(zeros());
  var bytes = plat_blkdev_backing;
  foreach (i from 0 to (blkdev_max_bytes - 1)) {
    match bytes {
      [||] => (),
      byte :: rest => { blkdev_medium[i] = to_bits(8, byte); bytes = rest },
    }
  };
  blkdev_clear_volatile();
  blkdev_epoch = blkdev_epoch + 1;
}

// Overlap, not containment: neither a reserved address nor a crossing access
// may escape into RAM. The complete memory request is checked before splitting.
function blkdev_claims forall 'n, 0 < 'n <= max_mem_access .
    (Physaddr(addr) : physaddr, width : int('n)) -> bool =
  plat_have_blkdev & not(get_config_rvfi())
  & unsigned(addr) < unsigned(plat_blkdev_base) + unsigned(plat_blkdev_size)
  & unsigned(plat_blkdev_base) < unsigned(addr) + width

function blkdev_access_valid forall 'n, 0 < 'n <= max_mem_access .
    (access : MemoryAccessType(mem_payload), Physaddr(addr) : physaddr, width : int('n)) -> bool = {
  let ordinary : bool = match access { Load(Data) => true, Store(Data) => true, _ => false };
  ordinary & width == 8 & unsigned(addr) % 8 == 0
  & unsigned(plat_blkdev_base) <= unsigned(addr)
  & unsigned(addr) + width <= unsigned(plat_blkdev_base) + unsigned(plat_blkdev_size)
  & unsigned(addr) + width <= 2 ^ physaddr_bits
}

function blkdev_tear(mask : blkdev_buffer) -> unit = {
  let offset = unsigned(blkdev_pending_block) * plat_blkdev_block_bytes;
  assert(offset >= 0 & plat_blkdev_block_bytes > 0
    & plat_blkdev_block_bytes <= blkdev_max_block_bytes
    & offset + plat_blkdev_block_bytes <= blkdev_max_bytes);
  foreach (i from 0 to (plat_blkdev_block_bytes - 1)) {
    blkdev_medium[offset + i] = (blkdev_medium[offset + i] & not_vec(mask[i]))
                              | (blkdev_payload[i] & mask[i]);
  }
}

function blkdev_reset(mask : blkdev_buffer) -> unit = {
  if blkdev_status == 1 & blkdev_command == 2 then blkdev_tear(mask);
  blkdev_clear_volatile();
  blkdev_epoch = blkdev_epoch + 1;
}

// Explicit, synchronous harness inputs. A final READ samples the addressed
// medium here, after earlier ordered corruption. A wrong-block event supplies
// intact bytes, with DONE; authentication remains the storage layer's work.
function blkdev_progress(epoch : nat, io_error : bool, misplaced : option(bits(64)),
                         mask : blkdev_buffer) -> unit = {
  if epoch != blkdev_epoch | blkdev_status != 1 then return ();
  let remaining = blkdev_remaining;
  if remaining > 1 then {
    blkdev_remaining = remaining - 1;
    return ();
  };
  if io_error then {
    if blkdev_command == 2 then blkdev_tear(mask);
    blkdev_status = 3;
    blkdev_result = 4;
  } else {
    if blkdev_command == 1 then {
      let block : bits(64) = match misplaced { None() => blkdev_pending_block, Some(b) => b };
      assert(unsigned(block) < plat_blkdev_block_count);
      let offset = unsigned(block) * plat_blkdev_block_bytes;
      assert(offset >= 0 & plat_blkdev_block_bytes > 0
        & plat_blkdev_block_bytes <= blkdev_max_block_bytes
        & offset + plat_blkdev_block_bytes <= blkdev_max_bytes);
      foreach (i from 0 to (plat_blkdev_block_bytes - 1)) {
        blkdev_staging[i] = blkdev_medium[offset + i];
      }
    } else if blkdev_command == 2 then blkdev_tear(vector_init(ones()));
    blkdev_status = 2;
    blkdev_result = 0;
  };
  blkdev_payload = vector_init(zeros());
  blkdev_pending_block = zeros();
  blkdev_remaining = 0;
}

// A simultaneous reset/progress boundary has exactly the reviewed priority.
function blkdev_boundary(reset_now : bool, step_now : bool, epoch : nat,
                         io_error : bool, misplaced : option(bits(64)),
                         mask : blkdev_buffer) -> unit = {
  if reset_now then blkdev_reset(mask)
  else if step_now then blkdev_progress(epoch, io_error, misplaced, mask);
}

// Explicit media faults are independent of command completion and guest writes.
function blkdev_corrupt(block : bits(64), bytes : blkdev_buffer) -> unit = {
  assert(unsigned(block) < plat_blkdev_block_count);
  let offset = unsigned(block) * plat_blkdev_block_bytes;
  assert(offset >= 0 & plat_blkdev_block_bytes > 0
    & plat_blkdev_block_bytes <= blkdev_max_block_bytes
    & offset + plat_blkdev_block_bytes <= blkdev_max_bytes);
  foreach (i from 0 to (plat_blkdev_block_bytes - 1)) {
    blkdev_medium[offset + i] = bytes[i];
  }
}

function blkdev_load forall 'n, 0 < 'n <= max_mem_access .
    (access : MemoryAccessType(mem_payload), paddr : physaddr, width : int('n)) -> MemoryOpResult(bits(8 * 'n)) = {
  if not(blkdev_access_valid(access, paddr, width)) then return Err(paddr, accessFaultFromAccessType(access));
  let offset = unsigned(bits_of(paddr)) - unsigned(plat_blkdev_base);
  var value : bits(64) = zeros();
  if offset == 0 then value = 0x0000000000000001
  else if offset == 8 then value = to_bits(64, plat_blkdev_block_bytes)
  else if offset == 16 then value = to_bits(64, plat_blkdev_block_count)
  else if offset == 24 then value = to_bits(64, blkdev_status)
  else if offset == 32 then value = to_bits(64, blkdev_result)
  else if offset == 40 then value = blkdev_block
  else if offset >= 256 & offset + 8 <= 256 + plat_blkdev_block_bytes
       & blkdev_status == 2 & blkdev_command == 1 then {
    let index = offset - 256;
    assert(index >= 0 & index + 8 <= blkdev_max_block_bytes);
    foreach (i from 0 to 7) { value[(8 * i + 7) .. (8 * i)] = blkdev_staging[index + i] }
  } else return Err(paddr, accessFaultFromAccessType(access));
  assert(width == 8);
  Ok(value)
}

function blkdev_store forall 'n, 0 < 'n <= max_mem_access .
    (paddr : physaddr, width : int('n), data : bits(8 * 'n)) -> MemoryOpResult(bool) = {
  if not(blkdev_access_valid(Store(Data), paddr, width)) then return Err(paddr, E_SAMO_Access_Fault());
  assert(width == 8);
  let offset = unsigned(bits_of(paddr)) - unsigned(plat_blkdev_base);
  if offset == 56 then {
    if data != 0x0000000000000001 | (blkdev_status != 2 & blkdev_status != 3)
    then return Err(paddr, E_SAMO_Access_Fault());
    blkdev_clear_volatile();
    return Ok(true);
  };
  if blkdev_status != 0 then return Err(paddr, E_SAMO_Access_Fault());
  if offset == 40 then {
    blkdev_block = data;
    blkdev_staging = vector_init(zeros());
    blkdev_written = zeros();
  } else if offset == 48 then {
    var failure : range(0, 4) = 0;
    if data != 0x0000000000000001 & data != 0x0000000000000002 & data != 0x0000000000000003
    then failure = 1
    else if data != 0x0000000000000003 & unsigned(blkdev_block) >= plat_blkdev_block_count
    then failure = 2
    else if data == 0x0000000000000002 then {
      assert(plat_blkdev_block_bytes > 0 & plat_blkdev_block_bytes <= blkdev_max_block_bytes);
      foreach (i from 0 to (plat_blkdev_block_bytes / 8 - 1)) {
        if blkdev_written[i] == 0b0 then failure = 3;
      }
    };
    if failure != 0 then {
      blkdev_status = 3;
      blkdev_result = failure;
    } else {
      blkdev_epoch = blkdev_epoch + 1;
      blkdev_pending_block = blkdev_block;
      blkdev_command = if data == 0x0000000000000001 then 1 else if data == 0x0000000000000002 then 2 else 3;
      if blkdev_command == 2 then blkdev_payload = blkdev_staging;
      let steps = if blkdev_command == 1 then plat_blkdev_read_steps
                  else if blkdev_command == 2 then plat_blkdev_write_steps else plat_blkdev_flush_steps;
      assert(steps > 0);
      blkdev_remaining = steps;
      blkdev_status = 1;
      blkdev_result = 0;
    };
    blkdev_staging = vector_init(zeros());
    blkdev_written = zeros();
  } else if offset >= 256 & offset + 8 <= 256 + plat_blkdev_block_bytes then {
    let index = offset - 256;
    assert(index >= 0 & index + 8 <= blkdev_max_block_bytes);
    foreach (i from 0 to 7) { blkdev_staging[index + i] = data[(8 * i + 7) .. (8 * i)] };
    blkdev_written[index / 8] = 0b1;
  } else return Err(paddr, E_SAMO_Access_Fault());
  Ok(true)
}
