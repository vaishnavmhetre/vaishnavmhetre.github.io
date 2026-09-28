"""D2 diagram generator — the AUTHORITATIVE source for every figure on the site.

Run from the REPO ROOT (the generator uses relative paths for the icon set):
    python3 scripts/diagrams/build.py

Output lands in assets/diagrams/<name>.<theme>.svg and is COMMITTED. Hugo does
not run this; assets/ is source, public/ is gitignored build output. The
`{{< diagram >}}` shortcode reads these files off disk via resources.Get and
fails the build via errorf if either theme of a name is missing.

Three non-obvious post-processes run on every file. Each exists because the
obvious alternative is silently wrong, not because it is a style preference:

1. open_icon_label_gap() — D2 gives no control over icon-to-label clearance
   (see its docstring). Fixes the geometry in the only place it lives.
2. strip_backdrop() — D2 emits an opaque full-canvas white <rect> as the first
   element of every render. Left alone it is a white panel behind the figure,
   which is glaring in dark mode. Removed so the figure inherits the page
   surface. (D2 also rewrites strokes for a white page, so edge contrast had to
   be set explicitly in THEME — see `edge`.)
3. inline_icons() — D2 emits <image href="assets/icons/…">, a path RELATIVE TO
   THE .d2 SOURCE FILE. Once the SVG is published at /diagrams/<name>.svg that
   relative href resolves to /diagrams/assets/icons/… and 404s, so the icons
   vanish while shape, border and label keep rendering: a quiet, partial
   failure. The bytes are inlined as data URIs instead, making each SVG
   self-contained — which is what an <img> needs anyway.
"""
import base64, os, re, subprocess, sys
ICONS="assets/icons/light"
OUT="assets/diagrams"
DIAGRAMS = {
"01-ai-pipeline": dict(dirn="down", nodes=[
  ("src","Source systems","cloud","cloud"),("qry","Query and filter","rectangle","filter"),
  ("enr","Enrichment","rectangle","cpu"),("pack","Pack and frame","rectangle","package"),
  ("prod","Production payload","cylinder","database"),("ai","AI training inputs","cylinder","chart"),
  ("mdl","Model store","cylinder","server")],
  edges=[("src","qry"),("qry","enr"),("enr","pack"),("pack","prod"),("pack","ai"),("ai","mdl")]),
# 02 and 04 are each SPLIT INTO TWO FIGURES rather than drawn as one tall
# column. Seven stacked stages in a 566px measure render at 1500px, and there
# is no layout that fixes that: a landscape `direction: right` chain collapses
# to 4.7px text at 87px tall, and D2 groups (containers) are stacked vertically
# by dagre regardless of direction, so grouping made it TALLER (1686px), not
# shorter. Height here is decided by the number of nodes, so the only lever is
# fewer nodes per figure. Each half is 3-4 stages and reads as one idea.
"02a-query-and-enrich": dict(dirn="down", nodes=[
  ("db","Source database","cylinder","database"),("push","Filter pushdown","rectangle","search"),
  ("flt","Filter stage","rectangle","filter"),("enr","Enrichment stage","rectangle","cpu")],
  edges=[("db","push"),("push","flt"),("flt","enr")]),
"02b-pack-and-deliver": dict(dirn="down", nodes=[
  ("pack","Pack and frame","rectangle","package"),
  ("obj","Object storage","cylinder","storage"),
  ("con","Consumer loads payload","rectangle","monitor")],
  edges=[("pack","obj"),("obj","con")]),
"03-file-lifecycle": dict(dirn="down", nodes=[
  ("w","Write payload","rectangle","save"),("v","Verify count and checksum","hexagon","shield"),
  ("p","Publish under final key","rectangle","swap"),("m","Write delivery manifest","rectangle","save"),
  ("c","Consumer fetches","rectangle","monitor"),("r","Re-verify checksum","hexagon","check")],
  edges=[("w","v"),("v","p"),("p","m"),("m","c"),("c","r")]),
# 04 splits at the handover point, which is also the semantic boundary: the
# first figure is the path being retired, the second is what replaces it. Every
# node is `retired` here, so they stay dashed and dimmed. Keeping that styling
# is what makes the pair read as one before/after across two figures, instead
# of two unrelated diagrams.
"04a-before-bespoke": dict(dirn="down", nodes=[
   ("s1","Forecast service","rectangle","monitor"),
   ("q1","Own query and retries","rectangle","search"),
   ("x1","Direct database reads","cylinder","database")],
   group_of={"s1":"retired","q1":"retired","x1":"retired"},
   edges=[("s1","q1"),("q1","x1")]),
"04b-after-shared": dict(dirn="down", nodes=[
   ("c","Delivery subscription","rectangle","swap"),
   ("p","Shared pipeline","rectangle","sliders"),
   ("o","Object storage","cylinder","storage"),
   ("s2","Forecast service reads","rectangle","monitor")],
   group_of={"c":"current","p":"current","o":"current","s2":"current"},
   edges=[("c","p"),("p","o"),("o","s2")]),
"05-cutover": dict(dirn="down", nodes=[
  ("a","Bespoke path","rectangle","server"),("b","Shadow both, compare","hexagon","shield"),
  ("c","Pipeline authoritative","rectangle","sliders"),("d","Fallback window closes","hexagon","check"),
  ("e","Pipeline only","rectangle","database")],
  edges=[("a","b"),("b","c"),("c","d"),("d","e")]),
"06-build-pipeline": dict(dirn="down", nodes=[
  ("push","Push to main","rectangle","save"),("act","GitHub Actions","rectangle","cpu"),
  ("build","Hugo build","rectangle","package"),("dep","Deploy to Pages","rectangle","server"),
  ("cdn","Served from CDN","cloud","storage")],
  edges=[("push","act"),("act","build"),("build","dep"),("dep","cdn")]),
# The diagram pipeline itself, for the build writeup. Shapes stay in the same
# vocabulary as everything else: rectangle for a process, cylinder for something
# stored on disk. The middle two are where the non-obvious work happens — the
# layout engine and the three post-processes that fix what it gets wrong.
"07-diagram-pipeline": dict(dirn="down", nodes=[
  ("md","Markdown","rectangle","save"),
  ("gen","Generator","rectangle","cpu"),
  ("d2","D2 layout","rectangle","sliders"),
  ("fix","Three fixes","rectangle","shield"),
  ("svg","Committed SVG","cylinder","storage"),
  ("page","Static page","cloud","monitor")],
  edges=[("md","gen"),("gen","d2"),("d2","fix"),("fix","svg"),("svg","page")]),
}
THEME={"light":dict(fill="#FFF3E4",stroke="#CE651B",ink="#241005",edge="#C24E0C",
                    icons="assets/icons/light",fs=20),
      "dark" :dict(fill="#2D1608",stroke="#CE651B",ink="#FFF7ED",edge="#FF8C2E",
                    icons="assets/icons/dark", fs=20)}
# A node's group may override fill/stroke so the two halves of a before/after
# diagram are told apart by the drawing itself. These are the same hue family as
# the node palette, one step apart, so the figure still reads as one system
# rather than two colour-coded halves. A dashed stroke marks the half that is
# being replaced; the replacement half is solid, so the handover is visible
# without needing a caption to explain it.
GROUP_STYLE={
  "retired":  dict(dash=True,  stroke="#B4541B"),
  "current":  dict(dash=False, stroke="#CE651B"),
  "handover": dict(stroke="#B4541B"),
}
# The retired half is also dimmed by fill. Light and dark need different
# values: a light-mode fill is unreadable on the espresso surface, so each
# theme carries its own. `fill` here is "how much this node recedes", not a
# brand colour.
GROUP_FILL={"light":dict(retired="#F6E7D6", current="#FFF3E4"),
            "dark" :dict(retired="#3A1C0A", current="#2D1608")}
# Dashed borders are the convention for "being replaced"; the replacement half
# stays solid so the handover reads without a caption.


def open_icon_label_gap(svg_text, gap=15.0):
    """Give the icon real clearance from the label above it.

    Measured on a rendered node: shape 85x102, label baseline y=25, icon spans
    y=29.5..72.5 — a ~4.5px gap, with ~29px of EMPTY space already inside the
    shape below the icon. So the box is big enough; the icon is simply placed
    too high. D2 offers no control for this (icon.near moves it but does not
    reflow, style/shape width+height are rejected or inert, and icon size is
    normalised regardless of source), so it is fixed where the geometry lives:
    drop each <image> by whatever the current gap is short of `gap`.

    The shape is never resized, so borders, corner radius and edge routing are
    untouched."""
    labels = [(float(m.group(1)), float(m.group(2)))
              for m in re.finditer(r'<text[^>]*x="([-\d.]+)"[^>]*y="([-\d.]+)"', svg_text)]
    def per_image(m):
        tag = m.group(0)
        iy = float(re.search(r'y="([-\d.]+)"', tag).group(1))
        ix = float(re.search(r'x="([-\d.]+)"', tag).group(1))
        above = [ly for lx, ly in labels if abs(ly - iy) < 90 and abs(lx - ix) < 90]
        if not above:
            return tag
        drop = max(0.0, gap - (iy - max(above)))
        if drop == 0.0:
            return tag
        return tag.replace('y="%s"' % re.search(r'y="([-\d.]+)"', tag).group(1),
                           'y="%s"' % (iy + drop), 1)
    return re.sub(r'<image\b[^>]*>', per_image, svg_text)

def strip_backdrop(svg_text):
    """Remove D2's opaque full-canvas white rect.

    D2 renders for a white page, so the first element of every output is
    `<rect x="-41" y="-41" width="…" height="…" fill="#FFFFFF" …/>` covering the
    whole canvas. Left in place it is a white panel behind the figure — a
    glaring white block in dark mode, and a visible seam against the themed
    figure surface in light mode. Deleting it lets the figure inherit the page
    background, which is what `background: var(--vm-card-dark)` on
    .vm-figure--diagram is for.

    Only rects that are BOTH pure white AND the canvas backdrop are touched:
    the pattern requires fill="#FFFFFF" and class=" fill-N7" (D2's canvas
    neutral), so a node that happened to be filled white would not match, and
    the per-file count is asserted by the caller."""
    out, n = re.subn(r'<rect[^>]*fill="#FFFFFF"[^>]*class=" fill-N7"[^>]*/>', "", svg_text)
    return out, n

def inline_icons(svg_text):
    """Embed each icon's bytes as a data URI so the SVG is self-contained.

    D2 writes `<image href="assets/icons/light/cloud.svg" …>`, a path relative
    to the .d2 source. After publishing at /diagrams/<name>.svg the browser
    resolves that to /diagrams/assets/icons/… → 404. The failure is silent and
    partial: shape, border, radius and label still render, so the figure looks
    almost right with its icons missing. Inlining the bytes is also simply
    correct for an <img> — an SVG loaded as an image cannot fetch siblings.
    Geometry (x/y/width/height) is left exactly as D2 computed it."""
    def sub(m):
        tag = m.group(0)
        path = re.search(r'href="([^"]+)"', tag).group(1)
        if path.startswith("data:"):
            return tag
        with open(path, "rb") as fh:
            uri = "data:image/svg+xml;base64," + base64.b64encode(fh.read()).decode("ascii")
        return tag.replace('href="%s"' % path, 'href="%s"' % uri, 1)
    return re.sub(r'<image\b[^>]*/>', sub, svg_text)

def _node(k,label,shape,role,t,th,group=None):
    st=GROUP_STYLE.get(group or "",{})
    fill=GROUP_FILL[th].get(group or "",t["fill"])
    L=[f'{k}: "{label}" {{', f'  shape: {shape}', f'  icon: {t["icons"]}/{role}.svg',
       f'  style.fill: "{fill}"', f'  style.stroke: "{st.get("stroke",t["stroke"])}"',
       f'  style.font-color: "{t["ink"]}"', f'  style.font-size: "{t["fs"]}"',
       '  style.border-radius: 10']
    if st.get("dash"): L += ['  style.stroke-dash: 3']
    L += ['}']
    return L

def src(d,t,th):
    L=[f"direction: {d['dirn']}","vars: {","  d2-config: {","    pad: 40","    layout-engine: dagre","  }","}"]
    g_of=d.get("group_of",{})
    for k,label,shape,role in d["nodes"]:
        L += _node(k,label,shape,role,t,th,g_of.get(k))
    for a,b in d["edges"]:
        # The handover edge (retired half -> current half) is the one that
        # carries the meaning, so it takes the accent stroke. Edges inside a
        # half stay on the normal edge colour.
        handover = g_of.get(a)=="retired" and g_of.get(b)=="current"
        edge=GROUP_STYLE["handover"]["stroke"] if handover else t["edge"]
        L += [f'{a} -> {b}: {{', f'  style.stroke: "{edge}"', '  style.stroke-width: 2', '}']
    return "\n".join(L)

GAP=15.0
# Layout budget, used only to self-check the result. MEASURE_PX is the width a
# diagram gets inside the article (68ch measure, ~566px in CSS px at the prose
# size) and FS is the node label size authored below. A figure wider than
# MEASURE_PX is scaled down by the browser, so these two numbers together give
# the label size a reader actually sees.
MEASURE_PX=566.0
FS=20
# Below this, node labels stop being comfortably readable. 15px is a judgement
# call, not a standard: it is roughly where 20px source text stops reading as
# body copy. The resulting width ceiling is MEASURE_PX*FS/FS_MIN = 755px.
FS_MIN=15.0
os.makedirs(OUT, exist_ok=True)
bad=0
for name,d in DIAGRAMS.items():
    for th,t in THEME.items():
        f=f"/tmp/{name}.{th}.d2"; o=f"{OUT}/{name}.{th}.svg"
        open(f,"w").write(src(d,t,th))
        r=subprocess.run(["d2","--layout=dagre",f,o],capture_output=True,text=True)
        ok=os.path.exists(o); ar=""; n=0; probs=[]
        if ok:
            sv=open(o,encoding="utf-8").read()
            sv=open_icon_label_gap(sv,GAP)
            sv,backdrops=strip_backdrop(sv)
            sv=inline_icons(sv)
            open(o,"w",encoding="utf-8").write(sv)
            # Self-check: a post-process that silently no-ops is exactly how the
            # white-panel and missing-icon bugs shipped in the first place, so
            # every invariant is asserted here rather than eyeballed later.
            if backdrops!=1: probs.append(f"backdrop x{backdrops} (want 1)")
            if 'href="assets/' in sv: probs.append("EXTERNAL icon href survived")
            if 'fill="#FFFFFF"' in sv: probs.append("white fill left")
            m=re.search(r'viewBox="([^"]+)"',sv)
            if m:
                _,_,w,h=m.group(1).split()
                w=float(w); ar=f"AR {w/float(h):.2f}"
                # Width is the axis that hurts, not height. CSS fits every
                # diagram to the article measure (max-width:100%), so a figure
                # wider than that is scaled down rather than scrolled, and its
                # labels shrink with it. Flag any figure whose labels would
                # land under FS_MIN there, while it is still cheap to fix,
                # rather than discovering it as 4.7px text on the live page.
                if w>MEASURE_PX:
                    eff=FS*MEASURE_PX/w
                    if eff<FS_MIN:
                        probs.append(f"{int(w)}px wide -> labels {eff:.1f}px at the "
                                     f"{int(MEASURE_PX)}px measure (floor {FS_MIN}px; "
                                     f"keep under {int(MEASURE_PX*FS/FS_MIN)}px)")
            n=sv.count('data:image/svg+xml;base64,')
            if n!=len(d["nodes"]): probs.append(f"icons {n}/{len(d['nodes'])}")
        else:
            bad+=1
        flag="ok" if ok and not probs else ("FAIL" if not ok else "CHECK")
        print(f"  {name:22s} {th:6s} {flag:5s} {os.path.getsize(o)//1024 if ok else 0:3d}KB "
              f"{ar:9s} icons={n}"
              + (("  "+", ".join(probs)) if probs else "")
              + ("" if ok else "  "+r.stderr.strip()[:90]))
if bad: sys.exit(1)
