---
title: "Why I rebuilt this site as a static site: zero-cost, zero-node infrastructure"
date: 2026-09-24
draft: false
tags: [hugo]
summary: "A practical note on choosing GitHub Pages, GitHub Actions, and Hugo for a personal engineering site that stays inexpensive to run and easy to own."
hero: true
showtoc: true
diagrams: true
---

## The constraints

I wanted a place for engineering notes that was cheap to keep online, easy to write in, and simple enough that I would still use it. I did not need a server, an admin panel, or a database. Those choices may make sense for some products, but they were unnecessary for a personal portfolio and blog.

Three constraints drove everything else: the running cost should be zero at this size, the publishing path should have no moving parts I have to babysit, and the content should be readable and editable without running anything.

## Why static

The site is a static site built with Hugo. The pages are generated ahead of time and hosted on GitHub Pages. GitHub Actions builds the same content whenever I push to the main branch, then publishes the generated site through the Pages deployment workflow.

That setup has a useful property: the deployed result is just files. There is no application process to keep alive, no runtime dependency to patch, and no server-side session or database to maintain. The serving layer is managed for me, and the public content can be cached cheaply because it does not change for each request.

The free tier is enough for a site of this size. GitHub Pages provides the public hosting, and GitHub Actions runs the build and deployment using the included public-repository minutes. The limits are worth checking as usage grows, but a documentation site is a much simpler workload than a continuously running application.

## The build pipeline

The whole path from a text edit to a live page is four steps, and it is the same on every push.

{{< mermaid caption="Push to main, and the deployed artifact is a directory of files. Nothing else runs." >}}
flowchart TB
  A["@doc Push to main"] --> B["@work GitHub Actions"]
  B --> C["@step Hugo build"]
  C --> D["@server Deploy to Pages"]
  D --> E["@client Served from CDN"]
{{< /mermaid >}}

Here is the shape of the workflow that does it — an excerpt from the actual file in this repository, with the favicon and search steps left out, and with the lines that use GitHub Actions' double-brace expression syntax omitted:

```yaml {title=".github/workflows/hugo.yaml"}
name: Deploy Hugo site to Pages
on:
  push: { branches: [main] }
  workflow_dispatch:
permissions: { contents: read, pages: write, id-token: write }
concurrency: { group: pages, cancel-in-progress: false }
jobs:
  build:
    runs-on: ubuntu-latest
    env: { HUGO_VERSION: 0.166.0, GO_VERSION: 1.27.1 }
    steps:
      - uses: actions/checkout@v7
      - id: pages
        uses: actions/configure-pages@v6
      - name: Build
        run: |
          hugo mod get -u github.com/adityatelange/hugo-PaperMod || true
          hugo mod tidy || true
          HUGO_ENVIRONMENT=production hugo build --gc --minify
      - uses: actions/upload-pages-artifact@v5
        with: { path: ./public, include-hidden-files: false }
  deploy:
    runs-on: ubuntu-latest
    needs: build
    environment: { name: github-pages }
    steps:
      - uses: actions/deploy-pages@v5
```

Those omitted lines are not incidental: this site's own verification treats a literal double-brace sequence anywhere in the built output as a build failure, so a workflow file quoted verbatim would fail the very build it describes. That is a genuine constraint of publishing a template-heavy site, and it is worth knowing before you quote your own CI in a post.

The separation into `build` and `deploy` jobs is not decoration. The build produces an artifact; the deploy consumes it with elevated permissions. That means the step that runs Hugo — the step that fetches and executes code — does not hold the permission to publish.

One line in there is a known wart rather than a decision: `hugo mod get -u` re-resolves the theme to its latest version on every build, so a build is not reproducible in the strict sense. It is convenient, and I have left it, but a build that should be byte-identical next month would drop the `-u` and commit the resolved version.

## The authoring model

The authoring model is just as important. I write in Markdown, keep the files in Git, and use front matter for the small amount of metadata Hugo needs. That gives me plain text I can read without the site running, version history I can inspect, and a reviewable diff before anything goes live. The file is the source of truth, not a hidden database record.

This has a concrete benefit that I did not anticipate: because the content is plain text in Git, I can check the site for internal problems without deploying it. A small verification script builds the site to a temporary directory and asserts the things that silently break — that there is a title, that the feeds and sitemap exist, and that no template went unrendered:

```bash {title="scripts/verify-site.sh"}{linenos=false}
OUT="$(mktemp -d)"
HUGO_ENVIRONMENT=production hugo build --gc --minify --destination "$OUT"
grep -q '<title>' "$OUT/index.html"
[ -f "$OUT/sitemap.xml" ] && [ -f "$OUT/posts/index.xml" ]
```

It also greps the output for stray local development URLs, so a link that only works on my machine cannot reach production. The unrendered-template check is the other one that earns its place: a malformed template can render as visibly broken HTML without failing the build, so the script greps for a double-brace sequence and fails if it finds one — a page of literal template syntax otherwise ships quietly.

Both checks have a false-positive mode worth naming, because I hit both writing this post. Quoting a file that legitimately contains double braces, such as a GitHub Actions workflow, trips the template check; naming the development host in prose trips the URL check. The safe response is to change the content, not to relax the checks. A canary that gets quieter when it is inconvenient is not a canary.

## What it costs

Financially, nothing at this size. In effort, the costs are real and I want to be specific about them rather than claiming this is free:

- **Build time is my compute cost.** A documentation site is small, but every push spends minutes. That is cheap and it is not nothing.
- **No server-side features.** Comments, search across dynamic content, and anything needing a request-time database are out of reach without adding a service. Search here is a static index built at compile time, which is adequate for a site this size and would not be for a large one.
- **Content lives in Git.** That is excellent for review and versioning, and it means writing is coupled to Git. For anyone not comfortable with that, it is a real cost.
- **Template errors surface late.** Because there is no runtime, a broken layout is caught by reading the output, not by a stack trace.

## What would change my mind

I would move off a static site if any of these became true:

- **Content that genuinely needs request-time data.** If the site became a tool rather than a publication, the build-time model would be fighting the use case.
- **Publishing that cannot wait for a push.** If I needed to edit and go live without a commit, a static model would be the wrong shape.
- **A hosting or minutes limit I actually hit.** Not a projected limit — a real one. Until then, moving would add a component to remove a cost I am not paying.
- **Collaboration that needs concurrent editing.** Git handles sequential review well and real-time co-authoring badly.

None of those are true today. That is the whole argument: the infrastructure should match the current constraints, and the constraints should be revisited when they actually change rather than when they might.
