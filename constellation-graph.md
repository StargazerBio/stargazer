---
title: The asset graph as a living constellation
status: done
priority: normal
created: 2026-10-26
pr: 97
---

The explorer's graph should be the part of the dashboard people enjoy:
beautiful at rest, alive under the pointer, and responsive to every filter
change without jumping. Today it's a static layout that's recomputed from
scratch on each change. Redraw it as a constellation: assets are stars,
provenance links are the lines between them, and the whole thing moves with
real physics.

Waits on ticket `explorer-filter-defaults`, whose filter state the graph
reacts to and whose type chips become its legend.

## Current State

`app/templates/_assets.html` draws the graph with Cytoscape
(`/static/cytoscape.min.js`) on a 420 px canvas:

- Nodes are uniform translucent violet circles sized by degree, with an
  ellipsized mono label; the user's public records get a green border.
- Edges are `*_cid` and `companion_of` links between records in view, with
  arrows.
- The layout is `cose`, run with `animate: false`. Every filter change
  removes every element, adds the new ones and reruns the layout, so the
  picture jumps.
- Hovering lights a node's neighbors and shows a tooltip, clicking opens the
  detail card, and double-clicking fits the view. There's no physics after
  layout, no color by type, no legend, and a 150-node cap (`NODE_CAP`).

## Target State

**The look.** A night-sky canvas with a faint starfield.

- **Nodes are stars**: a bright core with a soft glow, the core's size from
  the node's degree. Hue comes from the asset type, from one categorical
  palette shared with the type chips. Notebooks are drawn as four-point star
  glyphs, so they read as a different kind of thing.
- **Ownership** shows as brightness: the user's own entries burn at full
  strength, public ones are dimmer, and shipped notebooks carry a thin ring.
- **Links** are thin, low-alpha constellation lines. Slow particles drift
  along each one from the derived asset to its source, which shows
  provenance without arrowheads.
- **Labels** fade in with zoom, so the zoomed-out view is clean and a close
  view is readable.

**The feel.**

- **Live physics.** Dragging a star pulls its neighbors after it, and the
  graph settles when it's let go. Same-type stars gather gently around a
  shared anchor, so unlinked records cluster instead of scattering, and
  collision keeps labels apart.
- **Focus on hover.** The hovered star, its neighbors and its links stay
  lit; everything else dims, with a quick fade. The tooltip shows as now.
- **Fly to on click.** Clicking centers and zooms on the star with a smooth
  transition and opens the detail card. Selecting a row in the list view
  selects the same star, and the reverse.
- **Filters animate.** Entries that drop out of a filter shrink and fade;
  new ones appear beside a linked star (or their type's anchor) and grow in.
  Stars that stay keep their place, and the simulation reheats only a little,
  so the picture never jumps.
- **Search lights up.** While the user types in the search box, matching
  stars pulse and the rest dim.
- **The legend is the type chips.** Hovering a chip lights that type's stars;
  clicking it toggles the type, as in the filter bar.
- Double-clicking the background flies back to fit everything.

**Restraint.**

- Under `prefers-reduced-motion`, the particles, starfield drift and
  transitions are off, and the physics settles at once.
- Once the graph settles and nothing is hovered, it stops redrawing, so an
  idle dashboard costs no CPU.
- Touch works: drag to pan, pinch to zoom, tap to select.

## Implementation Plan

### Phase 1: The renderer

1. Swap Cytoscape for `force-graph` (vasturiano, MIT), vendored into
   `app/static/` at an exact version, as Cytoscape is now. It draws to a 2D
   canvas on `d3-force`, with per-node custom painting
   (`nodeCanvasObject`), directional link particles, animated `centerAt`,
   `zoom` and `zoomToFit`, access to the forces, and redraws that stop once
   the graph is idle. Remove `cytoscape.min.js`.
2. Rebuild `graphElements` as `{nodes, links}`, keeping node objects
   between renders so positions survive a filter change.
3. Port the existing behavior first (hover, the tooltip, click to select,
   double-click to fit, the detail card), so the swap alone is complete.

### Phase 2: The look

1. Use the `frontend-design` and `dataviz` skills. Pick the categorical type
   palette with the `dataviz` validator against the page's `--bg`, and put
   it in one place that the chips read too.
2. Star and notebook painting, glow, ownership brightness, labels that fade
   with zoom, the starfield, link particles.

### Phase 3: The feel

1. Forces: per-type anchors on a ring (weak `forceX`/`forceY`), `forceCollide`
   sized to node and label, and link distance by link kind.
2. Hover focus and dimming, fly-to on click, list↔graph selection, search
   pulse, legend hover and toggle.
3. Enter and exit transitions on filter changes, and a gentle reheat.
4. Reduced motion, idle redraw stop, touch.

### Phase 4: Scale, docs and verification

1. Measure frame rate while dragging at 150, 500 and 1,000 nodes (seeded
   test store, built-in browser), and raise `NODE_CAP` to the largest size
   that holds a smooth drag. Record the numbers in this ticket.
2. Docs: the Graph paragraph of `docs/architecture/app.md`, and the
   graph mechanics in `app_internals.md`.
3. Verify on the test account's Union dashboard in the built-in browser:
   screenshots at rest, on hover and with a node selected; a recording of a
   drag and of a filter change; CPU idle after it settles (Performance
   panel); reduced motion emulated; a phone-width screenshot. Tear down
   after.

## Design Decisions

1. **`force-graph` over tuning Cytoscape.** What the graph lacks is continuous
   physics and custom painting. Cytoscape's layouts compute a picture and
   stop, and its nodes are styled shapes; `force-graph` is a running
   simulation with a canvas hook for each node. It's also lighter for this
   one job.
2. **2D, not 3D.** A 3D graph is a spectacle, but it's harder to read and
   to click on. The constellation look carries the delight in 2D.
3. **Color is type, brightness is ownership.** Two independent things the
   user filters on get two channels that don't fight.
4. **Positions survive filters.** A user who narrows a filter should see the
   same sky with fewer stars, not a new one.

## Progress

- [x] Phase 1: force-graph 1.52.0 vendored, Cytoscape removed, `{nodes, links}` with node objects kept across renders, hover, tooltip, click, double-click fit and the detail card ported.
- [x] Phase 2: `TYPE_HUES` (dataviz reference dark categorical order, validated adjacent-pairs against `#0d1117`: all checks pass; all-pairs fails for any 4+ hues, so labels, tooltip and the chip legend are the secondary encoding), shared with the type chips as a swatch; star glow and core, ownership brightness, notebook four-point glyph, Stargazer ring, labels fading in with zoom, static CSS starfield, link particles.
- [x] Phase 3, part: type anchors on a ring, collision, link distance by kind; hover focus and dimming (instant, no fade); fly-to on click; list↔graph selection through `state.selected`; legend hover (chip click already toggles the type); new stars placed beside a linked star or their type's anchor and grown in; reduced motion (warmup layout, no particles, growth or transitions); idle redraw stop.
- [x] Phase 3, rest: search pulse; exit shrink-and-fade; filter changes pin the stars that stay while new ones settle (force-graph's centering force removed); hover and legend dimming fade over 160 ms.
- [x] Pointer interactions driven locally with the pane in front: hover focus and tooltip, click fly-to and card, drag, double-click fit, legend hover, list↔graph selection, tap at phone width.
- [x] Phase 4, local: frame rate at 150/500/1,000; `NODE_CAP` raised to 1,000; idle paints; reduced motion; phone width.
- [x] Union: the recipe's step 4 on the test account's dashboard at `e736465`, then `bf60831` after the hue fix it turned up.

Choices: a filter change pins the stars that stay (`fx`/`fy`) while new ones settle and frees them when the engine stops, rather than a gentler reheat: with a reheat alone, even with the centering force gone and a fast cooling, the stars that stayed moved a median of 56–93 graph units. Search narrows the entries, so its pulse is a ring on the stars that remain; the dimming of non-matches is their exit fade. A hovered star's neighbors are labeled only from zoom 0.8, since a hub's labels pile up when zoomed out. The camera doesn't move on a filter change; double-click fits. Particles run only on the hovered or selected star's links, so an idle graph with nothing selected stops redrawing. The starfield is a static CSS background (no drift). The layout settles after 400 ticks rather than force-graph's 15 s timer, since a throttled tab otherwise freezes a half-done layout. Hues go to the types with the most loaded entries (ties by name), so the gray past the eighth falls on the rarest. `companion_of` links are 28 long, so a primary file's companions keep their labels apart.

## Verification recipe

1. Locally: serve the dashboard with a fake Pinata listing of N linked public records (a short script that sets `app.assets._pinata_client` to a fake whose `query` returns the records, with `SG_OWNER_SUBJECT`/`SG_STAND_IN_SUBJECT` set, then `uvicorn.run(app.admin_app.asgi_app)`), open it in the built-in browser, press Public.
2. Check: `fg.graphData()` node and link counts; screenshot at rest; hover a star (neighbors lit, tooltip); click it (card opens, view flies to it).
3. Idle: wrap the painter with a counter (`fg.nodeCanvasObject((...a) => (n++, paintNode(...a)))`), wait for the engine to stop, and count paints over 3 s with nothing hovered or selected: expect 0.
4. On Union: `union_dashboard.py deploy`, open the test account's dashboard, repeat 2 on real records, then `union_dashboard.py teardown`.

The built-in browser pane runs no animation frames while it's hidden, so the simulation only advances while it's shown or screenshotted.

### Evidence

- Local, 150 synthetic records (measured): 150 nodes and 159 links drawn; stars hued by type with labels at zoom; after settling, 0 paints in 3 s idle; no console errors. With the earlier position-based collision the minimum star spacing ended at 0.005 (stacked); with velocity-based collision it measured 5.2 after a settle.
- Union, test account dashboard at `49c6d3c` (measured): force-graph loaded, 84 entries (Mine + Stargazer) drawn as 84 stars with 39 links across 20 types; the first eight types hued, the other twelve gray; screenshot at rest shows type clusters and links. Hover and click could not be driven: the built-in browser pane was hidden, so it ran no animation frames, and force-graph detects the pointer in its frame loop. Torn down: `stopped: ['dashboard']`, live runs `[]`, all 7 apps in `u-pryce` STOPPED.
- Local, branch head `e736465`, pane in front (measured):
  - Hover on the 26-link hub: 27 stars lit, 123 dimmed, tooltip "GRCh38_1.fa", pointer cursor. Legend hover on `variants`: 28 lit, 122 dimmed, the fade 0 → 1 in about 140 ms.
  - Click: `state.selected` the hub, view centered on it exactly, zoom 2.5, card open. Double-click on the background: zoom 2.2 → 0.39, all 150 stars in view.
  - Drag of `S18.bam` (before the fix): it moved and its neighbors stayed put (0.0), because `d3AlphaMin` stopped the engine before force-graph's drag reheat. After: neighbors moved 154, 265 and 184 units with it, the graph settled, then 0 paints in 3 s.
  - Filter changes `S1`, clear, `bam`, clear, `GRCh38_1`: the stars that stayed moved 0 units every time (before: median 227 with the centering force, 56–93 without), and no star was left pinned. `S1` from 150: 125 stars fading at 200 ms, 25 in the data by 600 ms. Pulse rings on the matching stars at 200 ms, gone by 1.7 s. A narrow and a clear: about 60 frames painted in the first 500 ms, then 0 paints in 3 s idle, `autoPauseRedraw` back on.
  - Frame rate under a running simulation (the per-frame work of a drag): 150 stars 120 fps (p95 frame 10.2 ms), 505 stars 120 fps (9.0 ms), 1,000 stars 120 fps (10.3 ms; display refresh 120 Hz). 1,000 stars run 120 ticks/s and a full layout settles in 3.35 s. `collideForce` at 1,000: 2.2 ms a tick. The 1,000-star fit was clamped by `minZoom` 0.2 (it needs 0.15), so `minZoom` is 0.05.
  - Reduced motion (the page in an iframe with the media query forced true): no star moved between 2.5 s and 4 s after the fetch, dimming instant (128 dimmed at once), particles 0, no exit ghosts, `FLY_MS` 0.
  - Phone (375 × 812): `scrollWidth` 375, a tap on the hub selected it and flew to zoom 2.5.
  - List → graph: selecting the `S18.bam` row and switching to Graph left it selected with its 3 links hot and its card open.
  - Unit tier: 560 passed.
- Union, test account `u-pryce`, built-in browser, pane in front (measured):
  - At `e736465`: 84 entries (Mine + Stargazer) as 84 stars and 39 links over 20 types. Hover on `GRCh38_TP53.fa` (8 links): 9 lit, 75 dimmed, tooltip shown. Click: selected, centered exactly (offset 0), zoom 2.5, card open. Drag of `NA12829_aligned.bam`: it moved 82 units, its R1 followed 13 and the reference 2; settled, then 0 paints in 3 s and no star left pinned. Searches `TP53`, clear, `NA12829`, clear: 10 and 11 of 84; 74 and 73 stars fading at 250 ms; the stars that stayed moved 0; no request to the dashboard.
  - Two flaws found there: hues went to the first eight types by name, so 44 of 84 stars were gray, `notebook`, `reference` and `variants` among them; and the reference's index companions, 14 units out, had overlapping labels at zoom 2.5.
  - At `bf60831` (hues by count, companions 28 out): `notebook` hued; 15 of 84 gray; `.fai` and `.dict` labels clear of the reference at zoom 2.5. The five aligner-index files still crowd a little at that zoom and part further in.
  - Torn down: `stopped: ['dashboard']`, `live runs: []`; all 7 apps in `u-pryce` STOPPED; no running runs in `u-pryce` or `flytesnacks`.
- Code review fixes at `2638fe5`, local, 150 and 1,000 stars (measured; the pane was hidden, so checks read state rather than frames):
  - Particles: force-graph works them out only when the data or their accessor is set. Before the fix, hovering or selecting the 26-link hub gave 0, and one stayed after deselecting. Now hover and select give 26, and unhover and deselect give 0.
  - A drag's settle while a slowed listing loads doesn't zoom, and a failed fetch leaves no fit pending. A fetch landing mid-settle (60 pinned, decay 0.08) frees them all and restores decay 0.0228 over 400 ticks.
  - A hover inside a search pulse keeps the redraw running through the pulse (still on at 500 ms, off by 1,200). A fade at 15 fps reaches full dim in 3 frames (0.42, 0.84, 1).
  - Reduced motion at 1,000 stars, timed from the first warmup tick to the last: a keystroke blocked 3.5–4.3 s and now blocks 0.14–0.57 s. Collide went from all pairs to a grid and costs 0.83 ms a tick; d3's charge is 2.24 ms. A full layout and four filter changes leave 0 overlapping stars.
  - No page errors. Unit tier: 560 passed. Frame rate and drag were not rerun after these fixes.

## Outcome

Shipped in PR #97 (merge `5ba6985`): the explorer's graph redrawn as a constellation on force-graph 1.52.0 in place of Cytoscape. Stars hued by type from `TYPE_HUES` (shared with the type chips), brightness by ownership, notebook glyphs, labels fading with zoom, live physics with type anchors and grid collision, hover focus, fly-to on click, list↔graph selection, filter changes that pin the stars that stay, search pulse, particles on the focused star's links, no frames once idle, reduced motion and touch; `NODE_CAP` 1,000. Verified by the unit tier (560 passed), locally in the built-in browser at 150–1,000 stars, and on Union with the test account's dashboard at `e736465` and `bf60831` (the recipe above); frame rate and drag weren't rerun after the review fixes at `2638fe5`. Left: the aligner-index files around a reference crowd slightly at zoom 2.5; the camera doesn't move on a filter change; under reduced motion at 1,000 stars a keystroke still blocks for up to about half a second. No review comments.
