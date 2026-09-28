---
title: "Binary data delivery for retail measurement"
date: 2026-09-24
draft: false
tags: [data-delivery, gcp]
summary: "A case study about querying retail measurement data out of databases and delivering it as binary payloads through a delivery pipeline — filters, enrichments, and file handling at scale."
hero: true
showtoc: true
diagrams: true
---

## The frame

At NielsenIQ, the core job is taking retail measurement data — POS transactions, pricing, and analytics observations — and delivering it to downstream systems in a form they can consume quickly and cheaply. For many consumers that form is not a document or a report. It is a binary payload: compact, typed, and ready to load.

The design question was never "how do we produce the file". It was "how do we get data from the database, through the processing chain, and out to consumers without the pipeline becoming the bottleneck".

{{< mermaid caption="Filter pushdown is the load-bearing step: enrichment must never receive a superset." >}}
flowchart TB
  A[("@db Source database")] --> B["@work Query with filter pushdown"]
  B --> C["@step Filter stage"]
  C --> D["@step Enrichment stage"]
  D --> E["@doc Pack and frame"]
  E --> F[("@store Object storage")]
  F --> G["@client Consumer loads payload"]
{{< /mermaid >}}

## Why binary

The choice of a binary payload over JSON or CSV is a payload-size decision, and it is worth being concrete about the trade rather than asserting that binary is better.

A measurement window can hold hundreds of thousands of observations that share the same field names and types. In a self-describing format every record repeats that structure. In a framed binary layout, the schema is stated once in the envelope, the data is a fixed-width record stream, and the consumer allocates exactly what it needs.

What that buys:

- **Smaller transfers.** Less data over the same network, and less at rest.
- **Faster load.** No per-record parsing of field names; a typed reader maps offsets directly.
- **A stable contract.** Field order and types are fixed by the schema version, so a consumer cannot be surprised by a reordered or retyped field.

What it costs, honestly: a binary payload is not inspectable without the reader. A payload that arrives corrupt is harder to diagnose than a truncated JSON document. That is why the envelope carries a record count and a checksum — the binary format gives up legibility, so the metadata has to give it back.

## Querying the source

The chain starts by getting the right rows out efficiently. That meant pushing the delivery's filters into the query rather than reading a broad slice and discarding most of it downstream.

```sql {title="observation-extract.sql"}
SELECT
    o.store_id,
    o.week_index,
    o.product_code,
    o.quantity,
    p.price_amount,
    p.promotion_flag
FROM observation o
JOIN price p
  ON p.store_id = o.store_id
 AND p.week_index = o.week_index
 AND p.product_code = o.product_code
WHERE o.week_index = ANY($1::int[])   -- the delivery window, narrowed here
  AND o.store_id = ANY($2::text[])    -- the consumer's store selection
  AND p.promotion_flag IS NOT NULL
ORDER BY o.store_id, o.week_index, o.product_code;
```

The two `ANY(...)` clauses are the point. Filter pushdown means the enrichment stage receives only rows the consumer asked for. The alternative — a broad read followed by in-memory filtering — looks equivalent and is not: it transfers rows nobody wants, and it makes the enrichment stage's memory footprint scale with the source rather than with the delivery.

## Filters and enrichments

Raw retail data is rarely in the shape consumers want. Filters drop what is not part of a given delivery; enrichments add the derived context that makes the payload useful.

The distinction that keeps this maintainable is that **filters are about the delivery, enrichments are about the data**. A filter answers "does this row belong in this file?". An enrichment answers "what does this row mean?".

```yaml {title="delivery-filters.yaml"}
deliveryId: d-2026-03-14-000417
schema: measurement.observation.v3
filters:
  - field: weekIndex
    op: in
    value: [10, 11, 12]
  - field: storeTier
    op: eq
    value: national
  - field: promotionFlag
    op: notNull
enrichments:
  - name: priceIndex
    from: priceAmount
    rule: normaliseToCategoryMedian
  - name: classification
    from: productCode
    rule: lookupProductHierarchy
  - name: channel
    from: storeId
    rule: resolveStoreMetadata
```

Declared as configuration, this has two practical benefits. The filter set that produced a given delivery is reconstructable afterwards, which is what makes an incident diagnosable. And a filter is testable on its own, without running the pipeline.

## File handling at the edge

Once the payload is packed, the remaining problem is the file lifecycle: a consumer must never observe a partially written object as if it were complete.

The sequence matters, and the ordering is the guarantee:

{{< mermaid caption="The consumer only ever sees a completed object, because the manifest is published last." >}}
sequenceDiagram
  participant P as Pipeline
  participant S as Object storage
  participant C as Consumer
  P->>S: Write payload (temporary key)
  P->>S: Verify record count and checksum
  P->>S: Publish under final key
  P->>S: Write delivery manifest last
  C->>S: List manifest
  C->>S: Fetch payload by final key
  C->>C: Re-verify checksum
{{< /mermaid >}}

The manifest is written last on purpose. A consumer discovers deliveries by listing manifests, so a payload that is fully written and verified but not yet announced is simply not visible yet. That makes "payload exists" and "payload is complete" the same observation, which removes a whole category of partial-read bug without a transaction.

The consumer still re-verifies the checksum after fetching. The producer's verification protects the consumer from a truncated transfer; the consumer's verification protects it from a producer that believed it was correct.

## Failure modes

- **A slow source turns into a late delivery.** Pushing filters down helps, but a query that degrades under a large window still threatens the schedule. Tracking query time separately from total delivery time is what makes this visible before it becomes a missed delivery.
- **An enrichment rule that depends on a lookup going stale.** A classification that quietly resolves differently after a product-hierarchy update is a data change disguised as a code deploy. Versioning the enrichment rule alongside the schema version is the mitigation.
- **A consumer that trusts `recordCount`.** The count is a cheap first check, not a guarantee. Reconciling it against the source is the only real verification, and it is worth doing in the consumer's own monitoring rather than the producer's.

## What I would keep

The pushdown discipline is the part I would protect hardest in review. It is the one decision that makes the rest of the chain scale, and it is also the easiest to undo by accident — a filter moved from the query into the enrichment stage looks like a harmless refactor and quietly returns the pipeline to reading everything.
