// SPDX-License-Identifier: Apache-2.0
// Authored I/O wrapper around the unchanged upstream verified LLVM checker.
// This wrapper and native compilation are explicitly outside its Isabelle proof.
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <vector>

extern "C" {
#include "lrat_isa_export.h"
}

static FILE* proof_file = nullptr;

extern "C" size_t fread_from_proof(void* pointer, size_t count) {
  return proof_file == nullptr ? 0 : fread(pointer, 1, count, proof_file);
}

int main(int argc, char** argv) {
  if (argc != 3) return 2;
  std::ifstream cnf(argv[1], std::ios::binary | std::ios::ate);
  if (!cnf) return 2;
  const auto length = cnf.tellg();
  if (length <= 0 || length > 64 * 1024 * 1024) return 2;
  cnf.seekg(0);
  std::vector<uint8_t> bytes(static_cast<size_t>(length));
  if (!cnf.read(reinterpret_cast<char*>(bytes.data()), length)) return 2;
  proof_file = fopen(argv[2], "rb");
  if (proof_file == nullptr) return 2;
  const bool accepted = lrat_checker(bytes.data(), bytes.size());
  fclose(proof_file);
  proof_file = nullptr;
  if (!accepted) {
    std::cout << "c ERROR\n";
    return 1;
  }
  std::cout << "s VERIFIED UNSAT\n";
  return 0;
}
