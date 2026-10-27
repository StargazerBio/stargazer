---
title: The asset graph as a living constellation
status: doing
priority: normal
created: 2026-10-26
blocked_by:
  - explorer-filter-defaults
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
- [ ] Phase 3, left: search pulse; exit shrink-and-fade for stars that drop out; a gentler reheat on filter changes than force-graph's default; hover fade.
- [ ] Pointer interactions not yet driven anywhere (hover focus, click to fly and open the card, drag, double-click fit): the browser pane was hidden, so force-graph got no animation frames. Drive them with the pane in front before the PR.
- [ ] Phase 4, left: frame-rate measurement at 150/500/1,000 and raising `NODE_CAP` (still 150); a drag and filter-change recording; Performance-panel CPU check; phone-width screenshot.

Choices: particles run only on the hovered or selected star's links, so an idle graph with nothing selected stops redrawing. The starfield is a static CSS background (no drift). The layout settles after 400 ticks rather than force-graph's 15 s timer, since a throttled tab otherwise freezes a half-done layout. Types past the eighth are gray.

## Verification recipe

1. Locally: serve the dashboard with a fake Pinata listing of N linked public records (a short script that sets `app.assets._pinata_client` to a fake whose `query` returns the records, with `SG_OWNER_SUBJECT`/`SG_STAND_IN_SUBJECT` set, then `uvicorn.run(app.admin_app.asgi_app)`), open it in the built-in browser, press Public.
2. Check: `fg.graphData()` node and link counts; screenshot at rest; hover a star (neighbors lit, tooltip); click it (card opens, view flies to it).
3. Idle: wrap the painter with a counter (`fg.nodeCanvasObject((...a) => (n++, paintNode(...a)))`), wait for the engine to stop, and count paints over 3 s with nothing hovered or selected: expect 0.
4. On Union: `union_dashboard.py deploy`, open the test account's dashboard, repeat 2 on real records, then `union_dashboard.py teardown`.

The built-in browser pane runs no animation frames while it's hidden, so the simulation only advances while it's shown or screenshotted.

### Evidence

- Local, 150 synthetic records (measured): 150 nodes and 159 links drawn; stars hued by type with labels at zoom; after settling, 0 paints in 3 s idle; no console errors. With the earlier position-based collision the minimum star spacing ended at 0.005 (stacked); with velocity-based collision it measured 5.2 after a settle.
- Union, test account dashboard at `49c6d3c` (measured): force-graph loaded, 84 entries (Mine + Stargazer) drawn as 84 stars with 39 links across 20 types; the first eight types hued, the other twelve gray; screenshot at rest shows type clusters and links. Hover and click could not be driven: the built-in browser pane was hidden, so it ran no animation frames, and force-graph detects the pointer in its frame loop. Torn down: `stopped: ['dashboard']`, live runs `[]`, all 7 apps in `u-pryce` STOPPED.
- Not yet verified on a shown pane: hover focus and tooltip, click fly-to and card, drag, filter-change animation, reduced motion, phone width.
