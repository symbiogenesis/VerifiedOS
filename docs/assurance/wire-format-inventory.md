# Wire-format inventory

<!-- Generated from interfaces/wire-formats.json by vos.wire_formats.emit; do not edit. -->
<!-- Source SHA256: b65d80436f17b06155bbe959474521a057742156ffa46e93f8a109195b4ec482 -->

This is U-12's inventory of the attacker-facing format families the current design names, including crown-jewel row 10's member classes and row 3's IDL mapping. The authored source is [wire-formats.json](../../interfaces/wire-formats.json). A composition must specialize each open family into exact versions, subsets, byte/field/depth limits and descriptor identities before admitting it. The release's still-image, audio, container, font and document selections remain open; a family row does not choose a format or admit an implementation.

Every Narcissus descriptor is absent in this inventory. Existing hand-written Gallina codecs, abstract format conditions and generated ring encodings are identified separately. Their theorems do not establish a Narcissus derivation, copy-once implementation, verified lowering or descriptor-to-standard fidelity. No R-05-042 admission or crown-jewel completion follows from this document.

## Reading an entry

`none authored` means no hand-transcribed descriptor is present; it does not certify a future generator. `NAS grammar required` records R-05-050's explicit exception and its owed differential corpus. `reference codec only` marks hand-authored executable evidence that cannot be shipped as a substitute for the required derived parser. The owner is a work item or literal `none`; `none` is an unpriced descriptor obligation, not a waiver. U-14 selects either the pack manifest or immutable-module manifest as its first measured descriptor.

Canonicity means decode injectivity on the entire admissible byte language and re-encoding an accepted input unchanged, in addition to the correctness pair. Each identity-consuming site must name its descriptor and theorem under R-05-051a through R-05-051c. A role-gated entry must prove canonicity before signature, name, content-address, cache-key or equality use; recording the gate does not authorize that use. Differential tests do not discharge it.

## Member-class coverage

| Crown-jewel row 10 class | Inventory entries |
| --- | --- |
| `archive` | [Composition-selected archive formats](#archives) |
| `document` | [Composition-selected document formats](#documents) |
| `ensemble` | [Ensemble fixed-size message-block forms](#ensemble-frames) |
| `font` | [Composition-selected font formats](#fonts) |
| `image` | [Composition-selected still-image formats](#still-image) |
| `manifest` | [Typed pack and generation manifest](#pack-manifest) |
| `media` | [Composition-selected audio coding and containers](#audio), [Composition-selected video bitstream syntax](#video-syntax), [Composition-selected video containers](#video-container) |
| `mlme` | [802.11 MLME elements and security handshake framing](#wifi-mlme) |
| `module-certificate` | [Immutable-module proof-certificate transport](#module-certificate) |
| `module-endorsement` | [Immutable-module unit-key endorsement](#module-endorsement) |
| `module-manifest` | [Immutable-module design manifest](#module-manifest) |
| `module-message` | [Immutable-module identification, handshake, transfer and management records](#module-messages) |
| `nas` | [5G-core NAS IEI/TLV](#fiveg-nas) |
| `pack` | [Content-addressed pack header, flat object table and blob framing](#pack) |
| `rrc` | [NR RRC ASN.1 UPER and aligned-PER profiles](#nr-rrc) |
| `usb` | [USB enumeration, configuration, control and endpoint framing](#usb-enumeration), [USB device and cable authentication records](#usb-auth), [USB HID report descriptors and reports](#usb-hid), [Other admitted USB class grammars](#usb-class) |
| `x509` | [X.509 DER certificate](#x509-certificate), [TLS peer certificate-chain container](#x509-chain) |

## Format entries

### NR RRC ASN.1 UPER and aligned-PER profiles <a id="nr-rrc"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: The verified ASN.1-to-Narcissus front end and published-module instantiation are absent. NAS is separately inventoried as IEI/TLV, not ASN.1.
- Requirements: R-05-042, R-05-048, R-18-029.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### 5G-core NAS IEI/TLV <a id="fiveg-nas"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **NAS grammar required**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: The exceptional hand-transcribed grammar and its four-reference differential corpus are both absent.
- Requirements: R-05-050, R-18-029.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### 802.11 MLME elements and security handshake framing <a id="wifi-mlme"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-05-042, R-12-040, R-12-043b.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### NR MAC, RLC and PDCP framing <a id="cellular-lower"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-039, R-12-040.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### 802.11 data framing <a id="wifi-data"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-039, R-12-040.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Bluetooth link, L2CAP, GATT and pairing records <a id="bluetooth"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-039, R-12-040, R-12-043b.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### GNSS receive navigation-message framing <a id="gnss"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: The receive-only service is named; its message profile, parser and bounded grammar remain unselected.
- Requirements: R-12-038, R-05-042.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### IMS session and voice-transport grammars <a id="ims"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: Ordinary and emergency voice require these grammars. Session signalling, media transport and codec subsets remain to be fixed; no IMS parser is credited.
- Requirements: R-12-041, R-18-004a.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### eUICC APDU and TPDU records <a id="euicc"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-047.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### USB enumeration, configuration, control and endpoint framing <a id="usb-enumeration"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-058, R-12-060, R-05-042.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### USB device and cable authentication records <a id="usb-auth"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-061.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### USB HID report descriptors and reports <a id="usb-hid"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-063.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Other admitted USB class grammars <a id="usb-class"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: The per-device composition must enumerate each admitted class and profile before admission. No generic class parser or tunnelling grammar is admitted.
- Requirements: R-12-058, R-12-062.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Bounded EDID and display metadata <a id="edid"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: The composition-fixed block cap and fixed-size static mastering metadata are specified; no descriptor is authored.
- Requirements: R-15-234, R-15-236d.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Ethernet framing and IPv6 network/control packets <a id="network-link"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: The admitted link, IPv6 extension-header and control-message subsets need bounded profiles; no descriptor is authored.
- Requirements: R-12-031, R-12-034.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### TCP and UDP transport framing <a id="network-transport"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-031, R-12-033.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### TLS 1.3 record and handshake messages <a id="tls"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-031, R-12-032.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### X.509 DER certificate <a id="x509-certificate"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: DER syntax, signed certificate bytes and bounded certificate policy inputs need their own descriptor. Chain-validation policy is separate crown-jewel row 30.
- Requirements: R-12-032a, R-05-051a.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### TLS peer certificate-chain container <a id="x509-chain"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: The bounded chain container and its certificate descriptor are separate from path validation, which supplies no parser theorem.
- Requirements: R-12-032a.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### WireGuard-style tunnel handshake and packet records <a id="tunnel"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-031.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### DNS-over-TLS request and response grammar <a id="dns"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: The TLS envelope does not discharge the DNS grammar, name interpretation or canonical cache-key obligation.
- Requirements: R-12-031, R-12-033.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Roughtime request, response and signed time records <a id="roughtime"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-031, R-12-035.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### NTS key-establishment and authenticated time records <a id="nts"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-035, R-12-037.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Secure PTP messages and authentication TLVs <a id="ptp"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: Time-receiver-only profile is specified; management and reconfiguration messages are refused.
- Requirements: R-12-037.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Package-fetch and hosted-content transport messages <a id="fetch"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: The transport application profiles remain to be selected. TLS and pack parsing do not cover a future fetch or hosted-content envelope.
- Requirements: R-12-032a, R-14-008.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Composition-selected still-image formats <a id="still-image"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required for content addressing and deterministic reuse keys; the admitted content profile must pin the canonical subset or refuse that identity role. No descriptor theorem exists.
- Current evidence: No concrete still-image format/version has been selected by the release demonstration set; that selection must create one descriptor entry per admitted grammar.
- Requirements: R-12-024f, R-18-004a.
- Sources: [requirements-register.md](../../docs/requirements-register.md), [HandlerGraph.v](../../proofs/HandlerGraph.v).

### Composition-selected audio coding and containers <a id="audio"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required for content addressing and deterministic reuse keys; the admitted content profile must pin the canonical subset or refuse that identity role. No descriptor theorem exists.
- Current evidence: Opus and AAC are algorithm/porting examples, not admitted parser profiles. The selected audio grammar and container need independent entries.
- Requirements: R-12-024f, R-18-004a.
- Sources: [requirements-register.md](../../docs/requirements-register.md), [userspace-porting.md](../../docs/implementation/userspace-porting.md).

### Composition-selected video bitstream syntax <a id="video-syntax"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required for content addressing and deterministic reuse keys; the admitted content profile must pin the canonical subset or refuse that identity role. No descriptor theorem exists.
- Current evidence: The AV1 reference lineage is an algorithm and conformance starting point. Entropy arithmetic and RVV reconstruction do not supply its syntax descriptor.
- Requirements: R-12-084a, R-15-238a.
- Sources: [requirements-register.md](../../docs/requirements-register.md), [userspace-porting.md](../../docs/implementation/userspace-porting.md).

### Composition-selected video containers <a id="video-container"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required for content addressing and deterministic reuse keys; the admitted content profile must pin the canonical subset or refuse that identity role. No descriptor theorem exists.
- Current evidence: The release container selection is open; a verified elementary syntax layer does not supply container parsing.
- Requirements: R-12-024f, R-18-004a.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Composition-selected font formats <a id="fonts"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required for content addressing and deterministic reuse keys; the admitted content profile must pin the canonical subset or refuse that identity role. No descriptor theorem exists.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-024f, R-18-004a.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Composition-selected archive formats <a id="archives"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required for content addressing and deterministic reuse keys; the admitted content profile must pin the canonical subset or refuse that identity role. No descriptor theorem exists.
- Current evidence: Archive metadata, entry names, bounds and any compression framing require selected profiles; no concrete archive grammar is admitted.
- Requirements: R-12-024f.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Composition-selected document formats <a id="documents"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required for content addressing and deterministic reuse keys; the admitted content profile must pin the canonical subset or refuse that identity role. No descriptor theorem exists.
- Current evidence: No descriptor, codec or correctness pair is authored.
- Requirements: R-12-024f, R-18-004a.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Typed IDL wire mapping and ring records <a id="idl-mapping"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: The IDL profile specifies the mapping. RingContract is generated encoding/contract evidence for ring members and K-99 checks those tables; it is not a Narcissus descriptor or whole-profile synthesis proof.
- Requirements: R-12-010, R-12-012, R-12-013.
- Sources: [idl-profile.md](../../docs/languages/idl-profile.md), [RingContract.v:descriptor](../../proofs/RingContract.v), [RingContract.v:completion](../../proofs/RingContract.v), [ring-reference.json](../../interfaces/ring-reference.json).

### Signed handler graph, typed metadata and reuse parameters <a id="handler-graph"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: HandlerGraph states abstract admitted-format and verified-parser flags; it neither defines nor verifies their byte grammars.
- Requirements: R-12-024b, R-12-024d, R-12-024f.
- Sources: [HandlerGraph.v](../../proofs/HandlerGraph.v).

### Content-addressed pack header, flat object table and blob framing <a id="pack"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: The bounded layout is specified; the object hashes do not replace the pack framing descriptor.
- Requirements: R-13-009, R-05-051a.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Typed pack and generation manifest <a id="pack-manifest"></a>

- Descriptor: **absent**. Owner: **U-14**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: Candidate for U-14, which selects one first descriptor and measures its cost. No choice or descriptor is credited here.
- Requirements: R-13-003, R-13-009.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Typed content-addressed objects and storage integrity metadata <a id="store-objects"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: Store object headers, typed metadata, Merkle-DAG and integrity records need bounded descriptors per admitted object kind. A raw blob has no semantic fields until a consumer interprets it.
- Requirements: R-10-005a, R-12-024d, R-05-051c.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Public-log checkpoints, inclusion and consistency evidence <a id="witness-records"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: The fixed-layout evidence rides inside the pack; outer pack verification supplies no inner evidence grammar.
- Requirements: R-13-023b, R-13-023c.
- Sources: [requirements-register.md](../../docs/requirements-register.md), [WitnessContinuity.v](../../proofs/WitnessContinuity.v).

### Attestation quotes, reference manifests and sealed-blob envelopes <a id="attestation"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: AttestedSession and CredentialHandles model symbolic identity and session operations, not wire descriptors.
- Requirements: R-12-014, R-12-015, R-12-015c.
- Sources: [requirements-register.md](../../docs/requirements-register.md), [AttestedSession.v](../../proofs/AttestedSession.v), [CredentialHandles.v](../../proofs/CredentialHandles.v).

### Signed boot configuration and devicetree <a id="boot-config"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: Typed signed objects replace trusted runtime text. Their byte formats need descriptors even when a separate schema or semantic contract exists.
- Requirements: R-10-029, R-15-198.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Signed calibration manifest <a id="calibration"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: The calibration schema is owned by U-07; its hardware validity and signed-envelope consumers remain separate from the absent Narcissus descriptor and canonical byte codec.
- Requirements: R-15-127, R-17-062, R-05-042, R-05-051a.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Admission proof, TAL derivation and certificate envelopes <a id="proof-transport"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: A proof kernel checking an admitted term does not verify the outer byte parser, length accounting or any target certificate envelope.
- Requirements: R-13-001, R-13-003, R-06-015a.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Packaged WebAssembly binary <a id="wasm"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Role-gated: a theorem is owed before any identity-consuming use; the profile must enumerate those sites and refuse the role without the theorem.
- Current evidence: The binary parser remains open independently of selected Wasm semantics and interpreter refinement; no descriptor is credited by WasmCert selection.
- Requirements: R-14-013b, R-05-042.
- Sources: [unassigned-proof-map.md](../../docs/assurance/unassigned-proof-map.md).

### Inference model shape descriptor <a id="inference-shape"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **reference codec only**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: InferenceAdmission has a hand-authored fixed-width schema codec with round-trip and injectivity theorems. Narcissus derivation and its correspondence to this codec remain absent.
- Requirements: R-12-085, R-05-051a.
- Sources: [InferenceAdmission.v:encode_shape](../../proofs/InferenceAdmission.v), [InferenceAdmission.v:decode_shape](../../proofs/InferenceAdmission.v), [InferenceAdmission.v:the_shape_descriptor_re_encodes_its_bytes](../../proofs/InferenceAdmission.v), [InferenceAdmission.v:the_shape_descriptor_decode_is_injective](../../proofs/InferenceAdmission.v).

### Inference model tensors, tokenizer and graph data <a id="inference-data"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required for content addressing and deterministic reuse keys; the admitted content profile must pin the canonical subset or refuse that identity role. No descriptor theorem exists.
- Current evidence: Opaque weights are data; each interpreted tensor, quantization, tokenizer or graph container needs its own bounded grammar. A shape theorem does not parse those bytes.
- Requirements: R-12-085, R-12-085g.
- Sources: [requirements-register.md](../../docs/requirements-register.md).

### Immutable-module design manifest <a id="module-manifest"></a>

- Descriptor: **absent**. Owner: **U-14**.
- Hand transcription: **reference codec only**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: ModuleFormats carries a hand-authored minimal-numeral codec with both round trips and canonicity. Its bounds are parameters and its identities opaque numerals. U-14 may choose this first descriptor; no Narcissus correspondence is present.
- Requirements: R-12-085g, R-05-051a.
- Sources: [ModuleFormats.v:manifest_parse_of_serialize](../../proofs/ModuleFormats.v), [ModuleFormats.v:manifest_serialize_of_parse](../../proofs/ModuleFormats.v), [ModuleFormats.v:manifest_has_one_admissible_encoding](../../proofs/ModuleFormats.v), [immutable-module-contract.md](../../docs/hardware/immutable-module-contract.md).

### Immutable-module proof-certificate transport <a id="module-certificate"></a>

- Descriptor: **absent**. Owner: **Q24c**.
- Hand transcription: **reference codec only**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: ModuleFormats carries the bounded hand-authored certificate codec and canonicity theorem. Evidence bytes are opaque; no executable proof checker, Narcissus parser or circuit admission is established.
- Requirements: R-12-085g, R-12-085h, R-06-015a.
- Sources: [ModuleFormats.v:certificate_parse_of_serialize](../../proofs/ModuleFormats.v), [ModuleFormats.v:certificate_serialize_of_parse](../../proofs/ModuleFormats.v), [ModuleFormats.v:certificate_has_one_admissible_encoding](../../proofs/ModuleFormats.v).

### Immutable-module unit-key endorsement <a id="module-endorsement"></a>

- Descriptor: **absent**. Owner: **Q24c**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: Q24c states the unit/design binding; symbolic endorsements are not a byte descriptor.
- Requirements: R-12-085g, R-12-085i.
- Sources: [ModuleAdmission.v](../../proofs/ModuleAdmission.v), [immutable-module-contract.md](../../docs/hardware/immutable-module-contract.md).

### Immutable-module identification, handshake, transfer and management records <a id="module-messages"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: Q24a specifies the grammar and frame bounds; no operation has a Narcissus descriptor. Public pre-session padding is the fixed constant in the slot contract, not an authority-bearing message.
- Requirements: R-12-085g, R-15-228f, R-15-228g.
- Sources: [immutable-module-contract.md](../../docs/hardware/immutable-module-contract.md).
- Forms generated from the owning grammar: `ID-RECORD`, `HS-INIT`, `HS-REPLY`, `INF-OPEN`, `INF-INPUT`, `INF-DRAW`, `INF-ABORT`, `INF-OUTPUT`, `INF-END`, `MGMT-QUIESCE`, `MGMT-QUIESCE-END`, `MGMT-SCRUB`, `MGMT-SCRUB-END`, `IDLE`.

### Ensemble fixed-size message-block forms <a id="ensemble-frames"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: Q23b specifies field order, admissible lengths and no-slack obligations for each form. The descriptor is over decoded message blocks, not error-correction symbols. No form has a Narcissus descriptor or canonicity theorem.
- Requirements: R-15-228e, R-12-015d.
- Sources: [ensemble-link-contract.md](../../docs/hardware/ensemble-link-contract.md).
- Forms generated from the owning grammar: `FF-1`, `FF-2`, `FF-3`, `FF-4`.

### Deterministic-replay event and nondeterminism records <a id="replay"></a>

- Descriptor: **absent**. Owner: **none**.
- Hand transcription: **none authored**.
- Canonicity: Required: identity, signature, hash or equality consumers require a whole-language theorem against the eventual Narcissus descriptor; none is present.
- Current evidence: The replay instrument has bounded host fixtures and private/public event distinctions; production public schemas, sealing and target parser correspondence remain open.
- Requirements: R-16-016, R-16-017, R-05-042.
- Sources: [requirements-register.md](../../docs/requirements-register.md), [replay_record.py](../../tools/vos/replay_record.py).

## Validation and the proposed descriptor rule

K-88 can regenerate this view with `vos.wire_formats.emit`. The source reader refuses a missing member class or owner, unknown requirement, duplicate ID, missing reference symbol, changed reviewed row-10 membership, absent or duplicated grammar table, and any attempt to promote an absent descriptor. Module operations and ensemble forms are read from their contracts, so adding a form changes this view. Schema 1 scans every `proofs/**/*.v` source after stripping comments and refuses Narcissus, CorrectDecoder or CorrectEncoder use until explicit descriptor bindings are introduced. This conservative source check neither parses Rocq dependency aliases nor verifies a theorem.

**Proposed rule, K-id owed:** when U-13 fixes the library/import identity and U-14 authors the first descriptor, register one manifest record per actual descriptor: inventory ID, proof path, fully qualified format constant, CorrectDecoder and CorrectEncoder proposition constants, canonicity constant or an explicit prohibition on identity roles, derivation inputs, hand-transcription flag, owner and review record. The rule must compare the inventory-to-manifest and manifest-to-compiled-symbol directions over the complete proof gate source and dependency closure. Missing, duplicate, unknown, orphaned or extra descriptors fail; each constant must resolve to the named descriptor's audited proposition in a fresh proof receipt. An empty set succeeds only with the explicit absent status and no descriptor-producing module. A declaration annotation alone never establishes Narcissus derivation or semantic correspondence. Mutants must drop each direction, substitute a reference codec, remove canonicity from an identity use, and add an unlisted descriptor. Add the checker registry row and mutation case with the allocated ID; U-12 proposes this contract and does not install that future proof-aware rule.

## Remaining foundation dependencies

U-13 owes Narcissus's pinned Rocq compatibility, assumptions and licence disposition. U-14 owes the first real descriptor, correctness pair, whole-language canonicity and measured cost. Every subsequent descriptor needs its own priced owner, bounded profile and independent R-05-150 review. RRC also needs R-18-029's verified ASN.1 front end; NAS needs its four-reference differential corpus. Q2b owns target lowering evidence. Q23b's frame contract and Q24a's module grammar supply statements, while Q23c/Q24c supply session and admission consumers. Their existing symbolic models and reference codecs close none of the missing descriptor or lowering obligations.

The inventory excludes declined grammars: 2G/3G/4G cellular state machines (R-12-041), USB tunnelling and general vendor messages (R-12-062), and runtime trusted text configuration (R-10-029). Raw bounded samples, ciphertext blocks and arithmetic codewords are not promoted to semantic parsers; their typed framing and metadata remain covered above. Build-host differential oracles remain outside the shipped-parser inventory.
