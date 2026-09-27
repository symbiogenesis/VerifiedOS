// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_COPY_ATOMIC_H
#define VOS_COPY_ATOMIC_H
#include <stdint.h>

/* These are atomic interface types, never directly read by the service. The
 * target definitions are accessed only by the matching fenced ISA primitives.
 * The header's index width is the declaration's physical one-byte wire width. */
#ifdef VOS_COPY_TARGET
typedef struct { uint8_t value; } vos_copy_atomic_index;
typedef struct { uint32_t value; } vos_copy_atomic_word;
uint32_t vos_copy_index_load(const vos_copy_atomic_index *cell);
void vos_copy_index_store(vos_copy_atomic_index *cell, uint32_t value);
uint32_t vos_copy_word_load(const vos_copy_atomic_word *cell);
void vos_copy_word_store(vos_copy_atomic_word *cell, uint32_t value);
uint32_t vos_copy_word_exchange(vos_copy_atomic_word *cell, uint32_t value);
#else
#include <stdatomic.h>
typedef _Atomic uint8_t vos_copy_atomic_index;
typedef _Atomic uint32_t vos_copy_atomic_word;
#define vos_copy_index_load(p) atomic_load_explicit((p), memory_order_seq_cst)
#define vos_copy_index_store(p, v) atomic_store_explicit((p), (v), memory_order_seq_cst)
#define vos_copy_word_load(p) atomic_load_explicit((p), memory_order_seq_cst)
#define vos_copy_word_store(p, v) atomic_store_explicit((p), (v), memory_order_seq_cst)
#define vos_copy_word_exchange(p, v) atomic_exchange_explicit((p), (v), memory_order_seq_cst)
#endif
#endif
