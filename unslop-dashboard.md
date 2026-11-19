---
title: unslop-dashboard
status: done
priority: normal
created: 2026-11-18
pr: 40
---

A design pass on the dashboard (StargazerBio/infra `app/templates/`, `app/static/explorer.js`) so it stops reading as generated UI: emoji controls become line icons, the floating glass card becomes a full-width app shell with a top bar, the violet and green washes and the background starfield go (the asset graph is the dashboard's sky), one quiet accent (the brand violet, rarely), off-white primary buttons, a near-grey ink ramp in place of GitHub's palette, spacing on a 4px grid, no hover lifts. Sections, copy and behavior stay. The login app's pages share `base.html` and change with it.

Direction: exact, nocturnal, a little playful; an observatory at night; the asset graph is the one rich moment; mono catalogue-style meta (filenames, short CIDs, the version) is the signature. Its sibling on the landing page is ticket unslop-landing.

## Outcome

Shipped in infra PR 40 (`b157d5e`, 2026-11-18), live on every dashboard
since the `2026.11.18.1` rollout. Verified on the devbox at 1440×900 and
375×812 against a real workspace (top bar, tiles, chips, graph, list,
detail card, upload panel, a launched notebook's controls), 406 tests
passing. Not checked then: the Settings, Publish and setup modals with
real input, and the login app's own pages. Its landing sibling, ticket
[[unslop-landing]], didn't reach `main` (see there).

Related: [[board]] [[unslop-landing]]
