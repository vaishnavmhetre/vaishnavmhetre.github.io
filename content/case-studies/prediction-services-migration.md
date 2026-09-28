---
title: "Migrating prediction services onto the delivery pipeline"
date: 2026-09-24
draft: false
tags: [data-delivery, platform]
summary: "A case study about supervising the migration of prediction services — such as a pricing forecast backend — onto a shared delivery pipeline, and making them robust."
hero: true
showtoc: true
diagrams: true
---

## The frame

Prediction services — such as a pricing forecast backend — need data to make predictions, and they need it on a schedule and shape they can rely on. Over time a service can drift: it builds its own data path, its own retrieval logic, its own error handling. Each service doing this separately means each is maintained separately, and each fails separately.

The frame for the work was consolidation. Prediction services should not each reinvent how they get data. They should sit on the shared delivery pipeline, inherit its guarantees, and spend their effort on the prediction itself.

{{< diagram name="04-before-after" alt="One path shown end to end. The forecast service first owns its query, its retries, and its direct database reads; then that same service holds a delivery subscription and reads from a shared pipeline that writes to object storage. The handover from direct database reads to the delivery subscription is the migration." caption="The same service, before and after: the direct database path gives way to a shared pipeline." >}}

## The data contract first

Before moving anything, the first piece of work was writing down what the service actually needs. Not what it currently reads, but what it needs — because those are usually different, and the difference is where the migration goes wrong.

The contract is explicit about shape, schedule, and completeness:

```json {title="forecast-input-contract.json"}
{
  "contract": "forecast.input.v2",
  "consumer": "pricing-forecast",
  "schedule": { "cadence": "daily", "readyBy": "04:30Z" },
  "inputs": {
    "historyWindow": { "weeks": 104, "grain": "store-product-week" },
    "features": ["priceIndex", "promotionFlag", "seasonalityIndex"],
    "keys": ["storeId", "productCode", "weekIndex"]
  },
  "completeness": {
    "requireFullWindow": true,
    "onIncomplete": "fail"
  }
}
```

The `onIncomplete: fail` line is the one that changes behaviour most. The bespoke path had no such notion; a short read simply produced a forecast computed over fewer weeks, and nothing distinguished that from a normal run. Making the failure explicit is what allows the pipeline to retry rather than to let a degraded forecast reach a downstream decision.

## Pipeline-native intake

Replacing bespoke retrieval meant deleting the service's own query and error handling, which is a larger change than it sounds — the bespoke path usually also carried retry, backoff, and logging that looked load-bearing but was only compensating for the shape of the data it received.

The subscription itself is small, because the pipeline is doing the work:

```go {title="forecast-subscription.go"}{linenos=false}
func (c *ForecastConsumer) Deliver(env Envelope) error {
    if !env.Complete {
        // Explicitly refuse rather than forecast over a short window.
        return ErrIncompleteWindow
    }
    rows, err := c.reader.Load(env.ContentURI, env.Schema)
    if err != nil {
        return fmt.Errorf("load %s: %w", env.DeliveryID, err)
    }
    return c.model.Refit(rows)
}
```

The contrast with the previous version is the point. There is no query, no connection handling, no retry loop, no partial-read tolerance. What remains is the part that is genuinely the service's responsibility.

## Cutover and rollback

The migration was not a lift-and-shift. Each service moved through explicit states, and the rollback path was designed before the cutover rather than after.

{{< diagram name="05-cutover" alt="The bespoke path runs first. Both paths then run side by side and their outputs are compared. Once the pipeline's outputs win it becomes authoritative, and the last step is the fallback window closing, after which only the pipeline remains." caption="Shadow first, and rollback stays a flag until the fallback window closes." >}}

Two decisions in that sequence are the ones I would keep:

**Shadow before cutover.** Running both paths and comparing outputs answers the question that actually matters — does the consolidated data produce the same prediction — before anything depends on the answer. It also surfaces the cases where the bespoke path was quietly doing something undocumented.

**Rollback as a flag, not a redeploy.** Keeping the bespoke path alive through a defined window means recovery is a configuration change. Recovering by redeploying the old code under incident pressure is how a migration becomes an outage.

## Failure modes

- **A service that depended on an undocumented behaviour of its own path.** The most common finding during shadowing. Sometimes it is a filter nobody wrote down; sometimes it is an ordering the model happened to be trained on. Both need to become explicit in the contract, or the service will not survive its own migration.
- **A schema change that is backwards-compatible for a producer but not a consumer.** The pipeline can add a field safely; a consumer that maps by position cannot. The contract's `keys` list is what makes this checkable.
- **A service whose retrain window outlives the fallback.** If a model is retrained from pipeline data, the bespoke path can no longer reproduce the previous model, and the rollback is no longer equivalent. The fallback window has to be at least as long as the reproducibility window.

## What consolidation cost

Being direct about this, because consolidation is not free.

The service teams lost the ability to change their retrieval logic without coordinating with the pipeline. A filter that used to be a one-line change became a pipeline configuration change with a review. That is a real reduction in autonomy, and for a service with genuinely unusual retrieval needs it can be the wrong trade.

What they gained was the removal of a whole class of problem: nobody on the service team was maintaining a query, a retry policy, and a partial-read tolerance any more. The work that remains is the prediction, and the pipeline's guarantees are now something they consume rather than something they defend.
