---
title: "Binary data delivery for retail measurement"
date: 2026-09-24
draft: false
tags: [data-delivery, gcp]
summary: "A case study about querying retail measurement data out of databases and delivering it as binary payloads through a delivery pipeline — filters, enrichments, and file handling at scale."
---

## The frame

At NielsenIQ, the core job is taking retail measurement data — POS transactions, pricing, and analytics observations — and delivering it to downstream systems in a form they can consume quickly and cheaply. For many consumers that form is not a document or a report. It is a binary payload: compact, typed, and ready to load.

The design question was never "how do we produce the file". It was "how do we get data from the database, through the processing chain, and out to consumers without the pipeline becoming the bottleneck". The pipeline I worked on does exactly that: querying the data out of the database, running it through filters and enrichments, and handling the files that carry it to consumers.

## The approach

The work split naturally into three connected pieces:

* **Querying the database.** The delivery chain starts with getting the right rows out efficiently. That meant query optimization against large databases, so the pipeline reads what the enrichment stage actually needs — not a superset that gets filtered later.
* **Filters and enrichments.** Raw retail data is rarely in the shape consumers want. The pipeline applies filters to drop what is not part of a given delivery and enrichments to add the derived context (pricing, classification, measurement metadata) that makes the payload useful downstream.
* **Configuration and file handling.** The pipeline is deliberately config-driven. Processing rules live in a configuration-handling framework, so changing what a delivery contains does not require a code deploy. The file-handling service owns how payloads are written, named, stored, and handed to consumers.

## Tradeoffs

Binary delivery is not free. It comes with real choices:

* **Query cost versus freshness.** Pulling more data into the pipeline makes each query more expensive; pulling less means enrichment needs to wait or interpolate. The balance has to be explicit per delivery.
* **Filtering early versus late.** Filtering in the pipeline saves storage and transfer cost. Filtering later keeps flexibility if consumers' needs change. Early filtering that is wrong is expensive to undo.
* **Config-driven versus code-driven.** Configuration makes rule changes cheap, but it needs schema discipline and validation — a config typo must fail loudly, not silently reshape a payload.
* **Binary versus readable.** Binary payloads are compact and fast to load but harder to inspect by hand. Debugging and observability have to compensate.

## Outcome and learnings

The outcome is a delivery chain that moves large volumes of retail measurement data reliably, where the processing rules are changeable without redeploying the pipeline. The main learning was that the database query is part of the product. Optimizing the query and the pipeline together — rather than treating them as separate teams' problems — is what makes delivery fast, and getting binary payloads right is an engineering discipline of its own, distinct from document handling.