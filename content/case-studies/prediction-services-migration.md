---
title: "Migrating prediction services onto the delivery pipeline"
date: 2026-09-24
draft: false
tags: [data-delivery, platform]
summary: "A case study about supervising the migration of prediction services — such as a pricing forecast backend — onto a shared delivery pipeline, and making them robust."
---

## The frame

Prediction services — such as a pricing forecast backend — need data to make predictions, and they need it on a schedule and shape they can rely on. Over time, a service can drift: it builds its own bespoke data path, its own retrieval logic, its own error handling. Each service doing this separately means each one is maintained separately, and each one fails separately.

The frame for the work was consolidation. Prediction services should not each reinvent how they get data. They should sit on the shared delivery pipeline, the same one that serves every other consumer, and inherit its guarantees instead of re-implementing them.

## The approach

I helped supervise the migration of prediction services — with the pricing forecast backend as a prominent example — onto the delivery pipeline. The migration was not a lift-and-shift. Each service needed:

* **A defined data contract.** What the service receives, in what shape, on what schedule — made explicit rather than incidental.
* **Pipeline-native intake.** Replacing bespoke retrieval with the pipeline's filters, enrichments, and file handling, so the service consumes the same well-formed payloads as everyone else.
* **Robustness work.** The migration was the moment to make the services robust — handling partial data, retrying deterministically, failing loudly when inputs are missing, and recovering without operator intervention.

## Tradeoffs

Consolidating onto the pipeline has genuine costs:

* **Standardization versus specialization.** The pipeline serves many consumers, so its contract is general. A service with truly unusual needs may find the standard path constraining.
* **Migration risk versus status quo risk.** Moving a working service onto a new data path carries immediate risk — even when the long-term benefit is clear. Sequencing and rollback matter.
* **Shared guarantees versus shared incidents.** Inheriting the pipeline's reliability also means inheriting its incidents. Services need to be robust to pipeline behavior, not just to their own.
* **One-time cost versus recurring cost.** The migration is a concentrated effort; the payoff is recurring — no separate data path to maintain, no bespoke handling to debug.

## Outcome and learnings

The result was a set of prediction services sitting on one shared, robust delivery path — simpler to operate, and no longer owning bespoke data plumbing. The main learning was that a migration is a reliable way to force robustness work that would otherwise stay perpetually "next quarter". When a service moves onto the pipeline, it is the right moment to make its failure modes explicit and its recovery deterministic.