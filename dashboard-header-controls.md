---
title: Settings and cleanup move into the dashboard header
status: review
priority: normal
created: 2026-10-26
pr: 94
blocked_by:
  - public-notebooks
---

The dashboard's Settings section becomes a Settings button in the header
that opens a modal, and the cleanup broom moves from the footer to sit
beside it. The home page is left with the Workspace section and the asset
explorer (tickets `unified-asset-explorer`, `explorer-filter-defaults`), and
the controls that are about the user rather than a notebook sit together at
the top.

Blocked by the tickets in review whose PRs edit
`app/templates/dashboard.html`.

## Current State

- `app/templates/dashboard.html`: a Settings `<section>` at the bottom of
  the page holds `#user-settings-form` (the save interval), shown only when
  `workspace_configured`. It posts to `POST /settings`.
- The footer holds the version, the alpha note and `#cleanup-btn`
  (`POST /workspace/cleanup`, "Clean up stopped notebooks"), whose tooltip
  turns into "Removed N" after a run.
- The header holds the brand, "View your runs ↗" and the avatar menu.
- A `<dialog id="settings-modal">` already exists, but it's the gear's
  notebook-setup editor, not the user's settings.

## Target State

- The header's end, left to right: the cleanup broom, a Settings button (a
  gear icon with a tooltip), "View your runs ↗", the avatar. The broom keeps
  its behavior and tooltip and shows on every dashboard, as now. Settings
  shows only when the workspace is configured, as the section does now.
- Settings opens a `<dialog>` with the section's text and form, its wording
  unchanged. Save posts to `/settings` as now, and the status line stays
  inside the modal. Escape, the backdrop and a Close button dismiss it.
- The gear's notebook-setup dialog is renamed `setup-modal` (its
  `settings-*` classes and JS names become `setup-*`), so "settings" means
  only the user's settings.
- At phone width the header wraps rather than overflowing, and the two icon
  buttons stay side by side.

## Pieces

- [x] Rename the notebook-setup dialog and its JS from `settings` to `setup`.
- [x] Header: the broom and the Settings button; the footer loses the broom.
- [x] The Settings `<dialog>`, built from the section's markup; the section goes.
- [x] Tests in `tests/unit/test_app.py`: update the two Settings tests
      (`POST /settings`, and the saved value shown on the page) for the
      modal. The cleanup tests stay as they are.
- [x] Docs: `docs/architecture/app.md` ("the dashboard's Settings section"
      becomes the Settings modal) and
      `.claude/reference/architecture/app_internals.md`.
- [x] Verify in the built-in browser on the test account's Union dashboard:
      open Settings, save 60, reload and reopen (60 is shown), save 30 back;
      run the broom; the gear's setup editor still opens and saves; take a
      phone-width screenshot of the header. Tear down after.

## Design Decisions

1. **A modal, not a page.** There's one setting today, and a page would be a
   round trip for one number. Later settings go in the modal, starting with
   the explorer's default filter (ticket `explorer-filter-defaults`).
2. **The broom stays an icon button with its tooltip.** It's a maintenance
   action, so it sits beside Settings rather than becoming a labelled button.
3. **Choices made in implementation.** The user's dialog takes the freed
   `settings-modal` id; both dialogs share a `.modal` surface. The header's
   icon buttons are avatar-sized and their tooltips drop below them. A
   dialog closes on a click outside its box only, not on its own padding.
   Opening Settings starts from the last saved value with the status cleared.

## Verification recipe: Settings and cleanup in the dashboard header

The dashboard header holds the cleanup broom and a Settings gear; Settings
opens a modal with the save-interval form, and the tile gear's setup editor
still works under its new name.

### Sub-features

- `hc-header`: the header's end reads broom, Settings, "View your runs ↗",
  avatar; no Settings section, no broom in the footer.
- `hc-settings`: Settings opens the modal; Save posts `/settings` and the
  status line shows inside it; a reload and reopen shows the saved value;
  Escape, the backdrop and Close dismiss it.
- `hc-broom`: the broom runs cleanup and its tooltip reads "Removed N".
- `hc-setup`: the tile gear opens the setup editor and Save retitles the
  tile in place.
- `hc-phone`: at phone width the header wraps without overflowing and the
  two icon buttons stay side by side.

### How to get to it (user POV)

- Dashboard header, top right: the 🧹 and ⚙️ buttons. The tile gear on any
  workspace notebook.

### Driving it

Preconditions: the `verify-stargazer` Union tenant preconditions; the
built-in browser pane signed in to the console as the test account.

- **Deploy.** With infra's `tenant.env` exported and `STARGAZER_TARGET=union`, `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy`; open the printed URL from the console page with `location.href`. The footer shows the branch's commit.
- **`hc-header`.** `[...document.querySelectorAll(".dash-header-end > *, .dash-header-icons > *")].map(e => e.id || e.className)` lists `cleanup-btn`, `settings-btn`, `dash-console`, `user-menu`; the section headings have no Settings.
- **`hc-settings`.** Note the current interval. Click ⚙️, enter 60, Save: "Saved. Notebooks you start from now on use it." inside the modal. Escape closes it; reopen shows 60 with the status empty; a click on the modal's padding keeps it open, one on the backdrop closes it. Reload, reopen: 60. Restore the noted value, then Close.
- **`hc-broom`.** Click 🧹: within a second it shows ✓ with tooltip "Removed N", and after 2 s 🧹 with its default tooltip.
- **`hc-setup`.** Hover a probe tile, click its gear: `#setup-modal` opens with `<slug>.py`. Change `main_description`, Save: the modal closes and the tile's blurb changes. Set it back the same way.
- **`hc-phone`.** `resize_window` to the mobile preset and to 320×700, reload, and compare the header items' rects: broom and gear share a row, and the header's right edge is inside the viewport. Reset to desktop.
- **Teardown.** `union_dashboard.py teardown`: `live runs: []`; `flyte get app` shows every app STOPPED.

### Gotchas

- At phone width the page's layout is 390 px wide whatever the viewport,
  because the asset panel's upload labels overflow; the header itself fits.

### Evidence (2026-10-27, commit 76fafeb, `u-pryce`)

- `hc-header`: header items `cleanup-btn, settings-btn, dash-console, user-menu`; sections Workflows, Workspace, Public notebooks, Tutorials, Assets; `footer #cleanup-btn` absent. Measured.
- `hc-settings`: interval was 5. Saved 60 → status inside the modal; after Escape `open=false`; reopened `value=60, status=""`; padding click `open=true`; backdrop click `open=false`; after reload `value=60`; restored 5 (Enter submits, status shown); Close → `open=false`. Measured.
- `hc-broom`: ✓ with tooltip "Removed 20", then back to 🧹 "Clean up stopped notebooks" and enabled. Measured.
- `hc-setup`: `build-probe-1026` gear → `setupOpen=true`, target `build-probe-1026.py`; Save → blurb "Header controls probe", then reverted to "Personal workspace notebook.". Measured.
- `hc-phone`: at the mobile preset one row (broom x 87, gear x 131, both y 51; scrollWidth = viewport). At 320 px the header wraps: brand, then broom and gear (y 101, side by side) with the runs link, then the avatar (y 153); header right edge 287. Measured.
- Teardown: `stopped: ['dashboard']`, `live runs: []`, all six apps in `u-pryce` STOPPED. Measured.
