// SPDX-License-Identifier: Apache-2.0
#include <iostream>
#include <limits>

#include "tflm_checked_plan.h"

int main() {
  using verifiedos::BufferPlan;
  using verifiedos::CheckedOfflinePlanner;
  constexpr BufferPlan rows[] = {{16, 0, 1, 0}, {16, 2, 3, 0}, {16, 0, 3, 16}};
  CheckedOfflinePlanner planner(rows, 3, 32, 16);
  tflite::MicroMemoryPlanner& api = planner;
  if (api.Init(nullptr, 0) != kTfLiteOk || api.GetBufferCount() != 0 ||
      api.preserves_all_tensors()) return 1;
  if (api.AddBuffer(16, 0, 1) != kTfLiteOk ||
      api.AddBuffer(16, 2, 3, 0) != kTfLiteOk ||
      api.AddBuffer(16, 0, 3, -1) != kTfLiteOk) return 2;
  int offset = -1;
  if (!planner.ready() || api.GetBufferCount() != 3 ||
      api.GetMaximumMemorySize() != 32 ||
      api.GetOffsetForBuffer(1, &offset) != kTfLiteOk || offset != 0 ||
      api.GetOffsetForBuffer(3, &offset) != kTfLiteError ||
      api.GetOffsetForBuffer(0, nullptr) != kTfLiteError) return 3;
  CheckedOfflinePlanner preserve(rows, 3, 32, 16, true);
  if (preserve.valid_plan()) return 4;
  CheckedOfflinePlanner mismatch(rows, 3, 32, 16);
  if (mismatch.Init(nullptr, 0) != kTfLiteOk ||
      mismatch.AddBuffer(16, 0, 1, 16) != kTfLiteError || mismatch.ready()) return 5;
  constexpr BufferPlan collision[] = {{16, 0, 1, 0}, {16, 1, 2, 0}};
  CheckedOfflinePlanner inclusive(collision, 2, 16, 16);
  if (inclusive.valid_plan()) return 6;
  constexpr BufferPlan overflow[] = {{1, 0, 0, std::numeric_limits<int>::max()}};
  CheckedOfflinePlanner large(overflow, 1, std::numeric_limits<int>::max(), 1);
  if (large.valid_plan()) return 7;
  CheckedOfflinePlanner scratch(rows, 3, 32, 16);
  if (scratch.Init(nullptr, 1) != kTfLiteError) return 8;
  constexpr BufferPlan zero[] = {{0, 0, 0, 0}};
  CheckedOfflinePlanner empty(zero, 1, 0, 16, true);
  if (empty.Init(nullptr, 0) != kTfLiteOk || empty.AddBuffer(0, 0, 0) != kTfLiteOk ||
      !empty.ready() || !empty.preserves_all_tensors()) return 9;
  std::cout << "PASS: actual MicroMemoryPlanner interface; 32-byte reusable arena, "
               "48-byte separate baseline; zero initialization scratch; "
               "identity, fixed offsets, inclusive endpoints, preservation, overflow checked\n";
  return 0;
}
