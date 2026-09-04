# Retained technical discovery sources

This registry records external technical sources retained for learning and architectural reconnaissance. Retention means **KEEP for investigation/reference value**, not authority, installation approval, operational adoption, or permission to execute downloaded code or models.

Canonical rule:

```text
useful recurring source != authority
interesting project != adopted runtime
upstream benchmark != independently verified fact
local-first != automatically safe
```

Each future item from a retained source still requires its own triage and KEEP/DISCARD decision.

## FareedKhan-dev / `kimi-k3-in-c`

**Decision:** KEEP — project + candidate technical discovery feed.

Retained project: `FareedKhan-dev/kimi-k3-in-c`.

The durable learning value is the systems pattern rather than the headline scale claim. Concepts worth retaining include:

- separating resident working memory from total model capacity;
- out-of-core inference using local storage;
- selective activation in Mixture-of-Experts architectures;
- quantized expert storage and streaming;
- explicit memory-versus-throughput trade-offs;
- local-first execution without a mandatory hosted inference service;
- small, inspectable systems implementations;
- deterministic validation and measurement artifacts where upstream provides them.

Retained principle:

> RAM is not the only capacity boundary: storage bandwidth, selective activation, quantization and controlled residency can trade memory pressure for latency while preserving the declared model semantics.

Claims such as checkpoint size, peak RSS, throughput, exact-output behavior and supported hardware remain **upstream evidence** until independently reproduced or cross-checked. This KEEP does not approve downloading large checkpoints, introducing credentials, running unreviewed scripts on a primary workstation, or integrating the project into GiadaWare/LAB environments.

Any future hands-on PoV must begin isolated and minimally, preferably with weightless/local validation before large downloads.

## Qwen3.5 Small family

**Decision:** KEEP — local-first model-family candidate + learning/reference source.

Retained candidate sizes from the discovery record:

- 0.8B;
- 2B;
- 4B;
- 9B.

The primary constrained-hardware candidates are 0.8B, 2B and 4B. The 9B variant remains separately bounded and must not inherit memory-fit assumptions from smaller variants.

Retained principle:

> Small local models should be evaluated as a capability trade-off across model size, quantization, RAM, storage, latency, task quality and privacy boundary — not by parameter count alone.

Any resource, benchmark or quality statement is configuration-specific: runtime, quantization, hardware and exact artifact provenance are part of the evidence. A local model is not automatically trusted merely because inference can occur offline.

Before hands-on use, verify model identity, publisher/source, license, weight provenance, quantization source, runtime/dependency provenance, network behavior, telemetry, cache/persistence behavior and any attached tool authority. First PoVs must use public or synthetic data and must not connect the model to private repositories, personal documents, Gmail/Drive, secrets or privileged agent workflows.

Operational promotion requires a concrete narrow use case with acceptable measured resource use and task utility. This KEEP alone does not approve installation or integration.

## Salvatore Sanfilippo / `antirez` — DwarfStar / `ds4`

**Decision:** KEEP — local-inference architecture + candidate technical discovery feed.

The retained value is the architectural pattern of a deliberately narrow inference engine optimized for a constrained set of models/workloads instead of a universal runtime.

Retained principles:

> Specializing a runtime for a small number of models and workloads can improve efficiency, observability, validation and operational control compared with a generic inference layer.

> Local-first inference is valuable when the privacy/control benefit justifies hardware, storage and operational cost.

Questions worth retaining for future study include:

- narrow engine versus generic runtime;
- model-specific optimization;
- quantization and memory residency;
- persistent or disk-backed inference state;
- long-context resource management;
- local API exposure to agents without mandatory hosted inference;
- privacy/control versus hardware-cost trade-offs;
- explicit supported-model and failure contracts.

Supported-model lists, benchmark figures, memory requirements and implementation details remain upstream claims until rechecked or reproduced. Any future PoV must verify license, model-weight provenance, dependencies, network/telemetry behavior, API bind/authentication defaults, persistence paths and attached-agent authority before use with sensitive material.

Retention of `antirez` as a discovery feed does not make author reputation an authority and does not make future items automatic KEEP decisions.

## Relationship among the retained examples

The three records cover distinct local-inference strategies:

```text
kimi-k3-in-c  -> enormous capacity + out-of-core/storage streaming
Qwen3.5 Small -> genuinely smaller models + reduced resource envelope
DwarfStar     -> narrow model-specific runtime + controlled execution surface
```

They are retained as comparative learning evidence. None is selected here as the GiadaWare AI runtime or as an approved dependency.
