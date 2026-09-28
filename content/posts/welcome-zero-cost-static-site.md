---
title: "Why I rebuilt this site as a static site: zero-cost, zero-node infrastructure"
date: 2026-09-24
draft: false
tags: [hugo]
summary: "A practical note on choosing GitHub Pages, GitHub Actions, and Hugo for a personal engineering site that stays inexpensive to run and easy to own."
---

I wanted a place for engineering notes that was cheap to keep online, easy to write in, and simple enough that I would still use it. I did not need a server, an admin panel, or a database. Those choices may make sense for some products, but they were unnecessary for a personal portfolio and blog.

The site is a static site built with Hugo. The pages are generated ahead of time and hosted on GitHub Pages. GitHub Actions builds the same content whenever I push to the main branch, then publishes the generated site through the Pages deployment workflow.

That setup has a useful property: the deployed result is just files. There is no application process to keep alive, no runtime dependency to patch, and no server-side session or database to maintain. The serving layer is managed for me, and the public content can be cached cheaply because it does not change for each request.

The free tier is enough for a site of this size. GitHub Pages provides the public hosting, and GitHub Actions runs the build and deployment using the included public-repository minutes. The limits are worth checking as usage grows, but a documentation site is a much simpler workload than a continuously running application.

The authoring model is just as important. I write in Markdown, keep the files in Git, and use front matter for the small amount of metadata Hugo needs. That gives me plain text I can read without the site running, version history I can inspect, and a reviewable diff before anything goes live. The file is the source of truth, not a hidden database record.

I still use automation, but the automation has a narrow job. It installs the build tool, generates the site, and uploads the output. A failed build stops the deployment. A successful build produces a predictable set of HTML, RSS, sitemap, and taxonomy pages that can be inspected before publication.

This approach is not the right answer for every site. If I needed authenticated content, user-specific responses, or a frequently changing application workflow, a static site would be the wrong tool. For engineering writing, though, the simple model fits well. The content is durable, the infrastructure is nearly free, and the maintenance surface is small.

I am treating this site as the frame around my work, not the painting itself. It gives my case studies and notes a stable home while LinkedIn and GitHub remain the places where the wider professional context lives. The stack is deliberately boring: Markdown, Hugo, GitHub Actions, and GitHub Pages. That gives me fewer moving parts to explain and more time to write the next thing.
