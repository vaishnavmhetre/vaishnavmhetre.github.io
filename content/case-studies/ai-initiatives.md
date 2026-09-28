---
title: "Foundations for AI-driven initiatives"
date: 2026-09-24
draft: false
tags: [platform, event-driven]
summary: "A case study about engineering the data and delivery foundations that AI-driven initiatives depend on — reusing the pipeline, not rebuilding bespoke paths."
hero: true
showtoc: true
diagrams: true
---

## The frame

AI-driven initiatives need the same thing every other data consumer needs: reliable, well-formed data, delivered on a schedule the model can depend on.

The temptation when a new initiative appears is to build it a bespoke data path — "this is special, it needs its own pipe". My view is the opposite. An AI initiative that needs training data, features, or inference inputs should sit on the same delivery pipeline as everything else, inheriting its filters, enrichments, file handling, and reliability guarantees.

The reason is not elegance. It is that the failure modes of a bespoke path stay invisible until they are expensive.

## What reuse actually buys

Reuse is not a slogan. It is a concrete set of commitments the AI consumer inherits, and that a bespoke path has to re-earn one at a time.

{{< diagram name="01-ai-pipeline" alt="Source systems feed a query and filter step, then enrichment, then pack and frame. That stage writes two payloads side by side: a production payload and a set of AI training inputs, which are stored in a model store." caption="One spine, two payloads. The AI path is a consumer of the shared pipeline, not a parallel build." >}}

A consumer sitting on that spine gets, without writing any of it:

- **Query pushdown.** The filter stage narrows data before enrichment runs, so the AI consumer never inherits a superset it has to discard.
- **Enrichment correctness.** Derived context — pricing, classification, measurement metadata — is computed once and identically for every consumer.
- **File-handling reliability.** Framing, checksums, retries, and partial-file semantics are solved once and tested once.
- **Observability.** Every delivery already reports what it produced, when, and whether it was complete.

A bespoke path gets none of these. It gets a second implementation of each, drifting independently.

## The data contract

The unit that makes this work is the delivery envelope. It is deliberately boring: an identifier, a schema reference, a window, and a content reference. The point is that a model-training consumer and a reporting consumer receive the *same* envelope, so "the AI data" is not a special object with its own semantics — it is a payload with a declared purpose.

```json {title="delivery-envelope.json"}
{
  "deliveryId": "d-2026-03-14-000417",
  "schema": "measurement.observation.v3",
  "window": {
    "from": "2026-03-14T00:00:00Z",
    "to": "2026-03-14T04:00:00Z"
  },
  "purpose": "training",
  "contentUri": "gs://delivery-artifacts/d-2026-03-14-000417/observations.bin",
  "recordCount": 184203,
  "complete": true
}
```

Two properties are doing the real work.

**`schema` is a versioned reference, not a copy of the data.** Consumers pin a version; the producer can add fields without silently changing what an existing consumer reads. That is what makes it safe for an AI consumer and a reporting consumer to share a producer.

**`complete` is explicit.** A truncated payload is a normal condition of failure, not an exceptional one. Because the envelope states it, a consumer can refuse to train on partial data instead of quietly learning from half a window. Most data-quality incidents I have seen come from a consumer that could not tell the difference.

## Deriving features from the same chain

The AI consumer's job is then ordinary pipeline work. Features come out of the same filter and enrichment stages that produce production payloads, so feature definitions and production definitions cannot silently diverge.

```go {title="feature-extraction.go"}{linenos=false}
func buildFeatures(rows []Observation) ([]FeatureRow, error) {
    out := make([]FeatureRow, 0, len(rows))
    for _, r := range rows {
        if !r.HasPrice || !r.HasClassification() {
            // Fail loudly rather than emit a row with silent defaults.
            return nil, fmt.Errorf("incomplete observation %s", r.ID)
        }
        out = append(out, FeatureRow{
            StoreID:   r.StoreID,
            WeekIndex: r.WeekIndex,
            PriceIdx:  Normalize(r.PriceIndex),
        })
    }
    return out, nil
}
```

The early return matters more than it looks. A pipeline that substitutes a default for missing data converts a data problem into a model problem, and the model problem is discovered weeks later with no obvious cause.

## Failure modes that compound

AI work makes data-quality problems worse than dashboards do, and the reason is worth being precise about.

- **A dashboard is read by a person who can notice something looks wrong.** A model does not notice. It fits the data it is given, including the part that arrived truncated, duplicated, or mis-enriched.
- **Errors compound through derived state.** If enrichment is wrong for one window, a feature built from it is wrong; the next feature built from *that* is wrong in a way no longer traceable to the original cause.
- **Retraining hides regressions.** A silently degraded input does not fail loudly; it produces a slightly worse model, and the regression gets attributed to the model rather than the pipeline.

This is the strongest practical argument for the shared spine. The pipeline already has the observability to catch a bad window, because a reporting consumer would have complained.

## What I'd do differently

- **Version the purpose, not just the schema.** `purpose: training` is useful, but a consumer that can be retrained on a changed schema needs the previous version to stay reproducible. I would keep both until the retrain window closes.
- **Make completeness checkable, not just declared.** `complete: true` is a promise. A checksum or a record-count reconciliation against the source would make it verifiable, and would let a consumer reject a payload without trusting the producer.
- **Write the failure test first.** For each AI consumer, the most valuable test is the one where the pipeline delivers a partial window. If nobody has run that, the consumer is not ready to be on the shared spine.
