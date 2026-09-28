---
title: "Foundations for AI-driven initiatives"
date: 2026-09-24
draft: false
tags: [platform, event-driven]
summary: "A case study about engineering the data and delivery foundations that AI-driven initiatives depend on — reusing the pipeline, not rebuilding bespoke paths."
---

## The frame

AI-driven initiatives need the same thing every other data consumer needs: reliable, well-formed data, delivered on a schedule the model can depend on. The temptation when a new initiative appears is to build it a bespoke data path — "this is special, it needs its own pipe". My view is the opposite. An AI initiative that needs training data, features, or inference inputs should sit on the same delivery pipeline as everything else, inheriting its filters, enrichments, file handling, and reliability guarantees.

## The approach

I now work on AI-driven initiatives, where the engineering contribution is largely about foundations: making sure the data those initiatives depend on is as robust as the data powering production retail measurement. That means:

* **Reusing the pipeline.** Features and training inputs come from the same delivery chain as production payloads — same contracts, same file handling, same guarantees — rather than parallel bespoke plumbing.
* **Making data dependable.** AI work compounds data-quality problems. Filtering, enrichment, and delivery have to be correct and observable, because a model silently learns from wrong data in a way a dashboard does not.
* **Building with the platform.** The configuration framework and file-handling service apply to AI payloads too. An initiative that reuses them inherits years of hardening instead of starting from zero.

## Tradeoffs

Foundations work has its own discipline:

* **Speed versus durability.** It is faster to hack a one-off intake for a pilot. It is more durable to route it through the pipeline. The right answer is usually both: pilot fast on the pipeline, not off it.
* **Generalization versus specificity.** A shared pipeline serves many consumers; an AI initiative may want unusual shapes. The pipeline should stretch for real needs and say no to accidental ones.
* **Platform work versus visible features.** Foundations are invisible until they fail. That makes them easy to under-invest in — and expensive to retrofit later.

## Outcome and learnings

The direction of travel is clear: AI-driven initiatives that inherit the pipeline's guarantees are cheaper to operate and safer to scale than ones that each build their own data path. The main learning is that data delivery is the substrate for everything else. Get the pipeline robust, and every consumer — human, service, or model — stands on the same solid ground.