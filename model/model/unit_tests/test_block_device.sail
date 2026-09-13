// SPDX-License-Identifier: BSD-2-Clause
// Local executions of the real Sail device. These are not the HTIF corpus,
// host-image persistence, storage authentication or recovery-policy evidence.

function blk_test_addr(offset : int) -> physaddr = Physaddr(plat_blkdev_base + offset)

function blk_test_write(offset : int, value : bits(64)) -> unit =
  match mem_write_value_meta(blk_test_addr(offset), 8, value, Store(Data), true, false, false) {
    Ok(true) => (), _ => assert(false, "block-device store must succeed"),
  }

function blk_test_read(offset : int) -> bits(64) =
  match mem_read_meta(Load(Data), blk_test_addr(offset), 8, false, false, true) {
    Ok(value, tag) => { assert(not(tag)); value },
    _ => { assert(false, "block-device load must succeed"); zeros() },
  }

function blk_test_load_fault(offset : int) -> unit =
  match mem_read(Load(Data), blk_test_addr(offset), 8, false, false) {
    Err(_, _) => (), _ => assert(false, "block-device load must fault"),
  }

function blk_test_store_fault(offset : int, value : bits(64)) -> unit =
  match mem_write_value(blk_test_addr(offset), 8, value, Store(Data), false, false) {
    Err(_, _) => (), _ => assert(false, "block-device store must fault"),
  }

function blk_test_complete(fail : bool, mask : blkdev_buffer) -> unit = {
  let steps = blkdev_remaining;
  foreach (_i from 1 to steps) { blkdev_progress(blkdev_epoch, fail, None(), mask) }
}

function blk_test_prepare(block : int, value : bits(64)) -> unit = {
  blk_test_write(40, to_bits_truncate(64, block));
  assert(plat_blkdev_block_bytes > 0 & plat_blkdev_block_bytes <= blkdev_max_block_bytes);
  foreach (i from (plat_blkdev_block_bytes / 8 - 1) downto 0) {
    blk_test_write(256 + 8 * i, value);
  }
}

$[test]
function test_blkdev_geometry_and_initial_bytes() -> unit = {
  blkdev_initialize();
  assert(plat_blkdev_block_count >= 2);
  assert(blk_test_read(0) == 0x0000000000000001);
  assert(blk_test_read(8) == to_bits_truncate(64, plat_blkdev_block_bytes));
  assert(blk_test_read(16) == to_bits_truncate(64, plat_blkdev_block_count));
  assert(blk_test_read(24) == zeros() & blk_test_read(32) == zeros());
  let b = plat_blkdev_block_bytes;
  let n = plat_blkdev_block_count;
  assert(blkdev_geometry_valid(0, 4096, b, n, 1, 1, 1, b * n));
  assert(not(blkdev_geometry_valid(0, 4096, b, n, 1, 1, 1, b * n - 1)));
  assert(not(blkdev_geometry_valid(0, 4096, b, n, 1, 1, 1, b * n + 1)));
  assert(not(blkdev_geometry_valid(0, 4096, b, n, 1, 1, 1, 0)));
  assert(not(blkdev_geometry_valid(0, 4096, 0, n, 1, 1, 1, 0)));
  assert(not(blkdev_geometry_valid(0, 4096, b, 0, 1, 1, 1, 0)));
  assert(not(blkdev_geometry_valid(1, 4096, b, n, 1, 1, 1, b * n)));
  assert(not(blkdev_geometry_valid(2 ^ 64 - 8, 4096, b, n, 1, 1, 1, b * n)));
  assert(not(blkdev_geometry_valid(0, 4096, 8, 2 ^ 64, 1, 1, 1, 8 * 2 ^ 64)));
  assert(not(blkdev_geometry_valid(0, 4096, b, n, 0, 1, 1, b * n)));
  blk_test_load_fault(256);
}

$[test]
function test_blkdev_read_progress_and_repeated_reads() -> unit = {
  blkdev_initialize();
  let medium = blkdev_medium;
  blk_test_write(40, to_bits_truncate(64, plat_blkdev_block_count - 1));
  blk_test_write(48, 0x0000000000000001);
  foreach (_i from 1 to 10) { assert(blk_test_read(24) == 0x0000000000000001) };
  assert(blkdev_remaining == plat_blkdev_read_steps);
  foreach (_i from 1 to (plat_blkdev_read_steps - 1)) {
    blkdev_progress(blkdev_epoch, false, None(), vector_init(zeros()));
    assert(blkdev_status == 1);
  };
  blkdev_progress(blkdev_epoch, false, None(), vector_init(zeros()));
  assert(blkdev_status == 2 & blkdev_medium == medium);
  assert(plat_blkdev_block_bytes > 0 & plat_blkdev_block_bytes <= blkdev_max_block_bytes);
  let offset = (plat_blkdev_block_count - 1) * plat_blkdev_block_bytes;
  assert(offset >= 0 & offset + plat_blkdev_block_bytes <= blkdev_max_bytes);
  foreach (word from 0 to (plat_blkdev_block_bytes / 8 - 1)) {
    let value = blk_test_read(256 + 8 * word);
    assert(value == blk_test_read(256 + 8 * word));
    foreach (i from 0 to 7) { assert(value[(8 * i + 7) .. (8 * i)] == medium[offset + 8 * word + i]) }
  };
  blkdev_progress(blkdev_epoch, true, None(), vector_init(ones()));
  assert(blkdev_status == 2 & blkdev_medium == medium);
}

$[test]
function test_blkdev_write_flush_ack_and_reset_durability() -> unit = {
  blkdev_initialize();
  let before = blkdev_medium;
  blk_test_prepare(plat_blkdev_block_count - 1, 0x0123456789abcdef);
  blk_test_write(256, 0xfedcba9876543210);
  blk_test_write(48, 0x0000000000000002);
  assert(blkdev_staging == vector_init(zeros()) & blkdev_written == zeros());
  // Executor ticks complete with no status loads.
  foreach (_i from 1 to plat_blkdev_write_steps) { tick_clock() };
  assert(blkdev_status == 2);
  blk_test_load_fault(256);
  let durable = blkdev_medium;
  let offset = (plat_blkdev_block_count - 1) * plat_blkdev_block_bytes;
  assert(plat_blkdev_block_bytes > 0);
  assert(offset >= 0 & offset + plat_blkdev_block_bytes <= blkdev_max_bytes);
  foreach (i from 0 to (plat_blkdev_block_bytes - 1)) {
    let expected : bits(64) = if i < 8 then 0xfedcba9876543210 else 0x0123456789abcdef;
    let byte = i % 8;
    assert(durable[offset + i] == expected[(8 * byte + 7) .. (8 * byte)]);
  };
  foreach (i from 0 to (blkdev_max_bytes - 1)) {
    if i < offset | i >= offset + plat_blkdev_block_bytes then assert(durable[i] == before[i]);
  };
  blkdev_reset(vector_init(ones()));
  assert(blkdev_medium == durable & blkdev_status == 0 & blkdev_block == zeros());
  blk_test_write(40, ones());
  blk_test_write(48, 0x0000000000000003);
  blk_test_complete(false, vector_init(zeros()));
  assert(blkdev_status == 2 & blkdev_medium == durable);
  blk_test_write(56, 0x0000000000000001);
  assert(blkdev_status == 0 & blkdev_command == 0 & blkdev_written == zeros());
  blk_test_write(48, 0x0000000000000002);
  assert(blkdev_status == 3 & blkdev_result == 3 & blkdev_medium == durable);
}

$[test]
function test_blkdev_validation_precedence_and_preparation() -> unit = {
  blkdev_initialize();
  let before = blkdev_medium;
  blk_test_write(40, ones());
  blk_test_write(48, ones());
  assert(blkdev_status == 3 & blkdev_result == 1 & blkdev_remaining == 0);
  blk_test_write(56, 0x0000000000000001);
  blk_test_write(40, to_bits_truncate(64, plat_blkdev_block_count));
  blk_test_write(48, 0x0000000000000002);
  assert(blkdev_status == 3 & blkdev_result == 2);
  blk_test_write(56, 0x0000000000000001);
  blk_test_prepare(0, ones());
  blk_test_write(40, zeros());
  blk_test_write(48, 0x0000000000000002);
  assert(blkdev_status == 3 & blkdev_result == 3 & blkdev_medium == before);
  assert(blkdev_staging == vector_init(zeros()) & blkdev_written == zeros());
}

$[test]
function test_blkdev_busy_terminal_and_direction_refusals() -> unit = {
  blkdev_initialize();
  blk_test_prepare(0, 0x0123456789abcdef);
  blk_test_write(48, 0x0000000000000002);
  let payload = blkdev_payload;
  let before = blkdev_medium;
  let epoch = blkdev_epoch;
  blk_test_store_fault(40, ones());
  blk_test_store_fault(48, ones());
  blk_test_store_fault(256, ones());
  blk_test_store_fault(56, 0x0000000000000001);
  blk_test_load_fault(256);
  assert(blkdev_status == 1 & blkdev_epoch == epoch & blkdev_payload == payload);
  assert(blkdev_medium == before & blkdev_remaining == plat_blkdev_write_steps);
  blk_test_complete(false, vector_init(zeros()));
  let durable = blkdev_medium;
  blk_test_store_fault(48, 0x0000000000000001);
  blk_test_store_fault(56, zeros());
  blk_test_load_fault(48);
  blk_test_load_fault(56);
  blk_test_load_fault(64);
  assert(blkdev_status == 2 & blkdev_medium == durable);
  blk_test_write(56, 0x0000000000000001);
  foreach (offset from 0 to 4) { blk_test_store_fault(8 * offset, ones()) };
  blk_test_store_fault(64, ones());
}

$[test]
function test_blkdev_complete_access_refuses_kinds_widths_crossings() -> unit = {
  blkdev_initialize();
  let before = blkdev_medium;
  let addr = blk_test_addr(40);
  match mem_write_value(addr, 16, ones(), Store(Data), false, false) { Err(_, _) => (), _ => assert(false) };
  match mem_write_value(addr, 4, ones(), Store(Data), false, false) { Err(_, _) => (), _ => assert(false) };
  match mem_write_value(blk_test_addr(41), 8, ones(), Store(Data), false, false) { Err(_, _) => (), _ => assert(false) };
  match mem_write_value(addr, 8, ones(), Atomic(AMOSWAP, false, false, Data, Data), false, false) { Err(_, _) => (), _ => assert(false) };
  match mem_write_ea(addr, 8, Atomic(AMOSWAP, false, false, Data, Data), false, false) { Err(_, _) => (), _ => assert(false) };
  match mem_read(InstructionFetch(), addr, 8, false, false) { Err(_, _) => (), _ => assert(false) };
  match mem_read(Atomic(AMOSWAP, false, false, Data, Data), addr, 8, false, false) { Err(_, _) => (), _ => assert(false) };
  match mem_read(Load(Data), blk_test_addr(-8), 16, false, false) { Err(_, _) => (), _ => assert(false) };
  match mem_write_value(blk_test_addr(unsigned(plat_blkdev_size) - 8), 16, ones(), Store(Data), false, false) { Err(_, _) => (), _ => assert(false) };
  assert(blkdev_status == 0 & blkdev_block == zeros() & blkdev_medium == before);
  assert(blkdev_written == zeros() & blkdev_staging == vector_init(zeros()));
}

$[test]
function test_blkdev_read_error_and_wrong_block() -> unit = {
  blkdev_initialize();
  blk_test_write(48, 0x0000000000000001);
  blk_test_complete(false, vector_init(zeros()));
  let first = blk_test_read(256);
  blk_test_write(56, 0x0000000000000001);
  blk_test_write(48, 0x0000000000000001);
  blk_test_complete(true, vector_init(zeros()));
  assert(blkdev_status == 3 & blkdev_result == 4 & blkdev_staging == vector_init(zeros()));
  blk_test_load_fault(256);
  blk_test_write(56, 0x0000000000000001);
  blk_test_write(48, 0x0000000000000001);
  foreach (_i from 1 to plat_blkdev_read_steps) {
    blkdev_progress(blkdev_epoch, false, Some(0x0000000000000001), vector_init(zeros()));
  };
  assert(blkdev_status == 2 & blk_test_read(256) != first);
}

$[test]
function test_blkdev_tears_order_reset_priority_and_stale_event() -> unit = {
  foreach (pattern from 0 to 2) {
    blkdev_initialize();
    blk_test_prepare(1, ones());
    blk_test_write(48, 0x0000000000000002);
    let old_epoch = blkdev_epoch;
    // Faults precede the tear: old means these bytes, not submission bytes.
    blkdev_corrupt(0x0000000000000001, vector_init(0x3c));
    let before = blkdev_medium;
    let mask : blkdev_buffer = vector_init(if pattern == 0 then 0x00 else if pattern == 1 then 0xff else 0xa5);
    foreach (_i from 1 to (plat_blkdev_write_steps - 1)) {
      blkdev_progress(blkdev_epoch, false, None(), vector_init(zeros()));
    };
    assert(blkdev_medium == before);
    blkdev_boundary(true, true, old_epoch, false, None(), mask);
    assert(blkdev_status == 0 & blkdev_command == 0 & blkdev_remaining == 0);
    assert(blkdev_payload == vector_init(zeros()) & blkdev_staging == vector_init(zeros()));
    assert(plat_blkdev_block_bytes > 0 & 2 * plat_blkdev_block_bytes <= blkdev_max_bytes);
    foreach (i from 0 to (blkdev_max_bytes - 1)) {
      if i >= plat_blkdev_block_bytes & i < 2 * plat_blkdev_block_bytes then {
        assert(blkdev_medium[i] == (0x3c | (if pattern == 0 then 0x00 else if pattern == 1 then 0xff else 0xa5)));
      } else assert(blkdev_medium[i] == before[i]);
    };
    blk_test_write(48, 0x0000000000000001);
    blk_test_complete(false, vector_init(zeros()));
    let after = blkdev_medium;
    let staging = blkdev_staging;
    blkdev_progress(old_epoch, false, None(), vector_init(ones()));
    assert(blkdev_status == 2 & blkdev_medium == after & blkdev_staging == staging);
  }
}

$[test]
function test_blkdev_io_write_masks_and_flush_error() -> unit = {
  foreach (pattern from 0 to 2) {
    blkdev_initialize();
    blk_test_prepare(0, zeros());
    blk_test_write(48, 0x0000000000000002);
    blkdev_corrupt(zeros(), vector_init(0xff));
    let mask : blkdev_buffer = vector_init(if pattern == 0 then 0x00 else if pattern == 1 then 0xff else 0xa5);
    blk_test_complete(true, mask);
    assert(blkdev_status == 3 & blkdev_result == 4);
    assert(plat_blkdev_block_bytes > 0 & plat_blkdev_block_bytes <= blkdev_max_bytes);
    foreach (i from 0 to (plat_blkdev_block_bytes - 1)) {
      assert(blkdev_medium[i] == (if pattern == 0 then 0xff else if pattern == 1 then 0x00 else 0x5a));
    };
    blk_test_write(56, 0x0000000000000001);
    blk_test_prepare(0, ones());
    blk_test_write(48, 0x0000000000000002);
    blk_test_complete(false, vector_init(zeros()));
    let durable = blkdev_medium;
    blk_test_write(56, 0x0000000000000001);
    blk_test_write(48, 0x0000000000000003);
    blk_test_complete(true, vector_init(ones()));
    assert(blkdev_status == 3 & blkdev_result == 4 & blkdev_medium == durable);
  }
}
