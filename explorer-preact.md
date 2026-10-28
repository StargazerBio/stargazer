---
title: Asset explorer on Preact and htm
status: backlog
priority: normal
created: 2026-10-27
---

The asset explorer's script (`app/templates/_assets.html`, ~1,280 lines
inline) keeps its state in one `state` object by hand and redraws the filter
bar, list, tooltip and detail card by assigning `innerHTML` strings, with
every interpolated value passed through `esc()`. One missed `esc()` is an
XSS hole, and every new control means another hand-written redraw. Move the
explorer onto Preact components written with htm's tagged templates: values
in `${}` are text, never parsed as HTML, so escaping is no longer something
to remember, and a state change re-renders only what changed. No build step:
Preact, its hooks and htm are vendored ES modules served from `/static`, like
`force-graph.min.js`.

Only the explorer moves. The dashboard's own script (`dashboard.html`: delete,
publish, the gear and Settings modals), `app/static/launch.js` and base's
starfield act on server-rendered markup or a canvas and stay vanilla. They
get their own ticket if they outgrow that.

## Current State

- `_assets.html` is three macros, `style()`, `panel()` and `script()`.
  `script()` is two inline `<script>` blocks: the Jinja values
  (`USERNAME`, `WORKSPACE_ON`, `TUS_MAX_BYTES`, `TUS_CHUNK_BYTES`,
  `EXPLORER_DEFAULT`, the Settings summary's `settings.explorer_default`)
  written straight into JS, then the explorer.
- Renderers that build HTML strings: `renderFilterBar` (type and keyvalue
  chips), `renderList`, `showGraphTip`, `renderDetail`, `detailHead`,
  `detailCid`, `renderNotebookDetail`, `renderDetailEditor`, `kvEditRow`,
  `populateTypeControls`, `renderTypedFields`, `addKvRow`. Click handling is
  delegated through `data-*` attributes (`data-goto`, `data-edit`,
  `data-filter-key`).
- The graph is force-graph on a canvas (`createGraph`, `paintNode`,
  `graphElements` and the forces), driven imperatively from `state.visible`.
- Notebook cards render a `.launch-group` that `launch.js` then mutates
  (Edit/Run → Open/Stop, the build watch) and re-hydrates on every card
  render via `hydrateLaunches(card)`.
- Upload is `doUpload` → tus-js-client, with progress written into the panel.
- `.claude/reference/architecture/app_internals.md` → Template describes the
  page JS as "dependency-free vanilla" and force-graph as the one exception
  to shipping only hand-written JS.

## Target State

- `app/static/explorer.js`, an ES module loaded with
  `<script type="module">`. The template keeps the markup shell (`panel()`)
  and the CSS (`style()`), and passes its values in one
  `<script type="application/json" id="explorer-boot">` block the module
  reads, so no Jinja is interpolated into JS.
- `app/static/vendor/`: `preact.module.js`, `hooks.module.js`, `htm.module.js`
  and their licenses, pinned, with an import map in `base.html` mapping
  `preact` and `preact/hooks` to them (the hooks module imports `preact` by
  bare name).
- Components: `Explorer` (owns the state with hooks: `filter`, `view`,
  `records`, `selected`, `editing`, `schema`; `visible` is derived), and under
  it `FilterBar`, `AssetList`, `GraphView`, `GraphTip`, `DetailCard` (with
  `NotebookCard` and `MetadataEditor`) and `UploadPanel`. Event handlers are
  props, so the `data-*` delegation goes.
- `GraphView` is a thin wrapper: a ref'd host div, force-graph created once in
  an effect, and fed `graphData` when `visible` changes. The simulation, the
  painter, hover, pinning and the exit animation keep their current code and
  constants; only how they read state changes.
- The notebook card's launch group is a component that renders the
  `.launch-group` markup once per entry (keyed by `entryKey`) and calls
  `hydrateLaunches` in an effect. Preact doesn't re-render that subtree, so
  `launch.js` can keep mutating it and its build-watch handoff still works.
- `esc()` and every `innerHTML` assignment are gone from the explorer.
- Behavior is unchanged: same filters, counts, graph, card, editing, upload
  and launch.

## Implementation Plan

### Phase 1: vendor and boot

1. Fetch pinned Preact (10.x, with `hooks`) and htm 3.x ESM builds and their
   `LICENSE`s from jsdelivr into `app/static/vendor/`. Use releases at least
   two weeks old.
2. Add the import map to `base.html` before any module script:

   ```html
   <script type="importmap">
   {"imports": {"preact": "/static/vendor/preact.module.js",
                "preact/hooks": "/static/vendor/hooks.module.js",
                "htm": "/static/vendor/htm.module.js"}}
   </script>
   ```

3. Replace the Jinja-in-JS constants with the boot block:

   ```html
   <script type="application/json" id="explorer-boot">
   {{ {"username": username, "workspace_on": workspace_configured,
       "tus_max_bytes": tus_max_bytes, "tus_chunk_bytes": tus_chunk_bytes,
       "explorer_default": explorer_default,
       "saved_default": settings.explorer_default} | tojson }}
   </script>
   <script type="module" src="/static/explorer.js"></script>
   ```

   `tojson` escapes `<`, `>` and `&`, so a value can't close the script tag.
4. Check that `_RevalidatingStatic` serves `.js` as `text/javascript`, which
   module scripts require.

### Phase 2: port the explorer

Port renderer by renderer into components, deleting each string renderer as
its component lands. The pure helpers (`matches`, `assetType`, `owner`,
`entryKey`, `linkTarget`, `relKeys`, `displayName`, `downloadUrl`, the hue
assignment) move over as plain functions.

```js
const AssetRow = ({ r, selected, mine, onSelect }) => html`
  <tr class=${[selected && "selected", mine && "mine"].filter(Boolean).join(" ")}
      onClick=${() => onSelect(entryKey(r))}>
    <td>${displayName(r)}</td>
    <td><span class="badge src">${SOURCE_LABEL[r.source]}</span></td>
    <td>${mine ? html`<span class="badge owner-me">${owner(r)}</span>` : owner(r)}</td>
    <td><span class="badge type">${assetType(r)}</span></td>
    <td><a class="btn btn-muted" href=${downloadUrl(r)}>Download</a></td>
  </tr>`;
```

Order: list and filter bar first (the simplest round trip through state),
then the detail card and editor, then the graph wrapper and tooltip, then
upload, then the notebook card's launch group.

### Phase 3: docs

Rewrite `app_internals.md` → Template: the module, the vendored libraries
and how to update them, the boot block, the component tree, and the
launch-group boundary with `launch.js`. Update `app/templates.py`'s
docstring where it describes the asset panel. Check `docs/architecture/app.md`
for anything that names the explorer's mechanics (it currently doesn't).

## File Changes

| File | Changes |
|------|---------|
| `app/templates/_assets.html` | `script()` becomes the boot block and the module tag; `panel()` keeps only the mount points; `style()` unchanged |
| `app/static/explorer.js` | New: the explorer as Preact components |
| `app/static/vendor/*` | New: Preact, hooks, htm and licenses |
| `app/templates/base.html` | The import map |
| `app/templates.py` | Docstring |
| `.claude/reference/architecture/app_internals.md` | Template section |

## Design Decisions

1. Only the explorer moves. It's the one script that builds markup from data
   and keeps real state; the rest acts on server-rendered markup.
2. Vendored, not loaded from a CDN at runtime: the explorer works on the
   devbox and doesn't break if a CDN does, and it follows force-graph's
   pattern.
3. htm, not JSX: no build step and no Node in the repo.
4. force-graph stays imperative behind a ref. Its simulation is the
   explorer's most tuned code and Preact has nothing to add to a canvas.
5. The launch group is a boundary Preact renders once and leaves to
   `launch.js`, rather than porting `launch.js`, which the workspace tiles
   share.

## Verification

There are no JS tests, and a test harness for one page would be more
machinery than the change. Drive the explorer before and after in the
built-in browser on the devbox dashboard, and again on the tenant as the test
account (`verify-stargazer`). `tests/unit/test_assets_routes.py` and the
dashboard render tests must still pass.

## Verification recipe

On the dashboard, with Mine, Public and Stargazer entries loaded:

1. Toggle each source; the listing refetches and the type chip counts match.
2. Type in search; the graph pulses and the list narrows per keystroke.
3. Toggle type chips and add a keyvalue with "filter by this"; Clear returns
   to the saved default.
4. Switch Graph ⇄ List; the selection carries over.
5. Hover and click a star: tooltip, fly-to, the detail card, linked-asset
   chips that select their target.
6. Edit metadata on an owned record, save, and see it refetched; a non-owned
   record shows no Edit.
7. Upload a small file with keyvalues; progress shows and it appears.
8. Open a built-in notebook's card, launch it, watch it go to Open/Stop,
   change the filter so the card re-renders, and Stop it.
9. Create an asset whose name is `<img src=x onerror=alert(1)>`; it shows as
   text everywhere (list, tooltip, card).
10. The console shows no errors; `grep -n 'innerHTML\|esc(' app/static/explorer.js`
    finds nothing.
