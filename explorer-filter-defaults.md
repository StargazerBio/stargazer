---
title: Explorer filters, and a default filter each user picks
status: doing
priority: normal
created: 2026-10-26
blocked_by:
  - unified-asset-explorer
---

Once everything but the workspace is in the explorer (ticket
`unified-asset-explorer`), finding things is the explorer's whole job. Its
filters become fast and direct: search as you type, types and sources as
toggles with counts, and keyvalue filters picked straight from an entry.
Each user can save the filter they want to land on as their default, and
change or clear it in Settings (ticket `dashboard-header-controls`).

## Current State

- `_assets.html` has three inputs, Asset Type, Key and Value, and a Filter
  button. They set `asset=` and one `key=value` on `GET /assets/list`, so
  every change is a round trip, and only one keyvalue filter at a time.
- There is no text search, and nothing remembers a filter across reloads.
- The user's settings are `settings.json` beside their workspace
  (`app/workspace_store.py` `get_settings`), holding the save interval.

## Target State

**The filter** is one object, held by the page and stored as a default:

```json
{"sources": ["mine", "stargazer"], "types": ["notebook", "alignment"],
 "keyvalues": {"sample_id": "NA12829"}, "text": "chr22"}
```

- **Sources** pick what's fetched, so changing them is a request. The rest
  filters the loaded entries in the browser, instantly.
- **Search** matches as you type, case-insensitively, against an entry's
  name, title, description, keyvalue values and CID prefix.
- **Types** are toggle chips, one per type present in the loaded entries,
  each with its count. None selected means every type.
- **Keyvalues** are removable chips, ANDed. A keyvalue on the detail card
  has a "filter by this" control that adds it; a Key/Value pair can still be
  typed in.
- A **Clear** control returns to the user's default, and the result count
  shows beside the filters ("42 of 310").

**Defaults.** "Save as default" stores the current filter as
`explorer_default` in the user's `settings.json`. The page loads with it.
Without one, the built-in default is Mine and Stargazer with nothing else
set. The Settings modal shows the saved default in words ("Mine, Stargazer;
notebook, alignment; sample_id = NA12829; 'chr22'") with Reset to the
built-in default.

**A stored default that no longer fits** is applied as far as it can be: a
source that isn't offered (Public with public assets off) is dropped, and a
type with no entries keeps its chip at a count of 0, so the user sees why
the view is empty.

## Implementation Plan

### Phase 1: The stored default

1. `app/workspace_store.py`: `explorer_default` in the settings, read with
   the built-in default when missing.
2. `POST /settings/explorer-default` takes the filter as JSON; it's checked
   (known sources, string types and keyvalues, text up to 200 characters)
   and 400s otherwise, writing nothing. `DELETE` resets it.
3. `dashboard()` passes the default to the page.
4. Tests: no file → the built-in default; a saved filter reads back equal;
   an unknown source 400s and the stored default is unchanged; `DELETE`
   brings back the built-in default.

### Phase 2: The filter bar

1. `_assets.html`: the filter object in the page's `state` in place of
   `state.filters`; the search box, source and type chips with counts,
   keyvalue chips, Clear, the result count, Save as default.
2. "Filter by this" on each keyvalue in the detail card.
3. The graph and list views render the filtered entries; the graph's legend
   becomes the type chips in ticket `constellation-graph`.

### Phase 3: Settings, docs and verification

1. The default's summary and Reset in the Settings modal.
2. Docs: `docs/architecture/app.md` (the explorer's filters and the stored
   default) and `app_internals.md` (the route and the settings key).
3. Verify on the test account's Union dashboard in the built-in browser:
   typing narrows the list on each keystroke with no request in the network
   log; type chips' counts match the list; filter by this from a detail card;
   save a default, reload and it's applied; Reset in Settings, reload and
   the built-in default is back. Tear down after.

## Design Decisions

1. **Filter in the browser, fetch by source.** The listing for a set of
   sources is already loaded for the graph, so search and chips filter it
   without a round trip. Measure the public tier's listing size first: if it's
   too big to load whole, its type and keyvalue filters go to the server.
2. **One default, not named presets.** One saved filter answers "where do I
   land". Presets wait until someone asks for them.
3. **The default lives with the other settings**, in `settings.json`, so it
   follows the user across browsers and survives the dashboard scaling to
   zero. Browser storage would do neither.
