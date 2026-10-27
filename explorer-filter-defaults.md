---
title: Explorer filters, and a default filter each user picks
status: review
priority: normal
created: 2026-10-26
pr: 96
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

## Choices made in implementation

- The public tier's whole listing is 6 records, 1,704 bytes of JSON, read in
  0.34 s (measured 2026-10-27 with `PinataClient().query({})`; the tenant
  shows the same 6 public rows). It loads whole, and every filter but the
  sources runs in the browser.
- Only the dashboard's owner saves or resets the default: both routes 403 to
  a visitor who isn't the owner, and the page offers Save as default and the
  Settings section to the owner only.
- `dashboard()` fits the default to the visitor before the page sees it
  (`_fitted`): Mine is dropped for a non-owner, Public when public assets are
  off. Settings describes the saved default, unfitted.
- A type chip's count is the entries matching everything but the types.
- Keyvalue chips match the value exactly; a typed pair needs both a key and a
  value, and an empty value on a card has no "filter by this".
- A card's links resolve among the shown entries.
- `/assets/list` keeps its keyvalue params for other callers; the page no
  longer sends them.

## Verification recipe: Explorer filters and the saved default

The explorer narrows its loaded entries as you type or press a chip, with no
request; sources still fetch. The owner saves the filter as their default,
the page opens on it, and Settings shows it with Reset.

### Sub-features

- `ux-search`: each keystroke in the search box narrows the list; no
  dashboard request in the resource log.
- `ux-counts`: each type chip's count equals the list rows of that type.
- `ux-filter-by`: "filter by this" on a card's keyvalue adds a chip and
  narrows the list; the card stays.
- `ux-save`: Save as default, reload: sources, types, keyvalues and search
  are as saved, and Settings describes it.
- `ux-clear`: after changing the filter, Clear returns to the default.
- `ux-reset`: Reset in Settings, reload: Mine and Stargazer, nothing else.
- `ux-graph`: a keystroke that leaves the same entries keeps the graph's
  zoom and node positions.
- `ux-phone`: at 375 px, `scrollWidth <= innerWidth`.

### How to get to it (user POV)

Dashboard → Assets → the search box, type chips, Key/Value + Add, Clear and
Save as default under the source buttons; a row's card → "filter by this";
the header's ⚙️ → Settings → Reset to the built-in default.

### Driving it

Preconditions: the `verify-stargazer` Union tenant preconditions; the
built-in browser signed in to the console as the test account; the Union
lock held.

- **Deploy.** With infra's `tenant.env` exported, `union_dashboard.py deploy`; wait for the page's `.dash-version` to show the commit. Install the alert recorder.
- **Search (`ux-search`).** Note `performance.getEntriesByType('resource').length`, focus `#filter-text`, type one character per `computer type` call, recording `#filter-count` on each `input`. New resource entries on the dashboard's origin must be none (Union's analytics beacon is not the dashboard's).
- **Counts (`ux-counts`).** In List, compare `#type-chips .chip .n` with the rows' type badges.
- **Filter by this (`ux-filter-by`).** Open a stored record's card, click "filter by this" on `build`: a `build = …` chip, the count drops, the card stays.
- **Save (`ux-save`).** Press Public, a type chip, add search text, click Save as default: "Saved as your default." Reload and read the pressed sources, `#filter-text`, pressed chips and `#kv-chips`.
- **Clear (`ux-clear`).** Remove the keyvalue chip and unpress Public, click Clear: both back.
- **Reset (`ux-reset`).** ⚙️ → Reset to the built-in default: the summary reads "Mine, Stargazer". Reload: `EXPLORER_DEFAULT` is Mine + Stargazer, nothing else.
- **Graph (`ux-graph`).** Graph view, search `GRCh38_TP5`, `cy.zoom(2)`, note a node's position; search `GRCh38_TP53` (same entries): position and zoom unchanged.
- **Phone (`ux-phone`).** `resize_window` mobile, reload, check, then preset desktop.
- **Teardown.** Reset the default if a check left one saved; `union_dashboard.py teardown`: `live runs: []`.

### Evidence (2026-10-27, test account `u-pryce`, dashboard `7dcebf7`, then `cbb10cb`)

- `ux-search` (measured): typing v, a, r, i, a gave 84 → 70 → 5 → 4 → 4 of
  84; no request to the dashboard's origin.
- `ux-counts` (measured): 20 type chips, each equal to the list's rows of
  that type (anndata 24, verify_note 23, notebook 5, …).
- `ux-filter-by` (measured): `build = GRCh38` from the
  `cohort-dsql-192839_genotyped.vcf` card → 10 of 84, card kept.
- `ux-save` (measured): Mine + Public + Stargazer, `variants`,
  `build = GRCh38`, "NA" → "Saved as your default.", Settings read "Mine,
  Stargazer, Public; variants; build = GRCh38; 'NA'"; after reload all
  three sources pressed, the same chips and search, 2 of 90, one
  `/assets/list` request for the three sources.
- `ux-clear` (measured): chip removed and Public unpressed (2 of 84), Clear
  → 2 of 90 with the chip and Public back.
- `ux-reset` (measured): Reset → "Mine, Stargazer"; after reload Mine and
  Stargazer pressed, 84 of 84, no chips or search. A bad source posted from
  the page → 400.
- `ux-graph` (measured): node position and zoom 2 unchanged from
  `GRCh38_TP5` to `GRCh38_TP53` (8 of 84 both).
- `ux-phone` (measured): `scrollWidth` 375 at 375 px.
- Empty keyvalue (measured on `cbb10cb`): the card's empty `vqsr_mode` has
  no "filter by this"; the other seven do.
- Owner-only Mine, the 403 for a visitor and Public dropped when off: unit
  tests in `tests/unit/test_app.py` (measured), not driven on Union.
- Teardown (measured): `stopped: ['dashboard']`, `live runs: []`; every app
  in `u-pryce` STOPPED.
