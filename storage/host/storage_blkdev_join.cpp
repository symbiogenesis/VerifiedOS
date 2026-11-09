// SPDX-License-Identifier: Apache-2.0
// M5.3d persistent-image join: connects storage_publish.c and crypto_core.c
// directly to the emulator's blkdev::image host persistence adapter
// (model/c_emulator/blkdev_image.cpp), exercising create, persist, receipt
// SHA-256 chaining, reopen across all five crash cuts, non-prefix reset bit
// tears, media corruption refusals, and two-instance (system-integrity and
// user-data) resident-read verification.

#include "blkdev_image.h"

extern "C" {
#include "vos_storage_publish.h"
}

#include <cstdio>
#include <cstring>
#include <fstream>
#include <functional>
#include <string>
#include <vector>

namespace {

bool load_from_blkdev(
    const std::string &path,
    const std::string &receipt,
    struct vos_storage_medium *medium,
    struct vos_storage_store *store,
    struct vos_crypto_core *crypto,
    uint32_t crypto_slot,
    uint64_t expected_domain_id)
{
    const blkdev::geometry geom{
        VOS_STORAGE_BLKDEV_BLOCK_BYTES,
        VOS_STORAGE_BLKDEV_BLOCK_COUNT
    };
    const std::vector<uint8_t> empty_fixture;
    blkdev::image img(path, blkdev::image::mode::open, geom, empty_fixture, receipt);
    if (!img.persist_bytes(
            static_cast<uint64_t>(blkdev::event::read),
            0, 0, nullptr, 0) ||
        !img.close()) {
        return false;
    }
    if (!vos_storage_decode_blkdev_medium(img.opened_bytes().data(), medium)) {
        return false;
    }
    return vos_storage_reopen(
               medium, store, crypto, crypto_slot, expected_domain_id) != 0;
}

bool persist_medium_to_blkdev(
    blkdev::image &img,
    const struct vos_storage_medium *medium,
    blkdev::event ev = blkdev::event::write,
    const std::function<bool()> &after_write = {})
{
    uint8_t raw_medium[VOS_STORAGE_BLKDEV_MEDIUM_BYTES];
    if (!vos_storage_encode_blkdev_medium(medium, raw_medium)) {
        return false;
    }
    if (std::memcmp(raw_medium, img.current_bytes().data(), sizeof(raw_medium)) == 0)
        return img.persist_bytes(static_cast<uint64_t>(blkdev::event::flush),
                                  0, 0, nullptr, 0);
    auto write_changed = [&](uint32_t block, const uint8_t *bytes) {
        const size_t offset = block * VOS_STORAGE_BLKDEV_BLOCK_BYTES;
        return std::memcmp(bytes + offset, img.current_bytes().data() + offset,
                           VOS_STORAGE_BLKDEV_BLOCK_BYTES) == 0 ||
               (img.persist_bytes(static_cast<uint64_t>(ev), offset,
                                   VOS_STORAGE_BLKDEV_BLOCK_BYTES, bytes,
                                   block == 0 ? static_cast<size_t>(VOS_STORAGE_BLKDEV_BLOCK_BYTES) : sizeof(raw_medium)) &&
                (!after_write || after_write()));
    };
    uint8_t header[VOS_STORAGE_BLKDEV_BLOCK_BYTES];
    std::memcpy(header, img.current_bytes().data(), sizeof(header));
    std::memcpy(header + 64, raw_medium + 64, 64);
    if (!write_changed(0, header)) return false;
    // [Publication ordering](../../docs/implementation/storage-recovery-policy.md#storage-critique-repair-acceptance):
    // nonce, redo, primary checkpoint, arena application, fallback checkpoint.
    // A changed block gets its own durability answer; unchanged blocks do no IO.
    for (uint32_t block = 17; block <= 31; ++block)
        if (!write_changed(block, raw_medium)) return false;
    std::memcpy(header, raw_medium, sizeof(header));
    std::memset(header + 44, 0, 4);
    if (!write_changed(0, header)) return false;
    static constexpr uint32_t order[] = {
        32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47,
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
        48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63
    };
    for (const uint32_t block : order) {
        if (!write_changed(block, raw_medium)) return false;
    }
    if (!write_changed(0, raw_medium)) return false;
    return img.persist_bytes(
               static_cast<uint64_t>(blkdev::event::flush),
               0, 0, nullptr, 0);
}

struct persistence_bridge {
    blkdev::image *image;
    std::function<bool()> after_write;
    const struct vos_crypto_core *crypto = nullptr;
    uint64_t fail_after_epoch = UINT64_MAX;
};

int persist_storage(void *opaque, const struct vos_storage_medium *medium)
{
    auto *bridge = static_cast<persistence_bridge *>(opaque);
    if (bridge->crypto != nullptr && bridge->crypto->rot_epoch_counter > bridge->fail_after_epoch)
        return 0;
    return persist_medium_to_blkdev(*bridge->image, medium, blkdev::event::write,
                                     bridge->after_write) ? 1 : 0;
}

std::string read_file_text(const std::string &path)
{
    std::ifstream in(path, std::ios::binary);
    return std::string(
        (std::istreambuf_iterator<char>(in)),
        std::istreambuf_iterator<char>());
}

std::string extract_event_sha256(const std::string &receipt_text, const std::string &event_kind)
{
    const std::string needle = "\"event\":\"" + event_kind + "\"";
    size_t pos = receipt_text.find(needle);
    if (pos == std::string::npos) {
        return {};
    }
    const std::string sha_key = "\"sha256\":\"";
    size_t sha_pos = receipt_text.find(sha_key, pos);
    if (sha_pos == std::string::npos) {
        return {};
    }
    sha_pos += sha_key.size();
    if (sha_pos + 64 > receipt_text.size()) {
        return {};
    }
    return receipt_text.substr(sha_pos, 64);
}

bool check_packed_adapter(const std::string &dir)
{
    const std::string path = dir + "/packed.blk";
    const blkdev::geometry geom{128, 2};
    const std::vector<uint8_t> fixture(256, 0x5a);
    std::vector<uint8_t> next = fixture;
    next[137] = 0xc3;
    {
        blkdev::image img(path, blkdev::image::mode::create, geom, fixture);
        if (!img.persist_bytes(static_cast<uint64_t>(blkdev::event::read),
                               128, 128, next.data(), next.size()) ||
            img.current_bytes() != fixture || !img.close()) return false;
    }
    {
        blkdev::image img(path, blkdev::image::mode::open, geom, {});
        if (img.opened_bytes() != fixture ||
            !img.persist_bytes(static_cast<uint64_t>(blkdev::event::write),
                               128, 128, next.data(), next.size()) ||
            img.current_bytes() != next || img.opened_bytes() != fixture ||
            !img.close()) return false;
    }
    {
        blkdev::image img(path, blkdev::image::mode::open, geom, {});
        if (img.opened_bytes() != next ||
            img.persist_bytes(static_cast<uint64_t>(blkdev::event::write),
                              255, 2, next.data(), next.size()) ||
            img.healthy() || !img.close()) return false;
    }
    return true;
}

bool check_publication_prefixes(const std::string &dir, bool fresh)
{
    const std::string path = dir + (fresh ? "/fresh-prefixes.blk" : "/prefixes.blk");
    const struct vos_node_geometry geometry = {4u, 16u, 128u};
    const struct vos_tree_limits limits = {0u, 4u, 64u};
    struct vos_crypto_core crypto;
    struct vos_storage_medium medium;
    struct vos_storage_store store;
    const uint8_t key[32] = {0x8c};
    vos_crypto_core_init(&crypto, 100u);
    if (!vos_crypto_core_unlock_domain(&crypto, 0u, 19u, 1u, key, sizeof(key)) ||
        !vos_storage_format(&medium, &store, &crypto, 0u, 19u, 1u,
                            &geometry, &limits, 1u, 100u)) return false;
    std::vector<uint8_t> fixture(VOS_STORAGE_BLKDEV_MEDIUM_BYTES);
    if (!vos_storage_encode_blkdev_medium(&medium, fixture.data())) return false;
    blkdev::image img(path, blkdev::image::mode::create, {128, 64}, fixture);
    uint64_t prior_value = 0;
    bool prior_found = false;
    size_t writes = 0, tears = 0;
    for (uint32_t round = 0; round < 16; ++round) {
        const uint64_t prior_generation = store.committed_generation;
        struct vos_storage_tx_spec tx = {};
        tx.op_kind = round % 4 == 3 ? VOS_STORAGE_OP_COMPACT : VOS_STORAGE_OP_INSERT;
        tx.key = 7;
        tx.value = 300 + round;
        tx.commit_mode = fresh ? VOS_STORAGE_COMMIT_FRESH : VOS_STORAGE_COMMIT_ROLLBACKABLE;
        tx.fresh_region_id = 1;
        tx.fresh_region_version = round + 1;
        const uint64_t next_value = tx.op_kind == VOS_STORAGE_OP_COMPACT ? prior_value : tx.value;
        const uint64_t next_generation = medium.nonce_record.reserved_generation + 1;
        auto previous = img.current_bytes();
        auto recover = [&](const std::vector<uint8_t> &bytes) {
            struct vos_storage_medium recovered;
            struct vos_storage_store reader;
            if (!vos_storage_decode_blkdev_medium(bytes.data(), &recovered) ||
                !vos_storage_reopen(&recovered, &reader, &crypto, 0u, 19u)) return false;
            uint64_t value = 0;
            const int result = vos_storage_lookup(&reader, 19u, 7u, &value);
            if (reader.committed_generation == prior_generation)
                return prior_found ? result == VOS_TREE_FOUND && value == prior_value :
                                     result == VOS_TREE_MISSING;
            return reader.committed_generation == next_generation &&
                   result == VOS_TREE_FOUND && value == next_value;
        };
        auto observe = [&]() {
            ++writes;
            const auto current = img.current_bytes();
            const std::string on_disk = read_file_text(path);
            if (on_disk.size() != blkdev::header_bytes + current.size() ||
                std::memcmp(on_disk.data() + blkdev::header_bytes, current.data(), current.size()) != 0 ||
                !recover(current)) return false;
            for (uint32_t block = 32; block < 64; ++block) {
                const size_t offset = block * VOS_STORAGE_BLKDEV_BLOCK_BYTES;
                if (std::memcmp(current.data() + offset, previous.data() + offset, 128) == 0) continue;
                auto torn = current;
                for (size_t byte = 0; byte < 128; ++byte) {
                    const uint8_t mask = byte % 2 == 0 ? 0x55 : 0xaa;
                    torn[offset + byte] = static_cast<uint8_t>(
                        (previous[offset + byte] & ~mask) | (current[offset + byte] & mask));
                }
                ++tears;
                if (!recover(torn)) return false;
            }
            previous = current;
            return true;
        };
        persistence_bridge bridge{&img, observe};
        uint64_t ack = 0;
        if (!vos_storage_attach_persistence(&store, persist_storage, &bridge) ||
            !vos_storage_reserve(&store, 19u, &tx) ||
            !vos_storage_stage(&store, 19u) ||
            !vos_storage_publish(&store, 19u, VOS_STORAGE_CUT_NONE, &ack) || ack != next_generation) {
            std::fprintf(stderr, "prefix recovery failed fresh=%d round %u write %zu\n", fresh, round, writes);
            return false;
        }
        const size_t before_noop = writes;
        if (!persist_medium_to_blkdev(img, &medium, blkdev::event::write, observe) ||
            writes != before_noop) return false;
        prior_value = next_value;
        prior_found = true;
    }
    if (fresh) {
        persistence_bridge bridge{&img, {}, &crypto, crypto.rot_epoch_counter};
        struct vos_storage_tx_spec tx = {};
        tx.op_kind = VOS_STORAGE_OP_INSERT;
        tx.commit_mode = VOS_STORAGE_COMMIT_FRESH;
        tx.key = 7; tx.value = 999;
        tx.fresh_region_id = 1; tx.fresh_region_version = 17;
        uint64_t ack = 0;
        if (!vos_storage_attach_persistence(&store, persist_storage, &bridge) ||
            !vos_storage_reserve(&store, 19u, &tx) || !vos_storage_stage(&store, 19u) ||
            vos_storage_publish(&store, 19u, VOS_STORAGE_CUT_NONE, &ack) || ack != 0 || store.open)
            return false;
        struct vos_storage_medium recovered;
        struct vos_storage_store reader;
        uint64_t value = 0;
        if (!vos_storage_decode_blkdev_medium(img.current_bytes().data(), &recovered) ||
            !vos_storage_reopen(&recovered, &reader, &crypto, 0u, 19u) ||
            vos_storage_lookup(&reader, 19u, 7u, &value) != VOS_TREE_FOUND || value != 999)
            return false;
    }
    return writes > 0 && tears > 0 && img.close();
}

} // namespace

int main(int argc, char **argv)
{
    if (argc != 2) {
        std::fprintf(stderr, "usage: %s <scratch-dir>\n", argv[0]);
        return 1;
    }
    const std::string dir = argv[1];
    if (!check_packed_adapter(dir)) {
        std::fprintf(stderr, "storage_blkdev_join: packed adapter failed\n");
        return 1;
    }
    if (!check_publication_prefixes(dir, false) || !check_publication_prefixes(dir, true)) {
        std::fprintf(stderr, "storage_blkdev_join: publication prefixes failed\n");
        return 1;
    }
    const std::string sys_img_path = dir + "/system.blk";
    const std::string usr_img_path = dir + "/user.blk";

    static const struct vos_node_geometry geom = {4u, 16u, 128u};
    static const struct vos_tree_limits limits = {0u, 4u, 64u};
    static const uint8_t sys_key[32] = {
        0x10u, 0x11u, 0x12u, 0x13u, 0x14u, 0x15u, 0x16u, 0x17u,
        0x18u, 0x19u, 0x1au, 0x1bu, 0x1cu, 0x1du, 0x1eu, 0x1fu,
        0x20u, 0x21u, 0x22u, 0x23u, 0x24u, 0x25u, 0x26u, 0x27u,
        0x28u, 0x29u, 0x2au, 0x2bu, 0x2cu, 0x2du, 0x2eu, 0x2fu
    };
    static const uint8_t usr_key[32] = {
        0x90u, 0x91u, 0x92u, 0x93u, 0x94u, 0x95u, 0x96u, 0x97u,
        0x98u, 0x99u, 0x9au, 0x9bu, 0x9cu, 0x9du, 0x9eu, 0x9fu,
        0xa0u, 0xa1u, 0xa2u, 0xa3u, 0xa4u, 0xa5u, 0xa6u, 0xa7u,
        0xa8u, 0xa9u, 0xaau, 0xabu, 0xacu, 0xadu, 0xaeu, 0xafu
    };
    const uint64_t sys_dom = 0x1111u;
    const uint64_t usr_dom = 0x2222u;

    struct vos_crypto_core crypto;
    vos_crypto_core_init(&crypto, 32u);
    if (!vos_crypto_core_unlock_domain(
            &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, sys_dom, 1u, sys_key, sizeof(sys_key)) ||
        !vos_crypto_core_unlock_domain(
            &crypto, VOS_CRYPTO_DOMAIN_USER, usr_dom, 1u, usr_key, sizeof(usr_key))) {
        std::fprintf(stderr, "storage_blkdev_join: unlock failed\n");
        return 1;
    }

    struct vos_storage_medium sys_med;
    struct vos_storage_store sys_store;
    struct vos_storage_medium usr_med;
    struct vos_storage_store usr_store;
    if (!vos_storage_format(
            &sys_med, &sys_store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
            sys_dom, 1u, &geom, &limits, 1u, 64u) ||
        !vos_storage_format(
            &usr_med, &usr_store, &crypto, VOS_CRYPTO_DOMAIN_USER,
            usr_dom, 1u, &geom, &limits, 1u, 64u)) {
        std::fprintf(stderr, "storage_blkdev_join: format failed\n");
        return 1;
    }

    uint8_t sys_init_bytes[VOS_STORAGE_BLKDEV_MEDIUM_BYTES];
    uint8_t usr_init_bytes[VOS_STORAGE_BLKDEV_MEDIUM_BYTES];
    if (!vos_storage_encode_blkdev_medium(&sys_med, sys_init_bytes) ||
        !vos_storage_encode_blkdev_medium(&usr_med, usr_init_bytes)) {
        std::fprintf(stderr, "storage_blkdev_join: initial encode failed\n");
        return 1;
    }

    const blkdev::geometry blk_geom{
        VOS_STORAGE_BLKDEV_BLOCK_BYTES,
        VOS_STORAGE_BLKDEV_BLOCK_COUNT
    };
    const std::string r_create = dir + "/receipt-create.jsonl";
    {
        std::vector<uint8_t> fixture(
            sys_init_bytes, sys_init_bytes + VOS_STORAGE_BLKDEV_MEDIUM_BYTES);
        blkdev::image img(
            sys_img_path, blkdev::image::mode::create, blk_geom, fixture, r_create);
        persistence_bridge bridge{&img, {}};

        /* Publish batch at generation 2. */
        struct vos_storage_tx_spec batch_tx = {};
        batch_tx.op_kind = VOS_STORAGE_OP_INSERT_BATCH;
        batch_tx.commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE;
        batch_tx.entry_count = 5u;
        for (size_t i = 0; i < 5u; ++i) {
            batch_tx.entries[i].key = static_cast<uint64_t>((i + 1u) * 10u);
            batch_tx.entries[i].value = static_cast<uint64_t>((i + 1u) * 100u);
        }
        uint64_t ack = 0;
        if (!vos_storage_attach_persistence(&sys_store, persist_storage, &bridge) ||
            !vos_storage_reserve(&sys_store, sys_dom, &batch_tx) ||
            !vos_storage_stage(&sys_store, sys_dom) ||
            !vos_storage_publish(&sys_store, sys_dom, VOS_STORAGE_CUT_NONE, &ack) ||
            ack != 2u ||
            !persist_medium_to_blkdev(img, &sys_med) ||
            !img.close()) {
            std::fprintf(stderr, "storage_blkdev_join: gen2 persist failed\n");
            return 1;
        }
    }

    /* Verify receipt SHA-256 chaining between writer close and reader open. */
    const std::string r_reopen1 = dir + "/receipt-reopen1.jsonl";
    struct vos_storage_medium re_med;
    struct vos_storage_store re_store;
    if (!load_from_blkdev(
            sys_img_path, r_reopen1, &re_med, &re_store,
            &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, sys_dom) ||
        re_store.committed_generation != 2u ||
        re_store.committed_height == 0u) {
        std::fprintf(stderr, "storage_blkdev_join: gen2 reopen failed\n");
        return 1;
    }
    const std::string close_sha =
        extract_event_sha256(read_file_text(r_create), "close");
    const std::string open_sha =
        extract_event_sha256(read_file_text(r_reopen1), "open");
    if (close_sha.size() != 64 || close_sha != open_sha) {
        std::fprintf(stderr, "storage_blkdev_join: receipt sha256 mismatch\n");
        return 1;
    }

    /* Exercise BEFORE_ACK redo recovery across blkdev::image reopen. */
    const std::string r_cut5 = dir + "/receipt-cut5.jsonl";
    {
        const std::vector<uint8_t> empty_fixture;
        blkdev::image img(
            sys_img_path, blkdev::image::mode::open, blk_geom, empty_fixture, r_cut5);
        persistence_bridge bridge{&img, {}};
        struct vos_storage_tx_spec ins_tx = {};
        ins_tx.op_kind = VOS_STORAGE_OP_INSERT;
        ins_tx.commit_mode = VOS_STORAGE_COMMIT_FRESH;
        ins_tx.key = 60u;
        ins_tx.value = 600u;
        ins_tx.fresh_region_id = 1u;
        ins_tx.fresh_region_version = 1u;
        uint64_t ack = 0;
        if (!vos_storage_attach_persistence(&re_store, persist_storage, &bridge) ||
            !vos_storage_reserve(&re_store, sys_dom, &ins_tx) ||
            !vos_storage_stage(&re_store, sys_dom) ||
            vos_storage_publish(
                &re_store, sys_dom, VOS_STORAGE_CUT_BEFORE_ACK, &ack) ||
            !persist_medium_to_blkdev(img, &re_med) ||
            !img.close()) {
            std::fprintf(stderr, "storage_blkdev_join: cut5 persist failed\n");
            return 1;
        }
    }
    const std::string r_reopen2 = dir + "/receipt-reopen2.jsonl";
    uint64_t val = 0;
    if (!load_from_blkdev(
            sys_img_path, r_reopen2, &re_med, &re_store,
            &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, sys_dom) ||
        re_store.committed_generation != 3u ||
        re_med.checkpoint.sealed_epoch != 1u ||
        vos_storage_lookup(&re_store, sys_dom, 60u, &val) != VOS_TREE_FOUND ||
        val != 600u) {
        std::fprintf(stderr, "storage_blkdev_join: cut5 redo reopen failed\n");
        return 1;
    }

    /* Exercise BEFORE_EPOCH_SEAL rollback across blkdev::image reopen. */
    const std::string r_cut4 = dir + "/receipt-cut4.jsonl";
    {
        const std::vector<uint8_t> empty_fixture;
        blkdev::image img(
            sys_img_path, blkdev::image::mode::open, blk_geom, empty_fixture, r_cut4);
        persistence_bridge bridge{&img, {}};
        struct vos_storage_tx_spec fresh_tx = {};
        fresh_tx.op_kind = VOS_STORAGE_OP_INSERT;
        fresh_tx.commit_mode = VOS_STORAGE_COMMIT_FRESH;
        fresh_tx.key = 70u;
        fresh_tx.value = 700u;
        fresh_tx.fresh_region_id = 1u;
        fresh_tx.fresh_region_version = 2u;
        uint64_t ack = 0;
        if (!vos_storage_attach_persistence(&re_store, persist_storage, &bridge) ||
            !vos_storage_reserve(&re_store, sys_dom, &fresh_tx) ||
            !vos_storage_stage(&re_store, sys_dom) ||
            vos_storage_publish(
                &re_store, sys_dom, VOS_STORAGE_CUT_BEFORE_EPOCH_SEAL, &ack) ||
            !persist_medium_to_blkdev(img, &re_med) ||
            !img.close()) {
            std::fprintf(stderr, "storage_blkdev_join: cut4 persist failed\n");
            return 1;
        }
    }
    const std::string r_reopen3 = dir + "/receipt-reopen3.jsonl";
    if (!load_from_blkdev(
            sys_img_path, r_reopen3, &re_med, &re_store,
            &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, sys_dom) ||
        re_store.committed_generation != 3u ||
        re_med.nonce_record.reserved_generation != 4u ||
        vos_storage_lookup(&re_store, sys_dom, 70u, &val) != VOS_TREE_MISSING ||
        vos_storage_lookup(&re_store, sys_dom, 60u, &val) != VOS_TREE_FOUND ||
        val != 600u) {
        std::fprintf(stderr, "storage_blkdev_join: cut4 rollback reopen failed\n");
        return 1;
    }

    /* Exercise two-instance persistence + Q44 vos_storage_verify_resident
     * across both system.blk and user.blk reopened through blkdev::image. */
    static const uint8_t obj_bytes[32] = {
        0xdeu, 0xadu, 0xbeu, 0xefu, 0x11u, 0x22u, 0x33u, 0x44u,
        0x55u, 0x66u, 0x77u, 0x88u, 0x99u, 0xaau, 0xbbu, 0xccu,
        0x01u, 0x02u, 0x03u, 0x04u, 0x05u, 0x06u, 0x07u, 0x08u,
        0x56u, 0x4fu, 0x53u, 0x42u, 0x4cu, 0x4bu, 0x30u, 0x31u
    };
    struct vos_resident_identity sys_id = {};
    struct vos_resident_identity usr_id = {};
    uint64_t sys_tree_val = 0;
    uint64_t usr_tree_val = 0;
    re_store.committed_generation = 5u;
    usr_store.committed_generation = 2u;
    if (!vos_storage_bind_resident_identity(
            &re_store, 11u, 900u, 1u, VOS_RESIDENT_SYSTEM,
            obj_bytes, sizeof(obj_bytes), &sys_tree_val, &sys_id) ||
        !vos_storage_bind_resident_identity(
            &usr_store, 22u, 900u, 1u, VOS_RESIDENT_USER,
            obj_bytes, sizeof(obj_bytes), &usr_tree_val, &usr_id) ||
        std::memcmp(sys_id.root, usr_id.root, VOS_CRYPTO_DIGEST_BYTES) == 0) {
        std::fprintf(stderr, "storage_blkdev_join: bind resident identity failed\n");
        return 1;
    }
    re_store.committed_generation = 3u;
    usr_store.committed_generation = 1u;

    {
        const std::vector<uint8_t> empty_fixture;
        blkdev::image sys_img(
            sys_img_path, blkdev::image::mode::open, blk_geom, empty_fixture);
        persistence_bridge bridge{&sys_img, {}};
        struct vos_storage_tx_spec sys_tx = {};
        sys_tx.op_kind = VOS_STORAGE_OP_INSERT;
        sys_tx.commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE;
        sys_tx.key = 900u;
        sys_tx.value = sys_tree_val;
        uint64_t ack = 0;
        if (!vos_storage_attach_persistence(&re_store, persist_storage, &bridge) ||
            !vos_storage_reserve(&re_store, sys_dom, &sys_tx) ||
            !vos_storage_stage(&re_store, sys_dom) ||
            !vos_storage_publish(&re_store, sys_dom, VOS_STORAGE_CUT_NONE, &ack) ||
            ack != 5u ||
            !persist_medium_to_blkdev(sys_img, &re_med) ||
            !sys_img.close()) {
            std::fprintf(stderr, "storage_blkdev_join: sys resident commit failed\n");
            return 1;
        }
    }
    {
        std::vector<uint8_t> usr_fixture(
            usr_init_bytes, usr_init_bytes + VOS_STORAGE_BLKDEV_MEDIUM_BYTES);
        blkdev::image usr_img(
            usr_img_path, blkdev::image::mode::create, blk_geom, usr_fixture);
        persistence_bridge bridge{&usr_img, {}};
        struct vos_storage_tx_spec usr_tx = {};
        usr_tx.op_kind = VOS_STORAGE_OP_INSERT;
        usr_tx.commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE;
        usr_tx.key = 900u;
        usr_tx.value = usr_tree_val;
        uint64_t ack = 0;
        if (!vos_storage_attach_persistence(&usr_store, persist_storage, &bridge) ||
            !vos_storage_reserve(&usr_store, usr_dom, &usr_tx) ||
            !vos_storage_stage(&usr_store, usr_dom) ||
            !vos_storage_publish(&usr_store, usr_dom, VOS_STORAGE_CUT_NONE, &ack) ||
            ack != 2u ||
            !persist_medium_to_blkdev(usr_img, &usr_med) ||
            !usr_img.close()) {
            std::fprintf(stderr, "storage_blkdev_join: usr resident commit failed\n");
            return 1;
        }
    }

    struct vos_storage_medium sys_re_med;
    struct vos_storage_store sys_re_store;
    struct vos_storage_medium usr_re_med;
    struct vos_storage_store usr_re_store;
    if (!load_from_blkdev(
            sys_img_path, "", &sys_re_med, &sys_re_store,
            &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, sys_dom) ||
        !load_from_blkdev(
            usr_img_path, "", &usr_re_med, &usr_re_store,
            &crypto, VOS_CRYPTO_DOMAIN_USER, usr_dom)) {
        std::fprintf(stderr, "storage_blkdev_join: two-instance reopen failed\n");
        return 1;
    }

    struct vos_resident_owner owner;
    struct vos_storage_resident_receipt resident_receipt = {};
    struct vos_resident_handle handle = {};
    uint64_t seq = 0;
    uint8_t out[16] = {};
    size_t out_len = 0;
    if (!vos_storage_admit_resident(&sys_re_store, &sys_id, obj_bytes,
                                     sizeof(obj_bytes), &resident_receipt) ||
        !vos_resident_init(&owner, 1u, sys_id.generation, 64u, nullptr, nullptr) ||
        !vos_resident_publish(&owner, &sys_id, obj_bytes, sizeof(obj_bytes)) ||
        !vos_resident_admit(&owner, 0u, sys_dom, &sys_id, 0u, 16u, 1u, 10u, &handle) ||
        !vos_resident_begin(&owner, &handle, sys_dom, 0u, 16u, 2u, &seq) ||
        !vos_resident_complete(
            &owner, &handle, sys_dom, seq, 2u,
            vos_storage_verify_admitted_resident, &resident_receipt,
            out, sizeof(out), &out_len) ||
        out_len != 16u ||
        std::memcmp(out, obj_bytes, 16u) != 0) {
        std::fprintf(stderr, "storage_blkdev_join: reopened resident read failed\n");
        return 1;
    }

    std::printf("storage_blkdev_join: ok\n");
    return 0;
}
