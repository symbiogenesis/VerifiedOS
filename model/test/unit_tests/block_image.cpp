// SPDX-License-Identifier: BSD-2-Clause
// M5.3d: the modeled block device's host backing image across process exit.
//
// Each phase that runs the device is its own forked process running the actual
// generated Sail model with the emulator's image adapter (blkdev_image.h)
// behind `blkdev_host_persist`. A phase that models an abrupt exit ends with
// _exit at the chosen point, so no destructor, close or flush of this program
// stands between the model's last persistence answer and the process ending.
// The parent then reads the image file itself and reopens it in a fresh
// process. Expected bytes are computed in the parent from the fixture, the
// payloads and the masks, never read back from the image under test.
#include <sail_config.h>
#include "blkdev_image.h"
#include "config_utils.h"
#include "sail_riscv_model.h"
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <sys/file.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>

namespace {
using Bytes = std::vector<uint8_t>;
using Mode = blkdev::image::mode;

[[noreturn]] void fail(const std::string &message) {
  throw std::runtime_error(message);
}

void require(bool condition, const std::string &message) {
  if (!condition) {
    fail(message);
  }
}

// The generated model with its persistence boundary routed to a bound image,
// as ModelImpl routes it in the emulator.
class ImageModel final : public hart::Model {
public:
  blkdev::image *bound = nullptr;
  bool dispatch() { return zplat_have_blkdev && !get_config_rvfi(UNIT); }
  bool blkdev_host_persist(uint64_t kind, uint64_t offset, uint64_t length) override {
    return bound == nullptr || bound->persist(kind, offset, length, zblkdev_medium.data, zblkdev_medium.len);
  }
};

uint64_t quantity(const sail_int n) {
  require(mpz_sgn(n) >= 0 && mpz_fits_ulong_p(n), "fixture quantity must fit the host");
  return mpz_get_ui(n);
}

// Whatever a phase's process knows about the fixture, read from the model.
struct Shape {
  size_t block_bytes = 0, blocks = 0, register_bytes = 0, max_block = 0;
  size_t steps[4] = {0, 0, 0, 0};
  Bytes fixture;
  size_t medium_bytes() const { return block_bytes * blocks; }
};

class Device {
public:
  ImageModel m;
  std::unique_ptr<blkdev::image> image;
  Shape shape;

  Device() {
    m.model_init();
    require(m.dispatch(), "device dispatch must be enabled");
    // The model's own startup copy of the configured fixture, as init_model makes it.
    m.zblkdev_initializze(UNIT);
    shape.block_bytes = quantity(m.zplat_blkdev_block_bytes);
    shape.blocks = quantity(m.zplat_blkdev_block_count);
    shape.register_bytes = m.zblkdev_medium.len;
    shape.max_block = static_cast<size_t>(m.zblkdev_max_block_bytes);
    shape.steps[1] = quantity(m.zplat_blkdev_read_steps);
    shape.steps[2] = quantity(m.zplat_blkdev_write_steps);
    shape.steps[3] = quantity(m.zplat_blkdev_flush_steps);
    require(shape.block_bytes > 0 && shape.block_bytes % 8 == 0 && shape.blocks >= 2 &&
            shape.medium_bytes() <= shape.register_bytes && shape.block_bytes <= shape.max_block,
            "fixture geometry is inadmissible");
    for (size_t i = 0; i < shape.medium_bytes(); ++i) {
      shape.fixture.push_back(static_cast<uint8_t>(m.zblkdev_medium.data[i]));
    }
  }

  blkdev::geometry geometry() const { return {shape.block_bytes, shape.blocks}; }

  // As the emulator binds: open or create, then load unless the negative
  // control asks for the startup that recreates the fixture.
  void bind(const std::string &path, Mode how, const std::string &receipt = {}, bool load = true) {
    image = std::make_unique<blkdev::image>(path, how, geometry(), shape.fixture, receipt);
    if (load) {
      image->load(m.zblkdev_medium.data, m.zblkdev_medium.len);
    }
    m.bound = image.get();
  }

  Bytes medium() const {
    Bytes out;
    for (size_t i = 0; i < m.zblkdev_medium.len; ++i) {
      out.push_back(static_cast<uint8_t>(m.zblkdev_medium.data[i]));
    }
    return out;
  }

  void store(size_t offset, uint64_t value) {
    sail_int at;
    mpz_init_set_ui(at, offset);
    m.zblk_test_write(at, value);
    mpz_clear(at);
  }

  uint64_t load(size_t offset) {
    sail_int at;
    mpz_init_set_ui(at, offset);
    const uint64_t value = m.zblk_test_read(at);
    mpz_clear(at);
    return value;
  }

  uint64_t status() { return load(24); }
  uint64_t result() { return load(32); }

  void stage(size_t block, const Bytes &payload) {
    store(40, block);
    for (size_t i = 0; i < shape.block_bytes; i += 8) {
      uint64_t word = 0;
      for (size_t j = 0; j < 8; ++j) {
        word |= uint64_t{payload[i + j]} << (8 * j);
      }
      store(256 + i, word);
    }
  }

  std::vector<uint64_t> buffer(const Bytes &bytes) const {
    std::vector<uint64_t> out(shape.max_block, 0);
    for (size_t i = 0; i < bytes.size() && i < out.size(); ++i) {
      out[i] = bytes[i];
    }
    return out;
  }

  static hart::zoptionzIbzK none() {
    hart::zoptionzIbzK result{};
    result.kind = hart::Kind_zNonezIbzK;
    result.variants.zNonezIbzK = UNIT;
    return result;
  }

  void step(bool error, const Bytes &mask) {
    std::vector<uint64_t> raw = buffer(mask);
    hart::zz5vecz8z5bv8z9 view{raw.size(), raw.data()};
    m.zblkdev_progress(m.zblkdev_epoch, error, none(), view);
  }

  void steps(size_t count) {
    for (size_t i = 0; i < count; ++i) {
      step(false, Bytes{});
    }
  }

  void reset_with(const Bytes &mask) {
    std::vector<uint64_t> raw = buffer(mask);
    hart::zz5vecz8z5bv8z9 view{raw.size(), raw.data()};
    m.zblkdev_boundary(true, true, m.zblkdev_epoch, false, none(), view);
  }

  void corrupt(size_t block, const Bytes &bytes) {
    std::vector<uint64_t> raw = buffer(bytes);
    hart::zz5vecz8z5bv8z9 view{raw.size(), raw.data()};
    m.zblkdev_corrupt(block, view);
  }

  // A complete command with fault-free progress, acknowledged.
  void command(uint64_t opcode, uint64_t expect_status, uint64_t expect_result) {
    store(48, opcode);
    require(status() == 1, "an accepted command must be busy");
    steps(shape.steps[opcode]);
    require(status() == expect_status && result() == expect_result,
            "command " + std::to_string(opcode) + " ended " + std::to_string(status()) + "/" +
              std::to_string(result()) + ", expected " + std::to_string(expect_status) + "/" +
              std::to_string(expect_result));
    store(56, 1);
  }

  Bytes read_block(size_t block) {
    store(40, block);
    store(48, 1);
    steps(shape.steps[1]);
    require(status() == 2 && result() == 0, "a READ of block " + std::to_string(block) + " must complete");
    Bytes out(shape.block_bytes);
    for (size_t i = 0; i < shape.block_bytes; i += 8) {
      const uint64_t word = load(256 + i);
      for (size_t j = 0; j < 8; ++j) {
        out[i + j] = static_cast<uint8_t>(word >> (8 * j));
      }
    }
    store(56, 1);
    return out;
  }

  // Reset volatile state: nothing but the medium survives a process.
  void require_clean() {
    bool clean = m.zblkdev_status == 0 && m.zblkdev_result == 0 && m.zblkdev_block == 0 &&
                 m.zblkdev_pending_block == 0 && m.zblkdev_command == 0 &&
                 mpz_sgn(m.zblkdev_remaining) == 0 && mpz_sgn(*m.zblkdev_written.bits) == 0;
    for (const auto *v : {&m.zblkdev_staging, &m.zblkdev_payload}) {
      for (size_t i = 0; i < v->len; ++i) {
        clean = clean && v->data[i] == 0;
      }
    }
    require(clean, "a reopened device must hold reset volatile state");
  }
};

[[noreturn]] void vanish() {
  _exit(0);
}

// Runs `body` in a forked process. Exit 0 is a completed or vanished body, 3 a
// refusal the body did not catch, 1 a failed check.
int run_child(const std::function<void()> &body) {
  std::fflush(stdout);
  std::fflush(stderr);
  const pid_t pid = fork();
  require(pid >= 0, "fork failed");
  if (pid == 0) {
    int code = 0;
    try {
      body();
    } catch (const blkdev::refusal &refused) {
      std::fprintf(stderr, "block image child: refused: %s\n", refused.what());
      code = 3;
    } catch (const std::exception &error) {
      std::fprintf(stderr, "block image child: FAIL %s\n", error.what());
      code = 1;
    }
    std::fflush(stderr);
    _exit(code);
  }
  int wstatus = 0;
  while (waitpid(pid, &wstatus, 0) < 0) {
    require(errno == EINTR, "waitpid failed");
  }
  require(WIFEXITED(wstatus), "a phase process did not exit normally");
  return WEXITSTATUS(wstatus);
}

bool exists(const std::string &path) {
  struct stat st {};
  return lstat(path.c_str(), &st) == 0;
}

Bytes file_bytes(const std::string &path) {
  Bytes out;
  FILE *f = std::fopen(path.c_str(), "rb");
  require(f != nullptr, "cannot read " + path);
  int c = 0;
  while ((c = std::fgetc(f)) != EOF) {
    out.push_back(static_cast<uint8_t>(c));
  }
  std::fclose(f);
  return out;
}

void write_file(const std::string &path, const Bytes &bytes) {
  FILE *f = std::fopen(path.c_str(), "wb");
  require(f != nullptr, "cannot write " + path);
  require(std::fwrite(bytes.data(), 1, bytes.size(), f) == bytes.size(), "short write to " + path);
  std::fclose(f);
}

std::vector<std::string> lines(const std::string &path) {
  std::vector<std::string> out;
  std::string line;
  for (uint8_t c : file_bytes(path)) {
    if (c == '\n') {
      out.push_back(line);
      line.clear();
    } else {
      line += static_cast<char>(c);
    }
  }
  if (!line.empty()) {
    out.push_back(line);
  }
  return out;
}

bool contains(const std::string &text, const std::string &part) {
  return text.find(part) != std::string::npos;
}

std::string hex(const Bytes &bytes) {
  return blkdev::sha256_hex(bytes.data(), bytes.size());
}

void compare(const Bytes &actual, const Bytes &expected, const std::string &what) {
  require(actual.size() == expected.size(), what + ": length " + std::to_string(actual.size()) +
                                              ", expected " + std::to_string(expected.size()));
  for (size_t i = 0; i < actual.size(); ++i) {
    require(actual[i] == expected[i], what + " byte " + std::to_string(i) + " expected " +
                                        std::to_string(expected[i]) + " got " + std::to_string(actual[i]));
  }
}

class Campaign {
  std::string dir, emulator;
  bool negative_byte, negative_reload;
  Shape shape;
  Bytes zero_mask, full_mask, split_mask;
  size_t reopens = 0, process_exits = 0, tears = 0, refusals = 0, emulator_runs = 0;
  std::vector<std::string> made;

  std::string path(const std::string &name) {
    const std::string full = dir + "/" + name;
    made.push_back(full);
    return full;
  }

  Bytes header() const { return blkdev::image_header({shape.block_bytes, shape.blocks}); }

  // The image a medium is expected to leave: the header, then the medium.
  Bytes image_of(const Bytes &medium) const {
    Bytes out = header();
    out.insert(out.end(), medium.begin(), medium.end());
    return out;
  }

  Bytes payload(size_t seed) const {
    Bytes out(shape.block_bytes);
    for (size_t i = 0; i < out.size(); ++i) {
      out[i] = static_cast<uint8_t>((i * 29 + seed * 71 + 0x3d) ^ (seed << 4));
    }
    return out;
  }

  Bytes block_of(const Bytes &medium, size_t block) const {
    const auto first = medium.begin() + static_cast<std::ptrdiff_t>(block * shape.block_bytes);
    return Bytes(first, first + static_cast<std::ptrdiff_t>(shape.block_bytes));
  }

  void put_block(Bytes &medium, size_t block, const Bytes &bytes) const {
    std::copy(bytes.begin(), bytes.end(), medium.begin() + static_cast<std::ptrdiff_t>(block * shape.block_bytes));
  }

  void mix(Bytes &medium, size_t block, const Bytes &fresh, const Bytes &mask) const {
    for (size_t i = 0; i < shape.block_bytes; ++i) {
      uint8_t &old = medium[block * shape.block_bytes + i];
      old = static_cast<uint8_t>((old & ~mask[i]) | (fresh[i] & mask[i]));
    }
  }

  // A fresh process opens the image and must present exactly `expected`,
  // through the register and through PIO READs, with reset volatile state.
  void reopen(const std::string &image, const Bytes &medium, const std::string &receipt = {}) {
    Bytes expected = medium;
    if (negative_byte && reopens == 0) {
      expected[0] ^= 1;
    }
    const bool skip_load = negative_reload;
    const int code = run_child([&] {
      Device d;
      d.bind(image, Mode::open, receipt, !skip_load);
      Bytes whole = expected;
      whole.resize(d.shape.register_bytes, 0);
      compare(d.medium(), whole, "reopened medium");
      d.require_clean();
      for (size_t block = 0; block < d.shape.blocks; ++block) {
        compare(d.read_block(block), block_of(expected, block), "reopened READ of block " + std::to_string(block));
      }
      d.image->close();
    });
    require(code == 0, "the reopen of " + image + " failed");
    compare(file_bytes(image), image_of(medium), "image after a read-only reopen");
    ++reopens;
  }

  void expect_refusal(const std::string &image, const std::string &why) {
    const bool present = exists(image);
    const Bytes before = present ? file_bytes(image) : Bytes{};
    const Bytes fixture = shape.fixture;
    const int code = run_child([&] {
      Device d;
      try {
        d.bind(image, Mode::open);
      } catch (const blkdev::refusal &refused) {
        // Refused before the register was replaced: the startup fixture copy stands.
        compare(d.medium(), [&] { Bytes w = fixture; w.resize(d.shape.register_bytes, 0); return w; }(),
                "medium after a refused bind");
        std::fprintf(stderr, "block image: expected refusal (%s): %s\n", why.c_str(), refused.what());
        std::fflush(stderr);
        _exit(3);
      }
    });
    require(code == 3, "an image with " + why + " was not refused");
    require(exists(image) == present, "a refused bind created or removed " + image);
    if (present) {
      compare(file_bytes(image), before, "refused image " + why);
    }
    ++refusals;
  }

  int emulate(const std::vector<std::string> &args, const std::string &log) {
    std::fflush(stdout);
    std::fflush(stderr);
    const pid_t pid = fork();
    require(pid >= 0, "fork failed");
    if (pid == 0) {
      const int fd = ::open(log.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
      if (fd < 0) {
        _exit(126);
      }
      dup2(fd, 1);
      dup2(fd, 2);
      std::vector<char *> argv;
      argv.push_back(const_cast<char *>(emulator.c_str()));
      for (const auto &a : args) {
        argv.push_back(const_cast<char *>(a.c_str()));
      }
      argv.push_back(nullptr);
      execv(emulator.c_str(), argv.data());
      _exit(127);
    }
    int wstatus = 0;
    while (waitpid(pid, &wstatus, 0) < 0) {
      require(errno == EINTR, "waitpid failed");
    }
    require(WIFEXITED(wstatus), "the emulator did not exit normally");
    ++emulator_runs;
    return WEXITSTATUS(wstatus);
  }

  std::string text(const std::string &file) {
    const Bytes b = file_bytes(file);
    return std::string(b.begin(), b.end());
  }

public:
  Campaign(std::string directory, std::string sim, bool bad_byte, bool bad_reload)
      : dir(std::move(directory)), emulator(std::move(sim)), negative_byte(bad_byte),
        negative_reload(bad_reload) {
    // The geometry and fixture come from a model in its own process, like
    // every phase; the parent holds no model instance.
    const std::string probe = path("probe.fixture");
    require(run_child([&] {
              Device d;
              Bytes out;
              for (size_t v : {d.shape.block_bytes, d.shape.blocks, d.shape.register_bytes, d.shape.max_block,
                               d.shape.steps[1], d.shape.steps[2], d.shape.steps[3]}) {
                for (unsigned i = 0; i < 8; ++i) {
                  out.push_back(static_cast<uint8_t>(uint64_t{v} >> (8 * i)));
                }
              }
              out.insert(out.end(), d.shape.fixture.begin(), d.shape.fixture.end());
              write_file(probe, out);
            }) == 0,
            "the fixture probe failed");
    const Bytes raw = file_bytes(probe);
    auto field = [&](unsigned index) {
      uint64_t v = 0;
      for (unsigned i = 0; i < 8; ++i) {
        v |= uint64_t{raw.at(8 * index + i)} << (8 * i);
      }
      return static_cast<size_t>(v);
    };
    shape.block_bytes = field(0);
    shape.blocks = field(1);
    shape.register_bytes = field(2);
    shape.max_block = field(3);
    shape.steps[1] = field(4);
    shape.steps[2] = field(5);
    shape.steps[3] = field(6);
    shape.fixture.assign(raw.begin() + 56, raw.end());
    require(shape.fixture.size() == shape.medium_bytes(), "the probe returned a short fixture");
    zero_mask.assign(shape.block_bytes, 0);
    full_mask.assign(shape.block_bytes, 0xff);
    for (size_t i = 0; i < shape.block_bytes; ++i) {
      split_mask.push_back(i % 2 ? 0x5a : 0xa5);
    }
  }

  void sha256_known_answers() {
    // FIPS 180-4's own examples (NIST CSRC "SHA256.pdf" and the one-million
    // repetition case).
    auto of = [](const std::string &s) {
      return blkdev::sha256_hex(reinterpret_cast<const uint8_t *>(s.data()), s.size());
    };
    require(of("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "SHA-256 of empty");
    require(of("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "SHA-256 of abc");
    require(of("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq") ==
              "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
            "SHA-256 of the two-block message");
    require(of(std::string(1000000, 'a')) == "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0",
            "SHA-256 of one million a");
  }

  void run() {
    sha256_known_answers();
    const size_t n = shape.blocks;
    const size_t last = n - 1;
    const std::string image = path("medium.img");
    const std::string create_receipt = path("create.receipt");

    // Creation from the fixture, exclusive and complete.
    require(run_child([&] {
              Device d;
              d.bind(image, Mode::create, create_receipt);
              d.image->close();
            }) == 0,
            "creating the image failed");
    Bytes medium = shape.fixture;
    compare(file_bytes(image), image_of(medium), "created image");
    {
      const auto records = lines(create_receipt);
      require(records.size() == 2 && contains(records[0], "\"event\":\"open\"") &&
                contains(records[0], "\"mode\":\"create\"") &&
                contains(records[0], "\"sha256\":\"" + hex(image_of(medium)) + "\"") &&
                contains(records[1], "\"event\":\"close\"") &&
                contains(records[1], "\"sha256\":\"" + hex(image_of(medium)) + "\""),
              "the creation receipt must name the created image");
    }
    {
      const Bytes before = file_bytes(image);
      require(run_child([&] {
                Device d;
                d.bind(image, Mode::create);
              }) == 3,
              "creating over an existing image must be refused");
      compare(file_bytes(image), before, "image after a refused creation");
      ++refusals;
    }
    reopen(image, medium);

    // P-flush across a process: WRITE the last block, then FLUSH with an
    // out-of-range BLOCK, and vanish. The receipt names both events.
    const Bytes p = payload(1);
    const std::string write_receipt = path("write.receipt");
    require(run_child([&] {
              Device d;
              d.bind(image, Mode::open, write_receipt);
              d.stage(last, p);
              d.command(2, 2, 0);
              d.store(40, n);
              d.command(3, 2, 0);
              vanish();
            }) == 0,
            "the write/flush phase failed");
    ++process_exits;
    put_block(medium, last, p);
    compare(file_bytes(image), image_of(medium), "image after WRITE and FLUSH");
    {
      const auto records = lines(write_receipt);
      require(records.size() == 3 && contains(records[1], "\"kind\":\"write\"") &&
                contains(records[1], "\"offset\":" + std::to_string(last * shape.block_bytes)) &&
                contains(records[1], "\"durable\":true") && contains(records[2], "\"kind\":\"flush\"") &&
                contains(records[2], "\"durable\":true"),
              "the write receipt must record the durable WRITE and FLUSH");
    }
    const std::string read_receipt = path("read.receipt");
    reopen(image, medium, read_receipt);
    {
      const auto records = lines(read_receipt);
      require(records.size() == 2 + n && contains(records.back(), "\"event\":\"close\"") &&
                contains(records.back(), "\"sha256\":\"" + hex(image_of(medium)) + "\""),
              "the reopen receipt must record each READ and the unchanged image");
    }

    // C-durable: completion is durable before STATUS is loaded or ACK written.
    const Bytes q = payload(2);
    require(run_child([&] {
              Device d;
              d.bind(image, Mode::open);
              d.stage(0, q);
              d.store(48, 2);
              d.steps(d.shape.steps[2]);
              vanish();
            }) == 0,
            "the unobserved-completion phase failed");
    ++process_exits;
    put_block(medium, 0, q);
    compare(file_bytes(image), image_of(medium), "image after an unobserved completion");
    reopen(image, medium);

    // Incomplete work does not survive a process: staging alone, then a WRITE
    // at every nonfinal progress boundary. Nothing reaches the image.
    const Bytes r = payload(3);
    require(run_child([&] {
              Device d;
              d.bind(image, Mode::open);
              d.stage(last, r);
              vanish();
            }) == 0,
            "the staging-only phase failed");
    ++process_exits;
    compare(file_bytes(image), image_of(medium), "image after staging alone");
    for (size_t done = 0; done < shape.steps[2]; ++done) {
      require(run_child([&] {
                Device d;
                d.bind(image, Mode::open);
                d.stage(last, r);
                d.store(48, 2);
                d.steps(done);
                require(d.status() == 1, "the write must still be pending");
                vanish();
              }) == 0,
              "the pending-write phase failed");
      ++process_exits;
      compare(file_bytes(image), image_of(medium), "image after a pending write at boundary " + std::to_string(done));
    }
    reopen(image, medium);

    // Tears under the explicit reset input, persisted and reopened, for every
    // block and each of the zero, full and non-prefix masks; one case with an
    // earlier media fault while the write is pending.
    for (size_t block = 0; block < n; ++block) {
      for (const Bytes *mask : {&zero_mask, &full_mask, &split_mask}) {
        Bytes fresh = block_of(medium, block);
        for (auto &b : fresh) {
          b = static_cast<uint8_t>(b ^ 0xff);
        }
        const Bytes tear = *mask;
        require(run_child([&] {
                  Device d;
                  d.bind(image, Mode::open);
                  d.stage(block, fresh);
                  d.store(48, 2);
                  d.steps(d.shape.steps[2] - 1);
                  d.reset_with(tear);
                  d.require_clean();
                  vanish();
                }) == 0,
                "the reset-tear phase failed");
        ++process_exits;
        mix(medium, block, fresh, tear);
        compare(file_bytes(image), image_of(medium), "image after a reset tear of block " + std::to_string(block));
        reopen(image, medium);
        ++tears;
      }
    }
    {
      const Bytes fresh = payload(4);
      Bytes fault(shape.block_bytes);
      for (size_t i = 0; i < fault.size(); ++i) {
        fault[i] = static_cast<uint8_t>(medium[i] ^ 0x3c);
      }
      require(run_child([&] {
                Device d;
                d.bind(image, Mode::open);
                d.stage(0, fresh);
                d.store(48, 2);
                d.corrupt(0, fault);
                d.steps(d.shape.steps[2] - 1);
                d.reset_with(split_mask);
                vanish();
              }) == 0,
              "the fault-then-tear phase failed");
      ++process_exits;
      put_block(medium, 0, fault);
      mix(medium, 0, fresh, split_mask);
      compare(file_bytes(image), image_of(medium), "image after a media fault and a reset tear");
      reopen(image, medium);
      ++tears;
    }
    // A WRITE error's tear, and a media fault alone.
    {
      const Bytes fresh = payload(5);
      require(run_child([&] {
                Device d;
                d.bind(image, Mode::open);
                d.stage(last, fresh);
                d.store(48, 2);
                d.steps(d.shape.steps[2] - 1);
                d.step(true, split_mask);
                require(d.status() == 3 && d.result() == 4, "an injected write error must be ERROR/IO");
                vanish();
              }) == 0,
              "the write-error phase failed");
      ++process_exits;
      mix(medium, last, fresh, split_mask);
      compare(file_bytes(image), image_of(medium), "image after a write error's tear");
      reopen(image, medium);
      ++tears;
      const Bytes fault = payload(6);
      require(run_child([&] {
                Device d;
                d.bind(image, Mode::open);
                d.corrupt(last, fault);
                vanish();
              }) == 0,
              "the media-fault phase failed");
      ++process_exits;
      put_block(medium, last, fault);
      compare(file_bytes(image), image_of(medium), "image after a media fault");
      reopen(image, medium);
    }

    // A host write the image cannot hold completes with IO, and every later
    // command does too; the image keeps the last durable bytes. RLIMIT_FSIZE
    // makes the block-1 range unwritable while block 0 stays writable.
    {
      const Bytes s = payload(7);
      const Bytes t = payload(8);
      const size_t limit = blkdev::header_bytes + shape.block_bytes;
      require(run_child([&] {
                std::signal(SIGXFSZ, SIG_IGN);
                Device d;
                d.bind(image, Mode::open);
                struct rlimit cap {limit, limit};
                require(setrlimit(RLIMIT_FSIZE, &cap) == 0, "setrlimit failed");
                d.stage(0, s);
                d.command(2, 2, 0);
                d.stage(1, t);
                d.command(2, 3, 4);
                d.command(1, 3, 4);
                d.command(3, 3, 4);
                require(!d.image->healthy(), "the adapter must record its failure");
                vanish();
              }) == 0,
              "the host-failure phase failed");
      ++process_exits;
      put_block(medium, 0, s);
      compare(file_bytes(image), image_of(medium), "image after a host write failure");
      reopen(image, medium);
    }

    // Startup refusals: the file and the register are unchanged.
    const Bytes body = medium;
    auto crafted = [&](const std::string &name, uint64_t b, uint64_t count, const Bytes &payload_bytes,
                       size_t magic_flip, uint8_t reserved) {
      Bytes out = blkdev::image_header({b, count});
      if (magic_flip < 8) {
        out[magic_flip] ^= 0x20;
      }
      out[24] = reserved;
      out.insert(out.end(), payload_bytes.begin(), payload_bytes.end());
      const std::string file = path(name);
      write_file(file, out);
      return file;
    };
    expect_refusal(crafted("half-blocks.img", shape.block_bytes / 2, n * 2, body, 8, 0), "half-length blocks, same total");
    Bytes longer = body;
    longer.resize(body.size() + shape.block_bytes, 0);
    expect_refusal(crafted("extra-block.img", shape.block_bytes, n + 1, longer, 8, 0), "one block too many");
    expect_refusal(crafted("short.img", shape.block_bytes, n, Bytes(body.begin(), body.end() - 1), 8, 0),
                   "a medium one byte short");
    Bytes plus = body;
    plus.push_back(0);
    expect_refusal(crafted("long.img", shape.block_bytes, n, plus, 8, 0), "a medium one byte long");
    expect_refusal(crafted("magic.img", shape.block_bytes, n, body, 0, 0), "a wrong magic");
    expect_refusal(crafted("reserved.img", shape.block_bytes, n, body, 8, 1), "nonzero reserved bytes");
    {
      const std::string stub = path("stub.img");
      write_file(stub, Bytes(10, 0));
      expect_refusal(stub, "fewer bytes than a header");
    }
    expect_refusal(path("missing.img"), "no file");
    {
      const std::string sub = path("directory.img");
      require(mkdir(sub.c_str(), 0755) == 0, "mkdir failed");
      expect_refusal(sub, "a directory");
    }
    {
      // One run owns an image.
      const int held = ::open(image.c_str(), O_RDONLY | O_CLOEXEC);
      require(held >= 0 && flock(held, LOCK_EX | LOCK_NB) == 0, "cannot hold the image lock");
      expect_refusal(image, "a lock held by another run");
      ::close(held);
    }
    reopen(image, medium);

    if (!emulator.empty()) {
      emulator_cases();
    }
    std::printf("block image: B=%zu N=%zu reopens=%zu process_exits=%zu tears=%zu refusals=%zu "
                "emulator_runs=%zu PASS\n",
                shape.block_bytes, shape.blocks, reopens, process_exits, tears, refusals, emulator_runs);
  }

  // The emulator's own option surface: refusal, creation and opening happen
  // before any ELF is needed, so the run ends at "No elf file provided." after
  // a successful bind and before it after a refusal.
  void emulator_cases() {
    const std::string log = path("emulator.log");
    const std::string wrong = dir + "/half-blocks.img";
    const Bytes before = file_bytes(wrong);
    require(emulate({"--blkdev-image", wrong}, log) != 0, "the emulator must refuse a wrong-geometry image");
    require(contains(text(log), "Block device image refused:") && contains(text(log), "records geometry") &&
              !contains(text(log), "No elf file provided."),
            "the emulator's refusal must name the geometry and precede ELF handling");
    compare(file_bytes(wrong), before, "image the emulator refused");
    ++refusals;

    const std::string made_image = path("emulator.img");
    const std::string receipt = path("emulator.receipt");
    require(emulate({"--blkdev-image-create", made_image, "--blkdev-receipt", receipt}, log) != 0,
            "an emulator run without an ELF still fails");
    require(contains(text(log), "Block device image created: " + made_image) &&
              contains(text(log), "No elf file provided."),
            "the emulator must create the image before ELF handling");
    compare(file_bytes(made_image), image_of(shape.fixture), "image the emulator created");
    require(contains(lines(receipt).at(0), "\"sha256\":\"" + hex(image_of(shape.fixture)) + "\""),
            "the emulator's receipt must name the created image");

    require(emulate({"--blkdev-image", made_image}, log) != 0, "an emulator run without an ELF still fails");
    require(contains(text(log), "Block device image opened: " + made_image), "the emulator must open the image");

    // GDB can reinitialize the model and does not use the checked image-close
    // path. Refuse the combination before opening either image or receipt.
    const std::string gdb_receipt = path("gdb.receipt");
    require(emulate({"--gdb-server-port", "1234", "--blkdev-image", made_image,
                     "--blkdev-receipt", gdb_receipt}, log) != 0 &&
              contains(text(log), "Block device image refused:") &&
              contains(text(log), "unavailable in GDB server mode") &&
              !contains(text(log), "Block device image opened:") &&
              !contains(text(log), "No elf file provided."),
            "a bound image must refuse GDB mode before binding or ELF handling");
    compare(file_bytes(made_image), image_of(shape.fixture), "image after the refused GDB open");
    require(!exists(gdb_receipt), "the refused GDB open must create no receipt");
    ++refusals;

    const std::string gdb_image = path("gdb.img");
    require(emulate({"--gdb-server-port", "1234", "--blkdev-image-create", gdb_image,
                     "--blkdev-receipt", gdb_receipt}, log) != 0 &&
              contains(text(log), "Block device image refused:") &&
              contains(text(log), "unavailable in GDB server mode"),
            "image creation must refuse GDB mode");
    require(!exists(gdb_image) && !exists(gdb_receipt),
            "the refused GDB creation must create neither image nor receipt");
    ++refusals;

    require(emulate({"--blkdev-image-create", made_image}, log) != 0 &&
              contains(text(log), "Block device image refused:") && contains(text(log), "already exists"),
            "the emulator must refuse to create over an image");
    compare(file_bytes(made_image), image_of(shape.fixture), "image after the emulator's refused creation");
    ++refusals;
    require(emulate({"--blkdev-receipt", path("orphan.receipt")}, log) != 0 &&
              contains(text(log), "--blkdev-receipt needs"),
            "a receipt without an image must be refused");
  }

  void clean() {
    for (auto it = made.rbegin(); it != made.rend(); ++it) {
      if (::unlink(it->c_str()) != 0) {
        ::rmdir(it->c_str());
      }
    }
    ::rmdir(dir.c_str());
  }
};

} // namespace

int main(int argc, char **argv) {
  bool bad_byte = false, bad_reload = false;
  std::string emulator;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--negative-byte") {
      bad_byte = true;
    } else if (arg == "--negative-reload-fixture") {
      bad_reload = true;
    } else if (arg == "--emulator" && i + 1 < argc) {
      emulator = argv[++i];
    } else {
      std::fputs("usage: block_image [--negative-byte | --negative-reload-fixture] [--emulator PATH]\n", stderr);
      return 2;
    }
  }
  sail_config_set_string(get_default_config());
  char scratch[] = "block_image.XXXXXX";
  if (mkdtemp(scratch) == nullptr) {
    std::perror("block image: mkdtemp");
    return 1;
  }
  std::unique_ptr<Campaign> campaign;
  try {
    campaign = std::make_unique<Campaign>(scratch, emulator, bad_byte, bad_reload);
    campaign->run();
    campaign->clean();
  } catch (const std::exception &error) {
    // An inverted expectation fails by design and keeps nothing; any other
    // failure keeps its images and receipts for inspection.
    const bool inverted = bad_byte || bad_reload;
    if (inverted && campaign) {
      campaign->clean();
    }
    std::fprintf(stderr, "block image: FAIL %s%s%s\n", error.what(), inverted ? "" : " (scratch kept at ",
                 inverted ? "" : (std::string(scratch) + ")").c_str());
    return 1;
  }
  return 0;
}
