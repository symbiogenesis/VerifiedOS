# Inference admission C core

GC-free C17 implementation of the inference descriptor codec, seven-term ceiling admission, finite Mixture-of-Experts residency and uniform work checks, and symbolic bank-grant token-rate derivation specified in [InferenceAdmission.v](../proofs/InferenceAdmission.v) and [service-authoring.md](../docs/implementation/contracts/service-authoring.md#3-inference-descriptor-and-admission).

## Scope

- **M6.6-i (Descriptor and ceiling admission):** [vos_inference_admission.h](include/vos_inference_admission.h) and [inference_admission.c](src/inference_admission.c) implement the fixed-width, least-significant-byte-first canonical shape descriptor encoder/decoder (`vos_inf_encode_shape`, `vos_inf_decode_shape`), enforcing exact schema byte length, per-field width bounds (`0..8` bytes), and refusal of truncated or trailing-byte inputs (`VOS_INF_DESCRIPTOR_NOT_CANONICAL`). `vos_inf_opening` and `vos_inf_composition_opening` enforce the seven-term ceiling (`vos_inf_why_refused` plus the symbolic bank grant), bounded session capacity without overcommit (`VOS_INF_SESSION_POOL_EXHAUSTED`), and exact server/session resource preservation on refusal.
- **M6.7-i (Residency, fixed `top_k` routing, and storage fence):** `vos_inf_all_experts_resident` checks the complete finite expert prefix `0..expert_count-1`, `vos_inf_routing_ok` checks exact `top_k` route length and expert index bounds, `vos_inf_checked_routed_work` computes constant per-token work independent of routed expert indices under uniform expert cost, and `vos_inf_serve` refuses nonresident expert fetches with `VOS_INF_ROUTED_FETCH_ACROSS_STORAGE`. `vos_inf_dispatch` refuses unqualified routes without implicit fallback.
- **M6.8-i (Bank-grant token rate and ensemble minimum):** `vos_inf_per_token_bytes` implements both `VOS_KV_WEIGHTS_ONLY` and `VOS_KV_WEIGHTS_AND_CACHE` traffic arms with overflow refusal, `vos_inf_admitted_rate` derives the integer quotient `grant / bytes_per_token` while refusing zero byte demand (`VOS_INF_PER_TOKEN_BYTES_NOT_DECLARED`), above-grant requests refuse with `VOS_INF_TOKEN_RATE_ABOVE_GRANT` without rate degradation, and `vos_inf_ensemble_rate` takes the minimum member rate rather than the sum.

## Validation

- Host and Linux differential checks plus compiled sanitizer and mutation controls live in [test_inference_admission_c.py](../tools/tests/test_inference_admission_c.py), built around [test_inference_admission.c](test/test_inference_admission.c).
- Target purecap compilation, physical KV placement qualification, kernel WCET bounds, and DSE hardware grants remain open at their owning milestones.
