// SPDX-License-Identifier: BSD-2-Clause
// The modeled block device's host backing image (M5.3d).
//
// interfaces/block-device-contract.md makes the device write-through: a WRITE
// is durable at its block before DONE is observable, and "the host adapter
// cannot equate a buffered host write with that boundary: its success path
// must establish persistence in the backing image used for restart, and an
// adapter that cannot do so reports IO". The model's persistent register
// (sys/block_device.sail) is the medium within one process. This adapter is
// the medium across processes: it binds the register to one host file, loads
// that file's bytes before the first instruction, and makes every change the
// model reports durable with a data sync before answering. The model turns a
// false answer into ERROR/IO, and every later answer is false.
//
// What the adapter does not decide. It chooses no tear: a modeled crash is the
// model's explicit reset input, whose mask the model applies before it asks the
// adapter to persist the result. A host process that exits or is killed
// between two answers leaves the image as the last answer left it, so an
// incomplete command changes nothing and staging is lost; killing a process is
// still not evidence of the model's crash transition. A host write interrupted
// inside one answer can leave a mixture of the old and new bytes of the block
// being persisted, which is inside the contract's tear class but is not a
// recorded mask.
//
// The image layout, version 1. Bytes 0..7 are the magic "VOSBLK01"; bytes
// 8..15 and 16..23 are the block length B and block count N, unsigned little
// endian; bytes 24..31 are zero; then exactly N * B medium bytes in block
// order. The header binds an image to a geometry, so an image written for
// another geometry with the same total length is refused rather than read as
// this one. There is no implicit blank disk, discovery or truncation: opening
// requires an existing file of exactly this length and header, and creating
// requires that no file exist at the path. Host paths never reach the guest.
#pragma once

#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

namespace blkdev {

// A startup refusal. It is raised before the adapter writes any byte of an
// existing image and before the model's medium is replaced.
class refusal : public std::runtime_error {
public:
  using std::runtime_error::runtime_error;
};

struct geometry {
  uint64_t block_bytes = 0;
  uint64_t block_count = 0;
};

constexpr uint64_t header_bytes = 32;

// The kinds sys/block_device.sail passes to `blkdev_host_persist`.
enum class event : uint64_t {
  read = 1,
  write = 2,
  flush = 3,
  write_error_tear = 4,
  reset_tear = 5,
  media_fault = 6,
};

const char *event_name(uint64_t kind);

// FIPS 180-4 SHA-256 of `length` bytes, as 64 lowercase hex digits. It names
// images in receipts; it authenticates nothing.
std::string sha256_hex(const uint8_t *data, size_t length);

// The header a version-1 image of this geometry begins with.
std::vector<uint8_t> image_header(geometry g);

class image {
public:
  enum class mode { open, create };

  // Binds `path` for this composition's geometry. `create` requires that no
  // file exist at `path`, writes the header and `fixture` (exactly N * B bytes)
  // to a new file, syncs it and links it into place, so a crash leaves either
  // no image or a complete one. Both modes then open the file, take an
  // exclusive lock for the run and read it whole. `receipt`, when nonempty,
  // names a new file (an existing one is refused) that receives one JSON object
  // per line for the open, each persistence event and the close. Throws
  // `refusal`.
  image(const std::string &path, mode how, geometry g, const std::vector<uint8_t> &fixture,
        const std::string &receipt = {});
  ~image();
  image(const image &) = delete;
  image &operator=(const image &) = delete;

  geometry shape() const { return m_geometry; }

  // The medium bytes the file held when it was bound.
  const std::vector<uint8_t> &opened_bytes() const { return m_opened; }

  // Replaces the model's medium register with the opened bytes and zeroes the
  // register beyond N * B, which is what the model's own startup does with a
  // configured fixture. Throws `refusal` if the register cannot hold them.
  void load(uint64_t *medium, size_t medium_len);

  // One persistence event from the model: write medium bytes [offset, offset +
  // length) through to the image and sync, or for a FLUSH issue the barrier.
  // Returns whether every change since binding is durable in the image.
  bool persist(uint64_t kind, uint64_t offset, uint64_t length, const uint64_t *medium,
               size_t medium_len);

  bool healthy() const { return !m_failed; }

  // Records the image's current on-disk identity in the receipt, if any, and
  // releases the file. Later events answer false.
  void close();

private:
  void bind(mode how, const std::vector<uint8_t> &fixture);
  [[noreturn]] void refuse(const std::string &why);
  void note(const std::string &json);
  void release();

  std::string m_path;
  geometry m_geometry;
  int m_fd = -1;
  FILE *m_receipt = nullptr;
  bool m_failed = false;
  std::vector<uint8_t> m_opened;
};

} // namespace blkdev
