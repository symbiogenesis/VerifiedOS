// SPDX-License-Identifier: BSD-2-Clause
// The modeled block device's host backing image (M5.3d). See blkdev_image.h.
#include "blkdev_image.h"

#include <cerrno>
#include <cinttypes>
#include <cstring>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

namespace blkdev {
namespace {

// FIPS 180-4 s4.2.2 and s5.3.3.
constexpr uint32_t round_constants[64] = {
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
};

constexpr uint32_t initial_hash[8] = {
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
};

uint32_t rotr(uint32_t x, unsigned n) {
  return (x >> n) | (x << (32 - n));
}

void compress(uint32_t h[8], const uint8_t *block) {
  uint32_t w[64];
  for (unsigned t = 0; t < 16; ++t) {
    w[t] = (uint32_t{block[4 * t]} << 24) | (uint32_t{block[4 * t + 1]} << 16) |
           (uint32_t{block[4 * t + 2]} << 8) | uint32_t{block[4 * t + 3]};
  }
  for (unsigned t = 16; t < 64; ++t) {
    const uint32_t s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >> 3);
    const uint32_t s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >> 10);
    w[t] = w[t - 16] + s0 + w[t - 7] + s1;
  }
  uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], k = h[7];
  for (unsigned t = 0; t < 64; ++t) {
    const uint32_t t1 = k + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) +
                        round_constants[t] + w[t];
    const uint32_t t2 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
    k = g;
    g = f;
    f = e;
    e = d + t1;
    d = c;
    c = b;
    b = a;
    a = t1 + t2;
  }
  h[0] += a;
  h[1] += b;
  h[2] += c;
  h[3] += d;
  h[4] += e;
  h[5] += f;
  h[6] += g;
  h[7] += k;
}

std::string quoted(const std::string &text) {
  std::string out = "\"";
  for (unsigned char c : text) {
    if (c == '"' || c == '\\') {
      out += '\\';
      out += static_cast<char>(c);
    } else if (c < 0x20) {
      char escaped[8];
      std::snprintf(escaped, sizeof escaped, "\\u%04x", c);
      out += escaped;
    } else {
      out += static_cast<char>(c);
    }
  }
  return out + "\"";
}

std::string number(uint64_t value) {
  return std::to_string(value);
}

void put_u64(std::vector<uint8_t> &out, uint64_t value) {
  for (unsigned i = 0; i < 8; ++i) {
    out.push_back(static_cast<uint8_t>(value >> (8 * i)));
  }
}

uint64_t get_u64(const std::vector<uint8_t> &in, size_t at) {
  uint64_t value = 0;
  for (unsigned i = 0; i < 8; ++i) {
    value |= uint64_t{in[at + i]} << (8 * i);
  }
  return value;
}

bool write_all(int fd, const uint8_t *data, size_t length, uint64_t at) {
  while (length != 0) {
    const ssize_t done = pwrite(fd, data, length, static_cast<off_t>(at));
    if (done < 0) {
      if (errno == EINTR) {
        continue;
      }
      return false;
    }
    if (done == 0) {
      errno = EIO;
      return false;
    }
    data += done;
    length -= static_cast<size_t>(done);
    at += static_cast<uint64_t>(done);
  }
  return true;
}

bool read_all(int fd, std::vector<uint8_t> &out, uint64_t length) {
  out.assign(length, 0);
  uint64_t at = 0;
  while (at < length) {
    const ssize_t done = pread(fd, out.data() + at, length - at, static_cast<off_t>(at));
    if (done < 0) {
      if (errno == EINTR) {
        continue;
      }
      return false;
    }
    if (done == 0) {
      errno = EIO;
      return false;
    }
    at += static_cast<uint64_t>(done);
  }
  return true;
}

std::string error_text() {
  return std::strerror(errno);
}

std::string parent_directory(const std::string &path) {
  const size_t slash = path.find_last_of('/');
  if (slash == std::string::npos) {
    return ".";
  }
  return slash == 0 ? "/" : path.substr(0, slash);
}

constexpr char magic[8] = {'V', 'O', 'S', 'B', 'L', 'K', '0', '1'};

} // namespace

const char *event_name(uint64_t kind) {
  switch (kind) {
  case static_cast<uint64_t>(event::read):
    return "read";
  case static_cast<uint64_t>(event::write):
    return "write";
  case static_cast<uint64_t>(event::flush):
    return "flush";
  case static_cast<uint64_t>(event::write_error_tear):
    return "write-error-tear";
  case static_cast<uint64_t>(event::reset_tear):
    return "reset-tear";
  case static_cast<uint64_t>(event::media_fault):
    return "media-fault";
  default:
    return "unknown";
  }
}

std::string sha256_hex(const uint8_t *data, size_t length) {
  uint32_t h[8];
  std::memcpy(h, initial_hash, sizeof h);
  const size_t whole = length / 64;
  for (size_t i = 0; i < whole; ++i) {
    compress(h, data + 64 * i);
  }
  uint8_t tail[128] = {};
  const size_t rest = length - 64 * whole;
  if (rest != 0) {
    std::memcpy(tail, data + 64 * whole, rest);
  }
  tail[rest] = 0x80;
  const size_t tail_bytes = rest + 1 + 8 <= 64 ? 64 : 128;
  const uint64_t bits = static_cast<uint64_t>(length) * 8;
  for (unsigned i = 0; i < 8; ++i) {
    tail[tail_bytes - 1 - i] = static_cast<uint8_t>(bits >> (8 * i));
  }
  compress(h, tail);
  if (tail_bytes == 128) {
    compress(h, tail + 64);
  }
  char out[65];
  for (unsigned i = 0; i < 8; ++i) {
    std::snprintf(out + 8 * i, 9, "%08" PRIx32, h[i]);
  }
  return std::string(out, 64);
}

std::vector<uint8_t> image_header(geometry g) {
  std::vector<uint8_t> out(magic, magic + sizeof magic);
  put_u64(out, g.block_bytes);
  put_u64(out, g.block_count);
  put_u64(out, 0);
  return out;
}

image::image(const std::string &path, mode how, geometry g, const std::vector<uint8_t> &fixture,
             const std::string &receipt)
    : m_path(path), m_geometry(g) {
  try {
    if (!receipt.empty()) {
      // "x": an existing receipt is evidence of another run and is not replaced.
      m_receipt = std::fopen(receipt.c_str(), "wx");
      if (m_receipt == nullptr) {
        refuse("cannot create receipt " + receipt + ": " + error_text());
      }
    }
    bind(how, fixture);
  } catch (...) {
    release();
    throw;
  }
}

image::~image() {
  close();
}

void image::refuse(const std::string &why) {
  note("{\"event\":\"refused\",\"image\":" + quoted(m_path) + ",\"reason\":" + quoted(why) + "}");
  throw refusal(why);
}

void image::note(const std::string &json) {
  if (m_receipt != nullptr) {
    std::fputs(json.c_str(), m_receipt);
    std::fputc('\n', m_receipt);
    std::fflush(m_receipt);
  }
}

void image::release() {
  if (m_fd >= 0) {
    ::close(m_fd);
    m_fd = -1;
  }
  if (m_receipt != nullptr) {
    std::fclose(m_receipt);
    m_receipt = nullptr;
  }
}

void image::bind(mode how, const std::vector<uint8_t> &fixture) {
  const geometry g = m_geometry;
  if (g.block_bytes == 0 || g.block_count == 0 || g.block_count > UINT64_MAX / g.block_bytes ||
      g.block_bytes * g.block_count > UINT64_MAX - header_bytes) {
    refuse("the composition's geometry has no image length");
  }
  const uint64_t medium_bytes = g.block_bytes * g.block_count;
  const uint64_t file_bytes = header_bytes + medium_bytes;

  if (how == mode::create) {
    struct stat existing {};
    if (lstat(m_path.c_str(), &existing) == 0) {
      refuse("an image already exists at " + m_path + "; creation never replaces one");
    }
    if (errno != ENOENT) {
      refuse("cannot inspect " + m_path + ": " + error_text());
    }
    if (fixture.size() != medium_bytes) {
      refuse("the fixture holds " + number(fixture.size()) + " bytes and the geometry needs " +
             number(medium_bytes));
    }
    // Written beside the destination and linked into place: link() refuses an
    // existing destination, and a crash leaves no partial image at the path.
    const std::string partial = m_path + ".partial." + number(static_cast<uint64_t>(getpid()));
    const int fd = ::open(partial.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0644);
    if (fd < 0) {
      refuse("cannot create " + partial + ": " + error_text());
    }
    std::vector<uint8_t> bytes = image_header(g);
    bytes.insert(bytes.end(), fixture.begin(), fixture.end());
    bool written = write_all(fd, bytes.data(), bytes.size(), 0) && fsync(fd) == 0;
    std::string failure = written ? std::string{} : error_text();
    ::close(fd);
    if (written && link(partial.c_str(), m_path.c_str()) != 0) {
      written = false;
      failure = error_text();
    }
    unlink(partial.c_str());
    if (!written) {
      refuse("cannot create " + m_path + ": " + failure);
    }
    const int dir = ::open(parent_directory(m_path).c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    const bool dir_synced = dir >= 0 && fsync(dir) == 0;
    const std::string dir_failure = dir_synced ? std::string{} : error_text();
    if (dir >= 0) {
      ::close(dir);
    }
    if (!dir_synced) {
      refuse("created " + m_path + " but could not sync its directory: " + dir_failure);
    }
  }

  m_fd = ::open(m_path.c_str(), O_RDWR | O_CLOEXEC);
  if (m_fd < 0) {
    refuse("cannot open image " + m_path + ": " + error_text());
  }
  // One run owns an image: two writers would interleave their persistence.
  if (flock(m_fd, LOCK_EX | LOCK_NB) != 0) {
    refuse(errno == EWOULDBLOCK ? "image " + m_path + " is held by another run"
                                : "image " + m_path + " cannot be locked: " + error_text());
  }
  struct stat st {};
  if (fstat(m_fd, &st) != 0) {
    refuse("cannot inspect image " + m_path + ": " + error_text());
  }
  if (!S_ISREG(st.st_mode)) {
    refuse("image " + m_path + " is not a regular file");
  }
  const uint64_t size = static_cast<uint64_t>(st.st_size);
  if (size < header_bytes) {
    refuse("image " + m_path + " holds " + number(size) + " bytes, fewer than its header");
  }
  std::vector<uint8_t> header;
  if (!read_all(m_fd, header, header_bytes)) {
    refuse("cannot read image " + m_path + ": " + error_text());
  }
  if (std::memcmp(header.data(), magic, sizeof magic) != 0) {
    refuse("image " + m_path + " does not begin with the version-1 magic");
  }
  const uint64_t b = get_u64(header, 8);
  const uint64_t n = get_u64(header, 16);
  if (b != g.block_bytes || n != g.block_count) {
    refuse("image " + m_path + " records geometry B=" + number(b) + " N=" + number(n) +
           " and the composition declares B=" + number(g.block_bytes) + " N=" + number(g.block_count));
  }
  if (get_u64(header, 24) != 0) {
    refuse("image " + m_path + " has nonzero reserved header bytes");
  }
  if (size != file_bytes) {
    refuse("image " + m_path + " holds " + number(size) + " bytes and its geometry needs exactly " +
           number(file_bytes));
  }
  std::vector<uint8_t> whole;
  if (!read_all(m_fd, whole, file_bytes)) {
    refuse("cannot read image " + m_path + ": " + error_text());
  }
  m_opened.assign(whole.begin() + static_cast<std::ptrdiff_t>(header_bytes), whole.end());
  note("{\"schema\":\"verifiedos-blkdev-receipt-1\",\"event\":\"open\",\"mode\":" +
       quoted(how == mode::create ? "create" : "open") + ",\"image\":" + quoted(m_path) +
       ",\"block_bytes\":" + number(g.block_bytes) + ",\"block_count\":" + number(g.block_count) +
       ",\"sha256\":" + quoted(sha256_hex(whole.data(), whole.size())) + "}");
}

void image::load(uint64_t *medium, size_t medium_len) {
  if (m_opened.size() > medium_len) {
    refuse("the model's medium register holds " + number(medium_len) + " bytes and the image " +
           number(m_opened.size()));
  }
  for (size_t i = 0; i < medium_len; ++i) {
    medium[i] = i < m_opened.size() ? m_opened[i] : 0;
  }
}

bool image::persist(uint64_t kind, uint64_t offset, uint64_t length, const uint64_t *medium,
                    size_t medium_len) {
  const uint64_t medium_bytes = m_geometry.block_bytes * m_geometry.block_count;
  const bool known = kind >= static_cast<uint64_t>(event::read) &&
                     kind <= static_cast<uint64_t>(event::media_fault);
  bool durable = m_fd >= 0 && !m_failed && known;
  std::string failure;
  if (!known) {
    failure = "unknown event kind";
  }
  if (durable && length != 0) {
    if (offset > medium_bytes || length > medium_bytes - offset || offset + length > medium_len) {
      durable = false;
      failure = "range outside the image";
    } else {
      std::vector<uint8_t> bytes(length);
      for (uint64_t i = 0; i < length && durable; ++i) {
        const uint64_t value = medium[offset + i];
        if (value > 0xff) {
          durable = false;
          failure = "medium element is not a byte";
        }
        bytes[i] = static_cast<uint8_t>(value);
      }
      if (durable && !write_all(m_fd, bytes.data(), bytes.size(), header_bytes + offset)) {
        durable = false;
        failure = error_text();
      }
    }
  }
  // The data sync is the durability boundary for a change, and a FLUSH's
  // barrier; a READ changes nothing and only asks.
  if (durable && (length != 0 || kind == static_cast<uint64_t>(event::flush)) && fdatasync(m_fd) != 0) {
    durable = false;
    failure = error_text();
  }
  if (!durable) {
    m_failed = true;
  }
  std::string record = "{\"event\":\"persist\",\"kind\":" + quoted(event_name(kind)) +
                       ",\"offset\":" + number(offset) + ",\"length\":" + number(length) +
                       ",\"durable\":" + (durable ? "true" : "false");
  if (!failure.empty()) {
    record += ",\"error\":" + quoted(failure);
  }
  note(record + "}");
  return durable;
}

void image::close() {
  if (m_fd >= 0 && m_receipt != nullptr) {
    struct stat st {};
    std::vector<uint8_t> whole;
    if (fstat(m_fd, &st) == 0 && read_all(m_fd, whole, static_cast<uint64_t>(st.st_size))) {
      note("{\"event\":\"close\",\"healthy\":" + std::string(m_failed ? "false" : "true") +
           ",\"sha256\":" + quoted(sha256_hex(whole.data(), whole.size())) + "}");
    } else {
      note("{\"event\":\"close\",\"healthy\":" + std::string(m_failed ? "false" : "true") +
           ",\"error\":" + quoted(error_text()) + "}");
    }
  }
  release();
}

} // namespace blkdev
