# Diagram standard

Every diagram on this site is rendered through one global `mermaid.initialize()`
call in `layouts/partials/head.html`. That call **is** the house style. There are
no per-article diagram overrides, and there should not be any — if a diagram needs
different settings to look right, the diagram is wrong, not the standard.

## The standard

| Property | Value | Why |
|---|---|---|
| Node / state label | `15px` | The content. The thing the reader is here for. |
| Edge / transition label | `12px` | The annotation. Must not compete with the node. |
| Cluster / subgraph label | `12px` | Grouping, subordinate to both. |
| Font family | `--vm-font-sans` | The page's own stack, not Mermaid's `trebuchet ms`. |
| `nodeSpacing` | `56` | Comfortable, not airy. |
| `rankSpacing` | `80` | Headroom for dense diagrams without bloat. |
| `diagramPadding` | `14` | Breathing room at the frame edge. |
| `useMaxWidth` | `true` | Never wider than the 68ch measure. |
| Palette | `--vm-*` tokens | Diagrams re-theme with the site. |

Type sizes and label margins are applied through `themeCSS`, not the `fontSize`
option. That is not a stylistic preference: `fontSize` only reaches **node**
labels, and Mermaid's own ID-scoped rule wins on the edge/cluster `<g>`. Setting
`fontSize: '15px'` alone leaves node labels at 16px until the `themeCSS` rule is
also present.

## The one rule that matters most: keep diagrams portrait

A Mermaid diagram has a single intrinsic size and is scaled by
`rendered / viewBox-width`. In a portrait reading column that means **a landscape
diagram does not render small, it renders illegible** — the text scales with
everything else. This is not theoretical: before the standard existed, four of six
diagrams on this site were painting their labels at **3.8–5.0px**, the worst being
a 19:1 sliver. Nothing errored. The build was green. The figures just looked
broken.

So:

- **Prefer `flowchart TB`.** A left-to-right chain of 6+ nodes becomes a
  landscape ribbon in a portrait column. `TB` turns that same graph into a
  portrait column that renders at scale 1.0.
- **Target an aspect ratio between 0.3 and 1.6.** Under ~0.3 the diagram gets
  very tall; over ~1.6 it starts shrinking.
- **Target an intrinsic width of 200–600 units.** The article column is ~566px
  wide, so anything wider than that is being scaled down.
- **`subgraph` blocks that are not connected to each other get packed
  side-by-side by dagre**, regardless of `TB`. If you need two subgraphs stacked,
  connect them with an edge — even a dashed one carrying the real meaning
  (`X -.->|migrated to| Y`).

## Icons

Mermaid 11 cannot put an image in a node — Font Awesome node classes were removed
in v10, and its markdown-image label syntax fails the flowchart lexer outright
(`Lexical error ... Unrecognized text`). So the loader injects icons **after**
render, keyed off a marker at the start of a node label:

```
A["@db Source database"]      ->  database glyph, marker removed
```

The marker is stripped and replaced with an inline `<svg>` inside the label's own
`<p>`, so the layout engine never sees the extra text and the node box sizes
itself around the icon. Icons are inline SVG, not `<img>`, so they theme with the
site and cost no extra request.

Available names — pick by **what the thing is**, not what it looks like:

| Name | Use for |
|---|---|
| `@db` | a database / datastore the system reads or writes |
| `@store` | object storage, a bucket, a CDN origin |
| `@server` | a compute service, a worker, a host |
| `@client` | a consumer, browser, or downstream client |
| `@work` | a generic processing stage |
| `@step` | a single transform or filter step |
| `@doc` | a file, an envelope, a document, an artefact |
| `@people` | humans, teams, an external party |

An unknown name is left as literal text rather than silently dropped, so a typo is
visible instead of invisible.

Icon tone is derived from `--vm-peach-italic` and `--vm-eyebrow` — the two warm
tokens that **flip** with the theme. `--vm-accent` is deliberately *not* used for
icon strokes: it is static brand orange and measures only 2.3:1 on the light-theme
node fill, which is why an earlier pass had washed-out, unreadable icons. All
seven icons measure ≥3:1 (WCAG non-text) in both themes.

## Labels

- **Edge labels: 2–4 words.** `pipeline wins`, not `the pipeline is now
  authoritative and the bespoke path is retained as a fallback`. Long edge labels
  are the direct cause of label collisions; a collision is a layout bug you cannot
  fix with CSS.
- **Node labels: 1–3 words, no trailing punctuation.** Prefer `Query and filter`
  over `Query stage with filter pushdown`.
- **One idea per diagram.** A diagram that needs a paragraph to read is a
  paragraph.

## The legibility floor (safety net, not a licence)

`enforceLegibility()` in `head.html` measures each rendered diagram. If the implied
scale would drop labels below **0.8× (12px effective)**, it pins a `min-width` on
the SVG so the figure scrolls horizontally instead of shrinking into illegibility.

`min-width` beats Mermaid's inline `max-width` in the CSS cascade, which is why
this works without `!important`.

This is a **net for authoring mistakes, not permission to write landscape
diagrams.** A guarded diagram is legible but requires horizontal scrolling. Fix the
orientation instead. When the guard fires it sets `data-mermaid-min-width` on the
`<pre>`, which is how you find the offenders.

## Verifying a change

Diagrams are client-rendered, so a green build proves nothing about them. After
adding or editing a diagram, check it in a browser:

```js
// paste in the console on the article page
[...document.querySelectorAll('pre.vm-mermaid')].map(pre => {
  const svg = pre.querySelector('svg');
  const vb = (svg.getAttribute('viewBox') || '0 0 1 1').split(/\s+/).map(Number);
  const r = svg.getBoundingClientRect();
  const p = svg.querySelector('.nodeLabel p');
  return {
    intrinsic: Math.round(vb[2]) + 'x' + Math.round(vb[3]),
    ar: +(vb[2] / vb[3]).toFixed(1),
    effectivePx: +((p ? parseFloat(getComputedStyle(p).fontSize) : 15) * (r.width / vb[2])).toFixed(1),
    guardFired: pre.dataset.mermaidMinWidth || null
  };
});
```

Targets: `ar` between 0.3 and 1.6, `effectivePx` ≥ 12, `guardFired` ideally `null`.

Also confirm `pre.dataset.mermaidState === 'ready'` and that the browser console
has no `[mermaid] render failed` entry. A diagram that failed to parse leaves its
source visible as text and logs the reason — it does not fail the build.

## Adding a diagram to an article

1. Add `diagrams: true` to the front matter (this is what loads Mermaid at all —
   pages without it ship zero Mermaid bytes).
2. Add the shortcode on its own line, never mid-paragraph:

   ```
   {{< mermaid caption="What the reader should take away." >}}
   flowchart TB
     A[First] --> B[Second]
   {{< /mermaid >}}
   ```

3. Work to the rules above, then verify in a browser.
