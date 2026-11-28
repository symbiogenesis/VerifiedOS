// SPDX-License-Identifier: Apache-2.0
#include "vos_checkpoint.h"

_Static_assert(16u + VOS_CP_MAX_TEXT_BYTES + 16u * VOS_CP_MAX_UNDO <= VOS_CP_MAX_PAYLOAD_BYTES,
               "editor semantic payload fits wire buffer");
_Static_assert(24u + 48u * VOS_CP_MAX_TILES + 16u * VOS_CP_MAX_IMAGE_HISTORY <= VOS_CP_MAX_PAYLOAD_BYTES,
               "painter semantic payload fits wire buffer");

static const uint8_t VOS_CP_MAGIC[8] = {'V', 'O', 'S', 'S', 'E', 'M', '0', '1'};
static const uint64_t VOS_CP_DOMAIN_EDITOR = UINT64_C(0x564F534350454431);
static const uint64_t VOS_CP_DOMAIN_PAINTER = UINT64_C(0x564F534350505431);

static void zero_bytes(void *ptr, size_t length)
{
    if (ptr == NULL) {
        return;
    }
    volatile uint8_t *wipe = (volatile uint8_t *)ptr;
    for (size_t i = 0u; i < length; ++i) {
        wipe[i] = 0u;
    }
}

static void copy_bytes(uint8_t *dst, const uint8_t *src, size_t length)
{
    for (size_t i = 0u; i < length; ++i) {
        dst[i] = src[i];
    }
}

static int equal_bytes_ct(const uint8_t *a, const uint8_t *b, size_t length)
{
    uint8_t diff = 0u;
    for (size_t i = 0u; i < length; ++i) {
        diff |= (uint8_t)(a[i] ^ b[i]);
    }
    return diff == 0u;
}

static void put_le32(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8u);
    dst[2] = (uint8_t)(value >> 16u);
    dst[3] = (uint8_t)(value >> 24u);
}

static uint32_t get_le32(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8u) |
           ((uint32_t)src[2] << 16u) |
           ((uint32_t)src[3] << 24u);
}

static void put_le64(uint8_t *dst, uint64_t value)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(value >> (8u * i));
    }
}

static uint64_t get_le64(const uint8_t *src)
{
    uint64_t value = 0u;
    for (uint32_t i = 0u; i < 8u; ++i) {
        value |= ((uint64_t)src[i]) << (8u * i);
    }
    return value;
}

static int valid_app_id(uint32_t app_id)
{
    return app_id == VOS_CP_APP_EDITOR || app_id == VOS_CP_APP_PAINTER;
}

static uint32_t app_index(uint32_t app_id)
{
    return app_id == VOS_CP_APP_EDITOR ? 0u : 1u;
}

static uint32_t other_app_id(uint32_t app_id)
{
    return app_id == VOS_CP_APP_EDITOR ? VOS_CP_APP_PAINTER : VOS_CP_APP_EDITOR;
}

static uint64_t domain_for_app(uint32_t app_id)
{
    return app_id == VOS_CP_APP_EDITOR ? VOS_CP_DOMAIN_EDITOR : VOS_CP_DOMAIN_PAINTER;
}

struct vos_cp_roots vos_cp_roots_cleared(void)
{
    const struct vos_cp_roots r = {
        .inventory_complete = 1u,
        .bases_closed = 1u,
        .ingress_closed = 1u,
        .live_registers_clear = 1u,
        .raw_saved_clear = 1u,
        .mint_roots_clear = 1u,
        .loans_closed = 1u,
        .proxy_acknowledged = 1u,
        .devices_completed = 1u,
        .barrier_complete = 1u,
        .sweep_after_barrier = 1u,
        .sweep_complete = 1u,
        .data_tags_sanitized = 1u
    };
    return r;
}

/* [SemanticCheckpoint.v](../../proofs/SemanticCheckpoint.v#reusable_excludes_all_hazards)
 * connects these 13 root-clearance fields to [WorkflowProfiles.v](../../proofs/WorkflowProfiles.v#reusable). */
int vos_cp_roots_reusable(const struct vos_cp_roots *roots)
{
    if (roots == NULL) {
        return 0;
    }
    if (!roots->inventory_complete || !roots->bases_closed || !roots->ingress_closed) {
        return 0;
    }
    if (!roots->live_registers_clear) {
        return 0;
    }
    if (!roots->raw_saved_clear) {
        return 0;
    }
    if (!roots->mint_roots_clear) {
        return 0;
    }
    if (!roots->loans_closed) {
        return 0;
    }
    if (!roots->proxy_acknowledged) {
        return 0;
    }
    if (!roots->devices_completed) {
        return 0;
    }
    if (!roots->barrier_complete || !roots->sweep_after_barrier ||
        !roots->sweep_complete || !roots->data_tags_sanitized) {
        return 0;
    }
    return 1;
}

void vos_cp_editor_doc_init(struct vos_cp_editor_doc *doc)
{
    if (doc == NULL) {
        return;
    }
    zero_bytes(doc, sizeof(*doc));
}

int vos_cp_editor_apply_insert(struct vos_cp_editor_doc *doc, uint32_t offset, uint8_t ch)
{
    if (doc == NULL || doc->text_len >= VOS_CP_MAX_TEXT_BYTES ||
        offset > doc->text_len || doc->undo_count >= VOS_CP_MAX_UNDO) {
        return VOS_CP_ERR_INVALID_ARG;
    }
    for (uint32_t i = doc->text_len; i > offset; --i) {
        doc->text[i] = doc->text[i - 1u];
    }
    doc->text[offset] = ch;
    doc->text_len += 1u;
    struct vos_cp_undo_entry *u = &doc->undo[doc->undo_count];
    zero_bytes(u, sizeof(*u));
    u->op_kind = 1u;
    u->offset = offset;
    u->prev_cursor = doc->cursor;
    u->old_byte = 0u;
    u->new_byte = ch;
    doc->undo_count += 1u;
    doc->cursor = offset + 1u;
    doc->dirty = 1u;
    return VOS_CP_OK;
}

void vos_cp_painter_doc_init(struct vos_cp_painter_doc *doc,
                             uint32_t preview_width, uint32_t preview_height)
{
    if (doc == NULL) {
        return;
    }
    zero_bytes(doc, sizeof(*doc));
    doc->preview_width = preview_width;
    doc->preview_height = preview_height;
}

int vos_cp_painter_add_tile(struct vos_cp_painter_doc *doc, uint32_t tile_id,
                            uint32_t width, uint32_t height, uint32_t revision,
                            const uint8_t digest[VOS_CRYPTO_DIGEST_BYTES])
{
    if (doc == NULL || digest == NULL ||
        doc->tile_count >= VOS_CP_MAX_TILES ||
        doc->history_count >= VOS_CP_MAX_IMAGE_HISTORY) {
        return VOS_CP_ERR_INVALID_ARG;
    }
    struct vos_cp_tile_desc *t = &doc->tiles[doc->tile_count];
    t->tile_id = tile_id;
    t->width = width;
    t->height = height;
    t->revision = revision;
    copy_bytes(t->content_digest, digest, VOS_CRYPTO_DIGEST_BYTES);
    doc->tile_count += 1u;

    struct vos_cp_image_op *h = &doc->history[doc->history_count];
    h->op_kind = 1u;
    h->tile_id = tile_id;
    h->revision = revision;
    h->param = (width << 16u) ^ height;
    doc->history_count += 1u;
    doc->preview_epoch += 1u;
    doc->dirty = 1u;
    return VOS_CP_OK;
}

static int validate_meta_for_encode(const struct vos_cp_meta *meta, uint32_t expected_app)
{
    if (meta == NULL || meta->app_id != expected_app ||
        meta->schema_version != VOS_CP_SCHEMA_VERSION ||
        meta->generation == 0u) {
        return VOS_CP_ERR_BAD_FORMAT;
    }
    if (meta->payload_kind != VOS_CP_PAYLOAD_SEMANTIC) {
        return VOS_CP_ERR_NON_SEMANTIC;
    }
    if (meta->forbidden_flags != 0u) {
        return VOS_CP_ERR_FORBIDDEN_AUTHORITY;
    }
    if (meta->security_critical != 0u && meta->fresh_epoch == 0u) {
        return VOS_CP_ERR_FRESH_FAILED;
    }
    return VOS_CP_OK;
}

static void write_wire_header(uint8_t *dst, const struct vos_cp_meta *meta, uint32_t payload_len)
{
    copy_bytes(dst, VOS_CP_MAGIC, 8u);
    put_le32(dst + 8u, VOS_CP_WIRE_VERSION);
    put_le32(dst + 12u, meta->app_id);
    put_le32(dst + 16u, meta->payload_kind);
    put_le32(dst + 20u, meta->schema_version);
    put_le64(dst + 24u, meta->generation);
    put_le32(dst + 32u, meta->confidentiality_label);
    put_le32(dst + 36u, meta->security_critical);
    put_le64(dst + 40u, meta->fresh_epoch);
    put_le32(dst + 48u, meta->forbidden_flags);
    put_le32(dst + 52u, payload_len);
}

int vos_cp_encode_editor(const struct vos_cp_meta *meta,
                         const struct vos_cp_editor_doc *doc,
                         const uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                         uint8_t *out_wire, size_t out_cap, size_t *out_len)
{
    if (doc == NULL || auth_key == NULL || out_wire == NULL || out_len == NULL) {
        return VOS_CP_ERR_INVALID_ARG;
    }
    const int mrc = validate_meta_for_encode(meta, VOS_CP_APP_EDITOR);
    if (mrc != VOS_CP_OK) {
        return mrc;
    }
    if (doc->text_len > VOS_CP_MAX_TEXT_BYTES || doc->cursor > doc->text_len ||
        doc->undo_count > VOS_CP_MAX_UNDO) {
        return VOS_CP_ERR_BAD_FORMAT;
    }
    const uint32_t payload_len = 16u + doc->text_len + 16u * doc->undo_count;
    const size_t total_len = (size_t)VOS_CP_WIRE_HEADER_BYTES + (size_t)payload_len +
                             (size_t)VOS_CRYPTO_DIGEST_BYTES;
    if (out_cap < total_len) {
        return VOS_CP_ERR_OUT_OF_SPACE;
    }
    write_wire_header(out_wire, meta, payload_len);
    size_t at = VOS_CP_WIRE_HEADER_BYTES;
    put_le32(out_wire + at, doc->text_len);
    put_le32(out_wire + at + 4u, doc->cursor);
    put_le32(out_wire + at + 8u, doc->undo_count);
    put_le32(out_wire + at + 12u, doc->dirty ? 1u : 0u);
    at += 16u;
    if (doc->text_len != 0u) {
        copy_bytes(out_wire + at, doc->text, doc->text_len);
        at += doc->text_len;
    }
    for (uint32_t i = 0u; i < doc->undo_count; ++i) {
        const struct vos_cp_undo_entry *u = &doc->undo[i];
        put_le32(out_wire + at, u->op_kind);
        put_le32(out_wire + at + 4u, u->offset);
        put_le32(out_wire + at + 8u, u->prev_cursor);
        out_wire[at + 12u] = u->old_byte;
        out_wire[at + 13u] = u->new_byte;
        out_wire[at + 14u] = u->reserved[0];
        out_wire[at + 15u] = u->reserved[1];
        at += 16u;
    }
    if (!vos_hmac_sha256(auth_key, VOS_CRYPTO_DIGEST_BYTES,
                         out_wire, at, out_wire + at)) {
        zero_bytes(out_wire, total_len);
        return VOS_CP_ERR_AUTH_FAILED;
    }
    *out_len = total_len;
    return VOS_CP_OK;
}

int vos_cp_encode_painter(const struct vos_cp_meta *meta,
                          const struct vos_cp_painter_doc *doc,
                          const uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                          uint8_t *out_wire, size_t out_cap, size_t *out_len)
{
    if (doc == NULL || auth_key == NULL || out_wire == NULL || out_len == NULL) {
        return VOS_CP_ERR_INVALID_ARG;
    }
    const int mrc = validate_meta_for_encode(meta, VOS_CP_APP_PAINTER);
    if (mrc != VOS_CP_OK) {
        return mrc;
    }
    if (doc->tile_count > VOS_CP_MAX_TILES ||
        doc->history_count > VOS_CP_MAX_IMAGE_HISTORY) {
        return VOS_CP_ERR_BAD_FORMAT;
    }
    const uint32_t payload_len =
        24u + 48u * doc->tile_count + 16u * doc->history_count;
    const size_t total_len = (size_t)VOS_CP_WIRE_HEADER_BYTES + (size_t)payload_len +
                             (size_t)VOS_CRYPTO_DIGEST_BYTES;
    if (out_cap < total_len) {
        return VOS_CP_ERR_OUT_OF_SPACE;
    }
    write_wire_header(out_wire, meta, payload_len);
    size_t at = VOS_CP_WIRE_HEADER_BYTES;
    put_le32(out_wire + at, doc->tile_count);
    put_le32(out_wire + at + 4u, doc->preview_width);
    put_le32(out_wire + at + 8u, doc->preview_height);
    put_le32(out_wire + at + 12u, doc->preview_epoch);
    put_le32(out_wire + at + 16u, doc->history_count);
    put_le32(out_wire + at + 20u, doc->dirty ? 1u : 0u);
    at += 24u;
    for (uint32_t i = 0u; i < doc->tile_count; ++i) {
        const struct vos_cp_tile_desc *t = &doc->tiles[i];
        put_le32(out_wire + at, t->tile_id);
        put_le32(out_wire + at + 4u, t->width);
        put_le32(out_wire + at + 8u, t->height);
        put_le32(out_wire + at + 12u, t->revision);
        copy_bytes(out_wire + at + 16u, t->content_digest, VOS_CRYPTO_DIGEST_BYTES);
        at += 48u;
    }
    for (uint32_t i = 0u; i < doc->history_count; ++i) {
        const struct vos_cp_image_op *h = &doc->history[i];
        put_le32(out_wire + at, h->op_kind);
        put_le32(out_wire + at + 4u, h->tile_id);
        put_le32(out_wire + at + 8u, h->revision);
        put_le32(out_wire + at + 12u, h->param);
        at += 16u;
    }
    if (!vos_hmac_sha256(auth_key, VOS_CRYPTO_DIGEST_BYTES,
                         out_wire, at, out_wire + at)) {
        zero_bytes(out_wire, total_len);
        return VOS_CP_ERR_AUTH_FAILED;
    }
    *out_len = total_len;
    return VOS_CP_OK;
}

static int parse_and_verify_header(const uint8_t *wire, size_t wire_len,
                                   const uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                                   uint32_t expected_app,
                                   uint32_t expected_label,
                                   struct vos_cp_meta *out_meta,
                                   uint32_t *out_payload_len)
{
    if (wire == NULL || auth_key == NULL || out_meta == NULL || out_payload_len == NULL) {
        return VOS_CP_ERR_INVALID_ARG;
    }
    if (wire_len < (size_t)VOS_CP_WIRE_HEADER_BYTES + (size_t)VOS_CRYPTO_DIGEST_BYTES ||
        wire_len > (size_t)VOS_CP_MAX_WIRE_BYTES) {
        return VOS_CP_ERR_BAD_FORMAT;
    }
    if (!equal_bytes_ct(wire, VOS_CP_MAGIC, 8u)) {
        return VOS_CP_ERR_BAD_FORMAT;
    }
    const uint32_t version = get_le32(wire + 8u);
    const uint32_t app_id = get_le32(wire + 12u);
    const uint32_t payload_kind = get_le32(wire + 16u);
    const uint32_t schema_version = get_le32(wire + 20u);
    const uint64_t generation = get_le64(wire + 24u);
    const uint32_t label = get_le32(wire + 32u);
    const uint32_t sec_crit = get_le32(wire + 36u);
    const uint64_t fresh_epoch = get_le64(wire + 40u);
    const uint32_t forbidden_flags = get_le32(wire + 48u);
    const uint32_t payload_len = get_le32(wire + 52u);

    if (version != VOS_CP_WIRE_VERSION || app_id != expected_app ||
        schema_version != VOS_CP_SCHEMA_VERSION || generation == 0u ||
        label != expected_label) {
        return VOS_CP_ERR_BAD_FORMAT;
    }
    if (payload_kind != VOS_CP_PAYLOAD_SEMANTIC) {
        return VOS_CP_ERR_NON_SEMANTIC;
    }
    if (forbidden_flags != 0u) {
        return VOS_CP_ERR_FORBIDDEN_AUTHORITY;
    }
    if (sec_crit != 0u && fresh_epoch == 0u) {
        return VOS_CP_ERR_FRESH_FAILED;
    }
    if (payload_len > VOS_CP_MAX_PAYLOAD_BYTES) {
        return VOS_CP_ERR_BAD_FORMAT;
    }
    const size_t expected_total = (size_t)VOS_CP_WIRE_HEADER_BYTES +
                                  (size_t)payload_len +
                                  (size_t)VOS_CRYPTO_DIGEST_BYTES;
    if (wire_len != expected_total) {
        return VOS_CP_ERR_TRAILING_BYTES;
    }

    uint8_t computed_mac[VOS_CRYPTO_DIGEST_BYTES];
    const size_t mac_offset = (size_t)VOS_CP_WIRE_HEADER_BYTES + (size_t)payload_len;
    if (!vos_hmac_sha256(auth_key, VOS_CRYPTO_DIGEST_BYTES,
                         wire, mac_offset, computed_mac)) {
        return VOS_CP_ERR_AUTH_FAILED;
    }
    const int mac_match = equal_bytes_ct(computed_mac, wire + mac_offset,
                                         VOS_CRYPTO_DIGEST_BYTES);
    zero_bytes(computed_mac, sizeof(computed_mac));
    if (!mac_match) {
        return VOS_CP_ERR_AUTH_FAILED;
    }

    out_meta->app_id = app_id;
    out_meta->payload_kind = payload_kind;
    out_meta->schema_version = schema_version;
    out_meta->generation = generation;
    out_meta->confidentiality_label = label;
    out_meta->security_critical = sec_crit;
    out_meta->fresh_epoch = fresh_epoch;
    out_meta->forbidden_flags = forbidden_flags;
    *out_payload_len = payload_len;
    return VOS_CP_OK;
}

int vos_cp_decode_editor(const uint8_t *wire, size_t wire_len,
                         const uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                         uint32_t expected_label,
                         struct vos_cp_meta *out_meta,
                         struct vos_cp_editor_doc *out_doc)
{
    if (out_doc == NULL) {
        return VOS_CP_ERR_INVALID_ARG;
    }
    struct vos_cp_meta meta;
    uint32_t payload_len = 0u;
    const int hrc = parse_and_verify_header(wire, wire_len, auth_key,
                                            VOS_CP_APP_EDITOR, expected_label,
                                            &meta, &payload_len);
    if (hrc != VOS_CP_OK) {
        return hrc;
    }
    if (payload_len < 16u) {
        return VOS_CP_ERR_BAD_FORMAT;
    }
    const uint8_t *p = wire + VOS_CP_WIRE_HEADER_BYTES;
    const uint32_t text_len = get_le32(p);
    const uint32_t cursor = get_le32(p + 4u);
    const uint32_t undo_count = get_le32(p + 8u);
    const uint32_t dirty = get_le32(p + 12u);
    if (text_len > VOS_CP_MAX_TEXT_BYTES || cursor > text_len ||
        undo_count > VOS_CP_MAX_UNDO) {
        return VOS_CP_ERR_BAD_FORMAT;
    }
    const uint32_t expected_payload = 16u + text_len + 16u * undo_count;
    if (payload_len != expected_payload) {
        return VOS_CP_ERR_TRAILING_BYTES;
    }
    struct vos_cp_editor_doc tmp;
    zero_bytes(&tmp, sizeof(tmp));
    tmp.text_len = text_len;
    tmp.cursor = cursor;
    tmp.undo_count = undo_count;
    tmp.dirty = dirty ? 1u : 0u;
    size_t at = 16u;
    if (text_len != 0u) {
        copy_bytes(tmp.text, p + at, text_len);
        at += text_len;
    }
    for (uint32_t i = 0u; i < undo_count; ++i) {
        tmp.undo[i].op_kind = get_le32(p + at);
        tmp.undo[i].offset = get_le32(p + at + 4u);
        tmp.undo[i].prev_cursor = get_le32(p + at + 8u);
        tmp.undo[i].old_byte = p[at + 12u];
        tmp.undo[i].new_byte = p[at + 13u];
        tmp.undo[i].reserved[0] = p[at + 14u];
        tmp.undo[i].reserved[1] = p[at + 15u];
        at += 16u;
    }
    *out_meta = meta;
    *out_doc = tmp;
    return VOS_CP_OK;
}

int vos_cp_decode_painter(const uint8_t *wire, size_t wire_len,
                          const uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                          uint32_t expected_label,
                          struct vos_cp_meta *out_meta,
                          struct vos_cp_painter_doc *out_doc)
{
    if (out_doc == NULL) {
        return VOS_CP_ERR_INVALID_ARG;
    }
    struct vos_cp_meta meta;
    uint32_t payload_len = 0u;
    const int hrc = parse_and_verify_header(wire, wire_len, auth_key,
                                            VOS_CP_APP_PAINTER, expected_label,
                                            &meta, &payload_len);
    if (hrc != VOS_CP_OK) {
        return hrc;
    }
    if (payload_len < 24u) {
        return VOS_CP_ERR_BAD_FORMAT;
    }
    const uint8_t *p = wire + VOS_CP_WIRE_HEADER_BYTES;
    const uint32_t tile_count = get_le32(p);
    const uint32_t pw = get_le32(p + 4u);
    const uint32_t ph = get_le32(p + 8u);
    const uint32_t pe = get_le32(p + 12u);
    const uint32_t history_count = get_le32(p + 16u);
    const uint32_t dirty = get_le32(p + 20u);
    if (tile_count > VOS_CP_MAX_TILES || history_count > VOS_CP_MAX_IMAGE_HISTORY) {
        return VOS_CP_ERR_BAD_FORMAT;
    }
    const uint32_t expected_payload = 24u + 48u * tile_count + 16u * history_count;
    if (payload_len != expected_payload) {
        return VOS_CP_ERR_TRAILING_BYTES;
    }
    struct vos_cp_painter_doc tmp;
    zero_bytes(&tmp, sizeof(tmp));
    tmp.tile_count = tile_count;
    tmp.preview_width = pw;
    tmp.preview_height = ph;
    tmp.preview_epoch = pe;
    tmp.history_count = history_count;
    tmp.dirty = dirty ? 1u : 0u;
    size_t at = 24u;
    for (uint32_t i = 0u; i < tile_count; ++i) {
        tmp.tiles[i].tile_id = get_le32(p + at);
        tmp.tiles[i].width = get_le32(p + at + 4u);
        tmp.tiles[i].height = get_le32(p + at + 8u);
        tmp.tiles[i].revision = get_le32(p + at + 12u);
        copy_bytes(tmp.tiles[i].content_digest, p + at + 16u, VOS_CRYPTO_DIGEST_BYTES);
        at += 48u;
    }
    for (uint32_t i = 0u; i < history_count; ++i) {
        tmp.history[i].op_kind = get_le32(p + at);
        tmp.history[i].tile_id = get_le32(p + at + 4u);
        tmp.history[i].revision = get_le32(p + at + 8u);
        tmp.history[i].param = get_le32(p + at + 12u);
        at += 16u;
    }
    *out_meta = meta;
    *out_doc = tmp;
    return VOS_CP_OK;
}

int vos_cp_exclusive_slate(const struct vos_cp_engine *eng)
{
    if (eng == NULL) {
        return 0;
    }
    return !(eng->apps[0].owns_slate != 0u && eng->apps[1].owns_slate != 0u);
}

const struct vos_cp_durable_slot *vos_cp_active_slot(const struct vos_cp_engine *eng,
                                                     uint32_t app_id)
{
    if (eng == NULL || !valid_app_id(app_id)) {
        return NULL;
    }
    const struct vos_cp_ab_store *st = &eng->stores[app_index(app_id)];
    const struct vos_cp_durable_slot *slot = &st->slots[st->active_slot];
    if (!slot->valid || !slot->committed) {
        return NULL;
    }
    return slot;
}

int vos_cp_engine_init(struct vos_cp_engine *eng,
                       const uint8_t auth_key[VOS_CRYPTO_DIGEST_BYTES],
                       const uint8_t master_key[VOS_CRYPTO_KEY_BYTES_256],
                       uint32_t space_reserved,
                       uint32_t endurance_limit,
                       uint32_t confidentiality_label)
{
    if (eng == NULL || auth_key == NULL || master_key == NULL ||
        space_reserved == 0u || space_reserved > VOS_CP_MAX_WIRE_BYTES ||
        endurance_limit == 0u) {
        return VOS_CP_ERR_INVALID_ARG;
    }
    zero_bytes(eng, sizeof(*eng));
    copy_bytes(eng->auth_key, auth_key, VOS_CRYPTO_DIGEST_BYTES);
    vos_crypto_core_init(&eng->crypto, (uint64_t)endurance_limit + 16u);
    if (!vos_crypto_core_unlock_domain(&eng->crypto, 0u, VOS_CP_DOMAIN_EDITOR, 1u,
                                       master_key, VOS_CRYPTO_KEY_BYTES_256) ||
        !vos_crypto_core_unlock_domain(&eng->crypto, 1u, VOS_CP_DOMAIN_PAINTER, 1u,
                                       master_key, VOS_CRYPTO_KEY_BYTES_256)) {
        zero_bytes(eng, sizeof(*eng));
        return VOS_CP_ERR_AUTH_FAILED;
    }
    eng->space_reserved = space_reserved;
    eng->endurance_limit = endurance_limit;
    eng->confidentiality_label = confidentiality_label;
    eng->selected_app = VOS_CP_APP_EDITOR;
    eng->target_app = VOS_CP_APP_NONE;
    eng->recovery_outcome = VOS_CP_RECOVERY_NONE;

    eng->apps[0].phase = VOS_CP_PHASE_ACTIVE;
    eng->apps[0].owns_slate = 1u;
    eng->apps[0].document_grant = 1u;
    eng->apps[0].session_authority = 1u;

    eng->apps[1].phase = VOS_CP_PHASE_HIBERNATED;
    eng->apps[1].owns_slate = 0u;
    eng->apps[1].document_grant = 0u;
    eng->apps[1].session_authority = 0u;

    vos_cp_editor_doc_init(&eng->editor_doc);
    vos_cp_painter_doc_init(&eng->painter_doc, 64u, 64u);

    /* Install initial baseline checkpoints for both apps in slot 0. */
    eng->stores[0].next_generation = 1u;
    eng->stores[1].next_generation = 1u;

    struct vos_cp_meta ed_meta = {
        .app_id = VOS_CP_APP_EDITOR,
        .payload_kind = VOS_CP_PAYLOAD_SEMANTIC,
        .schema_version = VOS_CP_SCHEMA_VERSION,
        .generation = 1u,
        .confidentiality_label = confidentiality_label,
        .security_critical = 0u,
        .fresh_epoch = 0u,
        .forbidden_flags = 0u
    };
    size_t ed_len = 0u;
    const int e_rc = vos_cp_encode_editor(&ed_meta, &eng->editor_doc, eng->auth_key,
                                          eng->stores[0].slots[0].wire,
                                          VOS_CP_MAX_WIRE_BYTES, &ed_len);
    if (e_rc != VOS_CP_OK) {
        return e_rc;
    }
    eng->stores[0].slots[0].valid = 1u;
    eng->stores[0].slots[0].committed = 1u;
    eng->stores[0].slots[0].generation = 1u;
    eng->stores[0].slots[0].wire_len = (uint32_t)ed_len;
    eng->stores[0].next_generation = 2u;

    struct vos_cp_meta pt_meta = {
        .app_id = VOS_CP_APP_PAINTER,
        .payload_kind = VOS_CP_PAYLOAD_SEMANTIC,
        .schema_version = VOS_CP_SCHEMA_VERSION,
        .generation = 1u,
        .confidentiality_label = confidentiality_label,
        .security_critical = 0u,
        .fresh_epoch = 0u,
        .forbidden_flags = 0u
    };
    size_t pt_len = 0u;
    const int p_rc = vos_cp_encode_painter(&pt_meta, &eng->painter_doc, eng->auth_key,
                                           eng->stores[1].slots[0].wire,
                                           VOS_CP_MAX_WIRE_BYTES, &pt_len);
    if (p_rc != VOS_CP_OK) {
        return p_rc;
    }
    eng->stores[1].slots[0].valid = 1u;
    eng->stores[1].slots[0].committed = 1u;
    eng->stores[1].slots[0].generation = 1u;
    eng->stores[1].slots[0].wire_len = (uint32_t)pt_len;
    eng->stores[1].next_generation = 2u;
    return VOS_CP_OK;
}

int vos_cp_request_switch(struct vos_cp_engine *eng, uint32_t target_app)
{
    if (eng == NULL || !valid_app_id(target_app)) {
        return VOS_CP_ERR_INVALID_ARG;
    }
    if (eng->target_app != VOS_CP_APP_NONE || target_app == eng->selected_app) {
        return VOS_CP_ERR_BAD_STATE;
    }
    if (eng->endurance_used >= eng->endurance_limit) {
        return VOS_CP_ERR_ENDURANCE_EXHAUSTED;
    }
    struct vos_cp_app_runtime *old_app = &eng->apps[app_index(eng->selected_app)];
    if (old_app->phase != VOS_CP_PHASE_ACTIVE &&
        old_app->phase != VOS_CP_PHASE_CLOSED) {
        return VOS_CP_ERR_BAD_STATE;
    }
    if (old_app->phase == VOS_CP_PHASE_ACTIVE) {
        old_app->phase = VOS_CP_PHASE_QUIESCING;
    }
    old_app->retirement_committed = 0u;
    eng->target_app = target_app;
    return VOS_CP_OK;
}

int vos_cp_stage_current(struct vos_cp_engine *eng, uint32_t security_critical)
{
    if (eng == NULL || eng->target_app == VOS_CP_APP_NONE) {
        return VOS_CP_ERR_BAD_STATE;
    }
    const uint32_t cur_id = eng->selected_app;
    const uint32_t idx = app_index(cur_id);
    struct vos_cp_app_runtime *cur = &eng->apps[idx];
    if (cur->phase != VOS_CP_PHASE_QUIESCING) {
        return VOS_CP_ERR_BAD_STATE;
    }
    if (eng->endurance_used >= eng->endurance_limit) {
        return VOS_CP_ERR_ENDURANCE_EXHAUSTED;
    }

    struct vos_cp_ab_store *st = &eng->stores[idx];
    /* Stage strictly into the INACTIVE slot so active_slot remains intact pre-commit. */
    const uint32_t stage_idx = 1u - st->active_slot;
    struct vos_cp_durable_slot *dst = &st->slots[stage_idx];

    uint8_t candidate_wire[VOS_CP_MAX_WIRE_BYTES];
    size_t candidate_len = 0u;
    const uint64_t gen = st->next_generation;

    struct vos_cp_meta meta = {
        .app_id = cur_id,
        .payload_kind = VOS_CP_PAYLOAD_SEMANTIC,
        .schema_version = VOS_CP_SCHEMA_VERSION,
        .generation = gen,
        .confidentiality_label = eng->confidentiality_label,
        .security_critical = security_critical ? 1u : 0u,
        .fresh_epoch = security_critical ? (uint64_t)(eng->crypto.rot_epoch_counter + 1u) : 0u,
        .forbidden_flags = 0u
    };

    int rc = VOS_CP_ERR_BAD_STATE;
    if (cur_id == VOS_CP_APP_EDITOR) {
        rc = vos_cp_encode_editor(&meta, &eng->editor_doc, eng->auth_key,
                                  candidate_wire, sizeof(candidate_wire), &candidate_len);
    } else {
        rc = vos_cp_encode_painter(&meta, &eng->painter_doc, eng->auth_key,
                                   candidate_wire, sizeof(candidate_wire), &candidate_len);
    }
    if (rc != VOS_CP_OK) {
        return rc;
    }
    if (candidate_len > (size_t)eng->space_reserved) {
        return VOS_CP_ERR_OUT_OF_SPACE;
    }

    uint64_t sealed_epoch = 0u;
    uint8_t sealed_root[VOS_CRYPTO_DIGEST_BYTES];
    zero_bytes(sealed_root, sizeof(sealed_root));
    if (security_critical != 0u) {
        uint8_t digest[VOS_CRYPTO_DIGEST_BYTES];
        if (!vos_sha256(candidate_wire,
                        candidate_len - (size_t)VOS_CRYPTO_DIGEST_BYTES,
                        digest)) {
            return VOS_CP_ERR_AUTH_FAILED;
        }
        if (!vos_crypto_core_seal_epoch(&eng->crypto, idx, domain_for_app(cur_id),
                                        gen, digest, &sealed_epoch, sealed_root) ||
            sealed_epoch != meta.fresh_epoch) {
            return VOS_CP_ERR_FRESH_FAILED;
        }
    }

    zero_bytes(dst, sizeof(*dst));
    copy_bytes(dst->wire, candidate_wire, candidate_len);
    dst->wire_len = (uint32_t)candidate_len;
    dst->generation = gen;
    dst->fresh_epoch = sealed_epoch;
    copy_bytes(dst->fresh_root, sealed_root, VOS_CRYPTO_DIGEST_BYTES);
    dst->valid = 1u;
    dst->committed = 0u;

    st->staging_dirty = 1u;
    st->next_generation += 1u;
    eng->endurance_used += 1u;
    return VOS_CP_OK;
}

int vos_cp_commit_staged(struct vos_cp_engine *eng)
{
    if (eng == NULL || eng->target_app == VOS_CP_APP_NONE) {
        return VOS_CP_ERR_BAD_STATE;
    }
    const uint32_t cur_id = eng->selected_app;
    const uint32_t idx = app_index(cur_id);
    struct vos_cp_app_runtime *cur = &eng->apps[idx];
    struct vos_cp_ab_store *st = &eng->stores[idx];
    if (cur->phase != VOS_CP_PHASE_QUIESCING || !st->staging_dirty) {
        return VOS_CP_ERR_BAD_STATE;
    }
    const uint32_t stage_idx = 1u - st->active_slot;
    struct vos_cp_durable_slot *staged = &st->slots[stage_idx];
    if (!staged->valid || staged->wire_len > eng->space_reserved) {
        return VOS_CP_ERR_INCOMPLETE_CHECKPOINT;
    }

    /* Independently verify the staged semantic wire before flipping active_slot. */
    struct vos_cp_meta decoded_meta;
    int vrc = VOS_CP_ERR_BAD_STATE;
    if (cur_id == VOS_CP_APP_EDITOR) {
        struct vos_cp_editor_doc tmp_ed;
        vrc = vos_cp_decode_editor(staged->wire, staged->wire_len, eng->auth_key,
                                   eng->confidentiality_label, &decoded_meta, &tmp_ed);
    } else {
        struct vos_cp_painter_doc tmp_pt;
        vrc = vos_cp_decode_painter(staged->wire, staged->wire_len, eng->auth_key,
                                    eng->confidentiality_label, &decoded_meta, &tmp_pt);
    }
    if (vrc != VOS_CP_OK) {
        return vrc;
    }

    staged->committed = 1u;
    st->active_slot = stage_idx;
    st->staging_dirty = 0u;
    cur->phase = VOS_CP_PHASE_RETIRING;
    cur->document_grant = 0u;
    cur->session_authority = 0u;
    cur->retirement_committed = 1u;
    return VOS_CP_OK;
}

int vos_cp_release_slate(struct vos_cp_engine *eng, const struct vos_cp_roots *roots)
{
    if (eng == NULL || eng->target_app == VOS_CP_APP_NONE) {
        return VOS_CP_ERR_BAD_STATE;
    }
    const uint32_t idx = app_index(eng->selected_app);
    struct vos_cp_app_runtime *cur = &eng->apps[idx];
    if (cur->phase != VOS_CP_PHASE_RETIRING || !cur->retirement_committed) {
        return VOS_CP_ERR_BAD_STATE;
    }
    if (!vos_cp_roots_reusable(roots)) {
        return VOS_CP_ERR_REUSE_BARRIER;
    }
    cur->phase = VOS_CP_PHASE_HIBERNATED;
    cur->owns_slate = 0u;
    cur->document_grant = 0u;
    cur->session_authority = 0u;
    cur->tagged_state_restored = 0u;
    cur->retirement_committed = 0u;
    return VOS_CP_OK;
}

int vos_cp_begin_restore(struct vos_cp_engine *eng, uint32_t target_app)
{
    if (eng == NULL || !valid_app_id(target_app) || eng->target_app != target_app) {
        return VOS_CP_ERR_BAD_STATE;
    }
    const uint32_t dst_idx = app_index(target_app);
    const uint32_t other_idx = app_index(other_app_id(target_app));
    struct vos_cp_app_runtime *dst = &eng->apps[dst_idx];
    const struct vos_cp_app_runtime *other = &eng->apps[other_idx];

    if (dst->owns_slate != 0u || other->owns_slate != 0u) {
        return VOS_CP_ERR_DUAL_OWNERSHIP;
    }
    if (dst->phase != VOS_CP_PHASE_HIBERNATED && dst->phase != VOS_CP_PHASE_CLOSED) {
        return VOS_CP_ERR_BAD_STATE;
    }
    if (vos_cp_active_slot(eng, target_app) == NULL) {
        return VOS_CP_ERR_INCOMPLETE_CHECKPOINT;
    }

    dst->phase = VOS_CP_PHASE_RESTORING;
    dst->owns_slate = 1u;
    dst->document_grant = 0u;
    dst->session_authority = 0u;
    dst->tagged_state_restored = 0u;
    return VOS_CP_OK;
}

static int verify_slot_fresh_if_needed(const struct vos_cp_engine *eng,
                                       uint32_t app_id,
                                       const struct vos_cp_durable_slot *slot,
                                       const struct vos_cp_meta *meta)
{
    if (meta->security_critical == 0u) {
        return VOS_CP_OK;
    }
    uint8_t digest[VOS_CRYPTO_DIGEST_BYTES];
    if (!vos_sha256(slot->wire,
                    (size_t)slot->wire_len - (size_t)VOS_CRYPTO_DIGEST_BYTES,
                    digest)) {
        return VOS_CP_ERR_FRESH_FAILED;
    }
    if (!vos_crypto_core_verify_epoch(&eng->crypto, app_index(app_id),
                                      meta->fresh_epoch, domain_for_app(app_id),
                                      meta->generation, digest, slot->fresh_root)) {
        return VOS_CP_ERR_FRESH_FAILED;
    }
    return VOS_CP_OK;
}

int vos_cp_finish_restore(struct vos_cp_engine *eng, uint32_t target_app,
                          uint32_t grant_state)
{
    if (eng == NULL || !valid_app_id(target_app) || eng->target_app != target_app) {
        return VOS_CP_ERR_BAD_STATE;
    }
    const uint32_t dst_idx = app_index(target_app);
    struct vos_cp_app_runtime *dst = &eng->apps[dst_idx];
    if (dst->phase != VOS_CP_PHASE_RESTORING || dst->owns_slate == 0u) {
        return VOS_CP_ERR_BAD_STATE;
    }
    const struct vos_cp_durable_slot *slot = vos_cp_active_slot(eng, target_app);
    if (slot == NULL || slot->wire_len > eng->space_reserved) {
        eng->recovery_outcome = VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT;
        return VOS_CP_ERR_INCOMPLETE_CHECKPOINT;
    }

    struct vos_cp_meta meta;
    if (target_app == VOS_CP_APP_EDITOR) {
        struct vos_cp_editor_doc tmp_ed;
        const int rc = vos_cp_decode_editor(slot->wire, slot->wire_len, eng->auth_key,
                                            eng->confidentiality_label, &meta, &tmp_ed);
        if (rc != VOS_CP_OK) {
            eng->recovery_outcome = VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT;
            return rc;
        }
        const int frc = verify_slot_fresh_if_needed(eng, target_app, slot, &meta);
        if (frc != VOS_CP_OK) {
            eng->recovery_outcome = VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT;
            return frc;
        }
        if (grant_state != VOS_CP_GRANT_VALID) {
            dst->document_grant = 0u;
            dst->session_authority = 0u;
            dst->tagged_state_restored = 0u;
            eng->recovery_outcome = VOS_CP_RECOVERY_GRANT_REFUSED;
            return VOS_CP_ERR_GRANT_REFUSED;
        }
        eng->editor_doc = tmp_ed;
    } else {
        struct vos_cp_painter_doc tmp_pt;
        const int rc = vos_cp_decode_painter(slot->wire, slot->wire_len, eng->auth_key,
                                             eng->confidentiality_label, &meta, &tmp_pt);
        if (rc != VOS_CP_OK) {
            eng->recovery_outcome = VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT;
            return rc;
        }
        const int frc = verify_slot_fresh_if_needed(eng, target_app, slot, &meta);
        if (frc != VOS_CP_OK) {
            eng->recovery_outcome = VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT;
            return frc;
        }
        if (grant_state != VOS_CP_GRANT_VALID) {
            dst->document_grant = 0u;
            dst->session_authority = 0u;
            dst->tagged_state_restored = 0u;
            eng->recovery_outcome = VOS_CP_RECOVERY_GRANT_REFUSED;
            return VOS_CP_ERR_GRANT_REFUSED;
        }
        eng->painter_doc = tmp_pt;
    }

    dst->phase = VOS_CP_PHASE_ACTIVE;
    dst->owns_slate = 1u;
    dst->document_grant = 1u;
    /* Never reinstate prior session authority or tagged capabilities on restore. */
    dst->session_authority = 0u;
    dst->tagged_state_restored = 0u;
    eng->selected_app = target_app;
    eng->target_app = VOS_CP_APP_NONE;
    eng->locked = 0u;
    eng->recovery_outcome = VOS_CP_RECOVERY_OK;
    return VOS_CP_OK;
}

void vos_cp_inject_crash(struct vos_cp_engine *eng)
{
    if (eng == NULL) {
        return;
    }
    for (uint32_t i = 0u; i < VOS_CP_APP_COUNT; ++i) {
        struct vos_cp_app_runtime *app = &eng->apps[i];
        app->phase = app->owns_slate ? VOS_CP_PHASE_RETIRING : VOS_CP_PHASE_HIBERNATED;
        app->document_grant = 0u;
        app->session_authority = 0u;
        app->tagged_state_restored = 0u;
        app->retirement_committed = 0u;

        struct vos_cp_ab_store *st = &eng->stores[i];
        const uint32_t inactive = 1u - st->active_slot;
        zero_bytes(&st->slots[inactive], sizeof(st->slots[inactive]));
        st->staging_dirty = 0u;
    }
    vos_cp_editor_doc_init(&eng->editor_doc);
    vos_cp_painter_doc_init(&eng->painter_doc, 0u, 0u);
    eng->target_app = other_app_id(eng->selected_app);
}

int vos_cp_recover_quarantined_slate(struct vos_cp_engine *eng,
                                     const struct vos_cp_roots *roots)
{
    if (eng == NULL) {
        return VOS_CP_ERR_INVALID_ARG;
    }
    if (!vos_cp_exclusive_slate(eng)) {
        return VOS_CP_ERR_DUAL_OWNERSHIP;
    }
    if (!vos_cp_roots_reusable(roots)) {
        return VOS_CP_ERR_REUSE_BARRIER;
    }
    uint32_t owner_idx = app_index(eng->selected_app);
    if (eng->apps[0].owns_slate != 0u) {
        owner_idx = 0u;
    } else if (eng->apps[1].owns_slate != 0u) {
        owner_idx = 1u;
    }
    struct vos_cp_app_runtime *owner = &eng->apps[owner_idx];
    if (owner->phase != VOS_CP_PHASE_RETIRING &&
        owner->phase != VOS_CP_PHASE_HIBERNATED) {
        return VOS_CP_ERR_BAD_STATE;
    }
    owner->phase = VOS_CP_PHASE_CLOSED;
    owner->owns_slate = 0u;
    owner->document_grant = 0u;
    owner->session_authority = 0u;
    owner->tagged_state_restored = 0u;
    owner->retirement_committed = 0u;
    eng->selected_app = (owner_idx == 0u) ? VOS_CP_APP_EDITOR : VOS_CP_APP_PAINTER;
    eng->target_app = VOS_CP_APP_NONE;
    return VOS_CP_OK;
}

int vos_cp_switch_with_cut(struct vos_cp_engine *eng, uint32_t target_app,
                           const struct vos_cp_roots *roots,
                           uint32_t grant_state,
                           uint32_t security_critical,
                           enum vos_cp_crash_cut cut)
{
    int rc = vos_cp_request_switch(eng, target_app);
    if (rc != VOS_CP_OK) {
        return rc;
    }
    if (cut == VOS_CP_CUT_AFTER_QUIESCE) {
        vos_cp_inject_crash(eng);
        return VOS_CP_OK;
    }
    rc = vos_cp_stage_current(eng, security_critical);
    if (rc != VOS_CP_OK) {
        return rc;
    }
    if (cut == VOS_CP_CUT_AFTER_STAGE_BEFORE_COMMIT) {
        vos_cp_inject_crash(eng);
        return VOS_CP_OK;
    }
    rc = vos_cp_commit_staged(eng);
    if (rc != VOS_CP_OK) {
        return rc;
    }
    if (cut == VOS_CP_CUT_AFTER_COMMIT_BEFORE_RELEASE) {
        vos_cp_inject_crash(eng);
        return VOS_CP_OK;
    }
    rc = vos_cp_release_slate(eng, roots);
    if (rc != VOS_CP_OK) {
        return rc;
    }
    if (cut == VOS_CP_CUT_AFTER_RELEASE_BEFORE_RESTORE) {
        vos_cp_inject_crash(eng);
        return VOS_CP_OK;
    }
    rc = vos_cp_begin_restore(eng, target_app);
    if (rc != VOS_CP_OK) {
        return rc;
    }
    if (cut == VOS_CP_CUT_DURING_RESTORE_BEFORE_FINISH) {
        vos_cp_inject_crash(eng);
        return VOS_CP_OK;
    }
    return vos_cp_finish_restore(eng, target_app, grant_state);
}

int vos_cp_lock_editor(struct vos_cp_engine *eng, const struct vos_cp_roots *roots,
                       uint32_t security_critical, enum vos_cp_crash_cut cut)
{
    if (eng == NULL || eng->selected_app != VOS_CP_APP_EDITOR ||
        eng->target_app != VOS_CP_APP_NONE ||
        eng->apps[0].phase != VOS_CP_PHASE_ACTIVE) {
        return VOS_CP_ERR_BAD_STATE;
    }
    if (eng->endurance_used >= eng->endurance_limit) {
        return VOS_CP_ERR_ENDURANCE_EXHAUSTED;
    }
    eng->apps[0].phase = VOS_CP_PHASE_QUIESCING;
    eng->target_app = VOS_CP_APP_PAINTER;
    if (cut == VOS_CP_CUT_AFTER_QUIESCE) {
        vos_cp_inject_crash(eng);
        return VOS_CP_OK;
    }
    int rc = vos_cp_stage_current(eng, security_critical);
    if (rc != VOS_CP_OK) {
        return rc;
    }
    if (cut == VOS_CP_CUT_AFTER_STAGE_BEFORE_COMMIT) {
        vos_cp_inject_crash(eng);
        return VOS_CP_OK;
    }
    rc = vos_cp_commit_staged(eng);
    if (rc != VOS_CP_OK) {
        return rc;
    }
    if (cut == VOS_CP_CUT_AFTER_COMMIT_BEFORE_RELEASE) {
        vos_cp_inject_crash(eng);
        return VOS_CP_OK;
    }
    rc = vos_cp_release_slate(eng, roots);
    if (rc != VOS_CP_OK) {
        return rc;
    }
    if (!vos_crypto_core_lock_domain(&eng->crypto, 0u)) {
        return VOS_CP_ERR_AUTH_FAILED;
    }
    vos_cp_editor_doc_init(&eng->editor_doc);
    eng->target_app = VOS_CP_APP_NONE;
    eng->locked = 1u;
    return VOS_CP_OK;
}

int vos_cp_unlock_editor(struct vos_cp_engine *eng, uint32_t grant_state,
                         const uint8_t *master_key, size_t master_key_len,
                         uint32_t *out_outcome)
{
    if (eng == NULL || out_outcome == NULL) {
        return VOS_CP_ERR_INVALID_ARG;
    }
    if (eng->apps[1].owns_slate != 0u) {
        return VOS_CP_ERR_DUAL_OWNERSHIP;
    }
    struct vos_cp_app_runtime *ed = &eng->apps[0];
    const struct vos_cp_durable_slot *slot = vos_cp_active_slot(eng, VOS_CP_APP_EDITOR);
    if (slot == NULL || slot->wire_len > eng->space_reserved) {
        ed->document_grant = 0u;
        ed->session_authority = 0u;
        ed->tagged_state_restored = 0u;
        eng->recovery_outcome = VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT;
        *out_outcome = VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT;
        return VOS_CP_ERR_INCOMPLETE_CHECKPOINT;
    }

    struct vos_cp_meta meta;
    struct vos_cp_editor_doc tmp_ed;
    const int drc = vos_cp_decode_editor(slot->wire, slot->wire_len, eng->auth_key,
                                         eng->confidentiality_label, &meta, &tmp_ed);
    if (drc != VOS_CP_OK) {
        ed->document_grant = 0u;
        ed->session_authority = 0u;
        ed->tagged_state_restored = 0u;
        eng->recovery_outcome = VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT;
        *out_outcome = VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT;
        return drc;
    }

    if (grant_state != VOS_CP_GRANT_VALID) {
        ed->document_grant = 0u;
        ed->session_authority = 0u;
        ed->tagged_state_restored = 0u;
        eng->recovery_outcome = VOS_CP_RECOVERY_GRANT_REFUSED;
        *out_outcome = VOS_CP_RECOVERY_GRANT_REFUSED;
        return VOS_CP_ERR_GRANT_REFUSED;
    }

    if (master_key == NULL ||
        !vos_crypto_core_unlock_domain(&eng->crypto, 0u, VOS_CP_DOMAIN_EDITOR, 1u,
                                       master_key, master_key_len)) {
        ed->document_grant = 0u;
        ed->session_authority = 0u;
        eng->recovery_outcome = VOS_CP_RECOVERY_GRANT_REFUSED;
        *out_outcome = VOS_CP_RECOVERY_GRANT_REFUSED;
        return VOS_CP_ERR_AUTH_FAILED;
    }

    const int frc = verify_slot_fresh_if_needed(eng, VOS_CP_APP_EDITOR, slot, &meta);
    if (frc != VOS_CP_OK) {
        ed->document_grant = 0u;
        ed->session_authority = 0u;
        eng->recovery_outcome = VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT;
        *out_outcome = VOS_CP_RECOVERY_INCOMPLETE_CHECKPOINT;
        return frc;
    }

    eng->editor_doc = tmp_ed;
    ed->phase = VOS_CP_PHASE_ACTIVE;
    ed->owns_slate = 1u;
    ed->document_grant = 1u;
    ed->session_authority = 0u; /* unlock never restores prior session */
    ed->tagged_state_restored = 0u;
    eng->selected_app = VOS_CP_APP_EDITOR;
    eng->target_app = VOS_CP_APP_NONE;
    eng->locked = 0u;
    eng->recovery_outcome = VOS_CP_RECOVERY_OK;
    *out_outcome = VOS_CP_RECOVERY_OK;
    return VOS_CP_OK;
}
