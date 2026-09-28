---
title: "How this site is built: static output, no diagram runtime, and the bugs that hid in plain sight"
date: 2026-09-28
draft: false
tags: [hugo, css]
summary: "Notes on rebuilding the diagrams on this site to render at build time instead of in the browser, and on the three classes of bug that only showed up once something was measured properly."
hero: true
showtoc: true
---

This is the writeup I wanted to exist before I built any of it: what the site does, how it does it, and
where the seams are. It is written for the engineer reading it rather than for a portfolio reviewer, so
it spends most of its length on the parts that went wrong.

The [case studies](/case-studies/) argue through platform decisions. This argues through tooling.

## The shape of it

Hugo builds every page ahead of time and GitHub Pages serves the result. There is no application process,
no database, and nothing that runs per request. That part is unremarkable and covered in
[why this site is static](/posts/welcome-zero-cost-static-site/).

The part worth writing about is that the site has **no client-side runtime at all**. No framework, no
hydration, no CDN script. Every diagram on this site is an SVG file that was rendered before you loaded
the page, and the only JavaScript that ships is the theme toggle.

That property is not a goal I started with. It is what was left after removing the last thing that
needed it, and the removing is the interesting part.

## Diagrams moved to build time

The diagrams used to be Mermaid, rendered in the browser by a script pulled from a CDN. It worked, and it
was wrong for this site in three separate ways.

It was **illegible at the reading measure**. Mermaid scales its output down to fit its container, and
this site reads at a 68-character measure. Four of the six diagrams were too small to read — labels
were technically present and practically absent. The failure was silent, which is the worst kind: the
page built, the diagrams rendered, and they were unreadable.

It was **a runtime dependency on someone else's CDN**, with an integrity hash and a pinned version, for
content that is entirely under my control and changes only when I change it. I was paying availability
and correctness risk for a rendering step that has no reason to happen per request.

And it **re-rendered on every theme flip**, because a diagram drawn in one palette cannot be recoloured
in place.

D2 fixes all three. It is a layout engine that emits SVG, it runs at build time, and each theme is
rendered as its own file. The pipeline is short:

{{< diagram name="07-diagram-pipeline" alt="A diagram starts as Markdown that names the figure, a Python generator turns that into a D2 source file, the D2 layout engine arranges it, three post-processes fix what the layout engine gets wrong, and the result is committed as an SVG that Hugo embeds in the page as a plain image." caption="The diagram is a committed file, not a runtime render. The post-processes in the middle are the interesting part." >}}

The SVGs are committed, not built by Hugo. That is deliberate: the diagram content is authored in
Python, and committing the output means the repository holds what the reader actually gets. A future
check can regenerate and diff, which is the only way to know the committed files still match the
generator.

## The constraint I had the wrong model of

I spent a while trying to make the tall diagrams shorter, and I was measuring the wrong thing.

I was reading aspect ratio. The number that actually matters is **effective label size**: the font size
after the browser scales the SVG to fit its column. A figure that is too tall keeps its full label size
and merely gets long. A figure that is too wide loses its label size entirely, and there is no recovering
it. Too tall is survivable. Too wide is not.

Once I measured that properly, most of my ideas about the problem dissolved. I had assumed a wide
landscape layout would let a figure be short *and* readable. Rendering it gave 4.7-pixel labels. The
idea was not clever, it was arithmetically impossible.

Two other attempts failed in instructive ways:

- **Laying the chain out horizontally** produced a 2399-pixel-wide ribbon that collapsed to 4.7-pixel
  text. Unusable.
- **Grouping stages into named containers** made the figure *taller*, not shorter — 1686 pixels against
  1500. The layout engine stacks containers rather than placing them side by side, which is not obvious
  until you have measured it.

What actually worked was the least technical option available: fewer nodes per figure. Two diagrams were
each seven stages in a single column, rendering 1500 pixels tall. Splitting each at its natural boundary
into two figures brought them to 842 and 640 pixels with every label still at its full size. No amount of
layout cleverness was going to beat simply not drawing seven things in a column.

The rule I ended up with is enforced in the generator, not in CSS: a figure that would render its labels
below 15 pixels is a build-time failure, not a page someone discovers later.

## Three bugs that hid in plain sight

Each of these shipped to a green build. None of them was found by looking at the page.

**A white panel behind every dark-mode diagram.** The layout engine renders for a white page, so its
first element in every file is an opaque white rectangle covering the whole canvas. On a light surface
that is nearly invisible; on a dark surface it is a glaring white block. I found it by reading the
generated SVG rather than the rendered page, which is a habit I would now recommend to anyone building
this way.

**Icons that silently stopped loading.** The engine writes icon references as paths relative to the
source file it was given. Once the SVG was published at its own URL, those relative references resolved
to nothing and returned 404. The failure was partial in the worst way: the node shapes, borders, and
labels all still rendered, so the figure looked almost right with its icons missing. The fix was to
inline the icon bytes into each file, which is also simply correct — an SVG loaded as an image cannot
reach its siblings.

**Syntax highlighting with five invisible token classes.** This is the one I am most embarrassed by,
because the file said it had been checked. I had generated a light syntax palette with Hugo's built-in
generator, spot-checked a handful of token colours against the light code surface, and written a comment
claiming the palette was contrast-checked. It was not, and five classes were unreadable — one of them
pure white on a cream background.

Three of those five were the interesting failure. The palette generator is older than the SQL and YAML
lexers in use, so those token classes have no entry in its output at all. An undefined class gets no
rule from my file and falls through to the theme's own palette, which is a *dark* palette. So the
undefined classes were being painted with light colours intended for dark backgrounds, on a light
background, by a stylesheet I had written specifically to prevent that.

That is the kind of bug that a build cannot catch and a screenshot will not reliably show. Measuring
every token against the actual surface is what found it, and it took one pass to find all five after I
had already declared the file done.

The fix was not just correcting colours. It was making the generator's promise true: measure every
token, and if any falls below the contrast floor, say so in the build rather than in a comment.

## The fix that made it worse

Worth recording because it is the most instructive mistake here.

The invisible `.err` token was GitHub's light-on-dark error styling, which is invisible on a light
surface. I re-pointed its text colour to the deletion red already used elsewhere in the palette. That
fixed the text and made the figure worse, because Chroma styles pair a foreground *with* a background,
and I had overridden one and left the other. The result was dark red text on a dark red block: a solid
rectangle with the token invisible inside it.

Overriding half of a paired style is worse than not overriding it, because it looks like it worked. Both
properties now move together, and the file says so, because the next regeneration would otherwise put the
background back.

There was also a genuine lexer gap underneath: the SQL lexer does not recognise PostgreSQL positional
placeholders, so a `$1` in a parameter list was classified as an error token. The fence is now fenced as
PostgreSQL, which handles them. I checked the two obvious alternative names first, and both of them
silently fall back to no highlighting at all — a quieter and worse bug than the one it replaced.

## What I got wrong about verification

Several of the findings above only arrived because I measured instead of reasoned, and several mistakes
survived a long time precisely because I asserted rather than checked. Being specific, because these are
the parts I would tell someone else to watch for:

I claimed a palette was contrast-checked when I had spot-checked it. I twice said a layout change would
make a figure shorter, on the strength of the aspect ratio alone, without rendering it. I twice mistook
a screenshot artefact for a rendering bug — an element screenshot captures the visible box, not the
scrollable area, so a figure that scrolls correctly looks clipped. I once got a diagram's dimensions as
`312x42` because of a careless pattern in my own checking script, and briefly took it as evidence of a
regression.

The pattern is consistent enough to be worth stating as a rule: **on a page built by a generator, the
generator is the thing to trust and the browser is the thing to check.** A file that a tool produced will
happily contain a white rectangle or a dangling path, and it will do so while every check passes. The
only thing that found these was reading the output — and then reading the output again after changing it.

## Where the seams are

Two places where this design is a cost rather than a feature, so they are written down.

Editing a diagram means running a Python generator, which means having the D2 CLI installed. There is no
way to tweak a figure in the browser. That is the price of a committed, diffable, reproducible figure, and
for eight diagrams it is worth paying.

And the committed SVGs can drift from the generator that produced them. Nothing fails today if they do.
The check that would catch it — regenerate in CI and diff the result — is the obvious next thing to add,
and I have not added it yet.

The rest of the site is in the [case studies](/case-studies/) and the
[posts](/posts/). The diagram conventions, including the measured constraints and the approaches that
did not work, are documented in `docs/diagrams.md` in the repository.
