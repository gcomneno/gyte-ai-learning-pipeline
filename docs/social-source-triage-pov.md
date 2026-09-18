# Social-source triage manual Proof of Value

## Purpose

This record completes the manual Proof of Value required by issue #27 before any social-platform ingestion automation is considered.

The sample contains **12 real discovery items**. Four were already present in the GYTE issue history; eight additional public social/community items were manually captured for this PoV. No scraper or platform integration was introduced.

The PoV records only URLs, concise derived observations, source-resolution references and triage decisions. It does not copy posts, images, infographics, videos or private material.

Canonical rule:

```text
social discovery signal != authoritative source
candidate skill != verified skill material
promotion != source authority
```

## Decision vocabulary

- **PROMOTED** — the durable principle is materially supported by stronger/original evidence and is worth entering a normal learning-source workflow.
- **CANDIDATE** — useful principle identified, but verification is incomplete or the learning value is not yet strong enough for promotion.
- **DISCARDED** — framing is too speculative, promotional, redundant, shallow, or insufficiently resolvable to justify more work.

A promoted item retains its discovery URL in provenance. The stronger source, not the social item, carries the verification weight.

## Sample

| # | Discovery item | Extracted durable principle | Resolution / verification | Decision |
|---|---|---|---|---|
| 1 | Facebook / Source Code.dev — “20 ChatGPT Prompts for Brainstorming” — https://www.facebook.com/share/1DQYVVAPB7/ | Structured brainstorming techniques are more durable than model-specific prompt recipes; an LLM is optional assistance. | Techniques named in the capture are independently established methods; the social infographic is not needed as authority. | **PROMOTED** |
| 2 | Social discovery → `FareedKhan-dev/kimi-k3-in-c` — https://github.com/FareedKhan-dev/kimi-k3-in-c | Capacity is not identical to resident RAM: out-of-core storage, quantization and selective activation trade memory for latency. | Upstream project is the stronger technical source; exact performance claims remain upstream evidence until reproduced. | **PROMOTED** |
| 3 | Social discovery → Qwen3.5 Small family — https://huggingface.co/Qwen/Qwen3.5-9B | Local-model suitability is a workload × model × quantization × hardware × latency trade-off, not a parameter-count slogan. | Official Qwen model artifacts confirm the family/model identity; memory/quality claims remain configuration-specific. | **PROMOTED** |
| 4 | Social discovery → DwarfStar / ds4 — https://github.com/antirez/ds4 | A deliberately narrow runtime can trade universality for explicit model support, integration testing and controlled resource assumptions. | Canonical upstream repository explicitly describes a self-contained, deliberately narrow engine and its supported hardware/models. | **PROMOTED** |
| 5 | Reddit r/LocalLLaMA — Cohere unreleased coding model early access — https://www.reddit.com/r/LocalLLaMA/comments/1tylzy2/coheres_unreleased_coding_model_early_access_for/ | Early community announcements are discovery evidence; model identity, license and architecture should be resolved to publisher artifacts before use. | Cohere later published North Mini Code as 30B total / 3B active, Apache-2.0: https://cohere.com/blog/north-mini-code | **PROMOTED** |
| 6 | Reddit r/LocalLLaMA — “Local models went from mostly useless to actually useful really fast” — https://www.reddit.com/r/LocalLLaMA/comments/1u85t9c/local_models_went_from_mostly_useless_to_actually/ | “Useful locally” is workload- and hardware-specific; community experience can identify evaluation axes but cannot establish universal capability. | Thread contains heterogeneous experiences rather than one falsifiable source claim. Use it to derive evaluation dimensions, not a capability conclusion. | **CANDIDATE** |
| 7 | Reddit r/LocalLLaMA — “massive open weight drops” — https://www.reddit.com/r/LocalLLaMA/comments/1uylutc/anyone_else_completely_tuning_out_these_massive/ | Open weights and practical local executability are different properties; hardware/resource envelope belongs in the capability contract. | Model size/resource claims must be resolved per model card/runtime; the principle is consistent with the already retained Qwen/DwarfStar resource-boundary work. | **PROMOTED** |
| 8 | Reddit r/LocalLLaMA — memory/performance findings compilation — https://www.reddit.com/r/LocalLLaMA/comments/1s9tojo/compilation_of_recent_findings_which_could_save/ | Quantization, KV-cache reduction and speculative decoding are distinct optimization levers and should be evaluated separately. | Example APEX technical source: https://github.com/localai-org/apex-quant/blob/main/paper/APEX_Technical_Report.md ; individual techniques still require their own primary-source resolution. | **CANDIDATE** |
| 9 | Reddit r/aiagents — “my agent skills stack in 2026” — https://www.reddit.com/r/aiagents/comments/1w12382/my_agent_skills_stack_in_2026/ | A list of installable agent skills is discovery metadata, not evidence that a skill is safe, correct, or authorized; inspect source and permissions before adoption. | Named repositories can be inspected individually; popularity/install convenience does not establish authority. This reinforces the #28 host-authorization boundary. | **PROMOTED** |
| 10 | Reddit r/AI_Agents — “5 agent skills I'd install...” — https://www.reddit.com/r/AI_Agents/comments/1roe8k8/5_agent_skills_id_install_before_starting_any_new/ | Agent-skill packaging can make reusable operational knowledge discoverable, but installation recommendations must not substitute for provenance, scope and validation review. | The post points to identifiable upstream skill repositories; each remains independently reviewable. No blanket install decision is retained. | **PROMOTED** |
| 11 | Hacker News — “A site for stopping work slop” — https://news.ycombinator.com/item?id=47813403 | Quality principles and review criteria are more durable than prompt recipes, but “slop” is an evaluative label rather than a technical specification. | The item is primarily opinion/heuristic; no stronger source is needed unless a concrete quality metric is proposed. | **CANDIDATE** |
| 12 | Reddit r/LocalLLaMA — “Is 2026 the Year Local AI Becomes the Default?” — https://www.reddit.com/r/LocalLLaMA/comments/1re5qdy/is_2026_the_year_local_ai_becomes_the_default_not/ | “Local AI will become the default” is a broad prediction; useful subclaims must be decomposed into concrete hardware, privacy, latency and workload questions. | The headline cannot be promoted as knowledge. Concrete model/resource claims require independent model/runtime evidence. | **DISCARDED** |

## Detailed observations

### 1. Brainstorming infographic

The first issue example behaves exactly as expected. The social artifact is useful because it surfaces a cluster of techniques. Its durable value is not the wording of twenty prompts.

Derived candidate skill:

> select a brainstorming/problem-solving technique based on the problem shape, then use an LLM only as optional facilitation.

The infographic remains low-authority discovery provenance. **PROMOTED as a candidate skill source, not as authority.**

### 2–4. Existing retained technical discoveries

Issues #29, #30 and #31 demonstrate three different successful resolutions:

- social framing → inspectable upstream implementation;
- social model claim → publisher/model artifact;
- social runtime claim → canonical upstream architecture.

All three preserved a useful principle while refusing to promote benchmark or hardware claims beyond their evidence.

### 5. Early-access model announcement

The Reddit item was useful before release because it exposed a concrete candidate. The later publisher release resolved the important stable facts: product identity, MoE shape and license.

Lesson:

```text
community early access -> candidate
publisher artifact      -> stronger source
hands-on qualification  -> separate evidence
```

### 6–8. Local-inference discussion

Community threads are especially useful for discovering **evaluation axes**:

- resident memory;
- storage;
- quantization;
- context/KV cache;
- throughput/latency;
- workload fit;
- hardware cost.

They are poor authority for universal claims such as “local models are now useful” or “technique X saves enough memory”. Promotion therefore attaches to the durable evaluation principle, not to a thread consensus.

### 9–10. Agent-skill recommendation posts

Both posts demonstrate a recurring social pattern: convenient install lists compress provenance, scope, permission and validation questions into a recommendation.

The extracted skill is not “install these packages”. It is:

> triage an agent skill as executable/operational supply-chain input: resolve upstream identity, inspect scope and authority, validate usefulness, then decide adoption.

This is consistent with issue #28: an agent-facing skill artifact never grants host permissions merely by describing actions.

### 11. AI “slop” discussion

The item usefully reinforces principle-over-prompt thinking, but its central label is subjective and does not yet define a stable technical capability. It remains a candidate observation rather than a promoted learning source.

### 12. “Local AI default” prediction

The broad forecast is not needed. The useful components—privacy, latency, hardware fit, specialized models and local/cloud trade-offs—already have stronger, testable formulations elsewhere. The headline is therefore discarded rather than preserved as knowledge.

## PoV results

### What recurred

Across the 12 items, the stable reusable structure was:

1. capture a URL/reference;
2. record a concise observed idea;
3. extract a principle without copying the post;
4. classify discovery authority separately from idea quality;
5. resolve to primary/publisher/upstream evidence where possible;
6. mark unsupported claims explicitly;
7. decide PROMOTED/CANDIDATE/DISCARDED;
8. retain discovery provenance without upgrading it to authority.

This is stable enough to justify a small structured triage record.

### What did not recur reliably

The sample does **not** justify a common ingestion schema for:

- likes/upvotes/views;
- creator follower counts;
- media download;
- captions;
- image OCR;
- platform-specific engagement metadata;
- automatic author reputation;
- automatic truth scores.

Those fields are unnecessary for the durable decision.

### Automation decision

**Do not approve automated social-platform ingestion.**

The PoV demonstrates recurring semantic triage, but acquisition is heterogeneous and platform-dependent. URL-only capture plus user-supplied concise observation is sufficient for the demonstrated workflow.

A future automation issue is justified only for the platform-independent record/triage mechanics, not for scraping Facebook, Instagram, Reddit, Hacker News or other platforms.

Potential deterministic automation:

- candidate-record schema validation;
- state-transition validation;
- URL/provenance presence;
- duplicate capture detection;
- requirement that PROMOTED records contain at least one stronger-source reference or an explicit verification rationale.

Human authority remains mandatory for:

- principle extraction;
- deciding whether the idea is worth learning;
- source-quality judgment;
- verification interpretation;
- PROMOTED/DISCARDED decision.

AI assistance, if added later, remains advisory and cannot promote a candidate.

## Conclusion

The manual PoV supports the issue #27 contract and narrows the useful automation boundary:

```text
manual/url capture
  -> structured triage record
  -> human principle extraction
  -> source resolution
  -> human promotion decision
  -> normal GYTE evidence/review workflow
```

The evidence does **not** support social scraping or automatic promotion.
