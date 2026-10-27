---
title: Settings and cleanup move into the dashboard header
status: next
priority: normal
created: 2026-10-26
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

- [ ] Rename the notebook-setup dialog and its JS from `settings` to `setup`.
- [ ] Header: the broom and the Settings button; the footer loses the broom.
- [ ] The Settings `<dialog>`, built from the section's markup; the section goes.
- [ ] Tests in `tests/unit/test_app.py`: update the two Settings tests
      (`POST /settings`, and the saved value shown on the page) for the
      modal. The cleanup tests stay as they are.
- [ ] Docs: `docs/architecture/app.md` ("the dashboard's Settings section"
      becomes the Settings modal) and
      `.claude/reference/architecture/app_internals.md`.
- [ ] Verify in the built-in browser on the test account's Union dashboard:
      open Settings, save 60, reload and reopen (60 is shown), save 30 back;
      run the broom; the gear's setup editor still opens and saves; take a
      phone-width screenshot of the header. Tear down after.

## Design Decisions

1. **A modal, not a page.** There's one setting today, and a page would be a
   round trip for one number. Later settings go in the modal, starting with
   the explorer's default filter (ticket `explorer-filter-defaults`).
2. **The broom stays an icon button with its tooltip.** It's a maintenance
   action, so it sits beside Settings rather than becoming a labelled button.
