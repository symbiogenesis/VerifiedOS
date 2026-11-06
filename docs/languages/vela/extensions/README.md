# Vela extension designs

These non-normative documents design Vela extensions and policy proposals
outside the [first supported release](../first-release.md#release-boundary).
Each is consumer-gated: selecting one requires a named client, a comparison with
the supported subset, a bounded implementation and qualification budget and a
decision predicate, as the release boundary states. None of them supplies an
implementation, a release obligation or a VerifiedOS guarantee. The
[first-release contract](../first-release.md) and [core design](../core-design.md)
define the release without them.

| Document | Extension it designs |
| --- | --- |
| [Graded foundation](graded-foundation.md) | User-defined grade domains, type-use accounting and the graded-extension selection protocol |
| [Handlers and async lifecycles](handlers-async.md) | Effect handlers, one-shot and multi-shot control, async tasks, structured scopes and cancellation |
| [Interior mutability](interior-mutability.md) | Cells, snapshots, invariant opening and lifting, and local aliases |
| [Metaprogramming](metaprogramming.md) | Typed introspection, derivation, hygienic generation and compiler services |
| [Unified source contract](unified-source-contract.md) | One Vela codebase for software, proofs, the machine model and hardware, and native self-hosting |
| [Assurance profiles](assurance-profiles.md) | Proposed Safe, Contracted and Complete presets and evidence presentation beside declarations |
| [Composition review](full-language-review.md) | How the extensions compose and which owner decides each frontend row |

[PLAN.md](../../../../PLAN.md#vela-first-release-delivery) owns commissioning and
budgets for any extension a consumer selects.
