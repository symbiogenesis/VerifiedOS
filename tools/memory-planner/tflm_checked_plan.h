// SPDX-License-Identifier: Apache-2.0
#ifndef VERIFIEDOS_TFLM_CHECKED_PLAN_H_
#define VERIFIEDOS_TFLM_CHECKED_PLAN_H_

#include <cstddef>
#include <limits>

#include "tensorflow/lite/micro/memory_planner/micro_memory_planner.h"

namespace verifiedos {

// These are immutable host-planned rows in AddBuffer call order. Their backing
// must outlive the planner. The target owns no solver, heap, or scratch storage.
struct BufferPlan {
  int size;
  int first;
  int last;  // Inclusive, exactly as MicroMemoryPlanner receives it.
  int offset;
};

class CheckedOfflinePlanner final : public tflite::MicroMemoryPlanner {
 public:
  CheckedOfflinePlanner(const BufferPlan* rows, int count, int arena_size,
                        int alignment, bool preserve_all = false)
      : rows_(rows), expected_(count), arena_size_(arena_size),
        alignment_(alignment), preserve_all_(preserve_all), valid_(Validate()) {}

  TfLiteStatus Init(unsigned char* scratch_buffer, int scratch_buffer_size) override {
    if (scratch_buffer_size < 0 || (scratch_buffer_size > 0 && scratch_buffer == nullptr)) {
      valid_ = false;
      return kTfLiteError;
    }
    added_ = 0;
    initialized_ = true;
    return valid_ ? kTfLiteOk : kTfLiteError;
  }

  TfLiteStatus AddBuffer(int size, int first, int last) override {
    return AddBuffer(size, first, last, -1);
  }

  TfLiteStatus AddBuffer(int size, int first, int last, int offline_offset) override {
    if (!valid_ || !initialized_ || added_ >= expected_ || offline_offset < -1) {
      valid_ = false;
      return kTfLiteError;
    }
    const auto& row = rows_[added_];
    if (size != row.size || first != row.first || last != row.last ||
        (offline_offset >= 0 && offline_offset != row.offset)) {
      valid_ = false;
      return kTfLiteError;
    }
    ++added_;
    return kTfLiteOk;
  }

  size_t GetMaximumMemorySize() override {
    return ready() ? static_cast<size_t>(arena_size_) : 0;
  }

  int GetBufferCount() override { return added_; }

  TfLiteStatus GetOffsetForBuffer(int index, int* offset) override {
    if (!ready() || offset == nullptr || index < 0 || index >= added_) {
      return kTfLiteError;
    }
    *offset = rows_[index].offset;
    return kTfLiteOk;
  }

  bool preserves_all_tensors() const override { return preserve_all_; }

  // Richer admission status stays separate from the legacy size/offset results.
  bool ready() const { return valid_ && initialized_ && added_ == expected_; }
  bool valid_plan() const { return valid_; }
  static constexpr size_t ScratchBytes() { return 0; }

 private:
  bool Validate() const {
    if (expected_ < 0 || arena_size_ < 0 || alignment_ <= 0 ||
        (expected_ > 0 && rows_ == nullptr)) {
      return false;
    }
    int height = 0;
    for (int i = 0; i < expected_; ++i) {
      const auto& row = rows_[i];
      if (row.size < 0 || row.first < 0 || row.last < row.first || row.offset < 0 ||
          row.offset % alignment_ != 0 || row.offset > arena_size_ ||
          row.size > arena_size_ - row.offset) {
        return false;
      }
      // Subtraction above proves both additions below stay inside signed int.
      const int end = row.offset + row.size;
      if (end > height) height = end;
      for (int j = 0; j < i; ++j) {
        const auto& other = rows_[j];
        const bool coexists = preserve_all_ ||
            (row.first <= other.last && other.first <= row.last);
        const bool overlaps = row.size > 0 && other.size > 0 &&
            row.offset < other.offset + other.size && other.offset < end;
        if (coexists && overlaps) return false;
      }
    }
    return height == arena_size_;
  }

  const BufferPlan* rows_;
  int expected_;
  int arena_size_;
  int alignment_;
  bool preserve_all_;
  bool valid_;
  bool initialized_ = false;
  int added_ = 0;
};

}  // namespace verifiedos
#endif  // VERIFIEDOS_TFLM_CHECKED_PLAN_H_
