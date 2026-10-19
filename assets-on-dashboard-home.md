---
title: The asset browser moves onto the dashboard home
status: doing
priority: high
created: 2026-10-18
---

**The dashboard becomes an asset explorer and notebook launcher** (decided
2026-10-16). Its home page shows the user's assets. Their notebooks keep a
section of their own, and launch from there as they do now. Every other
asset is in the graph and list browser that the separate asset page has
today, with upload, download and metadata edits. The separate `/assets` page
and its link in the avatar menu go.

Split out of `asset-manager-on-index` on 2026-10-18, which puts the Private
tab on the user's own index and store first. It waits on that and on
`save-whole-workspace` (PR #41), since all three change the dashboard's
templates.

Ticket `public-notebooks` makes a published notebook an asset. Whichever of
this ticket and `public-notebooks` lands second makes the browser leave out
`asset=notebook`, since notebooks have their own section.

## Pieces

- [ ] Move the browser onto the dashboard's home page, below the notebook
      sections: the Graph and List views, the detail card and the upload
      panel. The routes stay under `/assets/*`. The `/assets` page and its
      link in the avatar menu go.
- [ ] If `public-notebooks` has landed, the browser leaves out
      `asset=notebook` rows. Test it: a notebook row in the index → it isn't
      in the browser's listing.
- [ ] Docs: `docs/architecture/app.md` and
      `.opencode/reference/architecture/app_internals.md`, the Asset Manager
      section as part of the dashboard home rather than a page of its own.
- [ ] Verify on the test account's Union dashboard: on the home page,
      upload, list, download and edit, and the notebook tiles still launch.
      Stop every app the check started.
