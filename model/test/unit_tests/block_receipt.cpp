// SPDX-License-Identifier: BSD-2-Clause
// A requested image receipt must fail visibly when its sink stops accepting
// bytes. These are adapter checks; block_image covers the generated Sail join.
#include "blkdev_image.h"
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

namespace {
void require(bool condition, const char *message) {
  if (!condition) {
    throw std::runtime_error(message);
  }
}

void cap_file_size(rlim_t size) {
  const struct rlimit cap {size, size};
  require(setrlimit(RLIMIT_FSIZE, &cap) == 0, "cannot limit receipt size");
}

void child_case(const std::string &image_path, const std::string &receipt_path, unsigned which) {
  std::signal(SIGXFSZ, SIG_IGN);
  if (which == 0) {
    cap_file_size(0);
    bool refused = false;
    try {
      blkdev::image image(image_path, blkdev::image::mode::open, {64, 2}, {}, receipt_path);
    } catch (const blkdev::refusal &) {
      refused = true;
    }
    require(refused, "an unwritable opening receipt must refuse startup");
    return;
  }

  blkdev::image image(image_path, blkdev::image::mode::open, {64, 2}, {}, receipt_path);
  struct stat st {};
  require(stat(receipt_path.c_str(), &st) == 0 && st.st_size > 0, "missing opening receipt");
  cap_file_size(static_cast<rlim_t>(st.st_size));
  if (which == 1) {
    // The image remains writable below this limit. Only the receipt append
    // fails, after the selected block was durably written.
    require(st.st_size >= static_cast<off_t>(blkdev::header_bytes + 128), "receipt too short for control");
    uint64_t medium[128] = {};
    for (unsigned i = 0; i < 64; ++i) {
      medium[i] = 0x5a;
    }
    require(!image.persist(2, 0, 64, medium, 128), "a lost persistence receipt must return IO");
    require(!image.healthy(), "receipt failure must be sticky");
    require(!image.persist(1, 0, 0, medium, 128), "later READ must return IO");
    require(!image.persist(3, 0, 0, medium, 128), "later FLUSH must return IO");
  }
  require(!image.close(), "a lost final receipt must fail close");
  require(!image.close(), "repeated close must retain the evidence failure");
}
} // namespace

int main() {
  char scratch[] = "block_receipt.XXXXXX";
  if (mkdtemp(scratch) == nullptr) {
    std::perror("block receipt: mkdtemp");
    return 1;
  }
  const std::string dir = scratch;
  const std::string image_path = dir + "/medium.img";
  try {
    {
      blkdev::image image(image_path, blkdev::image::mode::create, {64, 2}, std::vector<uint8_t>(128, 0));
      require(image.close(), "creation without a receipt must succeed");
    }
    for (unsigned which = 0; which < 3; ++which) {
      const std::string receipt_path = dir + "/receipt-" + std::to_string(which);
      const pid_t pid = fork();
      require(pid >= 0, "fork failed");
      if (pid == 0) {
        try {
          child_case(image_path, receipt_path, which);
          _exit(0);
        } catch (const std::exception &error) {
          std::fprintf(stderr, "block receipt child: FAIL %s\n", error.what());
          _exit(1);
        }
      }
      int status = 0;
      while (waitpid(pid, &status, 0) < 0) {
        require(errno == EINTR, "waitpid failed");
      }
      require(WIFEXITED(status) && WEXITSTATUS(status) == 0, "receipt failure case failed");
      blkdev::image reopened(image_path, blkdev::image::mode::open, {64, 2}, {});
      const auto &bytes = reopened.opened_bytes();
      for (unsigned i = 0; i < bytes.size(); ++i) {
        require(bytes[i] == (which >= 1 && i < 64 ? 0x5a : 0), "receipt failure changed unexpected image bytes");
      }
      require(reopened.close(), "reopen without a receipt must succeed");
      require(unlink(receipt_path.c_str()) == 0, "cannot remove test receipt");
    }
    require(unlink(image_path.c_str()) == 0 && rmdir(dir.c_str()) == 0, "cannot remove test outputs");
    std::puts("block receipt: startup, persistence and close failures PASS");
    return 0;
  } catch (const std::exception &error) {
    std::fprintf(stderr, "block receipt: FAIL %s (scratch kept at %s)\n", error.what(), scratch);
    return 1;
  }
}
